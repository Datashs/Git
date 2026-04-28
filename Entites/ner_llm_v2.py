"""
ner_llm_v2.py — Extraction d'entités nommées, positions et section_type (v2)
=============================================================================

Version 2 — intègre les décisions de l'addendum au CONTEXTE_PROJET :
  - Format de sortie LLM : objet JSON {section_type, entities, positions}
    au lieu du tableau plat de la v1
  - Extraction simultanée des positions argumentaires (séances plénières)
  - Détection du section_type : regex sur le titre en premier,
    LLM en fallback si le titre est ambigu
  - Le champ section_type est écrit dans sections.json en place

Position dans la chaîne de traitement :
    [ocr_fix.py] --> sections_fixed.json
                          |
                    [ner_llm_v2.py]
                          |
              +-----------+----------+
              |                      |
          entities.json         positions.json
          (versionné)           (intermédiaire)

Entrée  : sections.json ou sections_fixed.json
Sortie  : entities.json      — entités NER (versionné dans git)
          positions.json     — positions argumentaires (non versionné)
          ner_report_v2.txt  — rapport de traitement

Différences avec ner_llm.py (v1) :
  - parse_llm_response() attend un objet, pas un tableau
  - Nouvelle fonction detect_section_type_regex() — regex sur le titre
  - Le prompt reçoit section_type_hint (résultat de la regex ou "inconnu")
  - Les positions sont collectées séparément et écrites dans positions.json
  - sections.json est mis à jour avec le section_type détecté

Usage :
    python ner_llm_v2.py
    python ner_llm_v2.py --sections-file corpus/annuaire_1877/sections_fixed.json
    python ner_llm_v2.py --section-ids s0003 s0007
    python ner_llm_v2.py --dry-run

Dépendances :
    python-dotenv>=1.0
    anthropic>=0.20
    openai>=1.0

Adaptation à un autre corpus :
    1. Ajuster SECTION_TYPE_PATTERNS pour vos titres de sections
    2. Modifier PROMPT_FILE pour pointer vers votre prompt métier
    3. Les conventions de canonicalisation et les catégories sont dans le prompt
"""

import os
import re
import sys
import json
import time
import argparse
import textwrap
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

# ==============================================================================
# PARAMETRES
# ==============================================================================

SECTIONS_FILE  = os.getenv("SECTIONS_FILE",  "corpus/annuaire_1877/sections_fixed.json")
ENTITIES_FILE  = os.getenv("ENTITIES_FILE",  "corpus/annuaire_1877/entities.json")
POSITIONS_FILE = os.getenv("POSITIONS_FILE", "corpus/annuaire_1877/positions.json")
REPORT_FILE    = os.getenv("REPORT_FILE",    "corpus/annuaire_1877/ner_report_v2.txt")
PROMPT_FILE    = os.getenv("NER_PROMPT_FILE","prompts/ner_v2.txt")

MIN_WORD_COUNT    = int(os.getenv("NER_MIN_WORD_COUNT", "10"))
LEVELS_TO_PROCESS = [int(x) for x in os.getenv("NER_LEVELS", "1,2,3,4").split(",")]

MAX_RETRIES           = int(os.getenv("NER_MAX_RETRIES",          "3"))
RETRY_DELAY_SECONDS   = float(os.getenv("NER_RETRY_DELAY",        "5.0"))
INTER_SECTION_DELAY   = float(os.getenv("NER_INTER_SECTION_DELAY","1.0"))
MAX_TOKENS            = int(os.getenv("NER_MAX_TOKENS",           "4096"))
TEMPERATURE           = float(os.getenv("NER_TEMPERATURE",        "0.0"))

LLM_PROVIDER    = os.getenv("LLM_PROVIDER",    "anthropic").lower()
ANTHROPIC_KEY   = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-5")
OPENAI_KEY      = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL    = os.getenv("OPENAI_MODEL",    "gpt-4o")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL",    "mistral")

# ==============================================================================
# DETECTION DU SECTION_TYPE PAR REGEX
# ==============================================================================

# Patterns ordonnes par priorite (premier match gagne).
# Chaque entree : (section_type, [patterns regex sur le titre]).
#
# Adaptation a un autre corpus :
#   Remplacer ces patterns par ceux qui correspondent a vos titres.
#   La valeur de retour doit etre l'une des 8 valeurs VALID_SECTION_TYPES.

SECTION_TYPE_PATTERNS: list[tuple[str, list[str]]] = [
    ("seance_pleniere", [
        r"s[eé]ance",
        r"proc[eè]s.verbal",
        r"session.*plen",
        r"plen.*session",
        r"r[eé]union",
        r"assembl[eé]e",
    ]),
    ("notice_biographique", [
        r"notice",
        r"biograph",
        r"n[eé]crolog",
        r"membre.*d[eé]c[eè]d[eé]",
        r"in memoriam",
    ]),
    ("texte_traite", [
        r"convention",
        r"trait[eé]",
        r"d[eé]claration",
        r"protocole",
        r"r[eè]glement.*adopt[eé]",
        r"texte.*adopt[eé]",
    ]),
    ("tableau_chronologique", [
        r"tableau",
        r"liste.*membre",
        r"membre.*liste",
        r"chronolog",
    ]),
    ("bibliographie", [
        r"bibliograph",
        r"publications?",
        r"ouvrages?",
        r"travaux.*publi[eé]s",
    ]),
    ("statuts", [
        r"statuts?",
        r"r[eè]glement int[eé]rieur",
        r"r[eè]gles de proc[eé]dure",
    ]),
    ("rapport", [
        r"rapport",
        r"rapporteur",
        r"expos[eé] des motifs",
    ]),
]


def detect_section_type_regex(title: str) -> str | None:
    """
    Tente de deduire le section_type depuis le titre par regex.

    Retourne la valeur section_type si un pattern correspond,
    None si aucun pattern ne correspond (le LLM decidera seul).

    L'ordre des patterns dans SECTION_TYPE_PATTERNS est la priorite :
    si un titre pourrait matcher plusieurs types, le premier gagne.
    Ajuster l'ordre pour refleter les ambiguites de votre corpus.
    """
    title_lower = title.lower()
    for section_type, patterns in SECTION_TYPE_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, title_lower):
                return section_type
    return None

# ==============================================================================
# PROMPT
# ==============================================================================

PROMPT_FALLBACK = """
Tu es un assistant NER pour textes juridiques du XIXe siecle (francais).
Analyse le texte ci-dessous et retourne UNIQUEMENT un objet JSON valide,
sans texte autour, sans Markdown.

Categories NER : PER, ORG, LOC, DATE, ACTE (+ acte_type obligatoire),
SESSION, FONCTION.

Types de section : seance_pleniere | notice_biographique | texte_traite |
tableau_chronologique | bibliographie | statuts | rapport | autre

Types de positions (seances plenieres uniquement) :
vote_pour | vote_contre | reserve | proposition | abstention | rapport

Format attendu :
{
  "section_type": "...",
  "entities": [
    {"surface":"...","canonical":"...","label":"...","start_char":0,"end_char":0,"confidence":0.0}
  ],
  "positions": [
    {"acteur":"...","type":"...","objet":"...","texte_source":"..."}
  ]
}

Canonicalisation : PER -> "Nom (Prenom)", LOC -> nom officiel francais,
ACTE -> titre complet, FONCTION -> forme nominale sans article.

Titre : {section_title}
ID    : {section_id}
Niveau: {section_level}
Indice regex : {section_type_hint}

Texte :
{section_text}
""".strip()


def load_prompt_template() -> str:
    """
    Charge le prompt depuis le fichier externe, avec fallback inline.
    Meme logique que la v1 — voir ner_llm.py pour la justification.
    """
    prompt_path = Path(PROMPT_FILE)
    if prompt_path.exists():
        try:
            template = prompt_path.read_text(encoding="utf-8")
            print(f"[prompt] Charge depuis {PROMPT_FILE}")
            return template
        except OSError as e:
            print(f"[prompt] Impossible de lire {PROMPT_FILE} : {e}")
    else:
        print(f"[prompt] {PROMPT_FILE} introuvable — fallback inline.")
    return PROMPT_FALLBACK


def build_prompt(template: str, section: dict, type_hint: str) -> str:
    """
    Injecte les donnees de la section dans le template.

    Nouveaute v2 : le champ {section_type_hint} transmet le resultat
    de la regex au LLM. Si la regex n'a rien trouve, on passe "inconnu"
    pour signaler au LLM qu'il doit decider sans aide prealable.
    """
    MAX_TEXT_CHARS = 12_000
    raw_text = section.get("raw_text", "")
    if len(raw_text) > MAX_TEXT_CHARS:
        raw_text = raw_text[:MAX_TEXT_CHARS] + "\n[... texte tronque pour longueur ...]"

    return template.format(
        section_title=section.get("title", "(sans titre)"),
        section_id=section.get("section_id", "?"),
        section_level=section.get("level", "?"),
        section_type_hint=type_hint,
        section_text=raw_text,
    )

# ==============================================================================
# CLIENTS LLM
# ==============================================================================

def call_anthropic(prompt: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    message = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def call_openai(prompt: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def call_ollama(prompt: str) -> str:
    from openai import OpenAI
    base = OLLAMA_BASE_URL
    if not base.endswith("/v1"):
        base = base + "/v1"
    client = OpenAI(api_key="ollama", base_url=base)
    response = client.chat.completions.create(
        model=OLLAMA_MODEL,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def call_llm(prompt: str) -> str:
    if LLM_PROVIDER == "anthropic":
        return call_anthropic(prompt)
    elif LLM_PROVIDER == "openai":
        return call_openai(prompt)
    elif LLM_PROVIDER == "ollama":
        return call_ollama(prompt)
    else:
        raise ValueError(f"Fournisseur inconnu : '{LLM_PROVIDER}'")

# ==============================================================================
# PARSING ET VALIDATION
# ==============================================================================

VALID_LABELS = {"PER", "ORG", "LOC", "DATE", "ACTE", "SESSION", "FONCTION"}

VALID_ACTE_TYPES = {
    "traite_multilateral", "traite_bilateral", "loi_nationale",
    "acte_sans_force", "texte_doctrinal", "precedent_arbitral",
}

VALID_SECTION_TYPES = {
    "seance_pleniere", "notice_biographique", "texte_traite",
    "tableau_chronologique", "bibliographie", "statuts", "rapport", "autre",
}

VALID_POSITION_TYPES = {
    "vote_pour", "vote_contre", "reserve",
    "proposition", "abstention", "rapport",
}

REQUIRED_ENTITY_FIELDS   = {"surface", "canonical", "label", "start_char", "end_char", "confidence"}
REQUIRED_POSITION_FIELDS = {"acteur", "type", "objet", "texte_source"}


def strip_to_object(text: str) -> str:
    """
    Extrait le premier objet JSON {...} du texte brut retourne par le LLM.

    Strategie : chercher la premiere accolade ouvrante et la derniere
    fermante. Robuste aux balises Markdown et aux textes autour.
    """
    text = text.strip()
    start = text.find("{")
    end   = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    lines = [l for l in text.splitlines() if not l.strip().startswith("```")]
    return "\n".join(lines).strip()


def validate_entity(entity: dict, section_text: str) -> tuple[bool, str]:
    """
    Valide une entite. Identique a la v1, avec la meme tolerance sur les offsets.
    Voir ner_llm.py pour la justification des choix.
    """
    missing = REQUIRED_ENTITY_FIELDS - entity.keys()
    if missing:
        return False, f"Champs manquants : {missing}"

    label = entity.get("label", "")
    if label not in VALID_LABELS:
        return False, f"Label invalide : '{label}'"

    try:
        start = int(entity["start_char"])
        end   = int(entity["end_char"])
        conf  = float(entity["confidence"])
    except (ValueError, TypeError) as e:
        return False, f"Type incorrect : {e}"

    n = len(section_text)
    if start < 0 or end < 0:
        return False, "Offsets negatifs"
    if start >= end:
        return False, f"start_char ({start}) >= end_char ({end})"
    if end > n + 50:
        return False, f"end_char ({end}) depasse longueur texte ({n})"

    if end <= n:
        extracted = section_text[start:end]
        surface   = entity.get("surface", "")
        if extracted.strip() != surface.strip():
            entity["_offset_warning"] = (
                f"surface='{surface[:30]}' != texte[{start}:{end}]='{extracted[:30]}'"
            )

    if label == "ACTE":
        acte_type = entity.get("acte_type", "")
        if acte_type not in VALID_ACTE_TYPES:
            return False, f"acte_type invalide : '{acte_type}'"

    entity["confidence"] = max(0.0, min(1.0, conf))
    return True, ""


def validate_position(pos: dict) -> tuple[bool, str]:
    """
    Valide une position argumentaire.

    Permissif sur objet et texte_source (peuvent etre courts) :
    l'essentiel est acteur + type.
    """
    missing = REQUIRED_POSITION_FIELDS - pos.keys()
    if missing:
        return False, f"Champs manquants : {missing}"

    pos_type = pos.get("type", "")
    if pos_type not in VALID_POSITION_TYPES:
        return False, f"type de position invalide : '{pos_type}'"

    if not pos.get("acteur", "").strip():
        return False, "acteur vide"

    return True, ""


def parse_llm_response(
    raw: str, section: dict
) -> tuple[str, list[dict], list[dict], list[str]]:
    """
    Parse la reponse v2 du LLM : objet JSON contenant section_type,
    entities et positions.

    Retourne (section_type, entites_valides, positions_valides, erreurs).

    Difference cle avec la v1 : on attend un objet {}, pas un tableau [].
    strip_to_object() remplace strip_markdown_fences() de la v1.

    On conserve toutes les entites valides meme si l'objet contient des
    erreurs partielles — maximise la recuperation d'information.
    """
    section_text = section.get("raw_text", "")
    section_id   = section.get("section_id", "?")
    errors = []

    clean = strip_to_object(raw)

    try:
        data = json.loads(clean)
    except json.JSONDecodeError as e:
        errors.append(f"JSONDecodeError : {e}")
        return "autre", [], [], errors

    if not isinstance(data, dict):
        errors.append(f"Attendu un objet, recu {type(data).__name__}")
        return "autre", [], [], errors

    # --- section_type ---------------------------------------------------------
    section_type = data.get("section_type", "autre")
    if section_type not in VALID_SECTION_TYPES:
        errors.append(f"section_type invalide : '{section_type}' -> 'autre'")
        section_type = "autre"

    # --- entities -------------------------------------------------------------
    entities_raw   = data.get("entities", [])
    entities_valid = []

    if not isinstance(entities_raw, list):
        errors.append(f"'entities' n'est pas une liste")
    else:
        for i, entity in enumerate(entities_raw):
            if not isinstance(entity, dict):
                errors.append(f"Entite #{i} n'est pas un dict")
                continue
            ok, reason = validate_entity(entity, section_text)
            if ok:
                entity["section_id"] = section_id
                entities_valid.append(entity)
            else:
                errors.append(f"Entite #{i} rejetee ({reason}) : {entity.get('surface','?')!r}")

    # --- positions ------------------------------------------------------------
    positions_raw   = data.get("positions", [])
    positions_valid = []

    if not isinstance(positions_raw, list):
        errors.append("'positions' n'est pas une liste")
    else:
        for i, pos in enumerate(positions_raw):
            if not isinstance(pos, dict):
                errors.append(f"Position #{i} n'est pas un dict")
                continue
            ok, reason = validate_position(pos)
            if ok:
                pos["section_id"] = section_id
                positions_valid.append(pos)
            else:
                errors.append(f"Position #{i} rejetee ({reason})")

    return section_type, entities_valid, positions_valid, errors

# ==============================================================================
# TRAITEMENT D'UNE SECTION
# ==============================================================================

def process_section(
    section: dict,
    prompt_template: str,
    dry_run: bool = False,
) -> tuple[str, list[dict], list[dict], dict]:
    """
    Traite une section : detection regex du section_type, construction du
    prompt, appel LLM avec retry, parsing et validation.

    Retourne (section_type, entites, positions, metadonnees).

    La regex fournit un hint au LLM mais ne decide pas : le LLM a toujours
    le dernier mot. Le hint accelere le traitement des cas evidents et aide
    sur les sections a titre ambigu. Les discordances regex/LLM sont tracees
    dans le rapport — utile pour affiner les patterns regex.
    """
    section_id = section.get("section_id", "?")
    title      = section.get("title", "")

    type_hint = detect_section_type_regex(title) or "inconnu"
    prompt    = build_prompt(prompt_template, section, type_hint)

    meta = {
        "section_id":      section_id,
        "title":           title,
        "level":           section.get("level"),
        "type_hint_regex": type_hint,
        "section_type":    None,
        "attempts":        0,
        "status":          "pending",
        "entity_count":    0,
        "position_count":  0,
        "errors":          [],
        "warnings":        [],
    }

    if dry_run:
        print(f"\n{'='*60}")
        print(f"DRY RUN — {section_id} | hint regex : {type_hint}")
        print(f"{'='*60}")
        print(textwrap.shorten(prompt, width=800, placeholder=" [...]"))
        meta["status"] = "dry_run"
        return type_hint, [], [], meta

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        meta["attempts"] = attempt
        try:
            raw_response = call_llm(prompt)
            section_type, entities, positions, errors = parse_llm_response(
                raw_response, section
            )

            if errors:
                meta["errors"].extend(errors)

            for ent in entities:
                w = ent.pop("_offset_warning", None)
                if w:
                    meta["warnings"].append(w)

            # Succes si le parsing a produit un objet valide (meme vide)
            if section_type is not None:
                meta["status"]         = "ok"
                meta["section_type"]   = section_type
                meta["entity_count"]   = len(entities)
                meta["position_count"] = len(positions)
                return section_type, entities, positions, meta

            last_error = f"Parsing echoue ({len(errors)} erreurs)"

        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            meta["errors"].append(f"Tentative {attempt}/{MAX_RETRIES} : {last_error}")

        if attempt < MAX_RETRIES:
            print(
                f"  [retry {attempt}/{MAX_RETRIES}] {section_id} — "
                f"{str(last_error)[:80]} — attente {RETRY_DELAY_SECONDS}s"
            )
            time.sleep(RETRY_DELAY_SECONDS)

    meta["status"] = "failed"
    meta["errors"].append(f"Abandon apres {MAX_RETRIES} tentatives.")
    print(f"  [ECHEC] {section_id} abandonnee.")
    return type_hint, [], [], meta

# ==============================================================================
# RAPPORT
# ==============================================================================

def build_report(
    all_meta:         list[dict],
    all_entities:     list[dict],
    all_positions:    list[dict],
    sections_skipped: list[dict],
    elapsed:          float,
) -> str:
    """
    Rapport v2 : inclut la repartition des section_types detectes,
    le nombre de positions par type, et les discordances regex/LLM.

    Les discordances sont particulierement utiles pour affiner les patterns
    regex : si le LLM corrige souvent un type donne, c'est que les patterns
    correspondants sont trop larges ou trop etroits.
    """
    model_name = (
        ANTHROPIC_MODEL if LLM_PROVIDER == "anthropic"
        else OPENAI_MODEL if LLM_PROVIDER == "openai"
        else OLLAMA_MODEL
    )
    lines = []
    lines.append("=" * 70)
    lines.append("RAPPORT NER v2 — ner_llm_v2.py")
    lines.append(f"Date        : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Fournisseur : {LLM_PROVIDER} / {model_name}")
    lines.append(f"Duree       : {elapsed:.1f}s")
    lines.append("=" * 70)

    n_ok     = sum(1 for m in all_meta if m["status"] == "ok")
    n_failed = sum(1 for m in all_meta if m["status"] == "failed")
    n_dry    = sum(1 for m in all_meta if m["status"] == "dry_run")

    lines.append(f"\nSECTIONS TRAITEES : {len(all_meta)}")
    lines.append(f"  Succes           : {n_ok}")
    lines.append(f"  Echecs           : {n_failed}")
    lines.append(f"  Dry run          : {n_dry}")
    lines.append(f"  Ignorees (filtre): {len(sections_skipped)}")
    lines.append(f"\nENTITES EXTRAITES  : {len(all_entities)}")
    lines.append(f"POSITIONS EXTRAITES: {len(all_positions)}")

    by_label: dict[str, int] = {}
    for e in all_entities:
        by_label[e["label"]] = by_label.get(e["label"], 0) + 1
    if by_label:
        lines.append("\nREPARTITION PAR LABEL :")
        for label in sorted(by_label):
            lines.append(f"  {label:<12} {by_label[label]:>5}")

    by_acte: dict[str, int] = {}
    for e in all_entities:
        if e.get("label") == "ACTE":
            t = e.get("acte_type", "?")
            by_acte[t] = by_acte.get(t, 0) + 1
    if by_acte:
        lines.append("\nSous-types ACTE :")
        for t in sorted(by_acte):
            lines.append(f"  {t:<30} {by_acte[t]:>4}")

    by_stype: dict[str, int] = {}
    for m in all_meta:
        st = m.get("section_type") or "non_defini"
        by_stype[st] = by_stype.get(st, 0) + 1
    if by_stype:
        lines.append("\nSECTION_TYPES DETECTES :")
        for st in sorted(by_stype):
            lines.append(f"  {st:<30} {by_stype[st]:>4}")

    discordances = [
        m for m in all_meta
        if m.get("type_hint_regex") not in ("inconnu", None)
        and m.get("section_type") not in (None, m.get("type_hint_regex"))
    ]
    if discordances:
        lines.append(f"\nDISCORDANCES REGEX <-> LLM ({len(discordances)}) :")
        for m in discordances[:15]:
            lines.append(
                f"  {m['section_id']} : regex={m['type_hint_regex']}"
                f" -> LLM={m['section_type']} | {m['title'][:50]}"
            )
        if len(discordances) > 15:
            lines.append(f"  ... et {len(discordances)-15} autres")

    by_postype: dict[str, int] = {}
    for p in all_positions:
        pt = p.get("type", "?")
        by_postype[pt] = by_postype.get(pt, 0) + 1
    if by_postype:
        lines.append("\nPOSITIONS PAR TYPE :")
        for pt in sorted(by_postype):
            lines.append(f"  {pt:<20} {by_postype[pt]:>4}")

    failed = [m for m in all_meta if m["status"] == "failed"]
    if failed:
        lines.append(f"\nSECTIONS EN ECHEC ({len(failed)}) :")
        for m in failed:
            lines.append(f"  {m['section_id']} — {m['title'][:60]}")
            for err in m["errors"][-2:]:
                lines.append(f"    > {err[:100]}")

    warnings = [(m["section_id"], w) for m in all_meta for w in m.get("warnings", [])]
    if warnings:
        lines.append(f"\nAVERTISSEMENTS OFFSET ({len(warnings)}) :")
        for sid, w in warnings[:20]:
            lines.append(f"  {sid}: {w[:100]}")
        if len(warnings) > 20:
            lines.append(f"  ... et {len(warnings)-20} autres")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)

# ==============================================================================
# CHARGEMENT / SAUVEGARDE
# ==============================================================================

def load_sections(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        sections = json.load(f)
    for s in sections:
        if "word_count" not in s or s["word_count"] is None:
            text = s.get("raw_text", "")
            s["word_count"] = len(text.split()) if text.strip() else 0
    return sections


def load_existing(path: str) -> list[dict]:
    p = Path(path)
    if p.exists():
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return []


def save_json(path: str, data: list[dict]) -> None:
    """Ecriture atomique via fichier temporaire."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(p)


def save_report(path: str, report: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(report, encoding="utf-8")


def update_section_types(sections_path: str, type_map: dict[str, str]) -> None:
    """
    Met a jour le champ section_type dans sections.json pour toutes les
    sections traitees. Modification en place : sections.json est la source
    de verite structurelle et section_type lui appartient naturellement.
    """
    try:
        with open(sections_path, encoding="utf-8") as f:
            sections = json.load(f)
        updated = 0
        for s in sections:
            sid = s.get("section_id", "")
            if sid in type_map:
                s["section_type"] = type_map[sid]
                updated += 1
        with open(sections_path, "w", encoding="utf-8") as f:
            json.dump(sections, f, ensure_ascii=False, indent=2)
        print(f"[OK] section_type mis a jour pour {updated} sections dans {sections_path}")
    except Exception as e:
        print(f"[WARN] Impossible de mettre a jour section_type : {e}")

# ==============================================================================
# FILTRAGE
# ==============================================================================

def should_process(section: dict) -> bool:
    level = section.get("level")
    wc    = section.get("word_count", 0) or 0
    return level in LEVELS_TO_PROCESS and wc >= MIN_WORD_COUNT

# ==============================================================================
# POINT D'ENTREE
# ==============================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NER v2 — entites, positions et section_type")
    parser.add_argument("--sections-file",  default=SECTIONS_FILE)
    parser.add_argument("--entities-file",  default=ENTITIES_FILE)
    parser.add_argument("--positions-file", default=POSITIONS_FILE)
    parser.add_argument("--section-ids", nargs="+", metavar="ID")
    parser.add_argument("--dry-run",    action="store_true")
    parser.add_argument("--overwrite",  action="store_true",
                        help="Reextraire meme si la section est deja dans entities.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    model_name = (
        ANTHROPIC_MODEL if LLM_PROVIDER == "anthropic"
        else OPENAI_MODEL if LLM_PROVIDER == "openai"
        else OLLAMA_MODEL
    )

    print("=" * 60)
    print("ner_llm_v2.py — NER + positions + section_type")
    print(f"Fournisseur : {LLM_PROVIDER} / {model_name}")
    print(f"Sections    : {args.sections_file}")
    print(f"Entites     : {args.entities_file}")
    print(f"Positions   : {args.positions_file}")
    if args.dry_run:
        print("MODE DRY RUN")
    print("=" * 60)

    prompt_template = load_prompt_template()

    try:
        sections = load_sections(args.sections_file)
    except FileNotFoundError:
        print(f"[ERREUR] Fichier introuvable : {args.sections_file}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[ERREUR] JSON invalide : {e}")
        sys.exit(1)

    print(f"\n{len(sections)} sections chargees")

    existing_entities  = load_existing(args.entities_file)
    existing_positions = load_existing(args.positions_file)
    existing_ids = {e["section_id"] for e in existing_entities}
    print(f"{len(existing_entities)} entites existantes | {len(existing_positions)} positions existantes")

    sections_to_process = []
    sections_skipped    = []

    for section in sections:
        sid = section.get("section_id", "")
        if args.section_ids and sid not in args.section_ids:
            continue
        if not args.overwrite and sid in existing_ids:
            sections_skipped.append(section)
            continue
        if should_process(section):
            sections_to_process.append(section)
        else:
            sections_skipped.append(section)

    print(f"{len(sections_to_process)} sections a traiter | {len(sections_skipped)} ignorees")

    if not sections_to_process:
        print("\nRien a traiter. Utilisez --overwrite pour reextraire.")
        return

    all_new_entities:  list[dict] = []
    all_new_positions: list[dict] = []
    all_meta:          list[dict] = []
    type_map:          dict[str, str] = {}
    start_time = time.time()

    for i, section in enumerate(sections_to_process, 1):
        sid   = section.get("section_id", "?")
        title = section.get("title", "")[:50]
        wc    = section.get("word_count", 0)
        print(f"\n[{i:>3}/{len(sections_to_process)}] {sid} — {title} ({wc} mots)")

        section_type, entities, positions, meta = process_section(
            section, prompt_template, dry_run=args.dry_run
        )

        all_new_entities.extend(entities)
        all_new_positions.extend(positions)
        all_meta.append(meta)
        if section_type:
            type_map[sid] = section_type

        print(
            f"  -> type={section_type} | "
            f"{meta['entity_count']} entites | "
            f"{meta['position_count']} positions | "
            f"{meta['attempts']} tentative(s) [{meta['status']}]"
        )

        if i % 10 == 0 and not args.dry_run:
            save_json(args.entities_file,  existing_entities  + all_new_entities)
            save_json(args.positions_file, existing_positions + all_new_positions)
            print(f"  [checkpoint] {len(all_new_entities)} entites, {len(all_new_positions)} positions")

        if INTER_SECTION_DELAY > 0 and not args.dry_run:
            time.sleep(INTER_SECTION_DELAY)

    elapsed = time.time() - start_time

    if not args.dry_run:
        processed_ids  = {m["section_id"] for m in all_meta}
        preserved_ent  = [e for e in existing_entities  if e["section_id"] not in processed_ids]
        preserved_pos  = [p for p in existing_positions if p["section_id"] not in processed_ids]
        final_entities  = preserved_ent + all_new_entities
        final_positions = preserved_pos + all_new_positions

        save_json(args.entities_file,  final_entities)
        save_json(args.positions_file, final_positions)
        print(f"\n[OK] {len(final_entities)} entites -> {args.entities_file}")
        print(f"[OK] {len(final_positions)} positions -> {args.positions_file}")

        if type_map:
            update_section_types(args.sections_file, type_map)

        report = build_report(all_meta, all_new_entities, all_new_positions, sections_skipped, elapsed)
        save_report(REPORT_FILE, report)
        print(f"[OK] Rapport -> {REPORT_FILE}")
        print("\n" + report)
    else:
        print(f"\n[DRY RUN] {len(sections_to_process)} sections auraient ete traitees.")


if __name__ == "__main__":
    main()
