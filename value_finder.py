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

MIN_BOOKMAKERS = 3  # si hay menos de 3 casas cotizando, no confiamos en el consenso
MIN_EV_TO_FLAG = 0.03  # solo avisamos si el EV estimado supera +3%


@dataclass
class ValueBet:
    match_name: str
    commence_time: str
    market: str        # "h2h" o "totals"
    outcome_name: str  # ej. "Club America" o "Over 2.5"
    best_bookmaker: str
    best_odds: float
    fair_probability: float
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
    for book_odds in outcomes_by_bookmaker.values():
        names = list(book_odds.keys())
        odds = [book_odds[n] for n in names]
        if len(odds) < 2:
            continue
        clean = remove_vig(odds)
        for name, p in zip(names, clean):
            clean_probs_per_outcome[name].append(p)

    # Consenso = promedio de probabilidades limpias entre casas
    fair_prob = {
        name: sum(probs) / len(probs)
        for name, probs in clean_probs_per_outcome.items()
        if probs
    }

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
                    ev=round(ev, 4),
                    n_bookmakers=n_books,
                )
            )

    return results


def find_value_bets(events):
    """events: la respuesta cruda de The Odds API (lista de partidos)."""
    all_value_bets = []

    for event in events:
        match_name = f"{event.get('home_team')} vs {event.get('away_team')}"
        commence_time = event.get("commence_time", "")
        bookmakers = event.get("bookmakers", [])

        # Reorganizar por mercado: market_key -> {bookmaker: {outcome: odds}}
        markets_data = {}
        for bm in bookmakers:
            book_name = bm.get("title", bm.get("key", "desconocida"))
            for market in bm.get("markets", []):
                mkey = market.get("key")
                outcomes = {
                    o["name"]: o["price"] for o in market.get("outcomes", [])
                }
                markets_data.setdefault(mkey, {})[book_name] = outcomes

        for mkey, outcomes_by_bookmaker in markets_data.items():
            bets = analyze_market(match_name, commence_time, mkey, outcomes_by_bookmaker)
            all_value_bets.extend(bets)

    # Ordenar de mayor a menor EV
    all_value_bets.sort(key=lambda b: b.ev, reverse=True)
    return all_value_bets
