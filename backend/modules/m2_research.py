import os
import json
import time
import requests
from typing import Dict, Any, List, Optional

try:
    from config import GROQ_KEY_M2, MODEL_M2, TAVILY_KEY, SERPER_KEY
except ImportError:
    GROQ_KEY_M2 = os.getenv("GROQ_KEY_M2")
    MODEL_M2 = os.getenv("MODEL_M2", "llama-3.3-70b-versatile")
    TAVILY_KEY = os.getenv("TAVILY_KEY")
    SERPER_KEY = os.getenv("SERPER_KEY")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
TAVILY_API_URL = "https://api.tavily.com/search"
SERPER_API_URL = "https://google.serper.dev/search"

def validate_api_keys() -> Dict[str, bool]:
    return {
        "groq": bool(GROQ_KEY_M2),
        "tavily": bool(TAVILY_KEY),
        "serper": bool(SERPER_KEY)
    }

def search_with_tavily(query: str, retries: int = 2) -> Optional[Dict]:
    if not TAVILY_KEY:
        return None
    for attempt in range(retries):
        try:
            headers = {
                "Authorization": f"Bearer {TAVILY_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "query": query,
                "search_depth": "advanced",
                "max_results": 5
            }
            response = requests.post(TAVILY_API_URL, headers=headers, json=payload, timeout=25)
            if response.status_code == 200:
                return response.json()
            else:
                if attempt == retries - 1:
                    print(f"Tavily xətası (status {response.status_code}): {query}")
                time.sleep(1)
        except requests.exceptions.Timeout:
            print(f"Tavily timeout (cəhd {attempt+1}): {query}")
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
            headers = {
                "X-API-KEY": SERPER_KEY,
                "Content-Type": "application/json"
            }
            payload = {
                "q": query,
                "num": 5
            }
            response = requests.post(SERPER_API_URL, headers=headers, json=payload, timeout=25)
            if response.status_code == 200:
                return response.json()
            else:
                if attempt == retries - 1:
                    print(f"Serper xətası (status {response.status_code}): {query}")
                time.sleep(1)
        except requests.exceptions.Timeout:
            print(f"Serper timeout (cəhd {attempt+1}): {query}")
            time.sleep(1)
        except Exception as e:
            print(f"Serper exception: {e}")
            time.sleep(1)
    return None

def search_web(query: str) -> Optional[Dict]:
    result = search_with_tavily(query)
    if result:
        return result
    result = search_with_serper(query)
    if result:
        return result
    return None

def extract_search_text(search_result: Optional[Dict]) -> str:
    if not search_result:
        return "Heç bir nəticə tapılmadı."

    text_parts = []

    if "results" in search_result:
        for item in search_result["results"][:5]:
            title = item.get("title", "")
            snippet = item.get("content", item.get("snippet", ""))
            if title:
                text_parts.append(f"Başlıq: {title}")
            if snippet:
                text_parts.append(f"Məzmun: {snippet}")
            text_parts.append("---")

    elif "organic" in search_result:
        for item in search_result["organic"][:5]:
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            if title:
                text_parts.append(f"Başlıq: {title}")
            if snippet:
                text_parts.append(f"Məzmun: {snippet}")
            text_parts.append("---")

    if not text_parts:
        return "Heç bir nəticə tapılmadı."

    return "\n".join(text_parts)

def safe_json_parse(text: str) -> Dict:
    import re

    json_pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
    match = re.search(json_pattern, text, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        brace_pattern = r"(\{.*\})"
        match = re.search(brace_pattern, text, re.DOTALL)
        if match:
            json_str = match.group(1)
        else:
            json_str = text.strip()

    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"JSON parse xətası: {e}. Fallback edilir...")
        return {
            "referee": {"status": "tapılmadı", "confidence": 0.0},
            "coach": {"status": "tapılmadı", "confidence": 0.0},
            "injuries": {"status": "tapılmadı", "confidence": 0.0},
            "lineup": {"status": "tapılmadı", "confidence": 0.0},
            "stadium": {"status": "tapılmadı", "confidence": 0.0},
            "weather": {"status": "tapılmadı", "confidence": 0.0},
            "motivation": {"status": "tapılmadı", "confidence": 0.0},
            "fatigue": {"status": "tapılmadı", "confidence": 0.0}
        }

# ✅ DÜZƏLİŞ: m2_guveni hesablayan köməkçi funksiya
def calculate_m2_guveni(result: Dict) -> float:
    """
    Bütün kateqoriyaların confidence dəyərlərinin ortalamasını götürür,
    0-1 → 0-10 şkalasına çevirir.
    """
    confidences = []
    for key, value in result.items():
        if isinstance(value, dict) and isinstance(value.get("confidence"), (int, float)):
            confidences.append(float(value["confidence"]))
    if not confidences:
        return 0.0
    avg = sum(confidences) / len(confidences)
    return round(avg * 10, 1)  # 0-1 → 0-10

def _empty_result(warning: str = None, error: str = None) -> Dict:
    """Boş nəticə şablonu — m2_guveni həmişə daxildir."""
    result = {
        "referee":    {"status": "tapılmadı", "confidence": 0.0},
        "coach":      {"status": "tapılmadı", "confidence": 0.0},
        "injuries":   {"status": "tapılmadı", "confidence": 0.0},
        "lineup":     {"status": "tapılmadı", "confidence": 0.0},
        "stadium":    {"status": "tapılmadı", "confidence": 0.0},
        "weather":    {"status": "tapılmadı", "confidence": 0.0},
        "motivation": {"status": "tapılmadı", "confidence": 0.0},
        "fatigue":    {"status": "tapılmadı", "confidence": 0.0},
        "m2_guveni":  0.0  # ✅ həmişə mövcuddur
    }
    if warning:
        result["m2_warning"] = warning
    if error:
        result["m2_error"] = error
    return result

def analyze_with_groq(team1: str, team2: str, search_text: str) -> Dict:
    if not GROQ_KEY_M2:
        raise ValueError("GROQ_KEY_M2 environment-da tapılmadı.")

    system_prompt = """Sən futbol analitikisən. Verilən axtarış nəticələrinə əsasən aşağıdakı JSON strukturunu doldur. Hər məlumat üçün status (real, təxmin, tapılmadı) və confidence (0-1 arası) qaytar. Heç bir əlavə izah yazma, yalnız JSON.

{
    "referee": {
        "name": "Hakimin adı",
        "yellow_avg": float or null,
        "red_avg": float or null,
        "foul_sensitivity": "yüksək/orta/aşağı",
        "status": "real/təxmin/tapılmadı",
        "confidence": float
    },
    "coach": {
        "home_coach": "Ev komandasının məşqçisi",
        "away_coach": "Qonaq komandasının məşqçisi",
        "home_tactical_trend": "son oyunlardakı taktika",
        "away_tactical_trend": "son oyunlardakı taktika",
        "status": "real/təxmin/tapılmadı",
        "confidence": float
    },
    "injuries": {
        "home_absent": ["oyunçu1", "oyunçu2"],
        "away_absent": ["oyunçu1", "oyunçu2"],
        "home_doubtful": ["oyunçu1"],
        "away_doubtful": ["oyunçu1"],
        "key_players_missing": ["əsas oyunçu"],
        "status": "real/təxmin/tapılmadı",
        "confidence": float
    },
    "lineup": {
        "home_expected": "4-3-3",
        "away_expected": "4-4-2",
        "home_rotation": "aşağı/orta/yüksək",
        "away_rotation": "aşağı/orta/yüksək",
        "status": "real/təxmin/tapılmadı",
        "confidence": float
    },
    "stadium": {
        "name": "Stadion adı",
        "capacity": int or null,
        "home_advantage": "güclü/orta/zəif",
        "status": "real/təxmin/tapılmadı",
        "confidence": float
    },
    "weather": {
        "temperature": int or null,
        "condition": "yağışlı/buludlu/günəşli",
        "wind": "yüngül/orta/güclü",
        "impact": "aşağı/orta/yüksək",
        "status": "real/təxmin/tapılmadı",
        "confidence": float
    },
    "motivation": {
        "home_motivation": "yüksək/orta/aşağı",
        "away_motivation": "yüksək/orta/aşağı",
        "reason": "səbəb",
        "status": "real/təxmin/tapılmadı",
        "confidence": float
    },
    "fatigue": {
        "home_fatigue": "aşağı/orta/yüksək",
        "away_fatigue": "aşağı/orta/yüksək",
        "days_since_last_match_home": int or null,
        "days_since_last_match_away": int or null,
        "status": "real/təxmin/tapılmadı",
        "confidence": float
    }
}"""

    user_prompt = f"""Komandalar: {team1} vs {team2}

Axtarış nəticələri:
{search_text[:6000]}

Yuxarıdakı JSON strukturuna uyğun olaraq məlumatları doldur."""

    headers = {
        "Authorization": f"Bearer {GROQ_KEY_M2}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL_M2,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 3000
    }

    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        assistant_message = data["choices"][0]["message"]["content"]
        return safe_json_parse(assistant_message)
    except requests.exceptions.Timeout:
        raise Exception("Groq API timeout (60 saniyə).")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Groq API xətası: {str(e)}")
    except Exception as e:
        raise Exception(f"Gözlənilməz xəta: {str(e)}")

def run_m2(parser_json: Dict) -> Dict:
    team1 = parser_json.get("team1", "Unknown")
    team2 = parser_json.get("team2", "Unknown")

    keys = validate_api_keys()
    if not keys["groq"]:
        return _empty_result(error="GROQ_KEY_M2 tapılmadı. M2 işləyə bilməz.")
    if not keys["tavily"] and not keys["serper"]:
        return _empty_result(error="Nə TAVILY_KEY, nə SERPER_KEY tapılmadı.")

    print(f"M2 başladı: {team1} vs {team2}")
    print(f"API vəziyyəti: Groq={keys['groq']}, Tavily={keys['tavily']}, Serper={keys['serper']}")

    queries = [
        f"{team1} vs {team2} referee stats yellow cards fouls",
        f"{team1} vs {team2} coach tactics lineup",
        f"{team1} injuries lineup expected {team2} injuries",
        f"{team1} {team2} stadium weather match preview"
    ]

    all_search_text = ""
    successful_searches = 0
    for q in queries:
        print(f"Axtarış: {q}")
        search_result = search_web(q)
        text = extract_search_text(search_result)
        if text != "Heç bir nəticə tapılmadı.":
            successful_searches += 1
        all_search_text += f"\n--- SORĞU: {q} ---\n{text}\n"

    if successful_searches == 0:
        print("XƏBƏRDARLIQ: Heç bir axtarış nəticə vermədi.")
        return _empty_result(warning="Heç bir axtarış nəticəsi tapılmadı. API açarlarını yoxlayın.")

    try:
        result = analyze_with_groq(team1, team2, all_search_text)

        # ✅ DÜZƏLİŞ: m2_guveni hesabla və əlavə et (0-10 şkala)
        result["m2_guveni"] = calculate_m2_guveni(result)
        print(f"M2 güvəni: {result['m2_guveni']}/10")

        # Zəif kateqoriya xəbərdarlığı
        low_conf_count = sum(
            1 for key, value in result.items()
            if isinstance(value, dict) and value.get("status") == "tapılmadı"
        )
        if low_conf_count > 4:
            result["m2_warning"] = f"{low_conf_count} kateqoriyada məlumat tapılmadı."

        return result

    except Exception as e:
        print(f"M2 Groq xətası: {e}")
        return _empty_result(error=str(e))

if __name__ == "__main__":
    test_parser_json = {
        "team1": "Liverpool",
        "team2": "Manchester City"
    }
    try:
        result = run_m2(test_parser_json)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print("Test xətası:", e)
