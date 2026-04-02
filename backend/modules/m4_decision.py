# backend/modules/m4_decision.py
import json
import re
import os
import sys
from typing import Dict, Any, List, Optional

# Əgər backend qovluğundan çağırılıbsa, config-i tapa bilmək üçün
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import GROQ_KEY_M4, MODEL_M4

# Groq import
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

        # Çəki sistemi (baza)
        self.base_weights = {
            "M1": 0.50,
            "M2": 0.20,
            "M3": 0.30
        }
        # Bəzi bazarlar üçün M2 çəkisinin artırıldığı xüsusi hallar
        self.m2_boost_markets = [
            "hakim_təsiri", "travma", "heyət_çatışmazlığı", "hava", "motivasiya"
        ]

        # Hard override qaydaları (şərt -> qərar, güvən, səbəb)
        self.override_rules = [
            {
                "condition": lambda m1, m2, m3: m1.get("qol_over_under", {}).get("over_1_5_ehtimal", 0) > 0.85,
                "override": {"qərar": "OVER 1.5", "güvən": "✅✅", "səbəb": "M1-də over 1.5 ehtimalı çox yüksək (hard override)"}
            },
            {
                "condition": lambda m1, m2, m3: m3.get("m3_guveni", 0) < 0.3,
                "override": {"qərar": "OYNAMARAM", "güvən": "❌", "səbəb": "M3 güvəni çox aşağı, bütün bazarlar üçün riskli"}
            }
        ]

        # No Bet Zone threshold (sistem güvəni 6.5/10-dan aşağı olarsa, əsas qərar OYNAMARAM)
        self.no_bet_threshold = 6.5

    def _extract_json_from_response(self, text: str) -> Dict:
        """Groq cavabından JSON-u təmizləyir."""
        # Markdown bloklarını təmizlə
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*", "", text)
        # JSON hissəsini tap
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
        # Əgər alınmırsa, bütün mətni parse etməyə çalış
        try:
            return json.loads(text)
        except:
            return {"error": "JSON parse olunmadi", "raw": text[:500]}

    def _call_groq(self, prompt: str) -> Dict:
        """Groq API çağırışı."""
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

    def _calculate_system_confidence(self, m1_data: Dict, m2_data: Dict, m3_data: Dict) -> float:
        """Sistem güvəni (0-10) - M1,M2,M3 güvənlərinin ortalaması (çəkisiz)."""
        m1_guven = m1_data.get("m1_guveni", 5.0)
        m2_guven = m2_data.get("m2_guveni", 5.0) if isinstance(m2_data, dict) else 5.0
        m3_guven = m3_data.get("m3_guveni", 5.0)
        # Hamısı 0-10 arası
        return round((m1_guven + m2_guven + m3_guven) / 3.0, 1)

    def _combine_market_decision(self, market_name: str, m1_market: Any, m2_market: Any, m3_market: Any) -> Dict:
        """Bir bazar üçün voting, conflict detection, weight tətbiqi."""
        # Əgər məlumat yoxdursa, default
        if not m1_market and not m2_market and not m3_market:
            return {"qərar": "MƏLUMAT YOXDUR", "güvən": "⛔", "səbəb": "Heç bir moduldan məlumat gəlməyib", "dominant": "YOX"}

        # Məlumatları dict formatına çevir (hər biri ehtimal və ya qərar ola bilər)
        # Bu sadə versiyada hər bazar üçün ən sadə qərar: M1-dən ehtimal, M2-dən mətn, M3-dən çarpan
        # Lakin tələbə uyğun olaraq, M4 promptunda bütün bazarları ətraflı təhlil etdirəcəyik.
        # Daha etibarlı üsul: Bütün bazarları prompta verib DeepSeek-dən qərar istəmək.
        # Aşağıda biz hər bazar üçün prompt yaradıb DeepSeek-ə göndərəcəyik.

        # Lakin performans üçün, bütün bazarları bir prompta yığıb bir dəfə çağırmaq daha yaxşıdır.
        # Biz bunu run_m4-də edəcəyik. Bu funksiya fərdi bazar üçün nəzərdə tutulub, lakin əsas məntiq run_m4-dədir.
        pass

    def run_m4(self, m1_result: Dict, m2_result: Dict, m3_result: Dict) -> Dict:
        """
        M1, M2, M3 nəticələrini alır, çəki sistemi, voting, override qaydaları ilə son qərar JSON-unu qaytarır.
        """
        # Sistem güvəni
        system_conf = self._calculate_system_confidence(m1_result, m2_result, m3_result)

        # Əgər sistem güvəni no_bet_threshold-dan aşağıdırsa, default olaraq OYNAMARAM
        no_bet_active = system_conf < self.no_bet_threshold

        # Override qaydalarını yoxla
        override_applied = None
        for rule in self.override_rules:
            try:
                if rule["condition"](m1_result, m2_result, m3_result):
                    override_applied = rule["override"]
                    break
            except:
                continue

        # Əgər override varsa, ondan istifadə et
        if override_applied:
            final_decision = override_applied["qərar"]
            final_confidence = override_applied["güvən"]
            reason = override_applied["səbəb"]
            dominant = "OVERRIDE"
        else:
            # Normal proses: M4 Groq modelinə sorğu göndər
            prompt = self._build_decision_prompt(m1_result, m2_result, m3_result, system_conf, no_bet_active)
            groq_response = self._call_groq(prompt)

            # Groq cavabından qərar və digər sahələri çıxar
            final_decision = groq_response.get("qərar", "OYNAMARAM")
            final_confidence = groq_response.get("güvən_səviyyəsi", "⚠️")
            reason = groq_response.get("səbəb", "M4 təhlili nəticəsində")
            dominant = groq_response.get("dominant_modul", "M4")

        # Nəticə JSON-unu qur
        result = {
            "sistem_guveni": system_conf,
            "no_bet_zone_aktiv": no_bet_active,
            "qərar": final_decision,
            "qərar_guveni": final_confidence,
            "səbəb": reason,
            "dominant_modul": dominant,
            "bazarlar": self._generate_markets_summary(m1_result, m2_result, m3_result, final_decision)
        }

        return result

    def _build_decision_prompt(self, m1: Dict, m2: Dict, m3: Dict, sys_conf: float, no_bet: bool) -> str:
        """M4 üçün prompt qurur."""
        m1_str = json.dumps(m1, indent=2, ensure_ascii=False)
        m2_str = json.dumps(m2, indent=2, ensure_ascii=False)
        m3_str = json.dumps(m3, indent=2, ensure_ascii=False)

        prompt = f"""Sən futbol analizi üçün qərar modulusan (M4). Aşağıda M1 (riyazi statistik model), M2 (axtarış araşdırması), M3 (ekspert taktiki analiz) nəticələri verilir.

Çəki sistemi: M1=0.50, M2=0.20, M3=0.30. Lakin bəzi bazarlarda (hakim, travma, heyət, hava, motivasiya) M2-nin çəkisi 0.35-ə qədər arta bilər.
Sistem güvəni: {sys_conf}/10. No Bet Zone threshold: 6.5/10. No bet aktiv? {no_bet}

Tələblər:
1. Hər bazar üçün ehtimal, güvən səviyyəsi (✅✅, ✅, ⚠️, ❌, ⛔), səbəb və dominant modulu göstər.
2. Ümumi qərar (OYNARIM və ya OYNAMARAM) və onun güvən səviyyəsini ver.
3. Əgər no_bet aktivdirsə, ümumi qərar "OYNAMARAM" olmalıdır (ancaq override qaydaları pozarsa).
4. Çıxışını AŞAĞIDAKİ JSON formatında ver, başqa heç nə yazma:

{{
  "qərar": "OYNARIM" veya "OYNAMARAM",
  "güvən_səviyyəsi": "✅✅ veya ✅ veya ⚠️ veya ❌ veya ⛔",
  "səbəb": "Qısa izah",
  "dominant_modul": "M1 veya M2 veya M3 veya M4",
  "bazarlar": {{
    "qol_over_under": {{
      "ehtimal": 0.75,
      "güvən": "✅",
      "səbəb": "M1 yüksək ehtimal verir, M3 dəstəkləyir",
      "dominant": "M1"
    }},
    "btts": {{...}},
    "cerrah": {{...}}
    // bütün bazarları bura əlavə et
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
        """Sadəlik üçün, bazar məlumatlarını birləşdirir. Əslində M4-dən gələn bazarlar istifadə olunmalıdır.
           Bu versiyada demo olaraq m1-in bazar strukturunu qaytarırıq."""
        markets = {}
        # M1-də bazarlar varsa onları al
        if "bazarlar" in m1:
            for k, v in m1["bazarlar"].items():
                markets[k] = {
                    "ehtimal": v.get("ehtimal", 0.5) if isinstance(v, dict) else 0.5,
                    "güvən": "⚠️",
                    "səbəb": "M4 tərəfindən təhlil edilməyib (demo)",
                    "dominant": "M1"
                }
        return markets

# Modul funksiyası (xarici çağırış üçün)
def run_m4(m1_result: Dict, m2_result: Dict, m3_result: Dict) -> Dict:
    """M4 modulunu işə salır."""
    m4 = M4Decision()
    return m4.run_m4(m1_result, m2_result, m3_result)

# Test bloku
if __name__ == "__main__":
    # Mock məlumatlar
    test_m1 = {"m1_guveni": 8.0, "bazarlar": {"qol_over_under": {"ehtimal": 0.85}}}
    test_m2 = {"m2_guveni": 6.0}
    test_m3 = {"m3_guveni": 7.5}
    result = run_m4(test_m1, test_m2, test_m3)
    print(json.dumps(result, indent=2, ensure_ascii=False))
