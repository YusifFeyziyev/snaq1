import os
import json
import re
import requests
from groq import Groq

# ─────────────────────────────────────────
#  CONFIG IMPORT
# ─────────────────────────────────────────
try:
    from config import MODEL_M2, GROQ_KEY_M2, TAVILY_KEY, SERPER_KEY
except ImportError:
    MODEL_M2   = os.environ.get("MODEL_M2",    "llama-3.3-70b-versatile")
    GROQ_KEY_M2 = os.environ.get("GROQ_KEY_M2", "")
    TAVILY_KEY  = os.environ.get("TAVILY_KEY",  "")
    SERPER_KEY  = os.environ.get("SERPER_KEY",  "")

client = Groq(api_key=GROQ_KEY_M2)

# ─────────────────────────────────────────
#  M2 SYSTEM PROMPTU
# ─────────────────────────────────────────
M2_PROMPT = """Sən futbol analiz sistemi üçün araşdırma agentisən.
Sənə axtarış nəticələri veriləcək. Bu nəticələrə əsasən aşağıdakı JSON strukturunu doldur.

QAYDALAR:
- status: "real" → internetdən tapılıb, "təxmin" → məntiqə görə çıxarılıb, "tapılmadı" → məlumat yoxdur
- confidence: 0.0–1.0 arası
- Heç vaxt uydurma. Olmayan məlumatı "tapılmadı" et.
- YALNIZ JSON qaytar, başqa heç nə yazma.

ÇIXIŞ FORMATI (yalnız bu JSON):
{
  "hakim": {"value": null, "status": "tapılmadı", "confidence": 0.0},
  "hakim_sertlik": {"value": null, "status": "tapılmadı", "confidence": 0.0},
  "hakim_kart_ort": {"value": null, "status": "tapılmadı", "confidence": 0.0},
  "hakim_penalti_tezliyi": {"value": null, "status": "tapılmadı", "confidence": 0.0},
  "hakim_var_tezliyi": {"value": null, "status": "tapılmadı", "confidence": 0.0},
  "ev_mesqci": {"value": null, "status": "tapılmadı", "confidence": 0.0},
  "ev_taktika": {"value": null, "status": "tapılmadı", "confidence": 0.0},
  "ev_oyun_oncesi": {"value": null, "status": "tapılmadı", "confidence": 0.0},
  "qonaq_mesqci": {"value": null, "status": "tapılmadı", "confidence": 0.0},
  "qonaq_taktika": {"value": null, "status": "tapılmadı", "confidence": 0.0},
  "qonaq_oyun_oncesi": {"value": null, "status": "tapılmadı", "confidence": 0.0},
  "travma_ev": {"value": null, "status": "tapılmadı", "confidence": 0.0},
  "travma_qonaq": {"value": null, "status": "tapılmadı", "confidence": 0.0},
  "lineup_ev": {"value": null, "status": "tapılmadı", "confidence": 0.0},
  "lineup_qonaq": {"value": null, "status": "tapılmadı", "confidence": 0.0},
  "rotasiya_ev": {"value": false, "status": "tapılmadı", "confidence": 0.0},
  "rotasiya_qonaq": {"value": false, "status": "tapılmadı", "confidence": 0.0},
  "stadion": {"value": null, "status": "tapılmadı", "confidence": 0.0},
  "hava": {"value": null, "status": "tapılmadı", "confidence": 0.0},
  "motivasiya_ev": {"value": null, "status": "tapılmadı", "confidence": 0.0},
  "motivasiya_qonaq": {"value": null, "status": "tapılmadı", "confidence": 0.0}
}"""

# ─────────────────────────────────────────
#  AXTARIŞ SORĞULARI
# ─────────────────────────────────────────
def axtaris_sorğulari(parser_json: dict) -> dict:
    ev  = parser_json.get("ev",    {}).get("ad", "")
    qon = parser_json.get("qonaq", {}).get("ad", "")
    liqa = parser_json.get("oyun_info", {}).get("liqa", "")

    return {
        "hakim":         f"{ev} vs {qon} referee {liqa}",
        "travma_ev":     f"{ev} injury news team news",
        "travma_qonaq":  f"{qon} injury news team news",
        "lineup_ev":     f"{ev} predicted lineup starting XI",
        "lineup_qonaq":  f"{qon} predicted lineup starting XI",
        "mesqci_ev":     f"{ev} manager tactics press conference",
        "mesqci_qonaq":  f"{qon} manager tactics press conference",
    }

# ─────────────────────────────────────────
#  TAVILY AXTARIŞI
# ─────────────────────────────────────────
def tavily_axtar(sorğu: str) -> str | None:
    if not TAVILY_KEY:
        return None
    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_KEY,
                "query":   sorğu,
                "max_results": 3,
                "search_depth": "basic"
            },
            timeout=15
        )
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            if results:
                return "\n".join(
                    f"- {r.get('title','')}: {r.get('content','')[:300]}"
                    for r in results
                )
        elif resp.status_code == 429:
            return "LIMIT"
    except Exception:
        pass
    return None

# ─────────────────────────────────────────
#  SERPER AXTARIŞI (fallback)
# ─────────────────────────────────────────
def serper_axtar(sorğu: str) -> str | None:
    if not SERPER_KEY:
        return None
    try:
        resp = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"},
            json={"q": sorğu, "num": 3},
            timeout=15
        )
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("organic", [])
            if items:
                return "\n".join(
                    f"- {i.get('title','')}: {i.get('snippet','')}"
                    for i in items
                )
        elif resp.status_code == 429:
            return "LIMIT"
    except Exception:
        pass
    return None

# ─────────────────────────────────────────
#  ƏSAS AXTAR FUNKSİYASI (Tavily → Serper → tapılmadı)
# ─────────────────────────────────────────
def axtar(sorğu: str) -> tuple[str | None, str]:
    """
    Qaytarır: (mətn | None, mənbə)
    mənbə: "tavily" | "serper" | "tapılmadı"
    """
    # 1. Tavily cəhdi
    nəticə = tavily_axtar(sorğu)
    if nəticə and nəticə != "LIMIT":
        return nəticə, "tavily"

    # 2. Serper cəhdi (Tavily limit və ya uğursuz)
    nəticə = serper_axtar(sorğu)
    if nəticə and nəticə != "LIMIT":
        return nəticə, "serper"

    return None, "tapılmadı"

# ─────────────────────────────────────────
#  GROQ ANALİZ
# ─────────────────────────────────────────
def groq_analiz(axtaris_metn: str, ev_ad: str, qon_ad: str) -> dict | None:
    try:
        response = client.chat.completions.create(
            model=MODEL_M2,
            messages=[
                {"role": "system", "content": M2_PROMPT},
                {"role": "user", "content": (
                    f"Ev komandası: {ev_ad}\n"
                    f"Qonaq komandası: {qon_ad}\n\n"
                    f"AXTARIŞ NƏTİCƏLƏRİ:\n{axtaris_metn}"
                )}
            ],
            temperature=0.1,
            max_tokens=3000,
            timeout=120
        )
        content = response.choices[0].message.content.strip()

        # JSON-u təmizlə (code block varsa sil)
        content = re.sub(r"```(?:json)?", "", content).strip().rstrip("`")

        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())

    except Exception as e:
        print(f"[M2] Groq xətası: {e}")

    return None

# ─────────────────────────────────────────
#  GÜVƏN HESABI /10
# ─────────────────────────────────────────
def hesabla_m2_guveni(m2_data: dict) -> float:
    if not m2_data:
        return 0.0

    vacib_saheler = [
        "hakim", "hakim_sertlik",
        "ev_mesqci", "qonaq_mesqci",
        "travma_ev", "travma_qonaq",
        "lineup_ev", "lineup_qonaq",
        "rotasiya_ev", "rotasiya_qonaq"
    ]

    # 0–4 bal: tapılan "real" məlumat sayı
    tapilan = sum(
        1 for k in vacib_saheler
        if m2_data.get(k, {}).get("status") == "real"
    )
    say_bal = min(4.0, tapilan * 0.8)

    # 0–3 bal: ortalama confidence
    conf_list = [
        m2_data.get(k, {}).get("confidence", 0.0)
        for k in vacib_saheler
    ]
    ort_conf = sum(conf_list) / len(conf_list) if conf_list else 0.0
    menbe_bal = ort_conf * 3.0

    # 0–3 bal: vacib məlumatların dolğunluğu
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
    ev_ad  = parser_json.get("ev",    {}).get("ad", "Ev komandası")
    qon_ad = parser_json.get("qonaq", {}).get("ad", "Qonaq komandası")

    sorğular = axtaris_sorğulari(parser_json)

    toplam_metn       = ""
    axtaris_statuslari = {}

    for key, sorğu in sorğular.items():
        metn, menbe = axtar(sorğu)
        axtaris_statuslari[key] = menbe
        if metn:
            toplam_metn += f"\n=== {key.upper()} ===\n{metn}\n"

    # Heç nə tapılmadısa
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