from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .analysis import analyse
from .config import get_settings
from .footystats import FootyStatsClient
from .schemas import AnalysisRequest, AnalysisResponse
from .tips import next_48h_tips,game_analysis
from .learning import learning_summary,forecast_history

BASE = Path(__file__).resolve().parent
app = FastAPI(title="BetAp", version="0.1.0", docs_url="/api/docs")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(BASE / "static" / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyse", response_model=AnalysisResponse)
async def analyse_match(request: AnalysisRequest) -> AnalysisResponse:
    return analyse(request)


@app.get("/api/fixtures/today")
async def fixtures_today() -> dict:
    try:
        return await FootyStatsClient(get_settings()).todays_matches()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="FootyStats API is not configured") from exc
    except httpx.HTTPError as exc:
        # Never return the upstream request URL because it contains the API key.
        raise HTTPException(status_code=502, detail="FootyStats API request failed") from exc

@app.get("/api/tips/next-48h")
async def tips_next_48h(refresh: bool = False) -> dict:
    try:
        return await next_48h_tips(FootyStatsClient(get_settings()), force=refresh)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="FootyStats API is not configured") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="FootyStats API request failed") from exc

@app.get("/api/learning")
async def model_learning() -> dict:
    return learning_summary()

@app.get("/game/{match_id}",include_in_schema=False)
async def game_page(match_id:int) -> FileResponse:
    return FileResponse(BASE / "static" / "game2.html")

@app.get("/api/game/{match_id}")
async def game_detail(match_id:int) -> dict:
    tip=await game_analysis(FootyStatsClient(get_settings()),match_id)
    if not tip:raise HTTPException(status_code=404,detail="Game analysis not found in the current 48-hour window")
    return {"analysis":tip,"history":forecast_history(match_id),"learning":learning_summary()}
