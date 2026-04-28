"""
t3_parse_toc.py
===============
Troisième étape du traitement de la table des matières (TdM).

RÔLE
----
Ce script transforme le texte de la TdM — nettoyé par T1, vérifié par T2
et corrigé manuellement — en un fichier JSON structuré directement exploitable
par build_sections() pour segmenter le document en sections.

Il procède en quatre étapes internes :
  1. PARSING    — reconnaître la nature de chaque ligne par ses patrons
                  typographiques (forme du titre, numérotation, ponctuation)
  2. CLASSEMENT — attribuer un niveau hiérarchique (1 à 4) à chaque entrée
  3. CONVERSION — extraire et convertir le numéro de page (y compris les
                  chiffres romains des pages préliminaires)
  4. VALIDATION — vérifier la cohérence du JSON produit et signaler les
                  anomalies résiduelles sans bloquer la production du fichier

POURQUOI DÉTERMINISTE PLUTÔT QU'UN LLM ?
-----------------------------------------
Ce script aurait pu confier la structuration à un LLM (comme T2 le fait
pour la vérification). Le choix du traitement déterministe repose sur
plusieurs raisons :

1. REPRODUCTIBILITÉ : le même fichier d'entrée produit toujours exactement
   le même JSON. On peut rejouer T3 à tout moment sans risque de variation.

2. TRANSPARENCE : chaque entrée du JSON est traçable jusqu'à la règle regex
   qui l'a produite. En cas d'erreur, on sait exactement quelle règle corriger.

3. FAISABILITÉ : à ce stade du pipeline, la TdM a été nettoyée (T1),
   vérifiée (T2) et corrigée manuellement. La grande majorité des entrées
   suivent des patrons stables que les expressions régulières couvrent bien.

4. COÛT ET VITESSE : pas d'appel API, pas de latence, pas de coût variable.

Le LLM reste une option de secours documentée : si un volume futur présente
une TdM atypique que ce script gère mal, on peut basculer sur un appel LLM
pour ce volume spécifique, en changeant une ligne dans le pipeline.

POSITION DANS LA CHAÎNE
------------------------
  t1_extract_toc.py  →  [correction manuelle]  →  t2_llm_verify.py
                                                         ↓
                                          [corrections si signalement]
                                                         ↓
                                           t3_parse_toc.py  (ce script)
                                                         ↓
                                              toc_final.json
                                           (versionné dans git)

ENTRÉE / SORTIE
---------------
Entrée  : toc_cleaned.txt ou toc_corrected.txt — texte de la TdM,
          une entrée potentielle par ligne, après nettoyage et corrections.
Sortie  : toc_final.json — tableau JSON d'entrées, chacune ayant la forme :
          {"title": "...", "page": <int>, "level": <1|2|3|4>}
          + toc_parse_report.txt — rapport des entrées non classées et
          anomalies détectées lors de la validation.

FORMAT DU JSON DE SORTIE
------------------------
Chaque entrée du tableau a exactement trois champs :

  "title" : str  — titre nettoyé (sans points de conduite ni numéro de page)
  "page"  : int  — numéro de page (entier positif pour les pages du corps,
                   entier négatif pour les pages préliminaires en chiffres
                   romains : "v" → -5, "xiii" → -13)
  "level" : int  — niveau hiérarchique dans la TdM :
                   1 = Partie   ("Première Partie", "Deuxième Partie"...)
                   2 = Section  ("I. —", "II. —"...)
                   3 = Sous-section ("A. —", "1. —", noms propres, mois)
                   4 = Entrée fine (sous-entrées des annexes, sous-mois)
                   0 = Non classé (à vérifier manuellement)

USAGE
-----
  python t3_parse_toc.py <fichier_toc> [fichier_json] [fichier_rapport]

  Exemple :
    python t3_parse_toc.py toc_cleaned.txt toc_final.json

  Si les chemins de sortie sont omis, les fichiers sont écrits dans le même
  répertoire que le fichier d'entrée avec les noms par défaut.

DÉPENDANCES
-----------
  Aucune bibliothèque externe. Python 3.9+ suffisant.
"""

import re
import sys
import json
from pathlib import Path


# ══════════════════════════════════════════════════════════════════════════════
# PARAMÈTRES
# Toutes les constantes configurables sont ici. Pour adapter ce script à un
# autre corpus, c'est cette section qu'on modifie en priorité.
# ══════════════════════════════════════════════════════════════════════════════

# ── Numéro de page maximal attendu dans ce corpus ────────────────────────────
# Sert à détecter les numéros de page aberrants (erreurs OCR produisant
# des valeurs hors plage). À ajuster selon le volume traité.
PAGE_MAX = 500

# ── Tolérance sur la décroissance des pages ──────────────────────────────────
# Les numéros de page doivent être globalement croissants dans une TdM.
# On tolère une légère décroissance locale (quelques pages) pour les cas
# où deux entrées voisines ont des numéros très proches et potentiellement
# intervertis par OCR. Au-delà de cette tolérance, l'anomalie est signalée.
TOLERANCE_DECROISSANCE = 5

# ── Noms des mois pour la détection du tableau chronologique ─────────────────
# Utilisés pour reconnaître les entrées de niveau 3 dans la Troisième Partie
# (tableau chronologique des faits).
MOIS = [
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
]

# ── Expressions régulières de reconnaissance des niveaux ─────────────────────
# Chaque regex est documentée avec sa justification et ses limites.

# Niveau 1 — Parties
# Forme : "Première Partie." ou "Troisième partie."
# On reconnaît les six premières parties en français. L'adjectif ordinal
# peut être en majuscule ou minuscule (variantes OCR fréquentes).
RE_PARTIE = re.compile(
    r'^(Premi[èe]re?|Deuxi[èe]me?|Troisi[èe]me?|'
    r'Quatri[èe]me?|Cinqui[èe]me?|Sixi[èe]me?)\s+[Pp]artie',
    re.IGNORECASE
)

# Niveau 2 — Sections à numérotation romaine
# Forme : "I. — Titre" ou "II. —Titre" ou "III.— Titre"
# Le tiret cadratin (—) ou le tiret simple (-) sont tous deux acceptés :
# variantes fréquentes selon le volume et l'OCR.
RE_ROMAIN = re.compile(
    r'^([IVX]+)\.\s*[—\-]+\s*(.+)'
)

# Niveau 3 — Sous-sections à lettre
# Forme : "A. — Titre" ou "B.— Titre"
# Attention : ne pas confondre avec les noms propres qui commencent aussi
# par une majuscule. La présence du tiret après la lettre est discriminante.
RE_ALPHA = re.compile(
    r'^([A-Z])\.\s*[—\-]+\s*(.+)'
)

# Niveau 3 — Sous-sections à numérotation arabe
# Forme : "1. — Titre" ou "12. Titre" ou "1.— Titre"
# On accepte l'absence de tiret car certains volumes utilisent uniquement
# le point pour séparer le numéro du titre.
RE_ARABE = re.compile(
    r'^(\d{1,2})\.\s*[—\-]?\s*(.+)'
)

# Niveau 3 — Notices biographiques (noms propres avec parenthèse)
# Forme : "Dupont (Jean)" ou "Rolin-Jaequemyns (Gustave)"
RE_NOM_PROPRE = re.compile(
    r'^[A-ZÀÉÈÊÎÏÙÛÜ][a-zàéèêîïùûü]'   # commence par Maj puis min
    r'[\w\-àéèêîïùûü]*'                  # suite du nom (avec tiret possible)
    r'\s*[\(\[]'                          # parenthèse ou crochet ouvrant
)

# Niveau 3 — Noms propres sans parenthèse
# "Den Beer Portugael", "Drouyn de Lhuys" : noms sans prénom entre parenthèses.
# Testée EN DERNIER pour minimiser les faux positifs (règle plus large).
RE_NOM_SANS_PARENTHESE = re.compile(
    r'^[A-ZÀÉÈÊÎÏÙÛÜ][a-zàéèêîïùûü][\w\s\-àéèêîïùûü]*$'
)

# Niveau 2 — Titres entièrement en majuscules (rubriques sans numérotation)
# "STATUTS, RÈGLEMENT...", "NOTICES ET DOCUMENTS...",
# "TABLEAU CHRONOLOGIQUE...", "BIBLIOGRAPHIE DU DROIT INTERNATIONAL..."
RE_TITRE_CAPITALES = re.compile(
    r'^[A-ZÀÉÈÊÎÏÙÛÜ]{2,}[\w\s\-,àéèêîïùûü\.—]+$'
)

# Niveau 4 — Sous-entrées alphabétiques minuscules
# "a) L'Angleterre...", "b) Les Pays-Bas...", "c) La Question d'Orient..."
RE_ALPHA_MIN = re.compile(
    r'^([a-zàéèê])\)\s*(.+)'
)

# Niveau 3 — Annexes et listes
# "Annexe A. — ...", "Annexe B. — ...", "Annexe. — ...", "Liste des..."
RE_ANNEXE = re.compile(
    r'^(Annexe[s]?[\s\.]*[A-Z]?[\.\s]*[—\-]|Liste\s+des)',
    re.IGNORECASE
)

# Préfixes thématiques de la bibliographie (niveau 3)
# "Travaux spécialement...", "Publications spécialement...", etc.
PREFIXES_THEMATIQUES = (
    "Travaux spécialement",
    "Publications spécialement",
    "Publications relatives",
    "Monographies recommandant",
)

# Numéro de page en fin de ligne
# Forme : "Titre . . . . . 123" ou "Titre 123" ou "Titre......123"
# On capture le dernier groupe de chiffres ou de chiffres romains en fin
# de ligne, précédé de points, d'espaces ou de tirets.
# Les chiffres romains en minuscules (pages préliminaires) sont aussi capturés.
RE_PAGE_FIN = re.compile(
    r'[\.\s\-]{0,10}([ivxlcdmIVXLCDM]+|\d+)\s*$'
)

# Motif de points de conduite à supprimer du titre après extraction du n° page
# Forme : ". . . ." ou "......" ou "· · ·"
RE_POINTS_CONDUITE = re.compile(r'[\.\s·]{3,}$')


# ══════════════════════════════════════════════════════════════════════════════
# CONVERSION DES CHIFFRES ROMAINS
# ══════════════════════════════════════════════════════════════════════════════

# Table de correspondance des symboles romains.
# On n'utilise que les minuscules car les pages préliminaires des annuaires
# sont numérotées en minuscules (v, xiii, xvii...).
ROMAINS = {
    'i': 1, 'v': 5, 'x': 10, 'l': 50,
    'c': 100, 'd': 500, 'm': 1000
}


def romain_vers_entier(s: str) -> int | None:
    """
    Convertit une chaîne de chiffres romains en entier.

    Algorithme : on parcourt les symboles de gauche à droite. Si un symbole
    a une valeur inférieure au suivant, on le soustrait (ex: iv = 4) ;
    sinon on l'additionne (ex: vi = 6). C'est la règle standard de notation
    romaine.

    Retourne None si la chaîne n'est pas un chiffre romain valide — ce qui
    permet à l'appelant de signaler l'anomalie plutôt que de planter.

    Limites : cette fonction ne valide pas la conformité stricte de la
    notation romaine (ex: elle accepterait "iiii" comme 4). Pour ce corpus,
    cette tolérance est acceptable car les erreurs OCR sur les romains sont
    justement des formes non standard.

    Paramètre
    ---------
    s : str
        Chaîne à convertir, en minuscules ou majuscules.

    Retourne
    --------
    int | None : valeur entière, ou None si la conversion échoue.
    """
    s = s.lower().strip()
    if not s or not all(c in ROMAINS for c in s):
        return None

    resultat = 0
    for i, c in enumerate(s):
        valeur = ROMAINS[c]
        # Si le symbole suivant a une valeur plus grande, on soustrait
        if i + 1 < len(s) and ROMAINS[s[i + 1]] > valeur:
            resultat -= valeur
        else:
            resultat += valeur

    return resultat if resultat > 0 else None


def extraire_page(ligne: str) -> tuple[str, int | None, bool]:
    """
    Extrait le numéro de page en fin de ligne et nettoie le titre.

    Stratégie : on cherche le dernier groupe numérique (arabe ou romain)
    en fin de ligne. Si trouvé, on le retire du titre et on le convertit
    en entier. Les pages préliminaires en chiffres romains sont converties
    en entiers négatifs pour les distinguer des pages du corps du document.

    Convention choisie pour les négatifs :
    "v" → -5, "xiii" → -13. Ce choix permet de conserver l'ordre naturel
    dans le JSON (les pages préliminaires précèdent les pages du corps)
    tout en les distinguant clairement. L'alternative — les mettre à 0 ou
    None — perdrait l'information de position.

    Paramètres
    ----------
    ligne : str
        Ligne de TdM après nettoyage initial.

    Retourne
    --------
    tuple(titre_nettoye, numero_page, est_romain)
    - titre_nettoye : str — ligne sans le numéro de page ni les points
    - numero_page   : int | None — entier (négatif si romain), None si absent
    - est_romain    : bool — True si la page était en chiffres romains
    """
    m = RE_PAGE_FIN.search(ligne)
    if not m:
        return ligne.strip(), None, False

    token_page = m.group(1)
    titre = ligne[:m.start()].strip()
    titre = RE_POINTS_CONDUITE.sub('', titre).strip()

    # Essayer d'abord la conversion en entier arabe
    if token_page.isdigit():
        return titre, int(token_page), False

    # Essayer la conversion en chiffres romains
    valeur = romain_vers_entier(token_page)
    if valeur is not None:
        # Entier négatif pour les pages préliminaires
        return titre, -valeur, True

    # Ni arabe ni romain reconnu : on retourne None
    return titre, None, False


# ══════════════════════════════════════════════════════════════════════════════
# CLASSIFICATION DES ENTRÉES
# ══════════════════════════════════════════════════════════════════════════════

def classifier_ligne(titre: str) -> tuple[int, str]:
    """
    Détermine le niveau hiérarchique d'une entrée à partir de son titre.

    Les patrons sont testés dans l'ordre hiérarchique décroissant (du plus
    général au plus spécifique), ce qui garantit qu'une entrée de niveau 1
    ne soit pas mal classée comme niveau 3.

    Retourne un tuple (niveau, titre_normalise) où :
    - niveau          : int — 1 à 4, ou 0 si non classé
    - titre_normalise : str — titre éventuellement nettoyé après extraction
                        du préfixe de numérotation

    Le niveau 0 ("non classé") n'est pas une erreur bloquante : il signale
    une entrée que l'utilisateur doit vérifier manuellement. Ces cas sont
    listés dans le rapport de validation.

    Paramètres
    ----------
    titre : str
        Titre de l'entrée après extraction du numéro de page.

    Retourne
    --------
    tuple(niveau, titre_normalise)
    """
    # ── Niveau 1 : Parties ───────────────────────────────────────────────────
    if RE_PARTIE.match(titre):
        return 1, titre

    # ── Niveau 2 : sections à numérotation romaine ───────────────────────────
    m = RE_ROMAIN.match(titre)
    if m:
        # On conserve le titre complet avec son numéro romain :
        # "I. — Statuts..." est plus lisible que "Statuts..." pour retrouver
        # l'entrée dans le document.
        return 2, titre

    # ── Niveau 3 : mois (tableau chronologique) ──────────────────────────────
    # Testé avant RE_ALPHA pour éviter que "Avril 1874" soit classé niveau 3
    # par la sous-section lettre (ce qui ne se produirait pas, mais la
    # lisibilité du code gagne à avoir les cas spéciaux explicites).
    for mois in MOIS:
        if titre.startswith(mois):
            return 3, titre

    # ── Niveau 3 : sous-sections à lettre ────────────────────────────────────
    m = RE_ALPHA.match(titre)
    if m:
        return 3, titre

    # ── Niveau 3 : sous-sections à numérotation arabe ────────────────────────
    m = RE_ARABE.match(titre)
    if m:
        return 3, titre

    # ── Niveau 3 : notices biographiques (noms propres avec parenthèse) ────────
    if RE_NOM_PROPRE.match(titre):
        return 3, titre

    # ── Niveau 3 : annexes ───────────────────────────────────────────────────
    if RE_ANNEXE.match(titre):
        return 3, titre

    # ── Niveau 3 : regroupements thématiques (bibliographie) ─────────────────
    for prefixe in PREFIXES_THEMATIQUES:
        if titre.startswith(prefixe):
            return 3, titre

    # ── Niveau 2 : titres en capitales (rubriques majeures sans numérotation)
    # Testé après les règles de niveau 3 pour éviter que des titres courts
    # en majuscules soient sur-classés.
    if RE_TITRE_CAPITALES.match(titre) and len(titre) > 10:
        return 2, titre

    # ── Niveau 4 : sous-entrées alphabétiques minuscules ─────────────────────
    if RE_ALPHA_MIN.match(titre):
        return 4, titre

    # ── Niveau 3 : noms propres sans parenthèse ──────────────────────────────
    # Testé EN DERNIER car c'est la règle la plus large.
    # On ajoute une garde : le titre ne doit pas contenir de tiret cadratin
    # (qui indiquerait une section, déjà couverte par RE_ROMAIN ou RE_ALPHA).
    if RE_NOM_SANS_PARENTHESE.match(titre) and '—' not in titre:
        return 3, titre

    # ── Niveau 0 : non classé ────────────────────────────────────────────────
    return 0, titre


# ══════════════════════════════════════════════════════════════════════════════
# VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

def valider_entrees(entrees: list[dict]) -> list[str]:
    """
    Vérifie la cohérence de la liste d'entrées et retourne une liste
    d'anomalies sous forme de chaînes lisibles.

    Trois types de vérifications :

    1. ENTRÉES INCOMPLÈTES : titre vide, page absente, niveau 0.
       Ces entrées sont signalées mais conservées dans le JSON pour que
       l'utilisateur puisse les corriger manuellement.

    2. COHÉRENCE DES PAGES : les pages doivent être globalement croissantes.
       On tolère une légère décroissance locale (TOLERANCE_DECROISSANCE pages)
       pour les cas où deux entrées voisines ont des numéros très proches.
       Une décroissance importante signale une erreur de numéro de page.

    3. PAGES HORS PLAGE : pages supérieures à PAGE_MAX ou égales à 0.
       Probable erreur OCR (ex: "1O1" lu comme "101" alors qu'il s'agit
       de "101" avec un O à la place du zéro).

    Paramètre
    ---------
    entrees : list[dict]
        Liste d'entrées produites par parser_toc().

    Retourne
    --------
    list[str] : liste d'anomalies détectées, vide si aucune.
    """
    anomalies = []
    derniere_page_corps = 0   # dernière page positive vue (corps du document)

    for i, e in enumerate(entrees):
        titre = e.get("title", "")
        page  = e.get("page")
        level = e.get("level", 0)

        # ── Entrées incomplètes ──────────────────────────────────────────────
        if not titre:
            anomalies.append(f"Entrée {i+1} : titre vide.")

        if page is None:
            anomalies.append(
                f"Entrée {i+1} ({titre[:40]!r}) : numéro de page absent."
            )

        if level == 0:
            anomalies.append(
                f"Entrée {i+1} ({titre[:40]!r}) : niveau non classé (0)."
            )

        # ── Cohérence des pages (corps du document uniquement) ───────────────
        # On ne vérifie la croissance que pour les pages positives (corps)
        # et sous PAGE_MAX. Une valeur aberrante (ex: "159167" capturée comme
        # page par erreur) ne doit pas contaminer toutes les vérifications
        # suivantes : on l'ignore pour le calcul de la dernière page vue.
        if page is not None and 0 < page <= PAGE_MAX:
            if (derniere_page_corps > 0
                    and page < derniere_page_corps - TOLERANCE_DECROISSANCE):
                anomalies.append(
                    f"Entrée {i+1} ({titre[:40]!r}) : page {page} "
                    f"inférieure à la page précédente {derniere_page_corps} "
                    f"(décroissance de {derniere_page_corps - page})."
                )
            derniere_page_corps = max(derniere_page_corps, page)

        # ── Pages hors plage ─────────────────────────────────────────────────
        if page is not None and page > PAGE_MAX:
            anomalies.append(
                f"Entrée {i+1} ({titre[:40]!r}) : page {page} "
                f"supérieure au maximum attendu ({PAGE_MAX})."
            )

    return anomalies


# ══════════════════════════════════════════════════════════════════════════════
# PARSEUR PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def parser_toc(texte: str) -> list[dict]:
    """
    Parse le texte de la TdM et retourne une liste d'entrées structurées.

    Traitement ligne par ligne :
      1. Ignorer les lignes vides.
      2. Extraire le numéro de page en fin de ligne.
      3. Classifier le titre pour déterminer le niveau hiérarchique.
      4. Construire l'entrée JSON.

    Les lignes vides ne sont pas traitées : elles servent uniquement à
    séparer visuellement les entrées dans le fichier texte et n'ont pas
    de signification structurelle dans ce corpus.

    Paramètre
    ---------
    texte : str
        Contenu complet du fichier TdM nettoyé.

    Retourne
    --------
    list[dict] : liste d'entrées, chacune ayant les champs
                 "title", "page", "level".
    """
    entrees = []
    lignes = texte.splitlines()

    for numero_ligne, ligne in enumerate(lignes, start=1):
        ligne = ligne.strip()

        # Ignorer les lignes vides
        if not ligne:
            continue

        # Étape 1 : extraire le numéro de page
        titre, page, est_romain = extraire_page(ligne)

        # Étape 2 : classifier le titre
        # On classe sur le titre sans le numéro de page pour que les
        # expressions régulières ne soient pas perturbées par les chiffres
        # en fin de ligne.
        level, titre_normalise = classifier_ligne(titre)

        entrees.append({
            "title": titre_normalise,
            "page":  page,
            "level": level,
            # Métadonnée interne utile pour le rapport et le débogage.
            # On la supprimera avant l'export JSON final.
            "_ligne_source": numero_ligne,
            "_romain": est_romain,
        })

    return entrees


def nettoyer_pour_export(entrees: list[dict]) -> list[dict]:
    """
    Supprime les métadonnées internes avant l'export JSON final.

    Les champs préfixés par _ (comme _ligne_source et _romain) sont des
    informations de débogage utiles pendant le traitement mais qui n'ont
    pas vocation à figurer dans toc_final.json. Cette fonction produit
    la version propre destinée à build_sections().
    """
    return [
        {k: v for k, v in e.items() if not k.startswith("_")}
        for e in entrees
    ]


# ══════════════════════════════════════════════════════════════════════════════
# RAPPORT
# ══════════════════════════════════════════════════════════════════════════════

def produire_rapport(
    entrees: list[dict],
    anomalies: list[str],
    fichier_source: str
) -> str:
    """
    Produit le rapport de parsing : statistiques, entrées non classées
    et anomalies détectées lors de la validation.

    Ce rapport est le principal outil de contrôle qualité de T3. Il permet
    de vérifier rapidement que la structuration est correcte sans avoir à
    ouvrir le JSON. Les entrées de niveau 0 (non classées) et les anomalies
    de pages sont les deux signaux les plus importants à surveiller.

    Paramètres
    ----------
    entrees        : list[dict] — entrées avec métadonnées internes
    anomalies      : list[str]  — liste produite par valider_entrees()
    fichier_source : str        — chemin du fichier d'entrée (pour traçabilité)

    Retourne
    --------
    str : rapport formaté en texte lisible.
    """
    from datetime import datetime
    horodatage = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Statistiques par niveau
    compteurs = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
    for e in entrees:
        compteurs[e.get("level", 0)] += 1

    nb_sans_page   = sum(1 for e in entrees if e.get("page") is None)
    nb_romains     = sum(1 for e in entrees if e.get("_romain"))
    nb_non_classes = compteurs[0]

    lignes = [
        "RAPPORT DE PARSING — TABLE DES MATIÈRES",
        "=" * 50,
        f"Fichier source    : {fichier_source}",
        f"Généré le         : {horodatage}",
        "=" * 50,
        "",
        "── Statistiques ────────────────────────────────",
        f"  Entrées totales  : {len(entrees)}",
        f"  Niveau 1 (Parties)         : {compteurs[1]}",
        f"  Niveau 2 (Sections)        : {compteurs[2]}",
        f"  Niveau 3 (Sous-sections)   : {compteurs[3]}",
        f"  Niveau 4 (Entrées fines)   : {compteurs[4]}",
        f"  Niveau 0 (Non classés)     : {nb_non_classes}",
        f"  Pages en chiffres romains  : {nb_romains}",
        f"  Entrées sans numéro de page: {nb_sans_page}",
        "",
    ]

    # Entrées non classées (niveau 0)
    non_classes = [e for e in entrees if e.get("level") == 0]
    if non_classes:
        lignes.append("── Entrées non classées (niveau 0) ─────────────")
        lignes.append("   Ces entrées n'ont pas correspondu à un patron")
        lignes.append("   connu. Vérifier et corriger dans toc_final.json")
        lignes.append("   ou ajouter une règle dans t3_parse_toc.py.")
        lignes.append("")
        for e in non_classes:
            lignes.append(
                f"  ligne {e['_ligne_source']:4d} │ "
                f"page {str(e.get('page', '?')):>4} │ "
                f"{e['title'][:60]}"
            )
        lignes.append("")
    else:
        lignes.append("── Entrées non classées : aucune ───────────────")
        lignes.append("")

    # Anomalies de validation
    if anomalies:
        lignes.append("── Anomalies détectées ──────────────────────────")
        for a in anomalies:
            lignes.append(f"  {a}")
        lignes.append("")
    else:
        lignes.append("── Anomalies détectées : aucune ─────────────────")
        lignes.append("")

    lignes += [
        "─" * 50,
        "Le fichier toc_final.json a été produit même en",
        "présence d'anomalies : il doit être inspecté avant",
        "d'être passé à build_sections().",
    ]

    return "\n".join(lignes)


# ══════════════════════════════════════════════════════════════════════════════
# POINT D'ENTRÉE
# ══════════════════════════════════════════════════════════════════════════════

def main():
    # ── Lecture des arguments ────────────────────────────────────────────────
    if len(sys.argv) < 2:
        print(
            "Usage : python t3_parse_toc.py <fichier_toc> "
            "[fichier_json] [fichier_rapport]\n"
            "Exemple : python t3_parse_toc.py toc_cleaned.txt"
        )
        sys.exit(1)

    chemin_source = Path(sys.argv[1])
    if not chemin_source.exists():
        print(f"Erreur : fichier introuvable : {chemin_source}")
        sys.exit(1)

    chemin_json = (
        Path(sys.argv[2]) if len(sys.argv) >= 3
        else chemin_source.parent / "toc_final.json"
    )
    chemin_rapport = (
        Path(sys.argv[3]) if len(sys.argv) >= 4
        else chemin_source.parent / "toc_parse_report.txt"
    )

    # ── Lecture et parsing ───────────────────────────────────────────────────
    texte = chemin_source.read_text(encoding="utf-8")
    entrees = parser_toc(texte)

    print(f"Fichier lu      : {chemin_source}")
    print(f"Entrées parsées : {len(entrees)}")

    # ── Validation ───────────────────────────────────────────────────────────
    anomalies = valider_entrees(entrees)
    nb_non_classes = sum(1 for e in entrees if e.get("level") == 0)

    if anomalies or nb_non_classes:
        print(
            f"Attention : {len(anomalies)} anomalie(s) détectée(s), "
            f"{nb_non_classes} entrée(s) non classée(s).\n"
            f"Consulter le rapport : {chemin_rapport}"
        )
    else:
        print("Validation : aucune anomalie.")

    # ── Export JSON ──────────────────────────────────────────────────────────
    # On exporte la version nettoyée (sans les champs internes _*)
    entrees_export = nettoyer_pour_export(entrees)
    chemin_json.write_text(
        json.dumps(entrees_export, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"JSON écrit      : {chemin_json}")

    # ── Rapport ──────────────────────────────────────────────────────────────
    rapport = produire_rapport(entrees, anomalies, str(chemin_source))
    chemin_rapport.write_text(rapport, encoding="utf-8")
    print(f"Rapport écrit   : {chemin_rapport}")

    # Aperçu console des 15 premières entrées
    print("\n── Aperçu (15 premières entrées) ───────────────────")
    for e in entrees[:15]:
        page_str = str(e.get("page", "?")).rjust(5)
        print(
            f"  [niv.{e['level']}] "
            f"p.{page_str} │ "
            f"{e['title'][:55]}"
        )
    print("────────────────────────────────────────────────────")


if __name__ == "__main__":
    main()
