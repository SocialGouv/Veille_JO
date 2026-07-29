"""Validation hors ligne (règle « sans clés », §6 du plan) : produit les sorties du
28/05/2026 depuis la fixture de l'annexe E, sans clé API ni réseau.

Usage : python tests/generer_depuis_fixture.py
Sorties : sorties/veille_jo_2026-05-28.xlsx (E6) — à passer à compare_cible.py (E7) —
et sorties/corps_mail_2026-05-28.html (E8, rendu du mail sans Outlook ni navigateur).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "fixtures"))

import logging

from export import exporter
from fixture_annexe_e import resultat_consolide_28_05
from notification import corps_html, ecrire_fichier_html


def principal() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s — %(message)s")
    resultat = resultat_consolide_28_05()
    chemin_excel = exporter(resultat)
    chemin_html = ecrire_fichier_html(corps_html(resultat), resultat.date_jo)
    print(f"\nExcel généré depuis la fixture annexe E : {chemin_excel}")
    print(f"Corps de mail HTML (gabarit §5.2)        : {chemin_html}")
    print("Recette : python tests/compare_cible.py "
          f"{chemin_excel.relative_to(Path.cwd()) if chemin_excel.is_relative_to(Path.cwd()) else chemin_excel} "
          "tests/fixtures/veille_jo_2026-05-28_CIBLE.xlsx")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
