"""Diagnostic des flux externes de la veille JO.

Usage : `python diagnostic.py` (ou `python -m diagnostic`).

Teste dans l'ordre :
  1. l'obtention d'un token OAuth2 PISTE ;
  2. un appel réel à l'API Légifrance (`lastNJo` à 1 élément).

Sortie lisible, une ligne par flux : OK / KO (+ raison).
Code retour : 0 si tous les flux sont OK, 1 sinon.
"""

import os
import sys

import requests
from dotenv import load_dotenv

import config


def tester_token_piste() -> tuple[bool, str, str | None]:
    """Tente d'obtenir un token OAuth2 PISTE.

    Retourne (succès, message, token ou None).
    """
    client_id = os.getenv("PISTE_CLIENT_ID", "")
    client_secret = os.getenv("PISTE_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return False, "KO — PISTE_CLIENT_ID/PISTE_CLIENT_SECRET absents de .env (voir INSTALL.md)", None
    try:
        reponse = requests.post(
            config.URL_TOKEN,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "openid",
            },
            timeout=config.TIMEOUT_PISTE_S,
        )
        reponse.raise_for_status()
        token = reponse.json().get("access_token")
        if not token:
            return False, "KO — réponse sans access_token", None
        return True, "OK", token
    except requests.RequestException as exc:
        return False, f"KO — {exc}", None


def tester_api_piste(token: str) -> tuple[bool, str]:
    """Appelle `lastNJo` avec 1 élément pour vérifier l'accès à l'API Légifrance."""
    try:
        reponse = requests.post(
            config.URL_LAST_JO,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"nbElement": 1},
            timeout=config.TIMEOUT_PISTE_S,
        )
        reponse.raise_for_status()
        conteneurs = reponse.json().get("containers", [])
        if not conteneurs:
            return False, "KO — réponse sans containers"
        return True, f"OK — dernier JO : {conteneurs[0].get('titre', '(titre absent)')}"
    except requests.RequestException as exc:
        return False, f"KO — {exc}"


def principal() -> int:
    """Exécute les deux tests et affiche le verdict par flux."""
    load_dotenv()
    tout_ok = True

    ok_token, msg_token, token = tester_token_piste()
    print(f"PISTE token : {msg_token}")
    tout_ok &= ok_token

    if ok_token and token:
        ok_api, msg_api = tester_api_piste(token)
        print(f"PISTE API   : {msg_api}")
        tout_ok &= ok_api
    else:
        print("PISTE API   : non testé (pas de token)")
        tout_ok = False

    return 0 if tout_ok else 1


if __name__ == "__main__":
    sys.exit(principal())
