"""
Obtiene cuotas de múltiples casas de apuestas usando The Odds API.
Docs: https://the-odds-api.com/liveapi/guides/v4/
"""
import os
import requests

BASE_URL = "https://api.the-odds-api.com/v4"

# Deportes que cubrimos. Puedes ver la lista completa en:
# https://api.the-odds-api.com/v4/sports/?apiKey=TU_KEY
SPORTS = [
    "soccer_mexico_ligamx",
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_italy_serie_a",
    "soccer_germany_bundesliga",
    "soccer_uefa_champs_league",
    "basketball_nba",
    "americanfootball_nfl",
    "icehockey_nhl",
    "baseball_mlb",
]

REGIONS = "us,uk,eu"  # de dónde saca casas de apuestas (para tener varias y comparar)
MARKETS = "h2h,totals"  # h2h = 1X2/moneyline, totals = over/under


def get_api_key():
    key = os.environ.get("ODDS_API_KEY")
    if not key:
        raise RuntimeError(
            "Falta la variable de entorno ODDS_API_KEY. "
            "Consíguela gratis en https://the-odds-api.com"
        )
    return key


def fetch_odds_for_sport(sport_key: str):
    """Trae los partidos y cuotas de un deporte específico."""
    api_key = get_api_key()
    url = f"{BASE_URL}/sports/{sport_key}/odds"
    params = {
        "apiKey": api_key,
        "regions": REGIONS,
        "markets": MARKETS,
        "oddsFormat": "decimal",
        "dateFormat": "iso",
    }
    resp = requests.get(url, params=params, timeout=20)
    if resp.status_code == 401:
        raise RuntimeError("API key inválida para The Odds API.")
    if resp.status_code == 429:
        raise RuntimeError("Se acabaron las solicitudes del mes en The Odds API.")
    resp.raise_for_status()
    return resp.json()


def fetch_all_odds():
    """Trae los partidos de todos los deportes configurados. Ignora deportes sin partidos hoy."""
    all_events = []
    for sport in SPORTS:
        try:
            events = fetch_odds_for_sport(sport)
            for ev in events:
                ev["_sport_key"] = sport
            all_events.extend(events)
        except RuntimeError as e:
            print(f"[aviso] no se pudo traer {sport}: {e}")
        except requests.RequestException as e:
            print(f"[aviso] error de red en {sport}: {e}")
    return all_events
