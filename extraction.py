"""Extraction des textes du Journal officiel via l'API Légifrance (PISTE).

Chaîne d'appels (éprouvée par les scripts historiques, §6 E1 du plan) :
  1. token OAuth2 (`URL_TOKEN`, client_credentials, scope openid, validité ~1 h) ;
  2. `lastNJo` → liste des derniers JO (`containers`), datation par `datePubli` (ms epoch) ;
  3. `jorfCont` → arbre du sommaire du JO retenu ;
  4. `jorf` (`textCid`) → texte intégral de chaque JORFTEXT.

Aucun identifiant JORFTEXT n'est codé en dur : tout part de la date demandée.
"""

import logging
import time
from datetime import date, datetime

import requests

import config

JOURNAL = logging.getLogger("veille_jo.extraction")

# Champs du JSON de l'API susceptibles de porter du texte utile (constat scripts historiques).
CHAMPS_TEXTE = ["content", "html", "texte", "text", "visa", "notice", "texteSource"]
LONGUEUR_MINI_CHAMP = 20  # les chaînes plus courtes sont du bruit (codes, libellés techniques)


class ErreurPiste(Exception):
    """Échec définitif d'un appel PISTE (après relances)."""


def url_publique(id_texte: str) -> str:
    """URL Légifrance publique d'un texte du JORF (pour les hyperliens et les logs)."""
    return config.URL_PUBLIQUE_TEXTE.format(id=id_texte)


def trouver_jo(conteneurs: list, date_cible: date) -> dict | None:
    """Retourne le conteneur JO publié à `date_cible`, ou None.

    `datePubli` est un timestamp en millisecondes : comparaison sur la date locale.
    """
    for jo in conteneurs:
        ms = jo.get("datePubli")
        if ms is None:
            continue
        if datetime.fromtimestamp(ms / 1000).date() == date_cible:
            return jo
    return None


def lister_textes_sommaire(arbre) -> list[tuple[str, str]]:
    """Parcourt récursivement l'arbre du sommaire et liste les (id, titre) des textes.

    Un texte est un nœud dont l'`id` commence par `JORFTEXT` ; son titre est dans
    `titre` ou `title`. Dédoublonnage par id en conservant l'ordre du sommaire.
    """
    textes: list[tuple[str, str]] = []
    vus: set[str] = set()

    def parcourir(noeud) -> None:
        if isinstance(noeud, dict):
            identifiant = noeud.get("id")
            if isinstance(identifiant, str) and identifiant.startswith("JORFTEXT") and identifiant not in vus:
                vus.add(identifiant)
                titre = noeud.get("titre") or noeud.get("title") or "Titre inconnu"
                textes.append((identifiant, titre))
            for valeur in noeud.values():
                parcourir(valeur)
        elif isinstance(noeud, list):
            for element in noeud:
                parcourir(element)

    parcourir(arbre)
    return textes


def extraire_champs_texte(donnees) -> str:
    """Concatène récursivement les champs texte du JSON d'un texte intégral.

    Seules les chaînes de plus de `LONGUEUR_MINI_CHAMP` caractères portées par un champ
    de `CHAMPS_TEXTE` sont retenues, dédupliquées en conservant l'ordre de rencontre.
    """
    morceaux: list[str] = []

    def parcourir(noeud) -> None:
        if isinstance(noeud, dict):
            for cle, valeur in noeud.items():
                if cle in CHAMPS_TEXTE and isinstance(valeur, str) and len(valeur) > LONGUEUR_MINI_CHAMP:
                    morceaux.append(valeur)
                else:
                    parcourir(valeur)
        elif isinstance(noeud, list):
            for element in noeud:
                parcourir(element)

    parcourir(donnees)
    uniques: list[str] = []
    for morceau in morceaux:
        if morceau not in uniques:
            uniques.append(morceau)
    return "\n\n".join(uniques)


class ClientPiste:
    """Client OAuth2 de l'API Légifrance sur PISTE, avec relances et re-token sur 401."""

    def __init__(self, client_id: str, client_secret: str):
        if not client_id or not client_secret:
            raise ErreurPiste(
                "Identifiants PISTE absents : remplir PISTE_CLIENT_ID et PISTE_CLIENT_SECRET "
                "dans .env (procédure : INSTALL.md)."
            )
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: str | None = None

    def _obtenir_token(self) -> str:
        """Demande un token OAuth2 (validité ~1 h)."""
        reponse = requests.post(
            config.URL_TOKEN,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "scope": "openid",
            },
            timeout=config.TIMEOUT_PISTE_S,
        )
        reponse.raise_for_status()
        token = reponse.json().get("access_token")
        if not token:
            raise ErreurPiste("Réponse token PISTE sans access_token.")
        JOURNAL.debug("Nouveau token PISTE obtenu.")
        return token

    def _post(self, url: str, charge: dict) -> dict:
        """POST JSON authentifié, avec relances (backoff 2 s) et re-token sur 401."""
        derniere_erreur: Exception | None = None
        for tentative in range(1, config.TENTATIVES_PISTE + 1):
            try:
                if self._token is None:
                    self._token = self._obtenir_token()
                reponse = requests.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self._token}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    json=charge,
                    timeout=config.TIMEOUT_PISTE_S,
                )
                if reponse.status_code == 401:
                    JOURNAL.info("Token PISTE expiré (401) : renouvellement.")
                    self._token = None
                    raise requests.HTTPError("401 Unauthorized", response=reponse)
                reponse.raise_for_status()
                return reponse.json()
            except requests.RequestException as exc:
                derniere_erreur = exc
                JOURNAL.warning("Appel PISTE %s : tentative %d/%d en échec (%s).",
                                url, tentative, config.TENTATIVES_PISTE, exc)
                if tentative < config.TENTATIVES_PISTE:
                    time.sleep(2)
        raise ErreurPiste(f"Appel PISTE {url} en échec après "
                          f"{config.TENTATIVES_PISTE} tentatives : {derniere_erreur}")

    def sommaire_jo(self, date_cible: date) -> tuple[dict, list[tuple[str, str]]]:
        """Retourne (conteneur du JO, liste (id, titre) des textes du sommaire) pour la date.

        Lève `ErreurPiste` si aucun JO n'est publié à cette date dans la fenêtre
        `NB_ELEMENT_LASTNJO` (message explicite, géré par l'appelant).
        """
        donnees = self._post(config.URL_LAST_JO, {"nbElement": config.NB_ELEMENT_LASTNJO})
        conteneurs = donnees.get("containers", [])
        JOURNAL.info("lastNJo : %d JO reçus (fenêtre de rejeu).", len(conteneurs))
        jo = trouver_jo(conteneurs, date_cible)
        if jo is None:
            raise ErreurPiste(
                f"JO introuvable pour la date {date_cible.strftime('%d/%m/%Y')} "
                f"(fenêtre des {config.NB_ELEMENT_LASTNJO} derniers JO ; jour sans JO, "
                "publication pas encore faite, ou augmenter NB_ELEMENT_LASTNJO)."
            )
        JOURNAL.info("JO trouvé : %s (id %s).", jo.get("titre", "(sans titre)"), jo.get("id"))
        arbre = self._post(config.URL_JORF_CONT, {"id": jo["id"]})
        textes = lister_textes_sommaire(arbre)
        JOURNAL.info("Sommaire : %d textes JORFTEXT.", len(textes))
        return jo, textes

    def texte_integral(self, id_texte: str) -> str:
        """Texte intégral (champs texte concaténés) d'un JORFTEXT."""
        donnees = self._post(config.URL_JORF_TEXT, {"textCid": id_texte})
        texte = extraire_champs_texte(donnees)
        JOURNAL.debug("Texte %s : %d caractères bruts.", id_texte, len(texte))
        return texte
