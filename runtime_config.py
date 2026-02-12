from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from config import ADMIN_STEAMID, AVAILABLE_MAPS, LOG_DIR, MAX_ROUNDS, TAUNT_CHANCE


@dataclass(frozen=True)
class RuntimeConfig:
    admin_steamid: str = ADMIN_STEAMID
    available_maps: List[str] = None  # type: ignore[assignment]
    log_dir: str = LOG_DIR
    max_rounds: int = MAX_ROUNDS
    taunt_chance: float = TAUNT_CHANCE
    silence_seconds: int = 30
    idle_comment_seconds: int = 30
    commentary_cooldown_seconds: int = 10
    score_flow_cooldown_seconds: int = 8
    round_context_enabled: bool = True
    config_source: str = "config.py(defaults)"

    def __post_init__(self) -> None:
        if self.available_maps is None:
            object.__setattr__(self, "available_maps", list(AVAILABLE_MAPS))


def _parse_scalar(raw: str) -> Any:
    value = raw.strip()
    if not value:
        return ""
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
        return value[1:-1]
    lower = value.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _parse_simple_yaml(text: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    current_list_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- "):
            if current_list_key is None:
                continue
            item = _parse_scalar(line[2:])
            data.setdefault(current_list_key, [])
            if isinstance(data[current_list_key], list):
                data[current_list_key].append(item)
            continue
        current_list_key = None
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if not value:
            data[key] = []
            current_list_key = key
        else:
            data[key] = _parse_scalar(value)
    return data


def load_runtime_config(path: str = "config.yaml") -> RuntimeConfig:
    """Load runtime settings.

    Precedence:
    1. `config.yaml` (if present)
    2. Defaults from `config.py`
    """
    cfg_path = Path(path)
    if not cfg_path.exists():
        return RuntimeConfig(config_source="config.py(defaults)")

    text = cfg_path.read_text(encoding="utf-8")
    parsed: Dict[str, Any] = _parse_simple_yaml(text)

    return RuntimeConfig(
        admin_steamid=str(parsed.get("admin_steamid", ADMIN_STEAMID)),
        available_maps=list(parsed.get("available_maps", list(AVAILABLE_MAPS))),
        log_dir=str(parsed.get("log_dir", LOG_DIR)),
        max_rounds=int(parsed.get("max_rounds", MAX_ROUNDS)),
        taunt_chance=float(parsed.get("taunt_chance", TAUNT_CHANCE)),
        silence_seconds=int(parsed.get("silence_seconds", 30)),
        idle_comment_seconds=int(parsed.get("idle_comment_seconds", 30)),
        commentary_cooldown_seconds=int(parsed.get("commentary_cooldown_seconds", 10)),
        score_flow_cooldown_seconds=int(parsed.get("score_flow_cooldown_seconds", 8)),
        round_context_enabled=bool(parsed.get("round_context_enabled", True)),
        config_source=str(cfg_path),
    )
