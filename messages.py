ROUND_EVENTS = {
    "first_round": [
        "ファーストラウンド開始。落ち着いて入りましょう。",
        "開幕ラウンド、先手を取って流れを作りたい。",
        "最初の1本は大きい。丁寧に行こう。",
    ],
    "side_switch": [
        "サイドチェンジ。ここから後半戦です。",
        "攻守交代、リセットして次の流れを作ろう。",
        "サイド変更、ここからが本番。",
    ],
    "overtime_start": [
        "延長戦スタート。勝負はここから。",
        "オーバータイム突入。集中していこう。",
        "決着は延長へ。1本の重みが増します。",
    ],
    "overtime_late": [
        "延長後半。ミスが命取りになる場面。",
        "OT後半、勝負どころです。",
        "ここで取る1本が試合を動かす。",
    ],
}

SILENCE_MESSAGES = {
    "even": [
        "静かな展開。次の接敵が勝負を分けそうです。",
        "膠着状態、どちらが先に崩すか。",
    ],
    "ct_advantage": [
        "CT人数有利。ライン維持で時間を使いたい。",
        "CT有利の形。無理せず確実に。",
    ],
    "t_advantage": [
        "T人数有利。セットして一気に行きたい。",
        "T有利、連携で詰めていける形。",
    ],
    "balanced": [
        "人数は互角。1キルの価値が高い。",
        "互角のまま終盤へ。判断勝負です。",
    ],
}

ONE_V_ONE_MESSAGES = [
    "1v1、最後の読み合い。",
    "最終局面の1v1、勝つのはどっちだ。",
    "1v1クラッチタイム。会場の空気が張りつめる。",
]

SCORE_FLOW_MESSAGES = {
    "ct_match_point": [
        "CTがマッチポイント。スコア {ct}-{t}",
        "あと1本でCT勝利。{ct}-{t}",
    ],
    "t_match_point": [
        "Tがマッチポイント。スコア {ct}-{t}",
        "あと1本でT勝利。{ct}-{t}",
    ],
    "tie": [
        "スコアは並んだ。{ct}-{t}",
        "振り出しに戻った。{ct}-{t}",
    ],
    "comeback": [
        "追い上げ成功。{ct}-{t}",
        "流れが戻ってきた。{ct}-{t}",
    ],
    "ct_streak": [
        "CTが{count}連取中。",
        "CTの連勝が続く。{count}本目。",
    ],
    "t_streak": [
        "Tが{count}連取中。",
        "Tの連勝が続く。{count}本目。",
    ],
}

ROUND_CONTEXT_MESSAGES = {
    "pistol_round": [
        "ピストルラウンド。立ち上がりが重要。{ct}-{t}",
        "ピストル勝利が流れを左右する。{ct}-{t}",
    ],
    "anti_eco_ct": [
        "CTは対エコ想定。丁寧に取りたい。{ct}-{t}",
        "CT有利装備。取りこぼし注意。{ct}-{t}",
    ],
    "anti_eco_t": [
        "Tは対エコ想定。確実にラウンドを取りたい。{ct}-{t}",
        "T装備有利。落ち着いて進行。{ct}-{t}",
    ],
    "full_buy": [
        "フルバイラウンド。正面勝負です。{ct}-{t}",
        "両チームフルバイ。撃ち合い注目。{ct}-{t}",
    ],
    "ot_point": [
        "OTの重要ラウンド。{ct}-{t}",
        "延長の山場。ここを取れるか。{ct}-{t}",
    ],
}

OPENING_PLAYER_DUEL_MESSAGES = [
    "今日の見どころ、CT {ct_player} と T {t_player} の撃ち合い。",
    "まずはこの2人に注目。CT {ct_player}、T {t_player}。",
    "本日のキープレイヤーは CT {ct_player} と T {t_player}。",
    "序盤の主役候補、{ct_player} 対 {t_player}。",
    "注目マッチアップ: {ct_player} vs {t_player}。",
    "最初の流れを作るのは誰か。CT {ct_player}、T {t_player}。",
    "さぁ、開始です！CTの希望、{ct_player}！Tの切り札、{t_player}！", 
    "CTの先鋒は {ct_player}、Tの猛者は {t_player}！さあ、勝負の行方は！？", 
    "今回の注目選手は…CT側 {ct_player} vs T側 {t_player}！", 
    "戦いの火蓋が切られた！{ct_player} と {t_player}、どちらが先に仕掛けるか！？",
]
