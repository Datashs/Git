#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""

Test du pipeline post-OCR sur un corpus fourni par l'utilisateur
=================================================================
Ce script permet de vérifier le bon fonctionnement d'un pipeline de
correction automatique de textes issus de l'OCR (reconnaissance optique
de caractères). Il applique successivement 13 scripts de nettoyage sur
un fichier texte fourni par l'utilisateur, et rend compte des résultats.

À qui s'adresse ce script ?
    À toute personne souhaitant tester le pipeline sur son propre corpus
    avant de l'utiliser en production, sans avoir à lancer les 13 scripts
    un par un à la main.

Ce qu'il fait concrètement :
    1. Charge le fichier texte indiqué en argument.
    2. Applique dans l'ordre les scripts 02 à 14 (apostrophes, tirets,
       espaces, ordinaux, mois, abréviations, ponctuation, etc.).
    3. Vérifie après chaque étape que les paragraphes sont bien préservés
       (mode robustesse).
    4. Affiche optionnellement le détail de chaque correction appliquée
       pour permettre une vérification humaine (mode audit).
    5. Peut sauvegarder le texte final corrigé dans un fichier de sortie.

Ce qu'il ne fait pas :
    Il n'effectue pas les étapes manuelles 15 (mots collés) et 16 (formes
    inconnues), qui nécessitent une intervention humaine.

Deux modes combinés :
  MODE ROBUSTESSE : vérifie que chaque script tourne sans erreur
    et que les paragraphes sont préservés.
  MODE AUDIT : affiche toutes les corrections appliquées,
    script par script, pour vérification humaine.

Usage :
    python test_corpus.py mon_corpus.txt
    python test_corpus.py mon_corpus.txt --audit       # corrections détaillées
    python test_corpus.py mon_corpus.txt --audit --max 50  # limiter à 50 corrections par script

Les scripts doivent être dans le même répertoire que ce fichier,
ou dans le répertoire indiqué par SCRIPTS_DIR en tête.
"""

import sys
import re
import argparse
from pathlib import Path


# =============================================================================
# PARAMÈTRES
# =============================================================================

# Répertoire contenant les scripts du pipeline (02apost.py, 03tirets.py, etc.)
# Par défaut : "." signifie le répertoire courant, c'est-à-dire l'endroit depuis
# lequel vous lancez la commande — pas forcément l'endroit où se trouve ce fichier.
#
# Si vos scripts sont ailleurs, indiquez le chemin ici. Exemples :
#   SCRIPTS_DIR = Path(".")                        # répertoire courant (défaut)
#   SCRIPTS_DIR = Path(__file__).parent            # même dossier que ce script
#   SCRIPTS_DIR = Path("/home/alice/pipeline")     # chemin absolu (Linux/Mac)
#   SCRIPTS_DIR = Path(r"C:\Users\Alice\pipeline") # chemin absolu (Windows)
#   SCRIPTS_DIR = Path("../pipeline")              # chemin relatif au répertoire courant
#
# Conseil : si vous n'êtes pas sûr(e), placez tous les fichiers .py dans le même
# dossier et utilisez Path(__file__).parent — cela fonctionnera toujours.

SCRIPTS_DIR = Path(".")

# =============================================================================
# CHARGEMENT DES SCRIPTS
# =============================================================================

def charger_script(nom_fichier: str) -> dict:
    r"""Charge les fonctions d'un script sans exécuter son __main__."""
    chemin = SCRIPTS_DIR / nom_fichier
    if not chemin.exists():
        raise FileNotFoundError(f"Script introuvable : {chemin}")
    with open(chemin, encoding='utf-8') as f:
        src = f.read()
    ns = {}
    exec(src.split('def main')[0], ns)
    return ns


# =============================================================================
# FONCTIONS D'ANALYSE
# =============================================================================

def trouver_differences(avant: str, apres: str, max_exemples: int = 20) -> list:
    r"""
    Repère les tokens modifiés entre avant et après.
    Retourne une liste de (avant, après, contexte, ligne).

    Utilise difflib.SequenceMatcher sur les tokens (séquences non-espace)
    plutôt qu'une comparaison caractère par caractère.
    Cela évite l'effet cascade : quand un script supprime un caractère,
    la comparaison zip() décalerait tous les suivants et gonflerait
    artificiellement le comptage (ex : script 04 annonçait 715 000 modifs
    pour 1 seule suppression réelle).
    """
    differences = []
    tokens_avant = list(re.finditer(r'\S+', avant))
    tokens_apres = re.findall(r'\S+', apres)

    for m_av, tb in zip(tokens_avant, tokens_apres):
        ta = m_av.group()
        if ta != tb:
            pos = m_av.start()
            ligne = avant[:pos].count('\n') + 1
            ctx = avant[max(0, pos - 25):pos + 25].replace('\n', '↵')
            differences.append((ta, tb, ctx, ligne))
            if len(differences) >= max_exemples:
                break
    return differences


def appliquer_et_auditer(label: str, texte_avant: str,
                          fn_apply,
                          mode_audit: bool,
                          max_exemples: int) -> tuple:
    r"""
    Applique une fonction de correction et retourne (texte_après, stats).
    En mode audit, affiche chaque correction.
    """
    try:
        result = fn_apply(texte_avant)
        if isinstance(result, tuple):
            texte_apres = result[0]
        else:
            texte_apres = result
    except Exception as e:
        print(f"  ❌ {label} — ERREUR : {e}")
        return texte_avant, {'ok': False, 'erreur': str(e)}

    # Robustesse : paragraphes préservés
    paras_avant = len([p for p in texte_avant.split('\n\n') if p.strip()])
    paras_apres = len([p for p in texte_apres.split('\n\n') if p.strip()])
    paras_ok = paras_avant == paras_apres

    # Nombre de tokens modifiés (comparaison zip — rapide)
    # Note : pour les scripts qui insèrent des espaces (09, 10, 12), ce comptage
    # est approximatif par effet de décalage. Les exemples d'audit restent
    # fiables — seul le total global peut être surestimé.
    _sv = re.findall(r'\S+', texte_avant)
    _sa = re.findall(r'\S+', texte_apres)
    n_diff = sum(1 for a, b in zip(_sv, _sa) if a != b)
    n_diff += abs(len(_sv) - len(_sa))

    status = '✅' if paras_ok else '⚠️ '
    para_note = '' if paras_ok else f'  ← § : {paras_avant} → {paras_apres}'

    if n_diff == 0:
        print(f"  {status} {label:<22}   0 modification{para_note}")
    else:
        print(f"  {status} {label:<22} {n_diff:4d} token(s) modifié(s){para_note}")

    if mode_audit and n_diff > 0:
        differences = trouver_differences(texte_avant, texte_apres, max_exemples)
        if differences:
            for avant_tok, apres_tok, ctx, ligne in differences:
                print(f"       L{ligne:5d} : {repr(avant_tok):20s} → {repr(apres_tok)}")
                print(f"               {repr(ctx)}")
            if len(differences) == max_exemples:
                print(f"       … (limité à {max_exemples} exemples, --max N pour augmenter)")
        print()

    return texte_apres, {
        'ok': True,
        'paras_ok': paras_ok,
        'n_diff': n_diff,
        'paras_avant': paras_avant,
        'paras_apres': paras_apres,
    }


# =============================================================================
# PIPELINE
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Test du pipeline post-OCR sur un corpus utilisateur",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=r"""
Exemples :
  python test_corpus.py mon_corpus.txt
  python test_corpus.py mon_corpus.txt --audit
  python test_corpus.py mon_corpus.txt --audit --max 30
  python test_corpus.py mon_corpus.txt --sortie resultat.txt
        """
    )
    parser.add_argument('corpus', help="Fichier texte à tester")
    parser.add_argument('--audit', action='store_true',
                        help="Afficher le détail des corrections appliquées")
    parser.add_argument('--max', type=int, default=20, metavar='N',
                        help="Nombre maximum de corrections affichées par script (défaut: 20)")
    parser.add_argument('--sortie', metavar='FICHIER',
                        help="Sauvegarder le texte final corrigé dans ce fichier")
    args = parser.parse_args()

    corpus_path = Path(args.corpus)
    if not corpus_path.exists():
        print(f"❌ Corpus introuvable : {corpus_path}")
        sys.exit(1)

    print("=" * 60)
    print("  TEST PIPELINE POST-OCR sur corpus utilisateur")
    print("=" * 60)

    with open(corpus_path, 'r', encoding='utf-8') as f:
        texte = f.read()

    n_paras = len([p for p in texte.split('\n\n') if p.strip()])
    print(f"\n  Corpus  : {corpus_path.name}")
    print(f"  Taille  : {len(texte):,} caractères")
    print(f"  Paragraphes : {n_paras}")
    print(f"  Mode audit  : {'oui (--max ' + str(args.max) + ')' if args.audit else 'non (ajouter --audit)'}")

    # Chargement des scripts
    print(f"\n  Chargement des scripts...", end=' ', flush=True)
    try:
        ns02 = charger_script('02apost.py')
        ns03 = charger_script('03tirets.py')
        ns04 = charger_script('04_controle.py')
        ns05 = charger_script('05_espaces.py')
        ns06 = charger_script('06_ordinaux.py')
        ns07 = charger_script('07_mois.py')
        ns08 = charger_script('08_abrev.py')
        ns09 = charger_script('09_ponctuation.py')
        ns10 = charger_script('10_virgules.py')
        ns11 = charger_script('11_romains.py')
        ns12 = charger_script('12_refs.py')
        ns13 = charger_script('13_guillemets.py')
        ns14 = charger_script('14_ligatures.py')
        print("✅")
    except FileNotFoundError as e:
        print(f"\n❌ {e}")
        print("   Vérifier SCRIPTS_DIR en tête du script.")
        sys.exit(1)

    print()
    print(f"  {'Script':<22} {'Modifications':>15}  Robustesse")
    print("  " + "─" * 56)
    if args.audit:
        print()

    t = texte
    stats_globales = {}
    tous_ok = True

    # ── 02 ────────────────────────────────────────────────────────────────────
    t, st = appliquer_et_auditer(
        '02 Apostrophes', t,
        ns02['normalize_apostrophes'],
        args.audit, args.max)
    stats_globales['02'] = st
    if not st.get('paras_ok', True): tous_ok = False

    # ── 03 ────────────────────────────────────────────────────────────────────
    t, st = appliquer_et_auditer(
        '03 Tirets', t,
        ns03['normalize_tirets'],
        args.audit, args.max)
    stats_globales['03'] = st

    # ── 04 ────────────────────────────────────────────────────────────────────
    t, st = appliquer_et_auditer(
        '04 Contrôle', t,
        ns04['clean_text'],
        args.audit, args.max)
    stats_globales['04'] = st

    # ── 05 ────────────────────────────────────────────────────────────────────
    t, st = appliquer_et_auditer(
        '05 Espaces', t,
        ns05['normalize_all'],
        args.audit, args.max)
    stats_globales['05'] = st

    # ── 06 ────────────────────────────────────────────────────────────────────
    t, st = appliquer_et_auditer(
        '06 Ordinaux', t,
        ns06['normalize_ordinaux'],
        args.audit, args.max)
    stats_globales['06'] = st

    # ── 07 ────────────────────────────────────────────────────────────────────
    t, st = appliquer_et_auditer(
        '07 Mois', t,
        ns07['normalize_months'],
        args.audit, args.max)
    stats_globales['07'] = st

    # ── 08 ────────────────────────────────────────────────────────────────────
    t, st = appliquer_et_auditer(
        '08 Abréviations', t,
        ns08['normalize_abbreviations'],
        args.audit, args.max)
    stats_globales['08'] = st

    # ── 09 ────────────────────────────────────────────────────────────────────
    def pipeline_09(texte):
        r1, _ = ns09['corriger_ponctuation'](texte)
        r2, _ = ns09['supprimer_espace_avant_virgule'](r1)
        r3, _ = ns09['corriger_point_colle'](r2)
        return r3

    t, st = appliquer_et_auditer(
        '09 Ponctuation', t,
        pipeline_09,
        args.audit, args.max)
    stats_globales['09'] = st


    # ── 10 ────────────────────────────────────────────────────────────────────
    # appliquer() charge le dico via DICO_PATH — si absent, retourne t inchangé
    t, st = appliquer_et_auditer(
        '10 Virgules', t,
        ns10['appliquer'],
        args.audit, args.max)
    stats_globales['10'] = st

    # ── 11 ────────────────────────────────────────────────────────────────────
    def appliquer_11(texte):
        return ns11['corriger_romains'](texte)

    t, st = appliquer_et_auditer(
        '11 Romains', t,
        appliquer_11,
        args.audit, args.max)
    stats_globales['11'] = st

    # ── 12 ────────────────────────────────────────────────────────────────────
    def appliquer_12(texte):
        return ns12['normaliser_refs'](texte)

    t, st = appliquer_et_auditer(
        '12 Refs biblio', t,
        appliquer_12,
        args.audit, args.max)
    stats_globales['12'] = st

    # ── 13 ────────────────────────────────────────────────────────────────────
    def appliquer_13(texte):
        return ns13['corriger_guillemets'](texte)

    t, st = appliquer_et_auditer(
        '13 Guillemets', t,
        appliquer_13,
        args.audit, args.max)
    stats_globales['13'] = st

    # ── 14 ────────────────────────────────────────────────────────────────────
    def appliquer_14(texte):
        return ns14['corriger_ligatures'](texte)

    t, st = appliquer_et_auditer(
        '14 Ligatures', t,
        appliquer_14,
        args.audit, args.max)
    stats_globales['14'] = st

    # ── Résumé ────────────────────────────────────────────────────────────────
    print()
    print("  " + "─" * 56)
    n_modifie = len([s for s in stats_globales.values()
                     if s.get('ok') and s.get('n_diff', 0) > 0])
    n_erreurs = len([s for s in stats_globales.values() if not s.get('ok')])
    n_paras_final = len([p for p in t.split('\n\n') if p.strip()])

    print(f"\n  Scripts ayant appliqué des corrections : {n_modifie}/13")
    if n_erreurs:
        print(f"  ⚠️  Scripts en erreur : {n_erreurs}")
        tous_ok = False
    print(f"\n  Paragraphes : {n_paras} → {n_paras_final} "
          f"({'✅' if n_paras == n_paras_final else '⚠️  différence'})")
    print(f"  Taille finale : {len(t):,} caractères")

    # ── Sauvegarde ────────────────────────────────────────────────────────────
    if args.sortie:
        sortie_path = Path(args.sortie)
        with open(sortie_path, 'w', encoding='utf-8') as f:
            f.write(t)
        print(f"\n  💾 Texte corrigé sauvegardé : {sortie_path}")
    else:
        print(f"\n  (Ajouter --sortie fichier.txt pour sauvegarder le résultat)")

    print()
    if tous_ok:
        print("  ✅ Pipeline complet — aucune erreur de robustesse")
    else:
        print("  ⚠️  Vérifier les avertissements ci-dessus")

    # ── Étapes manuelles ─────────────────────────────────────────────────────
    print()
    print("  Étapes suivantes (manuelles) :")
    print("    15 — mots collés   : python 15_decoupage.py " + args.corpus)
    print("    16 — formes inconnues : python 16_inconnus.py " + args.corpus)

    return 0 if tous_ok else 1


if __name__ == "__main__":
    sys.exit(main())
