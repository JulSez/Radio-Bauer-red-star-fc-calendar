import unittest

from src.fetch import parse_espn


class FetchTests(unittest.TestCase):
    def test_parse_espn_fixture_and_convert_utc_to_paris(self):
        payload = {"events": [{
            "date": "2026-08-15T18:00:00Z",
            "week": {"number": 1},
            "links": [{"href": "https://example.test/match/1"}],
            "competitions": [{
                "competitors": [
                    {"homeAway": "home", "team": {"displayName": "Red Star FC"}},
                    {"homeAway": "away", "team": {"displayName": "Amiens SC"}},
                ],
                "venue": {"fullName": "Stade Bauer"},
                "status": {"type": {"dateTBD": False, "timeTBD": False}},
            }],
        }]}
        matches = parse_espn(payload, "https://example.test/api", "2026-08-18T08:00:00+00:00")
        self.assertEqual(1, len(matches))
        self.assertEqual("20:00", matches[0].time)
        self.assertEqual("confirmed", matches[0].time_status)
        self.assertEqual("https://example.test/match/1", matches[0].source_url)

    def test_tbd_fixture_has_no_invented_time(self):
        payload = {"events": [{
            "date": "2026-08-15T00:00:00Z",
            "week": {"number": 1},
            "competitions": [{
                "competitors": [
                    {"homeAway": "home", "team": {"displayName": "Amiens SC"}},
                    {"homeAway": "away", "team": {"displayName": "Red Star FC"}},
                ],
                "status": {"type": {"dateTBD": True, "timeTBD": True}},
            }],
        }]}
        match = parse_espn(payload, "https://example.test/api", "2026-08-18T08:00:00+00:00")[0]
        self.assertIsNone(match.time)
        self.assertEqual("provisional", match.date_status)
        self.assertEqual("unconfirmed", match.time_status)


if __name__ == "__main__":
    unittest.main()
