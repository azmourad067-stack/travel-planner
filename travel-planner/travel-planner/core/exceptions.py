"""Exceptions métier custom, pour des messages d'erreur clairs côté UI."""


class TripSenseError(Exception):
    """Classe de base pour toutes les erreurs métier de l'application."""


class ValidationError(TripSenseError):
    """Levée quand les entrées utilisateur sont invalides ou incomplètes."""


class GeocodingError(TripSenseError):
    """Levée quand une ville n'a pas pu être localisée."""


class NoResultsError(TripSenseError):
    """Levée quand aucune offre ne correspond aux critères de recherche."""
