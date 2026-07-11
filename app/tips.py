import asyncio
from datetime import datetime, timedelta, timezone
from time import monotonic
from zoneinfo import ZoneInfo
from .analysis import analyse
from .footystats import FootyStatsClient
from .schemas import AnalysisRequest

_cache = None
_lock = asyncio.Lock()

def _num(m, k, d):
    try:
        value = float(m.get(k, d))
        return value if value >= 0 else d
    except (TypeError, ValueError): return d
def _rate(m, k, d):
    v=_num(m,k,d*100); return min(1.0, v/100 if v>1 else v)
def _odds(m,k):
    v=_num(m,k,0); return v if v>1 else None

def _analyse_fixture(m):
    h,d,a=(_odds(m,k) for k in ("odds_ft_1","odds_ft_x","odds_ft_2"))
    if not all((h,d,a)): return None
    avg=max(1.2,_num(m,"avg_potential",2.5)); hx=_num(m,"team_a_xg_prematch",avg/2); ax=_num(m,"team_b_xg_prematch",avg/2)
    hp=_num(m,"pre_match_home_ppg",_num(m,"home_ppg",1.3)); ap=_num(m,"pre_match_away_ppg",_num(m,"away_ppg",1.1))
    over=_rate(m,"o25_potential",.5); btts=_rate(m,"btts_potential",.5)
    req=AnalysisRequest.model_validate({"home":{"name":m.get("home_name") or "Home","goals_for":hx,"goals_against":max(.2,avg-ax),"win_rate":min(1,hp/3),"btts_rate":btts,"over25_rate":over},"away":{"name":m.get("away_name") or "Away","goals_for":ax,"goals_against":max(.2,avg-hx),"win_rate":min(1,ap/3),"btts_rate":btts,"over25_rate":over},"league_avg_goals":avg,"odds":{"home":h,"draw":d,"away":a,"over25":_odds(m,"odds_ft_over25"),"btts":_odds(m,"odds_btts_yes")}})
    r=analyse(req)
    if not r.opportunities:return None
    best=r.opportunities[0]
    return {"match_id":m.get("id"),"competition_id":m.get("competition_id"),"home_team":r.home_team,"away_team":r.away_team,"kickoff":datetime.fromtimestamp(int(m["date_unix"]),timezone.utc).isoformat(),"best_tip":best.model_dump(),"all_markets":[x.model_dump() for x in r.opportunities],"expected_goals":{"home":r.expected_home_goals,"away":r.expected_away_goals},"signals":{"home_ppg":hp,"away_ppg":ap,"btts_potential":btts,"over25_potential":over,"average_goals":avg},"data_points_used":sum(v not in (None,"",-1) for v in m.values())}

async def next_48h_tips(client, force=False):
    global _cache
    if not force and _cache and monotonic()-_cache[0]<900:return _cache[1]
    async with _lock:
        now=datetime.now(timezone.utc); end=now+timedelta(hours=48); london=ZoneInfo("Europe/London")
        dates=sorted({(now+timedelta(days=i)).astimezone(london).date().isoformat() for i in range(3)})
        batches=await asyncio.gather(*(client.matches_by_date(x) for x in dates))
        fixtures={int(m["id"]):m for b in batches for m in b if m.get("id")}
        eligible=[m for m in fixtures.values() if m.get("status")=="incomplete" and now<=datetime.fromtimestamp(int(m.get("date_unix",0)),timezone.utc)<=end]
        tips=[t for m in eligible if (t:=_analyse_fixture(m))]
        tips.sort(key=lambda t:(t["best_tip"]["verdict"]!="VALUE",-t["best_tip"]["expected_value"]))
        payload={"generated_at":now.isoformat(),"window_end":end.isoformat(),"fixtures_found":len(eligible),"fixtures_analysed":len(tips),"tips":tips}; _cache=(monotonic(),payload); return payload
