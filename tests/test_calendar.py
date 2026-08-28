import json,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import update_calendar as u

def ok(name,cond):
    if not cond:raise AssertionError(name)
    print("PASS",name)

data=json.loads((ROOT/"data/events.json").read_text())
ok("schema events",isinstance(data["events"],list) and len(data["events"])>=10)
ok("sources configured",len(data["sources"])>=8)
ok("impact bounds",all(0<=e["impactScore"]<=100 for e in data["events"]))
ok("impact labels",all(e["impactLabel"] in {"CRITICAL","HIGH","MEDIUM"} for e in data["events"]))
ok("official only",all(e.get("official") is True for e in data["events"]))
ok("timestamps parse",all(datetime.fromisoformat(e["timestamp"].replace("Z","+00:00")).tzinfo for e in data["events"]))
ok("precision declared",all(e["timePrecision"] in {"exact","convention","date"} for e in data["events"]))
ok("date precision has note",all(e.get("timingNote") for e in data["events"] if e["timePrecision"]=="date"))
ok("source URL https",all(e["sourceUrl"].startswith("https://") for e in data["events"]))
parsed=u.parse_bls((ROOT/"fixtures/bls.ics").read_text())
ok("BLS fixture",len(parsed)==2)
ok("CPI score",next(x for x in parsed if "Consumer Price" in x["title"])["impactScore"]==100)
ok("NFP score",next(x for x in parsed if "Employment Situation" in x["title"])["impactScore"]==98)
ok("category inflation",u.category("Consumer Price Index")=="Inflation")
ok("category labour",u.category("Employment Situation")=="Labour")
ok("auction category",u.category("10-Year Treasury Auction")=="Sovereign Funding")
print("ALL TESTS PASSED")
