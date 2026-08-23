# 🧭 TripSense — Comparateur intelligent de voyages

Application Streamlit qui compare et recommande les meilleures combinaisons
**transport (train, bus, avion) + hébergement (hôtel, Airbnb)** selon un
départ, une destination et un budget donnés.

## ✨ Fonctionnalités

- Recherche par ville de départ / destination, dates, nombre de voyageurs.
- Budget cible avec **marge de tolérance ajustable** (± €).
- **Rayon de recherche** (km) pour l'hébergement autour de la destination.
- Choix du type d'hébergement : **Hôtel**, **Airbnb**, ou **les deux**.
- **Filtre par étoiles**, actif uniquement si le type sélectionné inclut « Hôtel ».
- Géolocalisation des villes **en temps réel** (API OpenStreetMap Nominatim).
- Recherche de vols **en temps réel** via l'API Amadeus si une clé est configurée
  (sinon simulation automatique, voir plus bas).
- **Score qualité-prix** calculé automatiquement (prix, durée, confort, CO₂).
- **Badges de recommandation** : meilleur rapport qualité-prix, le plus économique,
  le plus rapide, le plus écologique.
- **Comparaison visuelle** interactive (nuage de points prix / durée / score).
- **Estimation du temps de trajet porte-à-porte** (trajet + accès gare/aéroport).
- **Estimation de l'empreinte CO₂** de chaque option.
- Gestion claire des erreurs : champs vides, aucun résultat, budget trop restrictif.

## 🎯 Pourquoi ces choix (point de vue agence de voyage)

| Fonctionnalité | Intérêt pour le voyageur |
|---|---|
| Score qualité-prix relatif | Évite de comparer 4 critères à la main ; donne une réponse immédiate. |
| Temps porte-à-porte (et non juste la durée du trajet) | Un vol « 1h30 » avec 2h d'aéroport n'est pas toujours plus rapide qu'un train direct. |
| Empreinte CO₂ affichée | Critère de plus en plus décisif, différenciant vs comparateurs classiques. |
| Marge de tolérance budgétaire | Un budget strict élimine souvent toutes les offres ; la tolérance évite la frustration « aucun résultat ». |
| Rayon de recherche hébergement | Un hôtel « pas cher » à 40 km du centre n'est pas comparable à un hôtel central. |
| Badges (le plus rapide / le moins cher / le plus écolo) | Aide à la décision pour un utilisateur pressé, sans lire tous les détails. |

## 🗂️ Structure du projet

```
travel-planner/
├── app.py                     # Interface Streamlit (UI uniquement)
├── config.py                  # Constantes, barèmes, accès aux clés API
├── core/                      # Logique métier (aucun code Streamlit ici)
│   ├── geo.py                 # Géocodage temps réel + calcul de distance
│   ├── transport.py           # Recherche transport (réel + simulé)
│   ├── accommodation.py       # Recherche hébergement (simulé)
│   ├── combiner.py            # Construction des packages transport+hébergement
│   ├── scoring.py             # Score qualité-prix et badges
│   └── exceptions.py          # Exceptions métier
├── data/
│   └── airports.py            # Référentiel d'aéroports (pour l'API Amadeus)
├── ui/
│   ├── components.py          # Cartes de résultats, graphique de comparaison
│   └── styles.py               # CSS
├── .streamlit/
│   ├── config.toml            # Thème visuel
│   └── secrets.toml.example   # Modèle pour la clé API Amadeus
├── requirements.txt
└── README.md
```

## 🔌 Sources de données : réelles vs simulées

| Donnée | Source | Statut |
|---|---|---|
| Coordonnées des villes | API OpenStreetMap **Nominatim** | ✅ Réel, en temps réel, sans clé |
| Distance entre villes | Calcul (formule de haversine) sur coordonnées réelles | ✅ Réel |
| Vols | API **Amadeus** Flight Offers Search | ✅ Réel *si clé API configurée*, sinon simulation |
| Train / Bus | Aucune API publique gratuite équivalente disponible | ⚠️ Simulé, à partir de barèmes réalistes et de la distance réelle |
| Hôtels | Amadeus Hotel Search API (à implémenter sur le même modèle) | ⚠️ Simulé par défaut |
| Airbnb | Pas d'API publique officielle Airbnb | ⚠️ Toujours simulé |

Chaque module `core/*.py` documente précisément, en commentaire, où brancher
un vrai fournisseur (SNCF Connect, Trainline Partner API, FlixBus/Omio,
Booking.com Demand API, etc.).

### Activer les vols en temps réel (gratuit)

1. Créer un compte sur [developers.amadeus.com](https://developers.amadeus.com) (gratuit).
2. Créer une application en environnement **Self-Service (test)** → récupérer
   `API Key` et `API Secret`.
3. Sur Streamlit Community Cloud : `Settings` → `Secrets`, coller :
   ```toml
   AMADEUS_API_KEY = "votre_client_id"
   AMADEUS_API_SECRET = "votre_client_secret"
   ```
   En local, copier `.streamlit/secrets.toml.example` vers `.streamlit/secrets.toml`
   et renseigner vos clés.
4. Relancer l'application : un bandeau confirme que les vols réels sont utilisés.

## 🚀 Déploiement sur Streamlit Community Cloud

1. Créer un dépôt GitHub et y pousser l'intégralité de ce dossier (structure
   ci-dessus, `app.py` à la racine).
2. Aller sur [share.streamlit.io](https://share.streamlit.io) et se connecter
   avec votre compte GitHub.
3. Cliquer sur **New app**, sélectionner le dépôt, la branche, et indiquer
   `app.py` comme fichier principal.
4. (Optionnel) Ajouter les secrets Amadeus dans **Advanced settings → Secrets**.
5. Cliquer sur **Deploy**. L'application sera accessible sur une URL du type
   `https://votre-app.streamlit.app`.

## 💻 Lancer en local

```bash
git clone <url-du-depot>
cd travel-planner
pip install -r requirements.txt
streamlit run app.py
```

## 🔧 Pistes d'amélioration

- Brancher l'API Amadeus Hotel Search pour des tarifs hôtels réels.
- Ajouter un vrai fournisseur train/bus (SNCF Connect, Omio, FlixBus).
- Ajouter la conversion de devise (API gratuite type Frankfurter.app) pour
  les voyages hors zone euro.
- Ajouter un historique de recherches et des alertes de prix.
- Comptes utilisateurs pour sauvegarder des voyages favoris.

## ⚠️ Limites connues

- Les prix simulés sont des estimations basées sur des barèmes moyens du
  marché et une distance géographique réelle : ils ne remplacent pas une
  réservation réelle.
- L'API Nominatim impose un usage raisonnable (pas d'appels massifs en
  boucle) ; les résultats de géocodage sont mis en cache 1h pour la
  respecter.
- L'environnement Amadeus utilisé est l'environnement de **test** (gratuit,
  données réelles mais quotas limités) ; un passage en production nécessite
  un contrat commercial avec Amadeus.
