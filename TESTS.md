# Cas métier de non-régression — veille JO CEPS

Liste des comportements à vérifier avant de valider une évolution. Deux moyens :
la suite automatisée (ci-dessous) qui couvre chaque cas marqué 🤖, et le rejeu de dates
réelles (`date.txt` ou `--date`, cas marqués 📅 avec leur date de référence). L'attendu
détaillé des dates réelles est dans [result.md](result.md) — dont la question n° 6 (DCI
ou nom commercial) a depuis été tranchée, voir « Spécialité, jamais la molécule »
ci-dessous.

## Lancer les tests

Depuis la racine du projet, hors ligne (aucune clé, aucun réseau) :

```bash
python -m unittest discover -s tests -t tests
```

154 tests, ~0,3 s. Le `-t tests` est nécessaire (`tests/` n'est pas un paquet). Pour ne
lancer qu'un module, une classe ou un test précis :

```bash
python -m unittest tests.test_rapprochement.TestConsolider.test_generique_multi_labos -t tests
```

Recette sur pièces (rejoue le cas du 28/05/2026 depuis une fixture et compare au
fichier cible historique) :

```bash
python tests/generer_depuis_fixture.py
python tests/compare_cible.py sorties/veille_jo_2026-05-28.xlsx tests/fixtures/veille_jo_2026-05-28_CIBLE.xlsx
```

Les cas marqués ⚠ sont des **défauts connus et non corrigés** : ils n'ont pas de test
(un test vert les figerait) et attendent un arbitrage ou un correctif.

## Sélection et classification des textes

- [ ] 🤖 Un texte au titre pharmaceutique est retenu, un texte hors sujet est écarté
  (nominations, péages, tabac… et l'arrêté d'indemnités enseignants du 07/07).
- [ ] 🤖 Chaque famille de titre reçoit le bon type : inscription (SS, Collectivité,
  LES MCO, LES SMR, Rétrocession), radiation, avis de prix, majoration, baisse,
  décision de taux UNCAM, extension d'indication.
- [ ] 🤖 Un arrêté au titre d'inscription dont le corps radie (« sont radiées ») est
  reclassé radiation ; idem modification de libellé (« libellé … remplacé ») et
  extension d'indication (« ANNEXE (1 extension d'indication) »).
- [ ] 🤖 Un arrêté d'inscription/radiation sans liste identifiable dans le titre sort
  « à vérifier » — jamais classé en silence.
- [ ] 🤖 Aucune fausse ligne produit issue de la structure des tableaux : sous-en-tête
  (« Code CIP », « Présentation »…), ligne purement tarifaire (chiffres, €, %) et
  cellule de code CIP/UCD ne sont jamais pris pour une dénomination.
- [ ] 🤖 Tableau sans en-tête reconnu : la dénomination est lue dans la première
  colonne qui n'est ni un code ni un montant — aucune ligne perdue en silence.
- [ ] ⚠ **Défaut connu (29/07/2026)** : ce repli balaie AUSSI la colonne Laboratoire.
  Un tableau `Code CIP | Laboratoire exploitant` sort une ligne fantôme
  « ARROW GENERIQUES / ARROW », sans « (à vérifier) » et sans log. Correctif : exclure
  du repli la colonne déjà identifiée comme Laboratoire, et journaliser une rangée qui
  porte un code sans dénomination exploitable.
- [ ] 🤖 **Spécialité, jamais la molécule** : les arrêtés de liste en sus (L. 162-22-7
  et L. 162-23-6) ouvrent leur tableau par la DCI, la spécialité ne vient qu'en 2e
  colonne (« ENCORAFENIB | BRAFTOVI 75 mg gélules | Code UCD | … »). C'est BRAFTOVI qui
  sort. Sinon le produit est nommé comme l'utilisatrice ne l'écrit jamais, et il est
  DÉDOUBLÉ dès qu'un autre texte du jour le nomme par sa marque : VORICONAZOLE au lieu
  de VFEND (22/05), TEMOCILLINE/NEGABAN (04/06), INFLIXIMAB/REMSIMA (02/07).
  📅 23/07/2026.
- [ ] 🤖 **Bandeau de titre pleine largeur** (une seule cellule à colspan, ex. « Ancien
  laboratoire exploitant... ») avant la vraie rangée d'en-têtes : jamais pris pour elle.
  Défaut réparé le 04/08/2026 sur le JO du 30/07/2026 (transfert MEROPENEM BRADEX,
  liste en sus L. 162-23-6, AGUETTANT → DEMOGEN) : sans ce filtre, le bandeau ET la
  vraie rangée d'en-têtes sortaient en lignes fantômes (« ANCIEN LABORATOIRE
  EXPLOITANT... », « DÉNOMINATION COMMUNE INTERNATIONALE »), et le CIP/UCD n'était
  jamais lu — la vraie ligne MEROPENEM BRADEX restait invisible. Corollaire découvert
  au même correctif : le pont CIP (`_cles_canoniques_par_cip`) ne canonicalise plus que
  la RACINE, jamais le laboratoire — sinon, une fois le CIP correctement lu, ce même
  transfert réattribuait tout le produit à l'ANCIEN laboratoire (le nouveau
  disparaissait sans anomalie).
- [ ] 🤖 **Arrêtés de libellé à deux blocs** (état abrogé à gauche, nouveau à droite,
  deux rangées d'en-tête) : la présentation décrite est celle de DROITE (nom, CIP), le
  bloc de gauche ne livre que l'exploitant cédant, et aucune rangée d'en-tête ne sort en
  ligne produit. Un tableau à un seul bloc n'est jamais découpé ; des largeurs de blocs
  qui ne recouvrent pas la rangée de sous-en-têtes → lecture ordinaire, jamais de découpe
  au hasard (elle mélangerait les deux états sur une même ligne de veille).
  📅 23/07/2026 (CEFEPIME NORIDEM, GEMZAR).
- [ ] 🤖 Le filtre des rappels d'en-tête ne peut **jamais** écarter une ligne produit :
  le gabarit ne retient que les cellules SANS chiffre (un libellé d'en-tête n'en a pas,
  une dénomination presque toujours), et une rangée n'est écartée que si DEUX de ses
  cellules reproduisent un libellé, ou si toutes ses cellules non vides le font (rappel
  partiel). Contre-épreuve : un tableau sans en-tête dont la 1re rangée contient un mot
  d'en-tête (« nom » dans « NOMEGESTROL ACETATE VIATRIS 3,75 mg ») ne filtre pas les
  rangées qui répètent cette dénomination — un médicament sortait de la newsletter sans
  anomalie, sans « (à vérifier) » et sans log (29/07/2026).

## Consolidation (une ligne par médicament)

- [ ] 🤖 Les dosages/conditionnements d'un même nom fondent en UNE ligne
  (les 5 LACOSAMIDE → « LACOSAMIDE »). 📅 22/07/2026.
- [ ] 🤖 Les unités de radioactivité (Bq/Ci et préfixes SI — GBq, MBq, kBq, mCi…)
  comptent comme un dosage comme un autre (GALLIAPHARM, 8 présentations de 1,11 à
  3,70 GBq → « GALLIAPHARM »). 📅 30/07/2026.
  - [ ] ⚠ **Défaut connu (30/07/2026)** : une des 8 dénominations réelles de
    GALLIAPHARM est malformée à la source (« GALLIAPHARM 1,11 GBQ / CHLORURE DE
    GALLIUM ) » — parenthèse orpheline, « / » à la place d'une parenthèse ouvrante) et
    ne fond pas avec les 7 autres. Assumé : une heuristique de coupe sur « / »
    casserait AZELASTINE CHLORHYDRATE/FLUTICASONE PROPIONATE, où le « / » fait partie
    du nom.
- [ ] 🤖 Un générique multi-laboratoires garde une ligne PAR laboratoire
  (DARUNAVIR Viatris + Zentiva = 2 lignes ; AZELASTINE = 6 lignes). 📅 07/07/2026.
- [ ] 🤖 Le nom racine résiste aux pièges : parenthèses (même non fermées), dosages
  (chiffres ou toutes lettres), formes galéniques et abréviations d'avis (CPR, GELU,
  INJ…), sels/esters, laboratoire accolé au nom (mapping annexe D).
- [ ] 🤖 Un nom qui **finit par un chiffre** garde ce chiffre, qu'il soit collé
  (« CACIT VITAMINE D3 500 mg/440 UI » → « CACIT VITAMINE D3 » ; « VITAMINE B12
  1000 µg/2 ml » → « VITAMINE B12 ») ou détaché (« GARDASIL 9 0,5 ml » →
  « GARDASIL 9 » ; « OMEGA 3 1000 mg » → « OMEGA 3 »). Sinon deux spécialités
  distinctes (VITAMINE D2 / D3) fusionnent sur une ligne fausse.
  **Limite connue et assumée (29/07/2026)** : chiffre détaché suivi d'un dosage à
  exactement 3 chiffres (« OMEGA 3 500 mg », « PNEUMOVAX 23 500 000 UI ») →
  le chiffre est lu comme un séparateur de milliers et perdu. Les deux lectures sont
  typographiquement valides, aucune regex ne les sépare ; arbitré en faveur du dosage,
  plus fréquent. Le lever exigerait un référentiel externe (valences vaccinales).
  Contre-épreuves à ne jamais casser : « ORACILLINE 1 000 000 UI » → « ORACILLINE »
  et « HEPARINE CALCIQUE 12 500 UI/0,5 ml » → « HEPARINE CALCIQUE ».
- [ ] 🤖 **Dosage COLLÉ à une lettre** (les avis de prix abrègent ainsi) : il est bien
  retiré — « POMALIDOMIDE LPN1MG GELU » → « POMALIDOMIDE LPN », « REMSIMA 40MG/ML PERF
  FL2,5ML » → « REMSIMA », « ERIBULINE HIK 0,44MG/ML FL2ML » → « ERIBULINE HIK »,
  « PELMEG 6MG INJ SRG0,6ML » → « PELMEG ». Le pont CIP/UCD masque le défaut quand un
  arrêté du jour porte le nom complet : c'est l'avis SANS arrêté (REMSIMA au 02/07) qui
  le révèle, en sortant le conditionnement dans la colonne Produit. Dénominations
  relevées au rejeu réel des JO des 09/06, 02/07 et 23/07/2026. 📅
- [ ] 🤖 Un texte qui ne nomme pas le laboratoire alimente toutes les lignes de la
  racine (propagation).
- [ ] 🤖 **Pont CIP/UCD** : un avis aux dénominations abrégées (« MEROPENEM PAN 1G »)
  est rattaché à la ligne de l'arrêté portant le même code ; à codes égaux entre
  arrêtés, la racine courte fait foi (POMALIDOMIDE). Sans code commun : jamais de
  rapprochement deviné. 📅 04/06, 02/07/2026.
- [ ] 🤖 Le pont est insensible à l'**ordre du sommaire** : un avis listé AVANT l'arrêté
  du même produit donne le même résultat (l'élection de la clé est une pré-passe).
- [ ] ⚠ **Défaut connu (30/07/2026)** : un même arrêté de radiation peut publier SES
  DEUX tableaux (liste collectivités en CIP-13, liste L. 162-17 en codes UCD) avec des
  codes de préfixe différents (34009 vs 34008) pour les MÊMES spécialités — le pont
  CIP/UCD ne peut pas les relier (identifiants distincts, jamais un doublon de codage).
  EPIRUBICINE INTSEL CHIMOS et EPOPROSTENOL INTSEL CHIMOS sortent chacun en 2 lignes de
  radiation (dénomination complète et libellé UCD abrégé « EPIRUBICINE INT »). Aucun
  médicament perdu (les deux lignes disent bien « radié »), juste dédoublé. Fusion
  automatique jugée trop risquée (nécessiterait une clé de mapping labo à 3 lettres —
  « INT » → INTSEL CHIMOS SAS — qui matcherait en faux positif d'autres dénominations).
- [ ] 🤖 Les lignes sortent dans l'**ordre d'apparition** dans les textes du JO, et les
  anomalies de racine sans section précèdent le récapitulatif « à vérifier ».
- [ ] 🤖 Un dosage à séparateur de milliers ne scinde pas la racine
  (« ORACILLINE 1 000 000 UI » → une seule ligne « ORACILLINE », jamais
  « ORACILLINE 1 » + « ORACILLINE »). 📅 22/07/2026.
- [ ] 🤖 Dénomination non normalisable (racine vide après nettoyage) → « PRODUIT
  INCONNU » + ligne « à vérifier » avec la dénomination brute en motif — jamais
  de ligne muette ni de produit inventé.
- [ ] 🤖 Le laboratoire passe par le mapping unique (LAVOISIER et CHAIX ET DU MARAIS
  → même ligne MORPHINE ; TEVA → TEVA SANTE).
- [ ] 🤖 **Invariant de mapping** : le résultat ne dépend pas de l'ordre d'écriture de
  `MAPPING_LABOS` — la clé la plus longue gagne toujours (« ROSUVASTATINE VIATRIS
  SANTE » → « ROSUVASTATINE », que « VIATRIS » soit déclaré avant ou après
  « VIATRIS SANTE »). Le mapping est trié par ordre alphabétique dans le test :
  la suite doit rester verte. Idem en **conflit de suffixe** (« PHARMA » déclaré
  avant « G.L. PHARMA ») : « LACOSAMIDE G.L. PHARMA 100 mg » → « LACOSAMIDE »,
  jamais « LACOSAMIDE G.L ».

## Sections et listes

- [ ] 🤖 Six sections servies : Nouvelles inscriptions, Hausse de prix, Baisse de
  prix, Modification de libellé, Extensions d'indications, Radiations.
- [ ] 🤖 La colonne Liste porte les 5 listes dans l'ordre SS, Collectivité, LES MCO,
  LES SMR, Rétrocession — un lien cliquable PAR segment (« 1 liste = 1 arrêté »),
  format « SS & Collectivité ». 📅 09/06 (Collectivité & LES MCO), 02/07 (3 listes).
- [ ] 🤖 Radiation d'une ou plusieurs listes → section Radiations avec la ou les
  listes radiées. 📅 22/05 (VFEND/LES MCO), 02/07 (ZOLADEX/SS & Collectivité).
- [ ] 🤖 **Règle SIRTURO** : inscription + extension d'indication + avis de prix le
  même jour → la ligne ne sort QUE dans Extensions d'indications, avec le rappel
  « Inscription : … — modification de prix : … ». 📅 23/07/2026.
- [ ] 🤖 Une extension seule reste une extension ordinaire (pas de rappel) ; une
  inscription + extension sans prix reste en Inscriptions.
- [ ] 🤖 Produit inscrit ET radié le même jour → « à vérifier », jamais silencieux.

## Prix (contrat du 23/07/2026 : aucun prix affiché)

- [ ] 🤖 **Aucun montant nulle part** : les cellules Prix et Lien sont un lien texte
  « Site LégiFrance » seul. Le PPTTC est bien extrait, mais il ne sert qu'à l'orientation
  par référentiel — jamais affiché. Le **taux**, lui, reste chiffré (voir la section
  suivante) : le contrat « aucun montant » porte sur le prix, pas sur le taux.
- [ ] 🤖 Avis explicites : « majoration » → Hausse, « baisses de prix » → Baisse ;
  un avis mentionnant les deux reste non orienté (piège MORPHINE : jamais de
  routage par défaut) et sort « Hausse de prix (à vérifier) » avec un motif qui dit
  pourquoi, **avec et sans référentiel**.
- [ ] 🤖 Le doute d'un avis à deux sens porte sur le PRIX, pas sur la classification :
  une ligne dont la section vient d'une inscription ou de la règle SIRTURO n'est pas
  « à vérifier » pour autant (le prix n'y décide de rien), et la ligne réellement
  concernée n'a qu'UN motif, le spécifique (29/07/2026).
- [ ] 🤖 **Avis neutres (« les prix sont fixés… »)** : orientés par comparaison du
  PPTTC au prix antérieur connu (historique JO puis BDPM). Prix inconnu, égal ou
  sens contradictoires entre présentations → « Hausse de prix (à vérifier) »,
  jamais deviné. Référentiel indisponible (réseau, fichier) → idem, sans faire
  échouer le run. 📅 07/07 (10/12 orientés), 04/06 (XIOP).
- [ ] 🤖 L'historique local archive les prix publiés (idempotent au rejeu : un JO
  rejoué ne se compare jamais à lui-même).
- [ ] 🤖 Un avis déjà orienté par son texte n'est jamais re-basculé par le
  référentiel.
- [ ] 🤖 Plusieurs avis de prix pour un même produit → « à vérifier », premier lien
  conservé. 📅 04/06 (AXITINIB, prix + TFR).
- [ ] 🤖 **Bascule `ORIENTATION_PRIX_AUTO = False`** : retour au comportement
  100 % « à vérifier » sur les avis neutres, sans autre changement de rendu
  (repli demandé si le CEPS refuse la comparaison BDPM — question n° 1).
- [ ] 🤖 Les montants publiés sont lus sans erreur d'échelle : « 1 156,38 € »
  (séparateur de milliers) vaut bien 1156,38 et non 1 — un faux sens de variation
  serait pire qu'une absence de sens.
- [ ] ⚠ **Défaut connu (29/07/2026)** : un produit visé le même jour par un avis de prix
  ET par une radiation ou une modification de libellé sort dans la section de cette
  dernière, dont les colonnes n'affichent pas `lien_prix` — la variation de prix
  disparaît de la newsletter, sans anomalie. Seul le triplet inscription + extension +
  prix (règle SIRTURO) a prévu le rappel. À arbitrer avec l'utilisatrice : généraliser
  les rappels aux sections Radiations et Modifications, ou signaler une anomalie.
  Combinaison plausible (10 modifications de libellé au JO du 23/07).

## Taux de participation (colonne Taux, chiffrée)

- [ ] 🤖 Le taux est **affiché chiffré** : « 35% » cliquable vers la décision UNCAM dans
  le mail, nombre `0.35` au format `0%` dans l'Excel (le fichier CIBLE du 28/05/2026 fait
  foi sur le format), et la conversion est partagée par les deux rendus. Les colonnes
  Prix et Taux terminent le tableau des inscriptions, dans cet ordre (rétabli le
  29/07/2026 : elles manquaient).
- [ ] 🤖 Chaque présentation porte SON taux, lu dans la colonne « Taux de
  participation » : deux taux distincts dans le même tableau restent distincts, et le
  rattachement à la ligne d'inscription se fait par le code CIP.
- [ ] 🤖 Décision qui énonce son taux une seule fois (phrase d'attaque) : le repli le
  rattache à chaque présentation. Plusieurs pourcentages énoncés, ou aucun → « N/A »,
  jamais de choix arbitraire (piège « taux 1 » de VGENFLI).
- [ ] 🤖 Taux divergents entre présentations d'un même produit → ligne « à vérifier »
  avec le motif qui les cite (« 35% vs 65% ») ; décision de taux sans taux lisible →
  anomalie explicite. Jamais de taux déduit.

## Indications

- [ ] 🤖 L'indication est la recopie EXACTE de la section qui précède le tableau ;
  indication absente sur une inscription/extension → « à compléter manuellement »,
  jamais de vide silencieux.
- [ ] 🤖 Indications multiples d'un même nom : toutes conservées, dans l'ordre, sans
  doublon (cas FULBEV). Indication commune à plusieurs arrêtés : reprise une fois.
- [ ] 🤖 Une indication longue est recopiée telle quelle (jamais tronquée ni
  remplacée).
- [ ] 🤖 Le HTML en ligne du JO ne découpe pas l'indication : exposants
  (« kg/m² »), marques (« MOUNJARO® ») et liens d'articles restent dans leur
  phrase, jamais isolés sur une ligne. 📅 28/05 (WEGOVY, MOUNJARO).

## Rendus (mail et Excel)

- [ ] 🤖 Mail : titres et ordre des 6 sections (« Nouvelles inscriptions » au
  pluriel), colonnes par section (Produit et Laboratoire côte à côte ; les inscriptions
  finissent par Prix puis Taux), bandeaux colorés, pas de colonne Date, sections vides
  omises.
- [ ] 🤖 Excel : mêmes sections + colonne Date, départ en B2, une seule cellule
  = un seul lien (Liste : premier arrêté), suffixe « (à vérifier) » sur le produit
  des lignes douteuses.
- [ ] 🤖 L'export du 28/05/2026 (fixture) reste conforme au fichier CIBLE historique
  (produits, laboratoires, listes, dates, liens — recette `compare_cible`).
- [ ] 🤖 Récapitulatif des anomalies après « Cordialement » : une entrée par racine
  à vérifier + textes non téléchargés/vides avec leur lien.
- [ ] ⚠ **Défaut connu (29/07/2026)** : cette entrée unique ne reprend que les motifs de
  la PREMIÈRE ligne de la racine. Sur un générique multi-laboratoires, un motif propre à
  une autre ligne (« plusieurs avis de prix pour ce produit ») n'atteint jamais la
  relectrice : elle voit un drapeau « (à vérifier) » sans sa raison. Correctif : réunir
  les motifs de toutes les lignes de la racine, dédoublonnés, dans l'ordre d'apparition.
- [ ] 🤖 Les anomalies d'extraction (texte non téléchargé, contenu vide) arrivent
  EN TÊTE du récapitulatif : ce sont les seules qu'aucune ligne du tableau ne
  laisse deviner.
- [ ] 🤖 Objet du mail « [VEILLE] - Publication JO du JJ/MM/AAAA » et destinataires
  pris dans `config.DESTINATAIRES` — jamais d'adresse codée ailleurs.
- [ ] 🤖 Le fichier `sorties/corps_mail_<date>.html` est écrit à CHAQUE run, y
  compris quand le brouillon Outlook réussit (mode dégradé permanent : il reste
  toujours une trace copiable-collable).

## Garde-fous d'exploitation

- [ ] 🤖 Jour sans texte pharma : le mail « RAS » part quand même (pas de mail =
  panne, jamais « rien à signaler »).
- [ ] 🤖 Décision de taux/texte « autre » seuls sur un produit : aucune ligne, mais
  une anomalie explicite.
- [ ] 🤖 **Rien ne part jamais tout seul** : aucun `.Send()` tant que
  `ENVOI_AUTOMATIQUE` vaut False (brouillon affiché, envoi humain) ; le mail
  d'alerte est lui aussi seulement affiché, jamais envoyé.
- [ ] 🤖 `date.txt` : date valide JJ-MM-AAAA prise en compte, contenu vidé (jamais
  supprimé) après CHAQUE lancement, contenu invalide → date du jour avec log.
- [ ] 🤖 `--date` prime sur `date.txt`, et `date.txt` est vidé quand même (une date
  posée ne rejoue jamais le lendemain) ; `date.txt` absent → recréé vide.
- [ ] 🤖 Token PISTE expiré en cours de run (401) → renouvelé et l'appel aboutit ;
  panne réseau → 3 tentatives avant l'échec définitif (jamais d'abandon au
  premier hoquet).
- [ ] 🤖 Un texte présent deux fois dans le sommaire du JO n'est traité (et facturé
  en appel API) qu'une seule fois.
- [ ] 🤖 Excel cible ouvert dans Excel → export sous nom suffixé de l'heure.
- [ ] 🤖 Échec Outlook → repli HTML dans `sorties/` ; échec JO/PISTE → alerte
  explicite + code retour 1.
- [ ] 📅 Fenêtre de rejeu : une date à ~2-3 mois reste trouvable
  (`NB_ELEMENT_LASTNJO = 90`). 📅 22/05/2026 depuis fin juillet.

## Rejeu complet de référence

- [ ] 📅 **JO du 23/07/2026** : le résultat doit correspondre au mail manuel de
  Sabine (11 inscriptions, 10 modifications de libellé, SIRTURO en Extensions
  uniquement, zéro anomalie) — c'est le test de non-régression global.
