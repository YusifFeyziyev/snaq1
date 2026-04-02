import os
import json
import re
import time
import requests
from typing import Dict, Any, Optional, List

# Config-dən açarları və model adını götür
try:
    from config import GROQ_KEY_M3, MODEL_M3
except ImportError:
    GROQ_KEY_M3 = os.getenv("GROQ_KEY_M3")
    MODEL_M3 = os.getenv("MODEL_M3", "llama-3.3-70b-versatile")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# ========== API KEY YOXLANMASI ==========
def validate_api_keys() -> Dict[str, bool]:
    """API açarlarının vəziyyətini yoxlayır."""
    return {"groq": bool(GROQ_KEY_M3)}

# ========== M2 GÜVƏN HESABLAMASI (RECURSIVE) ==========
def extract_all_confidences(obj: Any, depth: int = 0) -> List[float]:
    """
    M2 JSON obyektindən bütün 'confidence' dəyərlərini rekursiv olaraq yığır.
    """
    confidences = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "confidence" and isinstance(value, (int, float)):
                confidences.append(float(value))
            else:
                confidences.extend(extract_all_confidences(value, depth + 1))
    elif isinstance(obj, list):
        for item in obj:
            confidences.extend(extract_all_confidences(item, depth + 1))
    return confidences

def calculate_m2_confidence(m2_data: Dict) -> float:
    """
    M2 məlumatlarının ortalama güvən səviyyəsini hesablayır.
    Heç bir confidence tapılmazsa 0.0 qaytarır.
    """
    if not isinstance(m2_data, dict):
        return 0.0
    confs = extract_all_confidences(m2_data)
    if not confs:
        return 0.0
    return sum(confs) / len(confs)

# ========== M2 DATA KEYFİYYƏT YOXLANMASI ==========
def is_m2_data_valid(m2_data: Dict) -> bool:
    """
    M2 məlumatlarının analiz üçün kifayət edib-etmədiyini yoxlayır.
    """
    if not isinstance(m2_data, dict):
        return False
    # Əgər M2-də xəta və ya xəbərdarlıq varsa
    if m2_data.get("m2_error") or m2_data.get("m2_warning"):
        # Yenə də cəhd edək, amma confidence aşağı olacaq
        pass
    # Ən azı bir məlumat kateqoriyasında real məlumat olmalıdır
    real_count = 0
    for key, value in m2_data.items():
        if isinstance(value, dict) and value.get("status") == "real":
            real_count += 1
    # Heç bir real məlumat yoxdursa, valid deyil
    return real_count >= 1

# ========== M2 DATA SIXMA (TOKEN QORUMASI) ==========
def smart_truncate_m2_data(m2_data: Dict, max_length: int = 3000) -> str:
    """
    M2 məlumatlarını ağıllı şəkildə qısaldır.
    - Ən vacib sahələri (referee, injuries, motivation, fatigue) saxla.
    - Qalanları at.
    """
    if not isinstance(m2_data, dict):
        return "{}"
    
    priority_keys = ["referee", "injuries", "motivation", "fatigue", "coach", "lineup"]
    filtered = {}
    for key in priority_keys:
        if key in m2_data:
            filtered[key] = m2_data[key]
    
    # Hələ də uzundursa, hər birini qısalt
    json_str = json.dumps(filtered, ensure_ascii=False)
    if len(json_str) > max_length:
        # Hər bir dəyəri sadələşdir
        simplified = {}
        for key, value in filtered.items():
            if isinstance(value, dict):
                # Yalnız status, confidence və ən vacib 2-3 açarı saxla
                simple_value = {}
                for subkey in ["status", "confidence", "name", "home_motivation", "away_motivation", "home_absent", "away_absent"]:
                    if subkey in value:
                        simple_value[subkey] = value[subkey]
                simplified[key] = simple_value
            else:
                simplified[key] = value
        json_str = json.dumps(simplified, ensure_ascii=False)
        if len(json_str) > max_length:
            # Son çarə: yalnız status və confidence
            json_str = json.dumps({k: {sk: v.get(sk) for sk in ["status", "confidence"] if isinstance(v, dict)} for k, v in filtered.items()}, ensure_ascii=False)
    return json_str

# ========== JSON PARSE (MÖHKƏM + STRUKTUR YOXLAMASI) ==========
def safe_json_parse(text: str) -> Dict:
    """
    Groq-dan gələn mətni JSON-a çevirir.
    Struktur yoxlaması əlavə edilib.
    """
    # 1. Markdown bloklarını təmizlə
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
    
    # 2. Trailing vergülləri təmizlə
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)
    
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"M3 JSON parse xətası: {e}. Fallback edilir...")
        return get_default_m3_result(error=f"JSON parse error: {str(e)[:100]}")
    
    # 3. Struktur yoxlaması (tələb olunan sahələr)
    required_top_keys = ["tempo", "taktika_ev", "taktika_qonaq", "carpanlar", "m3_guveni"]
    for key in required_top_keys:
        if key not in parsed:
            print(f"XƏBƏRDARLIQ: M3 nəticəsində '{key}' yoxdur. Default əlavə edilir.")
            if key == "tempo":
                parsed["tempo"] = "orta"
            elif key == "taktika_ev":
                parsed["taktika_ev"] = "balanslı"
            elif key == "taktika_qonaq":
                parsed["taktika_qonaq"] = "balanslı"
            elif key == "carpanlar":
                parsed["carpanlar"] = {
                    "motivasiya_ev": 1.0, "motivasiya_qonaq": 1.0,
                    "yorğunluq_ev": 1.0, "yorğunluq_qonaq": 1.0,
                    "hakim_təsiri": 1.0, "heyət_dərinliyi_ev": 1.0,
                    "heyət_dərinliyi_qonaq": 1.0, "psixoloji_ustunluk": 1.0
                }
            elif key == "m3_guveni":
                parsed["m3_guveni"] = 0.5
    
    # 4. carpanlar daxilində tələb olunan sahələr
    default_carpanlar = {
        "motivasiya_ev": 1.0, "motivasiya_qonaq": 1.0,
        "yorğunluq_ev": 1.0, "yorğunluq_qonaq": 1.0,
        "hakim_təsiri": 1.0, "heyət_dərinliyi_ev": 1.0,
        "heyət_dərinliyi_qonaq": 1.0, "psixoloji_ustunluk": 1.0
    }
    if "carpanlar" in parsed and isinstance(parsed["carpanlar"], dict):
        for k, v in default_carpanlar.items():
            if k not in parsed["carpanlar"]:
                parsed["carpanlar"][k] = v
    else:
        parsed["carpanlar"] = default_carpanlar
    
    # 5. Flags və critical_factors array olmalıdır
    if "flags" not in parsed or not isinstance(parsed["flags"], list):
        parsed["flags"] = []
    if "critical_factors" not in parsed or not isinstance(parsed["critical_factors"], list):
        parsed["critical_factors"] = []
    if "toqquşma_matrisi" not in parsed:
        parsed["toqquşma_matrisi"] = {
            "ev_hucum_qonaq_mudafiə": "balanslı",
            "qonaq_hucum_ev_mudafiə": "balanslı"
        }
    
    return parsed

def get_default_m3_result(error: str = None) -> Dict:
    """Default M3 nəticəsi (fallback)"""
    return {
        "tempo": "orta",
        "taktika_ev": "balanslı",
        "taktika_qonaq": "balanslı",
        "flags": [],
        "carpanlar": {
            "motivasiya_ev": 1.0, "motivasiya_qonaq": 1.0,
            "yorğunluq_ev": 1.0, "yorğunluq_qonaq": 1.0,
            "hakim_təsiri": 1.0, "heyət_dərinliyi_ev": 1.0,
            "heyət_dərinliyi_qonaq": 1.0, "psixoloji_ustunluk": 1.0
        },
        "m3_guveni": 0.3,
        "toqquşma_matrisi": {
            "ev_hucum_qonaq_mudafiə": "balanslı",
            "qonaq_hucum_ev_mudafiə": "balanslı"
        },
        "critical_factors": [],
        "m3_error": error or "Default fallback"
    }

# ========== GROQ ANALİZİ (YALNIZ M2 VALID OLDUQDA) ==========
def analyze_with_groq(team1: str, team2: str, parser_json: Dict, m2_data: Dict) -> Dict:
    """
    Groq Llama istifadə edərək taktiki təhlil edir.
    """
    if not GROQ_KEY_M3:
        raise ValueError("GROQ_KEY_M3 tapılmadı.")
    
    team1_stats = parser_json.get("team1_stats", {})
    team2_stats = parser_json.get("team2_stats", {})
    
    # M2 məlumatlarını ağıllı şəkildə qısalt
    m2_text = smart_truncate_m2_data(m2_data, max_length=3000)
    
    system_prompt = """Sən futbol taktiki analitikisən. Verilən statistik məlumatlar və araşdırma nəticələrinə əsasən aşağıdakı JSON strukturunu doldur. Heç bir əlavə izah yazma, yalnız JSON.

{
    "tempo": "yüksək/orta/aşağı",
    "taktika_ev": "müdafiə/balanslı/hücum",
    "taktika_qonaq": "müdafiə/balanslı/hücum",
    "flags": ["flag1", "flag2"],
    "carpanlar": {
        "motivasiya_ev": 0.8-1.2,
        "motivasiya_qonaq": 0.8-1.2,
        "yorğunluq_ev": 0.8-1.2,
        "yorğunluq_qonaq": 0.8-1.2,
        "hakim_təsiri": 0.9-1.1,
        "heyət_dərinliyi_ev": 0.8-1.2,
        "heyət_dərinliyi_qonaq": 0.8-1.2,
        "psixoloji_ustunluk": 0.9-1.1
    },
    "m3_guveni": 0-1,
    "toqquşma_matrisi": {
        "ev_hucum_qonaq_mudafiə": "çox_üstün/üstün/balanslı/zəif/çox_zəif",
        "qonaq_hucum_ev_mudafiə": "çox_üstün/üstün/balanslı/zəif/çox_zəif"
    },
    "critical_factors": ["faktor1", "faktor2"]
}

Məlumatların keyfiyyətinə görə m3_guveni təyin et."""
    
    user_prompt = f"""Komandalar: {team1} (ev) vs {team2} (qonaq)

STATİSTİKA:
Ev hücum gücü: {team1_stats.get('attack_strength', 1.0)}, müdafiə: {team1_stats.get('defense_strength', 1.0)}
Qonaq hücum gücü: {team2_stats.get('attack_strength', 1.0)}, müdafiə: {team2_stats.get('defense_strength', 1.0)}
Ev qol ortalaması: {team1_stats.get('avg_goals_scored', 1.5)} / buraxdığı: {team1_stats.get('avg_goals_conceded', 1.2)}
Qonaq qol ortalaması: {team2_stats.get('avg_goals_scored', 1.5)} / buraxdığı: {team2_stats.get('avg_goals_conceded', 1.2)}

ARAŞDIRMA NƏTİCƏLƏRİ (M2):
{m2_text}

Yuxarıdakı JSON strukturuna uyğun təhlil et."""
    
    headers = {
        "Authorization": f"Bearer {GROQ_KEY_M3}",
        "Content-Type": "application/json"
    }
    
    # Token limiti təhlükəsiz etmək üçün prompt uzunluğunu yoxla
    estimated_tokens = (len(system_prompt) + len(user_prompt)) // 4
    max_tokens_val = 4000 if estimated_tokens < 3500 else 3000
    
    payload = {
        "model": MODEL_M3,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.3,
        "max_tokens": max_tokens_val
    }
    
    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=75)
        response.raise_for_status()
        data = response.json()
        assistant_message = data["choices"][0]["message"]["content"]
        return safe_json_parse(assistant_message)
    except Exception as e:
        raise Exception(f"Groq xətası: {str(e)}")

# ========== ƏSAS run_m3 FUNKSİYASI ==========
def run_m3(parser_json: Dict, m2_data: Dict) -> Dict:
    """
    M3 modulu: Parser JSON və M2 nəticəsini alır, taktiki təhlil edir.
    M2 keyfiyyətsizdirsə, Groq çağırılmır, yalnız statistik əsaslı default qaytarılır.
    """
    team1 = parser_json.get("team1", "Unknown")
    team2 = parser_json.get("team2", "Unknown")
    
    keys = validate_api_keys()
    if not keys["groq"]:
        raise ValueError("GROQ_KEY_M3 tapılmadı.")
    
    print(f"M3 başladı: {team1} vs {team2}")
    
    # M2 keyfiyyətini yoxla
    m2_conf = calculate_m2_confidence(m2_data)
    m2_valid = is_m2_data_valid(m2_data)
    print(f"M2 ortalama güvən: {m2_conf:.2f}, valid: {m2_valid}")
    
    # Əgər M2 çox zəifdirsə, Groq-u çağırma
    if not m2_valid or m2_conf < 0.2:
        print("M2 məlumatları çox zəifdir. Groq çağırılmır, statistik default istifadə olunur.")
        result = get_default_m3_result(error="M2 data insufficient")
        result["m3_guveni"] = min(0.4, m2_conf + 0.1)
        result["m3_warning"] = "M2 məlumatları yetərsiz olduğu üçün analiz statistikaya əsaslanır."
        return result
    
    try:
        result = analyze_with_groq(team1, team2, parser_json, m2_data)
        
        # M2 güvəninə görə M3 güvənini tənzimlə
        base_conf = result.get("m3_guveni", 0.5)
        adjusted_conf = base_conf * (0.6 + 0.4 * m2_conf)  # M2 yaxşıdırsa, M3 də yaxşı
        result["m3_guveni"] = round(min(0.95, adjusted_conf), 3)
        
        # Critical factors boşdursa, əlavə et
        if not result.get("critical_factors"):
            result["critical_factors"] = ["M3 analizi tamamlandı, lakin kritik faktor göstərilməyib"]
        
        return result
    except Exception as e:
        print(f"M3 xətası: {e}")
        fallback = get_default_m3_result(error=str(e))
        fallback["m3_guveni"] = 0.25
        return fallback

# ========== TEST BLOKU ==========
if __name__ == "__main__":
    test_parser_json = {
        "team1": "Liverpool",
        "team2": "Manchester City",
        "team1_stats": {
            "attack_strength": 1.35,
            "defense_strength": 0.85,
            "avg_goals_scored": 2.4,
            "avg_goals_conceded": 0.9
        },
        "team2_stats": {
            "attack_strength": 1.45,
            "defense_strength": 0.75,
            "avg_goals_scored": 2.6,
            "avg_goals_conceded": 0.8
        }
    }
    test_m2_data = {
        "referee": {"name": "Michael Oliver", "status": "real", "confidence": 0.8},
        "injuries": {"home_absent": ["Alisson"], "away_absent": [], "status": "real", "confidence": 0.9},
        "motivation": {"home_motivation": "yüksək", "away_motivation": "yüksək", "status": "real", "confidence": 0.7}
    }
    try:
        result = run_m3(test_parser_json, test_m2_data)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print("Test xətası:", e)