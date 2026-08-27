"""
Bot de picks diarios.
Se ejecuta una vez al día (vía GitHub Actions) y manda a Telegram
las apuestas con valor esperado positivo detectado ese día.

IMPORTANTE - léelo de verdad:
- Esto NO es una promesa de ganancias. Es un filtro estadístico que compara
  cuotas entre casas para detectar precios mal puestos.
- El EV que calcula es un ESTIMADO basado en el consenso de las casas
  disponibles, no una certeza matemática de resultado.
- Nunca apuestes dinero que no puedas perder. Nunca subas el stake para
  recuperar pérdidas.
"""
from datetime import datetime, timezone

from odds_api import fetch_all_odds
from value_finder import find_value_bets, ValueBet
from telegram_sender import send_message

MAX_PICKS_PER_DAY = 8  # evita saturarte de mensajes / sobre-apostar


def suggest_stake(ev: float) -> str:
    """Unidades sugeridas según el tamaño del EV. 1u = 1% del bankroll."""
    if ev >= 0.10:
        return "1u (máx. 1.5u si tienes altísima confianza en el dato)"
    elif ev >= 0.06:
        return "0.75u"
    elif ev >= 0.03:
        return "0.5u"
    return "0.25u (EV al límite, considera pasar)"


def risk_label(bet: ValueBet) -> str:
    if bet.n_bookmakers >= 6 and bet.ev < 0.08:
        return "🟢 CONSERVADORA"
    elif bet.n_bookmakers >= 4:
        return "🟡 RIESGO MEDIO"
    else:
        return "🟠 RIESGO ALTO (pocas casas cotizando, consenso débil)"


def format_bet_line(bet: ValueBet, idx: int) -> str:
    market_label = "1X2/Moneyline" if bet.market == "h2h" else "Total (Over/Under)"
    dt = bet.commence_time.replace("T", " ").replace("Z", " UTC")
    return (
        f"<b>{idx}. {bet.match_name}</b>\n"
        f"🕒 {dt}\n"
        f"Mercado: {market_label}\n"
        f"Selección: <b>{bet.outcome_name}</b>\n"
        f"Mejor cuota: {bet.best_odds} ({bet.best_bookmaker})\n"
        f"Prob. de consenso (sin margen): {bet.fair_probability*100:.1f}%\n"
        f"EV estimado: <b>{bet.ev*100:+.1f}%</b>\n"
        f"Casas comparadas: {bet.n_bookmakers}\n"
        f"Riesgo: {risk_label(bet)}\n"
        f"Stake sugerido: {suggest_stake(bet.ev)}\n"
    )


def build_message(value_bets):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    header = (
        f"📊 <b>Picks del día — {today}</b>\n"
        f"Método: comparación de consenso entre casas de apuestas "
        f"(sin vig) vs. mejor cuota disponible.\n\n"
    )

    if not value_bets:
        return header + (
            "⚪ Hoy no se detectó ninguna apuesta con valor esperado positivo "
            f"claro (umbral mínimo {int(3)}% de EV). Mejor no forzar nada. NO BET."
        )

    picks = value_bets[:MAX_PICKS_PER_DAY]
    body = "\n".join(format_bet_line(b, i + 1) for i, b in enumerate(picks))
    footer = (
        "\n⚠️ Esto es un filtro estadístico, no una garantía. Nunca apuestes "
        "dinero que necesites para gastos. Registra el resultado de cada pick "
        "para medir tu ROI real."
    )
    return header + body + footer


def main():
    events = fetch_all_odds()
    print(f"Partidos encontrados: {len(events)}")

    value_bets = find_value_bets(events)
    print(f"Apuestas con valor detectadas: {len(value_bets)}")

    message = build_message(value_bets)
    send_message(message)
    print("Mensaje enviado a Telegram.")


if __name__ == "__main__":
    main()
