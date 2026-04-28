# Pipeline de structuration des annuaires juridiques

Documentation du pipeline de traitement pour l'extraction et la structuration
des annuaires de l'Institut de droit international (source : Gallica/BnF).

Ce README couvre la **phase de structuration documentaire** : du fichier texte
brut issu de la numérisation jusqu'au JSON structuré qui segmente le document
en sections exploitables. Les phases suivantes (extraction d'entités nommées,
chargement en base de données, agents de recherche) font l'objet de
documentations séparées.

---

## Table des matières

1. [Contexte et objectif](#1-contexte-et-objectif)
2. [Vue d'ensemble du pipeline](#2-vue-densemble-du-pipeline)
3. [Prérequis](#3-prérequis)
4. [Structure des fichiers](#4-structure-des-fichiers)
5. [Les scripts, un par un](#5-les-scripts-un-par-un)
6. [Lancer le pipeline](#6-lancer-le-pipeline)
7. [Comprendre les fichiers produits](#7-comprendre-les-fichiers-produits)
8. [Adapter à un nouveau volume](#8-adapter-à-un-nouveau-volume)
9. [Questions fréquentes](#9-questions-fréquentes)

---

## 1. Contexte et objectif

### Le corpus

Les annuaires de l'Institut de droit international sont des publications
annuelles parues depuis 1877. Chaque volume contient des documents de natures
très différentes : statuts et règlements de l'Institut, procès-verbaux de
séances, notices biographiques sur les membres, textes de traités
internationaux, bibliographies du droit international.

Ces annuaires ont été numérisés par la Bibliothèque nationale de France et
sont accessibles sur Gallica. Le téléchargement en mode texte produit un
fichier brut qui reconstitue le contenu des pages, mais sans aucune
structuration : tout est du texte continu, avec les seuls repères visuels
que l'OCR a su détecter.

### Ce que fait ce pipeline

Ce pipeline transforme ce texte brut en un ensemble de **sections structurées**,
chacune identifiée par son titre, son niveau hiérarchique dans le document
(partie, section, sous-section...), ses numéros de page de début et de fin,
et son texte brut.

Cette structuration est la fondation de tout ce qui vient ensuite : extraction
d'entités nommées (personnes, lieux, traités...), indexation pour la recherche,
alimentation d'agents capables de répondre à des questions sur le corpus.

### Pourquoi cette approche en scripts séquentiels

Le traitement de ces documents pose des problèmes de natures très différentes.
Certains sont entièrement mécaniques et parfaitement automatisables (détecter
une ligne de tirets, extraire un numéro de page). D'autres nécessitent un
jugement humain ou l'aide d'un modèle de langue (reconstituer un titre coupé
en deux lignes par le scanner, détecter qu'un numéro de page est une erreur
OCR).

Le pipeline est donc découpé en étapes distinctes, chacune faisant une seule
chose, lisant ses données dans un fichier et écrivant son résultat dans un
autre. Cela permet :

- de **rejouer une étape** sans reprendre depuis le début si quelque chose
  se passe mal ;
- d'**inspecter visuellement** ce que chaque transformation a produit avant
  de passer à la suivante ;
- d'**intervenir manuellement** à l'étape qui en a besoin, sans perturber
  les autres ;
- de **tracer l'origine** de chaque erreur jusqu'au script qui l'a produite.

---

## 2. Vue d'ensemble du pipeline

```
fichier texte brut Gallica (original.txt)
          │
          ▼
   t1_extract_toc.py          Extraction et nettoyage de la table des matières
          │
          ▼
   toc_cleaned.txt            [fichier intermédiaire — vérifier avant de continuer]
          │
    correction manuelle       Recoller les titres coupés, séparer les entrées
          │                   compressées, corriger les numéros erronés
          ▼
   t2_llm_verify.py           Vérification par un modèle de langue (LLM)
          │                   Signale les anomalies résiduelles sans corriger
          ▼
   toc_verification.txt       [rapport à lire — corriger si nécessaire]
          │
          ▼
   t3_parse_toc.py            Structuration de la TdM en JSON
          │                   Niveaux hiérarchiques, conversion chiffres romains
          ▼
   toc_final.json             [fichier versionné — résultat de la structuration]
   toc_parse_report.txt       [rapport — entrées non classées à vérifier]
          │
          ▼
   structure_annuaire.py      Segmentation du document en sections
          │                   Chaque section reçoit son texte brut
          ▼
   sections.json              [fichier de sortie principal de cette phase]
```

**Temps estimé par volume** : 30 à 45 minutes, dont 10 à 15 minutes de
correction manuelle de la table des matières.

**Intervention humaine requise** : une seule étape, entre T1 et T2, sur la
table des matières. Toutes les autres étapes sont automatiques.

---

## 3. Prérequis

### Python

Python 3.9 ou supérieur. Vérifier avec :

```bash
python3 --version
```

### Bibliothèques Python

```bash
pip install python-dotenv anthropic openai
```

Si vous utilisez Ollama (modèle local, voir section 5.2) :

```bash
pip install openai   # le client openai sert aussi pour Ollama
```

### Clé API pour T2 (vérification LLM)

T2 fait appel à un modèle de langue. Trois options :

**Option A — Anthropic (recommandé)**
Créer un compte sur https://console.anthropic.com et générer une clé API.

**Option B — OpenAI**
Créer un compte sur https://platform.openai.com et générer une clé API.

**Option C — Ollama (local, gratuit, sans envoi de données)**
Installer Ollama depuis https://ollama.com, puis :
```bash
ollama serve          # lancer le serveur local
ollama pull mistral   # télécharger un modèle (~4 Go)
```

### Fichier de configuration `.env`

Copier le modèle fourni et renseigner vos valeurs :

```bash
cp .env.example .env
```

Ouvrir `.env` dans un éditeur et renseigner :

```
# Choisir le fournisseur : anthropic | openai | ollama
LLM_PROVIDER=anthropic

# Si anthropic :
ANTHROPIC_API_KEY=sk-ant-...

# Si openai :
# OPENAI_API_KEY=sk-...

# Si ollama (laisser les autres vides) :
# OLLAMA_BASE_URL=http://localhost:11434/v1
# OLLAMA_MODEL=mistral
```

> **Important** : ne jamais commiter le fichier `.env` dans git. Il contient
> vos clés d'accès et ne doit rester que sur votre machine. Le fichier
> `.gitignore` fourni l'exclut automatiquement.

---

## 4. Structure des fichiers

### Organisation recommandée

```
projet/
│
├── scripts/                     Scripts Python du pipeline
│   ├── t1_extract_toc.py
│   ├── t2_llm_verify.py
│   ├── t3_parse_toc.py
│   └── structure_annuaire.py
│
├── .env                         Vos clés API (non versionné)
├── .env.example                 Modèle de configuration (versionné)
├── .gitignore                   Exclut .env et les fichiers générés
│
└── corpus/
    └── annuaire_1877/           Un répertoire par volume
        │
        ├── original.txt         Texte brut téléchargé depuis Gallica
        │
        ├── toc_cleaned.txt      Produit par T1 (non versionné)
        ├── toc_verification.txt Produit par T2 (non versionné)
        │
        ├── toc_corrected.txt    Votre correction manuelle (VERSIONNÉ)
        ├── toc_final.json       Produit par T3 (VERSIONNÉ)
        ├── toc_parse_report.txt Rapport de T3 (non versionné)
        │
        └── sections.json        Sortie principale (non versionné,
                                 recalculable depuis toc_final.json)
```

### Quels fichiers versionner dans git ?

Deux fichiers par volume contiennent un travail humain irremplaçable et
doivent être versionnés :

- `toc_corrected.txt` — votre correction manuelle de la table des matières.
  Si vous perdez ce fichier, vous devez recommencer la correction.
- `toc_final.json` — la table des matières structurée. C'est le résultat
  du travail de structuration, la fondation de tout ce qui vient ensuite.

Tous les autres fichiers sont recalculables : si vous les perdez, relancer
le script correspondant suffit à les retrouver.

---

## 5. Les scripts, un par un

### 5.1 `t1_extract_toc.py` — Extraction de la table des matières

**Ce qu'il fait** : localise la table des matières dans le fichier source,
l'extrait, et supprime les artefacts de mise en page produits par
la numérisation (lignes de tirets, répétitions du titre de section en
haut de chaque page numérisée, lignes parasites).

**Ce qu'il ne fait pas** : corriger les titres tronqués, les entrées
compressées sur une ligne, ou les numéros de page erronés. Ces corrections
sont faites manuellement à l'étape suivante.

**Pourquoi une étape séparée ?** La table des matières est critique pour
toute la suite — elle définit comment le document sera découpé. La nettoyer
proprement avant toute transformation automatique évite de propager des
erreurs en cascade.

**Usage** :
```bash
python3 t1_extract_toc.py corpus/annuaire_1877/original.txt
# Produit : corpus/annuaire_1877/toc_cleaned.txt
```

**Après l'exécution** : ouvrir `toc_cleaned.txt` et corriger manuellement :
- Les titres coupés sur deux lignes (les recoller en une seule)
- Les entrées compressées (`"Bernard 146 Besobrasoff 147"` → deux lignes)
- Les numéros de page manifestement erronés
- Les artefacts résiduels à supprimer

Sauvegarder le résultat sous `toc_corrected.txt`.

---

### 5.2 `t2_llm_verify.py` — Vérification par modèle de langue

**Ce qu'il fait** : envoie le texte de la table des matières (corrigée ou
nettoyée) à un modèle de langue qui signale les anomalies probables :
numéros de page incohérents, titres qui semblent tronqués, artefacts OCR
sur les chiffres. Produit un rapport textuel.

**Ce qu'il ne fait pas** : modifier le fichier source. Le modèle signale,
il ne corrige pas. La décision de corriger reste humaine.

**Pourquoi un LLM pour cette étape ?** Un modèle de langue voit des
incohérences que la relecture humaine laisse passer : un numéro de page
"101" quand les voisins sont "161" et "162" (probable OCR de "6" en "0"),
ou un titre qui commence par une minuscule (signe que le début est perdu).
Il n'est pas infaillible, mais il est complémentaire de la relecture humaine.

**Usage** :
```bash
# Sur le fichier corrigé manuellement (recommandé)
python3 t2_llm_verify.py corpus/annuaire_1877/toc_corrected.txt

# Ou sur le fichier nettoyé si vous n'avez pas encore corrigé
python3 t2_llm_verify.py corpus/annuaire_1877/toc_cleaned.txt
```

**Changer de fournisseur LLM** : modifier `LLM_PROVIDER` dans `.env`.
Aucune modification du script nécessaire.

```
LLM_PROVIDER=anthropic   # API Anthropic (payant, très précis)
LLM_PROVIDER=openai      # API OpenAI (payant, bon rapport qualité/coût)
LLM_PROVIDER=ollama      # Modèle local (gratuit, données restent sur machine)
```

**Après l'exécution** : lire `toc_verification.txt`. Pour chaque signalement,
décider si une correction s'impose et l'appliquer dans `toc_corrected.txt`.

---

### 5.3 `t3_parse_toc.py` — Structuration de la table des matières

**Ce qu'il fait** : lit le texte de la table des matières (une entrée par
ligne) et produit un fichier JSON structuré. Pour chaque entrée, il détermine :
- le **niveau hiérarchique** (1 = Partie, 2 = Section principale,
  3 = Sous-section, 4 = Entrée fine) à partir de la forme typographique
  du titre ;
- le **numéro de page**, en convertissant les chiffres romains des pages
  préliminaires en entiers négatifs (« v » → -5, « xiii » → -13) pour
  les distinguer des pages du corps du document ;
- le **titre nettoyé**, sans les points de conduite ni le numéro de page.

Il produit aussi un rapport des entrées qu'il n'a pas su classer et des
anomalies détectées.

**Pourquoi déterministe plutôt qu'un LLM ?** À ce stade, la table des
matières a été nettoyée et corrigée. La grande majorité des entrées suit
des patrons typographiques stables (« I. — Titre », « A. — Titre »,
« Nom (Prénom) »). Un script de règles est plus rapide, plus reproductible,
et plus transparent qu'un LLM — on voit exactement quelle règle a produit
quel résultat.

**Usage** :
```bash
python3 t3_parse_toc.py corpus/annuaire_1877/toc_corrected.txt
# Produit : toc_final.json et toc_parse_report.txt
```

**Après l'exécution** : lire `toc_parse_report.txt`. Les entrées de
niveau 0 (« non classées ») sont celles que le script n'a pas reconnues.
Elles peuvent être corrigées directement dans `toc_final.json` (changer
le champ `"level"`) ou ignorer si elles correspondent à des artefacts
sans importance.

---

### 5.4 `structure_annuaire.py` — Segmentation en sections

**Ce qu'il fait** : lit le fichier source original et `toc_final.json`,
puis assemble le texte de chaque section. Pour chaque entrée de la table
des matières, il collecte les pages correspondantes (du numéro de début
jusqu'au numéro de début de l'entrée suivante moins un) et les concatène
en un bloc de texte brut. Chaque page est marquée `[page N]` pour permettre
des citations précises.

**Usage** :
```bash
python3 structure_annuaire.py corpus/annuaire_1877/original.txt
# Lit aussi : corpus/annuaire_1877/toc_final.json
# Produit   : corpus/annuaire_1877/sections.json
```

**Résultat** : un fichier JSON contenant la liste de toutes les sections
avec leurs métadonnées et leur texte brut, prêt pour les étapes suivantes
(extraction d'entités, résumé, indexation).

---

## 6. Lancer le pipeline

### Étape par étape (recommandé pour un premier volume)

```bash
# 1. Extraire et nettoyer la table des matières
python3 scripts/t1_extract_toc.py corpus/annuaire_1877/original.txt

# 2. Corriger manuellement toc_cleaned.txt
#    Sauvegarder sous toc_corrected.txt
#    (ouvrir dans votre éditeur de texte habituel)

# 3. Vérifier par LLM
python3 scripts/t2_llm_verify.py corpus/annuaire_1877/toc_corrected.txt

# 4. Lire toc_verification.txt, corriger si nécessaire dans toc_corrected.txt

# 5. Structurer la table des matières
python3 scripts/t3_parse_toc.py corpus/annuaire_1877/toc_corrected.txt

# 6. Lire toc_parse_report.txt, corriger les entrées non classées si nécessaire

# 7. Segmenter le document en sections
python3 scripts/structure_annuaire.py corpus/annuaire_1877/original.txt
```

### Vérifier que tout s'est bien passé

```bash
# Nombre de sections produites
python3 -c "
import json
sections = json.load(open('corpus/annuaire_1877/sections.json'))
print(f'{len(sections)} sections')
print(f'Exemple : {sections[5][\"title\"]} (p.{sections[5][\"page_start\"]})')
"
```

### Pour les volumes suivants

Une fois que vous avez traité un premier volume et que les scripts
fonctionnent correctement, les volumes suivants vont plus vite : la
correction manuelle de la table des matières prend 10 à 15 minutes,
et vous connaissez déjà les patrons typographiques de la collection.

---

## 7. Comprendre les fichiers produits

### `toc_cleaned.txt`

Texte brut de la table des matières, débarrassé des artefacts de
numérisation. Une entrée par ligne (ou presque — certains titres longs
sont encore sur deux lignes et nécessitent une correction manuelle).

```
AVANT-PROPOS v

Première Partie.

STATUTS, RÈGLEMENT ET COMPOSITION DES DIVERSES COMMISSIONS D'ÉTUDE. 1

I. — Statuts votés par la conférence juridique internationale de Gand,
le 10 septembre 1873. 1
```

### `toc_final.json`

Liste JSON des entrées de la table des matières, structurées.

```json
[
  {
    "title": "Avant-propos",
    "page": -5,
    "level": 2
  },
  {
    "title": "Première Partie. Statuts, règlement et composition des commissions d'étude",
    "page": 1,
    "level": 1
  },
  {
    "title": "I. — Statuts votés par la conférence juridique internationale de Gand, le 10 septembre 1873",
    "page": 1,
    "level": 2
  },
  {
    "title": "Aschehoug (T.-H.)",
    "page": 143,
    "level": 3
  }
]
```

**Les niveaux** :
- `1` — Partie (« Première Partie », « Deuxième Partie »...)
- `2` — Section principale (numérotée en chiffres romains : I, II, III...)
- `3` — Sous-section (lettre : A, B, C ; chiffre arabe : 1, 2, 3 ;
         nom propre pour les notices biographiques ; mois pour le tableau
         chronologique)
- `4` — Entrée fine (sous-entrées des annexes, sous-mois)
- `0` — Non classé (à vérifier manuellement)

**Les pages négatives** : les pages préliminaires (avant-propos, additions)
sont numérotées en chiffres romains dans les annuaires. Pour les distinguer
des pages du corps du document, elles sont converties en entiers négatifs :
`v` → `-5`, `xiii` → `-13`. Une page à `-5` est donc la page « v ».

### `sections.json`

Liste JSON des sections avec leur texte brut. C'est la sortie principale
de cette phase.

```json
[
  {
    "section_id": "s0001",
    "title": "I. — Statuts votés par la conférence juridique internationale de Gand",
    "level": 2,
    "page_start": 1,
    "page_end": 6,
    "raw_text": "[page 1]\nArticle 1 — L'Institut de droit international est une association...\n\n[page 2]\n..."
  }
]
```

Le marqueur `[page N]` dans le texte brut permet de citer précisément
la page d'origine d'un passage, même après que le texte a été découpé
et réorganisé.

---

## 8. Adapter à un nouveau volume

### Si la table des matières est dans un format différent

Le principal paramètre à adapter dans `t1_extract_toc.py` est le motif
de détection du début de la table des matières. Dans les annuaires Gallica,
la première page de TdM n'est pas numérotée et commence directement par
`TABLE DES MATIERES`. D'autres corpus peuvent avoir des formats différents.

Ouvrir `t1_extract_toc.py` et modifier la section **PARAMÈTRES** en tête
de fichier — chaque paramètre est documenté avec des exemples d'adaptation.

### Si le modèle LLM ne convient pas

Modifier `LLM_PROVIDER` dans `.env`. Aucune modification de code. Si vous
ajoutez un fournisseur non prévu (Mistral, Cohere...), la fonction
`appeler_llm()` dans `t2_llm_verify.py` est documentée pour expliquer
comment ajouter un nouveau bloc.

### Si les niveaux hiérarchiques sont mal détectés

Ouvrir `t3_parse_toc.py` et modifier les expressions régulières dans la
section **PARAMÈTRES**. Chaque expression est documentée avec sa
justification et ses limites.

### Pour un corpus en anglais ou en allemand

Modifier dans `t1_extract_toc.py` :
- `DEBUT_TDM` pour reconnaître « TABLE OF CONTENTS » ou « INHALTSVERZEICHNIS »
- `LIGNES_A_SUPPRIMER` pour adapter les lignes parasites

Dans `t3_parse_toc.py` :
- `MOIS` pour les noms de mois dans la langue du corpus
- `RE_PARTIE` pour les termes désignant les parties

---

## 9. Questions fréquentes

**Le script T1 ne trouve pas la table des matières.**
Vérifier que le fichier source contient bien une ligne commençant par
`TABLE DES MATI` sans numéro devant. Si votre fichier a un format
différent, adapter `DEBUT_TDM` dans la section PARAMÈTRES de T1.

**T2 signale des dizaines d'anomalies.**
C'est normal si la correction manuelle n'a pas encore été faite. Lancer
T2 après avoir corrigé `toc_corrected.txt` réduit considérablement le
nombre de signalements. T2 est conçu pour être conservateur : mieux vaut
sur-signaler que rater une vraie erreur.

**T3 produit beaucoup d'entrées de niveau 0.**
Deux causes possibles : soit le fichier d'entrée contient encore des
titres fragmentés sur plusieurs lignes (correction manuelle à compléter),
soit le corpus a des patrons typographiques non prévus (ajouter une règle
dans `t3_parse_toc.py`). Le rapport `toc_parse_report.txt` liste
exactement les entrées concernées avec leur texte et leur numéro de ligne.

**Le fichier `sections.json` est vide ou incomplet.**
Vérifier que `toc_final.json` existe et est valide (ouvrir dans un
éditeur ou avec `python3 -m json.tool toc_final.json`). Vérifier aussi
que les numéros de page dans `toc_final.json` correspondent à des pages
effectivement présentes dans `original.txt`.

**Peut-on utiliser un modèle Ollama pour toutes les étapes LLM ?**
Oui. Ollama est supporté dans T2. Pour les étapes suivantes du pipeline
(NER, résumés), le même paramètre `LLM_PROVIDER=ollama` dans `.env`
s'appliquera. Les modèles locaux sont un peu moins précis que les modèles
cloud pour les tâches complexes, mais suffisants pour la vérification (T2).

**Combien coûte un appel à l'API Anthropic ou OpenAI pour ce pipeline ?**
T2 envoie la table des matières d'un volume (environ 500 lignes, soit
2 000 à 3 000 tokens) et reçoit un rapport court (moins de 500 tokens).
Le coût est inférieur à 0,01 € par volume avec les tarifs actuels.

---

## Licence et contact

Ce pipeline a été développé dans le cadre d'un projet de recherche sur
les annuaires de l'Institut de droit international. Le code est fourni
sous licence MIT. Pour toute question sur la méthodologie ou l'adaptation
à d'autres corpus juridiques, ouvrir une issue dans le dépôt.
