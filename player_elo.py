import json
import logging
import os
import tempfile
from typing import Any, Dict

logger = logging.getLogger(__name__)

PLAYER_ELO: Dict[str, int] = {}
PLAYER_ELO_FILE = "player_elo.json"
PLAYER_ELO_SCHEMA_VERSION = 2


def _atomic_write_json(path: str, payload: dict) -> None:
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def _normalize_elo_payload(raw: Any) -> Dict[str, int]:
    if not isinstance(raw, dict):
        return {}

    if "schema_version" in raw and "ratings" in raw and isinstance(raw["ratings"], dict):
        source = raw["ratings"]
    elif "ratings" in raw and isinstance(raw["ratings"], dict):
        source = raw["ratings"]
    else:
        # Legacy layout: {"PLAYER": 1000, ...}
        source = raw

    result: Dict[str, int] = {}
    for name, elo in source.items():
        if not isinstance(name, str):
            continue
        try:
            result[name] = int(elo)
        except (TypeError, ValueError):
            continue
    return result


def load_elo() -> None:
    """Load ELO ratings from disk with legacy compatibility."""
    global PLAYER_ELO
    if not os.path.exists(PLAYER_ELO_FILE):
        PLAYER_ELO.clear()
        return

    with open(PLAYER_ELO_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    PLAYER_ELO.clear()
    PLAYER_ELO.update(_normalize_elo_payload(raw))


def save_elo() -> None:
    """Save ELO ratings as schema-versioned JSON."""
    filtered = {k: v for k, v in PLAYER_ELO.items() if not is_bot(k)}
    payload = {
        "schema_version": PLAYER_ELO_SCHEMA_VERSION,
        "ratings": filtered,
    }
    _atomic_write_json(PLAYER_ELO_FILE, payload)
    logger.debug("saved ELO: %s", json.dumps(payload, indent=2, ensure_ascii=False))


def get_elo(player: str) -> int:
    return PLAYER_ELO.get(player.upper(), 1000)


def update_elo(winner_team: str, ct_players: list[str], t_players: list[str], k: int = 25) -> None:
    winner_team = winner_team.upper()
    ct_players = [p for p in ct_players if not is_bot(p)]
    t_players = [p for p in t_players if not is_bot(p)]

    for player in ct_players:
        name = player.upper()
        PLAYER_ELO.setdefault(name, 1000)
        PLAYER_ELO[name] += k if winner_team == "CT" else -k

    for player in t_players:
        name = player.upper()
        PLAYER_ELO.setdefault(name, 1000)
        PLAYER_ELO[name] += k if winner_team == "TERRORIST" else -k

    logger.debug("ELO updated: %s", PLAYER_ELO)
    save_elo()


def get_all_elo() -> Dict[str, int]:
    return PLAYER_ELO.copy()


def is_bot(name: str) -> bool:
    u = name.upper()
    return u.startswith("BOT") or u == "BOT"
