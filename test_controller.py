import time
import unittest
from unittest import mock

from controller import Controller, KILL_REGEX
from runtime_config import RuntimeConfig
from state import MatchState
from tactics import normalize_map_name


class ControllerTests(unittest.TestCase):
    def make_controller(
        self,
        settings: RuntimeConfig | None = None,
    ) -> tuple[Controller, list[str], list[str]]:
        rcon_calls: list[str] = []
        messages: list[str] = []

        def fake_rcon(cmd: str) -> str:
            rcon_calls.append(cmd)
            return ""

        def fake_say(msg: str) -> None:
            messages.append(msg)

        return Controller(fake_rcon, fake_say, MatchState(), settings=settings), rcon_calls, messages

    def test_map_change_resets_command_flags(self) -> None:
        controller, _, _ = self.make_controller()
        controller.state.coin_used = True
        controller.state.side_select_active = True
        controller.state.rdy_ct = True
        controller.state.rdy_t = True

        controller.handle_line('Loading map "de_mirage"')

        self.assertEqual(controller.state.current_map, "de_mirage")
        self.assertFalse(controller.state.coin_used)
        self.assertFalse(controller.state.side_select_active)
        self.assertFalse(controller.state.rdy_ct)
        self.assertFalse(controller.state.rdy_t)

    def test_apply_server_password_sends_sv_password(self) -> None:
        settings = RuntimeConfig(server_password="1122", available_maps=["dust2"])
        controller, rcon_calls, _ = self.make_controller(settings=settings)

        controller.apply_server_password()

        self.assertIn('sv_password "1122"', rcon_calls)

    def test_check_idle_announces_after_30_seconds(self) -> None:
        controller, _, messages = self.make_controller()
        controller.state.live_started = True
        controller.state.commentary_enabled = True
        controller.state.last_kill_time = time.time() - 31
        controller.state.alive_ct = {"CT_PLAYER"}

        with mock.patch("controller.random.choice", side_effect=lambda seq: seq[0]):
            controller.check_idle()

        self.assertEqual(len(messages), 1)
        self.assertGreater(controller.state.last_kill_time, time.time() - 5)

    def test_handle_line_dispatches_chat_command(self) -> None:
        controller, _, _ = self.make_controller()

        with mock.patch.object(controller, "handle_chat_command") as handler:
            controller.handle_line(
                'L 01/03/2026 - 18:18:05: "tattoo<2><[U:1:6111605]><CT>" say "!help hello world"'
            )

        handler.assert_called_once_with(
            "tattoo",
            "[U:1:6111605]",
            "CT",
            "help",
            "hello world",
        )

    def test_side_switch_announced_once_at_round_13(self) -> None:
        controller, _, messages = self.make_controller()
        controller.state.live_started = True
        controller.state.round_number = 13
        controller.state.side_switch_announced = False
        controller.state.player_teams = {"alice": "CT", "bob": "TERRORIST"}

        with mock.patch("controller.random.choice", side_effect=lambda seq: seq[0]):
            controller.handle_round_start("Round_Start")

        self.assertTrue(controller.state.side_switch_announced)
        self.assertEqual(controller.state.player_teams["alice"], "TERRORIST")
        self.assertEqual(controller.state.player_teams["bob"], "CT")
        self.assertEqual(len(messages), 1)

    def test_overtime_side_switch_at_round_28(self) -> None:
        controller, _, messages = self.make_controller()
        controller.state.live_started = True
        controller.state.round_number = 28
        controller.state.player_teams = {"alice": "CT", "bob": "TERRORIST"}

        with mock.patch("controller.random.choice", side_effect=lambda seq: seq[0]):
            controller.handle_round_start("Round_Start")

        self.assertEqual(controller.state.player_teams["alice"], "TERRORIST")
        self.assertEqual(controller.state.player_teams["bob"], "CT")
        self.assertEqual(controller.state.last_side_switch_round, 28)
        self.assertGreaterEqual(len(messages), 1)

    def test_no_overtime_side_switch_at_round_27(self) -> None:
        controller, _, messages = self.make_controller()
        controller.state.live_started = True
        controller.state.round_number = 27
        controller.state.player_teams = {"alice": "CT", "bob": "TERRORIST"}

        with mock.patch("controller.random.choice", side_effect=lambda seq: seq[0]):
            controller.handle_round_start("Round_Start")

        self.assertEqual(controller.state.player_teams["alice"], "CT")
        self.assertEqual(controller.state.player_teams["bob"], "TERRORIST")
        self.assertEqual(messages, [])

    def test_round_start_rebuilds_alive_from_team_assignments(self) -> None:
        controller, _, _ = self.make_controller()
        controller.state.live_started = True
        controller.state.round_number = 2
        controller.state.player_teams = {
            "ct1": "CT",
            "ct2": "CT",
            "ct3": "CT",
            "ct4": "CT",
            "t1": "TERRORIST",
            "t2": "TERRORIST",
            "t3": "TERRORIST",
            "t4": "TERRORIST",
        }
        controller.state.alive_ct = {"stale_ct_only"}
        controller.state.alive_t = {"stale_t_only"}

        controller.handle_round_start("Round_Start")

        self.assertEqual(controller.state.alive_ct, {"ct1", "ct2", "ct3", "ct4"})
        self.assertEqual(controller.state.alive_t, {"t1", "t2", "t3", "t4"})

    def test_round_start_filters_out_disconnected_players_from_alive_sets(self) -> None:
        controller, _, _ = self.make_controller()
        controller.state.live_started = True
        controller.state.round_number = 2
        controller.state.player_teams = {
            "ct1": "CT",
            "stale_ct": "CT",
            "t1": "TERRORIST",
            "stale_t": "TERRORIST",
        }

        # status contains only ct1 and t1, so stale_* must be pruned.
        status_output = '\n'.join(
            [
                '  1 "ct1" [U:1:111]',
                '  2 "t1" [U:1:222]',
            ]
        )
        controller.rcon = lambda cmd: status_output if cmd == "status" else ""

        controller.handle_round_start("Round_Start")

        self.assertEqual(controller.state.alive_ct, {"ct1"})
        self.assertEqual(controller.state.alive_t, {"t1"})

    def test_clutch_not_announced_for_1v0(self) -> None:
        controller, _, messages = self.make_controller()
        controller.state.alive_ct = {"ct_one"}
        controller.state.alive_t = set()

        controller._announce_clutch_state(ct_alive=1, t_alive=0)

        self.assertFalse(controller.state.clutch_active)
        self.assertEqual(messages, [])

    def test_clutch_announced_for_1v3(self) -> None:
        controller, _, messages = self.make_controller()
        controller.state.alive_ct = {"ct_one"}
        controller.state.alive_t = {"t1", "t2", "t3"}

        with mock.patch("controller.random.choice", side_effect=lambda seq: seq[0]):
            controller._announce_clutch_state(ct_alive=1, t_alive=3)

        self.assertTrue(controller.state.clutch_active)
        self.assertEqual(controller.state.clutch_player, "ct_one")
        self.assertEqual(controller.state.clutch_enemy_count, 3)
        self.assertEqual(len(messages), 1)

    def test_one_v_one_announced_after_clutch(self) -> None:
        controller, _, messages = self.make_controller()
        controller.state.alive_ct = {"ct_one"}
        controller.state.alive_t = {"t1", "t2", "t3"}

        with mock.patch("controller.random.choice", side_effect=lambda seq: seq[0]):
            controller._announce_clutch_state(ct_alive=1, t_alive=3)

        controller.state.alive_t = {"t1"}
        controller._announce_clutch_state(ct_alive=1, t_alive=1)

        self.assertTrue(controller.state.clutch_active)
        self.assertTrue(controller.state.one_v_one_announced)
        self.assertEqual(len(messages), 2)

    def test_bot_killer_is_not_added_to_alive_sets(self) -> None:
        controller, _, _ = self.make_controller()
        controller.state.alive_ct = {"ct1"}
        controller.state.alive_t = {"t1"}
        line = '"BOT Mike<5><BOT><TERRORIST>" killed "ct1<2><[U:1:111]><CT>" with "ak47"'
        match = KILL_REGEX.search(line)
        self.assertIsNotNone(match)

        controller.handle_kill(line, match)  # type: ignore[arg-type]

        self.assertNotIn("BOT Mike", controller.state.alive_t)

    def test_round_start_excludes_bot_named_like_human_via_steamid(self) -> None:
        controller, _, _ = self.make_controller()
        controller.state.live_started = True
        controller.state.round_number = 2
        controller.state.player_teams = {
            "Mangos": "CT",
            "real_ct": "CT",
            "real_t": "TERRORIST",
        }
        controller.state.name_to_steam = {
            "Mangos": "BOT",
            "real_ct": "[U:1:111]",
            "real_t": "[U:1:222]",
        }
        status_output = '\n'.join(
            [
                '  1 "real_ct" [U:1:111]',
                '  2 "real_t" [U:1:222]',
            ]
        )
        controller.rcon = lambda cmd: status_output if cmd == "status" else ""

        controller.handle_round_start("Round_Start")

        self.assertNotIn("Mangos", controller.state.alive_ct)
        self.assertEqual(controller.state.alive_ct, {"real_ct"})

    def test_kill_with_name_case_variation_does_not_duplicate_alive_player(self) -> None:
        controller, _, _ = self.make_controller()
        controller.state.alive_ct = {"BRAD"}
        controller.state.alive_t = {"t1"}
        controller.state.steam_to_name = {"[U:1:111]": "BRAD", "[U:1:222]": "t1"}
        controller.state.name_to_steam = {"BRAD": "[U:1:111]", "t1": "[U:1:222]"}
        controller.state.player_teams = {"BRAD": "CT", "t1": "TERRORIST"}

        line = '"brad<2><[U:1:111]><CT>" killed "t1<3><[U:1:222]><TERRORIST>" with "ak47"'
        match = KILL_REGEX.search(line)
        self.assertIsNotNone(match)

        controller.handle_kill(line, match)  # type: ignore[arg-type]

        self.assertEqual(controller.state.alive_ct, {"BRAD"})
        self.assertEqual(len(controller.state.alive_ct), 1)

    def test_score_flow_announces_streak(self) -> None:
        controller, _, messages = self.make_controller()
        controller.state.live_started = True
        controller.state.commentary_enabled = True
        controller.state.round_number = 5
        controller.state.ct_score = 3
        controller.state.t_score = 1
        controller.state.streak_team = "CT"
        controller.state.streak_count = 2

        controller._comment_on_score_flow(prev_ct=2, prev_t=1)

        self.assertEqual(controller.state.streak_count, 3)
        self.assertEqual(len(messages), 1)

    def test_score_flow_match_point_once(self) -> None:
        controller, _, messages = self.make_controller()
        controller.state.live_started = True
        controller.state.commentary_enabled = True
        controller.state.round_number = 20
        controller.state.ct_score = controller.state.WIN_ROUNDS - 1
        controller.state.t_score = 8

        controller._comment_on_score_flow(prev_ct=controller.state.WIN_ROUNDS - 2, prev_t=8)
        controller.state.round_number = 21
        controller.state.ct_score = controller.state.WIN_ROUNDS
        controller._comment_on_score_flow(prev_ct=controller.state.WIN_ROUNDS - 1, prev_t=8)

        self.assertTrue(controller.state.ct_match_point_announced)
        self.assertEqual(len(messages), 1)

    def test_normalize_map_name_accepts_short_name(self) -> None:
        self.assertEqual(normalize_map_name("mirage"), "de_mirage")
        self.assertEqual(normalize_map_name("de_inferno"), "de_inferno")

    def test_map_command_updates_current_map(self) -> None:
        controller, rcon_calls, _ = self.make_controller()
        controller.handle_chat_command("tattoo", "[U:1:6111605]", "CT", "map", "mirage")

        self.assertEqual(controller.state.current_map, "de_mirage")
        self.assertIn("changelevel de_mirage", rcon_calls)

    def test_map_command_supports_cache(self) -> None:
        controller, rcon_calls, _ = self.make_controller()
        controller.handle_chat_command("tattoo", "[U:1:6111605]", "CT", "map", "cache")

        self.assertEqual(controller.state.current_map, "de_cache")
        self.assertIn("changelevel de_cache", rcon_calls)

    def test_tactics_uses_normalized_current_map(self) -> None:
        controller, _, _ = self.make_controller()
        controller.state.current_map = "mirage"

        with mock.patch("controller.get_tactic", return_value="TACTIC") as get_tactic_mock:
            controller.handle_chat_command("tattoo", "[U:1:6111605]", "CT", "tactics", "")

        get_tactic_mock.assert_called_once_with("CT", "de_mirage")

    def test_smartshuffle_uses_connected_players_only(self) -> None:
        fake_status = ' 1 "tattoo" [U:1:6111605] active\n 2 "ton" [U:1:39882348] active\n'

        def rcon_with_status(cmd: str) -> str:
            return fake_status if cmd == "status" else ""

        controller = Controller(rcon_with_status, lambda msg: None, MatchState())

        with mock.patch.dict(
            "controller.TARGETS",
            {
                "TATTOO": "[U:1:6111605]",
                "TON": "[U:1:39882348]",
                "OFFLINE": "[U:1:9999999]",
            },
            clear=True,
        ), mock.patch(
            "controller.smart_shuffle_balanced",
            return_value=(["TATTOO"], ["TON"]),
        ) as smart_mock, mock.patch("controller.assign_teams") as assign_mock, mock.patch(
            "controller.ensure_players_initialized", return_value=[]
        ) as ensure_mock:
            controller.handle_chat_command("tattoo", "[U:1:6111605]", "CT", "smartshuffle", "")

        smart_mock.assert_called_once_with(["TATTOO", "TON"])
        ensure_mock.assert_called_once_with(["TATTOO", "TON"], 1000)
        assign_mock.assert_called_once()
        args, _ = assign_mock.call_args
        self.assertEqual(args[0], ["TATTOO"])
        self.assertEqual(args[1], ["TON"])

    def test_smartshuffle_accepts_hash_prefixed_status_output(self) -> None:
        fake_status = '# 1 "tattoo" [U:1:6111605] 00:12 15 0 active 196608\n# 2 "ton" [U:1:39882348] 00:10 22 0 active 196608\n'

        def rcon_with_status(cmd: str) -> str:
            return fake_status if cmd == "status" else ""

        controller = Controller(rcon_with_status, lambda msg: None, MatchState())

        with mock.patch.dict(
            "controller.TARGETS",
            {},
            clear=True,
        ), mock.patch(
            "controller.smart_shuffle_balanced",
            return_value=(["TATTOO"], ["TON"]),
        ) as smart_mock, mock.patch("controller.assign_teams") as assign_mock, mock.patch(
            "controller.ensure_players_initialized", return_value=[]
        ):
            controller.handle_chat_command("tattoo", "[U:1:6111605]", "CT", "smartshuffle", "")

        smart_mock.assert_called_once_with(["TATTOO", "TON"])
        assign_mock.assert_called_once()

    def test_smartshuffle_falls_back_to_tracked_players_when_status_unparsed(self) -> None:
        def rcon_with_unparsed_status(cmd: str) -> str:
            return "hostname: test server\nplayers : 8 humans, 0 bots\n" if cmd == "status" else ""

        controller = Controller(rcon_with_unparsed_status, lambda msg: None, MatchState())
        players = [f"p{i}" for i in range(8)]
        controller.state.player_teams = {
            player: "CT" if index < 4 else "TERRORIST"
            for index, player in enumerate(players)
        }
        controller.state.name_to_steam = {
            player: f"[U:1:{1000 + index}]"
            for index, player in enumerate(players)
        }

        with mock.patch(
            "controller.smart_shuffle_balanced",
            return_value=(players[:4], players[4:]),
        ) as smart_mock, mock.patch("controller.assign_teams") as assign_mock, mock.patch(
            "controller.ensure_players_initialized", return_value=[]
        ) as ensure_mock:
            controller.handle_chat_command("tattoo", "[U:1:6111605]", "CT", "smartshuffle", "")

        smart_mock.assert_called_once_with(players)
        ensure_mock.assert_called_once_with(players, 1000)
        assign_mock.assert_called_once()

    def test_lo3_limits_overtime_to_one_period(self) -> None:
        controller, rcon_calls, _ = self.make_controller()

        with mock.patch("controller.time.sleep"):
            controller.handle_chat_command("tattoo", "[U:1:6111605]", "CT", "lo3", "")

        self.assertIn("mp_overtime_enable 1", rcon_calls)
        self.assertIn("mp_overtime_maxrounds 6", rcon_calls)
        self.assertIn("mp_overtime_limit 1", rcon_calls)

    def test_side_switch_round_uses_runtime_max_rounds(self) -> None:
        settings = RuntimeConfig(max_rounds=30, available_maps=["dust2"])
        controller, _, messages = self.make_controller(settings=settings)
        controller.state.live_started = True
        controller.state.round_number = 16
        controller.state.player_teams = {"alice": "CT", "bob": "TERRORIST"}

        with mock.patch("controller.random.choice", side_effect=lambda seq: seq[0]):
            controller.handle_round_start("Round_Start")

        self.assertEqual(controller.state.player_teams["alice"], "TERRORIST")
        self.assertEqual(controller.state.player_teams["bob"], "CT")
        self.assertEqual(len(messages), 1)

    def test_idle_commentary_has_cooldown(self) -> None:
        settings = RuntimeConfig(
            idle_comment_seconds=0,
            commentary_cooldown_seconds=60,
            available_maps=["dust2"],
        )
        controller, _, messages = self.make_controller(settings=settings)
        controller.state.live_started = True
        controller.state.commentary_enabled = True
        controller.state.alive_ct = {"CT_PLAYER"}
        controller.state.last_kill_time = time.time() - 31

        with mock.patch("controller.random.choice", side_effect=lambda seq: seq[0]):
            controller.check_idle()
            controller.state.last_kill_time = time.time() - 31
            controller.check_idle()

        self.assertEqual(len(messages), 1)

    def test_round_context_full_buy_commentary(self) -> None:
        settings = RuntimeConfig(
            commentary_cooldown_seconds=0,
            score_flow_cooldown_seconds=0,
            round_context_enabled=True,
            available_maps=["dust2"],
        )
        controller, _, messages = self.make_controller(settings=settings)
        controller.state.live_started = True
        controller.state.commentary_enabled = True
        controller.state.round_number = 5
        controller.state.ct_score = 3
        controller.state.t_score = 2
        controller.state.round_weapons_ct = {"m4a1"}
        controller.state.round_weapons_t = {"ak47"}

        with mock.patch("controller.random.choice", side_effect=lambda seq: seq[0]):
            controller._comment_on_score_flow(prev_ct=2, prev_t=2)

        self.assertEqual(len(messages), 1)
        self.assertIn("フルバイ", messages[0])

    def test_json_parser_recovery_on_unbalanced_markers(self) -> None:
        controller, _, _ = self.make_controller()
        controller.handle_line("JSON_END")
        self.assertEqual(controller.state.json_parse_error_count, 1)
        self.assertEqual(controller.state.json_recovery_count, 1)
        self.assertFalse(controller.in_json_block)

    def test_collect_team_players_uses_multiple_sources(self) -> None:
        controller, _, _ = self.make_controller()
        controller.state.player_teams = {"alice": "CT"}
        controller.state.temp_player_teams = {"bob": "CT", "charlie": "TERRORIST"}
        controller.state.steam_to_name = {}

        ct = controller._collect_team_players("CT")
        t = controller._collect_team_players("TERRORIST")

        self.assertEqual(ct, ["alice", "bob"])
        self.assertEqual(t, ["charlie"])


if __name__ == "__main__":
    unittest.main()
