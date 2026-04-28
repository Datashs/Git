"""
t2_llm_verify.py
================
Deuxième étape du traitement de la table des matières (TdM).

RÔLE
----
Ce script soumet la TdM nettoyée (produite par t1_extract_toc.py et
éventuellement corrigée manuellement) à un modèle de langue (LLM) dont
le seul rôle est de SIGNALER des anomalies probables — pas de les corriger.

La distinction entre signalement et correction est délibérée et importante :
- Le LLM peut détecter des incohérences que la relecture humaine laisse passer
  (numéros de page non croissants, artefacts OCR sur les chiffres, titres
  manifestement tronqués).
- Mais il peut aussi se tromper ou sur-signaler. La décision de corriger
  reste donc humaine, après lecture du rapport produit par ce script.

Ce script ne modifie pas le fichier d'entrée. Il produit uniquement un
rapport textuel (toc_verification.txt) listant les anomalies détectées.

POSITION DANS LA CHAÎNE
------------------------
  t1_extract_toc.py  →  [correction manuelle]  →  t2_llm_verify.py
                                                         ↓
                                               toc_verification.txt
                                                         ↓
                                          [corrections si signalement]
                                                         ↓
                                           t3_llm_structure.py

ENTRÉE / SORTIE
---------------
Entrée  : toc_cleaned.txt (ou toc_corrected.txt si correction manuelle faite)
Sortie  : toc_verification.txt — rapport d'anomalies, format texte lisible

CLÉS API ET FOURNISSEUR LLM
----------------------------
Les clés API et le choix du fournisseur sont lus depuis un fichier .env
situé dans le répertoire courant ou un répertoire parent.
Ne jamais mettre une clé directement dans ce script.

Copier .env.example en .env et renseigner les valeurs :
  LLM_PROVIDER=anthropic        # ou : openai
  ANTHROPIC_API_KEY=sk-ant-...
  ANTHROPIC_MODEL=claude-opus-4-5
  # OPENAI_API_KEY=sk-...
  # OPENAI_MODEL=gpt-4o

USAGE
-----
  python t2_llm_verify.py <fichier_toc> [fichier_rapport]

  Exemple :
    python t2_llm_verify.py toc_cleaned.txt toc_verification.txt

  Si fichier_rapport est omis, le rapport est écrit dans toc_verification.txt
  dans le même répertoire que le fichier d'entrée.

DÉPENDANCES
-----------
  pip install python-dotenv anthropic
  # ou, si fournisseur OpenAI :
  pip install python-dotenv openai
"""

import os
import sys
from pathlib import Path

# python-dotenv charge les variables depuis le fichier .env sans qu'on ait
# à les exporter manuellement dans le shell. C'est la façon standard de
# gérer les secrets dans les projets Python : le .env est local à la machine,
# listé dans .gitignore, et ne voyage jamais dans le dépôt.
from dotenv import load_dotenv


# ══════════════════════════════════════════════════════════════════════════════
# PARAMÈTRES
# Toutes les constantes configurables sont ici. Pour adapter ce script à un
# autre contexte (autre corpus, autre fournisseur LLM, autre langue), c'est
# cette section qu'on modifie en priorité.
# ══════════════════════════════════════════════════════════════════════════════

# Chargement du fichier .env. load_dotenv() cherche .env dans le répertoire
# courant, puis remonte dans les répertoires parents. Si le fichier n'existe
# pas, les variables d'environnement système sont utilisées (ce qui permet
# de faire tourner le script dans un environnement CI/CD où les secrets sont
# injectés directement dans l'environnement).
load_dotenv()

# ── Fournisseur LLM ──────────────────────────────────────────────────────────
# Valeurs acceptées : "anthropic" | "openai"
# Ajouter un nouveau fournisseur = ajouter un bloc elif dans appeler_llm()
# et les variables correspondantes dans .env.example.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower()

# ── Identifiants Anthropic ───────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
# claude-opus-4-5 est le modèle le plus capable d'Anthropic au moment de
# l'écriture de ce script. Pour une tâche de vérification (pas de génération
# complexe), claude-haiku-4-5 serait suffisant et beaucoup moins coûteux.
# Le choix du modèle est un compromis qualité / coût à ajuster selon le corpus.
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-5")

# ── Identifiants OpenAI ──────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# gpt-4o offre un bon équilibre qualité / coût pour cette tâche.
# gpt-3.5-turbo serait suffisant pour la détection d'anomalies simples.
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# ── Paramètres de la requête LLM ─────────────────────────────────────────────
# Nombre maximum de tokens dans la réponse du LLM.
# Le rapport de vérification est court (liste d'anomalies) : 1000 tokens
# sont largement suffisants. Augmenter si le corpus est très long et que
# le LLM tronque son rapport.
MAX_TOKENS_REPONSE = 1000

# Nombre de tokens approximatif au-delà duquel on tronque le texte d'entrée
# avant de l'envoyer au LLM. La plupart des modèles acceptent 100 000+ tokens
# en contexte, mais une TdM fait rarement plus de 2 000 tokens — cette limite
# est une sécurité pour les corpus exceptionnellement longs.
MAX_TOKENS_ENTREE = 8000

# Nombre approximatif de mots par token (approximation raisonnable pour le
# français ; utilisé uniquement pour estimer la taille avant envoi).
MOTS_PAR_TOKEN = 0.75


# ══════════════════════════════════════════════════════════════════════════════
# VALIDATION DES PARAMÈTRES
# On vérifie immédiatement au démarrage que les clés nécessaires sont
# présentes. Cela évite de lancer un traitement long pour échouer à la
# dernière étape sur une erreur d'authentification.
# ══════════════════════════════════════════════════════════════════════════════

def valider_configuration():
    """
    Vérifie que le fournisseur LLM est reconnu et que la clé API
    correspondante est renseignée.

    On effectue cette vérification au démarrage, avant toute lecture de
    fichier, pour que l'utilisateur reçoive un message d'erreur clair
    plutôt qu'une exception cryptique de la bibliothèque API.
    """
    fournisseurs_connus = {"anthropic", "openai"}

    if LLM_PROVIDER not in fournisseurs_connus:
        print(
            f"Erreur : fournisseur LLM inconnu : '{LLM_PROVIDER}'.\n"
            f"Valeurs acceptées : {', '.join(sorted(fournisseurs_connus))}.\n"
            f"Vérifiez LLM_PROVIDER dans votre fichier .env."
        )
        sys.exit(1)

    if LLM_PROVIDER == "anthropic" and not ANTHROPIC_API_KEY:
        print(
            "Erreur : ANTHROPIC_API_KEY manquante.\n"
            "Créez un fichier .env à partir de .env.example\n"
            "et renseignez votre clé API Anthropic.\n"
            "Votre clé est disponible sur : https://console.anthropic.com/"
        )
        sys.exit(1)

    if LLM_PROVIDER == "openai" and not OPENAI_API_KEY:
        print(
            "Erreur : OPENAI_API_KEY manquante.\n"
            "Créez un fichier .env à partir de .env.example\n"
            "et renseignez votre clé API OpenAI.\n"
            "Votre clé est disponible sur : https://platform.openai.com/"
        )
        sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════════
# APPEL LLM
# ══════════════════════════════════════════════════════════════════════════════

def appeler_llm(prompt: str) -> str:
    """
    Envoie un prompt au LLM configuré et retourne le texte de la réponse.

    Cette fonction isole toute la logique spécifique à chaque fournisseur.
    Le reste du script est identique quel que soit le fournisseur choisi :
    il construit un prompt, appelle cette fonction, et lit le texte retourné.

    POURQUOI CETTE ISOLATION ?
    Chaque fournisseur a sa propre bibliothèque Python et sa propre structure
    de réponse. Anthropic retourne reponse.content[0].text ; OpenAI retourne
    reponse.choices[0].message.content. En isolant ces différences ici, on
    évite que la logique métier du script soit polluée par des détails
    d'implémentation API.

    AJOUTER UN NOUVEAU FOURNISSEUR
    Ajouter un bloc `elif LLM_PROVIDER == "nouveau_fournisseur":` ici,
    importer la bibliothèque correspondante, et adapter la structure
    d'appel. Le prompt et la lecture du résultat dans le reste du script
    n'ont pas à changer.

    Paramètre
    ---------
    prompt : str
        Texte complet à envoyer au modèle, incluant les instructions
        et le contenu à analyser.

    Retourne
    --------
    str : texte brut de la réponse du modèle.
    """
    if LLM_PROVIDER == "anthropic":
        # Import local : on n'importe que si le fournisseur est effectivement
        # utilisé, évitant une erreur d'import si la bibliothèque n'est pas
        # installée pour un fournisseur non utilisé.
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        reponse = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=MAX_TOKENS_REPONSE,
            messages=[{"role": "user", "content": prompt}]
        )
        return reponse.content[0].text

    elif LLM_PROVIDER == "openai":
        import openai
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        reponse = client.chat.completions.create(
            model=OPENAI_MODEL,
            max_tokens=MAX_TOKENS_REPONSE,
            messages=[{"role": "user", "content": prompt}]
        )
        return reponse.choices[0].message.content

    # Ce cas ne devrait pas se produire si valider_configuration() a été
    # appelée, mais on le garde comme filet de sécurité.
    raise ValueError(f"Fournisseur non géré : '{LLM_PROVIDER}'")


# ══════════════════════════════════════════════════════════════════════════════
# CONSTRUCTION DU PROMPT
# ══════════════════════════════════════════════════════════════════════════════

def construire_prompt(texte_toc: str) -> str:
    """
    Construit le prompt envoyé au LLM pour la vérification de la TdM.

    PRINCIPES DE CONCEPTION DU PROMPT
    -----------------------------------
    Un bon prompt de vérification doit être :

    1. CONSERVATEUR : le LLM doit signaler, pas corriger. Si on lui demande
       de corriger directement, il introduit des corrections silencieuses
       qu'on ne verra pas. Le rapport de signalement laisse la décision à
       l'humain.

    2. EXPLICITE SUR LE CONTEXTE : le LLM ne connaît pas ce corpus. On lui
       dit que c'est un annuaire juridique du XIXe siècle, que les numéros
       de page sont des entiers croissants entre 1 et 400 environ, que les
       chiffres romains désignent des pages préliminaires. Sans ce contexte,
       il risque de signaler comme anomalies des choses qui sont normales.

    3. PRÉCIS SUR LE FORMAT DE SORTIE : on veut une liste de signalements,
       pas un texte narratif. Chaque signalement cite la ligne exacte,
       décrit le problème, et indique une correction probable. Ce format
       est plus facile à parcourir et à exploiter.

    4. EXPLICITE SUR CE QU'IL NE FAUT PAS SIGNALER : sans cette précision,
       le LLM tend à sur-signaler (ponctuation variable, abréviations) et
       à sous-signaler (vrais problèmes numériques). On lui dit explicitement
       d'ignorer la ponctuation variable et les abréviations.

    TRONCATURE DU TEXTE
    -------------------
    Si la TdM est très longue, on la tronque avant envoi pour rester dans
    les limites de tokens raisonnables. En pratique, une TdM d'annuaire
    fait rarement plus de 500 lignes (environ 3 000 mots), bien en deçà
    des limites actuelles des modèles. La troncature est une sécurité.
    """
    # Estimation approximative de la taille du texte en tokens
    nb_mots = len(texte_toc.split())
    nb_tokens_estimes = int(nb_mots / MOTS_PAR_TOKEN)

    texte_a_envoyer = texte_toc
    note_troncature = ""

    if nb_tokens_estimes > MAX_TOKENS_ENTREE:
        # Tronquer en conservant le début (les premières entrées sont souvent
        # les plus structurellement importantes : parties, sections principales)
        mots_max = int(MAX_TOKENS_ENTREE * MOTS_PAR_TOKEN)
        texte_a_envoyer = " ".join(texte_toc.split()[:mots_max])
        note_troncature = (
            f"\n[Note : le texte a été tronqué à {mots_max} mots "
            f"sur {nb_mots} pour respecter les limites de contexte.]"
        )

    prompt = f"""Tu analyses la table des matières d'un annuaire juridique \
du XIXe siècle (Institut de droit international, publications Gallica/BnF).

Ce texte a été extrait par OCR puis nettoyé partiellement. Il peut contenir \
des erreurs résiduelles. Il a également été corrigé manuellement sur les \
problèmes les plus visibles.

TON RÔLE EST UNIQUEMENT DE SIGNALER des anomalies probables, pas de les \
corriger. La décision de correction reste humaine.

CONTEXTE DU CORPUS
- Annuaire juridique, fin XIXe siècle, en français
- Les numéros de page sont des entiers, croissants de 1 à environ 390
- Les chiffres romains (v, xiii, xvii...) désignent des pages préliminaires \
(avant-propos, additions) et sont normaux
- La hiérarchie est : Parties (Première, Deuxième...) > Sections (I, II, III) \
> Sous-sections (A, B, C ou 1, 2, 3) > Entrées fines (noms propres, mois)
- Les noms propres suivent la forme "Nom (Prénom)" ou "Nom (Prénom Initiale.)"
- Les points de conduite (......) séparent le titre du numéro de page

CE QU'IL FAUT SIGNALER
- Numéros de page non croissants ou manifestement erronés \
(ex: 165 suivi de 101 — probable OCR de 161)
- Titres qui semblent tronqués (commencent par une minuscule, \
une virgule, ou une conjonction isolée)
- Lignes qui ne ressemblent pas à des entrées de TdM \
(lignes de tirets, numéros isolés, artefacts)
- Doublons manifestes (même titre, même page)
- Fautes OCR visibles sur les chiffres \
(0 pour O, 1 pour l, 5 pour S, etc.)
- Entrées dont le numéro de page semble absent

CE QU'IL NE FAUT PAS SIGNALER
- La ponctuation variable (point final présent ou absent)
- Les abréviations et sigles (N°, pp., R.D.I., etc.)
- Les titres longs ou complexes qui sont syntaxiquement corrects
- Les numéros de page en chiffres romains pour les pages préliminaires
- Les légères irrégularités typographiques sans impact sur le sens

FORMAT DE RÉPONSE
Produire une liste numérotée de signalements. Chaque signalement contient :
  - La ligne exacte concernée (citée entre guillemets)
  - La nature du problème
  - Une correction probable (formulée comme hypothèse, pas comme certitude)

Si aucune anomalie n'est détectée, répondre simplement :
  "Aucune anomalie détectée."

Ne pas produire de texte introductif ni de conclusion.{note_troncature}

TABLE DES MATIÈRES À VÉRIFIER
------------------------------
{texte_a_envoyer}
------------------------------"""

    return prompt


# ══════════════════════════════════════════════════════════════════════════════
# FORMATAGE DU RAPPORT
# ══════════════════════════════════════════════════════════════════════════════

def formater_rapport(
    reponse_llm: str,
    fichier_source: str,
    fournisseur: str,
    modele: str,
    nb_lignes_toc: int
) -> str:
    """
    Enveloppe la réponse brute du LLM dans un rapport structuré.

    Le rapport inclut des métadonnées (fichier source, modèle utilisé,
    date) qui permettent de tracer l'origine de chaque vérification.
    Cela est utile quand on traite plusieurs volumes ou qu'on compare
    les résultats de deux modèles différents sur le même corpus.
    """
    from datetime import datetime
    horodatage = datetime.now().strftime("%Y-%m-%d %H:%M")

    return (
        f"RAPPORT DE VÉRIFICATION — TABLE DES MATIÈRES\n"
        f"{'=' * 50}\n"
        f"Fichier source : {fichier_source}\n"
        f"Fournisseur    : {fournisseur} ({modele})\n"
        f"Lignes TdM     : {nb_lignes_toc}\n"
        f"Généré le      : {horodatage}\n"
        f"{'=' * 50}\n\n"
        f"{reponse_llm.strip()}\n\n"
        f"{'─' * 50}\n"
        f"Ce rapport est produit par un LLM et peut contenir des erreurs.\n"
        f"Chaque signalement doit être vérifié manuellement avant correction.\n"
        f"Le fichier source n'a pas été modifié par ce script.\n"
    )


# ══════════════════════════════════════════════════════════════════════════════
# POINT D'ENTRÉE
# ══════════════════════════════════════════════════════════════════════════════

def main():
    # ── Validation de la configuration ──────────────────────────────────────
    # On valide avant de lire les fichiers : inutile de charger des données
    # si la clé API est absente.
    valider_configuration()

    # ── Lecture des arguments ────────────────────────────────────────────────
    if len(sys.argv) < 2:
        print(
            "Usage : python t2_llm_verify.py <fichier_toc> [fichier_rapport]\n"
            "Exemple : python t2_llm_verify.py toc_cleaned.txt"
        )
        sys.exit(1)

    chemin_source = Path(sys.argv[1])
    if not chemin_source.exists():
        print(f"Erreur : fichier introuvable : {chemin_source}")
        sys.exit(1)

    if len(sys.argv) >= 3:
        chemin_rapport = Path(sys.argv[2])
    else:
        chemin_rapport = chemin_source.parent / "toc_verification.txt"

    # ── Lecture du fichier TdM ───────────────────────────────────────────────
    texte_toc = chemin_source.read_text(encoding="utf-8")
    lignes_toc = [l for l in texte_toc.splitlines() if l.strip()]
    nb_lignes = len(lignes_toc)

    print(f"Fichier chargé : {chemin_source} ({nb_lignes} lignes non vides)")
    print(f"Fournisseur    : {LLM_PROVIDER}")
    print(f"Modèle         : {ANTHROPIC_MODEL if LLM_PROVIDER == 'anthropic' else OPENAI_MODEL}")
    print("Envoi au LLM en cours...")

    # ── Construction et envoi du prompt ─────────────────────────────────────
    prompt = construire_prompt(texte_toc)
    reponse = appeler_llm(prompt)

    # ── Formatage et écriture du rapport ────────────────────────────────────
    modele_utilise = (
        ANTHROPIC_MODEL if LLM_PROVIDER == "anthropic" else OPENAI_MODEL
    )
    rapport = formater_rapport(
        reponse_llm=reponse,
        fichier_source=str(chemin_source),
        fournisseur=LLM_PROVIDER,
        modele=modele_utilise,
        nb_lignes_toc=nb_lignes
    )

    chemin_rapport.write_text(rapport, encoding="utf-8")

    # ── Affichage console ────────────────────────────────────────────────────
    print(f"\nRapport écrit : {chemin_rapport}")
    print("\n── Aperçu du rapport ───────────────────────────────")
    # On affiche les 20 premières lignes du rapport pour vérification rapide
    for ligne in rapport.splitlines()[:20]:
        print(f"  {ligne}")
    if len(rapport.splitlines()) > 20:
        print(f"  ... ({len(rapport.splitlines()) - 20} lignes supplémentaires)")
    print("────────────────────────────────────────────────────")


if __name__ == "__main__":
    main()
