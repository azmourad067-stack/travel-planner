# Travel Budget Explorer — Streamlit

Application Streamlit qui compare des hébergements et des transports pour construire
des combinaisons compatibles avec un budget total.

## Architecture retenue

Il n'existe pas d'API publique gratuite et universelle couvrant de façon fiable :
hôtels + Airbnb + vols + trains + bus.

Cette application utilise donc une architecture hybride :

1. **Amadeus Self-Service APIs**
   - résolution de villes/aéroports ;
   - recherche de vols aller-retour ;
   - liste et tarifs d'hôtels.
2. **SerpAPI / Google Search**
   - découverte complémentaire d'Airbnb ;
   - résultats train et bus ;
   - liens vers les fournisseurs.
3. **Moteur de combinaisons local**
   - normalise les offres ;
   - additionne transport + hébergement ;
   - ne conserve que les combinaisons <= budget maximal.

### Pourquoi ne pas scraper directement Airbnb / Booking / Trainline ?

Le HTML change souvent, des protections anti-bot sont présentes et les conditions
d'utilisation peuvent interdire ou limiter le scraping automatisé. La recherche web
sert donc de couche de découverte, sans contourner ces protections.

## Limites importantes

- Les prix de voyage changent rapidement.
- Les tarifs Amadeus sont beaucoup plus structurés que les snippets d'un moteur de recherche.
- Un prix trouvé dans un snippet web peut être incomplet, "à partir de", par nuit,
  par personne ou aller simple.
- Par sécurité, l'application n'injecte un prix web dans le calcul du budget que lorsque
  le texte laisse suffisamment entendre qu'il s'agit d'un total.
- La disponibilité finale doit toujours être vérifiée sur le site du fournisseur.
- Le catalogue Amadeus Self-Service n'est pas exhaustif pour toutes les compagnies et
  tous les tarifs du marché.
- Airbnb ne fournit pas ici une API publique officielle utilisée directement par l'application.

## Structure

```text
travel_budget_streamlit/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── .streamlit/
│   ├── config.toml
│   └── secrets.example.toml
└── services/
    ├── __init__.py
    ├── amadeus.py
    ├── combinations.py
    ├── config.py
    ├── models.py
    └── search_web.py
```

## 1. Prérequis

- Python 3.12 recommandé
- Compte GitHub
- Compte Streamlit Community Cloud
- Clés Amadeus Developers
- Clé SerpAPI pour les recherches web complémentaires

## 2. Installation locale

```bash
git clone <URL_DE_TON_REPO>
cd travel_budget_streamlit

python -m venv .venv
```

### Windows

```powershell
.venv\Scripts\activate
pip install -r requirements.txt
```

### macOS / Linux

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. Configurer les secrets en local

Copie :

```text
.streamlit/secrets.example.toml
```

vers :

```text
.streamlit/secrets.toml
```

Puis remplis :

```toml
AMADEUS_CLIENT_ID = "..."
AMADEUS_CLIENT_SECRET = "..."
AMADEUS_BASE_URL = "https://test.api.amadeus.com"
SERPAPI_KEY = "..."
```

`secrets.toml` est ignoré par Git grâce au `.gitignore`.

## 4. Lancer l'application

Depuis la racine du dépôt :

```bash
streamlit run app.py
```

## 5. Créer les clés Amadeus

1. Crée un compte sur Amadeus for Developers.
2. Crée une application.
3. Récupère la clé API et le secret.
4. Commence avec l'environnement de test :
   `https://test.api.amadeus.com`
5. Passe à la production uniquement lorsque ton accès est validé.

Les endpoints utilisés sont notamment :
- OAuth2 token ;
- Airport & City Search ;
- Flight Offers Search ;
- Hotel List by City ;
- Hotel Search / Hotel Offers.

## 6. Ajouter SerpAPI

Crée une clé SerpAPI, puis renseigne :

```toml
SERPAPI_KEY = "..."
```

Sans SerpAPI, l'application reste capable d'utiliser Amadeus, mais n'affichera pas
les recherches complémentaires Airbnb/train/bus.

## 7. Déploiement Streamlit Community Cloud

1. Envoie tous les fichiers sur GitHub.
2. Vérifie que `.streamlit/secrets.toml` n'a PAS été envoyé.
3. Ouvre Streamlit Community Cloud.
4. Choisis **Create app**.
5. Sélectionne ton dépôt, ta branche et `app.py`.
6. Dans les paramètres avancés / Secrets, colle par exemple :

```toml
AMADEUS_CLIENT_ID = "..."
AMADEUS_CLIENT_SECRET = "..."
AMADEUS_BASE_URL = "https://test.api.amadeus.com"
SERPAPI_KEY = "..."
```

7. Choisis idéalement Python 3.12.
8. Déploie.

## 8. Passage en production

Pour une vraie application publique :

- demander/activer l'accès production Amadeus ;
- remplacer l'URL de test par :

```toml
AMADEUS_BASE_URL = "https://api.amadeus.com"
```

- surveiller les quotas et coûts API ;
- ajouter du cache Streamlit pour diminuer le nombre d'appels ;
- éventuellement ajouter une base de données pour historiser les recherches ;
- ajouter des fournisseurs spécialisés train/bus si tu obtiens leurs API partenaires.

## 9. Améliorations recommandées

- filtrage par durée de trajet ;
- nombre de bagages ;
- hébergement minimum en étoiles / note ;
- rayon autour du centre-ville ;
- carte ;
- tri "moins cher", "plus rapide", "meilleur compromis" ;
- favoris ;
- export PDF/CSV ;
- historique Supabase ;
- alertes de baisse de prix ;
- ajout d'une API météo ;
- ajout d'un LLM uniquement pour résumer/comparer les résultats, jamais pour inventer les prix.

## Sécurité

Ne mets jamais de clé API dans :
- `app.py`,
- `README.md`,
- un commit GitHub,
- une capture publique.

Utilise `st.secrets` sur Streamlit Community Cloud ou des variables d'environnement.
