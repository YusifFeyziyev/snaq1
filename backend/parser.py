# backend/parser.py
import json
import re
import sys
import os
from typing import Dict, Any

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from config import GROQ_KEYS_PARSER, MODEL_PARSER

try:
    import requests
except ImportError:
    raise ImportError("'pip install requests' edin.")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class SoccerStatsParser:
    def __init__(self):
        if not GROQ_KEYS_PARSER:
            raise ValueError("Hec bir GROQ_KEY_PARSER tapilmadi.")
        self.keys = GROQ_KEYS_PARSER
        self.model = MODEL_PARSER
        self.current_key_index = 0

    def _rotate_key(self):
        self.current_key_index = (self.current_key_index + 1) % len(self.keys)
        print(f"Parser: Key deyisdirildi -> {self.current_key_index + 1}-ci key istifade olunur")

    def _call_api(self, messages: list) -> str:
        headers = {
            "Authorization": f"Bearer {self.keys[self.current_key_index]}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 4000,
        }
        resp = requests.post(
            GROQ_API_URL,
            headers=headers,
            data=json.dumps(payload, ensure_ascii=True).encode("utf-8"),
            timeout=60,
        )
        if resp.status_code == 429:
            raise ConnectionError("rate limit")
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def _clean_json(self, text: str) -> str:
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*", "", text)
        return text.strip()

    def _extract_json(self, text: str) -> Dict:
        cleaned = self._clean_json(text)
        match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if match:
            json_str = match.group(1)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                try:
                    fixed = re.sub(r"'", '"', json_str)
                    return json.loads(fixed)
                except:
                    pass
                raise ValueError(f"JSON parse xetasi: {e}\nMetn: {json_str[:200]}")
        raise ValueError("JSON obyekti tapilmadi.")

    def _build_prompt(self, raw_text: str) -> str:
        return (
            "Sen futbol statistikasini tehlil eden bir parsersen. "
            "Asagida verilmis metni tehlil ederek asagida gosterilen JSON strukturuna cevir. "
            "Hec bir elave metn yazma, yalniz JSON obyekti qaytar.\n\n"
            "JSON strukturu:\n"
            "{\n"
            '  "ev_sahibi": "string",\n'
            '  "qonaq": "string",\n'
            '  "lig": "string",\n'
            '  "tarix": "YYYY-MM-DD",\n'
            '  "ortalama_qol_ev": 0.0,\n'
            '  "ortalama_qol_qonaq": 0.0,\n'
            '  "ortalama_korner_ev": 0.0,\n'
            '  "ortalama_korner_qonaq": 0.0,\n'
            '  "ortalama_sot_ev": 0.0,\n'
            '  "ortalama_sot_qonaq": 0.0,\n'
            '  "ortalama_faul_ev": 0.0,\n'
            '  "ortalama_faul_qonaq": 0.0,\n'
            '  "ortalama_sari_kart_ev": 0.0,\n'
            '  "ortalama_sari_kart_qonaq": 0.0,\n'
            '  "ortalama_qirmizi_kart_ev": 0.0,\n'
            '  "ortalama_qirmizi_kart_qonaq": 0.0,\n'
            '  "ortalama_ofsayt_ev": 0.0,\n'
            '  "ortalama_ofsayt_qonaq": 0.0,\n'
            '  "ortalama_aut_ev": 0.0,\n'
            '  "ortalama_aut_qonaq": 0.0,\n'
            '  "ortalama_qapidan_zerbe_ev": 0.0,\n'
            '  "ortalama_qapidan_zerbe_qonaq": 0.0,\n'
            '  "ortalama_penalti_ev": 0.0,\n'
            '  "ortalama_penalti_qonaq": 0.0,\n'
            '  "btts_faiz": 0.0,\n'
            '  "over_1_5_faiz": 0.0,\n'
            '  "over_2_5_faiz": 0.0,\n'
            '  "over_3_5_faiz": 0.0,\n'
            '  "h2h_qeyd": "string",\n'
            '  "son_form_ev": "string",\n'
            '  "son_form_qonaq": "string",\n'
            '  "ev_qol_sayisi_son_5": 0,\n'
            '  "qonaq_qol_sayisi_son_5": 0,\n'
            '  "ev_buraxilan_qol_son_5": 0,\n'
            '  "qonaq_buraxilan_qol_son_5": 0\n'
            "}\n\n"
            f"Metn:\n{raw_text}\n\n"
            "Yalniz JSON obyektini qaytar."
        )

    def parse(self, raw_text: str) -> Dict[str, Any]:
        if not raw_text or not raw_text.strip():
            raise ValueError("Bos metn gonderildi.")

        prompt = self._build_prompt(raw_text)
        messages = [
            {"role": "system", "content": "Sen bir JSON parsersen. Yalniz JSON cixisi et."},
            {"role": "user", "content": prompt},
        ]

        try:
            content = self._call_api(messages)
            return self._extract_json(content)
        except ConnectionError as e:
            if "rate limit" in str(e):
                print("Rate limit askarlandı, key deyisdirilir...")
                self._rotate_key()
                return self.parse(raw_text)
            raise
        except Exception as e:
            raise RuntimeError(f"Parser xetasi: {str(e)}")


def parse_soccer_stats(raw_text: str) -> Dict[str, Any]:
    parser = SoccerStatsParser()
    return parser.parse(raw_text)


if __name__ == "__main__":
    sample_text = (
        "Manchester United vs Liverpool\n"
        "Premier League\n"
        "Son 5 oyun: United: QMBMQ, Liverpool: MQBMQ\n"
        "United evde ortalama 1.8 qol atir, 1.1 buraxir.\n"
        "Liverpool seferde ortalama 2.0 qol atir, 0.9 buraxir.\n"
        "Over 2.5 faiz: 65%\n"
        "BTTS faiz: 54%\n"
        "Korner ortalama: United 5.3, Liverpool 6.1\n"
    )
    try:
        result = parse_soccer_stats(sample_text)
        # ensure_ascii=True: xususi herf olmadan ASCII formatinda yaz
        output = json.dumps(result, indent=2, ensure_ascii=True)
        sys.stdout.buffer.write(output.encode("utf-8") + b"\n")
    except Exception as e:
        print("Test xetasi:", e)