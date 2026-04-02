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

ÇƏKİ SİSTEMİ:
M1 → 0.50 (riyazi, ən etibarlı)
M3 → 0.30 (ekspert)
M2 → 0.20 (araşdırma)

VOTİNG:
M1 over25 >= 0.65 + M3 tempo "yüksək" → over25 +10%
M1 over25 >= 0.65 + M3 tempo "aşağı"  → confidence -15%
M1 btts >= 0.60 + M3 "hücum oyunu"    → btts +8%

CONFLICT DETECTION:
M1 over yüksək + M3 aşağı tempo → -15% confidence
M1 btts yüksək + M3 bus-stop   → BTTS ⛔
M1 corner yüksək + M3 kilid    → -10% confidence
M2 confidence < 0.5            → M2 təsiri sıfırlanır

PENALTY SİSTEMİ:
M2 guveni < 7.0  → -10%
M3 guveni < 6.5  → -10%
Ziddiyyət varsa  → -15%
Null data varsa  → həmin bazar -20%

HARD OVERRIDE:
bus_stop = true     → over25⛔ btts⛔ corner_ust⛔
rotasiya = true     → bütün bazarlar⛔
kritik_itki_sayi>=4 → bütün bazarlar⛔
btts_xeyr güclüdürsə → over25⛔
alt15 güclüdürsə    → btts⛔

4 DƏMİR QAYDA:
1. Bus-stop qonaq → BTTS⛔ Over2.5⛔ Corner üst⛔
2. Mental eliminasiya çarpanı aktiv olduqda over bazarları azaldılır
3. Konversiya <=10% + son5 qol <=4 → Over⛔
4. Qonaq qol <=0.9 + konversiya <=10% → BTTS⛔ Over2.5⛔

NO BET ZONE: final_sistem_guveni < 6.5 → "OYNAMARAM"

GÜVƏN VİZUALI:
9-10  → Əfsanəvi  ██████████
8-9   → Çox yüksək █████████░
7-8   → Yüksək    ████████░░
6.5-7 → Orta      ███████░░░
<6.5  → No Bet    █████░░░░░

HƏR BAZAR ÜÇÜN QAYTAR:
- ehtimal (0.0-1.0)
- guveni (0.0-10.0)
- qerar: "✅✅ Çox güvənli" / "✅ Güvənli" / "⚠️ Orta" / "❌ Zəif" / "⛔ Bloker"
- sebeb (qısa)
- dominant_modul: "M1" / "M3" / "M2"
- bloker_sebeb (yalnız ⛔ olduqda)

QƏTİ XƏBƏRDARLIQ: Qətiyyən markdown (` ```json ` və s.) istifadə etmə. Fikirlərini <think> blokunda yaz, amma yekunda BİRBAŞA { ilə başlayan JSON obyekti qaytar.

YALNIZ bu JSON formatında qaytar — heç bir izah yazma:
{
  "sistem_guveni": 0.0,
  "qerar_guveni": 0.0,
  "penaltyler": [],
  "final_guveni": 0.0,
  "oynayiram": true,
  "umumi_sebeb": null,
  "bazarlar": {
    "qol": {
      "over15": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null},
      "over25": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null},
      "over35": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null},
      "over45": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null},
      "under25": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null},
      "under35": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null}
    },
    "btts": {
      "beli": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null},
      "xeyr": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null}
    },
    "netice": {
      "p1": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null},
      "px": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null},
      "p2": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null},
      "p1x": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null},
      "px2": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null},
      "p12": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null}
    },
    "corner": {
      "over9.5": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null},
      "over10.5": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null},
      "over11.5": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null},
      "tek": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null},
      "cut": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null}
    },
    "kart": {
      "over25": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null},
      "over35": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null},
      "tek": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null},
      "cut": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null}
    },
    "faul": {
      "over205": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null},
      "over225": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null}
    },
    "penalti": {
      "beli": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null},
      "xeyr": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null}
    },
    "kombine": {
      "over25_btts": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null},
      "p1_over25": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null},
      "p2_over25": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null}
    },
    "ht": {
      "over05": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null},
      "over15": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null},
      "p1": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null},
      "px": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null},
      "p2": {"ehtimal": 0.0, "guveni": 0.0, "qerar": null, "sebeb": null, "dominant_modul": null}
    }
  },
  "top_tavsiyeler": [
    {"bazar": "Məsələn: Over 2.5", "ehtimal": 0.0, "qerar": "✅✅ Çox güvənli"}
  ]
}
"""

def hazirla_m4_input(m1: dict, m2: dict, m3: dict) -> dict:
    # Təhlükəsiz Data Çıxarışı (NoneType Error-un qarşısını almaq üçün)
    m1 = m1 or {}
    m2 = m2 or {}
    m3 = m3 or {}

    # M1 Dataları
    qol_bazarlari = m1.get("qol_bazarlari") or {}
    qol_bazasi = m1.get("qol_bazasi") or {}
    corner = m1.get("corner") or {}
    kart = m1.get("kart") or {}
    faul = m1.get("faul") or {}
    ht = qol_bazarlari.get("ht") or {}
    guveni_m1 = (m1.get("guveni") or {}).get("total", 0)

    # M3 Dataları
    m3_data = m3.get("data") if isinstance(m3, dict) and "data" in m3 else m3
    m3_data = m3_data or {}
    flags = m3_data.get("flags") or {}
    guveni_m3 = m3_data.get("m3_guveni", 0)

    # M2 Dataları
    m2_data = m2.get("data") if isinstance(m2, dict) and "data" in m2 else m2
    m2_data = m2_data or {}
    guveni_m2 = m2.get("guveni", 0) if isinstance(m2, dict) else 0

    return {
        "M1": {
            "over15": qol_bazarlari.get("over15"),
            "over25": qol_bazarlari.get("over25"),
            "over35": qol_bazarlari.get("over35"),
            "btts": qol_bazarlari.get("btts"),
            "btts_xeyr": qol_bazarlari.get("btts_xeyr"),
            "p1": qol_bazarlari.get("p1"),
            "px": qol_bazarlari.get("px"),
            "p2": qol_bazarlari.get("p2"),
            "p1x": qol_bazarlari.get("p1x"),
            "px2": qol_bazarlari.get("px2"),
            "p12": qol_bazarlari.get("p12"),
            "corner_ort": corner.get("ortalama"),
            "corner_over95": corner.get("over9_5"),
            "corner_over105": corner.get("over10_5"),
            "corner_tek": corner.get("tek"),
            "kart_over25": kart.get("over2_5"),
            "kart_over35": kart.get("over3_5"),
            "faul_over205": faul.get("over20_5"),
            "ht_over05": ht.get("over05"),
            "ht_over15": ht.get("over15"),
            "xam_baza": qol_bazasi.get("final_baza"),
            "guveni": guveni_m1,
            "null_fields": m1.get("null_fields", []),
            "null_data": qol_bazasi.get("null_data", False)
        },
        "M3": {
            "tempo": m3_data.get("tempo"),
            "taktika_ev": m3_data.get("taktika_ev"),
            "taktika_qonaq": m3_data.get("taktika_qonaq"),
            "dominant_teref": m3_data.get("dominant_teref"),
            "qol_veziyyeti": m3_data.get("qol_veziyyeti"),
            "oyun_oxunusu": m3_data.get("oyun_oxunusu"),
            "kahin_cumlesi": m3_data.get("kahin_cumlesi"),
            "carpanlar": m3_data.get("carpanlar"),
            "guveni": guveni_m3
        },
        "M2": {
            "hakim_sertlik": m2_data.get("hakim_sertlik"),
            "kritik_itki": flags.get("kritik_itki", False),
            "rotasiya": flags.get("rotasiya", False),
            "guveni": guveni_m2
        },
        "flags": {
            "bus_stop": flags.get("bus_stop", False),
            "rotasiya": flags.get("rotasiya", False),
            "kritik_itki": flags.get("kritik_itki", False),
            "kritik_itki_sayi": flags.get("kritik_itki_sayi", 0),
            "null_data": qol_bazasi.get("null_data", False),
            "m2_zeyif": guveni_m2 < 5.0
        }
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

        # DeepSeek <think> bloklarını təmizlə
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
        
        # Bəzən model ```json ... ``` içində qaytarır. Onu da təmizləyək.
        content = content.replace("```json", "").replace("```", "").strip()

        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if not json_match:
            return {"success": False, "error": "JSON strukturu tapılmadı. AI cavabı düzgün deyil.", "raw": content}

        m4_data = json.loads(json_match.group())
        return {"success": True, "data": m4_data}

    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON parse xətası: {str(e)}", "raw": content}
    except Exception as e:
        return {"success": False, "error": str(e)}