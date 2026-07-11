import asyncio
from datetime import datetime, timedelta, timezone
from time import monotonic
from zoneinfo import ZoneInfo
import numpy as np
from scipy.stats import poisson
from .learning import record_forecasts,pending_for_reconciliation,resolve_forecast
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
    return {"match_id":m.get("id"),"competition_id":m.get("competition_id"),"home_team":r.home_team,"away_team":r.away_team,"kickoff":datetime.fromtimestamp(int(m["date_unix"]),timezone.utc).isoformat(),"best_tip":best.model_dump(),"all_markets":[x.model_dump() for x in r.opportunities],"model_breakdown":_market_breakdown(m,r),"expected_goals":{"home":r.expected_home_goals,"away":r.expected_away_goals},"signals":{"home_ppg":hp,"away_ppg":ap,"btts_potential":btts,"over25_potential":over,"average_goals":avg},"data_points_used":sum(v not in (None,"",-1) for v in m.values())}

def _forecast_market(name, expected, line, empirical=None, seed=42):
    poisson_p=float(poisson.sf(int(line),expected))
    form_p=float(empirical if empirical is not None else 1/(1+np.exp(-(expected-line)*1.15)))
    rng=np.random.default_rng(seed); rates=rng.gamma(12,expected/12,20000); simulation_p=float(np.mean(rng.poisson(rates)>line))
    models=[]
    for model,p in (("Poisson",poisson_p),("Form / empirical",form_p),("Stochastic simulation",simulation_p)):
        models.append({"model":model,"probability":round(p,4),"outcome":f"Over {line}" if p>=.5 else f"Under {line}"})
    spread=max(x["probability"] for x in models)-min(x["probability"] for x in models)
    direction="over" if sum(x["probability"] for x in models)/3>=.5 else "under"
    narrative=f"The three models lean {direction} {line} with an expected count of {expected:.2f}. "
    narrative+=("Model agreement is strong, supporting the direction." if spread<.12 else "Model disagreement is material, so this market should be treated cautiously.")
    mean=sum(x["probability"] for x in models)/3
    recommendation=(f"Consider Over {line}" if mean>=.62 and spread<.18 else f"Consider Under {line}" if mean<=.38 and spread<.18 else "Pass — no robust consensus")
    return {"market":name,"status":"available","line":line,"expected":round(expected,2),"models":models,"narrative":narrative,"recommendation":recommendation,"disagreement":round(spread,4)}

def _market_breakdown(m,r):
    goals=r.model_probabilities
    goal_models=[]
    for model,label in (("poisson","Poisson"),("form_regression","Form / empirical"),("stochastic_simulation","Stochastic simulation")):
        p=goals[model]["over25"]; goal_models.append({"model":label,"probability":p,"outcome":"Over 2.5" if p>=.5 else "Under 2.5"})
    spread=max(x["probability"] for x in goal_models)-min(x["probability"] for x in goal_models)
    goal_mean=sum(x["probability"] for x in goal_models)/3
    goal_rec="Consider Over 2.5" if goal_mean>=.62 and spread<.18 else "Consider Under 2.5" if goal_mean<=.38 and spread<.18 else "Pass — no robust consensus"
    markets=[{"market":"Goals","status":"available","line":2.5,"expected":round(r.expected_home_goals+r.expected_away_goals,2),"models":goal_models,"disagreement":round(spread,4),"recommendation":goal_rec,"narrative":f"The models average {goal_mean*100:.1f}% for Over 2.5 goals. "+("Their agreement supports the signal." if spread<.12 else "Their disagreement challenges the signal; reduce confidence or pass.")}]
    corners=_num(m,"corners_potential",-1)
    if corners>=0:
        empirical=_rate(m,"corners_o85_potential",.5) if m.get("corners_o85_potential") not in (None,-1) else None
        markets.extend([_forecast_market("Corners",corners,8.5,empirical,int(m.get("id",42))),_forecast_market("1H corners",corners*.46,4.5,None,int(m.get("id",42))+1),_forecast_market("2H corners",corners*.54,4.5,None,int(m.get("id",42))+2)])
    else:
        markets.extend({"market":x,"status":"insufficient_data","reason":"No pre-match corner history supplied"} for x in ("Corners","1H corners","2H corners"))
    for name in ("1H throw-ins","2H throw-ins"):
        markets.append({"market":name,"status":"insufficient_data","reason":"FootyStats supplied no pre-match throw-in history or market price","narrative":"No responsible forecast is possible from the available pre-match feed. The model rejects this market rather than substituting an unsupported assumption."})
    return markets

async def next_48h_tips(client, force=False):
    global _cache
    if not force and _cache and monotonic()-_cache[0]<900:return _cache[1]
    async with _lock:
        await reconcile_completed(client)
        now=datetime.now(timezone.utc); end=now+timedelta(hours=48); london=ZoneInfo("Europe/London")
        dates=sorted({(now+timedelta(days=i)).astimezone(london).date().isoformat() for i in range(3)})
        batches=await asyncio.gather(*(client.matches_by_date(x) for x in dates))
        fixtures={int(m["id"]):m for b in batches for m in b if m.get("id")}
        eligible=[m for m in fixtures.values() if m.get("status")=="incomplete" and now-timedelta(hours=3)<=datetime.fromtimestamp(int(m.get("date_unix",0)),timezone.utc)<=end]
        tips=[t for m in eligible if (t:=_analyse_fixture(m))]
        tips.sort(key=lambda t:(t["best_tip"]["verdict"]!="VALUE",-t["best_tip"]["expected_value"]))
        payload={"generated_at":now.isoformat(),"window_end":end.isoformat(),"fixtures_found":len(eligible),"fixtures_analysed":len(tips),"tips":tips}; record_forecasts(tips,now.isoformat()); _cache=(monotonic(),payload); return payload

async def reconcile_completed(client):
    for match_id,_ in pending_for_reconciliation():
        try:
            payload=await client.match(match_id); match=payload.get("data",payload); match=match[0] if isinstance(match,list) and match else match
            if isinstance(match,dict) and match.get("status")=="complete":resolve_forecast(match_id,match)
        except Exception:
            continue
