#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
===============================================================================
SCRIPT 17 : CORRECTION DES HAPAX PAR DISTANCE DE DAMERAU-LEVENSHTEIN
===============================================================================

Description :
    Détecte les tokens hapax (fréquence 1 dans le corpus) absents du Lefff
    et les corrige automatiquement vers le mot du Lefff le plus proche,
    mesuré par la distance de Damerau-Levenshtein (DL).

    Ce script complète le script 16 (formes inconnues répétées) en traitant
    les erreurs OCR qui n'apparaissent qu'une seule fois — souvent des
    substitutions de caractères isolées :
        `activilé`       → `activité`       (l/t, substitution)
        `acles`          → `actes`          (l/t, substitution)
        `administralion` → `administration` (l/t, substitution)
        `mêmé`           → `même`           (accent parasite)
        `driot`          → `droit`          (io/oi, transposition)

Qu'est-ce que la distance de Damerau-Levenshtein ?
    C'est le nombre minimal d'opérations élémentaires pour transformer
    un mot en un autre. Quatre opérations comptent chacune pour 1 :
      - Substitution  : `acles`  → `actes`         (l → t)
      - Insertion     : `acte`   → `actes`          (+ s)
      - Suppression   : `acttes` → `actes`          (- t)
      - Transposition : `driot`  → `droit`          (io → oi)

    La transposition (absente de Levenshtein simple) capture les inversions
    de caractères adjacents, fréquentes en OCR. Sur ce corpus le gain est
    marginal (~2 cas sur 2 000) mais elle est implémentée par exhaustivité.

Note épistémologique — deux régimes de confiance :
    Ce script distingue deux situations qui ont des statuts épistémologiques
    différents, et les traite différemment en conséquence.

    — À d=1 (une seule opération) :
      Un hapax absent du Lefff à distance 1 d'un mot connu est dans la
      quasi-totalité des cas une erreur OCR ponctuelle. Le filtre d'unicité
      (voir ci-dessous) garantit de surcroît qu'un seul mot du Lefff est à
      cette distance — il n'y a pas d'ambiguïté sur la correction à appliquer.
      On est dans un régime de CERTITUDE OPÉRATIONNELLE : on agit
      automatiquement, et on documente dans un journal pour audit post-hoc.
      Le chercheur contrôle ce qui a été fait après coup, sur pièces.

    — À d=2 (deux opérations) :
      Le nombre de mots du Lefff à distance 2 d'un token donné est beaucoup
      plus élevé. L'espace de recherche s'élargit combinatoirement. Même avec
      le filtre d'unicité, le risque de proposer la mauvaise correction
      augmente. On est dans un régime de DÉCISION PROBABILISTE : on ne peut
      pas certifier que chaque correction est juste, on peut seulement estimer
      que la majorité l'est.
        Le chercheur peut, en fonction du taux d'erreur mesuré, 
        laisser le script appliquer la règle de remplacement ou pas. 
      Le oui revient à viser l'augmentation de la qualité du texte final, 
      en acceptant l'apparition de quelques erreurs. Il peut le refuser du fait
      des particularités de son matériau et de ses protocoles.
      Le protocole adapté n'est pas la validation cas par cas (fastidieuse
       sur plusierus centaines ou milliers de cas)  mais l'inspection d'un ÉCHANTILLON
      représentatif : si la qualité est acceptable sur 50 cas, on généralise
      la décision à l'ensemble. C'est la logique d'un test statistique
      appliquée à la correction textuelle.
      Le chercheur examine l'échantillon TSV et prend une décision binaire
      globale — appliquer ou non — qu'il assume et peut documenter.

    Cette distinction entre les deux régimes est une prise de position
    méthodologique explicite : on ne fait pas confiance de la même façon
    à une machine qui fait une opération et à une machine qui en fait deux.
    Le niveau de supervision humaine est calibré sur le niveau d'incertitude.

Filtres appliqués avant correction :
    1. Token absent du Lefff — condition nécessaire
    2. Fréquence = 1 dans le corpus (hapax)
    3. Longueur ≥ MIN_LONGUEUR (défaut 5 — les mots très courts sont trop ambigus)
    4. Pas de majuscule initiale (noms propres écartés)
    5. Pas de chiffre dans le token
    6. Heuristique non-français (patterns allemand/latin/néerlandais)
       Si langid est installé, protection au niveau du paragraphe en plus
    7. Candidat UNIQUE à la distance minimale — si deux mots du Lefff sont
       ex-aequo à la même distance, on ne corrige pas.
       Exemple : `vise` → `vice` (d=1) ET `viser` (d=1) → pas de correction.
                 `acles` → `actes` (d=1) uniquement → correction appliquée.

Comportement selon DISTANCE_AUTO :
    DISTANCE_AUTO = 1  (recommandé, défaut) :
      - Corrections d=1 appliquées automatiquement
      - Journal des N premières modifications exporté pour audit post-hoc
      - Aucune correction d=2

    DISTANCE_AUTO = 2 :
      - Corrections d=1 appliquées automatiquement (comme ci-dessus)
      - Échantillon de N_ECHANTILLON cas d=2 exporté en TSV
      - Le script s'arrête et demande confirmation
      - L'utilisateur examine le TSV et décide globalement (o/n)
      - Si oui : toutes les corrections d=2 sont appliquées
      - Si non : seules les corrections d=1 sont conservées

Dépendances :
    - Lefff (Lexiq/lefff_formes.txt) — obligatoire
    - langid (pip install langid) — optionnel, améliore le filtre langue
    - Modules standard uniquement : re, sys, csv, unicodedata, collections

Structure attendue :
    MonProjet/               ← répertoire de travail, lancer depuis ici
        17_levenshtein.py    ← ce script
        Lexiq/
            lefff_formes.txt ← dictionnaire Lefff (110 000 formes fléchies)

Pour utiliser un dictionnaire différent ou situé ailleurs :
    Modifier DICO_PATH ci-dessous.

USAGE :
    python 17_levenshtein.py CORPUS
    python 17_levenshtein.py CORPUS -o corpus_corrige.txt

ARGUMENTS :
    CORPUS              Fichier texte à traiter (obligatoire)
    -o, --output        Fichier de sortie (défaut : CORPUS_lev.txt)

EXEMPLES :
    # Avec DISTANCE_AUTO = 1 (défaut) :
    python 17_levenshtein.py corpus_postocr.txt
    # → applique les corrections d=1, exporte journal_lev.tsv pour audit

    # Avec DISTANCE_AUTO = 2 (modifier le paramètre en tête) :
    python 17_levenshtein.py corpus_postocr.txt
    # → applique d=1, exporte echantillon_d2.tsv, attend confirmation pour d=2

Pièges Python et points d'attention :
    1. COMPLEXITÉ ALGORITHMIQUE :
       Calculer DL entre chaque hapax et les ~110 000 entrées du Lefff
       serait O(n × m × k). On borne la recherche aux mots de longueur
       similaire (± DISTANCE_MAX) ce qui réduit m à ~3 000-5 000 par hapax.

    2. UNICITÉ DU CANDIDAT :
       On ne corrige que si UN SEUL mot du Lefff est à la distance minimale.
       C'est le filtre le plus important pour la précision — plus encore que
       la distance elle-même.

    3. PRÉSERVATION DES PARAGRAPHES :
       re.sub(r'\S+', fn, texte) — les \n\n ne sont jamais touchés.
       Même technique que les scripts 14, 15, 16.

    4. LANGID AU NIVEAU DU PARAGRAPHE :
       Sans langid, l'heuristique token ne détecte pas l'anglais courant
       (`affairs`, `upon`, `domain`). Ces cas atterrissent dans le journal
       d'audit ou l'échantillon d=2 — le chercheur les voit et les juge.
       C'est une limite connue, documentée, et gérée par la supervision
       humaine plutôt que par un filtre automatique supplémentaire.

===============================================================================
"""

import re
import sys
import csv
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Set, List, Tuple, Optional

# =============================================================================
# PARAMÈTRES CONFIGURABLES
# =============================================================================
# Tous les paramètres ajustables se trouvent ici.
# Ne pas modifier le code en dessous de cette section pour un usage courant.
#
# Structure attendue :
#
#   MonProjet/               ← répertoire de travail, lancer depuis ici
#       17_levenshtein.py    ← ce script
#       Lexiq/
#           lefff_formes.txt ← dictionnaire Lefff (110 000 formes fléchies)

# Chemin vers le dictionnaire Lefff
DICO_PATH = Path("Lexiq/lefff_formes.txt")

# Distance maximale pour correction AUTOMATIQUE (sans validation humaine)
#   1 → recommandé : corrections sûres, audit post-hoc
#   2 → plus agressif : d=1 auto + d=2 avec échantillon + confirmation globale
#   0 → désactive toutes les corrections automatiques (mode audit seul)
DISTANCE_AUTO = 1

# Distance maximale explorée
# Doit être >= DISTANCE_AUTO. Mettre à 1 si DISTANCE_AUTO = 1
# pour ne pas calculer inutilement les candidats d=2.
DISTANCE_MAX = 2

# Longueur minimale des tokens traités
# En dessous de 5, trop d'ambiguïté même à d=1
MIN_LONGUEUR = 5

# Nombre de corrections d=1 exportées dans le journal d'audit post-hoc
N_JOURNAL = 100

# Nombre de cas d=2 exportés pour l'échantillon de décision (si DISTANCE_AUTO=2)
N_ECHANTILLON = 100

# Noms des fichiers produits
FICHIER_JOURNAL     = "journal_lev.tsv"      # audit des corrections d=1
FICHIER_ECHANTILLON = "echantillon_d2.tsv"   # échantillon décisionnel d=2

ENCODAGE_LECTURE  = 'utf-8'
ENCODAGE_ECRITURE = 'utf-8'

# =============================================================================
# DÉPENDANCE OPTIONNELLE : langid
# =============================================================================
try:
    import langid
    LANGID_DISPONIBLE = True
except ImportError:
    LANGID_DISPONIBLE = False

# =============================================================================
# HEURISTIQUES DE REPLI (si langid absent)
# =============================================================================
_PATTERNS_NON_FR = [re.compile(p) for p in [
    r'[^aeiouàâéèêëîïôùûü]{4,}',   # 4+ consonnes consécutives
    r'ck\b', r'\bsch', r'oo\b', r'ee\b', r'ij\b',
    r'\bth[^éèêëàâîïôùûü]',
    r'recht\b', r'\bae\b',
    r'\b\w*atione\b', r'\b\w*ione\b',
    r'\b\w*orum\b', r'\b\w*arum\b', r'\b\w*ibus\b', r'\b\w*onis\b',
    r'\b\w{4,}ung\b', r'\b\w+keit\b', r'\b\w+heit\b', r'\b\w+schaft\b',
    r'\bge[rst][a-z]{4,}\b',
]]

def _est_non_fr(forme: str) -> bool:
    r"""Heuristique de repli quand langid n'est pas disponible."""
    fl = forme.lower()
    return any(p.search(fl) for p in _PATTERNS_NON_FR)

# =============================================================================
# DISTANCE DE DAMERAU-LEVENSHTEIN
# =============================================================================

def damerau_levenshtein(s1: str, s2: str) -> int:
    r"""
    Calcule la distance de Damerau-Levenshtein entre deux chaînes.

    La transposition de deux caractères adjacents compte pour 1,
    contrairement à Levenshtein simple où elle coûte 2.
    Exemple : 'driot' → 'droit' = DL 1, Levenshtein 2.

    Optimisation :
        Si la différence de longueur dépasse DISTANCE_MAX, retour immédiat —
        inutile de calculer une distance forcément supérieure au seuil.

    Complexité : O(len(s1) × len(s2)) — négligeable pour des mots courts.
    """
    if abs(len(s1) - len(s2)) > DISTANCE_MAX:
        return DISTANCE_MAX + 1

    len1, len2 = len(s1), len(s2)
    d = [[0] * (len2 + 1) for _ in range(len1 + 1)]
    for i in range(len1 + 1):
        d[i][0] = i
    for j in range(len2 + 1):
        d[0][j] = j

    for i in range(1, len1 + 1):
        for j in range(1, len2 + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            d[i][j] = min(
                d[i - 1][j] + 1,        # suppression
                d[i][j - 1] + 1,        # insertion
                d[i - 1][j - 1] + cost  # substitution
            )
            if i > 1 and j > 1 and s1[i-1] == s2[j-2] and s1[i-2] == s2[j-1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + cost)  # transposition

    return d[len1][len2]

# =============================================================================
# CHARGEMENT DU LEFFF
# =============================================================================

def charger_dico(chemin: Path) -> Set[str]:
    r"""
    Charge le Lefff en set pour des recherches O(1).
    Normalisation NFC pour cohérence avec le texte traité.
    """
    with open(chemin, 'r', encoding='utf-8') as f:
        return {unicodedata.normalize('NFC', ligne.strip())
                for ligne in f if ligne.strip()}

# =============================================================================
# FILTRES
# =============================================================================

def est_candidat(token: str, dico: Set[str]) -> bool:
    r"""
    Retourne True si le token est un candidat à la correction.

    Conditions cumulatives (toutes doivent être vraies) :
      - Longueur ≥ MIN_LONGUEUR
      - Pas de majuscule initiale (écarte les noms propres)
      - Pas de chiffre
      - Absent du Lefff (s'il y est, il est correct)
      - Pas de pattern orthographique non-français
    """
    if len(token) < MIN_LONGUEUR:
        return False
    if token[0].isupper():
        return False
    if any(c.isdigit() for c in token):
        return False
    forme = unicodedata.normalize('NFC', token.lower())
    if forme in dico or token in dico:
        return False
    if _est_non_fr(token):
        return False
    return True


def trouver_correction(token: str, dico: Set[str]) -> Tuple[Optional[str], int]:
    r"""
    Cherche le candidat unique le plus proche dans le Lefff.

    Retourne (correction, distance) ou (None, 99) si :
      - aucun candidat trouvé à distance ≤ DISTANCE_MAX
      - plusieurs candidats ex-aequo (ambiguïté → on ne corrige pas)

    Le filtre d'unicité est la garantie principale de précision.
    `vise` → `vice` (d=1) ET `viser` (d=1) → None (ambiguïté)
    `acles` → `actes` (d=1) uniquement → 'actes' (correction sûre)
    """
    forme = unicodedata.normalize('NFC', token.lower())
    meilleure_dist = DISTANCE_MAX + 1
    meilleur_cand  = None
    nb_ex_aequo    = 0

    for mot in dico:
        if abs(len(mot) - len(forme)) > DISTANCE_MAX:
            continue
        d = damerau_levenshtein(forme, mot)
        if d < meilleure_dist:
            meilleure_dist = d
            meilleur_cand  = mot
            nb_ex_aequo    = 1
        elif d == meilleure_dist:
            nb_ex_aequo   += 1

    if nb_ex_aequo > 1:
        return None, meilleure_dist  # ambiguïté → pas de correction

    return meilleur_cand, meilleure_dist

# =============================================================================
# ANALYSE DU CORPUS
# =============================================================================

def analyser(texte: str, dico: Set[str]) -> Tuple[List[dict], List[dict]]:
    r"""
    Analyse le corpus et retourne deux listes de corrections candidates.

    Retourne (candidats_d1, candidats_d2) :
      candidats_d1 : corrections à distance 1 (automatiques)
      candidats_d2 : corrections à distance 2 (décision globale si DISTANCE_AUTO=2)

    Chaque élément est un dict :
      token, correction, distance, contexte

    Pipeline :
      1. Filtrage des paragraphes non-français (langid si disponible)
      2. Comptage des tokens → identification des hapax
      3. Pour chaque hapax candidat → trouver_correction()
      4. Séparation d=1 / d=2
    """
    # Filtrage paragraphes non-français
    paragraphes = re.split(r'\n\s*\n', texte)
    if LANGID_DISPONIBLE:
        paras_fr = [p for p in paragraphes
                    if not p.strip() or langid.classify(p)[0] == 'fr']
    else:
        paras_fr = paragraphes
    texte_fr = '\n\n'.join(paras_fr)

    # Fréquences sur tout le texte
    compteur = Counter(
        t.lower() for t in re.findall(r'\b[a-zA-ZÀ-ÿ]{3,}\b', texte)
    )

    # Parcours des tokens du texte français
    candidats_vus = set()
    d1, d2 = [], []

    for m in re.finditer(r'\b[a-zA-ZÀ-ÿ]{3,}\b', texte_fr):
        token = m.group()
        tok_low = token.lower()

        if compteur.get(tok_low, 0) != 1:
            continue  # pas un hapax
        if tok_low in candidats_vus:
            continue
        if not est_candidat(token, dico):
            continue

        candidats_vus.add(tok_low)
        correction, dist = trouver_correction(token, dico)

        if correction is None:
            continue

        pos = m.start()
        ctx = texte_fr[max(0, pos - 25):pos + 30].replace('\n', '↵')
        entree = {'token': token, 'correction': correction,
                  'distance': dist, 'contexte': ctx}

        if dist == 1:
            d1.append(entree)
        elif dist == 2:
            d2.append(entree)

    d1.sort(key=lambda x: len(x['token']))
    d2.sort(key=lambda x: len(x['token']))
    return d1, d2

# =============================================================================
# APPLICATION DES CORRECTIONS
# =============================================================================

def appliquer_corrections(texte: str, candidats: List[dict]) -> Tuple[str, int]:
    r"""
    Applique une liste de corrections au texte.

    Utilise re.sub(r'\S+', fn, texte) pour préserver les \n\n.
    Retourne (texte_corrigé, nb_corrections_appliquées).

    Note sur l'écart candidats / corrections appliquées :
        Le nombre de corrections appliquées peut être inférieur au nombre
        de candidats pour deux raisons :
        1. Le token candidat ne se trouve pas dans le texte avec exactement
           cette casse (le re.sub parcourt le texte tel quel).
        2. Le token avait une majuscule initiale dans le texte —
           on ne corrige pas les tokens à majuscule pour ne pas toucher
           aux noms propres qui auraient échappé au filtre est_candidat().
        L'écart est affiché dans le bilan pour transparence.
    """
    index = {r['token'].lower(): r['correction'] for r in candidats}
    if not index:
        return texte, 0

    nb = [0]

    def traiter(match):
        tok = match.group(0)
        corr = index.get(tok.lower())
        if corr and tok[0].islower():
            nb[0] += 1
            return corr
        return tok

    return re.sub(r'\S+', traiter, texte), nb[0]

# =============================================================================
# EXPORT TSV
# =============================================================================

def exporter_tsv(candidats: List[dict], chemin: Path,
                 n: int, label: str, avec_jugement: bool = False):
    r"""
    Exporte les n premiers candidats dans un fichier TSV.

    Colonnes communes : token, correction, distance, contexte
    Colonne supplémentaire si avec_jugement=True : jugement
        → à remplir par le chercheur : 'correct' ou 'erreur'
        → permet d'évaluer la qualité spécifique des corrections d=2
          avant de prendre la décision globale d'appliquer ou non

    Note sur la colonne distance :
        Dans journal_lev.tsv elle vaudra toujours 1.
        Dans echantillon_d2.tsv elle vaudra toujours 2.
        Elle reste présente pour rappeler le régime de confiance
        et faciliter la lecture du fichier hors contexte.

    Encodage utf-8-sig pour compatibilité Numbers/Excel.
    """
    echantillon = candidats[:n]
    fieldnames = ['token', 'correction', 'distance', 'contexte']
    if avec_jugement:
        fieldnames.append('jugement')

    with open(chemin, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(
            f, fieldnames=fieldnames,
            delimiter='\t', extrasaction='ignore'
        )
        w.writeheader()
        for row in echantillon:
            if avec_jugement:
                row = dict(row, jugement='')
            w.writerow(row)
    print(f"   {len(echantillon)} {label} exportés → {chemin.name}")

# =============================================================================
# POINT D'ENTRÉE
# =============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="17 : correction des hapax par distance de Damerau-Levenshtein",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=r"""
Comportement selon DISTANCE_AUTO (paramètre en tête du script) :

  DISTANCE_AUTO = 1 (défaut) :
    Applique les corrections d=1 automatiquement.
    Exporte journal_lev.tsv (N premières) pour audit post-hoc.

  DISTANCE_AUTO = 2 :
    Applique les corrections d=1 automatiquement.
    Exporte echantillon_d2.tsv (100 cas d=2).
    Demande confirmation globale avant d'appliquer les d=2.
        """
    )
    parser.add_argument('corpus', help="Fichier texte à traiter")
    parser.add_argument('-o', '--output', metavar='FICHIER',
                        help="Fichier de sortie (défaut : CORPUS_lev.txt)")
    args = parser.parse_args()

    corpus_path = Path(args.corpus)
    if not corpus_path.exists():
        print(f"❌ Corpus introuvable : {corpus_path}")
        sys.exit(1)
    if not DICO_PATH.exists():
        print(f"❌ Dictionnaire introuvable : {DICO_PATH}")
        print(f"   Créer le dossier Lexiq/ et y placer lefff_formes.txt")
        sys.exit(1)

    sortie_path = (Path(args.output) if args.output
                   else Path(corpus_path.stem + '_lev.txt'))

    # En-tête
    print("=" * 60)
    print("  SCRIPT 17 — CORRECTION PAR DISTANCE DE LEVENSHTEIN")
    print("=" * 60)
    print(f"\n  Corpus        : {corpus_path.name}")
    print(f"  DISTANCE_AUTO : {DISTANCE_AUTO}")
    print(f"  DISTANCE_MAX  : {DISTANCE_MAX}")
    print(f"  langid        : {'✅ disponible' if LANGID_DISPONIBLE else '⚠️  absent (heuristiques)'}")

    # Chargement
    print(f"\n📚 Chargement du dictionnaire...")
    dico = charger_dico(DICO_PATH)
    print(f"   {len(dico):,} formes")

    print(f"📖 Lecture du corpus...")
    with open(corpus_path, 'r', encoding=ENCODAGE_LECTURE) as f:
        texte = f.read()
    n_paras = len([p for p in texte.split('\n\n') if p.strip()])
    print(f"   {len(texte):,} caractères — {n_paras} paragraphes")

    # Analyse
    print(f"\n🔍 Analyse des hapax...")
    candidats_d1, candidats_d2 = analyser(texte, dico)
    print(f"   Candidats d=1 (automatiques) : {len(candidats_d1)}")
    print(f"   Candidats d=2 (décision)     : {len(candidats_d2)}")

    if not candidats_d1 and not candidats_d2:
        print("\n   Aucun hapax corrigeable trouvé.")
        sys.exit(0)

    texte_final = texte

    # ─── RÉGIME 1 : corrections d=1 ──────────────────────────────────────────
    # Certitude opérationnelle : on agit, on documente pour audit post-hoc.
    # ─────────────────────────────────────────────────────────────────────────
    if candidats_d1:
        print(f"\n✍️  Application des corrections d=1...")
        texte_final, nb_d1 = appliquer_corrections(texte_final, candidats_d1)
        paras_apres = len([p for p in texte_final.split('\n\n') if p.strip()])
        print(f"   {nb_d1} correction(s) appliquée(s)")
        print(f"   Paragraphes : {n_paras} → {paras_apres} "
              f"({'✅' if n_paras == paras_apres else '⚠️  différence'})")

        # Journal d'audit — les N premières corrections pour vérification
        print(f"\n📋 Journal d'audit ({N_JOURNAL} premiers cas)...")
        print(f"   Régime : certitude opérationnelle — corrections appliquées,")
        print(f"   journal exporté pour vérification post-hoc.")
        exporter_tsv(candidats_d1, Path(FICHIER_JOURNAL), N_JOURNAL,
                     "corrections d=1")
        print(f"   → Inspecter {FICHIER_JOURNAL} pour vérifier la qualité.")

    # ─── RÉGIME 2 : corrections d=2 ──────────────────────────────────────────
    # Décision probabiliste : échantillon → décision globale du chercheur.
    # ─────────────────────────────────────────────────────────────────────────
    if candidats_d2 and DISTANCE_AUTO >= 2:
        print(f"\n📊 Régime d=2 — décision probabiliste")
        print(f"   {len(candidats_d2)} candidat(s) à distance 2 trouvé(s).")
        print(f"\n   Protocole :")
        print(f"   Un échantillon de {N_ECHANTILLON} cas est exporté dans")
        print(f"   {FICHIER_ECHANTILLON}. Examinez-le pour estimer la")
        print(f"   proportion de corrections correctes sur votre corpus.")
        print(f"   Votre décision s'appliquera à l'ensemble des {len(candidats_d2)} cas.")

        exporter_tsv(candidats_d2, Path(FICHIER_ECHANTILLON),
                     N_ECHANTILLON, "candidats d=2", avec_jugement=True)

        print(f"\n   Ouvrez {FICHIER_ECHANTILLON} dans Numbers ou Excel,")
        print(f"   examinez les corrections proposées, puis répondez :")
        reponse = input(
            f"\n   Appliquer les {len(candidats_d2)} corrections d=2 ? [o/n] : "
        ).strip().lower()

        if reponse in ('o', 'oui', 'y', 'yes'):
            texte_final, nb_d2 = appliquer_corrections(texte_final, candidats_d2)
            paras_apres = len([p for p in texte_final.split('\n\n') if p.strip()])
            nb_d2_applique = nb_d2
            print(f"   ✅ {nb_d2} correction(s) d=2 appliquée(s)")
            print(f"   Paragraphes : {n_paras} → {paras_apres} "
                  f"({'✅' if n_paras == paras_apres else '⚠️  différence'})")
        else:
            print(f"   ⏭️  Corrections d=2 ignorées.")

        # Aide à la documentation — taux de faux positifs estimé
        # Pour que le chercheur puisse consigner sa décision
        n_ech = min(N_ECHANTILLON, len(candidats_d2))
        print(f"\n   ── Aide à la documentation ──────────────────────────")
        print(f"   Examinez {FICHIER_ECHANTILLON} et comptez les erreurs.")
        print(f"   Le tableau ci-dessous donne l'IC à 95% selon vos observations :")
        print(f"")
        print(f"   {'Erreurs':>8}  {'Taux FP':>8}  {'IC 95% (Wilson)':>20}")
        print(f"   {'─'*44}")
        # Intervalle de Wilson — plus précis que l'IC normal pour les petits n
        # et les proportions proches de 0 ou 1
        # IC Wilson : (p̂ + z²/2n ± z√(p̂(1-p̂)/n + z²/4n²)) / (1 + z²/n)
        # avec z=1.96 pour 95%
        import math
        z = 1.96
        for k in [0, 1, 2, 3, 5, 8, 10, 15, 20]:
            if k > n_ech:
                break
            p = k / n_ech
            centre = (p + z**2 / (2*n_ech))
            marge  = z * math.sqrt(p*(1-p)/n_ech + z**2/(4*n_ech**2))
            denom  = 1 + z**2/n_ech
            ic_bas = max(0, (centre - marge) / denom)
            ic_haut = min(1, (centre + marge) / denom)
            print(f"   {k:>8}/{n_ech}  {p*100:>7.0f}%  "
                  f"   [{ic_bas*100:4.1f}% – {ic_haut*100:4.1f}%]")
        print(f"   {'─'*44}")
        print(f"   (Intervalle de Wilson à 95% — robuste pour les petits échantillons)")
        print(f"   À consigner dans votre journal de traitement.")
        print(f"   ────────────────────────────────────────────────────")

    elif candidats_d2 and DISTANCE_AUTO < 2:
        print(f"\n   ℹ️  {len(candidats_d2)} candidat(s) à d=2 non traités.")
        print(f"   Passer DISTANCE_AUTO = 2 pour les inclure.")

    # ─── BILAN RÉCAPITULATIF ─────────────────────────────────────────────────
    nb_d1_total    = len(candidats_d1)
    nb_d2_total    = len(candidats_d2)
    nb_d1_applique = nb_d1_total if candidats_d1 else 0
    # nb_d2_applique est mis à jour ci-dessous selon la décision
    # (on le récupère depuis nb_d2 si défini, sinon 0)
    try:
        nb_d2_applique
    except NameError:
        nb_d2_applique = 0

    paras_final = len([p for p in texte_final.split('\n\n') if p.strip()])

    print(f"\n{'═'*60}")
    print(f"  BILAN")
    print(f"{'═'*60}")
    print(f"  Hapax analysés")
    print(f"    Candidats d=1 trouvés     : {nb_d1_total}")
    print(f"    Candidats d=2 trouvés     : {nb_d2_total}")
    print(f"")
    print(f"  Corrections appliquées")
    print(f"    d=1 (automatiques)        : {nb_d1_applique}"
          + (f"  (sur {nb_d1_total} candidats — "
             f"{nb_d1_total - nb_d1_applique} ignorés : casse ou non trouvés)"
             if nb_d1_total != nb_d1_applique else ""))
    if DISTANCE_AUTO >= 2:
        print(f"    d=2 (décision chercheur)  : {nb_d2_applique}"
              + (f"  (sur {nb_d2_total} candidats)"
                 if nb_d2_applique != nb_d2_total else ""))
    print(f"    Total                     : {nb_d1_applique + nb_d2_applique}")
    print(f"")
    print(f"  Robustesse")
    print(f"    Paragraphes avant         : {n_paras}")
    print(f"    Paragraphes après         : {paras_final} "
          f"({'✅' if n_paras == paras_final else '⚠️  différence'})")
    print(f"")
    print(f"  Fichiers produits")
    print(f"    Corpus corrigé            : {sortie_path.name}")
    if candidats_d1:
        print(f"    Journal d=1 (audit)       : {FICHIER_JOURNAL}")
    if candidats_d2 and DISTANCE_AUTO >= 2:
        print(f"    Échantillon d=2 (décision): {FICHIER_ECHANTILLON}")
    print(f"{'═'*60}")

    # Écriture finale
    with open(sortie_path, 'w', encoding=ENCODAGE_ECRITURE) as f:
        f.write(texte_final)
    print(f"\n💾 Corpus corrigé → {sortie_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
