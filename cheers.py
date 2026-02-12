CHEER_MESSAGES = [
    "{player}、ここで1本取り切りたい。",
    "{player}、落ち着いていこう。",
    "{player}、勝負どころだ。",
    "{player}、今の判断いいぞ。",
    "{player}、次の当たりに備えよう。",
    "{player}、丁寧に前進したい。",
    "{player}、ここは集中していこう。",
    "{player}、流れを引き寄せたい。",
]

ONE_VS_ONE_MESSAGES = [
    "1v1、最後の読み合い。",
    "1対1の最終局面、勝つのはどっちだ。",
    "1v1クラッチタイム、緊張感MAX。",
    "{player1} vs {player2}、ファイナルデュエル。",
]

CLUTCH_MESSAGES = [
    "{player} が1v{count}のクラッチに挑戦。",
    "{player}、厳しい1v{count}を背負った。",
    "{player} vs {count}、ここから逆転なるか。",
    "{player}の1v{count}、見せ場の時間だ。",
    "勝負は {player} のクラッチ次第。",
]

KILL_STREAK_MESSAGES = {
    2: [
        "{player} が2キル、勢いが出てきた。",
        "{player} 連続キルで主導権を握る。",
        "{player} の2連続キル。",
    ],
    3: [
        "{player} が3キル、止まらない。",
        "{player} キルマシーン状態。",
        "{player} の3連キルで流れを作る。",
    ],
    4: [
        "{player} が4キル、あと1人。",
        "{player} がラウンドを支配している。",
        "{player} 4人抜き、圧巻。",
    ],
}

ACE_MESSAGES = [
    "{player} がACE達成！",
    "{player} の5キル、完璧なラウンド。",
    "{player} が全員をなぎ倒した。",
    "{player} ACE、会場が沸く。",
]

HEADSHOT_STREAK_MESSAGES = [
    "{player}、ヘッドショットが止まらない。",
    "{player} のHS連発、精度が高い。",
    "{player} が3連続ヘッドショット。",
]

TEAM_KILL_MESSAGES = [
    "[TK] {player}、味方キルに注意。",
    "[TK] {player}、落ち着いていこう。",
    "[TK] {player}、フレンドリーファイア発生。",
]

HELP_MESSAGES = [
    "使えるコマンド:",
    "!help - このヘルプを表示",
    "!coin - コイントス",
    "!shuffle - チームシャッフル",
    "!omikuji - 今日の運勢とラッキー武器",
    "!tactics - 現在マップの戦術ヒント",
    "!rdy - チームの準備完了を宣言",
    "!lo3 - Live on 3 で試合開始",
]

HELP_MESSAGES_ADMIN = [
    "!cancel - 試合開始をキャンセル（管理者）",
    "!rcon <command> - RCONコマンド実行（管理者）",
    "!eloshuffle - Elo基準でチーム分け",
    "!smartshuffle - バランス重視でチーム分け",
    "!balancecheck - 現在チームのElo差確認",
    "!simulate - 現在構成での勝率予測",
    "!top - 勝率ランキング表示",
    "!top elo - Eloランキング表示",
    "!stats [name] - 戦績表示",
    "!elo [name] - Elo表示",
    "!omikuji reset - おみくじ履歴リセット（管理者）",
]

OMIKUJI_RESULTS = [
    "大吉: 今日は強気に行ける日。",
    "中吉: 安定したプレーが光る日。",
    "小吉: 丁寧に進めれば勝機あり。",
    "末吉: 無理せず連携重視で。",
    "凶: 慎重な判断が必要な日。",
    "大凶: 焦らず一つずつ積み上げよう。",
]

LUCKY_WEAPONS = [
    "AK-47", "M4A1-S", "M4A4", "AWP", "Desert Eagle", "Glock-18", "USP-S",
    "P250", "FAMAS", "Galil AR", "MP9", "MAC-10", "P90", "Nova", "MAG-7",
    "XM1014", "Negev", "SCAR-20", "SSG 08", "Five-SeveN", "Tec-9", "CZ75-Auto",
]

ACCOLADE_MESSAGES = {
    "5k": "{player} が1ラウンドで{value}キル！圧巻のパフォーマンス。",
    "knifekills": "{player} がナイフキルを決めた！",
    "bombcarrierkills": "{player} が爆弾キャリアーを仕留めた。",
    "3k": "{player} が3キルでラウンドを引き寄せた。",
    "mvps": "{player} がMVPを獲得。",
    "adr": "{player} の平均ダメージは {value}。",
    "firstkills": "{player} がファーストキルを {value} 回獲得。",
    "cashspent": "{player} が積極投資で勝負。",
    "deaths": "{player} は厳しい展開でも最後まで戦った。",
    "gimme_10": "{player} が10キル未満。次に期待。",
}


def get_accolade_message(accolade_type, player, value):
    if accolade_type in ACCOLADE_MESSAGES:
        msg = ACCOLADE_MESSAGES[accolade_type]
        return msg.format(
            player=player,
            value=int(value) if value.is_integer() else round(value, 1),
        )
    return None
