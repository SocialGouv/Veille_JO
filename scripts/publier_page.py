"""Publication du digest du jour sur la page GitHub Pages (`gh-pages`).

Appelé par `.github/workflows/publier-pages.yml` juste après `python main.py` : ne
recalcule PAS la date traitée (aucune dépendance à `date.txt`/`--date`), mais repère
après coup le(s) fichier(s) daté(s) que `main.py` vient d'écrire dans `sorties/` —
`corps_mail_<date>.html` (jour normal, y compris « RAS ») ou, à défaut, `alerte_<date>.html`
(échec du run — publié aussi : une alerte visible vaut mieux qu'une page silencieuse).

Contrat avec le reste du pipeline (voir CLAUDE.md) : les noms de fichiers et le gabarit
HTML (`<body ...>{corps}</body>`) viennent de `notification.ecrire_fichier_html` ; le nom
de l'Excel vient de `export.exporter` (`veille_jo_<date>.xlsx`). Un changement de ces
formats doit se répercuter ici.

Écrit dans le répertoire de checkout de la branche `gh-pages` (par défaut
`gh-pages-checkout/`, réglable en argument) :
  - `archive/<date>.html` et `archive/<date>.xlsx` (si présent) — copie du jour ;
  - `index.html` — régénéré en listant tout `archive/*.html` (ancien + nouveau), le plus
    récent en tête, avec le digest du jour inliné sous la liste. La liste est affichée
    dans un conteneur défilant et peut être filtrée par une saisie de date approximative
    (distance de Damerau-Levenshtein, meilleures correspondances en tête, 10 résultats
    maximum affichés) — cf. `SCRIPT_FILTRE_ARCHIVES` ci-dessous ; ce filtrage est une
    amélioration cliente (JavaScript) : sans JavaScript, la liste complète reste visible.
"""

import argparse
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
MOTIF_DATE = re.compile(r"_(\d{4}-\d{2}-\d{2})\.html$")
MOTIF_BODY_OUVRANT = re.compile(r"(<body[^>]*>)", re.IGNORECASE)
LIEN_RETOUR = '<p><a href="../index.html">← Retour à la page d\'accueil</a></p>\n'


def fichier_du_jour(dossier_sorties: Path) -> Path:
    """Le fichier `corps_mail_<date>.html` du run qui vient de se terminer, ou à défaut
    `alerte_<date>.html`. Lève `FileNotFoundError` si aucun des deux n'existe : `main.py`
    en écrit toujours un (§ invariants CLAUDE.md — l'absence de mail signifie « panne »,
    jamais « rien à publier »)."""
    for motif in ("corps_mail_*.html", "alerte_*.html"):
        candidats = sorted(dossier_sorties.glob(motif))
        if candidats:
            return candidats[-1]
    raise FileNotFoundError(
        f"Aucun corps_mail_*.html ni alerte_*.html trouvé dans {dossier_sorties} "
        "— le run de main.py a-t-il bien eu lieu avant ce script ?")


def date_depuis_nom(chemin: Path) -> str:
    correspondance = MOTIF_DATE.search(chemin.name)
    if not correspondance:
        raise ValueError(f"Nom de fichier inattendu (date AAAA-MM-JJ introuvable) : {chemin.name}")
    return correspondance.group(1)


def _avec_lien_retour(document_html: str) -> str:
    """Insère un lien « Retour à la page d'accueil » juste après l'ouverture de `<body>`,
    pour permettre de revenir sur `index.html` sans passer par le bouton retour du
    navigateur — ces pages archivées sont aussi accédées directement (lien partagé,
    favori), pas seulement en cliquant depuis l'index."""
    return MOTIF_BODY_OUVRANT.sub(lambda m: m.group(1) + "\n" + LIEN_RETOUR,
                                  document_html, count=1)


def copier_dans_archive(fichier_html: Path, dossier_sorties: Path, date_iso: str,
                        dossier_gh_pages: Path) -> None:
    archive = dossier_gh_pages / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    contenu = _avec_lien_retour(fichier_html.read_text(encoding="utf-8"))
    (archive / f"{date_iso}.html").write_text(contenu, encoding="utf-8")

    fichier_excel = dossier_sorties / f"veille_jo_{date_iso}.xlsx"
    if fichier_excel.is_file():
        shutil.copyfile(fichier_excel, archive / f"{date_iso}.xlsx")


def _corps_depuis_document(document_html: str) -> str:
    """Extrait le contenu de `<body>...</body>` (gabarit de `ecrire_fichier_html`) pour
    l'inliner dans `index.html` sans dupliquer l'enveloppe `<html>`/`<head>`."""
    correspondance = re.search(r"<body[^>]*>(.*)</body>", document_html,
                               re.DOTALL | re.IGNORECASE)
    corps = correspondance.group(1) if correspondance else document_html
    # Le lien de retour n'a pas lieu d'être une fois inliné dans index.html lui-même.
    return corps.replace("\n" + LIEN_RETOUR, "").replace(LIEN_RETOUR, "")


def _date_affichee(date_iso: str) -> str:
    return datetime.strptime(date_iso, "%Y-%m-%d").strftime("%d/%m/%Y")


STYLE_ARCHIVES = (
    ".archives-conteneur{max-height:320px;overflow-y:auto;border:1px solid #cccccc;"
    "padding:0.5em 1em;margin-bottom:1em}\n"
    "#filtre-archives{width:16em;padding:0.3em;margin-bottom:0.5em}"
)

# Filtrage côté client de la liste des archives : distance de Damerau-Levenshtein
# (transpositions comprises) de la saisie contre CHAQUE sous-chaîne de la date affichée
# (« n'importe où dans la chaîne », pas seulement en préfixe — ex. taper "18/" doit faire
# remonter le 18 de tous les mois). Pas de seuil de distance : tri par distance croissante
# puis par date décroissante, et seuls les 10 premiers résultats restent affichés — une
# saisie qui ne correspond bien à rien affiche simplement les 10 « moins mauvaises »
# correspondances plutôt qu'une liste vide. Amélioration cliente uniquement : le <ul> est
# déjà rendu côté serveur avec la liste complète, donc l'absence de JavaScript laisse la
# liste complète visible (non filtrée, non triée dynamiquement).
SCRIPT_FILTRE_ARCHIVES = """
(function () {
  function damerauLevenshtein(a, b) {
    var al = a.length, bl = b.length;
    var d = [];
    for (var i = 0; i <= al; i++) { d[i] = [i]; }
    for (var j = 0; j <= bl; j++) { d[0][j] = j; }
    for (var i = 1; i <= al; i++) {
      for (var j = 1; j <= bl; j++) {
        var cout = a[i - 1] === b[j - 1] ? 0 : 1;
        var valeur = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cout);
        if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) {
          valeur = Math.min(valeur, d[i - 2][j - 2] + 1);
        }
        d[i][j] = valeur;
      }
    }
    return d[al][bl];
  }

  function distanceMeilleureSousChaine(saisie, cible) {
    var meilleure = Infinity;
    for (var i = 0; i <= cible.length; i++) {
      for (var j = i; j <= cible.length; j++) {
        var distance = damerauLevenshtein(saisie, cible.slice(i, j));
        if (distance < meilleure) { meilleure = distance; }
      }
    }
    return meilleure;
  }

  var conteneur = document.getElementById("archives");
  var champ = document.getElementById("filtre-archives");
  if (!conteneur || !champ) { return; }
  var lignes = Array.prototype.slice.call(conteneur.querySelectorAll("li"));

  champ.addEventListener("input", function () {
    var saisie = champ.value.trim();
    var notees = lignes.map(function (li) {
      return { li: li, distance: distanceMeilleureSousChaine(saisie, li.dataset.affichee) };
    });
    notees.sort(function (a, b) {
      if (a.distance !== b.distance) { return a.distance - b.distance; }
      return a.li.dataset.date < b.li.dataset.date ? 1 : -1;
    });
    notees.forEach(function (item, index) {
      item.li.style.display = index < 10 ? "" : "none";
      conteneur.appendChild(item.li);
    });
  });
})();
"""


def regenerer_index(dossier_gh_pages: Path) -> None:
    """Régénère `index.html` à partir de TOUT `archive/*.html` présent (ancien + nouveau) —
    la publication mise en avant est la plus RÉCENTE de l'archive, pas forcément celle du
    run qui vient de s'exécuter (robuste à un rejeu manuel d'une date passée)."""
    archive = dossier_gh_pages / "archive"
    dates = sorted((f.stem for f in archive.glob("*.html")), reverse=True)

    liens = []
    for date_iso in dates:
        date_affichee = _date_affichee(date_iso)
        lien = f'<a href="archive/{date_iso}.html">{date_affichee}</a>'
        if (archive / f"{date_iso}.xlsx").is_file():
            lien += f' (<a href="archive/{date_iso}.xlsx">Excel</a>)'
        liens.append(f'<li data-date="{date_iso}" data-affichee="{date_affichee}">{lien}</li>')

    date_plus_recente = dates[0]
    corps_du_jour = _corps_depuis_document(
        (archive / f"{date_plus_recente}.html").read_text(encoding="utf-8"))

    index = ("<!DOCTYPE html>\n<html lang=\"fr\">\n<head>\n<meta charset=\"utf-8\">\n"
             "<meta name=\"color-scheme\" content=\"light only\">\n"
             "<title>Veille JO — spécialités pharmaceutiques (CEPS)</title>\n"
             f"<style>\n{STYLE_ARCHIVES}\n</style>\n</head>\n"
             "<body style=\"background:#ffffff;color:#000000;"
             "font-family:Aptos,Arial,sans-serif\">\n"
             "<h1>Veille JO — spécialités pharmaceutiques (CEPS)</h1>\n"
             f"<p>Dernière publication : <strong>{_date_affichee(date_plus_recente)}</strong></p>\n"
             "<h2>Archives</h2>\n"
             '<input type="text" id="filtre-archives" autocomplete="off"\n'
             '       placeholder="Filtrer par date (JJ/MM/AAAA), ex. « 18/ »">\n'
             '<div class="archives-conteneur">\n<ul id="archives">\n'
             + "\n".join(liens) + "\n</ul>\n</div>\n"
             "<hr>\n<h2>Publication du jour</h2>\n"
             f"{corps_du_jour}\n"
             f"<script>{SCRIPT_FILTRE_ARCHIVES}</script>\n"
             "</body>\n</html>\n")
    (dossier_gh_pages / "index.html").write_text(index, encoding="utf-8")


def principal(argv=None) -> int:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--sorties", type=Path, default=RACINE / "sorties",
                           help="dossier des sorties du run (défaut : sorties/)")
    analyseur.add_argument("--gh-pages", type=Path, default=RACINE / "gh-pages-checkout",
                           help="dossier de checkout de la branche gh-pages "
                                "(défaut : gh-pages-checkout/)")
    arguments = analyseur.parse_args(argv)

    fichier_html = fichier_du_jour(arguments.sorties)
    date_iso = date_depuis_nom(fichier_html)
    arguments.gh_pages.mkdir(parents=True, exist_ok=True)

    copier_dans_archive(fichier_html, arguments.sorties, date_iso, arguments.gh_pages)
    regenerer_index(arguments.gh_pages)

    print(f"Page publiée pour le {date_iso} depuis {fichier_html.name} "
         f"dans {arguments.gh_pages}.")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
