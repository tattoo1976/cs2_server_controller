# controller.py
"""Documentation."""

from __future__ import annotations

import glob
import json
import logging
import os
import random
import re
import sys
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, TextIO

from cheers import (
    ACE_MESSAGES,
    ACE_INSIGHT_MESSAGES,
    CHEER_MESSAGES,
    REACTION_MESSAGES,
    CLUTCH_MESSAGES,
    CLUTCH_INSIGHT_MESSAGES,
    ONE_VS_ONE_MESSAGES,
    ONE_VS_ONE_INSIGHT_MESSAGES,
    HEADSHOT_STREAK_MESSAGES,
    KILL_STREAK_MESSAGES,
    TEAM_KILL_MESSAGES,
    TEAM_KILL_INSIGHT_MESSAGES,
    HELP_MESSAGES,
    HELP_MESSAGES_ADMIN,
    OMIKUJI_RESULTS,
    LUCKY_WEAPONS,
    get_accolade_message,
)
from announcers import ANNOUNCER_DUOS
from messages import (
    ROUND_EVENTS,
    ROUND_EVENT_INSIGHT_MESSAGES,
    SILENCE_MESSAGES,
    SILENCE_INSIGHT_MESSAGES,
    SCORE_FLOW_MESSAGES,
    ROUND_CONTEXT_MESSAGES,
    OPENING_PLAYER_DUEL_MESSAGES,
)
from player_elo import get_all_elo, get_elo, load_elo, save_elo, update_elo, ensure_players_initialized
from player_stats import (
    PLAYER_STATS,
    TARGETS,
    load_stats,
    load_targets,
    save_stats,
    save_targets,
    is_bot,
    increment_kills,
    increment_deaths,
    get_kills,
    get_deaths,
    get_kd_ratio,
)
from state import MatchState
from runtime_config import RuntimeConfig, load_runtime_config
from taunts import TAUNT_MESSAGES, TAUNT_MESSAGES_BY_PERSONA
from tactics import get_tactic, normalize_map_name, get_map_display_name
from team_utils import (
    assign_teams,
    predict_winrate,
    smart_shuffle_balanced,
    kd_shuffle_balanced,
    wingman_shuffle_balanced,
)

PLAYER_TEAM_RE = re.compile(r'"(?P<name>[^"<]+)<\d+><(?P<steam_id>[^>]+)><(?P<team>CT|TERRORIST)>"')
MATCH_STATUS_RE = re.compile(r'MatchStatus: Score: \d+:\d+ on map ".*?" RoundsPlayed: (\d+)', re.IGNORECASE)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# Configure module logger.
logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)

# File logging.
file_handler = logging.FileHandler("match.log", encoding="utf-8")
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Patterns
KILL_REGEX = re.compile(
    r'"(?P<killer>[^"<]+)<\d+><(?P<killer_steam_id>[^>]+)><(?P<killer_team>CT|TERRORIST)>".*?'
    r'killed.*?"(?P<victim>[^"<]+)<\d+><(?P<victim_steam_id>[^>]+)><(?P<victim_team>CT|TERRORIST)>".*?'
    r'with "(?P<weapon>[^"]+)"',
    re.IGNORECASE,
)

ACCOLADE_RE = re.compile(
    r'ACCOLADE, FINAL: \{(?P<type>[^}]+)\},\s+(?P<player>[^<]+)<\d+>,\s+VALUE: (?P<value>[\d.]+)',
    re.IGNORECASE,
)

DISCONNECT_RE = re.compile(
    r'"(?P<name>[^"<]+)<\d+><(?P<steam_id>[^>]+)><(?P<team>CT|TERRORIST)>" disconnected'
)

CONNECT_RE = re.compile(
    r'"(?P<name>[^"<]+)<\d+><(?P<steam_id>\[U:1:\d+\])><[^>]*>" connected.*'
)

# `status` output differs a bit across CS2/server builds (column widths, extra
# leading fields, etc.). Rather than anchoring to the exact leading columns
# (which broke entirely on at least one server build in the wild), just look
# for a quoted name immediately followed by a steamid bracket anywhere on the
# line. This is specific enough to avoid false positives elsewhere in the
# `status` output while being resilient to column-layout differences.
STATUS_RE = re.compile(
    r'"(?P<name>[^"]+)"\s*\[(?P<steam_id>U:1:\d+)\]',
    re.IGNORECASE,
)

MATCH_STATUS_RE = re.compile(r'MatchStatus: Score: \d+:\d+ on map ".*?" RoundsPlayed: (\d+)', re.IGNORECASE)

MAP_CHANGE_RE = re.compile(r'Loading map "([^\"]+)"')
ROUND_START_RE = re.compile(r'Round_Start|Starting Freeze period', re.IGNORECASE)
# Reliable signal that we're back in pre-match warmup. If a previous match
# never reached a proper Game Over (e.g. cut short for testing, or via
# mp_restartgame instead of a real match), live_started can otherwise stay
# stuck True, letting commentary fire again before the next !lo3.
WARMUP_START_RE = re.compile(r'World triggered "Warmup_Start"', re.IGNORECASE)
CHAT_CMD_RE = re.compile(
    r'L \d+/\d+/\d+ - \d+:\d+:\d+: "([^<]+)<\d+><(\[U:1:\d+\])><(CT|TERRORIST)>" say "!?(\w+)(?:\s+(.*))?"'
)
GAME_OVER_RE = re.compile(r'Game Over: .*?score\s+(\d+):(\d+)', re.IGNORECASE)

TEAM_ASSIGN_RE = re.compile(
    r'"(?P<name>[^"<]+)<\d+><(?P<steam_id>[^>]+)><[^>]*>" joined team "(?P<team>CT|TERRORIST)"'
)
# Common join-time line: `"name<uid><steamid>" switched from team <Unassigned> to <TEAM>`.
# Without this, a player's team is only learned from an incidental later line
# (a purchase, a kill) via PLAYER_TEAM_RE, so a round-start alive-count rebuilt
# from `player_teams` can undercount real players and trigger a false 1v1/clutch call.
SWITCH_TEAM_RE = re.compile(
    r'"(?P<name>[^"<]+)<\d+><(?P<steam_id>[^>]*)>" switched from team <[^>]*> to <(?P<team>CT|TERRORIST)>'
)
STEAM_ID_RE = re.compile(r"^\[U:1:\d+\]$")

CHAT_RE = re.compile(
    r'"(?P<name>.+?)<\d+><(?P<steamid>\[U:1:(?P<accountid>\d+)\])><(?P<team>\w+)>" say "(?P<text>.+)"'
)

TEAM_T = "TERRORIST"
TEAM_CT = "CT"
WARMUP_GUIDE_INTERVAL_SECONDS = 60
WARMUP_GUIDE_MESSAGES = [
    "使えるコマンドは !svr_help で確認できます",
    "試合開始は両チーム !rdy のあと !lo3 です",
    "マップ変更は !map dust2 のように入力してください",
    "チーム分けは !shuffle で実行できます",
]


class Controller:
    current_log_path: Optional[str] = None
    log_fp: Optional[TextIO] = None

    """Documentation."""

    def __init__(
        self,
        rcon_func: Callable[[str], Optional[str]],
        say_func: Callable[[str], None],
        state: Optional[MatchState] = None,
        settings: Optional[RuntimeConfig] = None,
    ) -> None:
        """Documentation."""
        self.rcon = rcon_func
        self._say_raw = say_func
        self._last_say_at = 0.0
        self._min_say_interval_seconds = 0.35
        self.say = self._say_throttled
        self.state = state or MatchState()
        self.settings = settings or load_runtime_config()
        self.state.WIN_ROUNDS = self._effective_max_rounds() // 2 + 1
        self.json_buffer: List[str] = []
        self.in_json_block: bool = False
        self.event_handlers: List[tuple[re.Pattern[str], Callable[[re.Match[str], str], None]]] = []
        self.setup_event_listeners()

    def _say_throttled(self, msg: str) -> None:
        """Throttle chat output to avoid command/message queue bursts."""
        now = time.time()
        wait = self._min_say_interval_seconds - (now - self._last_say_at)
        if wait > 0:
            time.sleep(wait)
        self._say_raw(msg)
        self._last_say_at = time.time()

    def _say_duo(self, commentary_msg: str, insight_msg: str) -> None:
        """Announce a big moment as a 実況 -> 解説 -> 実況 three-line exchange."""
        self.say(f"実況: {commentary_msg}")
        self.say(f"解説: {insight_msg}")
        reaction = self._pick_reaction()
        if reaction:
            self.say(f"実況: {reaction}")

    def _pick_reaction(self) -> Optional[str]:
        """Short 実況 reaction line following the 解説's remark, in this match's persona voice."""
        duo = self._current_duo()
        pool = duo.get("reactions") if duo else None
        if pool:
            return random.choice(pool)
        return random.choice(REACTION_MESSAGES) if REACTION_MESSAGES else None

    def _effective_max_rounds(self) -> int:
        """Regulation round count for the current match (Wingman uses its own count)."""
        if self.state.wingman_mode:
            return self.settings.wingman_max_rounds
        return self.settings.max_rounds

    def _say_commentary(self, msg: str) -> None:
        """Broadcast-flavor commentary line, prefixed like the play-by-play voice.

        Not for direct command responses (!svr_help, !stats, etc.) — only for
        unprompted match-flow narration.
        """
        self.say(f"実況: {msg}")

    def _current_duo(self) -> Optional[dict]:
        idx = self.state.announcer_duo_index
        if idx is None:
            return None
        return ANNOUNCER_DUOS[idx]

    def _duo_pool(self, category: str, subkey=None):
        """Look up this match's persona pool for `category`/`subkey`, or None if unset/missing."""
        duo = self._current_duo()
        if not duo:
            return None
        node = duo.get(category)
        if subkey is not None and isinstance(node, dict):
            node = node.get(subkey)
        return node or None

    def _pick(self, generic_list, category: str, subkey=None) -> str:
        """Pick a line from this match's persona pool, falling back to the generic pool."""
        pool = self._duo_pool(category, subkey)
        return random.choice(pool) if pool else random.choice(generic_list)

    def _pick_pair(self, generic_commentary, generic_insight, category: str, subkey=None):
        """Like `_pick` but for a commentary+insight duo line."""
        pool = self._duo_pool(category, subkey)
        if pool:
            commentary = random.choice(pool["commentary"])
            insight = random.choice(pool["insight"])
        else:
            commentary = random.choice(generic_commentary)
            insight = random.choice(generic_insight)
        return commentary, insight

    def setup_event_listeners(self) -> None:
        """Initialize the log event dispatcher table."""
        self.event_handlers = [
            (ROUND_START_RE, self._handle_round_start_event),
            (KILL_REGEX, self._handle_kill_event),
            (CHAT_RE, self._handle_chat_identity_event),
            (CONNECT_RE, self._handle_connect_event),
            (ACCOLADE_RE, self._handle_accolade_event),
            (MATCH_STATUS_RE, self._handle_match_status_event),
            (GAME_OVER_RE, self._handle_game_over_event),
            (MAP_CHANGE_RE, self._handle_map_change_event),
            (WARMUP_START_RE, self._handle_warmup_start_event),
            (CHAT_CMD_RE, self._handle_chat_command_event),
            (PLAYER_TEAM_RE, self._handle_player_team_event),
            (SWITCH_TEAM_RE, self._handle_player_team_event),
            (TEAM_ASSIGN_RE, self._handle_team_assign_event),
            (DISCONNECT_RE, self._handle_disconnect_event),
        ]

    def ensure_rcon_alive(self) -> None:
        """Best-effort health check for the RCON connection."""
        try:
            self.rcon("echo controller_ready")
        except Exception:
            logger.exception("RCON health-check failed")

    def apply_server_password(self) -> None:
        """Apply join password via RCON if configured."""
        pw = (self.settings.server_password or "").strip()
        if not pw:
            logger.info("server password is empty; password join is disabled")
            return
        safe = pw.replace('"', "")
        self.rcon(f'sv_password "{safe}"')
        logger.info("server password has been applied")

    def reset_command_flags(self) -> None:
        """Reset transient command flags after a map change."""
        self.state.coin_used = False
        self.state.coin_winner = None
        self.state.side_select_active = False
        self.state.rdy_ct = False
        self.state.rdy_t = False

    def _reset_json_parser(self, reason: str, recover: bool = False) -> None:
        if recover:
            self.state.json_recovery_count += 1
            logger.warning(
                "JSON parser reset (%s). recoveries=%d errors=%d",
                reason,
                self.state.json_recovery_count,
                self.state.json_parse_error_count,
            )
        self.json_buffer = []
        self.in_json_block = False

    # --- small helpers ---
    def get_random_warning_target(self, exclude_name: str) -> Optional[str]:
        """Documentation."""
        exclude_id = TARGETS.get(exclude_name.upper())
        candidates = [
            name for name, steam_id in TARGETS.items()
            if steam_id != exclude_id
        ]
        return random.choice(candidates) if candidates else None

    def parse_status_output(self, output: str) -> set[str]:
        """Documentation."""
        logger.debug("parse_status_output start")
        current_name_to_steam: Dict[str, str] = {}
        current_steam_to_name: Dict[str, str] = {}
        for line in output.splitlines():
            match = STATUS_RE.search(line)
            if match:
                name = match.group("name")
                steam_id = f"[{match.group('steam_id')}]"
                TARGETS[name.upper()] = steam_id
                current_name_to_steam[name] = steam_id
                current_steam_to_name[steam_id] = name
        if current_name_to_steam:
            self.state.name_to_steam = current_name_to_steam
            self.state.steam_to_name = current_steam_to_name
        elif output.strip():
            logger.warning(
                "status output was present but no players were parsed; raw sample: %r",
                output[:500],
            )
        save_targets()
        logger.info("rcon status から TARGETS を更新しました")
        return set(current_name_to_steam.keys())

    def get_connected_players(self) -> List[str]:
        """Return currently connected non-bot players in normalized form."""
        return sorted(self._refresh_connected_player_names())

    def _tracked_player_names(self) -> set[str]:
        """Return non-bot players from the controller's current team/name cache."""
        names: set[str] = set()
        for source in (self.state.player_teams, self.state.temp_player_teams):
            for key, team in source.items():
                if team not in (TEAM_CT, TEAM_T):
                    continue
                name = self.state.steam_to_name.get(key, key)
                if STEAM_ID_RE.match(name):
                    continue
                if not self._is_bot_player(name):
                    names.add(name)
        return names

    def _reset_special_game_mode_cvars(self) -> None:
        """Unconditionally clear any Wingman/Deathmatch/Retakes leftovers.

        Cvars like sv_skirmish_id and the weapon-buy restrictions persist
        across changelevel and aren't touched by the mode we're about to
        enter, so relying on "did we think we were in mode X" flags is
        fragile (they can desync from reality, e.g. going straight from
        !retake to !dm). Just always reset everything -- the extra rcon
        calls are harmless when there was nothing to clean up.
        """
        self.state.wingman_mode = False
        self.state.dm_mode = False
        self.state.retake_mode = False
        self.rcon("sv_skirmish_id 0")
        self.rcon("game_mode 1")
        self.rcon("bot_kick")
        self.rcon("mp_weapons_allow_smgs -1")
        self.rcon("mp_weapons_allow_heavy -1")

    def _apply_team_shuffle(self, team_ct: List[str], team_t: List[str], label: str) -> None:
        """Announce teams, attempt RCON assignment, and restart."""
        self.say(f"CT ({label}): " + ", ".join(team_ct))
        self.say(f"T ({label}): " + ", ".join(team_t))
        # Disable auto-balance so manual team selections survive the restart.
        self.rcon("mp_autoteambalance 0")
        self.rcon("mp_limitteams 0")
        # Best-effort RCON assignment (works on plugin-enabled servers).
        assign_teams(team_ct, team_t, self.rcon, self._resolve_player_steam_id)
        # Tell players which team to join in case RCON assignment has no effect.
        self.say("チーム移動: CT -> jointeam 2 / T -> jointeam 3 をコンソールで入力")
        self.rcon("mp_restartgame 3")

    def _start_wingman_match(self, players: List[str]) -> None:
        """Finish Wingman setup (bots/weapon cvars/shuffle) after the map reload."""
        connected = self.get_connected_players()
        if connected:
            players = connected
        if not (1 <= len(players) <= 4):
            self.say(f"Wingman再読み込み後に人数が変わりました（現在{len(players)}人）。もう一度 !wingman してください")
            return

        added = ensure_players_initialized(players, 1000)
        if added:
            logger.info("ELO初期値を追加: %s", ", ".join(added))

        self.state.wingman_mode = True
        self.state.WIN_ROUNDS = self._effective_max_rounds() // 2 + 1
        self.rcon(f"mp_maxrounds {self.settings.wingman_max_rounds}")

        team_a, team_b = wingman_shuffle_balanced(players)
        bots_needed_ct = team_a.count("BOT")
        bots_needed_t = team_b.count("BOT")
        if bots_needed_ct or bots_needed_t:
            # bot_quota is a *target* the engine actively maintains on its own
            # (it was already auto-filling empty slots with bots before we
            # ever sent a command). Kick whatever it already added, then pin
            # the quota to our target and let the engine's own fill logic do
            # the adding -- calling bot_add_ct/t on top of that as well is
            # what caused a doubled bot count in an earlier attempt.
            self.rcon("bot_kick")
            self.rcon("mp_autoteambalance 0")
            self.rcon("mp_limitteams 0")
            self.rcon("bot_quota_mode normal")
            self.rcon(f"bot_quota {bots_needed_ct + bots_needed_t}")
            self.rcon("bot_difficulty 3")
            # Keep bot loadouts sane: pistols, rifles, and snipers (AWP/Scout;
            # CS2 has no separate cvar to exclude the auto-snipers) only.
            self.rcon("mp_weapons_allow_pistols -1")
            self.rcon("mp_weapons_allow_rifles -1")
            self.rcon("mp_weapons_allow_snipers -1")
            self.rcon("mp_weapons_allow_smgs 0")
            self.rcon("mp_weapons_allow_heavy 0")

        self._apply_team_shuffle(team_a, team_b, label="Wingman")
        bot_note = ""
        total_bots = bots_needed_ct + bots_needed_t
        if total_bots:
            bot_note = f"（BOTを{total_bots}体追加）"
        self.say(
            f"Wingmanモード（MR{self.settings.wingman_max_rounds // 2}）に切り替えました{bot_note}。"
            "準備ができたら !rdy → !lo3 で開始してください"
        )

    def _recently_connected_names(self) -> set[str]:
        """Return non-bot names seen via connect/disconnect log events (real-time, may lead `status` by a beat)."""
        names: set[str] = set()
        for name in self.state.name_to_steam:
            if STEAM_ID_RE.match(name):
                continue
            if not self._is_bot_player(name):
                names.add(name.upper())
        return names

    def _refresh_connected_player_names(self) -> set[str]:
        """Refresh status and return currently connected non-bot names (upper-cased)."""
        output = self.rcon("status")
        if not output:
            return self._recently_connected_names()
        names = self.parse_status_output(output)
        connected = {name.upper() for name in names if not is_bot(name)}
        # `status` is a point-in-time snapshot and can momentarily miss a player who
        # just connected (log-tailed connect events update name_to_steam immediately,
        # before the next `status` poll picks them up). Union them in so a shuffle
        # run right after someone joins post-warmup doesn't drop them.
        connected |= self._recently_connected_names()
        if connected:
            return connected
        tracked = self._tracked_player_names()
        if tracked:
            logger.warning("falling back to tracked players because status parsing returned no players: %s", sorted(tracked))
        return tracked

    def _resolve_player_steam_id(self, player_name: str) -> Optional[str]:
        """Resolve a valid SteamID from runtime mappings/targets."""
        steam_id = self.state.name_to_steam.get(player_name) or TARGETS.get(player_name.upper())
        if steam_id and STEAM_ID_RE.match(steam_id):
            return steam_id
        return None

    def _is_bot_player(self, player_name: str, steam_id: Optional[str] = None) -> bool:
        """Detect bots by steam id first, then by conventional BOT name prefix."""
        if steam_id == "BOT":
            return True
        resolved = steam_id or self.state.name_to_steam.get(player_name) or TARGETS.get(player_name.upper())
        if resolved == "BOT":
            return True
        return player_name.upper().startswith("BOT")

    def _canonical_player_name(self, player_name: str, steam_id: Optional[str] = None) -> str:
        """Return a stable display name for a player, preferring steam-id mapping."""
        if steam_id:
            mapped = self.state.steam_to_name.get(steam_id)
            if mapped:
                return mapped
            for known_name, known_steam in self.state.name_to_steam.items():
                if known_steam == steam_id:
                    return known_name
        return player_name

    @staticmethod
    def _discard_case_insensitive(name_set: set[str], target_name: str) -> None:
        upper = target_name.upper()
        for existing in [n for n in name_set if n.upper() == upper]:
            name_set.discard(existing)

    def _add_alive_player(self, team: str, name: str, steam_id: Optional[str] = None) -> None:
        canonical = self._canonical_player_name(name, steam_id)
        if team == TEAM_CT:
            self._discard_case_insensitive(self.state.alive_ct, canonical)
            self._discard_case_insensitive(self.state.alive_t, canonical)
            self.state.alive_ct.add(canonical)
        elif team == TEAM_T:
            self._discard_case_insensitive(self.state.alive_t, canonical)
            self._discard_case_insensitive(self.state.alive_ct, canonical)
            self.state.alive_t.add(canonical)

    def _discard_alive_player(self, team: str, name: str, steam_id: Optional[str] = None) -> None:
        canonical = self._canonical_player_name(name, steam_id)
        if team == TEAM_CT:
            self._discard_case_insensitive(self.state.alive_ct, canonical)
            self._discard_case_insensitive(self.state.alive_ct, name)
        elif team == TEAM_T:
            self._discard_case_insensitive(self.state.alive_t, canonical)
            self._discard_case_insensitive(self.state.alive_t, name)
        else:
            self._discard_case_insensitive(self.state.alive_ct, canonical)
            self._discard_case_insensitive(self.state.alive_t, canonical)
            self._discard_case_insensitive(self.state.alive_ct, name)
            self._discard_case_insensitive(self.state.alive_t, name)

    def _backfill_player_stats_steam_id(self, player_name: str, steam_id: str) -> None:
        """Keep PLAYER_STATS steam_id populated for later result aggregation."""
        if not (player_name and steam_id and STEAM_ID_RE.match(steam_id)):
            return
        name = player_name.upper()
        stats = PLAYER_STATS.setdefault(name, {"wins": 0, "losses": 0})
        if stats.get("steam_id") != steam_id:
            stats["steam_id"] = steam_id

    def today_str(self) -> str:
        """Documentation."""
        return datetime.now().strftime("%Y-%m-%d")

    def handle_round_stats(self, data: Dict[str, Any]) -> None:
        """Documentation."""
        fields = [f.strip() for f in data.get("fields", "").split(",")]
        for player_id, stats_str in data.get("players", {}).items():
            values = [v.strip() for v in stats_str.split(",")]
            player_data = dict(zip(fields, values))

            name = self.state.accountid_to_name.get(player_data.get("accountid", "").strip())
            if not name:
                continue

            # Optional flavor message.
            if (
                self.should_commentate()
                and name.lower() == "tkmi"
                and self.state.rounds_played in (11, 23)
                and not self.state.round_awp_taunt_sent
            ):
                self._say_commentary("tkmiさん、そろそろ AWP 見たいですね")
                self.state.round_awp_taunt_sent = True

            if int(player_data.get("3k", 0)) > 0:
                self.state.accolades.append(("3k", name, int(player_data.get("3k", 0))))
            if int(player_data.get("4k", 0)) > 0:
                self.state.accolades.append(("4k", name, int(player_data.get("4k", 0))))
            if int(player_data.get("5k", 0)) > 0:
                self.state.accolades.append(("5k", name, int(player_data.get("5k", 0))))

    def handle_json_line(self, json_data: Dict[str, Any]) -> None:
        """Documentation."""
        if json_data.get("name") == "round_stats":
            try:
                prev_round = self.state.round_number
                prev_ct = self.state.ct_score
                prev_t = self.state.t_score
                self.state.round_number = int(json_data.get("round_number", self.state.round_number))
                self.state.t_score = int(json_data.get("score_t", self.state.t_score))
                self.state.ct_score = int(json_data.get("score_ct", self.state.ct_score))
                self.debug_print(
                    f"JSON round_stats: round={self.state.round_number}, CT={self.state.ct_score}, T={self.state.t_score}"
                )

                self._maybe_announce_side_switch(prev_round=prev_round)
                self._comment_on_score_flow(prev_ct=prev_ct, prev_t=prev_t)

                self.handle_round_stats(json_data)

            except Exception:  # pragma: no cover - defensive
                logger.exception("JSON処理に失敗しました")

    def _leader(self, ct_score: int, t_score: int) -> Optional[str]:
        if ct_score > t_score:
            return TEAM_CT
        if t_score > ct_score:
            return TEAM_T
        return None

    def _emit_commentary(
        self,
        message: str,
        key: str,
        *,
        cooldown_seconds: Optional[int] = None,
        once_per_round: bool = False,
        insight_message: Optional[str] = None,
    ) -> bool:
        """Emit commentary with cooldown/once-per-round guards."""
        if not self.should_commentate():
            return False
        if once_per_round and key in self.state.round_comment_keys:
            return False

        now = time.time()
        cooldown = (
            self.settings.commentary_cooldown_seconds
            if cooldown_seconds is None
            else cooldown_seconds
        )
        last_at = self.state.last_comment_at.get(key, 0.0)
        if cooldown > 0 and now - last_at < cooldown:
            return False

        if insight_message:
            self._say_duo(message, insight_message)
        else:
            self._say_commentary(message)
        self.state.last_comment_at[key] = now
        if once_per_round:
            self.state.round_comment_keys.add(key)
        return True

    def _buy_tier(self, weapons: set[str]) -> str:
        if not weapons:
            return "unknown"
        normalized = {w.lower() for w in weapons}
        full_buy = {
            "ak47", "m4a1", "m4a1_silencer", "m4a4", "famas", "galilar",
            "aug", "sg556", "awp", "scar20", "g3sg1",
        }
        force_weapons = {
            "mp9", "mac10", "ump45", "mp7", "mp5sd", "p90", "bizon",
            "nova", "xm1014", "mag7", "sawedoff",
            "deagle", "revolver", "five_seven", "tec9", "cz75a",
        }
        pistols = {
            "glock", "hkp2000", "p250", "elite", "usp_silencer", "fiveseven",
            "tec9", "cz75a", "deagle", "revolver",
        }
        utility = {"hegrenade", "smokegrenade", "flashbang", "molotov", "incgrenade", "knife", "taser"}

        if normalized & full_buy:
            return "full"
        if normalized & force_weapons:
            return "force"
        if normalized.issubset(pistols | utility):
            return "pistol"
        return "eco"

    def _comment_on_round_context(self, winner: Optional[str]) -> None:
        if not self.settings.round_context_enabled:
            return
        if self.state.round_number <= 0:
            return

        ct_buy = self._buy_tier(self.state.round_weapons_ct)
        t_buy = self._buy_tier(self.state.round_weapons_t)

        if self.state.round_number in (1, 13):
            msg = self._pick(ROUND_CONTEXT_MESSAGES["pistol_round"], "round_context", "pistol_round").format(
                ct=self.state.ct_score,
                t=self.state.t_score,
            )
            self._emit_commentary(msg, f"pistol_round_{self.state.round_number}", once_per_round=True)
            return

        if ct_buy == "full" and t_buy in {"eco", "pistol"}:
            msg = self._pick(ROUND_CONTEXT_MESSAGES["anti_eco_ct"], "round_context", "anti_eco_ct").format(ct=self.state.ct_score, t=self.state.t_score)
            self._emit_commentary(msg, f"anti_eco_ct_{self.state.round_number}", once_per_round=True)
        elif t_buy == "full" and ct_buy in {"eco", "pistol"}:
            msg = self._pick(ROUND_CONTEXT_MESSAGES["anti_eco_t"], "round_context", "anti_eco_t").format(ct=self.state.ct_score, t=self.state.t_score)
            self._emit_commentary(msg, f"anti_eco_t_{self.state.round_number}", once_per_round=True)
        elif ct_buy == "full" and t_buy == "full":
            msg = self._pick(ROUND_CONTEXT_MESSAGES["full_buy"], "round_context", "full_buy").format(ct=self.state.ct_score, t=self.state.t_score)
            self._emit_commentary(msg, f"full_buy_{self.state.round_number}", once_per_round=True)

        if self.state.round_number > self._effective_max_rounds() and abs(self.state.ct_score - self.state.t_score) <= 1:
            msg = self._pick(ROUND_CONTEXT_MESSAGES["ot_point"], "round_context", "ot_point").format(
                ct=self.state.ct_score,
                t=self.state.t_score,
            )
            self._emit_commentary(
                msg,
                f"ot_point_{self.state.round_number}",
                once_per_round=True,
                cooldown_seconds=self.settings.score_flow_cooldown_seconds,
            )

    def _comment_on_score_flow(self, prev_ct: int, prev_t: int) -> None:
        """Commentate round momentum based on score transitions."""
        if not self.should_commentate():
            return
        if self.state.round_number <= 0:
            return
        if self.state.round_number == self.state.last_flow_comment_round:
            return

        ct_delta = self.state.ct_score - prev_ct
        t_delta = self.state.t_score - prev_t
        if ct_delta == 0 and t_delta == 0:
            return

        winner: Optional[str] = None
        if ct_delta > 0 and t_delta == 0:
            winner = TEAM_CT
        elif t_delta > 0 and ct_delta == 0:
            winner = TEAM_T
        else:
            return

        if winner == self.state.streak_team:
            self.state.streak_count += 1
        else:
            self.state.streak_team = winner
            self.state.streak_count = 1

        prev_leader = self._leader(prev_ct, prev_t)
        now_leader = self._leader(self.state.ct_score, self.state.t_score)

        if self.state.ct_score == self.state.WIN_ROUNDS - 1 and not self.state.ct_match_point_announced:
            msg = random.choice(SCORE_FLOW_MESSAGES["ct_match_point"]).format(
                ct=self.state.ct_score,
                t=self.state.t_score,
            )
            self._emit_commentary(
                msg,
                "ct_match_point",
                cooldown_seconds=self.settings.score_flow_cooldown_seconds,
                once_per_round=True,
            )
            self.state.ct_match_point_announced = True
        elif self.state.t_score == self.state.WIN_ROUNDS - 1 and not self.state.t_match_point_announced:
            msg = random.choice(SCORE_FLOW_MESSAGES["t_match_point"]).format(
                ct=self.state.ct_score,
                t=self.state.t_score,
            )
            self._emit_commentary(
                msg,
                "t_match_point",
                cooldown_seconds=self.settings.score_flow_cooldown_seconds,
                once_per_round=True,
            )
            self.state.t_match_point_announced = True
        elif now_leader is None and prev_leader is not None:
            msg = random.choice(SCORE_FLOW_MESSAGES["tie"]).format(
                ct=self.state.ct_score,
                t=self.state.t_score,
            )
            self._emit_commentary(
                msg,
                "tie",
                cooldown_seconds=self.settings.score_flow_cooldown_seconds,
                once_per_round=True,
            )
        elif prev_leader is not None and now_leader is not None and prev_leader != now_leader:
            msg = random.choice(SCORE_FLOW_MESSAGES["comeback"]).format(
                ct=self.state.ct_score,
                t=self.state.t_score,
            )
            self._emit_commentary(
                msg,
                "comeback",
                cooldown_seconds=self.settings.score_flow_cooldown_seconds,
                once_per_round=True,
            )
        elif self.state.streak_count >= 3:
            key = "ct_streak" if winner == TEAM_CT else "t_streak"
            msg = random.choice(SCORE_FLOW_MESSAGES[key]).format(count=self.state.streak_count)
            self._emit_commentary(
                msg,
                key,
                cooldown_seconds=self.settings.score_flow_cooldown_seconds,
                once_per_round=True,
            )

        self._comment_on_round_context(winner)

        self.state.last_flow_comment_round = self.state.round_number

    def _swap_player_teams(self) -> None:
        """Swap tracked team assignments once when side switch happens."""
        new_teams: Dict[str, str] = {}
        for player, team in self.state.player_teams.items():
            if team == "CT":
                new_teams[player] = "TERRORIST"
            elif team == "TERRORIST":
                new_teams[player] = "CT"
            else:
                new_teams[player] = team
        self.state.player_teams = new_teams

    def _maybe_announce_side_switch(self, prev_round: Optional[int] = None) -> None:
        if not self.state.live_started:
            return

        if not self._is_side_switch_round(self.state.round_number):
            return
        if self.state.last_side_switch_round == self.state.round_number:
            return

        self.debug_print(f"[INFO] round: {self.state.round_number} -> side switch")
        self._say_duo(*self._pick_pair(
            ROUND_EVENTS.get("side_switch", []),
            ROUND_EVENT_INSIGHT_MESSAGES["side_switch"],
            "round_events", "side_switch",
        ))
        self.state.side_switch_announced = True
        self.state.last_side_switch_round = self.state.round_number
        self._swap_player_teams()
        self.state.streak_team = None
        self.state.streak_count = 0
        self.state.last_flow_comment_round = 0
        self.state.ct_match_point_announced = False
        self.state.t_match_point_announced = False

    def _is_side_switch_round(self, round_number: int) -> bool:
        regulation_switch = self._effective_max_rounds() // 2 + 1
        if round_number == regulation_switch:
            return True
        # Overtime MR3 halves: first switch after 3 OT rounds, then every 6 rounds.
        ot_first_round = self._effective_max_rounds() + 1
        ot_first_switch = ot_first_round + 3
        if round_number >= ot_first_switch and (round_number - ot_first_round) % 6 == 3:
            return True
        return False

    def handle_game_over_final(self, line: str) -> None:
        """Documentation."""
        match = re.search(r'score (\d+):(\d+)', line)
        if match:
            ct_score = int(match.group(1))
            t_score = int(match.group(2))
            if ct_score > t_score:
                winner = "CT"
            elif t_score > ct_score:
                winner = "TERRORIST"
            else:
                winner = "DRAW"
        else:
            winner = "UNKNOWN"

        if winner == "CT":
            self._say_commentary(f"CTチームの勝利！ {ct_score}-{t_score}")
        elif winner == "TERRORIST":
            self._say_commentary(f"Tチームの勝利！ {t_score}-{ct_score}")
        elif winner == "DRAW":
            self._say_commentary("引き分けです")
        else:
            self._say_commentary("試合終了")

    def _announce_opening_player_duel(self) -> None:
        """Announce one highlighted player from each team at match start."""
        ct_candidates = sorted(self.state.alive_ct)
        t_candidates = sorted(self.state.alive_t)
        if not ct_candidates or not t_candidates:
            return

        ct_player = random.choice(ct_candidates)
        t_player = random.choice(t_candidates)
        template = random.choice(OPENING_PLAYER_DUEL_MESSAGES)
        self._say_commentary(template.format(ct_player=ct_player, t_player=t_player))

    def handle_round_start(self, line: str) -> None:
        """Documentation."""
        if not self.state.live_started:
            return

        if self.state.pause_requested:
            self.state.pause_requested = False
            self.rcon("mp_pause_match")
            self.say("試合をポーズしました。再開は !unpause で")

        # Rebuild alive players from current team assignments at each round start.
        # This prevents stale/incomplete alive sets from causing false clutch/1v1 calls.
        self.state.alive_ct = {
            name
            for name, team in self.state.player_teams.items()
            if team == TEAM_CT and not self._is_bot_player(name)
        }
        self.state.alive_t = {
            name
            for name, team in self.state.player_teams.items()
            if team == TEAM_T and not self._is_bot_player(name)
        }
        if not self.state.alive_ct and not self.state.alive_t:
            self.state.alive_ct = {
                name
                for name, team in self.state.temp_player_teams.items()
                if team == TEAM_CT and not self._is_bot_player(name)
            }
            self.state.alive_t = {
                name
                for name, team in self.state.temp_player_teams.items()
                if team == TEAM_T and not self._is_bot_player(name)
            }

        connected_upper = self._refresh_connected_player_names()
        if connected_upper:
            self.state.alive_ct = {name for name in self.state.alive_ct if name.upper() in connected_upper}
            self.state.alive_t = {name for name in self.state.alive_t if name.upper() in connected_upper}

        self.state.round_start_time = time.time()
        self.state.headshot_kills.clear()
        self.state.kill_streaks.clear()
        self.state.round_kills.clear()
        self.state.round_weapons_ct.clear()
        self.state.round_weapons_t.clear()
        self.state.round_comment_keys.clear()
        self.state.clutch_active = False
        self.state.clutch_player = None
        self.state.clutch_enemy_count = 0
        self.state.one_v_one_announced = False
        self.state.last_kill_time = time.time()
        self.state.round_awp_taunt_sent = False

        if self.state.round_number == self._effective_max_rounds() + 1:
            self._say_duo(*self._pick_pair(
                ROUND_EVENTS.get("overtime_start", []),
                ROUND_EVENT_INSIGHT_MESSAGES["overtime_start"],
                "round_events", "overtime_start",
            ))
        elif self.state.round_number == self._effective_max_rounds() + 4:
            self._say_duo(*self._pick_pair(
                ROUND_EVENTS.get("overtime_late", []),
                ROUND_EVENT_INSIGHT_MESSAGES["overtime_late"],
                "round_events", "overtime_late",
            ))

        if self.state.round_number == 1 and self.state.live_started and not self.state.first_round_announced:
            if self.state.announcer_duo_index is None:
                self.state.announcer_duo_index = random.randrange(len(ANNOUNCER_DUOS))
            map_name = get_map_display_name(self.state.current_map)
            intro_commentary, intro_insight = ANNOUNCER_DUOS[self.state.announcer_duo_index]["intro"]
            self._say_duo(intro_commentary.format(map_name=map_name), intro_insight.format(map_name=map_name))
            self._announce_opening_player_duel()
            self.state.first_round_announced = True

        self._maybe_announce_side_switch()

    def handle_taunt(self, killer: str, kill_count: int) -> None:
        """Send a taunt message on 3-kill streaks."""
        if kill_count != 3:
            return

        candidates = TAUNT_MESSAGES.get(killer.upper()) or TAUNT_MESSAGES.get("__DEFAULT__", [])
        if candidates and random.random() < self.settings.taunt_chance:
            self._say_commentary(random.choice(candidates))

    def _announce_clutch_state(self, ct_alive: int, t_alive: int) -> None:
        """Announce clutch/1v1 state transitions once per round."""
        if ct_alive == 1 and t_alive == 1:
            if not self.state.one_v_one_announced:
                self.state.clutch_active = True
                self.state.one_v_one_announced = True
                player1 = next(iter(self.state.alive_ct), "")
                player2 = next(iter(self.state.alive_t), "")
                commentary, insight = self._pick_pair(
                    ONE_VS_ONE_MESSAGES, ONE_VS_ONE_INSIGHT_MESSAGES, "one_v_one",
                )
                self._say_duo(
                    commentary.format(player1=player1, player2=player2),
                    insight.format(player1=player1, player2=player2),
                )
                self.debug_print("[CLUTCH] 1v1 situation entered")
            return

        if self.state.clutch_active:
            return

        if ct_alive == 1 and t_alive >= 2:
            candidates = [p for p in self.state.alive_ct if not self._is_bot_player(p)]
            if not candidates:
                return
            self.state.clutch_active = True
            self.state.clutch_player = candidates[0]
            self.state.clutch_enemy_count = t_alive
            commentary, insight = self._pick_pair(CLUTCH_MESSAGES, CLUTCH_INSIGHT_MESSAGES, "clutch")
            self._say_duo(
                commentary.format(player=self.state.clutch_player, count=t_alive),
                insight.format(player=self.state.clutch_player, count=t_alive),
            )
            self.debug_print(f"[CLUTCH] {self.state.clutch_player} (CT) vs {t_alive} T")
            return

        if t_alive == 1 and ct_alive >= 2:
            candidates = [p for p in self.state.alive_t if not self._is_bot_player(p)]
            if not candidates:
                return
            self.state.clutch_active = True
            self.state.clutch_player = candidates[0]
            self.state.clutch_enemy_count = ct_alive
            commentary, insight = self._pick_pair(CLUTCH_MESSAGES, CLUTCH_INSIGHT_MESSAGES, "clutch")
            self._say_duo(
                commentary.format(player=self.state.clutch_player, count=ct_alive),
                insight.format(player=self.state.clutch_player, count=ct_alive),
            )
            self.debug_print(f"[CLUTCH] {self.state.clutch_player} (T) vs {ct_alive} CT")
            return

    def should_commentate(self) -> bool:
        """Documentation."""
        return self.state.commentary_enabled and self.state.live_started

    def _lookup_taunt_pool(self, pool: dict, player_name: str) -> List[str]:
        """Resolve a name -> taunts pool entry with tolerant name matching."""
        raw = player_name.strip()
        upper = raw.upper()

        direct = pool.get(upper)
        if direct:
            return direct

        # Fallback: compare alnum-only normalized keys to absorb tags/spaces/symbols.
        norm = re.sub(r"[^A-Z0-9]+", "", upper)
        if not norm:
            return []

        for key, msgs in pool.items():
            if key == "__DEFAULT__":
                continue
            key_norm = re.sub(r"[^A-Z0-9]+", "", key.upper())
            if key_norm and (key_norm == norm or key_norm in norm or norm in key_norm):
                return msgs

        return []

    def _get_personal_taunts(self, player_name: str) -> List[str]:
        """Resolve personal 3-kill taunts, preferring this match's announcer persona voice."""
        idx = self.state.announcer_duo_index
        if idx is not None:
            persona_taunts = self._lookup_taunt_pool(TAUNT_MESSAGES_BY_PERSONA[idx], player_name)
            if persona_taunts:
                return persona_taunts
            default = TAUNT_MESSAGES_BY_PERSONA[idx].get("__DEFAULT__")
            if default:
                return default

        return self._lookup_taunt_pool(TAUNT_MESSAGES, player_name)

    def _idle_comment_message(self, target: str) -> str:
        """Choose an idle cheer that does not contradict the current alive count."""
        ct_alive = len(self.state.alive_ct)
        t_alive = len(self.state.alive_t)

        if ct_alive == 1 and t_alive == 1:
            return random.choice(ONE_VS_ONE_MESSAGES)

        candidates = list(CHEER_MESSAGES)
        if ct_alive <= 1 and t_alive <= 1:
            candidates = [msg for msg in candidates if "人数有利" not in msg]

        return random.choice(candidates).format(player=target)

    def check_silence(self):
        if not self.should_commentate():
            return

        if not self.state.round_start_time or not self.state.last_kill_time:
            return

        now = time.time()
        silence_duration = now - self.state.last_kill_time

        if silence_duration >= self.settings.silence_seconds and not self.state.silence_comment_given:
            ct = len(self.state.alive_ct)
            t = len(self.state.alive_t)

            if ct == 0 or t == 0:
                return

            if ct == t:
                category = "even"
            elif ct > t:
                category = "ct_advantage"
            elif t > ct:
                category = "t_advantage"
            else:
                category = "balanced"

            message, insight_message = self._pick_pair(
                SILENCE_MESSAGES[category], SILENCE_INSIGHT_MESSAGES[category], "silence", category,
            )

            if self._emit_commentary(
                message,
                "silence",
                cooldown_seconds=self.settings.commentary_cooldown_seconds,
                once_per_round=True,
                insight_message=insight_message,
            ):
                self.state.silence_comment_given = True

    def handle_kill(self, line: str, match: re.Match) -> None:
        """Documentation."""
        killer = match.group("killer")
        killer_steam_id = match.group("killer_steam_id")
        killer_team = match.group("killer_team")

        victim = match.group("victim")
        victim_steam_id = match.group("victim_steam_id")
        victim_team = match.group("victim_team")

        weapon = match.group("weapon")

        # Keep alive sets accurate regardless of commentary toggle.
        if victim_steam_id == "BOT":
            vt = victim_team
        else:
            vt = self.get_team(victim_steam_id)
        if vt == TEAM_CT:
            self._discard_alive_player(TEAM_CT, victim, victim_steam_id)
        elif vt == TEAM_T:
            self._discard_alive_player(TEAM_T, victim, victim_steam_id)
        else:
            self._discard_alive_player("UNKNOWN", victim, victim_steam_id)
            self.debug_print(f"[WARN] victim team unknown: {victim} ({victim_steam_id})")

        killer_is_bot = self._is_bot_player(killer, killer_steam_id)
        victim_is_bot = self._is_bot_player(victim, victim_steam_id)
        is_teamkill = (killer_team == victim_team)

        if self.state.live_started and not self.state.practice_mode:
            if not victim_is_bot:
                increment_deaths(victim)
            if not killer_is_bot and not is_teamkill:
                increment_kills(killer)

        if killer_is_bot:
            kt = "UNKNOWN"
        else:
            kt = self.get_team(killer_steam_id)
        if kt == TEAM_CT:
            self._add_alive_player(TEAM_CT, killer, killer_steam_id)
        elif kt == TEAM_T:
            self._add_alive_player(TEAM_T, killer, killer_steam_id)
        else:
            self.debug_print(f"[WARN] killer team unknown: {killer} ({killer_steam_id})")

        if self.should_commentate():
            if self.state.round_start_time and time.time() - self.state.round_start_time <= 15:
                self._say_commentary(f"{victim} が開幕15秒以内にダウン")

            if "headshot" in line.lower():
                self.state.headshot_streaks[killer] = self.state.headshot_streaks.get(killer, 0) + 1
                if self.state.headshot_streaks[killer] == 3:
                    message = self._pick(HEADSHOT_STREAK_MESSAGES, "headshot_streak").format(player=killer)
                    self._say_commentary(message)
            else:
                self.state.headshot_streaks[killer] = 0

            if killer_team == victim_team and killer != victim and "BOT" not in line:
                commentary, insight = self._pick_pair(TEAM_KILL_MESSAGES, TEAM_KILL_INSIGHT_MESSAGES, "team_kill")
                self._say_duo(commentary.format(player=killer), insight.format(player=killer))
                return

            if kt == TEAM_CT and not killer_is_bot:
                self._add_alive_player(TEAM_CT, killer, killer_steam_id)
                self.state.round_weapons_ct.add(weapon.lower())
            elif kt == TEAM_T and not killer_is_bot:
                self._add_alive_player(TEAM_T, killer, killer_steam_id)
                self.state.round_weapons_t.add(weapon.lower())

            self.state.kill_streaks[killer] = self.state.kill_streaks.get(killer, 0) + 1
            streak = self.state.kill_streaks[killer]

            # The 4-kill messages all claim "1 more for the ace" — only true if the
            # opposing team still has exactly 1 player alive. If someone else already
            # took an earlier kill this round (teammate, suicide, etc.), the ace is
            # no longer possible and that claim would be misleading, so skip it.
            opposing_alive = None
            if kt == TEAM_CT:
                opposing_alive = len(self.state.alive_t)
            elif kt == TEAM_T:
                opposing_alive = len(self.state.alive_ct)

            if streak == 4 and opposing_alive != 1:
                pass
            elif streak in KILL_STREAK_MESSAGES:
                # At 3-kill streak, prefer a player-specific taunt by probability.
                if streak == 3:
                    personal = self._get_personal_taunts(killer)
                    if personal:
                        self._say_commentary(random.choice(personal))
                    else:
                        message = self._pick(KILL_STREAK_MESSAGES[streak], "kill_streak", streak).format(player=killer)
                        self._say_commentary(message)
                else:
                    message = self._pick(KILL_STREAK_MESSAGES[streak], "kill_streak", streak).format(player=killer)
                    self._say_commentary(message)

            if streak >= 5:
                commentary, insight = self._pick_pair(ACE_MESSAGES, ACE_INSIGHT_MESSAGES, "ace")
                self._say_duo(commentary.format(player=killer), insight.format(player=killer))

        self.state.last_kill_time = time.time()

        # Check clutch transition.
        ct_alive = len(self.state.alive_ct)
        t_alive = len(self.state.alive_t)

        self._announce_clutch_state(ct_alive=ct_alive, t_alive=t_alive)

    def get_team(self, steam_id: str) -> str:
        # Try lookup by steam_id first (may be like '[U:1:6111605]' or 'BOT')
        """Documentation."""
    
        team = self.state.player_teams.get(steam_id)
        if team is not None:
            return team
        # If not found, try resolving steam_id -> name and lookup by name
        name = self.state.steam_to_name.get(steam_id)
        if name:
            team = self.state.player_teams.get(name)
            if team is not None:
                return team
        self.debug_print(f"[WARN] get_team: team not found for '{steam_id}'")
        return "UNKNOWN"

    def latest_log(self) -> Optional[str]:
        """Documentation."""
        files = glob.glob(os.path.join(self.settings.log_dir, "*.log"))
        valid_files = []

        for f in files:
            try:
                if os.path.getsize(f) > 0:
                    valid_files.append(f)
            except OSError:
                continue

        if not valid_files:
            return None

        # Sort by modified time desc.
        valid_files.sort(key=os.path.getmtime, reverse=True)
        return valid_files[0]

    def debug_print(self, message: str) -> None:
        """Documentation."""
        if self.state.debug_enabled:
            logger.debug(message)

    def handle_chat_command(self, player: str, steam_id: str, team: str, command: str, arg: str) -> None:
        """Documentation."""
        cmd = command.lower()
        arg = arg.strip() if arg else ""

        if cmd == "svr_help":
            for line in HELP_MESSAGES:
                self.say(line)
            if steam_id == self.settings.admin_steamid:
                for line in HELP_MESSAGES_ADMIN:
                    self.say(line)                
            return

        if cmd == "commentary":
            if arg.lower() == "on":
                self.state.commentary_enabled = True
                self.say("実況を ON にしました")
            elif arg.lower() == "off":
                self.state.commentary_enabled = False
                self.say("実況を OFF にしました")
            else:
                self.say("使い方: !commentary on / !commentary off")
            return

        if cmd == "debug":
            self.state.debug_enabled = not self.state.debug_enabled
            status = "ON" if self.state.debug_enabled else "OFF"
            self.say(f"Debug mode: {status}")
            logger.debug("Debug mode changed to %s", status)
            return

        if cmd == "map":
            if not arg:
                maps_list = ", ".join(self.settings.available_maps)
                msg = f"利用可能マップ: {maps_list}"
                if self.settings.workshop_maps:
                    msg += " / Workshop: " + ", ".join(self.settings.workshop_maps)
                self.say(msg)
            else:
                selected = arg.split()[0].lower() if arg else ""
                if selected == "random":
                    chosen = random.choice(self.settings.available_maps)
                    self.state.current_map = normalize_map_name(chosen)
                    self.say(f"ランダムで {chosen} に変更します")
                    self.rcon(f"changelevel de_{chosen}")
                elif selected in self.settings.available_maps:
                    self.state.current_map = normalize_map_name(selected)
                    self.say(f"マップ {selected} に変更します")
                    self.rcon(f"changelevel de_{selected}")
                elif selected in self.settings.workshop_maps:
                    workshop_id = self.settings.workshop_maps[selected]
                    self.state.current_map = selected
                    self.say(f"Workshopマップ {selected} を読み込みます...")
                    self.rcon(f"host_workshop_map {workshop_id}")
                else:
                    self.say(f"'{selected}' はサポート外のマップです")
            return

        if cmd in ("coin", "cointos"):
            if self.state.coin_used:
                self.say("コイントスは既に実施済みです")
            else:
                self.state.coin_used = True
                self.state.coin_winner = random.choice(["CT", "TERRORIST"])
                self.state.side_select_active = True
                self.say(f"コイントス結果: {self.state.coin_winner} がサイド選択権を獲得")
                self.say("!ct または !t でサイドを選択してください")
            return

        if cmd in ("ct", "t"):
            if self.state.side_select_active and team == self.state.coin_winner:
                self.say(f"{player} が {cmd.upper()} を選択")
                self.state.side_select_active = False
            elif not self.state.side_select_active:
                self.say("現在はサイド選択タイミングではありません")
            else:
                self.say("サイド選択権がありません")
            return

        if cmd == "rdy":
            if team == "CT":
                self.state.rdy_ct = True
                self.say("CT チーム ready")
            elif team == "TERRORIST":
                self.state.rdy_t = True
                self.say("T チーム ready")
            if self.state.rdy_ct and self.state.rdy_t:
                self.say("両チーム ready。!lo3 で開始できます")
                output = self.rcon("status")
                logger.debug(f"[DEBUG] rcon status output: {output}")
                self.state.match_finished = False
                self.state.round_number = 0
                self.state.side_switch_announced = False
            return

        if cmd == "rcon":
            if steam_id == self.settings.admin_steamid:
                if arg and arg.strip():
                    self.debug_print(f"[DEBUG] RCON arg raw: '{arg}'")
                    clean_arg = arg.strip()
                    self.say(f"RCON実行: {clean_arg}")
                    self.rcon(clean_arg)
                else:
                    self.say("使い方: !rcon <command>")
            else:
                self.say("このコマンドは管理者専用です")
            return

        if cmd == "reset":
            if steam_id == self.settings.admin_steamid:
                self.say("試合状態をリセットします")
                self.state.reset()
                self._reset_special_game_mode_cvars()
                self.rcon("mp_restartgame 1")
            else:
                self.say("このコマンドは管理者専用です")
            return

        if cmd == "prac":
            bot_count = 5
            self.state.prac_mode_active = True
            self.state.prac_bot_quota = bot_count
            self.state.prac_enemy_bot_cmd = "bot_add_t" if team == "CT" else "bot_add_ct"
            self.rcon("mp_freezetime 3")
            self.rcon("mp_autoteambalance 0")
            self.rcon("mp_limitteams 0")
            self.rcon("mp_warmup_end")
            self.rcon("bot_kick")
            self.rcon("bot_quota_mode normal")
            self.rcon("bot_quota 0")
            self.rcon("bot_difficulty 5")
            self.rcon("custom_bot_difficulty 5")
            self.rcon("bot_allow_pistols 1")
            self.rcon("bot_allow_rifles 1")
            self.rcon("bot_allow_snipers 1")
            self.rcon("bot_allow_grenades 1")
            for _ in range(bot_count):
                self.rcon(self.state.prac_enemy_bot_cmd)
            # Now that our bots are placed, pin the quota to that exact count
            # so future re-assertions (see _handle_round_start_event) hold
            # them steady instead of kicking them back down to 0.
            self.rcon(f"bot_quota {bot_count}")
            self.say(f"練習モード: freezetime 3秒、反対チームにBOT{bot_count}体追加、autobalance OFF")
            return

        if cmd == "lo3":
            self.state.prac_mode_active = False
            tokens = arg.split() if arg else []
            self.state.practice_mode = False
            for token in tokens:
                if token.lower() == "practice":
                    self.state.practice_mode = True
                    continue
                try:
                    requested = int(token) - 1
                except ValueError:
                    requested = -1
                if 0 <= requested < len(ANNOUNCER_DUOS):
                    self.state.announcer_duo_index = requested
                else:
                    self.say(f"実況コンビは 1〜{len(ANNOUNCER_DUOS)} の番号で指定してください")

            if self.state.practice_mode:
                self.say("練習モードで試合を Live on 3 で開始します（戦績・ELOは記録されません）")
            else:
                self.say("試合を Live on 3 で開始します")
            self.state.WIN_ROUNDS = self._effective_max_rounds() // 2 + 1
            self.rcon(f"mp_maxrounds {self._effective_max_rounds()}")
            # In case !prac shortened freezetime for practice, restore the
            # normal competitive value for the real match.
            self.rcon("mp_freezetime 15")
            self.rcon("mp_match_can_clinch 1")
            self.rcon("mp_overtime_enable 1")
            self.rcon("mp_overtime_maxrounds 6")
            self.rcon("mp_overtime_limit 1")
            self.rcon("mp_warmup_end")
            load_stats()
            load_elo()
            save_stats()
            self.state.ct_players = list(self.state.alive_ct)
            self.state.t_players = list(self.state.alive_t)
            ct_players = [p for p, team in self.state.player_teams.items() if team == TEAM_CT]
            t_players = [p for p, team in self.state.player_teams.items() if team == TEAM_T]
            self.say("Live on 3... 準備してください")

            self.state.player_teams = self.state.temp_player_teams.copy()

            for i in range(3, 0, -1):
                self.rcon("mp_restartgame 1")
                time.sleep(1)
            self.say("Live on 3! GLHF!")
            self.rcon("mp_unpause_match")
            self.state.match_finished = False
            self.state.live_started = True

            # Refresh status after lo3.
            time.sleep(1.5)
            output = self.rcon("status")
            if output:
                self.parse_status_output(output)
                logger.info("lo3後のstatus取得に成功し、TARGETSを更新しました")
            else:
                logger.warning("lo3 後の status 取得に失敗しました")

            return

        if cmd == "cancel":
            if steam_id == self.settings.admin_steamid:
                self.say("試合開始をキャンセルしました")
                self.state.rdy_ct = False
                self.state.rdy_t = False
                self.state.live_started = False
                self.state.first_round_announced = False
                self.state.match_finished = False
                self.state.round_number = 0
                self.state.ct_players = []
                self.state.t_players = []
                self.state.alive_ct.clear()
                self.state.alive_t.clear()
                self.state.player_teams = self.state.temp_player_teams.copy()
            else:
                self.say("このコマンドは管理者専用です")
            return

        if cmd == "pause":
            if not self.state.live_started:
                self.say("試合中のみ使用できます")
                return
            if self.state.pause_requested:
                self.say("すでにポーズ予約済みです")
                return
            self.state.pause_requested = True
            self.say("次のラウンド開始時にポーズします")
            return

        if cmd == "unpause":
            self.state.pause_requested = False
            self.rcon("mp_unpause_match")
            self.say("試合を再開します")
            return

        if cmd == "shuffle":
            self.say("チームをランダムでシャッフルします")
            self.rcon("mp_scrambleteams 1")
            self.rcon("mp_restartgame 1")
            return

        if cmd == "omikuji":
            if arg.strip().lower() == "reset":
                if steam_id != self.settings.admin_steamid:
                    self.say("このコマンドは管理者専用です")
                    return

                count = 0
                for stats in PLAYER_STATS.values():
                    if "last_omikuji_date" in stats:
                        del stats["last_omikuji_date"]
                        count += 1
                    if "last_omikuji_weapon" in stats:
                        del stats["last_omikuji_weapon"]

                save_stats()
                self.say(f"おみくじ履歴をリセットしました。対象プレイヤー数: {count}")
                return

            name = player.upper()
            stats = PLAYER_STATS.setdefault(name, {"wins": 0, "losses": 0})

            last_date = stats.get("last_omikuji_date")
            today = self.today_str()

            if last_date == today:
                self.say(f"{player} さんは今日すでにおみくじを引いています")
                return

            fortune = random.choice(OMIKUJI_RESULTS)
            weapon = random.choice(LUCKY_WEAPONS)
            warning_target = self.get_random_warning_target(player)

            self.say(f"{player} のおみくじ結果: {fortune}")
            self.say(f"ラッキー武器は {weapon}")

            if warning_target:
                self.say(f"今日の注意人物: {warning_target}")

            stats["last_omikuji_date"] = today
            stats["last_omikuji_weapon"] = weapon
            save_stats()
            return

        if cmd == "elo":
            target = arg.strip().upper()
            if not target:
                target = player.upper()

            rating = get_elo(target)
            self.say(f"{target} の現在ELOは {rating}")
            return

        if cmd == "kd":
            target = arg.strip().upper() or player.upper()
            k = get_kills(target)
            d = get_deaths(target)
            ratio = get_kd_ratio(target)
            self.say(f"{target} K/D: {k}K {d}D ({ratio:.2f})")
            return

        if cmd == "top" and arg.strip().lower() == "kd":
            entries = [
                (name, get_kills(name), get_deaths(name), get_kd_ratio(name))
                for name in PLAYER_STATS
                if not is_bot(name) and (get_kills(name) + get_deaths(name)) > 0
            ]
            if not entries:
                self.say("K/Dデータがありません")
                return
            ranked = sorted(entries, key=lambda x: x[3], reverse=True)
            self.say("K/Dランキング TOP5")
            for i, (name, k, d, ratio) in enumerate(ranked[:5], 1):
                self.say(f"{i}. {name} - {ratio:.2f} ({k}K {d}D)")
            return

        if cmd == "top" and arg.strip().lower() == "elo":
            elo_data = get_all_elo()

            if not elo_data:
                self.say("ELOデータがありません")
                return

            ranked = sorted(elo_data.items(), key=lambda x: x[1], reverse=True)
            self.say("ELOランキング TOP5")
            for i, (player, elo) in enumerate(ranked[:5], 1):
                self.say(f"{i}. {player} - Elo {elo}")
            return

        if cmd == "kdshuffle":
            players = self.get_connected_players()
            if len(players) < 2:
                self.say("接続中プレイヤー数が足りません")
                return

            if self.state.wingman_mode or self.state.dm_mode or self.state.retake_mode:
                self._reset_special_game_mode_cvars()
                self.state.WIN_ROUNDS = self._effective_max_rounds() // 2 + 1

            team_ct, team_t = kd_shuffle_balanced(players)
            self._apply_team_shuffle(team_ct, team_t, label="KD")
            return

        if cmd == "smartshuffle":
            players = self.get_connected_players()
            if len(players) < 2:
                self.say("接続中プレイヤー数が足りません")
                return

            if self.state.wingman_mode or self.state.dm_mode or self.state.retake_mode:
                self._reset_special_game_mode_cvars()
                self.state.WIN_ROUNDS = self._effective_max_rounds() // 2 + 1

            added = ensure_players_initialized(players, 1000)
            if added:
                logger.info("ELO初期値を追加: %s", ", ".join(added))
            team_ct, team_t = smart_shuffle_balanced(players)
            self._apply_team_shuffle(team_ct, team_t, label="Smart")
            return

        if cmd == "wingman":
            players = self.get_connected_players()
            if not (1 <= len(players) <= 4):
                self.say(f"Wingmanは人間1〜4人が必要です（現在{len(players)}人）")
                return

            wingman_maps = self.settings.wingman_maps
            requested_map = arg.strip().lower() if arg else ""
            if requested_map:
                matches = [m for m in wingman_maps if requested_map in m.lower()]
                target_map = matches[0] if matches else None
                if not target_map:
                    self.say(f"Wingman対応マップ: {', '.join(wingman_maps)}")
                    return
            else:
                target_map = random.choice(wingman_maps)

            # CS2's Wingman mode uses the same map files as normal play, but
            # the correct (smaller) spawn/bombsite layout only kicks in on a
            # fresh map load with the mode cvars set beforehand. So switch to
            # a known Wingman-capable map now, and finish the bot/cvar/shuffle
            # setup once the map change event fires (see _handle_map_change_event).
            self._reset_special_game_mode_cvars()
            self.state.pending_wingman_players = players
            self.rcon("game_type 0")
            self.rcon("game_mode 2")
            self.say(f"Wingmanモードで {target_map} を読み込みます...")
            self.rcon(f"changelevel {target_map}")
            return

        if cmd == "dm":
            target_map = arg.strip().lower() if arg else ""
            if target_map:
                matches = [m for m in self.settings.available_maps if target_map in m.lower()]
                if not matches:
                    self.say(f"利用可能マップ: {', '.join(self.settings.available_maps)}")
                    return
                target_map = f"de_{matches[0]}"
            else:
                target_map = self.state.current_map

            # gamemode_deathmatch.cfg (bot fill, ffa, respawns, ...) only gets
            # applied on a fresh map load with the mode cvars set beforehand,
            # same as Wingman.
            self._reset_special_game_mode_cvars()
            self.state.pending_dm = True
            self.rcon("game_type 1")
            self.rcon("game_mode 2")
            self.say(f"デスマッチモードで {target_map} を読み込みます...")
            self.rcon(f"changelevel {target_map}")
            return

        if cmd == "retake":
            target_map = arg.strip().lower() if arg else ""
            if target_map:
                matches = [m for m in self.settings.available_maps if target_map in m.lower()]
                if not matches:
                    self.say(f"利用可能マップ: {', '.join(self.settings.available_maps)}")
                    return
                target_map = f"de_{matches[0]}"
            else:
                target_map = self.state.current_map

            # Official Retakes (added 2025-10-23): game_type 0 / game_mode 0
            # with sv_skirmish_id 12 selects the Retakes "war game", which
            # execs gamemode_retakecasual.cfg on the next fresh map load.
            self._reset_special_game_mode_cvars()
            self.state.pending_retake = True
            self.rcon("game_type 0")
            self.rcon("game_mode 0")
            self.rcon("sv_skirmish_id 12")
            self.say(f"Retakesモードで {target_map} を読み込みます...")
            self.rcon(f"changelevel {target_map}")
            return

        if cmd == "balancecheck":
            ct_players = [p for p, team in self.state.player_teams.items() if team == TEAM_CT]
            t_players = [p for p, team in self.state.player_teams.items() if team == TEAM_T]

            if not ct_players or not t_players:
                self.say("チーム情報が不足しています")
                return

            ct_elo = sum(get_elo(p) for p in ct_players)
            t_elo = sum(get_elo(p) for p in t_players)
            diff = abs(ct_elo - t_elo)

            self.say(f"CT Elo合計: {ct_elo}")
            self.say(f"T Elo合計: {t_elo}")
            self.say(f"チーム間の Elo 差: {diff}")
            return

        if cmd == "simulate":
            ct_players = [p for p, team in self.state.player_teams.items() if team == TEAM_CT]
            t_players = [p for p, team in self.state.player_teams.items() if team == TEAM_T]

            if not ct_players or not t_players:
                self.say("チーム情報が不足しています")
                return

            ct_elo = sum(get_elo(p) for p in ct_players)
            t_elo = sum(get_elo(p) for p in t_players)

            ct_winrate = predict_winrate(ct_elo, t_elo)
            t_winrate = 1 - ct_winrate

            self.say("勝率予測")
            self.say(f"CT: {ct_winrate * 100:.1f}%")
            self.say(f"T: {t_winrate * 100:.1f}%")
            return

        if cmd == "stats":
            target = arg.strip().upper()
            if not target:
                target = player.upper()

            stats = PLAYER_STATS.get(target)
            if not stats:
                self.say(f"{target} の戦績は登録されていません")
                return

            wins = stats.get("wins", 0)
            losses = stats.get("losses", 0)
            total = wins + losses
            win_rate = (wins / total * 100) if total > 0 else 0.0

            self.say(f"{target} の戦績: {wins}勝 {losses}敗 (勝率 {win_rate:.1f}%)")
            return

        if cmd == "top":
            MIN_MATCHES = 3
            ranked = []

            for player, stats in PLAYER_STATS.items():
                wins = stats.get("wins", 0)
                losses = stats.get("losses", 0)
                total = wins + losses
                if total >= MIN_MATCHES:
                    win_rate = wins / total
                    ranked.append((player, wins, losses, win_rate))

            if not ranked:
                self.say("ランキング表示には最低3試合の戦績が必要です")
                return

            ranked.sort(key=lambda x: x[3], reverse=True)

            limit = len(ranked) if arg.strip().lower() == "all" else 5

            self.say(f"勝率ランキング TOP{limit}")
            for i, (player, wins, losses, rate) in enumerate(ranked[:limit], 1):
                self.say(f"{i}. {player} - {wins}勝 {losses}敗 (勝率 {rate*100:.1f}%)")
            return

        if cmd == "tactics":
            map_name = normalize_map_name(self.state.current_map or "de_dust2")
            tactic = get_tactic(team, map_name)
            self.say(f"{team}側 ({map_name}): {tactic}")
            return

    def extract_json_content(self, line: str) -> str:
        """Documentation."""
        if ": " not in line:
            return ""

        content = line.split(": ", 1)[1].strip()

        if content.startswith(('"', '{', '}')):
            return content

        return ""

    def _handle_round_start_event(self, _match: re.Match[str], line: str) -> None:
        if self.state.prac_mode_active:
            # gamemode_competitive.cfg's bot_quota_mode "competitive" keeps
            # re-applying itself around each round, quietly resetting our
            # bot_quota override and auto-filling/rebalancing both teams.
            # Re-assert it every round -- pinned to our actual bot count, not
            # 0, or this would kick our own practice bots back down to zero.
            self.rcon("bot_quota_mode normal")
            self.rcon(f"bot_quota {self.state.prac_bot_quota}")
        self.handle_round_start(line)

    def _handle_kill_event(self, match: re.Match[str], line: str) -> None:
        self.handle_kill(line, match)

    def _handle_chat_identity_event(self, match: re.Match[str], _line: str) -> None:
        name = match.group("name").strip()
        accountid = match.group("accountid").strip()
        self.state.accountid_to_name[accountid] = name
        self.debug_print(f"[CHAT] {name} accountid {accountid} を保存")

    def _handle_connect_event(self, match: re.Match[str], _line: str) -> None:
        name = match.group("name")
        steam_id = match.group("steam_id")
        logger.info("CONNECT_RE 一致: %s (%s)", name, steam_id)
        self.state.name_to_steam[name] = steam_id
        self.state.steam_to_name[steam_id] = name
        TARGETS[name.upper()] = steam_id
        self._backfill_player_stats_steam_id(name, steam_id)
        logger.debug("TARGETS更新: %s => %s", name.upper(), steam_id)
        try:
            save_targets()
            save_stats()
            logger.info("TARGETSを保存しました")
        except Exception:
            logger.exception("TARGETS保存に失敗しました")
        logger.info("%s が接続しました (%s)", name, steam_id)

    def _handle_accolade_event(self, match: re.Match[str], _line: str) -> None:
        accolade_type = match.group("type")
        player = match.group("player").strip()
        value = float(match.group("value"))
        self.state.accolades.append((accolade_type, player, value))

    def _handle_match_status_event(self, match: re.Match[str], _line: str) -> None:
        self.state.rounds_played = int(match.group(1))
        self.debug_print(f"ラウンド数(MatchStatus): {self.state.rounds_played}")

    def _handle_warmup_start_event(self, _match: re.Match[str], _line: str) -> None:
        """Force live_started off whenever real warmup begins, in case a prior
        match never reached Game Over to reset it naturally (e.g. cut short
        for testing)."""
        if self.state.live_started:
            logger.info("Warmup_Start検知: live_started が立ったままだったためリセットします")
        self.state.live_started = False
        self.state.match_finished = True

    def _handle_game_over_event(self, match: re.Match[str], _line: str) -> None:
        if self.state.match_finished:
            return

        self.state.match_finished = True
        self.state.live_started = False

        ct_score = int(match.group(1))
        t_score = int(match.group(2))
        if ct_score > t_score:
            winner = "CT"
        elif t_score > ct_score:
            winner = "TERRORIST"
        else:
            logger.warning("引き分けスコアを検出したため試合終了処理を中断します")
            return

        output = self.rcon("status")
        if output:
            self.parse_status_output(output)

        # Keep full team assignments collected during the match.
        # If assignment tracking is empty for some reason, fall back to alive players.
        if not self.state.player_teams:
            for player in self.state.alive_ct:
                self.state.player_teams[player] = TEAM_CT
            for player in self.state.alive_t:
                self.state.player_teams[player] = TEAM_T

        self._say_commentary("試合終了！おつかれさまでした")
        self._say_commentary(f"全{self.state.rounds_played}ラウンドのハイライトです")
        for accolade_type, player, value in self.state.accolades:
            message = get_accolade_message(accolade_type, player, value)
            if message:
                self._say_commentary(message)

        self._say_commentary(f"{winner} の勝利！GG WP!")
        duo = self._current_duo()
        if duo:
            self._say_duo(*duo["sign_off"])

        ct_players = self._collect_team_players(TEAM_CT)
        t_players = self._collect_team_players(TEAM_T)
        if not ct_players and self.state.alive_ct:
            ct_players = [p for p in self.state.alive_ct if not is_bot(p)]
        if not t_players and self.state.alive_t:
            t_players = [p for p in self.state.alive_t if not is_bot(p)]

        if not ct_players and not t_players:
            logger.warning(
                "match result player extraction returned empty. player_teams=%s temp_player_teams=%s",
                self.state.player_teams,
                self.state.temp_player_teams,
            )

        logger.debug("[DEBUG] CT: %s, T: %s", ct_players, t_players)

        if self.state.practice_mode:
            self.say("練習モードのため、戦績・ELOは記録されません")
            logger.info("MATCH END (practice): %s の結果は記録をスキップしました", winner)
        else:
            tracked_ct = [p for p in ct_players if self._resolve_player_steam_id(p)]
            tracked_t = [p for p in t_players if self._resolve_player_steam_id(p)]
            skipped = [p for p in (ct_players + t_players) if not self._resolve_player_steam_id(p)]
            if skipped:
                logger.info("SteamID未登録のため結果集計をスキップ: %s", skipped)

            self.record_match_result(winner, tracked_ct, tracked_t)
            all_tracked = tracked_ct + tracked_t
            elo_before = {p: get_elo(p) for p in all_tracked}
            update_elo(winner, tracked_ct, tracked_t)
            save_elo()
            for p in all_tracked:
                before = elo_before[p]
                after = get_elo(p)
                sign = "+" if after >= before else ""
                self.say(f"ELO {p}: {sign}{after - before} ({before}→{after})")

            logger.info("MATCH END: %s の結果を保存しました", winner)
        if not self.state.accolades:
            self.say("アコレード情報はありませんでした")
        self.state.accolades.clear()

        logger.info("試合終了 -> プロセスを終了します")
        sys.exit(0)

    def _collect_team_players(self, team_name: str) -> List[str]:
        players: set[str] = set()

        for source in (self.state.player_teams, self.state.temp_player_teams):
            for key, team in source.items():
                if team != team_name:
                    continue
                name = self.state.steam_to_name.get(key, key)
                if name.startswith("[U:1:"):
                    continue
                if name.upper().startswith("BOT"):
                    continue
                players.add(name)

        return sorted(players)

    def _handle_map_change_event(self, match: re.Match[str], _line: str) -> None:
        new_map = match.group(1)
        logger.info("マップ変更検知: %s -> 状態をリセット", new_map)
        was_wingman = self.state.wingman_mode
        was_dm = self.state.dm_mode
        was_retake = self.state.retake_mode
        pending_wingman_players = self.state.pending_wingman_players
        pending_dm = self.state.pending_dm
        pending_retake = self.state.pending_retake
        self.state.reset()
        self.state.current_map = normalize_map_name(new_map)
        self.state.pending_wingman_players = None
        self.state.pending_dm = False
        self.state.pending_retake = False
        self.setup_event_listeners()
        self.ensure_rcon_alive()
        self.apply_server_password()
        self.reset_command_flags()
        if pending_dm:
            # This reload was triggered by !dm; gamemode_deathmatch.cfg
            # (bot fill, ffa, respawns, ...) applies itself automatically
            # now that the map has (re)loaded with the mode cvars set.
            self.state.dm_mode = True
        elif pending_retake:
            # This reload was triggered by !retake; gamemode_retakecasual.cfg
            # applies itself automatically now that the map has (re)loaded
            # with sv_skirmish_id set.
            self.state.retake_mode = True
        elif pending_wingman_players:
            # This reload was triggered by !wingman itself; finish setup now
            # that the map has (re)loaded with the mode cvars applied.
            self._start_wingman_match(pending_wingman_players)
        elif was_wingman or was_dm or was_retake:
            # Leaving a special mode via a plain !map: clean up any leftover
            # cvars (sv_skirmish_id, weapon restrictions, bots, ...).
            self._reset_special_game_mode_cvars()

    def _handle_chat_command_event(self, match: re.Match[str], _line: str) -> None:
        player_name, steam_id, team, command, arg = match.groups()
        arg = arg or ""
        # Keep team/mapping fresh from chat lines as an additional source of truth.
        self.state.player_teams[player_name] = team
        self.state.temp_player_teams[player_name] = team
        self.state.name_to_steam[player_name] = steam_id
        self.state.steam_to_name[steam_id] = player_name
        self._backfill_player_stats_steam_id(player_name, steam_id)
        logger.info("CHAT_CMD: %s (%s) [%s]: !%s %s", player_name, team, steam_id, command, arg)
        self.handle_chat_command(player_name, steam_id, team, command, arg)

    def _handle_player_team_event(self, match: re.Match[str], _line: str) -> None:
        name = match.group("name")
        steam_id = match.group("steam_id")
        team = match.group("team")
        if self._is_bot_player(name, steam_id):
            return
        self.state.temp_player_teams[name] = team
        self.state.player_teams[name] = team
        self.state.name_to_steam[name] = steam_id
        self.state.steam_to_name[steam_id] = name
        self._backfill_player_stats_steam_id(name, steam_id)

    def _handle_team_assign_event(self, match: re.Match[str], _line: str) -> None:
        name = match.group("name")
        steam_id = match.group("steam_id")
        team = match.group("team")
        if self._is_bot_player(name, steam_id):
            return
        self.state.player_teams[name] = team
        self.state.name_to_steam[name] = steam_id
        self.state.steam_to_name[steam_id] = name
        self._backfill_player_stats_steam_id(name, steam_id)
        logger.info("チーム割当: %s (%s) -> %s", name, steam_id, team)

    def _handle_disconnect_event(self, match: re.Match[str], _line: str) -> None:
        name = match.group("name")
        steam_id = match.group("steam_id")
        self.state.alive_ct.discard(name)
        self.state.alive_t.discard(name)
        self.state.player_teams.pop(name, None)
        self.state.player_teams.pop(steam_id, None)
        self.state.name_to_steam.pop(name, None)
        self.state.steam_to_name.pop(steam_id, None)
        logger.info("%s (%s) が切断しました", name, steam_id)

    def _dispatch_line_event(self, line: str) -> bool:
        for pattern, handler in self.event_handlers:
            match = pattern.match(line) if pattern is CHAT_RE else pattern.search(line)
            if not match:
                continue
            handler(match, line)
            return True
        return False

    def handle_line(self, line: str) -> None:
        if "JSON_BEGIN" in line:
            if self.in_json_block:
                self.state.json_parse_error_count += 1
                self._reset_json_parser("nested JSON_BEGIN", recover=True)
            self.in_json_block = True
            self.json_buffer = ["{"]
            return

        if "JSON_END" in line:
            if not self.in_json_block:
                self.state.json_parse_error_count += 1
                self._reset_json_parser("JSON_END without JSON_BEGIN", recover=True)
                return
            close_count = line.count("}")
            self.json_buffer.extend(["}"] * close_count)
            json_str = "\n".join(self.json_buffer)
            logger.debug("JSON buffer:\\n%s", json_str)
            try:
                json_data = json.loads(json_str)
                self.handle_json_line(json_data)
                self.state.json_parse_error_count = 0
            except json.JSONDecodeError as e:
                self.state.json_parse_error_count += 1
                logger.error("JSON解析エラー: %s", e)
                if self.state.json_parse_error_count % 3 == 0:
                    logger.warning(
                        "JSON解析エラーが連続発生しています。health-check を実行します。errors=%d",
                        self.state.json_parse_error_count,
                    )
                    self.ensure_rcon_alive()
            self._reset_json_parser("JSON_END processed")
            return

        if self.in_json_block:
            if len(self.json_buffer) > 500:
                self.state.json_parse_error_count += 1
                self._reset_json_parser("JSON buffer overflow", recover=True)
                return
            content = self.extract_json_content(line)
            if content:
                if (
                    self.json_buffer
                    and self.json_buffer[-1] not in ("{", "}")
                    and not self.json_buffer[-1].rstrip().endswith((",", "{"))
                ):
                    self.json_buffer[-1] += ","
                self.json_buffer.append(content)
                logger.debug("抽出JSON: %s", content)
            return

        if self._dispatch_line_event(line):
            return

        self.debug_print(f"[DEBUG] 未処理行: {line}")

    def record_match_result(self, winner: str, ct_players: List[str], t_players: List[str]) -> None:
        logger.debug(f"[DEBUG] Winner: {winner}")
        logger.debug(f"[DEBUG] CT: {ct_players}")
        logger.debug(f"[DEBUG] T: {t_players}")

        for player in ct_players:
            if is_bot(player):
                continue
            name = player.upper()
            steam_id = self._resolve_player_steam_id(player)
            if not steam_id:
                continue
            stats = PLAYER_STATS.setdefault(name, {"wins": 0, "losses": 0})
            stats["steam_id"] = steam_id
            if winner == "CT":
                stats["wins"] += 1
            else:
                stats["losses"] += 1
            logger.debug(f"[STATS] {name}: {stats}")

        for player in t_players:
            if is_bot(player):
                continue
            name = player.upper()
            steam_id = self._resolve_player_steam_id(player)
            if not steam_id:
                continue
            stats = PLAYER_STATS.setdefault(name, {"wins": 0, "losses": 0})
            stats["steam_id"] = steam_id
            if winner == "TERRORIST":
                stats["wins"] += 1
            else:
                stats["losses"] += 1
            logger.debug(f"[STATS] {name}: {stats}")

        save_stats()
        logger.info("試合結果を保存しました")


    def run(self) -> None:
        """Documentation."""
        logger.info("CS2 controller start")
        logger.info("config source: %s", self.settings.config_source)
        logger.info(
            "runtime settings: max_rounds=%d taunt_chance=%.2f silence=%ds idle=%ds password=%s",
            self.settings.max_rounds,
            self.settings.taunt_chance,
            self.settings.silence_seconds,
            self.settings.idle_comment_seconds,
            "set" if (self.settings.server_password or "").strip() else "empty",
        )
        load_stats()
        load_elo()
        load_targets()
        self.apply_server_password()

        self.current_log_path = None
        self.log_fp = None
        is_first_log_file = True

        wait_time = 0
        while True:
            latest = self.latest_log()
            if not latest:
                if wait_time == 0:
                    logger.info("ログファイルを待機中...")
                time.sleep(1)
                wait_time += 1
                if wait_time > 30:
                    logger.error("30秒待機してもログファイルが見つからないため終了します")
                    return
                continue

            if latest != self.current_log_path:
                if self.log_fp:
                    self.log_fp.close()
                self.current_log_path = latest
                self.log_fp = open(latest, "r", encoding="utf-8", errors="ignore")
                if is_first_log_file:
                    # Only skip history for the very first file we attach to
                    # (e.g. on process start/restart) so we don't replay a
                    # long-running server's entire past log. Any later file
                    # (created by a map change during this session) is brand
                    # new, and we need to read it from the start or we miss
                    # the "Loading map" line the map-change handler needs.
                    self.log_fp.seek(0, os.SEEK_END)
                is_first_log_file = False
                logger.info("ログ監視切り替え: %s", latest)

            line = self.log_fp.readline()
            if not line:
                self.check_warmup_guidance()
                self.check_idle()
                self.check_silence()
                time.sleep(0.1)
                continue

            logger.debug("Read line: %s", line.strip())
            self.handle_line(line.strip())
            self.check_silence()

    def check_idle(self) -> None:
        if not self.should_commentate():
            return
        if not self.state.last_kill_time:
            return
        if time.time() - self.state.last_kill_time >= self.settings.idle_comment_seconds:
            alive_players = list(self.state.alive_ct | self.state.alive_t)
            if alive_players:
                target = random.choice(alive_players)
                message = self._idle_comment_message(target)
                if self._emit_commentary(
                    message,
                    "idle_cheer",
                    cooldown_seconds=self.settings.commentary_cooldown_seconds,
                ):
                    self.state.last_kill_time = time.time()

    def check_warmup_guidance(self) -> None:
        """Send low-frequency command guidance before !lo3."""
        if self.state.live_started:
            return
        if not (self.state.alive_ct or self.state.alive_t or self.state.player_teams):
            return

        key = "warmup_guide"
        now = time.time()
        last_at = self.state.last_comment_at.get(key, 0.0)
        if now - last_at < WARMUP_GUIDE_INTERVAL_SECONDS:
            return

        self.say(random.choice(WARMUP_GUIDE_MESSAGES))
        self.state.last_comment_at[key] = now


def main() -> None:
    logger.debug("main() start")
    from rcon_utils import rcon as _rcon_func, say as _say_func

    settings = load_runtime_config()
    controller = Controller(_rcon_func, _say_func, MatchState(), settings=settings)
    controller.run()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception("エラーが発生しました: %s", e)
        input("エラーが発生しました。Enterキーで終了します。")




