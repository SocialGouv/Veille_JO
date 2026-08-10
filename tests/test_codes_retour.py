"""Tests des codes retour de `main.principal` (incident du 10/08/2026).

Ce jour-là, le JO n'était simplement pas encore publié côté DILA (un lundi ouvré
ordinaire) : `extraction.JoIntrouvable` doit produire un code retour 2, distinct des
vraies pannes (`ErreurPiste` générique, `--date` invalide, exception inattendue), qui
restent en 1. C'est ce qui permet à `publier-pages.yml` de ne pas afficher le job en
échec pour ce cas bénin (voir CLAUDE.md).
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main
from extraction import ErreurPiste, JoIntrouvable


class TestCodesRetourPrincipal(unittest.TestCase):
    def setUp(self):
        # Isole `principal()` de tout effet de bord (log réel, .env, date.txt du dépôt) :
        # seule la correspondance exception → code retour est testée ici.
        for nom, remplacement in [
            ("configurer_journalisation", lambda: Path("dummy.log")),
            ("alerter", mock.Mock()),
            ("date_depuis_fichier", lambda: None),
            ("vider_fichier_date", mock.Mock()),
            ("load_dotenv", mock.Mock()),
        ]:
            patcheur = mock.patch.object(main, nom, remplacement)
            patcheur.start()
            self.addCleanup(patcheur.stop)

    def _avec_executer_qui_leve(self, exception):
        return mock.patch.object(main, "executer", mock.Mock(side_effect=exception))

    def test_jo_introuvable_code_2(self):
        with self._avec_executer_qui_leve(JoIntrouvable("JO introuvable pour la date 10/08/2026")):
            self.assertEqual(main.principal([]), 2)

    def test_autre_echec_piste_code_1(self):
        with self._avec_executer_qui_leve(ErreurPiste("502 Bad Gateway après 3 tentatives")):
            self.assertEqual(main.principal([]), 1)

    def test_date_invalide_code_1(self):
        self.assertEqual(main.principal(["--date", "n'importe quoi"]), 1)

    def test_exception_inattendue_code_1(self):
        with self._avec_executer_qui_leve(RuntimeError("boom")):
            self.assertEqual(main.principal([]), 1)

    def test_succes_code_0(self):
        with mock.patch.object(main, "executer", mock.Mock(return_value=0)):
            self.assertEqual(main.principal([]), 0)


if __name__ == "__main__":
    unittest.main()
