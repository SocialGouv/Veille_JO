# Tutoriel — La veille JO au quotidien

> **À qui s'adresse ce guide** : à toute personne du CEPS chargée d'envoyer la newsletter
> de veille du Journal officiel, **sans aucune connaissance technique**. La toute première
> installation (une seule fois, environ 15 minutes) est décrite en annexe, à la fin ;
> demandez de l'aide au référent technique si besoin. Tout le reste, c'est votre quotidien :
> **4 étapes, 2 minutes par matin**.

## L'outil en deux mots

Chaque matin, l'outil lit le Journal officiel du jour, repère les textes qui concernent
les spécialités pharmaceutiques (inscriptions, radiations, prix, taux, libellés,
extensions d'indications), et prépare à votre place :

- le **tableau Excel** de la veille (dans le dossier `sorties`) ;
- le **brouillon du mail** dans Outlook : destinataires, objet, tableaux et pièce jointe
  déjà remplis.

**L'outil n'envoie jamais rien tout seul.** C'est toujours vous qui relisez et qui
cliquez sur Envoyer.

---

## Tous les matins : 4 étapes

### Étape 1 — Double-cliquez sur « lancer_veille »

L'icône est sur le bureau (ou dans le dossier `veille_jo`). Une fenêtre noire s'ouvre
avec du texte qui défile : c'est normal, **ne la fermez pas**, cela prend 1 à 2 minutes.

À la fin, la fenêtre affiche :

- `[OK] Veille terminee : resultats dans le dossier sorties\` → tout va bien,
  appuyez sur une touche pour fermer et passez à l'étape 2 ;
- `[ECHEC] ...` → voyez « [Quand quelque chose ne va pas](#quand-quelque-chose-ne-va-pas) »
  plus bas.

*(Si une tâche automatique a été mise en place à 7 h, cette étape se fait toute seule :
vous trouvez directement le brouillon prêt en arrivant.)*

L'outil traite **le JO du jour**, sans rien avoir à lui indiquer. Pour lui faire traiter
un autre jour, voyez « [Refaire la veille d'un jour passé](#refaire-la-veille-dun-jour-passé-cas-rare) ».

### Étape 2 — Le brouillon s'ouvre dans Outlook

Quelques secondes après la fin de la fenêtre noire, un brouillon de mail s'affiche :

- destinataires : la liste de diffusion SG_CEPS ;
- objet : `[VEILLE] - Publication JO du <date du jour>` ;
- corps : les tableaux colorés de la newsletter ;
- pièce jointe : l'Excel du jour ;
- votre signature habituelle, en dessous.

### Étape 3 — Relisez (c'est votre valeur ajoutée)

Quatre vérifications rapides :

1. **Les tableaux sont-ils plausibles ?** Les bons produits dans les bonnes sections
   (Nouvelles inscriptions / Hausse de prix / Baisse de prix / Modification de
   libellé / Extensions d'indications / Radiations).
2. **Le sens des variations de prix.** Beaucoup d'avis publient un prix sans dire
   « hausse » ni « baisse » : l'outil tranche en comparant au dernier prix connu
   (référentiel public des médicaments + prix déjà vus au JO). Quand il n'y parvient
   pas, la ligne est mise en **Hausse de prix avec « (à vérifier) »** : ouvrez son lien
   et déplacez-la en Baisse de prix si besoin.
3. **Y a-t-il des mentions « (à vérifier) » ou un bloc « Récapitulatif des anomalies »
   en bas du mail ?** L'outil vous y signale ce dont il n'est pas sûr, avec sa raison et
   le lien Légifrance à ouvrir pour trancher. Corrigez directement dans le brouillon.
4. **Une indication affiche « à compléter manuellement » ?** Cliquez sur le lien
   `Site LégiFrance` de la même ligne, copiez l'indication exacte depuis le texte
   officiel, collez-la dans le brouillon (et dans l'Excel joint si vous voulez qu'il
   soit complet).

### Étape 4 — Cliquez sur Envoyer

Rien ne part tant que vous n'avez pas cliqué. Après l'envoi, c'est terminé : l'Excel
reste archivé dans le dossier `sorties`.

---

## Le cas « RAS »

Certains jours, aucun texte ne concerne les spécialités pharmaceutiques. Le brouillon
dit alors simplement :

> RAS — aucun texte relatif aux spécialités pharmaceutiques au JO du JJ/MM/AAAA.

**Envoyez-le quand même.** C'est la règle de la veille : un mail « RAS » prouve que la
veille a tourné ; une absence de mail signifie « panne », jamais « rien à signaler ».

---

## Quand quelque chose ne va pas

| Ce que vous voyez | Ce que ça veut dire | Ce que vous faites |
|---|---|---|
| La fenêtre noire affiche `[ECHEC]` et un mail (ou une page) « ALERTE » parle de « JO introuvable » | Le JO du jour n'est pas encore publié (ça arrive en début de matinée) | Attendez une heure et double-cliquez à nouveau sur `lancer_veille`. Si la tâche automatique de 7 h est en place, elle réessaie toute seule 3 fois. |
| `[ECHEC]` qui persiste toute la matinée | Panne d'accès (réseau, clés d'accès expirées…) | Prévenez le référent technique en lui transmettant le fichier le plus récent du dossier `logs`. En attendant, la veille peut se faire à l'ancienne sur legifrance.gouv.fr. |
| La fenêtre dit `[OK]` mais **aucun brouillon Outlook** ne s'ouvre | Outlook était fermé, ou l'automatisation est bloquée sur le poste | Le contenu du mail vous attend quand même : ouvrez le dossier `sorties`, double-cliquez sur `corps_mail_<date>.html` (il s'ouvre dans le navigateur), faites Ctrl+A puis Ctrl+C, collez dans un nouveau mail Outlook, joignez l'Excel `veille_jo_<date>.xlsx` du même dossier, et envoyez à la liste habituelle. |
| Une indication affiche « à compléter manuellement » | Le texte officiel ne présente pas l'indication à l'endroit habituel — **le reste de la ligne est complet et fiable** | Complétez l'indication à la main via le lien `Site LégiFrance` (étape 3). Si cela devient fréquent, signalez-le au référent, sans urgence. |

En dernier recours, le mode d'emploi technique complet (installation, clé d'accès,
pannes courantes) est dans `INSTALL.md` : c'est le document du référent.

---

## Refaire la veille d'un jour passé (cas rare)

Exemple : vous étiez absente jeudi et vous voulez produire la veille du 28 mai 2026.

1. Ouvrez le dossier `veille_jo` dans l'explorateur.
2. Ouvrez le fichier **`date.txt`** (il est toujours là, normalement vide — double-clic,
   il s'ouvre dans le Bloc-notes) et écrivez dedans la date voulue au format
   **JJ-MM-AAAA** (jour, mois, année, séparés par des traits d'union), une seule ligne :

   ```
   28-05-2026
   ```

3. Enregistrez, fermez, puis lancez la veille comme d'habitude (double-clic sur
   « lancer_veille ») : elle traite le 28 mai au lieu d'aujourd'hui.
4. Reprenez à l'étape 2 du quotidien (brouillon Outlook, relecture, envoi).

Trois choses à savoir sur ce fichier :

- **`date.txt` vide = le JO du jour.** C'est son état normal, celui de tous les matins :
  vous n'avez rien à y écrire pour la veille quotidienne.
- **Son contenu s'efface tout seul après chaque lancement**, donc aucun risque de
  rejouer la même date le lendemain. Le fichier, lui, reste en place, prêt pour la
  prochaine fois — et s'il a été supprimé par erreur, il est recréé vide.
- **Une date impossible ou mal écrite** (`32-05-2026`, `2026-05-28`, `demain`) ne bloque
  rien : la veille le signale dans sa fenêtre et traite la date du jour.

---

## Les trois règles d'or

1. **Ne modifiez pas** les fichiers du dossier `veille_jo` (à part consulter `sorties`) :
   tout le paramétrage se fait avec le référent.
2. **Ne partagez jamais** le fichier `.env` : il contient les clés d'accès de l'outil
   (l'équivalent de mots de passe).
3. **N'activez pas l'envoi automatique** (mail qui part sans relecture) sans décision
   d'équipe : la relecture de l'étape 3 est votre filet de sécurité.

---

## Annexe — Première installation (une seule fois, ~15 minutes)

Elle se fait une seule fois par poste, idéalement avec le référent technique : la
procédure complète (Python, environnement, clé d'accès PISTE, raccourci « Veille JO »
sur le bureau, tâche automatique de 7 h) est décrite dans `INSTALL.md`.

Le jour du premier essai, déroulez les 4 étapes du quotidien mais ne cliquez sur
Envoyer qu'après avoir comparé le brouillon avec la newsletter habituelle.
