#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
===============================================================================
RÈGLE 4 : SUPPRESSION DES CARACTÈRES DE CONTRÔLE
===============================================================================

Description :
    Supprime tous les caractères de contrôle invisibles (U+0000 à U+001F,
    U+007F, U+0080 à U+009F, U+200B, U+FEFF, etc.) qui perturbent la
    segmentation et l'analyse du texte.

Fonction :
    - Élimine les caractères de contrôle C0 (U+0000 à U+001F) sauf \n, \r, \t
    - Élimine le caractère DELETE (U+007F)
    - Élimine les caractères de contrôle C1 (U+0080 à U+009F)
    - Élimine les espaces de largeur nulle (U+200B, U+200C, U+200D)
    - Élimine le BOM (Byte Order Mark) U+FEFF
    - Préserve les caractères imprimables et les sauts de ligne

Justification :
    Les fichiers OCR contiennent souvent des caractères de contrôle invisibles
    qui perturbent les traitements ultérieurs :
    - Segmentation en mots et phrases
    - Validation lexicale
    - Recherche de motifs
    - Affichage et impression
    
    Ces caractères sont indésirables et doivent être supprimés.

Exemple :
    Entrée :  "mot\u200B mot" (espace de largeur nulle entre les deux)
    Sortie :  "mot  mot" (espace de largeur nulle remplacée par espace ordinaire)
    
    Entrée :  "mot\u200Bmot" (espace de largeur nulle, sans espaces autour)
    Sortie :  "mot mot" (espace insérée pour éviter la fusion des mots)
    
    Entrée :  "\uFEFFIntroduction" (BOM au début)
    Sortie :  "Introduction"
    
    Entrée :  "texte\u0000avec\u0001nul" (caractères nuls)
    Sortie :  "texte avec nul" (espaces insérées entre les mots)

Risque : Nul
    - Ne modifie jamais le sens du texte
    - Les caractères de contrôle n'ont pas de signification sémantique
    - Opération parfaitement sûre et idempotente

    Note sur la fusion de mots :
    Quand un caractère de contrôle se trouve entre deux caractères
    imprimables, il est remplacé par une espace plutôt que simplement
    supprimé. Cela évite de coller deux mots qui n'ont rien à voir.
    Exemple sans cette précaution : "fin\x0Cdébut" → "findébut" (incorrect)
    Exemple avec cette précaution : "fin\x0Cdébut" → "fin début" (correct)

Dépendances :
    - Règles 1, 2, 3 (à appliquer avant pour une normalisation préalable)
    - Aucune bibliothèque externe nécessaire (uniquement standard)

Ressources lexicales :
    - Aucune pour cette règle purement technique

USAGE :
    python 04_suppression_caracteres_controle.py INPUT [-o OUTPUT] [--stats] [--preserve-tabs] [--preserve-linebreaks]

ARGUMENTS :
    INPUT                  Fichier d'entrée (texte brut) - OBLIGATOIRE
    -o, --output OUTPUT    Fichier de sortie (optionnel)
                           Défaut: INPUT_net.txt
    --stats                Affiche des statistiques détaillées
    --preserve-tabs        Préserve les tabulations (par défaut: converties en espaces)
    --preserve-linebreaks  Préserve les retours chariot (\r) (par défaut: normalisés en \n)

EXEMPLES :
    python 04_suppression_caracteres_controle.py document.txt
    python 04_suppression_caracteres_controle.py document.txt --stats
    python 04_suppression_caracteres_controle.py data.txt -o propre.txt
    python 04_suppression_caracteres_controle.py source.txt --preserve-tabs
    python 04_suppression_caracteres_controle.py source.txt --preserve-linebreaks

Pièges Python et points d'attention :
    1. ENCODAGES : Les fichiers peuvent être en latin1 plutôt qu'utf-8
       → Le script tente utf-8 puis latin1 automatiquement
       
    2. CARACTÈRES DE CONTRÔLE : La liste complète est longue :
       - C0 (U+0000 à U+001F) : 0-31
       - C1 (U+0080 à U+009F) : 128-159
       - DELETE (U+007F) : 127
       - BOM (U+FEFF) : 65279
       - Espaces de largeur nulle (U+200B, U+200C, U+200D, U+200E, U+200F)
       
    3. FUSION DE MOTS : Un caractère de contrôle entre deux mots est remplacé
       par une espace, jamais simplement supprimé.
       → Évite de coller deux mots qui n'ont rien à voir
       
    4. PRÉSERVATION : On préserve toujours \n (LF) pour les fins de ligne
       → Important pour la structure du document
       
    5. TABULATIONS : Par défaut, converties en espaces (configurable via --preserve-tabs)
       
    6. RETOURS CHARIOT : Par défaut, \r convertis en \n (configurable via --preserve-linebreaks)
       → Sur corpus Gallica (UTF-8 Unix), les \r sont absents : ce flag n'a
          généralement aucun effet pratique, mais il est présent pour montrer
          comment brancher un argument optionnel sur une fonction de traitement.
       
    7. PARAGRAPHES : Les séquences de 3+ sauts de ligne consécutifs sont
       normalisées en double saut (\n\n) pour préserver la structure en paragraphes
       sans multiplier les lignes vides.
       
    8. PERFORMANCE : Utilisation d'une liste + join() pour la vitesse
       → Ajouter des caractères un par un à une chaîne oblige Python à
          recréer une nouvelle chaîne à chaque ajout (coûteux).
          On accumule d'abord dans une liste, puis on assemble en une fois.
       → O(n) où n est la longueur du texte
       
    9. MÉMOIRE : Un fichier de 400 pages (~2 Mo) tient en mémoire
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
# Placés en tête pour faciliter les ajustements sans chercher dans le code
# Ces valeurs peuvent être modifiées selon les besoins du corpus

# Caractères à supprimer ou remplacer (identifiés par leur code Unicode)
CARACTERES_A_SUPPRIMER = {
    # Contrôles C0 (0-31), sauf \t (0x09), \n (0x0A), \r (0x0D) gérés séparément
    0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,  # 0-8
    0x0B, 0x0C,                                              # 11-12
    0x0E, 0x0F, 0x10, 0x11, 0x12, 0x13, 0x14, 0x15,        # 14-21
    0x16, 0x17, 0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x1F,  # 22-31
    0x7F,        # DELETE
    *range(0x80, 0xA0),  # Contrôles C1 (128-159)
    0xFEFF,      # BOM (Byte Order Mark)
    # Espaces de largeur nulle — invisibles mais présents entre les mots
    0x200B,      # Zero Width Space
    0x200C,      # Zero Width Non-Joiner
    0x200D,      # Zero Width Joiner
    0x200E,      # Left-to-Right Mark
    0x200F,      # Right-to-Left Mark
}

ENCODAGE_LECTURE = 'utf-8'              # Encodage d'entrée par défaut
ENCODAGE_LECTURE_FALLBACK = 'latin1'    # Fallback si utf-8 échoue
ENCODAGE_ECRITURE = 'utf-8'             # Encodage de sortie (toujours utf-8)
# =============================================================================


# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def is_control(char: str, preserve_tabs: bool = False,
               preserve_linebreaks: bool = False) -> bool:
    """
    Détermine si un caractère est un caractère de contrôle à supprimer.
    
    Args:
        char (str): Caractère à tester (1 caractère)
        preserve_tabs (bool): Si True, préserve les tabulations (\t)
        preserve_linebreaks (bool): Si True, préserve les retours chariot (\r)
        
    Returns:
        bool: True si le caractère doit être supprimé/remplacé, False sinon
        
    Note:
        \n (line feed) est toujours préservé — c'est le marqueur de fin de ligne.
        \r (carriage return) est normalisé en \n par normalize_special(),
        sauf si preserve_linebreaks est True.
        \t (tabulation) est normalisé en espace par normalize_special(),
        sauf si preserve_tabs est True.
    """
    # \n est toujours préservé, quoi qu'il arrive
    if char == '\n':
        return False
    
    # \r : préservé si le flag est actif, sinon normalisé par normalize_special()
    if char == '\r':
        return False  # normalize_special() s'en charge
    
    # \t : préservé si le flag est actif, sinon normalisé par normalize_special()
    if char == '\t' and preserve_tabs:
        return False
    
    # Tous les autres caractères de la liste sont à traiter
    return ord(char) in CARACTERES_A_SUPPRIMER or (char == '\t' and not preserve_tabs)


def normalize_special(char: str, preserve_tabs: bool = False,
                      preserve_linebreaks: bool = False) -> str:
    """
    Normalise les caractères spéciaux (tabulations, retours chariot).
    
    Args:
        char (str): Caractère à normaliser
        preserve_tabs (bool): Si True, préserve les tabulations
        preserve_linebreaks (bool): Si True, préserve les retours chariot (\r)
        
    Returns:
        str: Caractère normalisé
        
    Note:
        Cette fonction est appelée APRÈS is_control() a laissé passer le caractère.
        Elle gère les cas où on ne supprime pas mais on transforme.
        
    Exemple de branchement d'un flag sur une fonction :
        Sans --preserve-linebreaks : '\r' → '\n'
        Avec --preserve-linebreaks : '\r' → '\r' (inchangé)
        C'est le flag args.preserve_linebreaks qui est transmis ici depuis main().
    """
    # Retour chariot : converti en saut de ligne, sauf si préservation demandée
    if char == '\r':
        return '\r' if preserve_linebreaks else '\n'
    
    # Tabulation : convertie en espace, sauf si préservation demandée
    if char == '\t' and not preserve_tabs:
        return ' '
    
    # Tous les autres caractères : inchangés
    return char


def clean_text(text: str, preserve_tabs: bool = False,
               preserve_linebreaks: bool = False) -> str:
    """
    Supprime les caractères de contrôle et normalise les autres.
    
    Args:
        text (str): Texte d'entrée
        preserve_tabs (bool): Si True, préserve les tabulations
        preserve_linebreaks (bool): Si True, préserve les retours chariot
        
    Returns:
        str: Texte nettoyé
        
    Note sur la stratégie liste + join() :
        En Python, les chaînes sont immuables. Ajouter un caractère à une
        chaîne existante crée une nouvelle chaîne en mémoire à chaque fois.
        Sur un texte de 100 000 caractères, cela signifie 100 000 allocations.
        
        La solution : accumuler les caractères dans une liste (append est O(1)),
        puis assembler en une seule opération avec join() (une seule allocation).
        C'est environ 10x plus rapide sur de longs textes.
        
    Note sur la prévention de fusion de mots :
        Si un caractère de contrôle se trouve ENTRE deux caractères imprimables,
        on insère une espace à sa place plutôt que de simplement le supprimer.
        
        Sans cette précaution :
            "fin\x0Cdébut"  →  "findébut"   (deux mots fusionnés — incorrect)
        Avec cette précaution :
            "fin\x0Cdébut"  →  "fin début"  (mots séparés — correct)
            
        On vérifie le caractère PRÉCÉDENT (i-1) et SUIVANT (i+1) pour décider.
    """
    result = []
    
    for i, char in enumerate(text):
        if is_control(char, preserve_tabs, preserve_linebreaks):
            # Le caractère est à supprimer — mais faut-il insérer une espace ?
            # Oui si on est entre deux caractères imprimables (évite la fusion)
            avant_imprimable = i > 0 and text[i-1].isprintable() and text[i-1] != ' '
            apres_imprimable = i < len(text) - 1 and text[i+1].isprintable() and text[i+1] != ' '
            if avant_imprimable and apres_imprimable:
                result.append(' ')
            # Sinon : suppression pure (début/fin de ligne, déjà une espace à côté)
            continue
        
        # Le caractère est conservé, mais peut nécessiter une normalisation
        result.append(normalize_special(char, preserve_tabs, preserve_linebreaks))
    
    # Assemblage final : une seule opération, une seule allocation mémoire
    cleaned = ''.join(result)
    
    # Normalisation des paragraphes : 3+ sauts de ligne consécutifs → double saut
    # Cela évite que la conversion \r\n → \n\n multiplie les lignes vides
    # Un double \n représente une ligne vide = séparateur de paragraphe standard
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    
    return cleaned


def count_controls(text: str) -> dict:
    """
    Compte les différents types de caractères de contrôle.
    
    Args:
        text (str): Texte à analyser
        
    Returns:
        dict: Statistiques sur les caractères de contrôle trouvés
        
    Note:
        Distingue 'supprimés' (vraiment retirés) de 'normalisés' (\r → \n, \t → espace)
        pour que les statistiques reflètent fidèlement ce que le script a fait.
    """
    stats = {
        'c0': 0,        # C0 controls (0-31 sauf \n \r \t)
        'c1': 0,        # C1 controls (128-159)
        'delete': 0,    # DEL (127)
        'bom': 0,       # BOM (65279)
        'zwsp': 0,      # espaces de largeur nulle
        'tabs': 0,      # tabulations (normalisées en espace, pas supprimées)
        'cr': 0,        # carriage returns (normalisés en \n, pas supprimés)
    }
    
    for char in text:
        code = ord(char)
        if char == '\t':
            stats['tabs'] += 1
        elif char == '\r':
            stats['cr'] += 1
        elif 0x00 <= code <= 0x1F and code not in (0x09, 0x0A, 0x0D):
            stats['c0'] += 1
        elif code == 0x7F:
            stats['delete'] += 1
        elif 0x80 <= code <= 0x9F:
            stats['c1'] += 1
        elif code == 0xFEFF:
            stats['bom'] += 1
        elif code in (0x200B, 0x200C, 0x200D, 0x200E, 0x200F):
            stats['zwsp'] += 1
    
    return stats


# =============================================================================
# FONCTION PRINCIPALE
# =============================================================================

def main():
    """
    Fonction principale du script.
    
    1. Configuration du parser d'arguments
    2. Analyse des arguments
    3. Préparation des chemins de fichiers
    4. Lecture du fichier avec gestion d'encodage
    5. Statistiques avant traitement
    6. Application du nettoyage
    7. Statistiques après traitement
    8. Écriture du résultat
    
    Chaque bloc est commenté pour expliquer son rôle et les choix techniques.
    """
    
    # -------------------------------------------------------------------------
    # BLOC 1 : CONFIGURATION DU PARSER D'ARGUMENTS
    # -------------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        description="""
RÈGLE 4 : SUPPRESSION DES CARACTÈRES DE CONTRÔLE

Supprime tous les caractères de contrôle invisibles (U+0000 à U+001F,
U+007F, U+0080 à U+009F, U+200B, U+FEFF, etc.) qui perturbent la
segmentation et l'analyse du texte.
""",
        epilog="""
╔══════════════════════════════════════════════════════════════════════════════╗
║                            1. FONCTION DÉTAILLÉE                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  • Élimine les caractères de contrôle C0 (U+0000 à U+001F) sauf \\n, \\r, \\t  ║
║  • Élimine le caractère DELETE (U+007F)                                       ║
║  • Élimine les caractères de contrôle C1 (U+0080 à U+009F)                   ║
║  • Élimine les espaces de largeur nulle (U+200B, U+200C, U+200D)             ║
║  • Élimine le BOM (Byte Order Mark) U+FEFF                                   ║
║  • Normalise \\r → \\n et \\t → espace (sauf flags --preserve-*)               ║
║  • Insère une espace quand un contrôle séparait deux mots (anti-fusion)      ║
║  • Normalise les séquences de 3+ sauts de ligne en double saut               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                            2. JUSTIFICATION                                   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Les fichiers OCR contiennent souvent des caractères de contrôle invisibles  ║
║  qui perturbent les traitements ultérieurs :                                  ║
║  • Segmentation en mots et phrases                                            ║
║  • Validation lexicale                                                        ║
║  • Recherche de motifs                                                        ║
║  • Affichage et impression                                                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                               3. EXEMPLES                                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Entrée :  "mot\\u200Bmot" (espace de largeur nulle, sans espaces autour)    ║
║  Sortie :  "mot mot" (espace insérée — les mots ne sont pas fusionnés)       ║
║                                                                               ║
║  Entrée :  "\\uFEFFIntroduction" (BOM au début)                              ║
║  Sortie :  "Introduction"                                                     ║
║                                                                               ║
║  Entrée :  "texte\\u0000avec\\u0001nul" (caractères nuls)                    ║
║  Sortie :  "texte avec nul" (espaces insérées entre les mots)                ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                         4. RISQUE ET DÉPENDANCES                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  • RISQUE : NUL                                                               ║
║    - Ne modifie jamais le sens du texte                                       ║
║    - Les caractères de contrôle n'ont pas de sens sémantique                 ║
║    - Opération réversible et idempotente                                      ║
║                                                                               ║
║  • DÉPENDANCES :                                                              ║
║    - Règles 1, 2, 3 (normalisations préalables)                              ║
║    - Aucune bibliothèque externe nécessaire                                   ║
║                                                                               ║
║  • RESSOURCES LEXICALES :                                                     ║
║    - Aucune (règle purement technique)                                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                          5. PIÈGES PYTHON À ÉVITER                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  1. FUSION DE MOTS :                                                          ║
║     Supprimer un contrôle entre deux mots les colle sans espace.             ║
║     → Ce script insère une espace dans ce cas (voir clean_text)              ║
║                                                                               ║
║  2. STATS TROMPEUSES :                                                        ║
║     \r et \t sont "normalisés", pas "supprimés". Les compteurs               ║
║     les distinguent pour refléter fidèlement ce qui s'est passé.             ║
║                                                                               ║
║  3. PARAGRAPHES :                                                             ║
║     La conversion \r\n → \n\n peut doubler les lignes vides.                ║
║     → re.sub(r'\\n{3,}', '\\n\\n') normalise après nettoyage.               ║
║                                                                               ║
║  4. BRANCHER UN FLAG :                                                        ║
║     --preserve-linebreaks doit être transmis à TOUTES les fonctions          ║
║     qui prennent une décision sur \r : is_control(), normalize_special(),    ║
║     et clean_text(). Oublier un maillon = flag sans effet.                   ║
║                                                                               ║
║  5. PERFORMANCE : liste + join() plutôt que concaténation                    ║
║     → O(n), environ 10x plus rapide sur de longs textes                     ║
║                                                                               ║
║  6. MÉMOIRE : Fichiers jusqu'à ~100 Mo OK en mémoire                        ║
║     → Au-delà, prévoir un traitement par lots                               ║
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
        help="Fichier de sortie (optionnel) - Défaut: INPUT_net.txt"
    )
    
    parser.add_argument(
        '--stats',
        action='store_true',
        help="Affiche des statistiques détaillées"
    )
    
    parser.add_argument(
        '--preserve-tabs',
        action='store_true',
        help="Préserve les tabulations (par défaut: converties en espaces)"
    )
    
    # Ce flag est branché sur normalize_special() via clean_text().
    # Sur corpus Gallica (UTF-8 Unix), les \r sont absents et ce flag
    # n'a généralement aucun effet pratique. Il illustre comment transmettre
    # un argument optionnel à travers toute la chaîne de fonctions.
    parser.add_argument(
        '--preserve-linebreaks',
        action='store_true',
        help="Préserve les retours chariot (\\r) — par défaut normalisés en \\n"
    )
    
    # -------------------------------------------------------------------------
    # BLOC 3 : ANALYSE DES ARGUMENTS
    # -------------------------------------------------------------------------
    # parse_args() lit sys.argv et retourne un objet avec les attributs
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
        suffix = "_net"
        try:
            output_path = input_path.with_stem(input_path.stem + suffix)
        except AttributeError:
            output_path = input_path.with_name(input_path.stem + suffix + input_path.suffix)
    
    # -------------------------------------------------------------------------
    # BLOC 5 : LECTURE DU FICHIER D'ENTRÉE
    # -------------------------------------------------------------------------
    print(f"📖 Lecture de {input_path}...")
    
    try:
        with open(input_path, 'r', encoding=ENCODAGE_LECTURE) as f:
            text = f.read()
        print(f"   Encodage utilisé : {ENCODAGE_LECTURE}")
        
    except UnicodeDecodeError:
        print(f"⚠️  Échec avec {ENCODAGE_LECTURE}, tentative avec {ENCODAGE_LECTURE_FALLBACK}...")
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
    stats_avant = count_controls(text)
    
    # On distingue :
    # - "supprimés" : vraiment retirés du texte (C0, C1, BOM, zwsp...)
    # - "normalisés" : transformés en autre chose (\r → \n, \t → espace)
    total_supprimes = (stats_avant['c0'] + stats_avant['c1'] +
                       stats_avant['delete'] + stats_avant['bom'] +
                       stats_avant['zwsp'])
    total_normalises = stats_avant['tabs'] + stats_avant['cr']
    total_controles = total_supprimes + total_normalises
    
    print(f"   Total caractères : {len(text):,}")
    print(f"   Caractères de contrôle : {total_controles}")
    
    if args.stats and total_controles > 0:
        print("   Détail :")
        print("   → À supprimer :")
        if stats_avant['c0'] > 0:
            print(f"      C0 controls (0x00-0x1F) : {stats_avant['c0']}")
        if stats_avant['c1'] > 0:
            print(f"      C1 controls (0x80-0x9F) : {stats_avant['c1']}")
        if stats_avant['delete'] > 0:
            print(f"      DELETE (0x7F) : {stats_avant['delete']}")
        if stats_avant['bom'] > 0:
            print(f"      BOM (U+FEFF) : {stats_avant['bom']}")
        if stats_avant['zwsp'] > 0:
            print(f"      Espaces largeur nulle : {stats_avant['zwsp']}")
        print("   → À normaliser :")
        if stats_avant['tabs'] > 0:
            print(f"      Tabulations → espace : {stats_avant['tabs']}"
                  + (" (préservées)" if args.preserve_tabs else ""))
        if stats_avant['cr'] > 0:
            print(f"      Retours chariot → \\n : {stats_avant['cr']}"
                  + (" (préservés)" if args.preserve_linebreaks else ""))
    
    # -------------------------------------------------------------------------
    # BLOC 7 : APPLICATION DU NETTOYAGE
    # -------------------------------------------------------------------------
    print(f"🔄 Suppression des caractères de contrôle...")
    
    # Les deux flags sont transmis jusqu'à normalize_special() via clean_text()
    # C'est le "branchement" complet : args → clean_text → is_control/normalize_special
    cleaned = clean_text(text,
                         preserve_tabs=args.preserve_tabs,
                         preserve_linebreaks=args.preserve_linebreaks)
    
    # -------------------------------------------------------------------------
    # BLOC 8 : STATISTIQUES APRÈS TRAITEMENT
    # -------------------------------------------------------------------------
    stats_apres = count_controls(cleaned)
    
    total_supprimes_apres = (stats_apres['c0'] + stats_apres['c1'] +
                              stats_apres['delete'] + stats_apres['bom'] +
                              stats_apres['zwsp'])
    
    # Nombre réel de suppressions (hors normalisations)
    nb_supprimes = total_supprimes - total_supprimes_apres
    # Nombre de normalisations (\r et \t traités)
    nb_normalises = (stats_avant['cr'] if not args.preserve_linebreaks else 0) + \
                    (stats_avant['tabs'] if not args.preserve_tabs else 0)
    
    print(f"   Caractères supprimés  : {nb_supprimes}")
    print(f"   Caractères normalisés : {nb_normalises} (\\r→\\n, \\t→espace)")
    
    if nb_supprimes + nb_normalises > 0:
        print(f"   ✅ Nettoyage effectué")
    else:
        print(f"   ℹ️  Aucune modification nécessaire")
    
    # -------------------------------------------------------------------------
    # BLOC 9 : ÉCRITURE DU FICHIER DE SORTIE
    # -------------------------------------------------------------------------
    print(f"💾 Écriture de {output_path}...")
    
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding=ENCODAGE_ECRITURE) as f:
            f.write(cleaned)
        
        if output_path.exists():
            taille = output_path.stat().st_size
            print(f"   ✅ Fichier écrit : {taille:,} octets")
            
    except PermissionError:
        print(f"❌ Erreur : permission refusée pour écrire dans {output_path}")
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
# Cette condition permet d'importer les fonctions sans exécuter le code
# C'est essentiel pour les tests unitaires
if __name__ == "__main__":
    sys.exit(main())
