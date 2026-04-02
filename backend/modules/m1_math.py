import math
import json
from typing import Dict, List, Any, Tuple

# ========== SCIPY YOXLANMASI (əgər varsa, normal paylanma üçün, yoxsa fallback) ==========
try:
    from scipy.stats import norm
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

# ========== KÖMƏKÇİ FUNKSİYALAR ==========

def poisson_probability(lam: float, k: int) -> float:
    """Poisson ehtimalı: P(X=k) = (e^-lam * lam^k) / k!"""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (math.exp(-lam) * (lam ** k)) / math.factorial(k)

def poisson_cumulative(lam: float, k: int, lower_tail: bool = True) -> float:
    """Poisson yığılmış ehtimal: P(X <= k) və ya P(X > k)"""
    if lam <= 0:
        return 1.0 if k >= 0 else 0.0
    cum = sum(poisson_probability(lam, i) for i in range(k + 1))
    return cum if lower_tail else 1 - cum

def poisson_over_probability(lam: float, line: float) -> float:
    """Over X.5 ehtimalı (Poisson ilə)"""
    target = math.ceil(line)
    return 1 - poisson_cumulative(lam, target - 1)

def poisson_under_probability(lam: float, line: float) -> float:
    """Under X.5 ehtimalı"""
    target = math.floor(line)
    return poisson_cumulative(lam, target)

def normal_over_probability(mean: float, std: float, line: float) -> float:
    """Normal paylanma ilə over ehtimalı (scipy varsa, yoxsa Poisson fallback)"""
    if SCIPY_AVAILABLE and std > 0:
        return 1 - norm.cdf(line, loc=mean, scale=std)
    else:
        return poisson_over_probability(mean, line)

def dampen_poisson(lam: float, confidence: float, target_mean: float = 1.0) -> float:
    """
    Poisson damping: aşağı güvəndə target_mean dəyərinə doğru çəkir.
    confidence: 0-1 arası, 1 tam real, 0 tam damping.
    target_mean: damping ediləcək hədəf ortalama.
    """
    if confidence >= 1:
        return lam
    if confidence <= 0:
        return target_mean
    return lam * confidence + target_mean * (1 - confidence)

def calculate_h2h_weight(h2h_stats: Dict) -> float:
    """
    H2H çəkisi: son 5 qarşılaşmaya baxır, qol fərqi, qalibiyyət trendi.
    Sample factor əlavə edildi: az sayda oyun varsa təsir azalır.
    Qaytarır: 0.5-1.5 arası çarpan
    """
    if not h2h_stats or 'matches' not in h2h_stats:
        return 1.0
    
    matches = h2h_stats.get('matches', [])
    if not matches:
        return 1.0
    
    total_goals_home = 0
    total_goals_away = 0
    
    for m in matches[-5:]:  # son 5
        home_goals = m.get('home_goals', 0)
        away_goals = m.get('away_goals', 0)
        total_goals_home += home_goals
        total_goals_away += away_goals
    
    n = len(matches)
    if n == 0:
        return 1.0
    
    avg_home = total_goals_home / n
    avg_away = total_goals_away / n
    advantage = avg_home - avg_away  # müsbət ev üstünlüyü
    
    # Sample factor: nə qədər çox oyun, bir o qədər etibarlı
    sample_factor = min(1.0, n / 5.0)
    
    # Çarpan: 0.5 (çox pis) - 1.5 (çox yaxşı)
    weight = 1.0 + (advantage / 3.0) * sample_factor
    return max(0.5, min(1.5, weight))

# ========== ƏSAS HESABLAMA FUNKSİYALARI ==========

def calculate_1x2(team1_stats: Dict, team2_stats: Dict, h2h_weight: float = 1.0) -> Dict:
    """
    1X2 bazarı üçün ehtimallar (ev, heç-heçə, qonaq)
    Poisson modeli əsasında, düzgün normalizasiya ilə.
    """
    home_attack = team1_stats.get('attack_strength', 1.0)
    home_defense = team1_stats.get('defense_strength', 1.0)
    away_attack = team2_stats.get('attack_strength', 1.0)
    away_defense = team2_stats.get('defense_strength', 1.0)
    
    league_home_avg = team1_stats.get('league_home_avg_goals', 1.5)
    league_away_avg = team2_stats.get('league_away_avg_goals', 1.2)
    
    # Expected goals
    lambda_home = home_attack * away_defense * league_home_avg
    lambda_away = away_attack * home_defense * league_away_avg
    
    # Damping (ehtiyat)
    lambda_home = max(0.2, min(4.0, lambda_home))
    lambda_away = max(0.2, min(4.0, lambda_away))
    
    # H2H çəkisi ilə tənzimləmə
    lambda_home *= h2h_weight
    lambda_away /= max(0.5, h2h_weight)  # qonaq zəifləyir, sıfıra bölmə qarşısı
    
    # Dinamik limit: maksimum 12 qol və ya ortalama*3
    max_goals = max(10, int(max(lambda_home, lambda_away) * 3) + 1)
    
    prob_home = 0.0
    prob_draw = 0.0
    prob_away = 0.0
    
    for i in range(0, max_goals + 1):
        for j in range(0, max_goals + 1):
            p = poisson_probability(lambda_home, i) * poisson_probability(lambda_away, j)
            if i > j:
                prob_home += p
            elif i == j:
                prob_draw += p
            else:
                prob_away += p
    
    # Normalizasiya (cəm 1 olsun)
    total = prob_home + prob_draw + prob_away
    if total > 0:
        prob_home /= total
        prob_draw /= total
        prob_away /= total
    
    return {
        "home_win": round(prob_home, 4),
        "draw": round(prob_draw, 4),
        "away_win": round(prob_away, 4)
    }

def calculate_over_under(team1_stats: Dict, team2_stats: Dict, line: float = 2.5, market: str = "goals") -> Dict:
    """
    Over/Under bazarı (qol, corner, SOT, faul, kart və s.)
    market: "goals", "corners", "sot", "fouls", "cards", "offsides", "throwins", "shots", "penalties"
    Goals üçün attack/defense balansı, digər marketlər üçün sadə toplama + damping.
    """
    # Hər market üçün ortalama dəyərlər
    if market == "goals":
        home_attack = team1_stats.get('attack_strength', 1.0)
        away_defense = team2_stats.get('defense_strength', 1.0)
        league_home_avg = team1_stats.get('league_home_avg_goals', 1.5)
        expected_home = home_attack * away_defense * league_home_avg
        
        away_attack = team2_stats.get('attack_strength', 1.0)
        home_defense = team1_stats.get('defense_strength', 1.0)
        league_away_avg = team2_stats.get('league_away_avg_goals', 1.2)
        expected_away = away_attack * home_defense * league_away_avg
        
        expected_total = expected_home + expected_away
        league_avg = team1_stats.get('league_avg_goals', 2.7)
    elif market == "corners":
        home_avg = team1_stats.get('avg_corners_for', 5.0)
        away_avg = team2_stats.get('avg_corners_against', 4.5)
        expected_total = home_avg + away_avg
        league_avg = team1_stats.get('league_avg_corners', 9.5)
    elif market == "sot":
        home_avg = team1_stats.get('avg_sot_for', 4.5)
        away_avg = team2_stats.get('avg_sot_against', 4.0)
        expected_total = home_avg + away_avg
        league_avg = team1_stats.get('league_avg_sot', 8.5)
    elif market == "fouls":
        home_avg = team1_stats.get('avg_fouls_committed', 11.0)
        away_avg = team2_stats.get('avg_fouls_suffered', 10.5)
        expected_total = home_avg + away_avg
        league_avg = team1_stats.get('league_avg_fouls', 22.0)
    elif market == "cards":
        home_avg = team1_stats.get('avg_cards_per_match', 2.5)
        away_avg = team2_stats.get('avg_cards_per_match', 2.7)
        expected_total = home_avg + away_avg
        league_avg = team1_stats.get('league_avg_cards', 5.2)
    elif market == "offsides":
        home_avg = team1_stats.get('avg_offsides', 2.0)
        away_avg = team2_stats.get('avg_offsides', 2.1)
        expected_total = home_avg + away_avg
        league_avg = team1_stats.get('league_avg_offsides', 4.1)
    elif market == "throwins":
        home_avg = team1_stats.get('avg_throwins', 20.0)
        away_avg = team2_stats.get('avg_throwins', 19.0)
        expected_total = home_avg + away_avg
        league_avg = team1_stats.get('league_avg_throwins', 39.0)
    elif market == "shots":
        home_avg = team1_stats.get('avg_shots', 12.0)
        away_avg = team2_stats.get('avg_shots', 10.5)
        expected_total = home_avg + away_avg
        league_avg = team1_stats.get('league_avg_shots', 22.5)
    elif market == "penalties":
        home_avg = team1_stats.get('avg_penalties_for', 0.2)
        away_avg = team2_stats.get('avg_penalties_against', 0.15)
        expected_total = home_avg + away_avg
        league_avg = team1_stats.get('league_avg_penalties', 0.35)
    else:
        return {"over": 0.5, "under": 0.5}
    
    # Damping (target_mean = league_avg)
    confidence = min(team1_stats.get('data_confidence', 0.7), team2_stats.get('data_confidence', 0.7))
    expected_total = dampen_poisson(expected_total, confidence, target_mean=league_avg)
    
    prob_over = poisson_over_probability(expected_total, line)
    prob_under = poisson_under_probability(expected_total, line)
    
    return {
        "over": round(prob_over, 4),
        "under": round(prob_under, 4),
        "expected_total": round(expected_total, 2)
    }

def calculate_btts(team1_stats: Dict, team2_stats: Dict) -> Dict:
    """
    Hər iki komanda qol atar (BTTS) ehtimalı.
    Sadə independence assumption (real futbol üçün tam dəqiq deyil, amma əsas model).
    """
    home_attack = team1_stats.get('attack_strength', 1.0)
    home_defense = team1_stats.get('defense_strength', 1.0)
    away_attack = team2_stats.get('attack_strength', 1.0)
    away_defense = team2_stats.get('defense_strength', 1.0)
    
    league_home_avg = team1_stats.get('league_home_avg_goals', 1.5)
    league_away_avg = team2_stats.get('league_away_avg_goals', 1.2)
    
    lambda_home = home_attack * away_defense * league_home_avg
    lambda_away = away_attack * home_defense * league_away_avg
    
    lambda_home = max(0.2, min(4.0, lambda_home))
    lambda_away = max(0.2, min(4.0, lambda_away))
    
    # Ev komandasının qol atma ehtimalı (>=1 qol)
    prob_home_scores = 1 - poisson_probability(lambda_home, 0)
    # Qonaq komandasının qol atma ehtimalı
    prob_away_scores = 1 - poisson_probability(lambda_away, 0)
    
    prob_btts = prob_home_scores * prob_away_scores
    
    return {
        "yes": round(prob_btts, 4),
        "no": round(1 - prob_btts, 4)
    }

def calculate_exact_score(team1_stats: Dict, team2_stats: Dict, max_goals: int = 5) -> Dict:
    """
    Dəqiq hesab ehtimalları (0-0, 1-0, 0-1, ..., max_goals-max_goals)
    Dinamik limit.
    """
    home_attack = team1_stats.get('attack_strength', 1.0)
    home_defense = team1_stats.get('defense_strength', 1.0)
    away_attack = team2_stats.get('attack_strength', 1.0)
    away_defense = team2_stats.get('defense_strength', 1.0)
    
    league_home_avg = team1_stats.get('league_home_avg_goals', 1.5)
    league_away_avg = team2_stats.get('league_away_avg_goals', 1.2)
    
    lambda_home = home_attack * away_defense * league_home_avg
    lambda_away = away_attack * home_defense * league_away_avg
    
    lambda_home = max(0.2, min(4.0, lambda_home))
    lambda_away = max(0.2, min(4.0, lambda_away))
    
    # Dinamik limit (ən azı 5, ən çoxu 12)
    dynamic_max = max(max_goals, int(max(lambda_home, lambda_away) * 2) + 2)
    dynamic_max = min(dynamic_max, 12)
    
    scores = {}
    total_prob = 0.0
    for i in range(dynamic_max + 1):
        for j in range(dynamic_max + 1):
            prob = poisson_probability(lambda_home, i) * poisson_probability(lambda_away, j)
            scores[f"{i}-{j}"] = round(prob, 6)
            total_prob += prob
    
    # Normalizasiya
    if total_prob > 0:
        for k in scores:
            scores[k] = round(scores[k] / total_prob, 6)
    
    return scores

def calculate_first_half(team1_stats: Dict, team2_stats: Dict) -> Dict:
    """
    İlk yarı üçün 1X2, over/under, BTTS
    """
    first_half_factor = 0.45
    
    home_attack = team1_stats.get('attack_strength', 1.0)
    home_defense = team1_stats.get('defense_strength', 1.0)
    away_attack = team2_stats.get('attack_strength', 1.0)
    away_defense = team2_stats.get('defense_strength', 1.0)
    
    league_home_avg = team1_stats.get('league_home_avg_goals', 1.5)
    league_away_avg = team2_stats.get('league_away_avg_goals', 1.2)
    
    lambda_home_full = home_attack * away_defense * league_home_avg
    lambda_away_full = away_attack * home_defense * league_away_avg
    
    lambda_home_fh = lambda_home_full * first_half_factor
    lambda_away_fh = lambda_away_full * first_half_factor
    
    lambda_home_fh = max(0.1, min(2.0, lambda_home_fh))
    lambda_away_fh = max(0.1, min(2.0, lambda_away_fh))
    
    max_goals_fh = max(5, int(max(lambda_home_fh, lambda_away_fh) * 3))
    
    prob_home = 0.0
    prob_draw = 0.0
    prob_away = 0.0
    
    for i in range(max_goals_fh + 1):
        for j in range(max_goals_fh + 1):
            p = poisson_probability(lambda_home_fh, i) * poisson_probability(lambda_away_fh, j)
            if i > j:
                prob_home += p
            elif i == j:
                prob_draw += p
            else:
                prob_away += p
    
    total = prob_home + prob_draw + prob_away
    if total > 0:
        prob_home /= total
        prob_draw /= total
        prob_away /= total
    
    expected_total_fh = lambda_home_fh + lambda_away_fh
    over_05 = poisson_over_probability(expected_total_fh, 0.5)
    over_15 = poisson_over_probability(expected_total_fh, 1.5)
    under_05 = poisson_under_probability(expected_total_fh, 0.5)
    under_15 = poisson_under_probability(expected_total_fh, 1.5)
    
    prob_home_scores = 1 - poisson_probability(lambda_home_fh, 0)
    prob_away_scores = 1 - poisson_probability(lambda_away_fh, 0)
    btts = prob_home_scores * prob_away_scores
    
    return {
        "1x2": {
            "home_win": round(prob_home, 4),
            "draw": round(prob_draw, 4),
            "away_win": round(prob_away, 4)
        },
        "over_under": {
            "over_0_5": round(over_05, 4),
            "under_0_5": round(under_05, 4),
            "over_1_5": round(over_15, 4),
            "under_1_5": round(under_15, 4)
        },
        "btts": {
            "yes": round(btts, 4),
            "no": round(1 - btts, 4)
        }
    }

def calculate_combination(team1_stats: Dict, team2_stats: Dict, markets: List[str]) -> Dict:
    """
    Kombinə bazar: məsələn "Over 2.5 & BTTS", "Home win & Over 2.5"
    İndependence problemini azaltmaq üçün korrelyasiya əmsalı əlavə edildi.
    """
    results = {}
    
    if "over2.5_btts" in markets:
        ou = calculate_over_under(team1_stats, team2_stats, 2.5, "goals")
        btts_res = calculate_btts(team1_stats, team2_stats)
        prob_independent = ou["over"] * btts_res["yes"]
        # Korrelyasiya əmsalı (0.2): over 2.5 və BTTS arasında müsbət əlaqə
        correlation_boost = 0.2
        prob_adjusted = prob_independent * (1 + correlation_boost * (1 - prob_independent))
        prob_adjusted = min(prob_adjusted, 0.95)
        results["over2.5_and_btts"] = round(prob_adjusted, 4)
    
    if "home_win_over2.5" in markets:
        res_1x2 = calculate_1x2(team1_stats, team2_stats)
        ou = calculate_over_under(team1_stats, team2_stats, 2.5, "goals")
        prob = res_1x2["home_win"] * ou["over"]
        results["home_win_and_over2.5"] = round(prob, 4)
    
    if "draw_under2.5" in markets:
        res_1x2 = calculate_1x2(team1_stats, team2_stats)
        ou = calculate_over_under(team1_stats, team2_stats, 2.5, "goals")
        prob = res_1x2["draw"] * ou["under"]
        results["draw_and_under2.5"] = round(prob, 4)
    
    return results

def calculate_corner_handicap(team1_stats: Dict, team2_stats: Dict, handicap: float = -1.5) -> Dict:
    """Korner handikapı (ev komandası üçün)"""
    home_corners = team1_stats.get('avg_corners_for', 5.0)
    away_corners = team2_stats.get('avg_corners_for', 4.5)
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
    """
    Kaskad güvən bonusları: əgər bir neçə bazar yüksək ehtimal göstərirsə, bonus əlavə et
    """
    confidence_boost = 0.0
    high_prob_markets = []
    
    for market, data in m1_results.items():
        if isinstance(data, dict):
            if market == "1x2":
                for outcome, prob in data.items():
                    if prob > 0.55:
                        high_prob_markets.append(f"{market}_{outcome}")
                        confidence_boost += 0.02
            elif market == "btts" and data.get("yes", 0) > 0.6:
                high_prob_markets.append("btts_yes")
                confidence_boost += 0.03
            elif market == "over_under" and isinstance(data, dict) and "2.5" in data:
                if data["2.5"].get("over", 0) > 0.6:
                    high_prob_markets.append("over_2.5")
                    confidence_boost += 0.02
    
    confidence_boost = min(0.15, confidence_boost)
    
    return {
        "boost": round(confidence_boost, 4),
        "trigger_markets": high_prob_markets
    }

# ========== ƏSAS run_m1 FUNKSİYASI ==========

def run_m1(parser_json: Dict) -> Dict:
    """
    Parser JSON-dan gələn statistikaları işləyir və bütün bazarlar üçün ehtimalları qaytarır.
    """
    team1 = parser_json.get("team1", "Unknown")
    team2 = parser_json.get("team2", "Unknown")
    team1_stats = parser_json.get("team1_stats", {})
    team2_stats = parser_json.get("team2_stats", {})
    h2h_stats = parser_json.get("h2h_stats", {})
    
    # H2H çəkisini hesabla (təkmilləşdirilmiş)
    h2h_weight = calculate_h2h_weight(h2h_stats)
    
    # Bütün bazarlar üçün hesablamalar
    results = {
        "team1": team1,
        "team2": team2,
        "h2h_weight": h2h_weight,
        "m1_confidence": 0.0
    }
    
    # 1X2
    results["1x2"] = calculate_1x2(team1_stats, team2_stats, h2h_weight)
    
    # Over/Under qollar (1.5, 2.5, 3.5, 4.5)
    results["over_under"] = {}
    for line in [1.5, 2.5, 3.5, 4.5]:
        ou = calculate_over_under(team1_stats, team2_stats, line, "goals")
        results["over_under"][str(line)] = ou
    
    # BTTS
    results["btts"] = calculate_btts(team1_stats, team2_stats)
    
    # Dəqiq hesab (top 5 ehtimal)
    exact_scores = calculate_exact_score(team1_stats, team2_stats, max_goals=4)
    sorted_scores = sorted(exact_scores.items(), key=lambda x: x[1], reverse=True)[:5]
    results["exact_scores"] = dict(sorted_scores)
    
    # Kornerlər
    results["corners"] = {
        "total": calculate_over_under(team1_stats, team2_stats, 9.5, "corners"),
        "handicap": calculate_corner_handicap(team1_stats, team2_stats, -1.5)
    }
    
    # SOT
    results["sot"] = calculate_over_under(team1_stats, team2_stats, 8.5, "sot")
    
    # Faullar
    results["fouls"] = calculate_over_under(team1_stats, team2_stats, 21.5, "fouls")
    
    # Kartlar
    results["cards"] = calculate_over_under(team1_stats, team2_stats, 4.5, "cards")
    
    # Ofsaytlar
    results["offsides"] = calculate_over_under(team1_stats, team2_stats, 3.5, "offsides")
    
    # Autlar
    results["throwins"] = calculate_over_under(team1_stats, team2_stats, 38.5, "throwins")
    
    # Qapıdan zərbə
    results["shots"] = calculate_over_under(team1_stats, team2_stats, 22.5, "shots")
    
    # Penalti
    results["penalties"] = calculate_over_under(team1_stats, team2_stats, 0.5, "penalties")
    
    # İlk yarı
    results["first_half"] = calculate_first_half(team1_stats, team2_stats)
    
    # Kombinə bazarlar (təkmilləşdirilmiş korrelyasiya ilə)
    results["combinations"] = calculate_combination(team1_stats, team2_stats, 
                                                    ["over2.5_btts", "home_win_over2.5", "draw_under2.5"])
    
    # Kaskad bonus
    results["cascade_bonus"] = calculate_cascading_bonus(results)
    
    # M1 ümumi güvən (ortalama data_confidence + h2h_weight təsiri)
    data_conf = (team1_stats.get('data_confidence', 0.7) + team2_stats.get('data_confidence', 0.7)) / 2
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