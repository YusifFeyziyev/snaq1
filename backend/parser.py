import json
import re
import os
import sys
import logging
from groq import Groq

# Ana qovluğu əlavə etmək
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import GROQ_KEY_PARSER, MODEL_PARSER

log = logging.getLogger(__name__)
client = Groq(api_key=GROQ_KEY_PARSER)

PARSER_PROMPT = """
Sən SoccerStats məlumatını oxuyan peşəkar parser-sən.
Verilən mətndən aşağıdakı JSON strukturunu çıxar. 
Məlumat varsa doldur, yoxdursa null saxla. 
Yalnız mətndə olan faktiki məlumatları istifadə et, özündən rəqəm uydurma.

QAYDA: 
1. Mətn hissə-hissə gələ bilər, gördüyün sahələri doldur.
2. YALNIZ JSON qaytar. Markdown blokları (```json) istifadə etmə.
3. Faiz işarələrini (%) sil, yalnız rəqəmləri saxla.

JSON strukturu:
{
  "ev": {
    "ad": null,
    "ppg": {"ev": null, "umumi": null, "son8": null},
    "ppi": null, "pr": null,
    "qol_vurdu": null, "qol_buraxdi": null,
    "over15": null, "over25": null, "over35": null, "bts": null,
    "corner_ort": null, "sot_ort": null, "faul_ort": null,
    "kart_ort": null, "ofsayt_ort": null, "aut_ort": null,
    "qapidan_zerbe_ort": null, "ht_statistika": {},
    "qol_vaxt": {
      "0_15": null, "16_30": null, "31_45": null, "46_60": null,
      "61_75": null, "76_90": null, "ilk_yari": null, "ikinci_yari": null
    },
    "forma_son8": [], "cedvel_sirasi": null, "liqa": null
  },
  "qonaq": {
    "ad": null,
    "ppg": {"qonaq": null, "umumi": null, "son8": null},
    "ppi": null, "pr": null,
    "qol_vurdu": null, "qol_buraxdi": null,
    "over15": null, "over25": null, "over35": null, "bts": null,
    "corner_ort": null, "sot_ort": null, "faul_ort": null,
    "kart_ort": null, "ofsayt_ort": null, "aut_ort": null,
    "qapidan_zerbe_ort": null, "ht_statistika": {},
    "qol_vaxt": {
      "0_15": null, "16_30": null, "31_45": null, "46_60": null,
      "61_75": null, "76_90": null, "ilk_yari": null, "ikinci_yari": null
    },
    "forma_son8": [], "cedvel_sirasi": null, "liqa": null
  },
  "liqa_ortalama": {
    "qol_ort": null, "over15": null, "over25": null, "over35": null, "bts": null, "corner_ort": null
  },
  "h2h": {
    "oyunlar": [], "ev_qelebe": null, "beraberlik": null, "qonaq_qelebe": null, "ort_qol": null
  },
  "oyun_info": { "tarix": null, "liqa": null, "stadion": null }
}
"""

def split_text(text: str, chunk_size: int = 8000) -> list:
    """Mətni daha böyük hissələrə böl (Llama 3.3 üçün optimallaşdırılıb)"""
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    lines = text.split('\n')
    current_chunk = []
    current_len = 0
    
    for line in lines:
        if current_len + len(line) > chunk_size and current_chunk:
            chunks.append("\n".join(current_chunk))
            current_chunk = []
            current_len = 0
        current_chunk.append(line)
        current_len += len(line)
        
    if current_chunk:
        chunks.append("\n".join(current_chunk))
    return chunks

def parse_chunk(chunk: str) -> dict:
    """Bir hissəni Llama vasitəsilə parse et"""
    try:
        response = client.chat.completions.create(
            model=MODEL_PARSER,
            messages=[
                {"role": "system", "content": PARSER_PROMPT},
                {"role": "user", "content": f"Aşağıdakı mətni parse et:\n\n{chunk}"}
            ],
            temperature=0, # Daha dəqiq rəqəmlər üçün 0
        )
        content = response.choices[0].message.content.strip()
        
        # Markdown və lazımsız yazıları təmizlə
        content = re.sub(r'```json\s*|\s*```', '', content)
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        
        if json_match:
            return json.loads(json_match.group())
        return {}
    except Exception as e:
        log.error(f"Chunk parse xətası: {e}")
        return {}

def deep_merge(target, source):
    """İki lüğəti (dict) dərindən birləşdirir"""
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            deep_merge(target[key], value)
        elif value is not None:
            # Siyahıları birləşdir, digərlərini yenilə
            if isinstance(value, list) and key in target and isinstance(target[key], list):
                target[key] = list(set(target[key] + value))
            else:
                target[key] = value
    return target

def parse_statistics(raw_text: str) -> dict:
    """Əsas giriş funksiyası"""
    try:
        if not raw_text.strip():
            return {"success": False, "error": "Daxil edilən mətn boşdur"}

        chunks = split_text(raw_text)
        final_data = {}
        
        for chunk in chunks:
            chunk_res = parse_chunk(chunk)
            if chunk_res:
                if not final_data:
                    final_data = chunk_res
                else:
                    final_data = deep_merge(final_data, chunk_res)
        
        if not final_data or not final_data.get("ev", {}).get("ad"):
            return {"success": False, "error": "Məlumat oxuna bilmədi. Formatı yoxlayın."}
            
        return {"success": True, "data": final_data}
        
    except Exception as e:
        log.error(f"Ümumi Parser xətası: {e}")
        return {"success": False, "error": str(e)}