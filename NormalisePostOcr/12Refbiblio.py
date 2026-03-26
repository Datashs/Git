#!/usr/bin/env python3
# -*- coding: utf-8 -*-

r"""
===============================================================================
RÈGLE 12 : NORMALISATION DES RÉFÉRENCES BIBLIOGRAPHIQUES
===============================================================================

Description :
    
    Normalise le format des références bibliographiques dans le texte.
    Corrige les espaces manquantes et la ponctuation fautive dans les
    abréviations de tome et de pages courantes dans ce corpus.
    Vise les les erreurs courantes comme "T.VI" → "T. VI", "pp.582" → "pp. 582",
    "p.582" → "p. 582".

AVERTISSEMENT — RÈGLES CALIBRÉES SUR UN CORPUS SPÉCIFIQUE
==========================================================
Ce script a été établi par analyse exhaustive du corpus :
    Annuaire de l'Institut de droit international, volume 1 (Gallica XIXe)
    Fichier de référence : jette (763 276 caractères). 
    De manière générale un script déterministe peut avoir une forme générique
    mais il convient de l'ajuster au corpus que l'on travaille.

De nombreuses règles initialement envisagées ont été supprimées car
ABSENTES du corpus de référence (0 occurrence) :

    ❌ p.NNN   — p. collé : absent
    ❌ pp,NNN  — virgule pour point : absent
    ❌ vol.N   — vol. collé : absent
    ❌ n°N     — n° collé : absent
    ❌ et. ss. — point sur "et" : absent
    ❌ 582 – 584 — tirets typographiques dans intervalles : absent
    ❌ --normalize-dashes — DANGEREUX : 2843 tirets de dialogue dans
       le corpus seraient remplacés (— Réponse du président, etc.)

Ces règles restent dans le script COMMENTÉES avec leur explication,
pour faciliter l'adaptation à un autre corpus.

Pour adapter ce script : décommenter les règles pertinentes et valider
sur un échantillon du nouveau corpus avant toute application complète.

Fonctions (règles actives) :
    1. T.VI  → T. VI   (espace après T. avant chiffre romain collé)
    2. pp.N  → pp. N   (espace après pp. avant chiffre collé)
    3. T. I,pp.N → T. I, pp. N  (virgule+espace manquants entre tome et pages)
    4. et ss,  → et ss.  (virgule au lieu du point dans "et suivantes")
    5. et ss;  → et ss.  (point-virgule au lieu du point)
    6. et ss\b → et ss.  (point final manquant dans "et suivantes")

Exemples :
    Entrée :  "T.VI, pp.582-584"          Sortie :  "T. VI, pp. 582-584"
    Entrée :  "T. I,pp.118 et ss."        Sortie :  "T. I, pp. 118 et ss."
    Entrée :  "pp. 53 et ss,, de M."      Sortie :  "pp. 53 et ss., de M."
    Entrée :  "pp. 179 et↵ss,, de M."     Sortie :  "pp. 179 et↵ss., de M."
    Entrée :  "et ss.) sont"              Sortie :  "et ss.) sont"  (intact)

Risque : Faible (après suppression des règles non vérifiées)
    - Règles 1-3 : motifs très spécifiques, jamais de faux positif connu
    - Règles 4-6 : "et ss" suivi de ,;  ou fin de mot → sûr dans ce corpus
    - Idempotent : appliquer deux fois donne le même résultat

Dépendances :
    - Règles 1 à 11 (normalisations préalables recommandées)
    - Aucune bibliothèque externe nécessaire (uniquement standard)

USAGE :
    python 12_refs.py INPUT [-o OUTPUT] [--stats]

ARGUMENTS :
    INPUT                  Fichier d'entrée (texte brut) - OBLIGATOIRE
    -o, --output OUTPUT    Fichier de sortie (optionnel)
                           Défaut: INPUT_refs.txt
    --stats                Affiche le détail des corrections par règle

EXEMPLES :
    python 12_refs.py document.txt
    python 12_refs.py document.txt --stats
    python 12_refs.py data.txt -o propre.txt

Pièges Python et points d'attention :
    1. ORDRE DES RÈGLES — LA PLUS SPÉCIFIQUE EN PREMIER :
       La règle "et ss," (avec virgule) doit passer AVANT la règle
       "et ss" (sans point), sinon "et ss," devient "et ss.," (doublon).
       Principe : les règles avec suffixe explicite avant les règles génériques.

    2. RÈGLE AVEC GROUPE DE CAPTURE ET RÉINJECTION :
       Pour T. I,pp.N la règle capture le séparateur (T. I) avec un groupe
       et le réinjecte dans le remplacement avec \1.
       r'\b(T\.\s*[IVXLCDM]+),pp\.(\d)' → r'\1, pp. \2'

    3. POURQUOI PAS --normalize-dashes :
       Le tiret cadratin (—) a 2843 occurrences dans ce corpus, dont la
       grande majorité sont des tirets de dialogue ou de ponctuation
       (— Réponse du président). Remplacer tous les — par - détruirait
       la typographie du texte. La normalisation des tirets doit être
       restreinte au contexte numérique (\d+–\d+) et vérifiée sur corpus.

    4. re.subn() POUR LE COMPTAGE :
       re.subn(pattern, repl, texte) retourne (nouveau_texte, nb_substitutions).
       Permet de compter les corrections en une seule passe sans second parcours.

    5. IDEMPOTENCE — VÉRIFIER APRÈS CHAQUE AJOUT DE RÈGLE :
       Une règle mal ordonnée peut créer un cycle : la règle A transforme
       X en Y, et la règle B retransforme Y en X. Toujours tester
       normaliser_refs(normaliser_refs(texte)) == normaliser_refs(texte).

===============================================================================
r"""

import argparse
import re
import sys
from pathlib import Path

# =============================================================================
# PARAMÈTRES CONFIGURABLES
# =============================================================================
# Chaque règle est un tuple (pattern, remplacement, label, explication).
# L'ORDRE EST CRITIQUE : les plus spécifiques en premier.
# Voir la section "Pièges" pour le détail.
#
# Règles COMMENTÉES = absentes du corpus de référence.
# Les décommenter après vérification sur un nouveau corpus cible.

CORRECTIONS = [
    # ------------------------------------------------------------------
    # Règle 1 : T. I,pp.N → T. I, pp. N  (AVANT les règles 2 et 3)
    # Virgule et espace manquantes entre numéro de tome et pp.
    #
    # ORDRE CRITIQUE : cette règle doit passer AVANT la règle "pp.N",
    # sinon "T. I,pp.118" est d'abord transformé en "T. I,pp. 118"
    # par la règle pp.N, puis la règle 1 ne peut plus matcher (pattern
    # attendait ",pp." mais trouve ",pp. " avec espace).
    #
    # Le pattern (T\.\s*[IVXLCDM]+),\s*pp\.?\s*(\d) est robuste :
    # \s* absorbe l'espace éventuel → idempotent sur "T. I, pp. 118".
    # ------------------------------------------------------------------
    (
        r'\b(T\.\s*[IVXLCDM]{1,8}),\s*pp\.?\s*(\d)',
        r'\1, pp. \2',
        'T.romain,pp.N → T. romain, pp. N',
        'Virgule+espace manquantes entre tome et pages (1 cas corpus)'
    ),

    # ------------------------------------------------------------------
    # Règle 2 : T.VI → T. VI
    # Espace manquante entre T. et le chiffre romain.
    # \b évite de capturer en milieu de mot.
    # Ne matche pas si l'espace est déjà présente (T. VI ne matche pas
    # car [IVXLCDM] ne peut pas commencer après une espace dans ce pattern).
    # ------------------------------------------------------------------
    (
        r'\b(T\.)([IVXLCDM]{1,8})\b',
        r'\1 \2',
        'T.romain → T. romain',
        'Espace manquante entre T. et le chiffre romain (2 cas corpus)'
    ),

    # ------------------------------------------------------------------
    # Règle 3 : pp.N → pp. N
    # Espace manquante entre pp. et le numéro de page.
    # Placée APRÈS la règle 1 pour éviter le problème d'ordre.
    # ------------------------------------------------------------------
    (
        r'\bpp\.(\d)',
        r'pp. \1',
        'pp.N → pp. N',
        'Espace manquante entre pp. et le numéro de page (3 cas corpus)'
    ),

    # ------------------------------------------------------------------
    # Règle 4 : et ss, → et ss.  et  et ss; → et ss.
    # "et suivantes" doit se terminer par un point.
    # La virgule ou le point-virgule sont des erreurs OCR pour le point.
    # DOIT passer avant la règle 5 (générique sans ponctuation),
    # sinon "et ss," → "et ss.," (doublon de ponctuation).
    # \n est inclus dans \s donc fonctionne sur les sauts de ligne OCR.
    # ------------------------------------------------------------------
    (
        r'\bet(\s+)ss[,;]',
        r'et\1ss.',
        'et ss,/ss; → et ss.',
        'Virgule ou point-virgule erroné après ss (12 cas corpus)'
    ),

    # ------------------------------------------------------------------
    # Règle 5 : et ss (sans point final) → et ss.
    # "et ss" sans ponctuation finale : point manquant.
    # (?!\.) vérifie que le point n'est pas déjà présent.
    # (?![,;]) évite le doublon si la règle 4 n'a pas suffi.
    # Placée APRÈS la règle 4 pour éviter le cycle.
    # ------------------------------------------------------------------
    (
        r'\bet(\s+)ss\b(?![.,;])',
        r'et\1ss.',
        'et ss → et ss.',
        'Point final manquant après ss (13 cas corpus)'
    ),

    # ══════════════════════════════════════════════════════════════════
    # RÈGLES COMMENTÉES — ABSENTES DU CORPUS DE RÉFÉRENCE
    # Décommenter après vérification sur un nouveau corpus.
    # ══════════════════════════════════════════════════════════════════

    # p.NNN → p. NNN  (0 cas dans le corpus jette)
    # (r'\bp\.(\d)', r'p. \1',
    #  'p.N → p. N', 'Espace manquante après p. (absent du corpus)'),

    # pp,NNN → pp. NNN  (0 cas dans le corpus jette)
    # (r'\bpp,(\d)', r'pp. \1',
    #  'pp,N → pp. N', 'Virgule au lieu du point après pp (absent du corpus)'),

    # p,NNN → p. NNN  (0 cas)
    # (r'\bp,(\d)', r'p. \1',
    #  'p,N → p. N', 'Virgule au lieu du point après p (absent du corpus)'),

    # et. ss. → et ss.  (0 cas dans le corpus jette)
    # (r'\bet\.\s+ss\.', 'et ss.',
    #  'et. ss. → et ss.', 'Point fautif sur "et" (absent du corpus)'),

    # vol.N → vol. N  (0 cas)
    # (r'\bvol\.(\d)', r'vol. \1',
    #  'vol.N → vol. N', 'Espace manquante après vol. (absent du corpus)'),

    # vol,N → vol. N  (0 cas)
    # (r'\bvol,(\d)', r'vol. \1',
    #  'vol,N → vol. N', 'Virgule au lieu du point après vol (absent du corpus)'),

    # n°N → n° N  (0 cas)
    # (r'n°(\d)', r'n° \1',
    #  'n°N → n° N', 'Espace manquante après n° (absent du corpus)'),

    # 582 – 584 → 582-584 (tirets typographiques dans intervalles — 0 cas)
    # ATTENTION : ne jamais appliquer sur tout le texte sans restriction
    # au contexte numérique (\d+\s*[–—]\s*\d+) — les tirets de dialogue
    # et de ponctuation seraient détruits.
    # (r'(\d+)\s*[–—]\s*(\d+)', r'\1-\2',
    #  'N – N → N-N', 'Tirets typographiques dans intervalles (absent du corpus)'),
]

ENCODAGE_LECTURE = 'utf-8'
ENCODAGE_LECTURE_FALLBACK = 'latin1'
ENCODAGE_ECRITURE = 'utf-8'
# =============================================================================


# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def normaliser_refs(texte: str) -> tuple:
    r"""
    Applique toutes les corrections de références bibliographiques.

    Args:
        texte (str): Texte d'entrée

    Returns:
        tuple: (texte_corrigé: str, nb_total: int, détails: list[dict])

    Pipeline :
        Les règles sont appliquées dans l'ordre de CORRECTIONS.
        L'ordre est critique — voir le piège 1 dans la docstring module.

    Note sur re.subn() :
        re.subn(pattern, repl, texte) retourne (nouveau_texte, nb_substitutions).
        Équivalent à re.sub() mais avec le comptage intégré en une passe.

    Note sur les groupes de capture dans les remplacements :
        Plusieurs règles utilisent des groupes (\1, \2) pour réinjecter
        du contexte capturé. Ex : r'\b(T\.)([IVXLCDM]+)\b' → r'\1 \2'
        capture séparément T. et le romain, et réinsère les deux avec
        une espace entre eux. Sans le groupe \1, le T. serait perdu.
    r"""
    result = texte
    details = []
    total = 0

    for pattern, remplacement, label, _ in CORRECTIONS:
        nouveau, n = re.subn(pattern, remplacement, result)
        if n > 0:
            for m in re.finditer(pattern, result):
                pos = m.start()
                ctx = result[max(0, pos - 30):pos + 35].replace('\n', '↵')
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
        dict: {label: nb_occurrences} pour chaque règle active

    Utilisé pour les statistiques avant/après dans main().
    r"""
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
    r"""

    # -------------------------------------------------------------------------
    # BLOC 1 : CONFIGURATION DU PARSER D'ARGUMENTS
    # -------------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        description=r"""
RÈGLE 12 : NORMALISATION DES RÉFÉRENCES BIBLIOGRAPHIQUES

Corrige les espaces et ponctuation dans les références de tome, page
et "et suivantes". Règles calibrées pour le corpus Annuaire IDI (Gallica).
Voir les règles commentées en haut du script pour d'autres corpus.
r""",
        epilog=r"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         1. RÈGLES ACTIVES (CORPUS ANNUAIRE IDI)               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  1. T.VI   → T. VI    espace après T. avant romain collé         (2 cas)    ║
║  2. pp.N   → pp. N    espace après pp. avant chiffre collé       (3 cas)    ║
║  3. T.I,pp.N → T. I, pp. N    virgule+espace manquants           (1 cas)    ║
║  4. et ss, → et ss.   virgule erronée après ss                   (12 cas)   ║
║  5. et ss  → et ss.   point final manquant                       (13 cas)   ║
║                                                              ──────────     ║
║  Total sur corpus de référence : ~31 corrections, 0 faux positif            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                    2. RÈGLES COMMENTÉES (ABSENTES DU CORPUS)                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Ces règles existent dans le script mais sont désactivées car elles n'ont   ║
║  aucune occurrence dans ce corpus. Les décommenter pour un autre corpus :   ║
║  p.N, pp,N, p,N, et. ss., vol.N, vol,N, n°N, tirets typographiques.        ║
║                                                                               ║
║  ⚠️  NE PAS activer --normalize-dashes sans restriction numérique :          ║
║     2843 tirets de dialogue dans ce corpus seraient détruits.               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                               3. EXEMPLES                                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  "T.VI, pp.582-584"       →  "T. VI, pp. 582-584"                           ║
║  "T. I,pp.118 et ss."     →  "T. I, pp. 118 et ss."                        ║
║  "pp. 53 et ss,, de M."   →  "pp. 53 et ss., de M."                        ║
║  "pp. 179 et↵ss,, de M."  →  "pp. 179 et↵ss., de M."                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                          4. PIÈGES PYTHON À ÉVITER                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  1. ORDRE DES RÈGLES : règles spécifiques (avec ,;) AVANT génériques.       ║
║     Sans ça : "et ss," → "et ss.," (doublon).                               ║
║                                                                               ║
║  2. GROUPES DE CAPTURE : (T\.)([IVXLCDM]+) → \1 \2 réinjecte le préfixe.  ║
║     Sans \1, le "T." serait perdu dans le remplacement.                     ║
║                                                                               ║
║  3. re.subn() : retourne (texte, nb_substitutions) en une seule passe.     ║
║                                                                               ║
║  4. IDEMPOTENCE : toujours vérifier après ajout d'une règle.               ║
║     Un cycle A→B→A brise l'idempotence et multiplierait les passes.         ║
╚══════════════════════════════════════════════════════════════════════════════╝
r""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # -------------------------------------------------------------------------
    # BLOC 2 : DÉFINITION DES ARGUMENTS
    # -------------------------------------------------------------------------
    parser.add_argument('input', help="Fichier d'entrée (texte brut) - OBLIGATOIRE")
    parser.add_argument('-o', '--output',
                        help="Fichier de sortie - Défaut: INPUT_refs.txt")
    parser.add_argument('--stats', action='store_true',
                        help="Affiche le détail des corrections par règle")

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
        suffix = "_refs"
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
    print(f"   Total caractères     : {len(texte):,}")
    print(f"   Corrections détectées : {total_avant}")
    for label, n in stats_avant.items():
        if n > 0:
            print(f"      {label:35s} : {n}")

    # -------------------------------------------------------------------------
    # BLOC 7 : APPLICATION DES CORRECTIONS
    # -------------------------------------------------------------------------
    print("🔄 Normalisation des références bibliographiques...")
    texte_corrige, total, details = normaliser_refs(texte)

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
            print(f"      L{d['ligne']:5d} | {d['label']:35s} | "
                  f"{repr(d['avant']):20s} → {repr(d['apres'])}")
            print(f"             {repr(d['contexte'])}")

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
