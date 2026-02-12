import re

# 新しい正規表現
CHAT_CMD_RE = re.compile(
    r'L \d+/\d+/\d+ - \d+:\d+:\d+: "([^<]+)<\d+><(\[U:1:\d+\])><(CT|TERRORIST)>" say "!?(\w+)(?:\s+(.*))?$'
)

test_lines = [
    'L 01/03/2026 - 18:18:05: "test_user<2><[U:1:100000]><TERRORIST>" say "!rdy"',
    'L 01/03/2026 - 18:18:00: "test_user<2><[U:1:100000]><TERRORIST>" say "rdy"',
    'L 01/03/2026 - 18:18:10: "test_user<2><[U:1:100000]><CT>" say "!rdy"',
    'L 01/03/2026 - 18:18:10: "test_user<2><[U:1:100000]><CT>" say "!help hello world"',
]

print("=== 修正版CHAT_CMD_RE テスト ===\n")

for line in test_lines:
    match = CHAT_CMD_RE.search(line)
    print(f"行: {line}")
    if match:
        print(f"  ✓ マッチ成功")
        print(f"  グループ: {match.groups()}")
        player_name, steam_id, team, command, arg = match.groups()
        print(f"    プレイヤー: {player_name}")
        print(f"    Steam ID: {steam_id}")
        print(f"    チーム: {team}")
        print(f"    コマンド: {command}")
        print(f"    引数: {arg}")
    else:
        print(f"  ✗ マッチなし")
    print()

