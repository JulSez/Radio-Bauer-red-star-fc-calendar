# Calendrier Red Star FC 2026–2027

Générateur statique d’un calendrier iCalendar des **34 matchs de Ligue 2** du Red Star FC, destiné à être publié à l’adresse stable :

`https://julsez.github.io/Radio-Bauer-red-star-fc-calendar/red-star-fc-2026-2027.ics`

> **État initial :** l’environnement de développement n’a pas pu joindre le site officiel (proxy HTTP 403). Faute de données officielles vérifiables, aucun faux calendrier ni ICS partiel n’est livré. La page d’attente le dit explicitement. Le premier workflow qui extrait exactement 34 rencontres valides créera l’ICS et la page complète.

## Fonctionnement et source

`src/fetch.py` lit les objets publics Schema.org `SportsEvent` de la page calendrier du [site officiel du Red Star](https://www.redstar.fr/calendrier-resultats/). Cette source est isolée dans un adaptateur facile à remplacer. La variable de dépôt `MATCHES_SOURCE_URL` permet de changer l’URL sans modifier le code. Chaque entrée conserve l’URL et l’instant de vérification dans `data/competitions/ligue-2.json` puis dans la description ICS.

Les compétitions sont volontairement séparées :

- `data/competitions/ligue-2.json` doit contenir exactement les 34 journées ;
- `data/competitions/coupe-de-france.json` reste vide jusqu'à ce qu'une rencontre soit officiellement programmée.

Chaque match précise aussi `date_status` (`confirmed` ou `provisional`) et `time_status` (`confirmed` ou `unconfirmed`). Une date provisoire sans heure produit la fenêtre de trois jours et la mention « date et horaire à confirmer ».

La récupération écrit d’abord un fichier temporaire. La validation exige J1 à J34, exactement 34 matchs, des dates/heures ISO valides, Red Star dans chaque affiche, une source et aucun doublon. Ainsi une panne, un changement HTML ou une page amputée termine le workflow en erreur **avant** de toucher les données et documents existants. Les matchs passés restent présents car toute la saison est exigée.

Le générateur, sans dépendance externe, produit un ICS RFC 5545 (CRLF, échappement et lignes repliées) :

- horaire connu : heure locale `Europe/Paris`, durée de deux heures ;
- heure inconnue : journée entière de J-1 jusqu’à J+2 exclus et titre « horaire à confirmer » ;
- domicile `TRANSP:OPAQUE`, extérieur `TRANSP:TRANSPARENT` ;
- UID dérivé de saison/compétition/journée/équipes, donc indépendant de la programmation ;
- empreinte matérielle, `SEQUENCE` persistant et `LAST-MODIFIED` pour les reports, lieux et annulations.

## Exécution et configuration

Python 3.11+ suffit (`requirements.txt` est volontairement vide) :

```bash
python -m unittest discover -v
python -m src.fetch --url https://www.redstar.fr/calendrier-resultats/
python -m src.generate
```

Pour adapter une source ayant changé, modifier seulement `src/fetch.py` afin qu’il produise le schéma documenté par `Match` dans `src/calendar.py`. Ne contournez pas `validate()` et n’ajoutez pas une Coupe de France avant sa programmation officielle.

## Mettre en place la tâche récurrente

Après fusion sur `main` :

1. ouvrir **Settings → Actions → General** et, dans **Workflow permissions**, autoriser **Read and write permissions** afin que le bot puisse commiter les fichiers générés ;
2. ouvrir **Settings → Secrets and variables → Actions → Variables → New repository variable** ;
3. créer `MATCHES_SOURCE_URL` avec l'URL de la page calendrier officielle si elle diffère de l'URL par défaut (sinon ne rien créer) ;
4. ouvrir l'onglet **Actions**, sélectionner **Actualiser le calendrier**, puis cliquer sur **Run workflow** pour tester une première exécution ;
5. vérifier que l'exécution trouve bien 34 rencontres avant d'activer GitHub Pages.

Il n'y a ni appel ChatGPT ni clé API dans cette tâche récurrente : le JSON initial peut être préparé avec une recherche assistée, mais le mardi GitHub Actions relit directement la source officielle. En cas d'échec ou de résultat incomplet, le workflow échoue avant le commit et conserve la dernière publication valide.

## Automatisation

Le workflow **Actualiser le calendrier** se lance manuellement depuis **Actions → Actualiser le calendrier → Run workflow**. Deux crons UTC (07:00 et 08:00 le mardi), doublés d’un contrôle `TZ=Europe/Paris`, garantissent une seule exécution réelle à 09:00 malgré l’heure été/hiver. Il teste, récupère, valide, génère et ne pousse sur `main` qu’en cas de différence. Sa seule permission est `contents: write`; aucun secret n’est nécessaire.

## Activer GitHub Pages

Après fusion sur `main` et première génération valide :

1. ouvrir **Settings → Pages** ;
2. sous **Build and deployment**, choisir **Deploy from a branch** ;
3. choisir la branche **main**, le dossier **/docs**, puis **Save** ;
4. attendre le déploiement et ouvrir l’URL stable ci-dessus.

Ce réglage de dépôt ne peut pas être activé de façon portable depuis une pull request.

## S’abonner

### Proton Calendar

Dans Proton Calendar : **Paramètres → Calendriers → Ajouter un calendrier → S’abonner à un calendrier**, coller l’URL stable, nommer le calendrier puis valider. Proton décide de la fréquence de rafraîchissement des abonnements externes.

### Google Calendar

Dans Google Calendar sur ordinateur : à côté de **Autres agendas**, cliquer **+ → À partir de l’URL**, coller l’URL stable et choisir **Ajouter un agenda**. Ne pas importer le fichier ponctuellement : l’abonnement URL est nécessaire pour recevoir les changements.

## Limites connues

- L’adaptateur suppose que le site officiel expose les équipes, la date et le numéro de journée en JSON-LD. Une évolution du balisage fera échouer sans écraser la dernière version valide.
- La première édition complète ne peut être publiée que lorsque les 34 affiches officielles sont accessibles et vérifiées. Les heures non annoncées resteront volontairement « à confirmer ».
- La fréquence de prise en compte d’un ICS distant dépend de Proton/Google et non de ce dépôt.
