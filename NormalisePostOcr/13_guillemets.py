#!/usr/bin/env python3
# -*- coding: utf-8 -*-

r"""
===============================================================================
RÈGLE 13 : CORRECTION DES GUILLEMETS PARASITES OCR
===============================================================================

AVERTISSEMENT — CE SCRIPT N'EST PAS UN NORMALISATEUR DE GUILLEMETS
===================================================================


    Les guillemets «/» sont DÉJÀ CORRECTS dans le corpus traité (187 «, 391 »).
    Le déséquilibre «/» apparent (187 vs 391) est normal : les longues
    citations XIXe commencent chaque ligne par », sans « répété.

    Les 77 guillemets droits (") présents dans l'échantillon examiné
      ne sont PAS des guillemets de citation. 
      Ce sont des artefacts OCR de trois types :

    TYPE 1 — Format bibliographique (9 cas) :
        "in-8°" imprimé en XIXe lu comme "in-8"" par l'OCR.
        Le guillemet remplace le signe degré °.
        Ex : 'in-8", 670 pp.' → 'in-8°, 670 pp.'

    TYPE 2 — Numérotation d'articles (18 cas) :
        Un guillemet précède un numéro en début de paragraphe.
        Ex : '\n"5. — ITALIE.'  → '\n5. — ITALIE.'

    TYPE 3 — Numéros ordinaux tronqués (9 cas) :
        Un numéro suivi de " en début de paragraphe représente un ordinal.
        Ex : '\n2" S'ils ont' → '\n2° S'ils ont'

    TYPE 4 — Artefacts collés divers (41 cas) :
        Guillemets parasites au milieu du texte sans pattern identifiable.
        Trop hétérogènes pour une règle automatique sûre.
        Ces 41 cas sont laissés pour correction manuelle.

Ce script, sur l'échantillon traité, corrige les 36 cas des types 1, 2 et 3.
Il NE fait PAS de "normalisation de guillemets" au sens typographique.

Pourquoi pas les types « » → " " ?
    L'opération inverse (guillemets français → anglais) n'est jamais
    nécessaire sur ce corpus. Les «/» présents sont intentionnels.

Fonctions (règles actives) :
    1. in-N" → in-N°  et  in N" → in N°
       Formats bibliographiques : in-8°, in-4°, in-18° mal reconnus.
       Couvre les variantes minuscules (in-) et majuscules (In-),
       avec ou sans tiret.

    2. Suppression du " devant un chiffre en début de paragraphe
       Pattern : double saut de ligne + " + chiffre
       Le " est un artefact qui remplace un symbole de numérotation.

    3. N" → N° en début de paragraphe
       Pattern : double saut de ligne + chiffre(s) + " + espace
       Le " remplace le ° dans les numérotations ordinales.

Résultats sur le corpus de référence (jette) :
    Type 1 (in-N")  :  9 corrections
    Type 2 ("chiffre) : 18 corrections
    Type 3 (N" )    :  9 corrections
    Total           : 36 corrections
    Faux positifs   :  0
    Cas résiduels non couverts : 41 (trop hétérogènes)
    Idempotent      : ✅

Dépendances :
    - Règles 1 à 12 (normalisations préalables recommandées)
    - Aucune bibliothèque externe nécessaire (uniquement standard)

USAGE :
    python 13_guillemets.py INPUT [-o OUTPUT] [--stats]

ARGUMENTS :
    INPUT                  Fichier d'entrée (texte brut) - OBLIGATOIRE
    -o, --output OUTPUT    Fichier de sortie (optionnel)
                           Défaut: INPUT_guillemets.txt
    --stats                Affiche chaque correction avec son contexte

EXEMPLES :
    python 13_guillemets.py document.txt
    python 13_guillemets.py document.txt --stats
    python 13_guillemets.py data.txt -o propre.txt

Pièges Python et points d'attention :
    1. LAMBDA DANS re.subn() POUR PRÉSERVER LA CASSE :
       La règle in-N" doit produire 'in-8°' et 'In-8°' selon la casse.
       On ne peut pas écrire un remplacement fixe qui gère les deux.
       Solution : passer une fonction lambda à re.subn() qui reconstruit
       le remplacement à partir des groupes capturés :
           lambda m: m.group(1) + séparateur + m.group(2) + '°'
       Cette technique est plus lisible qu'une regex avec backreference
       conditionnelle.

    2. LOOKBEHIND POUR LES RÈGLES 2 ET 3 :
       (?<=\n\n) est un lookbehind de longueur fixe (2 caractères).
       Il vérifie que le " est précédé de deux sauts de ligne sans
       les consommer dans le match — la substitution ne modifie pas
       les sauts de ligne.

    3. re.subn() POUR LE COMPTAGE :
       re.subn() retourne (nouveau_texte, nb_substitutions) en une passe.
       Évite un second passage pour compter les corrections.

   4. POURQUOI PAS DE RÈGLE GÉNÉRALE POUR LES 41 CAS RÉSIDUELS :
        Ces 41 guillemets parasites apparaissent dans des contextes trop
        hétérogènes pour être couverts par une règle automatique sûre
        (milieu de mot, après ponctuation, avant espace, etc.).
        Le volume est trop faible pour justifier un apprentissage supervisé
        et trop variable pour qu'une règle regex soit sans risque de faux
        positif. La correction manuelle reste ici la solution la plus fiable
        et la plus rapide.

===============================================================================
"""

import argparse
import re
import sys
from pathlib import Path

# =============================================================================
# PARAMÈTRES CONFIGURABLES
# =============================================================================
# Chaque règle est un tuple (pattern, remplacement, label, explication).
#
# Note sur les remplacements :
#   - Règle 1 : remplacement par fonction (lambda) pour préserver la casse
#   - Règles 2 et 3 : remplacement par chaîne, groupes réinjectés avec \1

CORRECTIONS = [
    # ------------------------------------------------------------------
    # Règle 1 : in-N" → in-N°  (formats bibliographiques XIXe)
    # L'OCR confond le signe degré ° avec un guillemet " dans les
    # abréviations de format d'imprimé : in-8°, in-4°, in-18°, in-12°.
    # 
    # Pattern : \b([Ii]n)[ -]?(\d+)"
    #   \b       : frontière de mot (évite de matcher en milieu de mot)
    #   ([Ii]n)  : capture "in" ou "In" (préserve la casse)
    #   [ -]?    : tiret ou espace optionnel (in-8 ou in 8)
    #   (\d+)    : capture le numéro de format
    #   "        : le guillemet parasite à supprimer
    #
    # Remplacement par lambda : réinjecte group(1) (in/In) + séparateur
    # (tiret si présent, espace sinon) + group(2) (nombre) + '°'.
    # ------------------------------------------------------------------
    (
        r'\b([Ii]n)([ -]?)(\d+)"',
        lambda m: m.group(1) + m.group(2) + m.group(3) + '°',
        'in-N" → in-N°',
        'Format bibliographique : in-8°, in-4°... mal reconnus (9 cas corpus)'
    ),

    # ------------------------------------------------------------------
    # Règle 2 : suppression du " devant un chiffre en début de §
    # Pattern : (?<=\n\n)"(\d)
    #   (?<=\n\n) : lookbehind — doit être précédé de deux sauts de ligne
    #              (début de paragraphe dans ce corpus)
    #   "         : le guillemet parasite
    #   (\d)      : premier chiffre du numéro d'article, réinjecté avec \1
    #
    # Le " est un artefact qui remplace un symbole de numérotation
    # (★, ♦, *, ° ou autre) utilisé dans l'imprimé original.
    # Ex : '\n\n"5. — ITALIE.' → '\n\n5. — ITALIE.'
    # ------------------------------------------------------------------
    (
        r'(?<=\n\n)"(\d)',
        r'\1',
        '"chiffre → chiffre (début §)',
        'Guillemet parasite devant numéro d\'article en début de § (18 cas corpus)'
    ),

    # ------------------------------------------------------------------
    # Règle 3 : N" → N° en début de paragraphe
    # Pattern : (?<=\n\n)(\d+)" 
    #   (?<=\n\n) : lookbehind — début de paragraphe
    #   (\d+)     : le numéro ordinal, réinjecté avec \1
    #   "[ ]      : le guillemet suivi d'une espace (évite de matcher
    #              les cas "N"chiffre" qui seraient couverts par règle 2)
    #
    # Le " remplace ° dans les numérotations ordinales des articles.
    # Ex : '\n\n2" S\'ils ont' → '\n\n2° S\'ils ont'
    # ------------------------------------------------------------------
    (
        r'(?<=\n\n)(\d+)" ',
        r'\1° ',
        'N" → N° (début §)',
        'Guillemet remplaçant ° dans numérotation ordinale (9 cas corpus)'
    ),
]

ENCODAGE_LECTURE = 'utf-8'
ENCODAGE_LECTURE_FALLBACK = 'latin1'
ENCODAGE_ECRITURE = 'utf-8'
# =============================================================================


# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def corriger_guillemets(texte: str) -> tuple:
    r"""
    Applique les corrections de guillemets parasites OCR.

    Args:
        texte (str): Texte d'entrée

    Returns:
        tuple: (texte_corrigé: str, nb_total: int, détails: list[dict])

    Pipeline :
        Les 3 règles sont appliquées dans l'ordre de CORRECTIONS.
        Les règles sont indépendantes (patterns disjoints) donc l'ordre
        n'a pas d'impact sur le résultat final, mais l'ordre déclaré
        dans CORRECTIONS est conservé pour la lisibilité.

    Note sur re.subn() avec fonction :
        Quand le remplacement est une fonction (lambda), re.subn() appelle
        la fonction pour chaque correspondance et utilise sa valeur de retour
        comme remplacement. La fonction reçoit l'objet Match.
        re.subn() retourne quand même (texte, nb_substitutions).
    """
    result = texte
    details = []
    total = 0

    for pattern, remplacement, label, _ in CORRECTIONS:
        # Collecter les contextes avant substitution
        for m in re.finditer(pattern, result):
            pos = m.start()
            ctx = result[max(0, pos - 30):pos + 35].replace('\n', '↵')
            ligne = result[:pos].count('\n') + 1
            if callable(remplacement):
                apres = remplacement(m)
            else:
                apres = re.sub(pattern, remplacement, m.group())
            details.append({
                'ligne': ligne,
                'avant': m.group(),
                'apres': apres,
                'contexte': ctx,
                'label': label,
            })

        nouveau, n = re.subn(pattern, remplacement, result)
        result = nouveau
        total += n

    return result, total, details


def compter_guillemets_droits(texte: str) -> dict:
    r"""
    Compte et classifie les guillemets droits (") dans le texte.

    Args:
        texte (str): Texte à analyser

    Returns:
        dict: Statistiques et classification

    Utilisé pour les statistiques avant/après dans main().
    Distingue les cas couverts par les règles des cas résiduels.
    """
    total = texte.count('"')
    couverts = (len(re.findall(r'\b[Ii]n[ -]?\d+"', texte))
                + len(re.findall(r'(?<=\n\n)"\d', texte))
                + len(re.findall(r'(?<=\n\n)\d+" ', texte)))
    return {
        'total': total,
        'couverts_par_regles': couverts,
        'residuels': total - couverts,
        'guillemets_fr_ouvrants': texte.count('«'),
        'guillemets_fr_fermants': texte.count('»'),
    }


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
        description=r"""
RÈGLE 13 : CORRECTION DES GUILLEMETS PARASITES OCR

Corrige les guillemets droits (") qui sont des artefacts OCR, non des
guillemets de citation. Sur ce corpus, les guillemets «/» sont déjà corrects.
""",
        epilog=r"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         1. CE QUE FAIT CE SCRIPT                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Ce script NE normalise PAS les guillemets «/» (déjà corrects).             ║
║  Il corrige 3 types d'artefacts OCR où " remplace un autre caractère :      ║
║                                                                               ║
║  1. in-8" → in-8°    (° mal reconnu dans les formats bibliographiques)      ║
║  2. "\n5. → \n5.     (guillemet parasite devant un numéro d'article)        ║
║  3. \n2" → \n2°      (° mal reconnu dans les numéros ordinaux)              ║
║                                                                               ║
║  41 guillemets parasites résiduels (trop hétérogènes) ne sont pas couverts. ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                               2. EXEMPLES                                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  "in-8", 670 pp."      →  "in-8°, 670 pp."                                  ║
║  "\n\"5. — ITALIE."    →  "\n5. — ITALIE."                                  ║
║  "\n2\" S'ils ont"     →  "\n2° S'ils ont"                                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                            3. ANALYSE DU CORPUS                               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Guillemets « :  187  (déjà corrects — citations françaises)                ║
║  Guillemets » :  391  (déjà corrects — style citation longue XIXe)          ║
║  Guillemets " :   77  DONT :                                                 ║
║    in-N" (format livre)           :  9  → corrigés en in-N°                ║
║    "chiffre en début de §         : 18  → guillemet supprimé                ║
║    N" en début de §               :  9  → corrigés en N°                   ║
║    Artefacts divers non couverts  : 41  → correction manuelle               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                          4. PIÈGES PYTHON À ÉVITER                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  1. LAMBDA DANS re.subn() :                                                  ║
║     Permet de reconstruire le remplacement depuis les groupes capturés.     ║
║     Utile quand le remplacement dépend du contenu du match (ici : casse).   ║
║                                                                               ║
║  2. LOOKBEHIND (?<=\n\n) :                                                   ║
║     Longueur fixe (2 chars) → autorisé en Python.                           ║
║     Vérifie le contexte sans le consommer dans le match.                    ║
║                                                                               ║
║  3. re.subn() :                                                              ║
║     Retourne (texte, nb_substitutions) en une seule passe.                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # -------------------------------------------------------------------------
    # BLOC 2 : DÉFINITION DES ARGUMENTS
    # -------------------------------------------------------------------------
    parser.add_argument('input', help="Fichier d'entrée (texte brut) - OBLIGATOIRE")
    parser.add_argument('-o', '--output',
                        help="Fichier de sortie - Défaut: INPUT_guillemets.txt")
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
        suffix = "_guillemets"
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
    stats = compter_guillemets_droits(texte)
    print(f"   Guillemets \" total     : {stats['total']}")
    print(f"      Couverts par règles : {stats['couverts_par_regles']}")
    print(f"      Résiduels           : {stats['residuels']} (correction manuelle)")
    print(f"   Guillemets «           : {stats['guillemets_fr_ouvrants']} (déjà corrects)")
    print(f"   Guillemets »           : {stats['guillemets_fr_fermants']} (déjà corrects)")

    # -------------------------------------------------------------------------
    # BLOC 7 : APPLICATION DES CORRECTIONS
    # -------------------------------------------------------------------------
    print("🔄 Correction des guillemets parasites OCR...")
    texte_corrige, total, details = corriger_guillemets(texte)

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
            print(f"      L{d['ligne']:5d} | {d['label']:30s} | "
                  f"{repr(d['avant']):15s} → {repr(d['apres'])}")
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
