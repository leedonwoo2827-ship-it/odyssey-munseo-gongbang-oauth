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
let STYLE_FILES = []; // 지난 산출물(문체 앵커) 파일들
const COLLAPSED = new Set();  // 접힌 카테고리 이름들 (탐색기처럼 접기/펴기)

// ── 초기화 ───────────────────────────────────────────────
async function init() {
  $("#search").addEventListener("input", renderCatalog);
  $("#generate").addEventListener("click", generate);
  $("#refine-btn").addEventListener("click", refine);
  $("#refine").addEventListener("keydown", (e) => { if (e.key === "Enter") refine(); });
  // 근거 기반 5단계
  $("#guided-on").addEventListener("change", syncGuidedMode);
  $("#s-learn").addEventListener("click", stageLearn);
  $("#s-research").addEventListener("click", stageResearch);
  $("#s-generate").addEventListener("click", stageGenerate);
  $("#s-review").addEventListener("click", stageReview);
  $("#s-revise").addEventListener("click", stageRevise);
  $("#brief-box").addEventListener("blur", saveBrief);
  $("#style-files").addEventListener("change", (e) => {
    STYLE_FILES = Array.from(e.target.files || []);
    const box = $("#style-list");
    box.style.display = STYLE_FILES.length ? "block" : "none";
    box.textContent = STYLE_FILES.length ? ("✓ " + STYLE_FILES.map(f => f.name).join(", ")) : "";
  });
  // 연결 상태 모달 (agy)
  $("#open-settings").addEventListener("click", () => openSettings(false));
  $("#close-settings").addEventListener("click", closeSettings);
  $("#refresh-settings").addEventListener("click", () => openSettings(false));
  $("#open-terminal").addEventListener("click", openTerminal);
  // 공급자 토글
  const pa = $("#prov-agy"), pc = $("#prov-codex");
  if (pa) pa.addEventListener("click", () => setProvider("agy"));
  if (pc) pc.addEventListener("click", () => setProvider("codex"));
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
      const m = s.selected_model ? " · " + s.selected_model : "";
      chip.textContent = "● " + (s.label || "LLM") + m + " 연결됨";
      chip.className = "status ok";
      chip.title = (s.email || "") + (s.selected_model ? "\n모델: " + s.selected_model : "");
      return true;
    }
    chip.textContent = s.installed ? "● 로그인 필요 — 클릭" : "● CLI 미설치 — 클릭";
    chip.className = "status bad";
    chip.title = "";
    return false;
  } catch (e) {
    chip.textContent = "● 서버 응답 없음";
    chip.className = "status bad";
    return false;
  }
}

// 공급자 전환
async function setProvider(name) {
  try {
    await fetch(`/api/llm/provider`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider: name }),
    });
  } catch (e) { /* 무시 */ }
  openSettings(false);
}

// ── 연결 상태 모달 (공급자 토글) ─────────────────────────────────
async function openSettings(firstTime) {
  const st = $("#set-status");
  st.className = "modal-status"; st.textContent = "상태 확인 중…";
  $("#settings-overlay").style.display = "flex";
  let label = "LLM";
  try {
    const r = await fetch(`${API}/settings`);
    const s = await r.json();
    label = s.label || "LLM";
    // 공급자 토글 버튼 활성 표시
    const pa = $("#prov-agy"), pc = $("#prov-codex");
    if (pa) pa.style.outline = (s.provider === "agy") ? "2px solid #6366f1" : "none";
    if (pc) pc.style.outline = (s.provider === "codex") ? "2px solid #6366f1" : "none";
    if (!s.installed) {
      st.className = "modal-status bad";
      st.textContent = `✗ ${label} CLI가 설치되어 있지 않습니다. [로그인 관리 열기]에서 설치/로그인하세요.`;
    } else if (!s.authenticated) {
      st.className = "modal-status bad";
      st.textContent = `✗ ${label} 로그인이 필요합니다. [로그인 관리 열기] → 로그인.`;
    } else {
      st.className = "modal-status ok";
      st.textContent = `✓ 연결됨 (${label}) — 계정: ${s.email || ""}`;
    }
  } catch (e) {
    st.className = "modal-status bad"; st.textContent = "✗ 상태 확인 실패: " + e;
  }
  loadModelOptions();
  checkHealth();
}

// agy 모델 드롭다운: 목록은 agy models 에서 동적으로, [적용] 버튼으로 저장
async function loadModelOptions() {
  const sel = $("#studio-model");
  const msg = $("#studio-model-msg");
  const btn = $("#apply-model");
  if (!sel) return;
  try {
    const r = await fetch(`/api/llm/models`, { cache: "no-store" });
    const d = await r.json();
    // 드롭다운을 통째로 재구성 — 다른 공급자 모델이 섞여 남지 않게(선택 공급자 모델만).
    const defLabel = d.provider === "codex" ? "기본값 (codex 자동 선택)" : "기본값 (agy 자동 선택)";
    sel.innerHTML = "";
    const def = document.createElement("option");
    def.value = ""; def.textContent = defLabel; sel.appendChild(def);
    (d.models || []).forEach((m) => {
      const o = document.createElement("option");
      o.value = m; o.textContent = m; sel.appendChild(o);
    });
    sel.value = d.selected || "";
    if (msg) msg.textContent = "현재 적용: " + (d.selected || "기본 모델");
  } catch (e) { if (msg) msg.textContent = "모델 목록 로드 실패"; }

  if (btn && !btn._bound) {
    btn._bound = true;
    btn.addEventListener("click", async () => {
      if (msg) msg.textContent = "적용 중…";
      try {
        const rr = await fetch(`/api/llm/model`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ model: sel.value }),
        });
        const dd = await rr.json();
        if (rr.ok && dd.ok) {
          if (msg) msg.textContent = "✓ 적용됨 — 현재: " + (dd.selected || "기본 모델");
        } else if (msg) { msg.textContent = "적용 실패"; }
      } catch (e) { if (msg) msg.textContent = "적용 실패: " + e; }
    });
  }
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
  STYLE_FILES = [];
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

  // 근거 기반 5단계: 레시피 종류별 자동(full 만 노출). 상태 초기화.
  $("#style-files").value = "";
  $("#style-list").style.display = "none";
  $("#style-list").textContent = "";
  $("#guided").style.display = (r.workflow === "full") ? "block" : "none";
  $("#guided-on").checked = true;
  $("#brief-wrap").style.display = "none";
  $("#brief-box").value = "";
  $("#review-wrap").style.display = "none";
  $("#review-box").innerHTML = "";
  setGuidedMsg("");
  ["learn", "research", "generate", "review", "revise"].forEach(s => markStage(s, ""));
  syncGuidedMode();
}

// ── 근거 기반 5단계 ──────────────────────────────────────
function syncGuidedMode() {
  const guidedVisible = $("#guided").style.display !== "none";
  const on = guidedVisible && $("#guided-on").checked;
  $("#step-strip").style.display = on ? "" : "none";
  $(".guided-actions").style.display = on ? "" : "none";
  // 단계별 진행이 켜져 있으면 하단 '한 번에 생성'은 숨김(③ 생성으로 대체)
  $(".actions").style.display = on ? "none" : "flex";
  if (!on) {
    $("#brief-wrap").style.display = "none";
    $("#review-wrap").style.display = "none";
  }
}

function setGuidedMsg(t) { const e = $("#guided-msg"); if (e) e.textContent = t || ""; }

function markStage(name, state) {
  const icon = { running: "⏳", done: "✓", error: "✗" }[state] || "";
  const e = $("#st-" + name);
  if (e) e.textContent = icon;
}

function applyStageStatus(d) {
  const ss = (d && d.stage_status) || {};
  ["learn", "research", "generate", "review", "revise"].forEach(s => {
    if (ss[s]) markStage(s, ss[s]);
  });
}

function guidedBusy(on) {
  $("#guided-spinner").style.display = on ? "inline-block" : "none";
  ["s-learn", "s-research", "s-generate", "s-review", "s-revise"]
    .forEach(id => { const b = $("#" + id); if (b) b.disabled = on; });
}

// 첫 단계에서 'defer' 작업(생성 보류)을 만든다. 입력/지난 산출물/지시를 함께 올린다.
async function ensureJob() {
  if (JOB) return JOB;
  const fd = new FormData();
  fd.append("recipe_id", CURRENT.id);
  fd.append("instruction", $("#instruction").value || "");
  fd.append("defer_generate", "1");
  document.querySelectorAll(".slot").forEach(slot => {
    if (slot._file) fd.append(slot.dataset.key, slot._file);
  });
  STYLE_FILES.forEach(f => fd.append("__style__", f));
  const r = await fetch(`${API}/jobs`, { method: "POST", body: fd });
  const d = await r.json();
  if (!r.ok) throw new Error(d.detail || "작업 생성 실패");
  JOB = d.id;
  return JOB;
}

async function stageLearn() {
  if (!CURRENT) return;
  guidedBusy(true); markStage("learn", "running"); setGuidedMsg("자료 학습(추출·색인) 중…");
  try {
    await ensureJob();
    const r = await fetch(`${API}/jobs/${JOB}/learn`, { method: "POST" });
    const d = await r.json();
    if (!r.ok) { markStage("learn", "error"); setGuidedMsg(d.detail || "학습 실패"); return; }
    const fin = (d.status === "running") ? await pollJob(JOB) : d;
    applyStageStatus(fin);
    if (fin.status === "error") { markStage("learn", "error"); setGuidedMsg(fin.error || "학습 실패"); return; }
    const ev = fin.evidence || {};
    markStage("learn", "done");
    setGuidedMsg(`✓ 학습 완료 — ${ev.chunks || 0}개 조각 (${ev.retriever || "naive"} 검색)`);
  } catch (e) { markStage("learn", "error"); setGuidedMsg("학습 실패: " + e.message); }
  finally { guidedBusy(false); }
}

async function stageResearch() {
  if (!CURRENT) return;
  guidedBusy(true); markStage("research", "running"); setGuidedMsg("자료 심층분석 중…");
  try {
    await ensureJob();
    const r = await fetch(`${API}/jobs/${JOB}/research`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}),
    });
    const d = await r.json();
    if (!r.ok) { markStage("research", "error"); setGuidedMsg(d.detail || "분석 실패"); return; }
    const fin = (d.status === "running") ? await pollJob(JOB) : d;
    if (fin.status === "error") { markStage("research", "error"); setGuidedMsg(fin.error || "분석 실패"); return; }
    $("#brief-wrap").style.display = "block";
    $("#brief-box").value = fin.research_brief || "";
    applyStageStatus(fin); markStage("research", "done");
    setGuidedMsg("브리프 생성됨 — 검토·수정 후 ③ 생성");
  } catch (e) { markStage("research", "error"); setGuidedMsg("분석 실패: " + e.message); }
  finally { guidedBusy(false); }
}

async function saveBrief() {
  if (!JOB) return;
  try {
    await fetch(`${API}/jobs/${JOB}/brief`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ brief: $("#brief-box").value || "" }),
    });
  } catch (e) { /* 무시 */ }
}

async function stageGenerate() {
  if (!CURRENT) return;
  guidedBusy(true); markStage("generate", "running"); setGuidedMsg("문서 생성 중…");
  try {
    await ensureJob();
    if (($("#brief-box").value || "").trim()) await saveBrief();
    const r = await fetch(`${API}/jobs/${JOB}/generate`, { method: "POST" });
    const d = await r.json();
    if (!r.ok) { markStage("generate", "error"); setGuidedMsg(d.detail || "생성 실패"); return; }
    const fin = (d.status === "running") ? await pollJob(JOB) : d;
    JOB = fin.id || JOB;
    renderResult(fin); applyStageStatus(fin);
    markStage("generate", fin.status === "error" ? "error" : "done");
    setGuidedMsg(fin.status === "error" ? "생성 오류" : "생성 완료 — ④ 검수로 점검");
  } catch (e) { markStage("generate", "error"); setGuidedMsg("생성 실패: " + e.message); }
  finally { guidedBusy(false); }
}

async function stageReview() {
  if (!JOB) { setGuidedMsg("먼저 ③ 생성하세요."); return; }
  guidedBusy(true); markStage("review", "running"); setGuidedMsg("근거와 대조해 검수 중…");
  try {
    const r = await fetch(`${API}/jobs/${JOB}/review`, { method: "POST" });
    const d = await r.json();
    if (!r.ok) { markStage("review", "error"); setGuidedMsg(d.detail || "검수 실패"); return; }
    const fin = (d.status === "running") ? await pollJob(JOB) : d;
    if (fin.status === "error") { markStage("review", "error"); setGuidedMsg(fin.error || "검수 실패"); return; }
    $("#review-wrap").style.display = "block";
    $("#review-box").innerHTML = renderMarkdown(fin.review_report || "");
    applyStageStatus(fin); markStage("review", "done");
    setGuidedMsg("검수 결과 확인 — ⑤ 검수 반영");
  } catch (e) { markStage("review", "error"); setGuidedMsg("검수 실패: " + e.message); }
  finally { guidedBusy(false); }
}

async function stageRevise() {
  if (!JOB) { setGuidedMsg("먼저 ④ 검수하세요."); return; }
  guidedBusy(true); markStage("revise", "running"); setGuidedMsg("검수 결과 반영 중…");
  try {
    const r = await fetch(`${API}/jobs/${JOB}/revise`, { method: "POST" });
    const d = await r.json();
    if (!r.ok) { markStage("revise", "error"); setGuidedMsg(d.detail || "반영 실패"); return; }
    const fin = (d.status === "running") ? await pollJob(JOB) : d;
    renderResult(fin); applyStageStatus(fin);
    markStage("revise", fin.status === "error" ? "error" : "done");
    setGuidedMsg(fin.status === "error" ? "반영 오류" : "검수 반영 완료");
  } catch (e) { markStage("revise", "error"); setGuidedMsg("반영 실패: " + e.message); }
  finally { guidedBusy(false); }
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
