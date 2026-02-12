import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import player_elo
import player_stats


class PersistenceTests(unittest.TestCase):
    def test_load_stats_supports_legacy_layout(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            stats_path = Path(td) / "player_stats.json"
            stats_path.write_text(
                json.dumps({"ALICE": {"wins": 3, "losses": 1}}, ensure_ascii=False),
                encoding="utf-8",
            )
            with mock.patch.object(player_stats, "PLAYER_STATS_FILE", str(stats_path)):
                player_stats.PLAYER_STATS.clear()
                player_stats.load_stats()
                self.assertEqual(player_stats.PLAYER_STATS["ALICE"]["wins"], 3)

    def test_save_stats_writes_schema_layout(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            stats_path = Path(td) / "player_stats.json"
            with mock.patch.object(player_stats, "PLAYER_STATS_FILE", str(stats_path)):
                player_stats.PLAYER_STATS.clear()
                player_stats.PLAYER_STATS["ALICE"] = {"wins": 1, "losses": 0}
                player_stats.save_stats()
            payload = json.loads(stats_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], player_stats.PLAYER_STATS_SCHEMA_VERSION)
            self.assertIn("ALICE", payload["players"])

    def test_load_elo_supports_legacy_layout(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            elo_path = Path(td) / "player_elo.json"
            elo_path.write_text(json.dumps({"ALICE": 1200}), encoding="utf-8")
            with mock.patch.object(player_elo, "PLAYER_ELO_FILE", str(elo_path)):
                player_elo.PLAYER_ELO.clear()
                player_elo.load_elo()
                self.assertEqual(player_elo.PLAYER_ELO["ALICE"], 1200)

    def test_save_elo_writes_schema_layout(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            elo_path = Path(td) / "player_elo.json"
            with mock.patch.object(player_elo, "PLAYER_ELO_FILE", str(elo_path)):
                player_elo.PLAYER_ELO.clear()
                player_elo.PLAYER_ELO["ALICE"] = 1100
                player_elo.save_elo()
            payload = json.loads(elo_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], player_elo.PLAYER_ELO_SCHEMA_VERSION)
            self.assertEqual(payload["ratings"]["ALICE"], 1100)

    def test_load_targets_normalizes_uppercase_keys(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            targets_path = Path(td) / "targets.json"
            targets_path.write_text(
                json.dumps({"test_user": "[U:1:100000]"}, ensure_ascii=False),
                encoding="utf-8",
            )
            with mock.patch.object(player_stats, "TARGETS_FILE", str(targets_path)):
                player_stats.TARGETS.clear()
                player_stats.load_targets()
                self.assertIn("TEST_USER", player_stats.TARGETS)


if __name__ == "__main__":
    unittest.main()
