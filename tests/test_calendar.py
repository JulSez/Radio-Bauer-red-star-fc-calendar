import json, unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from src.calendar import Match, ValidationError, render_ics, update_state, validate

def match(round=1, home="Red Star FC", away="Paris FC", day="2026-08-15", clock="20:00", venue="Stade Bauer"):
    return Match(competition="Ligue 2",season="2026-2027",round=round,home=home,away=away,date=day,time=clock,date_status="confirmed",time_status="confirmed" if clock else "unconfirmed",venue=venue,status="scheduled",source_url="https://example.test",checked_at="2026-08-01T09:00:00+00:00")

class CalendarTests(unittest.TestCase):
    def render(self,m):
        now=datetime(2026,8,1,tzinfo=timezone.utc); return render_ics([m],update_state([m],{},now),now)
    def test_timed_match_is_two_hours(self):
        text=self.render(match()); self.assertIn("DTSTART;TZID=Europe/Paris:20260815T200000",text); self.assertIn("DTEND;TZID=Europe/Paris:20260815T220000",text)
    def test_unknown_time_spans_day_before_through_day_after(self):
        text=self.render(match(clock=None)); self.assertIn("DTSTART;VALUE=DATE:20260814",text); self.assertIn("DTEND;VALUE=DATE:20260817",text); self.assertIn("horaire à confirmer",text)
    def test_provisional_date_is_explicit(self):
        m=match(clock=None); m=Match(**{**m.__dict__,"date_status":"provisional"})
        self.assertIn("date et horaire à confirmer",self.render(m))
    def test_home_busy_away_free(self):
        self.assertIn("TRANSP:OPAQUE",self.render(match())); self.assertIn("TRANSP:TRANSPARENT",self.render(match(home="Paris FC",away="Red Star FC")))
    def test_uid_survives_schedule_and_venue_changes(self):
        a=match(); b=match(day="2026-08-16",clock="21:00",venue="Autre stade"); self.assertEqual(a.uid,b.uid)
    def test_material_change_increments_sequence(self):
        now=datetime(2026,8,1,tzinfo=timezone.utc); a=match(); state=update_state([a],{},now); state=update_state([match(clock="21:00")],state,datetime(2026,8,2,tzinfo=timezone.utc)); self.assertEqual(1,state[a.uid]["sequence"])
    def test_duplicate_rejected(self):
        games=[match(round=i,away=f"Club {i}") for i in range(1,35)]; games[-1]=games[0]
        with self.assertRaisesRegex(ValidationError,"doublon|34 rencontres"): validate(games)
    def test_official_cup_match_is_separate_from_league_count(self):
        games=[match(round=i,away=f"Club {i}") for i in range(1,35)]
        cup=Match(**{**match(round=7,away="Club de coupe").__dict__,"competition":"Coupe de France"})
        validate(games+[cup]); self.assertNotEqual(games[6].uid,cup.uid)
    def test_minimal_ics_shape_and_folding(self):
        text=self.render(match(away="Équipe au nom extrêmement long qui force le repli réglementaire de la ligne iCalendar")); self.assertTrue(text.endswith("\r\n")); self.assertIn("BEGIN:VCALENDAR\r\n",text); self.assertIn("\r\n ",text); self.assertEqual(text.count("BEGIN:VEVENT"),1)

if __name__ == "__main__": unittest.main()
