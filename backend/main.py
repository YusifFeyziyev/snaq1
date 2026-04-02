# main.py
import os
import sys
import json
import threading
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import traceback

# Logging konfiqurasiyası
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Kök qovluğu path-ə əlavə et (lazım olduqda)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Modulların import edilməsi və yoxlanması
try:
    from parser import parse_soccer_stats
    logger.info("✓ parser modulu yükləndi")
except ImportError as e:
    logger.error(f"✗ parser modulu tapılmadı: {e}")
    parse_soccer_stats = None

try:
    from modules.m1_math import run_m1
    logger.info("✓ m1_math modulu yükləndi")
except ImportError as e:
    logger.error(f"✗ m1_math modulu tapılmadı: {e}")
    run_m1 = None

try:
    from modules.m2_research import run_m2
    logger.info("✓ m2_research modulu yükləndi")
except ImportError as e:
    logger.error(f"✗ m2_research modulu tapılmadı: {e}")
    run_m2 = None

try:
    from modules.m3_expert import run_m3
    logger.info("✓ m3_expert modulu yükləndi")
except ImportError as e:
    logger.error(f"✗ m3_expert modulu tapılmadı: {e}")
    run_m3 = None

try:
    from modules.m4_decision import run_m4
    logger.info("✓ m4_decision modulu yükləndi")
except ImportError as e:
    logger.error(f"✗ m4_decision modulu tapılmadı: {e}")
    run_m4 = None

# Flask tətbiqi
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Bütün sorğulara icazə

def run_parallel_m1_m2(parsed_json):
    """M1 və M2-ni paralel işə salır, nəticələri qaytarır."""
    m1_result = None
    m2_result = None
    m1_error = None
    m2_error = None

    def target_m1():
        nonlocal m1_result, m1_error
        try:
            if run_m1 is None:
                m1_error = "m1_math modulu yoxdur"
                return
            m1_result = run_m1(parsed_json)
            logger.info("M1 uğurla tamamlandı")
        except Exception as e:
            m1_error = str(e)
            logger.error(f"M1 xətası: {e}")
            traceback.print_exc()

    def target_m2():
        nonlocal m2_result, m2_error
        try:
            if run_m2 is None:
                m2_error = "m2_research modulu yoxdur"
                return
            m2_result = run_m2(parsed_json)
            logger.info("M2 uğurla tamamlandı")
        except Exception as e:
            m2_error = str(e)
            logger.error(f"M2 xətası: {e}")
            traceback.print_exc()

    t1 = threading.Thread(target=target_m1)
    t2 = threading.Thread(target=target_m2)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Xəta baş veribsə, nəticələrə error əlavə et
    if m1_error:
        m1_result = {"error": m1_error, "m1_guveni": 0}
    if m2_error:
        m2_result = {"error": m2_error, "m2_guveni": 0}

    return m1_result, m2_result

@app.route('/health', methods=['GET'])
def health_check():
    """Sağlamlıq yoxlaması endpoint-i"""
    status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "modules": {
            "parser": parse_soccer_stats is not None,
            "m1": run_m1 is not None,
            "m2": run_m2 is not None,
            "m3": run_m3 is not None,
            "m4": run_m4 is not None
        }
    }
    http_status = 200 if all(status["modules"].values()) else 503
    return jsonify(status), http_status

@app.route('/analyze', methods=['POST'])
def analyze():
    """Əsas analiz endpoint-i"""
    # Giriş məlumatlarını yoxla
    if not request.is_json:
        logger.warning("JSON formatında sorğu göndərilməyib")
        return jsonify({"success": False, "error": "Content-Type application/json olmalıdır"}), 400

    data = request.get_json()
    if not data or 'stats_text' not in data:
        logger.warning("stats_text parametri tapılmadı")
        return jsonify({"success": False, "error": "stats_text tələb olunur"}), 400

    stats_text = data['stats_text']
    if not isinstance(stats_text, str) or len(stats_text.strip()) == 0:
        return jsonify({"success": False, "error": "stats_text boş ola bilməz"}), 400

    logger.info(f"Analiz sorğusu gəldi. Mətn uzunluğu: {len(stats_text)}")

    try:
        # 1. Parser
        if parse_soccer_stats is None:
            raise RuntimeError("Parser modulu işləmir")
        parsed = parse_soccer_stats(stats_text)
        logger.info("Parser uğurla tamamlandı")
        
        # 2. M1 və M2 paralel
        m1_result, m2_result = run_parallel_m1_m2(parsed)
        
        # 3. M3 (M2 nəticəsi ilə)
        if run_m3 is None:
            raise RuntimeError("M3 modulu işləmir")
        m3_result = run_m3(parsed, m2_result)
        logger.info("M3 uğurla tamamlandı")
        
        # 4. M4 (M1, M2, M3 ilə)
        if run_m4 is None:
            raise RuntimeError("M4 modulu işləmir")
        m4_result = run_m4(m1_result, m2_result, m3_result)
        logger.info("M4 uğurla tamamlandı")
        
        # Uğurlu cavab
        response = {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "parser": parsed,
            "m1": m1_result,
            "m2": m2_result,
            "m3": m3_result,
            "m4": m4_result
        }
        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Analiz zamanı xəta: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

# Əgər birbaşa işlədilirsə
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    
    logger.info(f"Flask tətbiqi başladılır. Port: {port}, Debug: {debug_mode}")
    
    # Modulların hamısının yükləndiyini yoxla
    missing = []
    if parse_soccer_stats is None: missing.append("parser")
    if run_m1 is None: missing.append("m1")
    if run_m2 is None: missing.append("m2")
    if run_m3 is None: missing.append("m3")
    if run_m4 is None: missing.append("m4")
    
    if missing:
        logger.warning(f"Aşağıdakı modullar yüklənməyib: {', '.join(missing)}")
        logger.warning("Tətbiq qismən işləyə bilər")
    else:
        logger.info("Bütün modullar uğurla yükləndi")
    
    app.run(host="0.0.0.0", port=port, debug=debug_mode)