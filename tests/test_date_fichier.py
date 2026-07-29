"""Tests du paramètre de date par fichier (demande utilisatrice du 22/07/2026).

Interface non technique multiplateforme : un fichier « date.txt » à la racine du projet,
contenant JJ-MM-AAAA. Tout ce qui n'est pas une date valide → date du jour (la veille ne
s'arrête jamais pour ça). Depuis l'évolution du 22/07/2026, le fichier reste EN
PERMANENCE dans le dossier : son contenu est vidé à chaque lancement (jamais supprimé),
et il est recréé vide s'il manque.
"""

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import date_depuis_fichier, vider_fichier_date


class TestDateDepuisFichier(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dossier = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _ecrire(self, contenu: str, encodage: str = "utf-8"):
        (self.dossier / "date.txt").write_text(contenu, encoding=encodage)

    def test_date_valide(self):
        self._ecrire("22-07-2026")
        self.assertEqual(date_depuis_fichier(self.dossier), date(2026, 7, 22))

    def test_espaces_et_retour_ligne_toleres(self):
        self._ecrire("  22-07-2026\r\n")            # fin de ligne Windows
        self.assertEqual(date_depuis_fichier(self.dossier), date(2026, 7, 22))

    def test_bom_notepad_tolere(self):
        self._ecrire("22-07-2026", encodage="utf-8-sig")
        self.assertEqual(date_depuis_fichier(self.dossier), date(2026, 7, 22))

    def test_fichier_absent(self):
        self.assertIsNone(date_depuis_fichier(self.dossier))

    def test_fichier_vide_etat_nominal(self):
        """Le fichier vidé en fin de lancement est l'état courant : date du jour, sans bruit."""
        self._ecrire("   \n")
        self.assertIsNone(date_depuis_fichier(self.dossier))

    def test_format_invalide(self):
        self._ecrire("2026-07-22")                  # AAAA-MM-JJ : réservé à --date
        self.assertIsNone(date_depuis_fichier(self.dossier))
        self._ecrire("demain")
        self.assertIsNone(date_depuis_fichier(self.dossier))

    def test_date_inexistante(self):
        self._ecrire("30-02-2026")
        self.assertIsNone(date_depuis_fichier(self.dossier))

    def test_vidage_a_chaque_lancement_sans_suppression(self):
        """Le contenu est vidé, le fichier reste en place (évolution du 22/07/2026)."""
        self._ecrire("22-07-2026")
        vider_fichier_date(self.dossier)
        self.assertTrue((self.dossier / "date.txt").exists())
        self.assertEqual((self.dossier / "date.txt").read_text(encoding="utf-8"), "")

    def test_date_txt_recree_vide_si_absent(self):
        """Aucun fichier : date.txt est (re)créé vide, prêt pour la prochaine saisie."""
        vider_fichier_date(self.dossier)
        self.assertTrue((self.dossier / "date.txt").exists())
        self.assertEqual((self.dossier / "date.txt").read_text(encoding="utf-8"), "")


if __name__ == "__main__":
    unittest.main()
