"""Sélection des textes « spécialités pharmaceutiques » par mots-clés sur les titres.

La veille couvre arrêtés + avis + décisions UNCAM (pas seulement les arrêtés) :
les mots-clés de `config.MOTS_CLES` sont comparés aux titres, insensibles à la casse.
Les deux listes (retenus, écartés) sont journalisées pour audit du filtre (E2).
"""

import logging

import config

JOURNAL = logging.getLogger("veille_jo.filtrage")


def filtrer_textes(textes: list[tuple[str, str]]) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Sépare les textes (id, titre) en (retenus, écartés) selon `config.MOTS_CLES`."""
    retenus: list[tuple[str, str]] = []
    ecartes: list[tuple[str, str]] = []
    mots = [mot.lower() for mot in config.MOTS_CLES]
    for identifiant, titre in textes:
        titre_minuscule = titre.lower()
        if any(mot in titre_minuscule for mot in mots):
            retenus.append((identifiant, titre))
        else:
            ecartes.append((identifiant, titre))

    JOURNAL.info("Filtrage : %d retenus, %d écartés.", len(retenus), len(ecartes))
    for identifiant, titre in retenus:
        JOURNAL.info("  [RETENU] %s — %s", identifiant, titre)
    for identifiant, titre in ecartes:
        JOURNAL.info("  [écarté] %s — %s", identifiant, titre)
    return retenus, ecartes
