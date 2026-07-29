"""Tests hors ligne de `notification.py` (E8) : structure du HTML au format des mails
manuels de l'utilisatrice (contrat du 23/07/2026).

Le brouillon Outlook (win32com) n'est pas testable pour de vrai hors du poste Windows
cible (voir INSTALL.md, « À valider sur le poste cible ») : la politique d'envoi, elle,
l'est — un faux `win32com.client` injecté dans `sys.modules` enregistre les appels et
`TestPolitiqueEnvoi` vérifie qu'aucun `.Send()` ne part sans autorisation explicite.
"""

import contextlib
import html
import re
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "fixtures"))

import config
import notification
from fixture_annexe_e import DATE_JO, URL, resultat_consolide_28_05
from rapprochement import (SECTION_EXTENSIONS, SECTION_MODIFICATIONS, SECTION_RADIATIONS,
                           SECTIONS, LigneConsolidee, ResultatVeille)

# Décision UNCAM qui publie le taux de WEGOVY dans la vérité terrain du 28/05.
URL_TAUX_WEGOVY = URL.format("JORFTEXT000054144868")


class TestCorpsHtml(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corps = notification.corps_html(resultat_consolide_28_05())

    def test_structure_du_gabarit(self):
        self.assertIn("Bonjour,", self.corps)
        self.assertIn("Veuillez trouver ci-dessous la publication du JO de ce jour&nbsp;:",
                      self.corps)
        self.assertIn("Cordialement,", self.corps)
        # L'ordre du gabarit est respecté.
        self.assertLess(self.corps.index("Bonjour"), self.corps.index("Veuillez trouver"))
        self.assertLess(self.corps.index("Veuillez trouver"),
                        self.corps.index("Nouvelles inscriptions"))
        self.assertLess(self.corps.index("Baisse de prix"), self.corps.index("Cordialement"))

    def test_ordre_des_six_sections(self):
        """Ordre d'affichage des 6 sections (contrat du 23/07/2026), mail ET Excel.

        Depuis la mise en source unique (`rapprochement.SECTIONS`, refacto phase 1),
        une permutation de cette liste casserait les DEUX rendus d'un coup : cet ordre
        n'était couvert par aucune assertion, seul « Nouvelles inscriptions » avant
        « Baisse de prix » l'était.
        """
        attendu = ["Nouvelles inscriptions", "Hausse de prix", "Baisse de prix",
                   "Modification de libellé", "Extensions d'indications", "Radiations"]
        # Toutes les sections servies : la fixture du 28/05 n'en couvre que deux, on
        # part donc d'un résultat où chaque section porte une ligne.
        resultat = ResultatVeille(date_jo=DATE_JO, lignes=[
            LigneConsolidee(produit=f"PRODUIT {cle}", date_jo=DATE_JO, laboratoire="LABO",
                            listes=[("SS", URL)], listes_radiation=[("SS", URL)],
                            lien_prix=URL, lien_modification=URL, lien_extension=URL,
                            section=cle, racine=f"PRODUIT {cle}")
            for cle, _titre, _couleur in SECTIONS])
        corps = notification.corps_html(resultat)
        # Les titres sont échappés dans le HTML (« d'indications » → « d&#x27;… »).
        positions = [corps.index(html.escape(titre)) for titre in attendu]
        self.assertEqual(positions, sorted(positions),
                         f"ordre des sections du mail ≠ {attendu}")

    def test_titres_des_sections(self):
        # « Nouvelles inscriptions » au pluriel : format des mails utilisatrice
        # (22-23/07/2026) ; hausse/baisse au singulier.
        self.assertIn("Nouvelles inscriptions<", self.corps)
        self.assertIn("Hausse de prix", self.corps)
        self.assertIn("Baisse de prix", self.corps)
        self.assertNotIn("Hausses de prix", self.corps)
        self.assertNotIn("Baisses de prix", self.corps)

    def test_bandeaux_aux_couleurs_de_l_excel(self):
        for couleur in ("#F2CEED", "#F6C5AC", "#C1F0C7"):
            self.assertIn(f"background:{couleur}", self.corps)

    def test_pas_de_colonne_date(self):
        self.assertNotIn(">Date<", self.corps)

    def _tableau_inscriptions(self) -> str:
        return self.corps[self.corps.index("Nouvelles inscriptions"):
                          self.corps.index("Hausse de prix")]

    def test_colonnes_inscriptions(self):
        """Colonnes du mail de l'utilisatrice (et du fichier CIBLE), dans son ordre :
        Produit, Laboratoire, Indication, Liste, Prix, Taux."""
        tableau = self._tableau_inscriptions()
        entetes = re.findall(r"><b>(Produit|Laboratoire|Indication|Liste|Prix|Taux)</b><",
                             tableau)
        self.assertEqual(entetes, ["Produit", "Laboratoire", "Indication", "Liste",
                                   "Prix", "Taux"])

    def test_prix_sans_montant_et_taux_en_pourcentage(self):
        """La colonne Prix reste un lien sans montant (23/07/2026) ; la colonne Taux
        porte le pourcentage entier de la décision UNCAM, cliquable vers elle."""
        tableau = self._tableau_inscriptions()
        self.assertIn(f'"{URL_TAUX_WEGOVY}" style="color:#467886;text-decoration:'
                      'underline">35%</a>', tableau)
        self.assertNotIn("0.35", tableau)
        self.assertNotIn("€", tableau)
        # VGENFLI : aucune décision de taux du jour ne le vise → « N/A », jamais de vide.
        vgenfli = tableau[tableau.index("VGENFLI"):]
        self.assertIn(">N/A</td>", vgenfli[:vgenfli.index("</tr>")])

    def test_liens_prix_hausses_baisses(self):
        # MORPHINE (hausse) et FYCOMPA (baisse) : lien texte « Site LégiFrance » seul.
        self.assertIn('href="https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000054144874"',
                      self.corps)
        self.assertIn('href="https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000054144876"',
                      self.corps)
        self.assertIn(">Site LégiFrance</a>", self.corps)

    def test_liste_un_lien_par_segment(self):
        """« 1 liste = 1 arrêté » : chaque segment est cliquable, joints par « & »."""
        self.assertIn(">SS</a> &amp; ", self.corps)
        self.assertIn(">Collectivité</a>", self.corps)
        self.assertIn('href="https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000054144800"',
                      self.corps)
        self.assertIn('href="https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000054144802"',
                      self.corps)

    def test_indication_multiligne_en_br(self):
        self.assertIn("invalidantes <br>", self.corps.replace("\n<br>", " <br>").replace("<br>\n", "<br>"))

    def test_pas_de_recapitulatif_sans_anomalie(self):
        self.assertNotIn("Récapitulatif des anomalies", self.corps)


def _ligne(section: str, **surcharges) -> LigneConsolidee:
    champs = dict(produit="PRODUIT T", date_jo=DATE_JO, laboratoire="LABO",
                  section=section, racine="PRODUIT T")
    champs.update(surcharges)
    return LigneConsolidee(**champs)


class TestNouvellesSections(unittest.TestCase):
    def test_modification_de_libelle(self):
        resultat = ResultatVeille(date_jo=DATE_JO, lignes=[
            _ligne(SECTION_MODIFICATIONS, lien_modification=URL.format("JORFTEXT1"))])
        corps = notification.corps_html(resultat)
        self.assertIn("Modification de libellé", corps)
        self.assertIn(">Lien</b>", corps)
        self.assertIn(f'href="{URL.format("JORFTEXT1")}"', corps)
        self.assertIn(">LABO</span>", corps)         # sans transfert : laboratoire seul

    def test_transfert_d_exploitation_affiche_les_deux_laboratoires(self):
        """Arrêté de modification de libellé qui change l'exploitant (cas nominal) : la
        colonne Laboratoire montre la transition, pour la voir sans ouvrir le texte."""
        resultat = ResultatVeille(date_jo=DATE_JO, lignes=[
            _ligne(SECTION_MODIFICATIONS, produit="GEMZAR", racine="GEMZAR",
                   laboratoire="CHEPLAPHARM", laboratoire_precedent="LILLY",
                   lien_modification=URL.format("JORFTEXT1"))])
        corps = notification.corps_html(resultat)
        self.assertIn(">LILLY → CHEPLAPHARM</span>", corps)

    def test_extensions_section_a_part_entiere(self):
        resultat = ResultatVeille(date_jo=DATE_JO, lignes=[
            _ligne(SECTION_EXTENSIONS, indication="Nouvelle indication",
                   lien_extension=URL.format("JORFTEXT2"))])
        corps = notification.corps_html(resultat)
        self.assertIn("Extensions d&#x27;indications", corps)   # apostrophe échappée
        self.assertIn("Nouvelle indication", corps)
        self.assertIn(f'href="{URL.format("JORFTEXT2")}"', corps)
        self.assertNotIn("Récapitulatif", corps)   # plus un cas d'anomalie depuis le 23/07

    def test_extension_regroupee_rappelle_listes_et_prix(self):
        """Règle SIRTURO : la ligne d'extension issue du regroupement rappelle ses
        listes d'inscription et son lien de prix sous l'indication."""
        resultat = ResultatVeille(date_jo=DATE_JO, lignes=[
            _ligne(SECTION_EXTENSIONS, produit="SIRTURO", racine="SIRTURO",
                   indication="En association appropriée…",
                   listes=[("Rétrocession", URL.format("JORFTEXT3"))],
                   lien_prix=URL.format("JORFTEXT4"),
                   lien_extension=URL.format("JORFTEXT5"))])
        corps = notification.corps_html(resultat)
        self.assertIn("Inscription :", corps)
        self.assertIn(">Rétrocession</a>", corps)
        self.assertIn("modification de prix :", corps)
        self.assertIn(f'href="{URL.format("JORFTEXT4")}"', corps)

    def test_radiations(self):
        resultat = ResultatVeille(date_jo=DATE_JO, lignes=[
            _ligne(SECTION_RADIATIONS, produit="VFEND", racine="VFEND",
                   laboratoire="PFIZER",
                   listes_radiation=[("LES MCO", URL.format("JORFTEXT6"))])])
        corps = notification.corps_html(resultat)
        self.assertIn("Radiations", corps)
        self.assertIn(">LES MCO</a>", corps)
        self.assertIn(f'href="{URL.format("JORFTEXT6")}"', corps)


class TestCasParticuliers(unittest.TestCase):
    def test_ras_le_mail_part_quand_meme(self):
        resultat = ResultatVeille(date_jo=date(2026, 5, 31), lignes=[], anomalies=[])
        corps = notification.corps_html(resultat)
        self.assertIn("RAS — aucun texte relatif aux spécialités pharmaceutiques au JO "
                      "du 31/05/2026.", corps)
        self.assertIn("Cordialement,", corps)
        self.assertNotIn("Nouvelles inscriptions", corps)

    def test_recapitulatif_anomalies_apres_cordialement(self):
        resultat = resultat_consolide_28_05()
        resultat.anomalies.append("Texte non analysé : https://www.legifrance.gouv.fr/jorf/id/X")
        corps = notification.corps_html(resultat)
        self.assertIn("Récapitulatif des anomalies", corps)
        self.assertLess(corps.index("Cordialement"), corps.index("Récapitulatif"))

    def test_sections_vides_omises(self):
        resultat = resultat_consolide_28_05()
        resultat.lignes = [l for l in resultat.lignes if l.produit == "FYCOMPA"]
        corps = notification.corps_html(resultat)
        self.assertNotIn("Nouvelles inscriptions", corps)
        self.assertNotIn("Hausse de prix", corps)
        self.assertIn("Baisse de prix", corps)

    def test_objet_mail(self):
        self.assertEqual(notification.objet_mail(date(2026, 5, 28)),
                         "[VEILLE] - Publication JO du 28/05/2026")

    def test_notifier_ecrit_toujours_le_html(self):
        """Mode brouillon_outlook sans Outlook (poste Linux) : repli propre sur le HTML."""
        dossier = Path(tempfile.mkdtemp(prefix="veille_test_"))
        resultat = resultat_consolide_28_05()
        corps = notification.corps_html(resultat)
        chemin = notification.ecrire_fichier_html(corps, resultat.date_jo, dossier=dossier)
        self.assertTrue(chemin.exists())
        contenu = chemin.read_text(encoding="utf-8")
        self.assertIn("<meta charset=\"utf-8\">", contenu)
        self.assertIn("[VEILLE] - Publication JO du 28/05/2026", contenu)

    def test_alerte_materialise_la_panne(self):
        dossier = Path(tempfile.mkdtemp(prefix="veille_test_"))
        corps_alerte = ("JO introuvable pour la date 31/05/2026 (fenêtre des 60 derniers JO)")
        chemin = notification.ecrire_fichier_html(
            f"<p>{corps_alerte}</p>", date(2026, 5, 31), dossier=dossier, prefixe="alerte")
        self.assertEqual(chemin.name, "alerte_2026-05-31.html")


# ---------------------------------------------------------------------------
# Faux win32com : le strict nécessaire de l'API Outlook utilisée par notification.py
# ---------------------------------------------------------------------------

class _PiecesJointesFactices:
    def __init__(self):
        self.ajoutees: list[str] = []

    def Add(self, chemin):
        self.ajoutees.append(str(chemin))


class _MailFactice:
    """Faux MailItem : enregistre les appels dans l'ordre, n'envoie évidemment rien."""

    def __init__(self):
        self.To = None
        self.Subject = None
        self.HTMLBody = ""
        self.Attachments = _PiecesJointesFactices()
        self.appels: list[str] = []

    @property
    def GetInspector(self):   # attribut côté Outlook : force le chargement de la signature
        self.appels.append("GetInspector")
        return None

    def Display(self):
        self.appels.append("Display")

    def Send(self):
        self.appels.append("Send")


class _OutlookFactice:
    def __init__(self):
        self.mails: list[_MailFactice] = []

    def CreateItem(self, _type_element):
        self.mails.append(_MailFactice())
        return self.mails[-1]


class _ClientFactice:
    """Tient lieu de module `win32com.client` (seul `Dispatch` est utilisé)."""

    def __init__(self):
        self.outlook = _OutlookFactice()

    def Dispatch(self, _nom_application):
        return self.outlook


@contextlib.contextmanager
def _outlook_simule(dossier_sorties: Path):
    """Injecte le faux win32com dans `sys.modules` et détourne `sorties/`.

    `import win32com.client` (import local de notification.py, le poste Linux n'a pas
    pywin32) se contente des deux entrées de `sys.modules` et de l'attribut `client`
    sur le module parent. `config.DOSSIER_SORTIES` en chemin absolu suffit à dérouter
    l'écriture du HTML hors du projet (pathlib : un absolu à droite du `/` gagne).
    """
    parent = type(sys)("win32com")
    client = _ClientFactice()
    parent.client = client
    modules = {"win32com": parent, "win32com.client": client}
    with mock.patch.dict(sys.modules, modules), \
            mock.patch.object(config, "DOSSIER_SORTIES", str(dossier_sorties)), \
            mock.patch.object(config, "MAIL_MODE", "brouillon_outlook"):
        yield client.outlook


class TestPolitiqueEnvoi(unittest.TestCase):
    """Garde-fou R3 « rien ne part jamais tout seul » : le brouillon est AFFICHÉ, jamais
    envoyé, tant que `ENVOI_AUTOMATIQUE` vaut False (période de confiance) ; le mail
    d'alerte n'est jamais envoyé, quelle que soit la valeur du drapeau."""

    def setUp(self):
        self.dossier = Path(tempfile.mkdtemp(prefix="veille_envoi_"))

    def test_notifier_affiche_le_brouillon_et_n_envoie_jamais(self):
        with mock.patch.object(config, "ENVOI_AUTOMATIQUE", False), \
                _outlook_simule(self.dossier) as outlook:
            notification.notifier(resultat_consolide_28_05(), chemin_excel=None, ouvrir=False)
        (mail,) = outlook.mails            # un seul brouillon, et le repli HTML n'a pas servi
        self.assertIn("Display", mail.appels)
        self.assertNotIn("Send", mail.appels)
        # Destinataires pris dans config.DESTINATAIRES — jamais d'adresse codée ailleurs.
        self.assertEqual(mail.To, ";".join(config.DESTINATAIRES))
        self.assertEqual(mail.Subject, "[VEILLE] - Publication JO du 28/05/2026")

    def test_alerter_n_envoie_jamais_meme_en_envoi_automatique(self):
        """Une alerte matérialise une panne : elle reste sous contrôle humain même
        après la période de confiance (`ENVOI_AUTOMATIQUE = True`)."""
        for automatique in (False, True):
            with self.subTest(envoi_automatique=automatique):
                with mock.patch.object(config, "ENVOI_AUTOMATIQUE", automatique), \
                        _outlook_simule(self.dossier) as outlook:
                    notification.alerter("JO introuvable pour la date 31/05/2026",
                                         date(2026, 5, 31), ouvrir=False)
                (mail,) = outlook.mails
                self.assertEqual(mail.appels, ["Display"])
                self.assertEqual(mail.To, ";".join(config.DESTINATAIRES))


if __name__ == "__main__":
    unittest.main()
