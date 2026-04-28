"""
t1_extract_toc.py
=================
Première étape du traitement de la table des matières (TdM).

RÔLE
----
Ce script fait exactement trois choses :
  1. Localiser le début de la TdM dans le fichier source texte brut.
  2. Extraire le bloc TdM (du début jusqu'à la fin du fichier).
  3. Nettoyer ce bloc des artefacts de mise en page : séparateurs décoratifs,
     répétitions du titre de section en en-tête de page, lignes parasites.

Ce script ne corrige PAS les erreurs de fond (titres tronqués, entrées
compressées, numéros de page erronés). Ces corrections sont faites manuellement
sur le fichier source AVANT d'appeler ce script, ou signalées par T2 (LLM)
APRÈS.

PRINCIPE DE CONCEPTION
-----------------------
Ce script est volontairement minimal et déterministe : il n'appelle aucun
service externe, ne prend aucune décision sémantique, et produit le même
résultat à chaque exécution sur le même fichier d'entrée.

Chaque transformation est documentée et paramétrable, afin que le script
puisse être adapté à d'autres corpus similaires (publications Gallica,
revues juridiques numérisées, etc.) en ne modifiant que la section PARAMÈTRES.

ENTRÉE / SORTIE
---------------
Entrée  : fichier texte brut issu de Gallica (original.txt ou version
          corrigée manuellement sur la zone TdM).
Sortie  : fichier texte nettoyé (toc_cleaned.txt), une entrée potentielle
          par ligne, prêt pour la correction manuelle ou le passage au LLM.

USAGE
-----
  python t1_extract_toc.py <fichier_source> [fichier_sortie]

  Exemple :
    python t1_extract_toc.py annuaire_1877.txt toc_cleaned.txt

  Si fichier_sortie est omis, le résultat est écrit dans toc_cleaned.txt
  dans le même répertoire que le fichier source.

DÉPENDANCES
-----------
  Aucune bibliothèque externe. Python 3.9+ suffisant.
"""

import re
import sys
from pathlib import Path


# ══════════════════════════════════════════════════════════════════════════════
# PARAMÈTRES
# Toutes les constantes qui dépendent du format du corpus sont regroupées ici.
# Pour adapter ce script à un autre corpus, c'est cette section qu'on modifie.
# ══════════════════════════════════════════════════════════════════════════════

# Motif d'un séparateur de page Gallica : ligne composée uniquement de tirets,
# au moins 20 caractères. Ces lignes délimitent chaque page dans le fichier texte.
SEPARATEUR = re.compile(r'^-{20,}\s*$')

# Motif du début de la TdM : première ligne non vide après un séparateur
# qui commence par "TABLE DES MATI" (avec tolérance sur l'accentuation
# et la présence d'un numéro de page DEVANT, qui indiquerait une page
# de continuation de TdM, pas le début).
# On cherche spécifiquement une ligne qui commence DIRECTEMENT par TABLE,
# sans numéro devant — ce qui correspond à la première page de TdM,
# non numérotée dans ce corpus (page 383 de l'annuaire 1877).
#
# TRANSPOSABILITÉ — autres formes de marqueur de début de TdM :
#
# La stratégie de ce script repose sur un invariant : le début de la TdM
# est repérable par un motif textuel stable dans le fichier source.
# Cet invariant tient pour la quasi-totalité des corpus numérisés, mais
# la forme du motif varie. Voici comment adapter DEBUT_TDM selon les cas :
#
# Cas 1 — TdM en début de document (et non en fin) :
#   La fonction localiser_debut_tdc() parcourt le fichier de haut en bas
#   et s'arrête au premier séparateur correspondant. Elle fonctionnera
#   sans modification si la TdM est en début de document.
#
# Cas 2 — TdM repérable par un titre différent ("SOMMAIRE", "INDEX", etc.) :
#   Modifier simplement le motif :
#     DEBUT_TDM = re.compile(r'^SOMMAIRE', re.IGNORECASE)
#
# Cas 3 — TdM sans séparateur de page (corpus sans tirets Gallica) :
#   La fonction localiser_debut_tdc() doit être remplacée par une version
#   qui cherche directement le motif dans toutes les lignes, sans condition
#   sur un séparateur précédent. Exemple minimal :
#     for i, ligne in enumerate(lignes):
#         if DEBUT_TDM.match(ligne.strip()):
#             return i
#
# Cas 4 — TdM toujours numérotée (toutes les pages portent un numéro) :
#   Dans ce corpus, la première page de TdM est non numérotée, ce qui
#   permet de la distinguer des pages de continuation ("384 TABLE DES
#   MATIÈRES."). Si dans votre corpus toutes les pages sont numérotées,
#   adapter le motif pour accepter également un numéro devant :
#     DEBUT_TDM = re.compile(r'^\d*\s*TABLE\s+DES\s+MATI', re.IGNORECASE)
#   et modifier localiser_debut_tdc() pour choisir la PREMIÈRE occurrence
#   plutôt que de distinguer première page / pages de continuation.
#
# Cas 5 — TdM repérable uniquement par sa position (dernière section) :
#   Si aucun marqueur textuel n'est fiable, on peut repérer la TdM par
#   sa position : elle commence après la dernière page numérotée du corps.
#   Ce cas est le moins robuste et nécessite une inspection manuelle
#   préalable pour confirmer la page de début.
DEBUT_TDM = re.compile(r'^TABLE\s+DES\s+MATI', re.IGNORECASE)

# Motif des en-têtes de page répétés à l'intérieur de la TdM.
# Gallica répète le titre de section en haut de chaque page numérisée,
# sous la forme "384 TABLE DES MATIÈRES." ou "TABLE DES MATIÈRES. 385".
# Ces lignes sont du bruit : elles ne font pas partie du contenu de la TdM.
ENTETE_PAGE_TDM = re.compile(
    r'^\d*\s*TABLE\s+DES\s+MATI[ÈE]RES?\.?\s*\d*\s*$',
    re.IGNORECASE
)

# Lignes à supprimer intégralement, indépendamment de leur position.
# "Pages." est un sous-titre répété en tête de chaque page de TdM.
# "FIN DE LA PREMIERE ANNEE" est la ligne de clôture du volume.
# On utilise des expressions régulières pour tolérer les variantes mineures.
LIGNES_A_SUPPRIMER = [
    re.compile(r'^Pages?\.\s*$', re.IGNORECASE),
    re.compile(r'^FIN\s+DE\s+LA\s+PREMI[EÈ]RE?\s+ANN[EÉ]E\s*\.?\s*$', re.IGNORECASE),
    re.compile(r'^\.\.\s*\d+\s*$'),   # artefacts du type ".. 23"
]

# Nombre maximum de lignes à inspecter après un séparateur pour trouver
# le marqueur de début de TdM. 5 est suffisant : le séparateur est suivi
# d'une ligne vide puis du titre TABLE DES MATIERES.
FENETRE_RECHERCHE = 5

# Nombre minimum de caractères non-espaces pour qu'une ligne soit conservée
# après nettoyage. Permet d'éliminer les lignes quasi-vides (un point,
# un tiret isolé) sans supprimer les courtes entrées légitimes.
LONGUEUR_MINIMALE = 2


# ══════════════════════════════════════════════════════════════════════════════
# FONCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def localiser_debut_tdc(lignes: list[str]) -> int | None:
    """
    Trouve l'index de la première ligne du bloc TdM.

    Stratégie : on parcourt les séparateurs de page un par un et on inspecte
    les quelques lignes qui suivent chacun. Le premier séparateur dont la suite
    immédiate contient "TABLE DES MATI" SANS numéro de page devant marque le
    début de la TdM.

    Pourquoi cette condition "sans numéro devant" ?
    Dans ce corpus, la TdM s'étend sur plusieurs pages. Les pages de
    continuation portent un en-tête numéroté ("384 TABLE DES MATIÈRES."),
    que le motif ENTETE_PAGE_TDM est chargé de supprimer plus loin.
    La première page de TdM, elle, n'est pas numérotée : son en-tête est
    simplement "TABLE DES MATIERES." sans chiffre devant. C'est ce contraste
    qui permet de la distinguer des autres.

    Si dans votre corpus toutes les pages de TdM sont numérotées (y compris
    la première), cette distinction disparaît. Dans ce cas, deux adaptations
    sont possibles :
      a) Modifier DEBUT_TDM pour accepter un numéro optionnel devant, et
         identifier le début par le numéro de page le plus petit (première
         occurrence dans l'ordre croissant des pages).
      b) Identifier le début de TdM par sa position dans le document plutôt
         que par son contenu : repérer le dernier séparateur de page du corps
         du texte, et considérer que tout ce qui suit est la TdM. Cette
         approche est plus fragile mais ne dépend pas du libellé exact.

    Retourne l'index de la ligne du séparateur (inclus dans l'extraction),
    ou None si la TdM n'est pas trouvée.
    """
    for i, ligne in enumerate(lignes):
        if not SEPARATEUR.match(ligne):
            continue
        # Inspecter les lignes suivantes dans la fenêtre de recherche
        for offset in range(1, FENETRE_RECHERCHE + 1):
            pos = i + offset
            if pos >= len(lignes):
                break
            candidate = lignes[pos].strip()
            if not candidate:
                continue  # ligne vide : continuer à chercher
            if DEBUT_TDM.match(candidate):
                return i  # on retourne la position du séparateur lui-même
            break  # première ligne non vide trouvée, pas un début de TdM

    return None


def est_ligne_parasite(ligne: str) -> bool:
    """
    Détermine si une ligne doit être supprimée du bloc TdM.

    Trois catégories de lignes parasites :
    - Les séparateurs de page (lignes de tirets) : artefacts visuels Gallica.
    - Les en-têtes de page répétés ("384 TABLE DES MATIÈRES.") : redondants.
    - Les lignes explicitement listées dans LIGNES_A_SUPPRIMER.

    Ce choix de supprimer les séparateurs à ce stade (et non en amont)
    est délibéré : on ne touche pas au fichier source, on nettoie uniquement
    dans la zone TdM extraite.
    """
    if SEPARATEUR.match(ligne):
        return True
    if ENTETE_PAGE_TDM.match(ligne.strip()):
        return True
    for motif in LIGNES_A_SUPPRIMER:
        if motif.match(ligne.strip()):
            return True
    return False


def normaliser_espaces(ligne: str) -> str:
    """
    Normalise les espaces internes d'une ligne.

    L'OCR produit fréquemment des espaces multiples (entre mots, avant
    ponctuation). On les réduit à un espace unique sans toucher à la
    structure de la ligne. On ne touche pas aux espaces en début de ligne :
    certaines entrées utilisent l'indentation pour signaler un sous-niveau,
    et cette information doit être préservée pour T2.
    """
    # Réduire les séquences d'espaces internes (pas en début de ligne)
    ligne_norm = re.sub(r'(?<=\S) {2,}', ' ', ligne)
    # Supprimer les espaces en fin de ligne
    return ligne_norm.rstrip()


def extraire_et_nettoyer(lignes: list[str], debut: int) -> list[str]:
    """
    Extrait le bloc TdM depuis la position `debut` et le nettoie.

    Le nettoyage est appliqué ligne par ligne, dans l'ordre :
      1. Supprimer les lignes parasites (séparateurs, en-têtes, lignes vides
         de liste).
      2. Normaliser les espaces internes.
      3. Éliminer les lignes trop courtes après nettoyage.

    On conserve les lignes vides entre entrées : elles peuvent porter
    une information de groupement que T2 utilisera pour reconstituer
    la hiérarchie. On ne conserve pas les séquences de plusieurs lignes
    vides consécutives.
    """
    bloc_brut = lignes[debut:]
    resultat = []
    ligne_vide_precedente = False

    for ligne in bloc_brut:
        # Étape 1 : suppression des lignes parasites
        if est_ligne_parasite(ligne):
            continue

        # Étape 2 : normalisation des espaces
        ligne = normaliser_espaces(ligne)

        # Gestion des lignes vides : on en conserve au plus une consécutive
        if not ligne.strip():
            if not ligne_vide_precedente:
                resultat.append('')
            ligne_vide_precedente = True
            continue

        # Étape 3 : éliminer les lignes trop courtes (un point, un tiret isolé)
        if len(ligne.strip()) < LONGUEUR_MINIMALE:
            continue

        resultat.append(ligne)
        ligne_vide_precedente = False

    # Supprimer les éventuelles lignes vides en début et fin de bloc
    while resultat and not resultat[0]:
        resultat.pop(0)
    while resultat and not resultat[-1]:
        resultat.pop()

    return resultat


def produire_rapport(lignes_brutes: int, lignes_nettoyees: int,
                     debut: int, fichier_source: str) -> str:
    """
    Produit un court rapport textuel affiché en console après traitement.

    Ce rapport permet de vérifier rapidement que l'extraction s'est bien
    passée sans ouvrir le fichier de sortie. Il indique notamment la ligne
    du fichier source où la TdM a été localisée, ce qui permet de vérifier
    manuellement si nécessaire.
    """
    return (
        f"\n── Rapport t1_extract_toc ──────────────────────\n"
        f"  Fichier source    : {fichier_source}\n"
        f"  TdM localisée     : ligne {debut + 1} du fichier source\n"
        f"  Lignes extraites  : {lignes_brutes} (brut)\n"
        f"  Lignes conservées : {lignes_nettoyees} (après nettoyage)\n"
        f"  Lignes supprimées : {lignes_brutes - lignes_nettoyees}\n"
        f"────────────────────────────────────────────────\n"
    )


# ══════════════════════════════════════════════════════════════════════════════
# POINT D'ENTRÉE
# ══════════════════════════════════════════════════════════════════════════════

def main():
    # ── Lecture des arguments ────────────────────────────────────────────────
    if len(sys.argv) < 2:
        print("Usage : python t1_extract_toc.py <fichier_source> [fichier_sortie]")
        sys.exit(1)

    chemin_source = Path(sys.argv[1])
    if not chemin_source.exists():
        print(f"Erreur : fichier introuvable : {chemin_source}")
        sys.exit(1)

    # Par défaut, on écrit toc_cleaned.txt à côté du fichier source
    if len(sys.argv) >= 3:
        chemin_sortie = Path(sys.argv[2])
    else:
        chemin_sortie = chemin_source.parent / "toc_cleaned.txt"

    # ── Lecture du fichier source ────────────────────────────────────────────
    # On lit en UTF-8. Gallica produit des fichiers UTF-8 ; si votre corpus
    # utilise un autre encodage (latin-1 pour les anciennes versions),
    # remplacer "utf-8" par "latin-1" ou "utf-8-sig".
    texte = chemin_source.read_text(encoding="utf-8")
    lignes = texte.splitlines()

    # ── Localisation de la TdM ───────────────────────────────────────────────
    debut = localiser_debut_tdc(lignes)

    if debut is None:
        print(
            "Erreur : impossible de localiser la table des matières.\n"
            "Vérifiez que le fichier contient une ligne 'TABLE DES MATIERES'\n"
            "sans numéro de page devant (première page de TdM non numérotée).\n"
            "Si votre corpus numérote toutes les pages, adaptez le motif\n"
            "DEBUT_TDM dans la section PARAMÈTRES."
        )
        sys.exit(1)

    # ── Extraction et nettoyage ──────────────────────────────────────────────
    lignes_brutes = lignes[debut:]
    lignes_nettoyees = extraire_et_nettoyer(lignes, debut)

    # ── Écriture du fichier de sortie ────────────────────────────────────────
    chemin_sortie.write_text(
        "\n".join(lignes_nettoyees) + "\n",
        encoding="utf-8"
    )

    # ── Rapport ──────────────────────────────────────────────────────────────
    print(produire_rapport(
        lignes_brutes=len(lignes_brutes),
        lignes_nettoyees=len(lignes_nettoyees),
        debut=debut,
        fichier_source=str(chemin_source)
    ))
    print(f"Fichier de sortie : {chemin_sortie}")

    # Aperçu des 10 premières lignes pour vérification immédiate
    print("\nAperçu (10 premières lignes) :")
    for i, ligne in enumerate(lignes_nettoyees[:10]):
        print(f"  {i+1:3d} │ {ligne}")


if __name__ == "__main__":
    main()
