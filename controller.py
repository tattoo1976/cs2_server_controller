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
    CHEER_MESSAGES,
    CLUTCH_MESSAGES,
    HEADSHOT_STREAK_MESSAGES,
    KILL_STREAK_MESSAGES,
    TEAM_KILL_MESSAGES,
    HELP_MESSAGES,
    HELP_MESSAGES_ADMIN,
    OMIKUJI_RESULTS,
    LUCKY_WEAPONS,
    get_accolade_message,
)
from messages import ROUND_EVENTS, SILENCE_MESSAGES, ONE_V_ONE_MESSAGES, SCORE_FLOW_MESSAGES, ROUND_CONTEXT_MESSAGES
from player_elo import get_all_elo, get_elo, load_elo, save_elo, update_elo
from player_stats import (
    PLAYER_STATS,
    TARGETS,
    load_stats,
    load_targets,
    save_stats,
    save_targets,
    is_bot,
)
from state import MatchState
from runtime_config import RuntimeConfig, load_runtime_config
from taunts import TAUNT_MESSAGES
from tactics import get_tactic, normalize_map_name
from team_utils import (
    assign_teams,
    elo_shuffle,
    predict_winrate,
    smart_shuffle_balanced,
)

PLAYER_TEAM_RE = re.compile(r'"(?P<name>[^<]+)<\d+><(?P<steam_id>[^>]+)><(?P<team>CT|TERRORIST)>"')
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

STATUS_RE = re.compile(r'^\s*\d+\s+"(?P<name>.+?)"\s+\[(?P<steam_id>U:1:\d+)\]')

MATCH_STATUS_RE = re.compile(r'MatchStatus: Score: \d+:\d+ on map ".*?" RoundsPlayed: (\d+)', re.IGNORECASE)

MAP_CHANGE_RE = re.compile(r'Loading map "([^\"]+)"')
ROUND_START_RE = re.compile(r'Round_Start|Starting Freeze period', re.IGNORECASE)
CHAT_CMD_RE = re.compile(
    r'L \d+/\d+/\d+ - \d+:\d+:\d+: "([^<]+)<\d+><(\[U:1:\d+\])><(CT|TERRORIST)>" say "!?(\w+)(?:\s+(.*))?"'
)
GAME_OVER_RE = re.compile(r'Game Over: .*?score\s+(\d+):(\d+)', re.IGNORECASE)

TEAM_ASSIGN_RE = re.compile(
    r'"(?P<name>.+?)<\d+><(?P<steam_id>[^>]+)><[^>]*>" joined team "(?P<team>CT|TERRORIST)"'
)

CHAT_RE = re.compile(
    r'"(?P<name>.+?)<\d+><(?P<steamid>\[U:1:(?P<accountid>\d+)\])><(?P<team>\w+)>" say "(?P<text>.+)"'
)

TEAM_T = "TERRORIST"
TEAM_CT = "CT"


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
        self.say = say_func
        self.state = state or MatchState()
        self.settings = settings or load_runtime_config()
        self.state.WIN_ROUNDS = self.settings.max_rounds // 2 + 1
        self.json_buffer: List[str] = []
        self.in_json_block: bool = False
        self.event_handlers: List[tuple[re.Pattern[str], Callable[[re.Match[str], str], None]]] = []
        self.setup_event_listeners()

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
            (CHAT_CMD_RE, self._handle_chat_command_event),
            (PLAYER_TEAM_RE, self._handle_player_team_event),
            (TEAM_ASSIGN_RE, self._handle_team_assign_event),
            (DISCONNECT_RE, self._handle_disconnect_event),
        ]

    def ensure_rcon_alive(self) -> None:
        """Best-effort health check for the RCON connection."""
        try:
            self.rcon("echo controller_ready")
        except Exception:
            logger.exception("RCON health-check failed")

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

    def parse_status_output(self, output: str) -> None:
        """Documentation."""
        logger.debug("parse_status_output start")
        for line in output.splitlines():
            match = STATUS_RE.match(line)
            if match:
                name = match.group("name")
                steam_id = f"[{match.group('steam_id')}]"
                TARGETS[name.upper()] = steam_id
                self.state.name_to_steam[name] = steam_id
                self.state.steam_to_name[steam_id] = name
        save_targets()
        logger.info("rcon status から TARGETS を更新しました")

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
                name.lower() == "tkmi"
                and self.state.rounds_played in (11, 23)
                and not self.state.round_awp_taunt_sent
            ):
                self.say("tkmiさん、そろそろ AWP 見たいですね")
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

        self.say(message)
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
            msg = random.choice(ROUND_CONTEXT_MESSAGES["pistol_round"]).format(
                ct=self.state.ct_score,
                t=self.state.t_score,
            )
            self._emit_commentary(msg, f"pistol_round_{self.state.round_number}", once_per_round=True)
            return

        if ct_buy == "full" and t_buy in {"eco", "pistol"}:
            msg = random.choice(ROUND_CONTEXT_MESSAGES["anti_eco_ct"]).format(ct=self.state.ct_score, t=self.state.t_score)
            self._emit_commentary(msg, f"anti_eco_ct_{self.state.round_number}", once_per_round=True)
        elif t_buy == "full" and ct_buy in {"eco", "pistol"}:
            msg = random.choice(ROUND_CONTEXT_MESSAGES["anti_eco_t"]).format(ct=self.state.ct_score, t=self.state.t_score)
            self._emit_commentary(msg, f"anti_eco_t_{self.state.round_number}", once_per_round=True)
        elif ct_buy == "full" and t_buy == "full":
            msg = random.choice(ROUND_CONTEXT_MESSAGES["full_buy"]).format(ct=self.state.ct_score, t=self.state.t_score)
            self._emit_commentary(msg, f"full_buy_{self.state.round_number}", once_per_round=True)

        if self.state.round_number > self.settings.max_rounds and abs(self.state.ct_score - self.state.t_score) <= 1:
            msg = random.choice(ROUND_CONTEXT_MESSAGES["ot_point"]).format(
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
        self.say(random.choice(ROUND_EVENTS.get("side_switch", [])))
        self.state.side_switch_announced = True
        self.state.last_side_switch_round = self.state.round_number
        self._swap_player_teams()
        self.state.streak_team = None
        self.state.streak_count = 0
        self.state.last_flow_comment_round = 0
        self.state.ct_match_point_announced = False
        self.state.t_match_point_announced = False

    def _is_side_switch_round(self, round_number: int) -> bool:
        regulation_switch = self.settings.max_rounds // 2 + 1
        if round_number == regulation_switch:
            return True
        # Overtime MR3 halves: first switch after 3 OT rounds, then every 6 rounds.
        ot_first_round = self.settings.max_rounds + 1
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
            self.say(f"CTチームの勝利！ {ct_score}-{t_score}")
        elif winner == "TERRORIST":
            self.say(f"Tチームの勝利！ {t_score}-{ct_score}")
        elif winner == "DRAW":
            self.say("引き分けです")
        else:
            self.say("試合終了")

    def handle_round_start(self, line: str) -> None:
        """Documentation."""
        if not self.state.live_started:
            return

        self.state.round_start_time = time.time()
        self.state.headshot_kills.clear()
        self.state.kill_streaks.clear()
        self.state.round_kills.clear()
        self.state.round_weapons_ct.clear()
        self.state.round_weapons_t.clear()
        self.state.round_comment_keys.clear()
        self.state.alive_ct.clear()
        self.state.alive_t.clear()
        self.state.clutch_active = False
        self.state.clutch_player = None
        self.state.clutch_enemy_count = 0
        self.state.one_v_one_announced = False
        self.state.last_kill_time = time.time()
        self.state.round_awp_taunt_sent = False

        if self.state.round_number == self.settings.max_rounds + 1:
            self.say(random.choice(ROUND_EVENTS.get("overtime_start", [])))
        elif self.state.round_number == self.settings.max_rounds + 4:
            self.say(random.choice(ROUND_EVENTS.get("overtime_late", [])))

        if self.state.round_number == 1 and self.state.live_started and not self.state.first_round_announced:
            self.say(random.choice(ROUND_EVENTS.get("first_round", [])))
            self.state.first_round_announced = True

        self._maybe_announce_side_switch()

    def handle_taunt(self, killer: str, kill_count: int) -> None:
        """Send a taunt message on 3-kill streaks."""
        if kill_count != 3:
            return

        candidates = TAUNT_MESSAGES.get(killer.upper()) or TAUNT_MESSAGES.get("__DEFAULT__", [])
        if candidates and random.random() < self.settings.taunt_chance:
            self.say(random.choice(candidates))

    def _announce_clutch_state(self, ct_alive: int, t_alive: int) -> None:
        """Announce clutch/1v1 state transitions once per round."""
        if ct_alive == 1 and t_alive == 1:
            if not self.state.one_v_one_announced:
                self.state.clutch_active = True
                self.state.one_v_one_announced = True
                self.say("1v1！最終決戦！")
                self.debug_print("[CLUTCH] 1v1 situation entered")
            return

        if self.state.clutch_active:
            return

        if ct_alive == 1 and t_alive >= 2:
            self.state.clutch_active = True
            self.state.clutch_player = list(self.state.alive_ct)[0]
            self.state.clutch_enemy_count = t_alive
            self.say(random.choice(CLUTCH_MESSAGES).format(player=self.state.clutch_player, count=t_alive))
            self.debug_print(f"[CLUTCH] {self.state.clutch_player} (CT) vs {t_alive} T")
            return

        if t_alive == 1 and ct_alive >= 2:
            self.state.clutch_active = True
            self.state.clutch_player = list(self.state.alive_t)[0]
            self.state.clutch_enemy_count = ct_alive
            self.say(random.choice(CLUTCH_MESSAGES).format(player=self.state.clutch_player, count=ct_alive))
            self.debug_print(f"[CLUTCH] {self.state.clutch_player} (T) vs {ct_alive} CT")
            return

    def should_commentate(self) -> bool:
        """Documentation."""
        return self.state.commentary_enabled and self.state.live_started
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
                message = random.choice(SILENCE_MESSAGES["even"])
            elif ct > t:
                message = random.choice(SILENCE_MESSAGES["ct_advantage"])
            elif t > ct:
                message = random.choice(SILENCE_MESSAGES["t_advantage"])
            else:
                message = random.choice(SILENCE_MESSAGES["balanced"])

            if self._emit_commentary(
                message,
                "silence",
                cooldown_seconds=self.settings.commentary_cooldown_seconds,
                once_per_round=True,
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

        if self.should_commentate():
            if self.state.round_start_time and time.time() - self.state.round_start_time <= 15:
                self.say(f"{victim} が開幕15秒以内にダウン")

            if "headshot" in line.lower():
                self.state.headshot_streaks[killer] = self.state.headshot_streaks.get(killer, 0) + 1
                if self.state.headshot_streaks[killer] == 3:
                    message = random.choice(HEADSHOT_STREAK_MESSAGES).format(player=killer)
                    self.say(message)
            else:
                self.state.headshot_streaks[killer] = 0

            if killer_team == victim_team and killer != victim and "BOT" not in line:
                message = random.choice(TEAM_KILL_MESSAGES).format(player=killer)
                self.say(message)
                return

            if victim_steam_id == "BOT":
                vt = victim_team
            else:
                vt = self.get_team(victim_steam_id)

            if vt == "CT":
                self.state.alive_ct.discard(victim)
            elif vt == "TERRORIST":
                self.state.alive_t.discard(victim)
            else:
                self.debug_print(f"[WARN] victim team unknown: {victim} ({victim_steam_id})")

            if killer_steam_id == "BOT":
                kt = killer_team
            else:
                kt = self.get_team(killer_steam_id)

            if kt == "CT":
                self.state.alive_ct.add(killer)
                self.state.round_weapons_ct.add(weapon.lower())
            elif kt == "TERRORIST":
                self.state.alive_t.add(killer)
                self.state.round_weapons_t.add(weapon.lower())
            else:
                self.debug_print(f"[WARN] killer team unknown: {killer} ({killer_steam_id})")

            self.state.kill_streaks[killer] = self.state.kill_streaks.get(killer, 0) + 1
            streak = self.state.kill_streaks[killer]

            if streak in KILL_STREAK_MESSAGES:
                # At 3-kill streak, prefer a player-specific taunt by probability.
                if streak == 3 and killer.upper() in TAUNT_MESSAGES:
                    if random.random() < self.settings.taunt_chance:
                        self.say(random.choice(TAUNT_MESSAGES[killer.upper()]))
                    else:
                        message = random.choice(KILL_STREAK_MESSAGES[streak]).format(player=killer)
                        self.say(message)
                else:
                    message = random.choice(KILL_STREAK_MESSAGES[streak]).format(player=killer)
                    self.say(message)

            if streak >= 5:
                ace_message = random.choice(ACE_MESSAGES).format(player=killer)
                self.say(ace_message)

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

        if cmd == "help":
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
                self.say("利用可能マップ: " + ", ".join(self.settings.available_maps))
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
                else:
                    self.say(f"'{selected}' はサポート外のマップです")
            return

        if cmd == "coin":
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
                self.rcon("mp_restartgame 1")
            else:
                self.say("このコマンドは管理者専用です")
            return

        if cmd == "lo3":
            self.state.match_finished = False
            self.state.live_started = True
            self.say("試合を Live on 3 で開始します")
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

        if cmd == "eloshuffle":
            players = list(TARGETS.keys())
            if len(players) < 2:
                self.say("プレイヤー数が足りません")
                return

            team_ct, team_t = elo_shuffle(players)
            self.say("CT (Elo): " + ", ".join(team_ct))
            self.say("T (Elo): " + ", ".join(team_t))

            assign_teams(team_ct, team_t)
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

        if cmd == "smartshuffle":
            players = list(TARGETS.keys())
            if len(players) < 2:
                self.say("プレイヤー数が足りません")
                return

            team_ct, team_t = smart_shuffle_balanced(players)
            self.say("CT (Smart): " + ", ".join(team_ct))
            self.say("T (Smart): " + ", ".join(team_t))
            assign_teams(team_ct, team_t)
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
            self.say(f"{team}蛛ｴ ({map_name}): {tactic}")
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
        logger.info("CONNECT_RE 荳閾ｴ: %s (%s)", name, steam_id)
        self.state.name_to_steam[name] = steam_id
        self.state.steam_to_name[steam_id] = name
        TARGETS[name.upper()] = steam_id
        logger.debug("TARGETS譖ｴ譁ｰ: %s => %s", name.upper(), steam_id)
        try:
            save_targets()
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

        self.say("試合終了！おつかれさまでした")
        self.say(f"全{self.state.rounds_played}ラウンドのハイライトです")
        for accolade_type, player, value in self.state.accolades:
            message = get_accolade_message(accolade_type, player, value)
            if message:
                self.say(message)

        self.say(f"{winner} の勝利！GG WP!")

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
        self.record_match_result(winner, ct_players, t_players)
        update_elo(winner, ct_players, t_players)
        save_elo()

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
        self.state.reset()
        self.state.current_map = normalize_map_name(new_map)
        self.setup_event_listeners()
        self.ensure_rcon_alive()
        self.reset_command_flags()

    def _handle_chat_command_event(self, match: re.Match[str], _line: str) -> None:
        player_name, steam_id, team, command, arg = match.groups()
        arg = arg or ""
        # Keep team/mapping fresh from chat lines as an additional source of truth.
        self.state.player_teams[player_name] = team
        self.state.temp_player_teams[player_name] = team
        self.state.name_to_steam[player_name] = steam_id
        self.state.steam_to_name[steam_id] = player_name
        logger.info("CHAT_CMD: %s (%s) [%s]: !%s %s", player_name, team, steam_id, command, arg)
        self.handle_chat_command(player_name, steam_id, team, command, arg)

    def _handle_player_team_event(self, match: re.Match[str], _line: str) -> None:
        name = match.group("name")
        steam_id = match.group("steam_id")
        team = match.group("team")
        self.state.temp_player_teams[name] = team
        self.state.player_teams[name] = team
        self.state.name_to_steam[name] = steam_id
        self.state.steam_to_name[steam_id] = name

    def _handle_team_assign_event(self, match: re.Match[str], _line: str) -> None:
        name = match.group("name")
        steam_id = match.group("steam_id")
        team = match.group("team")
        self.state.player_teams[name] = team
        self.state.name_to_steam[name] = steam_id
        self.state.steam_to_name[steam_id] = name
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
            steam_id = TARGETS.get(name)
            stats = PLAYER_STATS.setdefault(name, {"wins": 0, "losses": 0})
            if steam_id:
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
            steam_id = TARGETS.get(name)
            stats = PLAYER_STATS.setdefault(name, {"wins": 0, "losses": 0})
            if steam_id:
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
            "runtime settings: max_rounds=%d taunt_chance=%.2f silence=%ds idle=%ds",
            self.settings.max_rounds,
            self.settings.taunt_chance,
            self.settings.silence_seconds,
            self.settings.idle_comment_seconds,
        )
        load_stats()
        load_elo()
        load_targets()

        self.current_log_path = None
        self.log_fp = None

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
                self.log_fp.seek(0, os.SEEK_END)
                logger.info("ログ監視切り替え: %s", latest)

            line = self.log_fp.readline()
            if not line:
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
                message = random.choice(CHEER_MESSAGES).format(player=target)
                if self._emit_commentary(
                    message,
                    "idle_cheer",
                    cooldown_seconds=self.settings.commentary_cooldown_seconds,
                ):
                    self.state.last_kill_time = time.time()


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




