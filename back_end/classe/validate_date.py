import re

def validate_date(date_str):
    """Valide et corrige une date au format YYYY-MM-DD."""
    if not date_str:
        return None
        
    try:
        # Vérifier le format
        if not re.match(r'^\d{4}-\d{1,2}-\d{1,2}$', date_str):
            return None
            
        # Extraire les composants
        year, month, day = map(int, date_str.split('-'))
        
        # Vérifier les plages valides
        if not (1900 <= year <= 2100):
            return None
        if not (1 <= month <= 12):
            # Correction du mois si hors limites
            month = min(12, max(1, month))
        if not (1 <= day <= 31):
            # Correction du jour si hors limites
            day = min(28, max(1, day))  # Utiliser 28 comme valeur sécurisée
            
        # Retourner la date corrigée
        return f"{year}-{month:02d}-{day:02d}"
    except Exception:
        return None