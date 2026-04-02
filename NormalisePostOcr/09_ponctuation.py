#!/usr/bin/env python3
# -*- coding: utf-8 -*-

r"""
===============================================================================
RÈGLE 9 : CORRECTION DES PONCTUATIONS COLLÉES
===============================================================================

Description :
    Corrige les problèmes d'espaces autour des ponctuations doubles
    (:, ;, !, ?), selon les conventions typographiques françaises ou anglaises.
    Supprime les espaces avant une virgule. 
    Ajoute avec prudence un espace aprsè un point en fonction du contexte.


    En français, les signes de ponctuation sont classés en deux catégories :
    
    Ponctuation SIMPLE (point, virgule) :
    → Pas d'espace avant, espace après si suivi d'un mot.
    → Le traitement du point est délicat parce que le signe peut avoir de nombreux rôles
        → fin de phrase
        → Abréviation
        → Nombre décimal
        → Initiale (C.L. de Bar, espace seulement après la seconde initiale)
        → présence dans des séquences OCR parasites
    →  Un traitement automatique des espaces après les virgules pose des problèmes du même ordre
    du fait de nombreuses exceptions possibles sur ce corpus (nombres, abréviations, 
    structures tabulaires rendues par des virugles)
    Un traitement systèmétique par un regex présente des riques
    D'où la décision d'introduire des règles contextuelles.
    
    Ponctuation DOUBLE (:, ;, !, ?) :
    → En français : espace avant ET espace après.
    → En anglais  : pas d'espace avant, espace après.
    → Ce script corrige ces quatre signes, qui sont plus uniformes
      et moins sujets aux exceptions que la ponctuation simple.

Fonctions :
    En mode français (--lang fr, défaut) :
    - "mot:mot"   → "mot : mot"   (espace avant et après)
    - "mot ;mot"  → "mot ; mot"   (espace avant manquante ajoutée)
    - "mot: mot"  → "mot : mot"   (espace après présente, avant ajoutée)
    - "mot : mot" → "mot : mot"   (déjà correct, inchangé)
    
    En mode anglais (--lang en) :
    - "mot:mot"   → "mot: mot"    (espace après seulement)
    - "mot :mot"  → "mot: mot"    (espace superflue avant supprimée)
    
    Dans les deux modes :
    - "10:30"  → inchangé         (heure : deux chiffres de part et d'autre)
    - "M."     → inchangé         (abréviation reconnue)
    - "C.L."   → inchangé         (initiales : [A-Z]. répété)

    Règles supplémentaires (toujours actives) :
    - "l'institut , rendent" → "l'institut, rendent"  (espace avant virgule)
    - "venir.La Belgique"   → "venir. La Belgique"    (point collé + majuscule)
    - Mot avant le point doit avoir >= 4 lettres pour éviter les faux positifs
      sur les initiales (G.M.) et abréviations courtes (Cav.)

Exemples :
    Entrée :  "membre:l'Institut"         Sortie :  "membre : l'Institut"
    Entrée :  "nous;justifier"            Sortie :  "nous ; justifier"
    Entrée :  "Quoi?comment"              Sortie :  "Quoi ? comment"
    Entrée :  "membre :l'Institut"        Sortie :  "membre : l'Institut"
    Entrée :  "réunion à 10:30"           Sortie :  "réunion à 10:30"  (inchangé)

Risque : Faible
    - Les quatre ponctuations traitées sont plus uniformes que la ponctuation simple
    - Les heures sont protégées (chiffre:chiffre)
    - Les abréviations connues sont protégées (M., vol., etc.)
    - Les initiales (C.L.) sont protégées
    
    Faux positifs résiduels possibles :
    - Ratios et fractions typographiques ("2:1", "1:3")
      → protégés par la règle heure (chiffre:chiffre)
    - Deux-points dans du code source intégré au texte
      → rare dans un corpus littéraire/juridique XIXe
    
    Idempotence : appliquer deux fois donne le même résultat.

Dépendances :
    - Règles 1 à 8 (normalisations préalables recommandées)
    - Aucune bibliothèque externe nécessaire (uniquement standard)

USAGE :
    python 09_ponctuation.py INPUT [-o OUTPUT] [--stats] [--lang fr|en]

ARGUMENTS :
    INPUT                  Fichier d'entrée (texte brut) - OBLIGATOIRE
    -o, --output OUTPUT    Fichier de sortie (optionnel)
                           Défaut: INPUT_ponctuation.txt
    --stats                Affiche le détail par signe de ponctuation
    --lang {fr,en}         Style typographique (défaut: fr)
                           fr : espace avant ET après  (" : ")
                           en : espace après seulement (": ")

EXEMPLES :
    python 09_ponctuation.py document.txt
    python 09_ponctuation.py document.txt --stats
    python 09_ponctuation.py document.txt --lang en
    python 09_ponctuation.py data.txt -o propre.txt

Pièges Python et points d'attention :
    1. TRAITEMENT DE DROITE À GAUCHE :
       Quand on insère ou supprime des caractères dans une liste,
       les indices des éléments suivants se décalent.
       En traitant de DROITE À GAUCHE (indice décroissant), on modifie
       toujours des positions déjà "passées" — les positions encore
       à traiter (à gauche) ne sont pas affectées.
       
       Exemple avec liste ['m','o','t',':','m','o','t'] :
         gauche→droite : insérer ' ' à 3 → indices 4-6 décalent → bugs
         droite→gauche : insérer ' ' à 4 → indices 0-3 intacts → OK
    
    2. CONSTRUCTION DU REMPLACEMENT REGEX :
       Le remplacement dans re.sub peut contenir des références de groupe
       (\1, \2, \3...). Si on construit la chaîne avec une f-string :
       
       Correct   : r'\1' + style + r'\3'
       Incorrect : rf'\1{style}\3'  → si style = ' : ', produit '\1 : \3'
                   → Python interprète '\3' comme groupe 3 ✅
                   → mais si style contient des backslashes, crash possible
       
       La concaténation explicite est plus sûre et plus lisible.
    
    3. CONDITION DE STYLE POUR LES DEUX LANGUES :
       Pour décider d'ajouter une espace AVANT, ne pas tester
       style.startswith(' ') car cela exclut le mode 'en'.
       Tester la langue directement : if langue == 'fr'.
    
    4. HEURES — DÉTECTION ROBUSTE :
       Un deux-points entre deux chiffres est presque certainement une heure.
       La condition pos > 0 and pos < len(texte)-1 est essentielle :
       sans elle, texte[pos-1] et texte[pos+1] pourraient lever IndexError.
    
    5. ABRÉVIATIONS — RECHERCHE EN O(1) :
       On utilise un set Python (ABREVIATIONS) plutôt qu'une liste.
       La recherche dans un set est en temps constant O(1) quelle que soit
       sa taille, contre O(n) pour une liste. Sur un texte de 100 000
       caractères avec 20 abréviations vérifiées à chaque ponctuation,
       la différence est significative.

===============================================================================
"""

import argparse
import re
import sys
from pathlib import Path

# =============================================================================
# PARAMÈTRES CONFIGURABLES
# =============================================================================

# Style d'espacement par langue
# fr : espace AVANT et APRÈS  → " : ", " ; ", " ! ", " ? "
# en : espace APRÈS seulement → ": ",  "; ",  "! ",  "? "
PONCTUATIONS = {
    ':': {'fr': ' : ', 'en': ': '},
    ';': {'fr': ' ; ', 'en': '; '},
    '!': {'fr': ' ! ', 'en': '! '},
    '?': {'fr': ' ? ', 'en': '? '},
}

# Abréviations à ne pas modifier
# Un set permet la recherche en O(1) — plus rapide qu'une liste
ABREVIATIONS = {
    'M.', 'MM.', 'Mme.', 'Mlles.', 'Dr.', 'Mgr.', 'St.', 'Ste.',
    'vol.', 't.', 'p.', 'pp.', 'art.', 'ch.', 'fig.', 'col.',
    'etc.', 'cf.', 'ibid.', 'id.', 'op. cit.', 'loc. cit.',
    'Cie.', 'Sté.', 'Ass.', 'Univ.', 'Acad.',
}

ENCODAGE_LECTURE = 'utf-8'
ENCODAGE_LECTURE_FALLBACK = 'latin1'
ENCODAGE_ECRITURE = 'utf-8'
# =============================================================================


# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def est_abreviation(texte: str, pos: int) -> bool:
    r"""
    Vérifie si la ponctuation à la position pos fait partie d'une abréviation.

    Args:
        texte (str): Texte complet
        pos (int): Position du signe de ponctuation

    Returns:
        bool: True si c'est une abréviation connue ou des initiales

    Note sur la stratégie :
        On remonte vers le début du mot (tant que les caractères sont des lettres),
        puis on extrait le mot complet (lettres + ponctuation) et on vérifie
        s'il appartient au set ABREVIATIONS.

        On vérifie aussi les initiales de la forme "C.L." ou "M.A." :
        la regex r'^([A-Z]\.)+$' matche une ou plusieurs lettres majuscules
        chacune suivie d'un point.

    Exemple :
        texte = "voir M. Dupont", pos = 7 (position du point après M)
        debut = 6 (position du M)
        mot = "M."
        "M." in ABREVIATIONS → True
    """
    # Remonter au début du mot
    debut = pos
    while debut > 0 and texte[debut - 1].isalpha():
        debut -= 1

    # Extraire le mot incluant la ponctuation
    mot = texte[debut:pos + 1]

    # Vérifier dans le set d'abréviations (O(1))
    if mot in ABREVIATIONS:
        return True

    # Vérifier les initiales : "C.L.", "M.A.", "J.C."...
    # [A-Z]\. répété une ou plusieurs fois
    if re.match(r'^([A-Z]\.)+$', mot):
        return True

    return False


def est_heure(texte: str, pos: int) -> bool:
    r"""
    Vérifie si un deux-points est un séparateur d'heure (ex: "10:30").

    Args:
        texte (str): Texte complet
        pos (int): Position du deux-points

    Returns:
        bool: True si entouré de chiffres des deux côtés

    Note :
        La vérification pos > 0 and pos < len(texte)-1 est indispensable
        pour éviter un IndexError si le ':' est en début ou fin de texte.

        Cette règle protège aussi les ratios ("2:1") et les références
        de type "art. 5:3" (article 5 alinéa 3) — effet secondaire utile.
    """
    return (pos > 0 and pos < len(texte) - 1
            and texte[pos - 1].isdigit()
            and texte[pos + 1].isdigit())


def supprimer_espace_avant_virgule(texte: str) -> tuple:
    r"""
    Supprime les espaces parasites avant une virgule.

    Args:
        texte (str): Texte d'entrée

    Returns:
        tuple: (texte_corrigé: str, nb_corrections: int)

    Justification :
        En français, la virgule n'est JAMAIS précédée d'une espace.
        C'est une règle sans exception dans le texte courant.
        Les espaces avant virgule sont systématiquement des artefacts OCR.

        Exemples dans le corpus :
            "l'institut , rendent"  →  "l'institut, rendent"
            "Sclopis ,↵Vergé"       →  "Sclopis,↵Vergé"
            "§ VII (1) , M."        →  "§ VII (1), M."

    Note sur la simplicité de la règle :
        Contrairement à la ponctuation double (:;!?), la virgule n'a pas
        de cas d'exception à gérer — pas d'heures, pas d'abréviations,
        pas de mode langue. Un simple remplacement suffit.
        re.subn() retourne (nouveau_texte, nb_remplacements) en une passe.
    """
    # re.subn() : comme re.sub() mais retourne aussi le nombre de remplacements
    result, n = re.subn(r' ,', ',', texte)
    return result, n


def corriger_point_colle(texte: str) -> tuple:
    r"""
    Insère une espace après un point de fin de phrase collé au mot suivant.

    Args:
        texte (str): Texte d'entrée

    Returns:
        tuple: (texte_corrigé: str, nb_corrections: int)

    Cible :
        Les cas du type "venir.La" ou "sympathiques.Il" où un point de fin
        de phrase est directement suivi d'un mot commençant par une majuscule,
        sans espace entre les deux.

    Règle de sécurité — longueur du mot avant le point :
        On n'applique la correction QUE si le mot avant le point comporte
        au moins 4 lettres. Cela exclut :
        - Les initiales : "G.D.", "D.", "M." (1 lettre)
        - "Cav." (3 lettres) — abréviation de Cavaliere
        Ces formes courtes sont vraisemblablement des abréviations ou
        des initiales, pas des fins de phrase.

        Exemples CORRIGÉS (mot >= 4 lettres) :
            "venir.La"        →  "venir. La"
            "sympathiques.Il" →  "sympathiques. Il"
            "élite.Nous"      →  "élite. Nous"
            "Egypte.Rapport"  →  "Egypte. Rapport"

        Exemples LAISSÉS INTACTS (mot < 4 lettres) :
            "M.Heffter"   →  inchangé  (M. = Monsieur, 1 lettre)
            "G.Lizarraga" →  inchangé  (initiale, 1 lettre)
            "Cav.Pietro"  →  inchangé  (abréviation, 3 lettres)

    Faux positif résiduel connu :
        "Mariano.Tanco" (nom propre composé, 7 lettres) sera corrigé
        en "Mariano. Tanco" — acceptable car extrêmement rare.

    Technique — utilisation d'une fonction lambda dans re.sub() :
        La règle de longueur ne peut pas s'exprimer directement en regex.
        On utilise re.sub() avec une fonction qui vérifie la longueur
        du groupe capturé avant de décider du remplacement.

        La fonction reçoit l'objet Match et retourne :
        - group(0) + ' '  si len(group(1)) >= 4  (correction)
        - group(0)        sinon                   (inchangé)
    """
    corrections = [0]  # compteur mutable dans la closure

    def remplacer(match):
        mot_avant = match.group(1)  # lettres avant le point
        if len(mot_avant) >= 4:
            corrections[0] += 1
            return match.group(0) + ' '  # ajouter espace après le point
        return match.group(0)  # laisser intact

    # Capturer : (lettres)(point)(Majuscule+minuscule)
    # On utilise un lookahead (?=...) pour ne pas consommer la majuscule suivante
    result = re.sub(
        r'([a-zA-ZÀ-ÿ]{1,})\.(?=[A-ZÀ-Ÿ][a-z])',
        remplacer,
        texte
    )
    return result, corrections[0]



def corriger_ponctuation(texte: str, langue: str = 'fr') -> tuple:
    r"""
    Corrige les espaces autour des ponctuations doubles.

    Args:
        texte (str): Texte d'entrée
        langue (str): 'fr' (espace avant+après) ou 'en' (espace après seulement)

    Returns:
        tuple: (texte_corrigé: str, modifications: list[str])

    Algorithme — traitement de droite à gauche :
        On convertit d'abord le texte en liste de caractères (les chaînes
        Python sont immuables — on ne peut pas les modifier en place).

        On parcourt ensuite de la fin vers le début
        parce que les insertions et suppressions décalent les indices.
        En allant de droite à gauche, on modifie toujours des positions
        déjà traitées — les positions encore à venir (à gauche) restent
        intactes.

        Pour chaque ponctuation trouvée :
        1. Vérifier les exceptions (heure, abréviation) → passer si oui
        2. Gérer l'espace AVANT :
           - En fr : si pas d'espace avant → insérer une espace
           - En fr ou en : si espace(s) multiple(s) avant → garder une seule
           - En en : si espace avant → supprimer
        3. Gérer l'espace APRÈS :
           - Si pas d'espace après → insérer une espace
           - Si déjà une espace → ne rien faire

    Note sur l'indice après suppression/insertion :
        Quand on supprime resultat[i-1] (l'espace avant),
        la ponctuation se retrouve à l'indice i-1.
        On ajuste i en faisant i -= 1 AVANT de tester l'espace après,
        sinon on teste la mauvaise position.

        Quand on insère resultat.insert(i, ' ') (espace avant),
        la ponctuation se retrouve à l'indice i+1.
        On ajuste i en faisant i += 1.
    """
    resultat = list(texte)
    modifications = []

    i = len(resultat) - 1
    while i >= 0:
        char = resultat[i]

        if char not in PONCTUATIONS:
            i -= 1
            continue

        # --- Vérification des exceptions ---
        texte_courant = ''.join(resultat)

        if char == ':' and est_heure(texte_courant, i):
            i -= 1
            continue

        if est_abreviation(texte_courant, i):
            i -= 1
            continue

        # --- Gestion de l'espace AVANT ---
        if langue == 'fr':
            if i > 0 and resultat[i - 1] == ' ':
                # Espace déjà présente → OK, ne rien faire
                pass
            elif i > 0 and resultat[i - 1] != ' ':
                # Espace manquante → insérer
                resultat.insert(i, ' ')
                i += 1  # La ponctuation est maintenant à i+1... non, à i après insert
                # insert(i, ' ') insère AVANT i : la ponctuation passe à i+1
                # mais on a fait i += 1 pour pointer à nouveau sur la ponctuation
                modifications.append(f"ajout espace avant {char}")
        else:
            # Mode anglais : supprimer l'espace avant si elle existe
            if i > 0 and resultat[i - 1] == ' ':
                del resultat[i - 1]
                i -= 1
                modifications.append(f"suppression espace avant {char}")

        # --- Gestion de l'espace APRÈS ---
        if i < len(resultat) - 1 and resultat[i + 1] != ' ':
            resultat.insert(i + 1, ' ')
            modifications.append(f"ajout espace après {char}")

        i -= 1

    return ''.join(resultat), modifications


def compter_problemes_ponctuation(texte: str) -> dict:
    r"""
    Compte les problèmes d'espacement autour des ponctuations.

    Args:
        texte (str): Texte à analyser

    Returns:
        dict: Statistiques — total, collée_avant, collée_après, correct, details

    Note sur le comptage :
        Chaque occurrence est classée dans UNE SEULE catégorie :
        - 'correct'      : espace avant ET après (en mode fr) ou après seul (en)
        - 'collee_avant' : lettre directement avant la ponctuation
        - 'collee_apres' : lettre directement après la ponctuation
        - 'les_deux'     : lettre avant ET après (collée des deux côtés)
        
        Les abréviations et heures sont ignorées du comptage (elles ne
        sont pas des erreurs).
    """
    stats = {
        'total': 0,
        'correct': 0,
        'collee_avant': 0,
        'collee_apres': 0,
        'les_deux': 0,
        'details': {}
    }

    for punct in PONCTUATIONS:
        punct_esc = re.escape(punct)
        stats['details'][punct] = {
            'total': 0, 'correct': 0,
            'collee_avant': 0, 'collee_apres': 0, 'les_deux': 0
        }

        for m in re.finditer(punct_esc, texte):
            pos = m.start()

            # Ignorer les exceptions
            if punct == ':' and est_heure(texte, pos):
                continue
            if est_abreviation(texte, pos):
                continue

            stats['total'] += 1
            stats['details'][punct]['total'] += 1

            avant_ok = pos > 0 and texte[pos - 1] == ' '
            apres_ok = pos < len(texte) - 1 and texte[pos + 1] == ' '
            avant_collee = pos > 0 and texte[pos - 1].isalpha()
            apres_collee = pos < len(texte) - 1 and texte[pos + 1].isalpha()

            # Classer dans UNE catégorie (évite le double comptage)
            if avant_collee and apres_collee:
                stats['les_deux'] += 1
                stats['details'][punct]['les_deux'] += 1
            elif avant_collee:
                stats['collee_avant'] += 1
                stats['details'][punct]['collee_avant'] += 1
            elif apres_collee:
                stats['collee_apres'] += 1
                stats['details'][punct]['collee_apres'] += 1
            elif avant_ok and apres_ok:
                stats['correct'] += 1
                stats['details'][punct]['correct'] += 1

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
    6.  Application de la correction
    7.  Statistiques après traitement
    8.  Écriture du résultat
    9.  Fin du traitement
    """

    # -------------------------------------------------------------------------
    # BLOC 1 : CONFIGURATION DU PARSER D'ARGUMENTS
    # -------------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        description="""
RÈGLE 9 : CORRECTION DES PONCTUATIONS COLLÉES

Corrige les espaces autour des ponctuations doubles (:, ;, !, ?).
En français : espace avant ET après. En anglais : espace après seulement.
""",
        epilog=r"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                            1. FONCTION DÉTAILLÉE                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Mode français (--lang fr, défaut) :                                          ║
║  • "mot:mot"   → "mot : mot"    (espace avant ET après ajoutées)             ║
║  • "mot ;mot"  → "mot ; mot"    (espace avant manquante ajoutée)             ║
║  • "mot: mot"  → "mot : mot"    (espace avant ajoutée)                       ║
║  • "mot : mot" → "mot : mot"    (déjà correct, inchangé)                     ║
║                                                                               ║
║  Mode anglais (--lang en) :                                                   ║
║  • "mot:mot"   → "mot: mot"     (espace après seulement)                     ║
║  • "mot :mot"  → "mot: mot"     (espace avant supprimée)                     ║
║                                                                               ║
║  Toujours préservé :                                                          ║
║  • "10:30"  → inchangé          (heure : chiffre:chiffre)                    ║
║  • "M."     → inchangé          (abréviation connue)                         ║
║  • "C.L."   → inchangé          (initiales [A-Z].)                           ║
║                                                                               ║
║  Règles supplémentaires (toujours actives, indépendantes de --lang) :        ║
║  • "l'institut , rendent" → "l'institut, rendent"  (espace avant virgule)   ║
║  • "venir.La Belgique"    → "venir. La Belgique"    (point collé + maj.)     ║
║    Condition : mot avant le point >= 4 lettres (protège M., G., Cav.)        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                            2. JUSTIFICATION                                   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Les OCR collent fréquemment les ponctuations aux mots adjacents.            ║
║  En français, :;!? exigent une espace AVANT et APRÈS.                        ║
║  La virgule (espace parasite avant) et le point collé à une majuscule        ║
║  sont aussi corrigés — dans les cas suffisamment sûrs uniquement.           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                         3. RISQUE ET LIMITATIONS                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  • RISQUE : Faible                                                            ║
║    - Heures protégées (chiffre:chiffre)                                      ║
║    - Abréviations protégées (set ABREVIATIONS)                               ║
║                                                                               ║
║                                                                           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                          4. PIÈGES PYTHON À ÉVITER                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  1. TRAITEMENT DROITE→GAUCHE :                                                ║
║     Les insertions décalent les indices. En allant de droite à gauche,       ║
║     on modifie des positions déjà traitées — celles à venir restent intactes.║
║                                                                               ║
║  2. AJUSTEMENT D'INDICE APRÈS INSERT :                                        ║
║     insert(i, ' ') insère AVANT i → la ponctuation passe à i+1.             ║
║     Il faut faire i += 1 pour pointer à nouveau sur la ponctuation.         ║
║                                                                               ║
║  3. CONDITION DE LANGUE :                                                     ║
║     Ne pas tester style.startswith(' ') pour décider d'ajouter une espace   ║
║     avant — cela exclut le mode 'en'. Tester langue == 'fr' directement.    ║
║                                                                               ║
║                                                                               ║
║  4. SET vs LISTE :                                                            ║
║     La recherche dans un set est O(1), dans une liste O(n).                  ║
║     Pour ABREVIATIONS (~20 éléments), l'impact est faible mais              ║
║     la bonne habitude s'acquiert sur les petits exemples.                    ║
║                                                                               ║
║  5. re.subn() vs re.sub() :                                                  ║
║     re.subn(pattern, repl, texte) retourne (nouveau_texte, nb_remplacements) ║
║     re.sub() retourne seulement le nouveau texte.                            ║
║     Utile pour compter les corrections sans second passage sur le texte.    ║
║                                                                               ║
║  6. re.sub() AVEC FONCTION LAMBDA :                                          ║
║     Quand la décision de remplacer dépend du contenu du match,              ║
║     on passe une fonction à re.sub() au lieu d'une chaîne fixe.            ║
║     La fonction reçoit l'objet Match et retourne la chaîne de remplacement. ║
║     Exemple : corriger_point_colle() vérifie len(match.group(1)) >= 4       ║
║     avant de décider d'insérer l'espace — impossible avec une chaîne fixe. ║
╚══════════════════════════════════════════════════════════════════════════════╝
""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # -------------------------------------------------------------------------
    # BLOC 2 : DÉFINITION DES ARGUMENTS
    # -------------------------------------------------------------------------
    parser.add_argument('input', help="Fichier d'entrée (texte brut) - OBLIGATOIRE")
    parser.add_argument('-o', '--output',
                        help="Fichier de sortie - Défaut: INPUT_ponctuation.txt")
    parser.add_argument('--stats', action='store_true',
                        help="Affiche le détail par signe de ponctuation")
    parser.add_argument('--lang', choices=['fr', 'en'], default='fr',
                        help="Style typographique : fr (défaut) ou en")

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
        suffix = "_ponctuation"
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
    stats_avant = compter_problemes_ponctuation(texte)

    print(f"   Total caractères      : {len(texte):,}")
    print(f"   Ponctuations analysées : {stats_avant['total']}")
    print(f"      Correctes           : {stats_avant['correct']}")
    print(f"      Collées avant       : {stats_avant['collee_avant']}")
    print(f"      Collées après       : {stats_avant['collee_apres']}")
    print(f"      Collées des deux    : {stats_avant['les_deux']}")

    if args.stats and stats_avant['total'] > 0:
        print("   Détail par signe :")
        for punct, details in stats_avant['details'].items():
            if details['total'] > 0:
                print(f"      '{punct}' : {details['total']} total  "
                      f"correct={details['correct']}  "
                      f"avant={details['collee_avant']}  "
                      f"après={details['collee_apres']}  "
                      f"deux={details['les_deux']}")

    # -------------------------------------------------------------------------
    # BLOC 7 : APPLICATION DE LA CORRECTION
    # -------------------------------------------------------------------------
    print(f"🔄 Correction des ponctuations (langue={args.lang})...")

    # Étape 1 : espaces autour de :;!?
    texte_corrige, liste_modifs = corriger_ponctuation(texte, langue=args.lang)

    # Étape 2 : espace parasite avant virgule
    texte_corrige, n_virgule = supprimer_espace_avant_virgule(texte_corrige)

    # Étape 3 : point collé suivi d'une majuscule
    texte_corrige, n_point = corriger_point_colle(texte_corrige)

    # -------------------------------------------------------------------------
    # BLOC 8 : STATISTIQUES APRÈS TRAITEMENT
    # -------------------------------------------------------------------------
    total = len(liste_modifs) + n_virgule + n_point
    if total > 0:
        print(f"   ✅ {len(liste_modifs)} correction(s) :;!?")
        if n_virgule > 0:
            print(f"   ✅ {n_virgule} espace(s) avant virgule supprimée(s)")
        if n_point > 0:
            print(f"   ✅ {n_point} point(s) collé(s) corrigé(s)")
    else:
        print("   ℹ️  Aucune modification nécessaire")

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
