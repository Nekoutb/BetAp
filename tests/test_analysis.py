from app.analysis import analyse
from app.schemas import AnalysisRequest


def test_probabilities_and_market_outputs():
    request = AnalysisRequest.model_validate({
        "home": {"name":"Home","goals_for":2.0,"goals_against":0.9,"shots_on_target":6,"win_rate":0.65},
        "away": {"name":"Away","goals_for":1.2,"goals_against":1.6,"shots_on_target":4,"win_rate":0.35},
        "odds": {"home":2.0,"draw":3.5,"away":4.0,"over25":2.0,"btts":1.9}
    })
    result = analyse(request)
    assert len(result.model_probabilities) == 3
    assert len(result.opportunities) == 5
    for model in result.model_probabilities.values():
        assert 0 <= model["home"] <= 1
        assert abs(model["home"] + model["draw"] + model["away"] - 1) < 0.02
    assert all(0 <= item.stake_units <= 1 for item in result.opportunities)
