r"""
===============================================================================
RÈGLE 8 : AJOUT DES POINTS AUX ABRÉVIATIONS
===============================================================================

Description :
    Ajoute un point après les abréviations courantes qui en sont dépourvues.
    Cette opération normalise les abréviations selon les conventions
    typographiques françaises.


    Ce script est l'un des plus délicats du pipeline. L'idée de départ
    semble simple : "ajouter un point après les abréviations connues".
    Mais beaucoup d'abréviations courtes sont aussi des mots courants 
    ou peuvent surgir dans le cas d'une OCR.
    
    Certaines règles ont donc été écartées 
    
    ❌ 't' → 't.' (pour corriger t 2, abréviation de tome 2)
       Déclenche sur des espaces OCR dans les mots coupés.
       Ex: "essentiellemen t" (OCR) → "essentiellemen t." (faux)
       Et sur les constructions verbales : "n'a-t-il" → "n'a-t.il"
    
    ❌ 'p' (seul) → 'p.' (pour corriger p 3, abréviation de page 3)
       Déclenche sur des lettres isolées dans les notes de bas de page
       et les mots étrangers. 
    

    
    Une abréviation d'une ou deux lettres ne peut être
    traitée de façon sûre que si on vérifie son contexte immédiat.
    Les règles sécurisées de ce script utilisent des lookahead pour
    vérifier que l'abréviation est suivie d'un chiffre ou d'un signe
    typographique caractéristique (°, tiret de nom propre...).

Fonctions :
    Groupe 1 — Titres et civilités (sûrs, jamais ambigus dans ce corpus) :
    - M → M.   (Monsieur, devant nom propre)
    - MM → MM. (Messieurs)
    - Dr → Dr. (Docteur)
    - Mgr → Mgr. (Monseigneur)
    - Mme → Mme. (Madame, si manquant)
    - Mlle → Mlle. (Mademoiselle, si manquant)
    - Mlles → Mlles. (Mesdemoiselles, si manquant)
    
    Groupe 2 — Références bibliographiques (sécurisées par contexte numérique) :
    - pp → pp.     (pages, devant chiffre ou virgule)
    - p devant chiffre → p. (page)
    - vol devant chiffre → vol. (volume)
    - t devant chiffre romain → t. (tome)
    - n° → n.°     (numéro, le ° suit directement le n)
    - art devant chiffre/§ → art. (article)
    
    Groupe 3 — Latin et divers (sûrs, formes fixes) :
    - etc → etc.   (et cetera)
    - cf → cf.     (confer)
    - ibid → ibid. (ibidem)
    - id → id.     (idem)
    - op cit → op cit. (opere citatum)

    
    Groupe 4 — Noms propres géographiques :
    - St- → St.- (Saint-, devant tiret de nom propre)

Exemples :
    Entrée :  "MM Asser et Bluntschli"   Sortie :  "MM. Asser et Bluntschli"
    Entrée :  "M de Parieu"              Sortie :  "M. de Parieu"
    Entrée :  "Dr Dupont"                Sortie :  "Dr. Dupont"
    Entrée :  "pp 438-552"               Sortie :  "pp. 438-552"
    Entrée :  "art 5 du traité"          Sortie :  "art. 5 du traité"
    Entrée :  "n° 59"                    Sortie :  "n.° 59"
    Entrée :  "etc, il a publié"         Sortie :  "etc. il a publié"
    Entrée :  "St-Pétersbourg"           Sortie :  "St.-Pétersbourg"

Risque : Faible 
    Les règles sont sécurisées de deux façons :
    1. Les titres (M, MM, Dr...) ne peuvent pas être confondus avec
       des mots courants dans ce contexte (ils précèdent des noms propres).
    2. Les abréviations bibliographiques courtes (p, t, n, vol, art)
       ne sont appliquées que devant un chiffre ou un signe typographique
       spécifique — ce qui rend les faux positifs quasi-impossibles.
    
    Faux positifs résiduels possibles :
    - "M" devant un mot commençant par une minuscule qui n'est pas
      un titre : rare sur corpus juridique XIXe.
    - "St-" dans un contexte qui n'est pas un hagiotoponyme :
      quasi-absent de ce corpus.
    
    Idempotence : appliquer deux fois donne le même résultat.

Dépendances :
    - Règles 1 à 7 (normalisations préalables recommandées)
    - Aucune bibliothèque externe nécessaire (uniquement standard)

USAGE :
    python 08_abrev.py INPUT [-o OUTPUT] [--stats] [--custom FICHIER]

ARGUMENTS :
    INPUT                  Fichier d'entrée (texte brut) - OBLIGATOIRE
    -o, --output OUTPUT    Fichier de sortie (optionnel)
                           Défaut: INPUT_abrev.txt
    --stats                Affiche le détail des abréviations trouvées
    --custom FICHIER       Fichier d'abréviations supplémentaires (une par ligne)
                           Format : une abréviation par ligne, sans le point final
                           Lignes commençant par # ignorées (commentaires)

EXEMPLES :
    python 08_abrev.py document.txt --stats
    python 08_abrev.py document.txt --custom mes_abrev.txt
    python 08_abrev.py data.txt -o propre.txt

Pièges Python et points d'attention :
    1. ORDRE DES RÈGLES : les abréviations longues avant les courtes.
       Si on traite "M" avant "MM", "MM" serait d'abord partiellement
       transformé : "MM" → "M.M" au lieu de "MM."
       Solution : tri par longueur décroissante dans prepare_abbreviations().
    
    2. LOOKAHEAD NÉGATIF (?!\\\.) :
       Empêche d'ajouter un point si l'abréviation en a déjà un.
       Sans cette assertion, "M." deviendrait "M.." (doublon).
    
    3. LOOKBEHIND NÉGATIF (?<!\\\w) :
       Empêche de capturer l'abréviation à l'intérieur d'un mot.
       Exemple : sans (?<!\\\w), "Dr" dans "Adresse" serait capturé.
    
    4. RÈGLES CONTEXTUELLES (lookahead positif) :
       Pour les abréviations courtes (p, t, n, vol, art), on ajoute
       un lookahead positif vérifiant ce qui suit :
       - (?=\\\s+\\\d) : suivi d'une espace puis d'un chiffre
       - (?=°)     : suivi directement du signe °
       - (?=-)     : suivi directement d'un tiret
       Ce contexte élimine presque tous les faux positifs.
    
    5. ABRÉVIATIONS AVEC ESPACE ('op cit', 'loc cit') :
       re.escape() gère correctement l'espace dans ces chaînes.
       Le motif produit : r'op\\ cit' qui matche bien "op cit".
    

===============================================================================
r"""

import argparse
import re
import sys
from pathlib import Path

# =============================================================================
# PARAMÈTRES CONFIGURABLES
# =============================================================================

# ─────────────────────────────────────────────────────────────────────────────
# GROUPE 1 : Abréviations de titres et civilités
# Sûres : dans un texte français du XIXe, ces séquences ne sont jamais
# des mots courants. "M" seul devant un nom propre ne peut être que
# "Monsieur". "Dr" ne peut être que "Docteur".
# ─────────────────────────────────────────────────────────────────────────────
ABREVIATIONS_TITRES = [
    'Mlles',   # Mesdemoiselles  — en premier car contient 'Mlle'
    'Mlle',    # Mademoiselle    — avant 'M'
    'Mme',     # Madame          — avant 'M'
    'MM',      # Messieurs       — avant 'M'
    'Mgr',     # Monseigneur     — avant 'M'
    'Dr',      # Docteur
    'M',       # Monsieur        — en dernier du groupe pour éviter captures partielles
]

# ─────────────────────────────────────────────────────────────────────────────
# GROUPE 2 : Abréviations bibliographiques SÉCURISÉES PAR CONTEXTE
# Ces règles n'agissent que si l'abréviation est immédiatement suivie
# d'un chiffre, d'un chiffre romain, ou d'un signe typographique
# caractéristique. Cela élimine les faux positifs sur les mots courants.
#
# Format : (pattern_regex, remplacement, description)
# ─────────────────────────────────────────────────────────────────────────────
ABREVIATIONS_BIBLIO_CONTEXTUELLES = [
    # pp (pages) — devant chiffre : "pp 438" → "pp. 438"
    # Placé avant 'p' pour éviter que "pp" soit traité comme deux "p"
    (r'(?<!\w)(pp)(?=[ \t]+\d)(?!\.)',       r'\1.', 'pp devant chiffre'),
    # p (page) — devant chiffre : "p 582" → "p. 582"
    (r'(?<!\w)(p)(?=[ \t]+\d)(?!\.)',        r'\1.', 'p devant chiffre'),
    # vol (volume) — devant chiffre ou romain : "vol 3" → "vol. 3"
    (r'(?<!\w)(vol)(?=[ \t]+[\dIVXLCDM])(?!\.)', r'\1.', 'vol devant chiffre'),
    # t (tome) — devant chiffre romain uniquement : "t VI" → "t. VI"
    # On cible les chiffres romains car 't' devant un arabe serait trop ambigu
    (r'(?<!\w)(t)(?=[ \t]+(?:I{1,3}|IV|VI{0,3}|IX|X{1,3}|XI{0,3}|XIV|XIX|XX{0,3})\b)(?!\.)',
     r'\1.', 't devant chiffre romain'),
    # art (article) — devant chiffre ou § : "art 5" → "art. 5"
    (r'(?<!\w)(art)(?=[ \t]+[\d§])(?!\.)',   r'\1.', 'art devant chiffre/§'),
    # n° (numéro) — le ° suit directement : "n°" → "n.°"
    (r'(?<!\w)(n)(?=°)(?!\.)',               r'\1.', 'n devant °'),
]

# ─────────────────────────────────────────────────────────────────────────────
# GROUPE 3 : Abréviations latines et formules fixes
# Ces formes sont suffisamment spécifiques pour être traitées sans contexte.
# ─────────────────────────────────────────────────────────────────────────────
ABREVIATIONS_LATIN = [
    'loc cit',   # loco citato  — avant 'loc' simple
    'op cit',    # opere citato — avant 'op' simple
    'ibid',      # ibidem
    'etc',       # et cetera
    'cf',        # confer
    'id',        # idem
]

# ─────────────────────────────────────────────────────────────────────────────
# GROUPE 4 : Noms propres géographiques
# St- devant un tiret = Saint- dans un hagiotoponyme (St-Pétersbourg...)
# On n'ajoute le point QUE devant le tiret pour éviter les confusions.
# ─────────────────────────────────────────────────────────────────────────────
ABREVIATIONS_GEO = [
    # Format (pattern, remplacement, description)
    (r'(?<!\w)(St)(?=-)(?!\.)', r'\1.', 'St devant tiret (hagiotoponyme)'),
]

ENCODAGE_LECTURE = 'utf-8'
ENCODAGE_LECTURE_FALLBACK = 'latin1'
ENCODAGE_ECRITURE = 'utf-8'
# =============================================================================


# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def load_custom_abbreviations(custom_file: str) -> list:
    r"""
    Charge des abréviations supplémentaires depuis un fichier texte.
    
    Args:
        custom_file (str): Chemin vers le fichier
        
    Returns:
        list: Liste des abréviations (sans points)
        
    Format du fichier :
        Une abréviation par ligne.
        Les lignes commençant par # sont des commentaires ignorés.
        Les lignes vides sont ignorées.
        
    Exemple de fichier :
        # Abréviations spécifiques au corpus
        Sté    # Société
        Cie    # Compagnie
        Univ   # Université
    r"""
    abbreviations = []
    try:
        with open(custom_file, 'r', encoding='utf-8') as f:
            for line in f:
                # strip() supprime les espaces et sauts de ligne
                line = line.strip()
                # Ignorer les commentaires et les lignes vides
                if line and not line.startswith('#'):
                    # Supprimer les commentaires en fin de ligne
                    line = line.split('#')[0].strip()
                    if line:
                        abbreviations.append(line)
        print(f"   ✅ {len(abbreviations)} abréviation(s) chargée(s) depuis {custom_file}")
    except FileNotFoundError:
        print(f"⚠️  Fichier non trouvé : {custom_file}")
    except Exception as e:
        print(f"⚠️  Erreur lors du chargement de {custom_file} : {e}")
    return abbreviations


def build_simple_pattern(abbr: str) -> str:
    r"""
    Construit le pattern regex pour une abréviation simple (sans contexte).
    
    Args:
        abbr (str): L'abréviation à traiter (ex: "MM", "Dr", "etc")
        
    Returns:
        str: Le pattern regex correspondant
        
    Note sur la construction :
        (?<!\w)  : lookbehind négatif — pas de caractère alphanumérique avant
                   Empêche de capturer l'abréviation à l'intérieur d'un mot.
                   Ex : sans ça, "Dr" dans "Adresse" serait capturé.
        
        re.escape(abbr) : échappe les caractères spéciaux regex dans l'abréviation.
                   Nécessaire pour "op cit" (l'espace doit être échappé).
        
        (?!\.)   : lookahead négatif — pas de point juste après.
                   Empêche d'ajouter un point si l'abréviation en a déjà un.
                   Ex : "M." ne devient pas "M.."
        
        (?!\w)   : lookahead négatif — pas de caractère alphanumérique après.
                   Empêche de capturer l'abréviation au milieu d'un mot.
    r"""
    escaped = re.escape(abbr)
    # (?!\.) : pas de point déjà présent (évite le doublon "M..")
    # (?!\w) : pas de caractère alphanumérique juste après (évite les mots)
    # Note : on n'exclut PAS la virgule — "etc.," est typographiquement
    # acceptable en français (le point d'abréviation tient lieu de point final,
    # la virgule indique la suite de la phrase).
    return rf'(?<!\w)({escaped})(?!\.)(?!\w)'


def normalize_abbreviations(text: str, custom_abbr: list = None) -> str:
    r"""
    Applique toutes les corrections d'abréviations au texte.
    
    Args:
        text (str): Texte d'entrée
        custom_abbr (list): Abréviations supplémentaires (sans point)
        
    Returns:
        str: Texte avec abréviations normalisées
        
    Pipeline de traitement (ordre important) :
        1. Abréviations contextuelles bibliographiques (pp, p, vol, t, art, n)
           → Traitées en premier car leurs patterns sont précis
        2. Abréviations géographiques (St-)
           → Avant les titres pour éviter conflits
        3. Titres et civilités (Mlles, Mlle, Mme, MM, Mgr, Dr, M)
           → Triés par longueur décroissante pour éviter captures partielles
        4. Abréviations latines (loc cit, op cit, ibid, etc, cf, id)
           → Les longues avant les courtes
        5. Abréviations personnalisées (fichier --custom)
           → En dernier pour permettre des surcharges
        
    Note sur le tri par longueur :
        "Mlles" doit être traité avant "Mlle" qui doit l'être avant "M".
        Si on traitait "M" en premier, "MM" serait transformé en "M.M"
        au lieu de "MM.". Le tri par longueur décroissante garantit
        que les formes les plus longues sont capturées en premier.
    r"""
    result = text

    # --- Étape 1 : abréviations contextuelles (pattern déjà complet) ---
    for pattern, replacement, _ in ABREVIATIONS_BIBLIO_CONTEXTUELLES:
        result = re.sub(pattern, replacement, result)

    # --- Étape 2 : abréviations géographiques ---
    for pattern, replacement, _ in ABREVIATIONS_GEO:
        result = re.sub(pattern, replacement, result)

    # --- Étape 3 : titres (ordre fixé dans la liste, long→court) ---
    for abbr in ABREVIATIONS_TITRES:
        pattern = build_simple_pattern(abbr)
        result = re.sub(pattern, r'\1.', result)

    # --- Étape 4 : latin (op cit et loc cit avant cf et id) ---
    latin_tries = sorted(ABREVIATIONS_LATIN, key=len, reverse=True)
    for abbr in latin_tries:
        pattern = build_simple_pattern(abbr)
        result = re.sub(pattern, r'\1.', result)

    # --- Étape 5 : abréviations personnalisées ---
    if custom_abbr:
        # Tri par longueur décroissante pour les mêmes raisons
        for abbr in sorted(custom_abbr, key=len, reverse=True):
            pattern = build_simple_pattern(abbr)
            result = re.sub(pattern, r'\1.', result)

    return result


def count_abbreviations(text: str, custom_abbr: list = None) -> dict:
    r"""
    Compte les abréviations présentes avec et sans point.
    
    Args:
        text (str): Texte à analyser
        custom_abbr (list): Abréviations supplémentaires
        
    Returns:
        dict: Statistiques détaillées
        
    Note sur la conception :
        On compte séparément les formes "avec point" et "sans point"
        pour que les stats avant/après traitement soient comparables.
        La clé 'sans_point' diminuera après normalize_abbreviations().
    r"""
    stats = {'total': 0, 'avec_point': 0, 'sans_point': 0, 'details': {}}

    # Toutes les abréviations simples (titres + latin + custom)
    toutes = (list(ABREVIATIONS_TITRES)
              + list(ABREVIATIONS_LATIN)
              + (custom_abbr or []))
    toutes = sorted(set(toutes), key=len, reverse=True)

    for abbr in toutes:
        escaped = re.escape(abbr)
        sans = len(re.findall(rf'(?<!\w){escaped}(?!\.)(?!\w)', text))
        avec = len(re.findall(rf'(?<!\w){escaped}\.', text))
        if sans > 0 or avec > 0:
            stats['details'][abbr] = {'sans_point': sans, 'avec_point': avec}
            stats['sans_point'] += sans
            stats['avec_point'] += avec
            stats['total'] += sans + avec

    # Abréviations contextuelles (on compte seulement les "sans point")
    for pattern, _, label in ABREVIATIONS_BIBLIO_CONTEXTUELLES + ABREVIATIONS_GEO:
        sans = len(re.findall(pattern, text))
        if sans > 0:
            stats['details'][label] = {'sans_point': sans, 'avec_point': 0}
            stats['sans_point'] += sans
            stats['total'] += sans

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
    3.  Chargement des abréviations personnalisées
    4.  Préparation des chemins de fichiers
    5.  Lecture du fichier
    6.  Statistiques avant traitement
    7.  Application de la normalisation
    8.  Statistiques après traitement
    9.  Écriture du résultat
    10. Fin du traitement
    r"""

    # -------------------------------------------------------------------------
    # BLOC 1 : CONFIGURATION DU PARSER D'ARGUMENTS
    # -------------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        description=r"""
RÈGLE 8 : AJOUT DES POINTS AUX ABRÉVIATIONS

Ajoute un point après les abréviations courantes qui en sont dépourvues.
Seules les abréviations sans risque de faux positif sont traitées.
r""",
        epilog=r"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         1. ABRÉVIATIONS TRAITÉES                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Titres et civilités (sûrs) :                                                 ║
║  M→M.  MM→MM.  Dr→Dr.  Mgr→Mgr.  Mme→Mme.  Mlle→Mlle.  Mlles→Mlles.       ║
║                                                                               ║
║  Références bibliographiques (sécurisées par contexte) :                     ║
║  pp→pp.  p+chiffre→p.  vol+chiffre→vol.  t+romain→t.                        ║
║  art+chiffre/§→art.  n°→n.°                                                  ║
║                                                                               ║
║  Latin et formules fixes :                                                    ║
║  etc→etc.  cf→cf.  ibid→ibid.  id→id.  op cit→op cit.  loc cit→loc cit.    ║
║                                                                               ║
║  Géographie :                                                                 ║
║  St-→St.- (Saint- devant tiret dans les hagiotoponymes)                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                               3. EXEMPLES                                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  "MM Asser et Bluntschli"  →  "MM. Asser et Bluntschli"                      ║
║  "M de Parieu"             →  "M. de Parieu"                                 ║
║  "Dr Dupont"               →  "Dr. Dupont"                                   ║
║  "pp 438-552"              →  "pp. 438-552"                                  ║
║  "art 5 du traité"         →  "art. 5 du traité"                             ║
║  "n° 59"                   →  "n.° 59"                                       ║
║  "etc, il a publié"        →  "etc. il a publié"                             ║
║  "St-Pétersbourg"          →  "St.-Pétersbourg"                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                          4. PIÈGES PYTHON À ÉVITER                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  1. ORDRE : traiter les abréviations longues avant les courtes.              ║
║     "MM" avant "M" — sinon "MM" → "M.M" au lieu de "MM."                   ║
║                                                                               ║
║  2. (?!\.) : empêche le doublon "M.." si déjà normalisé.                    ║
║                                                                               ║
║  3. (?<!\w) et (?!\w) : isolent l'abréviation du reste du mot.             ║
║                                                                               ║
║  4. RÈGLES CONTEXTUELLES : pour les abréviations courtes (p, t, n...),     ║
║     toujours vérifier ce qui suit avec un lookahead positif.                ║
║     Ne jamais traiter une lettre isolée sans ancrage contextuel.            ║
╚══════════════════════════════════════════════════════════════════════════════╝
r""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # -------------------------------------------------------------------------
    # BLOC 2 : DÉFINITION DES ARGUMENTS
    # -------------------------------------------------------------------------
    parser.add_argument('input', help="Fichier d'entrée (texte brut) - OBLIGATOIRE")
    parser.add_argument('-o', '--output',
                        help="Fichier de sortie - Défaut: INPUT_abrev.txt")
    parser.add_argument('--stats', action='store_true',
                        help="Affiche le détail des abréviations trouvées")
    parser.add_argument('--custom',
                        help="Fichier d'abréviations supplémentaires (une par ligne)")

    # -------------------------------------------------------------------------
    # BLOC 3 : ANALYSE DES ARGUMENTS
    # -------------------------------------------------------------------------
    args = parser.parse_args()

    # -------------------------------------------------------------------------
    # BLOC 4 : CHARGEMENT DES ABRÉVIATIONS PERSONNALISÉES
    # -------------------------------------------------------------------------
    custom_abbr = []
    if args.custom:
        custom_abbr = load_custom_abbreviations(args.custom)

    # -------------------------------------------------------------------------
    # BLOC 5 : PRÉPARATION DES CHEMINS DE FICHIERS
    # -------------------------------------------------------------------------
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Erreur : le fichier {input_path} n'existe pas")
        sys.exit(1)

    if args.output:
        output_path = Path(args.output)
    else:
        suffix = "_abrev"
        try:
            output_path = input_path.with_stem(input_path.stem + suffix)
        except AttributeError:
            output_path = input_path.with_name(
                input_path.stem + suffix + input_path.suffix)

    # -------------------------------------------------------------------------
    # BLOC 6 : LECTURE DU FICHIER D'ENTRÉE
    # -------------------------------------------------------------------------
    print(f"📖 Lecture de {input_path}...")
    try:
        with open(input_path, 'r', encoding=ENCODAGE_LECTURE) as f:
            text = f.read()
        print(f"   Encodage utilisé : {ENCODAGE_LECTURE}")
    except UnicodeDecodeError:
        print(f"⚠️  Échec avec {ENCODAGE_LECTURE}, "
              f"tentative avec {ENCODAGE_LECTURE_FALLBACK}...")
        try:
            with open(input_path, 'r', encoding=ENCODAGE_LECTURE_FALLBACK) as f:
                text = f.read()
            print(f"   Encodage utilisé : {ENCODAGE_LECTURE_FALLBACK}")
        except Exception as e:
            print(f"❌ Erreur de lecture : {e}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Erreur inattendue : {e}")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # BLOC 7 : STATISTIQUES AVANT TRAITEMENT
    # -------------------------------------------------------------------------
    stats_avant = count_abbreviations(text, custom_abbr)
    print(f"   Total caractères    : {len(text):,}")
    print(f"   Abréviations totales : {stats_avant['total']}")
    print(f"      Avec point       : {stats_avant['avec_point']}")
    print(f"      Sans point       : {stats_avant['sans_point']}  ← à corriger")

    if args.stats and stats_avant['sans_point'] > 0:
        print("   Détail (sans point seulement) :")
        for abbr, counts in sorted(stats_avant['details'].items(),
                                   key=lambda x: -x[1]['sans_point']):
            if counts['sans_point'] > 0:
                print(f"      {abbr:12s} : {counts['sans_point']:4d} sans point"
                      f"  {counts['avec_point']:4d} avec")

    # -------------------------------------------------------------------------
    # BLOC 8 : APPLICATION DE LA NORMALISATION
    # -------------------------------------------------------------------------
    print("🔄 Application de la normalisation des abréviations...")
    normalized = normalize_abbreviations(text, custom_abbr)

    # -------------------------------------------------------------------------
    # BLOC 9 : STATISTIQUES APRÈS TRAITEMENT
    # -------------------------------------------------------------------------
    stats_apres = count_abbreviations(normalized, custom_abbr)
    # Points ajoutés = différence de taille (chaque correction ajoute 1 char)
    points_ajoutes = len(normalized) - len(text)

    if points_ajoutes > 0:
        print(f"   ✅ {points_ajoutes} point(s) ajouté(s)")
    else:
        print("   ℹ️  Aucune modification nécessaire")

    # -------------------------------------------------------------------------
    # BLOC 10 : ÉCRITURE DU FICHIER DE SORTIE
    # -------------------------------------------------------------------------
    print(f"💾 Écriture de {output_path}...")
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding=ENCODAGE_ECRITURE) as f:
            f.write(normalized)
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
    # BLOC 11 : FIN DU TRAITEMENT
    # -------------------------------------------------------------------------
    print("✅ Terminé avec succès")
    return 0


# =============================================================================
# POINT D'ENTRÉE
# =============================================================================
if __name__ == "__main__":
    sys.exit(main())
