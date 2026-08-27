import os
import requests


def get_config():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError(
            "Faltan TELEGRAM_BOT_TOKEN y/o TELEGRAM_CHAT_ID como variables de entorno."
        )
    return token, chat_id


def send_message(text: str):
    token, chat_id = get_config()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    # Telegram limita a 4096 caracteres por mensaje
    chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)] or [text]
    for chunk in chunks:
        resp = requests.post(
            url,
            data={
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        resp.raise_for_status()


def send_pick_with_buttons(text: str, pick_id: str):
    """Manda un pick individual con botones inline Apostar / Paso."""
    token, chat_id = get_config()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ Voy a apostarle", "callback_data": f"bet:{pick_id}"},
            {"text": "❌ Paso", "callback_data": f"pass:{pick_id}"},
        ]]
    }
    resp = requests.post(
        url,
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": keyboard,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def edit_message(chat_id, message_id, new_text: str):
    token, _ = get_config()
    url = f"https://api.telegram.org/bot{token}/editMessageText"
    resp = requests.post(
        url,
        json={
            "chat_id": chat_id,
            "message_id": message_id,
            "text": new_text,
            "parse_mode": "HTML",
        },
        timeout=15,
    )
    resp.raise_for_status()


def answer_callback(callback_query_id, text=""):
    token, _ = get_config()
    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    requests.post(url, json={"callback_query_id": callback_query_id, "text": text}, timeout=10)
