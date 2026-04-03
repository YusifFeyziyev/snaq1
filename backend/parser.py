import os
os.environ["PYTHONUTF8"] = "1"

# backend/parser.py
import json
import re
import sys
sys.stdout.reconfigure(encoding='utf-8')
from typing import Dict, Any, Optional

# Config-dən açarı almaq üçün path-i tənzimlə
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import GROQ_KEYS_PARSER, MODEL_PARSER

try:
    from groq import Groq
except ImportError:
    print("Groq modulu tapilmadi. 'pip install groq' edin.")
    Groq = None

class SoccerStatsParser:
    def __init__(self):
        if Groq is None:
            raise ImportError("Groq modulu yuklenmeyib. 'pip install groq' edin.")
        
        if not GROQ_KEYS_PARSER:
            raise ValueError("Heç bir GROQ_KEY_PARSER_1, GROQ_KEY_PARSER_2 və s. tapılmadı.")
        
        self.keys = GROQ_KEYS_PARSER
        self.model = MODEL_PARSER
        self.current_key_index = 0
        self.client = self._create_client()

    def _clean_json(self, text: str) -> str:
        """Markdown bloklarını və lazımsız hissələri təmizləyir."""
        # JSON kod blokunu çıxar
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*", "", text)
        # Baş və son boşluqları sil
        text = text.strip()
        return text

    def _extract_json(self, text: str) -> Dict:
        """Regex ilə JSON obyektini axtarır və parse edir."""
        # Əvvəlcə təmizlə
        cleaned = self._clean_json(text)
        # JSON obyektini tap (ən böyük {} bloku)
        match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if match:
            json_str = match.group(1)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                # Bəlkə daxildə tək dırnaqlar var? Onları düzəltməyə çalış
                try:
                    # Sadə hallar üçün: tək dırnaqları ikiqat dırnağa çevir
                    fixed = re.sub(r"'", '"', json_str)
                    return json.loads(fixed)
                except:
                    pass
                raise ValueError(f"JSON parse xətası: {e}\nMətn: {json_str[:200]}")
        else:
            raise ValueError("JSON obyekti tapilmadi.")
        
    def _create_client(self):
        """Cari key ilə Groq client yaradır."""
        key = self.keys[self.current_key_index]
        return Groq(api_key=key)

    def _rotate_key(self):
        """Növbəti key-ə keçir (rate limit və ya xəta olduqda)."""
        self.current_key_index = (self.current_key_index + 1) % len(self.keys)
        print(f"Parser: Key dəyişdirildi → {self.current_key_index + 1}-ci key istifadə olunur")
        self.client = self._create_client()    


    def _build_prompt(self, raw_text: str) -> str:
        """Groq modelinə göndəriləcək promptu qurur."""
        prompt = """Sən futbol statistikasını təhlil edən bir parsersən. Aşağıda SoccerStats-dan alınmış mətn verilir. Bu mətni təhlil edərək aşağıda göstərilən JSON strukturuna tam uyğun şəkildə çevir. Heç bir əlavə mətn yazma, yalnız JSON obyekti qaytar.

Tələb olunan JSON strukturu (boşluqlar olmadan, dəyərlər mümkün qədər doldurulmalı, tapılmayan sahələr null və ya boş string ola bilər):

{
    "ev_sahibi": "string",
    "qonaq": "string",
    "lig": "string",
    "tarix": "YYYY-MM-DD",
    "ortalama_qol_ev": 1.45,
    "ortalama_qol_qonaq": 1.12,
    "ortalama_korner_ev": 5.2,
    "ortalama_korner_qonaq": 4.1,
    "ortalama_sot_ev": 4.8,
    "ortalama_sot_qonaq": 3.9,
    "ortalama_faul_ev": 11.2,
    "ortalama_faul_qonaq": 12.5,
    "ortalama_sari_kart_ev": 1.8,
    "ortalama_sari_kart_qonaq": 2.1,
    "ortalama_qirmizi_kart_ev": 0.1,
    "ortalama_qirmizi_kart_qonaq": 0.2,
    "ortalama_ofsayt_ev": 1.9,
    "ortalama_ofsayt_qonaq": 2.0,
    "ortalama_aut_ev": 22.3,
    "ortalama_aut_qonaq": 21.1,
    "ortalama_qapidan_zərbə_ev": 12.4,
    "ortalama_qapidan_zərbə_qonaq": 11.0,
    "ortalama_penalti_ev": 0.15,
    "ortalama_penalti_qonaq": 0.10,
    "btts_faiz": 0.52,
    "over_1_5_faiz": 0.78,
    "over_2_5_faiz": 0.55,
    "over_3_5_faiz": 0.32,
    "h2h_qeyd": "Son 5 qarşılaşmada ev sahibi 3 qalibiyyət, 1 heç-heçə, 1 məğlubiyyət",
    "son_form_ev": "QMBMB",
    "son_form_qonaq": "MQBMQ",
    "ev_qol_sayisi_son_5": 8,
    "qonaq_qol_sayisi_son_5": 6,
    "ev_buraxilan_qol_son_5": 5,
    "qonaq_buraxilan_qol_son_5": 7
}

Mətn:
"""
        prompt += f'"""{raw_text}"""\n\nYalnız JSON obyektini qaytar, başqa heç nə yazma.'
        return prompt

    def parse(self, raw_text: str) -> Dict[str, Any]:
        """Əsas funksiya: mətni qəbul edir, JSON qaytarır."""
        if not raw_text or not raw_text.strip():
            raise ValueError("Boş mətn göndərildi.")

        prompt = self._build_prompt(raw_text)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Sən bir JSON parsersən. Yalnız JSON çıxışı et."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=4000
            )
            content = response.choices[0].message.content
            # JSON-u təmizlə və parse et
            result = self._extract_json(content)
            return result

        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "rate limit" in error_str or "quota" in error_str:
                print("Rate limit aşkarlandı, key dəyişdirilir...")
                self._rotate_key()
                # Yenidən cəhd et
                return self.parse(raw_text)
            else:
                raise RuntimeError(f"Parser xətası: {str(e)}")

# Modul funksiyası (xarici çağırış üçün)
def parse_soccer_stats(raw_text: str) -> Dict[str, Any]:
    """Köməkçi funksiya: SoccerStatsParser class-nı işə salır."""
    parser = SoccerStatsParser()
    return parser.parse(raw_text)

# Test bloku (yalnız birbaşa işlədikdə)
if __name__ == "__main__":
    # Nümunə mətn
    sample_text = """
    Manchester United vs Liverpool
    Premier League
    Son 5 oyun: United: QMBMQ, Liverpool: MQBMQ
    United evdə ortalama 1.8 qol atır, 1.1 buraxır.
    Liverpool səfərdə ortalama 2.0 qol atır, 0.9 buraxır.
    Over 2.5 faiz: 65%
    BTTS faiz: 54%
    Korner ortalama: United 5.3, Liverpool 6.1
    """
    try:
        result = parse_soccer_stats(sample_text)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print("Test xətası:", e)