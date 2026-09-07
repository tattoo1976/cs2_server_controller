REACTION_MESSAGES = [
    "いや、その通りだと思いますね！",
    "うんうん、まさにそれです！",
    "なるほど、確かに！",
    "だよなーっ！",
]

CHEER_MESSAGES = [
    "{player}、ここで1本取り切れーー！",
    "{player}、いけるぞ、思い切っていこう！",
    "{player}、まさに勝負どころだ！",
    "{player}、次の判断が全てを決める！",
    "{player}、ここで人数有利を作りたい！",
    "{player}、このラウンド掴めるか！？",
    "{player}、集中力を切らすな！",
    "{player}、流れを変える一撃を頼む！",
]

ONE_VS_ONE_MESSAGES = [
    "1v1だーー！最後の読み合い、震えるぞ！",
    "1対1の最終局面！勝つのはどっちだーー！？",
    "1v1クラッチタイム！緊張感MAXだ！",
    "{player1} vs {player2}、ファイナルデュエル開幕！",
]

ONE_VS_ONE_INSIGHT_MESSAGES = [
    "ここは撃ち合いよりポジション取りが勝負を分けますね。",
    "音を聞いてるはずなので、無駄撃ちは禁物です。",
    "どちらも焦って前に出過ぎないことがポイントですね。",
    "有利ポジションを取れた方がまず一歩リードです。",
]

CLUTCH_MESSAGES = [
    "{player} が 1v{count} のクラッチに挑戦だ！！",
    "{player}、厳しい 1v{count} を背負った！ここが見せ場！",
    "{player} vs {count}、ここから逆転なるかーー！？",
    "{player} の 1v{count}、まさに見せ場の時間だ！",
    "注目は {player} のクラッチ判断！信じろ！",
]

CLUTCH_INSIGHT_MESSAGES = [
    "数的不利なので、各個撃破に持ち込めるかがカギですね。",
    "無理に複数を相手にせず、1人ずつ処理したいところです。",
    "時間を味方につける戦い方も選択肢に入りますね。",
    "{player} なら冷静に立ち回れるはずです、期待しましょう。",
]

KILL_STREAK_MESSAGES = {
    2: [
        "{player} の2キル！勢いが出てきたぞ！",
        "{player} 連続キルで主導権を握った！",
        "{player}、2連取でラウンド優勢！",
    ],
    3: [
        "{player} の3キル！止まらないーー！",
        "{player}、完全にキルマシーン状態だ！",
        "{player} の3連キルで流れを完全に掴んだ！",
    ],
    4: [
        "{player} の4キル！あと1人でACEだ！",
        "{player} がこのラウンドを完全に支配している！",
        "{player}、4人抜き！ACEなるかーー！？",
    ],
}

ACE_MESSAGES = [
    "{player} がACE達成ーーー！！",
    "{player} の5キル、完璧すぎるラウンド！！",
    "{player} が敵を全員なぎ倒したーー！",
    "{player}、圧巻のACE！これは伝説だ！",
]

ACE_INSIGHT_MESSAGES = [
    "5人全員のポジションを把握してないとできない動きですね。",
    "エイムだけでなく、状況判断が完璧だったと思います。",
    "これは今日のハイライト間違いなしですね。",
    "{player} の勢い、次のラウンドにも注目です。",
]

HEADSHOT_STREAK_MESSAGES = [
    "{player}、ヘッドショットが止まらないーー！",
    "{player} のHS連発、精度がえげつない！",
    "{player}、連続ヘッドショット！化け物か！？",
]

TEAM_KILL_MESSAGES = [
    "[TK] {player}、味方キルは落ち着いていこう！",
    "[TK] {player}、気持ちはわかるが冷静に！",
    "[TK] {player}、フレンドリーファイア発生！気をつけろ！",
]

TEAM_KILL_INSIGHT_MESSAGES = [
    "{player}、それはさすがにダメですね。武器の切り替え、ちゃんと確認しましょう。",
    "これは完全に不注意です。{player}、次は絶対に気をつけてください。",
    "{player}、フラッシュもそうですが、味方の位置は常に頭に入れておくべきですね。",
]

ELO_UPSET_MESSAGES = [
    "{killer} が格上の {victim} を撃破！これは大金星だーー！",
    "ELO差をひっくり返したーー！{killer}、ナイスピック！",
    "{killer} が {victim} を落とした！番狂わせの一発だ！",
]

HELP_MESSAGES = [
    "使えるコマンド:",
    "!svr_help - ヘルプを表示",
    "!coin - コイントス",
    "!shuffle - チームをランダムシャッフル",
    "!pause - 次のラウンド開始時にポーズ",
    "!unpause - ポーズ解除",
    "!omikuji - 今日の運勢とラッキー武器",
    "!tactics - 現在マップの戦術ヒント",
    "!rdy - チームの準備完了を宣言",
    "!lo3 [番号] [practice] - Live on 3 で試合開始（番号で実況コンビ指定、practiceで戦績・ELO記録なしの練習モード）",
    "!prac - warmup終了＆freezetime3秒（撃ち合い練習用）",
]

HELP_MESSAGES_ADMIN = [
    "!cancel - 試合開始をキャンセル（管理者）",
    "!rcon <command> - RCONコマンド実行（管理者）",
    "!smartshuffle - ELO差最小でチーム分け",
    "!kdshuffle - K/D差最小でチーム分け",
    "!wingman - 接続中4人でWingman(2v2)モードに切替＆チーム分け",
    "!dm [マップ名] - デスマッチモードに切替",
    "!retake [マップ名] - Retakesモードに切替",
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
