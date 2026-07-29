"""Consolidation « une ligne par nom de médicament » (E5 révisée le 23/07/2026).

Historique du contrat : une ligne par produit racine (spec §5), puis une ligne par
présentation Légifrance (demande utilisatrice du 22/07/2026), puis retour arrière
demandé par l'utilisatrice le 23/07/2026 après retour des destinataires : les prix
détaillés faisaient des tableaux trop gros. Contrat final :

- **une ligne par nom de médicament et par laboratoire** (les 5 dosages de Lacosamide
  → une seule ligne « LACOSAMIDE » ; DARUNAVIR Viatris et DARUNAVIR Zentiva restent
  deux lignes : un même médicament générique est commercialisé par plusieurs
  laboratoires) ;
- **plus aucun prix chiffré** : la colonne Prix est un simple lien « Site LégiFrance »
  vers l'avis. Le **taux de participation** reste chiffré, lui : la maquette
  utilisatrice comme le fichier CIBLE du 28/05/2026 portent un « 35% » cliquable vers
  la décision UNCAM qui le publie ;
- **5 listes d'inscription** (SS, Collectivité, LES MCO, LES SMR, Rétrocession),
  chacune portée par son propre arrêté (« 1 liste = 1 arrêté ») → un lien cliquable
  par segment de la colonne Liste ;
- **6 sections** : Nouvelles inscriptions, Hausse de prix, Baisse de prix,
  Modification de libellé, Extensions d'indications, Radiations ;
- **transfert d'exploitation** : un arrêté de modification de libellé change presque
  toujours l'exploitant, pas le nom du produit. La ligne décrit l'état NOUVEAU, et la
  colonne Laboratoire montre la transition « ancien → nouveau » ;
- **règle SIRTURO (23/07/2026)** : une spécialité présente à la fois en inscription,
  extension d'indication et modification de prix ne sort QUE dans les Extensions
  d'indications, en précisant ses listes et le lien de prix.

Le rapprochement inter-textes reste générique (aucun identifiant codé en dur) :

- clé de ligne : (nom racine — annexe C, laboratoire mappé — annexe D) ; les textes
  dont les produits n'indiquent pas de laboratoire contribuent à toutes les lignes
  de la même racine ;
- l'indication vient de la section du tableau (analyse.py, recopie exacte) ; sans
  elle, « à compléter manuellement » sur les inscriptions/extensions — jamais de
  vide silencieux ;
- le laboratoire vient de la parenthèse « (laboratoires X) » ou de la colonne
  dédiée, puis passe par le mapping unique de l'annexe D (piège LAVOISIER).
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import date

import config
from analyse import TexteAnalyse
from referentiel_prix import en_decimal

JOURNAL = logging.getLogger("veille_jo.rapprochement")

PRODUIT_INCONNU = "PRODUIT INCONNU"

SECTION_INSCRIPTIONS = "nouvelles_inscriptions"
SECTION_HAUSSES = "hausses"
SECTION_BAISSES = "baisses"
SECTION_MODIFICATIONS = "modifications_libelle"
SECTION_EXTENSIONS = "extensions"
SECTION_RADIATIONS = "radiations"

# Sections de la veille dans l'ordre d'affichage : (clé, titre, couleur de bandeau en
# hexadécimal nu). Source unique des deux rendus — contrat du 23/07/2026, titres calqués
# sur les mails manuels de l'utilisatrice (22-23/07/2026) : « Nouvelles inscriptions » au
# pluriel, hausse et baisse au singulier. Le mail préfixe la couleur d'un « # », l'Excel
# la passe telle quelle à openpyxl ; chaque rendu ajoute sa propre table de colonnes.
SECTIONS = [
    (SECTION_INSCRIPTIONS, "Nouvelles inscriptions", "F2CEED"),
    (SECTION_HAUSSES, "Hausse de prix", "F6C5AC"),
    (SECTION_BAISSES, "Baisse de prix", "C1F0C7"),
    (SECTION_MODIFICATIONS, "Modification de libellé", "DEEAF6"),
    (SECTION_EXTENSIONS, "Extensions d'indications", "D1D6FF"),
    (SECTION_RADIATIONS, "Radiations", "D9D9D9"),
]

ROLES = {
    "arrete_inscription": "arrêté d'inscription",
    "arrete_radiation": "arrêté de radiation",
    "modification_libelle": "modification de libellé",
    "avis_prix": "avis de prix (non orienté)",
    "avis_hausse_prix": "avis de hausse de prix",
    "avis_baisse_prix": "avis de baisse de prix",
    "decision_taux": "décision de taux UNCAM",
    "extension_indication": "extension d'indication",
    "autre": "non exploité",
}

# Ordre d'affichage des listes dans la colonne Liste (« SS & Collectivité »).
ORDRE_LISTES = [liste for liste, _ in config.MOTIFS_LISTES]


def pourcentage(taux: str) -> str:
    """Taux décimal en pourcentage lisible : « 0.35 » → « 35% », « N/A » inchangé.

    Ici et pas dans chaque rendu : le mail, l'Excel et les motifs d'anomalie doivent
    écrire le même taux de la même façon.
    """
    return taux if taux == "N/A" else f"{round(float(taux) * 100)}%"

# Annexe C, étape 2 : dosages (nombre + unité, éventuellement rapporté à /ml ou /dose).
# Le nombre d'un dosage s'écrit : groupes de milliers séparés par une espace (exactement
# trois chiffres chacun, typographie française — « 1 000 000 UI » constaté sur ORACILLINE
# au JO du 22/07/2026, « 12 500 UI » sur les héparines calciques) puis, éventuellement,
# une décimale derrière une virgule (« 0,25 mg », et « 0, 25 mg » : l'espace parasite reste
# une décimale, comme dans `_couper_au_conditionnement`). Ces deux rôles sont DISTINCTS
# depuis le 29/07/2026 : le groupe unique `(?:[\s,]\s*[0-9]+)*` qui tenait les deux avalait
# le chiffre final du nom du produit dès qu'un dosage suivait (« GARDASIL 9 0,5 ml » →
# « GARDASIL », « OMEGA 3 1000 mg » → « OMEGA »), ce qui tronquait le nom ET fondait deux
# spécialités distinctes (VITAMINE D2 / D3) sur une même ligne de newsletter.
# Limite assumée : « NOM 3 500 mg » reste ambigu pour toute regex (« 3 500 mg » ou « NOM 3 »
# + « 500 mg » ?) et se lit comme un dosage à séparateur de milliers — arbitrage en faveur
# des dosages réels, plus fréquents que les noms terminés par un chiffre isolé.
MOTIF_DOSAGE = re.compile(
    # DEUX formes, parce que le JO écrit les deux — corrigé le 29/07/2026 après REJEU RÉEL
    # (JO des 09/06, 02/07 et 23/07) : un `\b` unique en tête protégeait bien le chiffre
    # final du nom, mais bloquait aussi les dosages COLLÉS des dénominations abrégées des
    # avis de prix (« POMALIDOMIDE LPN1MG » → « POMALIDOMIDE LPN1MG » au lieu de
    # « POMALIDOMIDE LPN », « REMSIMA … FL2,5ML » → « REMSIMA FL2 »).
    #   1. dosage DÉTACHÉ (cas nominal) : séparateurs de milliers et décimales admis ;
    #   2. dosage COLLÉ à une lettre : volontairement restreint — ni séparateur de milliers,
    #      ni espace avant l'unité. C'est cette restriction qui préserve le chiffre final du
    #      nom (« CACIT VITAMINE D3 500 mg », « VITAMINE B12 1000 µg »), lequel est TOUJOURS
    #      suivi d'une espace avant son dosage, jamais d'une unité accolée.
    r"(?:\b[0-9]+(?:\s[0-9]{3})*(?:,\s*[0-9]+)?\s*"
    r"|(?<=[A-Za-z])[0-9]+(?:,[0-9]+)?)"
    # Unités en toutes lettres constatées aux runs de test du 29/07/2026
    # (« 137 MICROGRAMMES/50 MICROGRAMMES », AZELASTINE au JO du 07/07) : les formes
    # longues AVANT les courtes, sinon « g » matche au milieu de « grammes ».
    r"(?:(?:microgrammes?|milligrammes?|grammes?|mg|ml|µg|ug|g|ui|unités?|unites?)\b|%)"
    r"(?:\s*/\s*[0-9]*\s*(?:ml|dose)\b|\s+par\s+ml\b)?",
    re.IGNORECASE,
)
# Annexe C, étape 4 : mentions de pack. « aiguille(s) (à filtre) » constaté au run réel
# du 28/05/2026 (« + 4 AIGUILLES », « + 1 AIGUILLE À FILTRE » — calibration E2/E3).
MOTIF_PACK_X = re.compile(r"\bx\s*\d+\b", re.IGNORECASE)
MOTIF_PACK_N = re.compile(r"\b\d+\s*(?:doses|stylos|sprays|aiguilles?(?:\s+à\s+filtre)?)\b",
                          re.IGNORECASE)
# Sels/esters (config.SELS_ET_ESTERS) : supprimés seulement s'ils SUIVENT un mot
# (MORPHINE SULFATE → MORPHINE, mais SULFATE DE MAGNÉSIUM reste intact).
MOTIF_SELS = re.compile(r"(?<=\S)\s+(?:" + "|".join(config.SELS_ET_ESTERS) + r")\b",
                        re.IGNORECASE)


@dataclass(frozen=True)
class RappelExtension:
    """Un rappel à porter sous l'indication d'une ligne d'extension (règle SIRTURO).

    Données, pas de rendu : l'étiquette et ce qu'elle désigne (des segments de liste ou
    un lien). Chaque rendu décide comment l'écrire — le mail pose des hyperliens, l'Excel
    renvoie au mail (une cellule Excel ne porte qu'un seul hyperlien).
    """

    etiquette: str
    segments: list[tuple[str, str | None]] = field(default_factory=list)
    lien: str | None = None


@dataclass
class LigneConsolidee:
    """Une ligne du tableau de veille : un nom de médicament × un laboratoire."""

    produit: str                       # nom racine (colonne Produit, contrat du 23/07/2026)
    date_jo: date
    laboratoire: str = ""
    indication: str = ""               # indications de section, uniques, séparées par \n
    listes: list[tuple[str, str | None]] = field(default_factory=list)
    # inscriptions : (libellé de liste, lien de SON arrêté) — un segment cliquable chacun
    listes_radiation: list[tuple[str, str | None]] = field(default_factory=list)
    lien_prix: str | None = None       # URL de l'avis de prix (colonne Prix, texte
                                       # « Site LégiFrance » — plus jamais de montant)
    taux: str = "N/A"                  # taux de participation en décimal (« 0.35 »)
    lien_taux: str | None = None       # URL de la décision UNCAM (colonne Taux)
    lien_modification: str | None = None  # URL de l'arrêté de modification de libellé
    laboratoire_precedent: str = ""     # exploitant cédant, quand un arrêté de
                                        # modification de libellé transfère l'exploitation
    lien_extension: str | None = None  # URL du texte d'extension (colonne Lien)
    section: str = ""
    a_verifier: bool = False
    motifs_verification: list[str] = field(default_factory=list)
    sources: list[tuple[str, str]] = field(default_factory=list)  # (JORFTEXT, rôle)
    racine: str = ""                   # nom racine (clé de la recette)

    @property
    def laboratoire_affiche(self) -> str:
        """Texte de la colonne Laboratoire : « ancien → nouveau » quand un arrêté de
        modification de libellé a transféré l'exploitation ce jour-là, le laboratoire seul
        partout ailleurs, « N/A » quand aucun texte ne le nomme.

        Le transfert s'affiche quelle que soit la section : c'est une information publiée
        du jour, et une ligne classée ailleurs (produit relabellisé ET inscrit le même
        jour) n'a pas de raison de la taire.
        """
        actuel = self.laboratoire or "N/A"
        if self.laboratoire_precedent and self.laboratoire_precedent != self.laboratoire:
            return f"{self.laboratoire_precedent} → {actuel}"
        return actuel

    @property
    def liste(self) -> str:
        """Texte de la colonne Liste (« SS & Collectivité », format utilisatrice)."""
        return " & ".join(libelle for libelle, _ in self.listes)

    @property
    def liste_radiation(self) -> str:
        return " & ".join(libelle for libelle, _ in self.listes_radiation)

    @property
    def segments_liste(self) -> list[tuple[str, str | None]]:
        """Segments (libellé, lien) que porte la colonne Liste : les listes radiées en
        section Radiations, les listes d'inscription partout ailleurs."""
        if self.section == SECTION_RADIATIONS:
            return self.listes_radiation
        return self.listes

    @property
    def lien_section(self) -> str | None:
        """URL de la colonne Lien : le texte porteur de la section (modification de
        libellé, arrêté de radiation, texte d'extension)."""
        if self.section == SECTION_MODIFICATIONS:
            return self.lien_modification
        if self.section == SECTION_RADIATIONS:
            return next((lien for _, lien in self.listes_radiation if lien), None)
        return self.lien_extension

    @property
    def rappels_extension(self) -> list[RappelExtension]:
        """Rappels de la règle SIRTURO (23/07/2026) : une ligne d'extension issue du
        regroupement inscription + extension + prix rappelle ses listes d'inscription et
        sa modification de prix. Vide sur toute autre ligne."""
        if self.section != SECTION_EXTENSIONS:
            return []
        rappels = []
        if self.listes:
            rappels.append(RappelExtension("Inscription", segments=self.listes))
        if self.lien_prix:
            rappels.append(RappelExtension("modification de prix", lien=self.lien_prix))
        return rappels


@dataclass
class ResultatVeille:
    """Sortie consolidée d'un run : ce que consomment l'export Excel et le mail."""

    date_jo: date
    lignes: list[LigneConsolidee]
    anomalies: list[str] = field(default_factory=list)

    def lignes_par_section(self, section: str) -> list[LigneConsolidee]:
        """Lignes d'une section, dans l'ordre de consolidation."""
        return [l for l in self.lignes if l.section == section]


def _cles_labos_par_longueur() -> list[str]:
    """Clés de `config.MAPPING_LABOS`, la plus LONGUE d'abord.

    L'ordre d'écriture du mapping n'a donc aucune importance (défaut D1) : le prochain
    contributeur qui trie cette table de configuration par ordre alphabétique ne casse
    rien. En cas de conflit de suffixe — ajouter « PHARMA » à côté de « G.L. PHARMA » —
    c'est la clé la plus spécifique qui gagne, dans le retrait du laboratoire en fin de
    nom comme dans le mapping. Recalculé à chaque appel : le mapping est une donnée de
    configuration de quelques dizaines de clés, et les tests le remplacent à chaud.
    """
    return sorted(config.MAPPING_LABOS, key=len, reverse=True)


def _couper_au_conditionnement(nom: str) -> str:
    """0. Coupe à la première virgule NON décimale.

    Calibration E2/E3 du 21/07/2026 sur les dénominations réelles du JO du 28/05/2026 :
    « NOM dosage (dci), forme - packaging (labo) » — tout ce qui suit la virgule est du
    conditionnement. « 0,25 mg » et « ,1 ml » (virgule suivie d'un chiffre) sont préservés.
    """
    return re.split(r",(?!\s*\d)", nom, maxsplit=1)[0]


def _retirer_parentheses(nom: str) -> str:
    """1. Parenthèses explicatives — y compris non fermée en fin de nom (dénominations
    tronquées sur plusieurs cellules, constaté sur ATIMIAC/XALACOM au JO du 23/07/2026).
    """
    nom = re.sub(r"\s*\([^)]+\)", " ", nom)
    return re.sub(r"\s*\([^)]*$", " ", nom)


def _retirer_dosages(nom: str) -> str:
    """2. Dosages (cf. MOTIF_DOSAGE : séparateurs de milliers, décimales, unités en toutes
    lettres, et le chiffre final du nom du produit préservé qu'il soit collé
    — « CACIT VITAMINE D3 » — ou détaché — « GARDASIL 9 »).
    """
    return MOTIF_DOSAGE.sub(" ", nom)


def _retirer_formes_et_sels(nom: str) -> str:
    """3. Formes galéniques et packagings (liste en config, extensible), puis sels/esters.

    Espaces des formes multi-mots traités en \\s+ : les suppressions précédentes
    (dosages, parenthèses) peuvent laisser des espaces doubles au milieu d'une forme.
    """
    for forme in config.FORMES_GALENIQUES:
        motif = r"\s+".join(re.escape(mot) for mot in forme.split())
        nom = re.sub(rf"\b{motif}\b", " ", nom, flags=re.IGNORECASE)
    return MOTIF_SELS.sub(" ", nom)


def _retirer_packs_et_ponctuation(nom: str) -> str:
    """4. Packs, ponctuation orpheline (y compris traînes mixtes « - + » constatées au
    run réel du 28/05/2026 après suppression des packagings), espaces multiples.
    """
    nom = MOTIF_PACK_X.sub(" ", nom)
    nom = MOTIF_PACK_N.sub(" ", nom)
    nom = re.sub(r"\s*,\s*,+", ",", nom)
    nom = re.sub(r"[\s,;:./+-]+$", " ", nom)
    nom = re.sub(r"^[\s,;:./+-]+", " ", nom)
    nom = re.sub(r"\s+[,;]\s+", " ", nom)
    return re.sub(r"\s+", " ", nom).strip()


def _retirer_laboratoire_final(nom: str) -> str:
    """5. Laboratoire connu du mapping en fin de nom → retiré (OXAZEPAM ARROW → OXAZEPAM).

    Le nom passe en majuscules (la racine est une clé de regroupement). Une seule passe,
    sur la clé la plus longue qui termine le nom : aucune dénomination réelle ne porte
    deux laboratoires en suffixe (défaut D2). Un nom réduit au seul laboratoire est
    conservé tel quel (« ARROW » reste « ARROW »).
    """
    nom = nom.upper()
    for cle in _cles_labos_par_longueur():
        if nom.endswith(" " + cle):
            reste = nom[: -len(cle) - 1].strip()
            if reste:
                return reste
    return nom


def _nettoyer_fin(nom: str) -> str:
    """6. Re-nettoyage de la ponctuation orpheline révélée par le retrait du laboratoire
    (« MORPHINE / LAVOISIER » → « MORPHINE / » constaté au run réel du 28/05/2026), trim.
    """
    return re.sub(r"[\s,;:./+-]+$", " ", nom).strip()


def nom_racine(denomination: str) -> str:
    """Nom racine d'une dénomination (annexe C) : la clé de regroupement des lignes.

    Séquence d'étapes numérotées, dans un ordre qui ne se permute pas : la coupe au
    conditionnement réduit le champ d'abord ; dosages et formes partent avant le nettoyage
    de la ponctuation qu'ils laissent orpheline ; le laboratoire ne se reconnaît qu'en fin
    de nom, donc après tout le reste, et son retrait exige un dernier nettoyage.
    Racine vide après nettoyage → « PRODUIT INCONNU » (ligne « à vérifier »).
    """
    nom = re.sub(r"\s+", " ", denomination.replace("\xa0", " ")).strip()
    nom = _couper_au_conditionnement(nom)
    nom = _retirer_parentheses(nom)
    nom = _retirer_dosages(nom)
    nom = _retirer_formes_et_sels(nom)
    nom = _retirer_packs_et_ponctuation(nom)
    nom = _retirer_laboratoire_final(nom)
    return _nettoyer_fin(nom) or PRODUIT_INCONNU


def mapper_laboratoire(brut: str) -> str:
    """Nom de laboratoire officiel via le mapping unique de l'annexe D.

    La clé la plus longue contenue dans le nom brut (en majuscules) → sa valeur ; sinon
    brut tel quel. La longueur départage : « VIATRIS SANTE » l'emporte sur « VIATRIS »
    quel que soit l'ordre d'écriture du mapping.
    """
    propre = brut.replace("\xa0", " ").strip()
    majuscules = propre.upper()
    for cle in _cles_labos_par_longueur():
        if cle in majuscules:
            return config.MAPPING_LABOS[cle]
    return propre


# Types de textes qui justifient une ligne de veille pour leurs produits. Les décisions
# de taux et les textes « autre » ne créent jamais de ligne : ils restent des sources
# tracées, et une racine vue uniquement chez eux sort en anomalie explicite.
TYPES_PORTEURS = ("arrete_inscription", "arrete_radiation", "modification_libelle",
                  "avis_prix", "avis_hausse_prix", "avis_baisse_prix",
                  "extension_indication")

# Les trois types d'avis de prix : orientés par leur titre (hausse, baisse) ou neutres.
TYPES_AVIS_PRIX = ("avis_prix", "avis_hausse_prix", "avis_baisse_prix")


def _ajouter_uniques(cible: list, ajouts: list) -> None:
    """Ajoute en fin de `cible` les éléments encore absents : ordre d'apparition
    préservé, aucun doublon (indications, motifs, sources)."""
    for element in ajouts:
        if element not in cible:
            cible.append(element)


@dataclass
class _ArreteDeListes:
    """Axe porté par des arrêtés de listes (inscription, radiation) : le produit est visé,
    et chaque liste garde le lien de SON arrêté (« 1 liste = 1 arrêté »)."""

    vise: bool = False         # visé par un tel arrêté (même sans liste lue dans le titre)
    listes: dict[str, str | None] = field(default_factory=dict)  # liste → lien de SON arrêté

    def rattacher(self, listes: list[str], url: str) -> None:
        """Rattache des listes SANS marquer le produit visé — le premier lien vu gagne."""
        for liste in listes:
            self.listes.setdefault(liste, url)  # une liste = un arrêté : segment cliquable

    def constater(self, listes: list[str], url: str) -> None:
        """Le produit est visé par cet arrêté, avec les listes que porte son titre."""
        self.vise = True
        self.rattacher(listes, url)

    def fusionner(self, autre: "_ArreteDeListes") -> None:
        self.vise = self.vise or autre.vise
        for liste, lien in autre.listes.items():
            self.listes.setdefault(liste, lien)   # lien déjà connu ici : jamais remplacé


@dataclass
class _TexteUnique:
    """Axe constaté par un texte unique (extension d'indication, modification de
    libellé) : le produit est visé, et le lien du premier texte vu est conservé."""

    vise: bool = False
    lien: str | None = None

    def constater(self, url: str) -> None:
        self.vise = True
        if self.lien is None:
            self.lien = url

    def fusionner(self, autre: "_TexteUnique") -> None:
        self.vise = self.vise or autre.vise
        self.lien = self.lien or autre.lien   # lien déjà connu ici : jamais remplacé


@dataclass
class _Prix:
    """Axe prix : le sens annoncé par les titres d'avis, le lien de l'avis, et le sens
    constaté par comparaison au référentiel pour les avis neutres."""

    hausse: bool = False
    baisse: bool = False
    non_oriente: bool = False
    # Avis dont le TEXTE annonce les deux sens (piège MORPHINE) : non orienté, comme
    # ci-dessus, mais pour une raison qui interdit de le trancher au référentiel.
    deux_sens_annonces: bool = False
    lien: str | None = None
    sens_constates: set[str] = field(default_factory=set)   # "hausse"/"baisse" constatés
                                                            # face au référentiel de prix

    @property
    def vise(self) -> bool:
        """Un avis de prix, quel que soit son sens, porte sur ce produit."""
        return self.hausse or self.baisse or self.non_oriente

    def constater(self, type_texte: str, url: str,
                  deux_sens_annonces: bool = False) -> str | None:
        """Enregistre un avis de prix ; retourne le motif d'anomalie si un autre avis
        porte déjà sur ce produit (premier lien conservé)."""
        self.deux_sens_annonces = self.deux_sens_annonces or deux_sens_annonces
        if type_texte == "avis_hausse_prix":
            self.hausse = True
        elif type_texte == "avis_baisse_prix":
            self.baisse = True
        else:
            self.non_oriente = True
        if self.lien is None:
            self.lien = url
        elif self.lien != url:
            return "plusieurs avis de prix pour ce produit (premier lien conservé)"
        return None

    def fusionner(self, autre: "_Prix") -> None:
        self.hausse = self.hausse or autre.hausse
        self.baisse = self.baisse or autre.baisse
        self.non_oriente = self.non_oriente or autre.non_oriente
        self.deux_sens_annonces = self.deux_sens_annonces or autre.deux_sens_annonces
        self.lien = self.lien or autre.lien
        self.sens_constates |= autre.sens_constates


@dataclass
class _Modification:
    """Axe modification de libellé : mêmes règles que `_TexteUnique`, plus le laboratoire
    ANTÉRIEUR quand l'arrêté transfère l'exploitation.

    C'est le cas nominal de ces arrêtés : le nom du produit ne bouge pas, l'exploitant
    change. La colonne Laboratoire montre alors la transition « ancien → nouveau », pour
    qu'un lecteur qui suit un transfert d'AMM la voie sans ouvrir le texte.
    """

    vise: bool = False
    lien: str | None = None
    laboratoire_precedent: str = ""

    def constater(self, url: str, laboratoire_precedent: str = "") -> None:
        self.vise = True
        if self.lien is None:
            self.lien = url
        if not self.laboratoire_precedent:
            self.laboratoire_precedent = laboratoire_precedent

    def fusionner(self, autre: "_Modification") -> None:
        self.vise = self.vise or autre.vise
        self.lien = self.lien or autre.lien          # déjà connu ici : jamais remplacé
        self.laboratoire_precedent = (self.laboratoire_precedent
                                      or autre.laboratoire_precedent)


@dataclass
class _Taux:
    """Axe taux de participation : la valeur publiée par une décision UNCAM et le lien de
    cette décision (seule source du taux — les arrêtés et les avis n'en portent pas).

    `sans_valeur` : une décision UNCAM a bien visé le produit, mais son taux n'a pas pu
    être lu. La ligne le dira (« à vérifier ») plutôt que d'afficher un « N/A » muet.
    """

    valeur: str = "N/A"          # chaîne décimale (« 0.35 ») ou « N/A » — jamais déduite
    lien: str | None = None
    sans_valeur: bool = False

    def constater(self, valeur: str, url: str) -> str | None:
        """Enregistre le taux d'une présentation ; retourne le motif d'anomalie si un
        autre taux est déjà connu pour cette ligne (le premier vu est conservé)."""
        if valeur == "N/A":
            self.sans_valeur = True
            return None
        if self.valeur == "N/A":
            self.valeur = valeur
            self.lien = url
            return None
        if self.valeur != valeur:
            # Les présentations d'un même nom peuvent relever de taux différents (une
            # forme à 30 %, une autre à 65 %) : la ligne unique du contrat ne peut en
            # montrer qu'un. Jamais silencieux.
            return (f"taux de participation divergents entre présentations "
                    f"({pourcentage(self.valeur)} vs {pourcentage(valeur)}) : "
                    f"{pourcentage(self.valeur)} conservé")
        return None

    def fusionner(self, autre: "_Taux") -> None:
        self.sans_valeur = self.sans_valeur or autre.sans_valeur
        if self.valeur == "N/A":       # taux déjà connu ici : jamais remplacé
            self.valeur = autre.valeur
            self.lien = autre.lien


@dataclass
class _Tracabilite:
    """Ce qui rend une ligne auditable : d'où elle vient (sources), ce qu'elle recopie
    (indications de section) et ce qu'elle demande de vérifier (motifs)."""

    indications: list[str] = field(default_factory=list)    # uniques, ordre d'apparition
    sources: list[tuple[str, str]] = field(default_factory=list)   # (JORFTEXT, rôle)
    motifs: list[str] = field(default_factory=list)
    a_verifier: bool = False
    porteur: bool = False

    def signaler(self, motif: str) -> None:
        """Marque la ligne « à vérifier » avec son motif (repris dans le récapitulatif)."""
        self.a_verifier = True
        _ajouter_uniques(self.motifs, [motif])

    def tracer(self, source: tuple[str, str], indication: str, porteur: bool) -> None:
        """Trace le texte contributeur, son indication de section et son caractère porteur."""
        if indication:
            _ajouter_uniques(self.indications, [indication])
        _ajouter_uniques(self.sources, [source])
        self.porteur = self.porteur or porteur

    def fusionner(self, autre: "_Tracabilite") -> None:
        _ajouter_uniques(self.indications, autre.indications)
        _ajouter_uniques(self.sources, autre.sources)
        _ajouter_uniques(self.motifs, autre.motifs)
        self.a_verifier = self.a_verifier or autre.a_verifier
        self.porteur = self.porteur or autre.porteur


@dataclass
class _Cumul:
    """Contributions accumulées pour une clé (racine, laboratoire) — ou pour la racine
    seule quand un texte ne nomme pas le laboratoire (contributions communes, fondues
    dans chaque ligne de la racine).

    Conteneur : un axe métier par attribut, chacun portant SA règle de fusion.
    """

    inscription: _ArreteDeListes = field(default_factory=_ArreteDeListes)
    radiation: _ArreteDeListes = field(default_factory=_ArreteDeListes)
    prix: _Prix = field(default_factory=_Prix)
    taux: _Taux = field(default_factory=_Taux)
    extension: _TexteUnique = field(default_factory=_TexteUnique)
    modification: _Modification = field(default_factory=_Modification)
    tracabilite: _Tracabilite = field(default_factory=_Tracabilite)

    @property
    def a_verifier(self) -> bool:
        return self.tracabilite.a_verifier

    @property
    def porteur(self) -> bool:
        """Au moins un texte porteur (TYPES_PORTEURS) a contribué : une ligne est due."""
        return self.tracabilite.porteur

    def signaler(self, motif: str) -> None:
        """Marque la ligne « à vérifier » avec son motif (repris dans le récapitulatif)."""
        self.tracabilite.signaler(motif)

    def fusionner_contributions_communes(self, commun: "_Cumul") -> None:
        """Fond les contributions communes (racine sans laboratoire) dans cette ligne.

        Fusion ASYMÉTRIQUE : cette ligne — celle du laboratoire — gagne tout conflit.
        Les drapeaux s'additionnent en `or`, mais un lien déjà connu ici n'est jamais
        remplacé par celui du commun (piège des génériques : 6 laboratoires pour une
        même racine, chacun garde le lien de SON arrêté).
        """
        self.inscription.fusionner(commun.inscription)
        self.radiation.fusionner(commun.radiation)
        self.prix.fusionner(commun.prix)
        self.taux.fusionner(commun.taux)
        self.extension.fusionner(commun.extension)
        self.modification.fusionner(commun.modification)
        self.tracabilite.fusionner(commun.tracabilite)


def _reporter_selon_le_type(cumul: _Cumul, texte: TexteAnalyse, produit) -> str | None:
    """Reporte le texte (via un de ses produits) sur l'axe métier que son type désigne ;
    retourne un motif d'anomalie éventuel (aucun axe pour « autre »)."""
    if texte.type_texte == "arrete_inscription":
        cumul.inscription.constater(texte.listes, texte.url)
    elif texte.type_texte == "arrete_radiation":
        cumul.radiation.constater(texte.listes, texte.url)
    elif texte.type_texte in TYPES_AVIS_PRIX:
        # `prix_deux_sens` (analyse.avis_prix_contradictoire) ne dit rien de la
        # classification : il n'interdit que de trancher le SENS. Il ne passe donc pas par
        # `ambigu`, dont `_accumuler` fait un « à vérifier » quelle que soit la section.
        return cumul.prix.constater(texte.type_texte, texte.url,
                                    deux_sens_annonces=texte.prix_deux_sens)
    elif texte.type_texte == "decision_taux":
        # Seule source du taux de participation. Ce texte ne crée jamais de ligne : il
        # alimente la colonne Taux de la ligne portée par les arrêtés et avis du jour
        # (rattachement par code CIP), et une racine vue uniquement ici sort en anomalie.
        return cumul.taux.constater(produit.taux, texte.url)
    elif texte.type_texte == "modification_libelle":
        cumul.modification.constater(
            texte.url, mapper_laboratoire(produit.laboratoire_precedent)
            if produit.laboratoire_precedent else "")
    elif texte.type_texte == "extension_indication":
        cumul.extension.constater(texte.url)
        # Une EIT portée par un arrêté d'inscription (cas nominal au JO) garde sa
        # liste : rappelée sur la ligne d'extension (« Inscription : … », règle
        # SIRTURO) sans basculer la ligne en section Inscriptions.
        cumul.inscription.rattacher(texte.listes, texte.url)
    return None


def _accumuler(cumul: _Cumul, texte: TexteAnalyse, produit) -> None:
    """Reporte la contribution d'un texte (via un de ses produits) sur un cumul."""
    motif = _reporter_selon_le_type(cumul, texte, produit)
    if motif:
        cumul.signaler(motif)
    # `ambigu` = classification douteuse (arrêté sans liste identifiable) : la ligne est
    # « à vérifier » quelle que soit sa section. Le doute d'ORIENTATION d'un avis de prix
    # ne passe pas ici : il est signalé par `_section_du_prix`, et seulement là où le prix
    # décide de la section (sinon la ligne sortait « à vérifier » sur un motif faux —
    # effet de bord corrigé le 29/07/2026).
    if texte.ambigu:
        cumul.signaler(f"classification ambiguë du texte {texte.id}")
    role = ROLES.get(texte.type_texte, texte.type_texte)
    cumul.tracabilite.tracer((texte.id, role), getattr(produit, "indication", ""),
                             texte.type_texte in TYPES_PORTEURS)


def _listes_ordonnees(par_liste: dict[str, str | None]) -> list[tuple[str, str | None]]:
    """Segments (libellé, lien) dans l'ordre d'affichage de config.MOTIFS_LISTES."""
    ordonnees = [(liste, par_liste[liste]) for liste in ORDRE_LISTES if liste in par_liste]
    # Libellé hors référentiel (jamais observé) : conservé en fin, jamais tu.
    ordonnees += [(liste, lien) for liste, lien in par_liste.items()
                  if liste not in ORDRE_LISTES]
    return ordonnees


def _section_du_cumul(cumul: _Cumul) -> tuple[str, str | None]:
    """Section d'une ligne d'après ses contributions (priorités du contrat), et le motif
    d'anomalie que ce choix impose — à l'appelant de le signaler (fonction pure).

    Règle SIRTURO (utilisatrice, 23/07/2026) : inscription + extension d'indication +
    modification de prix le même jour → la ligne ne sort QUE dans les Extensions
    d'indications (ses listes et son lien de prix y sont rappelés au rendu).
    """
    if cumul.inscription.vise and cumul.extension.vise and cumul.prix.vise:
        return SECTION_EXTENSIONS, None
    if cumul.inscription.vise:
        return SECTION_INSCRIPTIONS, None
    if cumul.radiation.vise:
        return SECTION_RADIATIONS, None
    if cumul.extension.vise:
        return SECTION_EXTENSIONS, None
    if cumul.modification.vise:
        return SECTION_MODIFICATIONS, None
    return _section_du_prix(cumul.prix)


def _section_du_prix(prix: _Prix) -> tuple[str, str | None]:
    """Section d'une ligne dont seuls des avis de prix décident, et son motif éventuel."""
    if prix.hausse:
        return SECTION_HAUSSES, None
    if prix.baisse:
        return SECTION_BAISSES, None
    # L'avis annonce lui-même une majoration ET une baisse (piège MORPHINE) : la
    # comparaison au référentiel ne tranche jamais ce que le texte déclare contradictoire
    # (réparé le 29/07/2026 : la ligne sortait avec un sens unique, sans « à vérifier »).
    if prix.deux_sens_annonces:
        return SECTION_HAUSSES, (f"avis de prix annonçant une majoration ET une baisse "
                                 f"({prix.lien}) : classé en Hausses de prix par "
                                 "convention, sens à vérifier")
    # Avis de prix non orienté par son texte : sens constaté par comparaison au
    # référentiel de prix (PPTTC publié vs prix antérieur connu, 29/07/2026) —
    # toutes les présentations comparées doivent aller dans le même sens.
    if prix.sens_constates == {"hausse"}:
        return SECTION_HAUSSES, None
    if prix.sens_constates == {"baisse"}:
        return SECTION_BAISSES, None
    # Sens introuvable (aucun prix antérieur connu) ou contradictoire : jamais deviné.
    return SECTION_HAUSSES, (f"avis de prix non orienté ({prix.lien}) : classé en Hausses "
                             "de prix par convention, sens à vérifier")


# Textes dont les tableaux portent les dénominations complètes du JO (les avis et
# décisions abrègent : « MEROPENEM PAN », « ERIBULINE HIK ») : leurs clés (racine,
# laboratoire) font foi pour un code CIP donné.
_TYPES_DENOMINATION_COMPLETE = ("arrete_inscription", "arrete_radiation",
                                "modification_libelle", "extension_indication")


def _cle_produit(produit) -> tuple[str, str]:
    """Clé (nom racine, laboratoire mappé) d'un produit extrait."""
    racine = nom_racine(produit.denomination_brute)
    laboratoire = (mapper_laboratoire(produit.laboratoire_brut)
                   if produit.laboratoire_brut else "")
    return racine, laboratoire


def _racine_prefixe(a: tuple[str, str], b: tuple[str, str]) -> tuple[str, str] | None:
    """Si les deux clés partagent le laboratoire et qu'une racine est le préfixe de
    l'autre (« POMALIDOMIDE » / « POMALIDOMIDE LPN » : le suffixe est un code de
    laboratoire ou de forme abrégé), retourne la clé à racine courte ; sinon None."""
    if a[1] != b[1]:
        return None
    if b[0].startswith(a[0] + " "):
        return a
    if a[0].startswith(b[0] + " "):
        return b
    return None


def _cles_canoniques_par_cip(textes: list[TexteAnalyse]) -> dict[str, tuple[str, str]]:
    """Élit, pour chaque code CIP/UCD, la clé (racine, laboratoire) qui fait foi.

    Ce code est le seul identifiant commun aux familles de tableaux : les avis de
    prix — et certains arrêtés (rétrocession, constat du 02/07/2026) — abrègent les
    dénominations (« MEROPENEM PAN 1G ») et leurs racines divergent. Priorité aux
    textes à dénominations complètes (arrêtés) ; à priorité égale, la racine courte
    l'emporte quand elle est préfixe de l'autre (le reste est un code abrégé), sinon
    premier vu — divergence réelle entre arrêtés signalée au journal (jamais observé).
    """
    canoniques: dict[str, tuple[int, tuple[str, str]]] = {}   # cip → (priorité, clé)
    for texte in textes:
        priorite = 0 if texte.type_texte in _TYPES_DENOMINATION_COMPLETE else 1
        for produit in texte.produits:
            cip = getattr(produit, "cip", "")
            if not cip:
                continue
            cle = _cle_produit(produit)
            en_place = canoniques.get(cip)
            if en_place is None or priorite < en_place[0]:
                canoniques[cip] = (priorite, cle)
            elif priorite == en_place[0] and en_place[1] != cle:
                courte = _racine_prefixe(en_place[1], cle)
                if courte is not None:
                    canoniques[cip] = (priorite, courte)
                elif priorite == 0:
                    JOURNAL.warning("CIP %s porté par deux dénominations d'arrêtés "
                                    "divergentes (%s vs %s) : première conservée.",
                                    cip, en_place[1], cle)
    return {cip: cle for cip, (_priorite, cle) in canoniques.items()}


def _comparer_au_referentiel(prix: _Prix, texte: TexteAnalyse, produit,
                             referentiel, date_jo: date) -> None:
    """Archive le PPTTC publié et constate le sens du prix face au référentiel.

    Uniquement pour les avis ; le sens ne sert qu'aux avis non orientés par leur
    texte (voir `_section_du_cumul`). Prix antérieur introuvable ou égal : aucun
    sens constaté — jamais deviné.
    """
    cip = getattr(produit, "cip", "")
    nouveau = en_decimal(getattr(produit, "ppttc", ""))
    if not cip or nouveau is None:
        return
    connu = referentiel.prix_anterieur(cip, date_jo)
    referentiel.enregistrer(cip, date_jo, nouveau)
    if connu is None:
        return
    ancien, source = connu
    if nouveau == ancien:
        return
    sens = "hausse" if nouveau > ancien else "baisse"
    prix.sens_constates.add(sens)
    JOURNAL.info("Avis %s : %s constatée pour « %s » (%s € → %s €, source %s).",
                 texte.id, sens, produit.denomination_brute, ancien, nouveau, source)


def _cle_consolidee(produit, canoniques: dict[str, tuple[str, str]]) -> tuple[str, str]:
    """Clé de ligne (racine, laboratoire) d'un produit, canonicalisée par code CIP.

    Le pont CIP/UCD rattache un produit à dénomination abrégée (« MEROPENEM PAN 1G »,
    avis de prix) à la clé de l'arrêté portant le même code — la seule reprise, jamais
    devinée, entre familles de tableaux.
    """
    cle_lue = _cle_produit(produit)
    cle = canoniques.get(getattr(produit, "cip", ""), cle_lue)
    if cle != cle_lue:
        JOURNAL.info("Produit « %s » rattaché par CIP à %s.",
                     produit.denomination_brute, cle)
    return cle


def _accumuler_contributions(textes: list[TexteAnalyse], date_jo: date, referentiel
                             ) -> tuple[dict[tuple[str, str], _Cumul],
                                        list[tuple[str, str]]]:
    """Reporte chaque produit de chaque texte sur le cumul de sa clé (racine, laboratoire).

    Retourne les cumuls et `ordre_cles`, l'ordre de PREMIÈRE APPARITION des clés dans les
    textes : c'est lui qui fixe l'ordre des lignes du résultat (l'export Excel et la
    recette `compare_cible` en dépendent).
    """
    cumuls: dict[tuple[str, str], _Cumul] = {}
    ordre_cles: list[tuple[str, str]] = []
    canoniques = _cles_canoniques_par_cip(textes)
    for texte in textes:
        for produit in texte.produits:
            cle = _cle_consolidee(produit, canoniques)
            if cle not in cumuls:
                cumuls[cle] = _Cumul()
                ordre_cles.append(cle)
            cumul = cumuls[cle]
            if cle[0] == PRODUIT_INCONNU:
                cumul.signaler(f"dénomination non normalisable "
                               f"« {produit.denomination_brute} » ({texte.id})")
            _accumuler(cumul, texte, produit)
            if referentiel is not None and texte.type_texte in TYPES_AVIS_PRIX:
                _comparer_au_referentiel(cumul.prix, texte, produit, referentiel, date_jo)
    return cumuls, ordre_cles


def _racines_dans_l_ordre(ordre_cles: list[tuple[str, str]]) -> list[str]:
    """Racines dédoublonnées, dans leur ordre de première apparition dans les textes
    (`dict.fromkeys` préserve l'ordre d'insertion) : l'ordre des lignes en découle."""
    return list(dict.fromkeys(racine for racine, _laboratoire in ordre_cles))


def _candidats_de_la_racine(racine: str, ordre_cles: list[tuple[str, str]],
                            cumuls: dict[tuple[str, str], _Cumul]
                            ) -> list[tuple[str, _Cumul]]:
    """Lignes candidates d'une racine : (laboratoire, cumul) dans l'ordre des clés.

    Les contributions sans laboratoire (clé (racine, "")) sont fondues dans chaque ligne
    de la racine ; une racine sans aucun laboratoire nommé garde sa ligne unique
    (laboratoire vide → « N/A » au rendu).
    """
    laboratoires = [labo for r, labo in ordre_cles if r == racine and labo]
    commun = cumuls.get((racine, ""))
    if not laboratoires:
        return [("", commun)] if commun is not None else []
    candidats: list[tuple[str, _Cumul]] = []
    for laboratoire in laboratoires:
        cumul = cumuls[(racine, laboratoire)]
        if commun is not None:
            cumul.fusionner_contributions_communes(commun)
        candidats.append((laboratoire, cumul))
    return candidats


def _anomalie_sans_section(racine: str, candidats: list[tuple[str, _Cumul]]) -> str:
    """Message de la racine vue uniquement dans des textes non porteurs (décision de
    taux, « autre ») : rien n'est inventé, rien n'est tu — anomalie explicite."""
    sources = [s for _labo, cumul in candidats for s in cumul.tracabilite.sources]
    lien = sources[0][0] if sources else "?"
    JOURNAL.warning("Produit %s sans section applicable (sources : %s).",
                    racine, sources)
    return (f"{racine} : vu uniquement dans "
            f"{', '.join(r for _, r in sources)} — aucune section "
            f"applicable, à vérifier manuellement ({lien}).")


def _indication_de_la_ligne(cumul: _Cumul, section: str) -> str:
    """Indication : recopie exacte des sections de tableaux (uniques, dans l'ordre) ;
    jamais de vide silencieux sur une inscription/extension."""
    indication = "\n".join(cumul.tracabilite.indications)
    if not indication and section in (SECTION_INSCRIPTIONS, SECTION_EXTENSIONS):
        return "à compléter manuellement"
    return indication


def _construire_ligne(racine: str, laboratoire: str, cumul: _Cumul,
                      date_jo: date) -> LigneConsolidee:
    """Ligne de veille d'un cumul porteur : section, motifs et indication de repli.

    L'ordre des deux signalements compte — il fixe l'ordre des motifs dans le
    récapitulatif du mail : le motif de section d'abord, « inscrit et radié » ensuite.
    """
    section, motif = _section_du_cumul(cumul)
    if motif:
        cumul.signaler(motif)
    if cumul.inscription.vise and cumul.radiation.vise:
        cumul.signaler("inscrit et radié le même jour (ligne classée en "
                       "inscriptions, radiation à vérifier)")
    if cumul.taux.sans_valeur and cumul.taux.valeur == "N/A":
        cumul.signaler("décision de taux trouvée mais valeur non extraite "
                       "(taux laissé N/A)")
    return LigneConsolidee(
        produit=racine,
        date_jo=date_jo,
        laboratoire=laboratoire,
        indication=_indication_de_la_ligne(cumul, section),
        listes=_listes_ordonnees(cumul.inscription.listes),
        listes_radiation=_listes_ordonnees(cumul.radiation.listes),
        lien_prix=cumul.prix.lien,
        taux=cumul.taux.valeur,
        lien_taux=cumul.taux.lien,
        lien_modification=cumul.modification.lien,
        laboratoire_precedent=cumul.modification.laboratoire_precedent,
        lien_extension=cumul.extension.lien,
        section=section,
        a_verifier=cumul.a_verifier,
        motifs_verification=list(cumul.tracabilite.motifs),
        sources=list(cumul.tracabilite.sources),
        racine=racine,
    )


def _recapituler_anomalies(lignes: list[LigneConsolidee]) -> list[str]:
    """Entrées « à vérifier » du récapitulatif du mail, dans l'ordre des lignes : une
    entrée par racine (pas par laboratoire — un avis douteux à 6 laboratoires ne doit pas
    produire 6 entrées identiques dans le mail)."""
    entrees: list[str] = []
    racines_signalees: set[str] = set()
    for ligne in lignes:
        if ligne.a_verifier and ligne.racine not in racines_signalees:
            racines_signalees.add(ligne.racine)
            entrees.append(f"{ligne.racine} : à vérifier — "
                           + " ; ".join(ligne.motifs_verification))
    return entrees


def _journaliser_synthese(lignes: list[LigneConsolidee], anomalies: list[str]) -> None:
    """Les deux logs de fin de consolidation : le détail des rapprochements, ligne par
    ligne avec ses sources, puis le compte par section."""
    for ligne in lignes:
        JOURNAL.info("Rapprochement : %s / %s ← %s", ligne.produit,
                     ligne.laboratoire or "labo inconnu",
                     ", ".join(f"{i} ({r})" for i, r in ligne.sources))
    compte = {cle: sum(1 for l in lignes if l.section == cle)
              for cle, _titre, _couleur in SECTIONS}
    JOURNAL.info("Consolidation : %d ligne(s) (%d inscriptions, %d hausses, %d baisses, "
                 "%d modifications de libellé, %d extensions, %d radiations), "
                 "%d anomalie(s).",
                 len(lignes), compte[SECTION_INSCRIPTIONS], compte[SECTION_HAUSSES],
                 compte[SECTION_BAISSES], compte[SECTION_MODIFICATIONS],
                 compte[SECTION_EXTENSIONS], compte[SECTION_RADIATIONS], len(anomalies))


def consolider(textes: list[TexteAnalyse], date_jo: date,
               referentiel=None) -> ResultatVeille:
    """Consolide les textes analysés : une ligne par (nom de médicament, laboratoire).

    Contrat du 23/07/2026 : les présentations (dosages, conditionnements) d'un même nom
    sont fondues dans une seule ligne ; un même médicament commercialisé par plusieurs
    laboratoires garde une ligne par laboratoire (cas des génériques). Les textes qui ne
    nomment pas le laboratoire contribuent à toutes les lignes de la racine ; ceux qui
    abrègent les dénominations (avis de prix) sont rattachés par leur code CIP à la
    ligne de l'arrêté correspondant. Indication absente sur une inscription/extension
    → « à compléter manuellement ».

    `referentiel` (optionnel, `referentiel_prix.ReferentielPrix`) : oriente les avis
    de prix « neutres » par comparaison du PPTTC publié au prix antérieur connu, et
    archive les prix du jour. Sans lui, ces avis restent « à vérifier » (comportement
    historique).
    """
    cumuls, ordre_cles = _accumuler_contributions(textes, date_jo, referentiel)
    lignes: list[LigneConsolidee] = []
    anomalies: list[str] = []
    # Assemblage par racine, dans l'ordre de première apparition dans les textes.
    for racine in _racines_dans_l_ordre(ordre_cles):
        candidats = _candidats_de_la_racine(racine, ordre_cles, cumuls)
        porteurs = [(labo, cumul) for labo, cumul in candidats if cumul.porteur]
        if not porteurs:
            anomalies.append(_anomalie_sans_section(racine, candidats))
            continue
        lignes += [_construire_ligne(racine, laboratoire, cumul, date_jo)
                   for laboratoire, cumul in porteurs]
    # Les anomalies de racine sans section précèdent le récapitulatif « à vérifier ».
    anomalies += _recapituler_anomalies(lignes)
    _journaliser_synthese(lignes, anomalies)
    return ResultatVeille(date_jo=date_jo, lignes=lignes, anomalies=anomalies)
