import json
import os
import sqlite3
from pathlib import Path

DB_PATH=Path(os.getenv("BETAP_DB_PATH","data/betap.db"))

def _db():
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    connection=sqlite3.connect(DB_PATH)
    connection.execute("CREATE TABLE IF NOT EXISTS forecasts(match_id INTEGER PRIMARY KEY, kickoff TEXT, generated_at TEXT, home_team TEXT, away_team TEXT, forecast_json TEXT, status TEXT DEFAULT 'pending', result_json TEXT)")
    return connection

def record_forecasts(tips,generated_at):
    with _db() as db:
        for tip in tips:
            db.execute("INSERT OR IGNORE INTO forecasts(match_id,kickoff,generated_at,home_team,away_team,forecast_json) VALUES(?,?,?,?,?,?)",(tip["match_id"],tip["kickoff"],generated_at,tip["home_team"],tip["away_team"],json.dumps(tip["model_breakdown"])))

def learning_summary():
    with _db() as db:
        total=db.execute("SELECT COUNT(*) FROM forecasts").fetchone()[0]
        resolved=db.execute("SELECT COUNT(*) FROM forecasts WHERE status='resolved'").fetchone()[0]
        recent=db.execute("SELECT match_id,kickoff,home_team,away_team,status FROM forecasts ORDER BY kickoff DESC LIMIT 10").fetchall()
        rows=db.execute("SELECT result_json FROM forecasts WHERE status='resolved'").fetchall()
    scores={}
    for row in rows:
        for item in json.loads(row[0] or "{}").get("scores",[]): scores.setdefault(item["model"],[]).append(item["brier"])
    calibration=[{"model":m,"samples":len(v),"brier":round(sum(v)/len(v),4),"assessment":"strong" if sum(v)/len(v)<.18 else "challenge" if sum(v)/len(v)>.25 else "monitor"} for m,v in scores.items()]
    return {"tracked_predictions":total,"resolved_predictions":resolved,"pending_predictions":total-resolved,"calibration":calibration,"method":"Lower Brier error is better. Models above 0.25 are challenged and should receive less trust.","recent":[{"match_id":r[0],"kickoff":r[1],"home_team":r[2],"away_team":r[3],"status":r[4]} for r in recent]}

def pending_for_reconciliation(limit=12):
    with _db() as db:return db.execute("SELECT match_id,forecast_json FROM forecasts WHERE status='pending' AND datetime(kickoff)<datetime('now','-90 minutes') LIMIT ?",(limit,)).fetchall()

def forecast_history(match_id):
    with _db() as db:
        row=db.execute("SELECT generated_at,status,result_json FROM forecasts WHERE match_id=?",(match_id,)).fetchone()
    return {"generated_at":row[0],"status":row[1],"actual_result":json.loads(row[2]) if row[2] else None} if row else None

def resolve_forecast(match_id,match):
    with _db() as db:
        row=db.execute("SELECT forecast_json FROM forecasts WHERE match_id=?",(match_id,)).fetchone()
        if not row:return
        markets=json.loads(row[0]); scores=[]
        actuals={"Goals":float(match.get("totalGoalCount",0))>2.5,"Corners":float(match.get("totalCornerCount",0))>8.5,"1H corners":float(match.get("corner_fh_count",0))>4.5,"2H corners":float(match.get("corner_2h_count",0))>4.5}
        for market in markets:
            if market.get("status")!="available" or market["market"] not in actuals:continue
            actual=1.0 if actuals[market["market"]] else 0.0
            for model in market["models"]:scores.append({"market":market["market"],"model":model["model"],"probability":model["probability"],"actual":actual,"brier":round((model["probability"]-actual)**2,4)})
        db.execute("UPDATE forecasts SET status='resolved',result_json=? WHERE match_id=?",(json.dumps({"score":f'{match.get("homeGoalCount",0)}-{match.get("awayGoalCount",0)}',"scores":scores}),match_id))
