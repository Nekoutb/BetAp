from app.tips import _analyse_fixture

def test_fixture_is_transformed_into_ranked_tip():
    tip=_analyse_fixture({"id":1,"home_name":"Alpha","away_name":"Beta","date_unix":1900000000,"odds_ft_1":2.1,"odds_ft_x":3.5,"odds_ft_2":3.8,"odds_ft_over25":1.95,"odds_btts_yes":1.9,"avg_potential":2.8,"team_a_xg_prematch":1.7,"team_b_xg_prematch":1.1,"pre_match_home_ppg":2,"pre_match_away_ppg":1.1,"o25_potential":61,"btts_potential":56})
    assert tip and len(tip["all_markets"])==5
