"""
Publish Malik Invest's industry-group rankings as a self-contained HTML page.

Inputs:
    group_ranks.csv  — one row per group (rank, scores, halal coverage)
    stocks.csv       — one row per (group, ticker) with RS, history, Shariah status

Output:
    A single self-contained HTML file. Branded for Malik Invest, with a
    Shariah filter, status badges on every stock, and a lead-capture footer.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd


# Malik Invest brand palette (dark navy + cyan accent + Montserrat fonts)
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&family=Noto+Kufi+Arabic:wght@500;700&display=swap');

:root {
  --bg: #0a1530;
  --panel: #11203f;
  --panel-2: #182a52;
  --panel-3: #213567;
  --text: #e7ecf5;
  --muted: #8da0c7;
  --accent: #00d1ff;
  --accent-2: #1e88ff;
  --halal:    #36c98c;
  --question: #f5b740;
  --haram:    #ff5d6c;
  --border: rgba(255,255,255,0.08);
  --brand: #00d1ff;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: 'Montserrat', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.5;
}
.container { max-width: 1200px; margin: 0 auto; padding: 24px 20px 80px; }

/* ---- Brand header ---- */
.brand-bar {
  display: flex; align-items: center; gap: 14px;
  padding-bottom: 18px; margin-bottom: 22px;
  border-bottom: 1px solid var(--border);
}
.brand-mark {
  width: 38px; height: 38px; border-radius: 9px;
  background: linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%);
  display: flex; align-items: center; justify-content: center;
  font-family: 'Noto Kufi Arabic', sans-serif; font-weight: 700;
  color: #04253a; font-size: 19px;
}
.brand-name {
  font-weight: 700; letter-spacing: -0.3px; font-size: 17px;
}
.brand-name span { color: var(--accent); }
.brand-tag {
  margin-left: auto; font-size: 12px; color: var(--muted);
  letter-spacing: 0.4px; text-transform: uppercase;
}
@media (max-width: 540px) { .brand-tag { display: none; } }

header.title { margin-bottom: 28px; }
h1 { margin: 0 0 8px; font-size: 30px; font-weight: 700; letter-spacing: -0.6px; }
h1 small { color: var(--muted); font-weight: 400; font-size: 16px; letter-spacing: 0; }
header.title .sub { color: var(--muted); font-size: 14px; max-width: 720px; }
header.title .sub strong { color: var(--text); font-weight: 500; }

section { margin: 36px 0; }
h2 { font-size: 18px; font-weight: 600; margin: 0 0 14px; letter-spacing: -0.2px; }

.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 720px) { .grid { grid-template-columns: 1fr; } }

.card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px 18px;
}
.card h3 { margin: 0 0 10px; font-size: 13px; color: var(--muted);
           text-transform: uppercase; letter-spacing: 0.7px; font-weight: 600; }

ol.ranklist { list-style: none; padding: 0; margin: 0; }
ol.ranklist li {
  display: grid; grid-template-columns: 36px 1fr auto auto;
  gap: 10px; padding: 8px 0;
  border-top: 1px solid var(--border); align-items: baseline;
  cursor: pointer;
}
ol.ranklist li:hover { background: rgba(0,209,255,0.04); }
ol.ranklist li:first-child { border-top: 0; }
ol.ranklist .rk { font-variant-numeric: tabular-nums; color: var(--muted); font-size: 13px; }
ol.ranklist .nm { font-size: 14px; }
ol.ranklist .nm small { color: var(--muted); font-size: 12px; margin-left: 6px; }
ol.ranklist .ph { font-size: 12px; font-variant-numeric: tabular-nums; }
ol.ranklist .sc { font-variant-numeric: tabular-nums; font-size: 13px; min-width: 50px; text-align: right; }

.heatmap { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px; }
.heatmap .cell {
  border-radius: 8px; padding: 12px; border: 1px solid var(--border);
  display: flex; flex-direction: column; gap: 4px;
}
.heatmap .cell .name { font-size: 12px; color: rgba(0,0,0,0.85); font-weight: 600; letter-spacing: 0.3px; }
.heatmap .cell .val  { font-size: 18px; color: rgba(0,0,0,0.9); font-variant-numeric: tabular-nums; font-weight: 600; }
.heatmap .cell .sub  { font-size: 11px; color: rgba(0,0,0,0.65); }

.controls { display: flex; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; align-items: center; }
.controls input, .controls select {
  background: var(--panel-2); color: var(--text); border: 1px solid var(--border);
  border-radius: 6px; padding: 8px 12px; font-size: 13px; outline: none;
  font-family: inherit;
}
.controls input { min-width: 220px; }
.controls input:focus, .controls select:focus { border-color: var(--accent); }
.shariah-toggle {
  display: inline-flex; gap: 4px; padding: 3px;
  background: var(--panel-2); border: 1px solid var(--border); border-radius: 8px;
}
.shariah-toggle button {
  border: 0; background: transparent; color: var(--muted);
  padding: 6px 12px; font-size: 12px; cursor: pointer; border-radius: 5px;
  font-family: inherit; font-weight: 500;
}
.shariah-toggle button.active { background: var(--accent); color: #04253a; }
.shariah-toggle button:hover:not(.active) { color: var(--text); }
.controls .hint { color: var(--muted); font-size: 12px; }

table.full { width: 100%; border-collapse: collapse; font-size: 13px; }
table.full thead th {
  position: sticky; top: 0; background: var(--panel-2);
  text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border);
  font-weight: 600; font-size: 11px; letter-spacing: 0.4px; color: var(--muted);
  cursor: pointer; user-select: none; text-transform: uppercase;
}
table.full thead th.num { text-align: right; }
table.full thead th .arrow { color: var(--accent); margin-left: 6px; }
table.full tbody td {
  padding: 8px 12px; border-bottom: 1px solid var(--border); vertical-align: top;
}
table.full tbody td.num { text-align: right; font-variant-numeric: tabular-nums; }
table.full tbody tr.group-row { cursor: pointer; }
table.full tbody tr.group-row:hover { background: rgba(0,209,255,0.04); }
table.full tbody tr.group-row.expanded { background: rgba(0,209,255,0.06); }
table.full tbody tr.group-row .caret {
  display: inline-block; width: 12px; color: var(--muted); transition: transform 0.15s;
}
table.full tbody tr.group-row.expanded .caret { transform: rotate(90deg); color: var(--accent); }

tr.detail-row > td { padding: 0; background: var(--panel-2); border-bottom: 1px solid var(--border); }
.detail-wrap { padding: 14px 18px 18px; }
.detail-wrap h4 { margin: 0 0 10px; font-size: 11px; color: var(--muted);
                  text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; }
.detail-wrap .empty { color: var(--muted); font-size: 13px; padding: 8px 0; }
.detail-wrap table.stocks { width: 100%; border-collapse: collapse; font-size: 13px; }
.detail-wrap table.stocks th {
  text-align: left; padding: 6px 8px; font-size: 11px;
  color: var(--muted); font-weight: 500; text-transform: uppercase; letter-spacing: 0.3px;
  border-bottom: 1px solid var(--border);
}
.detail-wrap table.stocks th.num { text-align: right; }
.detail-wrap table.stocks td { padding: 7px 8px; border-bottom: 1px solid rgba(255,255,255,0.04); }
.detail-wrap table.stocks td.num { text-align: right; font-variant-numeric: tabular-nums; }
.detail-wrap table.stocks tr:last-child td { border-bottom: 0; }
.detail-wrap table.stocks tr.stock-row { cursor: pointer; }
.detail-wrap table.stocks tr.stock-row:hover { background: rgba(255,255,255,0.03); }
.detail-wrap table.stocks tr.stock-row.expanded { background: rgba(0,209,255,0.05); }
.detail-wrap .ticker { font-weight: 600; letter-spacing: 0.2px; }
.detail-wrap table.stocks tr.stock-row .micro-caret {
  display: inline-block; width: 9px; color: var(--muted); margin-right: 4px;
  transition: transform 0.15s; font-size: 9px;
}
.detail-wrap table.stocks tr.stock-row.expanded .micro-caret {
  transform: rotate(90deg); color: var(--accent);
}

/* Status badges */
.badge {
  display: inline-block; padding: 2px 9px; border-radius: 999px;
  font-size: 11px; font-weight: 600; letter-spacing: 0.3px;
}
.badge-halal    { background: rgba(54,201,140,0.18); color: var(--halal); }
.badge-question { background: rgba(245,183,64,0.18); color: var(--question); }
.badge-haram    { background: rgba(255,93,108,0.18); color: var(--haram); }

/* Halal-percent bar — small inline visualisation */
.halal-bar {
  display: inline-flex; height: 6px; width: 64px;
  border-radius: 3px; overflow: hidden;
  background: rgba(255,93,108,0.25);
  vertical-align: middle; margin-right: 6px;
}
.halal-bar .h { background: var(--halal); }
.halal-bar .q { background: var(--question); }
.halal-pct { font-size: 11px; color: var(--muted); }

.rs-pill {
  display: inline-block; min-width: 30px; padding: 2px 8px;
  border-radius: 999px; font-size: 12px; font-weight: 600;
  font-variant-numeric: tabular-nums; text-align: center;
}
.rs-strong  { background: rgba(54,201,140,0.18);  color: var(--halal); }
.rs-mid     { background: rgba(245,183,64,0.16); color: var(--question); }
.rs-weak    { background: rgba(255,93,108,0.18);  color: var(--haram);  }
.rs-na      { background: rgba(141,160,199,0.16); color: var(--muted); }

.rank-pill {
  display: inline-block; min-width: 32px; padding: 2px 8px;
  border-radius: 999px; font-size: 12px; font-weight: 600;
  font-variant-numeric: tabular-nums; text-align: center;
}
.rank-top    { background: rgba(54,201,140,0.16);  color: var(--halal); }
.rank-mid    { background: rgba(245,183,64,0.14); color: var(--question); }
.rank-bottom { background: rgba(255,93,108,0.14);  color: var(--haram);  }

.chg-up   { color: var(--halal); }
.chg-down { color: var(--haram);  }

.chart-row > td { padding: 0; background: var(--panel-3); }
.chart-wrap {
  padding: 14px 12px 16px;
  display: flex; flex-direction: column; gap: 8px;
}
.chart-wrap .chart-meta {
  display: flex; gap: 16px; align-items: baseline; flex-wrap: wrap;
  font-size: 12px; color: var(--muted);
}
.chart-wrap .chart-meta .name { color: var(--text); font-weight: 600; }
.chart-wrap .chart-meta .reason { font-size: 11px; flex: 1 1 100%; }
.chart-wrap .chart-meta a {
  color: var(--accent); text-decoration: none; margin-left: auto;
}
.chart-wrap .chart-meta a:hover { text-decoration: underline; }

/* CTA / lead-capture */
.cta {
  margin-top: 50px;
  padding: 24px 26px;
  background: linear-gradient(135deg, rgba(0,209,255,0.06) 0%, rgba(30,136,255,0.04) 100%);
  border: 1px solid rgba(0,209,255,0.18);
  border-radius: 14px;
}
.cta h2 { margin: 0 0 8px; font-size: 20px; font-weight: 700; letter-spacing: -0.2px; }
.cta p { margin: 0 0 16px; color: var(--muted); font-size: 14px; max-width: 640px; }
.cta-row {
  display: flex; gap: 10px; flex-wrap: wrap; align-items: stretch;
}
.cta-row input[type=email] {
  flex: 1; min-width: 220px;
  background: var(--panel-2); color: var(--text); border: 1px solid var(--border);
  border-radius: 8px; padding: 11px 14px; font-size: 14px; outline: none;
  font-family: inherit;
}
.cta-row input[type=email]:focus { border-color: var(--accent); }
.cta-row button, .cta-row a.btn {
  background: var(--accent); color: #04253a; border: 0;
  border-radius: 8px; padding: 11px 18px; font-size: 14px; font-weight: 600;
  cursor: pointer; font-family: inherit; text-decoration: none;
  display: inline-flex; align-items: center; justify-content: center;
  white-space: nowrap;
}
.cta-row button:hover, .cta-row a.btn:hover { background: #00b8e0; }
.cta-msg { margin-top: 10px; font-size: 12px; color: var(--muted); min-height: 16px; }

footer { margin-top: 60px; padding-top: 20px; border-top: 1px solid var(--border);
         color: var(--muted); font-size: 12px; }
footer p { margin: 6px 0; }
.kbd { font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 12px;
       background: var(--panel-2); padding: 1px 6px; border-radius: 4px; border: 1px solid var(--border); }
"""

JS = """
(function () {
  const tbl = document.getElementById('fullTable');
  if (!tbl) return;
  const tbody = tbl.tBodies[0];
  const rows = Array.from(tbody.querySelectorAll('tr.group-row'));
  const stocks = window.__STOCKS_BY_GROUP__ || {};

  // --- search / sector / Shariah filter ---
  const search = document.getElementById('search');
  const sectorSel = document.getElementById('sectorSel');
  const shariahButtons = document.querySelectorAll('.shariah-toggle button');
  let shariahFilter = 'all';

  function applyFilter() {
    const q = search.value.trim().toLowerCase();
    const sec = sectorSel.value;
    for (const r of rows) {
      const okSec = !sec || r.dataset.sector === sec;
      const okQ = !q || r.dataset.search.includes(q);
      const halalPct = parseFloat(r.dataset.halalPct);
      let okSh = true;
      if (shariahFilter === 'halal_only') okSh = halalPct >= 0.7;
      else if (shariahFilter === 'avoid_haram') okSh = halalPct >= 0.3;
      const show = okSec && okQ && okSh;
      r.style.display = show ? '' : 'none';
      const detail = r.nextElementSibling;
      if (detail && detail.classList.contains('detail-row') && !show) {
        detail.style.display = 'none';
      } else if (detail && detail.classList.contains('detail-row') && show && r.classList.contains('expanded')) {
        detail.style.display = '';
      }
    }
  }
  search.addEventListener('input', applyFilter);
  sectorSel.addEventListener('change', applyFilter);
  shariahButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      shariahButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      shariahFilter = btn.dataset.filter;
      applyFilter();
    });
  });

  // --- column sort ---
  const ths = tbl.tHead.rows[0].cells;
  const dirs = new Array(ths.length).fill(0);
  function clearArrows() {
    for (const th of ths) {
      const a = th.querySelector('.arrow');
      if (a) a.remove();
    }
  }
  function collapseAll() {
    for (const r of rows) {
      r.classList.remove('expanded');
      const det = r.nextElementSibling;
      if (det && det.classList.contains('detail-row')) det.remove();
    }
  }
  function sortBy(idx, isNum) {
    const dir = dirs[idx] === 1 ? -1 : 1;
    dirs.fill(0); dirs[idx] = dir;
    collapseAll();
    const sorted = rows.slice().sort((a, b) => {
      const av = a.cells[idx].dataset.sort ?? a.cells[idx].textContent;
      const bv = b.cells[idx].dataset.sort ?? b.cells[idx].textContent;
      if (isNum) {
        const af = parseFloat(av); const bf = parseFloat(bv);
        const an = isNaN(af) ? Infinity : af;
        const bn = isNaN(bf) ? Infinity : bf;
        return (an - bn) * dir;
      }
      return av.localeCompare(bv) * dir;
    });
    tbody.replaceChildren(...sorted);
    clearArrows();
    const arrow = document.createElement('span');
    arrow.className = 'arrow';
    arrow.textContent = dir === 1 ? '▲' : '▼';
    ths[idx].appendChild(arrow);
  }
  for (let i = 0; i < ths.length; i++) {
    const isNum = ths[i].classList.contains('num');
    ths[i].addEventListener('click', () => sortBy(i, isNum));
  }

  // --- drill-down helpers ---
  function rsPillClass(rs) {
    if (rs == null || isNaN(rs)) return 'rs-na';
    if (rs >= 80) return 'rs-strong';
    if (rs >= 50) return 'rs-mid';
    return 'rs-weak';
  }
  function fmtPct(x) {
    if (x == null || isNaN(x)) return '—';
    const sign = x >= 0 ? '+' : '';
    return sign + (x * 100).toFixed(1) + '%';
  }
  function fmtPx(x) {
    if (x == null || isNaN(x)) return '—';
    if (x >= 1000) return x.toFixed(0);
    if (x >= 100) return x.toFixed(1);
    return x.toFixed(2);
  }
  function shariahBadge(s) {
    if (s === 'HALAL')        return '<span class="badge badge-halal">Halal</span>';
    if (s === 'QUESTIONABLE') return '<span class="badge badge-question">Questionable</span>';
    if (s === 'HARAM')        return '<span class="badge badge-haram">Haram</span>';
    return '';
  }

  function buildDetail(group) {
    const list = stocks[group] || [];
    const wrap = document.createElement('div');
    wrap.className = 'detail-wrap';
    if (!list.length) {
      wrap.innerHTML = '<h4>Constituent stocks</h4><div class="empty">No constituents mapped to this group yet.</div>';
      return wrap;
    }
    list.sort((a, b) => (b.rs ?? -1) - (a.rs ?? -1));
    let html = '<h4>Constituent stocks · sorted by relative-strength rating · click ticker for chart and Shariah note</h4>';
    html += '<table class="stocks"><thead><tr>'
         + '<th>Ticker</th>'
         + '<th>Shariah</th>'
         + '<th class="num">RS rating</th>'
         + '<th class="num">6-mo change</th>'
         + '<th class="num">Last close</th>'
         + '</tr></thead><tbody>';
    for (const s of list) {
      const cls = rsPillClass(s.rs);
      const rsTxt = (s.rs == null) ? '—' : s.rs;
      const chgCls = (s.chg == null || isNaN(s.chg)) ? '' :
                     (s.chg >= 0 ? 'chg-up' : 'chg-down');
      html += `<tr class="stock-row" data-ticker="${s.t}" data-group="${group.replace(/"/g,'&quot;')}">`
           +  `<td class="ticker"><span class="micro-caret">▶</span>${s.t}</td>`
           +  `<td>${shariahBadge(s.ss)}</td>`
           +  `<td class="num"><span class="rs-pill ${cls}">${rsTxt}</span></td>`
           +  `<td class="num ${chgCls}">${fmtPct(s.chg)}</td>`
           +  `<td class="num">${fmtPx(s.px)}</td></tr>`;
    }
    html += '</tbody></table>';
    wrap.innerHTML = html;

    const stockRows = wrap.querySelectorAll('tr.stock-row');
    for (const sr of stockRows) {
      sr.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleStockRow(sr);
      });
    }
    return wrap;
  }

  function buildChartRow(ticker, stockData) {
    const tvSymbol = ticker.replace('-', '.').toUpperCase();
    const tvUrl = `https://www.tradingview.com/symbols/${encodeURIComponent(tvSymbol)}/`;
    const reason = (stockData && stockData.sr) || '';
    const status = (stockData && stockData.ss) || '';

    const tr = document.createElement('tr');
    tr.className = 'chart-row';
    const td = document.createElement('td');
    td.colSpan = 5;

    const history = (stockData && stockData.h) ? stockData.h.split(';')
      .map(v => v === '' ? null : parseFloat(v))
      .filter(v => v !== null && !isNaN(v)) : [];

    let chartSvg = '';
    if (history.length < 2) {
      chartSvg = '<div style="font-size:12px;color:var(--muted);padding:14px;border:1px dashed var(--border);border-radius:6px;">No price history available.</div>';
    } else {
      const W = 720, H = 200, padL = 50, padR = 12, padT = 12, padB = 28;
      const chartW = W - padL - padR;
      const chartH = H - padT - padB;
      const min = Math.min(...history);
      const max = Math.max(...history);
      const range = (max - min) || 1;
      const xStep = chartW / (history.length - 1);
      const startPx = history[0];
      const endPx = history[history.length - 1];
      const isUp = endPx >= startPx;
      const lineColor = isUp ? '#36c98c' : '#ff5d6c';
      const fillColor = isUp ? 'rgba(54,201,140,0.12)' : 'rgba(255,93,108,0.12)';

      const pts = history.map((p, i) => {
        const x = padL + i * xStep;
        const y = padT + chartH - ((p - min) / range) * chartH;
        return [x, y];
      });
      const linePath = pts.map((p, i) =>
        (i === 0 ? 'M' : 'L') + p[0].toFixed(1) + ',' + p[1].toFixed(1)
      ).join(' ');
      const areaPath = linePath
        + ` L${pts[pts.length-1][0].toFixed(1)},${(padT + chartH).toFixed(1)}`
        + ` L${pts[0][0].toFixed(1)},${(padT + chartH).toFixed(1)} Z`;

      const fmtAxis = (v) => v >= 100 ? v.toFixed(0) : v.toFixed(2);
      const yLabels = [
        { y: padT, v: max },
        { y: padT + chartH/2, v: (min + max) / 2 },
        { y: padT + chartH, v: min },
      ];
      const monthsBack = Math.floor(history.length / 11);
      const xLabels = [];
      for (let m = 0; m <= monthsBack; m += Math.max(1, Math.floor(monthsBack / 4))) {
        const idx = history.length - 1 - m * 11;
        if (idx < 0) break;
        const x = padL + idx * xStep;
        const label = m === 0 ? 'now' : `-${m}mo`;
        xLabels.push({ x, label });
      }

      const yLabelSvg = yLabels.map(l =>
        `<line x1="${padL}" x2="${W - padR}" y1="${l.y}" y2="${l.y}" stroke="rgba(255,255,255,0.05)" stroke-width="1"/>`
        + `<text x="${padL - 6}" y="${l.y + 4}" fill="#8da0c7" font-size="11" text-anchor="end" font-family="Montserrat,sans-serif">${fmtAxis(l.v)}</text>`
      ).join('');
      const xLabelSvg = xLabels.map(l =>
        `<text x="${l.x}" y="${H - 8}" fill="#8da0c7" font-size="11" text-anchor="middle" font-family="Montserrat,sans-serif">${l.label}</text>`
      ).join('');

      const pctChg = ((endPx / startPx) - 1) * 100;
      const pctSign = pctChg >= 0 ? '+' : '';
      const pctColor = isUp ? '#36c98c' : '#ff5d6c';

      chartSvg = `
        <svg viewBox="0 0 ${W} ${H}" width="100%" height="auto" preserveAspectRatio="xMidYMid meet"
             style="display:block; max-width:720px;" role="img" aria-label="${ticker} price chart">
          ${yLabelSvg}
          <path d="${areaPath}" fill="${fillColor}" stroke="none"/>
          <path d="${linePath}" fill="none" stroke="${lineColor}" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/>
          <circle cx="${pts[pts.length-1][0].toFixed(1)}" cy="${pts[pts.length-1][1].toFixed(1)}" r="3.5" fill="${lineColor}"/>
          ${xLabelSvg}
          <text x="${W - padR}" y="${padT + 14}" fill="${pctColor}" font-size="13" font-weight="600" text-anchor="end" font-family="Montserrat,sans-serif">${pctSign}${pctChg.toFixed(1)}%</text>
        </svg>`;
    }

    td.innerHTML = `
      <div class="chart-wrap">
        <div class="chart-meta">
          <span class="name">${ticker}</span>
          ${shariahBadge(status)}
          <span>${history.length} sessions · ~6 months</span>
          <a href="${tvUrl}" target="_blank" rel="noopener">Open on TradingView ↗</a>
          ${reason ? `<span class="reason">Shariah note: ${reason}</span>` : ''}
        </div>
        ${chartSvg}
      </div>`;
    tr.appendChild(td);
    return tr;
  }

  function toggleStockRow(sr) {
    const next = sr.nextElementSibling;
    if (sr.classList.contains('expanded')) {
      sr.classList.remove('expanded');
      if (next && next.classList.contains('chart-row')) next.remove();
      return;
    }
    sr.classList.add('expanded');
    const ticker = sr.dataset.ticker;
    const group = sr.dataset.group;
    const stockData = (stocks[group] || []).find(s => s.t === ticker);
    const chartRow = buildChartRow(ticker, stockData);
    sr.parentNode.insertBefore(chartRow, sr.nextSibling);
  }

  function toggleRow(row) {
    const group = row.dataset.group;
    const next = row.nextElementSibling;
    if (row.classList.contains('expanded')) {
      row.classList.remove('expanded');
      if (next && next.classList.contains('detail-row')) next.remove();
      return;
    }
    row.classList.add('expanded');
    const detail = document.createElement('tr');
    detail.className = 'detail-row';
    const td = document.createElement('td');
    td.colSpan = ths.length;
    td.appendChild(buildDetail(group));
    detail.appendChild(td);
    row.parentNode.insertBefore(detail, row.nextSibling);
  }
  for (const r of rows) {
    r.addEventListener('click', () => toggleRow(r));
  }

  // top/bottom card click also drills in
  for (const li of document.querySelectorAll('ol.ranklist li[data-group]')) {
    li.addEventListener('click', () => {
      const g = li.dataset.group;
      const target = rows.find(r => r.dataset.group === g);
      if (!target) return;
      target.scrollIntoView({ behavior: 'smooth', block: 'center' });
      if (!target.classList.contains('expanded')) toggleRow(target);
    });
  }

  // --- lead capture (mailto fallback — replace with real endpoint when ready) ---
  const ctaForm = document.getElementById('ctaForm');
  if (ctaForm) {
    ctaForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const email = document.getElementById('ctaEmail').value.trim();
      const msg = document.getElementById('ctaMsg');
      if (!email || !email.includes('@')) {
        msg.textContent = 'Please enter a valid email address.';
        msg.style.color = 'var(--haram)';
        return;
      }
      // Replace this with a fetch() to your CRM/Mailchimp/ConvertKit endpoint
      // when you wire it up. For now, open the user's mail client with a
      // pre-filled message — gets you signups while you build the proper flow.
      const subj = encodeURIComponent('Subscribe to Malik Invest weekly');
      const body = encodeURIComponent(`Please add ${email} to the Malik Invest weekly research list.`);
      window.location.href = `mailto:hello@malikinvest.com?subject=${subj}&body=${body}`;
      msg.textContent = 'Thanks — your email client should open. If not, write to hello@malikinvest.com.';
      msg.style.color = 'var(--halal)';
    });
  }
})();
"""


def fmt(x, ndigits=2):
    if pd.isna(x):
        return ""
    return f"{x:.{ndigits}f}"


def fmt_int(x):
    if pd.isna(x):
        return ""
    return f"{int(x)}"


def rank_pill_class(rank: float, n: int) -> str:
    if pd.isna(rank):
        return ""
    if rank <= max(20, n // 10):
        return "rank-top"
    if rank >= n - max(20, n // 10) + 1:
        return "rank-bottom"
    return "rank-mid"


def heat_color(value: float, vmin: float, vmax: float) -> str:
    if pd.isna(value) or vmax == vmin:
        return "#2a3354"
    t = (value - vmin) / (vmax - vmin)
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        u = t * 2
        r = int(54 + (245 - 54) * u)
        g = int(201 + (183 - 201) * u)
        b = int(140 + (64 - 140) * u)
    else:
        u = (t - 0.5) * 2
        r = int(245 + (255 - 245) * u)
        g = int(183 + (93 - 183) * u)
        b = int(64 + (108 - 64) * u)
    return f"rgb({r},{g},{b})"


def halal_bar_html(n_h: int, n_q: int, n_total: int) -> str:
    if n_total <= 0:
        return ""
    pct_h = n_h / n_total
    pct_q = n_q / n_total
    return (
        f'<span class="halal-bar" title="{n_h} halal · {n_q} questionable · {n_total - n_h - n_q} haram">'
        f'<span class="h" style="width:{pct_h*64:.1f}px;"></span>'
        f'<span class="q" style="width:{pct_q*64:.1f}px;"></span>'
        f'</span>'
        f'<span class="halal-pct">{int(pct_h*100)}%</span>'
    )


def stocks_by_group_payload(stocks: pd.DataFrame) -> str:
    """Build the JS object: { group_name: [ {t, rs, chg, px, h, ss, sr}, ... ] }.
    ss = shariah_status, sr = shariah_reason."""
    payload: dict[str, list] = {}
    for grp, sub in stocks.groupby("group"):
        items = []
        for _, r in sub.iterrows():
            hist = r.get("history", "")
            items.append({
                "t":   r["ticker"],
                "rs":  int(r["rs_rating"]) if pd.notna(r["rs_rating"]) else None,
                "chg": float(r["six_month_change"]) if pd.notna(r["six_month_change"]) else None,
                "px":  float(r["last_close"]) if pd.notna(r["last_close"]) else None,
                "h":   hist if pd.notna(hist) else "",
                "ss":  r.get("shariah_status", ""),
                "sr":  r.get("shariah_reason", ""),
            })
        payload[grp] = items
    return json.dumps(payload, separators=(",", ":"))


def build_html(
    df: pd.DataFrame,
    stocks: pd.DataFrame,
    title: str,
    generated: str,
    meta: dict,
) -> str:
    df = df.copy()
    n = len(df)
    df_with_data = df[df["n_with_data"] > 0].copy()

    top = df_with_data.head(20)
    bot = df_with_data.tail(10).iloc[::-1]

    sector_stats = (
        df_with_data.groupby("sector")
        .agg(avg_rank=("rank", "mean"),
             groups=("group", "count"),
             best_rank=("rank", "min"))
        .sort_values("avg_rank")
    )
    vmin = sector_stats["avg_rank"].min() if len(sector_stats) else 0
    vmax = sector_stats["avg_rank"].max() if len(sector_stats) else 1

    def list_li(row):
        ph = halal_bar_html(int(row["n_halal"]), int(row["n_questionable"]), int(row["n_with_data"])) \
             if row["n_with_data"] > 0 else ""
        return (
            f'<li data-group="{row["group"]}">'
            f'<span class="rk">#{int(row["rank"])}</span>'
            f'<span class="nm">{row["group"]}<small>{row["sector"]}</small></span>'
            f'<span class="ph">{ph}</span>'
            f'<span class="sc">{fmt(row["composite_score"])}</span></li>'
        )
    top_html = "\n".join(list_li(r) for _, r in top.iterrows())
    bot_html = "\n".join(list_li(r) for _, r in bot.iterrows())

    heat_cells = []
    for sec, row in sector_stats.iterrows():
        color = heat_color(row["avg_rank"], vmin, vmax)
        heat_cells.append(
            f'<div class="cell" style="background:{color};">'
            f'<span class="name">{sec}</span>'
            f'<span class="val">{row["avg_rank"]:.0f}</span>'
            f'<span class="sub">avg rank · {int(row["groups"])} groups · best #{int(row["best_rank"])}</span>'
            f'</div>'
        )
    heat_html = "\n".join(heat_cells)

    sectors = sorted(df["sector"].dropna().unique())
    sector_options = '<option value="">All sectors</option>' + "".join(
        f'<option value="{s}">{s}</option>' for s in sectors
    )

    body_rows = []
    for _, r in df.iterrows():
        rk = r["rank"]
        cls = rank_pill_class(rk, n)
        rk_html = (f'<span class="rank-pill {cls}">{int(rk)}</span>'
                   if pd.notna(rk) else '<span class="rank-pill">—</span>')
        search_blob = f"{r['group']} {r['sector']}".lower()
        n_h = int(r.get("n_halal", 0))
        n_q = int(r.get("n_questionable", 0))
        nd = int(r["n_with_data"])
        halal_html = halal_bar_html(n_h, n_q, nd) if nd > 0 else ""
        halal_pct = (n_h / nd) if nd > 0 else 0.0
        body_rows.append(
            f'<tr class="group-row" data-group="{r["group"]}" '
            f'data-sector="{r["sector"]}" data-search="{search_blob}" '
            f'data-halal-pct="{halal_pct:.4f}">'
            f'<td class="num" data-sort="{rk if pd.notna(rk) else 99999}">{rk_html}</td>'
            f'<td><span class="caret">▶</span> {r["group"]}</td>'
            f'<td>{r["sector"]}</td>'
            f'<td data-sort="{halal_pct:.4f}">{halal_html}</td>'
            f'<td class="num" data-sort="{r["n_with_data"]}">{fmt_int(r["n_with_data"])}</td>'
            f'<td class="num" data-sort="{r["median_rs_rating"] if pd.notna(r["median_rs_rating"]) else -1}">{fmt_int(r["median_rs_rating"])}</td>'
            f'<td class="num" data-sort="{r["composite_score"] if pd.notna(r["composite_score"]) else -99}">{fmt(r["composite_score"])}</td>'
            f'</tr>'
        )
    table_body = "\n".join(body_rows)

    summary_with_data = int((df["n_with_data"] > 0).sum())
    summary_total = len(df)
    summary_universe = int(df["n_with_data"].sum())

    # Universe-wide Shariah counts
    n_halal_total = int(df["n_halal"].sum())
    n_question_total = int(df["n_questionable"].sum())
    n_haram_total = int(df["n_haram"].sum())
    pct_halal_universe = n_halal_total / summary_universe if summary_universe else 0.0

    stocks_payload = stocks_by_group_payload(stocks)

    is_real = meta.get("is_real_data", False)
    backend = meta.get("backend", "unknown")
    warning_banner = ""
    if not is_real:
        warning_banner = f"""
  <div style="background:#ff5d6c; color:#fff; padding:14px 20px; border-radius:8px;
              margin-bottom:18px; font-weight:600; font-size:14px;
              display:flex; align-items:center; gap:12px;">
    <span style="font-size:20px;">⚠</span>
    <span>
      <strong>DEMO DATA — NOT REAL PRICES.</strong>
      This page was built using <code style="background:rgba(0,0,0,0.2); padding:2px 6px; border-radius:3px;">backend={backend}</code>,
      not live market data. All prices, RS ratings, and rankings are
      synthetic and meaningless. Do not publish this version. Re-run
      with <code style="background:rgba(0,0,0,0.2); padding:2px 6px; border-radius:3px;">--backend yfinance</code>
      for real data.
    </span>
  </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Weekly industry-group rankings with AAOIFI-aligned Shariah status. Free research from Malik Invest.">
<style>{CSS}</style>
</head>
<body>
<div class="container">
{warning_banner}
  <div class="brand-bar">
    <div class="brand-mark">م</div>
    <div class="brand-name">Malik <span>Invest</span></div>
    <div class="brand-tag">Weekly Halal Equity Research</div>
  </div>

  <header class="title">
    <h1>Industry Group Rankings <small>· week of {generated}</small></h1>
    <div class="sub">
      <strong>197 industry groups, ranked.</strong> Each group's relative-strength
      score is computed from a 6-month weighted price formula across its
      constituent stocks. Each constituent is also screened for Shariah status
      using AAOIFI methodology — business-activity test plus financial-ratio
      review where data is available. Click any group to expand its stocks;
      click any ticker for a chart and the Shariah note for that company.
    </div>
  </header>

  <section>
    <div class="grid">
      <div class="card">
        <h3>Top 20 Groups</h3>
        <ol class="ranklist">{top_html}</ol>
      </div>
      <div class="card">
        <h3>Bottom 10 Groups</h3>
        <ol class="ranklist">{bot_html}</ol>
      </div>
    </div>
  </section>

  <section>
    <h2>Sector heatmap (avg group rank)</h2>
    <div class="heatmap">{heat_html}</div>
  </section>

  <section>
    <h2>Full ranking — all {summary_total} groups</h2>
    <div class="controls">
      <input id="search" type="text" placeholder="Search group or sector…" />
      <select id="sectorSel">{sector_options}</select>
      <div class="shariah-toggle" role="group" aria-label="Shariah filter">
        <button data-filter="all" class="active" type="button">All groups</button>
        <button data-filter="avoid_haram" type="button">Avoid Haram (≥30% halal)</button>
        <button data-filter="halal_only" type="button">Halal-leaning (≥70% halal)</button>
      </div>
      <span class="hint">Click a row to drill in · click a column header to sort.</span>
    </div>
    <table class="full" id="fullTable">
      <thead>
        <tr>
          <th class="num">Rank</th>
          <th>Group</th>
          <th>Sector</th>
          <th>% Halal</th>
          <th class="num"># Stocks</th>
          <th class="num">Median RS</th>
          <th class="num">Composite</th>
        </tr>
      </thead>
      <tbody>{table_body}</tbody>
    </table>
  </section>

  <section class="cta">
    <h2>Get this every week — for free</h2>
    <p>
      We send the updated rankings, plus written commentary on the leading
      groups, the rotation between sectors, and the halal-investible names that
      look interesting — every Friday after market close. No spam, just the
      work. Unsubscribe in one click.
    </p>
    <form id="ctaForm" class="cta-row">
      <input id="ctaEmail" type="email" required placeholder="you@example.com" />
      <button type="submit">Send me the weekly</button>
    </form>
    <div id="ctaMsg" class="cta-msg"></div>
  </section>

  <footer>
    <p><strong>Methodology.</strong> Per-stock 6-month weighted relative
       strength is computed as
       <span class="kbd">0.4·(P/P₋₆₅) + 0.2·(P/P₋₁₃₀) + 0.2·(P/P₋₁₉₅) + 0.2·(P/P₋₂₆₀)</span>
       and converted to a 1–99 percentile rating against the full universe.
       The composite z-score blends median RS rating (60%) with annualised
       price-trend slope (40%); groups are ranked 1 (strongest) to N (weakest).
       Shariah classification uses AAOIFI Shariah Standard No. 21 — business
       activity screen plus the three financial ratios (debt ≤30% of market
       cap, interest-bearing assets ≤30%, impure income ≤5%).</p>
    <p><strong>Universe.</strong> {summary_universe} stocks across
       {summary_total} groups · {n_halal_total} marked Halal
       ({pct_halal_universe:.0%}) · {n_question_total} Questionable
       ({n_question_total/summary_universe:.0%}) · {n_haram_total} Haram
       ({n_haram_total/summary_universe:.0%}).</p>
    <p><strong>Disclaimer.</strong> Shariah classifications here are a model,
       not a fatwa. Cross-check against Musaffa, Zoya, or your scholar before
       acting. Nothing here is investment advice. Equity prices may fall as
       well as rise.</p>
    <p>© Malik Invest. All rights reserved. <span style="opacity:0.6;">Data source: {backend}{" · LIVE" if is_real else " · SYNTHETIC — NOT FOR PUBLICATION"}</span></p>
  </footer>
</div>
<script>window.__STOCKS_BY_GROUP__ = {stocks_payload};</script>
<script>{JS}</script>
</body>
</html>
"""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="src", default="group_ranks.csv")
    p.add_argument("--in-stocks", dest="src_stocks", default="stocks.csv")
    p.add_argument("--in-meta", dest="src_meta", default="meta.json")
    p.add_argument("--out", dest="dst", default="group_ranks.html")
    p.add_argument("--title", default="Malik Invest · Industry Group Rankings")
    args = p.parse_args()

    df = pd.read_csv(args.src)
    stocks = pd.read_csv(args.src_stocks)
    # Read run metadata if available — defaults assume real data is fine
    # only when meta.json explicitly says so.
    meta = {"backend": "unknown", "is_real_data": False}
    meta_path = Path(args.src_meta)
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())

    generated = datetime.now().strftime("%B %-d, %Y")
    html = build_html(df, stocks, args.title, generated, meta)
    Path(args.dst).write_text(html, encoding="utf-8")
    size_kb = len(html) / 1024
    banner = "REAL DATA" if meta.get("is_real_data") else "DEMO DATA — DO NOT PUBLISH"
    print(f"Wrote {args.dst}  ({size_kb:.1f} KB, "
          f"{len(df)} groups, {len(stocks)} stock rows) [{banner}]")


if __name__ == "__main__":
    main()
