// ─────────────────────────────────────────
// KONFİQ
// ─────────────────────────────────────────
const BACKEND_URL = "https://snaq1.onrender.com"; // Deploy sonrasi dəyis

// ─────────────────────────────────────────
// YARDIMCI FUNKSİYALAR
// ─────────────────────────────────────────
function badge(pct, bloker) {
  if (bloker)      return "⛔";
  if (pct >= 90)   return "✅✅";
  if (pct >= 75)   return "✅";
  if (pct >= 60)   return "⚠️";
  return "❌";
}

function badgeColor(pct, bloker) {
  if (bloker)      return "c-muted";
  if (pct >= 90)   return "c-green";
  if (pct >= 75)   return "c-green";
  if (pct >= 60)   return "c-yellow";
  return "c-red";
}

function barColor(score10) {
  if (score10 >= 8) return "#22c55e";
  if (score10 >= 6) return "#3b82f6";
  if (score10 >= 4) return "#eab308";
  return "#ef4444";
}

// ─────────────────────────────────────────
// MODUL KARTI DOLDUR
// ─────────────────────────────────────────
function fillModCard(id, score) {
  const s = typeof score === "number" ? score : 0;
  document.getElementById(`score${id}`).textContent = `${s.toFixed(1)}/10`;

  const bar = document.getElementById(`bar${id}`);
  bar.style.width      = `${(s / 10) * 100}%`;
  bar.style.background = barColor(s);

  const statuses = [[9,"Əfsanəvi 🔥"],[7,"Yaxşı ✓"],[5,"Orta"],[3,"Zəif"],[0,"Məlumat yox"]];
  const label = statuses.find(([k]) => s >= k)?.[1] ?? "Məlumat yox";
  document.getElementById(`status${id}`).textContent = label;
}

// ─────────────────────────────────────────
// BAZAR SƏTRİ HTML
// ─────────────────────────────────────────
function marketRow(item) {
  const bloker = !!item.bloker;
  const pct    = bloker ? null : Math.round((item.ehtimal ?? 0) * 100);
  const bdg    = badge(pct, bloker);
  const cls    = badgeColor(pct, bloker);
  const pctTxt = bloker ? "—" : `${pct}%`;
  const meta   = [item.sebeb, item.modul ? `<b>${item.modul}</b>` : ""].filter(Boolean).join(" · ");

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
// ACCORDION
// ─────────────────────────────────────────
function toggleAcc(header) {
  const body   = header.nextElementSibling;
  const isOpen = body.classList.contains("open");

  document.querySelectorAll(".acc-body").forEach(b => b.classList.remove("open"));
  document.querySelectorAll(".acc-header").forEach(h => h.classList.remove("open"));

  if (!isOpen) {
    body.classList.add("open");
    header.classList.add("open");
  }
}

// ─────────────────────────────────────────
// BAZAR KATEQORİYALARINI DOLDUR
// ─────────────────────────────────────────
const MARKET_KEYS = [
  "qol","btts","tekcut","netice","handicap",
  "deqiq","ilkyari","vaxt","corner","sot",
  "faul","kart","ofsayt","aut","qapi",
  "penalti","var","ilkqol","kombine"
];

function fillMarkets(m4) {
  const bz = m4.bazarlar || {};

  MARKET_KEYS.forEach(key => {
    const el    = document.getElementById(`body-${key}`);
    if (!el) return;
    const items = bz[key] || [];

    el.innerHTML = items.length
      ? items.map(marketRow).join("")
      : `<p class="c-muted" style="padding:12px 0;font-size:13px">Məlumat yoxdur</p>`;
  });
}

// ─────────────────────────────────────────
// TOP TÖVSİYƏLƏR
// ─────────────────────────────────────────
function fillTopPicks(m4) {
  const picks = m4.top_tovsiyeler || [];
  const el    = document.getElementById("topPicks");

  if (!picks.length) {
    el.innerHTML = `<p class="c-muted" style="font-size:13px">Bu oyun üçün tövsiyə yoxdur.</p>`;
    return;
  }

  el.innerHTML = picks.map(p => {
    const pct = Math.round((p.ehtimal ?? 0) * 100);
    return `
      <div class="pick-card">
        <div class="pick-badge">${badge(pct, false)}</div>
        <div style="flex:1">
          <div class="pick-label">${p.ad || ""}</div>
          ${p.sebeb ? `<div class="pick-reason">${p.sebeb}</div>` : ""}
        </div>
        <div class="pick-pct">${pct}%</div>
      </div>`;
  }).join("");
}

// ─────────────────────────────────────────
// M4 FİNAL PANELİ
// ─────────────────────────────────────────
function fillFinal(m4) {
  const sg = m4.sistem_guveni ?? 0;
  const qg = m4.qerar_guveni  ?? 0;

  // Sistem güvəni çubuğu
  const fillS = document.getElementById("fillSistem");
  fillS.style.width      = `${(sg / 10) * 100}%`;
  fillS.style.background = barColor(sg);
  document.getElementById("lblSistem").textContent = `${sg.toFixed(1)}/10`;

  // Qərar güvəni çubuğu
  const fillQ = document.getElementById("fillQerar");
  fillQ.style.width      = `${(qg / 10) * 100}%`;
  fillQ.style.background = barColor(qg);
  document.getElementById("lblQerar").textContent = `${qg.toFixed(1)}/10`;

  // Cəza xülasəsi
  const pr = document.getElementById("penaltyRow");
  pr.textContent = m4.ceza_xulasesi || "";

  // Hökm
  const verd = document.getElementById("finalVerdict");
  if (m4.oynarim === true) {
    verd.textContent = "🏆 OYNARIM ✅";
    verd.className   = "final-verdict verdict-yes";
  } else {
    verd.textContent = "🚫 OYNAMARAM ❌";
    verd.className   = "final-verdict verdict-no";
  }

  document.getElementById("finalReason").textContent = m4.sebeb || "";
}

// ─────────────────────────────────────────
// UI SIFIRLA
// ─────────────────────────────────────────
function resetUI() {
  document.getElementById("errorBox").classList.add("hidden");
  document.getElementById("resultPanel").classList.add("hidden");

  MARKET_KEYS.forEach(key => {
    const el = document.getElementById(`body-${key}`);
    if (el) el.innerHTML = "";
  });

  ["M1","M2","M3","M4"].forEach(id => {
    document.getElementById(`score${id}`).textContent = "—";
    document.getElementById(`bar${id}`).style.width   = "0%";
    document.getElementById(`status${id}`).textContent = "";
  });
}

// ─────────────────────────────────────────
// ANA FUNKSIYA
// ─────────────────────────────────────────
async function startAnalysis() {
  const text = document.getElementById("statsInput").value.trim();
  if (!text) {
    const box = document.getElementById("errorBox");
    box.textContent = "Zəhmət olmasa statistika mətnini yapışdırın.";
    box.classList.remove("hidden");
    return;
  }

  resetUI();

  const btn     = document.getElementById("analyzeBtn");
  const btnText = document.getElementById("btnText");
  const spinner = document.getElementById("btnSpinner");

  btn.disabled       = true;
  btnText.textContent = "Analiz edilir...";
  spinner.classList.remove("hidden");

  try {
    const resp = await fetch(`${BACKEND_URL}/analyze`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ statistics: text })
    });

    const data = await resp.json();

    if (!resp.ok || !data.success) {
      throw new Error(data.error || `Server xətası: ${resp.status}`);
    }

    // Modul kartları
    fillModCard("M1", data.m1?.guveni?.total);
    fillModCard("M2", data.m2?.m2_guveni);
    fillModCard("M3", data.m3?.m3_guveni);
    fillModCard("M4", data.m4?.sistem_guveni);

    // Məzmun
    fillMarkets(data.m4);
    fillTopPicks(data.m4);
    fillFinal(data.m4);

    // Göstər
    document.getElementById("resultPanel").classList.remove("hidden");
    document.getElementById("resultPanel").scrollIntoView({ behavior: "smooth" });

  } catch (err) {
    const box = document.getElementById("errorBox");
    box.textContent = `Xəta: ${err.message}`;
    box.classList.remove("hidden");
  } finally {
    btn.disabled        = false;
    btnText.textContent = "Analiz Et";
    spinner.classList.add("hidden");
  }
}
