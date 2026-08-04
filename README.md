# Veille JO — spécialités pharmaceutiques (CEPS)

Chaque matin, l'outil lit le Journal officiel, repère les textes qui concernent les
spécialités pharmaceutiques (inscriptions, radiations, prix, libellés, indications)
et prépare la newsletter : un tableau Excel dans le dossier `sorties/` et un brouillon
de mail pré-rempli dans Outlook (destinataires, objet, tableaux, Excel joint).

**Rien ne part jamais tout seul** : c'est vous qui relisez et qui cliquez sur Envoyer.

## Lancer la veille (Windows)

**Double-cliquez sur `lancer_veille.bat`** (ou sur son raccourci « Veille JO » du bureau).
Une fenêtre noire travaille une à deux minutes, puis affiche :

- `[OK]` → le brouillon s'ouvre dans Outlook : relisez-le (surtout les mentions
  « (à vérifier) » et « à compléter manuellement » — chaque ligne a son lien
  Légifrance pour trancher), puis envoyez. Jour sans texte pharma : le brouillon
  dit « RAS », envoyez-le aussi (pas de mail = panne, jamais « rien à signaler ») ;
- `[ECHEC]` → le plus souvent, le JO n'est pas encore publié : réessayez dans l'heure.
  Si ça persiste, transmettez le fichier le plus récent du dossier `logs/` au référent.

## Lancer la veille (Mac, poste de développement)

Premier lancement seulement :
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # puis remplir PISTE_CLIENT_ID / PISTE_CLIENT_SECRET (voir INSTALL.md)
```

Ensuite, chaque matin :
```bash
./lancer_veille.sh
```
Pas d'Outlook sur Mac : le brouillon pré-rempli n'est pas disponible, l'outil bascule
automatiquement sur le fichier `sorties/corps_mail_<date>.html`, ouvert dans le
navigateur par défaut — copiez-collez son contenu dans un nouveau mail. L'Excel du
jour est dans `sorties/veille_jo_<date>.xlsx`, le journal dans `logs/`.

## Traiter un autre jour que celui du lancement

Ouvrez **`date.txt`** (à côté de `lancer_veille.bat`), écrivez la date voulue au format
**JJ-MM-AAAA** (exemple : `28-05-2026`), enregistrez, puis lancez la veille normalement.
Le contenu du fichier s'efface tout seul après chaque lancement ; laissé vide (ou mal
écrit), la veille traite simplement la date du jour.

## Comment ça marche

L'outil interroge l'API officielle Légifrance (PISTE), ne garde que les textes dont le
titre contient un mot-clé pharmaceutique, puis lit dans les textes et leurs tableaux
les produits, laboratoires, listes et indications. Il en tire **une ligne par nom de
médicament et par laboratoire** (les dosages sont regroupés ; un générique vendu par
plusieurs laboratoires garde une ligne par laboratoire), classée en « Nouvelles
inscriptions », « Hausse de prix », « Baisse de prix », « Modification de libellé »,
« Extensions d'indications » ou « Radiations ». Les prix ne sont plus détaillés :
chaque ligne renvoie vers l'avis officiel par un lien « Site LégiFrance » (décision
CEPS du 23/07/2026). Le taux de participation, lui, reste affiché (« 35% »), cliquable
vers la décision UNCAM qui le publie. La colonne Liste distingue les 5 listes
(SS, Collectivité, LES MCO, LES SMR, Rétrocession), un lien par liste. Tout vient du
texte publié : une donnée absente sort « N/A » ou « à compléter manuellement »,
jamais devinée.

Un même médicament est souvent visé le même jour par plusieurs textes qui l'écrivent
différemment (« MEROPENEM PAN 1G » dans l'avis de prix, « MÉROPÉNÈME … » dans l'arrêté) :
le rapprochement se fait alors sur le **code de la présentation** (CIP-13 ou UCD), pas
sur le nom. La colonne Produit porte le nom de la **spécialité**, jamais la molécule :
les arrêtés de liste en sus publient les deux côte à côte (« ENCORAFENIB » puis
« BRAFTOVI 75 mg gélules ») — c'est BRAFTOVI qui sort. Un produit à la fois inscrit, étendu et retarifé le même jour ne sort qu'une
fois, dans « Extensions d'indications », avec le rappel de ses listes et le lien de son
avis de prix sous l'indication (règle validée sur le JO du 23/07/2026).

Les arrêtés de modification de libellé changent presque toujours l'exploitant sans
toucher au nom du produit : la colonne Laboratoire y montre alors le transfert,
« AGUETTANT → DEMOGEN FRANCE SAS », l'exploitant qui cède à gauche et le nouveau à
droite (format à valider avec l'utilisatrice).

Beaucoup d'avis de prix ne disent pas s'il s'agit d'une hausse ou d'une baisse (et ne
publient pas l'ancien prix) : l'outil compare alors le prix publié au dernier prix
connu — référentiel public BDPM (téléchargé dans `donnees/`, au plus une fois par
semaine) et historique des prix déjà vus au JO. Sens introuvable ou contradictoire :
la ligne sort en « Hausse de prix (à vérifier) », à reclasser à la relecture.

## Publication GitHub Pages

En plus du brouillon Outlook/fichier HTML local, une exécution automatique quotidienne
(GitHub Actions, cf. `.github/workflows/publier-pages.yml`) republie le digest du jour sur
une page publique du dépôt : **https://socialgouv.github.io/Veille_JO/**. La page
d'accueil montre la dernière publication et une archive de tous les jours précédents
(digest HTML + Excel téléchargeable). Cette publication est un simple miroir en lecture
seule — elle ne remplace pas la relecture et l'envoi manuel du mail décrits ci-dessus.

## Pour aller plus loin

- [TUTORIEL.md](TUTORIEL.md) — le quotidien pas à pas, et que faire quand ça coince ;
- [INSTALL.md](INSTALL.md) — installation, clé d'accès, tâche planifiée, dépannage
  (pour le référent technique) ;
- [TESTS.md](TESTS.md) — comportements métier à vérifier et comment lancer les tests
  hors ligne (pour développeur) ;
- `presentation_veille_JO.pptx` — le fonctionnement et les garde-fous, en 5 diapositives.
