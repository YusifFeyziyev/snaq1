import os
import re
import json
import time
import requests
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    print("XƏBƏRDARLIQ: google-genai quraşdırılmayıb.")

try:
    from config import GEMINI_API_KEY, MODEL_M2, TAVILY_KEY, SERPER_KEY
except ImportError:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    MODEL_M2       = os.getenv("MODEL_M2", "gemini-2.5-flash-preview-04-17")
    TAVILY_KEY     = os.getenv("TAVILY_KEY")
    SERPER_KEY     = os.getenv("SERPER_KEY")

TAVILY_API_URL = "https://api.tavily.com/search"
SERPER_API_URL = "https://google.serper.dev/search"


# ========== DÜZƏLİŞ 6: DEBUG LOGGING ==========

def debug_m2(name, value):
    print(f"[M2 DEBUG] {name}: {value}")


# ========== DÜZƏLİŞ 1: SAFE REQUEST WRAPPER ==========

def safe_request_post(url, headers=None, json_data=None, timeout=10):
    try:
        resp = requests.post(url, headers=headers, json=json_data, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
        debug_m2("safe_request_post status", resp.status_code)
        return None
    except Exception as e:
        print(f"Request xətası: {e}")
        return None


# ========== API KEY VALIDATION ==========

def validate_api_keys() -> Dict[str, bool]:
    return {
        "gemini": bool(GEMINI_API_KEY),
        "tavily": bool(TAVILY_KEY),
        "serper": bool(SERPER_KEY),
    }


# ========== SEARCH FUNKSİYALARI ==========

def search_with_tavily(query: str, retries: int = 2) -> Optional[Dict]:
    if not TAVILY_KEY:
        return None
    for attempt in range(retries):
        result = safe_request_post(
            TAVILY_API_URL,
            headers={"Authorization": f"Bearer {TAVILY_KEY}", "Content-Type": "application/json"},
            json_data={
                "query": query,
                "search_depth": "basic",
                "max_results": 7,
                "include_answer": True,
            },
            timeout=15,
        )
        if result is not None:
            debug_m2("tavily search uğurlu", query[:40])
            return result
        debug_m2(f"tavily cəhd {attempt + 1} uğursuz", query[:40])
        time.sleep(0.5)
    return None


def search_with_serper(query: str, retries: int = 1) -> Optional[Dict]:
    if not SERPER_KEY:
        return None
    for attempt in range(retries):
        # ✅ DÜZƏLİŞ 1: requests.post → safe_request_post
        result = safe_request_post(
            SERPER_API_URL,
            headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"},
            json_data={"q": query, "num": 5},
            timeout=10,
        )
        if result is not None:
            debug_m2("serper search uğurlu", query[:40])
            return result
        debug_m2(f"serper cəhd {attempt + 1} uğursuz", query[:40])
    return None


def search_web(query: str) -> Optional[Dict]:
    result = search_with_tavily(query)
    if result:
        return result
    return search_with_serper(query)


# ========== DÜZƏLİŞ 3: NULL / BOŞ DATA ==========

def extract_search_text(search_result: Optional[Dict]) -> str:
    if not search_result:
        return "Heç bir nəticə tapılmadı."
    parts = []

    # Tavily answer field — ən dəqiq xülasə
    answer = search_result.get("answer", "").strip()
    if answer:
        parts.append(f"XÜLASƏ: {answer}")
        parts.append("---")

    if "results" in search_result:
        for item in search_result["results"][:7]:
            t = item.get("title", "").strip()
            s = item.get("content", item.get("snippet", "")).strip()
            url = item.get("url", "")
            if not t and not s:
                continue
            if t:
                parts.append(f"Başlıq: {t}")
            if url:
                parts.append(f"Mənbə: {url}")
            if s:
                # İlk 600 simvol — daha çox məzmun
                parts.append(f"Məzmun: {s[:600]}")
            parts.append("---")
    elif "organic" in search_result:
        for item in search_result["organic"][:7]:
            t = item.get("title", "").strip()
            s = item.get("snippet", "").strip()
            if not t and not s:
                continue
            if t:
                parts.append(f"Başlıq: {t}")
            if s:
                parts.append(f"Məzmun: {s[:600]}")
            parts.append("---")

    if not parts:
        return "Heç bir nəticə tapılmadı."

    text = "\n".join(parts)
    debug_m2("extract_search_text uzunluğu", len(text))
    return text


# ========== DÜZƏLİŞ 4: STABLE JSON PARSE ==========

def safe_json_parse(text: str) -> Dict:
    # ✅ DÜZƏLİŞ 4: boş text erkən yoxla
    if not text or not text.strip():
        debug_m2("safe_json_parse", "boş mətn gəldi → _empty_sections")
        return _empty_sections()
    try:
        from json_repair import repair_json
        text = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()
        start = text.find("{")
        end   = text.rfind("}")
        if start == -1 or end == -1:
            debug_m2("safe_json_parse", "{ } tapılmadı → _empty_sections")
            return _empty_sections()
        raw = text[start:end + 1]
        result = json.loads(repair_json(raw))
        # ✅ DÜZƏLİŞ 4: nəticə dict deyilsə → reject et
        if not isinstance(result, dict):
            debug_m2("safe_json_parse", "nəticə dict deyil → _empty_sections")
            return _empty_sections()
        if any(k in result for k in ["referee", "coach", "injuries"]):
            debug_m2("safe_json_parse", "uğurlu parse")
            return result
        debug_m2("safe_json_parse", "açar tapılmadı → _empty_sections")
        return _empty_sections()
    except Exception as e:
        print(f"JSON repair xətası: {e}")
        return _empty_sections()


# ========== BOŞLUQ STRUKTURLARI ==========

def _empty_sections() -> Dict:
    return {
        "referee":    {"status": "tapılmadı", "confidence": 0.0},
        "coach":      {"status": "tapılmadı", "confidence": 0.0},
        "injuries":   {"status": "tapılmadı", "confidence": 0.0},
        "lineup":     {"status": "tapılmadı", "confidence": 0.0},
        "stadium":    {"status": "tapılmadı", "confidence": 0.0},
        "weather":    {"status": "tapılmadı", "confidence": 0.0},
        "motivation": {"status": "tapılmadı", "confidence": 0.0},
        "fatigue":    {"status": "tapılmadı", "confidence": 0.0},
    }


def _empty_result(warning: str = None, error: str = None) -> Dict:
    result = _empty_sections()
    # ✅ DÜZƏLİŞ 9: m2_guveni mütləq float olsun
    result["m2_guveni"] = 0.0
    if warning:
        result["m2_warning"] = str(warning)
    if error:
        result["m2_error"] = str(error)
    return result


# ========== HESABLAMA KÖMƏKÇILƏRI ==========

def calculate_m2_guveni(result: Dict) -> float:
    confs = [
        float(v["confidence"])
        for k, v in result.items()
        if isinstance(v, dict) and isinstance(v.get("confidence"), (int, float))
    ]
    if not confs:
        return 0.0
    return round(sum(confs) / len(confs), 3)


# ========== DÜZƏLİŞ 5: CONFIDENCE LIMIT ==========

def _post_process(result: Dict) -> Dict:
    for key, val in result.items():
        if not isinstance(val, dict):
            continue
        status = val.get("status", "tapılmadı")
        conf   = float(val.get("confidence", 0.0))

        if status == "təxmin":
            val["status"]     = "tapılmadı"
            val["confidence"] = 0.0

        if val.get("status") == "tapılmadı":
            val["confidence"] = 0.0

        if val.get("status") == "real" and conf > 0.95:
            val["confidence"] = 0.95

        # ✅ DÜZƏLİŞ 5: confidence heç vaxt 0-1 aralığından kənara çıxmasın
        val["confidence"] = max(0.0, min(float(val.get("confidence", 0.0)), 1.0))

    return result


# ========== SYSTEM PROMPT (dəyişdirilməyib) ==========

SYSTEM_PROMPT = """Sən futbol məlumat analitikisən. Sənə axtarış nəticələri veriləcək.

QAYDALAR (MÜTLƏQ):
1. Axtarış nəticələrindəki HƏM BİRBAŞA, HƏM DOLAYI məlumatlardan istifadə et.
2. HAKİM: "referee", "arbitro", "árbitro", "officiel", "wasit" sözlərinin yanındakı adı tap.
   - Şübhəli olsa belə confidence=0.6 ilə "real" say
   - foul_sensitivity: hakimin ortalama sarı kartına görə — 4+ kart/oyun="yüksək", 3-4="orta", <3="aşağı"
3. ZƏDƏLƏLƏr: "injured", "out", "doubtful", "suspended", "missing", "unavailable", "assente", "squalificato" sözlərinin yanındakı oyunçu adları
   - Hər komanda üçün ayrı siyahı ver
4. MƏŞQÇI: "manager", "coach", "allenatore", "head coach", "mister" sözlərinin yanındakı adı tap
   - taktiki trend: son oyunlardakı "4-3-3", "4-2-3-1", "press", "possession", "counter" kimi ifadələrdən çıxar
5. HEYƏT: "lineup", "XI", "formation", "starting" sözlərinin yanındakı formasyonu tap
   - Tapılmadısa son oyundan gözlənilən formasyonu orta güvənlə ver (confidence=0.55)
6. YORĞUNLUq: 
   - Son oyun tarixini tap (məs: "played April 3rd", "last match on 3 Apr")
   - Bu oyunun tarixi: {match_date}
   - days_since = bu oyun tarixi - son oyun tarixi (gün fərqi hesabla)
   - 1-3 gün = "yüksək" yorğunluq, 4-5 gün = "orta", 6+ gün = "aşağı"
7. MOTİVASİYA: Cədvəl mövqeyi, şampionluq/degradasiya mübarizəsi, H2H rəqabəti nəzərə al
   - Avtomatik: zirvə mübarizəsi = "yüksək", orta cədvəl = "orta"
8. HAVA: stadionun şəhərinin hava proqnozunu tap (Naples/Milano/Madrid və s.)
9. Şübhəli məlumat → confidence=0.5-0.65, status="real"
10. Axtarışda İZ BELƏ OLMAYAN məlumat → status="tapılmadı", confidence=0.0
11. status="təxmin" QADAĞANDIR — ya "real", ya "tapılmadı"
12. Yalnız aşağıdakı JSON strukturunu qaytar, heç bir əlavə mətn yazma."""


# ========== DÜZƏLİŞ 7: GEMINI RESPONSE PROTECTION ==========

def analyze_with_gemini(team1: str, team2: str, search_text: str,
                        match_date: str = "") -> Dict:
    if not GENAI_AVAILABLE:
        raise ImportError("google-genai quraşdırılmayıb.")
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY tapılmadı.")

    model_name = MODEL_M2 or "gemini-2.5-flash-preview-04-17"
    client = genai.Client(api_key=GEMINI_API_KEY)

    # SYSTEM_PROMPT-da {match_date} placeholder doldur
    system_filled = SYSTEM_PROMPT.replace("{match_date}", match_date or "bilinmir")

    user_prompt = f"""
{system_filled}

Komandalar: {team1} (ev) vs {team2} (qonaq)
Bu oyunun tarixi: {match_date or "bilinmir"}

Axtarış nəticələri:
{search_text[:10000]}

ÇIXIŞ QAYDASI:
- Tapıldısa: status="real", confidence=0.70-0.95
- Şübhəlidirsə: status="real", confidence=0.50-0.69
- Tapılmadısa: status="tapılmadı", confidence=0.0, sahəni null burax

Yalnız bu JSON strukturunu qaytar (başqa heç nə yazma):
{{
    "referee": {{
        "name": "Hakimin adı soyadı",
        "yellow_avg": null,
        "red_avg": null,
        "foul_sensitivity": "yüksək/orta/aşağı",
        "status": "real",
        "confidence": 0.85
    }},
    "coach": {{
        "home_coach": "Ev məşqçisinin adı soyadı",
        "away_coach": "Qonaq məşqçisinin adı soyadı",
        "home_tactical_trend": "pressing/sahiblik/kontra/balanslı",
        "away_tactical_trend": "pressing/sahiblik/kontra/balanslı",
        "status": "real",
        "confidence": 0.75
    }},
    "injuries": {{
        "home_absent": ["Oyunçu 1", "Oyunçu 2"],
        "away_absent": ["Oyunçu adı"],
        "home_doubtful": [],
        "away_doubtful": [],
        "key_players_missing": ["Ən vacib çatışmayan oyunçu"],
        "status": "real",
        "confidence": 0.80
    }},
    "lineup": {{
        "home_expected": "4-3-3",
        "away_expected": "4-2-3-1",
        "home_rotation": "aşağı/orta/yüksək",
        "away_rotation": "aşağı/orta/yüksək",
        "status": "real",
        "confidence": 0.65
    }},
    "stadium": {{
        "name": "Stadion adı",
        "capacity": null,
        "home_advantage": "güclü/orta/zəif",
        "status": "real",
        "confidence": 0.80
    }},
    "weather": {{
        "temperature": 18,
        "condition": "aydın/buludlu/yağışlı",
        "wind": "zəif/orta/güclü",
        "impact": "aşağı/orta/yüksək",
        "status": "real",
        "confidence": 0.70
    }},
    "motivation": {{
        "home_motivation": "yüksək/orta/aşağı",
        "away_motivation": "yüksək/orta/aşağı",
        "reason": "Liqa mövqeyi və rəqabət konteksti",
        "status": "real",
        "confidence": 0.80
    }},
    "fatigue": {{
        "home_fatigue": "aşağı/orta/yüksək",
        "away_fatigue": "aşağı/orta/yüksək",
        "days_since_last_match_home": 7,
        "days_since_last_match_away": 6,
        "status": "real",
        "confidence": 0.70
    }}
}}"""

    content = ""
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=8000,
            ),
        )

        if not response or not response.text:
            raise ValueError("Gemini boş cavab qaytardı.")

        content = response.text.strip()
        if not content:
            raise ValueError("Gemini cavabı yalnız boşluqlardan ibarətdir.")

        print(f"GEMINI RAW: {content[:300]}")
        debug_m2("gemini cavab uzunluğu", len(content))

        return safe_json_parse(content)

    except Exception as e:
        print(f"Gemini xətası: {e}")
        raise Exception(f"Gemini API xətası: {str(e)}")


# ========== PARALEL AXTARIŞ ==========

def run_searches_parallel(queries: List[str]) -> tuple:
    """
    Bütün sorğuları eyni anda işlədir.
    6 ardıcıl axtarış (~60s) → 6 paralel axtarış (~10-15s)
    """
    results: Dict[str, str] = {}

    def _search_one(q: str) -> tuple:
        # ✅ DÜZƏLİŞ 8: hər request-dən əvvəl kiçik delay
        time.sleep(0.2)
        res  = search_web(q)
        text = extract_search_text(res)
        debug_m2("axtarış tamamlandı", q[:40])
        return q, text

    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {executor.submit(_search_one, q): q for q in queries}

        # ✅ DÜZƏLİŞ 2: timeout-u as_completed-dən çıxardıq
        # as_completed(..., timeout=25) bütün loop-u crash edirdi
        # İndi hər future ayrıca try/except ilə idarə olunur
        for future in as_completed(futures):
            q = futures[future]
            try:
                # ✅ DÜZƏLİŞ 2: hər future üçün ayrıca timeout
                result_q, text = future.result(timeout=20)
                results[result_q] = text
            except TimeoutError:
                print(f"Axtarış timeout ({q[:30]}): 20s keçdi.")
                results[q] = "Heç bir nəticə tapılmadı."
            except Exception as e:
                print(f"Axtarış xətası ({q[:30]}): {e}")
                results[q] = "Heç bir nəticə tapılmadı."

    # Birləşdir, sıranı qoru
    combined  = ""
    successful = 0
    for q in queries:
        text = results.get(q, "Heç bir nəticə tapılmadı.")
        if text != "Heç bir nəticə tapılmadı.":
            successful += 1
        combined += f"\n=== SORĞU: {q} ===\n{text}\n"

    debug_m2("run_searches_parallel uğurlu", f"{successful}/{len(queries)}")
    return combined, successful


# ========== ƏSAS run_m2 FUNKSİYASI ==========

def run_m2(parser_json: Dict) -> Dict:
    team1      = parser_json.get("team1", "Unknown")
    team2      = parser_json.get("team2", "Unknown")
    league     = parser_json.get("league", "")
    match_date = parser_json.get("date", "")[:10]   # "2026-04-06"
    date_tag   = match_date[:7] if match_date else "2026"  # "2026-04"

    if not GENAI_AVAILABLE:
        return _empty_result(error="google-genai quraşdırılmayıb.")
    if not GEMINI_API_KEY:
        return _empty_result(error="GEMINI_API_KEY tapılmadı.")
    if not TAVILY_KEY and not SERPER_KEY:
        return _empty_result(error="Nə TAVILY_KEY, nə SERPER_KEY tapılmadı.")

    league_tag = f"{league} " if league and league not in ("Unknown", "") else ""
    print(f"M2 başladı: {team1} vs {team2} | Liqa: {league_tag.strip() or 'naməlum'}")

    # 12 hədəfli axtarış sorğusu
    queries = [
        # Hakim
        f"{team1} {team2} referee official appointed {league_tag}{date_tag}",
        f"{team1} vs {team2} arbitro designato {date_tag}",
        # Zədələr — hər komanda ayrıca
        f"{team1} injury news team news out suspended {date_tag}",
        f"{team2} injury news team news out suspended {date_tag}",
        # Heyət
        f"{team1} predicted starting lineup XI formation {date_tag}",
        f"{team2} predicted starting lineup XI formation {date_tag}",
        # Məşqçi
        f"{team1} head coach manager name tactics {date_tag}",
        f"{team2} head coach manager name tactics {date_tag}",
        # Son oyun (yorğunluq üçün)
        f"{team1} last match played result date {date_tag}",
        f"{team2} last match played result date {date_tag}",
        # Ümumi preview + motivasiya
        f"{team1} {team2} match preview {league_tag}{date_tag}",
        f"{team1} {team2} {league_tag}standings title race motivation {date_tag}",
    ]

    all_search_text, successful = run_searches_parallel(queries)
    print(f"Axtarış tamamlandı: {successful}/{len(queries)} uğurlu")
    debug_m2("ümumi search text uzunluğu", len(all_search_text))

    if successful == 0:
        return _empty_result(warning="Heç bir axtarış nəticəsi tapılmadı.")

    try:
        result = analyze_with_gemini(team1, team2, all_search_text, match_date)
        result = _post_process(result)
        result["m2_guveni"] = calculate_m2_guveni(result)

        real_count    = sum(1 for k, v in result.items() if isinstance(v, dict) and v.get("status") == "real")
        missing_count = sum(1 for k, v in result.items() if isinstance(v, dict) and v.get("status") == "tapılmadı")
        print(f"M2 güvən: {result['m2_guveni']:.3f} | Real: {real_count} | Tapılmadı: {missing_count}")
        debug_m2("real_count", real_count)
        debug_m2("missing_count", missing_count)

        if missing_count > 4:
            result["m2_warning"] = f"{missing_count} kateqoriyada real məlumat tapılmadı."

        if not isinstance(result, dict):
            return _empty_result(error="Nəticə dict formatında deyil.")

        result["m2_guveni"] = float(result.get("m2_guveni", 0.0))

        empty = _empty_sections()
        for key in empty:
            if key not in result:
                result[key] = empty[key]

        debug_m2("m2_guveni final", result["m2_guveni"])
        return result

    except Exception as e:
        print(f"M2 xətası: {e}")
        return _empty_result(error=str(e))


# ========== TEST BLOKU ==========

if __name__ == "__main__":
    test = {"team1": "Inter Milan", "team2": "AS Roma"}
    try:
        result = run_m2(test)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print("Test xətası:", e)