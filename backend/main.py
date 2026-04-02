import threading
import logging
import json
import os
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

from parser import parse_statistics
from modules.m1_math import run_m1
from modules.m2_research import run_m2
from modules.m3_expert import run_m3
from modules.m4_decision import run_m4

# Loq ayarları
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app) 

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

def save_log(parser_json, m1, m2, m3, m4):
    try:
        ev = parser_json.get("ev", {}).get("ad", "Ev")
        qon = parser_json.get("qonaq", {}).get("ad", "Qonaq")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        safe_ev = "".join([c for c in ev if c.isalnum()])
        safe_qon = "".join([c for c in qon if c.isalnum()])
        name = f"{ts}_{safe_ev}_vs_{safe_qon}.json"
        path = os.path.join(LOG_DIR, name)

        record = {
            "timestamp": ts,
            "match": f"{ev} vs {qon}",
            "scores": {
                "m1": m1.get("guveni"),
                "m2": m2.get("guveni"),
                "m3": m3.get("m3_guveni", 0),
                "m4_final": m4.get("sistem_guveni") or m4.get("final_guveni")
            },
            "oynayiram": m4.get("oynarim") or m4.get("oynayiram"),
            "m4_full_decision": m4
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.warning(f"Loq yazarkən xəta: {e}")

@app.route("/analyze", methods=["POST"])
def analyze():
    # JS-in gözlədiyi standart cavab strukturu
    error_response = lambda msg: jsonify({"success": False, "error": msg, "data": {}})
    
    body = request.get_json(silent=True)
    if not body or "statistics" not in body:
        return error_response("Statistika mətni daxil edilməyib."), 400

    raw_text = body["statistics"].strip()
    
    # ── 1. PARSER ──
    try:
        parser_res = parse_statistics(raw_text)
        if not parser_res.get("success"):
            return error_response(f"Parser xətası: {parser_res.get('error')}"), 500
        parser_json = parser_res["data"]
    except Exception as e:
        return error_response(f"Məlumat oxunarkən gözlənilməz xəta: {str(e)}"), 500

    # ── 2. M1 + M2 PARALEL ──
    m1_res, m2_res = {}, {}
    m1_err, m2_err = None, None

    def task_m1():
        nonlocal m1_err
        try:
            m1_res.update(run_m1(parser_json))
        except Exception as e:
            m1_err = str(e)

    def task_m2():
        nonlocal m2_err
        try:
            m2_res.update(run_m2(parser_json))
        except Exception as e:
            m2_err = str(e)

    t1 = threading.Thread(target=task_m1)
    t2 = threading.Thread(target=task_m2)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    if m1_err: return error_response(f"Riyazi modul (M1) xətası: {m1_err}"), 500

    # ── 3. M3 (Expert) ──
    try:
        m3_res = run_m3(parser_json, m2_res)
    except Exception as e:
        log.error(f"M3 xətası: {e}")
        m3_res = {"m3_guveni": 0, "status": "Error"}

    # ── 4. M4 (Final Qərar) ──
    try:
        m4_output = run_m4(m1_res, m2_res, m3_res, parser_json)
        
        # ƏGƏR M4-dən "data" gəlmirsə, birbaşa m4_output-u götür
        m4_final = m4_output.get("data") if m4_output.get("success") else m4_output
        
        # JS-in başa düşməsi üçün vacib adları (keys) mütləq əlavə edirik
        if "sistem_guveni" not in m4_final:
            m4_final["sistem_guveni"] = m4_final.get("final_guveni") or m4_final.get("guven") or 0
        if "oynarim" not in m4_final:
            m4_final["oynarim"] = m4_final.get("oynayiram") or False

    except Exception as e:
        log.error(f"M4 xətası: {e}")
        return error_response("Final qərar modulu (M4) cavab vermədi."), 500

    # ── 5. CAVAB ──
    # Loq yazmağı arxa planda et (istifadəçini gözlətmə)
    threading.Thread(target=save_log, args=(parser_json, m1_res, m2_res, m3_res, m4_final)).start()

    return jsonify({
        "success": True,
        "data": {
            "parser": parser_json,
            "m1": m1_res,
            "m2": m2_res,
            "m3": m3_res,
            "m4": m4_final
        }
    })

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "active"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)