import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

HISTORY_FILE = Path(__file__).with_name("match_history.json")


def append_match(record: dict) -> None:
    data: list = []
    if HISTORY_FILE.exists():
        try:
            data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.exception("match_history.json が壊れていたため退避して作り直します")
            HISTORY_FILE.replace(HISTORY_FILE.with_suffix(".corrupt.json"))
            data = []
    data.append(record)
    tmp = HISTORY_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, HISTORY_FILE)
