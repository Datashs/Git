#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
===============================================================================
SCRIPT 16 : DÉTECTION ET CORRECTION DES FORMES INCONNUES DU DICTIONNAIRE
===============================================================================

Description :
    Repère les tokens absents du dictionnaire Lefff qui apparaissent entre
    SEUIL_MIN et SEUIL_MAX fois dans le corpus. Ces formes répétées sont
    probablement des erreurs OCR systématiques ("congrés" → "congrès",
    "conerence" → "conférence") plutôt que des hapax accidentels.

    Le script complète le script 15 (mots collés) : là où le 15 détecte
    les fusions ("ledroit"), le 16 détecte les déformations ("congrés").

Workflow en cycles :
    1. Le script analyse le corpus et exporte les formes suspectes en TSV
    2. L'utilisateur valide chaque forme dans Numbers ou Excel :
         y/ok  → erreur confirmée, saisir la correction dans 'correction'
         n/non → forme valide (nom propre, terme étranger, archaïsme)
         ?     → ignoré, reviendra au prochain cycle
    3. Le script réingère les décisions et mémorise le modèle
    4. Il applique les corrections validées au corpus
    5. Répéter jusqu'à ce qu'aucune nouvelle forme suspecte n'apparaisse

Seuils (configurables en tête) :
    SEUIL_MIN : occurrences minimum pour signaler une forme (défaut : 2)
                Les hapax (1 occurrence) sont ignorés — trop de bruit.
    SEUIL_MAX : occurrences maximum (défaut : 10)
                Au-delà, la forme est probablement un nom propre récurrent
                ou un terme technique du domaine, pas une erreur OCR.

Filtres automatiques :
    - Tokens de moins de 4 caractères → ignorés (trop courts pour être fiables)
    - Chiffres, chiffres romains, intervalles numériques → ignorés
    - URLs, chemins, identifiants structurés → ignorés
    - Mots composés avec tiret dont les parties sont connues → ignorés
    - Mots avec apostrophe dont une partie est connue → ignorés
    - Majuscule hors début de phrase → probablement nom propre, ignoré
    - Tout en majuscules → acronyme, ignoré
    - Détection de langue (langid ou heuristiques) → tokens non-français ignorés

Dépendance optionnelle — langid :
    Si langid est installé (pip install langid), le script l'utilise pour :
    - Filtrer les paragraphes entièrement en langue étrangère
    - Détecter les tokens en allemand, latin, néerlandais, anglais...
    - Affiner la détection des noms propres étrangers
    Si langid n'est PAS installé, le script fonctionne avec des heuristiques
    de repli basées sur des patterns orthographiques caractéristiques
    (suffixes latins -orum/-ibus, terminaisons allemandes -ung/-keit, etc.).
    La détection est moins précise mais aucune erreur n'est bloquante.
    ⚠️  langid est peu fiable sur des tokens courts (< 8 caractères).
    Son usage sur des tokens isolés est une heuristique, pas une certitude.

Format du fichier de validation (TSV, séparateur tabulation) :
    Colonnes : forme | occurences | contexte | decision | correction
    Colonne 'decision' :
      y  ou ok    → erreur confirmée, correction obligatoire dans 'correction'
      n  ou non   → forme valide à ignorer définitivement
      ?           → ignoré (reviendra au cycle suivant)

Cohérence avec le script 15 :
    Les deux scripts utilisent le même format TSV (séparateur tabulation)
    et le même mécanisme de cycle d'apprentissage (JSON persistant).
    Le script 15 traite les mots collés, le 16 traite les déformations.
    Ils peuvent être appliqués dans n'importe quel ordre ou en parallèle.

Dépendances :
    - Dictionnaire Lefff (lefff_formes.txt) ou tout fichier un-mot-par-ligne
    - langid (optionnel) : pip install langid
    - Modules standard : csv, json, re, sys, unicodedata, pathlib,
                         collections, typing

USAGE :
    python 16_inconnus.py [CORPUS]

ARGUMENTS :
    CORPUS    Fichier texte à traiter (optionnel)
              Défaut : corpus_brut.txt

EXEMPLES :
    python 16_inconnus.py
    python 16_inconnus.py annuaire_idi.txt
    python 16_inconnus.py mon_corpus.txt

PARAMÈTRES CONFIGURABLES (en tête du script) :
    DICO_PATH        Chemin vers le dictionnaire
    MODELE_PATH      Fichier JSON de sauvegarde (créé automatiquement)
    SEUIL_MIN        Occurrences minimum pour signaler une forme (défaut : 2)
    SEUIL_MAX        Occurrences maximum (défaut : 10)
    LIMITE_EXPORT    Nombre maximum de formes exportées par cycle (défaut : 1000)
    PREFIXE_SORTIE   Préfixe des fichiers corpus corrigés produits
    NB_CYCLES_MAX    Nombre maximum de cycles (défaut : 10)

FICHIERS PRODUITS :
    formes_inconnues_cycle_N.tsv    Formes à valider (cycle N)
    PREFIXE_SORTIE_cycle_N.txt      Corpus après application cycle N
    MODELE_PATH.json                Modèle cumulé (persiste entre sessions)

===============================================================================
"""

import csv
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
import json
from typing import Dict, Set

# =============================================================================
# DÉPENDANCE OPTIONNELLE : langid
# =============================================================================
try:
    import langid
    LANGID_DISPONIBLE = True
except ImportError:
    LANGID_DISPONIBLE = False

# =============================================================================
# PARAMÈTRES CONFIGURABLES
# =============================================================================
# Tous les paramètres ajustables se trouvent ici.
# Ne pas modifier le code en dessous de cette section pour un usage courant.
#
# Structure attendue :
#
#   MonProjet/               ← répertoire de travail, lancer depuis ici
#       10_virgules.py
#       15_decoupage.py
#       16_inconnus.py       ← ce script
#       Lexiq/
#           lefff_formes.txt ← dictionnaire Lefff (110 000 formes fléchies)
#
# Pour utiliser un dictionnaire différent ou situé ailleurs :
#   Modifier DICO_PATH ci-dessous.

# Chemin vers le dictionnaire Lefff
DICO_PATH = Path("Lexiq/lefff_formes.txt")

# Fichier de sauvegarde du modèle d'apprentissage (JSON, créé automatiquement)
# Persiste entre les sessions — conserve les décisions de validation
MODELE_PATH = Path("modele_formes_inconnues.json")

# Seuil minimum d'occurrences pour signaler une forme suspecte
# 1 → tous les hapax remontés (beaucoup de bruit)
# 2 → seulement les erreurs répétées (recommandé)
SEUIL_MIN = 2

# Seuil maximum d'occurrences
# Au-delà, la forme est probablement un terme du domaine, pas une erreur OCR
SEUIL_MAX = 10

# Nombre maximum de formes exportées par cycle pour validation humaine
LIMITE_EXPORT = 1000

# Préfixe des fichiers corpus produits à chaque cycle
PREFIXE_SORTIE = "corpus_inconnus"

# Nombre maximum de cycles avant arrêt automatique
NB_CYCLES_MAX = 10
# =============================================================================

# Chemin vers le fichier de dictionnaire (un mot par ligne, encodage utf-8)
DICO_PATH = Path("Lexiq/lefff_formes.txt")

# Fichier de sauvegarde du modèle d'apprentissage (JSON, créé automatiquement)
MODELE_PATH = Path("modele_formes_inconnues.json")

# Seuil minimum d'occurrences pour signaler une forme suspecte
# Valeur 1 → tous les hapax remontés (beaucoup de bruit)
# Valeur 2 → seulement les erreurs répétées (recommandé)
SEUIL_MIN = 2

# Seuil maximum d'occurrences
# Au-delà, la forme est probablement un terme du domaine ou un nom propre
# récurrent, pas une erreur OCR. Augmenter si le corpus est très spécialisé.
SEUIL_MAX = 10

# Nombre maximum de formes exportées par cycle pour validation humaine
LIMITE_EXPORT = 1000

# Préfixe des fichiers corpus corrigés produits à chaque cycle
# Le cycle N produit : PREFIXE_SORTIE + "_cycle_N.txt"
PREFIXE_SORTIE = "corpus_inconnus"

# Nombre maximum de cycles avant arrêt automatique
NB_CYCLES_MAX = 10

# =============================================================================
# HEURISTIQUES DE REPLI (utilisées si langid n'est pas installé)
# =============================================================================
# Patterns orthographiques caractéristiques des langues non-françaises
# présentes dans ce corpus (allemand, latin, néerlandais, anglais).
# Ces patterns ne remplacent pas langid mais permettent au script de
# fonctionner sans lui, avec une précision légèrement réduite.
# Faux positifs connus : 'gestion' (ge+s+tion) — innocuant car 'gestion'
# est dans le Lefff et filtré avant d'atteindre cette heuristique.

_PATTERNS_NON_FR = [re.compile(p) for p in [
    r'[^aeiouàâéèêëîïôùûü]{4,}',   # 4+ consonnes consécutives
    r'ck\b',                          # -ck final (allemand/anglais)
    r'\bsch',                         # sch- initial (allemand)
    r'oo\b',                          # -oo final
    r'ee\b',                          # -ee final
    r'ij\b',                          # -ij final (néerlandais)
    r'\bth[^éèêëàâîïôùûü]',          # th- non suivi d'une voyelle accentuée
    r'recht\b',                       # -recht final (allemand)
    r'ae\b',                          # -ae final (latin : materiae)
    r'\b\w*atione\b',                 # -atione (ratione, natione — latin)
    r'\b\w*ione\b',                   # -ione final (latin)
    r'\b\w*orum\b',                   # -orum (latin)
    r'\b\w*arum\b',                   # -arum (latin)
    r'\b\w*ibus\b',                   # -ibus (latin)
    r'\b\w*onis\b',                   # -onis (latin)
    r'\b\w{4,}ung\b',                 # -ung avec au moins 4 chars (allemand)
    r'\b\w+keit\b',                   # -keit (allemand)
    r'\b\w+heit\b',                   # -heit (allemand)
    r'\b\w+schaft\b',                 # -schaft (allemand)
    r'\bge[rst][a-z]{4,}\b',          # ge+r/s/t+4chars (Gericht, Gesetz)
]]


def _est_non_fr_heuristique(forme: str) -> bool:
    r"""
    Heuristique de repli quand langid n'est pas disponible.
    Retourne True si la forme ressemble à un mot non-français.
    Conservateur : préférable à un faux positif sur du français.
    """
    fl = forme.lower()
    return any(p.search(fl) for p in _PATTERNS_NON_FR)


def _classifier_langue(texte: str, seuil_score: float = 0.80):
    r"""
    Classifie la langue d'un texte.
    Utilise langid si disponible, heuristique sinon.
    Retourne (langue, fiable) où fiable indique si la détection est sûre.
    """
    if LANGID_DISPONIBLE:
        try:
            lang, score = langid.classify(texte)
            return lang, score > seuil_score
        except Exception:
            pass
    # Repli : tester les heuristiques
    est_non_fr = _est_non_fr_heuristique(texte)
    return ('xx' if est_non_fr else 'fr'), True


# =============================================================================
# CLASSE D'APPRENTISSAGE
# =============================================================================

class ApprentissageFormes:
    r"""
    Mémorise les décisions de l'utilisateur sur les formes inconnues.

    Deux catégories :
    - corrections : dict  "congrés" → "congrès"  (décisions y/ok)
    - ignorer     : set   {"Hautefeuille", "ratione"}  (décisions n/non)

    La persistance est assurée par sauvegarder()/charger() au format JSON.
    Le modèle survit entre les sessions et s'enrichit à chaque cycle.
    """

    def __init__(self):
        self.corrections = {}
        self.ignorer = set()
        self.stats = {'corrections': 0, 'ignores': 0}

    def ajouter_correction(self, forme: str, correction: str):
        self.corrections[forme] = correction
        self.stats['corrections'] += 1

    def ajouter_ignore(self, forme: str):
        self.ignorer.add(forme)
        self.stats['ignores'] += 1

    def charger_fichier_valide(self, chemin: Path):
        r"""
        Charge le fichier TSV de validation humaine.

        Format attendu — colonnes séparées par des tabulations :
            forme | occurences | contexte | decision | correction

        La colonne 'correction' n'est lue que si decision vaut 'y'/'ok'.
        Les lignes avec decision '?' sont ignorées silencieusement.
        Encodage : utf-8-sig (gère le BOM éventuel d'Excel/Numbers).
        """
        n_lues = 0
        with open(chemin, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for ligne in reader:
                n_lues += 1
                forme = ligne['forme'].strip()
                decision = ligne['decision'].strip().lower()
                correction = ligne.get('correction', '').strip()

                if decision in ('y', 'ok'):
                    if correction:
                        self.ajouter_correction(forme, correction)
                    else:
                        print(f"  ⚠️  '{forme}' marqué '{decision}' "
                              f"mais colonne 'correction' vide — ignoré")
                elif decision in ('n', 'non'):
                    self.ajouter_ignore(forme)
                # '?' → ignoré silencieusement
        print(f"   {n_lues} lignes lues depuis {chemin.name}")

    def sauvegarder(self, chemin: Path):
        r"""Sauvegarde le modèle en JSON pour persistance entre sessions."""
        data = {
            'corrections': self.corrections,
            'ignorer': list(self.ignorer),
            'stats': self.stats
        }
        with open(chemin, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def charger(self, chemin: Path):
        r"""Charge le modèle depuis un JSON existant. Ne fait rien si absent."""
        if chemin.exists():
            with open(chemin, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.corrections = data.get('corrections', {})
                self.ignorer = set(data.get('ignorer', []))
                self.stats = data.get('stats', self.stats)
            print(f"   Modèle chargé : "
                  f"{len(self.corrections)} corrections, "
                  f"{len(self.ignorer)} formes ignorées")


# =============================================================================
# CLASSE PRINCIPALE DE DÉTECTION
# =============================================================================

class DetecteurFormesInconnues:
    r"""
    Repère les tokens absents du Lefff apparaissant entre SEUIL_MIN et
    SEUIL_MAX fois dans le corpus, après filtrage des faux suspects.

    Caractères retirés autour des tokens avant analyse (PONCTUATION) :
    La ponctuation attachée aux mots dans un texte OCR varie selon le
    scanner et la page. On nettoie les bords pour normaliser les formes
    avant de les chercher dans le dictionnaire.
    """

    PONCTUATION = str.maketrans(
        '', '',
        ".,;:!?()[]{}«»\"\u2018\u2019'`*_\u2013\u2014\u2026/\\|@#$%^&+=<>~°•·"
    )

    def __init__(self, dictionnaire: Set[str], modele_path: Path = None):
        self.dictionnaire = dictionnaire
        self.apprentissage = ApprentissageFormes()
        if modele_path and modele_path.exists():
            self.apprentissage.charger(modele_path)

    def _nettoyer_token(self, token: str) -> str:
        r"""Retire la ponctuation autour du token."""
        return token.translate(self.PONCTUATION).strip()

    @staticmethod
    def _est_numerique(mot: str) -> bool:
        r"""
        Retourne True si le mot est un nombre, chiffre romain, intervalle,
        ou toute forme numérique non textuelle.
        """
        if mot.isdigit():
            return True
        if re.match(
            r'^(?=[MDCLXVI])M{0,4}(CM|CD|D?C{0,3})'
            r'(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$', mot, re.I
        ):
            return True
        if re.match(r'^\d+([\-\u2013]\d+)*$', mot):
            return True
        if re.match(r'^[a-z]*-?\d+[a-z]*$', mot, re.I):
            return True
        return False

    @staticmethod
    def _est_bruit_structural(mot: str) -> bool:
        r"""Retourne True si le mot ressemble à une URL, un identifiant, etc."""
        if re.search(r'(http|https|ark|www|gallica)', mot, re.I):
            return True
        if '/' in mot:
            return True
        return False

    @staticmethod
    def _est_compose_valide(mot: str, vocab: set) -> bool:
        r"""
        Retourne True si le mot avec tiret est un composé dont les parties
        sont connues du dictionnaire.
        """
        if '-' not in mot:
            return False
        if mot in vocab or mot.replace('-', '') in vocab:
            return True
        return all(p in vocab for p in mot.split('-'))

    @staticmethod
    def _est_apostrophe_valide(mot: str, vocab: set) -> bool:
        r"""
        Retourne True si le mot avec apostrophe a au moins une partie
        connue du dictionnaire (ex : "l'Institut" → "l" connue).
        """
        if "'" not in mot:
            return False
        parts = mot.split("'")
        if len(parts) != 2:
            return False
        return parts[0] in vocab or parts[1] in vocab

    def _est_probablement_nom_propre(self, forme: str,
                                      positions_debut: Set[int],
                                      positions_forme: Set[int]) -> bool:
        r"""
        Heuristique de détection des noms propres.

        Deux critères combinés :
        1. Majuscule hors début de phrase (positionnel)
           Si toutes les occurrences de la forme sont en début de phrase,
           la majuscule est grammaticale → pas un nom propre certain.
           Si au moins la moitié des occurrences sont hors début de phrase
           → probablement un nom propre.

        2. Détection de langue (langid ou heuristique)
           Pour une forme avec majuscule hors début de phrase, on vérifie
           si elle ressemble à un mot non-français. Si oui → nom propre
           étranger (Hautefeuille est français, Gesetzgebung est allemand).

        Note sur la fiabilité :
           langid sur un token isolé de 6-12 chars est peu fiable (score
           souvent bas). On n'utilise la détection de langue qu'en
           complément de l'heuristique positionnelle, jamais seule.
        """
        if not forme or not forme[0].isupper():
            return False

        debuts = positions_forme & positions_debut
        # Toutes les occurrences en début de phrase → peut être un nom commun
        if len(debuts) == len(positions_forme):
            return False

        # Vérifier avec langid ou heuristique si disponible
        if LANGID_DISPONIBLE:
            try:
                lang, score = langid.classify(forme)
                if lang != 'fr' and score > 0.80:
                    return True
            except Exception:
                pass
        else:
            if _est_non_fr_heuristique(forme):
                return True

        # Fallback positionnel : majorité hors début de phrase → nom propre
        return len(debuts) < len(positions_forme) / 2

    def analyser(self, texte: str) -> Dict:
        r"""
        Analyse le texte et retourne les formes inconnues avec leurs stats.

        Pipeline :
        1. Filtrage des paragraphes non-français (langid ou repli)
        2. Tokenisation avec conservation des apostrophes et tirets
        3. Identification des positions de début de phrase
        4. Application des filtres sur chaque token
        5. Comptage et filtrage par seuil + détection noms propres

        Note sur la tokenisation :
            re.findall(r"[\w'][\w'-]{2,}") capture les tokens de 3+ chars
            en préservant les apostrophes intégrées (l'Institut → l'Institut)
            et les tirets (Croix-Rouge → Croix-Rouge).
        """
        # Filtrer les paragraphes non-français
        paragraphes = re.split(r'\n\s*\n+', texte)
        if LANGID_DISPONIBLE:
            texte_fr_paras = [p for p in paragraphes
                              if langid.classify(p)[0] == 'fr']
        else:
            # Repli : conserver tous les paragraphes
            # (le filtrage token par token compensera partiellement)
            texte_fr_paras = paragraphes
        if not texte_fr_paras:
            texte_fr_paras = paragraphes

        # Tokeniser
        tokens_bruts = []
        for para in texte_fr_paras:
            para_norm = unicodedata.normalize("NFC", para)
            para_norm = para_norm.replace("\u2019", "'").replace("\u2018", "'")
            tokens_bruts.extend(re.findall(r"[\w'][\w'-]{2,}", para_norm))

        # Identifier les positions de début de phrase
        positions_debut = {0}
        for i, tok in enumerate(tokens_bruts[1:], 1):
            if tokens_bruts[i - 1].rstrip().endswith(('.', '!', '?')):
                positions_debut.add(i)

        # Compter les formes et leurs positions
        compteur = Counter()
        positions_par_forme: Dict[str, Set[int]] = {}

        for i, tok in enumerate(tokens_bruts):
            raw = unicodedata.normalize("NFC", tok).replace("\u2019", "'").replace("\u2018", "'")
            forme = raw.lower().strip()

            if len(forme) < 4:
                continue
            if forme in self.dictionnaire or raw in self.dictionnaire:
                continue
            if (raw in self.apprentissage.corrections
                    or raw in self.apprentissage.ignorer
                    or forme in self.apprentissage.corrections
                    or forme in self.apprentissage.ignorer):
                continue
            if self._est_numerique(forme):
                continue
            if self._est_bruit_structural(forme):
                continue
            if self._est_compose_valide(forme, self.dictionnaire):
                continue
            if self._est_apostrophe_valide(raw, self.dictionnaire):
                continue

            # Filtre langue (langid ou heuristique)
            if LANGID_DISPONIBLE:
                try:
                    lang, score = langid.classify(forme)
                    langues_etrangeres = {
                        'de', 'nl', 'la', 'en', 'it', 'es', 'pt',
                        'sv', 'da', 'no'
                    }
                    if lang in langues_etrangeres and score > 0.80:
                        continue
                except Exception:
                    pass
            else:
                if _est_non_fr_heuristique(forme):
                    continue

            # Majuscule hors début de phrase → probable nom propre
            if raw[0].isupper() and forme not in self.dictionnaire:
                continue
            # Tout en majuscules → acronyme
            if raw.isupper():
                continue

            compteur[forme] += 1
            positions_par_forme.setdefault(forme, set()).add(i)

        # Filtrer par seuil et noms propres
        resultats = {}
        for forme, count in compteur.items():
            if count < SEUIL_MIN or count > SEUIL_MAX:
                continue
            positions = positions_par_forme[forme]
            if self._est_probablement_nom_propre(forme, positions_debut, positions):
                continue
            premiere_pos = min(positions)
            contexte = ' '.join(
                tokens_bruts[max(0, premiere_pos - 3):premiere_pos + 4]
            )
            resultats[forme] = {'occurences': count, 'contexte': contexte}

        return resultats

    def exporter_pour_validation(self, texte: str, chemin: Path) -> int:
        r"""
        Exporte les formes inconnues en TSV pour validation humaine.

        Colonnes :
            forme       : le token normalisé
            occurences  : nombre d'occurrences dans le corpus
            contexte    : les 3 tokens avant et après la première occurrence
            decision    : pré-rempli à '?' (à compléter par l'utilisateur)
            correction  : vide (à remplir si decision='y'/'ok')

        Tri : par nombre d'occurrences décroissant (les erreurs les plus
        fréquentes en premier — plus rentables à corriger).
        Limite : LIMITE_EXPORT formes maximum (configurable en tête).

        Format TSV (séparateur tabulation) :
            Cohérent avec le script 15. Compatible Numbers et Excel.
            Encodage utf-8-sig (BOM) pour compatibilité Excel Mac/Windows.
        """
        resultats = self.analyser(texte)
        tries = sorted(
            resultats.items(),
            key=lambda x: x[1]['occurences'],
            reverse=True
        )

        chemin_tsv = chemin.with_suffix('.tsv')
        with open(chemin_tsv, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(
                f,
                fieldnames=['forme', 'occurences', 'contexte', 'decision', 'correction'],
                delimiter='\t'
            )
            writer.writeheader()
            for forme, info in tries[:LIMITE_EXPORT]:
                writer.writerow({
                    'forme': forme,
                    'occurences': info['occurences'],
                    'contexte': info['contexte'],
                    'decision': '?',
                    'correction': ''
                })

        n_total = len(tries)
        n_exporte = min(n_total, LIMITE_EXPORT)
        print(f"   {n_exporte} formes exportées dans {chemin_tsv.name}", end='')
        if n_total > LIMITE_EXPORT:
            print(f" (sur {n_total} — augmenter LIMITE_EXPORT si nécessaire)")
        else:
            print()
        return n_total

    def appliquer_corrections(self, texte: str) -> str:
        r"""
        Applique les corrections mémorisées au texte.

        IMPORTANT — préservation des paragraphes :
            On utilise re.sub(r'\S+', fn, texte) au lieu de split()/join().
            split() sans argument détruirait tous les sauts de ligne (\n\n).
            re.sub(r'\S+') ne touche que les séquences de non-espaces et
            laisse intacts tous les espaces et sauts de ligne en place.

        La ponctuation attachée au token est préservée :
            on nettoie la forme pour chercher dans les corrections,
            puis on réapplique la correction sur le token brut (tok.replace).
        """
        if not self.apprentissage.corrections:
            return texte

        corrections = self.apprentissage.corrections

        def traiter_token(match):
            tok = match.group(0)
            forme = self._nettoyer_token(tok).lower()
            if forme in corrections:
                return tok.replace(forme, corrections[forme], 1)
            return tok

        return re.sub(r'\S+', traiter_token, texte)

    def reinjecter_apprentissage(self, fichier_valide: Path):
        r"""Charge le TSV validé et met à jour le modèle."""
        self.apprentissage.charger_fichier_valide(fichier_valide)
        print(f"   Apprentissage mis à jour :")
        print(f"      {self.apprentissage.stats['corrections']} correction(s) enregistrée(s)")
        print(f"      {self.apprentissage.stats['ignores']} forme(s) ignorée(s)")


# =============================================================================
# GESTIONNAIRE DE CYCLES
# =============================================================================

class CycleFormesInconnues:
    r"""
    Orchestre les cycles d'apprentissage : export → validation → réingestion.

    Chaque cycle :
    1. Exporte les formes inconnues en TSV
    2. Attend que l'utilisateur valide le fichier
    3. Réingère les décisions et met à jour le modèle
    4. Sauvegarde le modèle
    5. Applique les corrections au corpus
    6. Écrit le corpus corrigé dans PREFIXE_SORTIE_cycle_N.txt
    7. Demande si l'utilisateur veut continuer
    """

    def __init__(self, corpus_path: Path, dictionnaire: Set[str],
                 modele_path: Path):
        self.corpus_path = corpus_path
        self.detecteur = DetecteurFormesInconnues(dictionnaire, modele_path)
        self.modele_path = modele_path
        self.iteration = 0

    def executer_cycle(self) -> bool:
        r"""
        Exécute un cycle complet. Retourne True si l'utilisateur veut continuer.
        """
        self.iteration += 1
        separateur = '=' * 55
        print(f"\n{separateur}")
        print(f"  CYCLE FORMES INCONNUES #{self.iteration}")
        print(separateur)

        print("\n📖 Chargement du corpus...")
        with open(self.corpus_path, 'r', encoding='utf-8') as f:
            texte = f.read()
        print(f"   {len(texte):,} caractères, "
              f"{texte.count(chr(10) * 2)} paragraphes")

        print("\n🔍 Analyse et export pour validation...")
        fichier_base = Path(f"formes_inconnues_cycle_{self.iteration}")
        nb = self.detecteur.exporter_pour_validation(texte, fichier_base)
        fichier_tsv = fichier_base.with_suffix('.tsv')

        if nb == 0:
            print("   Aucune forme inconnue détectée — cycle terminé.")
            return False

        print(f"\n{'─'*55}")
        print(f"  VEUILLEZ VALIDER : {fichier_tsv}")
        print(f"  Colonne 'decision' :")
        print(f"    y/ok  → erreur, saisir la correction dans 'correction'")
        print(f"    n/non → forme valide (nom propre, terme étranger…)")
        print(f"    ?     → ignoré (reviendra au prochain cycle)")
        print(f"{'─'*55}")
        input("\n  Appuyez sur Entrée une fois la validation terminée...")

        print("\n🔄 Réingestion et apprentissage...")
        self.detecteur.reinjecter_apprentissage(fichier_tsv)

        print("\n💾 Sauvegarde du modèle...")
        self.detecteur.apprentissage.sauvegarder(self.modele_path)
        print(f"   Modèle sauvegardé dans {self.modele_path}")

        print("\n✍️  Application des corrections au corpus...")
        texte_corrige = self.detecteur.appliquer_corrections(texte)
        sortie_path = Path(f"{PREFIXE_SORTIE}_cycle_{self.iteration}.txt")
        with open(sortie_path, 'w', encoding='utf-8') as f:
            f.write(texte_corrige)
        print(f"   Corpus corrigé : {sortie_path}")

        print(f"\n{'─'*55}")
        print(f"  RÉSULTATS DU CYCLE #{self.iteration}")
        print(f"  Corrections enregistrées : {self.detecteur.apprentissage.stats['corrections']}")
        print(f"  Formes ignorées          : {self.detecteur.apprentissage.stats['ignores']}")
        print(f"  Total corrections connus : {len(self.detecteur.apprentissage.corrections)}")
        print(f"  Total formes ignorées    : {len(self.detecteur.apprentissage.ignorer)}")
        print(f"{'─'*55}")

        reponse = input("\n  Continuer avec un nouveau cycle ? (o/n) : ").strip().lower()
        return reponse in ('o', 'oui', 'y', 'yes', '')


# =============================================================================
# POINT D'ENTRÉE
# =============================================================================

if __name__ == "__main__":

    # Signaler la disponibilité de langid
    if LANGID_DISPONIBLE:
        print("ℹ️  langid disponible — détection de langue activée")
    else:
        print("ℹ️  langid non installé — heuristiques de repli activées")
        print("   Pour une meilleure détection : pip install langid")

    # Vérifier le dictionnaire
    if not DICO_PATH.exists():
        print(f"❌ Dictionnaire introuvable : {DICO_PATH}")
        print(f"   Modifier DICO_PATH en tête de script.")
        sys.exit(1)

    print(f"\n📚 Chargement du dictionnaire {DICO_PATH.name}...")
    with open(DICO_PATH, 'r', encoding='utf-8') as f:
        dictionnaire = set(f.read().splitlines())
    print(f"   {len(dictionnaire):,} mots chargés")

    # Corpus
    if len(sys.argv) > 1:
        corpus_path = Path(sys.argv[1])
    else:
        print("Usage : python 16_inconnus.py <corpus.txt>")
        corpus_path = Path("corpus_brut.txt")

    if not corpus_path.exists():
        print(f"❌ Corpus introuvable : {corpus_path}")
        sys.exit(1)

    print(f"\n⚙️  Paramètres :")
    print(f"   Seuil min occurrences : {SEUIL_MIN}")
    print(f"   Seuil max occurrences : {SEUIL_MAX}")
    print(f"   Limite export         : {LIMITE_EXPORT}")

    # Lancer les cycles
    cycle = CycleFormesInconnues(corpus_path, dictionnaire, MODELE_PATH)

    nb_cycles = 0
    continuer = True
    while continuer and nb_cycles < NB_CYCLES_MAX:
        continuer = cycle.executer_cycle()
        nb_cycles += 1

    if nb_cycles >= NB_CYCLES_MAX:
        print(f"\nℹ️  Nombre maximum de cycles atteint ({NB_CYCLES_MAX}).")
        print(f"   Augmenter NB_CYCLES_MAX en tête de script si nécessaire.")
    else:
        print(f"\n✅ Traitement terminé après {nb_cycles} cycle(s).")
        print(f"   Modèle sauvegardé dans : {MODELE_PATH}")
