# A290 contre la pompe

Calculateur d'économies Alpine A290 contre voiture thermique, avec les prix moyens nationaux du carburant mis à jour automatiquement chaque jour.

## Contenu

| Fichier | Rôle |
|---|---|
| `index.html` | L'application (une seule page, rien à installer). |
| `data/prix.json` | Les prix moyens nationaux quotidiens. Mis à jour par le robot. |
| `scripts/update_prices.py` | Le calcul des moyennes à partir des données officielles. |
| `.github/workflows/update-prices.yml` | Le robot GitHub Actions qui lance le calcul chaque matin. |

## Mise en ligne (une seule fois)

1. Créez un dépôt **public** sur GitHub, par exemple `a290`.
2. Déposez-y tout le contenu de ce dossier, **y compris le dossier caché `.github`** (sur le site GitHub : « Add file » puis « Upload files », en glissant le dossier entier).
3. **Settings → Actions → General** : dans « Workflow permissions », cochez **Read and write permissions**, puis « Save ». Sans ça, le robot ne peut pas enregistrer les nouveaux prix.
4. **Settings → Pages** : « Source » = **Deploy from a branch**, branche `main`, dossier `/ (root)`, puis « Save ». Après une minute, l'adresse apparaît en haut de la page, du type `https://votre-nom.github.io/a290/`.
5. **Actions → Mise à jour des prix carburant → Run workflow**, cochez **Recalculer les 100 derniers jours**, puis lancez. Cela remplace les premières valeurs (relevés publiés, avec des jours estimés) par des moyennes calculées jour par jour à partir des données officielles. Comptez quelques minutes.

C'est tout : ensuite, le robot tourne seul tous les matins vers 7 h 30 et la page affiche toujours les 93 derniers jours.

## Bon à savoir

- **Vérifiez l'onglet Actions** après la première exécution : une coche verte signifie que tout va bien. En cas de croix rouge, ouvrez l'exécution pour lire l'erreur (souvent l'étape 3 oubliée).
- **GitHub met en pause les tâches planifiées** d'un dépôt sans activité pendant 60 jours. Vous recevrez un e-mail : il suffit de cliquer sur « Enable workflow » dans l'onglet Actions pour relancer.
- **Si le site du ministère ne répond pas** un matin, rien n'est écrit ce jour-là et la page estime le jour manquant à partir de ses voisins (affiché en italique). Le lendemain, tout repart normalement.
- **Si la page ne trouve pas `data/prix.json`**, elle utilise une copie de secours intégrée, arrêtée au 21 septembre 2026.

## Méthode

Pour chaque carburant (SP95-E10, SP98, gazole, E85), le script garde le dernier prix déclaré par chaque station, écarte les prix non mis à jour depuis plus de 7 jours et les valeurs hors de 0,30 à 5 €/L, puis calcule la moyenne arithmétique. Un jour n'est enregistré que si au moins 100 stations ont un prix valide.

Source : [Prix des carburants, données publiques](https://www.prix-carburants.gouv.fr/rubrique/opendata/), ministère de l'Économie.
