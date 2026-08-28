"""
Metodología del bot:
1. Para cada partido, juntamos las cuotas que ofrecen varias casas de apuestas
   para el mismo mercado (ej. "Equipo A gana").
2. Convertimos cada cuota a probabilidad implícita (1 / cuota).
3. Le quitamos el margen de la casa (vig) a cada casa individual, normalizando
   sus probabilidades para que sumen 100%.
4. Promediamos esas probabilidades "limpias" entre todas las casas -> esa es
   nuestra estimación de la probabilidad real de mercado (consenso).
5. Buscamos si ALGUNA casa ofrece una cuota mejor de lo que ese consenso
   justifica -> ahí hay valor esperado positivo (EV+) medible, no una opinión.

Esto NO garantiza ganar la apuesta individual. Es una ventaja estadística
que se paga a largo plazo, jugando muchas veces con disciplina de bankroll.
"""
from dataclasses import dataclass
import re

MIN_BOOKMAKERS = 3  # si hay menos de 3 casas cotizando, no confiamos en el consenso
MIN_EV_TO_FLAG = 0.03  # solo avisamos si el EV estimado supera +3%
MAX_SANE_EV = 0.15  # con varias casas comparadas, un EV real rara vez supera esto.
                     # Si lo supera, lo más probable es un dato corrupto (cuota vieja
                     # de una casa que no actualizó, error de la API, etc), no una
                     # joya escondida. Mejor descartarlo que confiar ciegamente.

# Casas "sharp" (afinan su precio con mucha información, son las más difíciles
# de ganarles). Si alguna está disponible para el partido, la usamos como
# referencia principal de "probabilidad real" en vez de promediar parejo con
# casas recreativas que a veces se equivocan o tardan en actualizar. Así
# trabajan los apostadores profesionales de verdad.
SHARP_BOOKMAKERS = ["Pinnacle"]


@dataclass
class ValueBet:
    match_name: str
    commence_time: str
    market: str        # "h2h" o "totals"
    outcome_name: str  # ej. "Club America" o "Over 2.5"
    best_bookmaker: str
    best_odds: float
    fair_probability: float
    fair_source: str    # "sharp" (Pinnacle) o "consenso" (promedio de casas)
    ev: float
    n_bookmakers: int


def remove_vig(odds_list):
    """Convierte una lista de cuotas decimales de UNA casa (para un mismo mercado)
    en probabilidades sin margen, que suman 100%."""
    implied = [1.0 / o for o in odds_list]
    total = sum(implied)
    return [p / total for p in implied]


def analyze_market(match_name, commence_time, market_key, outcomes_by_bookmaker):
    """
    outcomes_by_bookmaker: dict {bookmaker_name: {outcome_name: cuota_decimal}}
    Devuelve una lista de ValueBet si encuentra valor.
    """
    results = []

    # Nombres de resultados posibles en este mercado (ej. Local/Empate/Visitante)
    all_outcome_names = set()
    for book_odds in outcomes_by_bookmaker.values():
        all_outcome_names.update(book_odds.keys())

    n_books = len(outcomes_by_bookmaker)
    if n_books < MIN_BOOKMAKERS:
        return results

    # Probabilidad "limpia" (sin vig) que da cada casa, por resultado
    clean_probs_per_outcome = {name: [] for name in all_outcome_names}
    sharp_probs_per_outcome = {name: [] for name in all_outcome_names}
    for book_name, book_odds in outcomes_by_bookmaker.items():
        names = list(book_odds.keys())
        odds = [book_odds[n] for n in names]
        # BLINDAJE IMPORTANTE: si esta casa no cotizó TODAS las opciones del
        # mercado (ej. le falta el empate porque solo da moneyline de 2 vías),
        # la excluimos del cálculo de consenso. Mezclar un "quitado de margen"
        # de 2 opciones con uno de 3 opciones distorsiona la probabilidad y
        # puede inflar artificialmente el valor de los equipos chicos.
        # Igual la seguimos usando más abajo para buscar la mejor cuota.
        if set(names) != all_outcome_names:
            continue
        if len(odds) < 2:
            continue
        clean = remove_vig(odds)
        for name, p in zip(names, clean):
            clean_probs_per_outcome[name].append(p)
            if book_name in SHARP_BOOKMAKERS:
                sharp_probs_per_outcome[name].append(p)

    # Si alguna casa "sharp" cotizó este resultado, usamos SU probabilidad como
    # referencia (más confiable). Si no, usamos el promedio de todas las casas.
    fair_prob = {}
    fair_prob_source = {}
    for name in all_outcome_names:
        if sharp_probs_per_outcome.get(name):
            fair_prob[name] = sum(sharp_probs_per_outcome[name]) / len(sharp_probs_per_outcome[name])
            fair_prob_source[name] = "sharp"
        elif clean_probs_per_outcome.get(name):
            fair_prob[name] = sum(clean_probs_per_outcome[name]) / len(clean_probs_per_outcome[name])
            fair_prob_source[name] = "consenso"

    # Buscar la mejor cuota disponible por resultado y comparar contra el consenso
    for outcome_name, fp in fair_prob.items():
        best_odds = 0.0
        best_book = None
        for book_name, book_odds in outcomes_by_bookmaker.items():
            if outcome_name in book_odds and book_odds[outcome_name] > best_odds:
                best_odds = book_odds[outcome_name]
                best_book = book_name

        if best_odds <= 1.0 or fp <= 0:
            continue

        ev = (fp * best_odds) - 1
        if ev > MAX_SANE_EV:
            # Casi seguro es un dato corrupto (cuota desfasada, error de la API).
            # Lo ignoramos en vez de mandarlo como si fuera una joya real.
            continue
        if ev >= MIN_EV_TO_FLAG:
            results.append(
                ValueBet(
                    match_name=match_name,
                    commence_time=commence_time,
                    market=market_key,
                    outcome_name=outcome_name,
                    best_bookmaker=best_book,
                    best_odds=round(best_odds, 2),
                    fair_probability=round(fp, 4),
                    fair_source=fair_prob_source.get(outcome_name, "consenso"),
                    ev=round(ev, 4),
                    n_bookmakers=n_books,
                )
            )

    return results


def is_valid_bet(bet: ValueBet) -> bool:
    """Última línea de defensa: valida que el contenido del pick tenga sentido
    para el mercado que dice ser, sin importar de qué casa/clave rara vino el
    dato original. Si no calza, es más seguro descartarlo que mandarlo mal
    etiquetado (ej. un nombre de equipo apareciendo como si fuera Over/Under)."""
    if bet.market == "totals":
        return bool(re.match(r"^(Over|Under) -?\d+(\.\d+)?$", bet.outcome_name))
    if bet.market == "h2h":
        home, _, away = bet.match_name.partition(" vs ")
        return bet.outcome_name in (home.strip(), away.strip(), "Draw")
    return False  # cualquier otra clave de mercado, no la reconocemos: no se manda


def find_value_bets(events):
    """events: la respuesta cruda de The Odds API (lista de partidos)."""
    all_value_bets = []

    for event in events:
        match_name = f"{event.get('home_team')} vs {event.get('away_team')}"
        commence_time = event.get("commence_time", "")
        bookmakers = event.get("bookmakers", [])

        # Reorganizar por mercado: market_key -> {bookmaker: {outcome: odds}}
        # IMPORTANTE: en "totals" cada outcome trae un "point" (la línea, ej. 2.5,
        # 3.5...). Si no lo incluimos en el nombre, "Under" de la línea 2.5 se
        # mezcla con "Under" de la línea 4.5 como si fueran la misma apuesta,
        # lo cual arma un EV falso y absurdamente alto. Por eso metemos el
        # punto en el nombre del resultado cuando existe.
        markets_data = {}
        for bm in bookmakers:
            book_name = bm.get("title", bm.get("key", "desconocida"))
            for market in bm.get("markets", []):
                mkey = market.get("key")
                outcomes = {}
                for o in market.get("outcomes", []):
                    name = o["name"]
                    # Blindaje: en un mercado "totals" SOLO deben existir
                    # resultados "Over"/"Under". Si aparece cualquier otra
                    # cosa (como "Draw"), es un dato contaminado de la fuente
                    # y lo descartamos en vez de confiar en él a ciegas.
                    if mkey == "totals" and name not in ("Over", "Under"):
                        continue
                    if "point" in o and o["point"] is not None:
                        name = f"{name} {o['point']}"
                    outcomes[name] = o["price"]
                markets_data.setdefault(mkey, {})[book_name] = outcomes

        for mkey, outcomes_by_bookmaker in markets_data.items():
            bets = analyze_market(match_name, commence_time, mkey, outcomes_by_bookmaker)
            all_value_bets.extend(bets)

    # Ordenar de mayor a menor EV
    all_value_bets = [b for b in all_value_bets if is_valid_bet(b)]
    all_value_bets.sort(key=lambda b: b.ev, reverse=True)
    return all_value_bets
