// ─────────────────────────────────────────
// KONFİQURASİYA
// ─────────────────────────────────────────
const BACKEND_URL = "https://snaq1.onrender.com"; // Render və ya Vercel URL-i

// ─────────────────────────────────────────
// YARDIMÇI FUNKSİYALAR (UI üçün)
// ─────────────────────────────────────────
function badge(pct, bloker) {
    if (bloker) return "⛔";
    if (pct >= 90) return "✅✅";
    if (pct >= 75) return "✅";
    if (pct >= 60) return "⚠️";
    return "❌";
}

function badgeColor(pct, bloker) {
    if (bloker) return "c-muted";
    if (pct >= 90) return "c-green";
    if (pct >= 75) return "c-green";
    if (pct >= 60) return "c-yellow";
    return "c-red";
}

function barColor(score10) {
    if (score10 >= 8) return "#22c55e"; // Yaşıl
    if (score10 >= 6) return "#3b82f6"; // Mavi
    if (score10 >= 4) return "#eab308"; // Sarı
    return "#ef4444"; // Qırmızı
}

// ─────────────────────────────────────────
// MODUL KARTI DOLDURMA (M1, M2, M3, M4)
// ─────────────────────────────────────────
function fillModCard(id, score) {
    const elScore = document.getElementById(`score${id}`);
    const elBar = document.getElementById(`bar${id}`);
    const elStatus = document.getElementById(`status${id}`);

    if (!elScore || !elBar) return;

    // Hesabı rəqəmə çevir (Gələ biləcək null/undefined qarşısını al)
    let s = parseFloat(score);
    if (isNaN(s)) s = 0;

    elScore.textContent = `${s.toFixed(1)}/10`;
    elBar.style.width = `${(s / 10) * 100}%`;
    elBar.style.background = barColor(s);

    const statuses = [
        [9, "Əfsanəvi 🔥"],
        [7, "Yaxşı ✓"],
        [5, "Orta"],
        [3, "Zəif"],
        [0, "Məlumat yox"]
    ];
    const label = statuses.find(([k]) => s >= k)?.[1] ?? "Məlumat yox";
    if (elStatus) elStatus.textContent = label;
}

// ─────────────────────────────────────────
// BAZAR SƏTRİ (HTML Generasiyası)
// ─────────────────────────────────────────
function marketRow(item) {
    const bloker = !!item.bloker;
    // Faiz rəqəmini təmizlə (məsələn "85%" gələrsə rəqəmə çevir)
    let rawPct = typeof item.ehtimal === "string" ? parseFloat(item.ehtimal.replace("%", "")) : item.ehtimal;
    const pct = bloker ? null : Math.round((rawPct > 1 ? rawPct : rawPct * 100) || 0);
    
    const bdg = badge(pct, bloker);
    const cls = badgeColor(pct, bloker);
    const pctTxt = bloker ? "—" : `${pct}%`;
    
    const meta = [item.sebeb, item.modul ? `<b>${item.modul}</b>` : ""].filter(Boolean).join(" · ");

    return `
    <div class="market-row">
      <div class="market-name">
        ${item.ad || ""}
        ${meta ? `<div class="market-meta">${meta}</div>` : ""}
      </div>
      <div class="market-pct ${cls}">${pctTxt}</div>
      <div class="market-badge">${bdg}</div>
    </div>`;
}

// ─────────────────────────────────────────
// ACCORDION İDARƏETMƏSİ
// ─────────────────────────────────────────
function toggleAcc(header) {
    const body = header.nextElementSibling;
    const isOpen = body.classList.contains("open");

    // Digərlərini bağla
    document.querySelectorAll(".acc-body").forEach(b => b.classList.remove("open"));
    document.querySelectorAll(".acc-header").forEach(h => h.classList.remove("open"));

    if (!isOpen) {
        body.classList.add("open");
        header.classList.add("open");
    }
}

// ─────────────────────────────────────────
// BAZARLARI DOLDURMA (Xəta qorumalı)
// ─────────────────────────────────────────
const MARKET_KEYS = [
    "qol","btts","tekcut","netice","handicap","deqiq","ilkyari",
    "vaxt","corner","sot","faul","kart","ofsayt","aut","qapi",
    "penalti","var","ilkqol","kombine"
];

function fillMarkets(m4) {
    const bz = m4.bazarlar || {};

    function objToArray(obj) {
        if (!obj || typeof obj !== 'object') return [];
        // Əgər artıq array-dirsə (Llama bəzən array qaytarır)
        if (Array.isArray(obj)) return obj;

        return Object.entries(obj).map(([key, val]) => ({
            ad: key.replace(/_/g, " ").toUpperCase(),
            ehtimal: val.ehtimal ?? 0,
            sebeb: val.sebeb || "",
            modul: val.dominant_modul || "",
            bloker: val.qerar === "⛔" || val.bloker === true
        }));
    }

    MARKET_KEYS.forEach(key => {
        const el = document.getElementById(`body-${key}`);
        if (!el) return;
        
        const items = objToArray(bz[key]);
        el.innerHTML = items.length
            ? items.map(marketRow).join("")
            : `<p class="c-muted" style="padding:12px 0;font-size:13px">Məlumat tapılmadı</p>`;
    });
}

// ─────────────────────────────────────────
// TOP TÖVSİYƏLƏR VƏ FİNAL QƏRAR
// ─────────────────────────────────────────
function fillTopPicks(m4) {
    const picks = m4.top_tovsiyeler || [];
    const el = document.getElementById("topPicks");
    if (!el) return;

    if (!picks.length) {
        el.innerHTML = `<p class="c-muted">Bu oyun üçün xüsusi tövsiyə yoxdur.</p>`;
        return;
    }

    el.innerHTML = picks.map(p => {
        let pct = parseFloat(p.ehtimal);
        if (pct <= 1) pct = Math.round(pct * 100);
        return `
            <div class="pick-card">
                <div class="pick-badge">${badge(pct, false)}</div>
                <div style="flex:1">
                    <div class="pick-label">${p.ad || "Tövsiyə"}</div>
                    ${p.sebeb ? `<div class="pick-reason">${p.sebeb}</div>` : ""}
                </div>
                <div class="pick-pct">${pct}%</div>
            </div>`;
    }).join("");
}

function fillFinal(m4) {
    const sg = parseFloat(m4.sistem_guveni || 0);
    const qg = parseFloat(m4.qerar_guveni || 0);

    // Barların doldurulması
    const fillS = document.getElementById("fillSistem");
    if(fillS) {
        fillS.style.width = `${(sg / 10) * 100}%`;
        fillS.style.background = barColor(sg);
        document.getElementById("lblSistem").textContent = `${sg.toFixed(1)}/10`;
    }

    const fillQ = document.getElementById("fillQerar");
    if(fillQ) {
        fillQ.style.width = `${(qg / 10) * 100}%`;
        fillQ.style.background = barColor(qg);
        document.getElementById("lblQerar").textContent = `${qg.toFixed(1)}/10`;
    }

    const verd = document.getElementById("finalVerdict");
    if (verd) {
        // "oynarim" həm Boolean, həm String gələ bilər, yoxla
        const isPlay = m4.oynarim === true || m4.oynarim === "true" || m4.oynayiram === true;
        verd.textContent = isPlay ? "🏆 OYNARIM ✅" : "🚫 OYNAMARAM ❌";
        verd.className = `final-verdict ${isPlay ? 'verdict-yes' : 'verdict-no'}`;
    }

    const reason = document.getElementById("finalReason");
    if (reason) reason.textContent = m4.sebeb || "";
}

// ─────────────────────────────────────────
// ANA ANALİZ FUNKSİYASI
// ─────────────────────────────────────────
async function startAnalysis() {
    const text = document.getElementById("statsInput").value.trim();
    const errorBox = document.getElementById("errorBox");
    const resultPanel = document.getElementById("resultPanel");

    if (!text) {
        errorBox.textContent = "Zəhmət olmasa statistika mətnini daxil edin.";
        errorBox.classList.remove("hidden");
        return;
    }

    // UI Sıfırla
    errorBox.classList.add("hidden");
    resultPanel.classList.add("hidden");

    const btn = document.getElementById("analyzeBtn");
    const btnText = document.getElementById("btnText");
    const spinner = document.getElementById("btnSpinner");

    btn.disabled = true;
    btnText.textContent = "Analiz edilir...";
    spinner.classList.remove("hidden");

    try {
        const resp = await fetch(`${BACKEND_URL}/analyze`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ stats_text: text })
        });

        const resData = await resp.json();

        if (!resp.ok || !resData.success) {
            throw new Error(resData.error || "Server xətası baş verdi.");
        }

        const coreData = resData.data;

        // Kartları doldur (Təhlükəsiz yoxlama ilə)
        fillModCard("M1", coreData.m1?.guveni?.total || coreData.m1?.guveni);
        fillModCard("M2", coreData.m2?.m2_guveni);
        fillModCard("M3", coreData.m3?.m3_guveni);
        fillModCard("M4", coreData.m4?.sistem_guveni);

        // M4 Məzmununu doldur
        const m4 = coreData.m4 || {};
        fillMarkets(m4);
        fillTopPicks(m4);
        fillFinal(m4);

        // Nəticəni göstər
        resultPanel.classList.remove("hidden");
        resultPanel.scrollIntoView({ behavior: "smooth" });

    } catch (err) {
        errorBox.textContent = `Xəta: ${err.message}`;
        errorBox.classList.remove("hidden");
        console.error("Analiz xətası:", err);
    } finally {
        btn.disabled = false;
        btnText.textContent = "Analiz Et";
        spinner.classList.add("hidden");
    }
}