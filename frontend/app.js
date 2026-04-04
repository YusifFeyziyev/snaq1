const BACKEND_URL = "https://snaq1.onrender.com";

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

// ── KART RƏNGİ ───────────────────────────
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
  [["BttsYes", yp], ["BttsNo", np]].forEach(([key, p]) => {
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
    return `<div class="half-row"><span class="half-key">${k}</span><span class="half-val ${colorClass(p)}">${p}%</span></div>`;
  }).join("");

  const ou = fh.over_under || {};
  document.getElementById("fhOu").innerHTML = [
    ["Over 0.5", ou.over_0_5], ["Over 1.5", ou.over_1_5]
  ].map(([k, v]) => {
    const p = pct(v);
    return `<div class="half-row"><span class="half-key">${k}</span><span class="half-val ${colorClass(p)}">${p}%</span></div>`;
  }).join("");

  const bt = fh.btts || {};
  document.getElementById("fhBtts").innerHTML = [
    ["Hər ikisi atar", bt.yes], ["Yox", bt.no]
  ].map(([k, v]) => {
    const p = pct(v);
    return `<div class="half-row"><span class="half-key">${k}</span><span class="half-val ${colorClass(p)}">${p}%</span></div>`;
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
    { title: "⚡ SOT (İstiqamətli Zərbə)", key: "sot", line: "8.5" },
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
    { title: "👨‍⚖️ Hakim", key: "referee",
      fields: [["Ad","name"],["Sarı kart/oyun","yellow_avg"],["Qırmızı kart/oyun","red_avg"],["Həssaslıq","foul_sensitivity"]] },
    { title: "🤕 Zədələr", key: "injuries",
      fields: [["Ev (yoxdur)", d=>(d.home_absent||[]).join(", ")||"Yoxdur"],
               ["Qonaq (yoxdur)", d=>(d.away_absent||[]).join(", ")||"Yoxdur"],
               ["Əsas oyunçu", d=>(d.key_players_missing||[]).join(", ")||"Yoxdur"]] },
    { title: "💪 Motivasiya", key: "motivation",
      fields: [["Ev","home_motivation"],["Qonaq","away_motivation"],["Səbəb","reason"]] },
    { title: "😴 Yorğunluq", key: "fatigue",
      fields: [["Ev yorğunluğu","home_fatigue"],["Qonaq yorğunluğu","away_fatigue"],
               ["Ev (son oyundan gün)","days_since_last_match_home"],
               ["Qonaq (son oyundan gün)","days_since_last_match_away"]] },
    { title: "🌤 Hava", key: "weather",
      fields: [["Şərait","condition"],["Temperatur", d=>d.temperature?`${d.temperature}°C`:"—"],["Külək","wind"],["Təsir","impact"]] },
    { title: "📋 Heyət", key: "lineup",
      fields: [["Ev sxemi","home_expected"],["Qonaq sxemi","away_expected"],
               ["Ev rotasiya","home_rotation"],["Qonaq rotasiya","away_rotation"]] }
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
      return `<div class="res-row"><span class="res-key">${label}</span><span class="res-val">${val}</span></div>`;
    }).join("");
    return `<div class="res-card">
      <div class="res-header">
        <span class="res-title">${title}</span>
        <span class="res-status ${statusCls}">${statusTxt}</span>
      </div>${rows}
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

  // Təhlükəsiz çıxarış
  const tempoVal     = m3.tempo_value     || (m3.tempo && m3.tempo.value)     || m3.tempo     || "—";
  const taktikaEv    = m3.taktika_ev_value|| (m3.taktika_ev && m3.taktika_ev.value) || m3.taktika_ev || "—";
  const taktikaQonaq = m3.taktika_qonaq_value || (m3.taktika_qonaq && m3.taktika_qonaq.value) || m3.taktika_qonaq || "—";

  // Flag və Kritik hissələri ayrıca yığırıq (copy-paste üçün ən təhlükəsiz)
  let extra = "";

  if (flags.length > 0) {
    const flagHTML = flags.map(f => `<span class="tac-flag">${f}</span>`).join("");
    extra += `
      <div class="tac-item" style="grid-column:1/-1">
        <span class="tac-key">Flaglar</span>
        <div style="display:flex; flex-wrap:wrap; gap:6px; margin-top:4px">
          ${flagHTML}
        </div>
      </div>`;
  }

  if (critical.length > 0) {
    const critHTML = critical.map(f => `<span class="tac-flag" style="border-color:rgba(245,158,11,.3);color:var(--yellow)">${f}</span>`).join("");
    extra += `
      <div class="tac-item" style="grid-column:1/-1">
        <span class="tac-key">Kritik Faktorlar</span>
        <div style="display:flex; flex-wrap:wrap; gap:6px; margin-top:4px">
          ${critHTML}
        </div>
      </div>`;
  }

  box.innerHTML = `
    <div class="tac-item"><span class="tac-key">Oyun tempi</span><span class="tac-val">${tempoVal}</span></div>
    <div class="tac-item"><span class="tac-key">Ev taktikası</span><span class="tac-val">${taktikaEv}</span></div>
    <div class="tac-item"><span class="tac-key">Qonaq taktikası</span><span class="tac-val">${taktikaQonaq}</span></div>
    <div class="tac-item"><span class="tac-key">Ev motivasiya</span><span class="tac-val c-green">${c.motivasiya_ev || "—"}</span></div>
    <div class="tac-item"><span class="tac-key">Qonaq motivasiya</span><span class="tac-val c-yellow">${c.motivasiya_qonaq || "—"}</span></div>
    <div class="tac-item"><span class="tac-key">Ev yorğunluq</span><span class="tac-val">${c.yorgunluq_ev || c["yorğunluq_ev"] || "—"}</span></div>
    <div class="tac-item"><span class="tac-key">Qonaq yorğunluq</span><span class="tac-val">${c.yorgunluq_qonaq || c["yorğunluq_qonaq"] || "—"}</span></div>
    <div class="tac-item"><span class="tac-key">Hakim təsiri</span><span class="tac-val">${c.hakim_tesiri || c["hakim_təsiri"] || "—"}</span></div>
    ${extra}
  `;
}

// ── M4 BAZAR QƏRARLARI ────────────────────
function fillM4Markets(m4) {
  const grid = document.getElementById("m4MarketsGrid");
  if (!grid || !m4) return;

  const bazarlar = m4.bazarlar || {};
  const noBet = m4.no_bet_zone_aktiv || false;

  const marketLabels = {
    qol_over_under:      { icon: "⚽", name: "Qol Over/Under" },
    btts:                { icon: "🎯", name: "BTTS" },
    mac_sonucu_1x2:      { icon: "🥅", name: "Oyun Nəticəsi (1X2)" },
    ilk_yari_over_under: { icon: "⏱", name: "İlk Yarı O/U" },
    kart_bazari:         { icon: "🟨", name: "Kart Bazarı" },
    corner_bazari:       { icon: "🚩", name: "Korner Bazarı" },
    handicap:            { icon: "📐", name: "Handicap" },
    ust_ust:             { icon: "🔄", name: "İkinci Yarı Qol" }
  };

  if (Object.keys(bazarlar).length === 0) {
    grid.innerHTML = `<div style="color:var(--muted);font-size:13px;padding:16px;grid-column:1/-1">
      Bazar məlumatı yoxdur.</div>`;
    return;
  }

  grid.innerHTML = Object.entries(bazarlar).map(([key, val]) => {
    if (!val || typeof val !== "object") return "";

    const label = marketLabels[key] || { icon: "📊", name: key };
    const qerar  = (val.qerar || "").toUpperCase();
    const isPlay = qerar === "OYNARIM";
    const isNoBet = noBet || qerar === "" || qerar.includes("OYNAMARAM");

    const secenek = val.secenek || val["seçenek"] || "—";
    const ehtimal = parseFloat(val.ehtimal || 0);
    const ehtPct  = ehtimal <= 1 ? Math.round(ehtimal * 100) : Math.round(ehtimal);
    const guven   = val.guven || val["güvən"] || "⚠️";
    const sebeb   = val.sebeb || val["səbəb"] || "—";
    const dominant = val.dominant || "—";

    const probColor = ehtPct >= 70 ? "#22c55e" : ehtPct >= 55 ? "#3b82f6" : ehtPct >= 40 ? "#f59e0b" : "#ef4444";

    const cardClass = isPlay ? "play" : "noplay";
    const badgeClass = isPlay ? "play" : "noplay";
    const badgeText = isPlay ? "✅ OYNARIM" : "🚫 OYNAMARAM";

    return `
    <div class="m4-market-card ${cardClass}">
      <div class="m4mc-header">
        <span class="m4mc-name">${label.icon} ${label.name}</span>
        <span class="m4mc-guven">${guven}</span>
      </div>
      <div class="m4mc-decision">
        <span class="m4mc-badge ${badgeClass}">${badgeText}</span>
        ${isPlay && secenek !== "—" ? `<span class="m4mc-secenek">→ ${secenek}</span>` : ""}
      </div>
      ${ehtPct > 0 ? `
      <div class="m4mc-prob-row">
        <div class="m4mc-prob-bar">
          <div class="m4mc-prob-fill" style="width:${ehtPct}%;background:${probColor}"></div>
        </div>
        <span class="m4mc-prob-txt" style="color:${probColor}">${ehtPct}%</span>
      </div>` : ""}
      <div class="m4mc-sebeb">${sebeb}</div>
      <div class="m4mc-dominant">Dominant: ${dominant}</div>
    </div>`;
  }).join("");
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

  // Modul güvən çipləri
  const mg = m4.modul_guvenleri || {};
  const mgRow = document.getElementById("modulGuvenRow");
  if (mgRow) {
    mgRow.innerHTML = [
      { label: "M1", val: mg.M1 || 0 },
      { label: "M2", val: mg.M2 || 0 },
      { label: "M3", val: mg.M3 || 0 },
      { label: "Sistem", val: sg }
    ].map(({ label, val }) => {
      const v = parseFloat(val);
      return `<div class="modul-guven-chip">
        <span class="chip-label">${label}</span>
        <span class="chip-val" style="color:${barColor(v)}">${v.toFixed(1)}</span>
      </div>`;
    }).join("");
  }

  const verd = document.getElementById("finalVerdict");
  const qerar = (m4.umumi_qerar || m4["qərar"] || m4.qerar || "").toUpperCase();
  const isPlay = qerar === "OYNARIM" || (qerar.includes("OYNARIM") && !qerar.includes("OYNAMARAM"));
  verd.textContent = isPlay ? "🏆 OYNARIM ✅" : "🚫 OYNAMARAM ❌";
  verd.className = `verdict ${isPlay ? "v-yes" : "v-no"}`;

  const reason = document.getElementById("finalReason");
  if (reason) reason.textContent = m4.umumi_sebeb || m4["səbəb"] || m4.sebeb || "";

  const dom = document.getElementById("finalDominant");
  if (dom && m4.dominant_modul) dom.textContent = `Dominant modul: ${m4.dominant_modul}`;
}

// ── KOMANDA MÜQAYİSƏ CƏDVƏLİ ─────────────
function fillComparisonTable(m1, team1, team2, m4) {
  const wrapper = document.getElementById("comparisonTableWrapper");
  if (!wrapper || !m1) return;

  const x2   = m1["1x2"]       || {};
  const btts  = m1.btts         || {};
  const ou    = m1.over_under   || {};
  const fh    = m1.first_half   || {};
  const fhX2  = (fh["1x2"])    || {};
  const corn  = (m1.corners || {}).total || {};
  const cards = m1.cards        || {};

  const homeWin  = pct(x2.home_win);
  const awayWin  = pct(x2.away_win);
  const drawPct  = pct(x2.draw);
  const bttsYes  = pct(btts.yes);
  const over25   = pct((ou["2.5"]||{}).over);
  const over15   = pct((ou["1.5"]||{}).over);
  const fhHome   = pct(fhX2.home_win);
  const fhAway   = pct(fhX2.away_win);
  const cornExp  = corn.expected_total || "—";
  const cardExp  = cards.expected_total || "—";

  // Gözlənilən qol
  const expGoal = (ou["2.5"] || {}).expected_total || "—";

  // Kömək funksiya: daha yüksək dəyəri highlight et
  function highlight(homeVal, awayVal) {
    const h = parseFloat(homeVal);
    const a = parseFloat(awayVal);
    if (isNaN(h) || isNaN(a) || h === a) return ["td-neutral", "td-neutral"];
    return h > a ? ["td-highlight-home", "td-neutral"] : ["td-neutral", "td-highlight-away"];
  }

  const rows = [
    { stat: "Qalibiyyət ehtimalı", homeVal: `${homeWin}%`, awayVal: `${awayWin}%`, compare: true },
    { stat: "Heç-heçə ehtimalı",   homeVal: `${drawPct}%`, awayVal: `${drawPct}%`, compare: false },
    { stat: "Gözlənilən qol",      homeVal: expGoal, awayVal: "—", compare: false },
    { stat: "Over 1.5 qol",        homeVal: `${over15}%`, awayVal: `${100-over15}%`, compare: true },
    { stat: "Over 2.5 qol",        homeVal: `${over25}%`, awayVal: `${100-over25}%`, compare: true },
    { stat: "BTTS (Hər ikisi atar)",homeVal: `${bttsYes}% Hə`, awayVal: `${pct(btts.no)}% Yox`, compare: false },
    { stat: "İlk yarı qalibiyyəti",homeVal: `${fhHome}%`, awayVal: `${fhAway}%`, compare: true },
    { stat: "Gözlənilən korner",   homeVal: cornExp, awayVal: "—", compare: false },
    { stat: "Gözlənilən kart",     homeVal: cardExp, awayVal: "—", compare: false },
  ];

  const tableRows = rows.map(({ stat, homeVal, awayVal, compare }) => {
    let homeCls = "td-val td-neutral";
    let awayCls = "td-val td-neutral";
    if (compare) {
      const [hc, ac] = highlight(homeVal, awayVal);
      homeCls = `td-val ${hc}`;
      awayCls = `td-val ${ac}`;
    }
    return `<tr>
      <td class="td-val ${homeCls}">${homeVal}</td>
      <td class="td-stat">${stat}</td>
      <td class="td-val ${awayCls}">${awayVal}</td>
    </tr>`;
  }).join("");

  wrapper.innerHTML = `
    <div class="comparison-wrapper">
      <table class="comparison-table">
        <thead>
          <tr>
            <th class="th-home">🏠 ${team1}</th>
            <th class="th-stat">Kateqoriya</th>
            <th class="th-away">✈️ ${team2}</th>
          </tr>
        </thead>
        <tbody>${tableRows}</tbody>
      </table>
    </div>`;
}

// ── TRAYEKTORİYA QRAFİKİ ─────────────────
function seededRng(seed) {
  let s = seed;
  return function() {
    s = (Math.imul(1664525, s) + 1013904223) | 0;
    return ((s >>> 0) / 4294967296);
  };
}

function nameToSeed(name) {
  let h = 5381;
  for (let i = 0; i < name.length; i++) h = (Math.imul(31, h) + name.charCodeAt(i)) | 0;
  return Math.abs(h);
}

function generateTrajectory(winProb, drawProb, teamName, numGames) {
  const rng = seededRng(nameToSeed(teamName));
  let cum = 0;
  const pts = [];
  for (let i = 0; i < numGames; i++) {
    const r = rng();
    let result, gained;
    if (r < winProb) { result = "W"; gained = 1; }       // yuxarı
    else if (r < winProb + drawProb) { result = "D"; gained = 0; }  // düz
    else { result = "L"; gained = -1; }                   // aşağı
    cum += gained;
    pts.push({ g: i + 1, pts: gained, cum, result });
  }
  return pts;
}


function drawTrajectoryChart(m1, team1, team2, m4) {
  const canvas = document.getElementById("trajectoryChart");
  if (!canvas || !m1) return;

  const x2 = m1["1x2"] || {};
  let homeWin  = parseFloat(x2.home_win || 0);
  let awayWin  = parseFloat(x2.away_win || 0);
  let drawProb = parseFloat(x2.draw || 0);
  if (homeWin > 1) homeWin /= 100;
  if (awayWin > 1) awayWin /= 100;
  if (drawProb > 1) drawProb /= 100;

  const N = 15;
  const homeTraj = generateTrajectory(homeWin, drawProb * 0.55, team1, N);
  const awayTraj = generateTrajectory(awayWin, drawProb * 0.45, team2, N);

  const dpr = window.devicePixelRatio || 1;
  const W   = canvas.offsetWidth || 800;
  const H   = 240;
  canvas.width  = W * dpr;
  canvas.height = H * dpr;
  canvas.style.height = H + "px";

  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);

  const PAD = { top: 20, right: 24, bottom: 32, left: 46 };
  const cW  = W - PAD.left - PAD.right;
  const cH  = H - PAD.top  - PAD.bottom;

  const maxPts = N;

  ctx.clearRect(0, 0, W, H);

  // Y grid
  const yTicks = [-15, -10, -5, 0, 5, 10, 15].filter(v => v >= -N && v <= N);
  yTicks.forEach(v => {
    const y = PAD.top + (1 - v / maxPts) * cH;
    ctx.beginPath();
    ctx.moveTo(PAD.left, y);
    ctx.lineTo(PAD.left + cW, y);
    ctx.strokeStyle = "rgba(255,255,255,0.05)";
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.fillStyle = "#64748b";
    ctx.font = "10px Segoe UI, sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(v, PAD.left - 6, y + 4);
  });

  // X axis labels
  [1, 5, 10, 15].forEach(g => {
    const x = PAD.left + ((g - 1) / (N - 1)) * cW;
    ctx.fillStyle = "#64748b";
    ctx.font = "10px Segoe UI, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(`${g}`, x, PAD.top + cH + 16);
  });

  // X axis title
  ctx.fillStyle = "#475569";
  ctx.font = "10px Segoe UI, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText("Oyun №", PAD.left + cW / 2, PAD.top + cH + 28);

  // Y axis title
  ctx.save();
  ctx.translate(12, PAD.top + cH / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillStyle = "#475569";
  ctx.font = "10px Segoe UI, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText("Xal", 0, 0);
  ctx.restore();

  function getX(i) { return PAD.left + (i / (N - 1)) * cW; }
  function getY(cum) { return PAD.top + (0.5 - cum / (maxPts * 2)) * cH; }

  function drawLine(traj, lineColor) {
    // Area fill
    const grad = ctx.createLinearGradient(0, PAD.top, 0, PAD.top + cH);
    grad.addColorStop(0, lineColor.replace(")", ",0.18)").replace("rgb", "rgba"));
    grad.addColorStop(1, lineColor.replace(")", ",0.01)").replace("rgb", "rgba"));

    ctx.beginPath();
    traj.forEach((pt, i) => {
      const x = getX(i);
      const y = getY(pt.cum);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.lineTo(getX(N - 1), PAD.top + cH);
    ctx.lineTo(getX(0), PAD.top + cH);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    // Line
    ctx.beginPath();
    ctx.strokeStyle = lineColor;
    ctx.lineWidth = 2.5;
    ctx.lineJoin = "round";
    traj.forEach((pt, i) => {
      const x = getX(i);
      const y = getY(pt.cum);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Dots
    traj.forEach((pt, i) => {
      const x = getX(i);
      const y = getY(pt.cum);
      const dotColor = pt.result === "W" ? "#22c55e" : pt.result === "D" ? "#f59e0b" : "#ef4444";
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fillStyle = dotColor;
      ctx.fill();
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.strokeStyle = "rgba(0,0,0,0.4)";
      ctx.lineWidth = 1;
      ctx.stroke();
    });
  }

  drawLine(homeTraj, "rgb(59,130,246)");
  drawLine(awayTraj, "rgb(245,158,11)");

  // Mövsüm sonu xal fərqi
  const homeEnd = homeTraj[N - 1].cum;
  const awayEnd = awayTraj[N - 1].cum;
  const diff = homeEnd - awayEnd;
  const diffTxt = diff > 0
    ? `${team1} ${diff} xal üstün`
    : diff < 0
    ? `${team2} ${Math.abs(diff)} xal üstün`
    : "Bərabər nəticə";

  // Legend
  const leg = document.getElementById("chartLegend");
  if (leg) {
    leg.innerHTML = `
      <span><span class="legend-dot" style="background:#3b82f6"></span>${team1} (${homeEnd} xal)</span>
      <span><span class="legend-dot" style="background:#f59e0b"></span>${team2} (${awayEnd} xal)</span>
      <span style="margin-left:auto;font-size:11px;font-weight:700;color:${diff >= 0 ? '#3b82f6' : '#f59e0b'}">${diffTxt}</span>
    `;
  }

  // M4 qərarına görə chart border rəngi
  const chartWrapper = document.getElementById("chartContainerWrapper");
  if (chartWrapper && m4) {
    const qerar = (m4.umumi_qerar || m4["qərar"] || "").toUpperCase();
    chartWrapper.classList.remove("m4-yes", "m4-no");
    if (qerar === "OYNARIM") chartWrapper.classList.add("m4-yes");
    else if (qerar === "OYNAMARAM") chartWrapper.classList.add("m4-no");
  }
}

// ── MODAL ─────────────────────────────────
function openModuleDetail(mod) {
  const overlay = document.getElementById("moduleModal");
  const content = document.getElementById("modalContent");
  if (!overlay || !content) return;
  let html = "";
  if      (mod === "M2" && _m2Data) html = buildM2Modal(_m2Data);
  else if (mod === "M3" && _m3Data) html = buildM3Modal(_m3Data);
  else if (mod === "M4" && _m4Data) html = buildM4Modal(_m4Data);
  else html = `<div class="modal-title">⚠️ Məlumat yoxdur</div>
               <p style="color:var(--muted);font-size:13px;margin-top:8px">Əvvəlcə analizi başladın.</p>`;
  content.innerHTML = html;
  overlay.classList.add("active");
  document.body.style.overflow = "hidden";
}

function closeModal(e) {
  if (e && e.target.id !== "moduleModal") return;
  document.getElementById("moduleModal").classList.remove("active");
  document.body.style.overflow = "";
}

function buildM2Modal(m2) {
  const guven = ((parseFloat(m2.m2_guveni || 0)) * 10).toFixed(1);
  const sections = [
    { title: "👨‍⚖️ Hakim", key: "referee",
      fields: [["Ad","name"],["Sarı kart / oyun","yellow_avg"],["Qırmızı kart / oyun","red_avg"],["Foul həssaslığı","foul_sensitivity"]] },
    { title: "🤕 Zədə / Yoxlar", key: "injuries",
      fields: [["Ev yoxları", d=>(d.home_absent||[]).join(", ")||"Yoxdur"],
               ["Qonaq yoxları", d=>(d.away_absent||[]).join(", ")||"Yoxdur"],
               ["Əsas oyunçu", d=>(d.key_players_missing||[]).join(", ")||"Yoxdur"]] },
    { title: "💪 Motivasiya", key: "motivation",
      fields: [["Ev","home_motivation"],["Qonaq","away_motivation"],["Səbəb","reason"]] },
    { title: "😴 Yorğunluq", key: "fatigue",
      fields: [["Ev yorğunluğu","home_fatigue"],["Qonaq yorğunluğu","away_fatigue"],
               ["Ev – son oyundan gün","days_since_last_match_home"],
               ["Qonaq – son oyundan gün","days_since_last_match_away"]] },
    { title: "🌤 Hava", key: "weather",
      fields: [["Şərait","condition"],["Temperatur", d=>d.temperature?`${d.temperature}°C`:"—"],["Külək","wind"],["Oyuna təsir","impact"]] },
    { title: "📋 Gözlənilən Heyət", key: "lineup",
      fields: [["Ev sxemi","home_expected"],["Qonaq sxemi","away_expected"],
               ["Ev rotasiyası","home_rotation"],["Qonaq rotasiyası","away_rotation"]] }
  ];
  let html = `<div class="modal-title">🔍 M2 Araşdırma Analizi</div>
    <div class="modal-subtitle">Güvən Səviyyəsi: ${guven}/10</div>`;
  sections.forEach(({ title, key, fields }) => {
    const d = m2[key];
    if (!d) return;
    const rows = fields.map(([label, getter]) => {
      let val = typeof getter === "function" ? getter(d) : (d[getter] ?? "—");
      if (!val || val === "") val = "—";
      return `<div class="modal-row"><span class="modal-key">${label}</span><span class="modal-val">${val}</span></div>`;
    }).join("");
    html += `<div class="modal-section"><div class="modal-section-title">${title}</div>${rows}</div>`;
  });
  return html;
}

// ── M3 MODAL ─────────────────────────────
function buildM3Modal(m3) {
  if (!m3) return `<div class="modal-title">⚠️ M3 məlumatı yoxdur</div>`;

  const guven = parseFloat(m3.m3_guveni || 0).toFixed(1);

  const c = m3.carpanlar || {};
  const flags = m3.flags || [];
  const crit = m3.critical_factors || [];

  // Təhlükəsiz çıxarış (Python həm obyekt, həm _value göndərir)
  const tempoVal     = m3.tempo_value     || (m3.tempo && m3.tempo.value)     || m3.tempo     || "—";
  const taktikaEv    = m3.taktika_ev_value|| (m3.taktika_ev && m3.taktika_ev.value) || m3.taktika_ev || "—";
  const taktikaQonaq = m3.taktika_qonaq_value || (m3.taktika_qonaq && m3.taktika_qonaq.value) || m3.taktika_qonaq || "—";

  // Flag və Kritik hissələri ayrıca (copy-paste üçün təhlükəsiz)
  let extra = "";

  if (flags.length > 0) {
    const flagHTML = flags.map(f => `<span class="modal-flag">${f}</span>`).join("");
    extra += `
      <div class="modal-section">
        <div class="modal-section-title">🚩 Flaglar</div>
        <div class="modal-flag-row">${flagHTML}</div>
      </div>`;
  }

  if (crit.length > 0) {
    const critHTML = crit.map(f => `<span class="modal-flag yellow">${f}</span>`).join("");
    extra += `
      <div class="modal-section">
        <div class="modal-section-title">⚠️ Kritik Faktorlar</div>
        <div class="modal-flag-row">${critHTML}</div>
      </div>`;
  }

  return `
    <div class="modal-title">🧠 M3 Taktiki Analiz</div>
    <div class="modal-subtitle">Güvən Səviyyəsi: ${guven}/10</div>

    <div class="modal-section">
      <div class="modal-section-title">🎯 Ümumi Taktika</div>
      <div class="modal-row"><span class="modal-key">Oyun tempi</span><span class="modal-val">${tempoVal}</span></div>
      <div class="modal-row"><span class="modal-key">Ev taktikası</span><span class="modal-val">${taktikaEv}</span></div>
      <div class="modal-row"><span class="modal-key">Qonaq taktikası</span><span class="modal-val">${taktikaQonaq}</span></div>
    </div>

    <div class="modal-section">
      <div class="modal-section-title">⚙️ Çarpan Dəyərləri</div>
      <div class="modal-row"><span class="modal-key">Ev motivasiya çarpanı</span><span class="modal-val">${c.motivasiya_ev || "—"}</span></div>
      <div class="modal-row"><span class="modal-key">Qonaq motivasiya çarpanı</span><span class="modal-val">${c.motivasiya_qonaq || "—"}</span></div>
      <div class="modal-row"><span class="modal-key">Ev yorğunluq çarpanı</span><span class="modal-val">${c.yorgunluq_ev || c["yorğunluq_ev"] || "—"}</span></div>
      <div class="modal-row"><span class="modal-key">Qonaq yorğunluq çarpanı</span><span class="modal-val">${c.yorgunluq_qonaq || c["yorğunluq_qonaq"] || "—"}</span></div>
      <div class="modal-row"><span class="modal-key">Hakim təsiri çarpanı</span><span class="modal-val">${c.hakim_tesiri || c["hakim_təsiri"] || "—"}</span></div>
    </div>

    ${extra}
  `;
}

function buildM4Modal(m4) {
  const sg    = parseFloat(m4.sistem_guveni || 0);
  const qerar = (m4.umumi_qerar || m4["qərar"] || m4.qerar || "").toUpperCase();
  const isPlay = qerar === "OYNARIM" || (qerar.includes("OYNARIM") && !qerar.includes("OYNAMARAM"));
  const sebeb  = m4.umumi_sebeb || m4["səbəb"] || m4.sebeb || "—";
  const bazarlar = m4.bazarlar || {};

  const marketLabels = {
    qol_over_under: "⚽ Qol Over/Under",
    btts: "🎯 BTTS",
    mac_sonucu_1x2: "🥅 1X2 Nəticə",
    ilk_yari_over_under: "⏱ İlk Yarı O/U",
    kart_bazari: "🟨 Kart Bazarı",
    corner_bazari: "🚩 Korner",
    handicap: "📐 Handicap",
    ust_ust: "🔄 İkinci Yarı"
  };

  const mg = m4.modul_guvenleri || {};
  const marketsHtml = Object.entries(bazarlar).map(([key, val]) => {
    if (!val || typeof val !== "object") return "";
    const mq = (val.qerar || "").toUpperCase();
    const mPlay = mq === "OYNARIM";
    const secenek = val.secenek || val["seçenek"] || "";
    const ehtimal = parseFloat(val.ehtimal || 0);
    const ehtPct  = ehtimal <= 1 ? Math.round(ehtimal * 100) : Math.round(ehtimal);
    const guven   = val.guven || val["güvən"] || "";
    const sebeb   = val.sebeb || val["səbəb"] || "—";
    return `
    <div class="m4-modal-market ${mPlay ? "play" : "noplay"}">
      <div class="m4mm-top">
        <span class="m4mm-name">${marketLabels[key] || key}</span>
        <div class="m4mm-badges">
          <span>${guven}</span>
          <span class="m4mm-decision ${mPlay ? "play" : "noplay"}">${mPlay ? "✅ OYNARIM" : "🚫 OYNAMARAM"}</span>
        </div>
      </div>
      ${secenek ? `<div class="m4mm-secenek">→ ${secenek} ${ehtPct > 0 ? `(${ehtPct}%)` : ""}</div>` : ""}
      <div class="m4mm-sebeb">${sebeb}</div>
    </div>`;
  }).join("");

  return `<div class="modal-title">⚖️ M4 Final Qərar</div>
    <div class="modal-subtitle">Sistem Güvəni: ${sg.toFixed(1)}/10</div>

    <div class="modal-section">
      <div class="modal-section-title">📊 Modul Güvənləri</div>
      <div class="modal-row"><span class="modal-key">M1 (Riyazi)</span><span class="modal-val">${(mg.M1||0).toFixed(1)}/10</span></div>
      <div class="modal-row"><span class="modal-key">M2 (Araşdırma)</span><span class="modal-val">${(mg.M2||0).toFixed(1)}/10</span></div>
      <div class="modal-row"><span class="modal-key">M3 (Ekspert)</span><span class="modal-val">${(mg.M3||0).toFixed(1)}/10</span></div>
      <div class="modal-row"><span class="modal-key">Sistem (çəkili)</span><span class="modal-val" style="color:${barColor(sg)}">${sg.toFixed(1)}/10</span></div>
    </div>

    <div class="modal-section">
      <div class="modal-section-title">🏁 Ümumi Qərar</div>
      <div style="text-align:center;font-size:22px;font-weight:900;padding:14px;border-radius:10px;margin:8px 0;
        ${isPlay
          ? "background:rgba(34,197,94,.1);color:#22c55e;border:1px solid rgba(34,197,94,.4)"
          : "background:rgba(239,68,68,.1);color:#ef4444;border:1px solid rgba(239,68,68,.4)"}">
        ${isPlay ? "🏆 OYNARIM ✅" : "🚫 OYNAMARAM ❌"}
      </div>
      <p style="font-size:13px;color:#e2e8f0;line-height:1.7;padding:6px 0">${sebeb}</p>
    </div>

    ${marketsHtml ? `<div class="modal-section">
      <div class="modal-section-title">⚖️ Bazar Qərarları</div>
      ${marketsHtml}
    </div>` : ""}`;
}

// ── DÜYMƏ RESET ──────────────────────────
function resetAnalysisBtn() {
  const btn     = document.getElementById("analyzeBtn");
  const btnText = document.getElementById("btnText");
  const spinner = document.getElementById("btnSpinner");
  btn.classList.remove("btn-stop");
  btnText.textContent = "Analiz Et";
  spinner.classList.add("hidden");
}

// ── ANA FUNKSİYA ─────────────────────────
async function startAnalysis() {
  if (analysisController) {
    analysisController.abort();
    analysisController = null;
    resetAnalysisBtn();
    return;
  }

  const text      = document.getElementById("statsInput").value.trim();
  const errorBox  = document.getElementById("errorBox");
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
  btn.classList.add("btn-stop");
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

    _m1Data = m1;
    _m2Data = m2;
    _m3Data = m3;
    _m4Data = m4;

    _team1 = parser?.ev_sahibi || m1?.team1 || "Ev";
    _team2 = parser?.qonaq     || m1?.team2 || "Qonaq";
    document.getElementById("team1Name").textContent = _team1;
    document.getElementById("team2Name").textContent = _team2;
    document.getElementById("leagueTag").textContent = parser?.lig || "Liqa";

    // ── MODUL KARTLARI (Güvən səviyyələri) ─────────────────────────────
    // Bütün backend-lər indi 0-10 arası göndərir → hamısını /10 edirik
    const m1conf = m1?.m1_guveni || m1?.m1_confidence || 0;
    
    fillMod("M1", m1conf <= 10 ? m1conf / 10 : m1conf / 100);   // köhnə M1 xüsusi halı saxlandı
    fillMod("M2", m2?.m2_guveni || 0);
    fillMod("M3", (m3?.m3_guveni || 0) / 10);
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

    // M4 bazar qərarları
    fillM4Markets(m4 || {});

    // Final qərar
    fillFinal(m4 || {});

    // Komanda müqayisə cədvəli
    fillComparisonTable(m1 || {}, _team1, _team2, m4);

    resultPanel.classList.remove("hidden");

    setTimeout(() => {
      drawTrajectoryChart(_m1Data, _team1, _team2, _m4Data);
      resultPanel.scrollIntoView({ behavior: "smooth" });
    }, 80);

  } catch (err) {
    if (err.name === "AbortError") return;
    errorBox.textContent = `Xəta: ${err.message}`;
    errorBox.classList.remove("hidden");
    console.error(err);
  } finally {
    analysisController = null;
    resetAnalysisBtn();
  }
}
