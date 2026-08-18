from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path
from src.calendar import load_matches, render_html, render_ics, update_state, validate

def main():
    p=argparse.ArgumentParser(); p.add_argument("--data",type=Path,default=Path("data/competitions")); p.add_argument("--state",type=Path,default=Path("data/state.json")); p.add_argument("--docs",type=Path,default=Path("docs")); a=p.parse_args()
    matches,_=load_matches(a.data); validate(matches); now=datetime.now(timezone.utc).replace(microsecond=0)
    old=json.loads(a.state.read_text()) if a.state.exists() else {}; state=update_state(matches,old,now)
    a.docs.mkdir(exist_ok=True); ics=render_ics(matches,state,now)
    if ics.count("BEGIN:VEVENT") != 34: raise RuntimeError("contrôle final ICS: 34 VEVENT attendus")
    (a.docs/"red-star-fc-2026-2027.ics").write_text(ics,encoding="utf-8",newline="")
    url="https://julsez.github.io/Radio-Bauer-red-star-fc-calendar/red-star-fc-2026-2027.ics"
    (a.docs/"index.html").write_text(render_html(matches,now,url),encoding="utf-8")
    a.state.parent.mkdir(exist_ok=True); a.state.write_text(json.dumps(state,indent=2)+"\n")
if __name__ == "__main__": main()
