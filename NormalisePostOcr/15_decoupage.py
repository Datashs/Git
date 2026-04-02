#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
===============================================================================
SCRIPT 15 : DÉCOUPAGE INTELLIGENT DES MOTS COLLÉS
Avec apprentissage cumulatif par renforcement (cas positifs ET négatifs)
===============================================================================

Description :
    Détecte et corrige les mots collés produits par l'OCR ("ledroit" → "le droit")
    grâce à un cycle d'apprentissage supervisé par l'utilisateur.
    Les décisions sont mémorisées dans un fichier JSON et réutilisées
    automatiquement pour tous les corpus (ou fichiers) du même projet.

À qui s'adresse ce script ?
    À toute personne traitant un ensemble de documents OCR de même nature
    (même époque, même source, même domaine). Plus on traite de documents,
    moins il y a de cas à valider manuellement : le modèle s'enrichit à chaque
    corpus traité.

Ce qu'il fait concrètement :
    1. Charge le modèle d'apprentissage existant (s'il y en a un).
    2. Analyse le corpus et propose les découpages douteux non encore connus.
    3. Exporte ces propositions dans un fichier TSV pour validation humaine.
    4. Réingère le fichier validé et mémorise les nouvelles décisions.
    5. Applique tous les découpages connus au corpus et écrit le résultat.
    6. Sauvegarde le modèle mis à jour pour les corpus suivants.
    7. Répéter jusqu'à satisfaction (plusieurs cycles possibles par corpus).

Ce qu'il ne fait pas :
    Il ne prend aucune décision de découpage sans validation humaine préalable.
    Toute nouvelle forme passe par le fichier TSV avant d'être appliquée.

Workflow en cycles :
    1. Le script analyse le corpus et propose des découpages douteux
    2. Il exporte ces propositions dans un fichier TSV
    3. L'utilisateur valide/invalide chaque ligne dans Numbers ou Excel
    4. Le script réingère le fichier validé et mémorise les décisions
    5. Il applique les découpages validés au corpus
    6. Répéter jusqu'à satisfaction
Remarque : Plusieurs cycles sont nécessaires car on ne peut pas traiter tous les cas
    en une seule fois : LIMITE_EXPORT fixe un plafond par cycle pour garder
    la validation humaine gérable.
    Ex : avec LIMITE_EXPORT = 1000 et 2 300 collages détectés,
         il faut au moins 3 cycles pour tous les traiter.

    On continue jusqu'à ce qu'un cycle ne produise plus aucun cas nouveau.

Format du fichier de validation (TSV) :
    Colonnes : mot_colle | suggestion | contexte | decision | correction

    Colonne 'decision' — valeurs acceptées :
      y  ou ok    → découpe correcte, on l'apprend et on l'applique
      n  ou non   → faux positif, ce mot ne sera plus jamais découpé
      c  ou corr  → mot collé mais suggestion incorrecte :
                    saisir la bonne découpe dans la colonne 'correction'
      ?           → ignoré (ni appris ni rejeté, reviendra au prochain cycle)

Workflow Numbers / export TSV :
    Ouvrir le .tsv dans Numbers, remplir la colonne 'decision',
    puis Fichier > Exporter > CSV (renommer en .tsv à l'export).
    IMPORTANT : utiliser "Exporter" et non "Enregistrer", puis ajouter
    l'extension .tsv manuellement pour écraser le fichier d'origine.

Mécanisme d'apprentissage cumulatif :
    - Les décisions 'y'/'ok' sont mémorisées dans MODELE_PATH (JSON)
    - Les décisions 'n'/'non' le sont aussi : le mot n'est plus proposé
    - Les corrections 'c' remplacent la suggestion par la saisie manuelle
    - Le modèle persiste entre les cycles, entre les sessions ET entre les corpus
    - Au fil du temps, de moins en moins de cas remontent à la validation :
      ce qui a déjà été tranché n'est plus soumis à l'utilisateur

    IMPORTANT — un modèle par type de corpus :
      Les erreurs OCR varient selon les sources et les époques. Un corpus de
      presse des années 1950 n'aura pas les mêmes mots collés qu'un corpus
      juridique du XIXe siècle. Utilisez des fichiers de modèle distincts
      pour des corpus de nature différente (voir MODELE_PATH ci-dessous).

Algorithme de découpe :
    Méthode 1 — mot-outil + mot plein :
        Cherche si le début du mot collé est un mot-outil connu (le, la, du…)
        et si le reste existe dans le dictionnaire.
    Méthode 2 — deux mots pleins :
        Cherche une coupure où les deux parties existent dans le dictionnaire.
        Ne s'applique pas si l'une des parties est un mot-outil (trop risqué).

Dépendances :
    - Dictionnaire Lefff (lefff_formes.txt) ou tout fichier un-mot-par-ligne
    - Modules standard : csv, json, re, sys, pathlib, collections, typing

Usage :
    python 15_decoupage.py mon_corpus.txt
    python 15_decoupage.py mon_corpus.txt  (utilise 'corpus_brut.txt' par défaut)

===============================================================================
"""

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path
import json
from typing import List, Set

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
#       15_decoupage.py      ← ce script
#       16_inconnus.py
#       Lexiq/
#           lefff_formes.txt ← dictionnaire Lefff (110 000 formes fléchies)
#
# Pour utiliser un dictionnaire différent ou situé ailleurs :
#   Modifier DICO_PATH ci-dessous.

# Chemin vers le fichier de dictionnaire (un mot par ligne, encodage utf-8)
# Utiliser le Lefff (lefff_formes.txt) ou tout dictionnaire équivalent.
DICO_PATH = Path("Lexiq/lefff_formes.txt")

# Fichier de mémorisation des décisions de découpage (JSON, créé automatiquement)
# Ce fichier est CUMULATIF : il s'enrichit à chaque cycle et à chaque corpus
# traité dans le même projet. Plus vous traitez de documents du même type,
# moins il y a de cas à valider manuellement.
#
# IMPORTANT : si vous travaillez sur des corpus de nature différente
# (ex : textes juridiques ET presse), utilisez des fichiers séparés —
# les erreurs OCR ne sont pas les mêmes d'un type de source à l'autre.
#
# Convention de nommage suggérée :
#   MODELE_PATH = Path("modele_decoupe_juridique.json")
#   MODELE_PATH = Path("modele_decoupe_presse1950.json")
#   MODELE_PATH = Path("modele_decoupe_litterature.json")
MODELE_PATH = Path("modele_decoupe.json")

# Nombre maximum de cycles d'apprentissage avant arrêt automatique
NB_CYCLES_MAX = 10

# Nombre maximum de cas exportés par cycle pour validation humaine
# Augmenter si le corpus est grand et les collages nombreux
LIMITE_EXPORT = 1000

# Préfixe des fichiers de corpus corrigés produits à chaque cycle
# Le cycle N produit : PREFIXE_SORTIE + "_cycle_N.txt"
PREFIXE_SORTIE = "corpus_corrige"

# =============================================================================


# =============================================================================
# CLASSES D'APPRENTISSAGE
# =============================================================================

class ApprentissageDecoupe:
    r"""
    Mémorise les décisions de l'utilisateur sur les découpages.

    Trois catégories :
    - decoupes_valides : dict  "ledroit" → "le droit"  (décisions y/ok/c)
    - non_decoupes     : set   {"ailleurs", "donc"}     (décisions n/non)
    - stats            : compteurs pour le reporting

    La persistance est assurée par sauvegarder()/charger() au format JSON.
    Le modèle survit entre les cycles, entre les sessions et entre les corpus
    d'un même projet : plus on traite de documents, moins il y a de cas
    nouveaux à soumettre à la validation humaine.

    Pour des corpus de nature différente, utiliser des fichiers JSON distincts
    (voir MODELE_PATH en tête de script).
    """

    def __init__(self):
        self.decoupes_valides = {}
        self.non_decoupes = set()
        self.stats = {'positifs': 0, 'negatifs': 0, 'corrections': 0}

    def ajouter_cas_positif(self, mot_colle: str, decoupe: str):
        self.decoupes_valides[mot_colle] = decoupe
        self.stats['positifs'] += 1

    def ajouter_cas_negatif(self, mot: str):
        self.non_decoupes.add(mot)
        self.stats['negatifs'] += 1

    def ajouter_correction(self, mot_colle: str, correction: str):
        self.decoupes_valides[mot_colle] = correction
        self.stats['corrections'] += 1

    def charger_fichier_valide(self, chemin: Path):
        r"""
        Charge le fichier TSV de validation humaine et met à jour le modèle.

        Format attendu — colonnes séparées par des tabulations :
            mot_colle   suggestion   contexte   decision   correction

        La colonne 'correction' n'est lue que si decision vaut 'c'/'corr'.
        Les lignes avec decision '?' sont ignorées sans message.
        """
        n_lues = 0
        with open(chemin, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for ligne in reader:
                n_lues += 1
                mot = ligne['mot_colle'].strip()
                suggestion = ligne['suggestion'].strip()
                decision = ligne['decision'].strip().lower()
                correction = ligne.get('correction', '').strip()

                if decision in ('ok', 'y'):
                    self.ajouter_cas_positif(mot, suggestion)
                elif decision in ('non', 'n'):
                    self.ajouter_cas_negatif(mot)
                elif decision in ('corr', 'c'):
                    if correction:
                        self.ajouter_correction(mot, correction)
                    else:
                        print(f"  ⚠️  '{mot}' marqué '{decision}' "
                              f"mais colonne 'correction' vide — ignoré")
                # '?' → ignoré silencieusement
        print(f"   {n_lues} lignes lues depuis {chemin.name}")

    def sauvegarder(self, chemin: Path):
        r"""
        Sauvegarde le modèle en JSON pour persistance entre sessions.

        Le JSON contient :
          - decoupes_valides : dict str→str
          - non_decoupes     : liste (les sets ne sont pas sérialisables JSON)
          - stats            : compteurs cumulés
        """
        data = {
            'decoupes_valides': self.decoupes_valides,
            'non_decoupes': list(self.non_decoupes),
            'stats': self.stats
        }
        with open(chemin, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def charger(self, chemin: Path):
        r"""
        Charge le modèle depuis un JSON existant.
        Ne fait rien si le fichier n'existe pas (premier lancement).

        À chaque nouveau corpus du même projet, ce chargement réinjecte
        automatiquement toutes les décisions déjà validées : les mots collés
        connus sont appliqués sans passer par la validation humaine, et les
        faux positifs connus ne sont plus proposés.
        """
        if chemin.exists():
            with open(chemin, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.decoupes_valides = data.get('decoupes_valides', {})
                self.non_decoupes = set(data.get('non_decoupes', []))
                self.stats = data.get('stats', self.stats)
            print(f"   Modèle chargé : "
                  f"{len(self.decoupes_valides)} découpages, "
                  f"{len(self.non_decoupes)} non-découpages")


# =============================================================================
# CLASSE PRINCIPALE DE DÉCOUPE
# =============================================================================

class DecoupeurIntelligent:
    r"""
    Propose et applique les découpages de mots collés.

    La LISTE_NOIRE contient les mots qui ne doivent jamais être découpés,
    même s'ils contiennent des séquences qui ressemblent à un collage.
    Ex : "ailleurs" commence par "ail" (mot du dictionnaire) mais ce n'est
    pas "ail" + "leurs" — c'est un mot à part entière.

    Note sur les accents dans LISTE_NOIRE :
        Les mots y sont en minuscules sans accent (ex: 'apres', 'desir').
        Les mots accentués ('après', 'désir') sont protégés en amont par
        la vérification dictionnaire — s'ils y sont, ils ne sont pas candidats.
        La LISTE_NOIRE ne concerne que les mots potentiellement absents du dico.
    """

    LISTE_NOIRE = {
        'cette', 'celui', 'celle', 'celles', 'ceux',
        'lequel', 'laquelle', 'lesquels', 'lesquelles',
        'duquel', 'dequel', 'auquel', 'auxquels', 'auxquelles',
        'desquels', 'desquelles',
        'dessus', 'dessous', 'dedans', 'dehors', 'depuis', 'durant',
        'encore', 'entre', 'autre', 'autres',
        'comme', 'moins', 'certes', 'ainsi', 'aussi', 'avant', 'apres',
        'alors', 'donc', 'ailleurs', 'lorsque', 'puisque',
        'partout', 'surtout', 'seulement', 'souvent', 'toujours',
        'parfois', 'jamais', 'ensemble', 'autour', 'autant', 'ensuite',
        'envers', 'environ', 'pourtant', 'pendant', 'suivant',
        'mesure', 'devenir', 'devenu', 'devient', 'devoir',
        'cesser', 'cesse', 'mettre', 'partir', 'nature',
        'parler', 'parole', 'partie', 'pareil', 'parmi',
        'monter', 'montrer', 'moteur', 'mourir', 'mouvement',
        'vouloir', 'valeur', 'venir', 'vendre',
        'detail', 'destin', 'desir', 'dessert', 'demander',
        'session', 'parcourir', 'parcourront',
    }

    def __init__(self, dictionnaire: Set[str], modele_path: Path = None):
        self.dictionnaire = dictionnaire
        self.apprentissage = ApprentissageDecoupe()
        self.mots_outils = {
            'le', 'la', 'les', 'du', 'de', 'des', 'un', 'une', 'et', 'ou',
            'au', 'aux', 'en', 'dans', 'par', 'pour', 'sur', 'avec',
            'ce', 'cet', 'ces', 'mon', 'ton', 'son',
            'mes', 'tes', 'ses', 'nos', 'vos',
        }
        self.patterns_refuses = defaultdict(int)
        if modele_path and modele_path.exists():
            self.apprentissage.charger(modele_path)

    def doit_on_decouper(self, mot: str, suggestion: str) -> bool:
        r"""
        Décide si un collage candidat doit être découpé.

        Ordre de priorité des vérifications :
        1. LISTE_NOIRE globale → non
        2. Déjà validé positivement (apprentissage) → oui
        3. Déjà validé négativement (apprentissage) → non
        4. La suggestion ne fait pas exactement 2 parties → non
        5. Longueur minimale des parties (évite les découpages triviaux)
        6. Les deux parties existent dans le dictionnaire/mots-outils
        7. Faux amis connus (ailleurs = ail+leurs) → non
        8. Le collage reconstruit donne bien le mot original → oui
        """
        if mot in self.LISTE_NOIRE:
            return False
        if mot in self.apprentissage.decoupes_valides:
            return True
        if mot in self.apprentissage.non_decoupes:
            return False

        parties = suggestion.split()
        if len(parties) != 2:
            return False
        mot1, mot2 = parties

        # Longueur minimale selon la nature de mot1
        prepositions_courtes = {'de', 'du', 'au', 'en', 'ou', 'sur', 'par', 'les', 'des', 'aux',
                                     'le', 'la', 'et', 'un', 'ce'}
        if mot1 in prepositions_courtes:
            if len(mot2) < 3:
                return False
        elif len(mot1) < 3 or len(mot2) < 3:
            return False

        # Les deux parties doivent être connues
        if mot1 not in self.dictionnaire and mot1 not in self.mots_outils:
            return False
        if mot2 not in self.dictionnaire:
            return False

        # Faux amis : séquences qui ressemblent à un collage mais n'en sont pas
        faux_amis = [
            ('ail', 'leurs'),   # ailleurs
            ('don', 'c'),       # donc
            ('lors', 'que'),    # lorsque
            ('puis', 'que'),    # puisque
        ]
        if (mot1, mot2) in faux_amis:
            return False

        # Vérification de cohérence : la concaténation doit redonner le mot
        if mot != mot1 + mot2:
            return False

        return True

    def proposer_decoupes(self, mot: str) -> List[str]:
        r"""
        Génère les découpages candidats pour un mot.

        Retourne une liste vide si :
        - Le mot est trop court (< 5 caractères)
        - Le mot est dans le dictionnaire (déjà un vrai mot)
        - Le mot est dans la LISTE_NOIRE

        Méthode 1 (mot-outil + mot plein) :
            Teste si le début du mot correspond à un mot-outil connu,
            et si le reste existe dans le dictionnaire.
            Ex : "ledroit" → "le" + "droit" ✅

        Méthode 2 (deux mots pleins) :
            Cherche toutes les coupures possibles où les deux parties
            sont dans le dictionnaire et ne sont pas des mots-outils.
            La boucle commence à 3 (évite les coupures trop courtes)
            et s'arrête à len-2 (idem de l'autre côté).
            Ex : "droitinternational" → "droit" + "international" ✅
        """
        if len(mot) < 5:
            return []
        if mot in self.dictionnaire or mot.lower() in self.dictionnaire:
            return []
        if mot in self.LISTE_NOIRE:
            return []

        commence_par_majuscule = mot[0].isupper()
        propositions = []

        # Méthode 1 : mot-outil + mot plein
        for outil in self.mots_outils:
            if mot.lower().startswith(outil) and len(mot) > len(outil):
                reste = mot[len(outil):]
                if reste.lower() in self.dictionnaire:
                    suggestion = f"{mot[:len(outil)]} {mot[len(outil):]}"
                    if self.doit_on_decouper(mot, suggestion):
                        propositions.append(suggestion)

        # Méthode 2 : deux mots pleins
        mot_lower = mot.lower()
        for i in range(3, len(mot_lower) - 2):
            partie1 = mot_lower[:i]
            partie2 = mot_lower[i:]
            if (partie1 in self.dictionnaire and
                    partie2 in self.dictionnaire and
                    partie1 not in self.mots_outils):
                # Majuscule + partie courte → trop risqué
                if commence_par_majuscule and (len(partie1) < 4 or len(partie2) < 4):
                    continue
                suggestion = f"{mot[:i]} {mot[i:]}"
                if suggestion not in propositions:
                    propositions.append(suggestion)

        return propositions[:5]

    def appliquer_decoupes(self, texte: str) -> str:
        r"""
        Applique les découpages mémorisés au texte entier.

        IMPORTANT — preservation des paragraphes :
            On utilise re.sub(r'\S+', fn, texte) au lieu de split()/join().
            split() sans argument coupe sur tout espace blanc y compris \n\n,
            et join(' ') détruirait tous les sauts de ligne (paragraphes aplatis).
            re.sub(r'\S+') ne touche que les séquences de non-espaces et laisse
            intacts tous les caractères d'espacement à leur position originale.

        Ordre de traitement pour chaque token :
        1. Dans decoupes_valides → appliquer la découpe mémorisée
        2. Dans le dictionnaire → laisser intact
        3. Dans non_decoupes → laisser intact
        4. Sinon → proposer une découpe et l'appliquer si trouvée
        """
        apprentissage = self.apprentissage

        def traiter_token(match):
            mot = match.group(0)
            if mot in apprentissage.decoupes_valides:
                return apprentissage.decoupes_valides[mot]
            if mot in self.dictionnaire or mot.lower() in self.dictionnaire:
                return mot
            if len(mot) < 5:
                return mot
            if mot in apprentissage.non_decoupes:
                return mot
            propositions = self.proposer_decoupes(mot)
            return propositions[0] if propositions else mot

        # \S+ matche chaque token sans toucher aux espaces/sauts de ligne
        return re.sub(r'\S+', traiter_token, texte)

    def exporter_pour_validation(self, texte: str, chemin: Path):
        r"""
        Exporte les cas douteux en TSV pour validation humaine.

        Colonnes exportées :
            mot_colle   : le token tel qu'il apparaît dans le texte
            suggestion  : la découpe proposée ("le droit")
            contexte    : les 3 tokens avant et après pour aide à la décision
            decision    : pré-rempli à '?' (à compléter par l'utilisateur)
            correction  : vide (à remplir si decision='c')

        Limite : LIMITE_EXPORT cases maximum par cycle (configurable en tête).
        Les cas déjà validés (positifs ou négatifs) sont ignorés.

        Note sur le contexte :
            Extrait par split() pour avoir les tokens voisins.
            Le texte entier n'est pas réécrit — seul le contexte local
            est affecté par cette extraction (acceptable pour la validation).
        """
        # Pour le contexte seulement, split() est acceptable
        mots = texte.split()
        cas_a_valider = []
        deja_vus = set()

        for i, mot in enumerate(mots):
            if mot in self.apprentissage.decoupes_valides:
                continue
            if mot in self.apprentissage.non_decoupes:
                continue
            propositions = self.proposer_decoupes(mot)
            if propositions:
                contexte = ' '.join(mots[max(0, i - 3):i + 4])
                for prop in propositions:
                    cle = (mot, prop)
                    if cle not in deja_vus:
                        deja_vus.add(cle)
                        cas_a_valider.append({
                            'mot_colle': mot,
                            'suggestion': prop,
                            'contexte': contexte,
                            'decision': '?',
                            'correction': ''
                        })

        chemin_tsv = chemin.with_suffix('.tsv')
        with open(chemin_tsv, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(
                f,
                fieldnames=['mot_colle', 'suggestion', 'contexte', 'decision', 'correction'],
                delimiter='\t'
            )
            writer.writeheader()
            writer.writerows(cas_a_valider[:LIMITE_EXPORT])

        n_total = len(cas_a_valider)
        n_exporte = min(n_total, LIMITE_EXPORT)
        print(f"   {n_exporte} cas exportés dans {chemin_tsv.name}", end='')
        if n_total > LIMITE_EXPORT:
            print(f" (sur {n_total} — augmenter LIMITE_EXPORT si nécessaire)")
        else:
            print()

    def reinjecter_apprentissage(self, fichier_valide: Path):
        r"""
        Charge le fichier TSV validé et met à jour le modèle d'apprentissage.
        Appelle aussi _analyser_patterns_refus() pour détecter des tendances.
        """
        self.apprentissage.charger_fichier_valide(fichier_valide)
        self._analyser_patterns_refus()
        print(f"   Apprentissage mis à jour :")
        print(f"      {self.apprentissage.stats['positifs']} découpe(s) validée(s)")
        print(f"      {self.apprentissage.stats['negatifs']} non-découpage(s) enregistré(s)")
        print(f"      {self.apprentissage.stats['corrections']} correction(s) manuelle(s)")

    def _analyser_patterns_refus(self):
        r"""
        Détecte des tendances dans les refus pour information.
        Ex : si beaucoup de mots en '-eurs' sont refusés, c'est un pattern.
        (Utilisé pour le reporting — n'affecte pas le comportement.)
        """
        for mot in self.apprentissage.non_decoupes:
            if mot.endswith('eurs'):
                self.patterns_refuses['*eurs'] += 1
            if mot.endswith('onc'):
                self.patterns_refuses['*onc'] += 1


# =============================================================================
# GESTIONNAIRE DE CYCLES
# =============================================================================

class CycleApprentissageDecoupe:
    r"""
    Orchestre les cycles d'apprentissage : export → validation → réingestion.

    Chaque cycle :
    1. Exporte les cas douteux en TSV
    2. Attend que l'utilisateur valide le fichier
    3. Réingère les décisions et met à jour le modèle
    4. Sauvegarde le modèle
    5. Applique les découpages connus au corpus
    6. Écrit le corpus corrigé dans PREFIXE_SORTIE_cycle_N.txt
    7. Demande si l'utilisateur veut continuer
    """

    def __init__(self, corpus_path: Path, dictionnaire: Set[str], modele_path: Path):
        self.corpus_path = corpus_path
        self.decoupeur = DecoupeurIntelligent(dictionnaire, modele_path)
        self.modele_path = modele_path
        self.iteration = 0

    def executer_cycle(self) -> bool:
        r"""
        Exécute un cycle complet. Retourne True si l'utilisateur veut continuer.
        """
        self.iteration += 1
        separateur = '=' * 55
        print(f"\n{separateur}")
        print(f"  CYCLE D'APPRENTISSAGE #{self.iteration}")
        print(separateur)

        print("\n📖 Chargement du corpus...")
        with open(self.corpus_path, 'r', encoding='utf-8') as f:
            texte = f.read()
        print(f"   {len(texte):,} caractères, "
              f"{texte.count(chr(10)*2)} paragraphes")

        print("\n📤 Export pour validation humaine...")
        fichier_base = Path(f"validation_decoupe_cycle_{self.iteration}")
        self.decoupeur.exporter_pour_validation(texte, fichier_base)
        fichier_tsv = fichier_base.with_suffix('.tsv')

        print(f"\n{'─'*55}")
        print(f"  VEUILLEZ VALIDER : {fichier_tsv}")
        print(f"  Colonne 'decision' : y(oui) / n(non) / c(correction) / ?")
        print(f"  Si 'c' : saisir la bonne découpe dans 'correction'")
        print(f"{'─'*55}")
        input("\n  Appuyez sur Entrée une fois la validation terminée...")

        print("\n🔄 Réingestion et apprentissage...")
        self.decoupeur.reinjecter_apprentissage(fichier_tsv)

        print("\n💾 Sauvegarde du modèle...")
        self.decoupeur.apprentissage.sauvegarder(self.modele_path)
        print(f"   Modèle sauvegardé dans {self.modele_path}")

        print("\n✍️  Application des découpages au corpus...")
        texte_corrige = self.decoupeur.appliquer_decoupes(texte)
        sortie_path = Path(f"{PREFIXE_SORTIE}_cycle_{self.iteration}.txt")
        with open(sortie_path, 'w', encoding='utf-8') as f:
            f.write(texte_corrige)
        print(f"   Corpus corrigé : {sortie_path}")

        print(f"\n{'─'*55}")
        print(f"  RÉSULTATS DU CYCLE #{self.iteration}")
        print(f"  Découpes validées     : {self.decoupeur.apprentissage.stats['positifs']}")
        print(f"  Corrections manuelles : {self.decoupeur.apprentissage.stats['corrections']}")
        print(f"  Non-découpages        : {self.decoupeur.apprentissage.stats['negatifs']}")
        print(f"  Total découpes connus : {len(self.decoupeur.apprentissage.decoupes_valides)}")
        print(f"  Total non-découpages  : {len(self.decoupeur.apprentissage.non_decoupes)}")
        print(f"{'─'*55}")

        # Demander si l'utilisateur veut continuer
        reponse = input("\n  Continuer avec un nouveau cycle ? (o/n) : ").strip().lower()
        return reponse in ('o', 'oui', 'y', 'yes', '')


# =============================================================================
# POINT D'ENTRÉE
# =============================================================================

if __name__ == "__main__":

    # Vérifier le dictionnaire
    if not DICO_PATH.exists():
        print(f"❌ Dictionnaire introuvable : {DICO_PATH}")
        print(f"   Modifier DICO_PATH en tête de script.")
        sys.exit(1)

    print(f"📚 Chargement du dictionnaire {DICO_PATH.name}...")
    with open(DICO_PATH, 'r', encoding='utf-8') as f:
        dictionnaire = set(f.read().splitlines())
    print(f"   {len(dictionnaire):,} mots chargés")

    # Corpus : argument de ligne de commande ou nom par défaut
    if len(sys.argv) > 1:
        corpus_path = Path(sys.argv[1])
    else:
        print("Usage : python 15_decoupage.py <corpus.txt>")
        print("        python 15_decoupage.py  (utilise 'corpus_brut.txt')")
        corpus_path = Path("corpus_brut.txt")

    if not corpus_path.exists():
        print(f"❌ Corpus introuvable : {corpus_path}")
        sys.exit(1)

    # Lancer les cycles
    cycle = CycleApprentissageDecoupe(corpus_path, dictionnaire, MODELE_PATH)

    nb_cycles = 0
    continuer = True
    while continuer and nb_cycles < NB_CYCLES_MAX:
        continuer = cycle.executer_cycle()
        nb_cycles += 1

    if nb_cycles >= NB_CYCLES_MAX:
        print(f"\nℹ️  Nombre maximum de cycles atteint ({NB_CYCLES_MAX}).")
        print(f"   Augmenter NB_CYCLES_MAX en tête de script si nécessaire.")
    else:
        print(f"\n✅ Apprentissage terminé après {nb_cycles} cycle(s).")
        print(f"   Modèle sauvegardé dans : {MODELE_PATH}")
        print(f"   Ce modèle sera réutilisé automatiquement pour les prochains")
        print(f"   corpus du même projet — les décisions déjà validées ne")
        print(f"   remonteront plus à la validation humaine.")
