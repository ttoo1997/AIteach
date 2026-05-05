const panels = document.querySelectorAll(".panel");
const navButtons = document.querySelectorAll(".nav-btn");

const healthLine = document.querySelector("#health-line");
const solveChatLog = document.querySelector("#solve-chat-log");
const solveChatForm = document.querySelector("#solve-chat-form");
const solveChatInput = document.querySelector("#solve-chat-input");
const solveChatFileInput = document.querySelector("#solve-chat-file");
const solveUploadTriggerBtn = document.querySelector("#solve-upload-trigger");
const solveAttachmentPreview = document.querySelector("#solve-attachment-preview");
const solveAttachmentImage = document.querySelector("#solve-attachment-image");
const solveAttachmentName = document.querySelector("#solve-attachment-name");
const solveAttachmentRemoveBtn = document.querySelector("#solve-attachment-remove");
const clearSolveChatBtn = document.querySelector("#clear-solve-chat");
const solveModeSelect = document.querySelector("#solve-mode");
const solveSendBtn = document.querySelector("#solve-send-btn");
const compactSelects = document.querySelectorAll(".select-compact");
const qaResult = document.querySelector("#qa-result");
const simResult = document.querySelector("#sim-result");
const wrongList = document.querySelector("#wrong-list");
const solveFeedback = document.querySelector("#solve-feedback");
const addToWrongbookBtn = document.querySelector("#add-to-wrongbook");
const wrongReasonWrap = document.querySelector("#wrong-reason-wrap");
const wrongReasonInput = document.querySelector("#wrong-reason-input");
const saveWrongQuestionBtn = document.querySelector("#save-wrong-question");
const solveFeedbackTip = document.querySelector("#solve-feedback-tip");
const toast = document.querySelector("#toast");

const qaThinking = document.querySelector("#qa-thinking");
const simThinking = document.querySelector("#sim-thinking");
const simCoachThinking = document.querySelector("#sim-coach-thinking");
const wrongAiThinking = document.querySelector("#wrong-ai-thinking");
const simMatlabStatus = document.querySelector("#sim-matlab-status");
const simLabList = document.querySelector("#sim-lab-list");
const simLabDetail = document.querySelector("#sim-lab-detail");
const simLabForm = document.querySelector("#sim-lab-form");
const simLabParams = document.querySelector("#sim-lab-params");
const simBackendSelect = document.querySelector("#sim-backend");
const matlabCliModeSelect = document.querySelector("#matlab-cli-mode");
const matlabCliPathInput = document.querySelector("#matlab-cli-path");
const matlabCliSaveBtn = document.querySelector("#matlab-cli-save");
const simMatlabConfigNote = document.querySelector("#sim-matlab-config-note");
const simCoachLog = document.querySelector("#sim-coach-log");
const simCoachForm = document.querySelector("#sim-coach-form");
const simCoachInput = document.querySelector("#sim-coach-input");
const simCoachSendBtn = document.querySelector("#sim-coach-send");
const simCoachClearBtn = document.querySelector("#sim-coach-clear");

const wrongPageMeta = document.querySelector("#wrong-page-meta");
const wrongPrevBtn = document.querySelector("#wrong-prev");
const wrongNextBtn = document.querySelector("#wrong-next");
const wrongPageSizeSelect = document.querySelector("#wrong-page-size");

let currentSimulationLab = null;
let lastSolveResult = null;
let lastSolveSourceType = "text";
let wrongQuestionItems = [];
let editingWrongId = null;

const SIMULATION_FIELD_LABELS = {
  no_load_speed_rpm: "空载转速 (rpm)",
  stall_torque_nm: "堵转转矩 (N·m)",
  max_armature_current_a: "最大电枢电流 (A)",
  regulation_percent_at_full_load: "满载电压调整率 (%)",
  peak_efficiency_percent: "峰值效率 (%)",
  peak_efficiency_load_pu: "峰值效率负载率 (p.u.)",
  max_slip: "峰值对应滑差",
  max_torque: "最大转矩",
  start_torque: "启动转矩",
  max_power_kw: "最大电磁功率 (kW)",
  delta_at_max_power_deg: "峰值对应功角 (°)",
  static_stability_margin_deg: "静稳裕度 (°)",
  torque_nm: "转矩 (N·m)",
  speed_rpm: "转速 (rpm)",
  armature_current_a: "电枢电流 (A)",
  load_pu: "负载率 (p.u.)",
  v2_v: "二次侧电压 (V)",
  efficiency_percent: "效率 (%)",
  output_power_w: "输出功率 (W)",
  slip: "滑差 s",
  torque: "转矩",
  delta_deg: "功角 δ (°)",
  power_kw: "功率 (kW)",
};

const SIMULATION_PARAM_LABELS = {
  va_v: "电枢电压 \\(V_a\\) (V)",
  ra_ohm: "电枢电阻 \\(R_a\\) (Ω)",
  k_phi: "反电势常数 \\(k\\Phi\\)",
  torque_min_nm: "最小负载转矩 \\(T_{\\min}\\) (N·m)",
  torque_max_nm: "最大负载转矩 \\(T_{\\max}\\) (N·m)",
  n_points: "采样点数 \\(N\\)",
  v2_rated_v: "二次额定电压 \\(V_2\\) (V)",
  i2_rated_a: "二次额定电流 \\(I_2\\) (A)",
  r_eq_ohm: "等效电阻 \\(R_{eq}\\) (Ω)",
  x_eq_ohm: "等效电抗 \\(X_{eq}\\) (Ω)",
  p_core_w: "铁耗 \\(P_{core}\\) (W)",
  p_cu_full_w: "满载铜耗 \\(P_{cu,FL}\\) (W)",
  power_factor: "负载功率因数 \\(\\cos\\varphi\\)",
  load_max_pu: "最大负载率 \\(\\beta_{\\max}\\) (p.u.)",
  r2: "转子电阻 \\(R_2\\)",
  x2: "转子漏抗 \\(X_2\\)",
  e2: "转子感应电势 \\(E_2\\) (V)",
  s_min: "最小滑差 \\(s_{\\min}\\)",
  s_max: "最大滑差 \\(s_{\\max}\\)",
  e_phase_v: "内部电势 \\(E\\) (V/相)",
  v_phase_v: "端电压 \\(V\\) (V/相)",
  xs_ohm: "同步电抗 \\(X_s\\) (Ω)",
  delta_max_deg: "最大功角 \\(\\delta_{\\max}\\) (°)",
};

let toastTimer = null;
let solveAttachmentObjectUrl = null;
let pendingSolveFile = null;
let solveChatTurns = [];
let solveMessageImageUrls = [];
let isSolveStreaming = false;
let solveChatRenderFrame = 0;
let solveChatRenderNeedsTypeset = false;
let simulationLabs = [];
let simCoachTurns = [];
let isSimCoachPending = false;
let isSimLabRunning = false;
const simRunBtn = document.querySelector("#sim-run-btn");

let wrongPagination = {
  page: 1,
  page_size: Number(wrongPageSizeSelect?.value || "6"),
  total: 0,
  total_pages: 1,
  has_prev: false,
  has_next: false,
};


function setPanel(panelId) {
  navButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.panel === panelId);
  });
  panels.forEach((panel) => {
    panel.classList.toggle("active", panel.id === panelId);
  });
}


function setThinking(element, visible) {
  if (!element) {
    return;
  }
  element.classList.toggle("hidden", !visible);
}


function toPrettyJson(value) {
  return JSON.stringify(value, null, 2);
}


function formatNumber(value, digits = 3) {
  return Number(value ?? 0).toFixed(digits);
}


function syncCompactSelectWidth(select) {
  if (!select) {
    return;
  }
  if (window.innerWidth <= 900) {
    select.style.width = "";
    return;
  }
  // Keep short selects close to their current option text instead of stretching full width.
  const selectedText = select.options?.[select.selectedIndex]?.textContent?.trim() || "";
  let lengthCh = 0;
  for (let i = 0; i < selectedText.length; i++) {
    lengthCh += selectedText.charCodeAt(i) > 255 ? 2 : 1;
  }
  const widthCh = Math.min(Math.max(lengthCh + 2, 7), 24);
  select.style.width = `calc(${widthCh}ch + 28px)`;
}


function refreshCompactSelectWidths() {
  compactSelects.forEach((select) => syncCompactSelectWidth(select));
}

const mathTypesetTimers = new WeakMap();
const STREAM_MATHJAX_DELAY_MS = 140;


function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}


function formatAssistantInline(text) {
  return escapeHtml(String(text ?? "")).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

// Protect LaTeX blocks so markdown cleanup does not split formulas mid-stream.
function protectMathSegments(text) {
  const segments = [];
  const protectedText = String(text ?? "").replace(
    /\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|\\begin\{([a-zA-Z*]+)\}[\s\S]*?\\end\{\1\}/g,
    (match) => {
      const token = `@@AITEACH_MATH_${segments.length}@@`;
      segments.push(match);
      return token;
    }
  );
  return { protectedText, segments };
}

function restoreMathSegments(text, segments) {
  return (segments || []).reduce(
    (result, segment, index) => result.replaceAll(`@@AITEACH_MATH_${index}@@`, segment),
    String(text ?? "")
  );
}


function splitMarkdownTableRow(line) {
  const trimmed = String(line ?? "").trim();
  const withoutEdges = trimmed.replace(/^\|/, "").replace(/\|$/, "");
  return withoutEdges.split("|").map((cell) => cell.trim());
}


function isMarkdownTableSeparator(line) {
  if (!String(line ?? "").includes("|")) {
    return false;
  }
  const cells = splitMarkdownTableRow(line);
  if (!cells.length) {
    return false;
  }
  return cells.every((cell) => /^:?-{3,}:?$/.test(cell));
}


function normalizeMathDelimiters(text) {
  let result = String(text ?? "");
  result = result.replace(/\$\$([\s\S]+?)\$\$/g, "\\[$1\\]");
  result = result.replace(/(^|[^\$])\$([^\$]+?)\$(?!\$)/g, "$1\\($2\\)");
  return result;
}

function countUnescapedDollars(text) {
  let count = 0;
  const source = String(text ?? "");
  for (let index = 0; index < source.length; index += 1) {
    if (source[index] === "$" && source[index - 1] !== "\\") {
      count += 1;
    }
  }
  return count;
}

function hasBalancedMathEnvironments(text) {
  const envPattern = /\\(begin|end)\{([a-zA-Z*]+)\}/g;
  const stack = [];
  const source = String(text ?? "");
  let match = envPattern.exec(source);
  while (match) {
    const [, kind, name] = match;
    if (kind === "begin") {
      stack.push(name);
    } else if (stack.pop() !== name) {
      return false;
    }
    match = envPattern.exec(source);
  }
  return stack.length === 0;
}

function hasBalancedMathDelimiters(text) {
  const source = String(text ?? "");
  const inlineOpen = (source.match(/\\\(/g) || []).length;
  const inlineClose = (source.match(/\\\)/g) || []).length;
  const displayOpen = (source.match(/\\\[/g) || []).length;
  const displayClose = (source.match(/\\\]/g) || []).length;
  return (
    inlineOpen === inlineClose &&
    displayOpen === displayClose &&
    countUnescapedDollars(source) % 2 === 0 &&
    hasBalancedMathEnvironments(source)
  );
}

function containsMathMarkup(text) {
  const source = String(text ?? "");
  return /\\\(|\\\[|\\begin\{/.test(source) || countUnescapedDollars(source) > 0;
}

function shouldTypesetStreamingMath(text) {
  const normalized = normalizeMathDelimiters(String(text ?? ""));
  return containsMathMarkup(normalized) && hasBalancedMathDelimiters(normalized);
}

function preserveMathNewlines(html) {
  let result = html;
  result = result.replace(/\\\[([\s\S]*?)\\\]/g, (match) => match.replaceAll("<br>", "\n"));
  result = result.replace(/\\\(([\s\S]*?)\\\)/g, (match) => match.replaceAll("<br>", "\n"));
  result = result.replace(/\\begin\{([a-zA-Z*]+)\}([\s\S]*?)\\end\{\1\}/g, (match) => match.replaceAll("<br>", "\n"));
  return result;
}

function typesetMathJax(elements) {
  if (window.MathJax && typeof window.MathJax.typesetPromise === "function") {
    if (typeof window.MathJax.typesetClear === "function") {
      window.MathJax.typesetClear(elements);
    }
    window.MathJax.typesetPromise(elements).catch(() => {});
  }
}

// Debounce MathJax work during streaming updates to keep the chat smooth.
function scheduleTypesetMathJax(target, options = {}) {
  if (!target) {
    return;
  }
  const immediate = Boolean(options.immediate);
  const pendingTimer = mathTypesetTimers.get(target);
  if (pendingTimer) {
    window.clearTimeout(pendingTimer);
  }
  const timer = window.setTimeout(() => {
    mathTypesetTimers.delete(target);
    typesetMathJax([target]);
  }, immediate ? 0 : STREAM_MATHJAX_DELAY_MS);
  mathTypesetTimers.set(target, timer);
}


function renderSolveMessageText(text, role) {
  let source = String(text ?? "").replaceAll("\r\n", "\n");
  let mathSegments = [];
  if (role === "assistant") {
    source = normalizeMathDelimiters(source);
    const protectedMath = protectMathSegments(source);
    source = protectedMath.protectedText;
    mathSegments = protectedMath.segments;
  }
  if (role !== "assistant") {
    return escapeHtml(source).replaceAll("\n", "<br>");
  }

  const lines = source
    .split("\n")
    .map((line) => line.replace(/^\s*>\s*[-*]\s+/, "- "))
    .filter((line) => !/^\s*-{3,}\s*$/.test(line));
  const fragments = [];

  for (let index = 0; index < lines.length; index += 1) {
    const currentLine = lines[index] ?? "";
    const nextLine = lines[index + 1] ?? "";

    if (currentLine.includes("|") && isMarkdownTableSeparator(nextLine)) {
      const headerCells = splitMarkdownTableRow(currentLine);
      if (headerCells.length >= 2) {
        let cursor = index + 2;
        const rows = [];
        while (cursor < lines.length) {
          const rowLine = lines[cursor] ?? "";
          if (!rowLine.includes("|")) {
            break;
          }
          const rowCells = splitMarkdownTableRow(rowLine);
          if (rowCells.length !== headerCells.length) {
            break;
          }
          rows.push(rowCells);
          cursor += 1;
        }

        const headHtml = headerCells.map((cell) => `<th>${formatAssistantInline(cell)}</th>`).join("");
        const bodyHtml = rows
          .map((rowCells) => `<tr>${rowCells.map((cell) => `<td>${formatAssistantInline(cell)}</td>`).join("")}</tr>`)
          .join("");
        fragments.push(`
          <div class="solve-table-wrap">
            <table class="solve-md-table">
              <thead><tr>${headHtml}</tr></thead>
              <tbody>${bodyHtml}</tbody>
            </table>
          </div>
        `);
        index = cursor - 1;
        if (index < lines.length - 1) {
          fragments.push("<br>");
        }
        continue;
      }
    }

    const headingMatch = currentLine.match(/^#{1,6}\s*(.+)$/);
    if (headingMatch) {
      const cleanedTitle = headingMatch[1].replace(/^\*\*(.+)\*\*$/g, "$1");
      fragments.push(`<strong class="solve-inline-heading">${formatAssistantInline(cleanedTitle)}</strong>`);
    } else {
      const bulletMatch = currentLine.match(/^\s*[-*]\s+(.+)$/);
      if (bulletMatch) {
        fragments.push(
          `<span class="solve-bullet-line"><strong class="solve-bullet-dot">•</strong><span>${formatAssistantInline(bulletMatch[1])}</span></span>`
        );
      } else {
        fragments.push(formatAssistantInline(currentLine));
      }
    }

    if (index < lines.length - 1) {
      fragments.push("<br>");
    }
  }

  const restoredHtml = restoreMathSegments(fragments.join(""), mathSegments);
  return preserveMathNewlines(restoredHtml);
}


function renderRichText(target, text) {
  target.classList.remove("empty");
  const html = escapeHtml(String(text ?? "")).replaceAll("\n", "<br>");
  target.innerHTML = preserveMathNewlines(html);
  typesetMathJax([target]);
}


function renderError(target, message) {
  target.classList.remove("empty");
  target.textContent = `请求失败：${message}`;
}


function renderStoredRichContent(text, emptyLabel = "（空）") {
  const raw = String(text ?? "").trim();
  if (!raw) {
    return `<span class="content-empty">${escapeHtml(emptyLabel)}</span>`;
  }
  return renderSolveMessageText(raw, "assistant");
}


function showToast(message, type = "success") {
  if (!toast) {
    return;
  }
  toast.textContent = message;
  toast.classList.remove("hidden", "show", "error");
  if (type === "error") {
    toast.classList.add("error");
  }
  requestAnimationFrame(() => toast.classList.add("show"));
  if (toastTimer) {
    clearTimeout(toastTimer);
  }
  toastTimer = setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => toast.classList.add("hidden"), 360);
  }, 1800);
}


async function withPreservedScroll(task) {
  const top = window.scrollY || document.documentElement.scrollTop || 0;
  const result = await task();
  requestAnimationFrame(() => {
    window.scrollTo({ top, behavior: "auto" });
  });
  return result;
}


function rememberMessageImageUrl(url) {
  if (url) {
    solveMessageImageUrls.push(url);
  }
}


function revokeSolveMessageImageUrls() {
  solveMessageImageUrls.forEach((url) => {
    try {
      URL.revokeObjectURL(url);
    } catch {
      // Ignore object URL cleanup failures.
    }
  });
  solveMessageImageUrls = [];
}


function resetSolveAttachment() {
  pendingSolveFile = null;
  if (solveAttachmentObjectUrl) {
    URL.revokeObjectURL(solveAttachmentObjectUrl);
    solveAttachmentObjectUrl = null;
  }
  if (solveChatFileInput) {
    solveChatFileInput.value = "";
  }
  if (solveAttachmentPreview) {
    solveAttachmentPreview.classList.add("hidden");
  }
  if (solveAttachmentImage) {
    solveAttachmentImage.removeAttribute("src");
  }
  if (solveAttachmentName) {
    solveAttachmentName.textContent = "题目图片";
  }
}


function setSolveAttachment(file) {
  if (!file || !file.type?.startsWith("image/")) {
    resetSolveAttachment();
    return;
  }
  pendingSolveFile = file;
  if (solveAttachmentObjectUrl) {
    URL.revokeObjectURL(solveAttachmentObjectUrl);
  }
  solveAttachmentObjectUrl = URL.createObjectURL(file);
  if (solveAttachmentImage) {
    solveAttachmentImage.src = solveAttachmentObjectUrl;
  }
  if (solveAttachmentName) {
    solveAttachmentName.textContent = file.name || "题目图片";
  }
  if (solveAttachmentPreview) {
    solveAttachmentPreview.classList.remove("hidden");
  }
}


function buildSolveHistoryPayload() {
  return solveChatTurns
    .map((item) => {
      return {
        role: item.role,
        content: (item.historyContent || item.text || "").trim(),
      };
    })
    .filter((item) => item.content)
    .slice(-10);
}


function scrollSolveChatToBottom() {
  if (!solveChatLog) {
    return;
  }
  requestAnimationFrame(() => {
    solveChatLog.scrollTop = solveChatLog.scrollHeight;
  });
}


function setSolveComposerBusy(busy) {
  isSolveStreaming = Boolean(busy);
  if (solveSendBtn) {
    solveSendBtn.disabled = isSolveStreaming;
  }
  if (solveUploadTriggerBtn) {
    solveUploadTriggerBtn.disabled = isSolveStreaming;
  }
  if (solveAttachmentRemoveBtn) {
    solveAttachmentRemoveBtn.disabled = isSolveStreaming;
  }
  if (clearSolveChatBtn) {
    clearSolveChatBtn.disabled = isSolveStreaming;
  }
  if (solveModeSelect) {
    solveModeSelect.disabled = isSolveStreaming;
  }
  if (solveChatInput) {
    solveChatInput.disabled = isSolveStreaming;
  }
}


function renderSolveChat(options = {}) {
  if (!solveChatLog) {
    return;
  }

  const typeset = Boolean(options.typeset);
  const shouldTypesetStream = solveChatTurns.some(
    (item) => item.role === "assistant" && item.status === "streaming" && shouldTypesetStreamingMath(item.text)
  );
  if (!solveChatTurns.length) {
    solveChatLog.innerHTML = `
      <div class="solve-chat-ready">
        <span>AI解题已就绪</span>
      </div>
    `;
    return;
  }

  solveChatLog.innerHTML = solveChatTurns
    .map((item) => {
      const roleLabel = item.role === "assistant" ? "AI 助教" : "你";
      const isStreaming = item.role === "assistant" && item.status === "streaming";
      const bodyClass = item.text?.trim() ? "" : "empty";
      const imageBlock = item.attachmentUrl
        ? `<img src="${item.attachmentUrl}" alt="${escapeHtml(item.attachmentName || "题目图片")}" class="solve-message-image" />`
        : "";
      const metaBlock = item.extractedText
        ? `
          <details class="solve-message-meta">
            <summary>查看识别题干</summary>
            <div class="solve-message-meta-body">${escapeHtml(item.extractedText).replaceAll("\n", "<br>")}</div>
          </details>
        `
        : "";
      const streamBlock = isStreaming
        ? `
          <div class="solve-message-streaming">
            <div class="orb"></div>
            <span>AI 正在思考...</span>
          </div>
        `
        : "";
      const bodyText = item.text || (item.role === "assistant" ? "正在组织答案..." : "");
      const bodyHtml = renderSolveMessageText(bodyText, item.role);
      return `
        <div class="solve-message-row ${item.role}">
          <article class="solve-message-card">
            <div class="solve-message-head">
              <span class="solve-message-role">${roleLabel}</span>
              ${streamBlock}
            </div>
            <div class="solve-message-body ${bodyClass}" data-solve-role="${item.role}">${bodyHtml}</div>
            ${imageBlock}
            ${metaBlock}
          </article>
        </div>
      `;
    })
    .join("");

  scrollSolveChatToBottom();
  if (typeset) {
    scheduleTypesetMathJax(solveChatLog, { immediate: true });
  } else if (shouldTypesetStream) {
    scheduleTypesetMathJax(solveChatLog);
  }
}

function queueSolveChatRender(options = {}) {
  // Merge streaming deltas into a single frame to reduce chat flicker.
  solveChatRenderNeedsTypeset = solveChatRenderNeedsTypeset || Boolean(options.typeset);
  if (solveChatRenderFrame) {
    return;
  }
  solveChatRenderFrame = window.requestAnimationFrame(() => {
    const nextTypeset = solveChatRenderNeedsTypeset;
    solveChatRenderFrame = 0;
    solveChatRenderNeedsTypeset = false;
    renderSolveChat({ typeset: nextTypeset });
  });
}


function updateUserTurnHistoryFromResult(turn, result) {
  const userText = (turn.text || "").trim();
  const extractedText = (result?.extracted_text || "").trim();
  if (turn.attachmentName && extractedText) {
    turn.extractedText = extractedText;
    turn.historyContent = [
      userText ? `用户补充说明：\n${userText}` : "",
      `图片识别题目：\n${extractedText}`,
    ]
      .filter(Boolean)
      .join("\n\n");
    return;
  }
  turn.historyContent = userText;
}


function renderQaResult(result) {
  const head = [
    `回答类型：${result.answer_type ?? "未知"}`,
    `置信度：${Number(result.confidence ?? 0).toFixed(1)}%`,
    `命中条数：${result.total_matches ?? 0}`,
  ];
  const refs = (result.similar_questions ?? [])
    .slice(0, 5)
    .map(
      (item, index) =>
        `#${index + 1} ${item.question}\n综合相关度=${Number(item.score ?? 0).toFixed(3)}, 词项=${Number(item.lexical_score ?? 0).toFixed(3)}, 公式=${Number(item.formula_score ?? 0).toFixed(3)}`
    )
    .join("\n\n");
  renderRichText(qaResult, `${head.join("\n")}\n\n回答：\n${result.answer ?? ""}\n\n候选参考：\n${refs || "无"}`);
}


function renderSimulationResult(result) {
  const metrics = result?.key_metrics && typeof result.key_metrics === "object" ? result.key_metrics : {};
  const notes = Array.isArray(result?.notes) ? result.notes : [];
  const series = result?.series && typeof result.series === "object" ? result.series : {};
  const reportMarkdown = String(result?.report_markdown || "").trim();
  const plotImageDataUrl = String(result?.plot_image_data_url || "").trim();
  const plotCaption = String(result?.plot_caption || "异步电机 T-s 曲线").trim();

  const metricRows = Object.entries(metrics)
    .map(([key, value]) => {
      const label = getSimulationFieldLabel(key);
      const displayValue = Number.isFinite(Number(value)) ? formatNumber(value, 4) : String(value ?? "");
      return `<tr><th>${escapeHtml(label)}</th><td>${escapeHtml(displayValue)}</td></tr>`;
    })
    .join("");

  const notesHtml = notes.length
    ? `<ul class="sim-note-list">${notes.map((item) => `<li>${escapeHtml(String(item))}</li>`).join("")}</ul>`
    : `<p class="inline-note">暂无备注。</p>`;

  const seriesPreview = Object.entries(series)
    .map(([key, values]) => {
      const arrayValues = Array.isArray(values) ? values : [];
      const preview = arrayValues.slice(0, 8).map((item) => formatNumber(item, 3)).join(", ");
      const label = getSimulationFieldLabel(key);
      return `<li><strong>${escapeHtml(label)}</strong> (${arrayValues.length}点)：${escapeHtml(preview)}${arrayValues.length > 8 ? " ..." : ""}</li>`;
    })
    .join("");

  const reportHtml = reportMarkdown
    ? renderSolveMessageText(reportMarkdown, "assistant")
    : `<span class="content-empty">本次结果未生成实验报告。</span>`;

  const plotBlock = plotImageDataUrl
    ? `
      <section class="sim-result-block chart-block">
        <h4>仿真曲线</h4>
        <figure class="sim-result-figure">
          <img src="${escapeHtml(plotImageDataUrl)}" alt="${escapeHtml(plotCaption)}" />
          <figcaption>${escapeHtml(plotCaption)}</figcaption>
        </figure>
      </section>
    `
    : "";

  simResult.classList.remove("empty");
  simResult.innerHTML = `
    <div class="sim-result-shell">
      <div class="sim-result-meta">
        <span class="designer-pill">${escapeHtml(String(result?.machine_type || "电机实验"))}</span>
        <span class="designer-pill">后端：${escapeHtml(String(result?.backend || "auto"))}</span>
      </div>
      <section class="sim-result-block metrics-block">
        <h4>关键指标</h4>
        ${
          metricRows
            ? `<div class="solve-table-wrap"><table class="solve-md-table"><tbody>${metricRows}</tbody></table></div>`
            : `<p class="inline-note">暂无关键指标。</p>`
        }
      </section>
      <section class="sim-result-block report-block">
        <h4>实验报告</h4>
        <div class="sim-report rich-content">${reportHtml}</div>
      </section>
      ${plotBlock}
      <section class="sim-result-block preview-block">
        <h4>数据预览</h4>
        ${seriesPreview ? `<ul class="sim-note-list">${seriesPreview}</ul>` : `<p class="inline-note">暂无数据预览。</p>`}
      </section>
      <section class="sim-result-block notes-block">
        <h4>备注</h4>
        ${notesHtml}
      </section>
    </div>
  `;
  typesetMathJax([simResult]);
}


function getSimulationFieldLabel(key) {
  const normalized = String(key || "").trim();
  if (!normalized) {
    return "";
  }
  return SIMULATION_FIELD_LABELS[normalized] || normalized;
}


function getSimulationParamLabel(field) {
  const key = String(field?.key || "").trim();
  if (!key) {
    return "";
  }
  if (Object.prototype.hasOwnProperty.call(SIMULATION_PARAM_LABELS, key)) {
    return SIMULATION_PARAM_LABELS[key];
  }
  return escapeHtml(String(field?.label || key));
}


function renderWrongPagination(payload) {
  wrongPagination = {
    ...wrongPagination,
    ...payload,
    page: Number(payload.page ?? wrongPagination.page ?? 1),
    page_size: Number(payload.page_size ?? wrongPagination.page_size ?? 6),
    total: Number(payload.total ?? 0),
    total_pages: Number(payload.total_pages ?? 1),
    has_prev: Boolean(payload.has_prev),
    has_next: Boolean(payload.has_next),
  };

  if (wrongPageMeta) {
    wrongPageMeta.textContent = `共 ${wrongPagination.total} 条 · 第 ${wrongPagination.page}/${wrongPagination.total_pages} 页`;
  }
  if (wrongPrevBtn) {
    wrongPrevBtn.disabled = !wrongPagination.has_prev;
  }
  if (wrongNextBtn) {
    wrongNextBtn.disabled = !wrongPagination.has_next;
  }
  if (wrongPageSizeSelect) {
    wrongPageSizeSelect.value = String(wrongPagination.page_size);
  }
}


function renderWrongList(payload) {
  const items = payload.items ?? [];
  wrongQuestionItems = items;

  if (!items.length) {
    editingWrongId = null;
    wrongList.classList.add("empty");
    wrongList.textContent = "当前没有错题记录。";
    return;
  }

  if (editingWrongId && !items.some((item) => item.id === editingWrongId)) {
    editingWrongId = null;
  }

  wrongList.classList.remove("empty");
  wrongList.innerHTML = items
    .map((item, index) => {
      const createdAt = item.created_at ?? "";
      const source = item.source_type ?? "manual";
      const isEditing = editingWrongId === item.id;
      const rowNo = (wrongPagination.page - 1) * wrongPagination.page_size + index + 1;

      if (isEditing) {
        return `
          <article class="wrong-item" data-id="${item.id}">
            <h4>#${rowNo} · ID:${item.id} · ${source} · ${createdAt}</h4>
            <div class="wrong-item-grid">
              <div class="field">
                <span class="field-label">题干题目（只读）</span>
                <div class="preview-box rich-content">${renderStoredRichContent(item.question_text)}</div>
              </div>
              <div class="field">
                <span class="field-label">参考答案（只读）</span>
                <div class="preview-box rich-content">${renderStoredRichContent(item.answer_text)}</div>
              </div>
              <div class="field">
                <span class="field-label">错误原因（可修改）</span>
                <textarea data-field="error_reason">${escapeHtml(item.error_reason ?? "")}</textarea>
              </div>
            </div>
            <div class="wrong-item-actions">
              <button type="button" data-action="save" data-id="${item.id}">保存修改</button>
              <button type="button" class="btn-soft" data-action="cancel" data-id="${item.id}">取消</button>
            </div>
          </article>
        `;
      }

      return `
        <article class="wrong-item" data-id="${item.id}">
          <h4>#${rowNo} · ID:${item.id} · ${source} · ${createdAt}</h4>
          <div class="wrong-item-grid">
            <div class="field">
              <span class="field-label">题干题目</span>
              <div class="preview-box rich-content">${renderStoredRichContent(item.question_text)}</div>
            </div>
            <div class="field">
              <span class="field-label">参考答案</span>
              <div class="preview-box rich-content">${renderStoredRichContent(item.answer_text)}</div>
            </div>
            <div class="field">
              <span class="field-label">错误原因</span>
              <div class="preview-box rich-content">${renderStoredRichContent(item.error_reason)}</div>
            </div>
          </div>
          <div class="wrong-item-actions">
            <button type="button" data-action="edit" data-id="${item.id}">修改</button>
            <button type="button" class="btn-soft" data-action="delete" data-id="${item.id}">删除</button>
          </div>
        </article>
      `;
    })
    .join("");

  typesetMathJax([wrongList]);
}


function resetSolveFeedback() {
  lastSolveResult = null;
  solveFeedback.classList.add("hidden");
  wrongReasonWrap.classList.add("hidden");
  wrongReasonInput.value = "";
  solveFeedbackTip.textContent = "";
}


function renderSolveFeedback(result, sourceType) {
  if (!result || !result.success) {
    resetSolveFeedback();
    return;
  }
  lastSolveResult = result;
  lastSolveSourceType = sourceType || "text";
  solveFeedback.classList.remove("hidden");
  wrongReasonWrap.classList.add("hidden");
  wrongReasonInput.value = "";
  solveFeedbackTip.textContent = "如果这题做错了，可以加入错题本并填写错误原因。";
}

async function createWrongQuestionRecord(payload) {
  // Reuse one save path for both solve-page wrong questions and coach practice items.
  const response = await apiRequest("/api/wrong-questions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await loadWrongQuestions({ requestedPage: 1, pageSize: wrongPagination.page_size });
  await loadHealth();
  return response;
}


function parseStreamBuffer(buffer, onEvent) {
  const lines = buffer.split("\n");
  const rest = lines.pop() || "";
  lines.forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed) {
      return;
    }
    try {
      onEvent(JSON.parse(trimmed));
    } catch {
      // Ignore malformed partial line.
    }
  });
  return rest;
}


async function consumeSolveStream(response, onEvent) {
  if (!response.body) {
    throw new Error("浏览器不支持流式响应。");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    buffer = parseStreamBuffer(buffer, onEvent);
  }

  buffer += decoder.decode();
  const rest = buffer.trim();
  if (rest) {
    onEvent(JSON.parse(rest));
  }
}


async function apiRequest(path, options = {}) {
  const response = await fetch(path, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || toPrettyJson(payload) || `HTTP ${response.status}`);
  }
  return payload;
}


async function loadHealth() {
  try {
    const health = await apiRequest("/api/health");
    healthLine.textContent = `AI: ${health.ai_ready ? "就绪" : "未配置"} | 知识库: ${health.knowledge_count} | 错题数: ${health.wrong_question_count}`;
  } catch (error) {
    healthLine.textContent = `健康检查失败：${error.message}`;
  }
}


async function loadMatlabStatus() {
  if (!simMatlabStatus) {
    return;
  }
  simMatlabStatus.textContent = "MATLAB 状态检查中...";
  try {
    const status = await apiRequest("/api/simulate/matlab-status");
    applyMatlabCliConfig(status);
    if (status.local_matlab_available) {
      const mode = status.local_matlab_mode === "cli" ? "CLI" : "Engine";
      const sourceText = mode === "CLI" && status.local_cli_source === "custom" ? "，自定义路径" : "";
      const suffix = mode === "CLI" && status.local_cli_executable ? `（${status.local_cli_executable}）` : "";
      simMatlabStatus.textContent = `MATLAB 本地后端：可用（${mode}${sourceText}${suffix}）。`;
      return;
    }
    if (status.service_online && status.service_matlab_available) {
      simMatlabStatus.textContent = "MATLAB 本地引擎不可用，已打通独立仿真服务 MATLAB 后端。";
      return;
    }

    const localError = status.local_matlab_error
      ? `本地原因：${status.local_matlab_error}`
      : (status.local_engine_error || status.local_cli_error
        ? `本地原因：${status.local_engine_error || ""} ${status.local_cli_error || ""}`.trim()
        : "本地引擎/CLI未连接。");
    const serviceError = status.service_online
      ? (status.service_matlab_error ? ` 服务原因：${status.service_matlab_error}` : " 服务未检测到 MATLAB 可用。")
      : " 仿真服务未在线。";
    simMatlabStatus.textContent = `MATLAB 当前不可用。${localError}${serviceError}`;
  } catch (error) {
    simMatlabStatus.textContent = `MATLAB 状态检查失败：${error.message}`;
  }
}


function applyMatlabCliConfig(status = {}) {
  const mode = String(status.cli_config_mode || "auto");
  const configuredPath = String(status.cli_configured_path || "");
  const resolvedPath = String(status.cli_resolved_path || status.local_cli_executable || "");

  if (matlabCliModeSelect) {
    matlabCliModeSelect.value = mode === "custom" ? "custom" : "auto";
  }
  if (matlabCliPathInput) {
    matlabCliPathInput.value = configuredPath;
    matlabCliPathInput.disabled = mode !== "custom";
  }
  if (matlabCliSaveBtn) {
    matlabCliSaveBtn.textContent = mode === "custom" ? "保存手动路径" : "保存自动探测";
  }
  if (!simMatlabConfigNote) {
    return;
  }

  if (mode === "custom") {
    simMatlabConfigNote.textContent = resolvedPath
      ? `当前为手动指定模式，已解析到：${resolvedPath}`
      : "当前为手动指定模式。请填写 MATLAB 安装目录或 matlab.exe 完整路径。";
    return;
  }

  simMatlabConfigNote.textContent = resolvedPath
    ? `当前为自动探测模式，已识别本机 MATLAB：${resolvedPath}`
    : "当前为自动探测模式。它会优先尝试环境变量、PATH 和常见版本目录，适合不同电脑直接迁移。";
  refreshCompactSelectWidths();
}


async function loadWrongQuestions(options = {}) {
  const keepScroll = Boolean(options.keepScroll);
  if (Number.isFinite(options.requestedPage)) {
    wrongPagination.page = Math.max(1, Number(options.requestedPage));
  }
  if (Number.isFinite(options.pageSize)) {
    wrongPagination.page_size = Math.max(1, Number(options.pageSize));
  }

  const top = keepScroll ? window.scrollY || document.documentElement.scrollTop || 0 : null;
  const listTop = keepScroll ? wrongList.scrollTop || 0 : null;
  if (!keepScroll) {
    wrongList.classList.add("empty");
    wrongList.textContent = "正在加载错题记录...";
  }

  try {
    const query = new URLSearchParams({
      page: String(wrongPagination.page),
      page_size: String(wrongPagination.page_size),
    });
    const payload = await apiRequest(`/api/wrong-questions?${query.toString()}`);
    renderWrongPagination(payload);
    renderWrongList(payload);
  } catch (error) {
    renderError(wrongList, error.message);
  } finally {
    if (top !== null || listTop !== null) {
      requestAnimationFrame(() => {
        if (top !== null) {
          const currentTop = window.scrollY || document.documentElement.scrollTop || 0;
          if (Math.abs(currentTop - top) > 2) {
            window.scrollTo({ top, behavior: "auto" });
          }
        }
        if (listTop !== null) {
          wrongList.scrollTop = listTop;
        }
      });
    }
  }
}


function renderSimulationLabList() {
  if (!simLabList) {
    return;
  }
  if (!simulationLabs.length) {
    simLabList.classList.add("empty");
    simLabList.textContent = "未获取到实验清单。";
    return;
  }

  simLabList.classList.remove("empty");
  simLabList.innerHTML = simulationLabs
    .map((lab) => {
      const active = currentSimulationLab?.id === lab.id ? "active" : "";
      return `
        <button type="button" class="sim-lab-tab ${active}" data-lab-id="${escapeHtml(lab.id)}">
          <strong>${escapeHtml(lab.title || lab.id)}</strong>
          <span>${escapeHtml(lab.subtitle || "")}</span>
        </button>
      `;
    })
    .join("");
}


function renderSimulationLabDetail(lab) {
  if (!simLabDetail || !lab) {
    return;
  }
  const steps = Array.isArray(lab.tutorial_steps) ? lab.tutorial_steps : [];
  const points = Array.isArray(lab.focus_points) ? lab.focus_points : [];
  const stepsHtml = steps.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const pointsHtml = points.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  simLabDetail.classList.remove("empty");
  simLabDetail.innerHTML = `
    <div class="sim-lab-detail-shell">
      <div class="sim-lab-detail-meta">
        <span class="designer-pill">${escapeHtml(lab.machine_type || "电机实验")}</span>
        <h4>${escapeHtml(lab.title || "实验")}</h4>
        <p>${escapeHtml(lab.description || "")}</p>
      </div>
      <div class="sim-lab-figure-grid">
        <figure class="designer-figure">
          <img src="${escapeHtml(lab.circuit_image || "")}" alt="${escapeHtml(lab.title || "实验电路图")}" />
          <figcaption>实验电路图</figcaption>
        </figure>
        <figure class="designer-figure">
          <img src="${escapeHtml(lab.curve_image || "")}" alt="${escapeHtml(lab.title || "实验曲线")}" />
          <figcaption>建议观察曲线</figcaption>
        </figure>
      </div>
      <div class="sim-lab-detail-grid">
        <section class="designer-guidance">
          <h5>操作步骤</h5>
          <ul class="sim-guidance-list">${stepsHtml}</ul>
        </section>
        <section class="designer-guidance">
          <h5>重点观察</h5>
          ${pointsHtml ? `<ul class="sim-guidance-list sim-lab-focus">${pointsHtml}</ul>` : `<span class="content-empty">暂无重点。</span>`}
        </section>
      </div>
    </div>
  `;
}


function renderSimulationLabParams(lab) {
  if (!simLabParams || !lab) {
    return;
  }
  const fields = Array.isArray(lab.parameters) ? lab.parameters : [];
  simLabParams.innerHTML = fields
    .map((field) => {
      const key = String(field.key || "").trim();
      if (!key) {
        return "";
      }
      const label = getSimulationParamLabel(field);
      const min = Number.isFinite(Number(field.min)) ? String(field.min) : "";
      const max = Number.isFinite(Number(field.max)) ? String(field.max) : "";
      const step = Number.isFinite(Number(field.step)) ? String(field.step) : "any";
      const value = field.default ?? "";
      return `
        <label class="sim-param-field">
          <span class="sim-param-label">${label}</span>
          <input
            type="number"
            data-param-key="${escapeHtml(key)}"
            value="${escapeHtml(String(value))}"
            min="${escapeHtml(min)}"
            max="${escapeHtml(max)}"
            step="${escapeHtml(step)}"
          />
        </label>
      `;
    })
    .join("");

  typesetMathJax([simLabParams]);
}


function renderSimulationCoachLog(options = {}) {
  if (!simCoachLog) {
    return;
  }
  const typeset = Boolean(options.typeset);
  if (!simCoachTurns.length) {
    simCoachLog.innerHTML = `
      <div class="sim-coach-ready">
        <span>仿真助教已就绪</span>
      </div>
    `;
    return;
  }

  simCoachLog.innerHTML = simCoachTurns
    .map((item) => {
      const roleLabel = item.role === "assistant" ? "AI 助教" : "你";
      const body = renderSolveMessageText(item.text || "", item.role);
      const pendingBlock = item.role === "assistant" && item.pending
        ? `
          <div class="sim-coach-pending">
            <div class="orb"></div>
            <span>AI 正在思考...</span>
          </div>
        `
        : "";
      return `
        <div class="sim-coach-row ${item.role}">
          <article class="sim-coach-card">
            <header>
              <strong>${roleLabel}</strong>
            </header>
            ${pendingBlock}
            <div class="sim-coach-content">${body || "<span class='content-empty'>...</span>"}</div>
          </article>
        </div>
      `;
    })
    .join("");
  requestAnimationFrame(() => {
    simCoachLog.scrollTop = simCoachLog.scrollHeight;
  });
  if (typeset) {
    scheduleTypesetMathJax(simCoachLog, { immediate: true });
  }
}


function setSimulationCoachBusy(busy) {
  isSimCoachPending = Boolean(busy);
  if (simCoachInput) {
    simCoachInput.disabled = isSimCoachPending;
  }
  if (simCoachSendBtn) {
    simCoachSendBtn.disabled = isSimCoachPending;
  }
  if (simCoachClearBtn) {
    simCoachClearBtn.disabled = isSimCoachPending;
  }
  setThinking(simCoachThinking, isSimCoachPending);
}


function collectSimulationLabParams() {
  const payload = {};
  if (!simLabParams) {
    return payload;
  }
  simLabParams.querySelectorAll("[data-param-key]").forEach((input) => {
    const key = String(input.dataset.paramKey || "").trim();
    if (!key) {
      return;
    }
    payload[key] = Number(input.value);
  });
  return payload;
}


function setCurrentSimulationLab(labId) {
  const found = simulationLabs.find((item) => item.id === labId);
  if (!found) {
    return;
  }
  currentSimulationLab = found;
  renderSimulationLabList();
  renderSimulationLabDetail(found);
  renderSimulationLabParams(found);
  simCoachTurns = [];
  renderSimulationCoachLog();
}


async function loadSimulationLabs() {
  if (!simLabList) {
    return;
  }
  simLabList.classList.add("empty");
  simLabList.textContent = "正在加载固定实验清单...";
  try {
    const payload = await apiRequest("/api/simulate/labs");
    simulationLabs = Array.isArray(payload.items) ? payload.items : [];
    renderSimulationLabList();
    if (simulationLabs.length) {
      const preferredLab = simulationLabs.find((item) => item.id === currentSimulationLab?.id) || simulationLabs[0];
      setCurrentSimulationLab(preferredLab.id);
    } else if (simLabDetail) {
      simLabDetail.classList.add("empty");
      simLabDetail.textContent = "暂无实验详情。";
    }
  } catch (error) {
    simLabList.classList.add("empty");
    simLabList.textContent = `加载实验清单失败：${error.message}`;
  }
}


navButtons.forEach((button) => {
  button.addEventListener("click", () => setPanel(button.dataset.panel));
});


solveUploadTriggerBtn?.addEventListener("click", () => {
  solveChatFileInput?.click();
});


solveAttachmentRemoveBtn?.addEventListener("click", () => {
  resetSolveAttachment();
});


solveChatFileInput?.addEventListener("change", (event) => {
  const file = event.target?.files?.[0];
  setSolveAttachment(file);
});


clearSolveChatBtn?.addEventListener("click", () => {
  if (isSolveStreaming) {
    return;
  }
  solveChatTurns = [];
  resetSolveFeedback();
  resetSolveAttachment();
  revokeSolveMessageImageUrls();
  queueSolveChatRender();
  if (solveChatInput) {
    solveChatInput.value = "";
    solveChatInput.focus();
  }
});


solveChatForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (isSolveStreaming) {
    return;
  }
  const messageText = solveChatInput?.value?.trim() || "";
  const attachment = pendingSolveFile;
  const solveMode = solveModeSelect?.value || "standard";

  if (!messageText && !attachment) {
    showToast("请先输入题目或上传图片", "error");
    return;
  }

  const historyPayload = buildSolveHistoryPayload();
  const attachmentUrl = attachment ? URL.createObjectURL(attachment) : "";
  rememberMessageImageUrl(attachmentUrl);

  const userTurn = {
    id: `u_${Date.now()}`,
    role: "user",
    text: messageText || (attachment ? "请识别并解题" : ""),
    historyContent: messageText || (attachment ? "请识别并解题" : ""),
    attachmentName: attachment?.name || "",
    attachmentUrl,
    extractedText: "",
  };
  const assistantTurn = {
    id: `a_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`,
    role: "assistant",
    text: "",
    historyContent: "",
    status: "streaming",
    extractedText: "",
  };

  solveChatTurns.push(userTurn, assistantTurn);
  queueSolveChatRender();
  resetSolveFeedback();
  setSolveComposerBusy(true);

  if (solveChatInput) {
    solveChatInput.value = "";
  }
  resetSolveAttachment();

  const formData = new FormData();
  formData.append("message", messageText);
  formData.append("history_json", JSON.stringify(historyPayload));
  formData.append("top_k", "3");
  formData.append("solve_mode", solveMode);
  if (attachment) {
    formData.append("file", attachment);
  }

  try {
    let receivedDone = false;
    const response = await fetch("/api/solve/chat/stream", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }

    await consumeSolveStream(response, (payload) => {
      if (payload.type === "meta") {
        assistantTurn.extractedText = payload.extracted_text || "";
        queueSolveChatRender();
        return;
      }

      if (payload.type === "delta") {
        assistantTurn.text += payload.delta || "";
        queueSolveChatRender();
        return;
      }

      if (payload.type === "done") {
        receivedDone = true;
        const result = payload.result || {};
        assistantTurn.status = "done";
        assistantTurn.text = result.solution || assistantTurn.text;
        assistantTurn.historyContent = assistantTurn.text;
        if (result.extracted_text) {
          assistantTurn.extractedText = result.extracted_text;
        }
        lastSolveResult = result;
        lastSolveSourceType = attachment ? "image" : "text";
        updateUserTurnHistoryFromResult(userTurn, result);
        queueSolveChatRender({ typeset: true });
        renderSolveFeedback(result, lastSolveSourceType);
        return;
      }

      if (payload.type === "error") {
        throw new Error(payload.error || payload.message || "流式解题失败。");
      }
    });
    if (!receivedDone && assistantTurn.text.trim()) {
      assistantTurn.status = "done";
      assistantTurn.historyContent = assistantTurn.text;
      queueSolveChatRender({ typeset: true });
    }
  } catch (error) {
    assistantTurn.status = "error";
    assistantTurn.text = `请求失败：${error.message}`;
    assistantTurn.historyContent = assistantTurn.text;
    resetSolveFeedback();
    queueSolveChatRender();
    showToast("AI 解题失败", "error");
  } finally {
    setSolveComposerBusy(false);
    solveChatInput?.focus();
  }
});


document.querySelector("#qa-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = document.querySelector("#qa-question").value.trim();
  if (!question) {
    renderError(qaResult, "请先输入问题。");
    return;
  }
  const top_k = Number(document.querySelector("#qa-topk").value || "3");
  const similarity_threshold = Number(document.querySelector("#qa-threshold").value || "0.18");
  setThinking(qaThinking, true);
  try {
    const result = await apiRequest("/api/qa/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, top_k, similarity_threshold }),
    });
    renderQaResult(result);
  } catch (error) {
    renderError(qaResult, error.message);
  } finally {
    setThinking(qaThinking, false);
  }
});


simLabList?.addEventListener("click", (event) => {
  const tab = event.target.closest("button[data-lab-id]");
  if (!tab) {
    return;
  }
  const labId = String(tab.dataset.labId || "").trim();
  if (!labId) {
    return;
  }
  setCurrentSimulationLab(labId);
});


matlabCliModeSelect?.addEventListener("change", () => {
  const isCustom = matlabCliModeSelect.value === "custom";
  if (matlabCliPathInput) {
    matlabCliPathInput.disabled = !isCustom;
    if (!isCustom) {
      matlabCliPathInput.value = "";
    }
  }
  if (simMatlabConfigNote && isCustom) {
    simMatlabConfigNote.textContent = "请填写 MATLAB 安装目录或 matlab.exe 完整路径，然后保存。";
  }
});


matlabCliSaveBtn?.addEventListener("click", async () => {
  const mode = matlabCliModeSelect?.value || "auto";
  const executablePath = matlabCliPathInput?.value?.trim() || "";
  try {
    const status = await apiRequest("/api/simulate/matlab-cli-config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode,
        executable_path: executablePath,
      }),
    });
    applyMatlabCliConfig(status);
    await loadMatlabStatus();
    showToast(status.message || "MATLAB 路径配置已保存");
  } catch (error) {
    showToast(error.message || "MATLAB 路径配置失败", "error");
  }
});


simLabForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (isSimLabRunning) {
    return;
  }
  if (!currentSimulationLab) {
    showToast("请先选择一个实验。", "error");
    return;
  }
  const payload = {
    lab_id: currentSimulationLab.id,
    params: collectSimulationLabParams(),
    backend: simBackendSelect?.value || "auto",
  };
  isSimLabRunning = true;
  if (simRunBtn) {
    simRunBtn.disabled = true;
  }
  setThinking(simThinking, true);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 90_000);

  try {
    const result = await apiRequest("/api/simulate/lab-run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    renderSimulationResult(result);
    showToast("实验运行完成");
  } catch (error) {
    const message = error.name === "AbortError"
      ? "实验运行超时，请尝试切换仿真后端为 python 后重试。"
      : error.message;
    renderError(simResult, message);
    showToast("实验运行失败", "error");
  } finally {
    clearTimeout(timeoutId);
    isSimLabRunning = false;
    if (simRunBtn) {
      simRunBtn.disabled = false;
    }
    setThinking(simThinking, false);
  }
});


simCoachClearBtn?.addEventListener("click", () => {
  if (isSimCoachPending) {
    return;
  }
  simCoachTurns = [];
  renderSimulationCoachLog();
  simCoachInput?.focus();
});


simCoachForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (isSimCoachPending) {
    return;
  }
  if (!currentSimulationLab) {
    showToast("请先选择实验，再向助教提问。", "error");
    return;
  }
  const message = simCoachInput?.value?.trim() || "";
  if (!message) {
    showToast("请先输入问题。", "error");
    return;
  }

  const history = simCoachTurns
    .map((item) => ({ role: item.role, content: String(item.text || "").trim() }))
    .filter((item) => (item.role === "user" || item.role === "assistant") && item.content)
    .slice(-8);

  const userTurn = {
    role: "user",
    text: message,
  };
  const assistantTurn = {
    role: "assistant",
    text: "",
    pending: true,
  };
  simCoachTurns.push(userTurn, assistantTurn);
  renderSimulationCoachLog();
  setSimulationCoachBusy(true);
  if (simCoachInput) {
    simCoachInput.value = "";
  }

  try {
    const payload = await apiRequest("/api/simulate/lab-coach/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lab_id: currentSimulationLab.id,
        message,
        history,
      }),
    });
    assistantTurn.pending = false;
    assistantTurn.text = payload.answer || "暂无回复。";
    renderSimulationCoachLog({ typeset: true });
  } catch (error) {
    assistantTurn.pending = false;
    assistantTurn.text = `请求失败：${error.message}`;
    renderSimulationCoachLog();
    showToast("仿真助教请求失败", "error");
  } finally {
    setSimulationCoachBusy(false);
    simCoachInput?.focus();
  }
});


addToWrongbookBtn.addEventListener("click", () => {
  if (!lastSolveResult) {
    solveFeedbackTip.textContent = "请先完成一次解题后再操作。";
    return;
  }
  const isHidden = wrongReasonWrap.classList.contains("hidden");
  wrongReasonWrap.classList.toggle("hidden", !isHidden);
  solveFeedbackTip.textContent = isHidden ? "请填写错误原因后确认加入。" : "你可以继续解下一题，或再次点击加入错题本。";
  if (isHidden) {
    wrongReasonInput.focus();
  }
});


saveWrongQuestionBtn.addEventListener("click", async () => {
  if (!lastSolveResult || !lastSolveResult.success) {
    solveFeedbackTip.textContent = "当前没有可保存的解题结果。";
    return;
  }
  const reason = wrongReasonInput.value.trim();
  if (!reason) {
    solveFeedbackTip.textContent = "请先填写错误原因。";
    wrongReasonInput.focus();
    return;
  }
  try {
    await createWrongQuestionRecord({
      question_text: lastSolveResult.extracted_text || "",
      answer_text: lastSolveResult.solution || "",
      error_reason: reason,
      source_type: lastSolveSourceType,
      image_path: lastSolveResult.image_path || null,
    });
    wrongReasonWrap.classList.add("hidden");
    wrongReasonInput.value = "";
    solveFeedbackTip.textContent = "已加入错题本。";
    showToast("已加入错题本");
  } catch (error) {
    solveFeedbackTip.textContent = `保存失败：${error.message}`;
    showToast("加入错题本失败", "error");
  }
});


wrongList.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) {
    return;
  }
  const action = button.dataset.action;
  const recordId = Number(button.dataset.id || "0");
  if (!recordId) {
    return;
  }
  const card = button.closest(".wrong-item");
  if (!card) {
    return;
  }

  if (action === "edit") {
    editingWrongId = recordId;
    await withPreservedScroll(async () => {
      renderWrongList({ items: wrongQuestionItems, ...wrongPagination });
    });
    return;
  }

  if (action === "cancel") {
    editingWrongId = null;
    await withPreservedScroll(async () => {
      renderWrongList({ items: wrongQuestionItems, ...wrongPagination });
    });
    return;
  }

  if (action === "delete") {
    try {
      await apiRequest(`/api/wrong-questions/${recordId}`, { method: "DELETE" });
      showToast("已删除错题");
      await loadWrongQuestions({ keepScroll: true });
      await loadHealth();
    } catch (error) {
      renderError(wrongList, error.message);
      showToast("删除失败", "error");
    }
    return;
  }

  if (action === "save") {
    const currentItem = wrongQuestionItems.find((item) => Number(item.id) === recordId) || {};
    const questionText = String(currentItem.question_text ?? "");
    const answerText = String(currentItem.answer_text ?? "");
    const errorReason = card.querySelector("textarea[data-field='error_reason']")?.value ?? "";
    try {
      await apiRequest(`/api/wrong-questions/${recordId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question_text: questionText.trim(),
          answer_text: answerText.trim(),
          error_reason: errorReason.trim(),
        }),
      });
      editingWrongId = null;
      showToast("保存修改成功");
      await loadWrongQuestions({ keepScroll: true });
    } catch (error) {
      renderError(wrongList, error.message);
      showToast("保存修改失败", "error");
    }
  }
});


document.querySelector("#reload-wrong").addEventListener("click", async () => {
  editingWrongId = null;
  await loadWrongQuestions({ requestedPage: 1, pageSize: wrongPagination.page_size });
  await loadHealth();
});


wrongPrevBtn?.addEventListener("click", async () => {
  if (!wrongPagination.has_prev) {
    return;
  }
  editingWrongId = null;
  await loadWrongQuestions({ requestedPage: wrongPagination.page - 1, pageSize: wrongPagination.page_size });
});


wrongNextBtn?.addEventListener("click", async () => {
  if (!wrongPagination.has_next) {
    return;
  }
  editingWrongId = null;
  await loadWrongQuestions({ requestedPage: wrongPagination.page + 1, pageSize: wrongPagination.page_size });
});


wrongPageSizeSelect?.addEventListener("change", async () => {
  const pageSize = Number(wrongPageSizeSelect.value || "6");
  wrongPagination.page_size = pageSize;
  editingWrongId = null;
  await loadWrongQuestions({ requestedPage: 1, pageSize });
});


compactSelects.forEach((select) => {
  select.addEventListener("change", () => syncCompactSelectWidth(select));
});
