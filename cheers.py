CHEER_MESSAGES = [
    "{player}、ここで1本取り切りたい。",
    "{player}、落ち着いていこう。",
    "{player}、ここが勝負どころ。",
    "{player}、次の判断が大事。",
    "{player}、人数有利を作りたい。",
    "{player}、このラウンドを掴めるか。",
    "{player}、集中していこう。",
    "{player}、流れを変えるキルが欲しい。",
]

ONE_VS_ONE_MESSAGES = [
    "1v1、最後の読み合い。",
    "1対1の最終局面、勝つのはどっちだ。",
    "1v1クラッチタイム、緊張感MAX。",
    "{player1} vs {player2}、ファイナルデュエル。",
]

CLUTCH_MESSAGES = [
    "{player} が 1v{count} のクラッチに挑戦。",
    "{player}、厳しい 1v{count} を背負った。",
    "{player} vs {count}、ここから逆転なるか。",
    "{player} の 1v{count}、見せ場の時間だ。",
    "注目は {player} のクラッチ判断。",
]

KILL_STREAK_MESSAGES = {
    2: [
        "{player} の2キル、勢いが出てきた。",
        "{player} 連続キルで主導権。",
        "{player}、2連取でラウンド優勢。",
    ],
    3: [
        "{player} の3キル、止まらない。",
        "{player}、キルマシーン状態。",
        "{player} の3連キルで流れを作る。",
    ],
    4: [
        "{player} の4キル、あと1人。",
        "{player} がラウンドを支配している。",
        "{player}、4人抜き。ACEなるか。",
    ],
}

ACE_MESSAGES = [
    "{player} がACE達成！",
    "{player} の5キル、完璧なラウンド！",
    "{player} が全員をなぎ倒した！",
    "{player}、圧巻のACE！",
]

HEADSHOT_STREAK_MESSAGES = [
    "{player}、ヘッドショットが止まらない。",
    "{player} のHS連発、精度が高い。",
    "{player}、連続ヘッドショット！",
]

TEAM_KILL_MESSAGES = [
    "[TK] {player}、味方キルに注意。",
    "[TK] {player}、落ち着いていこう。",
    "[TK] {player}、フレンドリーファイア発生。",
]

HELP_MESSAGES = [
    "使えるコマンド:",
    "!help - ヘルプを表示",
    "!coin - コイントス",
    "!shuffle - チームをランダムシャッフル",
    "!pause - 次のラウンド開始時にポーズ",
    "!unpause - ポーズ解除",
    "!omikuji - 今日の運勢とラッキー武器",
    "!tactics - 現在マップの戦術ヒント",
    "!rdy - チームの準備完了を宣言",
    "!lo3 - Live on 3 で試合開始",
]

HELP_MESSAGES_ADMIN = [
    "!cancel - 試合開始をキャンセル（管理者）",
    "!rcon <command> - RCONコマンド実行（管理者）",
    "!smartshuffle - ELO差最小でチーム分け",
    "!kdshuffle - K/D差最小でチーム分け",
    "!kd [name] - K/D確認",
    "!top kd - K/Dランキング",
    "!balancecheck - 現在チームのELO差を確認",
    "!simulate - 現在編成の勝率予測",
    "!top - 勝率ランキング",
    "!top elo - ELOランキング",
    "!stats [name] - 戦績表示",
    "!elo [name] - ELO表示",
    "!omikuji reset - おみくじ履歴リセット（管理者）",
]

OMIKUJI_RESULTS = [
    "大吉: 今日は強気に攻める日。",
    "大吉: エントリーがハマる流れ。先手で主導権を取れる。",
    "大吉: 勝負所の撃ち合いで運が味方する。",
    "大吉: 1vXでも冷静に判断できる日。",
    "中吉: 丁寧なプレーが光る日。",
    "中吉: カバー意識でチームに貢献できる。",
    "中吉: セットプレーの連携が噛み合う。",
    "中吉: 無理せずいけば安定して勝てる。",
    "小吉: 焦らずいけば勝機あり。",
    "小吉: 中盤の判断が勝敗を左右する。",
    "小吉: 丁寧なクリアリングで流れを作れる。",
    "小吉: 1本ずつ積み上げる展開が吉。",
    "末吉: 連携を意識して前進。",
    "末吉: 報告とカバーで試合を整える日。",
    "末吉: 役割を徹底すると結果がついてくる。",
    "凶: 慎重な立ち回りが必要。",
    "凶: 単独行動は控えて味方と動こう。",
    "凶: ピークは一拍置いてから。",
    "大凶: 一つずつ丁寧に積み上げよう。",
    "大凶: 今日は耐える日。無理な勝負は禁物。",
    "大凶: リスク管理を最優先でいこう。",
]

LUCKY_WEAPONS = [
    "AK-47", "M4A1-S", "M4A4", "AWP", "Desert Eagle", "Glock-18", "USP-S",
    "P250", "FAMAS", "Galil AR", "MP9", "MAC-10", "P90", "Nova", "MAG-7",
    "XM1014", "Negev", "SCAR-20", "SSG 08", "Five-SeveN", "Tec-9", "CZ75-Auto",
]

ACCOLADE_MESSAGES = {
    "5k": "{player} がこのラウンドで{value}キル。圧巻のパフォーマンス。",
    "knifekills": "{player} がナイフキルを決めた。",
    "bombcarrierkills": "{player} が爆弾キャリアーをキル。",
    "3k": "{player} が3キルでラウンドを大きく動かした。",
    "mvps": "{player} がMVPを{value}回獲得。",
    "adr": "{player} の平均ダメージは {value}。",
    "firstkills": "{player} がファーストキルを{value}回獲得。",
    "cashspent": "{player} の総消費金額は {value}。",
    "deaths": "{player} は {value}デス。次は取り返したい。",
    "gimme_10": "{player} が10キル未満。次に期待。",
}


def get_accolade_message(accolade_type, player, value):
    key = (accolade_type or "").strip().lower()
    if key in ACCOLADE_MESSAGES:
        msg = ACCOLADE_MESSAGES[key]
        return msg.format(
            player=player,
            value=int(value) if value.is_integer() else round(value, 1),
        )
    # Unknown accolade types are still announced to avoid silent drops.
    shown = int(value) if value.is_integer() else round(value, 1)
    return f"{player} の {accolade_type}: {shown}"
