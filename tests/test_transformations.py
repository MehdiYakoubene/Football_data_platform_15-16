from __future__ import annotations

import unittest

from src.transform.build_facts import add_turnover_flags
from src.transform.clean_events import clean_events, is_progressive


def named(identifier: int, name: str) -> dict[str, object]:
    return {"id": identifier, "name": name}


class CleanEventsTest(unittest.TestCase):
    def test_flattens_pass_and_shot_fields(self) -> None:
        events = [
            {
                "id": "event-pass",
                "index": 1,
                "period": 1,
                "minute": 10,
                "second": 5,
                "type": named(30, "Pass"),
                "team": named(1, "Team A"),
                "player": named(10, "Player A"),
                "possession": 4,
                "possession_team": named(1, "Team A"),
                "play_pattern": named(1, "Regular Play"),
                "location": [70, 40],
                "pass": {"end_location": [90, 42], "recipient": named(11, "Player B"), "shot_assist": True},
            },
            {
                "id": "event-shot",
                "index": 2,
                "period": 1,
                "minute": 11,
                "second": 2,
                "type": named(16, "Shot"),
                "team": named(1, "Team A"),
                "player": named(10, "Player A"),
                "possession": 4,
                "possession_team": named(1, "Team A"),
                "play_pattern": named(1, "Regular Play"),
                "location": [108, 38],
                "shot": {"statsbomb_xg": 0.32, "outcome": named(97, "Goal")},
            },
        ]

        frame = clean_events(events, match_id=99)

        self.assertEqual(frame.loc[0, "event_uuid"], "event-pass")
        self.assertTrue(frame.loc[0, "pass_complete"])
        self.assertTrue(frame.loc[0, "pass_into_final_third"])
        self.assertEqual(frame.loc[0, "pass_recipient_name"], "Player B")
        self.assertTrue(frame.loc[0, "pass_shot_assist"])
        self.assertFalse(frame.loc[0, "pass_goal_assist"])
        self.assertEqual(frame.loc[1, "shot_xg"], 0.32)
        self.assertEqual(frame.loc[1, "shot_outcome"], "Goal")

    def test_progression_uses_normalized_attack_direction(self) -> None:
        events = [
            {
                "id": "shot-left",
                "index": 1,
                "period": 1,
                "minute": 1,
                "second": 0,
                "type": named(16, "Shot"),
                "team": named(1, "Team A"),
                "player": named(10, "Player A"),
                "possession": 1,
                "possession_team": named(1, "Team A"),
                "play_pattern": named(1, "Regular Play"),
                "location": [12, 40],
                "shot": {"statsbomb_xg": 0.1, "outcome": named(98, "Saved")},
            },
            {
                "id": "pass-left",
                "index": 2,
                "period": 1,
                "minute": 2,
                "second": 0,
                "type": named(30, "Pass"),
                "team": named(1, "Team A"),
                "player": named(10, "Player A"),
                "possession": 1,
                "possession_team": named(1, "Team A"),
                "play_pattern": named(1, "Regular Play"),
                "location": [60, 40],
                "pass": {"end_location": [40, 40]},
            },
        ]

        frame = clean_events(events, match_id=100)
        pass_row = frame.loc[frame["event_uuid"].eq("pass-left")].iloc[0]

        self.assertTrue(pass_row["coordinates_flipped"])
        self.assertEqual(pass_row["norm_x"], 60)
        self.assertEqual(pass_row["norm_end_x"], 80)
        self.assertTrue(pass_row["pass_into_final_third"])

    def test_turnover_flags_include_incomplete_passes(self) -> None:
        events = [
            {
                "id": "bad-pass",
                "index": 1,
                "period": 1,
                "minute": 1,
                "second": 0,
                "type": named(30, "Pass"),
                "team": named(1, "Team A"),
                "player": named(10, "Player A"),
                "possession": 1,
                "possession_team": named(1, "Team A"),
                "play_pattern": named(1, "Regular Play"),
                "location": [30, 20],
                "pass": {"end_location": [50, 20], "outcome": named(9, "Incomplete")},
            }
        ]

        frame = add_turnover_flags(clean_events(events, match_id=101))

        self.assertFalse(frame.loc[0, "pass_complete"])
        self.assertTrue(frame.loc[0, "is_turnover"])

    def test_progressive_threshold(self) -> None:
        self.assertTrue(is_progressive(60, 40, 85, 40))
        self.assertFalse(is_progressive(60, 40, 65, 40))


if __name__ == "__main__":
    unittest.main()
