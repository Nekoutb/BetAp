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
    return {"tracked_predictions":total,"resolved_predictions":resolved,"pending_predictions":total-resolved,"method":"Forecasts are stored before kickoff. Completed results will be compared using Brier error to challenge and recalibrate model weights.","recent":[{"match_id":r[0],"kickoff":r[1],"home_team":r[2],"away_team":r[3],"status":r[4]} for r in recent]}
