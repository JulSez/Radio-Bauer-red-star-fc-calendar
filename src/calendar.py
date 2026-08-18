from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass, asdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
TEAM = "Red Star FC"
EXPECTED_LEAGUE_MATCHES = 34
LEAGUE = "Ligue 2"


class ValidationError(ValueError):
    pass


@dataclass(frozen=True)
class Match:
    competition: str
    season: str
    round: int
    home: str
    away: str
    date: str
    time: str | None = None
    date_status: str = "confirmed"
    time_status: str = "unconfirmed"
    venue: str | None = None
    status: str = "scheduled"
    source_url: str = ""
    checked_at: str = ""

    @property
    def is_home(self): return self.home.casefold() == TEAM.casefold()
    @property
    def opponent(self): return self.away if self.is_home else self.home
    @property
    def uid(self):
        identity = f"{self.season}|{self.competition}|{self.round}|{self.home}|{self.away}".casefold()
        return hashlib.sha256(identity.encode()).hexdigest()[:24] + "@red-star-calendar"


def load_matches(path: Path) -> tuple[list[Match], list[dict]]:
    paths = sorted(path.glob("*.json")) if path.is_dir() else [path]
    matches, metadata = [], []
    for source in paths:
        raw = json.loads(source.read_text(encoding="utf-8"))
        matches.extend(Match(**item) for item in raw["matches"])
        metadata.append(raw.get("metadata", {}))
    return matches, metadata


def validate(matches: list[Match], expected: int = EXPECTED_LEAGUE_MATCHES) -> None:
    league_matches = [m for m in matches if m.competition == LEAGUE]
    if len(league_matches) != expected:
        raise ValidationError(f"Ligue 2: {expected} rencontres attendues, {len(league_matches)} reçues; publication refusée")
    uids: set[str] = set()
    rounds: set[tuple[str, int]] = set()
    for match in matches:
        try: date.fromisoformat(match.date)
        except ValueError as exc: raise ValidationError(f"date invalide J{match.round}: {match.date}") from exc
        if match.date_status not in {"confirmed", "provisional"}:
            raise ValidationError(f"statut de date invalide J{match.round}: {match.date_status}")
        if match.time_status not in {"confirmed", "unconfirmed"}:
            raise ValidationError(f"statut d'horaire invalide J{match.round}: {match.time_status}")
        if match.time:
            try: time.fromisoformat(match.time)
            except ValueError as exc: raise ValidationError(f"horaire invalide J{match.round}: {match.time}") from exc
        if bool(match.time) != (match.time_status == "confirmed"):
            raise ValidationError(f"J{match.round}: incohérence entre time et time_status")
        if (match.home.casefold() == TEAM.casefold()) == (match.away.casefold() == TEAM.casefold()):
            raise ValidationError(f"J{match.round}: Red Star doit être exactement une fois domicile/extérieur")
        if match.uid in uids: raise ValidationError(f"doublon détecté: {match.uid}")
        round_key = (match.competition, match.round)
        if round_key in rounds: raise ValidationError(f"tour/journée en double: {match.competition} {match.round}")
        if not match.source_url or not match.checked_at: raise ValidationError(f"J{match.round}: source/vérification manquante")
        uids.add(match.uid); rounds.add(round_key)
    league_rounds = {m.round for m in league_matches}
    if league_rounds != set(range(1, expected + 1)): raise ValidationError("les journées de Ligue 2 doivent couvrir J1 à J34")


def esc(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace(";", "\\;").replace(",", "\\,")


def fold(line: str) -> str:
    chunks, current = [], b""
    for char in line:
        encoded = char.encode("utf-8")
        limit = 75 if not chunks else 74
        if len(current) + len(encoded) > limit:
            chunks.append(current.decode()); current = encoded
        else: current += encoded
    chunks.append(current.decode())
    return "\r\n ".join(chunks)


def _stamp(value: str | datetime) -> str:
    dt = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def material(match: Match) -> str:
    fields = asdict(match); fields.pop("checked_at", None)
    return json.dumps(fields, sort_keys=True, ensure_ascii=False)


def update_state(matches: list[Match], old: dict, now: datetime) -> dict:
    result = {}
    for match in matches:
        previous = old.get(match.uid)
        digest = hashlib.sha256(material(match).encode()).hexdigest()
        changed = not previous or previous.get("digest") != digest
        result[match.uid] = {"digest": digest, "sequence": (previous.get("sequence", 0) + 1 if previous and changed else previous.get("sequence", 0) if previous else 0), "last_modified": now.isoformat() if changed else previous["last_modified"]}
    return result


def render_ics(matches: list[Match], state: dict, generated: datetime) -> str:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//JulSez//Red Star FC 2026-2027//FR", "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:Red Star FC 2026–2027", "X-WR-TIMEZONE:Europe/Paris",
             "BEGIN:VTIMEZONE", "TZID:Europe/Paris", "X-LIC-LOCATION:Europe/Paris",
             "BEGIN:DAYLIGHT", "TZOFFSETFROM:+0100", "TZOFFSETTO:+0200", "TZNAME:CEST", "DTSTART:19700329T020000", "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU", "END:DAYLIGHT",
             "BEGIN:STANDARD", "TZOFFSETFROM:+0200", "TZOFFSETTO:+0100", "TZNAME:CET", "DTSTART:19701025T030000", "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU", "END:STANDARD", "END:VTIMEZONE"]
    for m in sorted(matches, key=lambda x: x.round):
        uncertainty = " — date et horaire à confirmer" if m.date_status == "provisional" else " — horaire à confirmer" if not m.time else ""
        title = f"{m.home} – {m.away}" + uncertainty
        detail = [m.competition, f"Journée/tour {m.round}", "Domicile" if m.is_home else "Extérieur", "Date provisoire" if m.date_status == "provisional" else "Date confirmée", "Horaire confirmé" if m.time else "Horaire à confirmer"]
        if m.venue: detail.append(m.venue)
        detail += [f"Source : {m.source_url}", f"Dernière vérification : {m.checked_at}"]
        s = state[m.uid]
        lines += ["BEGIN:VEVENT", f"UID:{m.uid}", f"DTSTAMP:{_stamp(generated)}", f"LAST-MODIFIED:{_stamp(s['last_modified'])}", f"SEQUENCE:{s['sequence']}"]
        day = date.fromisoformat(m.date)
        if m.time:
            start = datetime.combine(day, time.fromisoformat(m.time))
            lines += [f"DTSTART;TZID=Europe/Paris:{start:%Y%m%dT%H%M%S}", f"DTEND;TZID=Europe/Paris:{start + timedelta(hours=2):%Y%m%dT%H%M%S}"]
        else:
            lines += [f"DTSTART;VALUE=DATE:{day - timedelta(days=1):%Y%m%d}", f"DTEND;VALUE=DATE:{day + timedelta(days=2):%Y%m%d}"]
        lines += [f"SUMMARY:{esc(title)}", f"DESCRIPTION:{esc(chr(10).join(detail))}", f"URL:{esc(m.source_url)}", f"LOCATION:{esc(m.venue)}" if m.venue else None, "TRANSP:OPAQUE" if m.is_home else "TRANSP:TRANSPARENT"]
        if m.status == "cancelled": lines += ["STATUS:CANCELLED"]
        lines += ["END:VEVENT"]
    lines += ["END:VCALENDAR"]
    return "\r\n".join(fold(x) for x in lines if x is not None) + "\r\n"


def render_html(matches: list[Match], generated: datetime, subscription_url: str) -> str:
    cards = "".join(f'''<li><small>{html.escape(m.competition)}</small><strong>{html.escape(m.opponent)}</strong><span>{"Domicile" if m.is_home else "Extérieur"} · J/tour {m.round}</span><time datetime="{m.date}">{date.fromisoformat(m.date).strftime("%d/%m/%Y")}{" (provisoire)" if m.date_status == "provisional" else ""} · {m.time[:5] if m.time else "à confirmer"}</time></li>''' for m in sorted(matches, key=lambda x: (x.date, str(x.round))))
    return f'''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Calendrier Red Star FC 2026–2027</title><link rel="stylesheet" href="style.css"></head><body><main><header><p class="eyebrow">TOUTES COMPÉTITIONS</p><h1>Calendrier Red Star FC <em>2026–2027</em></h1><p>Actualisé le {generated.astimezone(PARIS):%d/%m/%Y à %H:%M} (Paris)</p><nav><a class="primary" href="red-star-fc-2026-2027.ics" download>Télécharger le fichier ICS</a><a href="webcal://{subscription_url.removeprefix('https://')}">S’abonner au calendrier</a></nav></header><section class="url"><label for="url">URL d’abonnement</label><div><input id="url" readonly value="{html.escape(subscription_url)}"><button onclick="navigator.clipboard.writeText(document.querySelector('#url').value)">Copier</button></div></section><section><h2>Les rencontres</h2><p>Les 34 matchs de Ligue 2 sont obligatoires. La Coupe de France apparaît uniquement après programmation officielle. À domicile, les matchs sont marqués <b>occupé</b> ; à l’extérieur, ils vous laissent <b>disponible</b>.</p><ul>{cards}</ul></section></main></body></html>'''
