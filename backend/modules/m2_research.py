import json
import requests
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import GROQ_KEY_M2, MODEL_M2, TAVILY_KEY, SERPER_KEY
from groq import Groq

client = Groq(api_key=GROQ_KEY_M2)

# ─────────────────────────────────────────
#  AXTARIŞ SISTEMI
# ─────────────────────────────────────────

def tavily_axtar(query: str) -> str:
    try:
        headers = {"Content-Type": "application/json"}
        body = {
            "api_key": TAVILY_KEY,
            "query": query,
            "search_depth": "basic",
            "max_results": 5
        }
        r = requests.post(
            "https://api.tavily.com/search",
            json=body, headers=headers, timeout=10
        )
        data = r.json()
        results = data.get("results", [])
        if not results:
            return None
        text = ""
        for item in results[:4]:
            text += f"Başlıq: {item.get('title','')}\n"
            text += f"Məzmun: {item.get('content','')[:400]}\n\n"
        return text
    except Exception:
        return None

def serper_axtar(query: str) -> str:
    try:
        headers = {
            "X-API-KEY": SERPER_KEY,
            "Content-Type": "application/json"
        }
        body = {"q": query, "num": 5}
        r = requests.post(
            "https://google.serper.dev/search",
            json=body, headers=headers, timeout=10
        )
        data = r.json()
        items = data.get("organic", [])
        if not items:
            return None
        text = ""
        for item in items[:4]:
            text += f"Başlıq: {item.get('title','')}\n"
            text += f"Snippet: {item.get('snippet','')}\n\n"
        return text
    except Exception:
        return None

def axtar(query: str) -> tuple:
    """Tavily cəhd et, olmasa Serper, olmasa tapılmadı"""
    result = tavily_axtar(query)
    if result:
        return result, "tavily"
    result = serper_axtar(query)
    if result:
        return result, "serper"
    return None, "tapilmadi"


# ─────────────────────────────────────────
#  AXTARIŞ SORĞULARI
# ─────────────────────────────────────────

def axtaris_sorğulari(parser_json: dict) -> dict:
    ev_ad   = parser_json.get("ev", {}).get("ad", "")
    qon_ad  = parser_json.get("qonaq", {}).get("ad", "")
    liqa    = parser_json.get("oyun_info", {}).get("liqa") or \
              parser_json.get("ev", {}).get("liqa", "")
    tarix   = parser_json.get("oyun_info", {}).get("tarix", "")

    sorğular = {
        "travma_ev":     f"{ev_ad} injury news {tarix}",
        "travma_qonaq":  f"{qon_ad} injury news {tarix}",
        "lineup_ev":     f"{ev_ad} lineup {tarix}",
        "lineup_qonaq":  f"{qon_ad} lineup {tarix}",
        "hakim":         f"{ev_ad} vs {qon_ad} referee {tarix}",
        "mesqci_ev":     f"{ev_ad} manager tactics {tarix}",
        "mesqci_qonaq":  f"{qon_ad} manager tactics {tarix}",
        "xeberler":      f"{ev_ad} vs {qon_ad} preview {tarix}"
    }
    return sorğular


# ─────────────────────────────────────────
#  GROQ ANALİZ
# ─────────────────────────────────────────

M2_PROMPT = """
Sən futbol araşdırma agentisən.
Verilən axtarış nəticələrini analiz et və aşağıdakı JSON-u doldur.

QAYDALAR:
- status: "real" → internetdən tapılıb
- status: "təxmin" → məntiqə görə çıxarılıb
- status: "tapılmadı" → məlumat yoxdur
- confidence: 0.0–1.0
- HEÇ VAXT uydurma yazma
- confidence < 0.5 olan məlumatları "tapılmadı" kimi işarələ

JSON strukturu (YALNIZ JSON qaytar):
{
  "hakim": {"ad": null, "status": "tapılmadı", "confidence": 0.0},
  "hakim_sertlik": {"value": null, "status": "tapılmadı", "confidence": 0.0},
  "hakim_kart_ort": {"value": null, "status": "tapılmadı", "confidence": 0.0},
  "hakim_penalti_tezliyi": {"value": null, "status": "tapılmadı", "confidence": 0.0},
  "hakim_var_tezliyi": {"value": null, "status": "tapılmadı", "confidence": 0.0},
  "ev_mesqci": {"ad": null, "taktika_tipi": null, "status": "tapılmadı", "confidence": 0.0},
  "qonaq_mesqci": {"ad": null, "taktika_tipi": null, "status": "tapılmadı", "confidence": 0.0},
  "ev_mesqci_danisiq": {"value": null, "status": "tapılmadı", "confidence": 0.0},
  "qonaq_mesqci_danisiq": {"value": null, "status": "tapılmadı", "confidence": 0.0},
  "travma_ev": {"oyuncular": [], "status": "tapılmadı", "confidence": 0.0},
  "travma_qonaq": {"oyuncular": [], "status": "tapılmadı", "confidence": 0.0},
  "lineup_ev": {"heyat": [], "status": "tapılmadı", "confidence": 0.0},
  "lineup_qonaq": {"heyat": [], "status": "tapılmadı", "confidence": 0.0},
  "rotasiya_ev": {"value": false, "status": "tapılmadı", "confidence": 0.0},
  "rotasiya_qonaq": {"value": false, "status": "tapılmadı", "confidence": 0.0},
  "stadion": {"ad": null, "status": "tapılmadı", "confidence": 0.0},
  "hava": {"value": null, "status": "tapılmadı", "confidence": 0.0},
  "m2_confidence_total": 0.0
}
"""

def groq_analiz(axtaris_metn: str, ev_ad: str, qon_ad: str) -> dict:
    try:
        response = client.chat.completions.create(
            model=MODEL_M2,
            messages=[
                {"role": "system", "content": M2_PROMPT},
                {"role": "user", "content": f"""
Ev komandası: {ev_ad}
Qonaq komandası: {qon_ad}

AXTARIŞ NƏTİCƏLƏRİ:
{axtaris_metn}
"""}
            ],
            temperature=0.1,
            max_tokens=3000
        )
        content = response.choices[0].message.content.strip()

        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return None
    except Exception as e:
        return None


# ─────────────────────────────────────────
#  GÜVƏN HESABI /10
# ─────────────────────────────────────────

def hesabla_m2_guveni(m2_data: dict) -> float:
    if not m2_data:
        return 0.0

    vacib = [
        "hakim", "hakim_sertlik",
        "ev_mesqci", "qonaq_mesqci",
        "travma_ev", "travma_qonaq",
        "lineup_ev", "lineup_qonaq",
        "rotasiya_ev", "rotasiya_qonaq"
    ]

    tapilan = sum(
        1 for k in vacib
        if m2_data.get(k, {}).get("status") == "real"
    )

    # 0-4 bal: tapılan məlumat sayı
    say_bal = min(4.0, tapilan * 0.8)

    # 0-3 bal: ortalama confidence
    conf_list = [
        m2_data.get(k, {}).get("confidence", 0.0)
        for k in vacib
    ]
    ort_conf = sum(conf_list) / len(conf_list) if conf_list else 0
    menbe_bal = ort_conf * 3

    # 0-3 bal: vacib məlumat (hakim + mesqci)
    vacib_bal = 0.0
    if m2_data.get("hakim", {}).get("confidence", 0) >= 0.7:
        vacib_bal += 1.5
    if m2_data.get("ev_mesqci", {}).get("confidence", 0) >= 0.7:
        vacib_bal += 0.75
    if m2_data.get("qonaq_mesqci", {}).get("confidence", 0) >= 0.7:
        vacib_bal += 0.75

    total = round(min(10.0, say_bal + menbe_bal + vacib_bal), 2)
    return total


# ─────────────────────────────────────────
#  ANA FUNKSIYA
# ─────────────────────────────────────────

def run_m2(parser_json: dict) -> dict:
    ev_ad  = parser_json.get("ev", {}).get("ad", "Ev komandası")
    qon_ad = parser_json.get("qonaq", {}).get("ad", "Qonaq komandası")

    sorğular = axtaris_sorğulari(parser_json)

    # Bütün axtarışları topla
    toplam_metn = ""
    axtaris_statuslari = {}

    for key, sorğu in sorğular.items():
        metn, menbe = axtar(sorğu)
        axtaris_statuslari[key] = menbe
        if metn:
            toplam_metn += f"\n=== {key.upper()} ===\n{metn}\n"

    if not toplam_metn.strip():
        return {
            "success": False,
            "data": None,
            "guveni": 0.0,
            "axtaris_statuslari": axtaris_statuslari,
            "qeyd": "Heç bir axtarış nəticəsi tapılmadı"
        }

    # Groq analiz
    m2_data = groq_analiz(toplam_metn, ev_ad, qon_ad)

    if not m2_data:
        return {
            "success": False,
            "data": None,
            "guveni": 0.0,
            "axtaris_statuslari": axtaris_statuslari,
            "qeyd": "Groq analiz uğursuz oldu"
        }

    guveni = hesabla_m2_guveni(m2_data)
    m2_data["m2_confidence_total"] = guveni

    return {
        "success": True,
        "data": m2_data,
        "guveni": guveni,
        "axtaris_statuslari": axtaris_statuslari
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
