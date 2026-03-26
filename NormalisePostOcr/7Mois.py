#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
===============================================================================
RÈGLE 7 : MISE EN MINUSCULE DES MOIS
===============================================================================

Description :
    Convertit les noms de mois en majuscule initiale en minuscule, selon
    les conventions typographiques françaises. Cette erreur est fréquente
    dans les fichiers OCR car les moteurs sont souvent configurés pour
    l'anglais, où les mois prennent une majuscule.

Pourquoi les mois sont-ils en majuscule dans les fichiers OCR ?
    Les moteurs OCR (Tesseract, ABBYY, etc.) sont entraînés majoritairement
    sur des corpus anglais. En anglais, les mois s'écrivent avec une
    majuscule ("January", "February"...). Par contamination, les mois
    français ressortent souvent en majuscule dans les fichiers OCR,
    même quand l'original imprimé les avait en minuscule.
    
    Note : en français, les mois s'écrivent TOUJOURS en minuscule,
    y compris en début de phrase. "Janvier est un mois froid." est
    incorrect — la forme correcte est "janvier est un mois froid."
    Ce script applique cette règle systématiquement.

Fonctions :
    - Convertit "Janvier" → "janvier", "Février" → "février", etc.
    - Ne touche pas aux formes déjà en minuscule
    - Ne touche pas aux formes tout en majuscules (JANVIER, AOÛT...)
      car celles-ci sont vraisemblablement des titres intentionnels
    - Préserve les mois anglais (January, February...) — liste fermée française

Exemples :
    Entrée :  "19 Août 1875"          Sortie :  "19 août 1875"
    Entrée :  "lr Janvier 1874"       Sortie :  "lr janvier 1874"
    Entrée :  "Décembre 1876"         Sortie :  "décembre 1876"
    Entrée :  "SESSION DE AOÛT 1875"  Sortie :  "SESSION DE AOÛT 1875"  ← intact

Risque : Très faible
    Ce script modifie uniquement une liste fermée de 12 mots français,
    uniquement sous leur forme "Majuscule initiale + minuscules" (ex: "Janvier").
    
    Faux positifs possibles (rares sur corpus juridique XIXe) :
    - "Mars" peut être un nom propre (nom de famille, divinité)
    - "Mai" peut être un prénom d'origine asiatique
    - "Juin" peut être un nom propre (général Juin, 1888-1967)
    Ces cas sont extrêmement rares dans un corpus de droit international.
    Si votre corpus contient des noms propres homonymes des mois,
    utiliser --stats pour les repérer avant d'appliquer.
    
    Idempotence : appliquer ce script deux fois donne le même résultat.

Dépendances :
    - Règles 1 à 6 (normalisations préalables recommandées)
    - Aucune bibliothèque externe nécessaire (uniquement standard)

Ressources lexicales :
    - Aucune (liste fermée des 12 mois français)

USAGE :
    python 07_mois_minuscules.py INPUT [-o OUTPUT] [--stats]

ARGUMENTS :
    INPUT                  Fichier d'entrée (texte brut) - OBLIGATOIRE
    -o, --output OUTPUT    Fichier de sortie (optionnel)
                           Défaut: INPUT_mois.txt
    --stats                Affiche le détail par mois avant correction
                           Recommandé au premier passage pour vérifier
                           l'absence de faux positifs

EXEMPLES :
    python 07_mois_minuscules.py document.txt
    python 07_mois_minuscules.py document.txt --stats
    python 07_mois_minuscules.py data.txt -o propre.txt

Pièges Python et points d'attention :
    1. LISTE FERMÉE vs REGEX GÉNÉRIQUE :
       On travaille avec une liste explicite des 12 mois plutôt qu'une
       regex générique comme r'[A-Z][a-z]+'. Avantages :
       - Pas de faux positifs sur d'autres mots commençant par une majuscule
       - Contrôle total sur les formes accentuées (Août, Décembre, Février)
       - Facile à lire et à maintenir
    
    2. FORMES ACCENTUÉES :
       Plusieurs mois ont des accents dans leur forme française :
       - "Août"     (â : accent circonflexe)
       - "Décembre" (é : accent aigu)
       - "Février"  (é : accent aigu)
       La liste MOIS_MAJUSCULE doit inclure ces formes avec accents.
       capitalize() gère correctement les accents en Python 3 :
       "août".capitalize() → "Août" ✅
    
    3. COMPILATION DES PATTERNS AU NIVEAU MODULE :
       Les patterns regex sont compilés UNE SEULE FOIS au chargement
       du module (lignes après les constantes), pas à chaque appel de
       normalize_months(). Cela améliore les performances et évite
       de recompiler les mêmes expressions à chaque ligne traitée.
       
       Comparer (mauvais) :
           def normalize_months(text):
               pattern = re.compile(r'...')  # recompilé à chaque appel !
               ...
       
       Avec (bon) :
           PATTERN_MOIS = re.compile(r'...')  # compilé une fois au démarrage
           def normalize_months(text):
               PATTERN_MOIS.sub(...)           # réutilisé
    
    4. re.sub AVEC FONCTION DE REMPLACEMENT :
       re.sub accepte soit une chaîne, soit une FONCTION comme remplacement.
       Quand on passe une fonction, elle est appelée pour chaque correspondance
       avec l'objet Match en argument. Cela permet de décider dynamiquement
       du remplacement selon le contexte.
       
       Exemple :
           def remplacer(match):
               return match.group().lower()   # met en minuscule
           result = pattern.sub(remplacer, texte)
    
    5. (?<!\\w) et (?!\\w) — ASSERTIONS DE NON-PRÉSENCE :
       Le pattern utilise des lookbehind et lookahead négatifs pour
       s'assurer que le mois est un mot isolé :
       - (?<!\\w) : pas de caractère alphanumérique JUSTE AVANT
       - (?!\\w)  : pas de caractère alphanumérique JUSTE APRÈS
       
       Cela évite de capturer "Janvier" dans "préJanvier" (soudé)
       ou d'affecter "Janvierest" (mot collé, artefact OCR).
       
       Note : \\w inclut les chiffres, donc "19Janvier" ne serait
       pas capturé non plus (le 9 bloque le lookbehind).
       En pratique sur ce corpus, les mois sont toujours séparés
       par une espace ou une ponctuation.

    6. FORMES TOUT-MAJUSCULE NON TOUCHÉES (JANVIER, AOÛT...) :
       PATTERN_MOIS ne matche que les formes "Majuscule initiale +
       minuscules" (ex: "Janvier"). Il ne matche PAS "JANVIER" car
       le pattern contient "Janvier" littéralement, pas une regex
       insensible à la casse.
       
       C'est le comportement souhaité : les formes tout-majuscule
       sont des en-têtes de section ou des titres intentionnels
       (ex: "JANVIER 1874." comme titre de chapitre) — ne pas toucher.
       
       Ce n'est pas un choix explicite dans le code mais un effet
       naturel de la liste fermée. Si on voulait les toucher aussi,
       il faudrait ajouter re.IGNORECASE au pattern et gérer la
       casse du remplacement différemment.

===============================================================================
"""

import argparse
import re
import sys
from pathlib import Path

# =============================================================================
# PARAMÈTRES CONFIGURABLES
# =============================================================================

# Liste des mois français en minuscule (forme cible correcte)
MOIS_FRANCAIS = [
    'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
    'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
]

# Dictionnaire principal : forme avec majuscule initiale → forme cible en minuscule
# capitalize() met la première lettre en majuscule, le reste en minuscule.
# Ex : 'août'.capitalize() → 'Août'  (gère correctement les accents en Python 3)
MOIS_MAJUSCULE = {mois.capitalize(): mois for mois in MOIS_FRANCAIS}

# Variantes OCR : formes avec erreur d'accentuation → forme cible correcte
# Ces formes ne peuvent pas être générées par capitalize() car elles contiennent
# des fautes d'accent introduites par l'OCR.
#
# Exemple attesté dans le corpus :
#   'Aoùt' : le OCR a lu 'û' (u accent circonflexe) comme 'ù' (u accent grave)
#             Ces deux caractères sont visuellement proches en petits corps.
#   'aoùt' : même confusion en minuscule (artefact de numérisation)
#
# On traite la forme minuscule directement car elle peut apparaître dans le texte
# après d'autres normalisations du pipeline.
VARIANTES_OCR_MOIS = {
    'Aoùt': 'août',   # û → ù  (confusion accent circonflexe / grave)
    'aoùt': 'août',   # idem en minuscule
}

ENCODAGE_LECTURE = 'utf-8'
ENCODAGE_LECTURE_FALLBACK = 'latin1'
ENCODAGE_ECRITURE = 'utf-8'

# =============================================================================
# COMPILATION DES PATTERNS — UNE SEULE FOIS AU CHARGEMENT DU MODULE
# =============================================================================
# On construit un pattern qui matche l'un quelconque des mois avec majuscule.
# La construction est :
#   "Janvier|Février|Mars|...|Décembre"
# entouré de assertions de non-présence pour isoler le mot.
#
# re.escape() protège les caractères spéciaux éventuels (inutile ici car
# les noms de mois n'en contiennent pas, mais c'est une bonne pratique).
#
# re.UNICODE garantit que \w reconnaît les caractères accentués.

_mois_alternance = '|'.join(re.escape(m) for m in MOIS_MAJUSCULE)

PATTERN_MOIS = re.compile(
    r'(?<!\w)(' + _mois_alternance + r')(?!\w)',
    re.UNICODE
)
# =============================================================================


# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def normalize_months(text: str) -> str:
    """
    Convertit tous les mois avec majuscule initiale en minuscule.
    
    Args:
        text (str): Texte d'entrée
        
    Returns:
        str: Texte avec mois normalisés
        
    Note sur re.sub avec fonction :
        On passe une fonction lambda à re.sub plutôt qu'une chaîne fixe.
        Cette fonction reçoit l'objet Match pour chaque occurrence trouvée
        et retourne la forme en minuscule via le dictionnaire MOIS_MAJUSCULE.
        
        Exemple de ce qui se passe pour "19 Août 1875" :
        1. PATTERN_MOIS trouve "Août" à la position 3
        2. La lambda reçoit le match, extrait "Août" avec match.group(1)
        3. MOIS_MAJUSCULE["Août"] retourne "août"
        4. re.sub remplace "Août" par "août" dans le texte
        
        On aurait pu écrire plus simplement :
            return PATTERN_MOIS.sub(lambda m: m.group(1).lower(), text)
        Mais passer par le dictionnaire est plus sûr : lower() pourrait
        produire des formes incorrectes sur des caractères exotiques,
        alors que le dictionnaire contient exactement la cible voulue.
    """
    # Étape 1 : corriger les variantes OCR (accents fautifs)
    # Ces formes ne sont pas couvertes par PATTERN_MOIS car elles ne
    # correspondent à aucun mois avec majuscule initiale correcte.
    # On les traite en amont avec de simples remplacements directs.
    for variante, cible in VARIANTES_OCR_MOIS.items():
        text = text.replace(variante, cible)

    # Étape 2 : convertir les mois avec majuscule initiale correcte (Janvier → janvier)
    return PATTERN_MOIS.sub(
        lambda match: MOIS_MAJUSCULE[match.group(1)],
        text
    )


def count_months(text: str) -> dict:
    """
    Compte les occurrences des mois en majuscule et en minuscule.
    
    Args:
        text (str): Texte à analyser
        
    Returns:
        dict: {
            'total': int,
            'majuscule': int,        # formes à corriger
            'minuscule': int,        # formes déjà correctes
            'par_mois': {            # détail par mois
                'janvier': {'maj': int, 'min': int},
                ...
            }
        }
        
    Note sur la conception :
        On réutilise PATTERN_MOIS (déjà compilé) pour les majuscules,
        et on construit un pattern similaire pour les minuscules.
        Les deux patterns partagent la même structure (?<!\\w)...(?!\\w)
        pour garantir la cohérence du comptage.
    """
    # Pattern pour les minuscules (construit de la même façon que PATTERN_MOIS)
    pattern_min = re.compile(
        r'(?<!\w)(' + '|'.join(re.escape(m) for m in MOIS_FRANCAIS) + r')(?!\w)',
        re.UNICODE
    )

    stats = {
        'total': 0,
        'majuscule': 0,
        'minuscule': 0,
        'par_mois': {mois: {'maj': 0, 'min': 0} for mois in MOIS_FRANCAIS},
    }

    # Comptage des majuscules
    for match in PATTERN_MOIS.finditer(text):
        mois_min = MOIS_MAJUSCULE[match.group(1)]
        stats['majuscule'] += 1
        stats['par_mois'][mois_min]['maj'] += 1
        stats['total'] += 1

    # Comptage des minuscules
    for match in pattern_min.finditer(text):
        mois = match.group(1)
        stats['minuscule'] += 1
        stats['par_mois'][mois]['min'] += 1
        stats['total'] += 1

    return stats


# =============================================================================
# FONCTION PRINCIPALE
# =============================================================================

def main():
    """
    Fonction principale du script.
    
    Structure en blocs clairement identifiés :
    1.  Configuration du parser d'arguments
    2.  Analyse des arguments
    3.  Préparation des chemins de fichiers
    4.  Lecture du fichier avec gestion d'encodage
    5.  Statistiques avant traitement
    6.  Application de la normalisation
    7.  Statistiques après traitement
    8.  Écriture du résultat
    9.  Vérification du fichier créé
    10. Fin du traitement
    """

    # -------------------------------------------------------------------------
    # BLOC 1 : CONFIGURATION DU PARSER D'ARGUMENTS
    # -------------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        description="""
RÈGLE 7 : MISE EN MINUSCULE DES MOIS

Convertit les noms de mois en majuscule initiale (ex: "Janvier") en
minuscule ("janvier"), conformément aux conventions typographiques
françaises. Erreur fréquente dans les fichiers OCR configurés pour l'anglais.
""",
        epilog=r"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                            1. FONCTION DÉTAILLÉE                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Convertit les 12 mois français sous forme "Majuscule initiale" :            ║
║  Janvier→janvier  Février→février   Mars→mars      Avril→avril              ║
║  Mai→mai          Juin→juin         Juillet→juillet Août→août               ║
║  Septembre→sept.  Octobre→octobre   Novembre→nov.   Décembre→déc.           ║
║                                                                               ║
║  Ne touche PAS aux formes :                                                  ║
║  • Tout en majuscules (JANVIER, AOÛT) — titres intentionnels                ║
║  • Déjà en minuscule (janvier, août) — déjà corrects                        ║
║  • Mois anglais (January, February...) — liste fermée française             ║
║                                                                               ║
║  Corrige aussi les variantes OCR d'accentuation :                           ║
║  • "Aoùt" / "aoùt" → "août"  (ù confondu avec û par l'OCR)                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                            2. JUSTIFICATION                                   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  En français, les mois s'écrivent TOUJOURS en minuscule, même en début      ║
║  de phrase. Les OCR (Tesseract, ABBYY...) sont entraînés sur l'anglais      ║
║  où les mois prennent une majuscule — d'où l'erreur systématique.           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                               3. RISQUE                                       ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  • RISQUE : Très faible                                                       ║
║  • Faux positifs possibles (rares sur corpus juridique XIXe) :               ║
║    - "Mars" = nom propre (nom de famille, divinité romaine)                 ║
║    - "Mai" = prénom d'origine asiatique                                      ║
║    - "Juin" = nom propre (général Juin, 1888-1967)                          ║
║    → Utiliser --stats pour les repérer avant d'appliquer sur un             ║
║      nouveau corpus                                                          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                               4. EXEMPLES                                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  "19 Août 1875"         →  "19 août 1875"                                    ║
║  "lr Janvier 1874"      →  "lr janvier 1874"                                 ║
║  "Décembre 1876"        →  "décembre 1876"                                   ║
║  "SESSION DE AOÛT"      →  "SESSION DE AOÛT"  (tout-majuscule intact)       ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                          5. PIÈGES PYTHON À ÉVITER                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  1. COMPILER LES PATTERNS UNE SEULE FOIS :                                   ║
║     re.compile() doit être appelé au niveau module, pas dans la fonction.   ║
║     Sinon les patterns sont recompilés à chaque appel (perte de perf.).     ║
║                                                                               ║
║  2. FORMES ACCENTUÉES :                                                       ║
║     capitalize() gère correctement les accents en Python 3.                 ║
║     'août'.capitalize() → 'Août'  ✅                                         ║
║     Toujours utiliser re.UNICODE pour que \w reconnaisse les accents.       ║
║                                                                               ║
║  3. re.sub AVEC FONCTION :                                                    ║
║     re.sub(pattern, fonction, texte) appelle la fonction pour chaque match. ║
║     La fonction reçoit l'objet Match et retourne la chaîne de remplacement. ║
║     Plus flexible qu'une chaîne fixe quand le remplacement est dynamique.   ║
║                                                                               ║
║  4. (?<!\w) et (?!\w) :                                                      ║
║     Ces assertions isolent le mot sans le consommer.                        ║
║     Évite de capturer "Janvier" dans un mot collé ("préJanvier").           ║
╚══════════════════════════════════════════════════════════════════════════════╝
""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # -------------------------------------------------------------------------
    # BLOC 2 : DÉFINITION DES ARGUMENTS
    # -------------------------------------------------------------------------
    parser.add_argument(
        'input',
        help="Fichier d'entrée (texte brut) - OBLIGATOIRE"
    )
    parser.add_argument(
        '-o', '--output',
        help="Fichier de sortie - Défaut: INPUT_mois.txt"
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help="Affiche le détail par mois (recommandé au premier passage)"
    )

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
        suffix = "_mois"
        try:
            output_path = input_path.with_stem(input_path.stem + suffix)
        except AttributeError:
            # Fallback Python < 3.9
            output_path = input_path.with_name(
                input_path.stem + suffix + input_path.suffix)

    # -------------------------------------------------------------------------
    # BLOC 5 : LECTURE DU FICHIER D'ENTRÉE
    # -------------------------------------------------------------------------
    print(f"📖 Lecture de {input_path}...")

    try:
        with open(input_path, 'r', encoding=ENCODAGE_LECTURE) as f:
            text = f.read()
        print(f"   Encodage utilisé : {ENCODAGE_LECTURE}")

    except UnicodeDecodeError:
        print(f"⚠️  Échec avec {ENCODAGE_LECTURE}, "
              f"tentative avec {ENCODAGE_LECTURE_FALLBACK}...")
        try:
            with open(input_path, 'r', encoding=ENCODAGE_LECTURE_FALLBACK) as f:
                text = f.read()
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
    stats_avant = count_months(text)

    print(f"   Total caractères : {len(text):,}")
    print(f"   Mois détectés    : {stats_avant['total']}")
    print(f"      En majuscule  : {stats_avant['majuscule']}  ← à corriger")
    print(f"      En minuscule  : {stats_avant['minuscule']}  ← déjà corrects")

    if args.stats and stats_avant['majuscule'] > 0:
        print("   Détail des mois en majuscule :")
        for mois, counts in stats_avant['par_mois'].items():
            if counts['maj'] > 0:
                print(f"      {mois:12s} : {counts['maj']:3d} occurrence(s)")

    # -------------------------------------------------------------------------
    # BLOC 7 : APPLICATION DE LA NORMALISATION
    # -------------------------------------------------------------------------
    print("🔄 Application de la normalisation des mois...")
    normalized = normalize_months(text)

    # -------------------------------------------------------------------------
    # BLOC 8 : STATISTIQUES APRÈS TRAITEMENT
    # -------------------------------------------------------------------------
    stats_apres = count_months(normalized)
    modifications = stats_avant['majuscule'] - stats_apres['majuscule']

    if modifications > 0:
        print(f"   ✅ {modifications} mois mis en minuscule")
    else:
        print("   ℹ️  Aucune modification nécessaire")

    # -------------------------------------------------------------------------
    # BLOC 9 : ÉCRITURE DU FICHIER DE SORTIE
    # -------------------------------------------------------------------------
    print(f"💾 Écriture de {output_path}...")

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding=ENCODAGE_ECRITURE) as f:
            f.write(normalized)

        if output_path.exists():
            taille = output_path.stat().st_size
            print(f"   ✅ Fichier écrit : {taille:,} octets")

    except PermissionError:
        print(f"❌ Permission refusée : {output_path}")
        print("   Vérifiez que vous avez les droits d'écriture dans ce dossier.")
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
# POINT D'ENTRÉE DU SCRIPT
# =============================================================================
if __name__ == "__main__":
    sys.exit(main())
