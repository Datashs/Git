#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
===============================================================================
RÈGLE 6 : NORMALISATION DES NOMBRES ORDINAUX
===============================================================================

Description :
    Corrige les formes erronées de nombres ordinaux (1er, 2e, 3e, etc.)
    qui sont fréquemment mal OCRisées. Cette opération rétablit la forme
    correcte selon les conventions typographiques françaises.

Pourquoi les ordinaux sont-ils si souvent mal OCRisés ?
    Les systèmes OCR travaillent au niveau du pixel. Certains caractères
    se ressemblent visuellement dans les polices du XIXe siècle :
    
    - Le chiffre "1" ressemble au "l" minuscule dans les polices à empattement
      → "1er" est lu "lr", "1re" est lu "lre"
    
    - Le suffixe ordinal "me" (souvent imprimé en exposant, très petit)
      est mal reconstruit : "e" → "o" ou "c", "m" → "m", "em" → "em"
      → "2me" devient "2mo", "2mc", "2em" selon l'imprimante et le scan
    
    - Le symbole ™ (marque déposée, U+2122) ressemble visuellement à "me"
      en exposant dans certaines polices XIXe
      → "2me" est lu "2™" par l'OCR
    
    - Le "I" majuscule ressemble au chiffre "1" dans les dates
      → "1800" est lu "I800"

Fonctions du script :
    - Corrige les variantes de "1er" : lr, lRr
    - Corrige les variantes de "1re" : lre
    - Corrige les variantes de "Xe" : Xme, Xmo, Xmc, Xem, Xème, Xeme, etc.
    - Corrige les variantes de "Xde" : Xdo
    - Corrige "X™" (marque déposée OCR) en "Xe"
    - Corrige "Ixxx" (I majuscule) en "1xxx" dans les dates
    - Corrige les chiffres romains suivis d'un suffixe ordinal (avec --roman)
    - Préserve les formes déjà correctes

Exemples :
    Entrée :  "lr Janvier 1874"      Sortie :  "1er Janvier 1874"
    Entrée :  "lre PARTIE"           Sortie :  "1re PARTIE"
    Entrée :  "2me PARTIE"           Sortie :  "2e PARTIE"
    Entrée :  "4mo PARTIE"           Sortie :  "4e PARTIE"
    Entrée :  "2™ PARTIE"            Sortie :  "2e PARTIE"
    Entrée :  "I800"                 Sortie :  "1800"
    Entrée :  "XIXme siècle"         Sortie :  "XIXe siècle"  (avec --roman)

Risque : Faible à modéré — à lire attentivement avant d'appliquer
    Ce script est qualitativement différent des règles 1 à 5 :
    il ne fait pas que normaliser des caractères typographiques,
    il corrige du CONTENU textuel sur la base de motifs (regex).
    Il a été élaboré dans le cadre d'un travail sur un corpus spécifique
    (Annuaires de l'institut de droit international)
    Certaines règles peuvent présenter un risque en d'autres contextes
    D'autres règles seraient nécessaire pour travailler un autre corpus
    
    
    Trois niveaux de risque selon le type de motif :
    
    RISQUE TRÈS FAIBLE — motifs avec chiffre arabe
        Ex : \\d+me, \\d+mo, \\d+mc, \\d+ere, \\d+ème...
        Un chiffre suivi de "me", "mo", "mc" est quasi-certainement
        un ordinal mal OCRisé. Les faux positifs sont extrêmement rares.
    
    RISQUE MODÉRÉ — motifs sans chiffre ("lr", "lre" isolés)
        Ex : "lr" isolé → "1er", "lre" isolé → "1re"
        Correct sur corpus littéraire/juridique français du XIXe.
        Mais sur un corpus contenant des sigles ("lr" pour "law review",
        "livre", "lira"...), des faux positifs sont possibles.
        → Toujours vérifier avec --stats au premier passage sur un
          nouveau corpus.
    
    RISQUE MODÉRÉ — correction I→1 dans les dates (\\bI\\d{3}\\b)
        "I800" → "1800" est correct sur ce corpus.
        Mais le motif pourrait frapper un sigle ou une référence
        commençant par I suivi de trois chiffres.
        → Vérifier les occurrences avant d'appliquer en production.
    
    MOTIFS EXCLUS INTENTIONNELLEMENT (trop dangereux) :
        Il → II  : "Il" est le pronom sujet français le plus courant
        Vit → VII : "vit" est un verbe français très courant
        Ces motifs produiraient des milliers de faux positifs.
    
    Idempotence : appliquer ce script deux fois donne le même résultat.

Dépendances :
    - Règles 1 à 5 (normalisations préalables recommandées)
    - Aucune bibliothèque externe nécessaire (uniquement standard)

USAGE :
    python 06_ordinaux.py INPUT [-o OUTPUT] [--stats] [--roman]

ARGUMENTS :
    INPUT                  Fichier d'entrée (texte brut) - OBLIGATOIRE
    -o, --output OUTPUT    Fichier de sortie (optionnel)
                           Défaut: INPUT_ordinaux.txt
    --stats                Affiche le détail des formes trouvées avant correction
                           Recommandé au premier passage sur un nouveau corpus
    --roman                Corrige aussi les chiffres romains + suffixe ordinal
                           (XIXme → XIXe). Motifs sûrs uniquement.
    --exposant             Utilise les exposants Unicode (1ʳ, 2ᵉ)
                           ⚠️  Déconseillé en production (voir doc ci-dessous)

EXEMPLES :
    python 06_ordinaux.py document.txt --stats
    python 06_ordinaux.py document.txt --roman
    python 06_ordinaux.py data.txt -o propre.txt

Pièges Python et points d'attention :
    1. ORDRE DES CORRECTIONS : crucial pour éviter les chevauchements.
       Python applique les substitutions SÉQUENTIELLEMENT — chaque regex
       travaille sur le résultat de la précédente.
       
       Exemple de problème si l'ordre est mauvais :
           Règle A : "1ere" → "1re"
           Règle B : "1er"  → "1er" (identité, inutile mais inoffensif)
           
           Si on applique B avant A :
           "1ere" → "1ere" (B ne matche pas) → "1re" (A matche) ✅
           
           Mais si on avait une règle B qui transformait "1er" en autre chose,
           l'appliquer avant A pourrait modifier "1ere" partiellement.
       
       Règle générale : TOUJOURS mettre les motifs LONGS avant les COURTS.
    
    2. \\b ET CHIFFRES : le marqueur de frontière de mot \\b fonctionne
       entre un chiffre et une lettre en Python/regex.
       \\b(\\d+)me\\b  matche "3me" (frontière avant le 3 et après le e)
       mais PAS "3me" à l'intérieur d'un mot plus long comme "93mes" (rare).
    
    3. LOOKAHEAD/LOOKBEHIND : les motifs sans chiffre utilisent des
       assertions de non-présence ((?<![a-zA-Z\\d]) et (?![a-zA-Z])).
       Ces assertions vérifient ce qui précède/suit SANS le consommer.
       Exemple : (?<![a-zA-Z\\d])lr(?![a-zA-Z])
         ✅ matche " lr " (espaces autour)
         ✅ matche " lr." (ponctuation après)
         ❌ ne matche PAS "flr" (lettre avant)
         ❌ ne matche PAS "lre" (lettre après)
    
    4. U+2122 (™) : ce caractère est la "marque déposée" Unicode.
       Dans notre corpus, il apparaît uniquement comme confusion OCR
       pour le suffixe "me" imprimé en exposant ("2me" → "2™").
       La regex \\b(\\d+)™ n'a pas besoin de \\b après ™ car ™ n'est
       pas un caractère "de mot" — la frontière est naturelle.

===============================================================================
"""

import argparse
import re
import sys
from pathlib import Path

# =============================================================================
# PARAMÈTRES CONFIGURABLES
# =============================================================================
# Ces listes définissent TOUTES les corrections appliquées.
# Chaque entrée est un tuple : (motif_regex, remplacement, description)
# La description sert uniquement à la documentation et aux stats.
#
# ORDRE IMPORTANT : les motifs les plus longs (et spécifiques) doivent
# précéder les plus courts pour éviter les chevauchements.
# Exemple : "1ième" doit être traité avant "1ième" qui doit l'être avant "1e".

CORRECTIONS_ORDINAUX = [
    # =========================================================================
    # GROUPE 1 — Formes longues avec chiffre arabe (risque très faible)
    # Ces motifs sont spécifiques : un chiffre suivi d'une séquence
    # peu probable hors contexte ordinal.
    # =========================================================================

    # Formes en -ième / -ieme (avec ou sans accent)
    # Exemples OCR : "1ième" "2ieme" → confusions sur l'accent et le i
    (r'\b(\d+)ième\b',  r'\1e',  "\\d+ième → \\de"),
    (r'\b(\d+)ieme\b',  r'\1e',  "\\d+ieme → \\de"),

    # Formes en -ème / -eme (avec ou sans accent)
    # Exemples OCR : "3ème" "4eme" → l'accent est parfois omis ou ajouté
    (r'\b(\d+)ème\b',   r'\1e',  "\\d+ème → \\de"),
    (r'\b(\d+)eme\b',   r'\1e',  "\\d+eme → \\de"),

    # Formes en -lre et -ere → -re
    # "1lre" : le "l" est une confusion OCR pour "1" (voir introduction)
    # "1ere" : forme populaire non standard (la norme est "1re")
    (r'\b(\d+)lre\b',   r'\1re', "\\d+lre → \\dre"),
    (r'\b(\d+)ere\b',   r'\1re', "\\d+ere → \\dre"),

    # "1ère" avec accent → "1re" (forme correcte en français moderne)
    (r'\b1ère\b',        '1re',  "1ère → 1re"),

    # "1lr" : double confusion OCR — le "1" initial est correct mais
    # le "l" qui suit est aussi lu comme "1", donnant "lr" pour "er"
    (r'\b(\d+)lr\b',    r'\1er', "\\d+lr → \\der"),

    # =========================================================================
    # GROUPE 2 — Variantes du suffixe -me (toutes les confusions OCR réelles)
    # Ces formes ont été observées dans le corpus :
    #   -me : forme standard attendue
    #   -mo : "e" lu comme "o" (formes très similaires en petits caractères)
    #   -mc : "e" lu comme "c" (idem)
    #   -em : transposition des lettres "me" → "em"
    #   -™  : "me" exposant lu comme le symbole ™ (U+2122, marque déposée)
    #          Ce cas est surprenant mais attesté sur ce corpus.
    # =========================================================================
    (r'\b(\d+)me\b',    r'\1e',  "\\d+me → \\de  (forme principale)"),
    (r'\b(\d+)mo\b',    r'\1e',  "\\d+mo → \\de  (e lu comme o)"),
    (r'\b(\d+)mc\b',    r'\1e',  "\\d+mc → \\de  (e lu comme c)"),
    (r'\b(\d+)em\b',    r'\1e',  "\\d+em → \\de  (transposition me→em)"),
    (r'(\d+)™',         r'\1e',  "\\d+™ → \\de   (me exposant lu ™, U+2122)"),

    # Majuscules (titres en capitales)
    (r'\b(\d+)ME\b',    r'\1E',  "\\d+ME → \\dE  (majuscules)"),

    # =========================================================================
    # GROUPE 3 — Variante -do → -de
    # "2do" : "e" lu comme "o" dans le suffixe "de" (seconde, 2de)
    # Attesté dans le corpus : "2do chambre", "2do lecture"
    # =========================================================================
    (r'\b(\d+)do\b',    r'\1de', "\\d+do → \\dde (e lu comme o dans -de)"),

    # =========================================================================
    # GROUPE 4 — Correction I majuscule → 1 dans les années (risque modéré)
    # Dans les polices XIXe, le "I" majuscule et le "1" sont quasi-identiques.
    # Motif : I suivi de exactement 3 chiffres, isolé (\\b des deux côtés).
    # Exemples corpus : "I800" → "1800", "I856" → "1856"
    #
    # ⚠️  Risque : un sigle ou code commençant par I + 3 chiffres serait
    # également transformé. Vérifier avec --stats sur un nouveau corpus.
    # =========================================================================
    (r'\bI([0-9]{3})\b', r'1\1', "I\\d{3} → 1\\d{3} (I lu comme 1 dans dates)"),

    # =========================================================================
    # GROUPE 5 — Motifs sans chiffre (risque modéré — voir section Risque)
    # Ces motifs se basent sur la forme visuelle seule, sans chiffre pour
    # ancrer la correction. Ils sont corrects sur corpus juridique XIXe français
    # mais peuvent produire des faux positifs sur d'autres corpus.
    #
    # Syntaxe des assertions :
    #   (?<![a-zA-Z\d])  = ce qui précède n'est PAS une lettre ou un chiffre
    #   (?![a-zA-Z])     = ce qui suit n'est PAS une lettre
    # =========================================================================

    # "lr" isolé → "1er"
    # Attesté : "lr Janvier 1874", "§ lr.", "Article lRr"
    (r'(?<![a-zA-Z\d])lr(?![a-zA-Z])',   '1er', "lr isolé → 1er"),
    (r'(?<![a-zA-Z\d])lre(?![a-zA-Z])',  '1re', "lre isolé → 1re"),

    # Variante avec R majuscule : "lRr" → "1er"
    # Attesté : "Article lRr. -Il sera institué..."
    # Le R majuscule est une confusion OCR supplémentaire sur le "e" en exposant
    (r'\blRr\b',  '1er', "lRr → 1er (R majuscule, variante rare)"),
]


# =============================================================================
# CORRECTIONS POUR LES CHIFFRES ROMAINS (activées par --roman)
# =============================================================================
# Ces motifs ciblent les chiffres romains suivis d'un suffixe ordinal mal OCRisé.
# Exemples : "XIXme siècle" → "XIXe siècle"
#
# MOTIFS EXCLUS INTENTIONNELLEMENT — et pourquoi :
#   Il → II  : "Il" est le PRONOM SUJET français le plus fréquent.
#              Sur un texte de 100 000 mots, "Il" apparaît des centaines
#              de fois. Cette règle produirait des milliers de faux positifs.
#   Vit → VII : "vit" (verbe voir/vivre) est courant en français.
#              "Il vit à Paris" → "II VII à Paris" serait catastrophique.
#   Vl → VI   : "Vl" peut être un début de mot ou abréviation.
#   Xl → XI   : idem.
#
# Règle générale pour les chiffres romains :
#   Un motif est sûr SEULEMENT si la séquence [chiffres romains + suffixe]
#   ne correspond à aucun mot français courant.
#   [IVXLCDM]+me est sûr car aucun mot français courant ne finit en
#   [chiffres romains]me (XIme, IXme, VIme... ne sont pas des mots).

CORRECTIONS_ROMAINS = [
    # Chiffre romain + suffixe ordinal long (traiter avant le court)
    (r'\b([IVXLCDM]+)ième\b',  r'\1e', "ROM+ième → ROMe"),
    (r'\b([IVXLCDM]+)ieme\b',  r'\1e', "ROM+ieme → ROMe"),
    (r'\b([IVXLCDM]+)ème\b',   r'\1e', "ROM+ème → ROMe"),
    (r'\b([IVXLCDM]+)eme\b',   r'\1e', "ROM+eme → ROMe"),
    # Suffixe court en dernier
    (r'\b([IVXLCDM]+)me\b',    r'\1e', "ROM+me → ROMe (ex: XIXme → XIXe)"),
]


ENCODAGE_LECTURE = 'utf-8'
ENCODAGE_LECTURE_FALLBACK = 'latin1'
ENCODAGE_ECRITURE = 'utf-8'
# =============================================================================


# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def normalize_ordinaux(text: str, roman: bool = False) -> str:
    """
    Applique toutes les corrections d'ordinaux au texte.
    
    Args:
        text (str): Texte d'entrée
        roman (bool): Si True, applique aussi CORRECTIONS_ROMAINS
        
    Returns:
        str: Texte corrigé
        
    Note sur le mécanisme de substitution séquentielle :
        re.sub(pattern, replacement, text) parcourt le texte et remplace
        toutes les occurrences du pattern. Ensuite, le résultat est passé
        à la correction suivante. C'est un pipeline séquentiel, pas parallèle.
        
        Conséquence importante : si une correction produit un texte qui
        correspond à un motif ultérieur, ce motif s'appliquera aussi.
        C'est pourquoi l'ordre dans CORRECTIONS_ORDINAUX est crucial.
        
        Dans notre cas, ce risque est minime car les motifs sont disjoints
        (un ordinal corrigé "2e" ne correspond à aucun autre motif).
    """
    result = text

    # Application séquentielle de chaque correction
    for pattern, replacement, _ in CORRECTIONS_ORDINAUX:
        result = re.sub(pattern, replacement, result)

    # Corrections des chiffres romains (optionnelles)
    if roman:
        for pattern, replacement, _ in CORRECTIONS_ROMAINS:
            result = re.sub(pattern, replacement, result)

    return result


def apply_exponents(text: str) -> str:
    """
    Convertit les nombres ordinaux en utilisant des exposants Unicode.
    
    Args:
        text (str): Texte d'entrée (après normalize_ordinaux)
        
    Returns:
        str: Texte avec exposants Unicode
        
    ⚠️  Avertissement sur la compatibilité des polices :
        Les caractères utilisés sont issus de l'Alphabet Phonétique
        International (API), pas du bloc "exposants" standard :
        - U+02B3 (ʳ) : "modifier letter small r"
        - U+1D49 (ᵉ) : "modifier letter small e"
        
        Ces caractères sont ABSENTS de nombreuses polices courantes
        (Times New Roman, Arial, Calibri...). Ils s'afficheront comme
        □ ou ? dans les environnements sans support Unicode étendu.
        
        Usage recommandé : uniquement si vous contrôlez l'environnement
        d'affichage final (PDF avec police embarquée, HTML avec font-face).
        En dehors de ce cas, préférer les formes "1er", "2e" qui sont
        universellement lisibles en UTF-8 simple.
    """
    # U+02B3 = ʳ (lettre modificative r)
    text = re.sub(r'\b1er\b', '1\u02b3', text)
    text = re.sub(r'\b1re\b', '1\u02b3', text)
    # U+1D49 = ᵉ (lettre modificative e)
    text = re.sub(r'\b(\d+)e\b', lambda m: m.group(1) + '\u1d49', text)
    return text


# Listes séparées pour le comptage — plus lisible qu'une comparaison
# de chaîne sur la regex elle-même
_MOTIFS_CORRECTS = [
    r'\b\d+er\b',    # 1er
    r'\b\d+re\b',    # 1re
    r'\b\d+e\b',     # 2e, 3e, 10e...
    r'\b\d+de\b',    # 2de
]
_MOTIFS_A_CORRIGER = [
    r'\b\d+lr\b',    r'\b\d+lre\b',
    r'\b\d+me\b',    r'\b\d+mo\b',    r'\b\d+mc\b',
    r'\b\d+em\b',    r'\d+™',
    r'\b\d+ME\b',    r'\b\d+do\b',
    r'\b\d+ème\b',   r'\b\d+eme\b',
    r'\b\d+ième\b',  r'\b\d+ieme\b',
    r'\b\d+ere\b',   r'\b1ère\b',
    r'\bI[0-9]{3}\b',
]


def count_ordinaux(text: str) -> dict:
    """
    Compte les formes d'ordinaux présentes dans le texte.
    
    Args:
        text (str): Texte à analyser
        
    Returns:
        dict: Statistiques — formes correctes, à corriger, total
        
    Note sur la conception :
        On utilise deux listes séparées (_MOTIFS_CORRECTS et _MOTIFS_A_CORRIGER)
        plutôt qu'une logique conditionnelle sur le motif regex lui-même.
        Cela rend le code plus lisible et plus facile à maintenir :
        pour ajouter une nouvelle forme à corriger, on ajoute simplement
        son motif dans _MOTIFS_A_CORRIGER.
    """
    stats = {
        'formes_correctes':    0,
        'formes_corrigeables': 0,
        'total':               0,
    }
    for motif in _MOTIFS_CORRECTS:
        n = len(re.findall(motif, text))
        stats['formes_correctes'] += n
        stats['total'] += n
    for motif in _MOTIFS_A_CORRIGER:
        n = len(re.findall(motif, text))
        stats['formes_corrigeables'] += n
        stats['total'] += n
    return stats


# =============================================================================
# FONCTION PRINCIPALE
# =============================================================================

def main():
    """
    Fonction principale — orchestre les 10 blocs du pipeline.
    
    Structure :
    1.  Configuration du parser d'arguments
    2.  Analyse des arguments
    3.  Préparation des chemins de fichiers
    4.  Lecture du fichier avec gestion d'encodage
    5.  Statistiques avant traitement
    6.  Application de la normalisation
    7.  Statistiques après traitement
    8.  Écriture du résultat
    9.  (dans écriture) Vérification du fichier créé
    10. Fin du traitement
    """

    # -------------------------------------------------------------------------
    # BLOC 1 : CONFIGURATION DU PARSER D'ARGUMENTS
    # -------------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        description="""
RÈGLE 6 : NORMALISATION DES NOMBRES ORDINAUX

Corrige les formes erronées de nombres ordinaux (1er, 2e, 3e, etc.)
fréquemment produites par l'OCR sur des textes français du XIXe siècle.
""",
        epilog=r"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         1. CE QUE FAIT CE SCRIPT                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Formes corrigées (avec chiffre arabe) :                                      ║
║  • \d+lr, \d+lre          → 1er, 1re  (l confondu avec 1)                    ║
║  • \d+me, \d+mo, \d+mc    → \de       (suffixe -me et ses variantes OCR)     ║
║  • \d+em                  → \de       (transposition me→em)                  ║
║  • \d+™                   → \de       (me exposant lu comme ™, U+2122)       ║
║  • \d+ème, \d+eme         → \de       (avec/sans accent)                     ║
║  • \d+ième, \d+ieme       → \de       (formes longues)                       ║
║  • \d+ere, 1ère           → 1re       (forme populaire non standard)         ║
║  • \d+do                  → \dde      (e lu comme o dans -de)                ║
║  • I\d{3}                 → 1\d{3}    (I majuscule lu comme 1 dans dates)    ║
║  • lRr                    → 1er       (variante avec R majuscule)             ║
║                                                                               ║
║  Avec --roman (chiffres romains + suffixe ordinal) :                         ║
║  • [IVXLCDM]+me/ème/ième  → [ROM]e    (ex: XIXme → XIXe)                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                              2. NIVEAUX DE RISQUE                             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  TRÈS FAIBLE : motifs avec chiffre arabe (\d+me, \d+ere...)                  ║
║    Un chiffre suivi de "me" est quasi-certainement un ordinal OCRisé.        ║
║                                                                               ║
║  MODÉRÉ : motifs sans chiffre (lr, lre isolés)                               ║
║    ⚠️  Corrects sur corpus juridique français XIXe, mais vérifier            ║
║    avec --stats sur tout nouveau corpus.                                     ║
║                                                                               ║
║  MODÉRÉ : I\d{3} (I→1 dans les années)                                      ║
║    ⚠️  Vérifier qu'aucun sigle I+3chiffres n'est présent.                   ║
║                                                                               ║
║  MOTIFS EXCLUS — trop dangereux sur texte français :                        ║
║    Il→II  : "Il" est le pronom sujet le plus fréquent                       ║
║    Vit→VII : "vit" est un verbe courant                                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                            3. EXEMPLES CORPUS RÉEL                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  "lr Janvier 1874"     →  "1er Janvier 1874"                                 ║
║  "lre PARTIE"          →  "1re PARTIE"                                       ║
║  "2me PARTIE"          →  "2e PARTIE"                                        ║
║  "4mo PARTIE"          →  "4e PARTIE"                                        ║
║  "8mc PARTIE"          →  "8e PARTIE"                                        ║
║  "2™ PARTIE"           →  "2e PARTIE"                                        ║
║  "I800"                →  "1800"                                             ║
║  "XIXme siècle"        →  "XIXe siècle"  (avec --roman)                     ║
║  "Article lRr"         →  "Article 1er"                                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                          4. PIÈGES PYTHON À ÉVITER                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  1. ORDRE DES MOTIFS :                                                        ║
║     Toujours les motifs LONGS avant les COURTS.                              ║
║     Python applique les corrections séquentiellement.                        ║
║                                                                               ║
║  2. \b ET CHIFFRES :                                                          ║
║     \b fonctionne entre un chiffre et une lettre.                            ║
║     \b(\d+)me\b matche "3me" correctement.                                  ║
║                                                                               ║
║  3. LOOKAHEAD/LOOKBEHIND :                                                    ║
║     (?<![a-zA-Z\d])lr(?![a-zA-Z]) vérifie le contexte SANS le consommer.   ║
║     Cela permet de cibler "lr" isolé sans toucher "flr" ou "lre".           ║
║                                                                               ║
║  4. U+2122 (™) :                                                              ║
║     ™ n'est pas un caractère "de mot" — \b n'est pas nécessaire après lui.  ║
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
        help="Fichier de sortie - Défaut: INPUT_ordinaux.txt"
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help="Affiche le détail des formes trouvées (recommandé au premier passage)"
    )
    parser.add_argument(
        '--roman',
        action='store_true',
        help="Corrige les chiffres romains + suffixe ordinal (XIXme → XIXe)"
    )
    parser.add_argument(
        '--exposant',
        action='store_true',
        help="Exposants Unicode 1ʳ/2ᵉ — ⚠️  support limité, voir doc"
    )

    # -------------------------------------------------------------------------
    # BLOC 3 : ANALYSE DES ARGUMENTS
    # -------------------------------------------------------------------------
    args = parser.parse_args()

    if args.exposant:
        print("⚠️  --exposant : U+02B3 et U+1D49 absents de nombreuses polices.")
        print("   Résultat potentiellement non portable. Voir doc du script.")

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
        suffix = "_ordinaux"
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
    stats_avant = count_ordinaux(text)

    print(f"   Total caractères   : {len(text):,}")
    print(f"   Ordinaux détectés  : {stats_avant['total']}")
    print(f"   Formes correctes   : {stats_avant['formes_correctes']}")
    print(f"   Formes à corriger  : {stats_avant['formes_corrigeables']}")

    if args.stats and stats_avant['formes_corrigeables'] > 0:
        print("   Détail des formes à corriger :")
        for motif in _MOTIFS_A_CORRIGER:
            matches = re.findall(motif, text)
            if matches:
                # Compter par forme exacte pour plus de clarté
                from collections import Counter
                formes = Counter(matches)
                for forme, n in formes.most_common(5):
                    print(f"      {repr(forme):15s} × {n}")

    # -------------------------------------------------------------------------
    # BLOC 7 : APPLICATION DE LA NORMALISATION
    # -------------------------------------------------------------------------
    print("🔄 Application de la normalisation des ordinaux...")
    normalized = normalize_ordinaux(text, roman=args.roman)

    if args.exposant:
        print("🔄 Conversion en exposants Unicode...")
        normalized = apply_exponents(normalized)

    # -------------------------------------------------------------------------
    # BLOC 8 : STATISTIQUES APRÈS TRAITEMENT
    # -------------------------------------------------------------------------
    stats_apres = count_ordinaux(normalized)

    # Le nombre de corrections réelles = formes à corriger qui ont disparu
    modifications = (stats_avant['formes_corrigeables']
                     - stats_apres['formes_corrigeables'])

    if modifications > 0:
        print(f"   ✅ {modifications} ordinal(aux) normalisé(s)")
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
# Cette condition permet d'importer les fonctions du script dans un autre
# script (tests unitaires, pipeline) sans déclencher l'exécution de main().
# Si le fichier est lancé directement : __name__ == "__main__" → True
# Si le fichier est importé           : __name__ == nom_du_module → False
if __name__ == "__main__":
    sys.exit(main())