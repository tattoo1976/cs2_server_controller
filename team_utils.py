# team_utils.py
import random
import itertools
from player_elo import get_elo
from player_stats import get_steam_id
from rcon_utils import rcon

def elo_shuffle(players):
    """
    指定されたプレイヤーをELOに基づいて2つのチームにシャッフルします。

    シャッフルアルゴリズムは以下のとおりです。

    1. プレイヤーをランダムにシャッフルします。
    2. 2つのチームとそれぞれのスコアを0に初期化します。
    3. シャッフルされたプレイヤーを反復処理し、各プレイヤーを
    ELOの合計が低い方のチームに割り当てます。

    :param players: シャッフルするプレイヤーのリスト
    :type players: list[str]
    :return: 2つのプレイヤー名のリスト。それぞれがチームを表します。
    :rtype: tuple[list[str], list[str]]
    """
    players = list(players)
    random.shuffle(players)

    team1 = []
    team2 = []
    score1 = 0
    score2 = 0

    for p in players:
        elo = get_elo(p)
        if score1 <= score2:
            team1.append(p)
            score1 += elo
        else:
            team2.append(p)
            score2 += elo

    return team1, team2

def smart_shuffle_balanced(players):
    """
    指定されたプレイヤーを2つのチームにシャッフルし、2つのチーム間のELO差が最小になるようにします。

    :param players: シャッフルするプレイヤーのリスト
    :type players: list[str]
    :return: 2つのプレイヤー名のリスト（それぞれがチームを表す）
    :rtype: tuple[list[str], list[str]]
    """
    players = list(players)
    if len(players) < 2:
        return [], []

    best_diff = float("inf")
    best_split = ([], [])

    n = len(players)
    for i in range(n // 2, n // 2 + 2):
        for team1 in itertools.combinations(players, i):
            team2 = [p for p in players if p not in team1]

            elo1 = sum(get_elo(p) for p in team1)
            elo2 = sum(get_elo(p) for p in team2)
            diff = abs(elo1 - elo2)

            if diff < best_diff:
                best_diff = diff
                best_split = (list(team1), team2)

    return best_split

def assign_teams(team_ct, team_t):
    """
    RCON コマンドを使用して、指定されたチームを CT チームと TERRORIST チームに割り当てます。

    :param team_ct: CT チームに割り当てるプレイヤー名のリスト
    :type team_ct: list[str]
    :param team_t: TERRORIST チームに割り当てるプレイヤー名のリスト
    :type team_t: list[str]
    """
    for player in team_ct:
        steam_id = get_steam_id(player)
        if steam_id:
            rcon(f"mp_team_assign {steam_id} ct")

    for player in team_t:
        steam_id = get_steam_id(player)
        if steam_id:
            rcon(f"mp_team_assign {steam_id} t")

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
