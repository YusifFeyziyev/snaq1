import os
import json
import re
import requests
from typing import Dict, Any, List

try:
    from config import GROQ_KEY_M3, MODEL_M3
except ImportError:
    GROQ_KEY_M3 = os.getenv("GROQ_KEY_M3")
    MODEL_M3 = os.getenv("MODEL_M3", "llama-3.3-70b-versatile")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


# ─────────────────────────────────────────
#  YARDIMÇI: M2 datası oxu
# ─────────────────────────────────────────

def get_m2_field(m2_data: Dict, key: str, subkey: str = "value", min_conf: float = 0.5):
    field = m2_data.get(key, {})
    if not isinstance(field, dict):
        return None
    if field.get("status") == "tapılmadı":
        return None
    conf = field.get("confidence", 0.0)
    if conf < min_conf:
        return None
    return field.get(subkey)


def count_real_fields(m2_data: Dict) -> int:
    count = 0
    for v in m2_data.values():
        if isinstance(v, dict) and v.get("status") == "real":
            count += 1
    return count


# ─────────────────────────────────────────
#  TAKTİKİ DNA TƏYİNİ
# ─────────────────────────────────────────

def taktika_tipi_tey(goals_scored: float, goals_conceded: float,
                     corners: float, sot: float = None) -> str:
    if goals_scored is None or goals_conceded is None:
        return "balanslı"
    if goals_scored < 0.8 and goals_conceded < 0.9:
        return "bus-stop"
    if goals_scored < 1.0 and goals_conceded < 1.2:
        return "kilid-kontra"
    if goals_scored > 1.8 and corners is not None and corners > 5.5:
        return "tam-hücum"
    if goals_scored > 1.5 and goals_conceded > 1.4:
        return "pressing"
    if goals_scored > 1.3 and goals_conceded < 1.1:
        return "sahiblik"
    return "balanslı"


def toqqusma_effekti(tip_ev: str, tip_qonaq: str) -> Dict:
    matris = {
        ("tam-hücum",    "bus-stop"):      {"tempo": "aşağı",     "qol": "az",      "corner": "aşağı"},
        ("tam-hücum",    "kilid-kontra"):  {"tempo": "orta",      "qol": "az-orta", "corner": "ev-üstün"},
        ("tam-hücum",    "tam-hücum"):     {"tempo": "yüksək",    "qol": "çox",     "corner": "yüksək"},
        ("pressing",     "pressing"):      {"tempo": "yüksək",    "qol": "çox",     "corner": "orta"},
        ("sahiblik",     "bus-stop"):      {"tempo": "aşağı",     "qol": "az",      "corner": "aşağı"},
        ("kilid-kontra", "bus-stop"):      {"tempo": "çox-aşağı", "qol": "çox-az",  "corner": "çox-aşağı"},
        ("balanslı",     "balanslı"):      {"tempo": "orta",      "qol": "orta",    "corner": "orta"},
    }
    key = (tip_ev, tip_qonaq)
    if key in matris:
        return matris[key]
    if (tip_qonaq, tip_ev) in matris:
        return matris[(tip_qonaq, tip_ev)].copy()
    return {"tempo": "orta", "qol": "orta", "corner": "orta"}


# ─────────────────────────────────────────
#  ÇARPAN HESABI
# ─────────────────────────────────────────

def hesabla_carpanlar(parser_json: Dict, m2_data: Dict) -> Dict:
    t1 = parser_json.get("team1_stats", {})
    t2 = parser_json.get("team2_stats", {})

    carpanlar = {
        "motivasiya_ev":         1.0,
        "motivasiya_qonaq":      1.0,
        "yorgunluq_ev":          1.0,
        "yorgunluq_qonaq":       1.0,
        "hakim_tesiri":          1.0,
        "heyat_derinliyi_ev":    1.0,
        "heyat_derinliyi_qonaq": 1.0,
        "psixoloji_ustunluk":    1.0
    }

    # --- MOTİVASİYA ---
    pos1 = t1.get("league_position")
    pos2 = t2.get("league_position")

    def motivasiya_carpani(pos):
        if pos is None:  return 1.0
        if pos <= 3:     return 1.15
        if pos <= 6:     return 1.08
        if pos <= 14:    return 1.0
        return 1.12

    carpanlar["motivasiya_ev"]    = motivasiya_carpani(pos1)
    carpanlar["motivasiya_qonaq"] = motivasiya_carpani(pos2)

    mot_ev  = get_m2_field(m2_data, "motivation", "home_motivation", 0.6)
    mot_qon = get_m2_field(m2_data, "motivation", "away_motivation", 0.6)
    mot_map = {"çox yüksək": 1.15, "yüksək": 1.08, "orta": 1.0, "aşağı": 0.88, "yox": 0.82}
    if mot_ev  and mot_ev  in mot_map: carpanlar["motivasiya_ev"]    = mot_map[mot_ev]
    if mot_qon and mot_qon in mot_map: carpanlar["motivasiya_qonaq"] = mot_map[mot_qon]

    # --- YORĞUNLUQ ---
    def yorgunluq_carpani(days):
        if days is None: return 1.0
        if days <= 3:    return 0.88
        if days <= 5:    return 0.94
        return 1.0

    carpanlar["yorgunluq_ev"]    = yorgunluq_carpani(t1.get("days_since_last_match"))
    carpanlar["yorgunluq_qonaq"] = yorgunluq_carpani(t2.get("days_since_last_match"))

    # --- HEYƏT DƏRİNLİYİ ---
    inj = m2_data.get("injuries", {})
    if isinstance(inj, dict) and inj.get("confidence", 0) >= 0.5:
        absent_home = len(inj.get("home_absent", []))
        absent_away = len(inj.get("away_absent", []))
        if   absent_home >= 4: carpanlar["heyat_derinliyi_ev"] = 0.78
        elif absent_home >= 2: carpanlar["heyat_derinliyi_ev"] = 0.90
        elif absent_home == 1: carpanlar["heyat_derinliyi_ev"] = 0.95
        if   absent_away >= 4: carpanlar["heyat_derinliyi_qonaq"] = 0.78
        elif absent_away >= 2: carpanlar["heyat_derinliyi_qonaq"] = 0.90
        elif absent_away == 1: carpanlar["heyat_derinliyi_qonaq"] = 0.95

    # ✅ DÜZƏLİŞ 3: "severity" → "foul_sensitivity" (M2 strukturuna uyğun)
    # Əvvəl: get_m2_field(m2_data, "referee", "severity", 0.6)
    # Problem: M2 "severity" yox, "foul_sensitivity" qaytarır → həmişə None olurdu
    ref_sensitivity = get_m2_field(m2_data, "referee", "foul_sensitivity", 0.6)
    sev_map = {"yüksək": 1.12, "orta": 1.0, "aşağı": 0.88}
    if ref_sensitivity and ref_sensitivity in sev_map:
        carpanlar["hakim_tesiri"] = sev_map[ref_sensitivity]

    # --- PSİXOLOJİ ÜSTÜNLÜK ---
    h2h = parser_json.get("h2h", {})
    h2h_ev  = h2h.get("home_wins", 0)
    h2h_qon = h2h.get("away_wins", 0)
    if h2h_ev  > h2h_qon + 1: carpanlar["psixoloji_ustunluk"] = 1.06
    elif h2h_qon > h2h_ev + 1: carpanlar["psixoloji_ustunluk"] = 0.94

    return {k: round(v, 3) for k, v in carpanlar.items()}


# ─────────────────────────────────────────
#  FLAGLƏR
# ─────────────────────────────────────────

def hesabla_flags(parser_json: Dict, m2_data: Dict, tip_ev: str, tip_qonaq: str) -> List[str]:
    flags = []
    t1 = parser_json.get("team1_stats", {})
    t2 = parser_json.get("team2_stats", {})

    if tip_qonaq == "bus-stop":
        flags.append("BUS_STOP_QONAQ")

    inj = m2_data.get("injuries", {})
    if isinstance(inj, dict) and inj.get("confidence", 0) >= 0.5:
        if len(inj.get("home_absent", [])) >= 4: flags.append("KRİTİK_İTKİ_EV")
        if len(inj.get("away_absent", [])) >= 4: flags.append("KRİTİK_İTKİ_QONAQ")

    days1 = t1.get("days_since_last_match")
    days2 = t2.get("days_since_last_match")
    if days1 is not None and days1 <= 3: flags.append("YORĞUNLUQ_EV")
    if days2 is not None and days2 <= 3: flags.append("YORĞUNLUQ_QONAQ")

    derby = get_m2_field(m2_data, "match_context", "is_derby", 0.5)
    if derby is True: flags.append("DERBY")

    return flags


# ─────────────────────────────────────────
#  GÜVƏN HESABI (0-10 scale)
# ─────────────────────────────────────────

def hesabla_m3_guveni(m2_data: Dict, flags: List[str], carpanlar: Dict) -> float:
    real_count = count_real_fields(m2_data)
    m2_bal     = min(3.0, real_count * 0.6)
    ferg       = sum(abs(v - 1.0) for v in carpanlar.values())
    signal_bal = min(4.0, ferg * 5)
    zid_bal    = 3.0
    if "BUS_STOP_QONAQ" in flags and "YORĞUNLUQ_EV" in flags:
        zid_bal = 1.5
    if len(flags) > 4:
        zid_bal = 1.0
    return round(min(10.0, m2_bal + signal_bal + zid_bal), 2)


# ─────────────────────────────────────────
#  GROQ PROMPT
# ─────────────────────────────────────────

def build_prompt(team1: str, team2: str, parser_json: Dict,
                 m2_data: Dict, tip_ev: str, tip_qonaq: str,
                 toqqusma: Dict, carpanlar: Dict, flags: List[str]) -> tuple:

    t1 = parser_json.get("team1_stats", {})
    t2 = parser_json.get("team2_stats", {})

    m2_real = {
        k: v for k, v in m2_data.items()
        if isinstance(v, dict) and v.get("status") == "real" and v.get("confidence", 0) >= 0.6
    }

    system = """Sən peşəkar futbol analitikisən. Sənə statistika, taktiki analiz və araşdırma nəticələri veriləcək.
Yalnız verilən dataya əsaslan. Uydurma yazma. Hər sahə üçün confidence (0.0-1.0) ver.
Yalnız JSON qaytar, heç bir izah yazma."""

    # ✅ DÜZƏLİŞ 2: {flags} → json.dumps(flags) — Python list invalid JSON idi
    # Əvvəl: "flags": {flags}  → ["FLAG1", "FLAG2"] kimi Python repr yazırdı
    # İndi: json.dumps istifadə et → düzgün JSON array
    user = f"""Oyun: {team1} (ev) vs {team2} (qonaq)

--- STATİSTİKA ---
Ev qol vurdu: {t1.get('avg_goals_scored', 'N/A')} | buraxdı: {t1.get('avg_goals_conceded', 'N/A')}
Ev hücum gücü: {t1.get('attack_strength', 'N/A')} | müdafiə: {t1.get('defense_strength', 'N/A')}
Ev cədvəl sırası: {t1.get('league_position', 'N/A')}
Ev son oyundan gün: {t1.get('days_since_last_match', 'N/A')}

Qonaq qol vurdu: {t2.get('avg_goals_scored', 'N/A')} | buraxdı: {t2.get('avg_goals_conceded', 'N/A')}
Qonaq hücum gücü: {t2.get('attack_strength', 'N/A')} | müdafiə: {t2.get('defense_strength', 'N/A')}
Qonaq cədvəl sırası: {t2.get('league_position', 'N/A')}
Qonaq son oyundan gün: {t2.get('days_since_last_match', 'N/A')}

--- TAKTİKİ DNA ---
Ev taktikası: {tip_ev}
Qonaq taktikası: {tip_qonaq}
Toqquşma effekti: tempo={toqqusma.get('tempo')}, qol={toqqusma.get('qol')}, corner={toqqusma.get('corner')}

--- HESABLANMIŞ ÇARPANLAR ---
{json.dumps(carpanlar, ensure_ascii=False)}

--- FLAGLƏR ---
{json.dumps(flags, ensure_ascii=False)}

--- M2 REAL MƏLUMATLAR (confidence >= 0.6) ---
{json.dumps(m2_real, ensure_ascii=False) if m2_real else 'M2 real məlumat yoxdur'}

Aşağıdakı JSON strukturunu doldur. Hər sahə üçün:
- value: real dəyər (STRING olmalıdır, object yox)
- confidence: 0.0-1.0
- source: "m2_real" / "statistika" / "taktiki_analiz"

{{
  "tempo": {{"value": "yüksək/orta/aşağı", "confidence": 0.0, "source": ""}},
  "taktika_ev": {{"value": "{tip_ev}", "confidence": 0.0, "source": "statistika"}},
  "taktika_qonaq": {{"value": "{tip_qonaq}", "confidence": 0.0, "source": "statistika"}},
  "dominant_teref": {{"value": "ev/qonaq/balanslı", "confidence": 0.0, "source": ""}},
  "qol_veziyyeti": {{"value": "az/orta/çox", "confidence": 0.0, "source": ""}},
  "btts_siqnal": {{"value": "güclü/orta/zəif", "confidence": 0.0, "source": ""}},
  "corner_siqnal": {{"value": "yüksək/orta/aşağı", "confidence": 0.0, "source": ""}},
  "kart_siqnal": {{"value": "yüksək/orta/aşağı", "confidence": 0.0, "source": ""}},
  "hakim_tesiri": {{"value": "yüksək-kart/normal/az-kart", "confidence": 0.0, "source": ""}},
  "oyun_oxunusu": {{"value": "2-3 cümlə oyun proqnozu", "confidence": 0.0, "source": ""}},
  "kahin_cumlesi": {{"value": "1 konkret cümlə", "confidence": 0.0, "source": ""}},
  "flags": {json.dumps(flags, ensure_ascii=False)},
  "carpanlar": {json.dumps(carpanlar, ensure_ascii=False)},
  "toqqusma_matrisi": {{
    "ev_hucum_qonaq_mudafie": "çox_üstün/üstün/balanslı/zəif/çox_zəif",
    "qonaq_hucum_ev_mudafie": "çox_üstün/üstün/balanslı/zəif/çox_zəif"
  }},
  "critical_factors": ["ən vacib 3 faktor"],
  "m3_guveni": 0.0
}}"""

    return system, user


# ─────────────────────────────────────────
#  DEFAULT NƏTİCƏ
# ─────────────────────────────────────────

def get_default_m3_result(tip_ev="balanslı", tip_qonaq="balanslı",
                           carpanlar=None, flags=None, error=None) -> Dict:
    return {
        "tempo":          {"value": "orta",      "confidence": 0.3, "source": "default"},
        "taktika_ev":     {"value": tip_ev,       "confidence": 0.4, "source": "statistika"},
        "taktika_qonaq":  {"value": tip_qonaq,    "confidence": 0.4, "source": "statistika"},
        "dominant_teref": {"value": "balanslı",   "confidence": 0.3, "source": "default"},
        "qol_veziyyeti":  {"value": "orta",        "confidence": 0.3, "source": "default"},
        "btts_siqnal":    {"value": "orta",        "confidence": 0.3, "source": "default"},
        "corner_siqnal":  {"value": "orta",        "confidence": 0.3, "source": "default"},
        "kart_siqnal":    {"value": "orta",        "confidence": 0.3, "source": "default"},
        "hakim_tesiri":   {"value": "normal",      "confidence": 0.3, "source": "default"},
        "oyun_oxunusu":   {"value": "Məlumat yetərsizdir.", "confidence": 0.2, "source": "default"},
        "kahin_cumlesi":  {"value": "Analiz üçün kifayət qədər data yoxdur.", "confidence": 0.2, "source": "default"},
        "flags":     flags or [],
        "carpanlar": carpanlar or {
            "motivasiya_ev": 1.0, "motivasiya_qonaq": 1.0,
            "yorgunluq_ev": 1.0,  "yorgunluq_qonaq": 1.0,
            "hakim_tesiri": 1.0,  "heyat_derinliyi_ev": 1.0,
            "heyat_derinliyi_qonaq": 1.0, "psixoloji_ustunluk": 1.0
        },
        "toqqusma_matrisi": {
            "ev_hucum_qonaq_mudafie": "balanslı",
            "qonaq_hucum_ev_mudafie": "balanslı"
        },
        "critical_factors": [],
        "m3_guveni": 3.0,
        "m3_error": error or "Default fallback"
    }


# ─────────────────────────────────────────
#  GROQ ÇAĞIRIŞI
# ─────────────────────────────────────────

def call_groq(system_prompt: str, user_prompt: str) -> Dict:
    if not GROQ_KEY_M3:
        raise ValueError("GROQ_KEY_M3 tapılmadı.")

    headers = {
        "Authorization": f"Bearer {GROQ_KEY_M3}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_M3,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt}
        ],
        "temperature": 0.15,
        "max_tokens": 3000
    }

    response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=75)
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"].strip()

    match = re.search(r'\{.*\}', content, re.DOTALL)
    if not match:
        raise ValueError("JSON tapılmadı")

    raw = match.group()
    raw = re.sub(r',\s*}', '}', raw)
    raw = re.sub(r',\s*]', ']', raw)
    return json.loads(raw)


# ─────────────────────────────────────────
#  ANA FUNKSIYA
# ─────────────────────────────────────────

def run_m3(parser_json: Dict, m2_data: Dict) -> Dict:
    team1 = parser_json.get("team1", "Ev")
    team2 = parser_json.get("team2", "Qonaq")
    t1    = parser_json.get("team1_stats", {})
    t2    = parser_json.get("team2_stats", {})

    print(f"M3 başladı: {team1} vs {team2}")
    print(f"M2 real məlumat sayı: {count_real_fields(m2_data)}")

    tip_ev = taktika_tipi_tey(
        t1.get("avg_goals_scored"), t1.get("avg_goals_conceded"), t1.get("avg_corners")
    )
    tip_qonaq = taktika_tipi_tey(
        t2.get("avg_goals_scored"), t2.get("avg_goals_conceded"), t2.get("avg_corners")
    )

    coach_home = get_m2_field(m2_data, "coach", "home_tactical_trend", 0.65)
    coach_away = get_m2_field(m2_data, "coach", "away_tactical_trend", 0.65)
    if coach_home: tip_ev    = coach_home
    if coach_away: tip_qonaq = coach_away

    toqqusma  = toqqusma_effekti(tip_ev, tip_qonaq)
    carpanlar = hesabla_carpanlar(parser_json, m2_data)
    flags     = hesabla_flags(parser_json, m2_data, tip_ev, tip_qonaq)

    try:
        system_p, user_p = build_prompt(
            team1, team2, parser_json, m2_data,
            tip_ev, tip_qonaq, toqqusma, carpanlar, flags
        )
        result = call_groq(system_p, user_p)

        guveni = hesabla_m3_guveni(m2_data, flags, carpanlar)
        result["m3_guveni"] = guveni

        # ✅ DÜZƏLİŞ 1: [object Object] problemi
        # Əvvəl: frontend result.tempo → {"value":"orta",...} → [object Object]
        # İndi: _flat sahələr əlavə et → frontend result.tempo_value istifadə edə bilər
        # Həm də mövcud object strukturu saxlanılır (M4 üçün lazımdır)
        flat_fields = ["tempo", "taktika_ev", "taktika_qonaq", "dominant_teref",
                       "qol_veziyyeti", "btts_siqnal", "corner_siqnal",
                       "kart_siqnal", "hakim_tesiri", "oyun_oxunusu", "kahin_cumlesi"]
        for field in flat_fields:
            if field in result and isinstance(result[field], dict):
                # Flat versiya: result["tempo_value"] = "orta"
                result[f"{field}_value"] = result[field].get("value", "—")

        result.setdefault("flags", flags)
        result["carpanlar"] = carpanlar  # Groq uydurmasın deyə override et

        print(f"M3 güvəni: {guveni}/10")
        return result

    except Exception as e:
        print(f"M3 xətası: {e}")
        return get_default_m3_result(
            tip_ev=tip_ev, tip_qonaq=tip_qonaq,
            carpanlar=carpanlar, flags=flags, error=str(e)
        )


# ─────────────────────────────────────────
#  TEST
# ─────────────────────────────────────────

if __name__ == "__main__":
    test_parser = {
        "team1": "Rayo Vallecano",
        "team2": "Elche",
        "team1_stats": {
            "attack_strength": 1.12, "defense_strength": 1.08,
            "avg_goals_scored": 1.41, "avg_goals_conceded": 1.35,
            "avg_corners": 5.2, "league_position": 12, "days_since_last_match": 6
        },
        "team2_stats": {
            "attack_strength": 0.95, "defense_strength": 1.22,
            "avg_goals_scored": 1.18, "avg_goals_conceded": 1.47,
            "avg_corners": 4.8, "league_position": 19, "days_since_last_match": 4
        },
        "h2h": {"home_wins": 3, "draws": 1, "away_wins": 1}
    }
    test_m2 = {
        "referee": {
            "name": "Jesus Gil Manzano", "foul_sensitivity": "yüksək",
            "status": "real", "confidence": 0.85
        },
        "injuries": {
            "home_absent": ["Bebé"], "away_absent": ["Boyé", "Fidel"],
            "status": "real", "confidence": 0.80
        },
        "motivation": {
            "home_motivation": "orta", "away_motivation": "çox yüksək",
            "status": "real", "confidence": 0.75
        },
        "coach": {
            "home_tactical_trend": "pressing", "away_tactical_trend": "kilid-kontra",
            "status": "real", "confidence": 0.70
        }
    }

    try:
        result = run_m3(test_parser, test_m2)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print("Test xətası:", e)
