"""
ocr_fix.py — Détection et correction des variantes OCR dans le texte de travail
================================================================================

Position dans la chaîne de traitement :
    original.txt  (copié une fois en _work.txt manuellement ou par init_volume.py)
         |
    [ocr_fix.py]  → corrections_candidates.tsv  (à valider dans un tableur)
         |
    [apply_corrections.py]  → _work.txt modifié + corrections.json
         |
    structure_annuaire.py  → sections.json
         |
    ner_llm_v2.py

Rôle :
    1. Extrait tous les tokens candidats à être des noms propres (majuscule,
       longueur > MIN_TOKEN_LENGTH) depuis _work.txt.
    2. Clusterise ces tokens par similarité (rapidfuzz, distance Levenshtein)
       pour regrouper les variantes probables d'un même nom.
    3. Soumet les clusters au LLM en batch pour valider : même entité ?
       quelle forme canonique retenir ?
    4. Exporte le résultat dans corrections_candidates.tsv pour validation
       humaine dans un tableur (LibreOffice Calc, Excel).

Ce script ne modifie PAS _work.txt — c'est apply_corrections.py qui le fait,
après validation humaine du TSV.

Pourquoi agir sur _work.txt plutôt que sur sections.json ?
    Le texte de travail versionné dans git est la source de vérité éditoriale.
    Chaque correction est un commit git traçable. Les fichiers dérivés
    (sections.json, entities.json) sont recalculables depuis _work.txt.
    original.txt (archive Gallica) n'est jamais touché.

Usage :
    python ocr_fix.py
    python ocr_fix.py --work-file corpus/annuaire_1877/annuaire_1877_work.txt
    python ocr_fix.py --min-score 0.80   # seuil de similarité plus strict
    python ocr_fix.py --dry-run          # affiche les clusters sans appel LLM

Dépendances :
    python-dotenv>=1.0
    rapidfuzz>=3.0
    anthropic>=0.20   (ou openai)

Adaptation à un autre corpus :
    1. Ajuster MIN_TOKEN_LENGTH et MAX_LEVENSHTEIN_DIST selon la densité
       de noms propres de votre corpus.
    2. Modifier BATCH_SIZE si votre LLM a une fenêtre de contexte plus petite.
    3. Le prompt de validation LLM est dans PROMPT_VALIDATE_CLUSTERS — le
       modifier pour vos conventions de canonicalisation.
"""

import os
import re
import sys
import csv
import json
import time
import argparse
import unicodedata
from pathlib import Path
from collections import Counter
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

# ==============================================================================
# PARAMÈTRES
# ==============================================================================

# --- Chemins ------------------------------------------------------------------

WORK_FILE        = os.getenv("WORK_FILE",        "corpus/annuaire_1877/annuaire_1877_work.txt")
CANDIDATES_TSV   = os.getenv("CANDIDATES_TSV",   "corpus/annuaire_1877/corrections_candidates.tsv")
CLUSTERS_JSON    = os.getenv("CLUSTERS_JSON",     "corpus/annuaire_1877/clusters_raw.json")

# --- Extraction des tokens ----------------------------------------------------

# Longueur minimale d'un token pour être considéré comme nom propre candidat.
# 4 évite les abréviations courantes (M., Dr., etc.) tout en capturant les
# noms courts (Gand, Twiss, Gent...).
MIN_TOKEN_LENGTH = int(os.getenv("OCR_MIN_TOKEN_LENGTH", "4"))

# Nombre minimal d'occurrences dans le texte pour qu'un token soit inclus
# dans le clustering. Filtrer les hapax réduit le bruit sur les gros volumes.
MIN_OCCURRENCES  = int(os.getenv("OCR_MIN_OCCURRENCES", "1"))

# --- Clustering ---------------------------------------------------------------

# Distance de Levenshtein maximale pour regrouper deux tokens dans le même
# cluster. 2 est adapté aux erreurs OCR courantes (substitution d'un caractère,
# insertion d'un espace). Augmenter à 3 pour des textes très bruités.
MAX_LEVENSHTEIN_DIST = int(os.getenv("OCR_MAX_LEVENSHTEIN", "2"))

# Score de similarité minimal (0–100) pour la comparaison rapidfuzz.
# Équivalent approximatif de MAX_LEVENSHTEIN_DIST mais en pourcentage.
# rapidfuzz.fuzz.ratio retourne 0–100 ; 85 correspond à ~1-2 chars différents
# sur un nom de 8-12 chars.
MIN_SIMILARITY_SCORE = int(os.getenv("OCR_MIN_SIMILARITY", "85"))

# Taille maximale d'un cluster. Les clusters trop grands (> 10 variantes)
# sont souvent des faux positifs (noms courts très communs). On les signale
# dans le rapport mais on les inclut quand même dans le TSV.
MAX_CLUSTER_SIZE = int(os.getenv("OCR_MAX_CLUSTER_SIZE", "10"))

# --- LLM batch ----------------------------------------------------------------

# Nombre de clusters envoyés au LLM en un seul appel.
# 30-50 est un bon compromis entre coût et qualité pour claude-opus-*.
# Réduire si le LLM tronque sa réponse.
BATCH_SIZE = int(os.getenv("OCR_BATCH_SIZE", "40"))

# Délai en secondes entre deux batchs LLM.
BATCH_DELAY = float(os.getenv("OCR_BATCH_DELAY", "2.0"))

MAX_TOKENS  = int(os.getenv("OCR_MAX_TOKENS",  "4096"))
TEMPERATURE = float(os.getenv("OCR_TEMPERATURE", "0.0"))

# --- Fournisseurs LLM ---------------------------------------------------------

LLM_PROVIDER    = os.getenv("LLM_PROVIDER",    "anthropic").lower()
ANTHROPIC_KEY   = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-5")
OPENAI_KEY      = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL    = os.getenv("OPENAI_MODEL",    "gpt-4o")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL",    "mistral")

# ==============================================================================
# PROMPT DE VALIDATION LLM
# ==============================================================================

# Injecté une fois par batch de clusters. Chaque cluster est numéroté.
# Le LLM retourne un tableau JSON d'objets {id, meme_entite, forme_retenue}.

PROMPT_VALIDATE_CLUSTERS = """
Tu analyses des clusters de variantes graphiques probables issus d'un texte OCR du XIXe siècle
(annuaires de l'Institut de droit international, principalement en français,
avec des noms propres allemands, anglais, italiens, latins).

Pour chaque cluster ci-dessous, réponds UNIQUEMENT avec un tableau JSON valide,
sans texte autour, sans Markdown.

Pour chaque cluster :
- "id"            : le numéro du cluster (repris tel quel)
- "meme_entite"   : true si toutes les variantes désignent probablement la même entité,
                    false si ce sont des entités distinctes ou si le cluster est ambigu
- "forme_retenue" : la graphie correcte à utiliser (si meme_entite = true),
                    ou null (si meme_entite = false)
- "confiance"     : 0.0–1.0 (ta certitude sur la décision)
- "note"          : courte explication si utile, null sinon

Règles de canonicalisation pour les noms de personnes :
- Respecter la graphie originale correcte (pas de modernisation)
- Préférer la forme la plus complète présente dans le cluster
- Conserver les traits d'union, accents, particules (de, van, von...)

Exemples de clusters typiques et réponses attendues :
- ["Bluntschli", "Bluntscbli", "Bluntscbii"] → meme_entite: true, forme_retenue: "Bluntschli"
- ["Pierantoni", "Pierantóni", "Pierantomi"] → meme_entite: true, forme_retenue: "Pierantoni"
- ["Gand", "Grand"] → meme_entite: false (Gand=ville belge, Grand=autre chose)
- ["Rolin", "Roliu"] → meme_entite: true, forme_retenue: "Rolin"

Clusters à analyser :
{clusters_json}
""".strip()

# ==============================================================================
# EXTRACTION DES TOKENS
# ==============================================================================

# Regex pour identifier les tokens candidats à être des noms propres :
# commence par une majuscule, suivi de lettres (avec accents, traits d'union).
# Le \b final assure qu'on capture des mots complets.
TOKEN_RE = re.compile(r'\b([A-ZÀÂÄÉÈÊËÎÏÔÖÙÛÜŸÆŒ][a-zA-ZÀ-ÿ\-]{%d,})\b' % (MIN_TOKEN_LENGTH - 1))

# Mots à exclure : début de phrase, titres courants, mots grammaticaux
# commençant par une majuscule dans ce corpus.
STOPWORDS_UPPER: set[str] = {
    "Le", "La", "Les", "Un", "Une", "Des", "Du", "De", "Au", "Aux",
    "En", "Par", "Pour", "Sur", "Avec", "Dans", "Que", "Qui", "Ce",
    "Il", "Elle", "Ils", "Elles", "Nous", "Vous", "Leur", "Leurs",
    "Institut", "Article", "Seance", "Session", "Rapport",
    "Commission", "Projet", "Comite", "Membre", "Membres",
    "Monsieur", "Messieurs", "Madame",
}


def extract_tokens(text: str) -> Counter:
    """
    Extrait tous les tokens candidats noms propres et compte leurs occurrences.

    On exclut les stopwords et les tokens trop courts.
    On normalise légèrement (strip) mais on conserve la casse exacte —
    c'est la graphie telle qu'elle apparaît dans le texte qui sera corrigée.
    """
    counts: Counter = Counter()
    for match in TOKEN_RE.finditer(text):
        token = match.group(1).strip()
        if token not in STOPWORDS_UPPER and len(token) >= MIN_TOKEN_LENGTH:
            counts[token] += 1
    return counts


# ==============================================================================
# CLUSTERING PAR SIMILARITÉ
# ==============================================================================

def normalize_for_comparison(token: str) -> str:
    """
    Normalise un token pour la comparaison de similarité uniquement.
    NE modifie PAS le token original stocké dans le cluster.

    On supprime les accents et met en minuscules pour que "Bluntschli" et
    "Bluntscbli" soient correctement comparés malgré les artefacts OCR
    qui substituent parfois des caractères accentués.
    """
    nfkd = unicodedata.normalize("NFKD", token)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def cluster_tokens(token_counts: Counter) -> list[dict]:
    """
    Regroupe les tokens par similarité textuelle (distance Levenshtein via rapidfuzz).

    Algorithme greedy (union-find simplifié) :
    - Trier les tokens par fréquence décroissante (le plus fréquent devient
      le "pivot" naturel du cluster — il a le plus de chances d'être correct).
    - Pour chaque token non encore assigné, chercher un cluster existant dont
      le pivot est suffisamment similaire.
    - Si aucun cluster ne convient, créer un nouveau cluster.

    Complexité : O(n²) sur le nombre de tokens uniques. Acceptable pour des
    corpus de cette taille (< 5000 tokens uniques typiquement).

    Pourquoi greedy plutôt que clustering hiérarchique ?
        On veut des clusters petits et cohérents, pas une fusion agressive.
        Le greedy avec pivot fréquent produit des clusters où la forme
        correcte est souvent le pivot — ce que le LLM confirmera.
    """
    try:
        from rapidfuzz import fuzz
    except ImportError:
        print("[ERREUR] rapidfuzz non installé : pip install rapidfuzz")
        sys.exit(1)

    # Tokens triés par fréquence décroissante
    sorted_tokens = [t for t, _ in token_counts.most_common()
                     if token_counts[t] >= MIN_OCCURRENCES]

    clusters: list[dict] = []
    assigned: set[str] = set()

    for token in sorted_tokens:
        if token in assigned:
            continue

        norm_token = normalize_for_comparison(token)
        cluster_found = False

        for cluster in clusters:
            pivot      = cluster["pivot"]
            norm_pivot = normalize_for_comparison(pivot)

            score = fuzz.ratio(norm_token, norm_pivot)
            if score >= MIN_SIMILARITY_SCORE:
                cluster["variantes"].append(token)
                cluster["scores"].append(score)
                cluster["occurrences"][token] = token_counts[token]
                assigned.add(token)
                cluster_found = True
                break

        if not cluster_found:
            clusters.append({
                "pivot":       token,
                "variantes":   [token],
                "scores":      [100],
                "occurrences": {token: token_counts[token]},
            })
            assigned.add(token)

    # Ne garder que les clusters avec au moins 2 variantes
    # (un token seul ne peut pas avoir de variante OCR à corriger)
    multi = [c for c in clusters if len(c["variantes"]) > 1]

    # Trier par score minimal croissant : les plus douteux en premier
    # (priorité de validation humaine)
    multi.sort(key=lambda c: min(c["scores"]))

    return multi

# ==============================================================================
# VALIDATION LLM
# ==============================================================================

def call_anthropic(prompt: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    msg = client.messages.create(
        model=ANTHROPIC_MODEL, max_tokens=MAX_TOKENS, temperature=TEMPERATURE,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def call_openai(prompt: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY)
    r = client.chat.completions.create(
        model=OPENAI_MODEL, max_tokens=MAX_TOKENS, temperature=TEMPERATURE,
        messages=[{"role": "user", "content": prompt}],
    )
    return r.choices[0].message.content


def call_ollama(prompt: str) -> str:
    from openai import OpenAI
    base = OLLAMA_BASE_URL if OLLAMA_BASE_URL.endswith("/v1") else OLLAMA_BASE_URL + "/v1"
    client = OpenAI(api_key="ollama", base_url=base)
    r = client.chat.completions.create(
        model=OLLAMA_MODEL, max_tokens=MAX_TOKENS, temperature=TEMPERATURE,
        messages=[{"role": "user", "content": prompt}],
    )
    return r.choices[0].message.content


def call_llm(prompt: str) -> str:
    if LLM_PROVIDER == "anthropic": return call_anthropic(prompt)
    if LLM_PROVIDER == "openai":    return call_openai(prompt)
    if LLM_PROVIDER == "ollama":    return call_ollama(prompt)
    raise ValueError(f"Fournisseur inconnu : '{LLM_PROVIDER}'")


def validate_clusters_llm(clusters: list[dict]) -> list[dict]:
    """
    Soumet les clusters au LLM en batches pour valider et canonicaliser.

    Chaque batch contient BATCH_SIZE clusters numérotés. Le LLM retourne
    un tableau JSON d'objets {id, meme_entite, forme_retenue, confiance, note}.

    On enrichit chaque cluster avec la réponse LLM. En cas d'erreur sur
    un batch, on marque les clusters correspondants comme non validés
    (validation humaine obligatoire) et on continue.
    """
    results = list(clusters)  # copie pour enrichissement

    batches = [results[i:i+BATCH_SIZE] for i in range(0, len(results), BATCH_SIZE)]
    print(f"  {len(clusters)} clusters → {len(batches)} batch(s) LLM")

    for b_idx, batch in enumerate(batches, 1):
        # Préparer le JSON des clusters pour le prompt
        clusters_for_llm = [
            {
                "id": i,
                "variantes": c["variantes"],
                "score_min": min(c["scores"]),
                "nb_total_occurrences": sum(c["occurrences"].values()),
            }
            for i, c in enumerate(batch)
        ]
        prompt = PROMPT_VALIDATE_CLUSTERS.format(
            clusters_json=json.dumps(clusters_for_llm, ensure_ascii=False, indent=2)
        )

        print(f"  Batch {b_idx}/{len(batches)} ({len(batch)} clusters)...", end=" ", flush=True)
        try:
            raw = call_llm(prompt)
            # Extraire le tableau JSON
            start = raw.find("[")
            end   = raw.rfind("]")
            if start == -1 or end == -1:
                raise ValueError("Pas de tableau JSON dans la réponse")
            validations = json.loads(raw[start:end+1])

            # Mapper les résultats sur les clusters du batch
            val_by_id = {v["id"]: v for v in validations if isinstance(v, dict)}
            for i, cluster in enumerate(batch):
                val = val_by_id.get(i, {})
                cluster["llm_meme_entite"]   = val.get("meme_entite")
                cluster["llm_forme_retenue"] = val.get("forme_retenue")
                cluster["llm_confiance"]     = val.get("confiance", 0.5)
                cluster["llm_note"]          = val.get("note")
                cluster["llm_status"]        = "ok"

            print(f"OK ({len(validations)} réponses)")

        except Exception as e:
            print(f"ERREUR : {e}")
            for cluster in batch:
                cluster["llm_meme_entite"]   = None
                cluster["llm_forme_retenue"] = None
                cluster["llm_confiance"]     = 0.0
                cluster["llm_note"]          = f"Erreur LLM : {e}"
                cluster["llm_status"]        = "error"

        if b_idx < len(batches):
            time.sleep(BATCH_DELAY)

    return results

# ==============================================================================
# EXPORT TSV
# ==============================================================================

# Colonnes du TSV exporté.
# Les colonnes d'action (decision, forme_retenue) sont à remplir par le
# validateur humain. Les autres sont en lecture seule (information).
TSV_COLUMNS = [
    "decision",          # À remplir : OK | REJETER
    "forme_retenue",     # À corriger si besoin (pré-rempli par le LLM)
    "variantes",         # Lecture seule : toutes les graphies trouvées
    "score_min",         # Lecture seule : similarité la plus faible du cluster
    "nb_occurrences",    # Lecture seule : total d'occurrences dans le texte
    "llm_confiance",     # Lecture seule : confiance du LLM
    "llm_note",          # Lecture seule : explication du LLM
    "llm_status",        # Lecture seule : ok | error
    "cluster_id",        # Référence interne (pour apply_corrections.py)
]


def export_tsv(clusters: list[dict], path: str) -> None:
    """
    Exporte les clusters validés par le LLM dans un TSV.

    Stratégie de pré-remplissage :
    - Si le LLM a dit meme_entite=true et fourni une forme_retenue :
      la décision est pré-remplie "OK" et la forme pré-remplie.
      Le validateur n'a qu'à confirmer ou corriger.
    - Si le LLM a dit meme_entite=false ou a échoué :
      la décision est laissée vide et la forme_retenue aussi.
      Le validateur doit décider.

    Les clusters sont triés par score_min croissant : les plus douteux
    (score bas) arrivent en tête pour attirer l'attention.

    Format TSV choisi plutôt que CSV :
        Les noms propres de ce corpus contiennent des virgules (rares mais
        possibles). Le TSV avec séparateur tabulation évite toute ambiguïté
        sans avoir à gérer les guillemets d'échappement.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    with open(p, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TSV_COLUMNS, delimiter="\t")
        writer.writeheader()

        for i, cluster in enumerate(clusters):
            meme    = cluster.get("llm_meme_entite")
            forme   = cluster.get("llm_forme_retenue") or cluster["pivot"]
            score   = min(cluster["scores"])
            nb_occ  = sum(cluster["occurrences"].values())
            variantes_str = " | ".join(cluster["variantes"])

            # Pré-remplissage selon la décision LLM
            if meme is True and cluster.get("llm_status") == "ok":
                decision_pre = "OK"
            elif meme is False:
                decision_pre = "REJETER"
            else:
                decision_pre = ""   # Erreur LLM — le validateur décide

            writer.writerow({
                "decision":       decision_pre,
                "forme_retenue":  forme if decision_pre == "OK" else "",
                "variantes":      variantes_str,
                "score_min":      score,
                "nb_occurrences": nb_occ,
                "llm_confiance":  cluster.get("llm_confiance", ""),
                "llm_note":       cluster.get("llm_note") or "",
                "llm_status":     cluster.get("llm_status", ""),
                "cluster_id":     f"c{i:04d}",
            })

    print(f"[OK] {len(clusters)} clusters exportés dans {path}")

# ==============================================================================
# POINT D'ENTRÉE
# ==============================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Détection et clustering des variantes OCR dans _work.txt"
    )
    parser.add_argument("--work-file",      default=WORK_FILE)
    parser.add_argument("--candidates-tsv", default=CANDIDATES_TSV)
    parser.add_argument("--min-score",      type=int, default=MIN_SIMILARITY_SCORE)
    parser.add_argument("--dry-run",        action="store_true",
                        help="Affiche les clusters sans appel LLM")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("=" * 60)
    print("ocr_fix.py — Clustering variantes OCR")
    print(f"Fichier source : {args.work_file}")
    print(f"TSV sortie     : {args.candidates_tsv}")
    print(f"Score min      : {args.min_score}")
    print("=" * 60)

    # Lecture du fichier de travail
    work_path = Path(args.work_file)
    if not work_path.exists():
        print(f"[ERREUR] Fichier introuvable : {args.work_file}")
        print("  Conseil : copier original.txt en _work.txt avant de lancer ce script.")
        sys.exit(1)

    text = work_path.read_text(encoding="utf-8")
    print(f"\n{len(text):,} caractères lus depuis {args.work_file}")

    # Extraction des tokens
    print("\n[1/3] Extraction des tokens candidats...")
    token_counts = extract_tokens(text)
    eligible = {t: c for t, c in token_counts.items() if c >= MIN_OCCURRENCES}
    print(f"  {len(token_counts):,} tokens uniques trouvés")
    print(f"  {len(eligible):,} tokens avec >= {MIN_OCCURRENCES} occurrence(s)")

    # Clustering
    print("\n[2/3] Clustering par similarité (rapidfuzz)...")
    clusters = cluster_tokens(Counter(eligible))
    gros = [c for c in clusters if len(c["variantes"]) > MAX_CLUSTER_SIZE]
    print(f"  {len(clusters)} clusters multi-variantes trouvés")
    if gros:
        print(f"  {len(gros)} clusters larges (> {MAX_CLUSTER_SIZE} variantes) — probablement des faux positifs")

    if not clusters:
        print("\nAucun cluster trouvé. Le texte est peut-être déjà propre.")
        return

    if args.dry_run:
        print("\n[DRY RUN] Premiers clusters :")
        for i, c in enumerate(clusters[:10], 1):
            print(f"  {i:>3}. pivot={c['pivot']!r:25} variantes={c['variantes']}")
        print(f"\n  ... {len(clusters)} clusters au total. Relancer sans --dry-run pour la validation LLM.")
        return

    # Validation LLM
    print(f"\n[3/3] Validation LLM ({LLM_PROVIDER})...")
    clusters = validate_clusters_llm(clusters)

    # Sauvegarde intermédiaire des clusters bruts (diagnostic)
    clusters_path = Path(CLUSTERS_JSON)
    clusters_path.parent.mkdir(parents=True, exist_ok=True)
    with open(clusters_path, "w", encoding="utf-8") as f:
        json.dump(clusters, f, ensure_ascii=False, indent=2)
    print(f"  Clusters bruts sauvegardés dans {CLUSTERS_JSON}")

    # Export TSV
    export_tsv(clusters, args.candidates_tsv)

    # Rapport console
    n_ok     = sum(1 for c in clusters if c.get("llm_meme_entite") is True)
    n_rej    = sum(1 for c in clusters if c.get("llm_meme_entite") is False)
    n_err    = sum(1 for c in clusters if c.get("llm_status") == "error")
    print(f"\nRésumé :")
    print(f"  LLM → même entité   : {n_ok}")
    print(f"  LLM → entités diff. : {n_rej}")
    print(f"  LLM → erreur        : {n_err}")
    print(f"\nProchaine étape :")
    print(f"  1. Ouvrir {args.candidates_tsv} dans un tableur")
    print(f"  2. Vérifier/corriger les colonnes 'decision' et 'forme_retenue'")
    print(f"  3. Lancer : python apply_corrections.py --tsv {args.candidates_tsv}")


if __name__ == "__main__":
    main()
