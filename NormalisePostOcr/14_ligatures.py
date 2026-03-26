#!/usr/bin/env python3
# -*- coding: utf-8 -*-

r"""
===============================================================================
RÈGLE 14 : RESTAURATION DE LA LIGATURE Œ
===============================================================================

Description :
    Restaure la ligature œ dans les mots français courants où l'OCR a produit
    "oe" à la place. Utilise un lexique intégré et une liste d'exceptions pour
    ne corriger que les formes certaines.

Pourquoi "oe" → "œ" est nécessaire ici :
    Les systèmes OCR XIXe éclatent systématiquement la ligature œ en deux
    lettres séparées "oe". Le corpus contient ainsi "oeuvre", "voeu",
    "coeur", "moeurs" là où la graphie normative française exige "œuvre",
    "vœu", "cœur", "mœurs".
    
    Ces 79 occurrences sont toutes des mots français du vocabulaire courant —
    pas des emprunts, pas des noms propres.

Pourquoi PAS "ae" → "æ" dans ce corpus :
    L'analyse exhaustive du corpus révèle que tous les mots contenant "ae"
    sont des noms propres flamands et néerlandais :
        Jaequemyns (×40), Portugael (×11), Disraeli (×4), Zachariae (×3)...
    Ces noms NE prennent PAS la ligature æ — c'est la graphie correcte de
    ces patronymes (Rolin-Jaequemyns est l'un des fondateurs de l'Institut).
    La règle æ est donc désactivée pour ce corpus.
    Elle est documentée ci-dessous pour adaptation à d'autres corpus.

Approche technique — pourquoi PAS texte.split() / ' '.join() :
    L'approche naïve (séparer sur les espaces, corriger chaque token,
    rejoindre avec ' ') détruit irrémédiablement les sauts de ligne.
    Sur ce corpus : 4 919 paragraphes → 0 (texte aplati en une seule ligne).
    
    Solution : re.sub() avec une fonction de remplacement. La regex cible
    les mots contenant "oe" en contexte, la fonction vérifie le lexique
    et retourne le mot corrigé ou l'original. Le reste du texte (espaces,
    sauts de ligne, ponctuation hors mot) est préservé tel quel.

Lexique intégré (LEXIQUE_OE) :
    Contient toutes les formes "oe" → "œ" attestées dans ce corpus.
    Format : { 'forme_sans_ligature': 'forme_avec_ligature' }
    Toutes les formes sont en minuscules ; la casse est restaurée
    dynamiquement lors du remplacement (voir corriger_ligatures()).

Exceptions (EXCEPTIONS_OE) :
    Mots avec "oe" qui NE prennent PAS de ligature française :
    - Mots français courants : poésie, moelle, coefficient...
    - Noms propres germaniques : Loening, Koenig, Goettingue...
    - Artefacts OCR : personoe, coeurl...
    - Mots anglais : does...

Résultats sur le corpus de référence (jette) :
    oeuvre/oeuvres  ×35  →  œuvre/œuvres
    voeu/voeux      ×26  →  vœu/vœux
    moeurs          × 8  →  mœurs
    coeur/coeurs    × 4  →  cœur/cœurs
    soeur/soeurs    × 2  →  sœur/sœurs
    oeil            × 1  →  œil
    oequo           × 3  →  œquo  (ex bono et œquo)
    Total           ×79  corrections, 0 faux positif
    Idempotent      : ✅

Dépendances :
    - Règles 1 à 13 (normalisations préalables recommandées)
    - Aucune bibliothèque externe nécessaire (uniquement standard)

USAGE :
    python 14_ligatures.py INPUT [-o OUTPUT] [--stats]

ARGUMENTS :
    INPUT                  Fichier d'entrée (texte brut) - OBLIGATOIRE
    -o, --output OUTPUT    Fichier de sortie (optionnel)
                           Défaut: INPUT_ligatures.txt
    --stats                Affiche chaque correction avec son contexte

EXEMPLES :
    python 14_ligatures.py document.txt
    python 14_ligatures.py document.txt --stats
    python 14_ligatures.py data.txt -o propre.txt

Pièges Python et points d'attention :
    1. NE PAS UTILISER split() / join() POUR CORRIGER MOT PAR MOT :
       texte.split() coupe sur tout espace blanc, y compris \n et \n\n.
       ' '.join(mots) réunit avec des espaces simples.
       Résultat : tous les sauts de ligne (et donc tous les paragraphes)
       sont détruits. Utiliser re.sub() avec une fonction à la place.

    2. re.sub() AVEC FONCTION DE REMPLACEMENT :
       re.sub(pattern, fonction, texte) appelle la fonction pour chaque
       correspondance. La fonction reçoit l'objet Match et retourne la
       chaîne de remplacement. Permet une logique conditionnelle :
           def remplacer(match):
               if condition: return version_corrigée
               else: return match.group(0)  # inchangé

    3. PRÉSERVATION DE LA CASSE :
       Le lexique stocke les formes en minuscules.
       Avant de retourner le remplacement, on vérifie :
       - mot entier en majuscules → remplacement en majuscules
       - première lettre majuscule → première lettre majuscule
       - sinon → minuscules (cas normal)

    4. STRIPPING DE PONCTUATION POUR LA RECHERCHE LEXICALE :
       Un mot peut être suivi de ponctuation : "œuvre," "vœu."
       On nettoie la ponctuation finale avant de chercher dans le lexique,
       puis on la réattache après le remplacement.

    5. IDEMPOTENCE :
       "œuvre" ne contient pas "oe" → ne matche pas le pattern.
       Appliquer deux fois donne le même résultat.

    6. POUR ADAPTER CE SCRIPT À UN AUTRE CORPUS :
       a) Lancer le script avec --stats sur le nouveau corpus pour voir
          quels mots contenant "oe" sont présents.
       b) Ajouter les formes manquantes dans LEXIQUE_OE.
       c) Ajouter les noms propres locaux dans EXCEPTIONS_OE.
       d) Pour activer æ : décommenter la section "æ" dans LEXIQUE_AE
          et la passer dans corriger_ligatures().

===============================================================================
"""

import argparse
import re
import sys
from pathlib import Path

# =============================================================================
# PARAMÈTRES CONFIGURABLES
# =============================================================================

# ─────────────────────────────────────────────────────────────────────────────
# LEXIQUE OE → Œ
# Toutes les formes en minuscules. La casse est restaurée dynamiquement.
# Ajouter ici les formes spécifiques au corpus cible.
# ─────────────────────────────────────────────────────────────────────────────
LEXIQUE_OE = {
    # Mots courants
    'oeuvre':   'œuvre',
    'oeuvres':  'œuvres',
    'voeu':     'vœu',
    'voeux':    'vœux',
    'moeurs':   'mœurs',
    'coeur':    'cœur',
    'coeurs':   'cœurs',
    'soeur':    'sœur',
    'soeurs':   'sœurs',
    'oeil':     'œil',
    'oeuf':     'œuf',
    'oeufs':    'œufs',
    'noeud':    'nœud',
    'noeuds':   'nœuds',
    'boeuf':    'bœuf',
    'boeufs':   'bœufs',
    'choeur':   'chœur',
    'choeurs':  'chœurs',
    # Termes latins présents dans ce corpus
    'oequo':    'œquo',   # "ex bono et œquo" — formule juridique latine
}

# ─────────────────────────────────────────────────────────────────────────────
# LEXIQUE AE → Æ
# Désactivé pour ce corpus (tous les 'ae' sont des noms propres flamands).
# Décommenter et compléter pour un corpus contenant des termes latins.
# ─────────────────────────────────────────────────────────────────────────────
LEXIQUE_AE = {
    # Exemples de formes latines (absentes de ce corpus) :
    # 'aequo':   'æquo',
    # 'aether':  'æther',
    # 'aedile':  'ædile',
}

# ─────────────────────────────────────────────────────────────────────────────
# EXCEPTIONS OE — mots avec "oe" qui NE prennent PAS de ligature
# ─────────────────────────────────────────────────────────────────────────────
EXCEPTIONS_OE = {
    # Mots français sans ligature
    'poesie', 'poeme', 'poete', 'poetes', 'poemes',
    'noel', 'noels',
    'moelle', 'moelleux', 'moellon', 'moellons',
    'coefficient', 'coefficients',
    'coexistence', 'coexistences', 'coexister',
    # Noms propres germaniques (Allemagne, Autriche, Scandinavie)
    # "oe" est une transcription de ö/ø dans ces langues, pas une ligature fr.
    'loening', 'koenig', 'koenigs', 'warnkoenig',
    'goettingue', 'goettingen', 'goettinger',
    'oesterreich',  # Autriche en allemand
    'oelde',        # ville allemande (OElde dans le corpus)
    'malmoe',       # Malmö (ville suédoise)
    'schroeder',
    # Noms propres néerlandais/flamands avec "oe" non ligaturé
    'boeken', 'daartoe', 'toelating', 'proefschrift', 'redevoering',
    # Artefacts OCR (ne pas corriger une erreur par une autre)
    'personoe', 'personaoe', 'coeurl',
    # Mots anglais ou autres langues
    'does',
}

ENCODAGE_LECTURE = 'utf-8'
ENCODAGE_LECTURE_FALLBACK = 'latin1'
ENCODAGE_ECRITURE = 'utf-8'
# =============================================================================


# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def corriger_ligatures(texte: str) -> tuple:
    r"""
    Restaure les ligatures œ dans le texte par substitution regex.

    Args:
        texte (str): Texte d'entrée

    Returns:
        tuple: (texte_corrigé: str, nb_corrections: int, détails: list[dict])

    Algorithme :
        re.sub() avec une fonction de remplacement parcourt le texte
        en préservant tous les caractères non-correspondants (espaces,
        sauts de ligne, ponctuation). La fonction est appelée pour chaque
        mot contenant "oe" et décide si la substitution est applicable.

    Note sur la préservation de la casse :
        Le lexique stocke les formes en minuscules ("oeuvre" → "œuvre").
        Avant de retourner le remplacement, on vérifie trois cas :
        - "OEUVRE" (tout majuscules) → "ŒUVRE"
        - "Oeuvre" (initiale majuscule) → "Œuvre"
        - "oeuvre" (tout minuscules) → "œuvre"

    Note sur la ponctuation :
        La ponctuation finale d'un mot ("vœu." "cœur,") est nettoyée
        avant la recherche lexicale, puis réattachée après le remplacement.
    """
    details = []
    corrections = [0]  # liste pour permettre la modification dans la closure

    def remplacer_oe(match):
        r"""Fonction appelée pour chaque mot contenant 'oe'."""
        mot_brut = match.group(0)
        mot_lower = mot_brut.lower()

        # Nettoyer la ponctuation finale pour la recherche lexicale
        mot_clean = mot_lower.rstrip('.,;:!?()[]{}«»"\'')
        ponctuation = mot_lower[len(mot_clean):]

        # Ne pas corriger si le mot est dans les exceptions
        if mot_clean in EXCEPTIONS_OE:
            return mot_brut

        # Chercher dans le lexique
        if mot_clean not in LEXIQUE_OE:
            return mot_brut

        cible = LEXIQUE_OE[mot_clean]

        # Restaurer la casse du mot original
        if mot_brut.isupper():
            cible_casee = cible.upper()
        elif mot_brut[0].isupper():
            cible_casee = cible[0].upper() + cible[1:]
        else:
            cible_casee = cible

        corrections[0] += 1
        details.append({
            'avant': mot_brut,
            'apres': cible_casee + ponctuation,
        })
        return cible_casee + ponctuation

    # Pattern : mot contenant "oe" (insensible à la casse) + ponctuation optionnelle
    # \b...\b : frontières de mot
    # [.,;:!?()\[\]{}«»"']* : ponctuation finale optionnelle
    pattern = r'\b\w*[oO][eE]\w*\b[.,;:!?()\[\]{}\xab\xbb"\']*'
    result = re.sub(pattern, remplacer_oe, texte)

    # Enrichir les détails avec le contexte
    pos_courante = 0
    details_avec_ctx = []
    for d in details:
        idx = texte.find(d['avant'], pos_courante)
        if idx >= 0:
            ctx = texte[max(0, idx-25):idx+25].replace('\n', '↵')
            ligne = texte[:idx].count('\n') + 1
            details_avec_ctx.append({**d, 'contexte': ctx, 'ligne': ligne})
            pos_courante = idx + 1
        else:
            details_avec_ctx.append({**d, 'contexte': '', 'ligne': 0})

    return result, corrections[0], details_avec_ctx


def compter_candidats(texte: str) -> dict:
    r"""
    Compte les occurrences corrigeables avant traitement.

    Args:
        texte (str): Texte à analyser

    Returns:
        dict: Statistiques par forme
    """
    stats = {}
    for forme_sans in LEXIQUE_OE:
        # Chercher la forme sans ligature (insensible à la casse)
        n = len(re.findall(r'\b' + re.escape(forme_sans) + r'\b', texte, re.I))
        if n > 0:
            stats[forme_sans] = n
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
    6.  Application des corrections
    7.  Affichage des détails (si --stats)
    8.  Écriture du résultat
    9.  Fin du traitement
    """

    # -------------------------------------------------------------------------
    # BLOC 1 : CONFIGURATION DU PARSER D'ARGUMENTS
    # -------------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        description=r"""
RÈGLE 14 : RESTAURATION DE LA LIGATURE Œ

Restaure la ligature œ dans les mots français courants où l'OCR a produit
"oe" à la place. Lexique intégré, pas de dépendance externe.
""",
        epilog=r"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                            1. FONCTION DÉTAILLÉE                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Corrige les mots du lexique intégré (LEXIQUE_OE en tête du script) :       ║
║  oeuvre→œuvre  voeu→vœu  moeurs→mœurs  coeur→cœur  soeur→sœur             ║
║  voeux→vœux    oeil→œil  oeuf→œuf      noeud→nœud  oequo→œquo             ║
║                                                                               ║
║  Préserve les exceptions (EXCEPTIONS_OE) :                                   ║
║  noms germaniques (Loening, Koenig, Goettingue...)                          ║
║  mots sans ligature (coefficient, coexistence, moelle...)                  ║
║  artefacts OCR (personoe, coeurl...)                                        ║
║                                                                               ║
║  Ligature æ : désactivée (tous les "ae" de ce corpus sont des noms         ║
║  propres flamands — Jaequemyns, Portugael... — qui ne prennent pas æ).     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                               2. EXEMPLES                                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  "oeuvre"         →  "œuvre"                                                 ║
║  "ex bono et oequo" → "ex bono et œquo"                                      ║
║  "Koenig"         →  "Koenig"  (exception : nom germanique)                 ║
║  "coefficient"    →  "coefficient"  (pas de ligature)                       ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                            3. RÉSULTATS CORPUS                                ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  79 corrections sur le corpus Annuaire IDI (jette), 0 faux positif          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                          4. PIÈGES PYTHON À ÉVITER                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  1. NE PAS utiliser split()/join() : détruit les sauts de ligne (§).        ║
║     Utiliser re.sub() avec une fonction de remplacement.                    ║
║                                                                               ║
║  2. re.sub() avec fonction : appelée pour chaque match, retourne soit       ║
║     la correction soit match.group(0) (inchangé) selon le lexique.         ║
║                                                                               ║
║  3. Casse : lexique en minuscules, casse restaurée dynamiquement.           ║
║     OEUVRE → ŒUVRE  /  Oeuvre → Œuvre  /  oeuvre → œuvre                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # -------------------------------------------------------------------------
    # BLOC 2 : DÉFINITION DES ARGUMENTS
    # -------------------------------------------------------------------------
    parser.add_argument('input', help="Fichier d'entrée (texte brut) - OBLIGATOIRE")
    parser.add_argument('-o', '--output',
                        help="Fichier de sortie - Défaut: INPUT_ligatures.txt")
    parser.add_argument('--stats', action='store_true',
                        help="Affiche chaque correction avec son contexte")

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
        suffix = "_ligatures"
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
    stats_avant = compter_candidats(texte)
    total_avant = sum(stats_avant.values())
    print(f"   Total caractères     : {len(texte):,}")
    print(f"   Candidats détectés   : {total_avant}")
    for forme, n in sorted(stats_avant.items(), key=lambda x: -x[1]):
        print(f"      {forme:15s} → {LEXIQUE_OE[forme]:15s} × {n}")

    # -------------------------------------------------------------------------
    # BLOC 7 : APPLICATION DES CORRECTIONS
    # -------------------------------------------------------------------------
    print("🔄 Restauration des ligatures œ...")
    texte_corrige, total, details = corriger_ligatures(texte)

    if total > 0:
        print(f"   ✅ {total} correction(s) effectuée(s)")
    else:
        print("   ℹ️  Aucune modification nécessaire")

    # -------------------------------------------------------------------------
    # BLOC 8 : AFFICHAGE DES DÉTAILS (--stats)
    # -------------------------------------------------------------------------
    if args.stats and details:
        print("\n   Détail des corrections :")
        for d in details:
            print(f"      L{d['ligne']:5d} | {repr(d['avant']):15s} → "
                  f"{repr(d['apres']):15s} | {repr(d['contexte'])}")

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
