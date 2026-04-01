import json
import re
from groq import Groq
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import GROQ_KEY_PARSER, MODEL_PARSER

client = Groq(api_key=GROQ_KEY_PARSER)

PARSER_PROMPT = """
Sen SoccerStats məlumatini oxuyan parser-sən.
Verilən mətndən aşağidaki JSON strukturunu cixar.
Məlumat varsa doldur, yoxdursa null qoy.
HEÇ VAXT uydurma — yalniz mətndə olan məlumati yaz.

JSON strukturu:
{
  "ev": {
    "ad": null,
    "ppg": {"ev": null, "umumi": null, "son8": null},
    "ppi": null,
    "pr": null,
    "qol_vurdu": null,
    "qol_buraxdi": null,
    "over15": null,
    "over25": null,
    "over35": null,
    "bts": null,
    "corner_ort": null,
    "sot_ort": null,
    "faul_ort": null,
    "kart_ort": null,
    "ofsayt_ort": null,
    "aut_ort": null,
    "qapidan_zerbe_ort": null,
    "ht_statistika": {},
    "qol_vaxt": {
      "0_15": null, "16_30": null, "31_45": null,
      "46_60": null, "61_75": null, "76_90": null,
      "ilk_yari": null, "ikinci_yari": null
    },
    "forma_son8": [],
    "cedvel_sirasi": null,
    "liqa": null
  },
  "qonaq": {
    "ad": null,
    "ppg": {"ev": null, "umumi": null, "son8": null},
    "ppi": null,
    "pr": null,
    "qol_vurdu": null,
    "qol_buraxdi": null,
    "over15": null,
    "over25": null,
    "over35": null,
    "bts": null,
    "corner_ort": null,
    "sot_ort": null,
    "faul_ort": null,
    "kart_ort": null,
    "ofsayt_ort": null,
    "aut_ort": null,
    "qapidan_zerbe_ort": null,
    "ht_statistika": {},
    "qol_vaxt": {
      "0_15": null, "16_30": null, "31_45": null,
      "46_60": null, "61_75": null, "76_90": null,
      "ilk_yari": null, "ikinci_yari": null
    },
    "forma_son8": [],
    "cedvel_sirasi": null,
    "liqa": null
  },
  "liqa_ortalama": {
    "qol_ort": null,
    "over15": null,
    "over25": null,
    "over35": null,
    "bts": null,
    "corner_ort": null
  },
  "h2h": {
    "oyunlar": [],
    "ev_qelebe": null,
    "beraberlik": null,
    "qonaq_qelebe": null,
    "ort_qol": null
  },
  "oyun_info": {
    "tarix": null,
    "liqa": null,
    "stadion": null
  }
}

YALNIZ JSON qaytar. Heç bir izah yazma.
"""

def split_text(text: str, chunk_size: int = 3000) -> list:
    """Mətni hissələrə böl"""
    words = text.split()
    chunks = []
    current = []
    current_len = 0
    
    for word in words:
        current_len += len(word) + 1
        current.append(word)
        if current_len >= chunk_size:
            chunks.append(" ".join(current))
            current = []
            current_len = 0
    
    if current:
        chunks.append(" ".join(current))
    
    return chunks


def parse_chunk(chunk: str) -> dict:
    """Bir hissəni parse et"""
    try:
        response = client.chat.completions.create(
            model=MODEL_PARSER,
            messages=[
                {"role": "system", "content": PARSER_PROMPT},
                {"role": "user", "content": chunk}
            ],
            temperature=0.1,
            max_tokens=4000
        )
        content = response.choices[0].message.content.strip()
        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return {}
    except:
        return {}


def merge_results(results: list) -> dict:
    """Hissələrin nəticələrini birləşdir"""
    final = {}
    for result in results:
        for key, value in result.items():
            if key not in final:
                final[key] = value
            elif isinstance(value, dict) and isinstance(final[key], dict):
                for k, v in value.items():
                    if v is not None and (k not in final[key] or final[key][k] is None):
                        final[key][k] = v
    return final


def parse_statistics(raw_text: str) -> dict:
    try:
        chunks = split_text(raw_text)
        results = []
        
        for chunk in chunks:
            result = parse_chunk(chunk)
            if result:
                results.append(result)
        
        if not results:
            return {"success": False, "error": "Heç bir məlumat oxunmadı"}
        
        final_data = merge_results(results)
        return {"success": True, "data": final_data}
        
    except Exception as e:
        return {"success": False, "error": f"Xəta: {str(e)}"}

print(json.dumps(test, ensure_ascii=False, indent=2))
