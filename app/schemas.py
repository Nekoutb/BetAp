from pydantic import BaseModel, Field


class TeamMetrics(BaseModel):
    name: str
    goals_for: float = Field(ge=0)
    goals_against: float = Field(ge=0)
    shots_on_target: float = Field(default=4.0, ge=0)
    win_rate: float = Field(default=0.4, ge=0, le=1)
    btts_rate: float = Field(default=0.5, ge=0, le=1)
    over25_rate: float = Field(default=0.5, ge=0, le=1)


class Odds(BaseModel):
    home: float = Field(gt=1)
    draw: float = Field(gt=1)
    away: float = Field(gt=1)
    over25: float | None = Field(default=None, gt=1)
    btts: float | None = Field(default=None, gt=1)


class AnalysisRequest(BaseModel):
    home: TeamMetrics
    away: TeamMetrics
    league_avg_goals: float = Field(default=2.6, gt=0)
    odds: Odds


class MarketResult(BaseModel):
    market: str
    probability: float
    fair_odds: float
    offered_odds: float
    edge: float
    expected_value: float
    confidence: float
    stake_units: float
    verdict: str


class AnalysisResponse(BaseModel):
    home_team: str
    away_team: str
    expected_home_goals: float
    expected_away_goals: float
    model_probabilities: dict[str, dict[str, float]]
    opportunities: list[MarketResult]
    warnings: list[str]
