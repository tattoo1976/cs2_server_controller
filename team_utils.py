# team_utils.py
import random
import itertools
import logging
from player_elo import get_elo
from player_stats import get_steam_id, get_kd_ratio
from rcon_utils import rcon

logger = logging.getLogger(__name__)


def balanced_shuffle(players, rating_fn):
    """全組み合わせを探索して rating_fn の合計差が最小になる2チーム分割を返す。"""
    players = list(players)
    if len(players) < 2:
        return [], []

    best_diff = float("inf")
    best_split: tuple = ([], [])

    n = len(players)
    team_sizes = [n // 2] if n % 2 == 0 else [n // 2, n // 2 + 1]
    for i in team_sizes:
        for team1 in itertools.combinations(players, i):
            team2 = [p for p in players if p not in team1]
            diff = abs(sum(rating_fn(p) for p in team1) - sum(rating_fn(p) for p in team2))
            if diff < best_diff:
                best_diff = diff
                best_split = (list(team1), team2)

    return best_split


def smart_shuffle_balanced(players):
    """ELO差が最小になる2チーム分割を返す。"""
    return balanced_shuffle(players, get_elo)


def kd_shuffle_balanced(players):
    """K/D比の合計差が最小になる2チーム分割を返す。"""
    return balanced_shuffle(players, get_kd_ratio)

def assign_teams(team_ct, team_t, rcon_func=None, steam_id_resolver=None):
    """
    RCON コマンドを使用して、指定されたチームを CT チームと TERRORIST チームに割り当てます。

    :param team_ct: CT チームに割り当てるプレイヤー名のリスト
    :type team_ct: list[str]
    :param team_t: TERRORIST チームに割り当てるプレイヤー名のリスト
    :type team_t: list[str]
    """
    sender = rcon_func or rcon
    resolver = steam_id_resolver or get_steam_id

    for player in team_ct:
        steam_id = resolver(player)
        if steam_id:
            cmd = f'mp_team_assign "{steam_id}" ct'
            result = sender(cmd)
            logger.info("team assign CT: %s -> %s result=%r", player, steam_id, result)
        else:
            logger.warning("team assign CT skipped (steam id missing): %s", player)

    for player in team_t:
        steam_id = resolver(player)
        if steam_id:
            cmd = f'mp_team_assign "{steam_id}" t'
            result = sender(cmd)
            logger.info("team assign T: %s -> %s result=%r", player, steam_id, result)
        else:
            logger.warning("team assign T skipped (steam id missing): %s", player)

def predict_winrate(elo_a, elo_b):
    """
    チームAとチームBのELOレーティングに基づいて、その勝率を予測します。

    勝率は以下の式で計算されます。

    1 / (1 + 10 ** ((elo_b - elo_a) / 400))

    ここで、elo_aとelo_bはそれぞれチームAとチームBのELOレーティングです。

    :param elo_a: チームAのELOレーティング
    :type elo_a: int
    :param elo_b: チームBのELOレーティング
    :type elo_b: int
    :return: チームAとチームBの予測勝率
    :rtype: float
    """
    return 1 / (1 + 10 ** ((elo_b - elo_a) / 400))
