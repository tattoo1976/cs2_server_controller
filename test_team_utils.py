import unittest

from team_utils import balanced_shuffle


class TeamUtilsTests(unittest.TestCase):
    def test_balanced_shuffle_keeps_even_player_counts_equal(self) -> None:
        players = [f"p{i}" for i in range(8)]
        ratings = {
            "p0": 100,
            "p1": 100,
            "p2": 100,
            "p3": 100,
            "p4": 1000,
            "p5": 1000,
            "p6": 1000,
            "p7": 1000,
        }

        team_ct, team_t = balanced_shuffle(players, ratings.__getitem__)

        self.assertEqual(len(team_ct), 4)
        self.assertEqual(len(team_t), 4)

    def test_balanced_shuffle_allows_one_player_difference_for_odd_counts(self) -> None:
        players = [f"p{i}" for i in range(9)]

        team_ct, team_t = balanced_shuffle(players, lambda _player: 1000)

        self.assertEqual({len(team_ct), len(team_t)}, {4, 5})


if __name__ == "__main__":
    unittest.main()
