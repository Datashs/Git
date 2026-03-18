#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
===============================================================================
RÈGLE 1 : NORMALISATION UNICODE
===============================================================================

Description :
    Convertit l'intégralité du texte en forme Unicode NFC (Normalization Form
    Canonical Composition). Cette opération garantit que les caractères
    accentués, les ligatures et autres diacritiques sont représentés de
    manière unique et cohérente.

Fonction :
    - Transforme les caractères décomposés (ex: e + accent) en leur forme
      composée unique (é)
    - Uniformise la représentation des caractères spéciaux à travers tout
      le document

Justification :
    Les systèmes OCR peuvent produire du texte avec différentes
    représentations Unicode pour un même caractère (par exemple, "é" peut
    être encodé comme U+00E9 ou comme U+0065 U+0301). Cette variabilité
    perturbe tous les traitements ultérieurs : recherche de motifs,
    validation lexicale, comptage de fréquences, etc.

Exemple :
    Entrée :  "e\u0301tude"  (e + accent combinant)
    Sortie :  "étude"        (caractère unique U+00E9)

Risque : Nul
    - Ne modifie jamais le sens du texte
    - Ne peut pas introduire d'erreurs
    - Opération réversible (on peut toujours redécomposer)

Dépendances :
    - Aucune (cette règle doit être appliquée en premier)
    - Nécessite la bibliothèque standard unicodedata

Paramétrage possible :
    - FORME_NORMALISATION : 'NFC' (par défaut), 'NFD', 'NFKC', 'NFKD'
      (ne pas modifier sauf cas très spécifique)
    - ENCODAGE_LECTURE : 'utf-8' avec fallback 'latin1'
    - ENCODAGE_ECRITURE : 'utf-8' (toujours)

Pièges Python et points d'attention :
    1. Les fichiers peuvent être encodés en latin1 (ISO-8859-1) plutôt qu'utf-8
       → On tente utf-8 d'abord, puis latin1 en secours
    2. La normalisation NFC n'affecte pas tous les caractères de la même façon
       → Certaines séquences restent inchangées (c'est normal)
    3. Le comptage de modifications peut être trompeur car certains caractères
       changent sans que le texte "visuel" change
    4. Attention à la mémoire : un fichier de 400 pages (~1-2 Mo) tient en mémoire,
       mais pour des fichiers géants, il faudrait un traitement par lots
    5. Sous Windows, l'encodage par défaut de la console peut être différent
       → Toujours spécifier encoding='utf-8' dans les open()
===============================================================================
"""

import argparse
import unicodedata
from pathlib import Path

# Paramètres modifiables (en tête du script pour faciliter les ajustements)
# ---------------------------------------------------------------------------
FORME_NORMALISATION = 'NFC'        # Choix : 'NFC', 'NFD', 'NFKC', 'NFKD'
ENCODAGE_LECTURE = 'utf-8'         # Encodage d'entrée par défaut
ENCODAGE_LECTURE_FALLBACK = 'latin1' # Fallback si utf-8 échoue
ENCODAGE_ECRITURE = 'utf-8'        # Encodage de sortie (toujours utf-8)
# ---------------------------------------------------------------------------

def normalize_unicode(text: str) -> str:
    """
    Je définis une fonction appelée normalize_unicode.
        Elle prend en entrée un texte (une chaîne de caractères)
        et elle renvoie également une chaîne de caractères.
        
    Note:
        La forme NFC est la plus courante et recommandée pour le stockage
        et l'échange de texte en français.
    """
    return unicodedata.normalize(FORME_NORMALISATION, text)

"""
La fonction renvoie un texte modifié après application des règles qui suivent 
On appelle ici une fonction normalize qui appartient au module standard Python unicodedata.
La fonction normalize applique une forme de normalisation Unicode à une chaîne de caractères.
La méthode choisie est définie dans les paramètres d'entrée (début du script)
Elle s'applique à l'objet text défini lors de la déclaration de la fonction

 """

def count_changes(original: str, normalized: str) -> int:
    """
    Compte le nombre de caractères modifiés par la normalisation.
    
    Args:
        original: Texte original
        normalized: Texte normalisé
        
    Returns:
    Comparer le texte original et le texte normalisé caractère par caractère.
Compter le nombre de positions où les caractères diffèrent.
Renvoyer ce nombre.
        int: Nombre de positions où les caractères diffèrent
        
    Note:
        Ce n'est pas une véritable distance d'édition, elle ne tient pas compte des insertions et suppressions
et donne juste un ordre de grandeur
    """
    return sum(1 for a, b in zip(original, normalized) if a != b)


def main():
    global FORME_NORMALISATION
    parser = argparse.ArgumentParser(
        description="Règle 1 : Normalisation Unicode NFC",
        epilog="Documentation complète dans l'en-tête du script."
    )
    parser.add_argument(
        'input', 
        help="Fichier d'entrée (texte brut)"
    )
    parser.add_argument(
        '-o', '--output',
        help="Fichier de sortie (défaut : input_norm.txt)"
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help="Afficher des statistiques détaillées"
    )
    parser.add_argument(
        '--form',
        choices=['NFC', 'NFD', 'NFKC', 'NFKD'],
        default=FORME_NORMALISATION,
        help=f"Forme de normalisation (défaut : {FORME_NORMALISATION})"
    )
    
    args = parser.parse_args()
    
    # Mise à jour du paramètre si différent
   
    FORME_NORMALISATION = args.form
    
    # Déterminer les noms de fichiers
    input_path = Path(args.input)
    if args.output:
        output_path = Path(args.output)
    else:
        # Générer un nom de sortie basé sur le nom d'entrée
        suffix = f"_{FORME_NORMALISATION.lower()}"
        output_path = input_path.with_stem(input_path.stem + suffix)
    
    # Lecture du fichier
    print(f"📖 Lecture de {input_path}...")
    try:
        with open(input_path, 'r', encoding=ENCODAGE_LECTURE) as f:
            text = f.read()
        print(f"   Encodage détecté : {ENCODAGE_LECTURE}")
    except UnicodeDecodeError:
        # Tentative avec l'encodage de secours
        try:
            with open(input_path, 'r', encoding=ENCODAGE_LECTURE_FALLBACK) as f:
                text = f.read()
            print(f"⚠️  Lecture avec fallback : {ENCODAGE_LECTURE_FALLBACK}")
        except Exception as e:
            print(f"❌ Erreur de lecture : {e}")
            return 1
    
    # Statistiques avant traitement
    taille_originale = len(text)
    print(f"   Taille originale : {taille_originale:,} caractères")
    
    # Application de la normalisation
    print(f"🔄 Application de la normalisation {FORME_NORMALISATION}...")
    normalized = normalize_unicode(text)
    
    # Statistiques après traitement
    taille_normalisee = len(normalized)
    modifications = count_changes(text, normalized)
    
    print(f"   Taille normalisée : {taille_normalisee:,} caractères")
    print(f"   Modifications : {modifications:,} caractères")
    
    if args.stats:
        # Statistiques détaillées (optionnelles)
        diff = taille_normalisee - taille_originale
        if diff != 0:
            print(f"   Variation de taille : {diff:+d} caractères")
        if modifications > 0:
            # Compter les types de changements (informationnel)
            print(f"   Taux de modification : {modifications/taille_originale*100:.2f}%")
    
    # Écriture du résultat
    print(f"💾 Écriture de {output_path}...")
    try:
        with open(output_path, 'w', encoding=ENCODAGE_ECRITURE) as f:
            f.write(normalized)
        print("✅ Terminé avec succès")
    except Exception as e:
        print(f"❌ Erreur d'écriture : {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())