import os
import sys
import logging
import importlib
import threading
import traceback
from datetime import datetime

from flask import Flask, request, jsonify
from flask_cors import CORS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

parse_soccer_stats = None
run_m1 = None
run_m2 = None
run_m3 = None
run_m4 = None

try:
    _parser_mod = importlib.import_module("parser")
    parse_soccer_stats = _parser_mod.parse_soccer_stats
    logger.info("✓ parser modulu yükləndi")
except Exception as e:
    logger.error(f"✗ parser modulu tapılmadı: {e}")

try:
    from modules.m1_math import run_m1
    logger.info("✓ m1_math modulu yükləndi")
except Exception as e:
    logger.error(f"✗ m1_math modulu tapılmadı: {e}")

try:
    from modules.m2_research import run_m2
    logger.info("✓ m2_research modulu yükləndi")
except Exception as e:
    logger.error(f"✗ m2_research modulu tapılmadı: {e}")

try:
    from modules.m3_expert import run_m3
    logger.info("✓ m3_expert modulu yükləndi")
except Exception as e:
    logger.error(f"✗ m3_expert modulu tapılmadı: {e}")

try:
    from modules.m4_decision import run_m4
    logger.info("✓ m4_decision modulu yükləndi")
except Exception as e:
    logger.error(f"✗ m4_decision modulu tapılmadı: {e}")

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})


# ─────────────────────────────────────────────
# ✅ DÜZƏLİŞ: Parser çıxışını M2/M3 formatına çevir
# ─────────────────────────────────────────────
def normalize_parsed(parsed: dict) -> dict:
    # BUG FIX: parser None qaytararsa crash olmasın
    if not isinstance(parsed, dict):
        logger.error(f"normalize_parsed: gözlənilən dict, gələn: {type(parsed)}")
        parsed = {}
    normalized = dict(parsed)

    if not normalized.get("team1"):
        normalized["team1"] = parsed.get("ev_sahibi", "Unknown")

    if not normalized.get("team2"):
        normalized["team2"] = parsed.get("qonaq", "Unknown")

    if not normalized.get("team1_stats"):
        normalized["team1_stats"] = {
            "avg_goals_scored":   parsed.get("ortalama_qol_ev", 1.5),
            "avg_goals_conceded": parsed.get("ev_buraxilan_qol_son_5", 1.2),
            "attack_strength":    parsed.get("ortalama_sot_ev", 1.0),
            "defense_strength":   parsed.get("ortalama_sot_qonaq", 1.0),
        }

    if not normalized.get("team2_stats"):
        normalized["team2_stats"] = {
            "avg_goals_scored":   parsed.get("ortalama_qol_qonaq", 1.5),
            "avg_goals_conceded": parsed.get("qonaq_buraxilan_qol_son_5", 1.2),
            "attack_strength":    parsed.get("ortalama_sot_qonaq", 1.0),
            "defense_strength":   parsed.get("ortalama_sot_ev", 1.0),
        }

    # BUG FIX: team1_form / team2_form həmişə string olmalıdır
    if not isinstance(normalized.get("team1_form"), str):
        normalized["team1_form"] = ""
    if not isinstance(normalized.get("team2_form"), str):
        normalized["team2_form"] = ""

    logger.info(f"Komandalar: {normalized['team1']} vs {normalized['team2']}")
    return normalized

# ─────────────────────────────────────────────
# ✅ DÜZƏLİŞ 1: Confidence normalizer
# ─────────────────────────────────────────────
def normalize_confidence(val):
    try:
        val = float(val)
        if val <= 1:
            val *= 100   # 0-1 şkalası → 0-100
        elif val <= 10:
            val *= 10    # 0-10 şkalası → 0-100
        return max(0, min(100, val))
    except:
        return 0


def run_m1_m2_parallel(parsed_json: dict) -> tuple:
    m1_result, m2_result = None, None
    m1_error,  m2_error  = None, None

    def _m1():
        nonlocal m1_result, m1_error
        try:
            if run_m1 is None:
                raise RuntimeError("m1_math modulu yüklənməyib")
            m1_result = run_m1(parsed_json)
            logger.info("M1 tamamlandı")
        except Exception as e:
            m1_error = str(e)
            logger.error(f"M1 xətası: {e}")
            traceback.print_exc()

    def _m2():
        nonlocal m2_result, m2_error
        try:
            if run_m2 is None:
                raise RuntimeError("m2_research modulu yüklənməyib")
            m2_result = run_m2(parsed_json)
            logger.info("M2 tamamlandı")
        except Exception as e:
            m2_error = str(e)
            logger.error(f"M2 xətası: {e}")
            traceback.print_exc()

    t1 = threading.Thread(target=_m1)
    t2 = threading.Thread(target=_m2)
    t1.start(); t2.start()
    t1.join();  t2.join()

    if m1_error:
        m1_result = {"error": m1_error, "m1_guveni": 0}
    if m2_error:
        m2_result = {"error": m2_error, "m2_guveni": 0}

    return m1_result, m2_result


@app.route("/health", methods=["GET"])
def health_check():
    modules = {
        "parser": parse_soccer_stats is not None,
        "m1":     run_m1 is not None,
        "m2":     run_m2 is not None,
        "m3":     run_m3 is not None,
        "m4":     run_m4 is not None,
    }
    all_ok = all(modules.values())
    return jsonify({
        "status":    "healthy" if all_ok else "degraded",
        "timestamp": datetime.now().isoformat(),
        "modules":   modules
    }), 200 if all_ok else 503


@app.route("/analyze", methods=["POST"])
def analyze():
    if not request.is_json:
        return jsonify({"success": False,
                        "error": "Content-Type application/json olmalıdır"}), 400

    data = request.get_json()
    if not data or "stats_text" not in data:
        return jsonify({"success": False,
                        "error": "stats_text tələb olunur"}), 400

    stats_text = data["stats_text"]
    if not isinstance(stats_text, str) or not stats_text.strip():
        return jsonify({"success": False,
                        "error": "stats_text boş ola bilməz"}), 400

    logger.info(f"Analiz sorğusu gəldi. Mətn uzunluğu: {len(stats_text)}")

    m1_result = {}
    m2_result = {}
    m3_result = {}

    def safe_dict(x):
        return x if isinstance(x, dict) else {}

    try:
        # 1. PARSER
        if parse_soccer_stats is None:
            raise RuntimeError("Parser modulu işləmir")
        parsed = parse_soccer_stats(stats_text)
        logger.info("Parser tamamlandı")

        # ✅ DÜZƏLİŞ: team1/team2 + team_stats əlavə et
        parsed = normalize_parsed(parsed)

        # 2. M1 + M2 (paralel)
        m1_result, m2_result = run_m1_m2_parallel(parsed)

        # ─────────────────────────────────────────────
        # ✅ DÜZƏLİŞ 2: Safe confidence oxuma
        # ─────────────────────────────────────────────
        def safe_get_conf(obj, key_list):
            for k in key_list:
                if isinstance(obj, dict) and k in obj:
                    return normalize_confidence(obj[k])
            return 0

        m1_conf = safe_get_conf(m1_result, ["confidence", "m1_guveni", "m1_confidence"])
        m2_conf = safe_get_conf(m2_result, ["confidence", "m2_guveni"])
        m3_conf = 0  # M3 hələ çağırılmayıb, sonra yenilənəcək
        logger.info(f"M2 keys: {list(m2_result.keys()) if isinstance(m2_result, dict) else m2_result}")
        

        # ─────────────────────────────────────────────
        # ✅ DÜZƏLİŞ 3: Error guard — M1/M2 xətası varsa M3/M4-ə getmə
        # ─────────────────────────────────────────────
        if "error" in m1_result or "error" in m2_result:
            logger.warning("M1/M2 error detected → NO BET")
            return jsonify({
                "success":  True,
                "decision": "NO BET",
                "reason":   "M1/M2 error",
                "parser":   safe_dict(parsed),
                "m1":       safe_dict(m1_result),
                "m2":       safe_dict(m2_result),
                "m3":       safe_dict(m3_result),
                "m4": {
                    "umumi_qerar": "OYNAMARAM",
                    "sebeb": "error fallback"
                }
            }), 200

        # 3. M3
        if run_m3 is None:
            raise RuntimeError("M3 modulu işləmir")
        # ─────────────────────────────────────────────
        # ✅ DÜZƏLİŞ 6: M3 call protection
        # ─────────────────────────────────────────────
        if "error" in m2_result:
            logger.warning("M2 error → M3 input zəif ola bilər")
        m3_result = run_m3(parsed, m2_result)
        logger.info("M3 tamamlandı")

        # ─────────────────────────────────────────────
        # ✅ DÜZƏLİŞ 4: Conflict detection
        # ─────────────────────────────────────────────
        def detect_conflict(m1, m3):
            try:
                m1_pred = str(m1.get("prediction", "")).lower()
                m3_pred = str(m3.get("prediction", "")).lower()
                return m1_pred and m3_pred and m1_pred != m3_pred
            except:
                return False

        conflict = detect_conflict(m1_result, m3_result)
        if conflict:
            logger.warning("M1 və M3 arasında conflict aşkarlandı")

        # M3 confidence-i indi yenilə
        m3_conf = safe_get_conf(m3_result, ["confidence", "m3_guveni", "m3_confidence"])
        logger.info(f"CONF (yeniləndi) → M1:{m1_conf} M2:{m2_conf} M3:{m3_conf}")

        # ─────────────────────────────────────────────
        # ✅ DÜZƏLİŞ 5: No bet logic
        # ─────────────────────────────────────────────
        avg_conf = (m1_conf + m2_conf + m3_conf) / 3
        if avg_conf < 55 or conflict:
            logger.warning(f"NO BET | avg_conf={avg_conf} conflict={conflict}")
            return jsonify({
                "success":          True,
                "decision":         "NO BET",
                "reason":           "low confidence or conflict",
                "avg_confidence":   avg_conf,
                "conflict":         conflict,
                "parser":           safe_dict(parsed),
                "m1":               safe_dict(m1_result),
                "m2":               safe_dict(m2_result),
                "m3":               safe_dict(m3_result),
                "m4": {
                    "umumi_qerar": "OYNAMARAM",
                    "sebeb": "NO BET"
                }
            }), 200

        # 4. M4
        if run_m4 is None:
            raise RuntimeError("M4 modulu işləmir")

        # ─────────────────────────────────────────────
        # ✅ DÜZƏLİŞ 7: M4 debug log
        # ─────────────────────────────────────────────
        logger.info("M4 input summary:")
        logger.info(f"M1: {m1_result}")
        logger.info(f"M2: {m2_result}")
        logger.info(f"M3: {m3_result}")

        m4_result = run_m4(m1_result, m2_result, m3_result)
        logger.info("M4 tamamlandı")

        return jsonify({
            "success":   True,
            "timestamp": datetime.now().isoformat(),
            "parser":    parsed,
            "m1":        m1_result,
            "m2":        m2_result,
            "m3":        m3_result,
            "m4":        m4_result
        }), 200

    except Exception as e:
        logger.error(f"Analiz xətası: {e}")
        traceback.print_exc()
        return jsonify({
            "success":   False,
            "error":     str(e),
            "timestamp": datetime.now().isoformat()
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)