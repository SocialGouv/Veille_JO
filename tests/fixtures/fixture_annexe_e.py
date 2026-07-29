"""Vérité terrain du JO du 28/05/2026 (annexe E du plan), sous forme de fixtures Python.

Deux jeux, pour la validation hors ligne prévue par la règle « sans clés » (§6 du plan) :

- `textes_analyses_28_05()` : les textes du 28/05 tels qu'ils sortiraient de l'analyse
  déterministe (E3, indications de section incluses), avec des dénominations brutes
  reprenant les pièges historiques (§7 du plan) — entrée du test de
  `rapprochement.consolider` ;
- `resultat_consolide_28_05()` : les 8 lignes consolidées de l'annexe E — entrée directe
  d'`export.py`, `tests/compare_cible.py` et `notification.py`.

Les indications reprennent la CIBLE à l'identique (y compris ses raccourcis humains,
« Idem que PRADAXA », et ses coquilles) : le volet strict de la recette ne les compare
pas, et le rendu du mail reste fidèle au gabarit. Les identifiants JORFTEXT…800/802 des
arrêtés d'inscription sont FICTIFS : la cible ne référence pas ces arrêtés (ils
n'alimentent que la colonne Liste), leurs vrais ids seront constatés au premier run réel.
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from analyse import ProduitExtrait, TexteAnalyse
from rapprochement import (
    SECTION_BAISSES,
    SECTION_HAUSSES,
    SECTION_INSCRIPTIONS,
    LigneConsolidee,
    ResultatVeille,
)

# Liens (fictifs) des arrêtés d'inscription du 28/05 : la colonne Liste porte un lien
# par segment depuis le 22/07/2026 (« 1 liste = 1 arrêté »).
ID_ARRETE_SS = "JORFTEXT000054144800"
ID_ARRETE_COLLECTIVITES = "JORFTEXT000054144802"

DATE_JO = date(2026, 5, 28)
URL = "https://www.legifrance.gouv.fr/jorf/id/{}"

INDICATIONS_CIBLE = {
    "WEGOVY": "Chez l'adulte en cas d'échec de la prise en charge nutritionnelle bien "
              "conduite […] pour la gestion du poids, incluant la perte de poids et le "
              "maintien du poids",
    "MOUNJARO": "",
    "VGENFLI": "DMLA, Occlusion veineuse centrale de la rétine, Occlusion de branche "
               "veineuse rétiniennen, Œdème maculaire diabétique, Néovascularisation "
               "choroïdienne",
    "DABIGATRAN": "Idem que PRADAXA",
    "OXAZEPAM": "Traitement symptomatique des manifestations anxieuses sévères et/ou "
                "invalidantes \nPrévention et traitement di delirium tremens et des autres "
                "manifestations de sevrage alcoolique.",
    "LIKOZAM": "Traitement symptomatique à court terme (2-4 semaines) de l'anxiété sévère, "
               "invalidante ou responsable d'un état de détresse inacceptable chez l'adulte\n"
               "Traitement de l'épilepsie partielle ou généralisée, en association avec un "
               "autre traitement antiépileptique chez les adultes ou les enfants de plus de "
               "2 ans, en cas d'échec de deux monothérapies consécutives",
}


def _texte(id_court: str, titre: str, type_texte: str, produits, **kwargs) -> TexteAnalyse:
    identifiant = f"JORFTEXT{id_court}"
    return TexteAnalyse(
        id=identifiant,
        url=URL.format(identifiant),
        titre=titre,
        type_texte=type_texte,
        ambigu=False,
        produits=produits,
        texte_nettoye=kwargs.pop("texte_nettoye", f"[SIMULÉ] corps nettoyé de {identifiant}"),
        **kwargs,
    )


def textes_analyses_28_05() -> list[TexteAnalyse]:
    """Les 13 textes du 28/05 (11 JORFTEXT de l'annexe E + 2 arrêtés fictifs), analysés.

    Les dénominations brutes rejouent les pièges historiques : présentations multiples
    (MORPHINE ×6, WEGOVY ×2), laboratoire accolé au nom (DABIGATRAN TEVA, OXAZEPAM ARROW),
    dosages « /ml » (LIKOZAM), parenthèses, mapping laboratoires divergent (LAVOISIER /
    CHAIX ET DU MARAIS).
    """
    # Indications = celles des sections de tableaux (extraction déterministe E3, comme
    # `indication_de_section` les attache depuis la révision du 22/07/2026). MOUNJARO
    # volontairement sans indication de section : « à compléter manuellement » attendu
    # (la cible, elle, l'affiche vide — champ hors volet strict de la recette).
    inscrits_ss = [
        ProduitExtrait("WEGOVY 0,25 mg, solution injectable en stylo prérempli FlexTouch",
                       "NOVO NORDISK", indication=INDICATIONS_CIBLE["WEGOVY"]),
        ProduitExtrait("MOUNJARO 2,5 mg, solution injectable en stylo prérempli KwikPen", "LILLY"),
        ProduitExtrait("VGENFLI 40 mg/ml, solution injectable en seringue préremplie",
                       "FRESENIUS KABI", indication=INDICATIONS_CIBLE["VGENFLI"]),
        ProduitExtrait("DABIGATRAN TEVA 110 mg, gélules", "TEVA",
                       indication=INDICATIONS_CIBLE["DABIGATRAN"]),
        ProduitExtrait("OXAZEPAM ARROW 10 mg, comprimé", "ARROW",
                       indication=INDICATIONS_CIBLE["OXAZEPAM"]),
        ProduitExtrait("LIKOZAM 1 mg/ml, sirop", "ADVICENNE",
                       indication=INDICATIONS_CIBLE["LIKOZAM"]),
    ]
    inscrits_collectivites = [
        ProduitExtrait("WEGOVY 1 mg, solution injectable en stylo prérempli FlexTouch",
                       "NOVO NORDISK", indication=INDICATIONS_CIBLE["WEGOVY"]),
        ProduitExtrait("MOUNJARO 5 mg, solution injectable en stylo prérempli KwikPen", "LILLY"),
        ProduitExtrait("VGENFLI 40 mg/ml, solution injectable en seringue préremplie",
                       "FRESENIUS KABI", indication=INDICATIONS_CIBLE["VGENFLI"]),
        ProduitExtrait("DABIGATRAN TEVA 150 mg, gélules", "TEVA",
                       indication=INDICATIONS_CIBLE["DABIGATRAN"]),
        ProduitExtrait("OXAZEPAM ARROW 50 mg, comprimé sécable", "ARROW",
                       indication=INDICATIONS_CIBLE["OXAZEPAM"]),
        ProduitExtrait("LIKOZAM 2 mg/ml, sirop", "ADVICENNE",
                       indication=INDICATIONS_CIBLE["LIKOZAM"]),
    ]
    morphine = [
        ProduitExtrait(f"MORPHINE (CHLORHYDRATE) LAVOISIER {dosage}, solution injectable en ampoule",
                       labo)
        for dosage, labo in [("1 mg/ml", "LAVOISIER"), ("10 mg/ml", "LAVOISIER"),
                             ("20 mg/ml", "CHAIX ET DU MARAIS"), ("40 mg/ml", "LAVOISIER"),
                             ("50 mg/ml", "CHAIX ET DU MARAIS"), ("500 mg", "LAVOISIER")]
    ]

    return [
        _texte("000054144800",  # id FICTIF (arrêté non référencé par la cible)
               "Arrêté du 27 mai 2026 modifiant la liste des spécialités pharmaceutiques "
               "remboursables aux assurés sociaux",
               "arrete_inscription", inscrits_ss, listes=["SS"]),
        _texte("000054144802",  # id FICTIF (arrêté non référencé par la cible)
               "Arrêté du 27 mai 2026 modifiant la liste des spécialités pharmaceutiques "
               "agréées à l'usage des collectivités et divers services publics",
               "arrete_inscription", inscrits_collectivites, listes=["Collectivité"]),
        _texte("000054144856", "Avis relatif aux prix de spécialités pharmaceutiques",
               "avis_prix",
               [ProduitExtrait("VGENFLI 40 mg/ml, solution injectable en seringue préremplie",
                               "FRESENIUS KABI")]),
        _texte("000054144858", "Avis relatif aux prix de spécialités pharmaceutiques",
               "avis_prix",
               [ProduitExtrait("DABIGATRAN TEVA 110 mg, gélules", "TEVA"),
                ProduitExtrait("DABIGATRAN TEVA 150 mg, gélules", "TEVA"),
                ProduitExtrait("OXAZEPAM ARROW 10 mg, comprimé", "ARROW")]),
        _texte("000054144860",
               "Décision du 12 mai 2026 de l'Union nationale des caisses d'assurance maladie "
               "relative aux taux de participation de l'assuré applicables à des spécialités "
               "pharmaceutiques", "decision_taux",
               [ProduitExtrait("DABIGATRAN TEVA, gélules", "TEVA", taux="0.35"),
                ProduitExtrait("OXAZEPAM ARROW, comprimé", "ARROW", taux="0.35")]),
        _texte("000054144862", "Avis relatif aux prix de spécialités pharmaceutiques",
               "avis_prix",
               [ProduitExtrait("LIKOZAM 1 mg/ml, sirop", "ADVICENNE"),
                ProduitExtrait("LIKOZAM 2 mg/ml, sirop", "ADVICENNE")]),
        _texte("000054144864",
               "Décision du 12 mai 2026 de l'Union nationale des caisses d'assurance maladie "
               "relative aux taux de participation de l'assuré applicables à des spécialités "
               "pharmaceutiques", "decision_taux",
               [ProduitExtrait("LIKOZAM, sirop", "ADVICENNE", taux="0.35")]),
        _texte("000054144866", "Avis relatif aux prix de spécialités pharmaceutiques",
               "avis_prix",
               [ProduitExtrait("WEGOVY 0,25 mg, solution injectable en stylo prérempli FlexTouch",
                               "NOVO NORDISK"),
                ProduitExtrait("WEGOVY 1 mg, solution injectable en stylo prérempli FlexTouch",
                               "NOVO NORDISK")]),
        _texte("000054144868",
               "Décision du 12 mai 2026 de l'Union nationale des caisses d'assurance maladie "
               "relative aux taux de participation de l'assuré applicables à des spécialités "
               "pharmaceutiques", "decision_taux",
               [ProduitExtrait("WEGOVY, solution injectable", "NOVO NORDISK", taux="0.35")]),
        _texte("000054144870", "Avis relatif aux prix de spécialités pharmaceutiques",
               "avis_prix",
               [ProduitExtrait("MOUNJARO 2,5 mg, solution injectable en stylo prérempli KwikPen",
                               "LILLY")]),
        _texte("000054144872",
               "Décision du 12 mai 2026 de l'Union nationale des caisses d'assurance maladie "
               "relative aux taux de participation de l'assuré applicables à des spécialités "
               "pharmaceutiques", "decision_taux",
               [ProduitExtrait("MOUNJARO, solution injectable", "LILLY", taux="0.35")]),
        _texte("000054144874",
               "Avis relatif à la majoration du prix de spécialités pharmaceutiques",
               "avis_hausse_prix", morphine),
        _texte("000054144876",
               "Avis relatif aux baisses de prix de spécialités pharmaceutiques",
               "avis_baisse_prix",
               [ProduitExtrait("FYCOMPA 2 mg, comprimé", "EISAI")]),
    ]


_LISTES_SS_COLLECTIVITES = [("SS", URL.format(ID_ARRETE_SS)),
                            ("Collectivité", URL.format(ID_ARRETE_COLLECTIVITES))]


def _ligne(produit: str, laboratoire: str, section: str, lien_prix: str,
           taux: str = "N/A", lien_taux: str | None = None,
           listes=(), indication: str = "", sources=()) -> LigneConsolidee:
    return LigneConsolidee(
        produit=produit, date_jo=DATE_JO, laboratoire=laboratoire, indication=indication,
        listes=list(listes), lien_prix=URL.format(lien_prix),
        taux=taux, lien_taux=URL.format(lien_taux) if lien_taux else None,
        section=section, sources=list(sources), racine=produit,
    )


def resultat_consolide_28_05() -> ResultatVeille:
    """Les 8 lignes consolidées de l'annexe E (vérité terrain du 28/05/2026), au contrat
    du 23/07/2026 : une ligne par nom de médicament, sans prix chiffré. Le taux, lui,
    reste celui de la CIBLE (0.35, lié à sa décision UNCAM ; « N/A » pour VGENFLI, que
    nulle décision du jour ne vise)."""
    lignes = [
        _ligne("WEGOVY", "NOVO NORDISK", SECTION_INSCRIPTIONS, "JORFTEXT000054144866",
               taux="0.35", lien_taux="JORFTEXT000054144868",
               listes=_LISTES_SS_COLLECTIVITES, indication=INDICATIONS_CIBLE["WEGOVY"],
               sources=[("JORFTEXT000054144866", "avis de prix (non orienté)"),
                        ("JORFTEXT000054144868", "décision de taux UNCAM")]),
        _ligne("MOUNJARO", "LILLY", SECTION_INSCRIPTIONS, "JORFTEXT000054144870",
               taux="0.35", lien_taux="JORFTEXT000054144872",
               listes=_LISTES_SS_COLLECTIVITES, indication=INDICATIONS_CIBLE["MOUNJARO"],
               sources=[("JORFTEXT000054144870", "avis de prix (non orienté)"),
                        ("JORFTEXT000054144872", "décision de taux UNCAM")]),
        _ligne("VGENFLI", "FRESENIUS KABI", SECTION_INSCRIPTIONS, "JORFTEXT000054144856",
               listes=_LISTES_SS_COLLECTIVITES, indication=INDICATIONS_CIBLE["VGENFLI"],
               sources=[("JORFTEXT000054144856", "avis de prix (non orienté)")]),
        _ligne("DABIGATRAN", "TEVA SANTE", SECTION_INSCRIPTIONS, "JORFTEXT000054144858",
               taux="0.35", lien_taux="JORFTEXT000054144860",
               listes=_LISTES_SS_COLLECTIVITES, indication=INDICATIONS_CIBLE["DABIGATRAN"],
               sources=[("JORFTEXT000054144858", "avis de prix (non orienté)"),
                        ("JORFTEXT000054144860", "décision de taux UNCAM")]),
        _ligne("OXAZEPAM", "ARROW", SECTION_INSCRIPTIONS, "JORFTEXT000054144858",
               taux="0.35", lien_taux="JORFTEXT000054144860",
               listes=_LISTES_SS_COLLECTIVITES, indication=INDICATIONS_CIBLE["OXAZEPAM"],
               sources=[("JORFTEXT000054144858", "avis de prix (non orienté)"),
                        ("JORFTEXT000054144860", "décision de taux UNCAM")]),
        _ligne("LIKOZAM", "ADVICENNE", SECTION_INSCRIPTIONS, "JORFTEXT000054144862",
               taux="0.35", lien_taux="JORFTEXT000054144864",
               listes=_LISTES_SS_COLLECTIVITES, indication=INDICATIONS_CIBLE["LIKOZAM"],
               sources=[("JORFTEXT000054144862", "avis de prix (non orienté)"),
                        ("JORFTEXT000054144864", "décision de taux UNCAM")]),
        _ligne("MORPHINE", "LAVOISIER - CHAIX ET DU MARAIS", SECTION_HAUSSES,
               "JORFTEXT000054144874",
               sources=[("JORFTEXT000054144874", "avis de hausse de prix")]),
        _ligne("FYCOMPA", "EISAI SAS", SECTION_BAISSES, "JORFTEXT000054144876",
               sources=[("JORFTEXT000054144876", "avis de baisse de prix")]),
    ]
    return ResultatVeille(date_jo=DATE_JO, lignes=lignes, anomalies=[])
