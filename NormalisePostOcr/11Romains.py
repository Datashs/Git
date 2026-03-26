#!/usr/bin/env python3
# -*- coding: utf-8 -*-

r"""
===============================================================================
RÈGLE 11 : CORRECTION DES CHIFFRES ROMAINS MAL RECONNUS PAR L'OCR
===============================================================================

AVERTISSEMENT — SCRIPT ADAPTÉ À UN CORPUS SPÉCIFIQUE
=====================================================
Ce script est conçu et validé pour le corpus :
    Annuaire de l'Institut de droit international (Gallica, XIXe siècle)
    Fichier de référence : jette (763 276 caractères)

Il N'EST PAS un correcteur générique de chiffres romains. Ses règles
ont été établies par analyse exhaustive du corpus cible et ne doivent
pas être appliquées à un autre corpus sans révision préalable.

En particulier :
  - Les règles sont intentionnellement peu nombreuses (4 règles, 12 cas)
  - Chaque règle repose sur un contexte spécifique à ce corpus
  - "Vit" → "VII" n'est valide QUE dans "T. Vit" (tome bibliographique)
  - "Il" → "II" n'est valide QUE précédé de "T." ou "I." (tome/item)

Pour adapter ce script à un autre corpus, relancer l'analyse sur le
nouveau corpus et réviser les règles dans la section PARAMÈTRES.

Pourquoi si peu de règles ?
===========================
L'analyse du corpus montre 199 occurrences de "Il" (potentiel "II"),
mais 196 sont le pronom français — corriger sans contexte produirait
196 faux positifs catastrophiques. Les scripts de ce pipeline
privilégient toujours la précision sur le rappel : mieux vaut ne pas
corriger que de corriger à tort.

Les erreurs OCR de chiffres romains dans ce corpus se concentrent sur
une seule confusion : le "l" minuscule confondu avec le "I" majuscule,
et le "L" majuscule confondu avec le "I" majuscule, dans le chiffre VII.
Cette confusion est visuellement évidente : dans les polices sérif XIXe,
"l" (minuscule) et "I" (majuscule) sont quasi-identiques.

Description des 4 règles :
===========================
1. Vil → VII  (5 cas)
   Le "l" final est un "I" mal reconnu. Apparaît systématiquement
   dans des contextes bibliographiques ("T. Vil", "§ Vil.") ou
   des titres de section ("VIL — DES NON-COMBATTANTS").
   Confusion visuelle : "l" minuscule ≈ "I" majuscule en sérif XIXe.

2. VIL → VII  (3 cas)
   Variante tout-majuscule : le "L" final est un "I" mal reconnu.
   Apparaît dans "CHAPITRE VIL", "t. VIL", "VIL —".
   Confusion visuelle : "L" majuscule ≠ "I" mais l'OCR confond
   les hastes dans les polices condensées de l'imprimé.

3. T. Il → T. II  et  I. Il → I. II  (3 cas)
   "Il" après un indicateur de tome ("T." ou "I.") est le chiffre II,
   pas le pronom. Contexte : références bibliographiques du type
   "T. Il, pp. 179", "T. Il (1870)".
   Sans cet ancrage contextuel, corriger "Il" serait catastrophique :
   199 occurrences dans le corpus dont 196 sont le pronom.

4. T. Vit → T. VII  (1 cas)
   "Vit" serait normalement le verbe "voir/vivre" en français.
   Mais dans "Revue., T. Vit, 1875" le contexte (tome + année)
   lève l'ambiguïté : c'est VII mal reconnu.
   Cette règle serait dangereuse hors contexte "T. + année".

Résultats sur le corpus de référence :
=======================================
  Vil → VII  : 5 corrections
  VIL → VII  : 3 corrections
  T./I. Il → T./I. II : 3 corrections
  T. Vit → T. VII     : 1 correction
  Total               : 12 corrections
  Faux positifs       : 0
  Idempotent          : ✅

Dépendances :
    - Règles 1 à 10 (normalisations préalables recommandées)
    - Aucune bibliothèque externe nécessaire (uniquement standard)

USAGE :
    python 11_romains.py INPUT [-o OUTPUT] [--stats]

ARGUMENTS :
    INPUT                  Fichier d'entrée (texte brut) - OBLIGATOIRE
    -o, --output OUTPUT    Fichier de sortie (optionnel)
                           Défaut: INPUT_romains.txt
    --stats                Affiche chaque correction avec son contexte

EXEMPLES :
    python 11_romains.py document.txt
    python 11_romains.py document.txt --stats
    python 11_romains.py data.txt -o propre.txt

Pièges Python et points d'attention :
    1. LOOKBEHIND À LONGUEUR FIXE :
       Python n'autorise pas les lookbehind à longueur variable.
       (?<=T\.\s*)Il ne fonctionne pas car \s* est de longueur variable.
       Solution : capturer le préfixe dans un groupe et le réinjecter
       avec \1 dans le remplacement : (T\.|I\.)\s*Il → \1 II

    2. ORDRE DES RÈGLES :
       Les règles sont appliquées dans l'ordre de CORRECTIONS.
       Vil et VIL doivent passer avant toute règle qui toucherait
       à "VII" pour préserver l'idempotence.

    3. IDEMPOTENCE :
       Appliquer le script deux fois donne le même résultat.
       "VII" ne matche aucune des règles (ni Vil, ni VIL, ni Il après T.).

    4. re.subn() :
       Retourne (nouveau_texte, nb_substitutions) en une seule passe,
       sans nécessiter de second comptage.

===============================================================================
"""

import argparse
import re
import sys
from pathlib import Path

# =============================================================================
# PARAMÈTRES CONFIGURABLES
# =============================================================================
# Placés en tête pour faciliter l'adaptation à un autre corpus.
# Modifier uniquement après analyse exhaustive du nouveau corpus cible.
#
# Format de chaque règle :
#   (pattern_regex, remplacement, label_court, explication)
#
# AVERTISSEMENT : ces règles sont calibrées pour le corpus Annuaire IDI.
# Toute modification doit être validée sur le corpus cible avant application.

CORRECTIONS = [
    # ------------------------------------------------------------------
    # Règle 1 : Vil → VII
    # "l" minuscule final confondu avec "I" majuscule par l'OCR.
    # Sûr sans ancrage contextuel car "Vil" n'est pas un mot français
    # courant (à la différence de "vil" en minuscule, qui lui n'est
    # pas capturé grâce à la frontière de mot \b et à la majuscule V).
    # ------------------------------------------------------------------
    (
        r'\bVil\b',
        'VII',
        'Vil → VII',
        'l minuscule confondu avec I majuscule dans VII'
    ),

    # ------------------------------------------------------------------
    # Règle 2 : VIL → VII
    # Variante tout-majuscule : "L" final confondu avec "I" dans les
    # polices condensées de l'imprimé XIXe.
    # Sûr sans ancrage car "VIL" tout-majuscule n'est pas un mot français.
    # ------------------------------------------------------------------
    (
        r'\bVIL\b',
        'VII',
        'VIL → VII',
        'L majuscule confondu avec I majuscule dans VII'
    ),

    # ------------------------------------------------------------------
    # Règle 3 : T. Il → T. II  et  I. Il → I. II
    # "Il" après un indicateur de tome est le chiffre II, pas le pronom.
    # L'ancrage sur T. ou I. est indispensable : sans lui, "Il" serait
    # corrigé dans 196 pronoms supplémentaires.
    #
    # Technique Python : lookbehind à longueur variable interdit →
    # on capture le préfixe (T. ou I.) dans le groupe \1 et on le
    # réinjecte dans le remplacement avec r'\1 II'.
    #
    # Note : \s* entre T. et Il absorbe l'espace éventuelle. Le
    # remplacement r'\1 II' insère une espace normalisée.
    # ------------------------------------------------------------------
    (
        r'\b(T\.|I\.)\s*Il\b',
        r'\1 II',
        'T./I. Il → T./I. II',
        'Il = chiffre II dans référence de tome bibliographique'
    ),

    # ------------------------------------------------------------------
    # Règle 4 : T. Vit → T. VII
    # "Vit" serait le verbe "voir/vivre" en français courant.
    # L'ancrage "T." (tome) lève l'ambiguïté : dans une référence
    # bibliographique, seul un chiffre peut suivre "T.".
    # Un seul cas dans le corpus (L1004) : "Revue., T. Vit, 1875".
    # Ne pas appliquer hors du contexte "T. + Vit".
    # ------------------------------------------------------------------
    (
        r'\bT\.\s*Vit\b',
        'T. VII',
        'T. Vit → T. VII',
        'Vit = chiffre VII dans référence de tome (contexte sûr uniquement)'
    ),
]

ENCODAGE_LECTURE = 'utf-8'
ENCODAGE_LECTURE_FALLBACK = 'latin1'
ENCODAGE_ECRITURE = 'utf-8'
# =============================================================================


# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def corriger_romains(texte: str) -> tuple:
    r"""
    Applique toutes les corrections de chiffres romains au texte.

    Args:
        texte (str): Texte d'entrée

    Returns:
        tuple: (texte_corrigé: str, nb_total: int, détails: list[dict])

    Pipeline :
        Les règles sont appliquées dans l'ordre de CORRECTIONS.
        Chaque règle utilise re.subn() pour compter les substitutions
        sans second passage sur le texte.

    Note sur re.subn() :
        re.subn(pattern, repl, texte) retourne (nouveau_texte, nb_substitutions).
        Équivalent à re.sub() mais avec le comptage intégré.

    Note sur le groupe de capture dans la règle 3 :
        r'\b(T\.|I\.)\s*Il\b' → r'\1 II'
        Le \1 réinjecte le préfixe capturé (T. ou I.) dans le résultat.
        Sans cela, "T. Il" deviendrait " II" (préfixe perdu).
    """
    result = texte
    details = []
    total = 0

    for pattern, remplacement, label, explication in CORRECTIONS:
        nouveau, n = re.subn(pattern, remplacement, result)
        if n > 0:
            # Collecter les contextes pour --stats
            for m in re.finditer(pattern, result):
                pos = m.start()
                ctx = result[max(0, pos - 35):pos + 35].replace('\n', '↵')
                ligne = result[:pos].count('\n') + 1
                details.append({
                    'ligne': ligne,
                    'avant': m.group(),
                    'apres': re.sub(pattern, remplacement, m.group()),
                    'contexte': ctx,
                    'label': label,
                })
            result = nouveau
            total += n

    return result, total, details


def compter_candidats(texte: str) -> dict:
    r"""
    Compte les occurrences corrigeables avant traitement.

    Args:
        texte (str): Texte à analyser

    Returns:
        dict: Nombre de correspondances par règle

    Utilisé pour les statistiques avant/après dans main().
    """
    stats = {}
    for pattern, _, label, _ in CORRECTIONS:
        stats[label] = len(re.findall(pattern, texte))
    return stats


# =============================================================================
# FONCTION PRINCIPALE
# =============================================================================

def main():
    r"""
    Fonction principale du script.

    Structure :
    1.  Configuration du parser d'arguments
    2.  Analyse des arguments
    3.  Préparation des chemins de fichiers
    4.  Lecture du fichier
    5.  Statistiques avant traitement
    6.  Application des corrections
    7.  Affichage des détails (si --stats)
    8.  Écriture du résultat
    9.  Fin du traitement
    """

    # -------------------------------------------------------------------------
    # BLOC 1 : CONFIGURATION DU PARSER D'ARGUMENTS
    # -------------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        description="""
RÈGLE 11 : CORRECTION DES CHIFFRES ROMAINS MAL RECONNUS PAR L'OCR

Script adapté au corpus : Annuaire de l'Institut de droit international
(Gallica XIXe siècle). Ne pas appliquer sur un autre corpus sans révision
des règles dans CORRECTIONS (en haut du script).
""",
        epilog=r"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         1. SCRIPT CORPUS-SPÉCIFIQUE                           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Ce script est calibré pour le corpus Annuaire IDI (Gallica XIXe).          ║
║  Ses 4 règles ont été établies par analyse exhaustive du corpus cible.      ║
║  Pour un autre corpus, réviser CORRECTIONS en haut du script.               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                            2. RÈGLES APPLIQUÉES                               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  1. Vil  → VII   l minuscule confondu avec I majuscule              (5 cas) ║
║  2. VIL  → VII   L majuscule confondu avec I majuscule              (3 cas) ║
║  3. T./I. Il → T./I. II   Il = II dans référence de tome           (3 cas) ║
║  4. T. Vit → T. VII   Vit = VII dans référence de tome             (1 cas) ║
║                                                                    ─────── ║
║  Total sur corpus de référence : 12 corrections, 0 faux positif            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                            3. POURQUOI SI PEU ?                               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  "Il" apparaît 199 fois dans le corpus — 196 fois c'est le pronom.         ║
║  Corriger "Il" sans contexte strict produirait 196 faux positifs.           ║
║  Les règles 3 et 4 utilisent un ancrage contextuel (T., I.) pour           ║
║  discriminer le chiffre du pronom. Sans ancrage, pas de correction.        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                         4. PIÈGES PYTHON À ÉVITER                             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  1. LOOKBEHIND À LONGUEUR VARIABLE :                                         ║
║     (?<=T\.\s*) est interdit en Python (longueur variable).                 ║
║     Solution : capturer le préfixe — (T\.|I\.)\s*Il → \1 II               ║
║                                                                               ║
║  2. re.subn() vs re.sub() :                                                  ║
║     re.subn() retourne (texte, nb_substitutions) en une seule passe.       ║
║     Évite un second passage pour compter les corrections.                  ║
║                                                                               ║
║  3. IDEMPOTENCE :                                                            ║
║     "VII" ne matche aucune règle → appliquer deux fois = même résultat.   ║
╚══════════════════════════════════════════════════════════════════════════════╝
""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # -------------------------------------------------------------------------
    # BLOC 2 : DÉFINITION DES ARGUMENTS
    # -------------------------------------------------------------------------
    parser.add_argument('input', help="Fichier d'entrée (texte brut) - OBLIGATOIRE")
    parser.add_argument('-o', '--output',
                        help="Fichier de sortie - Défaut: INPUT_romains.txt")
    parser.add_argument('--stats', action='store_true',
                        help="Affiche chaque correction avec son contexte")

    # -------------------------------------------------------------------------
    # BLOC 3 : ANALYSE DES ARGUMENTS
    # -------------------------------------------------------------------------
    args = parser.parse_args()

    # -------------------------------------------------------------------------
    # BLOC 4 : PRÉPARATION DES CHEMINS DE FICHIERS
    # -------------------------------------------------------------------------
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Erreur : le fichier {input_path} n'existe pas")
        sys.exit(1)

    if args.output:
        output_path = Path(args.output)
    else:
        suffix = "_romains"
        try:
            output_path = input_path.with_stem(input_path.stem + suffix)
        except AttributeError:
            output_path = input_path.with_name(
                input_path.stem + suffix + input_path.suffix)

    # -------------------------------------------------------------------------
    # BLOC 5 : LECTURE DU FICHIER D'ENTRÉE
    # -------------------------------------------------------------------------
    print(f"📖 Lecture de {input_path}...")
    try:
        with open(input_path, 'r', encoding=ENCODAGE_LECTURE) as f:
            texte = f.read()
        print(f"   Encodage utilisé : {ENCODAGE_LECTURE}")
    except UnicodeDecodeError:
        print(f"⚠️  Échec avec {ENCODAGE_LECTURE}, "
              f"tentative avec {ENCODAGE_LECTURE_FALLBACK}...")
        try:
            with open(input_path, 'r', encoding=ENCODAGE_LECTURE_FALLBACK) as f:
                texte = f.read()
            print(f"   Encodage utilisé : {ENCODAGE_LECTURE_FALLBACK}")
        except Exception as e:
            print(f"❌ Erreur de lecture : {e}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Erreur inattendue : {e}")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # BLOC 6 : STATISTIQUES AVANT TRAITEMENT
    # -------------------------------------------------------------------------
    stats_avant = compter_candidats(texte)
    total_avant = sum(stats_avant.values())
    print(f"   Total caractères : {len(texte):,}")
    print(f"   Corrections détectées : {total_avant}")
    if total_avant > 0:
        for label, n in stats_avant.items():
            if n > 0:
                print(f"      {label:30s} : {n}")

    # -------------------------------------------------------------------------
    # BLOC 7 : APPLICATION DES CORRECTIONS
    # -------------------------------------------------------------------------
    print("🔄 Correction des chiffres romains...")
    texte_corrige, total, details = corriger_romains(texte)

    if total > 0:
        print(f"   ✅ {total} correction(s) effectuée(s)")
    else:
        print("   ℹ️  Aucune modification nécessaire")

    # -------------------------------------------------------------------------
    # BLOC 8 : AFFICHAGE DES DÉTAILS (--stats)
    # -------------------------------------------------------------------------
    if args.stats and details:
        print("\n   Détail des corrections :")
        for d in details:
            print(f"      L{d['ligne']:5d} | {d['label']:25s} | "
                  f"{repr(d['avant']):12s} → {repr(d['apres']):12s}")
            print(f"             contexte : {repr(d['contexte'])}")

    # -------------------------------------------------------------------------
    # BLOC 9 : ÉCRITURE DU FICHIER DE SORTIE
    # -------------------------------------------------------------------------
    print(f"💾 Écriture de {output_path}...")
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding=ENCODAGE_ECRITURE) as f:
            f.write(texte_corrige)
        if output_path.exists():
            taille = output_path.stat().st_size
            print(f"   ✅ Fichier écrit : {taille:,} octets")
    except PermissionError:
        print(f"❌ Permission refusée : {output_path}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Erreur d'écriture : {e}")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # BLOC 10 : FIN DU TRAITEMENT
    # -------------------------------------------------------------------------
    print("✅ Terminé avec succès")
    return 0


# =============================================================================
# POINT D'ENTRÉE
# =============================================================================
if __name__ == "__main__":
    sys.exit(main())
