import math

import numpy as np
from scipy.stats import poisson

from .schemas import AnalysisRequest, AnalysisResponse, MarketResult


def _normalise(values: np.ndarray) -> np.ndarray:
    total = float(values.sum())
    return values / total if total else np.full_like(values, 1 / len(values))


def _expected_goals(req: AnalysisRequest) -> tuple[float, float]:
    baseline = req.league_avg_goals / 2
    home = max(0.15, (req.home.goals_for + req.away.goals_against + baseline) / 3 * 1.08)
    away = max(0.15, (req.away.goals_for + req.home.goals_against + baseline) / 3 * 0.92)
    return home, away


def _poisson_model(home_xg: float, away_xg: float) -> dict[str, float]:
    goals = np.arange(0, 9)
    matrix = np.outer(poisson.pmf(goals, home_xg), poisson.pmf(goals, away_xg))
    return {
        "home": float(np.tril(matrix, -1).sum()),
        "draw": float(np.trace(matrix)),
        "away": float(np.triu(matrix, 1).sum()),
        "over25": float(sum(matrix[i, j] for i in goals for j in goals if i + j >= 3)),
        "btts": float(matrix[1:, 1:].sum()),
    }


def _form_model(req: AnalysisRequest) -> dict[str, float]:
    strength = (
        1.35 * (req.home.win_rate - req.away.win_rate)
        + 0.09 * (req.home.shots_on_target - req.away.shots_on_target)
        + 0.18
    )
    home = 1 / (1 + math.exp(-strength))
    draw = max(0.16, 0.29 - abs(strength) * 0.06)
    probs = _normalise(np.array([home * (1 - draw), draw, (1 - home) * (1 - draw)]))
    return {
        "home": float(probs[0]), "draw": float(probs[1]), "away": float(probs[2]),
        "over25": float((req.home.over25_rate + req.away.over25_rate) / 2),
        "btts": float((req.home.btts_rate + req.away.btts_rate) / 2),
    }


def _monte_carlo(home_xg: float, away_xg: float, seed: int = 42) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    # Gamma-Poisson mixture captures match-to-match scoring uncertainty.
    h_rate = rng.gamma(shape=12, scale=home_xg / 12, size=30000)
    a_rate = rng.gamma(shape=12, scale=away_xg / 12, size=30000)
    home = rng.poisson(h_rate)
    away = rng.poisson(a_rate)
    return {
        "home": float(np.mean(home > away)), "draw": float(np.mean(home == away)),
        "away": float(np.mean(home < away)), "over25": float(np.mean(home + away >= 3)),
        "btts": float(np.mean((home > 0) & (away > 0))),
    }


def analyse(req: AnalysisRequest) -> AnalysisResponse:
    home_xg, away_xg = _expected_goals(req)
    models = {
        "poisson": _poisson_model(home_xg, away_xg),
        "form_regression": _form_model(req),
        "stochastic_simulation": _monte_carlo(home_xg, away_xg),
    }
    offered = {"home": req.odds.home, "draw": req.odds.draw, "away": req.odds.away,
               "over25": req.odds.over25, "btts": req.odds.btts}
    opportunities = []
    for market, odds in offered.items():
        if odds is None:
            continue
        estimates = np.array([m[market] for m in models.values()])
        probability = float(estimates.mean())
        disagreement = float(estimates.std())
        edge = probability - 1 / odds
        ev = probability * odds - 1
        confidence = max(0.0, min(1.0, 1 - disagreement * 3.5))
        kelly = max(0.0, (odds * probability - 1) / (odds - 1))
        stake = min(1.0, kelly * 2.5 * confidence)  # quarter Kelly, expressed in units.
        verdict = "PASS"
        if edge >= 0.05 and ev >= 0.08 and confidence >= 0.65:
            verdict = "VALUE"
        elif edge >= 0.025 and ev > 0:
            verdict = "WATCH"
        opportunities.append(MarketResult(
            market=market, probability=round(probability, 4), fair_odds=round(1 / probability, 2),
            offered_odds=odds, edge=round(edge, 4), expected_value=round(ev, 4),
            confidence=round(confidence, 4), stake_units=round(stake, 2), verdict=verdict,
        ))
    opportunities.sort(key=lambda x: x.expected_value, reverse=True)
    return AnalysisResponse(
        home_team=req.home.name, away_team=req.away.name,
        expected_home_goals=round(home_xg, 2), expected_away_goals=round(away_xg, 2),
        model_probabilities={k: {mk: round(mv, 4) for mk, mv in v.items()} for k, v in models.items()},
        opportunities=opportunities,
        warnings=["Probabilities are estimates, not guarantees.", "Stake sizes use capped quarter-Kelly and require a defined bankroll."],
    )
