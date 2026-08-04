# Installation (référent technique)

> Utilisation quotidienne : [README.md](README.md) (l'essentiel) et
> [TUTORIEL.md](TUTORIEL.md) (pas à pas). Ici : installer l'outil une fois,
> et le dépanner si besoin.

## Installer (une fois, ~15 minutes)

Prérequis : Python 3.10+ (à l'installation, cocher « Add python.exe to PATH »).

Depuis le dossier `veille_jo/`, dans un terminal (`cmd` sous Windows) :

```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
.venv\Scripts\python.exe diagnostic.py
```

Sous Linux/macOS : `.venv/bin/python` au lieu de `.venv\Scripts\python.exe`, `cp` au lieu de `copy`.

Puis :

1. remplir `.env` avec la clé PISTE (voir ci-dessous) ;
2. relancer `.venv\Scripts\python.exe diagnostic.py` : chaque flux doit afficher `OK` ;
3. créer le raccourci du matin : clic droit sur `lancer_veille.bat` → « Envoyer vers »
   → « Bureau », renommer « Veille JO ».

C'est terminé. **Il n'y a rien d'autre à lancer** : au quotidien, `lancer_veille.bat`
exécute `main.py`, qui enchaîne tout seul toutes les étapes (lecture du JO via PISTE,
filtrage, analyse, consolidation, Excel, brouillon de mail). Les autres fichiers `.py`
du dossier sont les modules de ce pipeline, pas des programmes à lancer. Seules
exceptions, à la main et seulement si besoin : `diagnostic.py` (test des accès) et le
dossier `tests/` (vérifications hors ligne, pour développeur — voir
[TESTS.md](TESTS.md) pour les lancer). Sur poste Linux de développement,
`lancer_veille.sh` est l'équivalent du `.bat`.

## Flux externes et dossier `donnees/`

Deux accès réseau sortants, à faire ouvrir si le poste passe par un proxy filtrant :

| Flux                        | Hôte                                        | Rôle                                                        | Si bloqué                                             |
| --------------------------- | ------------------------------------------- | ----------------------------------------------------------- | ----------------------------------------------------- |
| API Légifrance              | `oauth.piste.gouv.fr`, `api.piste.gouv.fr`  | source des textes                                           | **bloquant** : pas de veille (alerte + code retour 1) |
| Référentiel des prix (BDPM) | `base-donnees-publique.medicaments.gouv.fr` | prix antérieurs, pour orienter les avis de prix « neutres » | non bloquant : ces avis sortent « à vérifier »        |

Le dossier `donnees/` (créé au premier run, hors dépôt) contient le cache BDPM
(`CIS_CIP_bdpm.txt`, re-téléchargé au plus une fois par semaine ; en cas de panne
réseau le dernier fichier sert tel quel) et `historique_prix.csv`, l'historique des prix
publiés au JO, alimenté à chaque run. **Ne pas le supprimer** : il prime sur la BDPM et
c'est la seule mémoire des prix vus par l'outil.

## Clé d'accès PISTE (la seule du projet)

| Clé (`.env`)                              | Obtention                                                                                                                              | À expiration / révocation                                                                    |
| ----------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `PISTE_CLIENT_ID` / `PISTE_CLIENT_SECRET` | Compte sur [piste.gouv.fr](https://piste.gouv.fr) → créer une application → souscrire à l'**API Légifrance** → copier client id/secret | Régénérer le secret dans l'application PISTE, recopier dans `.env`, relancer `diagnostic.py` |

Le token d'exécution (validité ~1 h) est géré automatiquement.

## Réglages utiles (`config.py`)

| Clé                     | Défaut livré          | Effet                                                                                                                                                                                                             |
| ----------------------- | --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `MAIL_MODE`             | `"brouillon_outlook"` | `"html"` : pas d'Outlook, le fichier `corps_mail_<date>.html` s'ouvre dans le navigateur pour copier-coller. Le HTML est écrit dans tous les cas.                                                                 |
| `ENVOI_AUTOMATIQUE`     | `False`               | `True` : envoie le mail sans relecture (`.Send()`). À n'activer qu'après une période de confiance.                                                                                                                |
| `POLICE`                | `"Marianne"`          | `"Arial"` si Marianne absente du poste (simple nom de police : aucun plantage, juste le rendu).                                                                                                                   |
| `ORIENTATION_PRIX_AUTO` | `True`                | Oriente les avis de prix qui ne disent ni hausse ni baisse, par comparaison au dernier prix connu (BDPM + historique local). `False` : ces avis restent tous « à vérifier » (comportement d'avant le 29/07/2026). |

Rejouer une date au-delà d'environ 3 mois (`NB_ELEMENT_LASTNJO = 90`, la profondeur de
rejeu de l'API) : augmenter cette valeur dans `config.py`.

Les autres tables de `config.py` se complètent au fil de l'eau, sans toucher au code :
`MAPPING_LABOS` (écriture des laboratoires), `FORMES_GALENIQUES` et `SELS_ET_ESTERS`
(regroupement des dosages sous un même nom), `MOTS_CLES` et `MOTIFS_CLASSIFICATION`
(sélection et typage des textes). Chaque entrée y est datée et sourcée : garder cet usage.

## Tâche planifiée (une fois la recette signée)

Quotidienne à 7 h 00, jours ouvrés, relance sur échec (30 min, 3 fois), à créer sur
le poste cible (adapter le chemin) :

```bat
schtasks /Create /TN "Veille JO CEPS" /TR "C:\chemin\vers\veille_jo\lancer_veille.bat" ^
  /SC WEEKLY /D LUN,MAR,MER,JEU,VEN /ST 07:00 /RI 30 /DU 01:30 /RL LIMITED /F
```

Cocher ensuite « exécuter même si l'utilisateur n'est pas connecté » dans le
Planificateur de tâches (onglet Général de la tâche). La relance s'appuie sur le code
retour de `main.py` : `0` si la veille a abouti (même « RAS »), `1` en cas d'échec.
Sans tâche planifiée, le double-clic du matin suffit.

## Pannes courantes

| Symptôme                                                                                                                               | Cause probable                                                                                                                   | Remède                                                                                                                                                              |
| -------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `PISTE token : KO` au diagnostic, ou `401` en boucle dans le log                                                                       | Token/compte PISTE expiré ou désactivé, secret régénéré                                                                          | Se connecter sur piste.gouv.fr, vérifier l'application et la souscription Légifrance, régénérer le secret, mettre à jour `.env`                                     |
| Des indications affichent « à compléter manuellement »                                                                                 | L'arrêté ne porte pas l'indication dans la section attendue (tournure inhabituelle) — le reste de la ligne est complet et fiable | Cliquer le lien `Site LégiFrance` de la ligne, recopier l'indication exacte ; tournure récurrente → motif à étendre dans `analyse.py`                               |
| « JO introuvable pour la date … » le matin                                                                                             | JO pas encore publié (vers 2 h-3 h, parfois plus tard) ou jour sans JO (certains lundis/lendemains fériés)                       | Relancer plus tard dans la matinée (la tâche planifiée réessaie seule 3 fois toutes les 30 min)                                                                     |
| Le brouillon Outlook ne s'affiche pas                                                                                                  | Outlook fermé, ou automatisation COM interdite par la DSI                                                                        | Le run reste en succès : ouvrir `sorties/corps_mail_<date>.html` (écrit dans tous les cas), copier-coller dans un mail ; durablement : `MAIL_MODE = "html"`         |
| `Référentiel de prix indisponible` ou `Téléchargement BDPM impossible` dans le log, beaucoup de lignes « Hausse de prix (à vérifier) » | BDPM injoignable (proxy, site en panne) ou premier run sans historique                                                           | Non bloquant, la veille aboutit : ouvrir l'accès à `base-donnees-publique.medicaments.gouv.fr` ; l'historique local se remplit ensuite tout seul et prend le relais |
| Excel non écrit, log `Fichier cible ouvert`                                                                                            | le `veille_jo_<date>.xlsx` du jour est ouvert dans Excel                                                                         | Aucune perte : le fichier est écrit suffixé de l'heure ; fermer Excel avant le run suivant                                                                          |

## À valider sur le poste cible (Windows ministériel)

Codé et testé hors Windows, à vérifier à la première installation :

1. **Brouillon Outlook** : `.venv\Scripts\python.exe main.py --date 2026-05-28` avec
   Outlook ouvert → un brouillon pré-rempli s'affiche (destinataires, objet, tableaux,
   Excel joint), signature intacte. Ne pas cliquer Envoyer pendant le test.
2. **Planificateur** : créer la tâche (commande ci-dessus), clic droit → Exécuter →
   même résultat qu'un lancement manuel ; simuler un échec (réseau débranché) pour
   vérifier la relance.
3. **Police Marianne** : ouvrir l'Excel généré ; si la police n'est pas Marianne,
   installer Marianne ou passer `POLICE = "Arial"`.
4. **Accès BDPM** : au premier run, vérifier dans le log la ligne
   `Référentiel BDPM : N CIP-13 avec prix public` (13 103 au 29/07/2026). Un
   avertissement à la place = flux à ouvrir auprès de la DSI (voir « Flux externes »).
