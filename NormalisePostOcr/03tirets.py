#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
===============================================================================
RÈGLE 3 : NORMALISATION DES TIRETS
===============================================================================

Description :
    Remplace les tirets longs (—, –) par le tiret court (-). Cette opération
    uniformise le caractère tiret dans tout le document pour faciliter les
    traitements ultérieurs.

Fonction :
    - Convertit les tirets cadratins (—) en tirets courts (-)
    - Convertit les tirets demi-cadratins (–) en tirets courts (-)
    - Préserve les tirets déjà corrects
    - Ne modifie pas les traits d'union dans les mots composés

Justification :
    Les systèmes OCR produisent des tirets de différentes longueurs selon :
    - La police de caractères utilisée
    - Le contexte typographique (césure, énumération, dialogue)
    - L'encodage d'origine
    
    Une forme unique simplifie tous les traitements ultérieurs :
    - Détection des mots composés
    - Recherche de motifs (expressions régulières)
    - Segmentation correcte des phrases
    - Validation lexicale

Exemple :
    Entrée :  "Paris — Berlin" (tiret cadratin U+2014)
    Sortie :  "Paris - Berlin" (tiret court U+002D)
    
    Entrée :  "1870–1871" (tiret demi-cadratin U+2013)
    Sortie :  "1870-1871" (tiret court U+002D)
    
    Entrée :  "secrétaire-général" (déjà correct)
    Sortie :  "secrétaire-général" (inchangé)

Risque : Nul
    - Ne modifie jamais le sens du texte
    - Les différentes formes de tirets sont sémantiquement équivalentes
      dans un corpus littéraire : — (dialogue), – (plage) et - (trait
      d'union) se distinguent par leur contexte, pas par leur caractère.
      Un script de détection de dialogues utilisera la position en début
      de ligne, pas le code Unicode du tiret.
    - Opération parfaitement réversible si nécessaire
    - Peut être appliquée plusieurs fois sans risque (idempotente)

Dépendances :
    - Règle 1 (normalisation Unicode) à appliquer avant
    - Règle 2 (normalisation des apostrophes) à appliquer avant
    - Aucune bibliothèque externe nécessaire (uniquement standard)

Ressources lexicales :
    - Aucune pour cette règle purement typographique

USAGE :
    python 03tiret.py INPUT [-o OUTPUT] [--stats]

ARGUMENTS :
    INPUT                  Fichier d'entrée (texte brut) - OBLIGATOIRE
    -o, --output OUTPUT    Fichier de sortie (optionnel)
                           Défaut: INPUT_tirets.txt
    --stats                Affiche des statistiques détaillées
                           (recommandé pour la première utilisation)

EXEMPLES :
    python 03tirets.py document.txt
    python 03tirets.py document.txt --stats
    python 03tirets.py data.txt -o propre.txt
    python 03tirets.py source.txt -o dest.txt --stats

Pièges Python et points d'attention :
    1. ENCODAGES : Les fichiers peuvent être en latin1 plutôt qu'utf-8
       → Le script tente utf-8 puis latin1 automatiquement
       
    2. CODES UNICODE : Plusieurs codes peuvent représenter des tirets :
       - U+002D : tiret court (hyphen-minus) -
       - U+2013 : tiret demi-cadratin (en dash) –
       - U+2014 : tiret cadratin (em dash) —
       - U+2212 : signe moins − (parfois utilisé)
       
    3. CONTEXTE : Attention à ne pas confondre avec :
       - Les traits d'union dans les mots composés (doivent rester)
       - Les signes moins dans les nombres négatifs
       - Les indicateurs de plage (1870-1871)
       
    4. PERFORMANCE : L'utilisation de str.translate() est optimale
       pour ce type de substitution caractère par caractère
       
    5. MÉMOIRE : Un fichier de 400 pages (~2 Mo) tient en mémoire
       Pour des fichiers > 100 Mo, prévoir un traitement par lots
       
    6. PATHLIB : with_stem() nécessite Python 3.9+
       Pour Python plus ancien, utiliser :
       output_path = input_path.with_name(input_path.stem + suffix + input_path.suffix)

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

TIRETS_A_REMPLACER = "—–−"           # Tirets longs à remplacer (cadratin, demi-cadratin,
                                        # − = U+2212 signe moins mathématique, inclus car
                                        # faux positif OCR fréquent sur corpus littéraire.
                                        # ⚠️  Corpus scientifique/math : NE PAS inclure.
TIRET_CORRECT = "-"                     # Tiret standard (U+002D)
ENCODAGE_LECTURE = 'utf-8'              # Encodage d'entrée par défaut
ENCODAGE_LECTURE_FALLBACK = 'latin1'    # Fallback si utf-8 échoue
ENCODAGE_ECRITURE = 'utf-8'             # Encodage de sortie (toujours utf-8)
# =============================================================================


# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def normalize_tirets(text: str) -> str:
    """
    Remplace les tirets longs par le tiret standard.
    
    Args:
        text (str): Texte d'entrée
        
    Returns:
        str: Texte avec tirets normalisés
        
    Note:
        Utilise str.maketrans() pour une substitution rapide.
        Contrairement aux apostrophes, il y a peu de variantes de tirets,
        donc une simple série de replace() serait aussi efficace.
        Mais on garde la même approche pour la cohérence.
        
    Performance:
        O(n) où n est la longueur du texte.
    """
    # Création d'une table de traduction
    # maketrans(entrées, sorties) crée une table de correspondance
    # Chaque caractère dans entrées est remplacé par le caractère correspondant dans sorties
    table = str.maketrans(TIRETS_A_REMPLACER, 
                          TIRET_CORRECT * len(TIRETS_A_REMPLACER))
    
    # Application de la table au texte complet
    #L'intérêt de passer par len() plutôt qu'écrire "---" en dur
    # est que si on ajoute un caractère à TIRETS_A_REMPLACER 
    # len() est une fonction intégrée de Python qui retourne le nombre d'éléments dans un objet. Sur une chaîne de caractères, 
    #elle compte les caractères un par un.
    # Ici (état initial du script) elle retourne 3
    #la chaîne de remplacement s'ajuste automatiquement —
    #on ne risque pas d'oublier d'ajouter un - à la main.
    # translate() applique la table à toute la chaîne en une seule passe
    return text.translate(table)


def count_tirets(text: str) -> dict:
    """
    Compte les différentes formes de tirets dans le texte.
    
    Args:
        text (str): Texte à analyser
        
    Returns:
        dict: Dictionnaire avec le nombre de chaque type de tiret
              Clés : "-" (U+002D), "–" (U+2013), "—" (U+2014)
        
    Note:
        Utile pour les statistiques et le débogage.
        Permet de voir quelles formes sont présentes dans le corpus.
    """
    # Initialisation du compteur pour toutes les formes possibles
    tirets = {
        "-": 0,   # tiret court U+002D
        "–": 0,   # tiret demi-cadratin U+2013
        "—": 0,   # tiret cadratin U+2014
        "−": 0,   # signe moins U+2212 (faux positif OCR fréquent)
                      # ⚠️  Usage mathématique légitime sur corpus scientifique.
    }
    
    # Parcours caractère par caractère
    for char in text:
        if char in tirets:
            tirets[char] += 1
    
    return tirets


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
RÈGLE 3 : NORMALISATION DES TIRETS

Remplace les tirets longs (—, –) par le tiret court (-). Cette opération
uniformise le caractère tiret dans tout le document pour faciliter les
traitements ultérieurs.
""",
        epilog="""
╔══════════════════════════════════════════════════════════════════════════════╗
║                            1. FONCTION DÉTAILLÉE                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  • Convertit les tirets cadratins (—) en tirets courts (-)                   ║
║  • Convertit les tirets demi-cadratins (–) en tirets courts (-)              ║
║  • Préserve les tirets déjà corrects                                          ║
║  • Ne modifie pas les traits d'union dans les mots composés                   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                            2. JUSTIFICATION                                   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Les systèmes OCR produisent des tirets de différentes longueurs selon :     ║
║  • La police de caractères utilisée                                           ║
║  • Le contexte typographique (césure, énumération, dialogue)                 ║
║  • L'encodage d'origine                                                        ║
║                                                                               ║
║  Une forme unique simplifie tous les traitements ultérieurs :                 ║
║  • Détection des mots composés                                                ║
║  • Recherche de motifs (expressions régulières)                               ║
║  • Segmentation correcte des phrases                                          ║
║  • Validation lexicale                                                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                               3. EXEMPLES                                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Entrée : "Paris — Berlin" (tiret cadratin U+2014)                            ║
║  Sortie : "Paris - Berlin" (tiret court U+002D)                               ║
║                                                                               ║
║  Entrée : "1870–1871" (tiret demi-cadratin U+2013)                            ║
║  Sortie : "1870-1871" (tiret court U+002D)                                    ║
║                                                                               ║
║  Entrée : "secrétaire-général" (déjà correct)                                 ║
║  Sortie : "secrétaire-général" (inchangé)                                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                         4. RISQUE ET DÉPENDANCES                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  • RISQUE : NUL                                                               ║
║    - Ne modifie jamais le sens du texte                                       ║
║    - Les formes de tirets sont sémantiquement équivalentes :                 ║
║      — (dialogue), – (plage) et - se distinguent par leur contexte          ║
║      (position, caractères voisins), pas par leur code Unicode.              ║
║    - Opération réversible et idempotente                                     ║
║                                                                               ║
║  • DÉPENDANCES :                                                              ║
║    - Règle 1 (normalisation Unicode) à appliquer avant                       ║
║    - Règle 2 (normalisation des apostrophes) à appliquer avant               ║
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
║     Plusieurs codes peuvent représenter des tirets :                          ║
║     - U+002D : tiret court (hyphen-minus) -                                  ║
║     - U+2013 : tiret demi-cadratin (en dash) –                               ║
║     - U+2014 : tiret cadratin (em dash) —                                    ║
║     - U+2212 : signe moins − (parfois utilisé)                               ║
║                                                                               ║
║  3. CONTEXTE :                                                                ║
║     Attention à ne pas confondre avec :                                       ║
║     - Les traits d'union dans les mots composés (doivent rester)              ║
║     - Les signes moins dans les nombres négatifs                              ║
║     - Les indicateurs de plage (1870-1871)                                    ║
║                                                                               ║
║  4. PERFORMANCE :                                                             ║
║     L'utilisation de str.translate() est optimale                             ║
║     pour ce type de substitution caractère par caractère                      ║
║                                                                               ║
║  5. MÉMOIRE :                                                                 ║
║     Un fichier de 400 pages (~2 Mo) tient en mémoire                         ║
║     Pour des fichiers > 100 Mo, prévoir un traitement par lots               ║
║                                                                               ║
║  6. PATHLIB :                                                                 ║
║     with_stem() nécessite Python 3.9+                                        ║
║     Pour Python plus ancien, utiliser :                                      ║
║     output_path = input_path.with_name(input_path.stem + "_tirets" + input_path.suffix)
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
        help="Fichier de sortie (optionnel) - Défaut: INPUT_tirets.txt"
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
        suffix = "_tirets"
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
    # Comptage des différentes formes de tirets
    avant = count_tirets(text)
    total_tirets_longs = avant["–"] + avant["—"] + avant["−"]
    
    print(f"   Total caractères : {len(text):,}")
    print(f"   Tirets courts (-) : {avant['-']}")
    print(f"   Tirets longs total : {total_tirets_longs}")
    
    if args.stats and total_tirets_longs > 0:
        # Affichage détaillé si demandé
        print("   Détail par type :")
        if avant["–"] > 0:
            print(f"      Demi-cadratin (–) : {avant['–']}")
        if avant["—"] > 0:
            print(f"      Cadratin (—) : {avant['—']}")
    
    # -------------------------------------------------------------------------
    # BLOC 7 : APPLICATION DE LA NORMALISATION
    # -------------------------------------------------------------------------
    print(f"🔄 Application de la normalisation...")
    normalized = normalize_tirets(text)
    
    # -------------------------------------------------------------------------
    # BLOC 8 : STATISTIQUES APRÈS TRAITEMENT
    # -------------------------------------------------------------------------
    # Nouveau comptage pour vérifier le résultat
    apres = count_tirets(normalized)
    
    # Calcul du nombre de modifications
    modifications = total_tirets_longs
    
    print(f"   Tirets courts (-) après : {apres['-']}")
    
    if modifications > 0:
        print(f"   ✅ Modifications : {modifications} tirets longs normalisés")
    else:
        print(f"   ℹ️  Aucune modification (déjà normalisé)")
    
    if args.stats and modifications > 0:
        # Détail des remplacements effectués
        print("   Remplacements effectués :")
        if avant["–"] > 0:
            print(f"      – → - : {avant['–']} fois")
        if avant["—"] > 0:
            print(f"      — → - : {avant['—']} fois")
    
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