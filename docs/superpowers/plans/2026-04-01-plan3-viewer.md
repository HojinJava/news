# Viewer Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** viewer.html을 카테고리 스위처 + 시장 데이터 카드 + 차트가 있는 뷰어로 전면 개편.

**Architecture:** 정적 HTML 단일 파일. JS가 `data/registry.json` → `data/{slug}/config.json` + `news.json` + `market.json` 순서로 로드. 카드는 `[시간][출처라벨들] / 헤드라인 / 요약 / [W±%][C±%][N±%][K±%]` 레이아웃. 차트는 순수 SVG(외부 라이브러리 없음).

**Tech Stack:** HTML5, CSS3, Vanilla JS (ES2020), SVG

**선행 조건:** Plan 1 완료 (data/ 구조 + news.json v2.0.0)

---

### Task 1: 기존 viewer.html 백업 + 기본 뼈대 구성

**Files:**
- Modify: `viewer.html`

- [ ] **Step 1: 백업**

```bash
cp /mnt/d/develope/workspace/news/viewer.html /mnt/d/develope/workspace/news/viewer.html.bak
```

- [ ] **Step 2: viewer.html을 아래 뼈대로 교체**

`viewer.html` 전체를 아래 내용으로 교체:

```html
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>뉴스-시장 타임라인</title>
<style>
/* ── CSS 변수 ── */
:root {
  --bg: #0a0a0f;
  --surface: #12121a;
  --surface2: #1a1a26;
  --border: #2a2a3a;
  --text: #e8e8f0;
  --text-muted: #8888aa;
  --accent: #6b7cff;
  --critical: #ff4455;
  --major: #ff8c42;
  --minor: #6b7cff;
  --verified: #44cc88;
  --up: #44cc88;
  --down: #ff4455;
  --flat: #8888aa;
  --sidebar-w: 240px;
  --header-h: 56px;
  font-size: 14px;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: 'Pretendard', 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif;
  height: 100vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* ── 상단 헤더 ── */
#header {
  height: var(--header-h);
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 20px;
  gap: 16px;
  flex-shrink: 0;
  z-index: 100;
}
#header h1 { font-size: 15px; font-weight: 700; color: var(--text); }
#market-legend {
  display: flex; gap: 10px; margin-left: 12px; flex-wrap: wrap;
}
.legend-item {
  font-size: 11px; color: var(--text-muted);
  background: var(--surface2); border: 1px solid var(--border);
  padding: 3px 8px; border-radius: 4px;
}
.legend-key { color: var(--accent); font-weight: 700; }

/* ── 본문 레이아웃 ── */
#body-wrap {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* ── 왼쪽 사이드바 (카테고리) ── */
#sidebar {
  width: var(--sidebar-w);
  background: var(--surface);
  border-right: 1px solid var(--border);
  overflow-y: auto;
  flex-shrink: 0;
  padding: 16px 0;
}
#sidebar h2 {
  font-size: 10px; font-weight: 600; color: var(--text-muted);
  text-transform: uppercase; letter-spacing: 0.08em;
  padding: 0 16px 8px;
}
.cat-item {
  display: block; width: 100%;
  padding: 10px 16px;
  background: none; border: none; cursor: pointer;
  color: var(--text-muted); font-size: 13px; text-align: left;
  border-left: 3px solid transparent;
  transition: all 0.15s;
}
.cat-item:hover { color: var(--text); background: var(--surface2); }
.cat-item.active {
  color: var(--accent); border-left-color: var(--accent);
  background: rgba(107,124,255,0.08);
}
.cat-item .cat-date {
  display: block; font-size: 10px; color: var(--text-muted); margin-top: 2px;
}

/* ── 타임라인 메인 영역 ── */
#timeline-wrap {
  flex: 1;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 20px;
}
#timeline {
  display: flex;
  gap: 0;
  height: 100%;
  min-width: max-content;
  position: relative;
}

/* ── 가로 타임라인 선 ── */
#timeline::before {
  content: '';
  position: absolute;
  left: 0; right: 0;
  top: 52px;
  height: 2px;
  background: linear-gradient(to right, transparent, var(--border) 40px, var(--border) calc(100% - 40px), transparent);
  pointer-events: none;
}

/* ── 날짜 컬럼 ── */
.day-col {
  width: 300px;
  min-width: 300px;
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 0 10px;
  flex-shrink: 0;
}

/* ── 날짜 헤더 ── */
.day-header {
  padding: 0 0 12px;
  position: relative;
}
.day-dot {
  width: 10px; height: 10px;
  background: var(--accent); border-radius: 50%;
  border: 2px solid var(--bg);
  position: absolute; top: 6px; left: 50%;
  transform: translateX(-50%);
}
.day-label {
  font-size: 13px; font-weight: 700; color: var(--text);
  text-align: center; padding-top: 24px;
}
.day-market-row {
  display: flex; flex-wrap: wrap; gap: 4px; justify-content: center;
  margin-top: 6px;
}

/* ── 날짜별 시장 칩 ── */
.mkt-chip {
  font-size: 10px; font-weight: 600;
  padding: 2px 6px; border-radius: 3px;
  background: var(--surface2); border: 1px solid var(--border);
}
.mkt-chip.up   { color: var(--up);   border-color: rgba(68,204,136,0.3); }
.mkt-chip.down { color: var(--down); border-color: rgba(255,68,85,0.3); }
.mkt-chip.flat { color: var(--flat); }

/* ── 이벤트 카드 목록 ── */
.day-events {
  display: flex; flex-direction: column; gap: 8px;
  overflow-y: auto;
  flex: 1;
  padding-bottom: 8px;
}

/* ── 이벤트 카드 ── */
.evt-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
  min-height: 100px;
}
.evt-card:hover { border-color: var(--accent); box-shadow: 0 2px 12px rgba(107,124,255,0.15); }
.evt-card.expanded { border-color: var(--accent); }

.evt-head {
  padding: 12px 14px 10px;
  display: flex; flex-direction: column; gap: 6px;
}
.evt-meta {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
}
.evt-time { font-size: 11px; color: var(--text-muted); font-variant-numeric: tabular-nums; }
.src-label {
  font-size: 10px; padding: 1px 6px; border-radius: 3px;
  background: var(--surface2); border: 1px solid var(--border); color: var(--text-muted);
}
.imp-badge {
  font-size: 10px; font-weight: 700; padding: 1px 6px; border-radius: 3px;
  text-transform: uppercase; letter-spacing: 0.04em;
}
.imp-badge.critical { background: rgba(255,68,85,0.15); color: var(--critical); border: 1px solid rgba(255,68,85,0.3); }
.imp-badge.major    { background: rgba(255,140,66,0.15); color: var(--major);    border: 1px solid rgba(255,140,66,0.3); }
.imp-badge.minor    { background: rgba(107,124,255,0.10); color: var(--minor);   border: 1px solid rgba(107,124,255,0.3); }

.evt-title {
  font-size: 13px; font-weight: 600; color: var(--text);
  line-height: 1.4;
}
.evt-summary {
  font-size: 12px; color: var(--text-muted); line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.evt-market-row {
  display: flex; flex-wrap: wrap; gap: 4px; padding: 0 14px 10px;
}

/* ── 상세 펼치기 영역 ── */
.evt-detail {
  display: none;
  border-top: 1px solid var(--border);
}
.evt-card.expanded .evt-detail { display: block; }

.detail-tabs {
  display: flex; border-bottom: 1px solid var(--border);
}
.tab-btn {
  flex: 1; padding: 8px; background: none; border: none; cursor: pointer;
  font-size: 11px; color: var(--text-muted);
  border-bottom: 2px solid transparent;
  transition: all 0.15s;
}
.tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); }

.tab-pane { display: none; padding: 12px 14px; }
.tab-pane.active { display: block; }

/* ── 출처 목록 ── */
.src-list { display: flex; flex-direction: column; gap: 8px; }
.src-item {
  background: var(--surface2); border: 1px solid var(--border);
  border-radius: 6px; padding: 10px 12px;
}
.src-item-header {
  display: flex; justify-content: space-between; align-items: center; gap: 8px;
  margin-bottom: 4px;
}
.src-item-name { font-size: 11px; font-weight: 600; color: var(--accent); }
.src-item-meta { font-size: 10px; color: var(--text-muted); }
.src-item-title { font-size: 12px; font-weight: 600; color: var(--text); margin-bottom: 4px; }
.src-item-summary { font-size: 11px; color: var(--text-muted); line-height: 1.5; margin-bottom: 6px; }
.src-item-footer {
  display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 4px;
}
.src-item-views { font-size: 10px; color: var(--text-muted); }
.src-link {
  font-size: 10px; color: var(--accent); text-decoration: none;
  border: 1px solid rgba(107,124,255,0.3); padding: 2px 8px; border-radius: 3px;
}
.src-link:hover { background: rgba(107,124,255,0.1); }

/* ── SVG 차트 ── */
.chart-wrap {
  width: 100%; overflow: hidden;
}
.chart-wrap svg { width: 100%; height: 160px; display: block; }

/* ── 오류/로딩 ── */
#loading {
  position: fixed; inset: 0;
  background: var(--bg);
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; color: var(--text-muted);
  z-index: 200;
}
#error-msg {
  padding: 40px; text-align: center; color: var(--down); font-size: 13px;
}

@media (max-width: 768px) {
  :root { --sidebar-w: 0px; }
  #sidebar { display: none; }
  .day-col { width: calc(100vw - 32px); min-width: calc(100vw - 32px); }
}
</style>
</head>
<body>

<div id="loading">데이터 불러오는 중...</div>

<div id="header">
  <h1 id="cat-title">뉴스-시장 타임라인</h1>
  <div id="market-legend"></div>
</div>

<div id="body-wrap">
  <nav id="sidebar">
    <h2>카테고리</h2>
    <div id="cat-list"></div>
  </nav>
  <div id="timeline-wrap">
    <div id="timeline"></div>
  </div>
</div>

<script>
// ── 상태 ─────────────────────────────────────────────────────────────
let currentSlug = null;
let newsData    = null;
let marketData  = null;
let configData  = null;

// ── 유틸 ─────────────────────────────────────────────────────────────
function fmt_delta(pct) {
  if (pct == null || pct === 0) return null;
  const sign = pct > 0 ? '+' : '';
  return `${sign}${pct.toFixed(2)}%`;
}
function delta_class(pct) {
  if (!pct || Math.abs(pct) < 0.05) return 'flat';
  return pct > 0 ? 'up' : 'down';
}
function fmt_views(n) {
  if (!n || n < 0) return '';
  if (n >= 1000000) return `${(n/1000000).toFixed(1)}M 뷰`;
  if (n >= 1000)    return `${(n/1000).toFixed(0)}K 뷰`;
  return `${n} 뷰`;
}
function fmt_date_label(dateStr) {
  const d = new Date(dateStr + 'T00:00:00Z');
  return d.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric', weekday: 'short', timeZone: 'UTC' });
}
function fmt_time(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  return d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Seoul' });
}

// ── 데이터 로드 ───────────────────────────────────────────────────────
async function load_json(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path} 로드 실패 (${r.status})`);
  return r.json();
}

async function load_category(slug) {
  currentSlug = slug;
  document.getElementById('loading').style.display = 'flex';
  try {
    [configData, newsData] = await Promise.all([
      load_json(`data/${slug}/config.json`),
      load_json(`data/${slug}/news.json`),
    ]);
    try {
      marketData = await load_json(`data/${slug}/market.json`);
    } catch { marketData = null; }

    render_header();
    render_timeline();
    update_active_cat(slug);
  } catch (e) {
    document.getElementById('timeline').innerHTML = `<div id="error-msg">오류: ${e.message}</div>`;
  } finally {
    document.getElementById('loading').style.display = 'none';
  }
}

async function init() {
  let registry;
  try {
    registry = await load_json('data/registry.json');
  } catch {
    registry = { categories: [{ slug: 'iran-war', name: '이란-이스라엘 전쟁', last_updated: '' }] };
  }
  render_sidebar(registry.categories);
  if (registry.categories.length > 0) {
    await load_category(registry.categories[0].slug);
  }
}

// ── 렌더링 ────────────────────────────────────────────────────────────
function render_header() {
  document.getElementById('cat-title').textContent = configData.name || '타임라인';
  const leg = document.getElementById('market-legend');
  leg.innerHTML = (configData.markets || []).map(m =>
    `<span class="legend-item"><span class="legend-key">${m.key}</span> ${m.label}</span>`
  ).join('');
}

function render_sidebar(categories) {
  const list = document.getElementById('cat-list');
  list.innerHTML = categories.map(c => `
    <button class="cat-item" data-slug="${c.slug}" onclick="load_category('${c.slug}')">
      ${c.name}
      <span class="cat-date">${c.last_updated ? c.last_updated.slice(0,10) : ''}</span>
    </button>
  `).join('');
}

function update_active_cat(slug) {
  document.querySelectorAll('.cat-item').forEach(el => {
    el.classList.toggle('active', el.dataset.slug === slug);
  });
}

function get_daily_market(date) {
  if (!marketData || !configData) return [];
  const mkts = configData.markets || [];
  return mkts.map(m => {
    const ticker_data = marketData.tickers?.[m.ticker];
    const day = ticker_data?.daily?.find(d => d.date === date);
    if (!day) return null;
    const prev = ticker_data?.daily?.filter(d => d.date < date).slice(-1)[0];
    const baseline = prev?.close || day.open;
    const delta = baseline ? (day.close - baseline) / baseline * 100 : 0;
    return { key: m.key, label: m.label, delta };
  }).filter(Boolean);
}

function get_event_market(event) {
  if (!event.market_impact) return [];
  const mkts = configData?.markets || [];
  return mkts.map(m => {
    const mi = event.market_impact[m.key];
    if (!mi) return null;
    return { key: m.key, delta: mi.delta_pct };
  }).filter(Boolean);
}

function render_mkt_chips(items) {
  return items.map(item => {
    const d = fmt_delta(item.delta);
    if (!d) return `<span class="mkt-chip flat">${item.key} —</span>`;
    return `<span class="mkt-chip ${delta_class(item.delta)}">${item.key} ${d}</span>`;
  }).join('');
}

function render_timeline() {
  const tl = document.getElementById('timeline');
  if (!newsData?.events?.length) {
    tl.innerHTML = '<div style="padding:40px;color:var(--text-muted);font-size:13px;">이벤트 없음</div>';
    return;
  }

  // 날짜별 그룹
  const by_date = {};
  for (const evt of newsData.events) {
    const d = evt.date.slice(0, 10);
    if (!by_date[d]) by_date[d] = [];
    by_date[d].push(evt);
  }
  const dates = Object.keys(by_date).sort();

  tl.innerHTML = dates.map(date => {
    const events = by_date[date];
    const daily_mkts = get_daily_market(date);

    const events_html = events.map(evt => render_event_card(evt)).join('');
    const day_chips   = render_mkt_chips(daily_mkts);

    return `
      <div class="day-col">
        <div class="day-header">
          <div class="day-dot"></div>
          <div class="day-label">${fmt_date_label(date)}</div>
          <div class="day-market-row">${day_chips}</div>
        </div>
        <div class="day-events">${events_html}</div>
      </div>
    `;
  }).join('');
}

function render_event_card(evt) {
  const mkts = get_event_market(evt);
  const chips = render_mkt_chips(mkts);

  const sources = [...new Set((evt.articles || []).map(a => a.source))];
  const src_labels = sources.slice(0, 3).map(s =>
    `<span class="src-label">${s}</span>`
  ).join('');

  const first_time = evt.articles?.[0]?.published_date;
  const time_str = fmt_time(first_time);

  return `
    <div class="evt-card" id="evt-${evt.event_id}" onclick="toggle_card('${evt.event_id}')">
      <div class="evt-head">
        <div class="evt-meta">
          ${time_str ? `<span class="evt-time">${time_str}</span>` : ''}
          ${src_labels}
          <span class="imp-badge ${evt.importance}">${evt.importance}</span>
        </div>
        <div class="evt-title">${evt.title}</div>
        <div class="evt-summary">${evt.summary}</div>
      </div>
      ${chips ? `<div class="evt-market-row">${chips}</div>` : ''}
      <div class="evt-detail">
        <div class="detail-tabs">
          <button class="tab-btn active" onclick="switch_tab(event,'${evt.event_id}','sources')">출처 목록</button>
          <button class="tab-btn"        onclick="switch_tab(event,'${evt.event_id}','chart')">차트</button>
        </div>
        <div class="tab-pane active" id="tab-sources-${evt.event_id}">
          ${render_sources(evt.articles || [])}
        </div>
        <div class="tab-pane" id="tab-chart-${evt.event_id}">
          ${render_chart(evt)}
        </div>
      </div>
    </div>
  `;
}

function render_sources(articles) {
  if (!articles.length) return '<p style="color:var(--text-muted);font-size:12px;padding:4px 0;">기사 없음</p>';
  return `<div class="src-list">${articles.map(a => `
    <div class="src-item">
      <div class="src-item-header">
        <span class="src-item-name">${a.source}</span>
        <span class="src-item-meta">${fmt_time(a.published_date)} · ${a.verification_status === 'verified' ? '✓ 검증' : a.verification_status}</span>
      </div>
      <div class="src-item-title">${a.title_ko || a.title}</div>
      <div class="src-item-summary">${a.summary_ko || a.summary || ''}</div>
      <div class="src-item-footer">
        <span class="src-item-views">${fmt_views(a.view_count)}</span>
        <a class="src-link" href="${a.url}" target="_blank" rel="noopener">원문 →</a>
      </div>
    </div>
  `).join('')}</div>`;
}

function render_chart(evt) {
  if (!marketData || !configData) return '<p style="color:var(--text-muted);font-size:12px;">시장 데이터 없음</p>';
  const mkts = configData.markets || [];
  if (!mkts.length) return '';

  // 첫 번째 지표의 당일 차트만 표시 (일봉)
  const m = mkts[0];
  const ticker_data = marketData.tickers?.[m.ticker];
  if (!ticker_data?.daily?.length) return `<p style="color:var(--text-muted);font-size:12px;">${m.key} 데이터 없음</p>`;

  const date = evt.date.slice(0, 10);
  const daily = ticker_data.daily;
  // 전날 + 당일 데이터
  const idx = daily.findIndex(d => d.date === date);
  const slice = idx > 0 ? daily.slice(Math.max(0, idx - 1), idx + 1) : daily.slice(0, 2);
  if (!slice.length) return `<p style="color:var(--text-muted);font-size:12px;">당일 데이터 없음</p>`;

  return `<div class="chart-wrap">${build_svg_chart(slice, m.label)}</div>`;
}

function build_svg_chart(bars, label) {
  const W = 272, H = 120, PAD = { t: 16, r: 8, b: 24, l: 48 };
  const cw = W - PAD.l - PAD.r;
  const ch = H - PAD.t - PAD.b;

  const prices = bars.flatMap(b => [b.open, b.high, b.low, b.close]);
  const min_p = Math.min(...prices);
  const max_p = Math.max(...prices);
  const range = max_p - min_p || 1;

  const x_scale = cw / Math.max(bars.length - 1, 1);
  const y_scale = v => ch - ((v - min_p) / range) * ch;

  // 종가 라인
  const points = bars.map((b, i) => `${PAD.l + i * x_scale},${PAD.t + y_scale(b.close)}`).join(' ');
  const color = bars[bars.length-1].close >= bars[0].close ? '#44cc88' : '#ff4455';

  // Y축 레이블 (min, max)
  const fmt_p = v => v >= 1000 ? v.toFixed(0) : v.toFixed(2);

  return `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" style="background:var(--surface2);border-radius:6px;">
    <text x="4" y="${PAD.t + 4}" font-size="9" fill="#8888aa">${label}</text>
    <text x="4" y="${PAD.t + ch/2}" font-size="8" fill="#8888aa">${fmt_p((min_p+max_p)/2)}</text>
    <text x="4" y="${PAD.t + ch - 2}" font-size="8" fill="#8888aa">${fmt_p(min_p)}</text>
    <polyline points="${points}" fill="none" stroke="${color}" stroke-width="1.5" stroke-linejoin="round"/>
    ${bars.map((b,i) => `<text x="${PAD.l + i * x_scale}" y="${H - 6}" font-size="8" fill="#8888aa" text-anchor="middle">${b.date.slice(5)}</text>`).join('')}
  </svg>`;
}

// ── 인터랙션 ──────────────────────────────────────────────────────────
function toggle_card(evt_id) {
  const card = document.getElementById(`evt-${evt_id}`);
  card.classList.toggle('expanded');
}

function switch_tab(e, evt_id, tab) {
  e.stopPropagation();
  const card = document.getElementById(`evt-${evt_id}`);
  card.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  card.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  e.target.classList.add('active');
  document.getElementById(`tab-${tab}-${evt_id}`).classList.add('active');
}

// ── 진입점 ───────────────────────────────────────────────────────────
init();
</script>
</body>
</html>
```

- [ ] **Step 3: 브라우저에서 확인**

```bash
# viewer.html을 브라우저로 열기 (WSL에서)
explorer.exe "$(wslpath -w /mnt/d/develope/workspace/news/viewer.html)" 2>/dev/null || echo "직접 브라우저에서 파일 열기"
```

data/iran-war/news.json이 있어야 내용이 표시된다.
registry.json, config.json, news.json 세 파일 모두 존재하는지 확인:
```bash
ls data/iran-war/
```
Expected: config.json  news.json  (market.json은 선택)

- [ ] **Step 4: 커밋**

```bash
git add viewer.html viewer.html.bak
git commit -m "feat: redesign viewer.html with category switcher, market chips, source list, SVG chart"
```

---

### Task 2: 시장 데이터 없을 때 graceful fallback 검증 + 빈 chip 처리

**Files:**
- Modify: `viewer.html` (market 칩 조건부 렌더링 개선)

- [ ] **Step 1: market.json 없이 viewer 열기**

```bash
# market.json 임시 이동
mv data/iran-war/market.json data/iran-war/market.json.tmp 2>/dev/null || true
```

브라우저에서 viewer.html을 새로고침한다.

확인 항목:
- 에러 없이 뷰어 표시됨
- 시장 칩이 없거나 `—` 표시됨
- 차트 탭에 "시장 데이터 없음" 표시됨

- [ ] **Step 2: market.json 복원**

```bash
mv data/iran-war/market.json.tmp data/iran-war/market.json 2>/dev/null || true
```

- [ ] **Step 3: 커밋 (변경 없으면 스킵)**

```bash
git status
# 변경사항 있으면:
git add viewer.html
git commit -m "fix: graceful fallback when market.json missing"
```

---

### Task 3: 최종 통합 검증

**Files:** 없음 (검증만)

- [ ] **Step 1: 전체 테스트 실행**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```
Expected: Plan 1+2에서 추가한 테스트 모두 PASS

- [ ] **Step 2: viewer 전체 기능 체크리스트**

브라우저에서 viewer.html 열고 확인:

```
□ 카테고리 사이드바에 "이란-이스라엘 전쟁" 표시
□ 헤더에 W/C/N/K 범례 표시
□ 가로 타임라인 날짜별 컬럼 표시
□ 각 날짜 헤더에 시장 칩 표시 (market.json 있을 때)
□ 카드에 [시간][출처라벨][중요도배지] 표시
□ 카드에 헤드라인·요약 표시
□ 카드 하단에 W/C/N/K 증감 칩 표시
□ 카드 클릭 시 상세 펼침
□ 출처 탭: 기사 목록 표시 (제목·요약·조회수·원문링크)
□ 차트 탭: SVG 차트 표시 (또는 "데이터 없음")
□ 모바일(400px) 에서 카드 가득참
```

- [ ] **Step 3: 최종 커밋**

```bash
git add -A
git commit -m "feat: complete news-market impact timeline viewer v2.0.0"
```
