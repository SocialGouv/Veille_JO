"""Tests hors ligne d'`extraction.py` (E1) : fonctions pures + client mocké.

Le run réel sur le 28/05/2026 exige des clés PISTE.
"""

import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import extraction


def _ms(d: date) -> int:
    """Timestamp millisecondes d'une date locale à midi (comme `datePubli`)."""
    return int(datetime(d.year, d.month, d.day, 12, 0).timestamp() * 1000)


class TestFonctionsPures(unittest.TestCase):
    def test_trouver_jo_par_date(self):
        conteneurs = [
            {
                "id": "JORFCONT2",
                "titre": "JO du 29/05/2026",
                "datePubli": _ms(date(2026, 5, 29)),
            },
            {
                "id": "JORFCONT1",
                "titre": "JO du 28/05/2026",
                "datePubli": _ms(date(2026, 5, 28)),
            },
        ]
        jo = extraction.trouver_jo(conteneurs, date(2026, 5, 28))
        self.assertEqual(jo["id"], "JORFCONT1")

    def test_trouver_jo_absent(self):
        conteneurs = [{"id": "X", "datePubli": _ms(date(2026, 5, 29))}]
        self.assertIsNone(
            extraction.trouver_jo(conteneurs, date(2026, 5, 31))
        )  # dimanche

    def test_lister_textes_sommaire_recursif_et_deduplique(self):
        arbre = {
            "structure": {
                "items": [
                    {"id": "JORFTEXT000054144856", "titre": "Avis VGENFLI"},
                    {
                        "sections": [
                            {
                                "id": "JORFTEXT000054144858",
                                "title": "Avis DABIGATRAN/OXAZEPAM",
                            },
                            {"id": "SECTION1", "titre": "pas un texte"},
                            {
                                "id": "JORFTEXT000054144856",
                                "titre": "doublon à ignorer",
                            },
                        ]
                    },
                ]
            }
        }
        textes = extraction.lister_textes_sommaire(arbre)
        self.assertEqual(
            [t[0] for t in textes], ["JORFTEXT000054144856", "JORFTEXT000054144858"]
        )
        self.assertEqual(
            textes[1][1], "Avis DABIGATRAN/OXAZEPAM"
        )  # titre via « title »

    def test_extraire_champs_texte_filtre_et_ordonne(self):
        donnees = {
            "title": "x" * 30,  # champ non ciblé : ignoré
            "content": "A" * 30,
            "annexes": [
                {"html": "B" * 25},
                {"html": "B" * 25},
            ],  # doublon conservé une fois
            "meta": {"texte": "court"},  # ≤ 20 caractères : ignoré
        }
        texte = extraction.extraire_champs_texte(donnees)
        self.assertEqual(texte, "A" * 30 + "\n\n" + "B" * 25)

    def test_url_publique(self):
        self.assertEqual(
            extraction.url_publique("JORFTEXT000054144866"),
            "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000054144866",
        )


class TestClientPiste(unittest.TestCase):
    def _reponse(self, code=200, json_donnees=None):
        reponse = mock.Mock()
        reponse.status_code = code
        reponse.json.return_value = json_donnees or {}
        if code >= 400:
            import requests

            reponse.raise_for_status.side_effect = requests.HTTPError(response=reponse)
        else:
            reponse.raise_for_status.return_value = None
        return reponse

    def test_identifiants_absents(self):
        with self.assertRaises(extraction.ErreurPiste):
            extraction.ClientPiste("", "")

    @mock.patch("extraction.time.sleep")
    @mock.patch("extraction.requests.post")
    def test_retoken_sur_401(self, post, _sleep):
        """Un 401 déclenche un nouveau token puis la relance de l'appel."""
        post.side_effect = [
            self._reponse(json_donnees={"access_token": "T1"}),  # token initial
            self._reponse(code=401),  # appel API : token expiré
            self._reponse(json_donnees={"access_token": "T2"}),  # re-token
            self._reponse(
                json_donnees={
                    "containers": [
                        {
                            "id": "JO1",
                            "titre": "JO",
                            "datePubli": _ms(date(2026, 5, 28)),
                        }
                    ]
                }
            ),
            self._reponse(json_donnees={"id": "JO1"}),  # jorfCont
        ]
        client = extraction.ClientPiste("id", "secret")
        jo, textes = client.sommaire_jo(date(2026, 5, 28))
        self.assertEqual(jo["id"], "JO1")
        self.assertEqual(textes, [])
        jetons = [
            appel.kwargs.get("headers", {}).get("Authorization")
            for appel in post.call_args_list
            if "headers" in appel.kwargs
        ]
        self.assertIn("Bearer T2", jetons)

    @mock.patch("extraction.time.sleep")
    @mock.patch("extraction.requests.post")
    def test_jo_introuvable_message_propre(self, post, _sleep):
        """Une date sans JO (dimanche) lève JoIntrouvable (sous-classe d'ErreurPiste,
        cf. incident du 10/08/2026) avec un message exploitable."""
        post.side_effect = [
            self._reponse(json_donnees={"access_token": "T"}),
            self._reponse(
                json_donnees={
                    "containers": [
                        {
                            "id": "JO1",
                            "titre": "JO",
                            "datePubli": _ms(date(2026, 5, 29)),
                        }
                    ]
                }
            ),
        ]
        client = extraction.ClientPiste("id", "secret")
        with self.assertRaises(extraction.JoIntrouvable) as contexte:
            client.sommaire_jo(date(2026, 5, 31))
        self.assertIsInstance(contexte.exception, extraction.ErreurPiste)
        self.assertIn("JO introuvable", str(contexte.exception))
        self.assertIn("31/05/2026", str(contexte.exception))

    @mock.patch("extraction.time.sleep")
    @mock.patch("extraction.requests.post")
    def test_relances_puis_echec(self, post, sleep):
        """3 tentatives (backoff 2 s) puis ErreurPiste."""
        import requests

        post.side_effect = [
            self._reponse(json_donnees={"access_token": "T"}),
            requests.ConnectionError("réseau"),
            requests.ConnectionError("réseau"),
            requests.ConnectionError("réseau"),
        ]
        client = extraction.ClientPiste("id", "secret")
        with self.assertRaises(extraction.ErreurPiste):
            client._post(config.URL_LAST_JO, {"nbElement": 1})
        self.assertEqual(post.call_count, 1 + config.TENTATIVES_PISTE)
        sleep.assert_called_with(2)


if __name__ == "__main__":
    unittest.main()
