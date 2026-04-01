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

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

# --- App ---
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# --- Log qovluğu ---
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)


# ─────────────────────────────────────────
# Analiz nəticəsini fayla yaz (kalibrasiya)
# ─────────────────────────────────────────
def save_log(parser_json, m1, m2, m3, m4):
    try:
        ev  = parser_json.get("ev",    {}).get("ad", "?")
        qon = parser_json.get("qonaq", {}).get("ad", "?")
        ts  = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        name = f"{ts}_{ev}_vs_{qon}.json".replace(" ", "_")
        path = os.path.join(LOG_DIR, name)

        record = {
            "timestamp":        ts,
            "match":            f"{ev} vs {qon}",
            "m1_confidence":    m1.get("guveni", {}).get("total"),
            "m2_confidence":    m2.get("m2_guveni"),
            "m3_confidence":    m3.get("m3_guveni"),
            "m4_sistem_guveni": m4.get("sistem_guveni"),
            "m4_qerar_guveni":  m4.get("qerar_guveni"),
            "oynarim":          m4.get("oynarim"),
            "m4_full":          m4,
            "real_netice":      None  # kalibrasiya üçün sonra doldurulur
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)

        log.info(f"Log saxlandı: {name}")
    except Exception as e:
        log.warning(f"Log xətası: {e}")


# ─────────────────────────────────────────
# POST /analyze
# ─────────────────────────────────────────
@app.route("/analyze", methods=["POST"])
def analyze():

    # Giriş yoxlaması
    body = request.get_json(silent=True)
    if not body or "statistics" not in body:
        return jsonify({"success": False, "error": "statistics sahəsi lazımdır"}), 400

    raw_text = body["statistics"].strip()
    if not raw_text:
        return jsonify({"success": False, "error": "Statistika mətni boşdur"}), 400

    # ── 1. PARSER ──
    try:
        log.info("Parser başladı...")
        parser_json = parse_statistics(raw_text)
        log.info("Parser tamamlandı.")
    except Exception as e:
        log.error(f"Parser xətası: {e}")
        return jsonify({"success": False, "error": f"Parser xətası: {str(e)}"}), 500

    # ── 2. M1 + M2 PARALEL ──
    m1_result = {}
    m2_result = {}
    m1_error  = []
    m2_error  = []

    def run_m1_thread():
        try:
            log.info("M1 başladı...")
            m1_result.update(run_m1(parser_json))
            log.info("M1 tamamlandı.")
        except Exception as e:
            log.error(f"M1 xətası: {e}")
            m1_error.append(str(e))

    def run_m2_thread():
        try:
            log.info("M2 başladı...")
            m2_result.update(run_m2(parser_json))
            log.info("M2 tamamlandı.")
        except Exception as e:
            log.error(f"M2 xətası: {e}")
            m2_error.append(str(e))

    t1 = threading.Thread(target=run_m1_thread)
    t2 = threading.Thread(target=run_m2_thread)
    t1.start(); t2.start()
    t1.join();  t2.join()

    # M1 kritikdir — xəta varsa dayandır
    if m1_error:
        return jsonify({"success": False, "error": f"M1 xətası: {m1_error[0]}"}), 500

    # M2 boş qaldısa → weight=0 flag-i ilə davam
    if m2_error or not m2_result:
        log.warning("M2 boş qaldı — M2 weight=0 ilə davam edilir.")
        m2_result = {
            "m2_guveni": 0,
            "m2_bos":    True,
            "xeta":      m2_error[0] if m2_error else "M2 nəticə qaytarmadı"
        }
    else:
        m2_result.setdefault("m2_bos", False)

    # ── 3. M3 (M2 bitdikdən sonra) ──
    try:
        log.info("M3 başladı...")
        m3_result = run_m3(parser_json, m2_result)
        log.info("M3 tamamlandı.")
    except Exception as e:
        log.error(f"M3 xətası: {e}")
        return jsonify({"success": False, "error": f"M3 xətası: {str(e)}"}), 500

    # ── 4. M4 (M1 + M3 hər ikisi hazır) ──
    try:
        log.info("M4 başladı...")
        m4_result = run_m4(m1_result, m2_result, m3_result, parser_json)
        m4_result = m4_result.get("data", m4_result) if isinstance(m4_result, dict) and "data" in m4_result else m4_result
        log.info(f"M4 CIXIS: {json.dumps(m4_result, ensure_ascii=False)[:1000]}")
        log.info("M4 tamamlandı.")
    except Exception as e:
        log.error(f"M4 xətası: {e}")
        return jsonify({"success": False, "error": f"M4 xətası: {str(e)}"}), 500

    # ── 5. Log saxla ──
    save_log(parser_json, m1_result, m2_result, m3_result, m4_result)

    # ── 6. Cavab ──
    return jsonify({
        "success": True,
        "m1": m1_result,
        "m2": m2_result,
        "m3": m3_result,
        "m4": m4_result
    })


# ─────────────────────────────────────────
# Health check
# ─────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat()})


# ─────────────────────────────────────────
# Run
# ─────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
