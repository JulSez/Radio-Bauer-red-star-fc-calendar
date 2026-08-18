"""Récupération des rencontres depuis une source sportive publique remplaçable."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from src.calendar import Match, TEAM, ValidationError, validate

# Le précédent chemin supposé du site du club renvoie 404. ESPN constitue donc la
# source sportive publique de secours, conformément à l'ordre de priorité du projet.
DEFAULT_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/fra.2/scoreboard"
    "?dates=20260801-20270630&limit=1000"
)
PARIS = ZoneInfo("Europe/Paris")


def _team_name(competitor: dict) -> str:
    team = competitor.get("team") or {}
    name = team.get("displayName") or team.get("name") or ""
    normalized = " ".join(name.casefold().replace("fc", "").replace("93", "").split())
    return TEAM if normalized == "red star" else name


def parse_espn(payload: dict, source_url: str, checked_at: str) -> list[Match]:
    """Convertit la réponse publique ESPN en rencontres Red Star."""
    matches = []
    for event in payload.get("events", []):
        competition = (event.get("competitions") or [{}])[0]
        competitors = competition.get("competitors") or []
        home = next((_team_name(c) for c in competitors if c.get("homeAway") == "home"), "")
        away = next((_team_name(c) for c in competitors if c.get("homeAway") == "away"), "")
        if TEAM.casefold() not in (home.casefold(), away.casefold()):
            continue
        week = (event.get("week") or competition.get("week") or {}).get("number")
        if not isinstance(week, int):
            raise ValidationError(f"numéro de journée absent pour {home} - {away}")
        raw_start = event.get("date") or competition.get("date")
        if not raw_start:
            raise ValidationError(f"date absente pour la journée {week}")
        start = datetime.fromisoformat(raw_start.replace("Z", "+00:00")).astimezone(PARIS)
        status = ((competition.get("status") or {}).get("type") or {})
        cancelled = status.get("name") in {"STATUS_CANCELED", "STATUS_CANCELLED"}
        # Une heure fournie par le flux est considérée confirmée uniquement lorsque
        # le statut ESPN ne la qualifie pas de date à déterminer.
        confirmed = not status.get("dateTBD", False) and not status.get("timeTBD", False)
        venue = (competition.get("venue") or {}).get("fullName")
        link = next((item.get("href") for item in event.get("links", []) if item.get("href")), source_url)
        matches.append(Match(
            competition="Ligue 2", season="2026-2027", round=week,
            home=home, away=away, date=start.date().isoformat(),
            time=start.strftime("%H:%M") if confirmed else None,
            date_status="confirmed" if confirmed else "provisional",
            time_status="confirmed" if confirmed else "unconfirmed",
            venue=venue, status="cancelled" if cancelled else "scheduled",
            source_url=link, checked_at=checked_at,
        ))
    return matches


def fetch(url: str = DEFAULT_URL) -> dict:
    req = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "red-star-calendar/1.0 (+https://github.com/JulSez/Radio-Bauer-red-star-fc-calendar)",
    })
    with urlopen(req, timeout=30) as response:
        payload = json.load(response)
    checked = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    matches = parse_espn(payload, url, checked)
    validate(matches)
    return {
        "metadata": {
            "source_name": "ESPN public scoreboard (source sportive de secours)",
            "source_url": url,
            "checked_at": checked,
        },
        "matches": [m.__dict__ for m in sorted(matches, key=lambda match: match.round)],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--output", type=Path, default=Path("data/competitions/ligue-2.json"))
    args = parser.parse_args()
    try:
        data = fetch(args.url)
    except (URLError, TimeoutError, ValidationError, json.JSONDecodeError) as exc:
        sys.exit(f"Récupération refusée; les fichiers publiés restent inchangés : {exc}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)


if __name__ == "__main__":
    main()
