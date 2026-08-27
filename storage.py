"""
Guarda cada pick enviado, si el usuario decidió apostarle o no, y el resultado
final (cuando tú lo marques). Con esto se puede calcular un ROI real y
verificable — la base de cualquier historial creíble si algún día compartes
tus picks públicamente.
"""
import json
import os
from datetime import datetime, timezone

DB_PATH = os.environ.get("PICKS_DB_PATH", "picks_log.json")


def _load():
    if not os.path.exists(DB_PATH):
        return {}
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_pick(pick_id: str, bet_data: dict):
    data = _load()
    data[pick_id] = {
        **bet_data,
        "decision": None,       # "apostar" | "paso" | None (sin responder)
        "resultado": None,      # "ganada" | "perdida" | "push" | None
        "creado": datetime.now(timezone.utc).isoformat(),
    }
    _save(data)


def set_decision(pick_id: str, decision: str):
    data = _load()
    if pick_id in data:
        data[pick_id]["decision"] = decision
        _save(data)
        return True
    return False


def set_resultado(pick_id: str, resultado: str):
    data = _load()
    if pick_id in data:
        data[pick_id]["resultado"] = resultado
        _save(data)
        return True
    return False


def get_pick(pick_id: str):
    return _load().get(pick_id)


def compute_stats():
    """Calcula el historial real: solo cuenta picks donde el usuario dijo
    'apostar' Y ya se marcó el resultado."""
    data = _load()
    apostadas = [
        p for p in data.values()
        if p.get("decision") == "apostar" and p.get("resultado") in ("ganada", "perdida")
    ]
    total = len(apostadas)
    if total == 0:
        return {"total": 0, "ganadas": 0, "win_rate": 0.0, "roi_unidades": 0.0}

    ganadas = sum(1 for p in apostadas if p["resultado"] == "ganada")
    unidades_netas = 0.0
    for p in apostadas:
        stake = p.get("stake_unidades", 1.0)
        if p["resultado"] == "ganada":
            unidades_netas += stake * (p["best_odds"] - 1)
        else:
            unidades_netas -= stake

    return {
        "total": total,
        "ganadas": ganadas,
        "win_rate": round(100 * ganadas / total, 1),
        "roi_unidades": round(unidades_netas, 2),
    }
