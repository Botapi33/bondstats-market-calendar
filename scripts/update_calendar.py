#!/usr/bin/env python3
from __future__ import annotations
import json,re,hashlib,html as htmlmod
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import URLError,HTTPError
from zoneinfo import ZoneInfo
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data/events.json"
UA="BondStats-Market-Calendar/2.0 (+https://www.bondstats.org/)"

SOURCES={
 "fed":("Federal Reserve","https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"),
 "bls":("U.S. Bureau of Labor Statistics","https://www.bls.gov/schedule/news_release/bls.ics"),
 "bea":("U.S. Bureau of Economic Analysis","https://www.bea.gov/news/schedule"),
 "ecb":("European Central Bank","https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html"),
 "boe":("Bank of England","https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates"),
 "boj":("Bank of Japan","https://www.boj.or.jp/en/mopo/mpmsche_minu/index.htm"),
 "snb":("Swiss National Bank","https://www.snb.ch/en/services-events/digital-services/event-schedule"),
 "treasury":("U.S. Treasury Auctions","https://www.treasurydirect.gov/xml/PendingAuctions.xml"),
}

def fetch(url):
    req=Request(url,headers={"User-Agent":UA,"Accept":"text/html,text/calendar,application/xml,*/*"})
    with urlopen(req,timeout=30) as r:return r.read().decode("utf-8","replace")

def clean_html(s):
    s=re.sub(r"<script.*?</script>|<style.*?</style>"," ",s,flags=re.S|re.I)
    s=re.sub(r"<[^>]+>"," ",s)
    return re.sub(r"\s+"," ",htmlmod.unescape(s)).strip()

def eid(source,title,stamp):
    return source.lower().replace(" ","-")+"-"+hashlib.sha1(f"{source}|{title}|{stamp}".encode()).hexdigest()[:12]

def label(score):return "CRITICAL" if score>=90 else "HIGH" if score>=70 else "MEDIUM"

def category(title):
    t=title.lower()
    if any(x in t for x in ["fomc","monetary policy","mpc decision","policy assessment"]):return "Central Bank"
    if any(x in t for x in ["consumer price","producer price","personal income and outlays","pce","inflation"]):return "Inflation"
    if any(x in t for x in ["employment situation","job openings","employment cost","unemployment"]):return "Labour"
    if "auction" in t:return "Sovereign Funding"
    return "Macro"

def impact(title,cat):
    t=title.lower()
    if cat=="Central Bank": return 100 if any(x in t for x in ["fomc","ecb"]) else 96 if "england" in t else 94 if "japan" in t else 91
    if "consumer price" in t:return 100
    if "employment situation" in t:return 98
    if "personal income and outlays" in t:return 92
    if "producer price" in t:return 78
    if cat=="Sovereign Funding":
        if any(x in t for x in ["30-year","20-year","10-year","tips"]):return 82
        if any(x in t for x in ["7-year","5-year","3-year","2-year"]):return 74
        return 58
    return 65

def exposure(cat,country="US"):
    if cat=="Central Bank":return ["Sovereign bonds","FX","Rate expectations"]
    if cat=="Inflation":return ["Sovereign bonds","FX","Inflation expectations","Rate expectations"]
    if cat=="Labour":return ["Sovereign bonds","FX","Rate expectations"]
    if cat=="Sovereign Funding":return ["Treasuries","Term premium","Funding conditions"]
    return ["Sovereign bonds","FX"]

def event(source,short,title,country,region,cat,dt,precision,url,desc="",timing_note=None,score=None):
    stamp=dt.astimezone(timezone.utc).isoformat().replace("+00:00","Z")
    score=score if score is not None else impact(title,cat)
    e={"id":eid(short,title,stamp),"title":title,"country":country,"region":region,"category":cat,
       "eventType":"auction" if cat=="Sovereign Funding" else "policy" if cat=="Central Bank" else "macro",
       "timestamp":stamp,"timePrecision":precision,"impactScore":score,"impactLabel":label(score),
       "primaryExposure":exposure(cat,country),"source":source,"sourceShort":short,"sourceUrl":url,
       "official":True,"status":"scheduled","description":desc}
    if timing_note:e["timingNote"]=timing_note
    return e

def parse_ics_datetime(raw,tzid=None):
    raw=raw.strip()
    if raw.endswith("Z"):return datetime.strptime(raw,"%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    fmt="%Y%m%dT%H%M%S" if len(raw)>=15 else "%Y%m%dT%H%M"
    return datetime.strptime(raw,fmt).replace(tzinfo=ZoneInfo(tzid or "America/New_York")).astimezone(timezone.utc)

def parse_bls(text):
    out=[]
    for chunk in text.replace("\r\n ","").split("BEGIN:VEVENT")[1:]:
        sm=re.search(r"^SUMMARY:(.+)$",chunk,re.M)
        dm=re.search(r"^DTSTART(?:;TZID=([^:]+))?:(\d{8}T\d{4,6}Z?)$",chunk,re.M)
        if not(sm and dm):continue
        title=sm.group(1).replace("\\, ",", ").strip()
        cat=category(title)
        if not any(k in title.lower() for k in ["employment situation","consumer price","producer price","job openings","employment cost"]):continue
        dt=parse_ics_datetime(dm.group(2),dm.group(1))
        out.append(event(SOURCES["bls"][0],"BLS",title,"US","North America",cat,dt,"exact","https://www.bls.gov/schedule/2026/home.htm"))
    return out

def parse_fed(text):
    y=datetime.now(timezone.utc).year
    plain=clean_html(text)
    sec=re.search(rf"{y} FOMC Meetings(.*?)(?:{y+1} FOMC Meetings|Future Year)",plain,re.I)
    if not sec:return []
    months={m:i for i,m in enumerate("January February March April May June July August September October November December".split(),1)}
    out=[]
    for mon,num in months.items():
      for m in re.finditer(rf"{mon}\s+(\d{{1,2}})(?:-(\d{{1,2}}))?",sec.group(1),re.I):
        day=int(m.group(2) or m.group(1))
        local=datetime(y,num,day,14,0,tzinfo=ZoneInfo("America/New_York"))
        out.append(event(SOURCES["fed"][0],"Fed","Federal Reserve FOMC Decision","US","North America","Central Bank",
          local,"convention",SOURCES["fed"][1],"Federal Open Market Committee policy decision.",
          "Meeting date is official. Timestamp uses the standard scheduled FOMC decision-release convention.",100))
    return out

def parse_ecb(text):
    plain=clean_html(text); y=datetime.now(timezone.utc).year
    out=[]
    for m in re.finditer(r"(\d{2})/(\d{2})/(\d{4}).{0,160}?monetary policy meeting.{0,160}?Day 2",plain,re.I):
        d,mo,yy=map(int,m.groups())
        if yy<y:continue
        local=datetime(yy,mo,d,14,15,tzinfo=ZoneInfo("Europe/Frankfurt"))
        out.append(event(SOURCES["ecb"][0],"ECB","ECB Monetary Policy Decision","EA","Europe","Central Bank",local,
          "convention",SOURCES["ecb"][1],"ECB Governing Council monetary-policy meeting, followed by press conference.",
          "Meeting date is official. Decision time uses the ECB standard monetary-policy publication convention.",100))
    return out

def parse_boe(text):
    plain=clean_html(text); y=datetime.now(timezone.utc).year
    months={m:i for i,m in enumerate("January February March April May June July August September October November December".split(),1)}
    out=[]
    for m in re.finditer(r"Thursday\s+(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)",plain,re.I):
        day=int(m.group(1));mo=months[m.group(2).title()]
        local=datetime(y,mo,day,12,0,tzinfo=ZoneInfo("Europe/London"))
        out.append(event(SOURCES["boe"][0],"BoE","Bank of England MPC Decision","GB","Europe","Central Bank",local,
          "convention",SOURCES["boe"][1],"Monetary Policy Committee decision, summary and minutes.",
          "Official decision date; timestamp follows the Bank's standard noon-London publication convention.",96))
    return out

def parse_boj(text):
    plain=clean_html(text);y=datetime.now(timezone.utc).year
    months={m:i for i,m in enumerate("Jan Feb Mar Apr May June July Aug Sept Oct Nov Dec".split(),1)}
    out=[]
    # Capture second meeting day; release time is intentionally NOT inferred.
    for m in re.finditer(r"(Jan|Feb|Mar|Apr|May|June|July|Aug|Sept|Oct|Nov|Dec)\.\s*(\d{1,2}).{0,30}?(\d{1,2})\s*\((?:Mon|Tues|Wed|Thurs|Fri)",plain,re.I):
        mon=m.group(1).title(); day=int(m.group(3))
        try:local=datetime(y,months[mon],day,12,0,tzinfo=ZoneInfo("Asia/Tokyo"))
        except:continue
        out.append(event(SOURCES["boj"][0],"BoJ","Bank of Japan Monetary Policy Decision","JP","Asia","Central Bank",local,
          "date",SOURCES["boj"][1],"Second day of the Bank of Japan Monetary Policy Meeting.",
          "Official meeting date; policy-statement release time is not fixed and is displayed as Time TBA.",94))
    return out

def parse_snb(text):
    plain=clean_html(text);out=[]
    for m in re.finditer(r"(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2})\s+Monetary policy assessment",plain,re.I):
        d,mo,y,h,mi=map(int,m.groups())
        local=datetime(y,mo,d,h,mi,tzinfo=ZoneInfo("Europe/Zurich"))
        out.append(event(SOURCES["snb"][0],"SNB","Swiss National Bank Monetary Policy Assessment","CH","Europe","Central Bank",
          local,"exact",SOURCES["snb"][1],"SNB quarterly monetary-policy assessment and policy-rate decision.",None,91))
    return out

def parse_bea(text):
    plain=clean_html(text);y=datetime.now(timezone.utc).year
    months={m:i for i,m in enumerate("January February March April May June July August September October November December".split(),1)}
    out=[]
    rx=re.compile(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}).{0,35}?(\d{1,2}):(\d{2})\s*(AM|PM).{0,180}?(Gross Domestic Product|Personal Income and Outlays|U\.S\. International Trade in Goods and Services)",re.I)
    for m in rx.finditer(plain):
        mon,day,hh,mi,ap,title=m.groups();h=int(hh)%12+(12 if ap.upper()=="PM" else 0)
        local=datetime(y,months[mon.title()],int(day),h,int(mi),tzinfo=ZoneInfo("America/New_York"))
        cat=category(title)
        out.append(event(SOURCES["bea"][0],"BEA",title,"US","North America",cat,local,"exact",SOURCES["bea"][1]))
    return out

def child_text(el,names):
    names={n.lower() for n in names}
    for x in el.iter():
        tag=x.tag.split("}")[-1].lower()
        if tag in names and x.text:return x.text.strip()
    return None

def parse_treasury(text):
    out=[]
    root=ET.fromstring(text)
    for item in list(root.iter()):
        auction=child_text(item,["auctionDate","AuctionDate","auction_date"])
        sec=child_text(item,["securityType","SecurityType","security_type"])
        cusip=child_text(item,["cusip","CUSIP"])
        if not(auction and sec):continue
        dt=None
        for fmt in ("%Y-%m-%d","%m/%d/%Y","%Y%m%d"):
            try:dt=datetime.strptime(auction[:10],fmt).replace(hour=13,tzinfo=ZoneInfo("America/New_York"));break
            except:pass
        if not dt:continue
        title=f"U.S. Treasury {sec} Auction"
        e=event(SOURCES["treasury"][0],"Treasury",title,"US","North America","Sovereign Funding",dt,
          "date",SOURCES["treasury"][1],"Officially announced or tentatively scheduled U.S. Treasury marketable-security auction.",
          "Auction date is sourced from TreasuryDirect. Exact competitive close time is not inferred by BondStats.")
        if cusip:e["cusip"]=cusip
        out.append(e)
    # Deduplicate XML-tree descendant repeats
    return list({e["id"]:e for e in out}.values())

PARSERS={"bls":parse_bls,"fed":parse_fed,"bea":parse_bea,"ecb":parse_ecb,"boe":parse_boe,"boj":parse_boj,"snb":parse_snb,"treasury":parse_treasury}

def main():
    old={"events":[],"sources":[]}
    if OUT.exists():
        try:old=json.loads(OUT.read_text(encoding="utf-8"))
        except:pass
    now=datetime.now(timezone.utc);all_events=[];statuses=[]
    old_by_source={}
    for e in old.get("events",[]):old_by_source.setdefault(e.get("sourceShort"),[]).append(e)
    short_map={"fed":"Fed","bls":"BLS","bea":"BEA","ecb":"ECB","boe":"BoE","boj":"BoJ","snb":"SNB","treasury":"Treasury"}
    for sid,(name,url) in SOURCES.items():
        status={"id":sid,"name":name,"url":url,"status":"healthy","lastChecked":now.isoformat().replace("+00:00","Z")}
        try:
            parsed=PARSERS[sid](fetch(url))
            if not parsed:raise ValueError("No parsable events returned")
            all_events.extend(parsed);status["eventsParsed"]=len(parsed)
        except Exception as exc:
            status["status"]="degraded";status["warning"]=str(exc)[:180]
            fallback=old_by_source.get(short_map[sid],[])
            all_events.extend(fallback);status["eventsParsed"]=len(fallback);status["fallback"]="previous feed"
        statuses.append(status)
    cutoff=now-timedelta(days=2);limit=now+timedelta(days=550);dedup={}
    for e in all_events:
        try:t=datetime.fromisoformat(e["timestamp"].replace("Z","+00:00"))
        except:continue
        if cutoff<=t<=limit:dedup[e["id"]]=e
    data={"meta":{"name":"BondStats Market Calendar","version":"2.0.0-final",
      "generatedAt":now.isoformat().replace("+00:00","Z"),"timezone":"UTC",
      "method":"Official-source ingestion + deterministic BondStats market-impact model",
      "coverage":[x[0] for x in SOURCES.values()],
      "principles":["Official sources only","No invented consensus data","Unknown times shown as TBA","Source health exposed"]},
      "events":sorted(dedup.values(),key=lambda x:x["timestamp"]),"sources":statuses}
    OUT.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding="utf-8")
    print(f"{len(data['events'])} events | healthy {sum(s['status']=='healthy' for s in statuses)}/{len(statuses)} sources")

if __name__=="__main__":main()
