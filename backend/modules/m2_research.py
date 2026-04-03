import os
import re
import json
import time
import requests
from typing import Dict, Any, List, Optional

try:
    from config import GROQ_KEY_M2, MODEL_M2, TAVILY_KEY, SERPER_KEY
except ImportError:
    GROQ_KEY_M2 = os.getenv("GROQ_KEY_M2")
    MODEL_M2    = os.getenv("MODEL_M2", "llama-3.3-70b-versatile")
    TAVILY_KEY  = os.getenv("TAVILY_KEY")
    SERPER_KEY  = os.getenv("SERPER_KEY")

GROQ_API_URL   = "https://api.groq.com/openai/v1/chat/completions"
TAVILY_API_URL = "https://api.tavily.com/search"
SERPER_API_URL = "https://google.serper.dev/search"

# ──────────────────────────────────────────
# API YOXLAMA
# ──────────────────────────────────────────

def validate_api_keys() -> Dict[str, bool]:
    return {
        "groq":   bool(GROQ_KEY_M2),
        "tavily": bool(TAVILY_KEY),
        "serper": bool(SERPER_KEY)
    }

# ──────────────────────────────────────────
# AXTARIŞ FUNKSİYALARI
# ──────────────────────────────────────────

def search_with_tavily(query: str, retries: int = 2) -> Optional[Dict]:
    if not TAVILY_KEY:
        return None
    for attempt in range(retries):
        try:
            resp = requests.post(
                TAVILY_API_URL,
                headers={"Authorization": f"Bearer {TAVILY_KEY}", "Content-Type": "application/json"},
                json={"query": query, "search_depth": "advanced", "max_results": 6},
                timeout=25
            )
            if resp.status_code == 200:
                return resp.json()
            print(f"Tavily status {resp.status_code}: {query}")
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
            resp = requests.post(
                SERPER_API_URL,
                headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"},
                json={"q": query, "num": 6},
                timeout=25
            )
            if resp.status_code == 200:
                return resp.json()
            print(f"Serper status {resp.status_code}: {query}")
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

# ──────────────────────────────────────────
# JSON PARSE (DÜZƏLİŞ: indent bug aradan qaldırıldı)
# ──────────────────────────────────────────

def safe_json_parse(text: str) -> Dict:
    # Kod bloku içindəki JSON-u çəkməyə cəhd et
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        json_str = match.group(1) if match else text.strip()

    # Artıq vergülləri təmizlə
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"JSON parse xətası: {e}. Fallback istifadə edilir...")
        fallback = _empty_sections()
        # Regex ilə hakim adını xilas etməyə cəhd et
        ref_match = re.search(r'"referee"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)"', text)
        if ref_match:
            fallback["referee"]["name"]       = ref_match.group(1)
            fallback["referee"]["status"]     = "real"
            fallback["referee"]["confidence"] = 0.7
        return fallback

# ──────────────────────────────────────────
# KÖMƏKÇİ FUNKSİYALAR
# ──────────────────────────────────────────

def _empty_sections() -> Dict:
    """Sadəcə 8 kateqoriyanın boş strukturu (m2_guveni daxil deyil)."""
    return {
        "referee":    {"status": "tapılmadı", "confidence": 0.0},
        "coach":      {"status": "tapılmadı", "confidence": 0.0},
        "injuries":   {"status": "tapılmadı", "confidence": 0.0},
        "lineup":     {"status": "tapılmadı", "confidence": 0.0},
        "stadium":    {"status": "tapılmadı", "confidence": 0.0},
        "weather":    {"status": "tapılmadı", "confidence": 0.0},
        "motivation": {"status": "tapılmadı", "confidence": 0.0},
        "fatigue":    {"status": "tapılmadı", "confidence": 0.0}
    }

def _empty_result(warning: str = None, error: str = None) -> Dict:
    result = _empty_sections()
    result["m2_guveni"] = 0.0
    if warning: result["m2_warning"] = warning
    if error:   result["m2_error"]   = error
    return result

def calculate_m2_guveni(result: Dict) -> float:
    """Bütün kateqoriyaların confidence ortalaması → 0-10 şkala."""
    confs = [
        float(v["confidence"])
        for k, v in result.items()
        if isinstance(v, dict) and isinstance(v.get("confidence"), (int, float))
    ]
    return round((sum(confs) / len(confs)) * 10, 1) if confs else 0.0

def _post_process(result: Dict) -> Dict:
    """
    Axtarış mətnindən gəlməyən (status='təxmin') məlumatlarda
    confidence-i 0.3-ə endiririk ki real datanı seçsin M4.
    """
    for key, val in result.items():
        if not isinstance(val, dict):
            continue
        status = val.get("status", "tapılmadı")
        conf   = float(val.get("confidence", 0.0))
        if status == "təxmin" and conf > 0.4:
            val["confidence"] = 0.35   # süni artırılmış güvəni kəs
        if status == "tapılmadı":
            val["confidence"] = 0.0
    return result

# ──────────────────────────────────────────
# GROQ ANALİZİ
# ──────────────────────────────────────────

SYSTEM_PROMPT = """Sən futbol məlumat analitikisən. Sənə axtarış nəticələri verilir.
QAYDALAR (MÜTLƏQ):
1. Yalnız axtarış nəticələrindəki REAL məlumatlara əsaslan.
2. Axtarış nəticəsində tapılmayan məlumat üçün status="tapılmadı", confidence=0.0 qaytar.
3. ƏSLA uydurmaq, ehtimal etmək, ya da bil ki-dən istifadə etmə.
4. Məlumat tapılıbsa status="real", confidence=0.7-0.95 qaytar.
5. Məlumat qeyri-müəyyəndirsə status="tapılmadı", confidence=0.0 qaytar — status="təxmin" istifadə etmə.
6. Yalnız aşağıdakı JSON strukturunu qaytar, heç bir əlavə mətn yazma.

{
    "referee": {
        "name": "string or null",
        "yellow_avg": float or null,
        "red_avg": float or null,
        "foul_sensitivity": "yüksək/orta/aşağı or null",
        "status": "real/tapılmadı",
        "confidence": float
    },
    "coach": {
        "home_coach": "string or null",
        "away_coach": "string or null",
        "home_tactical_trend": "string or null",
        "away_tactical_trend": "string or null",
        "status": "real/tapılmadı",
        "confidence": float
    },
    "injuries": {
        "home_absent": [],
        "away_absent": [],
        "home_doubtful": [],
        "away_doubtful": [],
        "key_players_missing": [],
        "status": "real/tapılmadı",
        "confidence": float
    },
    "lineup": {
        "home_expected": "string or null",
        "away_expected": "string or null",
        "home_rotation": "aşağı/orta/yüksək or null",
        "away_rotation": "aşağı/orta/yüksək or null",
        "status": "real/tapılmadı",
        "confidence": float
    },
    "stadium": {
        "name": "string or null",
        "capacity": int or null,
        "home_advantage": "güclü/orta/zəif or null",
        "status": "real/tapılmadı",
        "confidence": float
    },
    "weather": {
        "temperature": int or null,
        "condition": "string or null",
        "wind": "string or null",
        "impact": "aşağı/orta/yüksək or null",
        "status": "real/tapılmadı",
        "confidence": float
    },
    "motivation": {
        "home_motivation": "yüksək/orta/aşağı or null",
        "away_motivation": "yüksək/orta/aşağı or null",
        "reason": "string or null",
        "status": "real/tapılmadı",
        "confidence": float
    },
    "fatigue": {
        "home_fatigue": "aşağı/orta/yüksək or null",
        "away_fatigue": "aşağı/orta/yüksək or null",
        "days_since_last_match_home": int or null,
        "days_since_last_match_away": int or null,
        "status": "real/tapılmadı",
        "confidence": float
    }
}"""

def analyze_with_groq(team1: str, team2: str, search_text: str) -> Dict:
    if not GROQ_KEY_M2:
        raise ValueError("GROQ_KEY_M2 environment-da tapılmadı.")

    user_prompt = (
        f"Komandalar: {team1} vs {team2}\n\n"
        f"Axtarış nəticələri:\n{search_text[:7000]}\n\n"
        "Yuxarıdakı axtarış nəticələrindən tapılan REAL məlumatları JSON strukturuna daxil et. "
        "Tapılmayan məlumatlar üçün mütləq status=tapılmadı, confidence=0.0 istifadə et."
    )

    headers = {
        "Authorization": f"Bearer {GROQ_KEY_M2}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_M2,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt}
        ],
        "temperature": 0.0,   # deterministik — hallusinasiya azalır
        "max_tokens": 2500
    }

    try:
        resp = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return safe_json_parse(content)
    except requests.exceptions.Timeout:
        raise Exception("Groq API timeout (60 saniyə).")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Groq API xətası: {str(e)}")
    except Exception as e:
        raise Exception(f"Gözlənilməz xəta: {str(e)}")

# ──────────────────────────────────────────
# ƏSAS run_m2 FUNKSİYASI
# ──────────────────────────────────────────

def run_m2(parser_json: Dict) -> Dict:
    team1 = parser_json.get("team1", "Unknown")
    team2 = parser_json.get("team2", "Unknown")

    keys = validate_api_keys()
    if not keys["groq"]:
        return _empty_result(error="GROQ_KEY_M2 tapılmadı.")
    if not keys["tavily"] and not keys["serper"]:
        return _empty_result(error="Nə TAVILY_KEY, nə SERPER_KEY tapılmadı.")

    print(f"M2 başladı: {team1} vs {team2}")
    print(f"API vəziyyəti: Groq={keys['groq']}, Tavily={keys['tavily']}, Serper={keys['serper']}")

    # Daha hədəflənmiş axtarış sorğuları — real data almaq üçün
    queries = [
        f"{team1} {team2} referee 2024 2025",
        f"{team1} {team2} injury report missing players",
        f"{team1} {team2} predicted lineup formation",
        f"{team1} {team2} preview head to head",
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
        print("XƏBƏRDARLIQ: Heç bir axtarış nəticəsi tapılmadı.")
        return _empty_result(warning="Heç bir axtarış nəticəsi tapılmadı.")

    try:
        result = analyze_with_groq(team1, team2, all_search_text)

        # Süni güvənləri aşağı çək
        result = _post_process(result)

        # m2_guveni hesabla
        result["m2_guveni"] = calculate_m2_guveni(result)
        print(f"M2 ortalama güvən: {result['m2_guveni'] / 10:.2f}, valid: True")

        # Neçə kateqoriyada real məlumat var?
        real_count = sum(
            1 for k, v in result.items()
            if isinstance(v, dict) and v.get("status") == "real"
        )
        missing_count = sum(
            1 for k, v in result.items()
            if isinstance(v, dict) and v.get("status") == "tapılmadı"
        )
        print(f"Real: {real_count} kateqoriya | Tapılmadı: {missing_count} kateqoriya")
        if missing_count > 4:
            result["m2_warning"] = (
                f"{missing_count} kateqoriyada real məlumat tapılmadı. "
                "Axtarış nəticələri kifayət deyildi."
            )

        return result

    except Exception as e:
        print(f"M2 Groq xətası: {e}")
        return _empty_result(error=str(e))


# ──────────────────────────────────────────
# TEST
# ──────────────────────────────────────────
if __name__ == "__main__":
    test = {"team1": "Liverpool", "team2": "Manchester City"}
    try:
        result = run_m2(test)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print("Test xətası:", e)