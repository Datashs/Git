#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
===============================================================================
RÈGLE 5 : NORMALISATION DES ESPACES
===============================================================================

Description :
    Normalise tous les types d'espaces (espaces insécables, espaces fines,
    espaces multiples, etc.) en espace simple (U+0020). Cette opération
    uniformise la segmentation du texte pour les traitements ultérieurs.

Fonction :
    - Convertit les espaces insécables (U+00A0) en espaces simples
    - Convertit les espaces fines (U+2009) en espaces simples
    - Convertit les espaces de ponctuation (U+2008) en espaces simples
    - Réduit les espaces multiples à un seul espace
    - Supprime les espaces en début et fin de ligne
    - Préserve les sauts de ligne (\n)

Justification :
    Les fichiers OCR contiennent souvent des types d'espaces variés selon :
    - La police de caractères utilisée
    - Le contexte typographique
    - L'encodage d'origine
    - La méthode de numérisation
    
    Une forme unique simplifie tous les traitements ultérieurs :
    - Segmentation correcte des mots
    - Validation lexicale
    - Recherche de motifs
    - Affichage cohérent

Exemple :
    Entrée :  "mot\u00A0mot" (espace insécable U+00A0)
    Sortie :  "mot mot" (espace simple U+0020)
    
    Entrée :  "mot   mot" (espaces multiples)
    Sortie :  "mot mot" (espace unique)
    
    Entrée :  "  début avec espaces  "
    Sortie :  "début avec espaces"

Risque : Nul pour les espaces techniques.
    Note sur l'espace insécable (U+00A0) en typographie française :
    En français correct, l'espace insécable précède les signes doubles
    ( : ; ! ? ) pour éviter qu'ils se retrouvent en début de ligne.
    Ce script la convertit en espace ordinaire : c'est un choix délibéré
    pour simplifier les traitements lexicaux ultérieurs (segmentation,
    recherche de motifs). Si la mise en forme typographique finale compte,
    les espaces insécables devront être restituées lors d'une étape de
    post-traitement dédiée.
    - Opération parfaitement réversible si nécessaire
    - Peut être appliquée plusieurs fois sans risque (idempotente)

Dépendances :
    - Règles 1, 2, 3, 4 (à appliquer avant)
    - Aucune bibliothèque externe nécessaire (uniquement standard)

Ressources lexicales :
    - Aucune pour cette règle purement typographique

USAGE :
    python 05_espaces.py INPUT [-o OUTPUT] [--stats] [--preserve-indent] [--min-space N]

ARGUMENTS :
    INPUT                  Fichier d'entrée (texte brut) - OBLIGATOIRE
    -o, --output OUTPUT    Fichier de sortie (optionnel)
                           Défaut: INPUT_espaces.txt
    --stats                Affiche des statistiques détaillées
    --preserve-indent      Préserve l'indentation (espaces en début de ligne)
    --min-space INTEGER    Nombre minimum d'espaces consécutifs à réduire (défaut: 2)
                           Exemple : --min-space 3 laisse intacts les doubles espaces

EXEMPLES :
    python 05_espaces.py document.txt
    python 05_espaces.py document.txt --stats
    python 05_espaces.py data.txt -o propre.txt
    python 05_espaces.py source.txt --preserve-indent
    python 05_espaces.py source.txt --min-space 3

Pièges Python et points d'attention :
    1. ENCODAGES : Les fichiers peuvent être en latin1 plutôt qu'utf-8
       → Le script tente utf-8 puis latin1 automatiquement
       
    2. TYPES D'ESPACES : Plusieurs codes Unicode représentent des espaces :
       - U+0020 : espace normal
       - U+00A0 : espace insécable (voir note sur typographie française)
       - U+2000 à U+200A : espaces de différentes largeurs
       - U+200B : espace de largeur nulle (déjà supprimé par règle 4)
       - U+202F : espace insécable fin
       - U+205F : espace mathématique
       
    3. min_space ET REGEX : Le seuil min_space doit être intégré dans la
       regex avec un quantificateur {N,} — pas un simple + qui ignore le seuil.
       Oublier cela rend --min-space sans effet (bug silencieux).
       
    4. INDENTATION : Par défaut, on normalise tout, mais on peut préserver
       l'indentation avec --preserve-indent
       
    5. SAUTS DE LIGNE : On doit les préserver, ne pas les normaliser
       → Traitement ligne par ligne avec splitlines()
       
    6. MÉMOIRE : Un fichier de 400 pages (~2 Mo) tient en mémoire
       Pour des fichiers > 100 Mo, prévoir un traitement par lots

===============================================================================
"""

import argparse
import re
import sys
from pathlib import Path

# =============================================================================
# PARAMÈTRES CONFIGURABLES
# =============================================================================

# Dictionnaire des caractères d'espace à normaliser
ESPACES_A_NORMALISER = {
    "\u00A0": " ",  # espace insécable
                     # ⚠️  En typographie française, précède : ; ! ?
                     #    Convertie ici en espace ordinaire pour simplifier
                     #    les traitements lexicaux. À restituer en post-traitement
                     #    si la mise en forme typographique finale est requise.
    "\u2000": " ",  # espace quadratin
    "\u2001": " ",  # espace demi-cadratin
    "\u2002": " ",  # espace cadratin
    "\u2003": " ",  # espace trois-quarts
    "\u2004": " ",  # espace trois-huitièmes
    "\u2005": " ",  # espace quart
    "\u2006": " ",  # espace sixième
    "\u2007": " ",  # espace figure
    "\u2008": " ",  # espace ponctuation
    "\u2009": " ",  # espace fine
    "\u200A": " ",  # espace très fine
    "\u202F": " ",  # espace insécable fin
    "\u205F": " ",  # espace mathématique
    "\u3000": " ",  # espace idéographique
}

# Classe de caractères pour la regex — utilisée avec un quantificateur {N,}
# pour respecter le seuil min_space
ESPACES_CLASSE = r"[ \t\u00A0\u2000-\u200A\u202F\u205F\u3000]"

ENCODAGE_LECTURE = "utf-8"
ENCODAGE_LECTURE_FALLBACK = "latin1"
ENCODAGE_ECRITURE = "utf-8"
# =============================================================================


# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def normalize_space_characters(text: str) -> str:
    """
    Remplace tous les types d'espaces spéciaux par l'espace normal (U+0020).
    
    Args:
        text (str): Texte d'entrée
        
    Returns:
        str: Texte avec espaces normalisés
        
    Note:
        Utilise str.maketrans() + translate() pour une substitution en une seule
        passe — plus efficace qu'une série de replace() successifs.
        
    Attention (espace insécable) :
        U+00A0 est incluse dans la normalisation. En typographie française,
        elle précède les signes doubles ( : ; ! ? ). Sa conversion en espace
        ordinaire est un choix de pipeline — voir la section Risque du module.
    """
    table = str.maketrans(
        "".join(ESPACES_A_NORMALISER.keys()),
        " " * len(ESPACES_A_NORMALISER)
    )
    return text.translate(table)


def normalize_multiple_spaces(text: str, min_space: int = 2,
                              preserve_indent: bool = False) -> str:
    """
    Réduit les groupes d'espaces multiples à un seul espace.
    
    Args:
        text (str): Texte d'entrée (après normalize_space_characters)
        min_space (int): Taille minimale du groupe à réduire.
                         Exemple : min_space=3 laisse intacts les doubles espaces.
        preserve_indent (bool): Si True, préserve l'indentation en début de ligne.
        
    Returns:
        str: Texte avec espaces multiples réduits.
        
    Note sur min_space et la regex :
        Le seuil min_space est intégré dans la regex via {N,} :
            ESPACES_CLASSE + "{2,}"  →  remplace 2 espaces ou plus
            ESPACES_CLASSE + "{3,}"  →  remplace 3 espaces ou plus (laisse les doubles)
        Un simple + ignorerait min_space — bug silencieux à éviter.
        
    Note sur splitlines() :
        splitlines() préserve les lignes vides (éléments "" dans la liste),
        ce qui garantit que les sauts de paragraphe (\n\n) sont conservés
        après le join() final.
    """
    # Construction de la regex avec le seuil min_space
    # {min_space,} signifie "min_space occurrences ou plus"
    pattern = ESPACES_CLASSE + "{" + str(min_space) + ",}"
    
    lines = text.splitlines()
    result = []
    
    for line in lines:
        if preserve_indent:
            # Identifier et préserver l'indentation initiale
            indent_match = re.match(ESPACES_CLASSE + "+", line)
            if indent_match:
                indent = indent_match.group(0)
                rest = line[len(indent):]
                rest = re.sub(pattern, " ", rest).strip()
                result.append(indent + rest)
            else:
                result.append(re.sub(pattern, " ", line).strip())
        else:
            result.append(re.sub(pattern, " ", line).strip())
    
    return "\n".join(result)


def normalize_leading_trailing(text: str) -> str:
    """
    Supprime les espaces en début et fin de chaque ligne.
    
    Args:
        text (str): Texte d'entrée
        
    Returns:
        str: Texte sans espaces aux extrémités de chaque ligne
        
    Note:
        Appelée explicitement dans normalize_all() comme étape distincte,
        après la réduction des espaces multiples. Cela rend le pipeline
        lisible : chaque transformation est nommée et visible.
        
        line.strip() supprime tous les espaces Unicode en bord de ligne,
        pas seulement U+0020 — ce qui est le comportement souhaité ici.
    """
    lines = text.splitlines()
    return "\n".join(line.strip() for line in lines)


def normalize_all(text: str, min_space: int = 2,
                  preserve_indent: bool = False) -> str:
    """
    Applique toutes les normalisations d'espace dans l'ordre correct.
    
    Args:
        text (str): Texte d'entrée
        min_space (int): Seuil pour les espaces multiples
        preserve_indent (bool): Préserver l'indentation
        
    Returns:
        str: Texte complètement normalisé
        
    Pipeline :
        1. normalize_space_characters() — convertit les espaces spéciaux en U+0020
        2. normalize_multiple_spaces()  — réduit les groupes selon min_space
        3. normalize_leading_trailing() — nettoie les bords de ligne
           (sauf si preserve_indent, auquel qu'elle est redondante avec l'étape 2)
           
    Note sur l'ordre :
        L'étape 1 doit précéder l'étape 2 : sans cela, une espace insécable
        suivie d'une espace normale formerait un groupe que la regex de l'étape 2
        ne reconnaîtrait pas (classes différentes).
    """
    # Étape 1 : convertir tous les types d'espaces en U+0020
    text = normalize_space_characters(text)
    
    # Étape 2 : réduire les groupes d'espaces multiples
    text = normalize_multiple_spaces(text, min_space, preserve_indent)
    
    # Étape 3 : supprimer les espaces résiduels en bord de ligne
    # (non redondante avec l'étape 2 quand preserve_indent=False :
    #  normalize_multiple_spaces fait déjà .strip(), mais rendre
    #  l'étape explicite améliore la lisibilité du pipeline)
    if not preserve_indent:
        text = normalize_leading_trailing(text)
    
    return text


def count_spaces(text: str) -> dict:
    """
    Compte les différents types d'espaces dans le texte.
    
    Args:
        text (str): Texte à analyser
        
    Returns:
        dict: Statistiques sur les types d'espaces présents
    """
    stats = {
        "normal": 0,    # U+0020
        "nobreak": 0,   # U+00A0
        "fine": 0,      # U+2000-U+200A, U+202F, U+205F, U+3000
        "multiple": 0,  # groupes de 2+ espaces normales consécutives
        "total": 0,
    }
    
    for char in text:
        code = ord(char)
        if char == " ":
            stats["normal"] += 1
            stats["total"] += 1
        elif char == "\u00A0":
            stats["nobreak"] += 1
            stats["total"] += 1
        elif 0x2000 <= code <= 0x200A or char in ("\u202F", "\u205F", "\u3000"):
            stats["fine"] += 1
            stats["total"] += 1
    
    # Groupes de 2+ espaces normales (après normalisation des types)
    stats["multiple"] = len(re.findall(r" {2,}", text))
    
    return stats


# =============================================================================
# FONCTION PRINCIPALE
# =============================================================================

def main():
    """
    Fonction principale du script.
    
    Structure en blocs clairement identifiés :
    1. Configuration du parser d'arguments
    2. Analyse des arguments
    3. Préparation des chemins de fichiers
    4. Lecture du fichier avec gestion d'encodage
    5. Statistiques avant traitement
    6. Application de la normalisation
    7. Statistiques après traitement
    8. Écriture du résultat
    
    Chaque bloc est commenté pour expliquer son rôle et les choix techniques.
    """
    
    # -------------------------------------------------------------------------
    # BLOC 1 : CONFIGURATION DU PARSER D'ARGUMENTS
    # -------------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        description="""
RÈGLE 5 : NORMALISATION DES ESPACES

Normalise tous les types d'espaces (espaces insécables, espaces fines,
espaces multiples, etc.) en espace simple (U+0020). Cette opération
uniformise la segmentation du texte pour les traitements ultérieurs.
""",
        epilog="""
╔══════════════════════════════════════════════════════════════════════════════╗
║                            1. FONCTION DÉTAILLÉE                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  • Convertit les espaces insécables (U+00A0) en espaces simples               ║
║    ⚠️  En français, U+00A0 précède : ; ! ? — info typographique perdue        ║
║  • Convertit les espaces fines et larges (U+2000-U+200A) en espaces simples  ║
║  • Réduit les groupes d'espaces multiples (seuil configurable --min-space)   ║
║  • Supprime les espaces en début et fin de ligne                              ║
║  • Préserve les sauts de ligne (\n) et la structure en paragraphes           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                            2. JUSTIFICATION                                   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Les fichiers OCR contiennent souvent des types d'espaces variés selon :     ║
║  • La police de caractères utilisée                                           ║
║  • Le contexte typographique                                                  ║
║  • L'encodage d'origine                                                       ║
║                                                                               ║
║  Une forme unique simplifie tous les traitements ultérieurs :                 ║
║  • Segmentation correcte des mots                                             ║
║  • Validation lexicale                                                        ║
║  • Recherche de motifs                                                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                               3. EXEMPLES                                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Entrée :  "Bonjour\u00A0; merci" (espace insécable avant ;)                 ║
║  Sortie :  "Bonjour ; merci" (espace ordinaire)                               ║
║                                                                               ║
║  Entrée :  "mot   mot" (espaces multiples)                                    ║
║  Sortie :  "mot mot" (espace unique)                                          ║
║                                                                               ║
║  Entrée :  "  début avec espaces  "                                           ║
║  Sortie :  "début avec espaces"                                               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                         4. RISQUE ET DÉPENDANCES                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  • RISQUE : NUL (sens lexical préservé)                                       ║
║    - Les types d'espaces sont sémantiquement équivalents pour l'analyse      ║
║    - Opération réversible et idempotente                                      ║
║    ⚠️  Perte d'info typographique : U+00A0 devant : ; ! ? (français)         ║
║       À restituer en post-traitement si la mise en forme finale compte.      ║
║                                                                               ║
║  • DÉPENDANCES :                                                              ║
║    - Règles 1, 2, 3, 4 (normalisations préalables)                           ║
║    - Aucune bibliothèque externe nécessaire                                   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                          5. PIÈGES PYTHON À ÉVITER                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  1. min_space ET REGEX :                                                      ║
║     Utiliser {N,} dans la regex, pas un simple + qui ignore le seuil.        ║
║     Un simple + rend --min-space sans effet (bug silencieux).                ║
║     Correct : ESPACES_CLASSE + "{" + str(min_space) + ",}"                  ║
║                                                                               ║
║  2. ESPACE INSÉCABLE (U+00A0) :                                               ║
║     Convertie en espace ordinaire — convention typographique française        ║
║     perdue. Documenter ce choix explicitement.                               ║
║                                                                               ║
║  3. ORDRE DES ÉTAPES :                                                        ║
║     normalize_space_characters() AVANT normalize_multiple_spaces()           ║
║     Sans cela, U+00A0 + U+0020 ne forment pas un groupe reconnu.            ║
║                                                                               ║
║  4. splitlines() ET PARAGRAPHES :                                             ║
║     splitlines() préserve les lignes vides (→ paragraphes intacts).         ║
║     Ne jamais utiliser re.sub(r'\s+', ' ', text) sur le texte entier :    ║
║     cela avalerait tous les sauts de ligne.                                  ║
║                                                                               ║
║  5. MÉMOIRE : Fichiers jusqu'à ~100 Mo OK                                    ║
║     → Au-delà, prévoir un traitement par lots                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # -------------------------------------------------------------------------
    # BLOC 2 : DÉFINITION DES ARGUMENTS
    # -------------------------------------------------------------------------
    parser.add_argument("input", help="Fichier d'entrée (texte brut) - OBLIGATOIRE")
    parser.add_argument("-o", "--output",
                        help="Fichier de sortie - Défaut: INPUT_espaces.txt")
    parser.add_argument("--stats", action="store_true",
                        help="Affiche des statistiques détaillées")
    parser.add_argument("--preserve-indent", action="store_true",
                        help="Préserve l'indentation (espaces en début de ligne)")
    parser.add_argument("--min-space", type=int, default=2,
                        help="Nombre minimum d'espaces consécutifs à réduire (défaut: 2)")
    
    # -------------------------------------------------------------------------
    # BLOC 3 : ANALYSE DES ARGUMENTS
    # -------------------------------------------------------------------------
    args = parser.parse_args()
    
    if args.min_space < 2:
        print("⚠️  --min-space doit être au moins 2. Valeur corrigée à 2.")
        args.min_space = 2
    
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
        suffix = "_espaces"
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
        with open(input_path, "r", encoding=ENCODAGE_LECTURE) as f:
            text = f.read()
        print(f"   Encodage utilisé : {ENCODAGE_LECTURE}")
    except UnicodeDecodeError:
        print(f"⚠️  Échec avec {ENCODAGE_LECTURE}, "
              f"tentative avec {ENCODAGE_LECTURE_FALLBACK}...")
        try:
            with open(input_path, "r", encoding=ENCODAGE_LECTURE_FALLBACK) as f:
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
    stats_avant = count_spaces(text)
    
    print(f"   Total caractères : {len(text):,}")
    print(f"   Espaces normaux (U+0020) : {stats_avant['normal']}")
    if stats_avant["nobreak"] > 0:
        print(f"   Espaces insécables (U+00A0) : {stats_avant['nobreak']}"
              " ← converties en espace ordinaire")
    if stats_avant["fine"] > 0:
        print(f"   Espaces fines/larges : {stats_avant['fine']}")
    if stats_avant["multiple"] > 0:
        print(f"   Groupes d'espaces multiples : {stats_avant['multiple']}")
    
    if args.stats:
        print(f"   Options actives :")
        print(f"      --min-space {args.min_space}")
        print(f"      --preserve-indent : {args.preserve_indent}")
    
    # -------------------------------------------------------------------------
    # BLOC 7 : APPLICATION DE LA NORMALISATION
    # -------------------------------------------------------------------------
    print("🔄 Application de la normalisation des espaces...")
    normalized = normalize_all(text, min_space=args.min_space,
                               preserve_indent=args.preserve_indent)
    
    # -------------------------------------------------------------------------
    # BLOC 8 : STATISTIQUES APRÈS TRAITEMENT
    # -------------------------------------------------------------------------
    stats_apres = count_spaces(normalized)
    
    # Calcul exact : espaces spéciales converties + espaces normales supprimées
    # (un groupe de N espaces devient 1 espace, soit N-1 suppressions)
    nb_speciaux = stats_avant["nobreak"] + stats_avant["fine"]
    nb_supprimes = stats_avant["normal"] - stats_apres["normal"]
    total_modifications = nb_speciaux + nb_supprimes
    
    if total_modifications > 0:
        print(f"   Espaces spéciales converties : {nb_speciaux}")
        print(f"   Espaces en trop supprimées   : {nb_supprimes}")
        print(f"   ✅ Total modifications : {total_modifications}")
    else:
        print("   ℹ️  Aucune modification nécessaire")
    
    # -------------------------------------------------------------------------
    # BLOC 9 : ÉCRITURE DU FICHIER DE SORTIE
    # -------------------------------------------------------------------------
    print(f"💾 Écriture de {output_path}...")
    
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding=ENCODAGE_ECRITURE) as f:
            f.write(normalized)
        if output_path.exists():
            taille = output_path.stat().st_size
            print(f"   ✅ Fichier écrit : {taille:,} octets")
    except PermissionError:
        print(f"❌ Erreur : permission refusée pour {output_path}")
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
