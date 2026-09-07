# CS2 Server Controller 運用手順書

## 1. 起動

### 単発起動
```powershell
py -3 controller.py
```

### 自動再起動モード
```powershell
py -3 launcher.py
```

`launcher.py` は `controller.py` 終了後に再起動します。  
`sys.executable` を使うため、`launcher.py` を起動したのと同じ Python で動作します。

## 2. 重要ファイル

- `controller.py`: メイン処理（ログ監視、イベント処理、実況、チャットコマンド）
- `config.yaml`: 実行時設定（`config.py` のデフォルトを上書き）
- `rcon_utils.py`: RCON ラッパー
- `messages.py`: ラウンド進行系メッセージ
- `cheers.py`: キル連続・アコレード等メッセージ
- `player_stats.json`: 戦績保存
- `player_elo.json`: ELO 保存
- `targets.json`: プレイヤー名 -> SteamID の対応表

## 3. 実行時設定（`config.yaml`）

主なキー:

- `admin_steamid`
- `log_dir`
- `max_rounds`
- `taunt_chance`
- `available_maps`
- `silence_seconds`
- `idle_comment_seconds`
- `commentary_cooldown_seconds`
- `score_flow_cooldown_seconds`
- `round_context_enabled`

優先順位:

1. `config.yaml`（存在する場合）
2. `config.py` のデフォルト

起動ログに `config source: ...` が出ます。

## 4. チャットコマンド

共通:

- `!svr_help`
- `!commentary on|off`
- `!debug`
- `!map <name|random>`
- `!coin`
- `!ct` / `!t`
- `!rdy`
- `!lo3`
- `!shuffle`
- `!omikuji`
- `!elo [name]`
- `!top`
- `!top elo`
- `!stats [name]`
- `!tactics`
- `!smartshuffle`
- `!balancecheck`
- `!simulate`

管理者のみ（`admin_steamid`）:

- `!rcon <command>`
- `!reset`
- `!cancel`
- `!omikuji reset`

チーム分けコマンド補足:

- `!smartshuffle` は、`status` で取得した接続中の非BOTプレイヤーのみ対象です。
- ELO 未登録プレイヤーは自動で `1000` で初期化されます。
- 振り分けは RCON `mp_team_assign "<steamid>" <ct|t>` を送信し、その後 `mp_restartgame 1` を実行します。

## 5. ログとヘルスチェック

- 実行ログ: コンソール + `match.log`
- JSON パーサ自動復旧ログ:
  - `JSON parser reset (...)`
- JSON 解析エラーが連続すると RCON ヘルスチェックを実行します。

## 6. トラブルシューティング

### ログが読めない

1. `config.yaml` の `log_dir` を確認
2. CS2 サーバ側でログ出力が有効か確認
3. 起動後ずっと待機する場合はパス誤りの可能性が高い

### JSON 解析エラーが頻発する

- コントローラは自動復旧します
- 頻発する場合はサーバログ形式やログ欠損を確認してください

### データファイル

- `player_stats.json` / `player_elo.json` は `schema_version` 付き形式で保存
- 旧形式も読み込み対応
- 保存はアトミック書き込み（tmp -> replace）

## 7. 動作確認

```powershell
py -3 -m py_compile controller.py messages.py cheers.py tactics.py launcher.py
py -3 -m unittest -q
```
