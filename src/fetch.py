"""Official-site adapter. It extracts schema.org SportsEvent JSON-LD without dependencies."""
from __future__ import annotations
import argparse, json, re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

from src.calendar import Match, TEAM, ValidationError, validate

DEFAULT_URL = "https://www.redstar.fr/calendrier-resultats/"

def _events(value):
    if isinstance(value, dict):
        if value.get("@type") == "SportsEvent": yield value
        for child in value.values(): yield from _events(child)
    elif isinstance(value, list):
        for child in value: yield from _events(child)

def fetch(url: str = DEFAULT_URL) -> dict:
    req = Request(url, headers={"User-Agent": "red-star-calendar/1.0 (+https://github.com/JulSez/Radio-Bauer-red-star-fc-calendar)"})
    with urlopen(req, timeout=30) as response: body = response.read().decode("utf-8")
    scripts = re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', body, re.I | re.S)
    checked = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    matches = []
    for script in scripts:
        try: roots = json.loads(script)
        except json.JSONDecodeError: continue
        for event in _events(roots):
            home = (event.get("homeTeam") or {}).get("name", "")
            away = (event.get("awayTeam") or {}).get("name", "")
            if TEAM.casefold() not in (home.casefold(), away.casefold()): continue
            start = event.get("startDate", "")
            day, clock = start[:10], (start[11:16] if "T" in start else None)
            round_match = re.search(r"(?:Journée|J)\s*(\d+)", event.get("name", ""), re.I)
            if not round_match: continue
            venue = (event.get("location") or {}).get("name") if isinstance(event.get("location"), dict) else None
            matches.append(Match("Ligue 2", "2026-2027", int(round_match.group(1)), home, away, day, clock, "confirmed" if clock else "provisional", "confirmed" if clock else "unconfirmed", venue, "scheduled", url, checked))
    validate(matches)
    return {"metadata": {"source_url": url, "checked_at": checked}, "matches": [m.__dict__ for m in sorted(matches, key=lambda x: x.round)]}

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--url", default=DEFAULT_URL); parser.add_argument("--output", type=Path, default=Path("data/competitions/ligue-2.json")); args = parser.parse_args()
    try:
        data = fetch(args.url)
    except (URLError, TimeoutError, ValidationError) as exc:
        sys.exit(f"Récupération refusée; les fichiers publiés restent inchangés : {exc}")
    args.output.parent.mkdir(exist_ok=True); tmp = args.output.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); tmp.replace(args.output)

if __name__ == "__main__": main()
