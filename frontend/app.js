const BACKEND_URL = "https://snaq1.onrender.com";

// ── QLobal vəziyyət ───────────────────────
let analysisController = null;
let _m1Data = null, _m2Data = null, _m3Data = null, _m4Data = null;
let _team1 = '—', _team2 = '—';

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

// ── BÖLMƏ AÇ/BAĞLA ───────────────────────
function toggleSection(id) {
  const content = document.getElementById(id);
  const chevron = document.getElementById('chev-' + id);
  if (!content) return;
  const isOpen = content.classList.contains('open');
  content.classList.toggle('open', !isOpen);
  if (chevron) chevron.textContent = isOpen ? '▶' : '▼';
}

// ── KART RƏNGİ (ehtimala görə) ───────────
function setCardColor(cardId, probability) {
  const card = document.getElementById(cardId);
  if (!card) return;
  card.classList.remove('card-hot', 'card-warm', 'card-cold');
  if (probability >= 65) card.classList.add('card-hot');
  else if (probability >= 48) card.classList.add('card-warm');
  else card.classList.add('card-cold');
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
    setCardColor(`card${key}`, p);
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
    setCardColor(`card${key}`, p);
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

// ── PERFORMANS QRAFİKİ ────────────────────
function drawPerformanceChart(m1, team1, team2) {
  const canvas = document.getElementById('performanceChart');
  if (!canvas || !m1) return;

  const dpr = window.devicePixelRatio || 1;
  const W = canvas.offsetWidth || 800;
  const H = 260;
  canvas.width = W * dpr;
  canvas.height = H * dpr;
  canvas.style.height = H + 'px';

  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);

  const x2   = m1['1x2']         || {};
  const btts  = m1.btts           || {};
  const ou    = m1.over_under     || {};
  const fh    = (m1.first_half || {})['1x2'] || {};

  const metrics = [
    { label: 'Qaliblıq %',  home: pct(x2.home_win),          away: pct(x2.away_win)          },
    { label: 'BTTS Hə',     home: pct(btts.yes),              away: pct(btts.no)               },
    { label: 'Over 2.5',    home: pct((ou['2.5']||{}).over),  away: pct((ou['2.5']||{}).under) },
    { label: 'Over 1.5',    home: pct((ou['1.5']||{}).over),  away: pct((ou['1.5']||{}).under) },
    { label: 'İY Qaliblıq', home: pct(fh.home_win),           away: pct(fh.away_win)           },
  ];

  const PAD   = { top: 14, right: 24, bottom: 30, left: 90 };
  const cW    = W - PAD.left - PAD.right;
  const cH    = H - PAD.top  - PAD.bottom;
  const rows  = metrics.length;
  const rowH  = cH / rows;
  const barH  = Math.min(14, rowH * 0.38);
  const gap   = 3;

  ctx.clearRect(0, 0, W, H);

  // Grid lines
  [25, 50, 75, 100].forEach(v => {
    const x = PAD.left + (v / 100) * cW;
    ctx.beginPath();
    ctx.moveTo(x, PAD.top);
    ctx.lineTo(x, PAD.top + cH);
    ctx.strokeStyle = 'rgba(255,255,255,0.05)';
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.fillStyle = 'rgba(100,116,139,0.6)';
    ctx.font = `10px Segoe UI, sans-serif`;
    ctx.textAlign = 'center';
    ctx.fillText(v + '%', x, PAD.top + cH + 16);
  });

  metrics.forEach((m, i) => {
    const midY = PAD.top + i * rowH + rowH / 2;
    const y1   = midY - barH - gap / 2;
    const y2   = midY + gap / 2;

    // Label
    ctx.fillStyle = '#94a3b8';
    ctx.font = `11px Segoe UI, sans-serif`;
    ctx.textAlign = 'right';
    ctx.fillText(m.label, PAD.left - 8, midY + 4);

    // Home bar (blue)
    const hw = (m.home / 100) * cW;
    ctx.fillStyle = '#3b82f6';
    drawRoundRect(ctx, PAD.left, y1, Math.max(hw, 2), barH, 3);

    // Home label inside/outside
    if (m.home > 10) {
      ctx.fillStyle = '#fff';
      ctx.font = `bold 9px Segoe UI, sans-serif`;
      ctx.textAlign = 'left';
      ctx.fillText(m.home + '%', PAD.left + hw - 26, y1 + barH - 2);
    }

    // Away bar (red/orange)
    const aw = (m.away / 100) * cW;
    ctx.fillStyle = '#f59e0b';
    drawRoundRect(ctx, PAD.left, y2, Math.max(aw, 2), barH, 3);

    if (m.away > 10) {
      ctx.fillStyle = '#fff';
      ctx.font = `bold 9px Segoe UI, sans-serif`;
      ctx.textAlign = 'left';
      ctx.fillText(m.away + '%', PAD.left + aw - 26, y2 + barH - 2);
    }
  });

  // Legend update
  const leg = document.getElementById('chartLegend');
  if (leg) {
    leg.innerHTML = `
      <span><span class="legend-dot" style="background:#3b82f6"></span>${team1 || 'Ev komanda'}</span>
      <span><span class="legend-dot" style="background:#f59e0b"></span>${team2 || 'Qonaq komanda'}</span>
    `;
  }
}

function drawRoundRect(ctx, x, y, w, h, r) {
  if (w < r * 2) r = w / 2;
  if (h < r * 2) r = h / 2;
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
  ctx.fill();
}

// ── MODAL: M2/M3/M4 DETAYLI MƏTİN ────────
function openModuleDetail(mod) {
  const overlay = document.getElementById('moduleModal');
  const content = document.getElementById('modalContent');
  if (!overlay || !content) return;

  let html = '';
  if      (mod === 'M2' && _m2Data) html = buildM2Modal(_m2Data);
  else if (mod === 'M3' && _m3Data) html = buildM3Modal(_m3Data);
  else if (mod === 'M4' && _m4Data) html = buildM4Modal(_m4Data);
  else {
    html = `<div class="modal-title">⚠️ Məlumat yoxdur</div>
            <p style="color:var(--muted);font-size:13px;margin-top:8px">
              Əvvəlcə analizi başladın.</p>`;
  }

  content.innerHTML = html;
  overlay.classList.add('active');
  document.body.style.overflow = 'hidden';
}

function closeModal(e) {
  if (e && e.target.id !== 'moduleModal') return;
  document.getElementById('moduleModal').classList.remove('active');
  document.body.style.overflow = '';
}

function buildM2Modal(m2) {
  const guven = ((parseFloat(m2.m2_guveni || 0)) * 10).toFixed(1);

  const sections = [
    {
      title: "👨‍⚖️ Hakim",
      key: "referee",
      fields: [
        ["Ad", "name"],
        ["Sarı kart / oyun", "yellow_avg"],
        ["Qırmızı kart / oyun", "red_avg"],
        ["Foul həssaslığı", "foul_sensitivity"]
      ]
    },
    {
      title: "🤕 Zədə / Yoxlar",
      key: "injuries",
      fields: [
        ["Ev yoxları", d => (d.home_absent || []).join(", ") || "Yoxdur"],
        ["Qonaq yoxları", d => (d.away_absent || []).join(", ") || "Yoxdur"],
        ["Əsas oyunçu", d => (d.key_players_missing || []).join(", ") || "Yoxdur"]
      ]
    },
    {
      title: "💪 Motivasiya",
      key: "motivation",
      fields: [["Ev", "home_motivation"], ["Qonaq", "away_motivation"], ["Səbəb", "reason"]]
    },
    {
      title: "😴 Yorğunluq",
      key: "fatigue",
      fields: [
        ["Ev yorğunluğu", "home_fatigue"],
        ["Qonaq yorğunluğu", "away_fatigue"],
        ["Ev – son oyundan gün", "days_since_last_match_home"],
        ["Qonaq – son oyundan gün", "days_since_last_match_away"]
      ]
    },
    {
      title: "🌤 Hava",
      key: "weather",
      fields: [
        ["Şərait", "condition"],
        ["Temperatur", d => d.temperature ? `${d.temperature}°C` : "—"],
        ["Külək", "wind"],
        ["Oyuna təsir", "impact"]
      ]
    },
    {
      title: "📋 Gözlənilən Heyət",
      key: "lineup",
      fields: [
        ["Ev sxemi", "home_expected"],
        ["Qonaq sxemi", "away_expected"],
        ["Ev rotasiyası", "home_rotation"],
        ["Qonaq rotasiyası", "away_rotation"]
      ]
    }
  ];

  let html = `<div class="modal-title">🔍 M2 Araşdırma Analizi</div>
    <div class="modal-subtitle">Güvən Səviyyəsi: ${guven}/10</div>`;

  sections.forEach(({ title, key, fields }) => {
    const d = m2[key];
    if (!d) return;
    const rows = fields.map(([label, getter]) => {
      let val = typeof getter === 'function' ? getter(d) : (d[getter] ?? '—');
      if (!val || val === '') val = '—';
      return `<div class="modal-row">
        <span class="modal-key">${label}</span>
        <span class="modal-val">${val}</span>
      </div>`;
    }).join('');
    html += `<div class="modal-section">
      <div class="modal-section-title">${title}</div>
      ${rows}
    </div>`;
  });

  return html;
}

function buildM3Modal(m3) {
  const guven = ((parseFloat(m3.m3_guveni || 0)) * 10).toFixed(1);
  const c     = m3.carpanlar || {};
  const flags = m3.flags || [];
  const crit  = m3.critical_factors || [];

  let html = `<div class="modal-title">🧠 M3 Taktiki Analiz</div>
    <div class="modal-subtitle">Güvən Səviyyəsi: ${guven}/10</div>

    <div class="modal-section">
      <div class="modal-section-title">🎯 Ümumi Taktika</div>
      <div class="modal-row"><span class="modal-key">Oyun tempi</span><span class="modal-val">${m3.tempo || '—'}</span></div>
      <div class="modal-row"><span class="modal-key">Ev taktikası</span><span class="modal-val">${m3.taktika_ev || '—'}</span></div>
      <div class="modal-row"><span class="modal-key">Qonaq taktikası</span><span class="modal-val">${m3.taktika_qonaq || '—'}</span></div>
    </div>

    <div class="modal-section">
      <div class="modal-section-title">⚙️ Çarpan Dəyərləri</div>
      <div class="modal-row"><span class="modal-key">Ev motivasiya çarpanı</span><span class="modal-val">${c.motivasiya_ev || '—'}</span></div>
      <div class="modal-row"><span class="modal-key">Qonaq motivasiya çarpanı</span><span class="modal-val">${c.motivasiya_qonaq || '—'}</span></div>
      <div class="modal-row"><span class="modal-key">Ev yorğunluq çarpanı</span><span class="modal-val">${c.yorğunluq_ev || '—'}</span></div>
      <div class="modal-row"><span class="modal-key">Qonaq yorğunluq çarpanı</span><span class="modal-val">${c.yorğunluq_qonaq || '—'}</span></div>
      <div class="modal-row"><span class="modal-key">Hakim təsiri çarpanı</span><span class="modal-val">${c.hakim_təsiri || '—'}</span></div>
    </div>`;

  if (flags.length) {
    html += `<div class="modal-section">
      <div class="modal-section-title">🚩 Flaglar</div>
      <div class="modal-flag-row">
        ${flags.map(f => `<span class="modal-flag">${f}</span>`).join('')}
      </div>
    </div>`;
  }

  if (crit.length) {
    html += `<div class="modal-section">
      <div class="modal-section-title">⚠️ Kritik Faktorlar</div>
      <div class="modal-flag-row">
        ${crit.map(f => `<span class="modal-flag yellow">${f}</span>`).join('')}
      </div>
    </div>`;
  }

  return html;
}

function buildM4Modal(m4) {
  const sg    = parseFloat(m4.sistem_guveni || 0);
  const qerar = (m4["qərar"] || m4.qerar || '').toUpperCase();
  const isPlay = qerar.includes("OYNARIM") && !qerar.includes("OYNAMARAM");
  const sebeb  = m4["səbəb"] || m4.sebeb || '—';

  return `<div class="modal-title">⚖️ M4 Final Qərar</div>
    <div class="modal-subtitle">Sistem Güvəni: ${sg.toFixed(1)}/10</div>

    <div class="modal-section">
      <div class="modal-section-title">🏁 Qərar</div>
      <div style="text-align:center;font-size:22px;font-weight:900;
                  padding:16px;border-radius:10px;margin:8px 0;
                  ${isPlay
                    ? 'background:rgba(34,197,94,.1);color:#22c55e;border:1px solid rgba(34,197,94,.4)'
                    : 'background:rgba(239,68,68,.1);color:#ef4444;border:1px solid rgba(239,68,68,.4)'}">
        ${isPlay ? '🏆 OYNARIM ✅' : '🚫 OYNAMARAM ❌'}
      </div>
    </div>

    <div class="modal-section">
      <div class="modal-section-title">📝 Əsas Səbəb</div>
      <p style="font-size:13px;color:#e2e8f0;line-height:1.7;padding:6px 0">${sebeb}</p>
    </div>

    <div class="modal-section">
      <div class="modal-section-title">📊 Sistem Məlumatları</div>
      <div class="modal-row"><span class="modal-key">Sistem güvəni</span><span class="modal-val">${sg.toFixed(1)} / 10</span></div>
      <div class="modal-row"><span class="modal-key">Dominant modul</span><span class="modal-val">${m4.dominant_modul || '—'}</span></div>
      <div class="modal-row"><span class="modal-key">Final qərar</span><span class="modal-val">${m4["qərar"] || m4.qerar || '—'}</span></div>
    </div>`;
}

// ── DÜYMƏ RESET ──────────────────────────
function resetAnalysisBtn() {
  const btn     = document.getElementById("analyzeBtn");
  const btnText = document.getElementById("btnText");
  const spinner = document.getElementById("btnSpinner");
  btn.classList.remove('btn-stop');
  btnText.textContent = "Analiz Et";
  spinner.classList.add("hidden");
}

// ── ANA FUNKSİYA ─────────────────────────
async function startAnalysis() {
  // Analiz gedərkən düyməyə basılarsa → dayandır
  if (analysisController) {
    analysisController.abort();
    analysisController = null;
    resetAnalysisBtn();
    return;
  }

  const text     = document.getElementById("statsInput").value.trim();
  const errorBox = document.getElementById("errorBox");
  const resultPanel = document.getElementById("resultPanel");

  if (!text) {
    errorBox.textContent = "Statistika mətnini daxil edin.";
    errorBox.classList.remove("hidden");
    return;
  }

  errorBox.classList.add("hidden");
  resultPanel.classList.add("hidden");

  const btn     = document.getElementById("analyzeBtn");
  const btnText = document.getElementById("btnText");
  const spinner = document.getElementById("btnSpinner");

  analysisController = new AbortController();
  btn.classList.add('btn-stop');
  btnText.textContent = "Analizi Dayandır";
  spinner.classList.remove("hidden");

  try {
    const resp = await fetch(`${BACKEND_URL}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stats_text: text.slice(0, 6000) }),
      signal: analysisController.signal
    });

    const res = await resp.json();
    if (!resp.ok || !res.success) throw new Error(res.error || "Server xətası");

    const { parser, m1, m2, m3, m4 } = res;

    // Qlobal məlumatları saxla (modal üçün)
    _m1Data = m1;
    _m2Data = m2;
    _m3Data = m3;
    _m4Data = m4;

    // Oyun başlığı
    _team1 = parser?.ev_sahibi || m1?.team1 || "Ev";
    _team2 = parser?.qonaq     || m1?.team2 || "Qonaq";
    document.getElementById("team1Name").textContent = _team1;
    document.getElementById("team2Name").textContent = _team2;
    document.getElementById("leagueTag").textContent = parser?.lig || "Liqa";

    // Modul kartları
    fillMod("M1", m1?.m1_confidence);
    fillMod("M2", m2?.m2_guveni);
    fillMod("M3", m3?.m3_guveni);
    fillMod("M4", (m4?.sistem_guveni || 0) / 10);

    // Bazarlar
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

    // Qrafik üçün kiçik gecikdirmə (layout tamamlansın)
    setTimeout(() => {
      drawPerformanceChart(_m1Data, _team1, _team2);
      resultPanel.scrollIntoView({ behavior: "smooth" });
    }, 60);

  } catch (err) {
    if (err.name === 'AbortError') return; // istifadəçi dayandırdı
    errorBox.textContent = `Xəta: ${err.message}`;
    errorBox.classList.remove("hidden");
    console.error(err);
  } finally {
    analysisController = null;
    resetAnalysisBtn();
  }
}
