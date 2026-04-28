"""
structure_annuaire.py
=====================
Parseur de structure pour les annuaires de l'Institut de droit international
(source Gallica / BnF, format texte brut post-OCR).

Observations sur le corpus :
- Séparateur de page : ligne de 20+ tirets  (--------)
- Header de page    : première ligne non vide après le séparateur,
                      forme "N° TITRE_SECTION" ou "TITRE_SECTION. N°"
                      (avec erreurs OCR tolérées : l→1, O→0)
- Table des matières : plusieurs pages consécutives portant "TABLE DES MATIERES"
                       dans leur header ; les entrées sont sur 1 ou 2 lignes
                       (titre / ... / numéro parfois séparé par un saut de ligne)
- Parties numérotées : "Première Partie", "Deuxième Partie", etc. (niveau 1)
- Sections           : "I. — ...", "II. — ..." (niveau 2)
- Sous-sections      : "A. — ...", noms propres, mois (niveau 3)
"""

import re
import json
from pathlib import Path
from dataclasses import dataclass, asdict


# ── Structures de données ────────────────────────────────────────────────────

@dataclass
class Page:
    num: int            # numéro de page du document original
    line_start: int     # ligne dans le fichier texte
    line_end: int
    section_hint: str   # texte du header de page
    raw_text: str


@dataclass
class TocEntry:
    title: str
    page: int
    level: int          # 1=Partie, 2=Section, 3=Sous-section


@dataclass
class Section:
    section_id: str
    title: str
    level: int
    page_start: int
    page_end: int | None
    raw_text: str = ""

    def word_count(self) -> int:
        return len(self.raw_text.split())


# ── Expressions régulières ───────────────────────────────────────────────────

SEP = re.compile(r'^-{20,}$')

# Header de page : "3 STATUTS." ou "STATUTS. 3" ou "384 TABLE DES MATIERES."
PAGE_HEADER = re.compile(
    r'^(\d{1,4})\s+([A-ZÀÉÈÊÎÏÙÛÜŒÆ][^\n]{2,70}?)\s*[.\s]*$'
    r'|^([A-ZÀÉÈÊÎÏÙÛÜŒÆ][^\n]{2,70}?)[.\s;,]+(\d{1,4})\s*$'
)

# Ligne de partie dans la TdM : "Première Partie." ou "Troisième partie."
PARTIE_LINE = re.compile(
    r'^(Premi[eè]re?|Deuxi[eè]me?|Troisi[eè]me?|Quatri[eè]me?|Cinqui[eè]me?)'
    r'\s+[Pp]artie\.?\s*$'
)

# Section romaine : "I. — Titre" ou "II. —Titre"
ROMAN_LINE = re.compile(r'^([IVX]+)\.\s*[—-]\s*(.+)$')

# Sous-section lettre : "A. — Titre"
ALPHA_LINE = re.compile(r'^([A-Z])\.\s*[—-]\s*(.+)$')

# Numéro de page seul en fin de ligne (après des points de conduite)
PAGE_AT_END = re.compile(r'[\.\s…·]{2,}(\d{1,4})\s*$')

# Numéro romain en chiffres romains (pour pages préliminaires en chiffres romains)
ROMAN_NUM = re.compile(r'^[IVXivx]+$')


def _parse_page_num(s: str) -> int | None:
    """Tolère les erreurs OCR courantes sur les chiffres."""
    s = s.strip().replace('l', '1').replace('O', '0').replace('I', '1')
    try:
        return int(s)
    except ValueError:
        return None


# ── Détection des pages ──────────────────────────────────────────────────────

def parse_pages(text: str) -> list[Page]:
    """
    Découpe le texte brut en pages.
    Chaque page commence après une ligne de tirets.
    Le numéro et le titre de section sont extraits du header de page.
    """
    lines = text.splitlines()
    sep_positions = [i for i, l in enumerate(lines) if SEP.match(l.strip())]

    pages = []
    for idx, sep_pos in enumerate(sep_positions):
        page_num = None
        section_hint = ""

        # Chercher le header dans les 6 premières lignes après le séparateur
        for offset in range(1, 7):
            pos = sep_pos + offset
            if pos >= len(lines):
                break
            candidate = lines[pos].strip()
            if not candidate:
                continue
            m = PAGE_HEADER.match(candidate)
            if m:
                if m.group(1):          # forme "N° TITRE"
                    n = _parse_page_num(m.group(1))
                    if n and n < 600:   # sanité : pas de page > 600 dans ce corpus
                        page_num = n
                        section_hint = m.group(2).strip().rstrip('.')
                else:                   # forme "TITRE N°"
                    n = _parse_page_num(m.group(4))
                    if n and n < 600:
                        page_num = n
                        section_hint = m.group(3).strip().rstrip('.')
                if page_num:
                    break

        line_end = sep_positions[idx + 1] if idx + 1 < len(sep_positions) else len(lines)
        raw = "\n".join(lines[sep_pos + 1: line_end])

        if page_num is not None:
            pages.append(Page(
                num=page_num,
                line_start=sep_pos,
                line_end=line_end,
                section_hint=section_hint,
                raw_text=raw,
            ))

    # Dédupliquer les pages qui auraient le même numéro (double-page scanné)
    seen = {}
    deduped = []
    for p in sorted(pages, key=lambda x: x.num):
        if p.num not in seen:
            seen[p.num] = True
            deduped.append(p)

    return deduped


# ── Parsing de la Table des matières ────────────────────────────────────────

def parse_toc(text: str) -> list[TocEntry]:
    """
    Extrait la table des matières.

    Stratégie :
    1. Repérer les pages dont le section_hint contient "TABLE DES MATIERES"
    2. Extraire les entrées en gérant les titres multi-lignes :
       - Un titre peut être sur 1 ou 2 lignes avant le numéro de page
       - Le numéro de page est soit en fin de la même ligne, soit seul
         sur la ligne suivante (après points de conduite ou blanc)
    3. Détecter le niveau hiérarchique selon la forme du titre
    """
    lines = text.splitlines()

    # Trouver toutes les zones TABLE DES MATIERES
    toc_zones = []
    for i, line in enumerate(lines):
        if re.search(r'TABLE\s+DES\s+MATI', line, re.I):
            toc_zones.append(i)

    if not toc_zones:
        return []

    toc_start = toc_zones[0]
    toc_end = len(lines)

    # Collecter les lignes pertinentes de la TdM (ignorer les lignes vides et
    # les répétitions du titre TABLE DES MATIÈRES)
    raw_lines = []
    for line in lines[toc_start:toc_end]:
        stripped = line.strip()
        if not stripped:
            continue
        if re.search(r'TABLE\s+DES\s+MATI', stripped, re.I):
            continue
        if stripped.lower() == 'pages.' or stripped == 'Pages.':
            continue
        raw_lines.append(stripped)

    entries: list[TocEntry] = []
    current_title_parts: list[str] = []
    current_level: int = 2

    def _flush(title_parts: list[str], page_num: int, level: int):
        title = " ".join(title_parts).strip().rstrip('.')
        title = re.sub(r'\s+', ' ', title)
        if title and page_num > 0:
            entries.append(TocEntry(title=title, page=page_num, level=level))

    def _detect_level(title: str) -> int:
        if PARTIE_LINE.match(title):
            return 1
        if ROMAN_LINE.match(title):
            return 2
        if ALPHA_LINE.match(title):
            return 3
        # Noms propres (notices biographiques) : "Dupont (Jean)"
        if re.match(r'^[A-ZÀÉÈÊ][a-zàéèê]+\s*[\(\[]', title):
            return 3
        # Mois (tableau chronologique)
        if re.match(r'^(Janvier|Février|Mars|Avril|Mai|Juin|Juillet|Août|'
                    r'Septembre|Octobre|Novembre|Décembre)\s+\d{4}', title):
            return 3
        return 2

    i = 0
    while i < len(raw_lines):
        line = raw_lines[i]

        # Cas 1 : la ligne contient titre + numéro de page
        m_end = PAGE_AT_END.search(line)
        if m_end:
            page_num = int(m_end.group(1))
            title_part = line[:m_end.start()].strip().rstrip('.')

            # Si on avait un titre en cours, c'est la suite
            if current_title_parts:
                current_title_parts.append(title_part)
                _flush(current_title_parts, page_num, current_level)
                current_title_parts = []
            else:
                # Titre et page sur la même ligne
                level = _detect_level(title_part)
                _flush([title_part], page_num, level)

            i += 1
            continue

        # Cas 2 : ligne qui est un numéro seul (suite d'un titre multi-ligne)
        if re.match(r'^\d{1,4}\s*$', line) and current_title_parts:
            page_num = int(line.strip())
            _flush(current_title_parts, page_num, current_level)
            current_title_parts = []
            i += 1
            continue

        # Cas 3 : ligne de Partie (niveau 1, souvent sans numéro de page)
        if PARTIE_LINE.match(line):
            if current_title_parts:
                # abandonner le titre précédent incomplet
                current_title_parts = []
            current_title_parts = [line]
            current_level = 1
            i += 1
            continue

        # Cas 4 : début d'un nouveau titre (commence par majuscule ou chiffre romain)
        is_new_title = (
            re.match(r'^[A-ZÀÉÈÊÎÏÙÛÜŒÆ]', line)
            or ROMAN_LINE.match(line)
            or ALPHA_LINE.match(line)
        )
        if is_new_title:
            # Flush le titre précédent si incomplet (sans numéro trouvé)
            current_title_parts = [line]
            current_level = _detect_level(line)
        elif current_title_parts:
            # Suite du titre précédent
            current_title_parts.append(line)

        i += 1

    return entries


# ── Assemblage des sections ──────────────────────────────────────────────────

def build_sections(pages: list[Page], toc: list[TocEntry]) -> list[Section]:
    """
    Assemble les pages en sections selon les entrées de la TdM.
    Chaque section regroupe les pages entre son numéro de début
    et le numéro de début de la section suivante - 1.
    """
    if not toc:
        # Fallback : une section par groupe de pages de même section_hint
        return _build_sections_from_hints(pages)

    sections = []
    for i, entry in enumerate(toc):
        p_start = entry.page
        p_end = toc[i + 1].page - 1 if i + 1 < len(toc) else None

        section_pages = [
            p for p in pages
            if p.num >= p_start and (p_end is None or p.num <= p_end)
        ]
        raw = "\n\n--- [page {}] ---\n".format(p_start).join(
            p.raw_text for p in section_pages
        )

        sections.append(Section(
            section_id=f"s{i:04d}",
            title=entry.title,
            level=entry.level,
            page_start=p_start,
            page_end=p_end,
            raw_text=raw,
        ))

    return sections


def _build_sections_from_hints(pages: list[Page]) -> list[Section]:
    """Fallback : regroupe les pages consécutives de même section_hint."""
    sections = []
    current_hint = None
    current_pages = []
    sid = 0

    for p in pages:
        hint = p.section_hint.strip()
        if hint != current_hint:
            if current_hint and current_pages:
                sections.append(Section(
                    section_id=f"s{sid:04d}",
                    title=current_hint,
                    level=2,
                    page_start=current_pages[0].num,
                    page_end=current_pages[-1].num,
                    raw_text="\n\n".join(pp.raw_text for pp in current_pages),
                ))
                sid += 1
            current_hint = hint
            current_pages = [p]
        else:
            current_pages.append(p)

    return sections


# ── Export JSON ──────────────────────────────────────────────────────────────

def export_json(pages: list[Page], toc: list[TocEntry],
                sections: list[Section], out_path: str):
    data = {
        "pages": [asdict(p) for p in pages],
        "toc": [asdict(e) for e in toc],
        "sections": [
            {**asdict(s), "word_count": s.word_count()}
            for s in sections
        ],
    }
    Path(out_path).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"→ Export JSON : {out_path}")


# ── Point d'entrée ───────────────────────────────────────────────────────────

def process_annuaire(filepath: str,
                     export: str | None = None) -> tuple[list[Page], list[TocEntry], list[Section]]:
    text = Path(filepath).read_text(encoding="utf-8")

    pages    = parse_pages(text)
    toc      = parse_toc(text)
    sections = build_sections(pages, toc)

    # ── Rapport ──
    print(f"\n{'='*60}")
    print(f"Fichier   : {filepath}")
    print(f"Pages détectées : {len(pages)}")
    print(f"Entrées TdM     : {len(toc)}")
    print(f"Sections créées : {len(sections)}")

    print(f"\n── Table des matières ({len(toc)} entrées) ──")
    for e in toc:
        indent = "  " * (e.level - 1)
        print(f"  {indent}[niv.{e.level}] p.{e.page:3d} — {e.title[:65]}")

    print(f"\n── Sections (aperçu) ──")
    for s in sections[:20]:
        print(f"  [{s.level}] {s.section_id}  p.{s.page_start}-{s.page_end or '?'}"
              f"  {s.word_count():5d} mots  {s.title[:55]}")

    if export:
        export_json(pages, toc, sections, export)

    return pages, toc, sections


if __name__ == "__main__":
    import sys
    filepath = sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads/jette"
    export   = sys.argv[2] if len(sys.argv) > 2 else "annuaire_structure.json"
    process_annuaire(filepath, export)
