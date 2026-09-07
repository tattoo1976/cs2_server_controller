import unittest

from controller import CHAT_CMD_RE


class ChatRegexTests(unittest.TestCase):
    def test_matches_ready_command(self) -> None:
        line = 'L 01/03/2026 - 18:18:05: "tattoo<2><[U:1:6111605]><TERRORIST>" say "!rdy"'
        match = CHAT_CMD_RE.search(line)
        self.assertIsNotNone(match)
        self.assertEqual(match.groups(), ("tattoo", "[U:1:6111605]", "TERRORIST", "rdy", None))

    def test_matches_command_with_argument(self) -> None:
        line = 'L 01/03/2026 - 18:18:10: "tattoo<2><[U:1:6111605]><CT>" say "!svr_help hello world"'
        match = CHAT_CMD_RE.search(line)
        self.assertIsNotNone(match)
        self.assertEqual(match.groups(), ("tattoo", "[U:1:6111605]", "CT", "svr_help", "hello world"))

    def test_matches_without_bang(self) -> None:
        line = 'L 01/03/2026 - 18:18:00: "tattoo<2><[U:1:6111605]><TERRORIST>" say "rdy"'
        match = CHAT_CMD_RE.search(line)
        self.assertIsNotNone(match)
        self.assertEqual(match.groups(), ("tattoo", "[U:1:6111605]", "TERRORIST", "rdy", None))

