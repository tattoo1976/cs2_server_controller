import json
import logging
import os
import tempfile
from typing import Any, Dict

logger = logging.getLogger(__name__)

PLAYER_STATS: Dict[str, Dict[str, Any]] = {}
TARGETS: Dict[str, str] = {}

PLAYER_STATS_FILE = "player_stats.json"
TARGETS_FILE = "targets.json"
PLAYER_STATS_SCHEMA_VERSION = 2


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


def _normalize_stats_payload(raw: Any) -> Dict[str, Dict[str, Any]]:
    if not isinstance(raw, dict):
        return {}

    if "schema_version" in raw and "players" in raw and isinstance(raw["players"], dict):
        return raw["players"]

    if "players" in raw and isinstance(raw["players"], dict):
        return raw["players"]

    # Legacy layout: {"PLAYER": {"wins": 1, "losses": 0}, ...}
    return {
        str(name): stats
        for name, stats in raw.items()
        if isinstance(name, str) and isinstance(stats, dict)
    }


def load_stats() -> None:
    """Load player stats from disk with legacy compatibility."""
    global PLAYER_STATS
    if not os.path.exists(PLAYER_STATS_FILE):
        PLAYER_STATS.clear()
        logger.info("player stats file not found; starting with empty stats")
        return

    with open(PLAYER_STATS_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    PLAYER_STATS.clear()
    PLAYER_STATS.update(_normalize_stats_payload(raw))
    logger.info("loaded player stats: %d players", len(PLAYER_STATS))


def save_stats() -> None:
    """Save stats as schema-versioned JSON."""
    payload = {
        "schema_version": PLAYER_STATS_SCHEMA_VERSION,
        "players": PLAYER_STATS,
    }
    _atomic_write_json(PLAYER_STATS_FILE, payload)
    logger.info("saved player stats: %d players", len(PLAYER_STATS))


def load_targets() -> None:
    """Load name->steam mapping used for player resolution."""
    global TARGETS
    if not os.path.exists(TARGETS_FILE):
        TARGETS.clear()
        logger.info("targets file not found; starting with empty targets")
        return

    with open(TARGETS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    TARGETS.clear()
    if isinstance(data, dict):
        # Normalize keys to uppercase for stable lookups.
        TARGETS.update({str(k).upper(): str(v) for k, v in data.items()})
    logger.info("loaded targets: %d entries", len(TARGETS))


def save_targets() -> None:
    """Save name->steam mapping."""
    try:
        _atomic_write_json(TARGETS_FILE, TARGETS)
        logger.info("saved targets: %d entries", len(TARGETS))
    except Exception as e:  # pragma: no cover - defensive
        logger.exception("failed to save targets: %s", e)


def get_steam_id(player: str) -> str | None:
    """Get steam id for player from stats first, then targets fallback."""
    name = player.upper()
    stats = PLAYER_STATS.get(name)
    if stats:
        return stats.get("steam_id")
    return TARGETS.get(name)


def is_bot(player: str) -> bool:
    """Best-effort bot detection."""
    steam_id = get_steam_id(player)
    return steam_id == "BOT" or steam_id is None
