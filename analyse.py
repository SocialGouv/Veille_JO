"""Analyse déterministe des textes retenus (E3) — la seule source des données de veille :

  1. nettoyage : suppression des visas (« Vu … ») et considérants, extraction séparée des
     tableaux HTML, suppression du HTML résiduel ;
  2. classification par titre (motifs de `config.MOTIFS_CLASSIFICATION`, calibrés en E2),
     orientation hausse/baisse des avis de prix et inscription/radiation/libellé des
     arrêtés par le corps du texte, listes visées (5 listes) lues dans le titre ;
  3. parsing des tableaux : dénominations, laboratoires, CIP, PPTTC, taux de
     participation ; indication recopiée de la section qui précède chaque tableau
     (arrêtés d'inscription).

Sans indication de section, la ligne sort « à compléter manuellement »
(rapprochement.py) — jamais de vide silencieux.

**Aucun montant n'est extrait pour l'affichage** (contrat du 23/07/2026 : la colonne
Prix est un lien vers l'avis, jamais un prix). Deux chiffres sont néanmoins lus :

- le **PPTTC**, jamais affiché — il oriente les avis de prix neutres par comparaison au
  référentiel de prix ;
- le **taux de participation** des décisions UNCAM, lui bien affiché en colonne Taux
  (« 35% ») : c'est la maquette utilisatrice du 23/07/2026, et le fichier CIBLE du
  28/05/2026 qui fait foi sur le format. Il est recopié de la colonne « Taux de
  participation » du tableau, à défaut du taux unique énoncé par le texte, et vaut
  « N/A » dès qu'il y a le moindre doute — jamais déduit.
"""

import logging
import re
import unicodedata
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

import config
from extraction import url_publique

JOURNAL = logging.getLogger("veille_jo.analyse")

TYPES_TEXTE = (
    "arrete_inscription", "arrete_radiation", "modification_libelle", "avis_prix",
    "decision_taux", "avis_hausse_prix", "avis_baisse_prix",
    "extension_indication", "autre",
)

# Motifs d'orientation d'un avis de prix par le corps du texte (E3.2). Jamais de défaut
# silencieux : ni hausse ni baisse détectée → type « avis_prix » non orienté, signalé
# « à vérifier » au rapprochement.
MOTIF_HAUSSE = re.compile(r"majoration|majoré", re.IGNORECASE)
MOTIF_BAISSE = re.compile(r"baisse|diminué", re.IGNORECASE)

# Motifs d'orientation d'un arrêté d'inscription par le corps du texte (révision du
# 23/07/2026) : les arrêtés de radiation et de modification de libellé partagent les
# titres « modifiant la liste… » des inscriptions — seul le corps tranche (« sont
# radiées de la liste », « le libellé … est remplacé/modifié »). À calibrer sur les
# JO de test fournis par l'utilisatrice (22/05, 02/07, 07/07/2026).
MOTIF_RADIATION_CORPS = re.compile(r"(?:sont|est)\s+radiées?\b", re.IGNORECASE)
MOTIF_LIBELLE_CORPS = re.compile(
    r"libellés?\b[^.]{0,300}?(?:modifié|remplacé|rectifié)"
    r"|(?:modification|remplacement)\s+(?:du|des)\s+libellés?",
    re.IGNORECASE | re.DOTALL,
)
# Extensions d'indication : au JO, une EIT est un arrêté d'inscription au titre
# ordinaire ; seul le corps la signale, par l'en-tête d'annexe « ANNEXE
# (1 extension d'indication) » — constaté sur pièces le 29/07/2026 (ACETATE DE
# CYPROTERONE au 07/07, SIRTURO au 23/07). Risque documenté : un arrêté mixte
# (annexes inscriptions + extension) serait reclassé en bloc — jamais observé,
# signalé au journal à chaque réorientation pour surveillance.
MOTIF_EIT_CORPS = re.compile(r"extensions?\s+d['']indication", re.IGNORECASE)

# Cellule d'une colonne tarifaire : un bloc de 12 à 14 chiffres sans espace, quel que
# soit son préfixe (codes CIP-13, mais aussi codes maison des tableaux de prix). Sert
# uniquement à écarter ces cellules d'une dénomination — jamais à produire une clé de
# rapprochement, d'où l'absence de groupe capturant. Distinct de `MOTIF_CIP_UCD`
# (ci-dessous) : les deux ensembles se croisent sans se recouvrir, cf. sa note.
MOTIF_CODE_TARIFAIRE = re.compile(r"^\s*3?\d{12,13}\s*$")

# Repérage des colonnes utiles dans les tableaux (en-têtes, insensible casse/accents usuels).
ENTETES_DENOMINATION = ("dénomination", "denomination", "présentation", "presentation",
                        "spécialité", "specialite", "libellé", "libelle", "nom")
ENTETES_LABORATOIRE = ("laboratoire", "exploitant", "titulaire")
ENTETES_TAUX = ("taux", "participation")
# Colonnes de DCI, écartées des candidates à la dénomination. Les arrêtés de liste en sus
# (L. 162-22-7 et L. 162-23-6) ouvrent leurs tableaux par la dénomination commune
# internationale AVANT le libellé de la spécialité : « ENCORAFENIB | BRAFTOVI 75 mg
# gélules | Code UCD | … ». La veille nomme la SPÉCIALITÉ (l'utilisatrice écrit BRAFTOVI,
# comme l'avis de prix du même jour) : sans cette exclusion, « Dénomination Commune
# Internationale » matchait « dénomination » en première colonne et la ligne sortait sous
# le nom de la molécule — constat du 29/07/2026 sur le JO du 23/07 (JORFTEXT…457566), qui
# dédoublait aussi le produit quand un autre texte le nommait par sa marque.
ENTETES_DCI = ("commune internationale", "dci")
# Tableaux à DEUX BLOCS des arrêtés de modification de libellé : le même produit à gauche
# dans son état abrogé, à droite dans son état nouveau (constat sur pièces, arrêté
# JORFTEXT…457525 du JO du 23/07/2026). En pratique ces arrêtés transfèrent l'exploitation
# sans toucher au nom : les deux libellés ne diffèrent que par leur « (laboratoires X) ».
# La veille décrit l'état NOUVEAU — le bloc de droite fait foi, celui de gauche ne fournit
# que le laboratoire antérieur. Écritures extensibles au fil des JO rencontrés.
ENTETES_BLOC_ABROGE = ("abrogé", "abroge", "ancien", "au lieu de")
ENTETES_BLOC_NOUVEAU = ("nouveau", "nouvelle", "lire")
# Libellés de (sous-)en-têtes jamais pris pour une dénomination (constaté au run réel du
# 21/07/2026 : une cellule « Code CIP » de sous-en-tête sortait en ligne produit).
LIBELLES_EN_TETE = (ENTETES_DENOMINATION + ENTETES_LABORATOIRE + ENTETES_TAUX
                    + ("code cip", "cip", "code", "prix", "date"))

# Taux de participation d'une cellule ou d'un texte : « 35 % » → 35. Un seul groupe, les
# décimales n'existent pas dans les décisions UNCAM (constat 28/05, 07/07, 23/07/2026).
MOTIF_TAUX = re.compile(r"(\d{1,3})\s*%")


# ---------------------------------------------------------------------------
# Structures de sortie de l'analyse
# ---------------------------------------------------------------------------

@dataclass
class ProduitExtrait:
    """Une présentation extraite d'une ligne de tableau du texte (données déterministes).

    Évolution du 22/07/2026 (demande utilisatrice) : l'unité n'est plus le « produit »
    mais la présentation — une ligne de veille par ligne de tableau Légifrance. Le code
    CIP, présent dans les trois familles de tableaux (arrêtés, avis, décisions UNCAM),
    devient la clé de rapprochement exacte entre textes.
    """

    denomination_brute: str    # présentation, débarrassée de la parenthèse « (laboratoires X) »
    laboratoire_brut: str = ""
    cip: str = ""              # code CIP-13/UCD de la présentation ("" si le tableau n'en a pas)
    ppttc: str = ""            # prix public TTC recopié de la colonne PPTTC ("" sinon) —
                               # sert à orienter les avis neutres par comparaison au
                               # référentiel de prix (29/07/2026), jamais affiché
    taux: str = "N/A"          # taux de participation, chaîne décimale (« 0.35 ») ou
                               # « N/A » — recopié, jamais déduit (colonne Taux)
    laboratoire_precedent: str = ""   # exploitant du libellé ABROGÉ, quand le tableau
                                      # porte les deux états (modification de libellé)
    indication: str = ""       # indication de la section du tableau (recopie exacte, "" sinon)


@dataclass
class TexteAnalyse:
    """Résultat d'analyse d'un texte du JO."""

    id: str
    url: str
    titre: str
    type_texte: str
    ambigu: bool                      # CLASSIFICATION douteuse : arrêté d'inscription ou
                                      # de radiation sans liste identifiable dans le titre
                                      # (unique producteur). Toute ligne alimentée par un
                                      # tel texte sort « à vérifier », motif
                                      # « classification ambiguë du texte … »
                                      # (rapprochement._accumuler).
    produits: list[ProduitExtrait]
    texte_nettoye: str
    listes: list[str] = field(default_factory=list)  # listes visées par un arrêté
                                      # d'inscription/radiation (« 1 liste = 1 arrêté »),
                                      # détectées dans le titre (config.MOTIFS_LISTES)
    # Avis de prix dont le TEXTE annonce à la fois une majoration et une baisse (piège
    # MORPHINE). Champ distinct d'`ambigu` (29/07/2026, second tour) : la classification,
    # elle, est bonne — seule l'ORIENTATION du prix est en doute. Passer par `ambigu`
    # faisait sortir « à vérifier », avec le motif faux « classification ambiguë », toute
    # ligne alimentée par un tel avis, y compris celles dont la section vient d'une
    # inscription ou de la règle SIRTURO — là où le prix ne décide de rien.
    prix_deux_sens: bool = False


# ---------------------------------------------------------------------------
# Volet déterministe
# ---------------------------------------------------------------------------

_MARQUEUR_TABLEAU = "\n@@TABLEAU_{i}@@\n"
_MOTIF_MARQUEUR = re.compile(r"@@TABLEAU_\d+@@")

# Balises HTML « en ligne » fondues dans leur phrase avant extraction du texte :
# get_text(separator="\n") coupe à CHAQUE frontière d'élément, ce qui isolait sur leur
# propre ligne les exposants (« kg/m² » → « 2 »), les marques (« MOUNJARO® » → « ® »)
# et les liens (« l'article R. 161-45 … ») — constaté sur les indications longues des
# arrêtés WEGOVY/MOUNJARO du 28/05/2026. Les tableaux sont extraits avant, donc non touchés.
_BALISES_EN_LIGNE = ["a", "abbr", "b", "em", "i", "small", "span", "strong", "sub", "sup", "u"]


def _epurer_lignes(texte: str) -> str:
    """Supprime lignes vides, visas (« Vu … ») et considérants d'un texte brut."""
    lignes_gardees = []
    for ligne in texte.splitlines():
        nette = ligne.strip()
        if not nette:
            continue
        if nette.startswith("Vu ") or nette.startswith("Vu,") or nette == "Vu":
            continue
        if nette.startswith("Considérant"):
            continue
        lignes_gardees.append(nette)
    return "\n".join(lignes_gardees)


def nettoyer_texte(brut: str) -> tuple[str, list, list[str]]:
    """Nettoie un texte brut de l'API : (texte nettoyé, tableaux HTML, segments).

    - extrait les `<table>` (analysées à part par `parser_tableaux`) ;
    - supprime le HTML résiduel, les lignes de visas (« Vu … ») et les considérants ;
    - `segments[i]` = texte nettoyé qui PRÉCÈDE le tableau i (sa « section ») : les
      arrêtés d'inscription énoncent l'indication d'un lot de présentations juste avant
      leur tableau (constaté sur les JO des 28/05 et 22/07/2026) — cette position est
      la seule liaison indication ↔ produits, détruite par l'ancien `extract()` aveugle.
    Le texte nettoyé sert à l'orientation hausse/baisse — jamais les colonnes tarifaires,
    qui restent dans les tableaux.
    """
    soupe = BeautifulSoup(brut, "html.parser")
    tableaux = soupe.find_all("table")
    for i, tableau in enumerate(tableaux):
        tableau.replace_with(_MARQUEUR_TABLEAU.format(i=i))
    for balise in soupe.find_all(_BALISES_EN_LIGNE):
        balise.unwrap()
    soupe.smooth()   # fusionne les nœuds texte adjacents laissés par unwrap()
    texte = _epurer_lignes(soupe.get_text(separator="\n"))

    segments: list[str] = []
    reste = texte
    for i in range(len(tableaux)):
        avant, _, reste = reste.partition(f"@@TABLEAU_{i}@@")
        segments.append(avant.strip())
    texte_sans_marqueurs = _MOTIF_MARQUEUR.sub(" ", texte)
    texte_sans_marqueurs = re.sub(r"[ \t]+\n", "\n", texte_sans_marqueurs)
    return texte_sans_marqueurs, tableaux, segments


# Liaison section → indication (arrêtés d'inscription). Deux tournures constatées sur
# pièces : « …indications thérapeutiques … ci-dessous : <indication> » (28/05, 22/07)
# et « …indications thérapeutiques … ci-dessous, celles qui figurent à l'AMM… » (22/07,
# arrêtés collectivités). Une section longue (indication structurée + conditions de
# prise en charge, constaté sur WEGOVY/MOUNJARO au 28/05) est recopiée TELLE QUELLE :
# demande utilisatrice du 22/07/2026 — mieux vaut tout le texte à élaguer qu'une case
# « à compléter manuellement ». Au-delà du seuil, simple signalement dans le journal.
_MOTIF_INDICATION_SECTION = re.compile(
    r"indications?\s+thérapeutiques?[^:]{0,400}?ci-dessous\s*(?::|,)\s*(.+)\Z",
    re.IGNORECASE | re.DOTALL,
)
_LONGUEUR_SIGNALEMENT_INDICATION = 1500


def indication_de_section(segment: str) -> str:
    """Indication portée par le texte qui précède un tableau (recopie exacte, "" sinon)."""
    trouve = _MOTIF_INDICATION_SECTION.search(segment)
    if not trouve:
        return ""
    indication = trouve.group(1).strip()
    if len(indication) > _LONGUEUR_SIGNALEMENT_INDICATION:
        JOURNAL.info("Indication de section longue (%d caractères) : recopiée telle quelle "
                     "(peut inclure des conditions de prise en charge, à élaguer à la "
                     "relecture).", len(indication))
    return indication


def classifier_par_titre(titre: str) -> str:
    """Classe un texte d'après son titre : son type, `"autre"` par défaut.

    Les motifs de `config.MOTIFS_CLASSIFICATION` sont évalués dans l'ordre ; le premier
    qui matche donne le type. Aucune ambiguïté ne naît ici : les cas douteux des
    arrêtés (liste introuvable dans le titre) sont signalés par
    `analyser_texte_deterministe` — jamais de défaut silencieux.
    """
    for type_texte, motif in config.MOTIFS_CLASSIFICATION:
        if re.search(motif, titre, re.IGNORECASE):
            return type_texte
    return "autre"


def listes_du_titre(titre: str) -> list[str]:
    """Listes visées par un arrêté d'inscription/radiation, lues dans son titre.

    Mots-clefs fournis par l'utilisatrice (mails des 22-23/07/2026), dans l'ordre
    d'affichage de `config.MOTIFS_LISTES`. « 1 liste = 1 arrêté » : plusieurs matches
    sont conservés tels quels (jamais observé, le rapprochement les affichera tous).
    """
    return [liste for liste, motif in config.MOTIFS_LISTES
            if re.search(motif, titre, re.IGNORECASE)]


def orienter_arrete(type_texte: str, corps: str) -> str:
    """Réoriente un `arrete_inscription` en radiation, extension d'indication ou
    modification de libellé.

    Les quatre familles partagent les titres « modifiant la liste… » : seul le corps
    tranche. L'extension est testée avant le libellé (son annexe peut mentionner une
    modification, jamais l'inverse). Aucun motif trouvé → le type reste
    `arrete_inscription` (comportement des inscriptions, le cas nominal).
    """
    if type_texte != "arrete_inscription":
        return type_texte
    if MOTIF_RADIATION_CORPS.search(corps):
        return "arrete_radiation"
    if MOTIF_EIT_CORPS.search(corps):
        JOURNAL.info("Arrêté d'inscription réorienté en extension d'indication "
                     "(marqueur d'annexe dans le corps).")
        return "extension_indication"
    if MOTIF_LIBELLE_CORPS.search(corps):
        return "modification_libelle"
    return type_texte


def orienter_avis_prix(type_texte: str, corps: str) -> str:
    """Oriente un `avis_prix` en hausse/baisse d'après le corps du texte.

    Retourne le type éventuellement orienté. Ni l'un ni l'autre, ou les deux : le type
    reste `avis_prix` non orienté — la ligne sortira « à vérifier ». Le routage par
    défaut en « baisse » des scripts historiques (piège MORPHINE) est proscrit.
    """
    if type_texte != "avis_prix":
        return type_texte
    if avis_prix_contradictoire(type_texte, corps):
        JOURNAL.warning("Avis de prix mentionnant majoration ET baisse : non orienté.")
        return "avis_prix"
    if MOTIF_HAUSSE.search(corps):
        return "avis_hausse_prix"
    if MOTIF_BAISSE.search(corps):
        return "avis_baisse_prix"
    return "avis_prix"


def avis_prix_contradictoire(type_texte: str, corps: str) -> bool:
    """Vrai si un avis de prix annonce lui-même une majoration ET une baisse.

    Le type reste alors `avis_prix`, mais ce non-orientement ne vaut pas celui d'un avis
    neutre (« les prix sont fixés comme suit ») : ici le texte déclare deux sens, donc la
    comparaison au référentiel de prix ne doit pas trancher en aval (rapprochement.py).
    Le résultat voyage par `TexteAnalyse.prix_deux_sens` ; son câblage manquait jusqu'au
    29/07/2026, si bien qu'un tel avis ressortait avec un sens unique affirmé en silence
    dès qu'un prix antérieur était connu — retour du piège MORPHINE par la porte de
    service. Ce câblage a d'abord passé par `ambigu` (même journée, premier tour) : c'était
    un champ de trop, dont le sens est la CLASSIFICATION — cf. le commentaire des deux
    champs sur `TexteAnalyse`.
    """
    return (type_texte == "avis_prix"
            and bool(MOTIF_HAUSSE.search(corps)) and bool(MOTIF_BAISSE.search(corps)))


def _texte_cellules(rangee) -> list[str]:
    """Texte des cellules (`td`/`th`) d'une rangée de tableau HTML."""
    return [cellule.get_text(" ", strip=True) for cellule in rangee.find_all(["td", "th"])]


def _index_colonne(entetes: list[str], candidats: tuple[str, ...],
                   exclus: tuple[str, ...] = ()) -> int | None:
    """Index de la première colonne dont l'en-tête contient un des candidats.

    `exclus` : sous-chaînes qui disqualifient une colonne malgré un candidat (la DCI
    contient « dénomination » sans être la dénomination cherchée, voir `ENTETES_DCI`).
    """
    for i, entete in enumerate(entetes):
        bas = entete.lower()
        if any(c in bas for c in exclus):
            continue
        if any(c in bas for c in candidats):
            return i
    return None


@dataclass(frozen=True)
class _IndexColonnes:
    """Où lire chaque donnée dans les rangées d'un tableau (`None` = colonne absente).

    `denomination` est toujours un index exploitable ; `entete_reconnu` dit s'il vient
    d'un en-tête ou du repli « première colonne » — les deux rôles étaient portés par la
    même variable avant le 29/07/2026.
    """

    denomination: int
    entete_reconnu: bool
    laboratoire: int | None
    cip: int | None
    ppttc: int | None
    taux: int | None


def _index_colonnes(entetes: list[str]) -> _IndexColonnes:
    """Repère les colonnes utiles dans la première rangée d'un tableau."""
    i_denomination = _index_colonne(entetes, ENTETES_DENOMINATION, exclus=ENTETES_DCI)
    return _IndexColonnes(
        # pas d'en-tête reconnu : la 1re colonne non-CIP portera la dénomination
        denomination=0 if i_denomination is None else i_denomination,
        entete_reconnu=i_denomination is not None,
        laboratoire=_index_colonne(entetes, ENTETES_LABORATOIRE),
        cip=_index_colonne(entetes, ("cip", "ucd")),
        ppttc=_index_colonne(entetes, ("ppttc", "prix public")),
        taux=_index_colonne(entetes, ENTETES_TAUX),
    )


def _cellule(cellules: list[str], index: int | None) -> str:
    """Texte d'une cellule, `""` si la colonne est absente ou la rangée trop courte.

    Les tableaux du JO ont des rangées plus courtes que leur en-tête (cellules
    fusionnées, lignes de total) : lire une colonne est toujours faillible.
    """
    if index is None or index >= len(cellules):
        return ""
    return cellules[index].strip()


# Pattern explicite des dénominations Légifrance : « … (laboratoires STRAGEN FRANCE) ».
# Étiquette littérale → aucune conjecture : le contenu EST le laboratoire (exploitant).
MOTIF_LABO_PARENTHESE = re.compile(r"\(\s*laboratoires?\s+([^)]+?)\s*\)", re.IGNORECASE)


def _extraire_laboratoire(denomination: str) -> tuple[str, str]:
    """(dénomination sans sa parenthèse laboratoire, laboratoire trouvé ou "").

    1. Pattern explicite « (laboratoires X) » (constaté sur les trois familles de
       tableaux du JO) : X est le laboratoire, la parenthèse est retirée de la
       dénomination affichée (l'information part en colonne Laboratoire).
    2. Repli : parenthèse contenant une clé du mapping laboratoires (usage historique) —
       on n'invente rien, une parenthèse quelconque reste une parenthèse explicative.
    """
    trouve = MOTIF_LABO_PARENTHESE.search(denomination)
    if trouve:
        nettoyee = MOTIF_LABO_PARENTHESE.sub("", denomination)
        nettoyee = re.sub(r"\s+", " ", nettoyee).strip(" ,;")
        return nettoyee, trouve.group(1).strip()
    for contenu in re.findall(r"\(([^)]+)\)", denomination):
        contenu_maj = contenu.upper()
        for cle in config.MAPPING_LABOS:
            if cle in contenu_maj:
                return denomination, contenu.strip()
    return denomination, ""


# Codes produit dans les cellules : CIP-13 (34009…) ou UCD (34008… — les textes de la
# liste en sus, arrêtés ET avis, publient des « Code UCD », constaté sur pièces au JO
# du 04/06/2026), en bloc (3400930163160) ou groupés par espaces (« 34009 301 631 6 0 »,
# format constaté sur les tableaux réels des 28/05 et 22/07). CIP et UCD partagent le
# rôle de clé de rapprochement inter-textes (champ `cip` des produits extraits).
#
# Périmètre distinct de `MOTIF_CODE_TARIFAIRE`, vérifié cellule par cellule le
# 29/07/2026 : les deux ensembles se croisent sans se recouvrir, aucun ne contient
# l'autre. Ce motif seul reconnaît les codes groupés par espaces (« 34009 301 631 6 0 »,
# présent dans les tableaux réels) et les longueurs hors norme à préfixe 34008/34009 ;
# `MOTIF_CODE_TARIFAIRE` seul reconnaît les blocs de 12 à 14 chiffres à autre préfixe
# (« 4000930000011 »). Les garder tous les deux n'est donc pas une redondance : la
# décision « cette cellule est un code, pas une dénomination » est leur UNION, portée
# par `_est_code_produit`.
MOTIF_CIP_UCD = re.compile(r"^\s*(3\s*4\s*0\s*0\s*[89](?:\s*\d)+)\s*$")

# Cellule sans lettre : chiffres, espaces, séparateurs, € et % — une ligne purement
# tarifaire, jamais une dénomination.
MOTIF_LIGNE_TARIFAIRE = re.compile(r"[\d\s,.€%]+")


def _cip_normalise(cellule: str) -> str:
    """Code CIP/UCD d'une cellule, chiffres seuls ("" si la cellule n'en est pas un)."""
    trouve = MOTIF_CIP_UCD.match(cellule)
    return re.sub(r"\s+", "", trouve.group(1)) if trouve else ""


def _est_code_produit(cellule: str) -> bool:
    """Vrai si la cellule porte un code (tarifaire ou CIP/UCD) et non une dénomination.

    Union des deux motifs, dont les périmètres diffèrent (voir la note de
    `MOTIF_CIP_UCD`) : aucun des deux ne suffit seul.
    """
    return bool(MOTIF_CODE_TARIFAIRE.match(cellule)) or bool(_cip_normalise(cellule))


def _libelle_comparable(cellule: str) -> str:
    """Libellé de cellule comparable à un en-tête : minuscules, sans accents, espaces
    réduits.

    Un même en-tête s'écrit accentué dans une rangée et en capitales non accentuées dans
    une autre (« DENOMINATION DE LA SPECIALITE ») : les deux orthographes de
    `ENTETES_DENOMINATION` en témoignent. La comparaison reste une égalité stricte à ces
    variations d'écriture près.
    """
    sans_accents = "".join(caractere
                           for caractere in unicodedata.normalize("NFD", cellule)
                           if not unicodedata.combining(caractere))
    return re.sub(r"\s+", " ", sans_accents).strip().lower()


# Un libellé d'en-tête ne porte pas de chiffre ; une dénomination en porte presque
# toujours un (dosage, conditionnement). Sert à écarter du gabarit de rappel d'en-tête les
# cellules qui n'en sont manifestement pas — voir `_libelles_d_entete`.
MOTIF_CHIFFRE = re.compile(r"\d")


def _libelles_d_entete(entetes: list[str]) -> tuple[str, ...]:
    """Libellés de la première rangée qui peuvent servir de gabarit aux rappels d'en-tête.

    Toute cellule contenant un CHIFFRE est écartée. Sans ce filtre, un tableau sans
    en-tête réel dont la première rangée est *crue* en-tête faisait de son premier produit
    le filtre du reste du tableau : `_index_colonnes` reconnaît un en-tête par sous-chaîne,
    et « nom » est dans « NOMEGESTROL ACETATE VIATRIS 3,75 mg ». Les rangées reproduisant
    cette dénomination disparaissaient alors sans anomalie, sans « (à vérifier) » et sans
    log — effet de bord constaté le 29/07/2026 sur la réparation du rappel d'en-tête, et
    exactement le vide silencieux que le projet proscrit.

    Les libellés réels des tableaux du JO n'ont pas de chiffre (« Code CIP »,
    « Dénomination de la spécialité », « PPTTC », « Date d'effet ») : le filtre ne leur
    coûte rien. Un libellé qui en porterait un (appel de note) sort du gabarit — la rangée
    de rappel reste écartée par les autres cellules, cf. `_rangee_rappelle_les_entetes`.
    """
    return tuple(_libelle_comparable(entete) for entete in entetes
                 if entete.strip() and not MOTIF_CHIFFRE.search(entete))


def _rangee_rappelle_les_entetes(cellules: list[str],
                                 entetes_du_tableau: tuple[str, ...]) -> bool:
    """Vrai si la rangée rappelle les en-têtes du tableau (saut de page) : pas un produit.

    Deux formes constatées, d'où deux conditions suffisantes :
    - **DEUX** cellules au moins reproduisent un libellé d'en-tête. Une vraie ligne
      produit n'en a jamais deux (au plus une, quand un montant vaut « PPTTC ») ; exiger
      deux cellules met donc la règle hors de portée des lignes produit ;
    - ou bien TOUTES les cellules non vides en reproduisent un — le rappel partiel, où le
      libellé est seul sur sa rangée (cellules vides ou `colspan`).

    La règle porte sur la RANGÉE et non sur la seule dénomination (première écriture, du
    29/07/2026) : une dénomination seule ne suffit pas, sinon la rangée d'un tableau dont
    la première ligne est faussement crue en-tête disparaît en silence. Compromis assumé,
    dans le sens que le projet privilégie (une ligne fantôme se voit, une ligne perdue
    non) : un rappel qui ne reproduirait qu'UN libellé et porterait par ailleurs une
    cellule étrangère non vide (« page 2 » dans un tableau à deux colonnes) ressort en
    ligne fantôme. Jamais observé — les rappels réels reprennent la rangée d'en-tête
    entière.
    """
    if not entetes_du_tableau:
        return False
    libelles = [_libelle_comparable(cellule) for cellule in cellules if cellule.strip()]
    if not libelles:
        return False
    rappels = sum(1 for libelle in libelles if libelle in entetes_du_tableau)
    return rappels >= 2 or rappels == len(libelles)


def _denomination_de_la_rangee(cellules: list[str], index_denomination: int,
                               entetes_du_tableau: tuple[str, ...] = ()) -> str:
    """Dénomination portée par une rangée, `""` si la rangée n'est pas un produit.

    Quatre façons de n'en être pas un, toutes constatées sur pièces : rangée trop courte,
    ligne purement tarifaire, (sous-)en-tête de tableau (« Code CIP » en cellule de
    données, run réel du 21/07/2026), et rappel d'un en-tête RÉEL du tableau au fil des
    sauts de page (« Dénomination de la spécialité ») : ces libellés multi-mots
    échappaient à `LIBELLES_EN_TETE`, qui n'égale que des mots isolés, et sortaient en
    ligne produit fantôme — sans « (à vérifier) », donc invisible au récapitulatif
    (défaut réparé le 29/07/2026).

    `entetes_du_tableau` : les libellés d'en-tête de CE tableau, déjà comparables (vides
    quand sa première rangée n'est pas un en-tête reconnu — ce sont alors des
    dénominations, qu'on ne compare pas entre elles). La règle reste une ÉGALITÉ, à la
    casse et aux espaces près, et porte sur la RANGÉE ENTIÈRE
    (`_rangee_rappelle_les_entetes`) : une dénomination réelle n'est jamais prise pour un
    en-tête, même courte, même lorsqu'elle contient — ou reproduit — un mot d'en-tête.
    """
    if not cellules or index_denomination >= len(cellules):
        return ""
    if _rangee_rappelle_les_entetes(cellules, entetes_du_tableau):
        return ""  # rappel des en-têtes réels de ce tableau, jamais un produit
    denomination = cellules[index_denomination].strip()
    if not denomination or _est_code_produit(denomination):
        # cellule vide ou code CIP : chercher la première cellule « nom » plausible
        candidates = [c.strip() for c in cellules
                      if c.strip() and not _est_code_produit(c)
                      and not MOTIF_LIGNE_TARIFAIRE.fullmatch(c.strip())]
        if not candidates:
            return ""
        denomination = candidates[0]
    if MOTIF_LIGNE_TARIFAIRE.fullmatch(denomination):
        return ""  # ligne purement tarifaire
    if denomination.lower().strip() in LIBELLES_EN_TETE:
        return ""  # sous-en-tête de tableau (« Code CIP »…), jamais un produit
    return denomination


def _cip_de_la_rangee(cellules: list[str], index: int | None) -> str:
    """Code CIP/UCD d'une rangée : la colonne dédiée, sinon la première cellule qui en
    a le format (tableaux sans en-tête reconnu)."""
    cip = _cip_normalise(_cellule(cellules, index))
    if cip:
        return cip
    for cellule in cellules:  # tableau sans colonne dédiée : première cellule au format CIP
        cip = _cip_normalise(cellule)
        if cip:
            return cip
    return ""


def _prix_de_la_rangee(cellules: list[str], index: int | None) -> str:
    """Montant recopié d'une colonne tarifaire, espaces réduits (`""` si absente)."""
    return re.sub(r"\s+", " ", _cellule(cellules, index))


def _taux_de_la_rangee(cellules: list[str], index: int | None, taux_global: str) -> str:
    """Taux de participation d'une rangée, en décimal (« 35 % » → « 0.35 »).

    Repli sur `taux_global` (taux unique énoncé par le texte) quand le tableau n'a pas de
    colonne de taux, ou que sa cellule n'en porte pas : une décision UNCAM à taux unique
    ne le répète pas toujours ligne à ligne.
    """
    trouve = MOTIF_TAUX.search(_cellule(cellules, index)) if index is not None else None
    return f"{int(trouve.group(1)) / 100:g}" if trouve else taux_global


def _produit_de_la_rangee(cellules: list[str], colonnes: _IndexColonnes, denomination: str,
                          indication_section: str, taux_global: str,
                          laboratoire_precedent: str = "") -> ProduitExtrait:
    """Assemble la présentation d'une rangée dont la dénomination est déjà établie.

    Le laboratoire vient de sa colonne dédiée ; à défaut de la parenthèse
    « (laboratoires X) », qui est alors retirée de la dénomination affichée.
    """
    laboratoire = _cellule(cellules, colonnes.laboratoire)
    denomination, labo_parenthese = _extraire_laboratoire(denomination)
    return ProduitExtrait(
        denomination_brute=denomination,
        laboratoire_brut=laboratoire or labo_parenthese,
        cip=_cip_de_la_rangee(cellules, colonnes.cip),
        ppttc=_prix_de_la_rangee(cellules, colonnes.ppttc),
        taux=_taux_de_la_rangee(cellules, colonnes.taux, taux_global),
        laboratoire_precedent=laboratoire_precedent,
        indication=indication_section)


def _colspan(cellule) -> int:
    """Nombre de colonnes couvertes par une cellule (1 si l'attribut est absent ou illisible)."""
    try:
        return max(1, int(cellule.get("colspan", 1)))
    except (TypeError, ValueError):
        return 1


def _decalage_bloc_abroge(rangees: list) -> int:
    """Nombre de cellules du bloc « libellés abrogés » en tête de chaque rangée de données,
    0 si le tableau n'est pas à deux blocs (cas de tous les autres tableaux du JO).

    Le gabarit se reconnaît sur DEUX rangées d'en-tête : la première annonce les deux blocs
    (deux cellules fusionnées, « Libellés abrogés » puis « Nouveaux libellés »), la seconde
    donne les colonnes réelles, répétées à l'identique de part et d'autre. Sans cette
    lecture, l'en-tête fusionné à deux cellules servait de gabarit à des rangées de données
    à quatre : les index tombaient à côté, le parser recopiait le libellé ABROGÉ et la
    veille annonçait l'ANCIEN exploitant (défaut constaté le 29/07/2026 sur le JO du
    23/07 — CEFEPIME NORIDEM donné à AGUETTANT, qui venait justement de le céder).
    """
    if len(rangees) < 2:
        return 0
    entetes_blocs = rangees[0].find_all(["td", "th"])
    if len(entetes_blocs) != 2:
        return 0
    gauche, droite = (_libelle_comparable(c.get_text(" ", strip=True)) for c in entetes_blocs)
    if not any(mot in gauche for mot in ENTETES_BLOC_ABROGE):
        return 0
    if not any(mot in droite for mot in ENTETES_BLOC_NOUVEAU):
        return 0
    decalage = _colspan(entetes_blocs[0])
    # Les deux blocs portent les mêmes colonnes : la rangée de sous-en-têtes le confirme.
    # Largeurs incohérentes → gabarit non reconnu, lecture ordinaire (jamais de découpe
    # au hasard, qui mélangerait les deux états).
    if len(_texte_cellules(rangees[1])) != decalage + _colspan(entetes_blocs[1]):
        return 0
    return decalage


def _est_bandeau_titre(rangee) -> bool:
    """Vrai si la rangée est un bandeau de titre pleine largeur (une seule cellule,
    fusionnée sur plusieurs colonnes) : jamais un en-tête de colonnes ni une donnée.

    Constaté sur le JO du 30/07/2026 (arrêté de transfert de laboratoire, liste en
    sus L. 162-23-6) : chacun des deux tableaux « Ancien/Nouveau laboratoire
    exploitant... » ouvre sur une rangée bandeau (`<th colspan="5">`) AVANT sa
    vraie rangée d'en-têtes de colonnes. Sans ce filtre, `_gabarit_du_tableau`
    prenait ce bandeau pour LA rangée d'en-tête ; aucune colonne n'y matchait
    (« ancien laboratoire... » ne contient ni « dénomination » ni « nom » ni
    « libellé »), si bien que le bandeau, la vraie rangée d'en-têtes ET la rangée
    de données étaient tous les trois lus comme des produits fantômes.
    """
    cellules = rangee.find_all(["td", "th"])
    return len(cellules) == 1 and _colspan(cellules[0]) >= 2


def _compter_bandeaux(rangees: list) -> int:
    """Nombre de bandeaux de titre en tête du tableau (0 pour tous les autres tableaux
    du JO, qui commencent directement par leur rangée d'en-têtes ou de données)."""
    n = 0
    while n < len(rangees) and _est_bandeau_titre(rangees[n]):
        n += 1
    return n


def _laboratoire_du_bloc_abroge(cellules: list[str], decalage: int) -> str:
    """Exploitant lu dans le bloc « libellés abrogés » d'une rangée (`""` hors de ce gabarit).

    Seule sa parenthèse « (laboratoires X) » est reprise : ce bloc décrit un état révolu,
    il n'alimente ni la dénomination, ni le CIP, ni le rapprochement.
    """
    for cellule in cellules[:decalage]:
        _, laboratoire = _extraire_laboratoire(cellule)
        if laboratoire:
            return laboratoire
    return ""


@dataclass(frozen=True)
class _Gabarit:
    """Comment lire les rangées de données d'un tableau : quelles colonnes, à partir de
    quelle rangée, et combien de cellules d'état abrogé les précèdent."""

    colonnes: _IndexColonnes
    entetes: tuple[str, ...]      # libellés d'en-tête, pour écarter leurs rappels
    premiere_donnee: int
    decalage: int = 0


def _gabarit_du_tableau(rangees: list) -> _Gabarit:
    """Établit le gabarit de lecture d'un tableau depuis sa (ou ses deux) rangée(s) d'en-tête.

    Les bandeaux de titre pleine largeur (`_compter_bandeaux`), s'il y en a, sont
    sautés avant toute lecture d'en-tête : ils ne portent ni colonnes ni données.
    """
    bandeaux = _compter_bandeaux(rangees)
    rangees_utiles = rangees[bandeaux:]
    if not rangees_utiles:
        return _Gabarit(_index_colonnes([]), (), len(rangees))
    decalage = _decalage_bloc_abroge(rangees_utiles)
    i_entetes = 1 if decalage else 0      # tableau à deux blocs : les colonnes sont en 2e rangée
    entetes = _texte_cellules(rangees_utiles[i_entetes])[decalage:]
    colonnes = _index_colonnes(entetes)
    # Libellés d'en-tête de ce tableau : ils servent à écarter leurs rappels de
    # mi-tableau (sauts de page des longs arrêtés). Sans en-tête reconnu, la première
    # rangée porte des dénominations : rien à comparer.
    entetes_du_tableau = _libelles_d_entete(entetes) if colonnes.entete_reconnu else ()
    premiere_donnee = bandeaux + (i_entetes + 1 if (decalage or colonnes.entete_reconnu) else 0)
    return _Gabarit(colonnes, entetes_du_tableau, premiere_donnee, decalage)


def parser_tableaux(tableaux: list, indications_sections: list[str] | None = None,
                    taux_global: str = "N/A") -> list[ProduitExtrait]:
    """Extrait une présentation par ligne des tableaux HTML d'un texte, dans l'ordre.

    Par ligne : dénomination, laboratoire (colonne dédiée, sinon parenthèse
    « (laboratoires X) » retirée de la dénomination), code CIP, PPTTC (recopie de la
    colonne, jamais affiché : il oriente les avis de prix neutres), taux de participation
    (colonne dédiée, sinon `taux_global`), et l'indication de la section du tableau
    (`indications_sections[i]`, liaison position constatée sur pièces).

    Tableau à deux blocs « libellés abrogés / nouveaux libellés » (arrêtés de modification
    de libellé) : la présentation est celle du bloc de droite — l'état nouveau, seul à
    décrire aujourd'hui — et le bloc de gauche ne livre que le laboratoire précédent.

    Deux rangées ne donnent aucun produit : celles des en-têtes, et celles qui les
    rappellent au fil des sauts de page (leur dénomination est un libellé d'en-tête du
    tableau — voir `_denomination_de_la_rangee`).
    """
    produits: list[ProduitExtrait] = []
    indications_sections = indications_sections or []
    for i_tableau, tableau in enumerate(tableaux):
        indication_section = (indications_sections[i_tableau]
                              if i_tableau < len(indications_sections) else "")
        rangees = tableau.find_all("tr")
        if not rangees:
            continue
        gabarit = _gabarit_du_tableau(rangees)
        for rangee in rangees[gabarit.premiere_donnee:]:
            rangee_entiere = _texte_cellules(rangee)
            cellules = rangee_entiere[gabarit.decalage:]   # bloc de l'état à décrire
            denomination = _denomination_de_la_rangee(cellules, gabarit.colonnes.denomination,
                                                      gabarit.entetes)
            if not denomination:
                continue
            produits.append(_produit_de_la_rangee(
                cellules, gabarit.colonnes, denomination, indication_section, taux_global,
                laboratoire_precedent=_laboratoire_du_bloc_abroge(rangee_entiere,
                                                                  gabarit.decalage)))
    return produits


def taux_unique_du_texte(texte: str) -> str:
    """Taux de participation unique mentionné dans un texte (décision UNCAM), sinon « N/A ».

    Plusieurs pourcentages distincts sans colonne par produit → « N/A » : on ne choisit
    jamais un taux à la place du texte (interdit d'inventer, piège « taux 1 » de VGENFLI).
    """
    trouves = {int(m.group(1)) for m in MOTIF_TAUX.finditer(texte)}
    if len(trouves) == 1:
        return f"{trouves.pop() / 100:g}"
    if len(trouves) > 1:
        JOURNAL.warning("Plusieurs taux distincts dans le texte (%s) : aucun retenu "
                        "globalement.", sorted(trouves))
    return "N/A"


def analyser_texte_deterministe(id_texte: str, titre: str, brut: str) -> TexteAnalyse:
    """Volet déterministe complet pour un texte : nettoyage, classification, parsing."""
    texte_nettoye, tableaux, segments = nettoyer_texte(brut)
    JOURNAL.info("Nettoyage %s : %d → %d caractères (%d tableau(x) extraits).",
                 id_texte, len(brut), len(texte_nettoye), len(tableaux))

    type_final = orienter_avis_prix(classifier_par_titre(titre), texte_nettoye)
    type_final = orienter_arrete(type_final, texte_nettoye)
    # Doute sur l'ORIENTATION du prix, pas sur la classification : un avis qui annonce les
    # deux sens (piège MORPHINE, câblé le 29/07/2026 — il interdit au référentiel de prix
    # de trancher). Champ dédié, jamais `ambigu` : ce dernier a un seul producteur,
    # l'absence de liste dans le titre d'un arrêté (ci-dessous).
    prix_deux_sens = avis_prix_contradictoire(type_final, texte_nettoye)
    ambigu = False

    # Listes visées par un arrêté (titre, « 1 liste = 1 arrêté »). Une extension
    # d'indication portée par un arrêté d'inscription garde sa liste : elle est
    # rappelée sur la ligne d'extension (règle SIRTURO). Arrêté d'inscription ou de
    # radiation sans liste identifiable : ambigu — la ligne sortira « à vérifier ».
    listes: list[str] = []
    if type_final in ("arrete_inscription", "arrete_radiation", "extension_indication"):
        listes = listes_du_titre(titre)
        if not listes and type_final != "extension_indication":
            JOURNAL.warning("Arrêté %s sans liste identifiable dans le titre : %s",
                            id_texte, titre)
            ambigu = True

    # Indication portée par la section de chaque tableau (arrêtés d'inscription et
    # extensions : la liaison est structurelle ; ailleurs le motif ne matche pas).
    indications_sections = [indication_de_section(s) for s in segments]
    trouvees = sum(1 for ind in indications_sections if ind)

    # Taux de participation : les décisions UNCAM le portent en colonne (cas nominal),
    # mais certaines l'énoncent une seule fois dans leur phrase d'attaque. Le repli ne
    # vaut que pour ces décisions : lui seul les rend exploitables, et une colonne de
    # taux n'existe pas ailleurs.
    taux_global = "N/A"
    if type_final == "decision_taux":
        taux_global = taux_unique_du_texte(texte_nettoye)

    produits = parser_tableaux(tableaux, indications_sections=indications_sections,
                               taux_global=taux_global)
    marques = ((" (AMBIGU)" if ambigu else "")
               + (" (PRIX À DEUX SENS)" if prix_deux_sens else ""))
    JOURNAL.info("Texte %s classé %s%s : %d présentation(s) extraites des tableaux, "
                 "%d indication(s) de section.",
                 id_texte, type_final, marques, len(produits), trouvees)
    return TexteAnalyse(id=id_texte, url=url_publique(id_texte), titre=titre,
                        type_texte=type_final, ambigu=ambigu, produits=produits,
                        texte_nettoye=texte_nettoye, listes=listes,
                        prix_deux_sens=prix_deux_sens)
