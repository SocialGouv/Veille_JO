"""Tests hors ligne de `filtrage.py` (E2) sur des titres plausibles du JORF.

La calibration réelle (les 11 JORFTEXT de l'annexe E retrouvés sur le 28/05/2026)
exige des clés PISTE.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from filtrage import filtrer_textes

# Titres calqués sur les intitulés usuels du JORF (à confronter au run réel, E2).
TITRES_PHARMA = [
    ("JORFTEXT000054144850", "Arrêté du 27 mai 2026 modifiant la liste des spécialités "
                             "pharmaceutiques remboursables aux assurés sociaux"),
    ("JORFTEXT000054144852", "Arrêté du 27 mai 2026 modifiant la liste des spécialités "
                             "pharmaceutiques agréées à l'usage des collectivités et divers "
                             "services publics"),
    ("JORFTEXT000054144866", "Avis relatif aux prix de spécialités pharmaceutiques"),
    ("JORFTEXT000054144868", "Décision du 12 mai 2026 de l'Union nationale des caisses "
                             "d'assurance maladie relative aux taux de participation de "
                             "l'assuré applicables à des spécialités pharmaceutiques"),
    ("JORFTEXT000054144874", "Avis relatif à la majoration du prix de spécialités "
                             "pharmaceutiques"),
    ("JORFTEXT000054144876", "Avis relatif aux baisses de prix de spécialités pharmaceutiques"),
    ("JORFTEXT000054144880", "Avis de tarification relatif à un médicament orphelin"),
    # Cas ajoutés au contrat le 23/07/2026 : LES MCO/SMR, rétrocession, radiation.
    ("JORFTEXT000054144882", "Arrêté du 2 juin 2026 modifiant la liste des spécialités "
                             "pharmaceutiques prises en charge en sus des prestations "
                             "d'hospitalisation mentionnée à l'article L. 162-22-7 du code "
                             "de la sécurité sociale"),
    ("JORFTEXT000054144884", "Arrêté du 21 juillet 2026 modifiant la liste des médicaments "
                             "de la réserve hospitalière mentionnée à l'article L. 5126-6 "
                             "du code de la santé publique"),
    ("JORFTEXT000054144886", "Arrêté du 20 mai 2026 portant radiation de spécialités "
                             "pharmaceutiques de la liste mentionnée à l'article "
                             "L. 162-22-7 du code de la sécurité sociale"),
]

TITRES_HORS_SUJET = [
    ("JORFTEXT000054144900", "Arrêté du 26 mai 2026 portant nomination au conseil "
                             "d'administration de l'Agence nationale"),
    ("JORFTEXT000054144901", "Décret n° 2026-612 relatif aux tarifs de péage autoroutiers"),
    ("JORFTEXT000054144902", "Arrêté du 27 mai 2026 relatif aux prix de vente du tabac"),
    # Incident réel du 05/08/2026 : « spécialité » nu (retiré de MOTS_CLES) attrapait cet
    # arrêté de répartition d'internes en médecine, sans rapport avec le pharma.
    ("JORFTEXT000054618874", "Arrêté du 4 août 2026 fixant le nombre d'étudiants de "
                             "troisième cycle des études de médecine susceptibles d'être "
                             "affectés, par spécialité et par subdivision territoriale au "
                             "titre de l'année universitaire 2026-2027"),
]


class TestFiltrage(unittest.TestCase):
    def test_titres_pharma_retenus(self):
        retenus, ecartes = filtrer_textes(TITRES_PHARMA)
        self.assertEqual(len(retenus), len(TITRES_PHARMA))
        self.assertEqual(ecartes, [])

    def test_titres_hors_sujet_ecartes(self):
        retenus, ecartes = filtrer_textes(TITRES_HORS_SUJET)
        self.assertEqual(retenus, [])
        self.assertEqual(len(ecartes), len(TITRES_HORS_SUJET))

    def test_melange_et_insensibilite_casse(self):
        textes = TITRES_PHARMA + TITRES_HORS_SUJET + [
            ("JORFTEXT000054144999", "AVIS RELATIF AUX PRIX DE SPÉCIALITÉS PHARMACEUTIQUES"),
        ]
        retenus, ecartes = filtrer_textes(textes)
        self.assertEqual(len(retenus), len(TITRES_PHARMA) + 1)
        self.assertEqual(len(ecartes), len(TITRES_HORS_SUJET))
        self.assertIn("JORFTEXT000054144999", [i for i, _ in retenus])


if __name__ == "__main__":
    unittest.main()
