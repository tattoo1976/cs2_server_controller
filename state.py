from dataclasses import dataclass, field
from typing import Dict, Set, List, Optional, Tuple
from config import MAX_ROUNDS


@dataclass
class MatchState:
    # Match flow
    first_round_announced: bool = False
    ct_wins: int = 0
    t_wins: int = 0
    round_number: int = 0
    last_round_winner: Optional[str] = None

    # 実況関連
    silence_comment_given: bool = False # ← これを追加！

    # Flags
    live_started: bool = False
    match_finished: bool = True
    side_switch_announced: bool = False
    round_awp_taunt_sent: bool = field(default=False)
 
    # Ready / coin
    rdy_ct: bool = False
    rdy_t: bool = False
    coin_used: bool = False
    coin_winner: Optional[str] = None
    side_select_active: bool = False

    # Per-player trackers
    headshot_streaks: Dict[str, int] = field(default_factory=dict)
    kill_streaks: Dict[str, int] = field(default_factory=dict)
    silent_streaks: Dict[str, int] = field(default_factory=dict)
    headshot_kills: Dict[str, int] = field(default_factory=dict)
    round_kills: Dict[str, int] = field(default_factory=dict)

    # Alive sets (player names)
    alive_ct: Set[str] = field(default_factory=set)
    alive_t: Set[str] = field(default_factory=set)

    # Clutch
    clutch_active: bool = False
    clutch_player: Optional[str] = None
    clutch_enemy_count: int = 0

    # Misc flags
    tkm_connected: bool = False
    awp_tkm_announced: bool = False

    # 1v1 tracking
    past_1v1_pairs: Set[Tuple[str, str]] = field(default_factory=set)
    one_v_one_announced: bool = False

    # Scores
    ct_score: int = 0
    t_score: int = 0

    # Timers
    round_start_time: Optional[float] = None
    last_kill_time: Optional[float] = None
    last_score_diff: int = 0

    # Streaks
    streak_team: Optional[str] = None
    streak_count: int = 0

    # Derived
    WIN_ROUNDS: int = field(init=False)

    # Commands
    chat_commands_enabled: bool = True

    # Temp/team mappings
    temp_player_teams: Dict[str, str] = field(default_factory=dict)
    player_teams: Dict[str, str] = field(default_factory=dict)

    # Commentary
    commentary_enabled: bool = True

    # Map / debug / accolades
    current_map: str = "de_dust2"
    debug_enabled: bool = False
    accolades: List[Tuple[str, str, float]] = field(default_factory=list)

    # Account mappings
    accountid_to_name: Dict[str, str] = field(default_factory=dict)
    accountid_to_steamid: Dict[str, str] = field(default_factory=dict)
    name_to_steam: Dict[str, str] = field(default_factory=dict)
    steam_to_name: Dict[str, str] = field(default_factory=dict)

    # Player lists used for match recording
    ct_players: List[str] = field(default_factory=list)
    t_players: List[str] = field(default_factory=list)

    # Round tracking
    rounds_played: int = 0
    last_flow_comment_round: int = 0
    ct_match_point_announced: bool = False
    t_match_point_announced: bool = False
    last_side_switch_round: int = 0
    round_weapons_ct: Set[str] = field(default_factory=set)
    round_weapons_t: Set[str] = field(default_factory=set)
    json_parse_error_count: int = 0
    json_recovery_count: int = 0

    # Anti-spam message tracking
    last_comment_at: Dict[str, float] = field(default_factory=dict)
    round_comment_keys: Set[str] = field(default_factory=set)

    def __post_init__(self):
        # Compute derived values
        """
        インスタンスの初期化が完了したら、WIN_ROUNDS などの派生値を計算します。
        """
        self.WIN_ROUNDS = MAX_ROUNDS // 2 + 1

    def reset(self) -> None:
        """新しい一致のために状態をデフォルトにリセットします (構成から派生したフィールドを保持します)。"""
        self.first_round_announced = False
        self.silence_comment_given = False # ← ここに追加！
        self.ct_wins = 0
        self.t_wins = 0
        self.round_number = 0
        self.last_round_winner = None

        self.live_started = False
        self.match_finished = True
        self.side_switch_announced = False

        self.rdy_ct = False
        self.rdy_t = False

        self.coin_used = False
        self.coin_winner = None
        self.side_select_active = False

        self.headshot_streaks.clear()
        self.kill_streaks.clear()
        self.silent_streaks.clear()
        self.headshot_kills.clear()
        self.round_kills.clear()

        self.alive_ct.clear()
        self.alive_t.clear()

        self.clutch_active = False
        self.clutch_player = None
        self.clutch_enemy_count = 0

        self.tkm_connected = False
        self.awp_tkm_announced = False

        self.past_1v1_pairs.clear()
        self.one_v_one_announced = False

        self.ct_score = 0
        self.t_score = 0

        self.round_start_time = None
        self.last_kill_time = None
        self.last_score_diff = 0

        self.streak_team = None
        self.streak_count = 0

        # WIN_ROUNDS remains derived from MAX_ROUNDS

        self.chat_commands_enabled = True

        self.temp_player_teams.clear()
        self.player_teams.clear()

        self.commentary_enabled = True

        self.current_map = "de_dust2"
        self.debug_enabled = False
        self.accolades.clear()

        self.accountid_to_name.clear()
        self.accountid_to_steamid.clear()
        self.name_to_steam.clear()
        self.steam_to_name.clear()

        self.ct_players.clear()
        self.t_players.clear()

        self.rounds_played = 0
        self.last_flow_comment_round = 0
        self.ct_match_point_announced = False
        self.t_match_point_announced = False
        self.last_side_switch_round = 0
        self.round_weapons_ct.clear()
        self.round_weapons_t.clear()
        self.json_parse_error_count = 0
        self.json_recovery_count = 0
        self.last_comment_at.clear()
        self.round_comment_keys.clear()


