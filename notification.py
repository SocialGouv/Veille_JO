"""Notification (E8) : corps de mail HTML au gabarit de la newsletter + remise.

Le HTML est construit depuis les données consolidées (jamais en relisant l'Excel),
au format des mails manuels de l'utilisatrice (référence : mails des 22-23/07/2026) :

- tableaux **sans colonne Date**, bandeaux aux couleurs de l'Excel ;
- 6 sections : « Nouvelles inscriptions », « Hausse de prix », « Baisse de prix »,
  « Modification de libellé », « Extensions d'indications », « Radiations » ;
- plus aucun prix chiffré (décision utilisatrice du 23/07/2026) : les cellules Prix et
  Lien sont de simples liens texte « Site LégiFrance ». La cellule Taux, elle, porte le
  pourcentage entier publié par la décision UNCAM (0.35 → « 35% »), cliquable vers
  cette décision — format des mails de l'utilisatrice et du fichier CIBLE ;
- colonne Liste : un lien cliquable par segment (« 1 liste = 1 arrêté »), segments
  joints par « & » (« SS & Collectivité », format des mails de l'utilisatrice) ;
- colonne Laboratoire : « ancien → nouveau » quand un arrêté de modification de libellé
  a transféré l'exploitation du jour (format à valider avec l'utilisatrice) ;
- règle SIRTURO : une ligne d'extension issue du regroupement inscription + extension
  + prix rappelle ses listes et son lien de prix sous l'indication ;
- sections vides omises ; jour sans texte pertinent : corps « RAS — … » (le mail part
  quand même : l'absence de mail signifie « panne », jamais « rien à signaler ») ;
- récapitulatif d'anomalies le cas échéant (textes non analysés avec leur lien
  Légifrance, lignes « à vérifier »).

Remise selon `config.MAIL_MODE` :
- Option A `"brouillon_outlook"` : brouillon pré-rempli affiché (`.Display()`), corps
  inséré AVANT la signature Outlook existante, Excel du jour en pièce jointe. JAMAIS
  de `.Send()` sans `ENVOI_AUTOMATIQUE = True` (R3, période de confiance) ;
- Option B `"html"` : le fichier `sorties/corps_mail_<date>.html` (écrit dans TOUS les
  cas, mode dégradé permanent) est ouvert dans le navigateur pour copier-coller.

Un échec de l'étape mail ne fait jamais échouer le run : l'Excel et le HTML sont dans
`sorties/` et le log le dit clairement.
"""

import html
import logging
import re
import webbrowser
from datetime import date
from pathlib import Path

import config
from rapprochement import (SECTION_BAISSES, SECTION_EXTENSIONS, SECTION_HAUSSES,
                           SECTION_INSCRIPTIONS, SECTION_MODIFICATIONS,
                           SECTION_RADIATIONS, SECTIONS, LigneConsolidee,
                           RappelExtension, ResultatVeille, pourcentage)

JOURNAL = logging.getLogger("veille_jo.notification")

COULEUR_LIEN = "#467886"        # rendu des liens de la newsletter réelle (thème Outlook)
COULEUR_PRODUIT = "#3A3A3A"

STYLE_TABLE = "border-collapse:collapse;margin-left:0"
STYLE_CELLULE = ("border:1px solid windowtext;padding:1px 5px;font-size:11.0pt;"
                 "font-family:'Aptos Narrow',sans-serif;text-align:center")
STYLE_INDICATION = STYLE_CELLULE.replace("text-align:center", "text-align:left")

TEXTE_LIEN = "Site LégiFrance"

# Colonnes de chaque section — contrat du 23/07/2026, calqué sur les mails manuels de
# l'utilisatrice (22-23/07/2026) : pas de colonne Date, Produit et Laboratoire côte à côte
# (un même médicament générique est vendu par plusieurs laboratoires), plus aucun prix
# chiffré. Les inscriptions terminent par Prix puis Taux, dans cet ordre — c'est celui du
# mail de l'utilisatrice comme du fichier CIBLE du 28/05/2026 (rétabli le 29/07/2026 :
# les deux colonnes manquaient au tableau des inscriptions). Le tableau Radiations n'a pas
# d'exemple dans les mails : colonnes proposées (Produit, Laboratoire, Liste, Lien), à
# confirmer avec l'utilisatrice.
COLONNES_MAIL = {
    SECTION_INSCRIPTIONS: ["Produit", "Laboratoire", "Indication", "Liste", "Prix", "Taux"],
    SECTION_HAUSSES: ["Produit", "Laboratoire", "Prix"],
    SECTION_BAISSES: ["Produit", "Laboratoire", "Prix"],
    SECTION_MODIFICATIONS: ["Produit", "Laboratoire", "Lien"],
    SECTION_EXTENSIONS: ["Produit", "Laboratoire", "Indication", "Lien"],
    SECTION_RADIATIONS: ["Produit", "Laboratoire", "Liste", "Lien"],
}

# (clé de section, titre du mail, couleur de bandeau, colonnes) — clés, titres, couleurs
# et ordre d'affichage viennent de la source unique `rapprochement.SECTIONS` ; le HTML
# préfixe la couleur hexadécimale d'un « # ».
SECTIONS_MAIL = [(cle, titre, "#" + couleur, COLONNES_MAIL[cle])
                 for cle, titre, couleur in SECTIONS]


def _texte(valeur: str) -> str:
    """Échappe une valeur pour le HTML, retours à la ligne rendus par des <br>."""
    return html.escape(valeur).replace("\n", "<br>\n")


def _lien(url: str, texte: str) -> str:
    return (f'<a href="{html.escape(url, quote=True)}" '
            f'style="color:{COULEUR_LIEN};text-decoration:underline">{html.escape(texte)}</a>')


def _cellule_prix(ligne: LigneConsolidee) -> str:
    # Décision utilisatrice du 23/07/2026 : lien seul, plus jamais de montant.
    return _lien(ligne.lien_prix, TEXTE_LIEN) if ligne.lien_prix else "N/A"


def _cellule_taux(ligne: LigneConsolidee) -> str:
    """Taux de participation : le pourcentage entier publié (0.35 → « 35% »), cliquable
    vers la décision UNCAM. « N/A » sans lien quand aucune décision ne le publie —
    l'absence de taux est une information, jamais un vide."""
    if ligne.taux == "N/A":
        return "N/A"
    affiche = pourcentage(ligne.taux)
    return _lien(ligne.lien_taux, affiche) if ligne.lien_taux else _texte(affiche)


def _segments_liste(segments: list[tuple[str, str | None]]) -> str:
    """Colonne Liste : un lien hypertexte par segment (« 1 liste = 1 arrêté »),
    joints par « & » (« SS & Collectivité », format des mails de l'utilisatrice)."""
    if not segments:
        return "N/A"
    return " &amp; ".join(_lien(lien, libelle) if lien else html.escape(libelle)
                          for libelle, lien in segments)


def _cellule_liste(ligne: LigneConsolidee) -> str:
    return _segments_liste(ligne.segments_liste)


def _cellule_lien(ligne: LigneConsolidee) -> str:
    """Colonne Lien : le texte porteur de la section (modification, extension, radiation)."""
    url = ligne.lien_section
    return _lien(url, TEXTE_LIEN) if url else "N/A"


def _texte_rappel(rappel: RappelExtension) -> str:
    """Un rappel SIRTURO en HTML : segments de liste cliquables un par un, lien de prix
    en hypertexte (formulation à confirmer avec l'utilisatrice)."""
    valeur = (_segments_liste(rappel.segments) if rappel.segments
              else _lien(rappel.lien, TEXTE_LIEN))
    return f"{rappel.etiquette} : {valeur}"


def _cellule_indication(ligne: LigneConsolidee) -> str:
    """Indication (recopie exacte), suivie des rappels de la ligne le cas échéant
    (règle SIRTURO du 23/07/2026 : listes d'inscription et lien de prix)."""
    contenu = _texte(ligne.indication) if ligne.indication else "&nbsp;"
    rappels = ligne.rappels_extension
    if rappels:
        contenu += ("<br><br><i>"
                    + " — ".join(_texte_rappel(rappel) for rappel in rappels)
                    + "</i>")
    return contenu


def _cellule_produit(ligne: LigneConsolidee) -> str:
    """Produit, suffixé « (à vérifier) » sur une ligne douteuse (§5.1)."""
    produit = ligne.produit + (" (à vérifier)" if ligne.a_verifier else "")
    return (f'<b><span style="font-family:{config.POLICE};color:{COULEUR_PRODUIT}">'
            f"{_texte(produit)}</span></b>")


def _cellule_laboratoire(ligne: LigneConsolidee) -> str:
    """Laboratoire, ou « ancien → nouveau » sur un transfert d'exploitation du jour."""
    return (f'<span style="font-family:{config.POLICE};color:{COULEUR_PRODUIT}">'
            f"{_texte(ligne.laboratoire_affiche)}</span>")


# (fonction de rendu, style) de chaque colonne des tables `COLONNES_MAIL`. Ajouter une
# colonne se fait ici et dans sa table de section, sans toucher `_cellules_ligne` — et
# seules les colonnes demandées sont calculées.
RENDUS_COLONNE = {
    "Produit": (_cellule_produit, STYLE_CELLULE),
    "Laboratoire": (_cellule_laboratoire, STYLE_CELLULE),
    "Indication": (_cellule_indication, STYLE_INDICATION),
    "Liste": (_cellule_liste, STYLE_CELLULE),
    "Prix": (_cellule_prix, STYLE_CELLULE),
    "Taux": (_cellule_taux, STYLE_CELLULE),
    "Lien": (_cellule_lien, STYLE_CELLULE),
}


def _cellules_ligne(ligne: LigneConsolidee, colonnes: list[str]) -> list[tuple[str, str]]:
    """(contenu HTML, style) de chaque cellule d'une ligne, dans l'ordre des colonnes.

    Colonne inconnue → `KeyError` : jamais de cellule muette dans le tableau.
    """
    cellules = []
    for colonne in colonnes:
        rendu, style = RENDUS_COLONNE[colonne]
        cellules.append((rendu(ligne), style))
    return cellules


def _table_section(titre: str, couleur: str, colonnes: list[str],
                   lignes: list[LigneConsolidee]) -> str:
    morceaux = [f'<table cellspacing="0" cellpadding="0" style="{STYLE_TABLE}">']
    morceaux.append(
        f'<tr><td colspan="{len(colonnes)}" style="{STYLE_CELLULE};background:{couleur}">'
        f"<b>{html.escape(titre)}</b></td></tr>")
    morceaux.append("<tr>" + "".join(f'<td style="{STYLE_CELLULE}"><b>{html.escape(c)}</b></td>'
                                     for c in colonnes) + "</tr>")
    for ligne in lignes:
        cellules = [f'<td style="{style}">{contenu}</td>'
                    for contenu, style in _cellules_ligne(ligne, colonnes)]
        morceaux.append("<tr>" + "".join(cellules) + "</tr>")
    morceaux.append("</table>")
    return "\n".join(morceaux)


def corps_html(resultat: ResultatVeille) -> str:
    """Corps HTML complet du mail (gabarit des mails utilisatrice, ordre 1 → 7)."""
    style_paragraphe = "font-size:12.0pt;font-family:Aptos,sans-serif;margin:0cm"
    blocs = [f'<div style="{style_paragraphe}">',
             "<p>Bonjour,</p>", "<p>&nbsp;</p>"]

    anomalies = list(resultat.anomalies)

    if resultat.lignes:
        blocs.append("<p>Veuillez trouver ci-dessous la publication du JO de ce jour&nbsp;:</p>")
        blocs.append("<p>&nbsp;</p>")
        for cle, titre, couleur, colonnes in SECTIONS_MAIL:
            lignes = resultat.lignes_par_section(cle)
            if not lignes:
                continue           # sections vides omises (§5.2.5)
            blocs.append(_table_section(titre, couleur, colonnes, lignes))
            blocs.append("<p>&nbsp;</p>")
    else:
        blocs.append(f"<p>RAS — aucun texte relatif aux spécialités pharmaceutiques au JO "
                     f"du {resultat.date_jo.strftime('%d/%m/%Y')}.</p>")
        blocs.append("<p>&nbsp;</p>")

    blocs.append("<p>Cordialement,</p>")

    if anomalies:
        blocs.append("<p>&nbsp;</p>")
        blocs.append("<p><b>Récapitulatif des anomalies (à vérifier manuellement)&nbsp;:</b></p>")
        blocs.append("<ul>" + "".join(f"<li>{_texte(a)}</li>" for a in anomalies) + "</ul>")

    blocs.append("</div>")
    return "\n".join(blocs)


def objet_mail(date_jo: date) -> str:
    return config.OBJET_MAIL.format(date_jjmmaaaa=date_jo.strftime("%d/%m/%Y"))


def ecrire_fichier_html(corps: str, date_jo: date, dossier: Path | None = None,
                        prefixe: str = "corps_mail") -> Path:
    """Écrit le fichier HTML de `sorties/` (toujours, quel que soit le mode)."""
    dossier = dossier or Path(__file__).parent / config.DOSSIER_SORTIES
    dossier.mkdir(exist_ok=True)
    chemin = dossier / f"{prefixe}_{date_jo:%Y-%m-%d}.html"
    # L'enveloppe force un rendu clair : un navigateur en mode sombre donnerait une
    # prévisualisation trompeuse (dans Outlook, le corps s'affiche sur fond blanc).
    document = ("<!DOCTYPE html>\n<html lang=\"fr\">\n<head>\n<meta charset=\"utf-8\">\n"
                "<meta name=\"color-scheme\" content=\"light only\">\n"
                f"<title>{html.escape(objet_mail(date_jo))}</title>\n</head>\n"
                "<body style=\"background:#ffffff;color:#000000\">\n"
                f"{corps}\n</body>\n</html>\n")
    chemin.write_text(document, encoding="utf-8")
    JOURNAL.info("Corps de mail écrit : %s", chemin)
    return chemin


def _nouveau_brouillon(objet: str):
    """Brouillon Outlook (win32com) adressé à `config.DESTINATAIRES`, sans corps.

    Ni corps, ni pièce jointe, ni remise : le corps ne s'écrit pas de la même façon
    selon l'appelant (avant la signature pour la newsletter, tel quel pour une alerte)
    et la **politique d'envoi reste explicite chez chacun** — `_brouillon_outlook`
    honore `ENVOI_AUTOMATIQUE`, `alerter` n'envoie JAMAIS.
    """
    # Import local : le pipeline B (et le poste Linux) tourne sans pywin32.
    import win32com.client

    outlook = win32com.client.Dispatch("Outlook.Application")
    mail = outlook.CreateItem(0)   # 0 = olMailItem
    mail.To = ";".join(config.DESTINATAIRES)
    mail.Subject = objet
    return mail


def _brouillon_outlook(corps: str, date_jo: date, chemin_excel: Path | None) -> None:
    """Option A : brouillon Outlook pré-rempli (win32com), corps avant la signature.

    `.Send()` uniquement si `ENVOI_AUTOMATIQUE = True` (R3) — jamais par défaut.
    """
    mail = _nouveau_brouillon(objet_mail(date_jo))
    mail.GetInspector  # force le chargement de la signature Outlook dans HTMLBody
    signature = mail.HTMLBody or ""
    if "<body" in signature.lower():
        mail.HTMLBody = re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + corps,
                               signature, count=1, flags=re.IGNORECASE)
    else:
        mail.HTMLBody = corps + signature
    if chemin_excel is not None:
        mail.Attachments.Add(str(Path(chemin_excel).resolve()))
    if config.ENVOI_AUTOMATIQUE:
        mail.Send()
        JOURNAL.info("Mail ENVOYÉ automatiquement (ENVOI_AUTOMATIQUE=True).")
    else:
        mail.Display()
        JOURNAL.info("Brouillon Outlook affiché (relecture puis envoi manuel).")


def _ouvrir_navigateur(chemin: Path) -> None:
    try:
        webbrowser.open(chemin.resolve().as_uri())
        JOURNAL.info("Fichier ouvert dans le navigateur : %s", chemin)
    except Exception as exc:
        JOURNAL.warning("Ouverture du navigateur impossible (%s) : ouvrir %s à la main.",
                        exc, chemin)


def notifier(resultat: ResultatVeille, chemin_excel: Path | None,
             ouvrir: bool = True) -> Path:
    """Produit la notification du run et retourne le chemin du fichier HTML.

    Le fichier HTML est écrit dans tous les cas ; le brouillon Outlook (option A) est
    tenté ensuite, avec repli automatique sur l'ouverture du HTML. Aucun échec ici ne
    remonte : le run reste en succès, le log explique quoi faire.
    """
    corps = corps_html(resultat)
    chemin_html = ecrire_fichier_html(corps, resultat.date_jo)

    if config.MAIL_MODE == "brouillon_outlook":
        try:
            _brouillon_outlook(corps, resultat.date_jo, chemin_excel)
            return chemin_html
        except Exception as exc:
            JOURNAL.warning("Brouillon Outlook impossible (%s) : repli sur le fichier HTML "
                            "%s (copier-coller dans un nouveau mail).", exc, chemin_html)
    if ouvrir:
        _ouvrir_navigateur(chemin_html)
    return chemin_html


def alerter(message: str, date_cible: date, ouvrir: bool = True) -> Path | None:
    """Garde-fou E9 : alerte explicite (JO introuvable, PISTE indisponible…).

    L'absence de mail devant toujours signifier « panne », l'alerte matérialise la
    panne : brouillon Outlook si possible, sinon fichier HTML `alerte_<date>.html`.
    Ne lève jamais (l'échec d'alerte est logué, le code retour 1 de main.py fait foi).
    """
    corps = (f'<div style="font-size:12.0pt;font-family:Aptos,sans-serif">'
             f"<p><b>ALERTE VEILLE JO — {date_cible.strftime('%d/%m/%Y')}</b></p>"
             f"<p>{_texte(message)}</p>"
             "<p>La newsletter n'a PAS été produite. Vérifier le dernier fichier du dossier "
             "<code>logs/</code>, puis relancer <code>lancer_veille.bat</code> (ou "
             "<code>python main.py</code>). Diagnostic des flux : "
             "<code>python diagnostic.py</code>.</p></div>")
    try:
        chemin = ecrire_fichier_html(corps, date_cible, prefixe="alerte")
    except Exception as exc:
        JOURNAL.error("Impossible d'écrire le fichier d'alerte : %s", exc)
        return None
    if config.MAIL_MODE == "brouillon_outlook":
        try:
            mail = _nouveau_brouillon(
                f"[VEILLE] - ALERTE - veille du {date_cible.strftime('%d/%m/%Y')} en échec")
            mail.HTMLBody = corps   # ni signature ni insertion : le message doit sauter aux yeux
            mail.Display()   # une alerte ne part JAMAIS seule : contrôle humain
            return chemin
        except Exception as exc:
            JOURNAL.warning("Brouillon d'alerte Outlook impossible (%s) : fichier %s.",
                            exc, chemin)
    if ouvrir:
        _ouvrir_navigateur(chemin)
    return chemin
