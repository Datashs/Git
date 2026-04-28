"""
apply_corrections.py — Application des corrections OCR validées dans _work.txt
===============================================================================

Position dans la chaîne de traitement :
    corrections_candidates.tsv  (validé dans un tableur)
         |
    [apply_corrections.py]  → _work.txt modifié (à committer dans git)
                            → corrections.json  (log versionné des décisions)
         |
    structure_annuaire.py  → sections.json
         |
    ner_llm_v2.py

Rôle :
    Lit le TSV validé par le chercheur, applique toutes les corrections
    marquées "OK" dans _work.txt par substitution globale de chaîne,
    et écrit corrections.json (log complet des décisions, versionné dans git).

    original.txt n'est JAMAIS touché.
    _work.txt est modifié en place et doit être committé dans git après
    chaque exécution de ce script.

Comportement :
    - Seules les lignes TSV avec decision="OK" sont appliquées.
    - Chaque variante du cluster est remplacée par la forme_retenue.
    - Le remplacement est global (toutes les occurrences dans le fichier).
    - Les remplacements sont sensibles à la casse et aux frontières de mots.
    - Un rapport détaillé indique combien d'occurrences ont été remplacées
      pour chaque variante.

Sécurités :
    - On vérifie que forme_retenue est non vide avant de remplacer.
    - On ne remplace pas une variante par elle-même (variante == forme_retenue).
    - On crée une sauvegarde _work.txt.bak avant toute modification.
    - corrections.json est écrit de façon atomique (fichier temporaire).

Usage :
    python apply_corrections.py
    python apply_corrections.py --tsv corpus/annuaire_1877/corrections_candidates.tsv
    python apply_corrections.py --dry-run   # affiche les remplacements sans modifier
    python apply_corrections.py --no-backup # désactive la sauvegarde .bak

Adaptation à un autre corpus :
    Ajuster WORK_FILE et CANDIDATES_TSV. Le reste est générique.
"""

import os
import re
import sys
import csv
import json
import shutil
import argparse
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

# ==============================================================================
# PARAMÈTRES
# ==============================================================================

WORK_FILE       = os.getenv("WORK_FILE",      "corpus/annuaire_1877/annuaire_1877_work.txt")
CANDIDATES_TSV  = os.getenv("CANDIDATES_TSV", "corpus/annuaire_1877/corrections_candidates.tsv")
CORRECTIONS_JSON = os.getenv("CORRECTIONS_JSON", "corpus/annuaire_1877/corrections.json")

# ==============================================================================
# LECTURE DU TSV VALIDÉ
# ==============================================================================

def load_validated_tsv(path: str) -> list[dict]:
    """
    Charge le TSV et retourne uniquement les lignes marquées "OK".

    On vérifie que forme_retenue est non vide — une ligne OK sans forme
    est une erreur de saisie qui doit être signalée, pas silencieusement
    ignorée.

    Le TSV est lu avec le séparateur tabulation, encodage UTF-8.
    LibreOffice et Excel sauvent bien en UTF-8 si l'option est sélectionnée.
    En cas de problème d'encodage, essayer UTF-8-sig (BOM Windows).
    """
    p = Path(path)
    if not p.exists():
        print(f"[ERREUR] TSV introuvable : {path}")
        sys.exit(1)

    corrections = []
    errors      = []

    with open(p, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for i, row in enumerate(reader, 2):   # ligne 2 = première ligne de données
            decision      = row.get("decision", "").strip().upper()
            forme_retenue = row.get("forme_retenue", "").strip()
            variantes_str = row.get("variantes", "").strip()
            cluster_id    = row.get("cluster_id", f"ligne_{i}")

            if decision != "OK":
                continue   # REJETER ou vide → ignorer

            if not forme_retenue:
                errors.append(f"Ligne {i} ({cluster_id}) : decision=OK mais forme_retenue vide")
                continue

            if not variantes_str:
                errors.append(f"Ligne {i} ({cluster_id}) : variantes vide")
                continue

            # Les variantes sont séparées par " | " dans le TSV
            variantes = [v.strip() for v in variantes_str.split("|") if v.strip()]

            corrections.append({
                "cluster_id":    cluster_id,
                "forme_retenue": forme_retenue,
                "variantes":     variantes,
                "source_ligne":  i,
            })

    if errors:
        print(f"[WARN] {len(errors)} ligne(s) TSV invalides :")
        for e in errors:
            print(f"  - {e}")

    return corrections


# ==============================================================================
# APPLICATION DES CORRECTIONS
# ==============================================================================

def make_replacement_regex(variante: str) -> re.Pattern:
    """
    Construit une regex pour remplacer une variante avec respect des
    frontières de mots.

    Pourquoi \b et non pas un simple str.replace() ?
        Un simple remplacement de chaîne remplacerait "Rolin" dans "Rolin-
        Jaequemyns" mais aussi dans "Caroline" si "Rolin" y apparaissait.
        \b garantit qu'on ne remplace que des occurrences de mots entiers.

    Cas particulier des traits d'union :
        "Rolin-Jaequemyns" doit être traité comme un tout. On utilise
        re.escape() pour échapper les tirets et autres métacaractères,
        et on accepte \b avant et après le nom complet.
    """
    escaped = re.escape(variante)
    return re.compile(r'\b' + escaped + r'\b')


def apply_corrections(text: str, corrections: list[dict]) -> tuple[str, list[dict]]:
    """
    Applique toutes les corrections validées au texte.

    Retourne (texte_corrigé, log_détaillé).

    Ordre d'application : les variantes les plus longues d'abord.
    Cela évite qu'une correction courte ("Gand") remplace le début
    d'une correction plus longue ("Gandini") avant qu'elle soit traitée.

    Pour chaque correction, on itère sur toutes les variantes du cluster
    et on remplace chacune par la forme_retenue, sauf si variante ==
    forme_retenue (remplacement inutile).

    Le log détaille le nombre de substitutions par variante, ce qui
    permet au chercheur de vérifier l'impact réel de chaque correction.
    """
    log = []
    current_text = text

    # Aplatir en liste (variante, forme_retenue, cluster_id) triée par
    # longueur décroissante de variante
    all_replacements = []
    for corr in corrections:
        for variante in corr["variantes"]:
            if variante != corr["forme_retenue"]:
                all_replacements.append((variante, corr["forme_retenue"], corr["cluster_id"]))

    all_replacements.sort(key=lambda x: len(x[0]), reverse=True)

    for variante, forme_retenue, cluster_id in all_replacements:
        pattern = make_replacement_regex(variante)
        new_text, n_subs = pattern.subn(forme_retenue, current_text)

        log.append({
            "cluster_id":    cluster_id,
            "variante":      variante,
            "forme_retenue": forme_retenue,
            "n_substitutions": n_subs,
        })

        if n_subs > 0:
            current_text = new_text

    return current_text, log


# ==============================================================================
# SAUVEGARDE DU LOG
# ==============================================================================

def save_corrections_json(path: str, corrections: list[dict], log: list[dict],
                           tsv_path: str, work_file: str) -> None:
    """
    Écrit corrections.json : log complet des décisions et des substitutions.

    Ce fichier est versionné dans git — il constitue la trace éditoriale
    de toutes les décisions de correction prises sur ce volume.
    Format : objet avec métadonnées + tableau des corrections appliquées.

    Écriture atomique via fichier temporaire pour éviter la corruption
    en cas d'interruption.
    """
    data = {
        "date":      datetime.now().isoformat(),
        "work_file": work_file,
        "tsv_source": tsv_path,
        "n_corrections_appliquees": sum(1 for l in log if l["n_substitutions"] > 0),
        "n_substitutions_total":    sum(l["n_substitutions"] for l in log),
        "log": log,
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(p)


# ==============================================================================
# POINT D'ENTRÉE
# ==============================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Application des corrections OCR validées dans _work.txt"
    )
    parser.add_argument("--tsv",       default=CANDIDATES_TSV,
                        help=f"TSV validé (défaut : {CANDIDATES_TSV})")
    parser.add_argument("--work-file", default=WORK_FILE,
                        help=f"Fichier de travail à modifier (défaut : {WORK_FILE})")
    parser.add_argument("--corrections-json", default=CORRECTIONS_JSON)
    parser.add_argument("--dry-run",   action="store_true",
                        help="Affiche les substitutions sans modifier le fichier")
    parser.add_argument("--no-backup", action="store_true",
                        help="Ne crée pas de sauvegarde .bak")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("=" * 60)
    print("apply_corrections.py — Application des corrections OCR")
    print(f"TSV source  : {args.tsv}")
    print(f"Fichier     : {args.work_file}")
    if args.dry_run:
        print("MODE DRY RUN — aucune modification")
    print("=" * 60)

    # Lecture du TSV validé
    print(f"\n[1/3] Lecture du TSV validé...")
    corrections = load_validated_tsv(args.tsv)

    if not corrections:
        print("Aucune correction à appliquer (aucune ligne 'OK' dans le TSV).")
        return

    n_variantes = sum(len(c["variantes"]) for c in corrections)
    print(f"  {len(corrections)} cluster(s) à corriger, {n_variantes} variante(s) au total")

    # Lecture du fichier de travail
    work_path = Path(args.work_file)
    if not work_path.exists():
        print(f"[ERREUR] Fichier introuvable : {args.work_file}")
        sys.exit(1)

    text_original = work_path.read_text(encoding="utf-8")
    print(f"\n[2/3] Application des corrections ({len(text_original):,} caractères)...")

    # Application
    text_corrige, log = apply_corrections(text_original, corrections)

    # Rapport des substitutions
    n_avec_subs = sum(1 for l in log if l["n_substitutions"] > 0)
    n_sans_subs = sum(1 for l in log if l["n_substitutions"] == 0)
    total_subs  = sum(l["n_substitutions"] for l in log)

    print(f"  {n_avec_subs} variante(s) remplacée(s), {total_subs} substitution(s) au total")
    if n_sans_subs:
        print(f"  {n_sans_subs} variante(s) non trouvée(s) dans le texte (déjà corrigées ?)")

    # Détail par variante (toutes, même celles à 0 substitution)
    print()
    for entry in log:
        if entry["n_substitutions"] > 0:
            print(
                f"  {entry['variante']!r:30} → {entry['forme_retenue']!r:25} "
                f"({entry['n_substitutions']} occurrence(s))"
            )
        else:
            print(f"  {entry['variante']!r:30}   [non trouvé dans le texte]")

    if args.dry_run:
        print("\n[DRY RUN] Aucune modification appliquée.")
        print(f"  Relancer sans --dry-run pour modifier {args.work_file}")
        return

    # Sauvegarde .bak
    if not args.no_backup:
        bak_path = work_path.with_suffix(".txt.bak")
        shutil.copy2(work_path, bak_path)
        print(f"\n  Sauvegarde créée : {bak_path}")

    # Écriture du fichier corrigé
    print(f"\n[3/3] Écriture de {args.work_file}...")
    work_path.write_text(text_corrige, encoding="utf-8")
    print(f"  [OK] {args.work_file} modifié")

    # Log JSON versionné
    save_corrections_json(args.corrections_json, corrections, log, args.tsv, args.work_file)
    print(f"  [OK] Log versionné : {args.corrections_json}")

    # Instructions post-exécution
    print(f"""
Prochaines étapes :
  1. Vérifier le diff dans git :
       git diff {args.work_file}
  2. Committer les modifications :
       git add {args.work_file} {args.corrections_json}
       git commit -m "corrections OCR : {n_avec_subs} variantes, {total_subs} substitutions"
  3. Régénérer sections.json :
       python scripts/structure_annuaire.py --input {args.work_file}
  4. Lancer le NER :
       python scripts/ner_llm_v2.py
""")


if __name__ == "__main__":
    main()
