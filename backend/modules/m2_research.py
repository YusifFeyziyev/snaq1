import os
import re
import json
import time
import requests
from typing import Dict, Any, List, Optional

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

# ✅ DÜZƏLİŞ 1: URL-i None ilə birləşdirmə — tamamilə silindi (istifadə olunmurdu)
TAVILY_API_URL = "https://api.tavily.com/search"
SERPER_API_URL = "https://google.serper.dev/search"


def validate_api_keys() -> Dict[str, bool]:
    return {
        "gemini": bool(GEMINI_API_KEY),
        "tavily": bool(TAVILY_KEY),
        "serper": bool(SERPER_KEY),
    }


def search_with_tavily(query: str, retries: int = 2) -> Optional[Dict]:
    if not TAVILY_KEY:
        return None
    for attempt in range(retries):
        try:
            resp = requests.post(
                TAVILY_API_URL,
                headers={"Authorization": f"Bearer {TAVILY_KEY}", "Content-Type": "application/json"},
                json={"query": query, "search_depth": "advanced", "max_results": 6},
                timeout=25,
            )
            if resp.status_code == 200:
                return resp.json()
            time.sleep(1)
        except Exception as e:
            print(f"Tavily exception: {e}")
            time.sleep(1)
    return None


def search_with_serper(query: str, retries: int = 2) -> Optional[Dict]:
    if not SERPER_KEY:
        return None
    for attempt in range(retries):
        try:
            resp = requests.post(
                SERPER_API_URL,
                headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"},
                json={"q": query, "num": 6},
                timeout=25,
            )
            if resp.status_code == 200:
                return resp.json()
            time.sleep(1)
        except Exception as e:
            print(f"Serper exception: {e}")
            time.sleep(1)
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
        for item in search_result["results"][:6]:
            t = item.get("title", "")
            s = item.get("content", item.get("snippet", ""))
            if t: parts.append(f"Başlıq: {t}")
            if s: parts.append(f"Məzmun: {s}")
            parts.append("---")
    elif "organic" in search_result:
        for item in search_result["organic"][:6]:
            t = item.get("title", "")
            s = item.get("snippet", "")
            if t: parts.append(f"Başlıq: {t}")
            if s: parts.append(f"Məzmun: {s}")
            parts.append("---")
    return "\n".join(parts) if parts else "Heç bir nəticə tapılmadı."


def safe_json_parse(text: str) -> Dict:
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        json_str = match.group(1) if match else text.strip()

    json_str = re.sub(r",\s*}", "}", json_str)
    json_str = re.sub(r",\s*]", "]", json_str)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"JSON parse xətası: {e}. Fallback istifadə edilir...")
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
    """0-1 aralığında qaytarır. M4 *10 edib 0-10 göstərəcək."""
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
        raise ImportError("google-genai quraşdırılmayıb. 'pip install google-genai' edin.")
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY tapılmadı.")

    # ✅ DÜZƏLİŞ 2: Model adını config-dən al, fallback ilə
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

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=2500,
                response_mime_type="application/json",
            ),
        )
        content = response.text.strip()
        return safe_json_parse(content)

    except Exception as e:
        print(f"Gemini xətası: {e}")
        raise Exception(f"Gemini API xətası: {str(e)}")


def run_m2(parser_json: Dict) -> Dict:
    team1 = parser_json.get("team1", "Unknown")
    team2 = parser_json.get("team2", "Unknown")

    # ✅ DÜZƏLİŞ 3: Import xətasını burada tut, modul səviyyəsində yox
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

    all_search_text = ""
    successful = 0
    for q in queries:
        print(f"Axtarış: {q}")
        res  = search_web(q)
        text = extract_search_text(res)
        if text != "Heç bir nəticə tapılmadı.":
            successful += 1
        all_search_text += f"\n=== SORĞU: {q} ===\n{text}\n"

    if successful == 0:
        return _empty_result(warning="Heç bir axtarış nəticəsi tapılmadı.")

    try:
        result = analyze_with_gemini(team1, team2, all_search_text)
        result = _post_process(result)
        result["m2_guveni"] = calculate_m2_guveni(result)

        real_count    = sum(1 for k, v in result.items() if isinstance(v, dict) and v.get("status") == "real")
        missing_count = sum(1 for k, v in result.items() if isinstance(v, dict) and v.get("status") == "tapılmadı")
        print(f"M2 güvən: {result['m2_guveni']:.3f} (0-1) | Real: {real_count} | Tapılmadı: {missing_count}")

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