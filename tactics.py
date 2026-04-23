import random

TACTICS = {
    "de_dust2": {
        "CT": [
            "Aロング2、B1、ミッド1で情報を取りに行く。",
            "Bトンネルは1人で時間を使い、A側は引き気味に守る。",
            "ミッドを早めにケアしてA/Bの寄りを早くする。",
        ],
        "TERRORIST": [
            "Bラッシュを見せてからカットしてA展開。",
            "ミッドを使ってA/Bどちらにも割れる形を作る。",
            "1ピック取れたら人数有利を使ってエントリー。",
        ],
    },
    "de_inferno": {
        "CT": [
            "バナナ2人で主導権を取り、Aは引き目で守る。",
            "中盤はユーティリティ温存で寄りを意識。",
            "Bは時間を使わせる守り、Aは連携リテイク。",
        ],
        "TERRORIST": [
            "バナナ圧をかけてからAへローテを誘う。",
            "アパートとミッドで同時にプレッシャー。",
            "エントリー後は設置優先でクロスを作る。",
        ],
    },
    "de_ancient": {
        "CT": [
            "ミッド主導で情報を取り、A/Bの寄りを早める。",
            "B入口は遅延重視、無理なピークは避ける。",
            "Aは人数不利を作らない配置でリテイク準備。",
        ],
        "TERRORIST": [
            "Aメインから圧をかけつつミッドで分断。",
            "B実行はスモークとフラッシュを丁寧に。",
            "1キル後は無理せず有利展開で詰める。",
        ],
    },
    "de_mirage": {
        "CT": [
            "ミッド2、A2、B1で開幕情報を取る。",
            "コネクターとジャングルでミッド連携を重視。",
            "Aは引き守り、Bは遅延でローテを待つ。",
        ],
        "TERRORIST": [
            "Aラッシュはフラッシュを合わせて一気に。",
            "ミッド制圧からA/Bスプリットを作る。",
            "Bはスモークで分断してからエントリー。",
        ],
    },
    "default": {
        "CT": [
            "開幕は情報優先、無理な勝負は避ける。",
            "人数有利時はライン維持で時間を使う。",
        ],
        "TERRORIST": [
            "まず1ピックを狙い、有利を作ってから実行。",
            "ユーティリティを合わせて同時に入る。",
        ],
    },
}


def normalize_map_name(map_name: str) -> str:
    """Normalize map name to de_* form used by TACTICS keys."""
    if not map_name:
        return "de_dust2"
    key = map_name.strip().lower()
    if key.startswith("workshop/"):
        key = key.split("/")[-1]
    if not key.startswith("de_"):
        key = f"de_{key}"
    return key


def get_tactic(team: str, map_name: str) -> str:
    """Return a random tactic line for team and map."""
    map_key = normalize_map_name(map_name)
    if map_key not in TACTICS:
        map_key = "default"

    team_tactics = TACTICS[map_key].get(team)
    if not team_tactics:
        return "戦術が見つかりません。基本の連携を意識していきましょう。"

    return random.choice(team_tactics)
