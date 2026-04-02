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

        self.base_weights = {
            "M1": 0.50,
            "M2": 0.20,
            "M3": 0.30
        }
        self.m2_boost_markets = [
            "hakim_təsiri", "travma", "heyət_çatışmazlığı", "hava", "motivasiya"
        ]

        self.override_rules = [
            {
                "condition": lambda m1, m2, m3: m1.get("qol_over_under", {}).get("over_1_5_ehtimal", 0) > 0.85,
                "override": {"qərar": "OVER 1.5", "güvən": "✅✅", "səbəb": "M1-də over 1.5 ehtimalı çox yüksək (hard override)"}
            },
            {
                "condition": lambda m1, m2, m3: self._get_m3_guveni_normalized(m3) < 3.0,
                "override": {"qərar": "OYNAMARAM", "güvən": "❌", "səbəb": "M3 güvəni çox aşağı, bütün bazarlar üçün riskli"}
            }
        ]

        self.no_bet_threshold = 6.5

    # ✅ DÜZƏLİŞ: M3 guveni 0-1 şkalasını 0-10-a çevirir
    def _get_m3_guveni_normalized(self, m3_data: Dict) -> float:
        """M3 m3_guveni 0-1 şkalasdır, 0-10-a çevir."""
        raw = m3_data.get("m3_guveni", 0.5)
        if isinstance(raw, (int, float)):
            return raw * 10 if raw <= 1.0 else raw
        return 5.0

    def _extract_json_from_response(self, text: str) -> Dict:
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*", "", text)
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
        try:
            return json.loads(text)
        except:
            return {"error": "JSON parse olunmadi", "raw": text[:500]}

    def _call_groq(self, prompt: str) -> Dict:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Sən futbol analizi üzrə qərar modulusan. Çıxışını yalnız JSON formatında ver, heç bir əlavə mətn olmadan."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=3000
            )
            content = response.choices[0].message.content
            return self._extract_json_from_response(content)
        except Exception as e:
            return {"error": f"Groq API xətası: {str(e)}"}

    # ✅ DÜZƏLİŞ: Şkala uyğunsuzluğu həll edildi
    def _calculate_system_confidence(self, m1_data: Dict, m2_data: Dict, m3_data: Dict) -> float:
        """
        M1 → 0-10 şkala
        M2 → 0-10 şkala (m2_guveni artıq run_m2-dən 0-10 gəlir)
        M3 → 0-1 şkala, burada 0-10-a çevrilir
        """
        # M1: birbaşa 0-10
        m1_guven = m1_data.get("m1_guveni", 5.0)
        if isinstance(m1_guven, float) and m1_guven <= 1.0:
            m1_guven = m1_guven * 10  # ehtiyat üçün

        # M2: run_m2-dən artıq 0-10 gəlir
        m2_guven = m2_data.get("m2_guveni", 5.0) if isinstance(m2_data, dict) else 5.0
        if isinstance(m2_guven, float) and m2_guven <= 1.0:
            m2_guven = m2_guven * 10  # ehtiyat üçün

        # M3: 0-1 → 0-10
        m3_guven = self._get_m3_guveni_normalized(m3_data)

        print(f"M4 sistem güvəni hesabı → M1:{m1_guven}, M2:{m2_guven}, M3:{m3_guven}")
        return round((m1_guven + m2_guven + m3_guven) / 3.0, 1)

    def run_m4(self, m1_result: Dict, m2_result: Dict, m3_result: Dict) -> Dict:
        system_conf = self._calculate_system_confidence(m1_result, m2_result, m3_result)
        no_bet_active = system_conf < self.no_bet_threshold

        override_applied = None
        for rule in self.override_rules:
            try:
                if rule["condition"](m1_result, m2_result, m3_result):
                    override_applied = rule["override"]
                    break
            except:
                continue

        if override_applied:
            final_decision = override_applied["qərar"]
            final_confidence = override_applied["güvən"]
            reason = override_applied["səbəb"]
            dominant = "OVERRIDE"
        else:
            prompt = self._build_decision_prompt(m1_result, m2_result, m3_result, system_conf, no_bet_active)
            groq_response = self._call_groq(prompt)

            if "error" in groq_response:
                print(f"M4 Groq xətası: {groq_response['error']}")
                final_decision = "OYNAMARAM"
                final_confidence = "⚠️"
                reason = f"M4 Groq xətası: {groq_response['error']}"
                dominant = "M4"
            else:
                final_decision = groq_response.get("qərar", "OYNAMARAM")
                final_confidence = groq_response.get("güvən_səviyyəsi", "⚠️")
                reason = groq_response.get("səbəb", "M4 təhlili nəticəsində")
                dominant = groq_response.get("dominant_modul", "M4")

        result = {
            "sistem_guveni": system_conf,
            "no_bet_zone_aktiv": no_bet_active,
            "qərar": final_decision,
            "qərar_guveni": final_confidence,
            "səbəb": reason,
            "dominant_modul": dominant,
            # ✅ modul güvənlərini ayrıca göstər (frontend üçün)
            "modul_guvenleri": {
                "M1": round(m1_result.get("m1_guveni", 5.0), 1),
                "M2": round(m2_result.get("m2_guveni", 0.0) if isinstance(m2_result, dict) else 0.0, 1),
                "M3": round(self._get_m3_guveni_normalized(m3_result), 1)
            },
            "bazarlar": self._generate_markets_summary(m1_result, m2_result, m3_result, final_decision)
        }

        return result

    def _build_decision_prompt(self, m1: Dict, m2: Dict, m3: Dict, sys_conf: float, no_bet: bool) -> str:
        # ✅ M3 güvənini normalize edib prompta göndər
        m3_normalized = dict(m3)
        m3_normalized["m3_guveni_normalized_10"] = self._get_m3_guveni_normalized(m3)

        m1_str = json.dumps(m1, indent=2, ensure_ascii=False)
        m2_str = json.dumps(m2, indent=2, ensure_ascii=False)
        m3_str = json.dumps(m3_normalized, indent=2, ensure_ascii=False)

        prompt = f"""Sən futbol analizi üçün qərar modulusan (M4). Aşağıda M1 (riyazi statistik model), M2 (axtarış araşdırması), M3 (ekspert taktiki analiz) nəticələri verilir.

Çəki sistemi: M1=0.50, M2=0.20, M3=0.30. Lakin bəzi bazarlarda (hakim, travma, heyət, hava, motivasiya) M2-nin çəkisi 0.35-ə qədər arta bilər.
Sistem güvəni: {sys_conf}/10. No Bet Zone threshold: 6.5/10. No bet aktiv? {no_bet}

Qeyd: M3-də m3_guveni_normalized_10 sahəsi 0-10 şkaladır, onu istifadə et.

Tələblər:
1. Hər bazar üçün ehtimal, güvən səviyyəsi (✅✅, ✅, ⚠️, ❌, ⛔), səbəb və dominant modulu göstər.
2. Ümumi qərar (OYNARIM və ya OYNAMARAM) və onun güvən səviyyəsini ver.
3. Əgər no_bet aktivdirsə, ümumi qərar "OYNAMARAM" olmalıdır.
4. Çıxışını YALNIZ aşağıdakı JSON formatında ver:

{{
  "qərar": "OYNARIM" və ya "OYNAMARAM",
  "güvən_səviyyəsi": "✅✅ və ya ✅ və ya ⚠️ və ya ❌ və ya ⛔",
  "səbəb": "Qısa izah",
  "dominant_modul": "M1 və ya M2 və ya M3 və ya M4",
  "bazarlar": {{
    "qol_over_under": {{
      "ehtimal": 0.75,
      "güvən": "✅",
      "səbəb": "M1 yüksək ehtimal verir, M3 dəstəkləyir",
      "dominant": "M1"
    }},
    "btts": {{}},
    "cerrah": {{}}
  }}
}}

M1 nəticəsi:
{m1_str}

M2 nəticəsi:
{m2_str}

M3 nəticəsi:
{m3_str}

Qərarını ver."""
        return prompt

    def _generate_markets_summary(self, m1: Dict, m2: Dict, m3: Dict, final_decision: str) -> Dict:
        markets = {}
        if "bazarlar" in m1:
            for k, v in m1["bazarlar"].items():
                markets[k] = {
                    "ehtimal": v.get("ehtimal", 0.5) if isinstance(v, dict) else 0.5,
                    "güvən": "⚠️",
                    "səbəb": "M1 əsaslı",
                    "dominant": "M1"
                }
        return markets


def run_m4(m1_result: Dict, m2_result: Dict, m3_result: Dict) -> Dict:
    m4 = M4Decision()
    return m4.run_m4(m1_result, m2_result, m3_result)


if __name__ == "__main__":
    test_m1 = {"m1_guveni": 8.0, "bazarlar": {"qol_over_under": {"ehtimal": 0.85}}}
    test_m2 = {"m2_guveni": 6.0}
    test_m3 = {"m3_guveni": 0.75}  # 0-1 şkala
    result = run_m4(test_m1, test_m2, test_m3)
    print(json.dumps(result, indent=2, ensure_ascii=False))
