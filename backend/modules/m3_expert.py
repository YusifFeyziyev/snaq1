import json
import re
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import GROQ_KEY_M3, MODEL_M3
from groq import Groq

client = Groq(api_key=GROQ_KEY_M3)

M3_PROMPT = """
Sən futbol ekspert analiz agentisən.
Sənə parser JSON (xam statistika) və M2 nəticəsi (araşdırma) veriləcək.
M1 riyazi nəticələrini GÖRMƏYƏCƏKSƏN — öz ekspert analizini ver.

QAYDA — M2 məlumata güvən:
- confidence >= 0.7  → normal siqnal
- confidence 0.5-0.7 → zəif siqnal, əsas qərar statistikaya verilir
- confidence < 0.5   → bu məlumat nəzərə alınmır
- status = "tapılmadı" → həmin sahə analiz edilmir

TAKTİKİ DNA:
Tip 1 Bus-stop     → corner↓↓ qol↓↓ sot↓↓ | BTTS⛔ Over2.5⛔
Tip 2 Kilid+Kontra → corner↓  qol az-orta  | Ev SOT↑↑
Tip 3 Sahiblik     → corner↓↓ qol↓ sot↓
Tip 4 Tam hücum    → corner↑↑ qol↑↑ sot↑↑
Tip 5 Elastik      → statistikaya güvən
Tip 6 Pressing     → corner orta-↑ qol↑ sot↑

TAKTİKİ TOQQUŞMA:
- Tam hücum vs Bus-stop → tempo aşağı, qol az, Ev SOT↑
- Tam hücum vs Tam hücum → tempo yüksək, qol çox
- Kilid vs Bus-stop → ultra aşağı tempo, qol çox az
- Pressing vs Pressing → tempo yüksək, qol çox

MOTİVASİYA:
1-3 (Şampion) → MAKSİMUM
4-6 (Avropa)  → YÜKSƏK
7-14 (Orta)   → ORTA
15+ (Releqasiya) → MAKSİMUM
Heç nə oynamır → AŞAĞI

MENTAL ÇARPANLAR:
Ardıcıl 3+ uduzma    → -10 güvən
Ardıcıl 3+ qalibiyyət → +5 güvən
Derby/tarixi rəqabət  → Ev+10, Qonaq+5
Məşqçi böhranı        → -15 güvən

YORĞUNLUQ:
≤3 gün  → -15 güvən
4-5 gün → -7 güvən
6+ gün  → 0

HEYƏT TƏSİRİ:
Kritik hücumçu yox        → qol baza×0.87 | BTTS-15%
Kritik mərkəz müdafiə yox → rəqib qol×1.12
Qapıçı yox                → rəqib qol×1.18
4+ kritik oyunçu yox       → bütün bazarlar⛔

HAKİM ÇARPANI:
Sərt    → kart↑↑ faul toleransı↓
Orta    → normal
Mülayim → kart↓ faul toleransı↑
tapılmadı → hakim təsiri nəzərə alınmır

DAXILI ZİDDİYYƏT YOXLAMA:
□ Tempo → qol vəziyyəti ilə uyğun?
□ Qonaq strategiyası → məşqçi profili ilə uyğun?
□ Dominant tərəf → motivasiya+forma ilə uyğun?
Ziddiyyət varsa → yenidən cavabla

YALNIZ bu JSON formatında qaytar:
{
  "tempo": {"value": null, "confidence": 0.0, "source": null},
  "taktika_ev": {"value": null, "confidence": 0.0, "source": null},
  "taktika_qonaq": {"value": null, "confidence": 0.0, "source": null},
  "toqqusma_effekti": {"value": null, "confidence": 0.0, "source": null},
  "dominant_teref": {"value": null, "confidence": 0.0, "source": null},
  "qol_veziyyeti": {"value": null, "confidence": 0.0, "source": null},
  "motivasiya_ev": {"value": null, "confidence": 0.0, "source": null},
  "motivasiya_qonaq": {"value": null, "confidence": 0.0, "source": null},
  "yorgunluq_ev": {"value": null, "confidence": 0.0, "source": null},
  "yorgunluq_qonaq": {"value": null, "confidence": 0.0, "source": null},
  "heyat_tesiri_ev": {"value": null, "confidence": 0.0, "source": null},
  "heyat_tesiri_qonaq": {"value": null, "confidence": 0.0, "source": null},
  "hakim_tesiri": {"value": null, "confidence": 0.0, "source": null},
  "oyun_oxunusu": {"value": null, "confidence": 0.0, "source": null},
  "kahin_cumlesi": {"value": null, "confidence": 0.0, "source": null},
  "flags": {
    "bus_stop": false,
    "rotasiya": false,
    "kritik_itki": false,
    "kritik_itki_sayi": 0,
    "yorgunluk_aktiv": false,
    "ziddiyyet": false
  },
  "carpanlar": {
    "ev_hucum": 1.0,
    "qonaq_hucum": 1.0,
    "ev_mudafie": 1.0,
    "qonaq_mudafie": 1.0,
    "sot_carpan": 1.0,
    "corner_carpan": 1.0
  },
  "m3_guveni": 0.0
}
"""

def hesabla_m3_guveni(m3_data: dict) -> float:
    if not m3_data:
        return 0.0

    # M2 məlumat dolğunluğu (0-3)
    vacib_saheler = ["tempo", "taktika_ev", "taktika_qonaq", "hakim_tesiri"]
    dolu = sum(
        1 for s in vacib_saheler
        if m3_data.get(s, {}).get("value") is not None
    )
    dolgunluk = dolu * 0.75

    # Siqnal uyğunluğu (0-4)
    conf_list = [
        m3_data.get(s, {}).get("confidence", 0.0)
        for s in ["tempo", "taktika_ev", "taktika_qonaq",
                  "dominant_teref", "qol_veziyyeti", "oyun_oxunusu"]
    ]
    ort_conf = sum(conf_list) / len(conf_list) if conf_list else 0
    signal_bal = ort_conf * 4

    # Ziddiyyətsizlik (0-3)
    ziddiyyet = m3_data.get("flags", {}).get("ziddiyyet", False)
    zid_bal = 1.5 if not ziddiyyet else 0.0

    total = round(min(10.0, dolgunluk + signal_bal + zid_bal), 2)
    return total


def run_m3(parser_json: dict, m2_data: dict) -> dict:
    ev_ad  = parser_json.get("ev", {}).get("ad", "Ev")
    qon_ad = parser_json.get("qonaq", {}).get("ad", "Qonaq")

    user_content = f"""
Ev komandası: {ev_ad}
Qonaq komandası: {qon_ad}

PARSER JSON (xam statistika):
{json.dumps(parser_json, ensure_ascii=False, indent=2)}

M2 NƏTİCƏSİ (araşdırma):
{json.dumps(m2_data, ensure_ascii=False, indent=2)}

Yuxarıdakı məlumatlara əsasən ekspert analizini JSON formatında ver.
"""

    try:
        response = client.chat.completions.create(
            model=MODEL_M3,
            messages=[
                {"role": "system", "content": M3_PROMPT},
                {"role": "user", "content": user_content}
            ],
            temperature=0.2,
            max_tokens=3000
        )

        content = response.choices[0].message.content.strip()
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if not json_match:
            return {"success": False, "error": "JSON tapılmadı"}

        m3_data = json.loads(json_match.group())
        guveni = hesabla_m3_guveni(m3_data)
        m3_data["m3_guveni"] = guveni

        return {"success": True, "data": m3_data, "guveni": guveni}

    except Exception as e:
        return {"success": False, "error": str(e)}
    
    

