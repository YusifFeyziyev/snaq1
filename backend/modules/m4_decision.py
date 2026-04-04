import json
import re
import os
import sys
from typing import Dict, Any, List, Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import GROQ_KEY_M4, MODEL_M4

try:
    from groq import Groq
except ImportError:
    print("Groq modulu tapilmadi. pip install groq")
    Groq = None


class M4Decision:
    def __init__(self):
        if Groq is None:
            raise ImportError("Groq modulu yuklenmeyib. 'pip install groq' edin.")
        if not GROQ_KEY_M4:
            raise ValueError("GROQ_KEY_M4 env-de tapilmadi.")
        self.client = Groq(api_key=GROQ_KEY_M4)
        self.model = MODEL_M4
        self.no_bet_threshold = 6.5

    def _get_m1_guveni(self, m1_data: Dict) -> float:
        val = m1_data.get("m1_guveni", 5.0)
        if isinstance(val, (int, float)):
            return float(val * 10 if val <= 1.0 else val)
        return 5.0

    def _get_m2_guveni(self, m2_data: Dict) -> float:
        if not isinstance(m2_data, dict):
            return 5.0
        val = m2_data.get("m2_guveni", 5.0)
        if isinstance(val, (int, float)):
            return float(val * 10 if val <= 1.0 else val)
        return 5.0

    def _get_m3_guveni(self, m3_data: Dict) -> float:
        val = m3_data.get("m3_guveni", 0.5)
        if isinstance(val, (int, float)):
            return float(val * 10 if val <= 1.0 else val)
        return 5.0

    def _extract_json_from_response(self, text: str) -> Dict:
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*", "", text)
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception as e:
                pass
        try:
            return json.loads(text)
        except Exception as e:
            return {"error": "JSON parse olunmadi", "raw": text[:500]}

    def _call_groq(self, prompt: str) -> Dict:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Sən futbol analizi üzrə qərar modulusan. "
                            "Çıxışını YALNIZ düzgün JSON formatında ver. "
                            "Heç bir əlavə mətn, açıqlama, markdown olmadan. "
                            "Yalnız xam JSON."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.15,
                max_tokens=4000
            )
            content = response.choices[0].message.content
            return self._extract_json_from_response(content)
        except Exception as e:
            return {"error": f"Groq API xətası: {str(e)}"}

    def _calculate_system_confidence(self, m1_g: float, m2_g: float, m3_g: float) -> float:
        return round((m1_g * 0.50 + m2_g * 0.20 + m3_g * 0.30), 1)

    def _build_decision_prompt(
        self,
        m1: Dict,
        m2: Dict,
        m3: Dict,
        m1_g: float,
        m2_g: float,
        m3_g: float,
        sys_conf: float,
        no_bet: bool
    ) -> str:
        m1_str = json.dumps(m1, indent=2, ensure_ascii=False)
        m2_str = json.dumps(m2, indent=2, ensure_ascii=False)
        m3_str = json.dumps(m3, indent=2, ensure_ascii=False)

        return f"""Sən futbol analizi üçün son qərar modulusan (M4).

MODUL GÜVƏNLƏRİ (0-10 şkala):
- M1 (Riyazi model): {m1_g}/10
- M2 (Araşdırma): {m2_g}/10
- M3 (Ekspert): {m3_g}/10
- Sistem güvəni (çəkili orta): {sys_conf}/10
- No Bet Zone aktiv: {no_bet} (threshold: 6.5/10)

ÇƏKI SİSTEMİ:
- Normal bazarlar: M1=50%, M2=20%, M3=30%
- Hakim/travma/heyət/hava/motivasiya bazarları: M1=35%, M2=35%, M3=30%

VƏZİFƏN:
Aşağıdakı bütün bazarların HƏR BİRİ üçün ayrı-ayrı qərar ver:
1. qol_over_under (Over 2.5 / Under 2.5)
2. btts (hər iki komanda qol vurur / vurmuyor)
3. mac_sonucu_1x2 (ev sahibi qazanır / bərabərlik / qonaq qazanır)
4. ilk_yari_over_under (ilk yarı over 0.5 / 1.5)
5. kart_bazari (sarı kart over/under)
6. corner_bazari (künc vuruşu over/under)
7. handicap (asiya hendikep)
8. ust_ust (ikinci yarı qol)

HƏR BAZAR ÜÇÜN:
- qerar: "OYNARIM" və ya "OYNAMARAM"
- eger OYNARIM: hansı tərəfə (over/under, 1/x/2 və s.)
- ehtimal: 0.0-1.0
- guven: ✅✅ (çox yüksək), ✅ (yüksək), ⚠️ (orta), ❌ (aşağı), ⛔ (oynamaram)
- sebeb: M1/M2/M3 məlumatlarına əsaslanaraq KONKRET rəqəmlər ilə izah et
- dominant: "M1" / "M2" / "M3"

QAYDALAR:
- Əgər no_bet True-dursa, ümumi qərar "OYNAMARAM" olmalıdır
- Hər bazarın səbəbini M1/M2/M3 məlumatlarına əsasən KONKRET yazmalısan (rəqəm, statistika istifadə et)
- Təxmin yox, verilənlərə əsaslanan analiz

ÇIXIŞ FORMATI (yalnız bu JSON, başqa heç nə):
{{
  "umumi_qerar": "OYNARIM" ya "OYNAMARAM",
  "umumi_guven": "✅✅" ya "✅" ya "⚠️" ya "❌" ya "⛔",
  "umumi_sebeb": "Sistemin ümumi qiymətləndirməsi KONKRET məlumatlarla",
  "dominant_modul": "M1" ya "M2" ya "M3",
  "bazarlar": {{
    "qol_over_under": {{
      "qerar": "OYNARIM",
      "secenek": "Over 2.5",
      "ehtimal": 0.72,
      "guven": "✅",
      "sebeb": "M1: ev sahibi son 5 oyunda orta 2.1 qol, qonaq 1.8 qol. M3: hər iki komanda hücum taktikası tətbiq edir.",
      "dominant": "M1"
    }},
    "btts": {{
      "qerar": "OYNAMARAM",
      "secenek": "Yox",
      "ehtimal": 0.45,
      "guven": "⚠️",
      "sebeb": "M1: qonaq hücum zəifdir. M2: qonaq komandada 2 hücumçu travmalıdır.",
      "dominant": "M2"
    }},
    "mac_sonucu_1x2": {{
      "qerar": "OYNARIM",
      "secenek": "1 (Ev sahibi)",
      "ehtimal": 0.65,
      "guven": "✅",
      "sebeb": "...",
      "dominant": "M1"
    }},
    "ilk_yari_over_under": {{
      "qerar": "OYNAMARAM",
      "secenek": "-",
      "ehtimal": 0.48,
      "guven": "⚠️",
      "sebeb": "...",
      "dominant": "M3"
    }},
    "kart_bazari": {{
      "qerar": "OYNARIM",
      "secenek": "Over 3.5 sarı kart",
      "ehtimal": 0.68,
      "guven": "✅",
      "sebeb": "M2: hakim bu mövsüm orta 4.2 sarı kart verir. Rəqabətli oyun gözlənilir.",
      "dominant": "M2"
    }},
    "corner_bazari": {{
      "qerar": "OYNAMARAM",
      "secenek": "-",
      "ehtimal": 0.50,
      "guven": "⚠️",
      "sebeb": "...",
      "dominant": "M1"
    }},
    "handicap": {{
      "qerar": "OYNAMARAM",
      "secenek": "-",
      "ehtimal": 0.50,
      "guven": "⚠️",
      "sebeb": "...",
      "dominant": "M1"
    }},
    "ust_ust": {{
      "qerar": "OYNAMARAM",
      "secenek": "-",
      "ehtimal": 0.50,
      "guven": "⚠️",
      "sebeb": "...",
      "dominant": "M3"
    }}
  }}
}}

M1 NƏTİCƏSİ:
{m1_str}

M2 NƏTİCƏSİ:
{m2_str}

M3 NƏTİCƏSİ:
{m3_str}

İndi yuxarıdakı məlumatlara əsaslanaraq bütün bazarlar üçün KONKRET, rəqəmlərə dayanan qərar ver. Yalnız JSON."""

    def run_m4(self, m1_result: Dict, m2_result: Dict, m3_result: Dict) -> Dict:
        m1_g = self._get_m1_guveni(m1_result)
        m2_g = self._get_m2_guveni(m2_result)
        m3_g = self._get_m3_guveni(m3_result)
        sys_conf = self._calculate_system_confidence(m1_g, m2_g, m3_g)
        no_bet = sys_conf < self.no_bet_threshold

        print(f"M4 sistem güvəni hesabı → M1:{m1_g}, M2:{m2_g}, M3:{m3_g}, Sistem:{sys_conf}")

        prompt = self._build_decision_prompt(
            m1_result, m2_result, m3_result,
            m1_g, m2_g, m3_g, sys_conf, no_bet
        )
        groq_response = self._call_groq(prompt)

        if "error" in groq_response:
            print(f"M4 Groq xətası: {groq_response['error']}")
            return {
                "sistem_guveni": sys_conf,
                "no_bet_zone_aktiv": no_bet,
                "umumi_qerar": "OYNAMARAM",
                "umumi_guven": "⚠️",
                "umumi_sebeb": f"M4 Groq xətası: {groq_response['error']}",
                "dominant_modul": "M4",
                "modul_guvenleri": {"M1": m1_g, "M2": m2_g, "M3": m3_g},
                "bazarlar": {}
            }

        bazarlar = groq_response.get("bazarlar", {})

        # No-bet zone aktivdirsə bütün bazarları OYNAMARAM et
        if no_bet:
            for bazar_key in bazarlar:
                bazarlar[bazar_key]["qerar"] = "OYNAMARAM"
                bazarlar[bazar_key]["guven"] = "⛔"
                bazarlar[bazar_key]["sebeb"] = (
                    bazarlar[bazar_key].get("sebeb", "") +
                    f" [No-Bet Zone: Sistem güvəni {sys_conf}/10 < 6.5]"
                )

        return {
            "sistem_guveni": sys_conf,
            "no_bet_zone_aktiv": no_bet,
            "umumi_qerar": "OYNAMARAM" if no_bet else groq_response.get("umumi_qerar", "OYNAMARAM"),
            "umumi_guven": "⛔" if no_bet else groq_response.get("umumi_guven", "⚠️"),
            "umumi_sebeb": groq_response.get("umumi_sebeb", ""),
            "dominant_modul": groq_response.get("dominant_modul", "M4"),
            "modul_guvenleri": {"M1": m1_g, "M2": m2_g, "M3": m3_g},
            "bazarlar": bazarlar
        }


def run_m4(m1_result: Dict, m2_result: Dict, m3_result: Dict) -> Dict:
    m4 = M4Decision()
    return m4.run_m4(m1_result, m2_result, m3_result)


if __name__ == "__main__":
    test_m1 = {
        "m1_guveni": 7.5,
        "bazarlar": {
            "qol_over_under": {"ehtimal": 0.72},
            "btts": {"ehtimal": 0.55}
        }
    }
    test_m2 = {"m2_guveni": 6.5}
    test_m3 = {"m3_guveni": 0.70}
    result = run_m4(test_m1, test_m2, test_m3)
    print(json.dumps(result, indent=2, ensure_ascii=False))
