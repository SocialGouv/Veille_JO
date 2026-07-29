"""Configuration de la veille JO « spécialités pharmaceutiques » (CEPS).

Toutes les constantes du pipeline sont ici : bascules A/B (§3 du plan),
endpoints PISTE, mots-clés de filtrage, mail, mise en forme.
Les secrets ne sont JAMAIS ici : ils vivent dans `.env` (voir `.env.example`).
"""

# --- Bascules A/B (voir §3 du plan) ---
MAIL_MODE = "brouillon_outlook"        # R2 : "brouillon_outlook" | "html"
ENVOI_AUTOMATIQUE = False              # R3 : True seulement après période de confiance
POLICE = "Marianne"                    # R6 : "Arial" si Marianne absente
# Orientation automatique des avis de prix « neutres » (« les prix sont fixés… »,
# sans mot de hausse/baisse ni prix antérieur — constat vérifié sur pièces le
# 29/07/2026) : comparaison déterministe du PPTTC publié au prix antérieur connu
# (référentiel BDPM public + historique local, voir referentiel_prix.py). Prix
# antérieur introuvable ou égal → l'avis reste « à vérifier », jamais deviné.
# Choix soumis à la validation CEPS (question n° 1 de questions.md) : False pour
# revenir au comportement 100 % « à vérifier ».
ORIENTATION_PRIX_AUTO = True

# --- PISTE / Légifrance ---
URL_TOKEN     = "https://oauth.piste.gouv.fr/api/oauth/token"
URL_LAST_JO   = "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app/consult/lastNJo"
URL_JORF_CONT = "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app/consult/jorfCont"
URL_JORF_TEXT = "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app/consult/jorf"
NB_ELEMENT_LASTNJO = 90                # profondeur de rejeu (~3 mois) ; augmenter pour rejouer plus ancien
                                       # (90 depuis le 29/07/2026 : couvre les JO de test
                                       # fournis par le CEPS, dont le 22/05/2026)
TIMEOUT_PISTE_S = 30                   # timeout de chaque appel PISTE
TENTATIVES_PISTE = 3                   # tentatives par appel PISTE (backoff 2 s)
URL_PUBLIQUE_TEXTE = "https://www.legifrance.gouv.fr/jorf/id/{id}"

# --- Filtrage (mots-clés éprouvés sur les scripts existants, insensibles à la casse) ---
# « majoration » retiré le 29/07/2026 (run de test du JO du 07/07) : il attrapait un
# arrêté d'indemnités de personnels enseignants dont les tableaux (tranches
# kilométriques) sortaient en fausses lignes de hausse. Redondant : les avis de
# majoration pharma contiennent toujours « spécialités pharmaceutiques ».
MOTS_CLES = ["pharmaceutique", "spécialité", "médicament", "prix de spécialité",
             "avis de tarification", "baisse de prix", "participation de l'assuré"]

# --- Classification des textes par titre (E3, regex insensibles à la casse) ---
# Calibration E2/E3 CONFIRMÉE sur run réel du JO du 28/05/2026 (le 21/07/2026) :
# les 21 textes retenus ont tous reçu le bon type. Familles de titres réelles constatées :
#   « Arrêté du <date> modifiant la liste des spécialités pharmaceutiques remboursables
#     aux assurés sociaux »                                → arrete_inscription (liste SS)
#   « Arrêté du <date> modifiant la liste des spécialités pharmaceutiques agréées à
#     l'usage des collectivités et divers services publics » → arrete_inscription (Collectivité)
#   « Avis relatif aux prix de spécialités pharmaceutiques »  → avis_prix
#   « Avis relatif aux décisions/à la décision de l'Union nationale des caisses d'assurance
#     maladie portant fixation du taux de participation de l'assuré applicable à des
#     spécialités pharmaceutiques »                        → decision_taux
# Révision du 23/07/2026 (mots-clefs fournis par l'utilisatrice, mail des 22-23/07) :
# un seul type « arrete_inscription », la liste visée (parmi les 5 de MOTIFS_LISTES)
# étant détectée séparément dans le titre ; nouveaux types « arrete_radiation » et
# « modification_libelle » (ce dernier est confirmé par le corps du texte, voir
# analyse.orienter_arrete — les arrêtés de libellé partagent les titres d'inscription).
# Vigilance MOTS_CLES (constat du 31/05/2026, jour à JO sans texte pharma pertinent) :
# « spécialité » attrape aussi des textes de biologie médicale (ex. nomenclature
# « PARASITOLOGIE ET MYCOLOGIE ») → 59 anomalies de bruit ce jour-là. À recalibrer sur
# plusieurs dates avant la mise en service.
MOTIFS_CLASSIFICATION = [
    # (type_texte, regex sur le titre) — évalués dans l'ordre, premier qui matche.
    # « radiation » avant les inscriptions : un titre de radiation cite aussi la liste.
    ("decision_taux", r"participation\s+de\s+l['']assur"),
    ("arrete_radiation", r"radiation|radiées?\b"),
    ("extension_indication", r"extension\s+d['']indication"),
    ("modification_libelle", r"modifications?\s+(?:du|des)\s+libellés?"),
    ("arrete_inscription", r"remboursables\s+aux\s+assur[ée]s\s+sociaux|collectivit[ée]s"
                           r"|liste\s+en\s+sus|162-22-7|162-23-6|5126-6"),
    ("avis_hausse_prix", r"majoration|major[ée]s?\b"),
    ("avis_baisse_prix", r"baisses?\s+(du|de|des)\s+prix"),
    ("avis_prix", r"\bprix\b|tarification"),
]

# --- Listes d'inscription/radiation (mots-clefs du titre, mail utilisatrice des 22-23/07) ---
# 1 liste = 1 arrêté : la liste visée se lit dans le titre de l'arrêté. L'ordre ci-dessous
# est l'ordre d'affichage dans la colonne Liste (« SS & Collectivité »).
#   Inscription SS           = « assurés sociaux »
#   Inscription Collectivité = « collectivités »
#   Inscription LES MCO      = article L. 162-22-7 du code de la sécurité sociale
#   Inscription LES SMR      = article L. 162-23-6 du code de la sécurité sociale
#   Inscription Rétrocession = article L. 5126-6 du code de la santé publique
MOTIFS_LISTES = [
    # « 162-17 » : les arrêtés de RADIATION désignent la liste SS par son article
    # (« liste mentionnée au premier alinéa de l'article L. 162-17 »), constaté au
    # run de test du 29/07/2026 sur le JO du 02/07 (ZOLADEX).
    ("SS", r"assur[ée]s\s+sociaux|162-17\b"),
    ("Collectivité", r"collectivit[ée]s"),
    ("LES MCO", r"162-22-7"),
    ("LES SMR", r"162-23-6"),
    ("Rétrocession", r"5126-6"),
]

# --- Normalisation « nom racine » (annexe C) ---
# Formes galéniques et packagings supprimés des dénominations (insensible à la casse).
# Liste extensible au fil de l'eau : ajouter ici toute forme rencontrée dans les JO.
# ORDRE IMPORTANT : les séquences longues avant les mots qu'elles contiennent
# (« flacon en verre jaune … » avant « flacon », sinon la longue ne matche plus).
# Calibration E2/E3 du 21/07/2026, run réel JO du 28/05/2026 : les libellés marqués
# [28/05] sont les packagings RÉELS constatés dans les tableaux JORF de ce jour.
FORMES_GALENIQUES = [
    "FlexTouch", "KwikPen", "FlexPen", "Pen",
    "solution injectable", "injectable", "solution buvable", "buvable", "solution",
    "sirop", "comprimés sécables", "comprimé sécable", "comprimés", "comprimé",
    "pelliculés", "pelliculé",                                    # [28/05] FYCOMPA PELLICULÉS
    "gélules", "gélule", "sachet", "spray", "patch", "crème", "gel",
    "lyophilisat", "poudre", "suspension", "en ampoule", "ampoules", "ampoule",
    "en stylo prérempli", "stylos préremplis", "stylo prérempli", "stylo",
    "en seringue préremplie", "seringues préremplies", "seringue préremplie", "seringue",
    "LP",                                                         # [21/07] libération prolongée (MELATONINE ARROW LP)
    "cartouches", "cartouche",                                    # [28/05] WEGOVY, MOUNJARO
    "en flacon", "flacons", "flacon",                             # [28/05] VGENFLI, LIKOZAM
    "sous plaquettes", "sous plaquette",                          # [28/05] OXAZEPAM
    "sans conservateur",                                          # [28/05] MORPHINE
    # [29/07] Abréviations des avis de prix (constatées aux runs de test : SIRTURO CPR,
    # BRAFTOVI GELU, MEROPENEM … INJ FL, PELMEG INJ SRG) — sans elles, l'avis et
    # l'arrêté du même produit donnent deux racines et deux lignes.
    "pour perfusion", "perfusion",
    "INJ", "CPR", "GELU", "SRG", "PERF", "FL",
]

# Sels et esters supprimés des dénominations (annexe C étendue, même prudence : la CIBLE
# fait foi — DABIGATRAN ETEXILATE → DABIGATRAN, MORPHINE SULFATE → MORPHINE [28/05]).
# Vigilance : ne jamais ajouter ici un mot qui peut être la tête d'un nom composé
# (« SULFATE DE MAGNÉSIUM » n'est pas concerné : le motif exige un mot précédent).
SELS_ET_ESTERS = ["etexilate", "sulfate"]

# --- Mapping laboratoires (annexe D, unique, complété au fil de l'eau) ---
# Règle : la clé la plus longue contenue dans le nom brut (majuscules) → valeur ; sinon nom
# brut tel quel. L'ORDRE D'ÉCRITURE DE CE MAPPING N'A AUCUNE IMPORTANCE : `rapprochement`
# trie les clés par longueur décroissante, donc la plus spécifique gagne (« VIATRIS SANTE »
# devant « VIATRIS », « G.L. PHARMA » devant un éventuel « PHARMA »). Ajoutez vos entrées
# où vous voulez, y compris par ordre alphabétique.
#
# La CLÉ sert à regrouper (toutes les écritures d'un même laboratoire tombent sur la même
# ligne de veille) ; la VALEUR est ce que lit la destinataire. Sur la valeur, deux sources
# font foi, chacune pour SES laboratoires — jamais une règle générale de troncature :
#   - le mail de l'utilisatrice du 23/07/2026 : nom d'usage court, sans forme juridique
#     (« STRAGEN FRANCE » → STRAGEN, « UPSA SAS » → UPSA, « VIATRIS SANTE » → VIATRIS) ;
#   - le fichier CIBLE du 28/05/2026 : « TEVA SANTE », « EISAI SAS », « LAVOISIER - CHAIX
#     ET DU MARAIS » — écrits longs, conservés tels quels.
# Les deux échantillons se contredisent sur l'usage (TEVA SANTE face à VIATRIS) : question
# ouverte pour l'utilisatrice, à trancher d'un mot. En attendant, chaque laboratoire garde
# l'écriture attestée pour LUI, et aucune n'est extrapolée aux autres.
MAPPING_LABOS = {
    "NOVO NORDISK": "NOVO NORDISK",
    "LILLY": "LILLY",
    "FRESENIUS KABI": "FRESENIUS KABI",
    "TEVA": "TEVA SANTE",
    "ARROW": "ARROW",
    "ADVICENNE": "ADVICENNE",
    "LAVOISIER": "LAVOISIER - CHAIX ET DU MARAIS",
    "CHAIX ET DU MARAIS": "LAVOISIER - CHAIX ET DU MARAIS",
    "AGUETTANT": "AGUETTANT",
    "COOPER": "COOPERATION PHARMACEUTIQUE FRANCAISE",
    "EISAI": "EISAI SAS",
    "BIOGARAN": "BIOGARAN",
    # Complétés aux runs de test du 29/07/2026 (dates fournies par le CEPS) : sans eux,
    # le laboratoire reste accolé au nom (« AXITINIB ACCORD », « ERIBULINE HIKMA »,
    # « SIRTURO CPR »…) et le même médicament sort en plusieurs lignes. Valeurs choisies
    # faute d'échantillon utilisatrice sur ces laboratoires (raison sociale du JO).
    "ACCORD": "ACCORD HEALTHCARE FRANCE SAS",
    "HIKMA": "HIKMA FRANCE",
    "LUPIN": "LUPIN",
    "ZENTIVA": "ZENTIVA FRANCE",
    "ZYDUS": "ZYDUS FRANCE",
    "SUBSTIPHARM": "SUBSTIPHARM",
    "SANDOZ": "SANDOZ",
    "G.L. PHARMA": "G.L. PHARMA",
    "PFIZER": "PFIZER",
    # Écritures ATTESTÉES par le mail de l'utilisatrice du 23/07/2026, tableau par tableau
    # (nouvelles inscriptions, modifications de libellé, extensions) : le JO publie la
    # raison sociale, elle écrit le nom d'usage.
    "VIATRIS SANTE": "VIATRIS",          # « VIATRIS SANTE » au JO (ROSUVASTATINE, XALACOM)
    "VIATRIS": "VIATRIS",
    "STRAGEN": "STRAGEN",                # « STRAGEN FRANCE » au JO (AMIKACINE)
    "HORUS": "HORUS",                    # « HORUS PHARMA » (ATIMIAC)
    "UPSA": "UPSA",                      # « UPSA SAS » (EFFERALGAN)
    "DIFARMED": "DIFARMED",              # « DIFARMED SLU » (DOSTINEX, EMEND, ZITHROMAX)
    "PIERRE FABRE": "PIERRE FABRE",      # « PIERRE FABRE MEDICAMENT » (BRAFTOVI)
    "JANSSEN-CILAG": "JANSSEN-CILAG",    # (SIRTURO)
    "DEMOGEN": "DEMOGEN",                # « DEMOGEN FRANCE SAS » (reprises NORIDEM)
    "CHEPLAPHARM": "CHEPLAPHARM",        # « CHEPLAPHARM FRANCE » (reprise de GEMZAR)
    "LEURQUIN": "LEURQUIN MEDIOLANUM",   # écrit en entier par l'utilisatrice (OZALIN)
    "DB PHARMA": "DB PHARMA",            # idem (PHENERGAN) : « DB » seul ne dirait rien
    # Exploitants du même JO que l'utilisatrice n'a pas écrits (elle ne montre que le
    # repreneur, et a gardé DB PHARMA pour PHENERGAN au lieu de FRILAB) : valeurs alignées
    # par analogie sur les précédentes, à confirmer à leur première parution.
    "ASPEN": "ASPEN",                    # « ASPEN FRANCE », exploitant cédant de NAROPEINE
    "FRILAB": "FRILAB",                  # « LABORATOIRES FRILAB », repreneur de PHENERGAN
    # Laboratoires que les GÉNÉRIQUES portent dans leur nom de spécialité (« MEROPENEM
    # PANPHARMA », « PARACETAMOL TEVA PHARMA ») : sans leur clé, le laboratoire reste
    # accolé à la racine et le même médicament sort sous plusieurs noms. La clé doit
    # reproduire le suffixe ENTIER du nom (« ARROW LAB », pas « ARROW » : `nom_racine` ne
    # retire qu'une clé qui TERMINE le nom). Constatés aux JO des 22/05 et 04/06/2026.
    "PANPHARMA": "PANPHARMA",
    "ARROW LAB": "ARROW",
    "KALCEKS": "KALCEKS",                # fabricant cité au nom, exploité par EVER PHARMA
    "TEVA PHARMA": "TEVA SANTE",
}

# --- Mail ---
DESTINATAIRES = ["ListediffusionSG_CEPS@canauxteams.social.gouv.fr"]
OBJET_MAIL = "[VEILLE] - Publication JO du {date_jjmmaaaa}"

# --- Référentiel de prix (orientation des avis neutres, 29/07/2026) ---
# Base de données publique des médicaments (BDPM, licence ouverte) : fichier plat
# CIP-13 → prix public. Téléchargé au plus une fois par BDPM_MAX_AGE_JOURS dans
# DOSSIER_DONNEES ; en cas d'échec réseau, le dernier fichier téléchargé sert tel
# quel (l'orientation est un bonus : son absence ne fait jamais échouer la veille).
URL_BDPM_CIP = "https://base-donnees-publique.medicaments.gouv.fr/download/file/CIS_CIP_bdpm.txt"
BDPM_MAX_AGE_JOURS = 7
TIMEOUT_BDPM_S = 120

# --- Dossiers de travail (relatifs à la racine du projet) ---
DOSSIER_LOGS = "logs"
DOSSIER_SORTIES = "sorties"
DOSSIER_DONNEES = "donnees"            # cache BDPM + historique local des prix publiés
