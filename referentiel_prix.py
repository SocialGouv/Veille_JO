"""Référentiel de prix antérieurs — orientation des avis de prix « neutres ».

Constat vérifié sur pièces (29/07/2026, API Légifrance et site public) : la plupart
des avis de prix ne publient ni le sens de la variation ni le prix antérieur, juste
le nouveau prix (« Les prix des spécialités visées ci-dessous sont fixés… »). Le sens
n'est donc calculable que par comparaison à un prix antérieur connu. Deux sources,
toutes deux déterministes et traçables :

1. **l'historique local** (`donnees/historique_prix.csv`) : chaque run archive les
   PPTTC publiés au JO (CIP, date, prix) ; un CIP déjà vu à une date antérieure donne
   la comparaison exacte, sans dépendance externe ;
2. **la BDPM** (Base de données publique des médicaments, licence ouverte) : fichier
   plat CIP-13 → prix public, téléchargé au plus une fois par
   `config.BDPM_MAX_AGE_JOURS` dans `donnees/`. En cas d'échec réseau, le dernier
   fichier téléchargé sert tel quel.

Garde-fous : l'historique (prix du JO, daté) prime sur la BDPM (instantané non daté) ;
prix antérieur introuvable ou égal au nouveau → pas d'orientation (l'avis reste
« à vérifier ») ; aucune erreur ici ne fait échouer la veille — au pire, tout reste
« à vérifier », comme avant.

Validation du 29/07/2026 (prototype sur le JO du 07/07) : 15/17 présentations
appariées, sens conformes aux tableaux du mail manuel du CEPS (AZELASTINE & co. en
hausse, DARUNAVIR en baisse).
"""

import csv
import logging
import re
import time
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import requests

import config

JOURNAL = logging.getLogger("veille_jo.referentiel_prix")

FICHIER_BDPM = "CIS_CIP_bdpm.txt"
FICHIER_HISTORIQUE = "historique_prix.csv"
_COLONNE_CIP13 = 6      # colonnes du fichier BDPM (séparateur tabulation, latin-1)
_COLONNE_PRIX = 9       # « prix du médicament en euro » (public TTC, hors honoraires)


def en_decimal(texte: str) -> Decimal | None:
    """Montant d'une cellule de prix, None si illisible.

    Accepte la décimale à virgule du JO et de la BDPM (« 1 156,38 € ») comme la
    décimale à point de l'historique CSV (« 156.38 ») ; avec virgule, les points
    résiduels sont des séparateurs de milliers.
    """
    trouve = re.search(r"\d(?:[\d\s.,]*\d)?", texte or "")
    if not trouve:
        return None
    brut = trouve.group(0).replace(" ", "")
    if "," in brut:
        brut = brut.replace(".", "").replace(",", ".")
    try:
        return Decimal(brut)
    except InvalidOperation:
        return None


class ReferentielPrix:
    """Prix antérieurs connus par CIP-13 : historique local d'abord, BDPM sinon."""

    def __init__(self, dossier: Path | None = None, telecharger: bool = True):
        self._dossier = Path(dossier) if dossier else Path(__file__).parent / config.DOSSIER_DONNEES
        self._dossier.mkdir(exist_ok=True)
        self._historique: dict[tuple[str, str], Decimal] = {}   # (cip, AAAA-MM-JJ) → prix
        self._historique_modifie = False
        self._bdpm: dict[str, Decimal] = {}
        self._charger_historique()
        if telecharger:
            self._telecharger_bdpm_si_perime()
        self._charger_bdpm()

    # --- BDPM ---------------------------------------------------------------

    def _telecharger_bdpm_si_perime(self) -> None:
        chemin = self._dossier / FICHIER_BDPM
        if chemin.is_file():
            age_jours = (time.time() - chemin.stat().st_mtime) / 86400
            if age_jours < config.BDPM_MAX_AGE_JOURS:
                JOURNAL.info("BDPM en cache (%.1f jour(s)) : pas de re-téléchargement.",
                             age_jours)
                return
        try:
            reponse = requests.get(config.URL_BDPM_CIP, timeout=config.TIMEOUT_BDPM_S)
            reponse.raise_for_status()
            if b"\t" not in reponse.content[:1000]:   # page HTML au lieu du fichier plat
                raise ValueError("réponse sans tabulations (page HTML ?)")
            chemin.write_bytes(reponse.content)
            JOURNAL.info("BDPM téléchargée : %s (%d octets).", chemin, len(reponse.content))
        except Exception as exc:
            # Jamais bloquant : le dernier fichier téléchargé (s'il existe) sert tel quel.
            JOURNAL.warning("Téléchargement BDPM impossible (%s) : %s.", exc,
                            "cache existant conservé" if chemin.is_file()
                            else "orientation limitée à l'historique local")

    def _charger_bdpm(self) -> None:
        chemin = self._dossier / FICHIER_BDPM
        if not chemin.is_file():
            return
        for ligne in chemin.read_text(encoding="latin-1", errors="replace").splitlines():
            champs = ligne.split("\t")
            if len(champs) <= _COLONNE_PRIX:
                continue
            cip = champs[_COLONNE_CIP13].strip()
            if len(cip) != 13 or not cip.isdigit():
                continue
            prix = en_decimal(champs[_COLONNE_PRIX])
            if prix is not None:
                self._bdpm[cip] = prix
        JOURNAL.info("Référentiel BDPM : %d CIP-13 avec prix public.", len(self._bdpm))

    # --- Historique local ----------------------------------------------------

    def _charger_historique(self) -> None:
        chemin = self._dossier / FICHIER_HISTORIQUE
        if not chemin.is_file():
            return
        with chemin.open(encoding="utf-8", newline="") as flux:
            for rang in csv.reader(flux, delimiter=";"):
                if len(rang) != 3 or rang[0] == "cip":
                    continue
                prix = en_decimal(rang[2])
                if prix is not None:
                    self._historique[(rang[0], rang[1])] = prix
        JOURNAL.info("Historique local des prix : %d enregistrement(s).",
                     len(self._historique))

    def enregistrer(self, cip: str, date_jo: date, prix: Decimal) -> None:
        """Archive un prix publié au JO (idempotent pour un même (CIP, date))."""
        cle = (cip, date_jo.isoformat())
        if self._historique.get(cle) != prix:
            self._historique[cle] = prix
            self._historique_modifie = True

    def sauvegarder(self) -> None:
        """Écrit l'historique complet (trié) si de nouveaux prix ont été archivés."""
        if not self._historique_modifie:
            return
        chemin = self._dossier / FICHIER_HISTORIQUE
        with chemin.open("w", encoding="utf-8", newline="") as flux:
            plume = csv.writer(flux, delimiter=";")
            plume.writerow(["cip", "date_jo", "ppttc"])
            for (cip, jour), prix in sorted(self._historique.items()):
                plume.writerow([cip, jour, prix])
        self._historique_modifie = False
        JOURNAL.info("Historique local des prix sauvegardé : %s (%d enregistrement(s)).",
                     chemin, len(self._historique))

    # --- Consultation ---------------------------------------------------------

    def prix_anterieur(self, cip: str, date_jo: date) -> tuple[Decimal, str] | None:
        """(prix antérieur connu, source) pour un CIP, None si inconnu.

        L'historique local (prix du JO, STRICTEMENT antérieur à la date traitée —
        un rejeu du même jour ne se compare jamais à lui-même) prime sur la BDPM
        (instantané, non daté).
        """
        jour = date_jo.isoformat()
        anterieurs = [(j, prix) for (c, j), prix in self._historique.items()
                      if c == cip and j < jour]
        if anterieurs:
            return max(anterieurs)[1], "historique JO"
        if cip in self._bdpm:
            return self._bdpm[cip], "BDPM"
        return None
