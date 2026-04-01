# Pipeline post-OCR pour corpus historiques Gallica

Scripts de normalisation textuelle pour corpus numérisés par Gallica (XIXe siècle).  
Développés sur l'*Annuaire de l'Institut de droit international* (1877), généralisables à tout corpus OCR similaire.

---

## Pourquoi ces scripts

Les textes récupérés sur Gallica au format texte brut sont souvent inutilisables directement pour l'analyse. L'OCR produit des erreurs systématiques et prévisibles : apostrophes non standard, tirets typographiques variés, ordinaux mal formés, ligatures manquantes, ponctuations collées, guillemets parasites, chiffres romains déformés. Sur un corpus de 116 000 mots, ces erreurs représentent plusieurs milliers de corrections à apporter.

On pourrait confier ce nettoyage à un grand modèle de langage. On ne le fait pas. Voici pourquoi.

**Ce que fait un LLM** : il produit un résultat visuellement convaincant en faisant des choix dont la logique est opaque. On ne sait pas exactement ce qu'il a changé, pourquoi, ni s'il a introduit des erreurs en corrigeant d'autres. Sur un corpus destiné à la recherche, c'est inacceptable.

**Ce que font ces scripts** : chacun fait une chose précise, documentée, vérifiable. Chaque règle a été testée sur le corpus réel. Les faux positifs ont été comptés et documentés dans le code. Les règles trop dangereuses ont été supprimées avec explication. Le résultat est reproductible et auditable — on peut retracer chaque modification.

C'est ce qu'on pourrait appeler une **philologie computationnelle explicite** : les opérations sont visibles, les décisions sont justifiées, les limites sont nommées.

Cette démarche a aussi une dimension pédagogique explicite. Ces scripts sont conçus pour être lus autant que pour être utilisés. Chaque règle conservée dans le code est documentée — avec les cas qu'elle traite, les cas qu'elle ne traite pas, et les raisons pour lesquelles certaines règles initialement envisagées ont été abandonnées. Un étudiant ou un thésard en histoire qui ouvre `08_abrev.py` trouvera non seulement le code, mais l'explication de pourquoi `par` → `par.` a été supprimé (927 faux positifs, 0 vrai positif sur le corpus de test), pourquoi `cl` n'est pas traité comme une abréviation (c'est une erreur OCR pour `et` dans ce corpus), et ce que cela implique pour les décisions à prendre sur un autre corpus.

L'enjeu n'est pas d'apprendre Python. C'est d'apprendre à **travailler son matériau** — à ne pas déléguer les choix techniques à un outil dont on ne comprend pas les décisions, à documenter ce qu'on a fait et pourquoi, à distinguer ce qu'on sait de ce qu'on suppose. Ce sont les mêmes exigences que la critique des sources, appliquées à l'outillage numérique.

Cette approche s'inscrit dans une réflexion plus large sur ce que devrait être la formation des historiens à l'ère des grands modèles de langage. La tentation est forte de confier le nettoyage, l'extraction, l'analyse à des outils puissants et accessibles — et les résultats sont souvent visuellement convaincants. Mais un résultat convaincant n'est pas un résultat contrôlé. Sur un corpus destiné à la recherche, la différence est essentielle : ce qu'on ne peut pas expliquer, on ne peut pas publier.

---

## Ce que le pipeline ne prétend pas faire

- Corriger toutes les erreurs OCR — seulement celles qui sont systématiques et prévisibles
- Remplacer la relecture humaine
- Fonctionner sans ajustement sur n'importe quel corpus XIXe

Les scripts 15 et 16 intègrent une validation humaine obligatoire à chaque cycle. Ce n'est pas un défaut de conception — c'est le moment où le jugement disciplinaire de l'historien entre dans la boucle, là où aucun outil ne peut le remplacer.

---

## Structure du projet

```
PostOCR/
    scripts/                      ← répertoire de travail, lancer depuis ici
        02apost.py
        03Tirets.py
        04_controle.py
        05_espaces.py
        06_ordinaux.py
        07_mois.py
        08_abrev.py
        09_ponctuation.py
        10_virgules.py
        11_romains.py
        12_refs.py
        13_guillemets.py
        14_ligatures.py
        15_decoupage.py
        16_inconnus.py
        postocr.py                ← pipeline complet (scripts 02-14)
        test_pipeline.py          ← test de régression sur corpus synthétique
        test_corpus.py            ← audit sur un corpus utilisateur
        Lexiq/
            lefff_formes.txt      ← dictionnaire Lefff (à télécharger séparément)
    corpus/
        raw/                      ← fichiers OCR Gallica bruts
            1877_jette.txt
            1878_xxx.txt
        processed/                ← sorties du pipeline
            1877_jette_postocr.txt
        rapports/                 ← rapports de modifications (.md)
    modeles/                      ← modèles d'apprentissage scripts 15 et 16
        modele_decoupe.json
        modele_formes_inconnues.json
```

**Convention de nommage** : `AAAA_nom.txt` pour les fichiers corpus (ex : `1877_jette.txt`).

---

## Dépendances

Python 3.8 ou supérieur. Aucune bibliothèque externe pour les scripts 02 à 14 — stdlib uniquement.

Les scripts 10, 15 et 16 nécessitent le **dictionnaire Lefff** (Lexique des Formes Fléchies du Français, environ 110 000 entrées). À télécharger séparément et placer dans `scripts/Lexiq/lefff_formes.txt`.

Les scripts 15 et 16 acceptent optionnellement **langid** pour la détection de langue sur les corpus multilingues :

```bash
pip install langid
```

Si langid n'est pas installé, les scripts fonctionnent avec des heuristiques de repli.

---

## Mode d'emploi

### Étape 1 — Tester que tout fonctionne

Depuis le répertoire `scripts/` :

```bash
python test_pipeline.py
```

Ce script applique les 12 scripts automatiques sur un corpus synthétique intégré et vérifie les résultats. Il doit afficher `12 scripts OK` sans erreur. Aucun fichier externe requis.

### Étape 2 — Auditer le pipeline sur votre corpus

```bash
python test_corpus.py ../corpus/raw/1877_jette.txt
```

Mode robustesse uniquement : vérifie que chaque script tourne sans erreur et que les paragraphes sont préservés. Pour voir le détail des corrections :

```bash
python test_corpus.py ../corpus/raw/1877_jette.txt --audit
python test_corpus.py ../corpus/raw/1877_jette.txt --audit --max 30
```

`--max N` limite à N exemples affichés par script. Utile pour inspecter les corrections avant de valider le traitement.

### Étape 3 — Lancer le pipeline complet

```bash
python postocr.py ../corpus/raw/1877_jette.txt
```

Produit automatiquement :
- `../corpus/processed/1877_jette_postocr.txt` — texte normalisé
- `../corpus/rapports/1877_jette_postocr.md` — rapport des modifications

Avec le rapport détaillé :

```bash
python postocr.py ../corpus/raw/1877_jette.txt --rapport --max 20
```

### Étape 4 — Mots collés (cycle interactif)

Le script 15 détecte les mots fusionnés par l'OCR (`ledroit` → `le droit`) et propose des découpages à valider.

```bash
python 15_decoupage.py ../corpus/processed/1877_jette_postocr.txt
```

Le script exporte un fichier TSV à valider dans Numbers ou Excel :
- `y` — découpe correcte
- `n` — faux positif, ne plus proposer ce mot
- `c` — découpe incorrecte, saisir la bonne dans la colonne `correction`
- `?` — incertain, reviendra au cycle suivant

Appuyer sur Entrée une fois le fichier validé. Répéter jusqu'à satisfaction. Le modèle d'apprentissage est sauvegardé dans `modeles/modele_decoupe.json` et persiste entre les sessions.

### Étape 5 — Formes inconnues (cycle interactif)

Le script 16 détecte les tokens absents du Lefff qui apparaissent plusieurs fois — probablement des erreurs OCR systématiques (`congrés` → `congrès`).

```bash
python 16_inconnus.py ../corpus/processed/1877_jette_postocr.txt
```

Même logique de validation que le script 15. Pour chaque forme marquée `y`, saisir la correction dans la colonne `correction`.

---

## Description des scripts

| Script | Fonction | Corrections sur jette (1877) | Faux positifs |
|--------|----------|:---:|:---:|
| `02apost.py` | Apostrophes non standard → U+0027 | 0 | 0 |
| `03Tirets.py` | Tirets U+2013/2014/2212 → tiret ASCII | 2 841 | 0 |
| `04_controle.py` | Caractères de contrôle, BOM | 1 | 0 |
| `05_espaces.py` | Espaces multiples et spéciaux | 0 | 0 |
| `06_ordinaux.py` | 1ere→1re, 2me→2e, 3me→3e… | 285 | 0 |
| `07_mois.py` | Mois avec majuscule → minuscule | 107 | 0 |
| `08_abrev.py` | M→M., Dr→Dr., pp→pp., etc. | 113 | 0 |
| `09_ponctuation.py` | Espaces autour de :;!? | 1 217 | 0 |
| `10_virgules.py` | Virgules collées (filtre Lefff) | ~45 | 0 |
| `11_romains.py` | Vil→VII, T. Il→T. II, T. Vit→T. VII | 12 | 0 |
| `12_refs.py` | T.VI→T. VI, pp.N→pp. N, et ss,→et ss. | 34 | 0 |
| `13_guillemets.py` | Guillemets droits parasites OCR | 36 | 0 |
| `14_ligatures.py` | oeuvre→œuvre, voeu→vœu, coeur→cœur | 79 | 0 |
| `15_decoupage.py` | Mots collés — cycle interactif | variable | ~25% |
| `16_inconnus.py` | Formes inconnues — cycle interactif | variable | variable |

**Script 10** : nécessite le Lefff. Sans le dictionnaire, retourne le texte inchangé avec un avertissement.

**Scripts 15 et 16** : les faux positifs sont gérés par la validation humaine — le modèle apprend à ne plus les proposer.

---

## Choix techniques

### Pourquoi pas de règle générale pour la virgule (script 09)

Le script 09 traite les ponctuations doubles (`:;!?`) qui ont des règles typographiques uniformes en français. La virgule a été volontairement exclue : ses exceptions sont trop nombreuses (nombres décimaux, abréviations, listes bibliographiques). Le script 10 traite séparément le cas `mot,mot` avec le filtre Lefff comme garde-fou.

### Pourquoi le Lefff plutôt qu'un modèle de langue

Le Lefff est un lexique de référence : chaque entrée a été vérifiée. Il ne fait pas de généralisation probabiliste. Sur un corpus du XIXe siècle avec des noms propres étrangers (Rolin-Jaequemyns, Holtzendorff, Mancini), un modèle de langue ferait des suppositions difficiles à contrôler. Le Lefff dit exactement ce qu'il sait et rien d'autre.

### Pourquoi les modèles JSON sont cumulatifs (scripts 15 et 16)

Sur quarante annuaires similaires, les erreurs OCR sont souvent les mêmes d'un volume à l'autre. Un modèle cumulatif signifie que les décisions prises sur l'annuaire 1877 s'appliquent automatiquement sur les suivants — sans revalider ce qu'on a déjà traité.

### Ce qui a été exclu et pourquoi

- **Script 10 original (points de suspension)** : exclu définitivement — les points de conduite dans les tableaux et tables des matières seraient détruits.
- **Ligature æ** : désactivée — tous les `ae` du corpus sont des noms propres flamands (Jaequemyns ×40).
- **`par` → `par.`** comme abréviation : 927 faux positifs sur le corpus de test, 0 vrai positif. Supprimé.
- **Correction des coupures de mots en fin de ligne** : nécessite une validation humaine ligne par ligne — trop hétérogène pour être automatisé de façon sûre.

---

## Paramètres configurables

Chaque script expose ses paramètres ajustables en tête de fichier, avant tout le code. Les principaux :

**`06_ordinaux.py`** — `roman=False` par défaut : les ordinaux romains (XIXme) ne sont pas corrigés sans activer explicitement ce mode.

**`10_virgules.py`** — `MIN_LONGUEUR = 2` : longueur minimale des tokens traités. Règle complémentaire : si les deux tokens font ≤ 2 chars simultanément, la virgule n'est pas corrigée (`de,la` reste intact).

**`15_decoupage.py`** — `SEUIL_MIN`, `LIMITE_EXPORT`, `NB_CYCLES_MAX`, `PREFIXE_SORTIE`.

**`16_inconnus.py`** — `SEUIL_MIN = 2`, `SEUIL_MAX = 10` : seules les formes apparaissant entre 2 et 10 fois sont proposées. En dessous : trop de bruit. Au-delà : probablement un terme du domaine.

---

## Corpus de développement

*Annuaire de l'Institut de droit international*, première année, 1877.  
Source : Gallica BnF — OCR texte brut.  
763 276 caractères, ~116 000 mots, 4 920 paragraphes.

L'Institut de droit international est une organisation savante fondée en 1873, réunissant des juristes internationaux pour codifier le droit international. L'Annuaire contient les statuts, les travaux des sessions, un tableau chronologique des faits internationaux, les textes de traités, et une bibliographie. Structure en cinq parties stables d'un volume à l'autre — ce qui rend le corpus particulièrement adapté à une généralisation sur les quarante volumes de la collection.

---

## Licence

Scripts : MIT.  
Corpus OCR Gallica : domaine public (documents antérieurs à 1900).  
Lefff : licence LGPLLR — voir la documentation du Lefff.
