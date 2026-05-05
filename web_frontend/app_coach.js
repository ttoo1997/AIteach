const analyzeWrongbookBtn = document.querySelector("#analyze-wrongbook");
const newPracticeQuestionBtn = document.querySelector("#new-practice-question");
const wrongAnalysis = document.querySelector("#wrong-analysis");
const practiceCard = document.querySelector("#practice-card");
const practiceTitle = document.querySelector("#practice-title");
const practiceMeta = document.querySelector("#practice-meta");
const practiceQuestion = document.querySelector("#practice-question");
const practiceHint = document.querySelector("#practice-hint");
const practiceAttempt = document.querySelector("#practice-attempt");
const showPracticeExplainBtn = document.querySelector("#show-practice-explain");
const practiceAddToWrongbookBtn = document.querySelector("#practice-add-to-wrongbook");
const anotherPracticeQuestionBtn = document.querySelector("#another-practice-question");
const practiceExplanation = document.querySelector("#practice-explanation");

let latestWrongbookAnalysis = null;
let currentPracticeQuestion = null;
let currentPracticeExplanation = null;

function buildPracticeQuestionText(payload) {
  if (!payload) {
    return "";
  }
  const points = Array.isArray(payload.knowledge_points) ? payload.knowledge_points : [];
  return [
    payload.title ? `### ${payload.title}` : "",
    payload.question || "",
    points.length ? `**考点**\n- ${points.join("\n- ")}` : "",
    payload.hint ? `**提示**\n${payload.hint}` : "",
  ]
    .filter(Boolean)
    .join("\n\n");
}

function buildPracticeAnswerText(questionPayload, explainPayload) {
  return [
    questionPayload?.answer_outline ? `**参考思路**\n${questionPayload.answer_outline}` : "",
    questionPayload?.solution ? `**参考答案**\n${questionPayload.solution}` : "",
    explainPayload?.explanation ? `**AI解析**\n${explainPayload.explanation}` : "",
  ]
    .filter(Boolean)
    .join("\n\n");
}

function syncPracticeWrongbookButton() {
  if (!practiceAddToWrongbookBtn) {
    return;
  }
  const canSave = Boolean(currentPracticeQuestion && currentPracticeExplanation);
  practiceAddToWrongbookBtn.classList.toggle("hidden", !canSave);
  practiceAddToWrongbookBtn.disabled = !canSave || Boolean(currentPracticeQuestion?.saved_to_wrongbook);
  practiceAddToWrongbookBtn.textContent = currentPracticeQuestion?.saved_to_wrongbook ? "已加入错题本" : "加入错题本";
}

async function saveCurrentPracticeToWrongbook(explainPayload = currentPracticeExplanation) {
  if (!currentPracticeQuestion || currentPracticeQuestion.saved_to_wrongbook || !explainPayload) {
    return false;
  }
  // Keep coach-generated practice records in the same format as regular wrongbook entries.
  const answerPreview = buildPracticeAnswerText(currentPracticeQuestion, explainPayload);
  const attemptText = (practiceAttempt?.value || "").trim();
  const reason = attemptText
    ? `AI教练练习题，已查看解析。\n\n用户作答：\n${attemptText}`
    : "AI教练练习题，已查看解析，建议后续再次独立完成。";

  await createWrongQuestionRecord({
    question_text: buildPracticeQuestionText(currentPracticeQuestion),
    answer_text: answerPreview || (explainPayload.explanation || currentPracticeQuestion.solution || ""),
    error_reason: reason,
    source_type: "practice",
    image_path: null,
  });
  currentPracticeQuestion.saved_to_wrongbook = true;
  syncPracticeWrongbookButton();
  return true;
}

function clearPracticeDisplay() {
  currentPracticeQuestion = null;
  currentPracticeExplanation = null;
  if (!practiceCard) {
    return;
  }
  practiceCard.classList.add("hidden");
  practiceAttempt.value = "";
  practiceQuestion.classList.add("empty");
  practiceQuestion.textContent = "";
  practiceHint.textContent = "";
  practiceExplanation.classList.add("hidden", "empty");
  practiceExplanation.textContent = "点击“查看解析”后展示讲解。";
  syncPracticeWrongbookButton();
}

function renderWrongbookAnalysis(payload) {
  latestWrongbookAnalysis = payload || null;
  if (!payload || !payload.analysis_text) {
    wrongAnalysis.classList.add("empty");
    wrongAnalysis.textContent = "暂无分析结果。";
    return;
  }
  renderRichText(wrongAnalysis, payload.analysis_text);
}

function renderPracticeQuestion(payload) {
  currentPracticeQuestion = { ...payload, saved_to_wrongbook: false };
  currentPracticeExplanation = null;
  practiceCard.classList.remove("hidden");
  practiceTitle.textContent = currentPracticeQuestion.title || "练习题";
  practiceMeta.textContent = currentPracticeQuestion.difficulty ? `难度：${currentPracticeQuestion.difficulty}` : "难度：中等";

  const points = Array.isArray(currentPracticeQuestion.knowledge_points) ? currentPracticeQuestion.knowledge_points : [];
  const pointsText = points.length ? `\n\n考点：${points.join("、")}` : "";
  renderRichText(practiceQuestion, `${currentPracticeQuestion.question || ""}${pointsText}`);
  practiceHint.textContent = currentPracticeQuestion.hint ? `提示：${currentPracticeQuestion.hint}` : "";

  practiceAttempt.value = "";
  practiceExplanation.classList.add("hidden", "empty");
  practiceExplanation.textContent = "点击“查看解析”后展示讲解。";
  syncPracticeWrongbookButton();
}

function renderPracticeExplanation(payload) {
  currentPracticeExplanation = payload || null;
  practiceExplanation.classList.remove("hidden");
  renderRichText(practiceExplanation, payload?.explanation || "暂无解析。");
  syncPracticeWrongbookButton();
}

async function createPracticeQuestion() {
  if (!latestWrongbookAnalysis) {
    showToast("请先点击“分析掌握情况”", "error");
    return;
  }

  const focus = latestWrongbookAnalysis?.analysis?.weaknesses?.[0] || "";
  setThinking(wrongAiThinking, true);
  newPracticeQuestionBtn.disabled = true;
  anotherPracticeQuestionBtn.disabled = true;
  showPracticeExplainBtn.disabled = true;
  practiceAddToWrongbookBtn?.classList.add("hidden");
  try {
    const payload = await apiRequest("/api/wrong-questions/practice/new", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ focus }),
    });
    renderPracticeQuestion(payload);
    showToast("已生成练习题");
  } catch (error) {
    showToast("生成练习题失败", "error");
    renderError(wrongAnalysis, error.message);
  } finally {
    setThinking(wrongAiThinking, false);
    newPracticeQuestionBtn.disabled = false;
    anotherPracticeQuestionBtn.disabled = false;
    showPracticeExplainBtn.disabled = false;
  }
}

analyzeWrongbookBtn?.addEventListener("click", async () => {
  setThinking(wrongAiThinking, true);
  analyzeWrongbookBtn.disabled = true;
  try {
    const payload = await apiRequest("/api/wrong-questions/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ record_limit: 120 }),
    });
    renderWrongbookAnalysis(payload);
    showToast("学情分析已完成");
  } catch (error) {
    renderError(wrongAnalysis, error.message);
    showToast("学情分析失败", "error");
  } finally {
    setThinking(wrongAiThinking, false);
    analyzeWrongbookBtn.disabled = false;
  }
});

newPracticeQuestionBtn?.addEventListener("click", createPracticeQuestion);
anotherPracticeQuestionBtn?.addEventListener("click", createPracticeQuestion);

showPracticeExplainBtn?.addEventListener("click", async () => {
  if (!currentPracticeQuestion?.question_id) {
    showToast("请先生成练习题", "error");
    return;
  }
  setThinking(wrongAiThinking, true);
  showPracticeExplainBtn.disabled = true;
  try {
    const payload = await apiRequest("/api/wrong-questions/practice/explain", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question_id: currentPracticeQuestion.question_id,
        user_answer: practiceAttempt.value || "",
      }),
    });
    renderPracticeExplanation(payload);
    showToast("解析已生成，可按需加入错题本");
  } catch (error) {
    showToast("生成解析失败", "error");
  } finally {
    setThinking(wrongAiThinking, false);
    showPracticeExplainBtn.disabled = false;
  }
});

practiceAddToWrongbookBtn?.addEventListener("click", async () => {
  if (!currentPracticeQuestion) {
    showToast("请先生成练习题", "error");
    return;
  }
  if (!currentPracticeExplanation) {
    showToast("请先查看解析，再决定是否加入错题本", "error");
    return;
  }
  if (currentPracticeQuestion.saved_to_wrongbook) {
    showToast("这道练习题已经加入错题本");
    return;
  }

  practiceAddToWrongbookBtn.disabled = true;
  try {
    await saveCurrentPracticeToWrongbook(currentPracticeExplanation);
    showToast("已加入错题本");
  } catch (error) {
    practiceAddToWrongbookBtn.disabled = false;
    showToast(`加入错题本失败：${error.message}`, "error");
  }
});
