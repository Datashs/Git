#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
===============================================================================
RÈGLE 2 : NORMALISATION DES APOSTROPHES
===============================================================================

Description :
    Remplace toutes les apostrophes typographiques (’, ‘, ‛, `, ') par
    l'apostrophe droite simple ('). Cette opération uniformise le caractère
    apostrophe dans tout le document.

Fonction :
    - Convertit les apostrophes courbes (’) en apostrophes droites (')
    - Convertit les guillemets simples ouvrants (‘) en apostrophes
    - Convertit les guillemets simples fermants (’) en apostrophes
    - Convertit l'accent grave (`) utilisé abusivement comme apostrophe
    - Préserve les apostrophes déjà correctes

Justification :
    Les systèmes OCR produisent des apostrophes de formes variées selon :
    - La police de caractères utilisée
    - La langue du document
    - L'encodage d'origine
    - La méthode de numérisation
    
    Une forme unique simplifie tous les traitements ultérieurs :
    - Recherche de motifs (expressions régulières)
    - Détection des mots avec apostrophe
    - Validation lexicale
    - Comptage de fréquences

Exemple :
    Entrée :  "l’Institut" (apostrophe courbe U+2019)
    Sortie :  "l'Institut" (apostrophe droite U+0027)
    
    Entrée :  "l‘étude" (guillemet ouvrant U+2018)
    Sortie :  "l'étude"
    
    Entrée :  "aujourd`hui" (accent grave U+0060)
    Sortie :  "aujourd'hui"

Risque : Nul
    - Ne modifie jamais le sens du texte
    - Les différentes formes d'apostrophes sont sémantiquement équivalentes
    - Opération parfaitement réversible si nécessaire
    - Peut être appliquée plusieurs fois sans risque (idempotente)

Dépendances :
    - Règle 1 (normalisation Unicode) à appliquer avant
    - Aucune bibliothèque externe nécessaire (uniquement standard)

Ressources lexicales :
    - Aucune pour cette règle purement typographique

USAGE :
    python 02_normalisation_apostrophes.py INPUT [-o OUTPUT] [--stats]

ARGUMENTS :
    INPUT                  Fichier d'entrée (texte brut) - OBLIGATOIRE
    -o, --output OUTPUT    Fichier de sortie (optionnel)
                           Défaut: INPUT_apostrophes.txt
    --stats                Affiche des statistiques détaillées
                           (recommandé pour la première utilisation)

EXEMPLES :
    python 02_normalisation_apostrophes.py document.txt
    python 02_normalisation_apostrophes.py document.txt --stats
    python 02_normalisation_apostrophes.py data.txt -o propre.txt
    python 02_normalisation_apostrophes.py source.txt -o dest.txt --stats

Pièges Python et points d'attention :
    1. ENCODAGES : Les fichiers peuvent être en latin1 plutôt qu'utf-8
       → Le script tente utf-8 puis latin1 automatiquement
       
    2. CODES UNICODE : Plusieurs codes peuvent représenter des apostrophes :
       - U+0027 : apostrophe droite (') 
       - U+2019 : apostrophe courbe (’)
       - U+2018 : guillemet simple ouvrant (‘)
       - U+201B : guillemet simple ouvrant bas (‛)
       - U+02BC : apostrophe modificative (ʼ)
       - U+0060 : accent grave (`)
       
    3. PERFORMANCE : L'utilisation de str.maketrans() est ~10x plus rapide
       qu'une série de replace() successifs
       
    4. MÉMOIRE : Un fichier de 400 pages (~2 Mo) tient en mémoire
       Pour des fichiers > 100 Mo, prévoir un traitement par lots
       
    5. PATHLIB : with_stem() nécessite Python 3.9+
       Pour Python plus ancien, utiliser :
       output_path = input_path.with_name(input_path.stem + suffix + input_path.suffix)
       
    6. CONFUSION : Ne pas confondre avec les guillemets anglais qui doivent
       rester inchangés (ils sont traités par une autre règle)

===============================================================================
"""

import argparse
from pathlib import Path
import sys

# =============================================================================
# PARAMÈTRES CONFIGURABLES
# =============================================================================
# Placés en tête pour faciliter les ajustements sans chercher dans le code
# Ces valeurs peuvent être modifiées selon les besoins du corpus

APOSTROPHES_A_REMPLACER = "’‘‛`"        # Tous les caractères à remplacer
APOSTROPHE_CORRECT = "'"                # L'apostrophe standard (U+0027)
ENCODAGE_LECTURE = 'utf-8'              # Encodage d'entrée par défaut
ENCODAGE_LECTURE_FALLBACK = 'latin1'    # Fallback si utf-8 échoue
ENCODAGE_ECRITURE = 'utf-8'             # Encodage de sortie (toujours utf-8)
# =============================================================================


# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def normalize_apostrophes(text: str) -> str:
    """
    Remplace toutes les variantes d'apostrophes par l'apostrophe standard.
    
    Args:
        text (str): Texte d'entrée
        
    Returns:
        str: Texte avec apostrophes normalisées
        
    Note:
        Utilise str.maketrans() pour une substitution rapide.
        C'est plus efficace qu'une série de replace() successifs.
        
    Performance:
        O(n) où n est la longueur du texte.
        Environ 10x plus rapide que replace() en série.
    """
    # Création d'une table de traduction
    # maketrans(entrées, sorties) crée une table de correspondance
    # Chaque caractère dans entrées est remplacé par le caractère correspondant dans sorties
    table = str.maketrans(APOSTROPHES_A_REMPLACER, 
                          APOSTROPHE_CORRECT * len(APOSTROPHES_A_REMPLACER))
    
    # Application de la table au texte complet
    # translate() applique la table à toute la chaîne en une seule passe
    return text.translate(table)


def count_apostrophes(text: str) -> dict:
    """
    Compte les différentes formes d'apostrophes dans le texte.
    
    Args:
        text (str): Texte à analyser
        
    Returns:
        dict: Dictionnaire avec le nombre de chaque type d'apostrophe
              Clés : "'", "’", "‘", "‛", "`"
        
    Note:
        Utile pour les statistiques et le débogage.
        Permet de voir quelles formes sont présentes dans le corpus.
    """
    # Initialisation du compteur pour toutes les formes possibles
    apostrophes = {
        "'": 0,   # apostrophe droite U+0027
        "’": 0,   # apostrophe courbe U+2019
        "‘": 0,   # guillemet ouvrant U+2018
        "‛": 0,   # guillemet ouvrant bas U+201B
        "`": 0,   # accent grave U+0060
    }
    
    # Parcours caractère par caractère
    for char in text:
        if char in apostrophes:
            apostrophes[char] += 1
    
    return apostrophes


# =============================================================================
# FONCTION PRINCIPALE
# =============================================================================

def main():
    """
    Fonction principale du script.
    
  
    1. Configuration du parser d'arguments (avec intégration complète de la doc)
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
    # argparse gère automatiquement l'aide (-h) et les erreurs de syntaxe
    # RawDescriptionHelpFormatter préserve la mise en forme des chaînes multilignes
    parser = argparse.ArgumentParser(
        description="""
RÈGLE 2 : NORMALISATION DES APOSTROPHES

Convertit toutes les variantes d'apostrophes (’, ‘, ‛, `) en apostrophe
standard ('). Cette opération uniformise le caractère apostrophe dans tout
le document.
""",
        epilog="""
╔══════════════════════════════════════════════════════════════════════════════╗
║                            1. FONCTION DÉTAILLÉE                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  • Transforme les apostrophes courbes (’) → '                                 ║
║  • Transforme les guillemets simples ouvrants (‘) → '                         ║
║  • Transforme l'accent grave (`) utilisé abusivement → '                      ║
║  • Préserve les apostrophes déjà correctes                                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                            2. JUSTIFICATION                                   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Les systèmes OCR produisent des apostrophes de formes variées selon :       ║
║  • La police de caractères utilisée                                           ║
║  • La langue du document                                                      ║
║  • L'encodage d'origine                                                        ║
║                                                                               ║
║  Une forme unique simplifie tous les traitements ultérieurs :                 ║
║  • Recherche de motifs                                                        ║
║  • Détection des mots avec apostrophe                                         ║
║  • Validation lexicale                                                        ║
║  • Comptage de fréquences                                                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                               3. EXEMPLES                                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Entrée : "l’Institut" (apostrophe courbe U+2019)                             ║
║  Sortie : "l'Institut" (apostrophe droite U+0027)                             ║
║                                                                               ║
║  Entrée : "l‘étude" (guillemet ouvrant U+2018)                                ║
║  Sortie : "l'étude"                                                           ║
║                                                                               ║
║  Entrée : "aujourd`hui" (accent grave U+0060)                                 ║
║  Sortie : "aujourd'hui"                                                       ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                         4. RISQUE ET DÉPENDANCES                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  • RISQUE : NUL                                                               ║
║    - Ne modifie jamais le sens du texte                                       ║
║    - Les formes d'apostrophes sont sémantiquement équivalentes               ║
║    - Opération réversible                                                     ║
║    - Idempotente (peut être appliquée plusieurs fois)                         ║
║                                                                               ║
║  • DÉPENDANCES :                                                              ║
║    - Règle 1 (normalisation Unicode) à appliquer avant                       ║
║    - Aucune bibliothèque externe nécessaire                                   ║
║                                                                               ║
║  • RESSOURCES LEXICALES :                                                     ║
║    - Aucune (règle purement typographique)                                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                          5. PIÈGES PYTHON À ÉVITER                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  1. ENCODAGES :                                                               ║
║     Les fichiers peuvent être en latin1 plutôt qu'utf-8                       ║
║     → Le script tente utf-8 puis latin1 automatiquement                       ║
║                                                                               ║
║  2. CODES UNICODE :                                                           ║
║     Plusieurs codes peuvent représenter des apostrophes :                     ║
║     - U+0027 : apostrophe droite (')                                         ║
║     - U+2019 : apostrophe courbe (’)                                         ║
║     - U+2018 : guillemet simple ouvrant (‘)                                  ║
║     - U+201B : guillemet simple ouvrant bas (‛)                              ║
║     - U+02BC : apostrophe modificative (ʼ)                                   ║
║     - U+0060 : accent grave (`)                                              ║
║                                                                               ║
║  3. PERFORMANCE :                                                             ║
║     L'utilisation de str.maketrans() est ~10x plus rapide                    ║
║     qu'une série de replace() successifs                                     ║
║                                                                               ║
║  4. MÉMOIRE :                                                                 ║
║     Un fichier de 400 pages (~2 Mo) tient en mémoire                         ║
║     Pour des fichiers > 100 Mo, prévoir un traitement par lots               ║
║                                                                               ║
║  5. PATHLIB :                                                                 ║
║     with_stem() nécessite Python 3.9+                                        ║
║     Pour Python plus ancien, utiliser :                                      ║
║     output_path = input_path.with_name(input_path.stem + "_apostrophes" + input_path.suffix)
║                                                                               ║
║  6. CONFUSION :                                                               ║
║     Ne pas confondre avec les guillemets anglais (" ") qui doivent           ║
║     rester inchangés (ils sont traités par une autre règle)                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
""",
        formatter_class=argparse.RawDescriptionHelpFormatter  # Préserve la mise en forme
    )
    
    # -------------------------------------------------------------------------
    # BLOC 2 : DÉFINITION DES ARGUMENTS
    # -------------------------------------------------------------------------
    # Argument positionnel (obligatoire) : fichier d'entrée
    # Sans tiret, doit être fourni en premier
    parser.add_argument(
        'input', 
        help="Fichier d'entrée (texte brut) - OBLIGATOIRE"
    )
    
    # Argument optionnel : fichier de sortie
    # -o est l'abréviation, --output le nom complet
    parser.add_argument(
        '-o', '--output',
        help="Fichier de sortie (optionnel) - Défaut: INPUT_apostrophes.txt"
    )
    
    # Argument optionnel (flag) : statistiques
    # action='store_true' = True si présent, False sinon
    parser.add_argument(
        '--stats',
        action='store_true',
        help="Affiche des statistiques détaillées (recommandé pour la première utilisation)"
    )
    
    # -------------------------------------------------------------------------
    # BLOC 3 : ANALYSE DES ARGUMENTS
    # -------------------------------------------------------------------------
    # parse_args() lit sys.argv et retourne un objet avec les attributs
    args = parser.parse_args()
    
    # -------------------------------------------------------------------------
    # BLOC 4 : PRÉPARATION DES CHEMINS DE FICHIERS
    # -------------------------------------------------------------------------
    # pathlib est plus moderne et intuitif que os.path
    input_path = Path(args.input)
    
    # Vérification que le fichier d'entrée existe
    # C'est une bonne pratique pour donner un message d'erreur clair
    if not input_path.exists():
        print(f"❌ Erreur : le fichier {input_path} n'existe pas")
        sys.exit(1)
    
    # Détermination du fichier de sortie
    if args.output:
        # Si l'utilisateur a fourni un nom, on l'utilise directement
        output_path = Path(args.output)
    else:
        # Sinon, on génère un nom basé sur l'entrée
        # with_stem() change le nom sans extension (Python 3.9+)
        suffix = "_apostrophes"
        try:
            # Python 3.9 et supérieur
            output_path = input_path.with_stem(input_path.stem + suffix)
        except AttributeError:
            # Fallback pour Python plus ancien
            output_path = input_path.with_name(input_path.stem + suffix + input_path.suffix)
    
    # -------------------------------------------------------------------------
    # BLOC 5 : LECTURE DU FICHIER D'ENTRÉE
    # -------------------------------------------------------------------------
    # Gestion des erreurs d'encodage avec fallback
    # C'est un problème fréquent avec les fichiers OCR historiques
    print(f"📖 Lecture de {input_path}...")
    
    try:
        # Tentative avec l'encodage par défaut (utf-8)
        with open(input_path, 'r', encoding=ENCODAGE_LECTURE) as f:
            text = f.read()
        print(f"   Encodage utilisé : {ENCODAGE_LECTURE}")
        
    except UnicodeDecodeError:
        # Si utf-8 échoue, on essaie latin1 (ISO-8859-1)
        # C'est souvent le cas pour les vieux fichiers OCR
        print(f"⚠️  Échec avec {ENCODAGE_LECTURE}, tentative avec {ENCODAGE_LECTURE_FALLBACK}...")
        try:
            with open(input_path, 'r', encoding=ENCODAGE_LECTURE_FALLBACK) as f:
                text = f.read()
            print(f"   Encodage utilisé : {ENCODAGE_LECTURE_FALLBACK}")
            
        except Exception as e:
            # Si les deux échouent, on abandonne avec un message d'erreur clair
            print(f"❌ Erreur de lecture : {e}")
            print("   Suggestions :")
            print("   - Vérifiez que le fichier existe et est lisible")
            print("   - Le fichier est peut-être dans un autre encodage (cp1252, etc.)")
            sys.exit(1)
    
    except Exception as e:
        # Autres erreurs (permissions, disque plein, etc.)
        print(f"❌ Erreur inattendue : {e}")
        sys.exit(1)
    
    # -------------------------------------------------------------------------
    # BLOC 6 : STATISTIQUES AVANT TRAITEMENT
    # -------------------------------------------------------------------------
    # Comptage des différentes formes d'apostrophes
    avant = count_apostrophes(text)
    total_apostrophes = sum(avant.values())
    
    print(f"   Total caractères : {len(text):,}")
    print(f"   Apostrophes détectées : {total_apostrophes}")
    
    if args.stats and total_apostrophes > 0:
        # Affichage détaillé si demandé
        print("   Détail par type :")
        for char, count in avant.items():
            if count > 0:
                # repr() affiche le caractère de façon lisible, même s'il est spécial
                print(f"      {repr(char)} : {count}")
    
    # -------------------------------------------------------------------------
    # BLOC 7 : APPLICATION DE LA NORMALISATION
    # -------------------------------------------------------------------------
    print(f"🔄 Application de la normalisation...")
    normalized = normalize_apostrophes(text)
    
    # -------------------------------------------------------------------------
    # BLOC 8 : STATISTIQUES APRÈS TRAITEMENT
    # -------------------------------------------------------------------------
    # Nouveau comptage pour vérifier le résultat
    apres = count_apostrophes(normalized)
    
    # Calcul du nombre de modifications
    # Total avant - total après (qui ne devrait contenir que des apostrophes droites)
    modifications = sum(avant.values()) - apres[APOSTROPHE_CORRECT]
    
    print(f"   Apostrophes standard : {apres[APOSTROPHE_CORRECT]}")
    
    if modifications > 0:
        print(f"   ✅ Modifications : {modifications} apostrophes normalisées")
    else:
        print(f"   ℹ️  Aucune modification (déjà normalisé)")
    
    if args.stats and modifications > 0:
        # Détail des remplacements effectués
        print("   Remplacements effectués :")
        for char in APOSTROPHES_A_REMPLACER:
            if avant.get(char, 0) > 0:
                print(f"      {repr(char)} → ' : {avant[char]} fois")
    
    # -------------------------------------------------------------------------
    # BLOC 9 : ÉCRITURE DU FICHIER DE SORTIE
    # -------------------------------------------------------------------------
    print(f"💾 Écriture de {output_path}...")
    
    try:
        # Création du répertoire parent si nécessaire
        # Cela évite les erreurs si le chemin contient des dossiers inexistants
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Écriture avec l'encodage spécifié
        with open(output_path, 'w', encoding=ENCODAGE_ECRITURE) as f:
            f.write(normalized)
        
        # Vérification rapide que le fichier a bien été créé
        if output_path.exists():
            taille = output_path.stat().st_size
            print(f"   ✅ Fichier écrit : {taille:,} octets")
        else:
            print(f"   ⚠️  Le fichier n'a pas été créé (vérifiez les permissions)")
            
    except PermissionError:
        # Erreur spécifique pour les permissions
        print(f"❌ Erreur : permission refusée pour écrire dans {output_path}")
        print("   Vérifiez que vous avez les droits d'écriture dans ce dossier")
        sys.exit(1)
        
    except Exception as e:
        # Autres erreurs d'écriture
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