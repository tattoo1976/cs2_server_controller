"""rcon utilities"""
import logging

from config import RCON_HOST, RCON_PASSWORD, RCON_PORT

logger = logging.getLogger(__name__)

try:
    from rcon.source import Client  # type: ignore
    _RCON_IMPORT_ERROR = None
except ModuleNotFoundError as exc:  # pragma: no cover
    Client = None  # type: ignore[assignment]
    _RCON_IMPORT_ERROR = exc


def _ensure_client_available() -> None:
    if Client is not None:
        return
    raise RuntimeError(
        "Python package 'rcon' is not installed. "
        "Install it with: py -3 -m pip install rcon"
    ) from _RCON_IMPORT_ERROR


def rcon(cmd):
    """Run a command on the game server via RCON."""
    try:
        _ensure_client_available()
        with Client(RCON_HOST, RCON_PORT, passwd=RCON_PASSWORD) as c:
            logger.debug("RCON: %s", cmd)
            return c.run(cmd)
    except Exception as e:
        logger.exception("RCON ERROR: %s", e)
        return None


def say(msg):
    """Send a sanitized chat message via RCON."""
    safe = msg.replace('"', "'")
    rcon(f'say "{safe}"')
