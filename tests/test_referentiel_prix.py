"""Tests hors ligne de `referentiel_prix.py` (orientation des avis neutres, 29/07/2026).

Le téléchargement BDPM réel est hors périmètre (réseau) : les tests écrivent un
fichier BDPM factice dans un dossier temporaire et passent `telecharger=False`.
"""

import sys
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from referentiel_prix import FICHIER_BDPM, FICHIER_HISTORIQUE, ReferentielPrix, en_decimal

# Deux lignes réelles (structure) du fichier CIS_CIP_bdpm.txt : 13 champs, tabulations,
# CIP-13 en 7e position, prix public en 10e, décimales à virgule.
BDPM_FACTICE = (
    "60002283\t4949729\tplaquette(s) de 30\tPrésentation active\tCommercialisée\t"
    "16/03/2011\t3400949497294\toui\t100%\t24,34\t25,36\t1,02\t\n"
    "62626950\t3008493\tplaquette(s) de 60\tPrésentation active\tCommercialisée\t"
    "01/01/2020\t3400930084939\toui\t65%\t160,24\t162,30\t2,06\t\n"
    "LIGNE\tINVALIDE\n"
)


def _referentiel(dossier: Path) -> ReferentielPrix:
    return ReferentielPrix(dossier=dossier, telecharger=False)


class TestEnDecimal(unittest.TestCase):
    def test_formats_reels(self):
        self.assertEqual(en_decimal("156,38 €"), Decimal("156.38"))
        self.assertEqual(en_decimal("3,21"), Decimal("3.21"))
        self.assertEqual(en_decimal("1 156,38 €"), Decimal("1156.38"))
        self.assertEqual(en_decimal("24"), Decimal("24"))
        self.assertIsNone(en_decimal(""))
        self.assertIsNone(en_decimal("N/A"))


class TestReferentiel(unittest.TestCase):
    def setUp(self):
        self.dossier = Path(tempfile.mkdtemp(prefix="veille_ref_"))
        (self.dossier / FICHIER_BDPM).write_text(BDPM_FACTICE, encoding="latin-1")

    def test_bdpm_chargee(self):
        referentiel = _referentiel(self.dossier)
        self.assertEqual(referentiel.prix_anterieur("3400930084939", date(2026, 7, 7)),
                         (Decimal("160.24"), "BDPM"))
        self.assertIsNone(referentiel.prix_anterieur("3400900000000", date(2026, 7, 7)))

    def test_historique_prime_sur_bdpm_et_reste_strictement_anterieur(self):
        referentiel = _referentiel(self.dossier)
        referentiel.enregistrer("3400930084939", date(2026, 7, 1), Decimal("158.00"))
        # Prix du jour traité : jamais comparé à lui-même (rejeu idempotent).
        referentiel.enregistrer("3400930084939", date(2026, 7, 7), Decimal("156.38"))
        self.assertEqual(referentiel.prix_anterieur("3400930084939", date(2026, 7, 7)),
                         (Decimal("158.00"), "historique JO"))
        # À une date ultérieure, le prix du 07/07 devient l'antérieur le plus récent.
        self.assertEqual(referentiel.prix_anterieur("3400930084939", date(2026, 8, 1)),
                         (Decimal("156.38"), "historique JO"))

    def test_sauvegarde_et_rechargement(self):
        referentiel = _referentiel(self.dossier)
        referentiel.enregistrer("3400949497294", date(2026, 7, 7), Decimal("25.98"))
        referentiel.sauvegarder()
        self.assertTrue((self.dossier / FICHIER_HISTORIQUE).is_file())
        recharge = _referentiel(self.dossier)
        self.assertEqual(recharge.prix_anterieur("3400949497294", date(2026, 8, 1)),
                         (Decimal("25.98"), "historique JO"))

    def test_sans_bdpm_ni_historique_jamais_bloquant(self):
        vide = Path(tempfile.mkdtemp(prefix="veille_ref_vide_"))
        referentiel = _referentiel(vide)
        self.assertIsNone(referentiel.prix_anterieur("3400949497294", date(2026, 7, 7)))


if __name__ == "__main__":
    unittest.main()
