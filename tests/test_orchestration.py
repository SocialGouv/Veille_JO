"""Tests hors ligne de l'orchestration (`main.executer`) : l'enchaînement du pipeline.

PISTE est simulé (aucun appel réseau, aucune clé requise) et les deux étapes de sortie
(`exporter`, `notifier`) sont interceptées : rien n'est écrit sur disque, on observe le
`ResultatVeille` tel qu'il arrive au mail.
"""

import sys
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import main
from extraction import ErreurPiste

DATE_JO = date(2026, 7, 7)

# Avis de prix « neutre » (« les prix sont fixés ») : ni majoration ni baisse dans le
# corps → non orienté, donc « à vérifier » au rapprochement. C'est l'anomalie de
# CONSOLIDATION du scénario, celle qu'une ligne du tableau laisse deviner.
AVIS_NEUTRE = """
<p>Les prix des spécialités visées ci-dessous sont fixés comme suit :</p>
<table>
 <tr><th>N° CIP</th><th>Présentation</th><th>PPTTC</th></tr>
 <tr><td>3400930000005</td><td>PRODUIT NEUTRE 10 mg, comprimé (laboratoires LABO Z)</td><td>12,00 €</td></tr>
</table>
"""

TITRE = "Avis relatif aux prix de spécialités pharmaceutiques"
CHEMIN_EXCEL = Path("veille_jo_2026-07-07.xlsx")  # jamais écrit : `exporter` est simulé


class _ClientPisteFactice:
    """Doublure de `extraction.ClientPiste` : un sommaire figé et des textes au choix.

    `textes[identifiant]` vaut soit le HTML brut, soit une `ErreurPiste` à lever
    (téléchargement en échec), soit "" (contenu vide côté API).
    """

    def __init__(self, sommaire, textes):
        self.sommaire = sommaire
        self.textes = textes
        self.demandes: list[str] = []

    def sommaire_jo(self, _date_cible):
        return {}, list(self.sommaire)

    def texte_integral(self, identifiant):
        self.demandes.append(identifiant)
        contenu = self.textes[identifiant]
        if isinstance(contenu, Exception):
            raise contenu
        return contenu


class TestRecapitulatifDesAnomalies(unittest.TestCase):
    """Les anomalies d'extraction (texte non téléchargé, contenu vide) arrivent EN TÊTE
    du récapitulatif : ce sont les seules qu'aucune ligne du tableau ne laisse deviner
    (§ « Rendus » de TESTS.md). Les anomalies de consolidation les suivent."""

    def setUp(self):
        self.sommaire = [
            ("JORFTEXT000054200001", f"{TITRE} (téléchargement en échec)"),
            ("JORFTEXT000054200002", f"{TITRE} (contenu vide)"),
            ("JORFTEXT000054200003", TITRE),
        ]
        self.client = _ClientPisteFactice(
            self.sommaire,
            {
                "JORFTEXT000054200001": ErreurPiste(
                    "502 Bad Gateway après 3 tentatives"
                ),
                "JORFTEXT000054200002": "   \n  ",
                "JORFTEXT000054200003": AVIS_NEUTRE,
            },
        )
        self.exportes: list = []
        self.notifies: list = []

    def _exporter(self, resultat) -> Path:
        """Tient lieu d'`export.exporter` : rien sur disque, chemin d'Excel figé."""
        self.exportes.append(resultat)
        return CHEMIN_EXCEL

    def _notifier(self, resultat, chemin_excel) -> None:
        """Tient lieu de `notification.notifier` : ni HTML ni Outlook, on garde l'entrée."""
        self.notifies.append((resultat, chemin_excel))

    def _executer(self) -> int:
        # Le référentiel de prix est hors périmètre ici (réseau, cache BDPM) : bascule
        # à False, l'avis neutre reste donc « à vérifier », comme au repli du CEPS.
        with (
            mock.patch.object(main, "ClientPiste", lambda *_: self.client),
            mock.patch.object(config, "ORIENTATION_PRIX_AUTO", False),
            mock.patch.object(main, "exporter", self._exporter),
            mock.patch.object(main, "notifier", self._notifier),
        ):
            return main.executer(DATE_JO)

    def test_anomalies_d_extraction_en_tete_du_recapitulatif(self):
        code = self._executer()

        self.assertEqual(code, 0)  # deux textes perdus ≠ échec du run : le mail part
        (resultat, chemin_excel) = self.notifies[0]
        self.assertEqual(len(self.notifies), 1)
        self.assertEqual(self.exportes, [resultat])  # même objet à l'Excel et au mail
        self.assertEqual(chemin_excel, CHEMIN_EXCEL)

        # Le seul texte exploitable a bien produit sa ligne (et donc son anomalie
        # de consolidation, l'avis n'étant pas orienté).
        self.assertEqual(
            [(l.produit, l.laboratoire) for l in resultat.lignes],
            [("PRODUIT NEUTRE", "LABO Z")],
        )

        self.assertEqual(len(resultat.anomalies), 3)
        extraction_1, extraction_2, consolidation = resultat.anomalies
        self.assertTrue(
            extraction_1.startswith("Texte non analysé (échec de téléchargement) : "),
            extraction_1,
        )
        self.assertIn(
            "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000054200001", extraction_1
        )
        self.assertTrue(
            extraction_2.startswith(
                "Texte au contenu vide côté API, à lire en ligne : "
            ),
            extraction_2,
        )
        self.assertIn(
            "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000054200002", extraction_2
        )
        self.assertTrue(
            consolidation.startswith("PRODUIT NEUTRE : à vérifier — "), consolidation
        )

        # Les trois textes retenus ont été demandés une fois chacun, dans l'ordre du
        # sommaire (la déduplication d'un doublon de sommaire, elle, est du ressort
        # d'`extraction.py` : voir tests/test_extraction.py).
        self.assertEqual(self.client.demandes, [i for i, _ in self.sommaire])


if __name__ == "__main__":
    unittest.main()
