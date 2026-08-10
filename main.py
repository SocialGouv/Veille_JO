"""Orchestration de la veille JO « spécialités pharmaceutiques » (CEPS).

Usage : `python main.py [--date AAAA-MM-JJ]` (défaut : aujourd'hui).
Code retour : 0 si la veille a abouti (même « RAS »), 1 en cas d'échec — la tâche
planifiée s'appuie sur ce code pour ses relances automatiques.

Pipeline (§2 du plan, 100 % déterministe) :
extraction PISTE → filtrage par titres → analyse déterministe →
rapprochement 1 ligne par nom de médicament et par laboratoire (contrat du
23/07/2026) → export Excel + notification (brouillon Outlook ou fichier HTML).
Garde-fous : jour sans texte pertinent → mail « RAS » ; JO introuvable ou PISTE
en panne → alerte explicite + code retour 1.
"""

import argparse
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

import config
from analyse import analyser_texte_deterministe
from export import exporter
from extraction import ClientPiste, ErreurPiste, url_publique
from filtrage import filtrer_textes
from notification import alerter, notifier
from rapprochement import ResultatVeille, consolider
from referentiel_prix import ReferentielPrix

JOURNAL = logging.getLogger("veille_jo")


def configurer_journalisation() -> Path:
    """Un fichier de log par exécution (annexe F) + écho console."""
    dossier = Path(__file__).parent / config.DOSSIER_LOGS
    dossier.mkdir(exist_ok=True)
    fichier = dossier / f"veille_{datetime.now():%Y-%m-%d_%H%M%S}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
        handlers=[
            logging.FileHandler(fichier, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    return fichier


def analyser_arguments(argv=None) -> str | None:
    """Lit `--date` (option développeur/recette), texte brut non validé.

    La validation du format est faite par `resoudre_date_argument`, appelée depuis
    `principal` à l'intérieur du bloc try/except : un format invalide doit déclencher
    une alerte comme tout autre échec (§ invariants CLAUDE.md — `main.py` écrit
    toujours un fichier de sortie), pas un `argparse.error()` qui quitterait le
    programme avant même d'écrire quoi que ce soit dans `sorties/`."""
    analyseur = argparse.ArgumentParser(
        description="Veille JO — spécialités pharmaceutiques (CEPS)"
    )
    analyseur.add_argument(
        "--date",
        help="date du JO à traiter — AAAA-MM-JJ de préférence, "
        "mais JJ-MM-AAAA/JJ/MM/AAAA/AAAA/MM/JJ acceptés aussi "
        "(défaut : fichier « date.txt », sinon aujourd'hui)",
    )
    return analyseur.parse_args(argv).date


# Formats acceptés pour --date, testés dans cet ordre (le premier qui correspond
# l'emporte) : le canonique AAAA-MM-JJ d'abord, puis les variantes JJ-MM-AAAA que la
# saisie manuelle (ex. déclenchement du workflow GitHub Actions) confond facilement avec
# le format de `date.txt` — cf. incident du 10/08/2026 où « 10/08/2026 » (JJ/MM/AAAA) a
# fait échouer `main.py` avant même l'écriture d'une alerte. Pas d'ambiguïté JJ/MM contre
# MM/JJ à lever : l'outil est francophone, JJ est toujours en premier dans ces variantes.
FORMATS_DATE_ARGUMENT = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d")


def resoudre_date_argument(valeur: str | None) -> date | None:
    """Convertit le `--date` brut en `date` en essayant `FORMATS_DATE_ARGUMENT` dans
    l'ordre, ou lève `ValueError` (message utilisateur prêt pour l'alerte) si aucun ne
    correspond. None si absent."""
    if not valeur:
        return None
    for format_essaye in FORMATS_DATE_ARGUMENT:
        try:
            resultat = datetime.strptime(valeur, format_essaye).date()
        except ValueError:
            continue
        if format_essaye != "%Y-%m-%d":
            JOURNAL.info(
                "--date « %s » reconnue au format %s (format canonique : AAAA-MM-JJ).",
                valeur,
                format_essaye,
            )
        return resultat
    raise ValueError(
        f"date invalide « {valeur} » (format attendu : AAAA-MM-JJ, "
        "JJ-MM-AAAA, JJ/MM/AAAA ou AAAA/MM/JJ)"
    )


# Interface non technique du choix de date (demande utilisatrice du 22/07/2026) : un
# fichier texte à la racine du projet, contenant JJ-MM-AAAA (ex. « 22-07-2026 »), créable
# sans peine sous Windows/Notepad. Le fichier reste EN PERMANENCE dans le dossier : son
# contenu est vidé en fin de lancement (jamais supprimé), prêt pour la prochaine saisie
# (évolution du 22/07). Seul nom accepté, celui du README, du TUTORIEL et de
# `lancer_veille.bat` : la variante « date » sans extension, jamais documentée, a été
# retirée le 29/07/2026.
FICHIER_DATE = "date.txt"


def date_depuis_fichier(dossier: Path | None = None) -> date | None:
    """Date demandée via le fichier « date.txt », None sinon.

    Fichier vide = état nominal (il est vidé en fin de chaque lancement) → date du
    jour, sans bruit. Tout contenu qui n'est pas une date JJ-MM-AAAA valide (format
    faux, date inexistante comme 30-02-2026) → None avec log explicite : la veille
    passe sur la date du jour, elle ne s'arrête jamais pour ça. Encodage tolérant
    (BOM Notepad, latin-1 en repli) : le fichier vient d'un poste Ubuntu ou Windows.
    """
    dossier = dossier or Path(__file__).parent
    chemin = dossier / FICHIER_DATE
    if not chemin.is_file():
        return None
    try:
        contenu = chemin.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        contenu = chemin.read_text(encoding="latin-1")
    contenu = contenu.strip()
    if not contenu:
        return None  # vide = pas de demande (nominal depuis le 22/07)
    try:
        demandee = datetime.strptime(contenu, "%d-%m-%Y").date()
    except ValueError:
        JOURNAL.warning(
            "Fichier %s : « %s » n'est pas une date JJ-MM-AAAA valide "
            "(ex. 22-07-2026) : la veille passe sur la date du jour.",
            FICHIER_DATE,
            contenu,
        )
        return None
    JOURNAL.info(
        "Date demandée via le fichier %s : %s.",
        FICHIER_DATE,
        demandee.strftime("%d/%m/%Y"),
    )
    return demandee


def vider_fichier_date(dossier: Path | None = None) -> None:
    """Vide le contenu du fichier date SANS le supprimer — à la fin de CHAQUE lancement
    (succès ou échec) : une date posée ne doit jamais rejouer silencieusement le
    lendemain, et le fichier reste en place, prêt pour la prochaine saisie (demande
    utilisatrice du 22/07/2026). Il est recréé vide s'il manque."""
    dossier = dossier or Path(__file__).parent
    chemin = dossier / FICHIER_DATE
    try:
        if not chemin.is_file():
            chemin.write_text("", encoding="utf-8")
            JOURNAL.info(
                "Fichier date.txt créé (vide) : y écrire JJ-MM-AAAA pour "
                "traiter un autre jour."
            )
        elif chemin.stat().st_size > 0:
            chemin.write_text("", encoding="utf-8")
            JOURNAL.info(
                "Fichier %s vidé (nettoyage de fin de lancement) : il reste "
                "en place pour une prochaine date.",
                FICHIER_DATE,
            )
    except (
        OSError
    ) as erreur:  # fichier verrouillé sous Windows : signalé, jamais bloquant
        JOURNAL.warning(
            "Fichier %s non vidé (%s) : effacer son contenu à la main pour "
            "éviter de rejouer cette date demain.",
            FICHIER_DATE,
            erreur,
        )


def executer(date_cible: date) -> int:
    """Déroule le pipeline complet pour une date. Retourne le code de sortie."""
    JOURNAL.info("Veille JO du %s — démarrage.", date_cible.strftime("%d/%m/%Y"))

    # 1. Extraction : sommaire du JO de la date.
    client = ClientPiste(
        os.getenv("PISTE_CLIENT_ID", ""), os.getenv("PISTE_CLIENT_SECRET", "")
    )
    _jo, textes_sommaire = client.sommaire_jo(date_cible)

    # 2. Filtrage par mots-clés sur les titres.
    retenus, _ecartes = filtrer_textes(textes_sommaire)

    if not retenus:
        # Jour sans texte pertinent : le mail « RAS » part quand même (§5.2.5 — l'absence
        # de mail signifie « panne », jamais « rien à signaler »). Pas d'Excel à joindre.
        JOURNAL.info("Aucun texte pharmaceutique ce jour : notification « RAS ».")
        notifier(
            ResultatVeille(date_jo=date_cible, lignes=[], anomalies=[]),
            chemin_excel=None,
        )
        return 0

    # 3. Analyse déterministe — les textes intégraux sont récupérés ici.
    analyses = []
    anomalies_extraction: list[str] = []
    for identifiant, titre in retenus:
        try:
            brut = client.texte_integral(identifiant)
        except ErreurPiste as erreur:
            JOURNAL.error("Texte %s non récupéré : %s", identifiant, erreur)
            anomalies_extraction.append(
                f"Texte non analysé (échec de téléchargement) : "
                f"{titre} — {url_publique(identifiant)}"
            )
            continue
        if not brut.strip():
            JOURNAL.warning("Texte %s vide côté API.", identifiant)
            anomalies_extraction.append(
                f"Texte au contenu vide côté API, à lire en ligne : "
                f"{titre} — {url_publique(identifiant)}"
            )
            continue
        analyses.append(analyser_texte_deterministe(identifiant, titre, brut))

    # 4. Rapprochement : une ligne par nom de médicament et par laboratoire.
    # Référentiel de prix (orientation des avis neutres) : un échec ici n'est jamais
    # bloquant — sans référentiel, ces avis restent « à vérifier », comme avant.
    referentiel = None
    if config.ORIENTATION_PRIX_AUTO:
        try:
            referentiel = ReferentielPrix()
        # Périmètre visé : historique local illisible (OSError), BDPM injoignable
        # (RequestException), contenu inexploitable (ValueError). Un défaut de code du
        # constructeur (AttributeError, TypeError) doit remonter, pas se déguiser en
        # panne réseau.
        except (OSError, ValueError, requests.RequestException) as erreur:
            JOURNAL.warning(
                "Référentiel de prix indisponible (%s) : avis de prix "
                "neutres laissés « à vérifier ».",
                erreur,
            )
    resultat = consolider(analyses, date_cible, referentiel=referentiel)
    if referentiel is not None:
        try:
            referentiel.sauvegarder()
        except OSError as erreur:
            JOURNAL.warning("Historique des prix non sauvegardé : %s", erreur)
    resultat.anomalies[0:0] = anomalies_extraction

    # 5a. Export Excel (sauf si aucune ligne : le mail RAS/anomalies suffit).
    chemin_excel = exporter(resultat) if resultat.lignes else None

    # 5b. Notification (échec mail ≠ échec du run : sorties/ contient tout).
    notifier(resultat, chemin_excel)

    JOURNAL.info(
        "Veille du %s terminée : %d ligne(s), %d anomalie(s), Excel : %s.",
        date_cible.strftime("%d/%m/%Y"),
        len(resultat.lignes),
        len(resultat.anomalies),
        chemin_excel or "aucun (RAS)",
    )
    return 0


def principal(argv=None) -> int:
    """Point d'entrée : journalisation, résolution de la date, pipeline, alerte sur échec.

    Date cible, par priorité : `--date` (développeur/recette) > fichier « date.txt »
    (interface utilisatrice, §0 du README) > date du jour. Le contenu du fichier date
    est vidé en fin de lancement dans TOUS les cas (succès, échec, --date prioritaire) ;
    le fichier lui-même reste en place.
    """
    load_dotenv(Path(__file__).parent / ".env")
    date_arg_brute = analyser_arguments(argv)
    fichier_log = configurer_journalisation()
    JOURNAL.info("Journal de cette exécution : %s", fichier_log)
    date_cible = date.today()
    try:
        date_arg = resoudre_date_argument(date_arg_brute)
        date_fichier = date_depuis_fichier()
        date_cible = date_arg or date_fichier or date.today()
        if date_arg and date_fichier:
            JOURNAL.info(
                "--date fourni : il prime sur le fichier date (qui sera vidé)."
            )
        return executer(date_cible)
    except ErreurPiste as erreur:
        JOURNAL.error("Échec PISTE : %s", erreur)
        alerter(str(erreur), date_cible)
        return 1
    except ValueError as erreur:
        # --date au mauvais format (ex. JJ/MM/AAAA au lieu d'AAAA-MM-JJ) : alerte datée
        # d'aujourd'hui plutôt qu'un `argparse.error()` qui quitterait le programme sans
        # rien écrire dans `sorties/` (voir `resoudre_date_argument`).
        JOURNAL.error("Argument --date invalide : %s", erreur)
        alerter(str(erreur), date_cible)
        return 1
    # Filet de dernier recours volontairement large : il garantit l'alerte et le code
    # retour 1 quoi qu'il arrive (pas de mail = panne). Le type de l'exception va dans
    # l'alerte elle-même, pas seulement dans le log : l'utilisatrice n'ouvre pas `logs/`.
    except Exception as erreur:
        JOURNAL.exception("Échec inattendu de la veille.")
        alerter(f"Erreur inattendue ({type(erreur).__name__}) : {erreur}", date_cible)
        return 1
    finally:
        vider_fichier_date()


if __name__ == "__main__":
    sys.exit(principal())
