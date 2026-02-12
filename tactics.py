# tactics.py

import random

TACTICS = {
    "de_dust2": {
        "CT": [
            "Aロング2人、Bサイト2人、ミッド1人でバランス守備！",
            "Bトンネルに1人忍ばせて奇襲を狙え！",
            "Aショートにスモーク→1人詰めて情報取り！",
            "Bサイトに3人固めて、ラッシュ対策！",
            "ミッドAWPで開幕ピック狙い！",
        ],
        "TERRORIST": [
            "Bラッシュで一気に制圧！スモークを忘れずに！",
            "Aロングをゆっくり進行、CTの油断を突け！",
            "ミッドからCTを割ってAとBに分散攻撃！",
            "Aショートにスモーク→ジャンプピークで様子見！",
            "CTに聞こえるように足音立てて、逆サイトへGO！",
        ],
    },
    "de_inferno": {
        "CT": [
            "バナナ2人、Aサイト3人で初動制圧！",
            "アパートに1人潜伏して奇襲を狙え！",
            "バナナにモロトフ→詰めて情報取り！",
            "AロングAWPで開幕ピック狙い！",
            "Bサイトに3人固めて、ラッシュ警戒！",
        ],
        "TERRORIST": [
            "バナナを取ってからBラッシュ！",
            "アパートから静かにAサイトを崩せ！",
            "ミッドにスモーク→アーチを抜けてCT裏へ！",
            "Aフェイク→バナナからBに切り替え！",
            "アパートでジャンプピークしてからの突撃！",
        ],
    },
    "de_ancient": {
        "CT": [
            "ミッド制圧が命！1人はドンピシャでピーク！",
            "Bロングにスモーク→詰めて情報取り！",
            "Aサイトに3人、Bに2人で固めて様子見！",
            "ミッドAWPで開幕ピック狙い！",
            "CTスポーンからAメインにフラッシュ→詰め！",
        ],
        "TERRORIST": [
            "Aメインからスモーク＆フラッシュで突撃！",
            "ミッドを取ってからBに分岐、CT混乱必至！",
            "Bロングを静かに進行→CT裏取り狙い！",
            "Aフェイク→ミッドからBに切り替え！",
            "スモークでCTを分断してAサイトを包囲！",
        ],
    },
    "de_mirage": {
        "CT": [
            "ミッド1人、A2人、B2人で王道配置！",
            "コネクターとジャングルを制圧して主導権を握れ！",
            "Bアパートに1人潜伏→裏取り狙い！",
            "Aラッシュ警戒でランプ＆パレスに2人配置！",
            "ミッドAWPで開幕ピック→すぐ引いて守備固め！",
        ],
        "TERRORIST": [
            "Aラッシュでフラッシュ祭り！",
            "ミッド→コネクター→Aの3点攻め！",
            "Bアパートから静かに侵入→爆速設置！",
            "ミッド制圧→CTを分断してAとBに分散！",
            "パレスから1人だけ出してフェイク→ミッド集合！",
        ],
    },
    "default": {
        "CT": [
            "CT側の基本戦術：守って勝つ！",
            "情報を取ってから動こう！",
            "スモークとフラッシュを活用して時間稼ぎ！",
        ],
        "TERRORIST": [
            "T側の基本戦術：攻めて勝つ！",
            "1人フェイク→4人本命で奇襲！",
            "スローラウンドでCTの動きを見極めよう！",
        ],
    }
}


import random


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

def get_tactic(team, map_name):
    """
    指定マップにおける指定チームのランダムな戦術を取得します。

    引数:
    team (文字列): 戦術を取得するチーム (CT または TERRORIST)
    map_name (文字列): マップ名

    戻り値:
    文字列: 指定マップにおける指定チームのランダムな戦術、または戦術が見つからない場合はメッセージ
    """
    map_key = normalize_map_name(map_name)
    if map_key not in TACTICS:
        map_key = "default"

    team_tactics = TACTICS[map_key].get(team)
    if not team_tactics:
        return "戦術が見つかりませんでした…作戦会議を！"

    return random.choice(team_tactics)
