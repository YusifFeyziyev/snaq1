import os
import re
import json
import time
import requests
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed   # ✅ YENİ

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


def validate_api_keys() -> Dict[str, bool]:
    return {
        "gemini": bool(GEMINI_API_KEY),
        "tavily": bool(TAVILY_KEY),
        "serper": bool(SERPER_KEY),
    }


def search_with_tavily(query: str, retries: int = 1) -> Optional[Dict]:   # ✅ retries: 2→1
    if not TAVILY_KEY:
        return None
    for attempt in range(retries):
        try:
            resp = requests.post(
                TAVILY_API_URL,
                headers={"Authorization": f"Bearer {TAVILY_KEY}", "Content-Type": "application/json"},
                json={"query": query, "search_depth": "basic", "max_results": 5},   # ✅ advanced→basic
                timeout=10,   # ✅ 25→10
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"Tavily exception: {e}")
    return None


def search_with_serper(query: str, retries: int = 1) -> Optional[Dict]:   # ✅ retries: 2→1
    if not SERPER_KEY:
        return None
    for attempt in range(retries):
        try:
            resp = requests.post(
                SERPER_API_URL,
                headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"},
                json={"q": query, "num": 5},
                timeout=10,   # ✅ 25→10
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"Serper exception: {e}")
    return None


def search_web(query: str) -> Optional[Dict]:
    result = search_with_tavily(query)
    if result:
        return result
    return search_with_serper(query)


def extract_search_text(search_result: Optional[Dict]) -> str:
    if not search_result:
        return "Heç bir nəticə tapılmadı."
    parts = []
    if "results" in search_result:
        for item in search_result["results"][:5]:
            t = item.get("title", "")
            s = item.get("content", item.get("snippet", ""))
            if t: parts.append(f"Başlıq: {t}")
            if s: parts.append(f"Məzmun: {s}")
            parts.append("---")
    elif "organic" in search_result:
        for item in search_result["organic"][:5]:
            t = item.get("title", "")
            s = item.get("snippet", "")
            if t: parts.append(f"Başlıq: {t}")
            if s: parts.append(f"Məzmun: {s}")
            parts.append("---")
    return "\n".join(parts) if parts else "Heç bir nəticə tapılmadı."


def safe_json_parse(text: str) -> Dict:
    try:
        from json_repair import repair_json
        text = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()
        start = text.find("{")
        end   = text.rfind("}")
        if start == -1 or end == -1:
            return _empty_sections()
        raw = text[start:end+1]
        result = json.loads(repair_json(raw))
        if any(k in result for k in ["referee", "coach", "injuries"]):
            return result
        return _empty_sections()
    except Exception as e:
        print(f"JSON repair xətası: {e}")
        return _empty_sections()


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
    result["m2_guveni"] = 0.0
    if warning: result["m2_warning"] = warning
    if error:   result["m2_error"]   = error
    return result


def calculate_m2_guveni(result: Dict) -> float:
    confs = [
        float(v["confidence"])
        for k, v in result.items()
        if isinstance(v, dict) and isinstance(v.get("confidence"), (int, float))
    ]
    if not confs:
        return 0.0
    return round(sum(confs) / len(confs), 3)


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

    return result


SYSTEM_PROMPT = """Sən futbol məlumat analitikisən. Sənə axtarış nəticələri verilir.
QAYDALAR (MÜTLƏQ):
1. Yalnız axtarış nəticələrindəki REAL məlumatlara əsaslan.
2. Axtarış nəticəsində tapılmayan məlumat üçün status="tapılmadı", confidence=0.0 qaytar.
3. ƏSLA uydurmaq, ehtimal etmək, ya da bil ki-dən istifadə etmə.
4. Məlumat tapılıbsa status="real", confidence=0.7-0.95 qaytar.
5. status="təxmin" istifadə etmə — ya "real", ya "tapılmadı".
6. Yalnız aşağıdakı JSON strukturunu qaytar, heç bir əlavə mətn yazma."""


def analyze_with_gemini(team1: str, team2: str, search_text: str) -> Dict:
    if not GENAI_AVAILABLE:
        raise ImportError("google-genai quraşdırılmayıb.")
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY tapılmadı.")
    

    model_name = MODEL_M2 or "gemini-2.5-flash-preview-04-17"
    client = genai.Client(api_key=GEMINI_API_KEY)

    user_prompt = f"""


{SYSTEM_PROMPT}

Komandalar: {team1} vs {team2}

Axtarış nəticələri:
{search_text[:8000]}

Yalnız aşağıdakı JSON strukturunu qaytar:
{{
    "referee": {{
        "name": "string or null",
        "yellow_avg": null,
        "red_avg": null,
        "foul_sensitivity": "yüksək/orta/aşağı or null",
        "status": "real/tapılmadı",
        "confidence": 0.0
    }},
    "coach": {{
        "home_coach": "string or null",
        "away_coach": "string or null",
        "home_tactical_trend": "string or null",
        "away_tactical_trend": "string or null",
        "status": "real/tapılmadı",
        "confidence": 0.0
    }},
    "injuries": {{
        "home_absent": [],
        "away_absent": [],
        "home_doubtful": [],
        "away_doubtful": [],
        "key_players_missing": [],
        "status": "real/tapılmadı",
        "confidence": 0.0
    }},
    "lineup": {{
        "home_expected": "string or null",
        "away_expected": "string or null",
        "home_rotation": "aşağı/orta/yüksək or null",
        "away_rotation": "aşağı/orta/yüksək or null",
        "status": "real/tapılmadı",
        "confidence": 0.0
    }},
    "stadium": {{
        "name": "string or null",
        "capacity": null,
        "home_advantage": "güclü/orta/zəif or null",
        "status": "real/tapılmadı",
        "confidence": 0.0
    }},
    "weather": {{
        "temperature": null,
        "condition": "string or null",
        "wind": "string or null",
        "impact": "aşağı/orta/yüksək or null",
        "status": "real/tapılmadı",
        "confidence": 0.0
    }},
    "motivation": {{
        "home_motivation": "yüksək/orta/aşağı or null",
        "away_motivation": "yüksək/orta/aşağı or null",
        "reason": "string or null",
        "status": "real/tapılmadı",
        "confidence": 0.0
    }},
    "fatigue": {{
        "home_fatigue": "aşağı/orta/yüksək or null",
        "away_fatigue": "aşağı/orta/yüksək or null",
        "days_since_last_match_home": null,
        "days_since_last_match_away": null,
        "status": "real/tapılmadı",
        "confidence": 0.0
    }}
}}"""
    content = ""
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=2500,
            ),
        )
        content = response.text.strip()
        print(f"GEMINI RAW: {content[:300]}")  # ← burda düzgündür
        return safe_json_parse(content)

    except Exception as e:
        print(f"Gemini xətası: {e}")
        raise Exception(f"Gemini API xətası: {str(e)}")


# ✅ YENİ: Paralel axtarış funksiyası
def run_searches_parallel(queries: List[str]) -> tuple[str, int]:
    """
    Bütün sorğuları eyni anda işlədir.
    6 ardıcıl axtarış (~60s) → 6 paralel axtarış (~10-15s)
    """
    results: Dict[str, str] = {}

    def _search_one(q: str) -> tuple[str, str]:
        res  = search_web(q)
        text = extract_search_text(res)
        print(f"Axtarış tamamlandı: {q[:40]}...")
        return q, text

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(_search_one, q): q for q in queries}
        for future in as_completed(futures, timeout=25):   # max 25s gözlə
            try:
                q, text = future.result()
                results[q] = text
            except Exception as e:
                q = futures[future]
                print(f"Axtarış xətası ({q[:30]}): {e}")
                results[q] = "Heç bir nəticə tapılmadı."

    # Birləşdir, sıranı qoru
    combined = ""
    successful = 0
    for q in queries:
        text = results.get(q, "Heç bir nəticə tapılmadı.")
        if text != "Heç bir nəticə tapılmadı.":
            successful += 1
        combined += f"\n=== SORĞU: {q} ===\n{text}\n"

    return combined, successful


def run_m2(parser_json: Dict) -> Dict:
    team1 = parser_json.get("team1", "Unknown")
    team2 = parser_json.get("team2", "Unknown")

    if not GENAI_AVAILABLE:
        return _empty_result(error="google-genai quraşdırılmayıb.")
    if not GEMINI_API_KEY:
        return _empty_result(error="GEMINI_API_KEY tapılmadı.")
    if not TAVILY_KEY and not SERPER_KEY:
        return _empty_result(error="Nə TAVILY_KEY, nə SERPER_KEY tapılmadı.")

    print(f"M2 başladı: {team1} vs {team2}")

    queries = [
        f"{team1} {team2} referee 2025 2026",
        f"{team1} {team2} injury report missing players",
        f"{team1} {team2} predicted lineup formation",
        f"{team1} {team2} match preview",
        f"{team1} recent results last 5 matches",
        f"{team2} recent results last 5 matches",
    ]

    # ✅ Paralel axtarış — əvvəl ardıcıl idi
    all_search_text, successful = run_searches_parallel(queries)
    print(f"Axtarış tamamlandı: {successful}/{len(queries)} uğurlu")

    if successful == 0:
        return _empty_result(warning="Heç bir axtarış nəticəsi tapılmadı.")

    try:
        result = analyze_with_gemini(team1, team2, all_search_text)
        result = _post_process(result)
        result["m2_guveni"] = calculate_m2_guveni(result)

        real_count    = sum(1 for k, v in result.items() if isinstance(v, dict) and v.get("status") == "real")
        missing_count = sum(1 for k, v in result.items() if isinstance(v, dict) and v.get("status") == "tapılmadı")
        print(f"M2 güvən: {result['m2_guveni']:.3f} | Real: {real_count} | Tapılmadı: {missing_count}")

        if missing_count > 4:
            result["m2_warning"] = f"{missing_count} kateqoriyada real məlumat tapılmadı."

        return result

    except Exception as e:
        print(f"M2 xətası: {e}")
        return _empty_result(error=str(e))


if __name__ == "__main__":
    test = {"team1": "Inter Milan", "team2": "AS Roma"}
    try:
        result = run_m2(test)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print("Test xətası:", e)