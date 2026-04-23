# CS2 Server Controller Runbook

## 1. Start

### Single run
```powershell
py -3 controller.py
```

### Auto-restart mode
```powershell
py -3 launcher.py
```

`launcher.py` restarts `controller.py` after exit.
It uses `sys.executable`, so it runs with the same Python interpreter used to start `launcher.py`.

## 2. Important Files

- `controller.py`: main logic (log watch, events, commentary, chat commands)
- `config.yaml`: runtime settings (overrides defaults from `config.py`)
- `rcon_utils.py`: RCON wrapper
- `messages.py`: round flow messages
- `cheers.py`: cheer/kill-streak/accolade messages
- `player_stats.json`: persisted match stats
- `player_elo.json`: persisted elo ratings
- `targets.json`: player name -> steam id map

## 3. Runtime Config (`config.yaml`)

Main keys:

- `admin_steamid`
- `server_password`
- `log_dir`
- `max_rounds`
- `taunt_chance`
- `available_maps`
- `silence_seconds`
- `idle_comment_seconds`
- `commentary_cooldown_seconds`
- `score_flow_cooldown_seconds`
- `round_context_enabled`

Priority:

1. `config.yaml` (if exists)
2. `config.py` defaults

At startup, logs include `config source: ...`.

## 4. Chat Commands

Common:

- `!help`
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

Admin only (`admin_steamid`):

- `!rcon <command>`
- `!reset`
- `!cancel`
- `!omikuji reset`

Notes for team shuffle:

- `!smartshuffle` targets only currently connected non-bot players (`status` based).
- If a connected player has no ELO entry yet, they are initialized to `1000`.
- Team assignment attempts RCON `mp_team_assign "<steamid>" <ct|t>` (plugin-enabled servers), then `mp_restartgame 3`. Players are also instructed via chat to use `jointeam 2` (CT) or `jointeam 3` (T).

## 5. Logs and Health

- Runtime logs: console + `match.log`
- JSON parser auto-recovery log:
  - `JSON parser reset (...)`
- Repeated JSON parse failures trigger RCON health-check.

## 6. Troubleshooting

### No log input

1. Check `config.yaml` -> `log_dir`
2. Check CS2 server log output is enabled
3. If waiting forever for logs, path is likely wrong

### Frequent JSON parse errors

- Controller recovers automatically
- If frequent, inspect server log format and truncation

### Data files

- `player_stats.json` and `player_elo.json` use schema format with `schema_version`
- Legacy formats are still loadable
- Writes are atomic (`tmp -> replace`)

## 7. Verification

```powershell
py -3 -m py_compile controller.py messages.py cheers.py tactics.py launcher.py
py -3 -m unittest -q
```
