# Triply — Travel Budget Web App

Triply est une application web Streamlit qui cherche automatiquement des options
de transport et d'hébergement, puis construit des voyages compatibles avec un
budget total.

## Fonctionnalités V2

- interface web responsive ;
- navigation horizontale multipage ;
- accueil avec moteur de recherche ;
- recherche vols, hôtels, locations, Airbnb, train et bus ;
- combinaisons transport + hébergement sous budget ;
- filtres de résultats ;
- favoris ;
- historique de recherches ;
- test de la clé SerpAPI ;
- gestion des erreurs et résultats non fiables.

## Architecture

```text
travel_budget_web_v2/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── .streamlit/
│   ├── config.toml
│   └── secrets.example.toml
├── pages/
│   ├── home.py
│   ├── search.py
│   ├── results.py
│   ├── favorites.py
│   ├── history.py
│   └── about.py
├── services/
│   ├── combinations.py
│   ├── config.py
│   ├── models.py
│   ├── search_service.py
│   ├── serpapi_client.py
│   └── state.py
└── ui/
    ├── actions.py
    ├── components.py
    ├── forms.py
    └── style.py
```

## API

Une seule clé est nécessaire :

```toml
SERPAPI_KEY = "..."
```

SerpAPI est utilisée pour :

- Google Flights Autocomplete ;
- Google Flights ;
- Google Hotels ;
- Google Hotels Vacation Rentals ;
- Google Search complémentaire.

## Installation locale

```bash
git clone <URL_DU_DEPOT>
cd travel_budget_web_v2

python -m venv .venv
```

Windows :

```powershell
.venv\Scripts\activate
pip install -r requirements.txt
```

macOS / Linux :

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Crée ensuite :

```text
.streamlit/secrets.toml
```

avec :

```toml
SERPAPI_KEY = "TA_CLE"
```

Puis :

```bash
streamlit run app.py
```

## Déploiement Streamlit Community Cloud

1. Envoie le projet sur GitHub.
2. Ne pousse jamais `.streamlit/secrets.toml`.
3. Dans Streamlit Community Cloud, crée une application depuis le dépôt.
4. Fichier principal : `app.py`.
5. Dans **Settings → Secrets**, ajoute :

```toml
SERPAPI_KEY = "TA_CLE"
```

6. Déploie.

## Favoris et historique

La V2 utilise `st.session_state`. Les données restent disponibles pendant la session
de navigation et entre les pages de l'application, mais ne sont pas encore persistées
après la fin de session.

Pour une V3, Supabase pourra ajouter :

- comptes utilisateurs ;
- favoris persistants ;
- historique multi-appareils ;
- alertes de prix ;
- profils et préférences.

## Fiabilité des prix

Les données structurées Google Flights / Google Hotels sont privilégiées.
Airbnb, train et bus peuvent provenir de résultats web. Lorsqu'un prix total
n'est pas suffisamment fiable, Triply affiche le résultat mais ne l'utilise pas
dans le calcul automatique du budget.

Toujours vérifier le tarif final sur le site du fournisseur avant réservation.


## Timeout SerpAPI

La version 2.1 utilise maintenant :

- un timeout de connexion de 10 secondes ;
- un timeout de lecture de 75 secondes ;
- jusqu'à 3 tentatives automatiques ;
- un backoff progressif en cas de timeout, HTTP 429 ou erreur serveur ;
- moins de résultats demandés pour Airbnb/train/bus afin de réduire le temps de réponse.

Les recherches Airbnb/train/bus restent complémentaires : si elles échouent,
Google Flights et Google Hotels peuvent quand même être affichés.
