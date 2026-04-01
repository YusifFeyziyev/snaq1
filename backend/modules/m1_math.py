import math
import json
from typing import Optional

# ─────────────────────────────────────────
#  YARDIMÇI FUNKSIYALAR
# ─────────────────────────────────────────

def poisson_prob(lam: float, k: int) -> float:
    if lam <= 0:
        return 0.0
    return (math.exp(-lam) * (lam ** k)) / math.factorial(k)

def poisson_over(lam: float, threshold: float) -> float:
    k = int(threshold + 0.5)
    under = sum(poisson_prob(lam, i) for i in range(k + 1))
    return round(max(0.0, min(1.0, 1.0 - under)), 4)

def poisson_exact(lam: float, k: int) -> float:
    return round(poisson_prob(lam, k), 4)

def normal_over(mean: float, std: float, threshold: float) -> float:
    if std <= 0:
        return 0.5
    z = (threshold - mean) / std
    prob_under = 0.5 * (1 + math.erf(z / math.sqrt(2)))
    return round(max(0.0, min(1.0, 1.0 - prob_under)), 4)

def safe(val, default=None):
    return val if val is not None else default


# ─────────────────────────────────────────
#  LIQA DAMPING
# ─────────────────────────────────────────

def get_damping(liqa_qol_ort: Optional[float]) -> float:
    if liqa_qol_ort is None:
        return 0.92
    if liqa_qol_ort < 2.2:
        return 0.88
    return 0.92


# ─────────────────────────────────────────
#  QOL BAZASI
# ─────────────────────────────────────────

def hesabla_qol_bazasi(data: dict) -> dict:
    ev = data.get("ev", {})
    qonaq = data.get("qonaq", {})
    liqa = data.get("liqa_ortalama", {})

    ev_vurdu   = safe(ev.get("qol_vurdu"))
    ev_buraxdi = safe(ev.get("qol_buraxdi"))
    qon_vurdu  = safe(qonaq.get("qol_vurdu"))
    qon_buraxdi= safe(qonaq.get("qol_buraxdi"))
    liqa_ort   = safe(liqa.get("qol_ort"))

    if None in [ev_vurdu, ev_buraxdi, qon_vurdu, qon_buraxdi]:
        return {"null_data": True, "sebeb": "qol_vurdu/buraxdi null"}

    ev_goz  = (ev_vurdu + qon_buraxdi) / 2
    qon_goz = (qon_vurdu + ev_buraxdi) / 2
    xam_baza = ev_goz + qon_goz

    damping = get_damping(liqa_ort)

    # H2H korreksiyası
    h2h = data.get("h2h", {})
    h2h_ort = safe(h2h.get("ort_qol"))
    h2h_ceki = 0.15
    if h2h_ort is not None:
        xam_baza = xam_baza * (1 - h2h_ceki) + h2h_ort * h2h_ceki
        if h2h_ort < 1.5:
            damping *= 0.92

    final_baza = xam_baza * damping

    return {
        "ev_goz": round(ev_goz, 3),
        "qon_goz": round(qon_goz, 3),
        "xam_baza": round(xam_baza, 3),
        "final_baza": round(final_baza, 3),
        "null_data": False
    }


# ─────────────────────────────────────────
#  QOL BAZARLARI
# ─────────────────────────────────────────

def hesabla_qol_bazarlari(qol: dict) -> dict:
    if qol.get("null_data"):
        return {"null_data": True}

    ev_lam  = qol["ev_goz"]
    qon_lam = qol["qon_goz"]
    total   = qol["final_baza"]

    result = {
        "over15": poisson_over(total, 1.5),
        "over25": poisson_over(total, 2.5),
        "over35": poisson_over(total, 3.5),
        "over45": poisson_over(total, 4.5),
        "under25": round(1 - poisson_over(total, 2.5), 4),
        "under35": round(1 - poisson_over(total, 3.5), 4),
        "under45": round(1 - poisson_over(total, 4.5), 4),
        "under55": round(1 - poisson_over(total, 5.5), 4),
        "btts": round(
            (1 - poisson_prob(ev_lam, 0)) *
            (1 - poisson_prob(qon_lam, 0)), 4
        ),
        "btts_xeyr": round(
            poisson_prob(ev_lam, 0) +
            poisson_prob(qon_lam, 0) -
            poisson_prob(ev_lam, 0) * poisson_prob(qon_lam, 0), 4
        ),
        "null_data": False
    }

    # Tək/Cüt
    tek = sum(
        poisson_exact(ev_lam, i) * poisson_exact(qon_lam, j)
        for i in range(8) for j in range(8) if (i + j) % 2 == 1
    )
    result["tek_qol"] = round(tek, 4)
    result["cut_qol"] = round(1 - tek, 4)

    # Dəqiq hesab (ilk 16 kombinasiya)
    deqiq = {}
    for ev_q in range(5):
        for qon_q in range(5):
            key = f"{ev_q}-{qon_q}"
            deqiq[key] = round(
                poisson_exact(ev_lam, ev_q) *
                poisson_exact(qon_lam, qon_q), 4
            )
    result["deqiq_hesab"] = deqiq

    # 1X2
    ev_qelib = sum(
        poisson_exact(ev_lam, i) * poisson_exact(qon_lam, j)
        for i in range(8) for j in range(8) if i > j
    )
    beraberlik = sum(
        poisson_exact(ev_lam, i) * poisson_exact(qon_lam, j)
        for i in range(8) for j in range(8) if i == j
    )
    result["p1"]  = round(ev_qelib, 4)
    result["px"]  = round(beraberlik, 4)
    result["p2"]  = round(1 - ev_qelib - beraberlik, 4)
    result["p1x"] = round(ev_qelib + beraberlik, 4)
    result["px2"] = round(beraberlik + (1 - ev_qelib - beraberlik), 4)
    result["p12"] = round(ev_qelib + (1 - ev_qelib - beraberlik), 4)

    # Klean-şit
    result["ev_klean"] = round(poisson_prob(qon_lam, 0), 4)
    result["qon_klean"] = round(poisson_prob(ev_lam, 0), 4)

    # İlk yarı
    ev_ht  = ev_lam * 0.45
    qon_ht = qon_lam * 0.45
    total_ht = ev_ht + qon_ht
    result["ht"] = {
        "over05": poisson_over(total_ht, 0.5),
        "over15": poisson_over(total_ht, 1.5),
        "over25": poisson_over(total_ht, 2.5),
        "p1":  round(sum(
            poisson_exact(ev_ht, i) * poisson_exact(qon_ht, j)
            for i in range(6) for j in range(6) if i > j
        ), 4),
        "px":  round(sum(
            poisson_exact(ev_ht, i) * poisson_exact(qon_ht, j)
            for i in range(6) for j in range(6) if i == j
        ), 4),
    }
    result["ht"]["p2"] = round(
        1 - result["ht"]["p1"] - result["ht"]["px"], 4
    )

    # Kombinə bazarlar
    result["kombine"] = {
        "over25_btts": round(result["over25"] * result["btts"] * 0.95, 4),
        "p1_over25":   round(result["p1"]    * result["over25"] * 0.95, 4),
        "p1_btts":     round(result["p1"]    * result["btts"]   * 0.95, 4),
        "p2_over25":   round(result["p2"]    * result["over25"] * 0.95, 4),
    }

    return result


# ─────────────────────────────────────────
#  CORNER BAZARLARI
# ─────────────────────────────────────────

def hesabla_corner(data: dict) -> dict:
    ev    = data.get("ev", {})
    qonaq = data.get("qonaq", {})

    ev_c  = safe(ev.get("corner_ort"))
    qon_c = safe(qonaq.get("corner_ort"))

    if ev_c is None or qon_c is None:
        return {"null_data": True}

    ev_adj  = ev_c * 1.15
    qon_adj = qon_c * 0.85
    mean    = ev_adj + qon_adj
    std     = mean * 0.30

    result = {"null_data": False, "ortalama": round(mean, 2)}
    for t in [7.5, 8.5, 9.5, 10.5, 11.5, 12.5, 13.5]:
        key = f"over{str(t).replace('.', '_')}"
        result[key] = normal_over(mean, std, t)

    # Tək/Cüt corner
    tek = sum(
        poisson_exact(ev_adj, i) * poisson_exact(qon_adj, j)
        for i in range(20) for j in range(20) if (i + j) % 2 == 1
    )
    result["tek"] = round(tek, 4)
    result["cut"] = round(1 - tek, 4)

    # İlk yarı corner
    ev_ht_c  = ev_adj * 0.45
    qon_ht_c = qon_adj * 0.45
    mean_ht  = ev_ht_c + qon_ht_c
    result["ht"] = {}
    for t in [3.5, 4.5, 5.5]:
        key = f"over{str(t).replace('.', '_')}"
        result["ht"][key] = normal_over(mean_ht, mean_ht * 0.30, t)

    # 1X2 corner
    result["p1"]  = normal_over(ev_adj - qon_adj, std * 0.7, 0)
    result["p2"]  = normal_over(qon_adj - ev_adj, std * 0.7, 0)
    result["px"]  = round(1 - result["p1"] - result["p2"], 4)

    return result


# ─────────────────────────────────────────
#  SOT BAZARLARI
# ─────────────────────────────────────────

def hesabla_sot(data: dict) -> dict:
    ev    = data.get("ev", {})
    qonaq = data.get("qonaq", {})

    ev_s  = safe(ev.get("sot_ort"))
    qon_s = safe(qonaq.get("sot_ort"))

    if ev_s is None or qon_s is None:
        return {"null_data": True}

    ev_adj  = ev_s * 1.12
    qon_adj = qon_s * 0.88
    mean    = ev_adj + qon_adj
    std     = mean * 0.28

    result = {"null_data": False, "ortalama": round(mean, 2)}
    for t in [7.5, 8.5, 9.5, 10.5, 11.5]:
        key = f"over{str(t).replace('.', '_')}"
        result[key] = normal_over(mean, std, t)

    return result


# ─────────────────────────────────────────
#  FAUL BAZARLARI
# ─────────────────────────────────────────

def hesabla_faul(data: dict) -> dict:
    ev    = data.get("ev", {})
    qonaq = data.get("qonaq", {})

    ev_f  = safe(ev.get("faul_ort"))
    qon_f = safe(qonaq.get("faul_ort"))

    if ev_f is None or qon_f is None:
        return {"null_data": True}

    mean = ev_f + qon_f
    std  = mean * 0.25

    result = {"null_data": False, "ortalama": round(mean, 2)}
    for t in [20.5, 22.5, 24.5]:
        key = f"over{str(t).replace('.', '_')}"
        result[key] = normal_over(mean, std, t)

    return result


# ─────────────────────────────────────────
#  KART BAZARLARI
# ─────────────────────────────────────────

def hesabla_kart(data: dict) -> dict:
    ev    = data.get("ev", {})
    qonaq = data.get("qonaq", {})

    ev_k  = safe(ev.get("kart_ort"))
    qon_k = safe(qonaq.get("kart_ort"))

    if ev_k is None or qon_k is None:
        return {"null_data": True}

    mean = ev_k + qon_k
    std  = mean * 0.30

    result = {"null_data": False, "ortalama": round(mean, 2)}
    for t in [2.5, 3.5, 4.5]:
        key = f"over{str(t).replace('.', '_')}"
        result[key] = normal_over(mean, std, t)

    # Tək/Cüt kart
    tek = sum(
        poisson_exact(ev_k, i) * poisson_exact(qon_k, j)
        for i in range(12) for j in range(12) if (i + j) % 2 == 1
    )
    result["tek"] = round(tek, 4)
    result["cut"] = round(1 - tek, 4)

    # Qırmızı kart (aşağı güvən)
    result["qirmizi_beli"] = round(min(mean * 0.08, 0.35), 4)
    result["qirmizi_confidence"] = "asagi"

    return result


# ─────────────────────────────────────────
#  OFSayt BAZARLARI
# ─────────────────────────────────────────

def hesabla_ofsayt(data: dict) -> dict:
    ev    = data.get("ev", {})
    qonaq = data.get("qonaq", {})

    ev_o  = safe(ev.get("ofsayt_ort"))
    qon_o = safe(qonaq.get("ofsayt_ort"))

    if ev_o is None or qon_o is None:
        return {"null_data": True}

    mean = ev_o + qon_o
    std  = mean * 0.35

    result = {"null_data": False, "ortalama": round(mean, 2)}
    for t in [1.5, 2.5, 3.5]:
        key = f"over{str(t).replace('.', '_')}"
        result[key] = normal_over(mean, std, t)

    return result


# ─────────────────────────────────────────
#  AUT BAZARLARI
# ─────────────────────────────────────────

def hesabla_aut(data: dict) -> dict:
    ev    = data.get("ev", {})
    qonaq = data.get("qonaq", {})

    ev_a  = safe(ev.get("aut_ort"))
    qon_a = safe(qonaq.get("aut_ort"))

    if ev_a is None or qon_a is None:
        return {"null_data": True, "confidence_cap": 6.5}

    mean = ev_a + qon_a
    std  = mean * 0.28

    result = {"null_data": False, "ortalama": round(mean, 2), "confidence_cap": 6.5}
    for t in [mean - 3, mean - 1.5, mean, mean + 1.5, mean + 3]:
        t = round(t + 0.5, 1)
        key = f"over{str(t).replace('.', '_')}"
        result[key] = normal_over(mean, std, t)

    return result


# ─────────────────────────────────────────
#  QAPIDAN ZƏRBƏ
# ─────────────────────────────────────────

def hesabla_qapidan_zerbe(data: dict) -> dict:
    ev    = data.get("ev", {})
    qonaq = data.get("qonaq", {})

    ev_q  = safe(ev.get("qapidan_zerbe_ort"))
    qon_q = safe(qonaq.get("qapidan_zerbe_ort"))

    if ev_q is None or qon_q is None:
        return {"null_data": True, "confidence_cap": 6.5}

    mean = ev_q + qon_q
    std  = mean * 0.28

    result = {"null_data": False, "ortalama": round(mean, 2), "confidence_cap": 6.5}
    for t in [mean - 2, mean, mean + 2]:
        t = round(t + 0.5, 1)
        key = f"over{str(t).replace('.', '_')}"
        result[key] = normal_over(mean, std, t)

    return result


# ─────────────────────────────────────────
#  PENALTİ
# ─────────────────────────────────────────

def hesabla_penalti(data: dict) -> dict:
    # Tarixi standart ehtimal — hakim çarpanı M3/M4-dən gəlir
    return {
        "beli": 0.26,
        "xeyr": 0.74,
        "qeyd": "Hakim çarpanı M4-dən tətbiq ediləcək",
        "null_data": False
    }


# ─────────────────────────────────────────
#  GÜVƏN SISTEMI /10
# ─────────────────────────────────────────

def hesabla_guveni(data: dict, qol: dict, corner: dict, sot: dict) -> dict:
    ev    = data.get("ev", {})
    qonaq = data.get("qonaq", {})

    # Data dolğunluğu (0-4)
    saheler = [
        "qol_vurdu", "qol_buraxdi", "over25", "bts",
        "corner_ort", "sot_ort", "faul_ort", "kart_ort"
    ]
    ev_dolu   = sum(1 for s in saheler if safe(ev.get(s)) is not None)
    qon_dolu  = sum(1 for s in saheler if safe(qonaq.get(s)) is not None)
    dolgunluk = round((ev_dolu + qon_dolu) / (len(saheler) * 2) * 4, 2)

    # Poisson dəqiqliyi (0-3)
    poisson_bal = 0.0
    if not qol.get("null_data"):
        poisson_bal = 3.0
    elif qol.get("null_data"):
        poisson_bal = 0.0

    # Liqa uyğunluğu (0-3)
    liqa_ort = safe(data.get("liqa_ortalama", {}).get("qol_ort"))
    liqa_bal = 2.0 if liqa_ort is not None else 1.0

    total = round(dolgunluk + poisson_bal + liqa_bal, 2)
    total = min(10.0, total)

    return {
        "dolgunluk": dolgunluk,
        "poisson_bal": poisson_bal,
        "liqa_bal": liqa_bal,
        "total": total
    }


# ─────────────────────────────────────────
#  KASKAD GÜVƏN BONUSLARI
# ─────────────────────────────────────────

def qol_ferqi_bonus(ev_goz: float, qon_goz: float) -> int:
    ferg = abs(ev_goz - qon_goz)
    if ferg < 0.4:   return -20
    if ferg < 0.8:   return 0
    if ferg < 1.2:   return 15
    if ferg < 1.6:   return 25
    if ferg < 2.0:   return 35
    return 45

def corner_ferqi_bonus(ev_c: Optional[float], qon_c: Optional[float]) -> int:
    if ev_c is None or qon_c is None:
        return 0
    ferg = abs(ev_c * 1.15 - qon_c * 0.85)
    if ferg < 1.0:   return -20
    if ferg < 1.5:   return 0
    if ferg < 2.0:   return 15
    if ferg < 2.5:   return 25
    if ferg < 3.0:   return 35
    return 45


# ─────────────────────────────────────────
#  ANA FUNKSIYA
# ─────────────────────────────────────────

def run_m1(parser_json: dict) -> dict:
    """
    Parser JSON-u alır, bütün bazarları hesablayır.
    Çıxış M4-ə göndərilir.
    """
    ev    = parser_json.get("ev", {})
    qonaq = parser_json.get("qonaq", {})

    qol     = hesabla_qol_bazasi(parser_json)
    bazarlar = hesabla_qol_bazarlari(qol)
    corner  = hesabla_corner(parser_json)
    sot     = hesabla_sot(parser_json)
    faul    = hesabla_faul(parser_json)
    kart    = hesabla_kart(parser_json)
    ofsayt  = hesabla_ofsayt(parser_json)
    aut     = hesabla_aut(parser_json)
    qapidan = hesabla_qapidan_zerbe(parser_json)
    penalti = hesabla_penalti(parser_json)
    guveni  = hesabla_guveni(parser_json, qol, corner, sot)

    # Kaskad bonuslar
    ev_oyun  = safe(ev.get("oyun_sayi")) or 16
    qon_oyun = safe(qonaq.get("oyun_sayi")) or 16

    ev_vurdu   = safe(ev.get("qol_vurdu")) or 0
    ev_buraxdi = safe(ev.get("qol_buraxdi")) or 0
    qon_vurdu  = safe(qonaq.get("qol_vurdu")) or 0
    qon_buraxdi= safe(qonaq.get("qol_buraxdi")) or 0

    ev_vurdu_ort   = ev_vurdu / ev_oyun
    ev_buraxdi_ort = ev_buraxdi / ev_oyun
    qon_vurdu_ort  = qon_vurdu / qon_oyun
    qon_buraxdi_ort= qon_buraxdi / qon_oyun

    ev_goz  = (ev_vurdu_ort + qon_buraxdi_ort) / 2
    qon_goz = (qon_vurdu_ort + ev_buraxdi_ort) / 2
    ev_c    = safe(parser_json.get("ev", {}).get("corner_ort"))
    qon_c   = safe(parser_json.get("qonaq", {}).get("corner_ort"))

    bonus_qol    = qol_ferqi_bonus(ev_goz, qon_goz)
    bonus_corner = corner_ferqi_bonus(ev_c, qon_c)

    # Null flagları
    null_fields = []
    for sahə in ["sot_ort", "faul_ort", "kart_ort", "ofsayt_ort", "aut_ort", "qapidan_zerbe_ort"]:
        if safe(parser_json.get("ev", {}).get(sahə)) is None:
            null_fields.append(sahə)

    return {
        "qol_bazasi": qol,
        "qol_bazarlari": bazarlar,
        "corner": corner,
        "sot": sot,
        "faul": faul,
        "kart": kart,
        "ofsayt": ofsayt,
        "aut": aut,
        "qapidan_zerbe": qapidan,
        "penalti": penalti,
        "guveni": guveni,
        "bonuslar": {
            "qol_ferqi": bonus_qol,
            "corner_ferqi": bonus_corner
        },
        "null_fields": null_fields
    }


# ─────────────────────────────────────────
#  TEST
# ─────────────────────────────────────────

if __name__ == "__main__":
    test_data = {
        "ev": {
            "ad": "Mirandes",
            "qol_vurdu": 0.88,
            "qol_buraxdi": 1.56,
            "over25": 50,
            "bts": 56,
            "corner_ort": 9.44,
            "sot_ort": None,
            "faul_ort": None,
            "kart_ort": None,
            "ofsayt_ort": None,
            "aut_ort": None,
            "qapidan_zerbe_ort": None
        },
        "qonaq": {
            "ad": "Albacete",
            "qol_vurdu": 1.12,
            "qol_buraxdi": 1.31,
            "over25": 55,
            "bts": 58,
            "corner_ort": 8.20,
            "sot_ort": None,
            "faul_ort": None,
            "kart_ort": None,
            "ofsayt_ort": None,
            "aut_ort": None,
            "qapidan_zerbe_ort": None
        },
        "liqa_ortalama": {
            "qol_ort": 2.45
        },
        "h2h": {
            "ort_qol": 2.1
        }
    }

    result = run_m1(test_data)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
