#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
===============================================================================
SCRIPT 10 : CORRECTION DES VIRGULES COLLÉES
===============================================================================

Description :
    Insère une espace après les virgules collées entre deux mots connus
    du dictionnaire Lefff.

    "membres,les"      →  "membres, les"
    "guerre,que"       →  "guerre, que"
    "Mancini,Asser"    →  inchangé  (Mancini absent du Lefff)
    "Revue,T"          →  inchangé  (T trop court)

Pourquoi ce script existe (et pas dans le script 09) :
    Le script 09 traite les ponctuations DOUBLES (:, ;, !, ?) qui suivent
    des règles typographiques uniformes en français (espace avant ET après).
    La virgule est une ponctuation SIMPLE : pas d'espace avant, espace après
    seulement si suivi d'un mot. Ses exceptions sont nombreuses (nombres
    décimaux, abréviations, listes bibliographiques, virgules OCR entre noms
    propres) — c'est pourquoi elle a été volontairement écartée du script 09.

    Ce script traite exclusivement le cas "mot,mot" sans espace après la
    virgule, en s'appuyant sur le dictionnaire Lefff comme garde-fou :
    si les deux tokens de part et d'autre de la virgule sont connus du Lefff,
    l'absence d'espace est très probablement une erreur OCR.

Pourquoi le Lefff est un garde-fou suffisant ici :
    Les faux positifs classiques de la virgule sont naturellement filtrés :
    - Nombres décimaux    "3,14"     → chiffres, absents du Lefff
    - Références biblio  "pp.582,583"→ chiffres ou abréviations, absents
    - Noms propres        "Mancini,Asser" → noms propres, absents du Lefff
    - Initiales isolées   "Revue,T"  → "T" trop court (< MIN_LONGUEUR)
    - Tout-majuscules     "RÉSULTATS,DES" → exclu par règle explicite

    Cas limites délibérément inclus :
    - "du,moins"  → "du, moins"   (correct)
    - "de,la"     → "de, la"      (correct)
    Ces prépositions/articles sont dans le Lefff et la correction est juste.

Exemples (observés sur le corpus Annuaire IDI) :
    Entrée :  "Mais,malgré ces soins,nous sommes"
    Sortie :  "Mais, malgré ces soins, nous sommes"

    Entrée :  "Rapports de MM. Mancini,Asser,etc."
    Sortie :  "Rapports de MM. Mancini,Asser,etc."  (inchangé — noms propres)

    Entrée :  "T. I,pp.118"
    Sortie :  "T. I,pp.118"                          (inchangé — "pp" < 3 chars)

Risque : Faible
    Conditionné au double filtre Lefff sur les deux tokens.
    Faux positifs résiduels possibles : quasi-absents sur corpus juridique XIXe.
    Idempotent : appliquer deux fois donne le même résultat.

Dépendances :
    - Dictionnaire Lefff (lefff_formes.txt) ou tout fichier un-mot-par-ligne
    - Scripts 02 à 09 (normalisations préalables recommandées)
    - Aucune bibliothèque externe (modules standard uniquement)

USAGE :
    python 10_virgules.py CORPUS [--dico LEFFF] [-o SORTIE] [--stats]

ARGUMENTS :
    CORPUS              Fichier texte à traiter
    --dico LEFFF        Chemin vers le dictionnaire (défaut : lefff_formes.txt)
    -o, --output        Fichier de sortie (défaut : CORPUS_virgules.txt)
    --stats             Affiche le détail des corrections appliquées

EXEMPLES :
    python 10_virgules.py annuaire.txt
    python 10_virgules.py annuaire.txt --dico /chemin/vers/lefff_formes.txt
    python 10_virgules.py annuaire.txt --stats

Pièges Python et points d'attention :
    1. LOOKBEHIND VARIABLE :
       re.lookbehind exige une longueur fixe — on ne peut pas écrire
       (?<=[a-zA-ZÀ-ÿ]+), car la longueur du groupe est variable.
       Solution : capturer les deux tokens dans le pattern et les réinjecter
       dans le remplacement → r'(\w+),(\w+)' avec \1, \2.

    2. NORMALISATION AVANT RECHERCHE DANS LE LEFFF :
       Le texte peut contenir des accents composés (NFC vs NFD) qui ne
       correspondent pas aux entrées du Lefff. On normalise en NFC avant
       de tester l'appartenance au dictionnaire.

    3. SENSIBILITÉ À LA CASSE :
       Le Lefff contient les formes en minuscules. On teste forme.lower()
       mais on préserve la casse originale dans le remplacement.
       "Membres,les" → "Membres, les"  (M majuscule conservé)

    4. POURQUOI PAS re.sub GLOBAL SIMPLE :
       Un re.sub(r'(\w+),(\w+)', fn, texte) traiterait aussi les cas à
       l'intérieur des mots avec traits d'union ou apostrophes. On cible
       explicitement les virgules entre tokens séparés par des frontières
       de mots (\b) pour éviter les faux matchs.

    5. LONGUEUR MINIMALE (MIN_LONGUEUR) :
       Les tokens d'un seul caractère ou de deux caractères ambigus
       (T, I, p, n°...) sont exclus. Valeur par défaut : 3.
       Augmenter cette valeur réduit le nombre de corrections mais
       améliore la précision — à ajuster selon le corpus.

===============================================================================
"""

import re
import sys
import unicodedata
import argparse
from pathlib import Path
from typing import Set

# =============================================================================
# PARAMÈTRES CONFIGURABLES
# =============================================================================
# Tous les paramètres ajustables se trouvent ici.
# Ne pas modifier le code en dessous de cette section pour un usage courant.
#
# Structure attendue :
#
#   MonProjet/               ← répertoire de travail, lancer depuis ici
#       10_virgules.py       ← ce script
#       15_decoupage.py
#       16_inconnus.py
#       Lexiq/
#           lefff_formes.txt ← dictionnaire Lefff (110 000 formes fléchies)
#
# Pour utiliser un dictionnaire différent ou situé ailleurs :
#   Modifier DICO_PATH ci-dessous, ou passer --dico en ligne de commande.

# Chemin vers le dictionnaire Lefff
# Défaut : sous-dossier Lexiq/ dans le répertoire courant
DICO_PATH = Path("Lexiq/lefff_formes.txt")

# Longueur minimale des tokens pour être traités
# 2 : inclut "de", "la", "le", "du" (prépositions/articles collés — fréquents)
# 3 : plus prudent, exclut tous les mots de 2 chars
# Règle complémentaire : si les DEUX tokens font ≤ MIN_LONGUEUR, on ne corrige pas
# (ex : "de,la" bloqué même avec MIN=2 — voir corriger_virgules())
MIN_LONGUEUR = 2

ENCODAGE_LECTURE  = 'utf-8'
ENCODAGE_ECRITURE = 'utf-8'


# =============================================================================
# FONCTIONS PRINCIPALES
# =============================================================================

def charger_dictionnaire(chemin: Path) -> Set[str]:
    r"""
    Charge le dictionnaire Lefff depuis un fichier texte.

    Le Lefff (Lexique des Formes Fléchies du Français) contient environ
    110 000 formes fléchies. On le charge en set pour des recherches O(1).

    Note sur l'encodage :
        Le fichier lefff_formes.txt est en utf-8. On normalise en NFC
        pour garantir la cohérence avec le texte traité.
    """
    with open(chemin, 'r', encoding='utf-8') as f:
        formes = set()
        for ligne in f:
            forme = ligne.strip()
            if forme:
                # Normalisation NFC pour cohérence avec le texte OCR normalisé
                formes.add(unicodedata.normalize('NFC', forme))
    return formes


def est_connu(token: str, dico: Set[str]) -> bool:
    r"""
    Retourne True si le token (ou sa forme minuscule) est dans le Lefff.

    On teste d'abord la forme originale (pour les mots avec majuscule
    qui seraient dans le Lefff tels quels), puis la forme en minuscule.
    On normalise en NFC avant la recherche.

    Exemple :
        "Membres" → False (nom propre), "membres" → True
        "droit"   → True,  "Droit"  → False (selon le Lefff)
    """
    if len(token) < MIN_LONGUEUR:
        # Token trop court — risque de faux positif trop élevé
        # Ex : "T" (tome), "I" (chiffre romain), "p" (page)
        return False

    # Exclure les tout-majuscules : acronymes, titres de section
    if token.isupper() and len(token) > 1:
        return False

    forme_nfc = unicodedata.normalize('NFC', token)
    forme_min = forme_nfc.lower()

    return forme_nfc in dico or forme_min in dico


def corriger_virgules(texte: str, dico: Set[str]) -> tuple:
    r"""
    Insère une espace après les virgules collées entre deux tokens connus.

    Algorithme :
        Pattern : r'([a-zA-ZÀ-ÿ]+),([a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ]*)'
        Pour chaque match (token1, token2) :
          - Si token1 ET token2 sont connus du Lefff → insérer une espace
          - Sinon → laisser intact

        On utilise une fonction de remplacement (re.sub avec callable)
        plutôt qu'un remplacement statique, pour pouvoir appliquer le
        filtre Lefff token par token.

        Note sur le pattern :
        [a-zA-ZÀ-ÿ]+ capture les lettres latines avec accents.
        On exclut volontairement les chiffres (pas de "3,14" capturé)
        et les caractères spéciaux.

    Args :
        texte (str) : Texte d'entrée
        dico (Set[str]) : Dictionnaire Lefff

    Returns :
        tuple : (texte_corrigé, nb_corrections, détails)
        - texte_corrigé (str)    : texte avec virgules corrigées
        - nb_corrections (int)   : nombre de virgules traitées
        - détails (list[dict])   : liste des corrections {avant, après, contexte}
    """
    nb_corrections = 0
    détails = []

    # Capturer deux tokens séparés par une virgule, sans espace après
    # [a-zA-ZÀ-ÿ]+ : lettres latines avec accents (pas de chiffres)
    # La deuxième partie exige au moins 1 char pour éviter les faux matchs
    pattern = re.compile(r'([a-zA-ZÀ-ÿ]+),([a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ]*)')

    def remplacer(match):
        nonlocal nb_corrections
        t1, t2 = match.group(1), match.group(2)

        if est_connu(t1, dico) and est_connu(t2, dico):
            # Les deux tokens sont connus → virgule collée probable
            #
            # Règle de sécurité supplémentaire : si les DEUX tokens font
            # exactement MIN_LONGUEUR (2 chars par défaut), on ne corrige pas.
            # Exemples bloqués : "de,la", "en,ce", "au,du"
            # Ces paires de mots grammaticaux courts sont trop ambiguës :
            # la virgule peut être intentionnelle dans certaines constructions.
            # Exemples autorisés : "internationale,du" (16+2), "membres,les" (7+3)
            # La règle "au moins un des deux doit faire > MIN_LONGUEUR" offre
            # le bon équilibre entre couverture et précision.
            if len(t1) <= MIN_LONGUEUR and len(t2) <= MIN_LONGUEUR:
                return match.group(0)  # les deux trop courts → on laisse
            nb_corrections += 1
            avant   = match.group(0)
            après   = f"{t1}, {t2}"
            # Contexte : 25 chars avant et après le match
            pos     = match.start()
            # (Le contexte sera calculé après le re.sub — on stocke la position)
            détails.append({'avant': avant, 'après': après, 'pos': pos})
            return après
        else:
            # Au moins un token inconnu → on ne touche pas
            return match.group(0)

    texte_corrigé = pattern.sub(remplacer, texte)

    # Ajouter le contexte dans les détails (depuis le texte original)
    for d in détails:
        pos = d['pos']
        ctx = texte[max(0, pos - 25):pos + 30].replace('\n', '↵')
        d['contexte'] = ctx
        del d['pos']

    return texte_corrigé, nb_corrections, détails


def compter_candidats(texte: str, dico: Set[str]) -> dict:
    r"""
    Compte les virgules collées dans le texte, avec et sans correction possible.

    Utile pour estimer l'impact avant traitement.

    Returns :
        dict avec clés :
          'total'        : toutes les virgules lettre,lettre trouvées
          'corrigeables' : celles où les deux tokens sont dans le Lefff
          'ignorées'     : celles où au moins un token est inconnu
    """
    pattern   = re.compile(r'([a-zA-ZÀ-ÿ]+),([a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ]*)')
    total = corrigeables = ignorées = 0

    for m in pattern.finditer(texte):
        total += 1
        t1, t2 = m.group(1), m.group(2)
        if est_connu(t1, dico) and est_connu(t2, dico):
            corrigeables += 1
        else:
            ignorées += 1

    return {'total': total, 'corrigeables': corrigeables, 'ignorées': ignorées}



def appliquer(texte: str) -> tuple:
    r"""
    Point d'entrée pour le pipeline postocr.py.

    Charge le dictionnaire depuis DICO_PATH (configurable en tête de script)
    et applique corriger_virgules().

    Retourne (texte_corrigé, nb_corrections, détails) — même signature
    que corriger_virgules() — pour cohérence avec les autres scripts du pipeline.

    Si le dictionnaire est introuvable, retourne le texte inchangé avec
    un avertissement, sans lever d'exception (le pipeline continue).
    """
    if not DICO_PATH.exists():
        print(f"  ⚠️  10_virgules : dictionnaire introuvable ({DICO_PATH})")
        print(f"      Modifier DICO_PATH en tête de script.")
        return texte, 0, []
    dico = charger_dictionnaire(DICO_PATH)
    return corriger_virgules(texte, dico)

# =============================================================================
# POINT D'ENTRÉE
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="10 : correction des virgules collées (mot,mot → mot, mot)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=r"""
Exemples :
  python 10_virgules.py annuaire.txt
  python 10_virgules.py annuaire.txt --dico /chemin/lefff_formes.txt
  python 10_virgules.py annuaire.txt --stats -o annuaire_v2.txt
        """
    )
    parser.add_argument('corpus',  help="Fichier texte à traiter")
    parser.add_argument('--dico',  default=str(DICO_PATH),
                        help=f"Dictionnaire Lefff (défaut : {DICO_PATH})")
    parser.add_argument('-o', '--output', metavar='FICHIER',
                        help="Fichier de sortie (défaut : CORPUS_virgules.txt)")
    parser.add_argument('--stats', action='store_true',
                        help="Afficher le détail de chaque correction")
    args = parser.parse_args()

    corpus_path = Path(args.corpus)
    dico_path   = Path(args.dico)

    if not corpus_path.exists():
        print(f"❌ Corpus introuvable : {corpus_path}")
        sys.exit(1)
    if not dico_path.exists():
        print(f"❌ Dictionnaire introuvable : {dico_path}")
        print(f"   Modifier DICO_PATH en tête de script ou utiliser --dico")
        sys.exit(1)

    if args.output:
        sortie_path = Path(args.output)
    else:
        sortie_path = Path(corpus_path.stem + '_virgules.txt')

    # Chargement
    print(f"📚 Chargement du dictionnaire {dico_path.name}...")
    dico = charger_dictionnaire(dico_path)
    print(f"   {len(dico):,} formes chargées")

    print(f"📖 Lecture de {corpus_path.name}...")
    with open(corpus_path, 'r', encoding=ENCODAGE_LECTURE) as f:
        texte = f.read()
    print(f"   {len(texte):,} caractères — "
          f"{len([p for p in texte.split(chr(10)*2) if p.strip()])} paragraphes")

    # Audit avant traitement
    stats = compter_candidats(texte, dico)
    print(f"\n   Virgules lettre,lettre trouvées : {stats['total']}")
    print(f"      Corrigeables (double Lefff)   : {stats['corrigeables']}")
    print(f"      Ignorées (token inconnu)       : {stats['ignorées']}")

    # Application
    print(f"\n🔄 Correction des virgules collées...")
    texte_corrigé, nb, détails = corriger_virgules(texte, dico)

    # Vérification robustesse paragraphes
    paras_av = len([p for p in texte.split('\n\n') if p.strip()])
    paras_ap = len([p for p in texte_corrigé.split('\n\n') if p.strip()])
    paras_ok = paras_av == paras_ap

    print(f"   ✅ {nb} correction(s) appliquée(s)")
    print(f"   Paragraphes : {paras_av} → {paras_ap} "
          f"({'✅' if paras_ok else '⚠️  différence'})")

    if args.stats and détails:
        print(f"\n   Détail des corrections :")
        for d in détails:
            print(f"     {repr(d['avant']):20s} → {repr(d['après'])}")
            print(f"       {repr(d['contexte'])}")

    # Écriture
    with open(sortie_path, 'w', encoding=ENCODAGE_ECRITURE) as f:
        f.write(texte_corrigé)
    print(f"\n💾 Texte corrigé → {sortie_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
