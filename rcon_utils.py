"""rcon utilities"""
import logging

from rcon.source import Client  # type: ignore
from config import RCON_HOST, RCON_PORT, RCON_PASSWORD

logger = logging.getLogger(__name__)


def rcon(cmd):
    """
    RCON サーバーでコマンドを実行します。

    引数:
    cmd (str): 実行するコマンド。

    戻り値:
    Optional[str]: コマンドの出力。エラーが発生した場合は None を返します。
    """
    try:
        with Client(RCON_HOST, RCON_PORT, passwd=RCON_PASSWORD) as c:
            logger.debug("RCON: %s", cmd)
            return c.run(cmd)
    except Exception as e:
        logger.exception("RCON ERROR: %s", e)
        return None


def say(msg):
    # サーバーにチャットメッセージを送信
    # メッセージ内の二重引用符をエスケープして安全に送信
    """
    チャットメッセージをサーバーに送信します。

    メッセージは、潜在的な問題を防ぐため、二重引用符を一重引用符に置き換えた上でサーバーに送信されます。

    :param msg: 送信するメッセージ
    :type msg: 文字列
    """
    safe = msg.replace('"', "'")
    rcon(f'say "{safe}"')
