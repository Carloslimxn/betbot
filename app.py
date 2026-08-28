"""
App principal para desplegar en Render (o cualquier host que soporte un
proceso web siempre activo).

Hace 3 cosas:
1. Una vez al día (hora configurable) busca valor y te manda cada pick
   con botones "Apostar" / "Paso".
2. Recibe el clic de esos botones vía webhook y lo guarda.
3. Comandos manuales por chat:
   /resultado <id> ganada|perdida  -> registra el resultado real
   /stats                          -> te da tu historial real (win rate, ROI)
"""
import os
import uuid
from datetime import datetime, timezone

from flask import Flask, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler

from odds_api import fetch_all_odds
from value_finder import find_value_bets
from main import format_bet_line, risk_label, suggest_stake  # reutilizamos formato
import telegram_sender as tg
import storage

app = Flask(__name__)

DAILY_HOUR_UTC = int(os.environ.get("DAILY_HOUR_UTC", "13"))  # 13 UTC ~ 7am CDMX
MAX_PICKS_PER_DAY = 8


def run_daily_job():
    print(f"[{datetime.now(timezone.utc)}] corriendo job diario...")
    events = fetch_all_odds()
    value_bets = find_value_bets(events)[:MAX_PICKS_PER_DAY]

    if not value_bets:
        tg.send_message("⚪ Hoy no se detectó ninguna apuesta con valor esperado positivo claro. NO BET.")
        return

    nuevos = [
        b for b in value_bets
        if not storage.was_already_sent_today(b.match_name, b.market, b.outcome_name)
    ]

    if not nuevos:
        print("Todos los picks de hoy ya se habían mandado antes. No se repite nada.")
        return

    for bet in nuevos:
        pick_id = uuid.uuid4().hex[:8]
        text = format_bet_line(bet, 1)  # numeración simple, es un pick por mensaje
        storage.save_pick(pick_id, {
            "match_name": bet.match_name,
            "market": bet.market,
            "outcome_name": bet.outcome_name,
            "best_odds": bet.best_odds,
            "best_bookmaker": bet.best_bookmaker,
            "ev": bet.ev,
            "stake_unidades": _stake_to_number(suggest_stake(bet.ev)),
        })
        tg.send_pick_with_buttons(text, pick_id)


def _stake_to_number(stake_label: str) -> float:
    # extrae el primer número del texto "0.5u" -> 0.5
    for token in stake_label.replace("u", " ").split():
        try:
            return float(token)
        except ValueError:
            continue
    return 1.0


@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json(force=True)

    # --- Clics de botones ---
    if "callback_query" in update:
        cq = update["callback_query"]
        data = cq.get("data", "")
        chat_id = cq["message"]["chat"]["id"]
        message_id = cq["message"]["message_id"]
        original_text = cq["message"].get("text", "")

        if ":" in data:
            action, pick_id = data.split(":", 1)
            decision = "apostar" if action == "bet" else "paso"
            storage.set_decision(pick_id, decision)
            tag = "✅ MARCASTE: VOY A APOSTARLE" if decision == "apostar" else "❌ MARCASTE: PASO"
            tg.edit_message(chat_id, message_id, f"{original_text}\n\n{tag}")
            tg.answer_callback(cq["id"], "Guardado.")
        return jsonify(ok=True)

    # --- Comandos de texto ---
    if "message" in update and "text" in update["message"]:
        text = update["message"]["text"].strip()

        if text.startswith("/stats"):
            stats = storage.compute_stats()
            msg = (
                f"📈 <b>Tu historial real</b>\n"
                f"Apuestas registradas: {stats['total']}\n"
                f"Ganadas: {stats['ganadas']}\n"
                f"Win rate: {stats['win_rate']}%\n"
                f"ROI acumulado: {stats['roi_unidades']:+.2f}u"
            )
            tg.send_message(msg)

        elif text.startswith("/resultado"):
            parts = text.split()
            if len(parts) == 3 and parts[2] in ("ganada", "perdida", "push"):
                ok = storage.set_resultado(parts[1], parts[2])
                tg.send_message("✅ Resultado guardado." if ok else "⚠️ No encontré ese ID de pick.")
            else:
                tg.send_message("Uso: /resultado <id_del_pick> ganada|perdida|push")

    return jsonify(ok=True)


@app.route("/run-now", methods=["GET", "POST"])
def run_now():
    """Para probar manualmente sin esperar al horario programado."""
    run_daily_job()
    return jsonify(ok=True)


@app.route("/", methods=["GET"])
def health():
    return "bot vivo"


scheduler = BackgroundScheduler(timezone="UTC")
scheduler.add_job(run_daily_job, "cron", hour=DAILY_HOUR_UTC, minute=0)
scheduler.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
