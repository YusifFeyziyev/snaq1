const BACKEND_URL = "https://snaq1.onrender.com";

// ── KÖMƏKÇI ──────────────────────────────
function pct(val) {
  let v = parseFloat(val);
  if (isNaN(v)) return 0;
  return v <= 1 ? Math.round(v * 100) : Math.round(v);
}

function badge(p) {
  if (p >= 85) return "✅✅";
  if (p >= 70) return "✅";
  if (p >= 55) return "⚠️";
  return "❌";
}

function colorClass(p) {
  if (p >= 70) return "c-green";
  if (p >= 55) return "c-yellow";
  return "c-red";
}

function barColor(v10) {
  if (v10 >= 7.5) return "#22c55e";
  if (v10 >= 5)   return "#3b82f6";
  if (v10 >= 3)   return "#f59e0b";
  return "#ef4444";
}

// ── MODUL KART ────────────────────────────
function fillMod(id, score01) {
  const s = Math.min(10, parseFloat(score01 || 0) * 10);
  const elS = document.getElementById(`score${id}`);
  const elB = document.getElementById(`bar${id}`);
  if (elS) elS.textContent = `${s.toFixed(1)}/10`;
  if (elB) {
    elB.style.width = `${s * 10}%`;
    elB.style.background = barColor(s);
  }
}

// ── 1X2 ──────────────────────────────────
function fill1x2(data) {
  const map = [
    ["Home", "1x2Home", data.home_win],
    ["Draw", "1x2Draw", data.draw],
    ["Away", "1x2Away", data.away_win]
  ];
  map.forEach(([, key, val]) => {
    const p = pct(val);
    const pEl = document.getElementById(`pct${key}`);
    const bEl = document.getElementById(`bdg${key}`);
    if (pEl) { pEl.textContent = `${p}%`; pEl.className = `out-pct ${colorClass(p)}`; }
    if (bEl) bEl.textContent = badge(p);
  });
}

// ── OVER/UNDER QOL ───────────────────────
function fillOU(ouData) {
  const grid = document.getElementById("ouGrid");
  if (!grid || !ouData) return;
  const lines = ["1.5", "2.5", "3.5", "4.5"];
  grid.innerHTML = lines.map(line => {
    const d = ouData[line];
    if (!d) return "";
    const op = pct(d.over);
    const up = pct(d.under);
    const exp = d.expected_total ? `Gözlənilən: ${d.expected_total}` : "";
    return `
    <div class="mkt-card">
      <div class="mkt-name">Toplam Qol</div>
      <div style="font-size:20px;font-weight:900;color:var(--acc);margin:4px 0">${line}</div>
      <div class="mkt-vals">
        <div>
          <div style="font-size:11px;color:var(--muted)">OVER</div>
          <div class="mkt-over ${colorClass(op)}">${op}%</div>
        </div>
        <div class="mkt-badge">${badge(op)}</div>
        <div style="text-align:right">
          <div style="font-size:11px;color:var(--muted)">UNDER</div>
          <div class="mkt-under">${up}%</div>
        </div>
      </div>
      <div class="mkt-exp">${exp}</div>
    </div>`;
  }).join("");
}

// ── BTTS ─────────────────────────────────
function fillBtts(data) {
  const yp = pct(data.yes);
  const np = pct(data.no);
  [
    ["BttsYes", yp],
    ["BttsNo", np]
  ].forEach(([key, p]) => {
    const pEl = document.getElementById(`pct${key}`);
    const bEl = document.getElementById(`bdg${key}`);
    if (pEl) { pEl.textContent = `${p}%`; pEl.className = `out-pct ${colorClass(p)}`; }
    if (bEl) bEl.textContent = badge(p);
  });
}

// ── İLK YARI ─────────────────────────────
function fillFirstHalf(fh) {
  if (!fh) return;
  const x2 = fh["1x2"] || {};
  document.getElementById("fh1x2").innerHTML = [
    ["Ev", x2.home_win], ["Heç-heçə", x2.draw], ["Qonaq", x2.away_win]
  ].map(([k, v]) => {
    const p = pct(v);
    return `<div class="half-row">
      <span class="half-key">${k}</span>
      <span class="half-val ${colorClass(p)}">${p}%</span>
    </div>`;
  }).join("");

  const ou = fh.over_under || {};
  document.getElementById("fhOu").innerHTML = [
    ["Over 0.5", ou.over_0_5], ["Over 1.5", ou.over_1_5]
  ].map(([k, v]) => {
    const p = pct(v);
    return `<div class="half-row">
      <span class="half-key">${k}</span>
      <span class="half-val ${colorClass(p)}">${p}%</span>
    </div>`;
  }).join("");

  const bt = fh.btts || {};
  document.getElementById("fhBtts").innerHTML = [
    ["Hər ikisi atar", bt.yes], ["Yox", bt.no]
  ].map(([k, v]) => {
    const p = pct(v);
    return `<div class="half-row">
      <span class="half-key">${k}</span>
      <span class="half-val ${colorClass(p)}">${p}%</span>
    </div>`;
  }).join("");
}

// ── KORNERLƏR ────────────────────────────
function fillCorners(corners) {
  const grid = document.getElementById("cornerGrid");
  if (!grid || !corners) return;
  const tot = corners.total || {};
  const hcp = corners.handicap || {};
  grid.innerHTML = `
    <div class="mkt-card">
      <div class="mkt-name">Toplam Korner Over 9.5</div>
      <div class="mkt-vals">
        <div>
          <div style="font-size:11px;color:var(--muted)">OVER</div>
          <div class="mkt-over ${colorClass(pct(tot.over))}">${pct(tot.over)}%</div>
        </div>
        <div class="mkt-badge">${badge(pct(tot.over))}</div>
        <div style="text-align:right">
          <div style="font-size:11px;color:var(--muted)">UNDER</div>
          <div class="mkt-under">${pct(tot.under)}%</div>
        </div>
      </div>
      ${tot.expected_total ? `<div class="mkt-exp">Gözlənilən: ${tot.expected_total}</div>` : ""}
    </div>
    <div class="mkt-card">
      <div class="mkt-name">Korner Handicap (Ev -1.5)</div>
      <div class="mkt-vals">
        <div>
          <div style="font-size:11px;color:var(--muted)">EV ÖRTÜR</div>
          <div class="mkt-over ${colorClass(pct(hcp.home_cover))}">${pct(hcp.home_cover)}%</div>
        </div>
        <div class="mkt-badge">${badge(pct(hcp.home_cover))}</div>
        <div style="text-align:right">
          <div style="font-size:11px;color:var(--muted)">QONAQ</div>
          <div class="mkt-under">${pct(hcp.away_cover)}%</div>
        </div>
      </div>
    </div>`;
}

// ── DİGƏR BAZARLAR ───────────────────────
function fillOther(m1) {
  const grid = document.getElementById("otherGrid");
  if (!grid) return;
  const markets = [
    { title: "⚡ SOT (İstiiqamətli Zərbə)", key: "sot", line: "8.5" },
    { title: "🟨 Kartlar", key: "cards", line: "4.5" },
    { title: "🚫 Faullar", key: "fouls", line: "21.5" },
    { title: "🏳️ Ofsaytlar", key: "offsides", line: "3.5" },
    { title: "🎯 Penalti", key: "penalties", line: "0.5" },
    { title: "🔄 Autlar", key: "throwins", line: "38.5" }
  ];
  grid.innerHTML = markets.map(({ title, key, line }) => {
    const d = m1[key];
    if (!d) return "";
    const op = pct(d.over);
    const up = pct(d.under);
    return `
    <div class="other-card">
      <div class="other-title">${title}</div>
      <div class="other-row">
        <span class="other-key">Over ${line}</span>
        <span class="other-val ${colorClass(op)}">${op}% ${badge(op)}</span>
      </div>
      <div class="other-row">
        <span class="other-key">Under ${line}</span>
        <span class="other-val">${up}%</span>
      </div>
      ${d.expected_total ? `<div class="other-row">
        <span class="other-key">Gözlənilən</span>
        <span class="other-val" style="color:var(--acc)">${d.expected_total}</span>
      </div>` : ""}
    </div>`;
  }).join("");
}

// ── DƏQİQ HESABLAR ───────────────────────
function fillScores(scores) {
  const grid = document.getElementById("scoresGrid");
  if (!grid || !scores) return;
  grid.innerHTML = Object.entries(scores)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([sc, prob]) => {
      const p = Math.round(prob * 100);
      return `<div class="score-pill">
        <span class="score-val">${sc}</span>
        <span class="score-pct">${p}%</span>
      </div>`;
    }).join("");
}

// ── M2 ARAŞDIRMA ─────────────────────────
function fillResearch(m2) {
  const grid = document.getElementById("researchGrid");
  if (!grid || !m2) return;

  const sections = [
    {
      title: "👨‍⚖️ Hakim",
      key: "referee",
      fields: [["Ad", "name"], ["Sarı kart/oyun", "yellow_avg"], ["Qırmızı kart/oyun", "red_avg"], ["Həssaslıq", "foul_sensitivity"]]
    },
    {
      title: "🤕 Zədələr",
      key: "injuries",
      fields: [["Ev (yoxdur)", d => (d.home_absent || []).join(", ") || "Yoxdur"],
               ["Qonaq (yoxdur)", d => (d.away_absent || []).join(", ") || "Yoxdur"],
               ["Əsas oyunçu", d => (d.key_players_missing || []).join(", ") || "Yoxdur"]]
    },
    {
      title: "💪 Motivasiya",
      key: "motivation",
      fields: [["Ev", "home_motivation"], ["Qonaq", "away_motivation"], ["Səbəb", "reason"]]
    },
    {
      title: "😴 Yorğunluq",
      key: "fatigue",
      fields: [["Ev yorğunluğu", "home_fatigue"], ["Qonaq yorğunluğu", "away_fatigue"],
               ["Ev (son oyundan gün)", "days_since_last_match_home"],
               ["Qonaq (son oyundan gün)", "days_since_last_match_away"]]
    },
    {
      title: "🌤 Hava",
      key: "weather",
      fields: [["Şərait", "condition"], ["Temperatur", d => d.temperature ? `${d.temperature}°C` : "—"], ["Küləк", "wind"], ["Təsir", "impact"]]
    },
    {
      title: "📋 Heyət",
      key: "lineup",
      fields: [["Ev sxemi", "home_expected"], ["Qonaq sxemi", "away_expected"],
               ["Ev rotasiya", "home_rotation"], ["Qonaq rotasiya", "away_rotation"]]
    }
  ];

  grid.innerHTML = sections.map(({ title, key, fields }) => {
    const d = m2[key];
    if (!d) return "";
    const status = d.status || "tapılmadı";
    const statusCls = status === "real" ? "status-real" : status === "təxmin" ? "status-guess" : "status-none";
    const statusTxt = status === "real" ? "Real" : status === "təxmin" ? "Təxmin" : "Tapılmadı";

    const rows = fields.map(f => {
      const [label, getter] = f;
      let val = typeof getter === "function" ? getter(d) : (d[getter] ?? "—");
      if (val === null || val === undefined || val === "") val = "—";
      return `<div class="res-row">
        <span class="res-key">${label}</span>
        <span class="res-val">${val}</span>
      </div>`;
    }).join("");

    return `<div class="res-card">
      <div class="res-header">
        <span class="res-title">${title}</span>
        <span class="res-status ${statusCls}">${statusTxt}</span>
      </div>
      ${rows}
    </div>`;
  }).join("");
}

// ── M3 TAKTİKİ ───────────────────────────
function fillTactical(m3) {
  const box = document.getElementById("tacticalBox");
  if (!box || !m3) return;

  const c = m3.carpanlar || {};
  const flags = m3.flags || [];
  const critical = m3.critical_factors || [];

  box.innerHTML = `
    <div class="tac-item">
      <span class="tac-key">Temp</span>
      <span class="tac-val">${m3.tempo || "—"}</span>
    </div>
    <div class="tac-item">
      <span class="tac-key">Ev taktikası</span>
      <span class="tac-val">${m3.taktika_ev || "—"}</span>
    </div>
    <div class="tac-item">
      <span class="tac-key">Qonaq taktikası</span>
      <span class="tac-val">${m3.taktika_qonaq || "—"}</span>
    </div>
    <div class="tac-item">
      <span class="tac-key">Ev motivasiya</span>
      <span class="tac-val c-green">${c.motivasiya_ev || "—"}</span>
    </div>
    <div class="tac-item">
      <span class="tac-key">Qonaq motivasiya</span>
      <span class="tac-val c-yellow">${c.motivasiya_qonaq || "—"}</span>
    </div>
    <div class="tac-item">
      <span class="tac-key">Ev yorğunluq</span>
      <span class="tac-val">${c.yorğunluq_ev || "—"}</span>
    </div>
    <div class="tac-item">
      <span class="tac-key">Qonaq yorğunluq</span>
      <span class="tac-val">${c.yorğunluq_qonaq || "—"}</span>
    </div>
    <div class="tac-item">
      <span class="tac-key">Hakim təsiri</span>
      <span class="tac-val">${c.hakim_təsiri || "—"}</span>
    </div>
    ${flags.length ? `<div class="tac-item" style="grid-column:1/-1">
      <span class="tac-key">Flaglar</span>
      <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:4px">
        ${flags.map(f => `<span class="tac-flag">${f}</span>`).join("")}
      </div>
    </div>` : ""}
    ${critical.length ? `<div class="tac-item" style="grid-column:1/-1">
      <span class="tac-key">Kritik Faktorlar</span>
      <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:4px">
        ${critical.map(f => `<span class="tac-flag" style="border-color:rgba(245,158,11,.3);color:var(--yellow)">${f}</span>`).join("")}
      </div>
    </div>` : ""}
  `;
}

// ── FİNAL QƏRAR ──────────────────────────
function fillFinal(m4) {
  const sg = parseFloat(m4.sistem_guveni || 0);
  const fillS = document.getElementById("fillSistem");
  if (fillS) {
    fillS.style.width = `${(sg / 10) * 100}%`;
    fillS.style.background = barColor(sg);
  }
  document.getElementById("lblSistem").textContent = `${sg.toFixed(1)}/10`;

  const verd = document.getElementById("finalVerdict");
  const qerar = (m4["qərar"] || m4.qerar || "").toUpperCase();
  const isPlay = qerar.includes("OYNARIM") && !qerar.includes("OYNAMARAM");
  verd.textContent = isPlay ? "🏆 OYNARIM ✅" : "🚫 OYNAMARAM ❌";
  verd.className = `verdict ${isPlay ? "v-yes" : "v-no"}`;

  const reason = document.getElementById("finalReason");
  if (reason) reason.textContent = m4["səbəb"] || m4.sebeb || "";

  const dom = document.getElementById("finalDominant");
  if (dom && m4.dominant_modul) dom.textContent = `Dominant modul: ${m4.dominant_modul}`;
}

// ── ANA FUNKSİYA ─────────────────────────
async function startAnalysis() {
  const text = document.getElementById("statsInput").value.trim();
  const errorBox = document.getElementById("errorBox");
  const resultPanel = document.getElementById("resultPanel");

  if (!text) {
    errorBox.textContent = "Statistika mətnini daxil edin.";
    errorBox.classList.remove("hidden");
    return;
  }

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
      body: JSON.stringify({ stats_text: text.slice(0, 6000) })
    });

    const res = await resp.json();
    if (!resp.ok || !res.success) throw new Error(res.error || "Server xətası");

    const { parser, m1, m2, m3, m4 } = res;

    // Oyun başlığı
    document.getElementById("team1Name").textContent = parser?.ev_sahibi || m1?.team1 || "Ev";
    document.getElementById("team2Name").textContent = parser?.qonaq     || m1?.team2 || "Qonaq";
    document.getElementById("leagueTag").textContent = parser?.lig || "Liqa";

    // Modul kartları (hamısı 0-1 arası)
    fillMod("M1", m1?.m1_confidence);
    fillMod("M2", m2?.m2_guveni);
    fillMod("M3", m3?.m3_guveni);
    fillMod("M4", (m4?.sistem_guveni || 0) / 10);

    // Bazarlar (M1-dən)
    fill1x2(m1?.["1x2"] || {});
    fillOU(m1?.over_under);
    fillBtts(m1?.btts || {});
    fillFirstHalf(m1?.first_half);
    fillCorners(m1?.corners);
    fillOther(m1 || {});
    fillScores(m1?.exact_scores);

    // M2 & M3
    fillResearch(m2);
    fillTactical(m3);

    // Final
    fillFinal(m4 || {});

    resultPanel.classList.remove("hidden");
    resultPanel.scrollIntoView({ behavior: "smooth" });

  } catch (err) {
    errorBox.textContent = `Xəta: ${err.message}`;
    errorBox.classList.remove("hidden");
    console.error(err);
  } finally {
    btn.disabled = false;
    btnText.textContent = "Analiz Et";
    spinner.classList.add("hidden");
  }
}