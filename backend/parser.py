import json
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

def parse_statistics(raw_text: str) -> dict:
    try:
        response = client.chat.completions.create(
            model=MODEL_PARSER,
            messages=[
                {"role": "system", "content": PARSER_PROMPT},
                {"role": "user", "content": raw_text}
            ],
            temperature=0.1,
            max_tokens=4000
        )
        
        content = response.choices[0].message.content.strip()
        
        # JSON təmizlə
        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            content = json_match.group()
        else:
            return {"success": False, "error": "JSON tapılmadı"}
        
        result = json.loads(content)
        return {"success": True, "data": result}
        
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON xətası: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": f"Xəta: {str(e)}"}


if __name__ == "__main__":
    # Test üçün
    test_text = """
    Mirandes vs Albacete
    LaLiga2
    PPG Home: 0.94, Away: 1.31, Total: 1.34
    """
    result = parse_statistics(test_text)
    print(json.dumps(result, ensure_ascii=False, indent=2))

