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
CORS(app) # Bütün mənşələrə icazə verilir

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

def save_log(parser_json, m1, m2, m3, m4):
    try:
        ev = parser_json.get("ev", {}).get("ad", "?")
        qon = parser_json.get("qonaq", {}).get("ad", "?")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Fayl adı yaratma
        safe_ev = "".join([c for c in ev if c.isalnum()])
        safe_qon = "".join([c for c in qon if c.isalnum()])
        name = f"{ts}_{safe_ev}_vs_{safe_qon}.json"
        path = os.path.join(LOG_DIR, name)

        record = {
            "timestamp": ts,
            "match": f"{ev} vs {qon}",
            "scores": {
                "m1": m1.get("guveni", {}).get("total") if isinstance(m1.get("guveni"), dict) else m1.get("guveni"),
                "m2": m2.get("guveni"),
                "m3": m3.get("m3_guveni", 0),
                "m4_final": m4.get("final_guveni")
            },
            "oynayiram": m4.get("oynayiram"), # Açar düzəldildi
            "m4_full_decision": m4,
            "raw_parser": parser_json
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)

        log.info(f"Analiz uğurla loqlandı: {name}")
    except Exception as e:
        log.warning(f"Loq yazarkən xəta: {e}")

@app.route("/analyze", methods=["POST"])
def analyze():
    body = request.get_json(silent=True)
    if not body or "statistics" not in body:
        return jsonify({"success": False, "error": "statistics sahəsi lazımdır"}), 400

    raw_text = body["statistics"].strip()
    
    # ── 1. PARSER ──
    log.info("Analiz prosesi başladı...")
    parser_res = parse_statistics(raw_text)
    if not parser_res.get("success"):
        return jsonify({"success": False, "error": parser_res.get("error")}), 500
    
    parser_json = parser_res["data"]

    # ── 2. M1 + M2 PARALEL (Həqiqi Threading) ──
    m1_res, m2_res = {}, {}
    errors = []

    def task_m1():
        try:
            res = run_m1(parser_json)
            m1_res.update(res)
        except Exception as e:
            errors.append(f"M1: {str(e)}")

    def task_m2():
        try:
            res = run_m2(parser_json)
            m2_res.update(res)
        except Exception as e:
            errors.append(f"M2: {str(e)}")

    t1 = threading.Thread(target=task_m1)
    t2 = threading.Thread(target=task_m2)

    t1.start()
    t2.start()

    t1.join() # Hər iki model bitənə qədər gözlə
    t2.join()

    if errors:
        log.error(f"Modul xətaları: {errors}")
        # Kritik deyilsə davam etmək olar, amma m1 kritikdir
        if any("M1" in e for e in errors):
            return jsonify({"success": False, "error": "M1 Riyazi modul çökdü"}), 500

    # ── 3. M3 (Expert) ──
    try:
        m3_res = run_m3(parser_json, m2_res)
    except Exception as e:
        log.error(f"M3 xətası: {e}")
        return jsonify({"success": False, "error": "M3 modulu xətası"}), 500

    # ── 4. M4 (Final Qərar) ──
    try:
        m4_output = run_m4(m1_res, m2_res, m3_res, parser_json)
        if not m4_output.get("success"):
            return jsonify({"success": False, "error": m4_output.get("error")}), 500
        
        m4_final = m4_output["data"]
    except Exception as e:
        log.error(f"M4 xətası: {e}")
        return jsonify({"success": False, "error": "M4 Final qərar modulu xətası"}), 500

    # ── 5. LOG VƏ CAVAB ──
    threading.Thread(target=save_log, args=(parser_json, m1_res, m2_res, m3_res, m4_final)).start()

    return jsonify({
        "success": True,
        "match": f"{parser_json.get('ev', {}).get('ad')} vs {parser_json.get('qonaq', {}).get('ad')}",
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
    return jsonify({"status": "active", "server_time": datetime.now().isoformat()})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)