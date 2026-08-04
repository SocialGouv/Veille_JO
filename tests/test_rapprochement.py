"""Tests hors ligne de `rapprochement.py` (E5) sur la vérité terrain de l'annexe E.

Contrat du 23/07/2026 (dernier mot de l'utilisatrice) : une ligne par nom de
médicament et par laboratoire, plus aucun prix chiffré (le taux de participation, lui,
reste affiché), 5 listes, 6 sections, règle SIRTURO. Chaque piège historique du §7 du
plan garde son assertion.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "fixtures"))

from fixture_annexe_e import DATE_JO, URL, textes_analyses_28_05

import config
import rapprochement
from analyse import ProduitExtrait, TexteAnalyse
from rapprochement import (
    SECTION_BAISSES,
    SECTION_EXTENSIONS,
    SECTION_HAUSSES,
    SECTION_INSCRIPTIONS,
    SECTION_MODIFICATIONS,
    SECTION_RADIATIONS,
    consolider,
    mapper_laboratoire,
    nom_racine,
)


class TestNomRacine(unittest.TestCase):
    """Annexe C, sur les pièges réels du §7 du plan."""

    CAS = [
        ("WEGOVY 0,25 mg, solution injectable en stylo prérempli FlexTouch", "WEGOVY"),
        ("LIKOZAM 1 mg/ml, sirop", "LIKOZAM"),  # et non « LIKOZAM ML »
        ("LIKOZAM 2 mg/ml, sirop", "LIKOZAM"),
        ("MORPHINE AGUETTANT 10 ml", "MORPHINE"),  # labo retiré en fin de nom
        (
            "MORPHINE (CHLORHYDRATE) LAVOISIER 50 mg/ml, solution injectable en ampoule",
            "MORPHINE",
        ),
        ("DABIGATRAN TEVA , GÉLULES", "DABIGATRAN"),  # piège historique verbatim
        ("OXAZEPAM ARROW 50 mg, comprimé sécable", "OXAZEPAM"),
        ("VGENFLI 40 mg/ml, solution injectable en seringue préremplie", "VGENFLI"),
        (
            "FYCOMPA 2 mg, comprimé pelliculé x28",
            "FYCOMPA",
        ),  # calibré 28/05 (cible : FYCOMPA)
        ("MOUNJARO 2,5 mg, solution injectable en stylo prérempli KwikPen", "MOUNJARO"),
        # Dénominations RÉELLES du run du 28/05/2026, recopiées telles quelles des tableaux
        # JORF (calibration E2/E3 du 21/07/2026) : la CIBLE attend les racines courtes.
        (
            "WEGOVY 0,25 mg FlexTouch (sémaglutide), solution injectable en stylo prérempli "
            "- cartouche (verre) dans un stylo prérempli (FlexTouch) de 1,5 ml (0,68 mg/ml) "
            "(B/1) + 4 aiguilles (laboratoires NOVO NORDISK)",
            "WEGOVY",
        ),
        (
            "LIKOZAM 1 mg/ml (clobazam), suspension buvable flacon en verre jaune(brun) 150 ml "
            "avec fermeture de sécurité enfant avec seringue corps en polypropylène et piston "
            "haute densité (PEHD) avec adaptateur flacon polyéthylène basse densité (PEBD) "
            "(B/1) (laboratoires ADVICENNE)",
            "LIKOZAM",
        ),
        (
            "MORPHINE (CHLORHYDRATE) 100 mg/5 ml, sans conservateur LAVOISIER, solution "
            "injectable, 5 ml en ampoule (B/10) (laboratoires CHAIX ET DU MARAIS)",
            "MORPHINE",
        ),
        (
            "MORPHINE (CHLORHYDRATE) 20 mg/1 ml sans conservateur LAVOISIER, solution "
            "injectable,1 ml en ampoule (B/10) (laboratoires CHAIX ET DU MARAIS)",
            "MORPHINE",
        ),
        (
            "FYCOMPA 10 mg (pérampanel), comprimés pelliculés (B/28) (laboratoires EISAI SAS)",
            "FYCOMPA",
        ),
        # Cas dérivés de la même calibration (structures sans virgule, sels, garde-fous).
        ("VGENFLI EN FLACON - FLACON - + 1 AIGUILLE À FILTRE", "VGENFLI"),
        ("OXAZEPAM ARROW SOUS PLAQUETTE", "OXAZEPAM"),
        ("MOUNJARO, - CARTOUCHE DANS UN DE", "MOUNJARO"),  # coupe sur virgule + tiret
        ("DABIGATRAN ETEXILATE", "DABIGATRAN"),  # sel/ester tronqué (cible)
        ("MORPHINE SULFATE LAVOISIER SANS CONSERVATEUR", "MORPHINE"),
        (
            "SULFATE DE MAGNÉSIUM LAVOISIER",
            "SULFATE DE MAGNÉSIUM",
        ),  # sel en tête : conservé
        ("MELATONINE ARROW LP", "MELATONINE"),  # [21/07] LP = forme, ARROW = labo
        # [22/07] Dosages à séparateurs de milliers (avis ORACILLINE réel) : l'ancienne
        # regex laissait « ORACILLINE 1 » et scindait la racine en deux lignes.
        (
            "ORACILLINE 1 000 000 UI (phénoxyméthylpénicilline), comprimés sécables (B/12)",
            "ORACILLINE",
        ),
        (
            "ORACILLINE 500 000 UI/ 5 ml (phénoxyméthylpénicilline benzathine), suspension "
            "buvable, 120 ml en flacon",
            "ORACILLINE",
        ),
        # [23/07] Une ligne par nom de médicament : les 5 dosages de Lacosamide doivent
        # tous tomber sur la racine « LACOSAMIDE » (exemple donné par l'utilisatrice,
        # G.L. PHARMA ajouté au mapping laboratoires le 29/07).
        (
            "LACOSAMIDE G.L. PHARMA 100 mg, comprimés pelliculés sécables (B/56)",
            "LACOSAMIDE",
        ),
        (
            "LACOSAMIDE G.L. PHARMA 50 mg, comprimés pelliculés sécables (B/56)",
            "LACOSAMIDE",
        ),
        # [30/07] Radiopharmaceutiques : les dosages en unités de radioactivité (Bq/Ci
        # et préfixes SI) doivent fondre comme tout autre dosage — GALLIAPHARM (JO du
        # 30/07/2026) sortait en 8 lignes, une par dosage (1,11 à 3,70 GBq), faute
        # d'unité reconnue par MOTIF_DOSAGE.
        ("GALLIAPHARM 1,48 GBQ", "GALLIAPHARM"),
        ("GALLIAPHARM 1,85 GBQ", "GALLIAPHARM"),
        ("GALLIAPHARM 3,70 GBQ", "GALLIAPHARM"),
        (
            "OCTREOSCAN 111 MBq, poudre pour préparation radiopharmaceutique",
            "OCTREOSCAN",
        ),
        (
            "SOMATOSCAN 5 mCi, trousse pour préparation radiopharmaceutique",
            "SOMATOSCAN",
        ),
        # [30/07] Résidu accepté : cette dénomination réelle est malformée à la source
        # (parenthèse orpheline, « / » à la place d'une parenthèse ouvrante) — elle ne
        # fond pas avec les 7 autres dosages de GALLIAPHARM. Volontaire (cf. plan du
        # 04/08/2026) : une heuristique qui couperait sur « / » casserait le cas
        # AZELASTINE CHLORHYDRATE/FLUTICASONE PROPIONATE ci-dessous, où le « / » fait
        # partie du nom.
        (
            "GALLIAPHARM 1,11 GBQ / CHLORURE DE GALLIUM )",
            "GALLIAPHARM / CHLORURE DE GALLIUM )",
        ),
        # [29/07] Calibrages des runs de test réels : dosages en toutes lettres,
        # parenthèse non fermée, labos constatés (ACCORD, HIKMA, VIATRIS, STRAGEN…).
        (
            "AZELASTINE CHLORHYDRATE/FLUTICASONE PROPIONATE BIOGARAN 137 MICROGRAMMES/ "
            "50 MICROGRAMMES",
            "AZELASTINE CHLORHYDRATE/FLUTICASONE PROPIONATE",
        ),
        ("ATIMIAC 20 mg/ 5 mg par ml (dorzolamide", "ATIMIAC"),
        ("AXITINIB ACCORD 5 mg, comprimé pelliculé", "AXITINIB"),
        ("ERIBULINE HIKMA 0,44 mg/ml, solution injectable", "ERIBULINE"),
        ("SIRTURO 100 mg CPR", "SIRTURO"),  # abréviation d'avis (forme galénique)
        ("BRAFTOVI 75 mg GELU", "BRAFTOVI"),
        ("ROSUVASTATINE VIATRIS SANTE 10 mg", "ROSUVASTATINE"),
        ("AMIKACINE STRAGEN 250 mg/ml", "AMIKACINE"),
        # [29/07] Noms terminés par un chiffre : le groupe « séparateur de milliers » de
        # MOTIF_DOSAGE (ajouté pour ORACILLINE) avalait ce chiffre. Le nom sortait tronqué
        # et deux spécialités distinctes (VITAMINE D2 / D3) fusionnaient sur une ligne.
        (
            "CACIT VITAMINE D3 500 mg/440 UI, granulés effervescents",
            "CACIT VITAMINE D3",
        ),
        ("OROCAL VITAMINE D3 500 mg/400 UI, comprimé à sucer", "OROCAL VITAMINE D3"),
        ("VITAMINE B12 1000 µg/2 ml", "VITAMINE B12"),
        ("CACIT VITAMINE D2 500 mg/440 UI", "CACIT VITAMINE D2"),  # ne fond pas dans D3
        # [29/07] Même famille, chiffre final DÉTACHÉ du nom (valence des vaccins,
        # « OMEGA 3 ») : le `\b` ne protège que le chiffre collé (« D3 »). Ici c'est le
        # groupe « séparateur de milliers » qui avalait « 9 0,5 » comme un seul nombre,
        # faute de distinguer l'espace des milliers de la virgule décimale.
        (
            "GARDASIL 9 0,5 ml, suspension injectable en seringue préremplie",
            "GARDASIL 9",
        ),
        ("OMEGA 3 1000 mg, capsule molle", "OMEGA 3"),
        ("PREVENAR 13 0,5 ml, suspension injectable", "PREVENAR 13"),
        ("PREVENAR 13 suspension injectable", "PREVENAR 13"),  # sans dosage : déjà vert
        ("GARDASIL 9 5 mg", "GARDASIL 9"),  # dosage à un chiffre juste derrière
        (
            "VITAMINE B12 1 000 µg/2 ml",
            "VITAMINE B12",
        ),  # chiffre collé + vrais milliers
        ("MACROGOL 4000 10 g, poudre pour solution buvable", "MACROGOL 4000"),
        # Contre-épreuves : les vrais séparateurs de milliers restent des dosages, y
        # compris non ronds (« 12 500 UI » des héparines calciques), sinon la racine se
        # scinde en deux lignes (« ORACILLINE 1 » / « ORACILLINE », défaut du 22/07).
        ("ORACILLINE 1 000 000 UI, poudre", "ORACILLINE"),
        (
            "HEPARINE CALCIQUE 12 500 UI/0,5 ml, solution injectable",
            "HEPARINE CALCIQUE",
        ),
        ("PARACETAMOL 1 000 mg, comprimé effervescent", "PARACETAMOL"),
        # Décimale écrite avec une espace parasite : elle reste une décimale, comme dans
        # `_couper_au_conditionnement` (qui ne coupe pas sur « , 25 »). Sinon la racine
        # sortirait « WEGOVY 0 ».
        ("WEGOVY 0, 25 mg, solution injectable", "WEGOVY"),
        # [29/07 — REJEU RÉEL] Dosages COLLÉS à une lettre, tels que le JO les écrit dans
        # les dénominations abrégées des avis de prix. Le `\b` de tête, ajouté le même jour
        # pour protéger « CACIT VITAMINE D3 », les rendait insupprimables : la racine
        # gardait le conditionnement (« REMSIMA FL2 » sortait tel quel dans la colonne
        # Produit du mail du 02/07, faute d'arrêté le même jour pour la rattraper par CIP).
        # Dénominations RÉELLES, relevées aux JO des 09/06, 02/07 et 23/07/2026.
        ("ERIBULINE HIK 0,44MG/ML FL2ML", "ERIBULINE HIK"),
        ("PELMEG 6MG INJ SRG0,6ML", "PELMEG"),
        ("POMALIDOMIDE LPN1MG GELU", "POMALIDOMIDE LPN"),
        ("POMALIDOMIDE LPN4MG GELU", "POMALIDOMIDE LPN"),
        ("REMSIMA 40MG/ML PERF FL2,5ML", "REMSIMA"),
    ]

    def test_pieges_annexe_c(self):
        for brut, attendu in self.CAS:
            with self.subTest(brut=brut):
                self.assertEqual(nom_racine(brut), attendu)

    def test_resultat_vide_devient_produit_inconnu(self):
        self.assertEqual(nom_racine("10 mg, comprimé"), rapprochement.PRODUIT_INCONNU)

    def test_nom_egal_au_laboratoire_conserve(self):
        # Si le nom entier est un laboratoire connu, on ne vide pas la dénomination.
        self.assertEqual(nom_racine("ARROW"), "ARROW")


class TestMappingLaboratoires(unittest.TestCase):
    def test_mapping_unique_annexe_d(self):
        self.assertEqual(
            mapper_laboratoire("LAVOISIER"), "LAVOISIER - CHAIX ET DU MARAIS"
        )
        self.assertEqual(
            mapper_laboratoire("CHAIX ET DU MARAIS"), "LAVOISIER - CHAIX ET DU MARAIS"
        )
        self.assertEqual(mapper_laboratoire("TEVA"), "TEVA SANTE")
        self.assertEqual(mapper_laboratoire("Laboratoires EISAI"), "EISAI SAS")
        self.assertEqual(mapper_laboratoire("\xa0FRESENIUS KABI"), "FRESENIUS KABI")
        self.assertEqual(mapper_laboratoire("LABO INCONNU SAS"), "LABO INCONNU SAS")

    def test_ecritures_du_mail_utilisatrice(self):
        """Le JO publie la raison sociale, l'utilisatrice écrit le nom d'usage : chaque
        laboratoire de son mail du 23/07/2026 doit ressortir comme elle l'écrit."""
        attendus = {
            "STRAGEN FRANCE": "STRAGEN",
            "VIATRIS SANTE": "VIATRIS",
            "HORUS PHARMA": "HORUS",
            "UPSA SAS": "UPSA",
            "DIFARMED SLU": "DIFARMED",
            "PIERRE FABRE MEDICAMENT": "PIERRE FABRE",
            "JANSSEN-CILAG": "JANSSEN-CILAG",
            "DEMOGEN FRANCE SAS": "DEMOGEN",
            "CHEPLAPHARM FRANCE": "CHEPLAPHARM",
            "LEURQUIN MEDIOLANUM": "LEURQUIN MEDIOLANUM",
            "DB PHARMA": "DB PHARMA",
            "SANDOZ": "SANDOZ",
        }
        for brut, attendu in attendus.items():
            with self.subTest(brut=brut):
                self.assertEqual(mapper_laboratoire(brut), attendu)

    def test_laboratoire_colle_au_nom_des_generiques(self):
        """Le nom de spécialité d'un générique porte son laboratoire (« MEROPENEM
        PANPHARMA ») : la clé doit reproduire le suffixe entier, sinon la racine le garde
        et le même médicament sort sous plusieurs noms (JO des 22/05 et 04/06/2026)."""
        self.assertEqual(
            nom_racine("MEROPENEM PANPHARMA 1 g, poudre pour perfusion"), "MEROPENEM"
        )
        self.assertEqual(nom_racine("MEROPENEM ARROW LAB 1 g, poudre"), "MEROPENEM")
        self.assertEqual(nom_racine("MEROPENEM KALCEKS 500 mg, poudre"), "MEROPENEM")
        self.assertEqual(
            nom_racine("PARACETAMOL TEVA PHARMA 500 mg, comprimé"), "PARACETAMOL"
        )
        # La clé la plus longue gagne : « ARROW LAB » ne renomme pas ARROW lui-même.
        self.assertEqual(mapper_laboratoire("ARROW LAB"), "ARROW")
        self.assertEqual(mapper_laboratoire("ARROW"), "ARROW")
        # NORIDEM reste dans le nom : l'utilisatrice écrit « CEFEPIME NORIDEM » (23/07).
        self.assertEqual(nom_racine("CEFEPIME NORIDEM 1 g, poudre"), "CEFEPIME NORIDEM")

    def test_exploitants_du_meme_jo_alignes_par_analogie(self):
        """Les deux exploitants du 23/07 que l'utilisatrice n'a pas écrits (elle ne montre
        que le repreneur, et a gardé DB PHARMA pour PHENERGAN) : valeurs à confirmer, mais
        jamais laissées à la raison sociale brute au milieu de noms d'usage."""
        self.assertEqual(mapper_laboratoire("ASPEN FRANCE"), "ASPEN")
        self.assertEqual(mapper_laboratoire("LABORATOIRES FRILAB"), "FRILAB")


class TestInvariantOrdreDuMapping(unittest.TestCase):
    """Le résultat ne doit PAS dépendre de l'ordre d'écriture de `config.MAPPING_LABOS`.

    Le commentaire de config.py demande aujourd'hui « VIATRIS SANTE avant VIATRIS » :
    le prochain contributeur qui trie ce mapping par ordre alphabétique — geste naturel
    sur une table de correspondance appelée à grossir au fil de l'eau — ne doit rien
    casser. Le mapping est donc rejoué ici trié alphabétiquement (« VIATRIS » AVANT
    « VIATRIS SANTE », soit l'inverse de la consigne).

    Vert au 29/07/2026 avant la phase 4 (la boucle à point fixe de `nom_racine` et le fait
    que les deux clés concurrentes pointent vers la même valeur rendaient l'ordre
    indifférent), et garanti depuis : `rapprochement._cles_labos_par_longueur` trie les
    clés par longueur décroissante, la plus spécifique gagne.
    """

    MAPPING_TRIE = dict(sorted(config.MAPPING_LABOS.items()))
    # Conflit de SUFFIXE, la clé courte écrite en PREMIER : le cas qui casserait une
    # variante naïve « première clé du dict, une seule passe ». Avant le tri par longueur,
    # « PHARMA » devant « G.L. PHARMA » donnait la racine « LACOSAMIDE G.L » (défauts
    # D1/D2) — le conflit de préfixe « VIATRIS » / « VIATRIS SANTE », lui, était bénin.
    MAPPING_CONFLIT_SUFFIXE = {"PHARMA": "PHARMA GENERIQUE", **config.MAPPING_LABOS}

    def test_racine_insensible_a_l_ordre_du_mapping(self):
        with mock.patch.dict(config.MAPPING_LABOS, self.MAPPING_TRIE, clear=True):
            self.assertEqual(
                nom_racine("ROSUVASTATINE VIATRIS SANTE 10 mg"), "ROSUVASTATINE"
            )
            # Tous les pièges de racine de l'annexe C, sous mapping trié.
            for brut, attendu in TestNomRacine.CAS:
                with self.subTest(brut=brut):
                    self.assertEqual(nom_racine(brut), attendu)

    def test_laboratoire_insensible_a_l_ordre_du_mapping(self):
        with mock.patch.dict(config.MAPPING_LABOS, self.MAPPING_TRIE, clear=True):
            self.assertEqual(mapper_laboratoire("VIATRIS SANTE"), "VIATRIS")
            self.assertEqual(mapper_laboratoire("VIATRIS"), "VIATRIS")

    def test_conflit_de_suffixe_la_cle_la_plus_longue_gagne(self):
        with mock.patch.dict(
            config.MAPPING_LABOS, self.MAPPING_CONFLIT_SUFFIXE, clear=True
        ):
            self.assertEqual(
                nom_racine(
                    "LACOSAMIDE G.L. PHARMA 100 mg, comprimés "
                    "pelliculés sécables (B/56)"
                ),
                "LACOSAMIDE",
            )
            self.assertEqual(mapper_laboratoire("G.L. PHARMA"), "G.L. PHARMA")
            self.assertEqual(
                mapper_laboratoire("PHARMA GENERIQUES SAS"), "PHARMA GENERIQUE"
            )
            # Les pièges de racine restent intacts sous ce mapping piégé.
            for brut, attendu in TestNomRacine.CAS:
                with self.subTest(brut=brut):
                    self.assertEqual(nom_racine(brut), attendu)


class TestConsolidation28Mai(unittest.TestCase):
    """Le cœur de la recette E5 (contrat du 23/07/2026 : une ligne par nom de
    médicament) : 13 textes analysés → 8 lignes, une par racine de l'annexe E."""

    @classmethod
    def setUpClass(cls):
        cls.resultat = consolider(textes_analyses_28_05(), DATE_JO)
        cls.par_racine = {ligne.racine: ligne for ligne in cls.resultat.lignes}

    def test_8_lignes_une_par_racine(self):
        """Les présentations (dosages, packs) sont fondues : une ligne par racine."""
        self.assertEqual(len(self.resultat.lignes), 8)
        self.assertEqual(
            set(self.par_racine),
            {
                "WEGOVY",
                "MOUNJARO",
                "VGENFLI",
                "DABIGATRAN",
                "OXAZEPAM",
                "LIKOZAM",
                "MORPHINE",
                "FYCOMPA",
            },
        )

    def test_sections_conformes(self):
        inscriptions = {
            l.racine for l in self.resultat.lignes_par_section(SECTION_INSCRIPTIONS)
        }
        self.assertEqual(
            inscriptions,
            {"WEGOVY", "MOUNJARO", "VGENFLI", "DABIGATRAN", "OXAZEPAM", "LIKOZAM"},
        )
        hausses = [l.racine for l in self.resultat.lignes_par_section(SECTION_HAUSSES)]
        # Piège MORPHINE : jamais en baisses ; et depuis le 23/07/2026, les 6
        # présentations (2 laboratoires du même mapping) fondent en UNE seule ligne.
        self.assertEqual(hausses, ["MORPHINE"])
        baisses = [l.racine for l in self.resultat.lignes_par_section(SECTION_BAISSES)]
        self.assertEqual(baisses, ["FYCOMPA"])

    def test_listes_et_liens_par_segment(self):
        """Chaque racine inscrite aux deux listes porte les deux segments, chacun avec
        le lien de SON arrêté (« 1 liste = 1 arrêté », format « SS & Collectivité »)."""
        for racine in (
            "WEGOVY",
            "MOUNJARO",
            "VGENFLI",
            "DABIGATRAN",
            "OXAZEPAM",
            "LIKOZAM",
        ):
            ligne = self.par_racine[racine]
            self.assertEqual(ligne.liste, "SS & Collectivité", racine)
            self.assertEqual(
                ligne.listes,
                [
                    ("SS", URL.format("JORFTEXT000054144800")),
                    ("Collectivité", URL.format("JORFTEXT000054144802")),
                ],
                racine,
            )

    def test_liens_prix_annexe_e(self):
        attendus = {
            "WEGOVY": "JORFTEXT000054144866",
            "MOUNJARO": "JORFTEXT000054144870",
            "VGENFLI": "JORFTEXT000054144856",
            "DABIGATRAN": "JORFTEXT000054144858",
            "OXAZEPAM": "JORFTEXT000054144858",  # avis partagé DABIGATRAN/OXAZEPAM
            "LIKOZAM": "JORFTEXT000054144862",
            "MORPHINE": "JORFTEXT000054144874",
            "FYCOMPA": "JORFTEXT000054144876",
        }
        for racine, id_ in attendus.items():
            self.assertEqual(self.par_racine[racine].lien_prix, URL.format(id_), racine)

    def test_taux_des_decisions_uncam(self):
        """Le taux vient de la décision UNCAM du jour, avec son lien. VGENFLI n'en a pas :
        « N/A » sans lien, et sans « à vérifier » (l'absence de décision est normale)."""
        attendus = {
            "WEGOVY": "JORFTEXT000054144868",
            "MOUNJARO": "JORFTEXT000054144872",
            "DABIGATRAN": "JORFTEXT000054144860",
            "OXAZEPAM": "JORFTEXT000054144860",  # décision partagée
            "LIKOZAM": "JORFTEXT000054144864",
        }
        for racine, id_ in attendus.items():
            self.assertEqual(self.par_racine[racine].taux, "0.35", racine)
            self.assertEqual(self.par_racine[racine].lien_taux, URL.format(id_), racine)
        self.assertEqual(self.par_racine["VGENFLI"].taux, "N/A")
        self.assertIsNone(self.par_racine["VGENFLI"].lien_taux)

    def test_laboratoires_mappes(self):
        attendus = {
            "WEGOVY": "NOVO NORDISK",
            "MOUNJARO": "LILLY",
            "VGENFLI": "FRESENIUS KABI",
            "DABIGATRAN": "TEVA SANTE",
            "OXAZEPAM": "ARROW",
            "LIKOZAM": "ADVICENNE",
            "MORPHINE": "LAVOISIER - CHAIX ET DU MARAIS",  # piège : mapping unique
            "FYCOMPA": "EISAI SAS",
        }
        for racine, labo in attendus.items():
            self.assertEqual(self.par_racine[racine].laboratoire, labo, racine)

    def test_indications_de_section_recopiees(self):
        self.assertTrue(
            self.par_racine["WEGOVY"].indication.startswith("Chez l'adulte")
        )
        # L'indication commune aux deux arrêtés (SS et collectivités) n'est reprise
        # qu'une fois sur la ligne fusionnée.
        self.assertEqual(self.par_racine["DABIGATRAN"].indication, "Idem que PRADAXA")
        # MOUNJARO n'a AUCUNE indication de section dans la fixture : jamais de vide
        # silencieux sur une inscription → « à compléter manuellement ».
        self.assertEqual(
            self.par_racine["MOUNJARO"].indication, "à compléter manuellement"
        )

    def test_aucune_ligne_a_verifier_ni_anomalie(self):
        """Fixture nominale : l'indication manquante de MOUNJARO est portée par la
        colonne elle-même (« à compléter manuellement »), pas par le récapitulatif."""
        self.assertEqual(
            {l.racine for l in self.resultat.lignes if l.a_verifier}, set()
        )
        self.assertEqual(self.resultat.anomalies, [])

    def test_sources_traceables(self):
        self.assertEqual(
            self.par_racine["MORPHINE"].sources,
            [("JORFTEXT000054144874", "avis de hausse de prix")],
        )


def _texte(
    type_texte,
    produits,
    id_="JORFTEXT000054140000",
    ambigu=False,
    listes=(),
    prix_deux_sens=False,
):
    return TexteAnalyse(
        id=id_,
        url=URL.format(id_),
        titre="titre",
        type_texte=type_texte,
        ambigu=ambigu,
        produits=produits,
        texte_nettoye="corps",
        listes=list(listes),
        prix_deux_sens=prix_deux_sens,
    )


class TestMultiLaboratoires(unittest.TestCase):
    """Cas des génériques (mail utilisatrice du 22/07/2026) : un même médicament
    commercialisé par plusieurs laboratoires garde une ligne par laboratoire."""

    def test_une_ligne_par_laboratoire(self):
        # Calqué sur DARUNAVIR Viatris/Zentiva (hausse de prix du JO du 07/07/2026).
        textes = [
            _texte(
                "avis_hausse_prix",
                [
                    ProduitExtrait("DARUNAVIR 400 mg, comprimé", "VIATRIS"),
                    ProduitExtrait("DARUNAVIR 600 mg, comprimé", "VIATRIS"),
                    ProduitExtrait("DARUNAVIR 400 mg, comprimé", "ZENTIVA"),
                ],
            )
        ]
        resultat = consolider(textes, DATE_JO)
        self.assertEqual(
            [(l.produit, l.laboratoire) for l in resultat.lignes],
            [("DARUNAVIR", "VIATRIS"), ("DARUNAVIR", "ZENTIVA FRANCE")],
        )
        for ligne in resultat.lignes:
            self.assertEqual(ligne.section, SECTION_HAUSSES)

    def test_contribution_sans_laboratoire_propagee(self):
        """Un texte qui ne nomme pas le laboratoire alimente toutes les lignes de la
        racine (ancienne propagation par racine, conservée)."""
        textes = [
            _texte(
                "arrete_inscription",
                [ProduitExtrait("PRODUIT X 10 mg", "")],
                listes=["SS"],
            ),
            _texte(
                "avis_hausse_prix",
                [ProduitExtrait("PRODUIT X 10 mg", "LABO A")],
                id_="JORFTEXT000054140002",
            ),
        ]
        resultat = consolider(textes, DATE_JO)
        (ligne,) = resultat.lignes
        self.assertEqual(ligne.laboratoire, "LABO A")
        self.assertEqual(ligne.liste, "SS")  # l'arrêté sans labo a bien alimenté
        self.assertEqual(ligne.section, SECTION_INSCRIPTIONS)


class TestCinqListes(unittest.TestCase):
    def test_ordre_et_liens_des_listes(self):
        """Les 5 listes (mail utilisatrice des 22-23/07/2026) sortent dans l'ordre de
        config.MOTIFS_LISTES, chacune avec le lien de son arrêté."""
        produit = [ProduitExtrait("PRODUIT Y 5 mg", "LABO")]
        textes = [
            _texte(
                "arrete_inscription",
                produit,
                id_="JORFTEXT000054140010",
                listes=["Rétrocession"],
            ),
            _texte(
                "arrete_inscription", produit, id_="JORFTEXT000054140011", listes=["SS"]
            ),
            _texte(
                "arrete_inscription",
                produit,
                id_="JORFTEXT000054140012",
                listes=["LES SMR"],
            ),
        ]
        resultat = consolider(textes, DATE_JO)
        (ligne,) = resultat.lignes
        self.assertEqual(ligne.liste, "SS & LES SMR & Rétrocession")
        self.assertEqual(
            ligne.listes,
            [
                ("SS", URL.format("JORFTEXT000054140011")),
                ("LES SMR", URL.format("JORFTEXT000054140012")),
                ("Rétrocession", URL.format("JORFTEXT000054140010")),
            ],
        )


class TestNouvellesSections(unittest.TestCase):
    def test_radiation(self):
        """VFEND radié de la LES MCO (JO du 22/05/2026, exemple utilisatrice)."""
        textes = [
            _texte(
                "arrete_radiation",
                [ProduitExtrait("VFEND 200 mg, poudre", "PFIZER")],
                listes=["LES MCO"],
            )
        ]
        resultat = consolider(textes, DATE_JO)
        (ligne,) = resultat.lignes
        self.assertEqual(ligne.section, SECTION_RADIATIONS)
        self.assertEqual(ligne.liste_radiation, "LES MCO")
        self.assertEqual(
            ligne.listes_radiation, [("LES MCO", URL.format("JORFTEXT000054140000"))]
        )

    def test_modification_libelle(self):
        textes = [
            _texte(
                "modification_libelle",
                [ProduitExtrait("CHLORHEXIDINE ARROW 0,20 %, solution", "ARROW")],
            )
        ]
        resultat = consolider(textes, DATE_JO)
        (ligne,) = resultat.lignes
        self.assertEqual(ligne.section, SECTION_MODIFICATIONS)
        self.assertEqual(ligne.lien_modification, URL.format("JORFTEXT000054140000"))
        # Libellé modifié sans changement d'exploitant : le laboratoire reste seul.
        self.assertEqual(ligne.laboratoire_affiche, "ARROW")

    def test_modification_libelle_transfert_d_exploitation(self):
        """Cas nominal de ces arrêtés (JO du 23/07/2026) : l'exploitation change de main.
        La ligne porte le NOUVEL exploitant, et la colonne Laboratoire montre la
        transition « ancien → nouveau ». Les deux passent par le mapping unique."""
        textes = [
            _texte(
                "modification_libelle",
                [
                    ProduitExtrait(
                        "GEMZAR 1000 mg, poudre pour perfusion",
                        "CHEPLAPHARM FRANCE",
                        laboratoire_precedent="LILLY FRANCE SAS",
                    )
                ],
            )
        ]
        resultat = consolider(textes, DATE_JO)
        (ligne,) = resultat.lignes
        # Les deux noms passent par le mapping de l'annexe D : « CHEPLAPHARM FRANCE » et
        # « LILLY FRANCE SAS » au JO, « CHEPLAPHARM » et « LILLY » sous sa plume.
        self.assertEqual(ligne.laboratoire, "CHEPLAPHARM")
        self.assertEqual(ligne.laboratoire_precedent, "LILLY")
        self.assertEqual(ligne.laboratoire_affiche, "LILLY → CHEPLAPHARM")

    def test_transfert_vers_le_meme_laboratoire_sans_fleche(self):
        """Exploitant inchangé après mapping (raison sociale reformulée) : pas de flèche,
        elle annoncerait un transfert qui n'a pas eu lieu."""
        textes = [
            _texte(
                "modification_libelle",
                [
                    ProduitExtrait(
                        "MELATONINE ARROW LP 2 mg, comprimé",
                        "ARROW",
                        laboratoire_precedent="ARROW GENERIQUES",
                    )
                ],
            )
        ]
        (ligne,) = consolider(textes, DATE_JO).lignes
        self.assertEqual(ligne.laboratoire_affiche, "ARROW")

    def test_regle_sirturo(self):
        """Règle du 23/07/2026 : inscription + extension + prix le même jour → la ligne
        ne sort QUE dans les Extensions d'indications, listes et lien de prix conservés
        pour le rappel au rendu."""
        produit = [ProduitExtrait("SIRTURO 100 mg, comprimé", "JANSSEN-CILAG")]
        textes = [
            _texte(
                "arrete_inscription",
                produit,
                id_="JORFTEXT000054140020",
                listes=["Rétrocession"],
            ),
            _texte(
                "extension_indication",
                [
                    ProduitExtrait(
                        "SIRTURO 100 mg, comprimé",
                        "JANSSEN-CILAG",
                        indication="En association appropriée…",
                    )
                ],
                id_="JORFTEXT000054140021",
            ),
            _texte("avis_prix", produit, id_="JORFTEXT000054140022"),
        ]
        resultat = consolider(textes, DATE_JO)
        (ligne,) = resultat.lignes
        self.assertEqual(ligne.section, SECTION_EXTENSIONS)
        self.assertEqual(ligne.liste, "Rétrocession")
        self.assertEqual(ligne.lien_prix, URL.format("JORFTEXT000054140022"))
        self.assertEqual(ligne.lien_extension, URL.format("JORFTEXT000054140021"))
        self.assertEqual(ligne.indication, "En association appropriée…")
        # Aucune autre section ne porte SIRTURO.
        self.assertEqual(resultat.lignes_par_section(SECTION_INSCRIPTIONS), [])
        self.assertEqual(resultat.lignes_par_section(SECTION_HAUSSES), [])

    def test_extension_seule_sans_regroupement(self):
        """Une extension sans inscription ni prix reste une extension ordinaire."""
        textes = [
            _texte(
                "extension_indication",
                [
                    ProduitExtrait(
                        "PRODUIT Z 5 mg", "LABO", indication="Nouvelle indication"
                    )
                ],
            )
        ]
        resultat = consolider(textes, DATE_JO)
        (ligne,) = resultat.lignes
        self.assertEqual(ligne.section, SECTION_EXTENSIONS)
        self.assertEqual(ligne.listes, [])
        self.assertIsNone(ligne.lien_prix)


class TestRapprochementParCip(unittest.TestCase):
    """Pont CIP (29/07/2026) : les avis de prix abrègent les dénominations
    (« MEROPENEM PAN 1G ») — le code CIP, commun aux deux familles de tableaux,
    rattache l'avis à la ligne de l'arrêté."""

    def test_avis_abrege_rattache_a_l_arrete(self):
        # Calqué sur MEROPENEM PANPHARMA au JO du 04/06/2026.
        textes = [
            _texte(
                "arrete_inscription",
                [
                    ProduitExtrait(
                        "MEROPENEM 1 g, poudre pour solution injectable",
                        "PANPHARMA",
                        cip="3400930111111",
                        indication="Idem MERONEM",
                    )
                ],
                id_="JORFTEXT000054140030",
                listes=["LES SMR"],
            ),
            _texte(
                "avis_prix",
                [
                    ProduitExtrait(
                        "MEROPENEM PAN 1G INJ FL", "PANPHARMA", cip="3400930111111"
                    )
                ],
                id_="JORFTEXT000054140031",
            ),
        ]
        resultat = consolider(textes, DATE_JO)
        (ligne,) = resultat.lignes  # une seule ligne, pas de parasite
        self.assertEqual(
            ligne.produit, "MEROPENEM"
        )  # la dénomination de l'arrêté fait foi
        self.assertEqual(ligne.section, SECTION_INSCRIPTIONS)
        self.assertEqual(ligne.lien_prix, URL.format("JORFTEXT000054140031"))
        self.assertEqual(
            resultat.anomalies, []
        )  # avis rattaché : plus d'« à vérifier »

    def test_avis_en_premier_dans_le_sommaire(self):
        """L'élection de la clé canonique ne dépend pas de l'ordre du sommaire."""
        textes = [
            _texte(
                "avis_prix",
                [ProduitExtrait("ERIBULINE HIK FL", "HIKMA", cip="3400930222222")],
                id_="JORFTEXT000054140032",
            ),
            _texte(
                "arrete_inscription",
                [
                    ProduitExtrait(
                        "ERIBULINE HIKMA 0,44 mg/ml, solution injectable",
                        "HIKMA FRANCE",
                        cip="3400930222222",
                    )
                ],
                id_="JORFTEXT000054140033",
                listes=["LES MCO"],
            ),
        ]
        resultat = consolider(textes, DATE_JO)
        (ligne,) = resultat.lignes
        self.assertEqual(ligne.produit, "ERIBULINE")
        self.assertEqual(ligne.liste, "LES MCO")

    def test_deux_arretes_meme_code_racine_courte_elue(self):
        """POMALIDOMIDE au 02/07/2026 : l'arrêté rétrocession abrège aussi
        (« POMALIDOMIDE LPN GELU ») — à priorité égale, la racine courte (préfixe)
        fait foi et les trois listes fusionnent sur une seule ligne."""
        cip = "3400930333333"
        textes = [
            _texte(
                "arrete_inscription",
                [ProduitExtrait("POMALIDOMIDE LPN GELU 4MG", "MEDISOL", cip=cip)],
                id_="JORFTEXT000054140035",
                listes=["Rétrocession"],
            ),
            _texte(
                "arrete_inscription",
                [ProduitExtrait("POMALIDOMIDE LUPIN 4 mg, gélule", "MEDISOL", cip=cip)],
                id_="JORFTEXT000054140036",
                listes=["LES SMR"],
            ),
            _texte(
                "arrete_inscription",
                [ProduitExtrait("POMALIDOMIDE LUPIN 4 mg, gélule", "MEDISOL", cip=cip)],
                id_="JORFTEXT000054140037",
                listes=["Collectivité"],
            ),
        ]
        resultat = consolider(textes, DATE_JO)
        (ligne,) = resultat.lignes
        self.assertEqual(ligne.produit, "POMALIDOMIDE")
        self.assertEqual(ligne.liste, "Collectivité & LES SMR & Rétrocession")

    def test_sans_cip_comportement_inchange(self):
        """Avis sans CIP et racine divergente : la ligne séparée « à vérifier »
        subsiste (jamais de rapprochement deviné)."""
        textes = [
            _texte(
                "arrete_inscription",
                [ProduitExtrait("PRODUIT K 5 mg, comprimé", "LABO")],
                listes=["SS"],
            ),
            _texte(
                "avis_prix",
                [ProduitExtrait("PRODUIT K ABR CPR", "LABO")],
                id_="JORFTEXT000054140034",
            ),
        ]
        resultat = consolider(textes, DATE_JO)
        self.assertEqual(len(resultat.lignes), 2)


class TestTauxDeParticipation(unittest.TestCase):
    """Colonne Taux : la décision UNCAM en est la seule source, et elle ne crée jamais de
    ligne — elle alimente celle de l'arrêté, rattachée par code CIP (cas réel du
    23/07/2026 : ATIMIAC inscrit, tarifé et taxé le même jour par trois textes)."""

    def _inscription(self, cip="3400930333211"):
        return _texte(
            "arrete_inscription",
            [
                ProduitExtrait(
                    "ATIMIAC 20 mg/5 mg par ml, collyre en solution",
                    "HORUS PHARMA",
                    cip=cip,
                    indication="Idem AMIKACINE",
                )
            ],
            id_="JORFTEXT000054457332",
            listes=["SS"],
        )

    def test_taux_rattache_a_l_inscription_par_le_cip(self):
        textes = [
            self._inscription(),
            _texte(
                "decision_taux",
                [
                    ProduitExtrait(
                        "ATIMIAC 20 mg/5 mg par ml (dorzolamide, timolol), collyre",
                        "HORUS PHARMA",
                        cip="3400930333211",
                        taux="0.35",
                    )
                ],
                id_="JORFTEXT000054458542",
            ),
        ]
        resultat = consolider(textes, DATE_JO)
        (ligne,) = resultat.lignes  # la décision n'ajoute pas de ligne
        self.assertEqual(ligne.section, SECTION_INSCRIPTIONS)
        self.assertEqual(ligne.taux, "0.35")
        self.assertEqual(ligne.lien_taux, URL.format("JORFTEXT000054458542"))
        self.assertEqual(resultat.anomalies, [])

    def test_taux_divergents_entre_presentations_signales(self):
        """Deux présentations d'un même nom à des taux différents : la ligne unique n'en
        montre qu'un (le premier vu) et le dit — jamais de choix silencieux."""
        textes = [
            self._inscription(),
            _texte(
                "decision_taux",
                [
                    ProduitExtrait(
                        "ATIMIAC 20 mg, collyre",
                        "HORUS PHARMA",
                        cip="3400930333211",
                        taux="0.35",
                    ),
                    ProduitExtrait(
                        "ATIMIAC 40 mg, collyre",
                        "HORUS PHARMA",
                        cip="3400930333211",
                        taux="0.65",
                    ),
                ],
                id_="JORFTEXT000054458542",
            ),
        ]
        resultat = consolider(textes, DATE_JO)
        (ligne,) = resultat.lignes
        self.assertEqual(ligne.taux, "0.35")
        self.assertTrue(ligne.a_verifier)
        self.assertTrue(
            any("35% vs 65%" in motif for motif in ligne.motifs_verification),
            ligne.motifs_verification,
        )

    def test_decision_sans_taux_lisible_signalee(self):
        """Décision UNCAM visant bien le produit, mais dont aucun taux n'a pu être lu :
        « N/A » ET « à vérifier » — l'inverse serait un vide muet."""
        textes = [
            self._inscription(),
            _texte(
                "decision_taux",
                [
                    ProduitExtrait(
                        "ATIMIAC 20 mg, collyre", "HORUS PHARMA", cip="3400930333211"
                    )
                ],
                id_="JORFTEXT000054458542",
            ),
        ]
        resultat = consolider(textes, DATE_JO)
        (ligne,) = resultat.lignes
        self.assertEqual(ligne.taux, "N/A")
        self.assertIsNone(ligne.lien_taux)
        self.assertTrue(
            any("valeur non extraite" in motif for motif in ligne.motifs_verification),
            ligne.motifs_verification,
        )


class TestPourcentage(unittest.TestCase):
    def test_conversion_partagee_par_les_deux_rendus(self):
        self.assertEqual(rapprochement.pourcentage("0.35"), "35%")
        self.assertEqual(rapprochement.pourcentage("0.7"), "70%")
        self.assertEqual(rapprochement.pourcentage("1"), "100%")
        self.assertEqual(rapprochement.pourcentage("N/A"), "N/A")


class TestExtensionParArrete(unittest.TestCase):
    """EIT portée par un arrêté d'inscription (cas nominal au JO, 29/07/2026) :
    la liste de l'arrêté est conservée pour le rappel, sans basculer la ligne en
    Inscriptions."""

    def test_extension_avec_listes_reste_en_extensions(self):
        # Calqué sur ACETATE DE CYPROTERONE au JO du 07/07/2026 (arrêtés SS et
        # collectivités réorientés extension_indication par le corps).
        produit = ProduitExtrait(
            "ACETATE DE CYPROTERONE ARROW 50 mg, comprimé",
            "ARROW",
            indication="Traitement pour la réduction…",
        )
        textes = [
            _texte(
                "extension_indication",
                [produit],
                id_="JORFTEXT000054140040",
                listes=["SS"],
            ),
            _texte(
                "extension_indication",
                [produit],
                id_="JORFTEXT000054140041",
                listes=["Collectivité"],
            ),
        ]
        resultat = consolider(textes, DATE_JO)
        (ligne,) = resultat.lignes
        self.assertEqual(ligne.section, SECTION_EXTENSIONS)
        self.assertEqual(ligne.liste, "SS & Collectivité")  # rappel « Inscription : … »
        self.assertEqual(ligne.lien_extension, URL.format("JORFTEXT000054140040"))
        self.assertEqual(ligne.indication, "Traitement pour la réduction…")


class _ReferentielFactice:
    """Doublure de referentiel_prix.ReferentielPrix pour les tests hors ligne."""

    def __init__(self, prix: dict):
        self.prix = prix  # cip → Decimal (prix antérieur)
        self.enregistres: list[tuple] = []

    def prix_anterieur(self, cip, date_jo):
        return (self.prix[cip], "test") if cip in self.prix else None

    def enregistrer(self, cip, date_jo, prix):
        self.enregistres.append((cip, date_jo, prix))


class TestOrientationParReferentiel(unittest.TestCase):
    """Avis « prix fixés » sans sens ni prix antérieur au JO (vérifié sur pièces le
    29/07/2026) : orientation par comparaison du PPTTC au référentiel de prix."""

    from decimal import Decimal as _D

    def _avis(self, ppttc="156,38 €", cip="3400930084939"):
        return _texte(
            "avis_prix",
            [
                ProduitExtrait(
                    "DARUNAVIR VIATRIS 400 mg, comprimé",
                    "VIATRIS",
                    cip=cip,
                    ppttc=ppttc,
                )
            ],
        )

    def test_baisse_constatee(self):
        referentiel = _ReferentielFactice({"3400930084939": self._D("160.24")})
        resultat = consolider([self._avis()], DATE_JO, referentiel=referentiel)
        (ligne,) = resultat.lignes
        self.assertEqual(ligne.section, SECTION_BAISSES)
        self.assertFalse(ligne.a_verifier)
        self.assertEqual(resultat.anomalies, [])
        # Le prix publié est archivé pour les comparaisons futures.
        self.assertEqual(
            referentiel.enregistres, [("3400930084939", DATE_JO, self._D("156.38"))]
        )

    def test_hausse_constatee(self):
        referentiel = _ReferentielFactice({"3400930084939": self._D("150.00")})
        resultat = consolider([self._avis()], DATE_JO, referentiel=referentiel)
        self.assertEqual(resultat.lignes[0].section, SECTION_HAUSSES)
        self.assertFalse(resultat.lignes[0].a_verifier)

    def test_prix_inconnu_ou_egal_reste_a_verifier(self):
        for referentiel in (
            _ReferentielFactice({}),  # inconnu
            _ReferentielFactice({"3400930084939": self._D("156.38")}),
        ):
            resultat = consolider([self._avis()], DATE_JO, referentiel=referentiel)
            ligne = resultat.lignes[0]
            self.assertEqual(ligne.section, SECTION_HAUSSES)  # convention historique
            self.assertTrue(ligne.a_verifier)  # jamais deviné

    def test_sens_contradictoires_jamais_devines(self):
        """Deux présentations du même avis qui divergent : « à vérifier »."""
        referentiel = _ReferentielFactice(
            {"3400930000001": self._D("10.00"), "3400930000002": self._D("30.00")}
        )
        textes = [
            _texte(
                "avis_prix",
                [
                    ProduitExtrait(
                        "PRODUIT M 5 mg, comprimé",
                        "LABO",
                        cip="3400930000001",
                        ppttc="12,00 €",
                    ),
                    ProduitExtrait(
                        "PRODUIT M 10 mg, comprimé",
                        "LABO",
                        cip="3400930000002",
                        ppttc="25,00 €",
                    ),
                ],
            )
        ]
        resultat = consolider(textes, DATE_JO, referentiel=referentiel)
        self.assertTrue(resultat.lignes[0].a_verifier)

    def test_avis_annoncant_les_deux_sens_jamais_tranche_par_le_referentiel(self):
        """Piège MORPHINE (TESTS.md) : un avis dont le TEXTE annonce à la fois une
        majoration et une baisse reste « Hausse de prix (à vérifier) » même quand le
        référentiel connaît un prix antérieur — la comparaison automatique ne tranche pas
        ce que le texte déclare contradictoire, et le motif dit pourquoi.

        Défaut réparé le 29/07/2026 : rien ne distinguait « non orienté faute de mot-clé »
        de « non orienté parce que les deux sens sont annoncés » ; la ligne partait en
        Baisses (ici : 4,00 € → 3,10 €), sans « à vérifier », sans motif, donc absente du
        récapitulatif — un sens unique affirmé en silence.
        """
        avis = _texte(
            "avis_prix",
            [
                ProduitExtrait(
                    "MORPHINE (CHLORHYDRATE) LAVOISIER 10 mg/ml, solution injectable",
                    "LAVOISIER",
                    cip="3400930084939",
                    ppttc="3,10 €",
                )
            ],
            prix_deux_sens=True,
        )  # les deux sens annoncés (analyse.py)
        referentiel = _ReferentielFactice({"3400930084939": self._D("4.00")})
        resultat = consolider([avis], DATE_JO, referentiel=referentiel)
        (ligne,) = resultat.lignes
        self.assertEqual(
            ligne.section, SECTION_HAUSSES
        )  # convention, jamais « baisse »
        self.assertTrue(ligne.a_verifier)
        self.assertTrue(
            any(
                "majoration" in motif and "baisse" in motif
                for motif in ligne.motifs_verification
            ),
            ligne.motifs_verification,
        )
        self.assertTrue(
            any(
                anomalie.startswith("MORPHINE : à vérifier —")
                for anomalie in resultat.anomalies
            ),
            resultat.anomalies,
        )
        # UN seul motif pour UN seul problème : plus de « classification ambiguë » en
        # doublon devant le motif spécifique (effet de bord corrigé le 29/07/2026).
        self.assertEqual(len(ligne.motifs_verification), 1, ligne.motifs_verification)

    def test_sans_referentiel_comportement_historique(self):
        resultat = consolider([self._avis()], DATE_JO)
        self.assertTrue(resultat.lignes[0].a_verifier)

    def test_bascule_orientation_desactivee_repli_a_verifier(self):
        """Repli de la bascule `ORIENTATION_PRIX_AUTO = False` (question n° 1 : repli
        promis au CEPS s'il refuse la comparaison BDPM). Le drapeau n'est lu que par
        `main.executer`, qui ne construit alors AUCUN référentiel : c'est cette absence
        de référentiel qui est rejouée ici. Le même avis neutre repart en « Hausse de
        prix (à vérifier) » — et rien d'autre du rendu ne bouge.
        """
        self.assertIn(
            "ORIENTATION_PRIX_AUTO", vars(config)
        )  # la bascule existe toujours
        avis = self._avis()
        referentiel = _ReferentielFactice({"3400930084939": self._D("160.24")})

        (avec,) = consolider([avis], DATE_JO, referentiel=referentiel).lignes
        resultat_sans = consolider([avis], DATE_JO)  # bascule à False
        (sans,) = resultat_sans.lignes

        self.assertEqual(avec.section, SECTION_BAISSES)  # orienté par le référentiel
        self.assertFalse(avec.a_verifier)
        self.assertEqual(sans.section, SECTION_HAUSSES)  # convention historique
        self.assertTrue(sans.a_verifier)
        self.assertTrue(
            any("sens à vérifier" in motif for motif in sans.motifs_verification)
        )
        self.assertTrue(
            any("DARUNAVIR" in anomalie for anomalie in resultat_sans.anomalies)
        )
        # « sans autre changement de rendu » : produit, laboratoire et lien identiques.
        self.assertEqual(
            (sans.produit, sans.laboratoire, sans.lien_prix),
            (avec.produit, avec.laboratoire, avec.lien_prix),
        )

    def test_avis_a_deux_sens_ne_deborde_pas_sur_les_lignes_qu_il_ne_classe_pas(self):
        """Effet de bord corrigé le 29/07/2026 (second tour) : le doute d'orientation d'un
        avis de prix ne « à vérifier » QUE les lignes dont le prix décide de la section.

        Le premier câblage passait par `TexteAnalyse.ambigu`, dont `_accumuler` fait un
        `signaler("classification ambiguë du texte …")` sans regarder la section. Deux
        lignes du contrat en sortaient faussement douteuses — une inscription et une ligne
        de la règle SIRTURO — avec « (à vérifier) » sur le produit dans le mail et l'Excel,
        une entrée au récapitulatif, et un motif faux : la classification, elle, est bonne.
        """
        produit = [
            ProduitExtrait(
                "INSCRIVIN 10 mg, comprimé",
                "LABO INSCRIT",
                cip="3400930084939",
                indication="Asthme sévère",
            )
        ]
        avis_contradictoire = _texte(
            "avis_prix",
            [
                ProduitExtrait(
                    "INSCRIVIN 10 mg, comprimé",
                    "LABO INSCRIT",
                    cip="3400930084939",
                    ppttc="8,50 €",
                )
            ],
            id_="JORFTEXT000054140031",
            prix_deux_sens=True,
        )
        referentiel = _ReferentielFactice({"3400930084939": self._D("9.00")})

        # a. section décidée par l'inscription : le prix n'y décide rien.
        inscription = _texte(
            "arrete_inscription", produit, id_="JORFTEXT000054140030", listes=["SS"]
        )
        (ligne,) = consolider(
            [inscription, avis_contradictoire], DATE_JO, referentiel=referentiel
        ).lignes
        self.assertEqual(ligne.section, SECTION_INSCRIPTIONS)
        self.assertFalse(ligne.a_verifier, ligne.motifs_verification)
        self.assertEqual(ligne.motifs_verification, [])

        # b. section décidée par la règle SIRTURO : idem, malgré l'avis de prix requis.
        extension = _texte(
            "extension_indication",
            [
                ProduitExtrait(
                    "INSCRIVIN 10 mg, comprimé",
                    "LABO INSCRIT",
                    cip="3400930084939",
                    indication="Extension à l'enfant",
                )
            ],
            id_="JORFTEXT000054140032",
        )
        resultat = consolider(
            [inscription, extension, avis_contradictoire],
            DATE_JO,
            referentiel=referentiel,
        )
        (ligne,) = resultat.lignes
        self.assertEqual(ligne.section, SECTION_EXTENSIONS)
        self.assertFalse(ligne.a_verifier, ligne.motifs_verification)
        self.assertEqual(resultat.anomalies, [])  # rien au récapitulatif du mail

    def test_avis_deja_oriente_par_son_texte_inchange(self):
        """Un avis explicitement « baisse » n'est pas re-basculé par le référentiel."""
        referentiel = _ReferentielFactice(
            {"3400930084939": self._D("150.00")}
        )  # dirait hausse
        textes = [
            _texte(
                "avis_baisse_prix",
                [
                    ProduitExtrait(
                        "DARUNAVIR VIATRIS 400 mg, comprimé",
                        "VIATRIS",
                        cip="3400930084939",
                        ppttc="156,38 €",
                    )
                ],
            )
        ]
        resultat = consolider(textes, DATE_JO, referentiel=referentiel)
        self.assertEqual(resultat.lignes[0].section, SECTION_BAISSES)


class TestCasLimites(unittest.TestCase):
    def test_avis_non_oriente_sans_inscription_en_hausses_a_verifier(self):
        textes = [_texte("avis_prix", [ProduitExtrait("PRODUIT X 10 mg", "LABO")])]
        resultat = consolider(textes, DATE_JO)
        self.assertEqual(len(resultat.lignes), 1)
        ligne = resultat.lignes[0]
        self.assertEqual(ligne.section, SECTION_HAUSSES)
        self.assertTrue(ligne.a_verifier)
        self.assertTrue(any("non orienté" in a for a in resultat.anomalies))

    def test_decision_taux_isolee_signale_sans_ligne(self):
        textes = [_texte("decision_taux", [ProduitExtrait("PRODUIT Y", "LABO")])]
        resultat = consolider(textes, DATE_JO)
        self.assertEqual(resultat.lignes, [])  # aucune section applicable
        self.assertTrue(
            any("PRODUIT Y" in a for a in resultat.anomalies)
        )  # jamais silencieux

    def test_indication_manquante_a_completer(self):
        """Inscription sans indication de section : jamais de vide silencieux."""
        textes = [
            _texte(
                "arrete_inscription",
                [ProduitExtrait("PRODUIT Z 5 mg", "LABO")],
                listes=["SS"],
            )
        ]
        resultat = consolider(textes, DATE_JO)
        self.assertEqual(resultat.lignes[0].indication, "à compléter manuellement")

    def test_indication_de_section_conservee(self):
        """L'indication attachée par l'analyse (section de tableau) est recopiée telle quelle."""
        textes = [
            _texte(
                "arrete_inscription",
                [
                    ProduitExtrait(
                        "PRODUIT W 5 mg",
                        "LABO",
                        indication="recopie exacte de la section",
                    )
                ],
                listes=["SS"],
            )
        ]
        resultat = consolider(textes, DATE_JO)
        self.assertEqual(resultat.lignes[0].indication, "recopie exacte de la section")

    def test_indications_divergentes_toutes_conservees(self):
        """Cas FULBEV (JO du 19/05/2025, exemple utilisatrice) : plusieurs indications
        pour un même nom → toutes recopiées, dans l'ordre, sans doublon."""
        textes = [
            _texte(
                "arrete_inscription",
                [
                    ProduitExtrait(
                        "FULBEV 25 mg/ml, solution", "LABO", indication="Indication A"
                    ),
                    ProduitExtrait(
                        "FULBEV 100 mg/4 ml, solution",
                        "LABO",
                        indication="Indication B",
                    ),
                    ProduitExtrait(
                        "FULBEV 400 mg/16 ml, solution",
                        "LABO",
                        indication="Indication A",
                    ),
                ],
                listes=["SS"],
            )
        ]
        resultat = consolider(textes, DATE_JO)
        (ligne,) = resultat.lignes
        self.assertEqual(ligne.indication, "Indication A\nIndication B")

    def test_arrete_ambigu_signale(self):
        """Arrêté dont la liste n'a pas été lue dans le titre : ligne inscrite quand
        même (section Inscriptions), « à vérifier »."""
        textes = [
            _texte(
                "arrete_inscription",
                [ProduitExtrait("PRODUIT V 5 mg", "LABO")],
                ambigu=True,
            )
        ]
        resultat = consolider(textes, DATE_JO)
        (ligne,) = resultat.lignes
        self.assertEqual(ligne.section, SECTION_INSCRIPTIONS)
        self.assertTrue(ligne.a_verifier)
        self.assertEqual(ligne.listes, [])


class TestFusionDesContributionsCommunes(unittest.TestCase):
    """Sémantique de fusion, axe par axe (`_Cumul.fusionner_contributions_communes`).

    Fusion asymétrique : la ligne du laboratoire gagne tout conflit. Une inversion de
    priorité ici ne casserait aucun test de bout en bout tant qu'un seul laboratoire est
    en jeu — elle se verrait seulement sur les génériques (AZELASTINE, 6 laboratoires).
    """

    def _cumul(self, type_texte, id_, listes=(), indication="", ambigu=False):
        cumul = rapprochement._Cumul()
        produit = ProduitExtrait("PRODUIT F 5 mg", "LABO", indication=indication)
        rapprochement._accumuler(
            cumul,
            _texte(type_texte, [produit], id_=id_, listes=listes, ambigu=ambigu),
            produit,
        )
        return cumul

    def test_drapeaux_cumules_liens_du_laboratoire_conserves(self):
        ligne = self._cumul("arrete_inscription", "JORFTEXT000000000001", listes=["SS"])
        commun = self._cumul(
            "arrete_inscription", "JORFTEXT000000000002", listes=["SS", "Collectivité"]
        )
        commun.radiation.constater(["LES MCO"], URL.format("JORFTEXT000000000003"))
        ligne.fusionner_contributions_communes(commun)
        self.assertTrue(ligne.inscription.vise and ligne.radiation.vise)
        # Premier lien vu gagne : « SS » garde l'arrêté de la ligne, pas celui du commun.
        self.assertEqual(
            ligne.inscription.listes["SS"], URL.format("JORFTEXT000000000001")
        )
        self.assertEqual(
            ligne.inscription.listes["Collectivité"], URL.format("JORFTEXT000000000002")
        )
        self.assertEqual(list(ligne.radiation.listes), ["LES MCO"])

    def test_prix_premier_lien_conserve_et_sens_unis(self):
        ligne = self._cumul("avis_baisse_prix", "JORFTEXT000000000001")
        commun = self._cumul("avis_prix", "JORFTEXT000000000002")
        ligne.prix.sens_constates.add("baisse")
        commun.prix.sens_constates.add("hausse")
        ligne.fusionner_contributions_communes(commun)
        self.assertTrue(ligne.prix.baisse and ligne.prix.non_oriente)
        self.assertFalse(ligne.prix.hausse)
        self.assertEqual(ligne.prix.lien, URL.format("JORFTEXT000000000001"))
        self.assertEqual(ligne.prix.sens_constates, {"hausse", "baisse"})

    def test_extension_et_modification_gardent_le_lien_de_la_ligne(self):
        ligne = self._cumul("extension_indication", "JORFTEXT000000000001")
        commun = self._cumul("extension_indication", "JORFTEXT000000000002")
        commun.modification.constater(URL.format("JORFTEXT000000000003"))
        ligne.fusionner_contributions_communes(commun)
        self.assertEqual(ligne.extension.lien, URL.format("JORFTEXT000000000001"))
        self.assertEqual(ligne.modification.lien, URL.format("JORFTEXT000000000003"))

    def test_tracabilite_ordre_preserve_sans_doublon(self):
        ligne = self._cumul(
            "arrete_inscription",
            "JORFTEXT000000000001",
            listes=["SS"],
            indication="Indication A",
        )
        commun = self._cumul(
            "extension_indication",
            "JORFTEXT000000000002",
            indication="Indication B",
            ambigu=True,
        )
        commun.signaler("motif du commun")
        ligne.signaler("motif de la ligne")
        ligne.fusionner_contributions_communes(commun)
        self.assertEqual(
            ligne.tracabilite.indications, ["Indication A", "Indication B"]
        )
        self.assertEqual(
            ligne.tracabilite.sources,
            [
                ("JORFTEXT000000000001", "arrêté d'inscription"),
                ("JORFTEXT000000000002", "extension d'indication"),
            ],
        )
        self.assertEqual(
            ligne.tracabilite.motifs,
            [
                "motif de la ligne",
                "classification ambiguë du texte JORFTEXT000000000002",
                "motif du commun",
            ],
        )
        self.assertTrue(ligne.a_verifier and ligne.porteur)

    def test_fusion_idempotente(self):
        """Fusionner deux fois le même commun ne duplique rien (le rejeu est sans effet)."""
        ligne = self._cumul("arrete_inscription", "JORFTEXT000000000001", listes=["SS"])
        commun = self._cumul(
            "avis_prix", "JORFTEXT000000000002", indication="Indication B"
        )
        ligne.fusionner_contributions_communes(commun)
        attendu = (
            dict(ligne.inscription.listes),
            ligne.prix.lien,
            list(ligne.tracabilite.indications),
            list(ligne.tracabilite.sources),
            list(ligne.tracabilite.motifs),
        )
        ligne.fusionner_contributions_communes(commun)
        self.assertEqual(
            (
                dict(ligne.inscription.listes),
                ligne.prix.lien,
                list(ligne.tracabilite.indications),
                list(ligne.tracabilite.sources),
                list(ligne.tracabilite.motifs),
            ),
            attendu,
        )


class TestSectionDuCumulEstPure(unittest.TestCase):
    """A4 : le choix de section est une requête — il ne mute plus le cumul (CQS)."""

    def test_avis_non_oriente_retourne_le_motif_sans_signaler(self):
        cumul = rapprochement._Cumul()
        cumul.prix.constater("avis_prix", URL.format("JORFTEXT000000000001"))
        section, motif = rapprochement._section_du_cumul(cumul)
        self.assertEqual(section, SECTION_HAUSSES)
        self.assertEqual(
            motif,
            f"avis de prix non orienté ({cumul.prix.lien}) : classé en "
            "Hausses de prix par convention, sens à vérifier",
        )
        self.assertFalse(cumul.a_verifier)  # aucune mutation cachée
        self.assertEqual(cumul.tracabilite.motifs, [])

    def test_section_orientee_sans_motif(self):
        cumul = rapprochement._Cumul()
        cumul.prix.constater("avis_baisse_prix", URL.format("JORFTEXT000000000001"))
        self.assertEqual(
            rapprochement._section_du_cumul(cumul), (SECTION_BAISSES, None)
        )


class TestOrdreDeSortie(unittest.TestCase):
    """Invariants d'ordre de `consolider` — l'export Excel, la recette `compare_cible` et
    le récapitulatif du mail en dépendent, et aucun autre test ne les fixe."""

    def test_ordre_des_lignes_suit_l_apparition_dans_les_textes(self):
        """Racines dans l'ordre de première apparition ; pour une racine, laboratoires
        dans l'ordre où leurs clés ont été vues."""
        textes = [
            _texte(
                "arrete_inscription",
                [
                    ProduitExtrait("ZORRO 10 mg, comprimé", "VIATRIS"),
                    ProduitExtrait("ALPHA 5 mg, comprimé", "TEVA"),
                    ProduitExtrait("ZORRO 20 mg, comprimé", "ARROW"),
                ],
                listes=["SS"],
            )
        ]
        resultat = consolider(textes, DATE_JO)
        self.assertEqual(
            [(l.produit, l.laboratoire) for l in resultat.lignes],
            [("ZORRO", "VIATRIS"), ("ZORRO", "ARROW"), ("ALPHA", "TEVA SANTE")],
        )

    def test_anomalies_sans_section_avant_le_recapitulatif(self):
        """Une racine sans section applicable est signalée avant les lignes « à
        vérifier », même quand elle apparaît après elles dans le sommaire du JO."""
        textes = [
            _texte(
                "avis_prix",
                [ProduitExtrait("DOUTEUX 10 mg", "LABO")],
                id_="JORFTEXT000000000001",
            ),
            _texte(
                "decision_taux",
                [ProduitExtrait("TAUX SEUL 5 mg", "LABO")],
                id_="JORFTEXT000000000002",
            ),
        ]
        resultat = consolider(textes, DATE_JO)
        self.assertEqual(len(resultat.anomalies), 2)
        self.assertTrue(
            resultat.anomalies[0].startswith("TAUX SEUL : vu uniquement dans")
        )
        self.assertTrue(resultat.anomalies[1].startswith("DOUTEUX : à vérifier —"))

    def test_recapitulatif_une_entree_par_racine_et_non_par_laboratoire(self):
        """Cas AZELASTINE (JO du 07/07/2026) : un avis douteux sur un générique à
        6 laboratoires donne 6 lignes mais UNE seule entrée dans le mail."""
        labos = ["BIOGARAN", "TEVA", "ARROW", "SANDOZ", "ZENTIVA", "ACCORD"]
        textes = [
            _texte(
                "avis_prix",
                [ProduitExtrait("GENERIQUE 10 mg, comprimé", labo) for labo in labos],
            )
        ]
        resultat = consolider(textes, DATE_JO)
        self.assertEqual(len(resultat.lignes), 6)
        self.assertTrue(all(l.a_verifier for l in resultat.lignes))
        self.assertEqual(len(resultat.anomalies), 1)
        self.assertTrue(resultat.anomalies[0].startswith("GENERIQUE : à vérifier —"))


if __name__ == "__main__":
    unittest.main()
