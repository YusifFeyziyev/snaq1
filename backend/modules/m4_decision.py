import json
import re
import os
import sys

# config.py faylını oxumaq üçün ana qovluğu path-ə əlavə edirik
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import GROQ_KEY_M4, MODEL_M4
from groq import Groq

client = Groq(api_key=GROQ_KEY_M4)

M4_PROMPT = """
Sən futbol qərar agentisən. Yalnız strukturlu JSON alırsan, yalnız JSON qaytarırsan.
QƏTİ XƏBƏRDARLIQ: Qətiyyən markdown (```json və s.) istifadə etmə. Fikirlərini <think> blokunda yaz, amma yekunda BİRBAŞA { ilə başlayan JSON obyekti qaytar.

YALNIZ bu JSON formatında qaytar — heç bir izah yazma:
{
  "sistem_guveni": 0.0,
  "qerar_guveni": 0.0,
  "penaltyler": [],
  "final_guveni": 0.0,
  "oynarim": true,
  "umumi_sebeb": "...",
  "bazarlar": { ... },
  "top_tovsiyeler": [
    {"ad": "Over 2.5", "ehtimal": 85, "sebeb": "...", "qerar": "✅✅ Çox güvənli"}
  ]
}
"""

def hazirla_m4_input(m1: dict, m2: dict, m3: dict) -> dict:
    m1 = m1 or {}
    m2 = m2 or {}
    m3 = m3 or {}

    qol_bazarlari = m1.get("qol_bazarlari") or {}
    qol_bazasi = m1.get("qol_bazasi") or {}
    corner = m1.get("corner") or {}
    kart = m1.get("kart") or {}
    faul = m1.get("faul") or {}
    ht = qol_bazarlari.get("ht") or {}
    guveni_m1 = (m1.get("guveni") or {}).get("total", 0)

    m3_data = m3.get("data") if isinstance(m3, dict) and "data" in m3 else m3
    m3_data = m3_data or {}
    flags = m3_data.get("flags") or {}
    guveni_m3 = m3_data.get("m3_guveni", 0)

    m2_data = m2.get("data") if isinstance(m2, dict) and "data" in m2 else m2
    m2_data = m2_data or {}
    guveni_m2 = m2.get("guveni", 0) if isinstance(m2, dict) else 0

    return {
        "M1": {
            "over15": qol_bazarlari.get("over15"),
            "over25": qol_bazarlari.get("over25"),
            "over35": qol_bazarlari.get("over35"),
            "btts": qol_bazarlari.get("btts"),
            "p1": qol_bazarlari.get("p1"),
            "px": qol_bazarlari.get("px"),
            "p2": qol_bazarlari.get("p2"),
            "guveni": guveni_m1
        },
        "M3": {
            "tempo": m3_data.get("tempo"),
            "guveni": guveni_m3
        },
        "M2": {
            "rotasiya": flags.get("rotasiya", False),
            "guveni": guveni_m2
        },
        "flags": flags
    }

def run_m4(m1: dict, m2: dict, m3: dict, parser_json: dict=None) -> dict:
    m4_input = hazirla_m4_input(m1, m2, m3)

    try:
        response = client.chat.completions.create(
            model=MODEL_M4,
            messages=[
                {"role": "system", "content": M4_PROMPT},
                {"role": "user", "content": json.dumps(m4_input, ensure_ascii=False)}
            ],
            temperature=0.1,
            max_tokens=4000
        )

        content = response.choices[0].message.content.strip()
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
        content = content.replace("```json", "").replace("```", "").strip()

        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if not json_match:
            return {"success": False, "error": "JSON tapılmadı", "raw": content}

        m4_data = json.loads(json_match.group())

        # ── DÜZƏLİŞ: JS-İN BAŞA DÜŞMƏSİ ÜÇÜN ADLARI SABİTLƏYİRİK ──
        # 1. Sistem Güvəni
        if "sistem_guveni" not in m4_data:
            m4_data["sistem_guveni"] = m4_data.get("final_guveni") or m4_data.get("final_score") or 0.0
        
        # 2. Qərar Güvəni
        if "qerar_guveni" not in m4_data:
            m4_data["qerar_guveni"] = m4_data.get("confidence") or m4_data.get("analiz_guveni") or 0.0

        # 3. Oynarim/Oynayarim
        if "oynarim" not in m4_data:
            m4_data["oynarim"] = m4_data.get("oynayiram") or m4_data.get("play") or False

        # 4. Top Tövsiyələr (Ad xətası düzəlişi)
        if "top_tovsiyeler" not in m4_data and "top_tavsiyeler" in m4_data:
            m4_data["top_tovsiyeler"] = m4_data["top_tavsiyeler"]

        # 5. Sebeb
        if "sebeb" not in m4_data:
            m4_data["sebeb"] = m4_data.get("umumi_sebeb") or m4_data.get("summary") or ""

        return {"success": True, "data": m4_data}

    except Exception as e:
        return {"success": False, "error": str(e)}