import json
import re
import os
import sys
import requests
from typing import Dict, Any, List, Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import GROQ_KEY_M4, MODEL_M4

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class M4Decision:
    def __init__(self):
        if not GROQ_KEY_M4:
            raise ValueError("GROQ_KEY_M4 env-də tapılmadı.")
        self.key   = GROQ_KEY_M4
        self.model = MODEL_M4
        self.no_bet_threshold = 6.5

    # ✅ DÜZƏLİŞ 1: m1_confidence → m1_guveni fallback
    # M1 modulu "m1_confidence" açarı ilə qaytarır, "m1_guveni" yox
    def _get_m1_guveni(self, m1_data: Dict) -> float:
        val = m1_data.get("m1_confidence",       # ← yeni açar
              m1_data.get("m1_guveni", 5.0))     # ← köhnə açar (fallback)
        if isinstance(val, (int, float)):
            return float(val * 10 if val <= 1.0 else val)
        return 5.0

    def _get_m2_guveni(self, m2_data: Dict) -> float:
        if not isinstance(m2_data, dict):
            return 0.0
        val = m2_data.get("m2_guveni", 0.0)
        if isinstance(val, (int, float)):
            # M2 0-1 qaytarır → *10 et
            return float(round(val * 10 if val <= 1.0 else val, 1))
        return 0.0

    def _get_m3_guveni(self, m3_data: Dict) -> float:
        val = m3_data.get("m3_guveni", 3.0)
        if isinstance(val, (int, float)):
            # M3 0-10 qaytarır
            return float(val * 10 if val <= 1.0 else val)
        return 3.0

    def _extract_json_from_response(self, text: str) -> Dict:
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*",     "", text)
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
        try:
            return json.loads(text)
        except Exception:
            return {"error": "JSON parse olunmadı", "raw": text[:500]}

    # ✅ DÜZƏLİŞ 2: groq paketi əvəzinə requests istifadə et
    # Əvvəl: from groq import Groq → ayrıca paket lazım idi
    # İndi: requests ilə birbaşa Groq API çağırışı (digər modullarla eyni)
    def _call_groq(self, prompt: str) -> Dict:
        headers = {
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Sən futbol analizi üzrə qərar modulusan. "
                        "Çıxışını YALNIZ düzgün JSON formatında ver. "
                        "Heç bir əlavə mətn, açıqlama, markdown olmadan. "
                        "Yalnız xam JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.15,
            "max_tokens":  4000,
        }
        try:
            resp = requests.post(GROQ_API_URL, headers=headers,
                                 json=payload, timeout=90)
            if resp.status_code == 429:
                return {"error": "Groq rate limit"}
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return self._extract_json_from_response(content)
        except Exception as e:
            return {"error": f"Groq API xətası: {str(e)}"}

    def _calculate_system_confidence(self, m1_g: float,
                                     m2_g: float, m3_g: float) -> float:
        return round(m1_g * 0.50 + m2_g * 0.20 + m3_g * 0.30, 1)

    def _build_decision_prompt(self, m1: Dict, m2: Dict, m3: Dict,
                                m1_g: float, m2_g: float, m3_g: float,
                                sys_conf: float, no_bet: bool) -> str:
        return f"""Sən futbol analizi üçün son qərar modulusan (M4).

"MÜHÜM QAYDA: Əgər umumi_qerar='OYNARIM'-dirsə, ən azı "
"2-3 bazarda qerar='OYNARIM' olmalıdır. "
"Əgər heç bir bazarda oynamırıqsa, umumi_qerar da 'OYNAMARAM' olmalıdır."       

MODUL GÜVƏNLƏRİ (0-10 şkala):
- M1 (Riyazi model): {m1_g}/10
- M2 (Araşdırma):    {m2_g}/10
- M3 (Ekspert):      {m3_g}/10
- Sistem güvəni:     {sys_conf}/10
- No Bet Zone aktiv: {no_bet} (threshold: 6.5/10)

ÇƏKI SİSTEMİ:
- Normal bazarlar: M1=50%, M2=20%, M3=30%
- Hakim/travma/heyət/hava/motivasiya: M1=35%, M2=35%, M3=30%

VƏZİFƏN:
Aşağıdakı bütün bazarların HƏR BİRİ üçün ayrı qərar ver:
1. qol_over_under (Over/Under 2.5)
2. btts (hər iki komanda qol vurur/vurmuyor)
3. mac_sonucu_1x2 (ev/bərabərlik/qonaq)
4. ilk_yari_over_under (ilk yarı over 0.5/1.5)
5. kart_bazari (sarı kart over/under)
6. corner_bazari (künc vuruşu over/under)
7. handicap (asiya hendikep)
8. ust_ust (ikinci yarı qol)

HƏR BAZAR ÜÇÜN:
- qerar: "OYNA" ya "OYNAMA"
- secenek: hansı tərəf (over/under, 1/x/2 və s.)
- ehtimal: 0.0-1.0
- guven: ✅✅ / ✅ / ⚠️ / ❌ / ⛔
- sebeb: M1/M2/M3 məlumatlarına əsaslanan KONKRET rəqəmli izah
- dominant: "M1" / "M2" / "M3"

QAYDALAR:
- no_bet True-dursa bütün qərarlar "OYNAMARAM" olmalıdır
- Hər bazarın səbəbini konkret rəqəmlərlə yazmalısan
- Uydurma yox, verilənlərə əsaslanan analiz

ÇIXIŞ (yalnız bu JSON, başqa heç nə):
{{
  "umumi_qerar": "OYNARIM" ya "OYNAMARAM",
  "umumi_guven": "✅✅" ya "✅" ya "⚠️" ya "❌" ya "⛔",
  "umumi_sebeb": "Sistemin ümumi qiymətləndirməsi konkret məlumatlarla",
  "dominant_modul": "M1" ya "M2" ya "M3",
  "bazarlar": {{
    "qol_over_under":    {{"qerar":"","secenek":"","ehtimal":0.0,"guven":"","sebeb":"","dominant":""}},
    "btts":              {{"qerar":"","secenek":"","ehtimal":0.0,"guven":"","sebeb":"","dominant":""}},
    "mac_sonucu_1x2":    {{"qerar":"","secenek":"","ehtimal":0.0,"guven":"","sebeb":"","dominant":""}},
    "ilk_yari_over_under":{{"qerar":"","secenek":"","ehtimal":0.0,"guven":"","sebeb":"","dominant":""}},
    "kart_bazari":       {{"qerar":"","secenek":"","ehtimal":0.0,"guven":"","sebeb":"","dominant":""}},
    "corner_bazari":     {{"qerar":"","secenek":"","ehtimal":0.0,"guven":"","sebeb":"","dominant":""}},
    "handicap":          {{"qerar":"","secenek":"","ehtimal":0.0,"guven":"","sebeb":"","dominant":""}},
    "ust_ust":           {{"qerar":"","secenek":"","ehtimal":0.0,"guven":"","sebeb":"","dominant":""}}
  }}
}}

M1 NƏTİCƏSİ:
{json.dumps(m1, indent=2, ensure_ascii=False)}

M2 NƏTİCƏSİ:
{json.dumps(m2, indent=2, ensure_ascii=False)}

M3 NƏTİCƏSİ:
{json.dumps(m3, indent=2, ensure_ascii=False)}

İndi yuxarıdakı məlumatlara əsaslanaraq bütün bazarlar üçün KONKRET qərar ver. Yalnız JSON."""

    def run_m4(self, m1_result: Dict, m2_result: Dict, m3_result: Dict) -> Dict:
        m1_g     = self._get_m1_guveni(m1_result)
        m2_g     = self._get_m2_guveni(m2_result)
        m3_g     = self._get_m3_guveni(m3_result)
        sys_conf = self._calculate_system_confidence(m1_g, m2_g, m3_g)
        no_bet   = sys_conf < self.no_bet_threshold

        print(f"M4 → M1:{m1_g}/10, M2:{m2_g}/10, M3:{m3_g}/10, Sistem:{sys_conf}/10")
        print(f"M4 → No-Bet Zone: {no_bet}")

        prompt       = self._build_decision_prompt(
            m1_result, m2_result, m3_result,
            m1_g, m2_g, m3_g, sys_conf, no_bet,
        )
        groq_response = self._call_groq(prompt)

        if "error" in groq_response:
            print(f"M4 Groq xətası: {groq_response['error']}")
            return {
                "sistem_guveni":    sys_conf,
                "no_bet_zone_aktiv": no_bet,
                "umumi_qerar":      "OYNAMARAM",
                "umumi_guven":      "⚠️",
                "umumi_sebeb":      f"M4 Groq xətası: {groq_response['error']}",
                "dominant_modul":   "M4",
                "modul_guvenleri":  {"M1": m1_g, "M2": m2_g, "M3": m3_g},
                "bazarlar":         {},
            }

        bazarlar = groq_response.get("bazarlar", {})

        # No-bet zone aktivdirsə bütün bazarları OYNAMARAM et
        if no_bet:
            for bazar_key in bazarlar:
                b = bazarlar[bazar_key]
                b["qerar"]  = "OYNAMARAM"
                b["guven"]  = "⛔"
                b["sebeb"]  = (b.get("sebeb", "") +
                               f" [No-Bet Zone: Sistem güvəni {sys_conf}/10 < 6.5]")

        return {
            "sistem_guveni":    sys_conf,
            "no_bet_zone_aktiv": no_bet,
            "umumi_qerar":      "OYNAMARAM" if no_bet else groq_response.get("umumi_qerar", "OYNAMARAM"),
            "umumi_guven":      "⛔" if no_bet else groq_response.get("umumi_guven", "⚠️"),
            "umumi_sebeb":      groq_response.get("umumi_sebeb", ""),
            "dominant_modul":   groq_response.get("dominant_modul", "M4"),
            "modul_guvenleri":  {"M1": m1_g, "M2": m2_g, "M3": m3_g},
            "bazarlar":         bazarlar,
        }


def run_m4(m1_result: Dict, m2_result: Dict, m3_result: Dict) -> Dict:
    m4 = M4Decision()
    return m4.run_m4(m1_result, m2_result, m3_result)


if __name__ == "__main__":
    test_m1 = {
        "team1": "Inter Milan",
        "team2": "AS Roma",
        "m1_confidence": 7.5,          # ← yeni açar adı
        "1x2": {"home_win": 0.62, "draw": 0.22, "away_win": 0.16},
        "over_under": {
            "2.5": {"over": 0.54, "under": 0.46, "expected_total": 2.7}
        },
        "btts": {"yes": 0.44, "no": 0.56},
    }
    test_m2 = {
        "m2_guveni": 0.65,              # ← 0-1 scale
        "referee": {"name": "Davide Massa", "status": "real", "confidence": 0.80},
        "injuries": {"home_absent": [], "away_absent": [], "status": "real", "confidence": 0.70},
    }
    test_m3 = {
        "m3_guveni": 5.8,               # ← 0-10 scale
        "dominant_teref": {"value": "ev", "confidence": 0.7},
        "qol_veziyyeti":  {"value": "orta", "confidence": 0.6},
    }

    result = run_m4(test_m1, test_m2, test_m3)
    print(json.dumps(result, indent=2, ensure_ascii=False))