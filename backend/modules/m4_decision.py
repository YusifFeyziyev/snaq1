import json
import re
import os
import sys
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
  "top_tavsiyeler": []
}
"""


def hazirla_m4_input(m1: dict, m2: dict, m3: dict) -> dict:
    qol = m1.get("qol_bazarlari", {})
    corner = m1.get("corner", {})
    kart = m1.get("kart", {})
    faul = m1.get("faul", {})
    m3_data = m3.get("data", {}) if isinstance(m3, dict) else m3
    m2_data = m2.get("data", {}) if isinstance(m2, dict) else m2

    flags = m3_data.get("flags", {}) if m3_data else {}

    return {
        "M1": {
            "over15": qol.get("over15"),
            "over25": qol.get("over25"),
            "over35": qol.get("over35"),
            "btts": qol.get("btts"),
            "btts_xeyr": qol.get("btts_xeyr"),
            "p1": qol.get("p1"),
            "px": qol.get("px"),
            "p2": qol.get("p2"),
            "p1x": qol.get("p1x"),
            "px2": qol.get("px2"),
            "p12": qol.get("p12"),
            "corner_ort": corner.get("ortalama"),
            "corner_over95": corner.get("over9_5"),
            "corner_over105": corner.get("over10_5"),
            "corner_tek": corner.get("tek"),
            "kart_over25": kart.get("over2_5"),
            "kart_over35": kart.get("over3_5"),
            "faul_over205": faul.get("over20_5"),
            "ht_over05": m1.get("qol_bazarlari", {}).get("ht", {}).get("over05"),
            "ht_over15": m1.get("qol_bazarlari", {}).get("ht", {}).get("over15"),
            "xam_baza": m1.get("qol_bazasi", {}).get("final_baza"),
            "guveni": m1.get("guveni", {}).get("total"),
            "null_fields": m1.get("null_fields", []),
            "null_data": m1.get("qol_bazasi", {}).get("null_data", False)
        },
        "M3": {
            "tempo": m3_data.get("tempo") if m3_data else None,
            "taktika_ev": m3_data.get("taktika_ev") if m3_data else None,
            "taktika_qonaq": m3_data.get("taktika_qonaq") if m3_data else None,
            "dominant_teref": m3_data.get("dominant_teref") if m3_data else None,
            "qol_veziyyeti": m3_data.get("qol_veziyyeti") if m3_data else None,
            "oyun_oxunusu": m3_data.get("oyun_oxunusu") if m3_data else None,
            "kahin_cumlesi": m3_data.get("kahin_cumlesi") if m3_data else None,
            "carpanlar": m3_data.get("carpanlar") if m3_data else None,
            "guveni": m3_data.get("m3_guveni", 0) if m3_data else 0
        },
        "M2": {
            "hakim_sertlik": m2_data.get("hakim_sertlik") if m2_data else None,
            "kritik_itki": flags.get("kritik_itki", False),
            "rotasiya": flags.get("rotasiya", False),
            "guveni": m2.get("guveni", 0) if isinstance(m2, dict) else 0
        },
        "flags": {
            "bus_stop": flags.get("bus_stop", False),
            "rotasiya": flags.get("rotasiya", False),
            "kritik_itki": flags.get("kritik_itki", False),
            "kritik_itki_sayi": flags.get("kritik_itki_sayi", 0),
            "null_data": m1.get("qol_bazasi", {}).get("null_data", False),
            "m2_zeyif": m2.get("guveni", 0) < 5.0 if isinstance(m2, dict) else True
        }
    }


def run_m4(m1: dict, m2: dict, m3: dict) -> dict:
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

        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if not json_match:
            return {"success": False, "error": "JSON tapılmadı"}

        m4_data = json.loads(json_match.group())
        return {"success": True, "data": m4_data}

    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    # Sadə test
    test_m1 = {
        "qol_bazasi": {"ev_goz": 1.1, "qon_goz": 1.3, "final_baza": 2.2, "null_data": False},
        "qol_bazarlari": {
            "over15": 0.78, "over25": 0.55, "over35": 0.30,
            "btts": 0.58, "btts_xeyr": 0.42,
            "p1": 0.35, "px": 0.28, "p2": 0.37,
            "p1x": 0.63, "px2": 0.65, "p12": 0.72,
            "ht": {"over05": 0.72, "over15": 0.38, "p1": 0.30, "px": 0.35, "p2": 0.35}
        },
        "corner": {"ortalama": 17.2, "over9_5": 0.72, "over10_5": 0.58, "tek": 0.48},
        "kart": {"over2_5": 0.61, "over3_5": 0.38},
        "faul": {"over20_5": 0.55},
        "guveni": {"total": 7.5},
        "null_fields": ["sot_ort", "faul_ort"],
        "bonuslar": {"qol_ferqi": 0, "corner_ferqi": 15}
    }

    test_m2 = {
        "success": True,
        "guveni": 4.0,
        "data": {
            "hakim_sertlik": {"value": None, "status": "tapılmadı", "confidence": 0.0}
        }
    }

    test_m3 = {
        "success": True,
        "guveni": 6.5,
        "data": {
            "tempo": {"value": "orta", "confidence": 0.65, "source": "statistika"},
            "taktika_ev": {"value": "elastik", "confidence": 0.55, "source": "statistika"},
            "taktika_qonaq": {"value": "elastik", "confidence": 0.55, "source": "statistika"},
            "dominant_teref": {"value": "qonaq", "confidence": 0.60, "source": "cədvəl mövqeyi"},
            "qol_veziyyeti": {"value": "orta qol gözlənilir", "confidence": 0.60, "source": "statistika"},
            "oyun_oxunusu": {"value": "Balanslaşmış oyun", "confidence": 0.60, "source": "M1+M2"},
            "kahin_cumlesi": {"value": "Hər iki komanda ehtiyatlı oynayacaq", "confidence": 0.55, "source": "analiz"},
            "carpanlar": {
                "ev_hucum": 1.0, "qonaq_hucum": 1.0,
                "ev_mudafie": 1.0, "qonaq_mudafie": 1.0,
                "sot_carpan": 1.0, "corner_carpan": 1.0
            },
            "flags": {
                "bus_stop": False, "rotasiya": False,
                "kritik_itki": False, "kritik_itki_sayi": 0,
                "yorgunluk_aktiv": False, "ziddiyyet": False
            },
            "m3_guveni": 6.5
        }
    }

    result = run_m4(test_m1, test_m2, test_m3)
    print(json.dumps(result, ensure_ascii=False, indent=2))
