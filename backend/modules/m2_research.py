import os
import json
import time
import requests
from typing import Dict, Any, List, Optional

# Config-dən açarları və model adını götür
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

# ========== API KEY YOXLANMASI (CRITICAL) ==========
def validate_api_keys() -> Dict[str, bool]:
    """API açarlarının vəziyyətini yoxlayır."""
    return {
        "groq": bool(GROQ_KEY_M2),
        "tavily": bool(TAVILY_KEY),
        "serper": bool(SERPER_KEY)
    }

# ========== AXTARIŞ FUNKSİYALARI (RETRY İLƏ) ==========
def search_with_tavily(query: str, retries: int = 2) -> Optional[Dict]:
    """Tavily API ilə axtarış edir. Retry mexanizmi var."""
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
    """Serper API ilə axtarış edir. Retry mexanizmi var."""
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
    """Əvvəl Tavily, sonra Serper ilə axtarış edir."""
    result = search_with_tavily(query)
    if result:
        return result
    result = search_with_serper(query)
    if result:
        return result
    return None

def extract_search_text(search_result: Optional[Dict]) -> str:
    """Axtarış nəticəsindən mətni çıxarır."""
    if not search_result:
        return "Heç bir nəticə tapılmadı."
    
    text_parts = []
    
    # Tavily formatı
    if "results" in search_result:
        for item in search_result["results"][:5]:
            title = item.get("title", "")
            snippet = item.get("content", item.get("snippet", ""))
            if title:
                text_parts.append(f"Başlıq: {title}")
            if snippet:
                text_parts.append(f"Məzmun: {snippet}")
            text_parts.append("---")
    
    # Serper formatı
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

# ========== GROQ JSON PARSE (MÖHKƏM) ==========
def safe_json_parse(text: str) -> Dict:
    """
    Groq-dan gələn mətni JSON-a çevirir.
    Bir çox səhv formatları idarə edir.
    """
    import re
    
    # 1. Markdown bloklarını təmizlə
    json_pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
    match = re.search(json_pattern, text, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        # 2. Ən böyük {} strukturunu tap
        brace_pattern = r"(\{.*\})"
        match = re.search(brace_pattern, text, re.DOTALL)
        if match:
            json_str = match.group(1)
        else:
            json_str = text.strip()
    
    # 3. Trailing vergülləri təmizlə (JSON-da icazə verilmir)
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)
    
    # 4. Null dəyərləri düzəlt
    json_str = json_str.replace("null", "null")
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        # 5. Fallback: regex ilə ən vacib sahələri çıxar
        print(f"JSON parse xətası: {e}. Fallback edilir...")
        fallback = {
            "referee": {"status": "tapılmadı", "confidence": 0.0},
            "coach": {"status": "tapılmadı", "confidence": 0.0},
            "injuries": {"status": "tapılmadı", "confidence": 0.0},
            "lineup": {"status": "tapılmadı", "confidence": 0.0},
            "stadium": {"status": "tapılmadı", "confidence": 0.0},
            "weather": {"status": "tapılmadı", "confidence": 0.0},
            "motivation": {"status": "tapılmadı", "confidence": 0.0},
            "fatigue": {"status": "tapılmadı", "confidence": 0.0}
        }
        # Regex ilə bəzi məlumatları çıxarmağa cəhd
        referee_match = re.search(r'"referee"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)"', text)
        if referee_match:
            fallback["referee"]["name"] = referee_match.group(1)
            fallback["referee"]["status"] = "təxmin"
            fallback["referee"]["confidence"] = 0.5
        return fallback

# ========== GROQ ANALİZİ (TIMEOUT İDARƏSİ) ==========
def analyze_with_groq(team1: str, team2: str, search_text: str) -> Dict:
    """
    Groq Llama istifadə edərək axtarış nəticələrini təhlil edir və JSON formatında qaytarır.
    """
    if not GROQ_KEY_M2:
        raise ValueError("GROQ_KEY_M2 environment-da tapılmadı. Zəhmət olmasa .env faylını yoxlayın.")
    
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
        "home_expected": "4-3-3 kimi format",
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
}

Mümkün qədər dəqiq ol. Əgər məlumat yoxdursa, "tapılmadı" statusu və confidence=0.0 qoy."""
    
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

# ========== ƏSAS run_m2 FUNKSİYASI ==========
def run_m2(parser_json: Dict) -> Dict:
    """
    M2 modulu: Parser JSON-dan komanda adlarını götürür, Tavily/Serper ilə axtarış edir,
    Groq ilə təhlil edir və nəticəni qaytarır.
    """
    team1 = parser_json.get("team1", "Unknown")
    team2 = parser_json.get("team2", "Unknown")
    
    # API key-lərin vəziyyətini yoxla
    keys = validate_api_keys()
    if not keys["groq"]:
        raise ValueError("GROQ_KEY_M2 tapılmadı. M2 işləyə bilməz.")
    if not keys["tavily"] and not keys["serper"]:
        raise ValueError("Nə TAVILY_KEY, nə SERPER_KEY tapılmadı. Axtarış mümkün deyil.")
    
    print(f"M2 başladı: {team1} vs {team2}")
    print(f"API vəziyyəti: Groq={keys['groq']}, Tavily={keys['tavily']}, Serper={keys['serper']}")
    
    # Axtarış üçün sorgular
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
        print("XƏBƏRDARLIQ: Heç bir axtarış nəticə verilmədi. M2 boş JSON qaytaracaq.")
        return {
            "referee": {"status": "tapılmadı", "confidence": 0.0},
            "coach": {"status": "tapılmadı", "confidence": 0.0},
            "injuries": {"status": "tapılmadı", "confidence": 0.0},
            "lineup": {"status": "tapılmadı", "confidence": 0.0},
            "stadium": {"status": "tapılmadı", "confidence": 0.0},
            "weather": {"status": "tapılmadı", "confidence": 0.0},
            "motivation": {"status": "tapılmadı", "confidence": 0.0},
            "fatigue": {"status": "tapılmadı", "confidence": 0.0},
            "m2_warning": "Heç bir axtarış nəticəsi tapılmadı. API açarlarını yoxlayın."
        }
    
    try:
        result = analyze_with_groq(team1, team2, all_search_text)
        # Məlumatların statusuna görə xəbərdarlıq əlavə et
        low_conf_count = 0
        for key, value in result.items():
            if isinstance(value, dict) and value.get("status") == "tapılmadı":
                low_conf_count += 1
        if low_conf_count > 4:
            result["m2_warning"] = f"{low_conf_count} kateqoriyada məlumat tapılmadı. Nəticələr məhduddur."
        return result
    except Exception as e:
        print(f"M2 Groq xətası: {e}")
        return {
            "referee": {"status": "tapılmadı", "confidence": 0.0},
            "coach": {"status": "tapılmadı", "confidence": 0.0},
            "injuries": {"status": "tapılmadı", "confidence": 0.0},
            "lineup": {"status": "tapılmadı", "confidence": 0.0},
            "stadium": {"status": "tapılmadı", "confidence": 0.0},
            "weather": {"status": "tapılmadı", "confidence": 0.0},
            "motivation": {"status": "tapılmadı", "confidence": 0.0},
            "fatigue": {"status": "tapılmadı", "confidence": 0.0},
            "m2_error": str(e)
        }

# ========== TEST BLOKU ==========
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