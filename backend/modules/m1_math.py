import math
import json
from typing import Dict, List, Any, Tuple

# ========== SCIPY YOXLANMASI ==========
try:
    from scipy.stats import norm
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

# ========== NONE-SAFE KÖMƏKÇI ==========

def safe(val, default):
    """None və ya falsy dəyərləri default ilə əvəz edir."""
    if val is None:
        return default
    try:
        f = float(val)
        return f if not math.isnan(f) else default
    except (TypeError, ValueError):
        return default

def get_stat(d: Dict, key: str, default: float) -> float:
    """Dict-dən None-safe float oxuma."""
    return safe(d.get(key), default)

# ========== KÖMƏKÇİ FUNKSİYALAR ==========

def poisson_probability(lam: float, k: int) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (math.exp(-lam) * (lam ** k)) / math.factorial(k)

def poisson_cumulative(lam: float, k: int, lower_tail: bool = True) -> float:
    if lam <= 0:
        return 1.0 if k >= 0 else 0.0
    cum = sum(poisson_probability(lam, i) for i in range(k + 1))
    return cum if lower_tail else 1 - cum

def poisson_over_probability(lam: float, line: float) -> float:
    target = math.ceil(line)
    return 1 - poisson_cumulative(lam, target - 1)

def poisson_under_probability(lam: float, line: float) -> float:
    target = math.floor(line)
    return poisson_cumulative(lam, target)

def normal_over_probability(mean: float, std: float, line: float) -> float:
    if SCIPY_AVAILABLE and std > 0:
        return 1 - norm.cdf(line, loc=mean, scale=std)
    return poisson_over_probability(mean, line)

def dampen_poisson(lam: float, confidence: float, target_mean: float = 1.0) -> float:
    confidence = max(0.0, min(1.0, confidence))
    return lam * confidence + target_mean * (1 - confidence)

def calculate_h2h_weight(h2h_stats: Dict) -> float:
    if not h2h_stats or 'matches' not in h2h_stats:
        return 1.0
    matches = h2h_stats.get('matches') or []
    if not matches:
        return 1.0
    total_home = 0
    total_away = 0
    last5 = matches[-5:]
    for m in last5:
        total_home += safe(m.get('home_goals'), 0)
        total_away += safe(m.get('away_goals'), 0)
    n = len(last5)
    if n == 0:
        return 1.0
    avg_home = total_home / n
    avg_away = total_away / n
    advantage = avg_home - avg_away
    sample_factor = min(1.0, n / 5.0)
    weight = 1.0 + (advantage / 3.0) * sample_factor
    return max(0.5, min(1.5, weight))

# ========== ƏSAS HESABLAMA FUNKSİYALARI ==========

def calculate_1x2(team1_stats: Dict, team2_stats: Dict, h2h_weight: float = 1.0) -> Dict:
    home_attack  = get_stat(team1_stats, 'attack_strength',      1.0)
    home_defense = get_stat(team1_stats, 'defense_strength',     1.0)
    away_attack  = get_stat(team2_stats, 'attack_strength',      1.0)
    away_defense = get_stat(team2_stats, 'defense_strength',     1.0)

    league_home_avg = get_stat(team1_stats, 'league_home_avg_goals', 1.5)
    league_away_avg = get_stat(team2_stats, 'league_away_avg_goals', 1.2)

    lambda_home = home_attack * away_defense * league_home_avg
    lambda_away = away_attack * home_defense * league_away_avg

    lambda_home = max(0.2, min(4.0, lambda_home))
    lambda_away = max(0.2, min(4.0, lambda_away))

    lambda_home *= h2h_weight
    lambda_away /= max(0.5, h2h_weight)

    max_goals = max(10, int(max(lambda_home, lambda_away) * 3) + 1)

    prob_home = prob_draw = prob_away = 0.0
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            p = poisson_probability(lambda_home, i) * poisson_probability(lambda_away, j)
            if   i > j: prob_home += p
            elif i == j: prob_draw += p
            else:        prob_away += p

    total = prob_home + prob_draw + prob_away
    if total > 0:
        prob_home /= total
        prob_draw /= total
        prob_away /= total

    return {
        "home_win": round(prob_home, 4),
        "draw":     round(prob_draw, 4),
        "away_win": round(prob_away, 4)
    }

def calculate_over_under(team1_stats: Dict, team2_stats: Dict,
                         line: float = 2.5, market: str = "goals") -> Dict:
    confidence = min(
        get_stat(team1_stats, 'data_confidence', 0.7),
        get_stat(team2_stats, 'data_confidence', 0.7)
    )

    if market == "goals":
        home_attack  = get_stat(team1_stats, 'attack_strength',      1.0)
        away_defense = get_stat(team2_stats, 'defense_strength',     1.0)
        away_attack  = get_stat(team2_stats, 'attack_strength',      1.0)
        home_defense = get_stat(team1_stats, 'defense_strength',     1.0)
        lh_avg = get_stat(team1_stats, 'league_home_avg_goals', 1.5)
        la_avg = get_stat(team2_stats, 'league_away_avg_goals', 1.2)
        expected_total = home_attack * away_defense * lh_avg + away_attack * home_defense * la_avg
        league_avg = get_stat(team1_stats, 'league_avg_goals', 2.7)

    elif market == "corners":
        home_avg = get_stat(team1_stats, 'avg_corners_for',     5.0)
        away_avg = get_stat(team2_stats, 'avg_corners_against', 4.5)
        expected_total = home_avg + away_avg
        league_avg = get_stat(team1_stats, 'league_avg_corners', 9.5)

    elif market == "sot":
        home_avg = get_stat(team1_stats, 'avg_sot_for',     4.5)
        away_avg = get_stat(team2_stats, 'avg_sot_against', 4.0)
        expected_total = home_avg + away_avg
        league_avg = get_stat(team1_stats, 'league_avg_sot', 8.5)

    elif market == "fouls":
        home_avg = get_stat(team1_stats, 'avg_fouls_committed', 11.0)
        away_avg = get_stat(team2_stats, 'avg_fouls_suffered',  10.5)
        expected_total = home_avg + away_avg
        league_avg = get_stat(team1_stats, 'league_avg_fouls', 22.0)

    elif market == "cards":
        home_avg = get_stat(team1_stats, 'avg_cards_per_match', 2.5)
        away_avg = get_stat(team2_stats, 'avg_cards_per_match', 2.7)
        expected_total = home_avg + away_avg
        league_avg = get_stat(team1_stats, 'league_avg_cards', 5.2)

    elif market == "offsides":
        home_avg = get_stat(team1_stats, 'avg_offsides', 2.0)
        away_avg = get_stat(team2_stats, 'avg_offsides', 2.1)
        expected_total = home_avg + away_avg
        league_avg = get_stat(team1_stats, 'league_avg_offsides', 4.1)

    elif market == "throwins":
        home_avg = get_stat(team1_stats, 'avg_throwins', 20.0)
        away_avg = get_stat(team2_stats, 'avg_throwins', 19.0)
        expected_total = home_avg + away_avg
        league_avg = get_stat(team1_stats, 'league_avg_throwins', 39.0)

    elif market == "shots":
        home_avg = get_stat(team1_stats, 'avg_shots', 12.0)
        away_avg = get_stat(team2_stats, 'avg_shots', 10.5)
        expected_total = home_avg + away_avg
        league_avg = get_stat(team1_stats, 'league_avg_shots', 22.5)

    elif market == "penalties":
        home_avg = get_stat(team1_stats, 'avg_penalties_for',     0.2)
        away_avg = get_stat(team2_stats, 'avg_penalties_against', 0.15)
        expected_total = home_avg + away_avg
        league_avg = get_stat(team1_stats, 'league_avg_penalties', 0.35)

    else:
        return {"over": 0.5, "under": 0.5}

    expected_total = dampen_poisson(expected_total, confidence, target_mean=league_avg)
    prob_over  = poisson_over_probability(expected_total, line)
    prob_under = poisson_under_probability(expected_total, line)

    return {
        "over":           round(prob_over, 4),
        "under":          round(prob_under, 4),
        "expected_total": round(expected_total, 2)
    }

def calculate_btts(team1_stats: Dict, team2_stats: Dict) -> Dict:
    home_attack  = get_stat(team1_stats, 'attack_strength',      1.0)
    home_defense = get_stat(team1_stats, 'defense_strength',     1.0)
    away_attack  = get_stat(team2_stats, 'attack_strength',      1.0)
    away_defense = get_stat(team2_stats, 'defense_strength',     1.0)

    lh_avg = get_stat(team1_stats, 'league_home_avg_goals', 1.5)
    la_avg = get_stat(team2_stats, 'league_away_avg_goals', 1.2)

    lambda_home = max(0.2, min(4.0, home_attack * away_defense * lh_avg))
    lambda_away = max(0.2, min(4.0, away_attack * home_defense * la_avg))

    prob_home_scores = 1 - poisson_probability(lambda_home, 0)
    prob_away_scores = 1 - poisson_probability(lambda_away, 0)
    prob_btts = prob_home_scores * prob_away_scores

    return {
        "yes": round(prob_btts, 4),
        "no":  round(1 - prob_btts, 4)
    }

def calculate_exact_score(team1_stats: Dict, team2_stats: Dict, max_goals: int = 5) -> Dict:
    home_attack  = get_stat(team1_stats, 'attack_strength',      1.0)
    home_defense = get_stat(team1_stats, 'defense_strength',     1.0)
    away_attack  = get_stat(team2_stats, 'attack_strength',      1.0)
    away_defense = get_stat(team2_stats, 'defense_strength',     1.0)

    lh_avg = get_stat(team1_stats, 'league_home_avg_goals', 1.5)
    la_avg = get_stat(team2_stats, 'league_away_avg_goals', 1.2)

    lambda_home = max(0.2, min(4.0, home_attack * away_defense * lh_avg))
    lambda_away = max(0.2, min(4.0, away_attack * home_defense * la_avg))

    dynamic_max = max(max_goals, int(max(lambda_home, lambda_away) * 2) + 2)
    dynamic_max = min(dynamic_max, 12)

    scores = {}
    total_prob = 0.0
    for i in range(dynamic_max + 1):
        for j in range(dynamic_max + 1):
            prob = poisson_probability(lambda_home, i) * poisson_probability(lambda_away, j)
            scores[f"{i}-{j}"] = round(prob, 6)
            total_prob += prob

    if total_prob > 0:
        scores = {k: round(v / total_prob, 6) for k, v in scores.items()}

    return scores

def calculate_first_half(team1_stats: Dict, team2_stats: Dict) -> Dict:
    first_half_factor = 0.45

    home_attack  = get_stat(team1_stats, 'attack_strength',      1.0)
    home_defense = get_stat(team1_stats, 'defense_strength',     1.0)
    away_attack  = get_stat(team2_stats, 'attack_strength',      1.0)
    away_defense = get_stat(team2_stats, 'defense_strength',     1.0)

    lh_avg = get_stat(team1_stats, 'league_home_avg_goals', 1.5)
    la_avg = get_stat(team2_stats, 'league_away_avg_goals', 1.2)

    lambda_home_fh = max(0.1, min(2.0, home_attack * away_defense * lh_avg * first_half_factor))
    lambda_away_fh = max(0.1, min(2.0, away_attack * home_defense * la_avg * first_half_factor))

    max_goals_fh = max(5, int(max(lambda_home_fh, lambda_away_fh) * 3))
    prob_home = prob_draw = prob_away = 0.0

    for i in range(max_goals_fh + 1):
        for j in range(max_goals_fh + 1):
            p = poisson_probability(lambda_home_fh, i) * poisson_probability(lambda_away_fh, j)
            if   i > j: prob_home += p
            elif i == j: prob_draw += p
            else:        prob_away += p

    total = prob_home + prob_draw + prob_away
    if total > 0:
        prob_home /= total; prob_draw /= total; prob_away /= total

    exp_fh = lambda_home_fh + lambda_away_fh

    prob_home_scores = 1 - poisson_probability(lambda_home_fh, 0)
    prob_away_scores = 1 - poisson_probability(lambda_away_fh, 0)
    btts = prob_home_scores * prob_away_scores

    return {
        "1x2": {
            "home_win": round(prob_home, 4),
            "draw":     round(prob_draw, 4),
            "away_win": round(prob_away, 4)
        },
        "over_under": {
            "over_0_5":  round(poisson_over_probability(exp_fh, 0.5), 4),
            "under_0_5": round(poisson_under_probability(exp_fh, 0.5), 4),
            "over_1_5":  round(poisson_over_probability(exp_fh, 1.5), 4),
            "under_1_5": round(poisson_under_probability(exp_fh, 1.5), 4)
        },
        "btts": {
            "yes": round(btts, 4),
            "no":  round(1 - btts, 4)
        }
    }

def calculate_combination(team1_stats: Dict, team2_stats: Dict, markets: List[str]) -> Dict:
    results = {}

    if "over2.5_btts" in markets:
        ou   = calculate_over_under(team1_stats, team2_stats, 2.5, "goals")
        btts = calculate_btts(team1_stats, team2_stats)
        prob = ou["over"] * btts["yes"]
        prob = min(prob * (1 + 0.2 * (1 - prob)), 0.95)
        results["over2.5_and_btts"] = round(prob, 4)

    if "home_win_over2.5" in markets:
        x12  = calculate_1x2(team1_stats, team2_stats)
        ou   = calculate_over_under(team1_stats, team2_stats, 2.5, "goals")
        results["home_win_and_over2.5"] = round(x12["home_win"] * ou["over"], 4)

    if "draw_under2.5" in markets:
        x12  = calculate_1x2(team1_stats, team2_stats)
        ou   = calculate_over_under(team1_stats, team2_stats, 2.5, "goals")
        results["draw_and_under2.5"] = round(x12["draw"] * ou["under"], 4)

    return results

def calculate_corner_handicap(team1_stats: Dict, team2_stats: Dict, handicap: float = -1.5) -> Dict:
    home_corners = get_stat(team1_stats, 'avg_corners_for', 5.0)
    away_corners = get_stat(team2_stats, 'avg_corners_for', 4.5)
    expected_diff = home_corners - away_corners

    if expected_diff > handicap:
        prob_home_cover = 0.6 + (expected_diff - handicap) / 10
    else:
        prob_home_cover = 0.4 + (expected_diff - handicap) / 10

    prob_home_cover = max(0.1, min(0.9, prob_home_cover))
    return {
        "home_cover": round(prob_home_cover, 4),
        "away_cover": round(1 - prob_home_cover, 4)
    }

def calculate_cascading_bonus(m1_results: Dict) -> Dict:
    confidence_boost = 0.0
    high_prob_markets = []

    for market, data in m1_results.items():
        if not isinstance(data, dict):
            continue
        if market == "1x2":
            for outcome, prob in data.items():
                if safe(prob, 0) > 0.55:
                    high_prob_markets.append(f"{market}_{outcome}")
                    confidence_boost += 0.02
        elif market == "btts" and safe(data.get("yes"), 0) > 0.6:
            high_prob_markets.append("btts_yes")
            confidence_boost += 0.03
        elif market == "over_under" and isinstance(data, dict) and "2.5" in data:
            if safe(data["2.5"].get("over"), 0) > 0.6:
                high_prob_markets.append("over_2.5")
                confidence_boost += 0.02

    return {
        "boost":           round(min(0.15, confidence_boost), 4),
        "trigger_markets": high_prob_markets
    }

# ========== ƏSAS run_m1 FUNKSİYASI ==========

def run_m1(parser_json: Dict) -> Dict:
    team1       = parser_json.get("team1", "Unknown")
    team2       = parser_json.get("team2", "Unknown")
    team1_stats = parser_json.get("team1_stats") or {}
    team2_stats = parser_json.get("team2_stats") or {}
    h2h_stats   = parser_json.get("h2h_stats")   or {}

    # team1_stats / team2_stats boş gəlsə default dəyərlərlə davam et
    # (bütün get_stat çağırışları safe-dir, 0 vurma olmur)

    h2h_weight = calculate_h2h_weight(h2h_stats)

    results = {
        "team1":       team1,
        "team2":       team2,
        "h2h_weight":  h2h_weight,
        "m1_confidence": 0.0
    }

    results["1x2"]        = calculate_1x2(team1_stats, team2_stats, h2h_weight)
    results["over_under"] = {
        str(line): calculate_over_under(team1_stats, team2_stats, line, "goals")
        for line in [1.5, 2.5, 3.5, 4.5]
    }
    results["btts"]       = calculate_btts(team1_stats, team2_stats)

    exact = calculate_exact_score(team1_stats, team2_stats, max_goals=4)
    results["exact_scores"] = dict(sorted(exact.items(), key=lambda x: x[1], reverse=True)[:5])

    results["corners"]    = {
        "total":    calculate_over_under(team1_stats, team2_stats, 9.5, "corners"),
        "handicap": calculate_corner_handicap(team1_stats, team2_stats, -1.5)
    }
    results["sot"]        = calculate_over_under(team1_stats, team2_stats, 8.5,  "sot")
    results["fouls"]      = calculate_over_under(team1_stats, team2_stats, 21.5, "fouls")
    results["cards"]      = calculate_over_under(team1_stats, team2_stats, 4.5,  "cards")
    results["offsides"]   = calculate_over_under(team1_stats, team2_stats, 3.5,  "offsides")
    results["throwins"]   = calculate_over_under(team1_stats, team2_stats, 38.5, "throwins")
    results["shots"]      = calculate_over_under(team1_stats, team2_stats, 22.5, "shots")
    results["penalties"]  = calculate_over_under(team1_stats, team2_stats, 0.5,  "penalties")
    results["first_half"] = calculate_first_half(team1_stats, team2_stats)
    results["combinations"] = calculate_combination(
        team1_stats, team2_stats,
        ["over2.5_btts", "home_win_over2.5", "draw_under2.5"]
    )
    results["cascade_bonus"] = calculate_cascading_bonus(results)

    data_conf = (
        get_stat(team1_stats, 'data_confidence', 0.7) +
        get_stat(team2_stats, 'data_confidence', 0.7)
    ) / 2
    results["m1_confidence"] = round(min(0.95, data_conf * (0.8 + h2h_weight * 0.2)), 4)

    return results

# ========== TEST BLOKU ==========
if __name__ == "__main__":
    test_parser_json = {
        "team1": "Liverpool",
        "team2": "Manchester City",
        "team1_stats": {
            "attack_strength": 1.35,
            "defense_strength": 0.85,
            "avg_goals_scored": 2.4,
            "avg_goals_conceded": 0.9,
            "avg_corners_for": 7.2,
            "avg_corners_against": 3.8,
            "avg_sot_for": 6.1,
            "avg_sot_against": 3.2,
            "avg_fouls_committed": 9.5,
            "avg_fouls_suffered": 12.0,
            "avg_cards_per_match": 1.8,
            "avg_offsides": 1.5,
            "avg_throwins": 23.0,
            "avg_shots": 16.0,
            "avg_penalties_for": 0.3,
            "league_home_avg_goals": 1.55,
            "league_away_avg_goals": 1.25,
            "league_avg_goals": 2.8,
            "league_avg_corners": 9.8,
            "league_avg_sot": 8.7,
            "league_avg_fouls": 21.5,
            "league_avg_cards": 5.0,
            "league_avg_offsides": 4.0,
            "league_avg_throwins": 40.0,
            "league_avg_shots": 23.0,
            "league_avg_penalties": 0.4,
            "data_confidence": 0.9
        },
        "team2_stats": {
            "attack_strength": 1.45,
            "defense_strength": 0.75,
            "avg_goals_scored": 2.6,
            "avg_goals_conceded": 0.8,
            "avg_corners_for": 6.8,
            "avg_corners_against": 4.2,
            "avg_sot_for": 5.9,
            "avg_sot_against": 3.5,
            "avg_fouls_committed": 10.2,
            "avg_fouls_suffered": 11.5,
            "avg_cards_per_match": 2.0,
            "avg_offsides": 1.7,
            "avg_throwins": 22.0,
            "avg_shots": 15.5,
            "avg_penalties_for": 0.35,
            "league_home_avg_goals": 1.55,
            "league_away_avg_goals": 1.25,
            "league_avg_goals": 2.8,
            "league_avg_corners": 9.8,
            "league_avg_sot": 8.7,
            "league_avg_fouls": 21.5,
            "league_avg_cards": 5.0,
            "league_avg_offsides": 4.0,
            "league_avg_throwins": 40.0,
            "league_avg_shots": 23.0,
            "league_avg_penalties": 0.4,
            "data_confidence": 0.9
        },
        "h2h_stats": {
            "matches": [
                {"home_goals": 2, "away_goals": 2},
                {"home_goals": 1, "away_goals": 0},
                {"home_goals": 3, "away_goals": 1},
                {"home_goals": 1, "away_goals": 1},
                {"home_goals": 0, "away_goals": 2}
            ]
        }
    }

    result = run_m1(test_parser_json)
    print(json.dumps(result, indent=2, ensure_ascii=False))