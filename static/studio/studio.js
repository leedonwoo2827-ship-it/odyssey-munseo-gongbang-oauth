/* 문서 생산 스튜디오 — 프론트 로직 (vanilla JS, 의존성 없음) */
"use strict";

const API = "/api/studio";
const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, txt) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (txt != null) e.textContent = txt;
  return e;
};

let RECIPES = [];
let CURRENT = null;   // 선택된 레시피
let JOB = null;       // 현재 작업 id
const COLLAPSED = new Set();  // 접힌 카테고리 이름들 (탐색기처럼 접기/펴기)

// ── 초기화 ───────────────────────────────────────────────
async function init() {
  $("#search").addEventListener("input", renderCatalog);
  $("#generate").addEventListener("click", generate);
  $("#refine-btn").addEventListener("click", refine);
  $("#refine").addEventListener("keydown", (e) => { if (e.key === "Enter") refine(); });
  // 연결 상태 모달 (agy)
  $("#open-settings").addEventListener("click", () => openSettings(false));
  $("#close-settings").addEventListener("click", closeSettings);
  $("#refresh-settings").addEventListener("click", () => openSettings(false));
  $("#open-terminal").addEventListener("click", openTerminal);
  // 산출물 목록 모달
  $("#open-outputs").addEventListener("click", openOutputs);
  $("#close-outputs").addEventListener("click", () => { $("#outputs-overlay").style.display = "none"; });

  await loadRecipes();
  // 첫 화면: 연결 상태 확인 → 미연결이면 설정창으로 유도
  const ok = await checkHealth();
  if (!ok) openSettings(true);
}

async function checkHealth() {
  // 칩은 agy 로그인 여부(자격증명)로 판단 — 빠르고 할당량 소모 없음.
  // (실제 생성 가능 여부와 동일: agy 로그인돼 있으면 생성 가능)
  const chip = $("#status-chip");
  chip.onclick = () => openSettings(true);
  try {
    const r = await fetch(`${API}/settings`);
    const s = await r.json();
    if (s.authenticated) {
      chip.textContent = "● Gemini(agy) 연결됨";
      chip.className = "status ok";
      chip.title = s.email || "";
      return true;
    }
    chip.textContent = s.installed ? "● 로그인 필요 — 클릭" : "● agy 미설치 — 클릭";
    chip.className = "status bad";
    chip.title = "";
    return false;
  } catch (e) {
    chip.textContent = "● 서버 응답 없음";
    chip.className = "status bad";
    return false;
  }
}

// ── 연결 상태 모달 (agy) ─────────────────────────────────
async function openSettings(firstTime) {
  const st = $("#set-status");
  st.className = "modal-status"; st.textContent = "상태 확인 중…";
  $("#settings-overlay").style.display = "flex";
  try {
    const r = await fetch(`${API}/settings`);
    const s = await r.json();
    if (!s.installed) {
      st.className = "modal-status bad";
      st.textContent = "✗ Antigravity CLI(agy)가 설치되어 있지 않습니다. 아래 터미널에서 설치/로그인하세요.";
    } else if (!s.authenticated) {
      st.className = "modal-status bad";
      st.textContent = "✗ agy 에 Google 로그인이 필요합니다. 아래 '터미널 열기' → agy 로그인.";
    } else {
      st.className = "modal-status ok";
      st.textContent = `✓ 연결됨 — 계정: ${s.email || ""} · 기본모델: ${s.default_model || ""}`;
    }
  } catch (e) {
    st.className = "modal-status bad"; st.textContent = "✗ 상태 확인 실패: " + e;
  }
  // 우상단 칩도 같이 갱신
  checkHealth();
}

function closeSettings() { $("#settings-overlay").style.display = "none"; }

// "터미널 열기" → 새 탭으로 브라우저 내장 터미널(/terminal) 열기.
// (내장 터미널이 pywinpty 없이 안 되면 그 페이지가 실제 cmd 창으로 자동 폴백)
function openTerminal() {
  window.open("/terminal", "_blank", "noopener");
  const st = $("#set-status");
  st.className = "modal-status";
  st.textContent = "새 탭의 터미널에서 agy 로 로그인 후, '상태 새로고침'을 누르세요.";
}

// ── 산출물 목록 모달 ─────────────────────────────────────
async function openOutputs() {
  const box = $("#outputs-list");
  box.innerHTML = '<div class="empty">불러오는 중…</div>';
  $("#outputs-overlay").style.display = "flex";
  try {
    const r = await fetch(`${API}/outputs`);
    const d = await r.json();
    if (!d.outputs || !d.outputs.length) {
      box.innerHTML = '<div class="empty">아직 생성된 산출물이 없습니다.</div>';
      return;
    }
    box.innerHTML = "";
    d.outputs.forEach(o => {
      const row = el("a", "out-row");
      row.href = `${API}/outputs/${encodeURIComponent(o.name)}`;
      row.setAttribute("download", o.name);
      const fmt = el("span", "out-fmt", (o.format || "").toUpperCase());
      const name = el("span", "out-name", o.name);
      const meta = el("span", "out-meta", `${o.modified} · ${o.size_kb}KB`);
      row.appendChild(fmt); row.appendChild(name); row.appendChild(meta);
      box.appendChild(row);
    });
  } catch (e) {
    box.innerHTML = '<div class="empty">목록을 불러오지 못했습니다.</div>';
  }
}

async function loadRecipes() {
  try {
    const r = await fetch(`${API}/recipes`);
    const d = await r.json();
    RECIPES = d.recipes || [];
  } catch (e) {
    RECIPES = [];
  }
  // 처음엔 모든 카테고리를 접힌 상태로 표시
  RECIPES.forEach(r => COLLAPSED.add(r.category || "기타"));
  renderCatalog();
}

// ── 카탈로그(버튼) ───────────────────────────────────────
function renderCatalog() {
  const q = ($("#search").value || "").trim().toLowerCase();
  const box = $("#catalog");
  box.innerHTML = "";
  const items = RECIPES.filter(r =>
    !q || r.name.toLowerCase().includes(q) || (r.category || "").toLowerCase().includes(q));
  if (!items.length) {
    box.appendChild(el("div", "empty",
      RECIPES.length ? "검색 결과가 없습니다." : "레시피가 없습니다. knowledge/recipes 폴더를 확인하세요."));
    return;
  }
  const groups = {};
  items.forEach(r => { (groups[r.category || "기타"] ||= []).push(r); });
  Object.keys(groups).sort().forEach(cat => {
    const collapsed = !q && COLLAPSED.has(cat);   // 검색 중엔 항상 펼침
    const g = el("div", "cat-group");
    const title = el("div", "cat-title");
    title.appendChild(el("span", "cat-caret", collapsed ? "▶" : "▼"));
    title.appendChild(el("span", "cat-name", `${cat} (${groups[cat].length})`));
    title.addEventListener("click", () => {
      if (COLLAPSED.has(cat)) COLLAPSED.delete(cat); else COLLAPSED.add(cat);
      renderCatalog();
    });
    g.appendChild(title);
    if (!collapsed) {
      groups[cat].forEach(r => {
        const b = el("button", "recipe-btn");
        if (CURRENT && CURRENT.id === r.id) b.classList.add("active");
        b.appendChild(el("div", "rb-name", r.name));
        b.appendChild(el("div", "rb-meta", `${r.format.toUpperCase()} · 입력 ${r.inputs.length}개`));
        b.addEventListener("click", () => selectRecipe(r));
        g.appendChild(b);
      });
    }
    box.appendChild(g);
  });
}

// ── 레시피 선택 → 작업 패널 ──────────────────────────────
function selectRecipe(r) {
  CURRENT = r;
  JOB = null;
  renderCatalog();
  $("#work-empty").style.display = "none";
  $("#work").style.display = "block";
  $("#recipe-name").textContent = r.name;
  $("#recipe-format").textContent = r.format;
  $("#recipe-desc").textContent = r.description || "";
  $("#instruction").value = "";
  $("#result").style.display = "none";

  const inputs = $("#inputs");
  inputs.innerHTML = "";
  if (!r.inputs.length) {
    inputs.appendChild(el("div", "empty", "이 유형은 입력 문서 없이 지시(메모)만으로 생성합니다."));
  }
  r.inputs.forEach(inp => inputs.appendChild(buildSlot(inp)));
}

function buildSlot(inp) {
  const slot = el("div", "slot" + (inp.required ? " req" : ""));
  slot.dataset.key = inp.key;
  const label = el("div", "s-label", inp.label);
  if (inp.required) label.appendChild(el("span", "s-req", " *필수"));
  slot.appendChild(label);
  slot.appendChild(el("div", "s-accept", "허용: " + (inp.accept || []).join(", ")));
  const fileLine = el("div", "s-file");
  slot.appendChild(fileLine);

  const file = document.createElement("input");
  file.type = "file";
  file.accept = (inp.accept || []).map(a => "." + a).join(",");
  slot.appendChild(file);

  const onPick = (f) => {
    if (!f) return;
    slot._file = f;
    slot.classList.add("has");
    fileLine.style.display = "block";
    fileLine.textContent = "✓ " + f.name;
  };
  file.addEventListener("change", () => onPick(file.files[0]));
  ["dragover", "dragenter"].forEach(ev => slot.addEventListener(ev, e => {
    e.preventDefault(); slot.classList.add("drag");
  }));
  ["dragleave", "drop"].forEach(ev => slot.addEventListener(ev, e => {
    e.preventDefault(); slot.classList.remove("drag");
  }));
  slot.addEventListener("drop", e => {
    const f = e.dataTransfer.files[0];
    if (f) { file.files = e.dataTransfer.files; onPick(f); }
  });
  return slot;
}

// ── 생성 ─────────────────────────────────────────────────
function _sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// 작업이 'running' 이면 완료(done/error)까지 GET /jobs/{id} 폴링.
// (긴 agy 생성이 단일 HTTP 요청 타임아웃에 걸리지 않도록 백그라운드+폴링 구조)
async function pollJob(id) {
  for (let i = 0; i < 360; i++) {   // 최대 ~12분 (2s * 360)
    await _sleep(2000);
    try {
      const r = await fetch(`${API}/jobs/${id}`);
      const d = await r.json();
      if (!r.ok) return { id, status: "error", error: d.detail || "작업 조회 실패" };
      if (d.status && d.status !== "running") return d;
    } catch (e) { /* 일시 오류는 무시하고 계속 폴링 */ }
  }
  return { id, status: "error", error: "생성 시간이 너무 깁니다(12분 초과). 다시 시도해 주세요." };
}

async function generate() {
  if (!CURRENT) return;
  const fd = new FormData();
  fd.append("recipe_id", CURRENT.id);
  fd.append("instruction", $("#instruction").value || "");
  document.querySelectorAll(".slot").forEach(slot => {
    if (slot._file) fd.append(slot.dataset.key, slot._file);
  });

  setBusy(true);
  try {
    const r = await fetch(`${API}/jobs`, { method: "POST", body: fd });
    const d = await r.json();
    if (!r.ok) { alert(d.detail || "생성 실패"); return; }
    JOB = d.id;
    const fin = (d.status === "running") ? await pollJob(d.id) : d;
    JOB = fin.id || JOB;
    renderResult(fin);
  } catch (e) {
    alert("요청 실패: " + e);
  } finally {
    setBusy(false);
  }
}

async function refine() {
  const text = ($("#refine").value || "").trim();
  if (!text || !JOB) return;
  $("#refine").value = "";
  setBusy(true, true);
  try {
    const r = await fetch(`${API}/jobs/${JOB}/refine`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ instruction: text }),
    });
    const d = await r.json();
    if (!r.ok) { alert(d.detail || "수정 실패"); return; }
    const fin = (d.status === "running") ? await pollJob(JOB) : d;
    renderResult(fin);
  } catch (e) {
    alert("요청 실패: " + e);
  } finally {
    setBusy(false, true);
  }
}

function setBusy(on, isRefine) {
  $("#gen-spinner").style.display = (on && !isRefine) ? "inline-block" : "none";
  $("#generate").disabled = on;
  $("#refine-btn").disabled = on;
}

// ── 결과 렌더 ────────────────────────────────────────────
function renderResult(d) {
  $("#result").style.display = "block";
  if (d.status === "error") {
    $("#preview").innerHTML = `<div class="w" style="color:var(--err)">생성 오류: ${escapeHtml(d.error || "")}</div>`;
    $("#downloads").innerHTML = "";
    $("#warnings").innerHTML = "";
    return;
  }
  // 다운로드
  const dls = $("#downloads");
  dls.innerHTML = "";
  (d.files || []).forEach((f, i) => {
    const a = document.createElement("a");
    a.className = "dl" + (f.format === "md" ? " alt" : "");
    a.href = `${API}/jobs/${d.id}/download/${encodeURIComponent(f.name)}`;
    a.textContent = `⬇ ${f.format.toUpperCase()}`;
    a.setAttribute("download", f.name);
    dls.appendChild(a);
  });
  // 경고
  const w = $("#warnings");
  w.innerHTML = "";
  (d.warnings || []).forEach(msg => w.appendChild(el("div", "w", msg)));
  // 미리보기
  $("#preview").innerHTML = renderMarkdown(d.preview || "");
  // 채팅
  const chat = $("#chat");
  chat.innerHTML = "";
  (d.chat || []).forEach(m => chat.appendChild(el("div", "msg " + m.role, m.text)));
  chat.scrollTop = chat.scrollHeight;
}

// ── 초경량 마크다운 렌더 ─────────────────────────────────
function escapeHtml(s) {
  return (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function inline(s) {
  return escapeHtml(s)
    .replace(/&lt;br\s*\/?&gt;/gi, "<br>")   // 셀/문장 안 <br> → 실제 줄바꿈
    .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
}
function renderMarkdown(md) {
  const lines = (md || "").split("\n");
  let html = "", inList = false, inTable = false;
  const closeList = () => { if (inList) { html += "</ul>"; inList = false; } };
  const closeTable = () => { if (inTable) { html += "</table>"; inTable = false; } };
  for (let raw of lines) {
    const line = raw.trimEnd();
    let m;
    if ((m = line.match(/^(#{1,6})\s+(.*)$/))) {
      closeList(); closeTable();
      const lvl = m[1].length;
      html += `<h${lvl}>${inline(m[2])}</h${lvl}>`;
    } else if (/^\s*[-*+]\s+/.test(line)) {
      closeTable();
      if (!inList) { html += "<ul>"; inList = true; }
      html += `<li>${inline(line.replace(/^\s*[-*+]\s+/, ""))}</li>`;
    } else if (/^\|.*\|$/.test(line)) {
      closeList();
      const cells = line.slice(1, -1).split("|").map(c => c.trim());
      if (cells.every(c => /^:?-+:?$/.test(c) || c === "")) continue; // 구분선
      if (!inTable) { html += "<table>"; inTable = true; }
      html += "<tr>" + cells.map(c => `<td>${inline(c)}</td>`).join("") + "</tr>";
    } else if (!line.trim()) {
      closeList(); closeTable();
    } else {
      closeList(); closeTable();
      html += `<p>${inline(line)}</p>`;
    }
  }
  closeList(); closeTable();
  return html;
}

init();
