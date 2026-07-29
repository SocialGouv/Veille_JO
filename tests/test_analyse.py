"""Tests hors ligne du volet déterministe d'`analyse.py` (E3).

Le run réel (types et produits des 11 textes de l'annexe E) exige des clés PISTE.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import analyse

TABLE_INSCRIPTION = """
<p>Texte de tête.</p>
<table>
 <tr><th>Code CIP</th><th>Dénomination de la spécialité</th><th>Laboratoire exploitant</th></tr>
 <tr><td>3400930000001</td><td>WEGOVY 0,25 mg, solution injectable en stylo prérempli FlexTouch</td><td>NOVO NORDISK</td></tr>
 <tr><td>3400930000002</td><td>LIKOZAM 1 mg/ml, sirop</td><td>ADVICENNE</td></tr>
</table>
"""

TABLE_SANS_ENTETE_RECONNU = """
<table>
 <tr><td>3400930000003</td><td>FYCOMPA 2 mg, comprimé (EISAI)</td><td>4,52 €</td></tr>
</table>
"""

# Sous-en-tête RÉPÉTÉ au milieu des données : structure constatée au run réel du
# 21/07/2026, où une cellule « Code CIP » de sous-en-tête sortait en ligne produit
# (d'où le filtre `LIBELLES_EN_TETE`). Les longs tableaux d'arrêtés rappellent leurs
# en-têtes à chaque saut de page.
TABLE_SOUS_ENTETE_INTERMEDIAIRE = """
<table>
 <tr><th>Code CIP</th><th>Présentation</th></tr>
 <tr><td>34009 301 631 6 0</td><td>LACOSAMIDE G.L. PHARMA 100 mg, comprimés pelliculés (B/56)</td></tr>
 <tr><td>Code CIP</td><td>Présentation</td></tr>
 <tr><td>34009 303 394 1 1</td><td>METHYLPHENIDATE VIATRIS SANTE LP 18 mg, comprimés</td></tr>
</table>
"""

# Même rappel d'en-tête, mais aux libellés RÉELS des arrêtés (ceux de TABLE_INSCRIPTION,
# multi-mots) : le filtre `LIBELLES_EN_TETE` ne teste que l'égalité exacte à des mots
# isolés, si bien que « Dénomination de la spécialité » passait et sortait en ligne
# produit fantôme (défaut constaté le 29/07/2026, antérieur au refactoring). Trois formes
# de rappel : à l'identique, en capitales non accentuées (casse et accents varient d'un
# saut de page à l'autre), et partiel (numéro de page dans la dernière colonne).
# Dernière rangée : une SEULE
# cellule reproduit son en-tête (« PPTTC ») mais la dénomination est réelle — le produit
# doit être conservé, la règle porte sur la dénomination, pas sur la rangée.
TABLE_RAPPEL_ENTETES_REELS = """
<table>
 <tr><th>Code CIP</th><th>Dénomination de la spécialité</th><th>Laboratoire exploitant</th><th>PPTTC</th></tr>
 <tr><td>3400930000001</td><td>WEGOVY 0,25 mg, solution injectable</td><td>NOVO NORDISK</td><td>4,52 €</td></tr>
 <tr><td>Code CIP</td><td>Dénomination de la spécialité</td><td>Laboratoire exploitant</td><td>PPTTC</td></tr>
 <tr><td>3400930000002</td><td>LIKOZAM 1 mg/ml, sirop</td><td>ADVICENNE</td><td>5,10 €</td></tr>
 <tr><td>CODE CIP</td><td>DENOMINATION DE LA SPECIALITE</td><td>LABORATOIRE EXPLOITANT</td><td>PPTTC</td></tr>
 <tr><td>3400930000003</td><td>FYCOMPA 2 mg, comprimé</td><td>EISAI</td><td>6,20 €</td></tr>
 <tr><td>Code CIP</td><td>Dénomination de la spécialité</td><td>Laboratoire exploitant</td><td>page 2</td></tr>
 <tr><td>3400930000004</td><td>GARDASIL 9 0,5 ml, suspension injectable</td><td>MSD FRANCE</td><td>PPTTC</td></tr>
</table>
"""

# Tableau SANS en-tête réel dont la PREMIÈRE rangée est prise pour un en-tête :
# `_index_colonnes` reconnaît un libellé de colonne par SOUS-CHAÎNE, et « nom » est dans
# « NOMEGESTROL ». Cette première rangée servait alors de gabarit de rappel d'en-tête à
# tout le tableau, et les rangées reproduisant ce produit disparaissaient en silence
# (effet de bord du 29/07/2026 ; forme réelle : les avis de prix d'un même générique
# répètent la même dénomination pour plusieurs CIP).
TABLE_SANS_ENTETE_PREMIERE_RANGEE_CRUE_ENTETE = """
<table>
 <tr><td>NOMEGESTROL ACETATE VIATRIS 3,75 mg, comprimé</td><td>34009 300 000 1 1</td></tr>
 <tr><td>ESTRADIOL ARROW 1 mg, comprimé</td><td>34009 300 000 2 2</td></tr>
 <tr><td>NOMEGESTROL ACETATE VIATRIS 3,75 mg, comprimé</td><td>34009 300 000 3 3</td></tr>
</table>
"""

# Rappels d'en-tête PARTIELS aux cellules vides : le libellé est seul sur sa rangée, soit
# que les autres cellules soient vides, soit que le rappel tienne dans un `colspan`. Une
# règle qui exigerait deux cellules rappelées les laisserait passer en lignes produit.
TABLE_RAPPEL_PARTIEL_CELLULES_VIDES = """
<table>
 <tr><th>Code CIP</th><th>Dénomination de la spécialité</th><th>Laboratoire exploitant</th></tr>
 <tr><td>3400930000001</td><td>PARTIELIN 10 mg, comprimé</td><td>LABO PARTIEL</td></tr>
 <tr><td></td><td>Dénomination de la spécialité</td><td></td></tr>
 <tr><td>3400930000002</td><td>PARTIELIN 20 mg, comprimé</td><td>LABO PARTIEL</td></tr>
 <tr><td colspan="3">DENOMINATION DE LA SPECIALITE</td></tr>
 <tr><td>3400930000003</td><td>PARTIELIN 40 mg, comprimé</td><td>LABO PARTIEL</td></tr>
</table>
"""

# Tableau purement tarifaire sans en-tête reconnu : ni la cellule de sous-en-tête
# (« Code CIP »), ni le code lui-même, ni le montant ne sont des dénominations.
TABLE_TARIFAIRE_SANS_DENOMINATION = """
<table>
 <tr><td>Code CIP</td><td>Prix</td></tr>
 <tr><td>3400930000004</td><td>4,52 €</td></tr>
</table>
"""

# Structure réelle des arrêtés d'inscription multi-produits (JO du 22/07/2026, JORFTEXT
# …451013) : chaque indication précède le tableau des présentations qu'elle concerne,
# CIP groupés par espaces, laboratoire dans la parenthèse « (laboratoires X) ».
ARRETE_SECTIONS = """
<p>Arrête :</p>
<p>1. - Sont inscrites sur la liste des médicaments remboursables aux assurés sociaux les spécialités suivantes. Les seules indications thérapeutiques ouvrant droit à la prise en charge ou au remboursement par l'assurance maladie sont, pour les spécialités visées ci-dessous : - en monothérapie et en association dans le traitement des crises partielles.</p>
<table>
 <tr><th>Code CIP</th><th>Présentation</th></tr>
 <tr><td>34009 301 631 6 0</td><td>LACOSAMIDE G.L. PHARMA 100 mg, comprimés pelliculés (B/56) (laboratoires STRAGEN FRANCE)</td></tr>
</table>
<p>2. - Sont inscrites sur la liste des médicaments remboursables aux assurés sociaux les spécialités suivantes. Les seules indications thérapeutiques ouvrant droit à la prise en charge par l'assurance maladie sont, pour les spécialités visées ci-dessous, celles qui figurent à l'autorisation de mise sur le marché à la date de publication du présent arrêté.</p>
<table>
 <tr><th>Code CIP</th><th>Présentation</th></tr>
 <tr><td>34009 303 394 1 1</td><td>METHYLPHENIDATE VIATRIS SANTE LP 18 mg, comprimés (laboratoires VIATRIS SANTE)</td></tr>
</table>
"""

# Arrêté d'inscription en liste en sus réel (JO du 23/07/2026, JORFTEXT…457566) : le
# tableau s'ouvre sur la DCI, la spécialité ne vient qu'en 2e colonne, et l'UCD porte un
# libellé abrégé. Format commun aux listes L. 162-22-7 (MCO) et L. 162-23-6 (SMR).
TABLE_LISTE_EN_SUS = """
<p>La spécialité suivante est inscrite sur la liste des spécialités pharmaceutiques facturables en sus des prestations d'hospitalisation visée à l'article L. 162-23-6 du code de la sécurité sociale.</p>
<table>
 <tr><th>Dénomination Commune Internationale</th><th>Libellé de la spécialité pharmaceutique</th><th>Code UCD</th><th>Libellé de l'UCD</th><th>Laboratoire exploitant ou titulaire de l'autorisation de mise sur le marché</th></tr>
 <tr><td>ENCORAFENIB</td><td>BRAFTOVI 75 mg gélules</td><td>3400894449393</td><td>BRAFTOVI 75MG GELU</td><td>PIERRE FABRE MEDICAMENT</td></tr>
</table>
"""

# Arrêté de modification de libellé réel (JO du 23/07/2026, JORFTEXT…457525) : deux blocs
# de colonnes, l'état abrogé à gauche, le nouveau à droite, et deux rangées d'en-tête. Les
# deux libellés d'une même rangée ne diffèrent que par leur « (laboratoires X) » : ces
# arrêtés transfèrent l'exploitation sans toucher au nom du produit.
TABLE_DEUX_BLOCS_LIBELLES = """
<p>L'annexe est modifiée comme suit :</p>
<table>
 <tr><th colspan="2">Libellés abrogés</th><th colspan="2">Nouveaux libellés</th></tr>
 <tr><th>Code CIP</th><th>Libellé</th><th>Code CIP</th><th>Libellé</th></tr>
 <tr><td>34009 301 541 7 5</td><td>CEFEPIME NORIDEM 1 g, poudre pour solution injectable (B/1) (laboratoires AGUETTANT)</td><td>34009 301 541 7 5</td><td>CEFEPIME NORIDEM 1 g, poudre pour solution injectable (B/1) (laboratoires DEMOGEN FRANCE SAS)</td></tr>
 <tr><td>34009 559 675 3 8</td><td>GEMZAR 1000 mg, poudre pour solution pour perfusion (B/1) (laboratoires LILLY FRANCE SAS)</td><td>34009 559 675 3 8</td><td>GEMZAR 1000 mg, poudre pour solution pour perfusion (B/1) (laboratoires CHEPLAPHARM FRANCE)</td></tr>
</table>
"""

# Décision UNCAM réelle (JO du 23/07/2026, JORFTEXT…458542) : le taux est en colonne, une
# ligne par présentation, et il s'écrit avec une espace insécable avant le « % ».
DECISION_TAUX = """
<p>Par décisions du directeur général de l'Union nationale des caisses d'assurance maladie en date du 27 avril 2026, le taux de participation de l'assuré applicable aux spécialités citées ci-dessous est fixé comme suit :</p>
<table>
 <tr><th>Code CIP</th><th>Présentation</th><th>Taux de participation</th></tr>
 <tr><td>34009 303 332 1 1</td><td>ATIMIAC 20 mg/5 mg par ml (dorzolamide, timolol), collyre en solution (laboratoires HORUS PHARMA)</td><td>35 %</td></tr>
 <tr><td>34009 303 034 8 1</td><td>EFFERALGAN 200 mg (paracétamol), suspension buvable (laboratoires UPSA SAS)</td><td>70 %</td></tr>
</table>
"""

# Avis de prix réel (JO du 22/07/2026, JORFTEXT…451565) : colonnes N° CIP / PFHT / PPTTC.
AVIS_PFHT = """
<p>Les prix des spécialités visées ci-dessous sont fixés comme suit :</p>
<table>
 <tr><th>N° CIP</th><th>Présentation</th><th>PFHT</th><th>PPTTC</th><th>Date d'effet</th></tr>
 <tr><td>34009 319 491 5 2</td><td>ORACILLINE 1 000 000 UI, comprimés sécables (B/12) (laboratoires TEOFARMA SRL)</td><td>3,21 €</td><td>3,87 €</td><td>01/08/2026</td></tr>
</table>
"""


class TestNettoyage(unittest.TestCase):
    def test_visas_considerants_et_html_supprimes(self):
        brut = ("<div>Vu le code de la sécurité sociale, notamment son article L. 162-16-4 ;\n"
                "Vu l'avis du comité économique des produits de santé ;\n"
                "Considérant que les conditions sont réunies ;\n"
                "Arrête :\nArticle 1er : les prix sont fixés comme suit.</div>" + TABLE_INSCRIPTION)
        texte, tableaux, _segments = analyse.nettoyer_texte(brut)
        self.assertNotIn("Vu le code", texte)
        self.assertNotIn("Considérant", texte)
        self.assertNotIn("<", texte)                      # plus de HTML résiduel
        self.assertIn("Article 1er", texte)               # le corps utile est conservé
        self.assertEqual(len(tableaux), 1)                 # les tables sont extraites à part
        self.assertNotIn("WEGOVY", texte)                  # ... et sorties du texte nettoyé

    def test_balises_en_ligne_fondues_dans_la_phrase(self):
        """Exposants, marques et liens ne sortent jamais sur leur propre ligne
        (« kg/m² » → « 2 » isolé, « MOUNJARO® » → « ® » isolé, constaté au 28/05)."""
        brut = ("<p>IMC initial ≥ 40 kg/m<sup>2</sup> sans comorbidité ;</p>"
                "<p>bon usage de MOUNJARO<sup>®</sup> et document prévu au III de "
                "l'<a href='x'>article R. 161-45 du code</a>.</p>")
        texte, _, _ = analyse.nettoyer_texte(brut)
        self.assertIn("40 kg/m2 sans comorbidité", texte)
        self.assertIn("MOUNJARO® et document", texte)
        self.assertIn("de l'article R. 161-45 du code.", texte)
        for ligne in texte.splitlines():
            self.assertGreater(len(ligne.strip()), 3, f"ligne orpheline : {ligne!r}")

    def test_reduction_de_taille_loggable(self):
        brut = "Vu " + "x" * 5000 + " ;\nArticle 1 : contenu utile."
        texte, _, _ = analyse.nettoyer_texte(brut)
        self.assertLess(len(texte), 100)


class TestClassification(unittest.TestCase):
    CAS = [
        ("Arrêté du 27 mai 2026 modifiant la liste des spécialités pharmaceutiques "
         "remboursables aux assurés sociaux", "arrete_inscription"),
        ("Arrêté du 27 mai 2026 modifiant la liste des spécialités pharmaceutiques agréées "
         "à l'usage des collectivités et divers services publics", "arrete_inscription"),
        # Titres LES et rétrocession (mots-clefs utilisatrice, mails des 22-23/07/2026).
        ("Arrêté du 2 juin 2026 modifiant la liste des spécialités pharmaceutiques prises "
         "en charge en sus des prestations d'hospitalisation mentionnée à l'article "
         "L. 162-22-7 du code de la sécurité sociale", "arrete_inscription"),
        ("Arrêté du 30 juin 2026 modifiant la liste des spécialités pharmaceutiques prises "
         "en charge en sus des prestations d'hospitalisation mentionnée à l'article "
         "L. 162-23-6 du code de la sécurité sociale", "arrete_inscription"),
        ("Arrêté du 21 juillet 2026 modifiant la liste des médicaments pouvant être vendus "
         "au public mentionnée à l'article L. 5126-6 du code de la santé publique",
         "arrete_inscription"),
        ("Arrêté du 20 mai 2026 portant radiation de spécialités pharmaceutiques de la "
         "liste mentionnée à l'article L. 162-22-7 du code de la sécurité sociale",
         "arrete_radiation"),
        ("Avis relatif aux prix de spécialités pharmaceutiques", "avis_prix"),
        ("Décision du 12 mai 2026 de l'Union nationale des caisses d'assurance maladie "
         "relative aux taux de participation de l'assuré applicables à des spécialités "
         "pharmaceutiques", "decision_taux"),
        ("Avis relatif à la majoration du prix de spécialités pharmaceutiques",
         "avis_hausse_prix"),
        ("Avis relatif aux baisses de prix de spécialités pharmaceutiques", "avis_baisse_prix"),
        ("Avis relatif à l'extension d'indication d'une spécialité pharmaceutique",
         "extension_indication"),
        ("Arrêté portant nomination au conseil d'administration", "autre"),
    ]

    def test_classification_par_titre(self):
        for titre, attendu in self.CAS:
            with self.subTest(titre=titre[:60]):
                self.assertEqual(analyse.classifier_par_titre(titre), attendu)

    def test_orientation_par_corps_jamais_par_defaut(self):
        """Piège MORPHINE : jamais de routage silencieux d'un avis de prix."""
        oriente = analyse.orienter_avis_prix("avis_prix", "le prix est majoré de 4 %")
        self.assertEqual(oriente, "avis_hausse_prix")
        oriente = analyse.orienter_avis_prix("avis_prix", "prix diminué à compter du…")
        self.assertEqual(oriente, "avis_baisse_prix")
        oriente = analyse.orienter_avis_prix("avis_prix", "les prix sont fixés ainsi")
        self.assertEqual(oriente, "avis_prix")            # non orienté, PAS « baisse »


    def test_avis_annoncant_les_deux_sens_marque_le_prix_et_non_la_classification(self):
        """Piège MORPHINE (tests.md) : un avis qui annonce une majoration ET une baisse
        reste non orienté, et sort marqué `prix_deux_sens` — c'est ce marquage qui interdit
        au référentiel de prix de trancher en aval (rapprochement.py).

        Câblage posé le 29/07/2026 : il manquait, si bien qu'un tel avis ressortait avec
        un sens unique affirmé en silence dès qu'un prix antérieur était connu. Un avis
        neutre ordinaire, lui, n'est PAS à deux sens : le référentiel doit pouvoir
        l'orienter.

        `ambigu` reste FAUX dans les deux cas : sa classification (« avis de prix ») ne
        fait aucun doute. Le premier câblage passait par ce champ, et faisait sortir
        « à vérifier » — avec le motif faux « classification ambiguë du texte … » — toute
        ligne alimentée par un tel avis, même quand la section venait d'une inscription
        (effet de bord corrigé le 29/07/2026, second tour).
        """
        titre = "Avis relatif aux prix de spécialités pharmaceutiques"
        deux_sens = ("<p>Le prix de la spécialité visée ci-dessous est majoré ; les prix "
                     "des autres présentations sont en baisse.</p>" + TABLE_INSCRIPTION)
        resultat = analyse.analyser_texte_deterministe("JORFTEXT000054144856", titre,
                                                      deux_sens)
        self.assertEqual(resultat.type_texte, "avis_prix")   # non orienté, jamais deviné
        self.assertTrue(resultat.prix_deux_sens)
        self.assertFalse(resultat.ambigu)

        neutre = ("<p>Les prix des spécialités visées ci-dessous sont fixés comme "
                  "suit :</p>" + TABLE_INSCRIPTION)
        resultat_neutre = analyse.analyser_texte_deterministe("JORFTEXT000054144858",
                                                             titre, neutre)
        self.assertEqual(resultat_neutre.type_texte, "avis_prix")
        self.assertFalse(resultat_neutre.prix_deux_sens)
        self.assertFalse(resultat_neutre.ambigu)


class TestListesEtOrientationArretes(unittest.TestCase):
    """Révision du 23/07/2026 : 5 listes lues dans le titre, corps des arrêtés
    départageant inscriptions / radiations / modifications de libellé."""

    def test_listes_du_titre(self):
        cas = [
            ("… remboursables aux assurés sociaux", ["SS"]),
            ("… agréées à l'usage des collectivités et divers services publics",
             ["Collectivité"]),
            ("… mentionnée à l'article L. 162-22-7 du code de la sécurité sociale",
             ["LES MCO"]),
            ("… mentionnée à l'article L. 162-23-6 du code de la sécurité sociale",
             ["LES SMR"]),
            ("… mentionnée à l'article L. 5126-6 du code de la santé publique",
             ["Rétrocession"]),
            ("Arrêté portant nomination", []),
        ]
        for titre, attendu in cas:
            with self.subTest(titre=titre[:50]):
                self.assertEqual(analyse.listes_du_titre(titre), attendu)

    def test_orientation_radiation_par_le_corps(self):
        """Arrêté au titre d'inscription dont le corps radie : reclassé radiation."""
        self.assertEqual(
            analyse.orienter_arrete("arrete_inscription",
                                    "Les spécialités suivantes sont radiées de la liste…"),
            "arrete_radiation")

    def test_orientation_libelle_par_le_corps(self):
        self.assertEqual(
            analyse.orienter_arrete("arrete_inscription",
                                    "Le libellé de la spécialité est remplacé par…"),
            "modification_libelle")

    def test_orientation_extension_par_le_corps(self):
        """Marqueur d'annexe constaté sur pièces (CYPROTERONE 07/07, SIRTURO 23/07) :
        « ANNEXE (1 extension d'indication) » dans un arrêté au titre d'inscription."""
        corps = ("Arrêtent : ANNEXE (1 extension d'indication) La prise en charge de la "
                 "spécialité ci-dessous est étendue à l'indication suivante : …")
        self.assertEqual(analyse.orienter_arrete("arrete_inscription", corps),
                         "extension_indication")

    def test_inscription_reste_inscription(self):
        self.assertEqual(
            analyse.orienter_arrete("arrete_inscription",
                                    "Sont inscrites sur la liste les spécialités suivantes."),
            "arrete_inscription")
        # Les autres types ne sont jamais réorientés.
        self.assertEqual(analyse.orienter_arrete("avis_prix", "sont radiées"), "avis_prix")


class TestParsingTableaux(unittest.TestCase):
    def test_table_inscription_denomination_et_labo(self):
        _, tableaux, _ = analyse.nettoyer_texte(TABLE_INSCRIPTION)
        produits = analyse.parser_tableaux(tableaux)
        self.assertEqual(len(produits), 2)
        self.assertEqual(produits[0].denomination_brute,
                         "WEGOVY 0,25 mg, solution injectable en stylo prérempli FlexTouch")
        self.assertEqual(produits[0].laboratoire_brut, "NOVO NORDISK")

    def test_table_sans_entete_ignore_cip_et_prix(self):
        _, tableaux, _ = analyse.nettoyer_texte(TABLE_SANS_ENTETE_RECONNU)
        produits = analyse.parser_tableaux(tableaux)
        self.assertEqual(len(produits), 1)
        self.assertIn("FYCOMPA", produits[0].denomination_brute)
        self.assertEqual(produits[0].laboratoire_brut, "EISAI")   # labo depuis la parenthèse

    def test_sous_entete_intermediaire_jamais_un_produit(self):
        """Un en-tête répété au milieu des données (saut de page des longs tableaux
        d'arrêtés) ne crée aucune fausse ligne : « Code CIP » et « Présentation » sont
        des libellés d'en-tête, jamais des dénominations (filtre `LIBELLES_EN_TETE`,
        posé après le run réel du 21/07/2026)."""
        _, tableaux, _ = analyse.nettoyer_texte(TABLE_SOUS_ENTETE_INTERMEDIAIRE)
        produits = analyse.parser_tableaux(tableaux)
        self.assertEqual([p.denomination_brute.split(" ")[0] for p in produits],
                         ["LACOSAMIDE", "METHYLPHENIDATE"])
        # Les deux vraies présentations gardent leur CIP : aucune ligne perdue au passage.
        self.assertEqual([p.cip for p in produits], ["3400930163160", "3400930339411"])

    def test_rangee_de_rappel_a_libelles_reels_jamais_un_produit(self):
        """Cas métier « aucune fausse ligne produit issue de la structure des tableaux »
        (tests.md), rejoué sur les libellés RÉELS des arrêtés : une rangée dont la
        dénomination reproduit un en-tête du tableau (« Dénomination de la spécialité »)
        ne donne aucun produit, quelles que soient sa casse et son accentuation, et même
        si le reste de la rangée n'est pas un rappel exact (numéro de page).

        Défaut réparé le 29/07/2026 : ces libellés multi-mots échappaient au filtre
        `LIBELLES_EN_TETE` (égalité exacte à des mots isolés) et sortaient en ligne
        « DÉNOMINATION DE LA SPÉCIALITÉ / Laboratoire exploitant » en Nouvelles
        inscriptions, avec l'indication et le lien de l'arrêté et SANS « (à vérifier) » —
        donc absente du récapitulatif, invisible au contrôle.
        """
        _, tableaux, _ = analyse.nettoyer_texte(TABLE_RAPPEL_ENTETES_REELS)
        produits = analyse.parser_tableaux(tableaux)
        self.assertEqual([p.denomination_brute.split(" ")[0] for p in produits],
                         ["WEGOVY", "LIKOZAM", "FYCOMPA", "GARDASIL"])
        # Les vraies présentations gardent leur laboratoire et leur CIP au passage.
        self.assertEqual([p.laboratoire_brut for p in produits],
                         ["NOVO NORDISK", "ADVICENNE", "EISAI", "MSD FRANCE"])
        self.assertEqual([p.cip for p in produits],
                         ["3400930000001", "3400930000002", "3400930000003",
                          "3400930000004"])

    def test_premiere_rangee_crue_entete_ne_filtre_pas_les_produits_du_tableau(self):
        """Cas métier « aucune ligne perdue en silence » (tests.md) : un tableau sans
        en-tête réel ne se filtre pas lui-même.

        Effet de bord de la réparation du rappel d'en-tête, constaté le 29/07/2026 : la
        première rangée devenait le gabarit du filtrage, et comme `_index_colonnes` la
        croit en-tête dès qu'une cellule CONTIENT un libellé de colonne (« nom » dans
        « NOMEGESTROL »), la 3e rangée — même dénomination, autre CIP, donc un vrai
        médicament — sortait de la newsletter sans anomalie, sans « (à vérifier) » et sans
        log. Le gabarit ne retient désormais que les cellules SANS chiffre.
        """
        _, tableaux, _ = analyse.nettoyer_texte(
            TABLE_SANS_ENTETE_PREMIERE_RANGEE_CRUE_ENTETE)
        produits = analyse.parser_tableaux(tableaux)
        # La rangée répétant la dénomination de la première est bien revenue, avec SON CIP.
        self.assertIn("NOMEGESTROL ACETATE VIATRIS 3,75 mg, comprimé",
                      [p.denomination_brute for p in produits])
        self.assertIn("3400930000033", [p.cip for p in produits])
        # Aucun gabarit n'est constitué : le tableau n'a pas de libellé d'en-tête sans
        # chiffre. Les deux rangées qui suivent la première sortent donc entières.
        self.assertEqual([p.denomination_brute for p in produits],
                         ["ESTRADIOL ARROW 1 mg, comprimé",
                          "NOMEGESTROL ACETATE VIATRIS 3,75 mg, comprimé"])
        # NB : la 1re rangée reste consommée comme rangée d'en-tête (`entete_reconnu`) —
        # défaut ANTÉRIEUR et distinct, hors du périmètre de cette réparation, documenté
        # dans les constats. Si `_index_colonnes` cesse un jour de croire cette rangée,
        # ce test attendra trois produits.

    def test_rappel_d_entete_partiel_a_cellules_vides_jamais_un_produit(self):
        """Contre-épreuve de la réparation ci-dessus : la couverture du défaut d'origine
        ne doit rien perdre. Un rappel d'en-tête réduit à UNE cellule (autres cellules
        vides, ou `colspan`) reste écarté — d'où la règle « deux cellules rappelées OU
        toutes les cellules non vides », et non « deux cellules » seule."""
        _, tableaux, _ = analyse.nettoyer_texte(TABLE_RAPPEL_PARTIEL_CELLULES_VIDES)
        produits = analyse.parser_tableaux(tableaux)
        self.assertEqual([p.denomination_brute for p in produits],
                         ["PARTIELIN 10 mg, comprimé", "PARTIELIN 20 mg, comprimé",
                          "PARTIELIN 40 mg, comprimé"])

    def test_ligne_tarifaire_et_code_ne_donnent_aucun_produit(self):
        """Tableau sans en-tête reconnu ne portant que codes et montants : rien n'en
        sort — ni le sous-en-tête, ni le code CIP, ni le prix. Jamais de produit
        inventé, et le rapprochement n'a pas de ligne fantôme à traiter."""
        _, tableaux, _ = analyse.nettoyer_texte(TABLE_TARIFAIRE_SANS_DENOMINATION)
        self.assertEqual(analyse.parser_tableaux(tableaux), [])

    def test_les_deux_motifs_de_code_ont_des_perimetres_distincts(self):
        """`MOTIF_CODE_TARIFAIRE` et `MOTIF_CIP_UCD` ne sont PAS redondants (vérifié
        cellule par cellule le 29/07/2026) : aucun ne contient l'autre, et la décision
        « cette cellule est un code, pas une dénomination » est leur union. Les unifier
        ferait entrer ou sortir des lignes produit."""
        groupe_par_espaces = "34009 301 631 6 0"   # format réel des tableaux 28/05 et 22/07
        autre_prefixe = "4000930000011"            # 13 chiffres, hors 34008/34009
        self.assertFalse(analyse.MOTIF_CODE_TARIFAIRE.match(groupe_par_espaces))
        self.assertTrue(analyse._cip_normalise(groupe_par_espaces))
        self.assertTrue(analyse.MOTIF_CODE_TARIFAIRE.match(autre_prefixe))
        self.assertFalse(analyse._cip_normalise(autre_prefixe))
        for cellule in (groupe_par_espaces, autre_prefixe):
            self.assertTrue(analyse._est_code_produit(cellule), cellule)

    def test_code_de_prefixe_inconnu_declenche_le_repli_de_denomination(self):
        """Conséquence du test précédent : un code que seul `MOTIF_CODE_TARIFAIRE`
        reconnaît, posé dans la colonne de dénomination, fait chercher le vrai nom dans
        les autres cellules — la ligne n'est pas perdue comme ligne tarifaire."""
        table = "<table><tr><td>4000930000011</td><td>DELTA 2 mg</td></tr></table>"
        _, tableaux, _ = analyse.nettoyer_texte(table)
        (delta,) = analyse.parser_tableaux(tableaux)
        self.assertEqual(delta.denomination_brute, "DELTA 2 mg")
        self.assertEqual(delta.cip, "")   # ce préfixe n'est pas une clé de rapprochement

    def test_cellule_hors_bornes_ou_colonne_absente(self):
        """Les rangées du JO sont plus courtes que leur en-tête (cellules fusionnées) :
        lire une colonne absente ou hors bornes rend "", jamais une exception."""
        self.assertEqual(analyse._cellule(["a", "b"], None), "")
        self.assertEqual(analyse._cellule(["a", "b"], 5), "")
        self.assertEqual(analyse._cellule([" a ", "b"], 0), "a")


class TestSectionsEtPresentations(unittest.TestCase):
    """Évolutions du 22/07/2026 : indications par section, CIP, PPTTC, labo en parenthèse."""

    def test_indications_rattachees_a_chaque_tableau(self):
        """La liaison indication ↔ tableau est structurelle : chaque section la porte."""
        _, tableaux, segments = analyse.nettoyer_texte(ARRETE_SECTIONS)
        self.assertEqual(len(tableaux), 2)
        indications = [analyse.indication_de_section(s) for s in segments]
        self.assertTrue(indications[0].startswith("- en monothérapie et en association"))
        self.assertTrue(indications[1].startswith("celles qui figurent à l'autorisation"))

    def test_presentations_cip_labo_et_indication(self):
        _, tableaux, segments = analyse.nettoyer_texte(ARRETE_SECTIONS)
        produits = analyse.parser_tableaux(
            tableaux, indications_sections=[analyse.indication_de_section(s) for s in segments])
        self.assertEqual(len(produits), 2)
        lacosamide, methylphenidate = produits
        self.assertEqual(lacosamide.cip, "3400930163160")   # CIP groupé par espaces normalisé
        self.assertEqual(lacosamide.laboratoire_brut, "STRAGEN FRANCE")
        self.assertNotIn("laboratoires", lacosamide.denomination_brute)  # parenthèse retirée
        self.assertIn("LACOSAMIDE G.L. PHARMA 100 mg", lacosamide.denomination_brute)
        self.assertTrue(lacosamide.indication.startswith("- en monothérapie"))
        self.assertTrue(methylphenidate.indication.startswith("celles qui figurent"))
        self.assertEqual(methylphenidate.laboratoire_brut, "VIATRIS SANTE")

    def test_ppttc_recopie_par_presentation(self):
        _, tableaux, _ = analyse.nettoyer_texte(AVIS_PFHT)
        (oracilline,) = analyse.parser_tableaux(tableaux)
        self.assertEqual(oracilline.ppttc, "3,87 €")   # sert à l'orientation par référentiel
        self.assertEqual(oracilline.cip, "3400931949152")
        self.assertEqual(oracilline.laboratoire_brut, "TEOFARMA SRL")

    def test_liste_en_sus_la_specialite_et_non_la_dci(self):
        """La veille nomme la SPÉCIALITÉ, pas la molécule : « BRAFTOVI 75 mg gélules », et
        non « ENCORAFENIB » — c'est ce qu'écrit l'utilisatrice, et ce que publient les avis
        de prix du même produit.

        Défaut réparé le 29/07/2026 (JO du 23/07) : « Dénomination Commune Internationale »
        contient « dénomination » et ouvre le tableau, donc la première colonne l'emportait.
        La même erreur donnait VORICONAZOLE au lieu de VFEND (22/05), TEMOCILLINE au lieu de
        NEGABAN (04/06), INFLIXIMAB au lieu de REMSIMA (02/07) — et dédoublait le produit
        quand un autre texte du jour le nommait par sa marque."""
        _, tableaux, _ = analyse.nettoyer_texte(TABLE_LISTE_EN_SUS)
        (braftovi,) = analyse.parser_tableaux(tableaux)
        self.assertEqual(braftovi.denomination_brute, "BRAFTOVI 75 mg gélules")
        self.assertEqual(braftovi.laboratoire_brut, "PIERRE FABRE MEDICAMENT")
        self.assertEqual(braftovi.cip, "3400894449393")

    def test_deux_blocs_libelles_l_etat_nouveau_fait_foi(self):
        """Arrêté de modification de libellé : la présentation décrite est celle du bloc
        de droite (état nouveau), le bloc de gauche ne livre que l'exploitant cédant.

        Défaut réparé le 29/07/2026 : l'en-tête fusionné à deux cellules servait de gabarit
        à des rangées à quatre, et la veille annonçait l'ANCIEN exploitant."""
        _, tableaux, _ = analyse.nettoyer_texte(TABLE_DEUX_BLOCS_LIBELLES)
        cefepime, gemzar = analyse.parser_tableaux(tableaux)
        self.assertEqual(cefepime.laboratoire_brut, "DEMOGEN FRANCE SAS")
        self.assertEqual(cefepime.laboratoire_precedent, "AGUETTANT")
        self.assertEqual(gemzar.laboratoire_brut, "CHEPLAPHARM FRANCE")
        self.assertEqual(gemzar.laboratoire_precedent, "LILLY FRANCE SAS")
        # La dénomination et le CIP viennent du bloc de droite, sans sa parenthèse labo.
        self.assertEqual(cefepime.denomination_brute,
                         "CEFEPIME NORIDEM 1 g, poudre pour solution injectable (B/1)")
        self.assertEqual(cefepime.cip, "3400930154175")
        # Les deux rangées d'en-tête sont écartées : aucune ligne « Code CIP » fantôme.
        self.assertEqual(len(analyse.parser_tableaux(tableaux)), 2)

    def test_tableau_ordinaire_lu_sans_decalage(self):
        """Un tableau à un seul bloc n'est jamais découpé : pas de laboratoire précédent,
        et le gabarit reste celui de la première rangée."""
        _, tableaux, _ = analyse.nettoyer_texte(TABLE_INSCRIPTION)
        for produit in analyse.parser_tableaux(tableaux):
            self.assertEqual(produit.laboratoire_precedent, "")
        self.assertEqual(analyse._decalage_bloc_abroge(tableaux[0].find_all("tr")), 0)

    def test_deux_blocs_de_largeurs_incoherentes_non_reconnus(self):
        """Largeurs de blocs qui ne recouvrent pas la rangée de sous-en-têtes : gabarit
        refusé, lecture ordinaire — jamais de découpe au hasard, qui mélangerait les deux
        états sur une même ligne de veille."""
        table = ('<table>'
                 '<tr><th colspan="2">Libellés abrogés</th>'
                 '<th colspan="2">Nouveaux libellés</th></tr>'
                 '<tr><th>Code CIP</th><th>Libellé</th></tr>'
                 '<tr><td>34009 301 541 7 5</td><td>CEFEPIME NORIDEM 1 g '
                 '(laboratoires AGUETTANT)</td></tr></table>')
        _, tableaux, _ = analyse.nettoyer_texte(table)
        self.assertEqual(analyse._decalage_bloc_abroge(tableaux[0].find_all("tr")), 0)

    def test_taux_par_presentation_depuis_sa_colonne(self):
        """Décision UNCAM réelle : chaque présentation porte SON taux, en décimal, et
        deux taux distincts dans le même tableau restent distincts (colonne Taux)."""
        _, tableaux, _ = analyse.nettoyer_texte(DECISION_TAUX)
        atimiac, efferalgan = analyse.parser_tableaux(tableaux)
        self.assertEqual(atimiac.taux, "0.35")
        self.assertEqual(efferalgan.taux, "0.7")
        self.assertEqual(atimiac.cip, "3400930333211")

    def test_taux_global_quand_le_tableau_n_en_porte_pas(self):
        """Décision UNCAM qui énonce son taux une seule fois, dans sa phrase d'attaque :
        le repli le rattache à chaque présentation. Sans repli, taux « N/A »."""
        table = ("<table><tr><th>Code CIP</th><th>Présentation</th></tr>"
                 "<tr><td>34009 303 332 1 1</td><td>ATIMIAC 20 mg, collyre</td></tr></table>")
        _, tableaux, _ = analyse.nettoyer_texte(table)
        (sans_repli,) = analyse.parser_tableaux(tableaux)
        self.assertEqual(sans_repli.taux, "N/A")
        (avec_repli,) = analyse.parser_tableaux(tableaux, taux_global="0.65")
        self.assertEqual(avec_repli.taux, "0.65")

    def test_taux_unique_du_texte(self):
        """Un seul pourcentage énoncé → il fait foi ; plusieurs → « N/A » (jamais de
        choix arbitraire : piège « taux 1 » de VGENFLI)."""
        self.assertEqual(analyse.taux_unique_du_texte(
            "le taux de participation est fixé à 65 % pour les spécialités visées"), "0.65")
        self.assertEqual(analyse.taux_unique_du_texte(
            "les taux sont fixés à 35 % et 65 % selon les présentations"), "N/A")
        self.assertEqual(analyse.taux_unique_du_texte("aucun pourcentage ici"), "N/A")

    def test_code_ucd_extrait_comme_cle(self):
        """Les textes de la liste en sus (arrêtés et avis) publient des codes UCD
        (34008…) : même rôle de clé de rapprochement que le CIP (constat 04/06/2026)."""
        table = ("<table><tr><th>Code UCD</th><th>Libellé</th></tr>"
                 "<tr><td>34008 935 382 3 4</td><td>MEROPENEM PAN 1G INJ FL "
                 "(laboratoires PANPHARMA)</td></tr></table>")
        _, tableaux, _ = analyse.nettoyer_texte(table)
        (meropenem,) = analyse.parser_tableaux(tableaux)
        self.assertEqual(meropenem.cip, "3400893538234")
        self.assertEqual(meropenem.laboratoire_brut, "PANPHARMA")

    def test_indication_longue_recopiee_telle_quelle(self):
        """Demande utilisatrice du 22/07/2026 : une section longue (indication structurée
        + conditions de prise en charge) est recopiée en entier, jamais remplacée par
        « à compléter manuellement » (constaté sur WEGOVY/MOUNJARO au 28/05)."""
        segment = ("Les seules indications thérapeutiques ouvrant droit à la prise en charge "
                   "sont, pour les spécialités visées ci-dessous : " + "x" * 2000)
        self.assertEqual(analyse.indication_de_section(segment), "x" * 2000)

    def test_segment_sans_motif_indication(self):
        self.assertEqual(analyse.indication_de_section("Arrête : les prix sont fixés."), "")


class TestAnalyseComplete(unittest.TestCase):
    def test_analyser_texte_deterministe(self):
        brut = ("Vu le code de la sécurité sociale ;\n"
                "Article 1er : sont inscrites les spécialités suivantes." + TABLE_INSCRIPTION)
        titre = ("Arrêté du 27 mai 2026 modifiant la liste des spécialités pharmaceutiques "
                 "remboursables aux assurés sociaux")
        resultat = analyse.analyser_texte_deterministe("JORFTEXT000054144800", titre, brut)
        self.assertEqual(resultat.type_texte, "arrete_inscription")
        self.assertEqual(resultat.listes, ["SS"])
        self.assertFalse(resultat.ambigu)
        self.assertEqual(len(resultat.produits), 2)
        self.assertEqual(resultat.url,
                         "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000054144800")
        self.assertNotIn("Vu le code", resultat.texte_nettoye)


if __name__ == "__main__":
    unittest.main()
