import json
import os
import re
from typing import Any, Dict, Iterator, List, Optional

import dashscope
from dashscope import Generation, MultiModalConversation
from dashscope.api_entities.dashscope_response import Role

from app_config import DEFAULT_TEXT_MODEL, DEFAULT_VISION_MODEL
from runtime_env import clear_invalid_proxy_env, load_local_env
from schemas.contracts import SolveResult


load_local_env()
clear_invalid_proxy_env()


DEFAULT_SYSTEM_PROMPT = (
    "你是电机学课程助教，但回答标准要接近严谨阅卷老师。回答时必须紧扣题意，优先依据题目条件和检索到的课程知识。"
    "请显式写出已知条件、求解目标、所用公式、代入过程、单位和结论。"
    "如果信息不足，请明确指出缺少哪些条件，不要编造。"
    "凡是涉及等效电路、电流、输入功率、功率因数、效率、电磁功率、电磁转矩的问题，必须先判断是否需要计入励磁支路/励磁电流/空载支路。"
    "对并励/他励/串励/复励直流电机，必须区分线路电流、励磁电流和电枢电流，不能把电枢电流直接当总电流。"
    "对异步电机等效电路，必须区分定子电流、转子折算电流和励磁支路电流；若忽略励磁支路，必须明确写出近似条件并说明为何本题允许这样做。"
    "如果题目已给出空载电流、励磁参数、励磁回路电阻/电抗或并励支路参数，默认不能无说明地忽略。"
    "普通说明用 Markdown，独立公式用 \\[ ... \\]，行内公式用 \\( ... \\)。"
)

ANALYSIS_PROMPT = (
    "请先整理题意，不要直接给最终答案。"
    "按以下 6 部分输出：\n"
    "1. 题型判断\n"
    "2. 已知条件\n"
    "3. 待求量\n"
    "4. 电机模型/等效电路该如何选取\n"
    "5. 是否必须计入励磁电流/励磁支路，并说明理由\n"
    "6. 候选公式与适用条件"
)

REVIEW_PROMPT = (
    "你现在是解题复核员。请检查解题是否遗漏条件、公式是否适用、计算逻辑是否一致。"
    "尤其检查：是否把电枢电流错当总电流，是否漏掉励磁支路/励磁电流，是否把支路量和总量混用。"
    "返回 JSON，字段固定为 confidence, grounded, issues, corrected_answer。"
    "其中 confidence 为 0 到 100 的整数，grounded 为 true/false，issues 为字符串数组。"
)

FAST_SOLVE_PROMPT = (
    "请直接给出可用于课程学习的解题结果，但先完成隐式自检：\n"
    "A. 题目要求的是总量、支路量还是折算量？\n"
    "B. 是否涉及励磁电流/励磁支路/空载支路？\n"
    "C. 若采用近似，是否会影响本题所求？\n"
    "然后按固定结构输出：\n"
    "1) 已知与待求\n"
    "2) 模型判断与是否需要计入励磁支路\n"
    "3) 公式与条件\n"
    "4) 推导/代入过程\n"
    "5) 结论\n"
    "要求简洁，但不要省略关键物理判断和关键公式。"
)


def normalize_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("text") is not None:
                    parts.append(str(item["text"]))
                elif item.get("content") is not None:
                    parts.append(str(item["content"]))
                else:
                    parts.append(json.dumps(item, ensure_ascii=False))
            else:
                parts.append(str(item))
        return "\n".join([p for p in parts if p]).strip()
    if isinstance(content, dict):
        if content.get("text") is not None:
            return str(content["text"])
        if content.get("content") is not None:
            return str(content["content"])
        return json.dumps(content, ensure_ascii=False)
    return str(content)


def contains_error_marker(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in [
            "error:",
            "调用api时发生错误",
            "图片文字提取失败",
            "failed",
            "exception",
        ]
    )


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def normalize_history_messages(history: Optional[List[Dict[str, Any]]]) -> List[Dict[str, str]]:
    sanitized: List[Dict[str, str]] = []
    for item in history or []:
        role = str(item.get("role", "")).strip().lower()
        if role not in {"user", "assistant"}:
            continue
        content = normalize_content(item.get("content"))
        if not content.strip():
            continue
        sanitized.append({"role": role, "content": content.strip()})
    return sanitized[-10:]


class QwenTextAgent:
    def __init__(self, api_key: str, model: Optional[str] = None):
        dashscope.api_key = api_key
        self.model = model or os.getenv("QWEN_TEXT_MODEL", DEFAULT_TEXT_MODEL)

    def query(
        self,
        text: str,
        history: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
    ) -> str:
        try:
            messages = [{"role": Role.SYSTEM, "content": system_prompt or DEFAULT_SYSTEM_PROMPT}]
            messages.extend(normalize_history_messages(history))
            messages.append({"role": Role.USER, "content": text})
            response = Generation.call(
                model=self.model,
                messages=messages,
                result_format="message",
                temperature=temperature,
            )
            if response.status_code == 200:
                return normalize_content(response.output.choices[0].message.content)
            return f"Error: {response.code} - {response.message}"
        except Exception as exc:
            return f"调用API时发生错误: {exc}"

    def stream_query(
        self,
        text: str,
        history: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
    ) -> Iterator[str]:
        try:
            messages = [{"role": Role.SYSTEM, "content": system_prompt or DEFAULT_SYSTEM_PROMPT}]
            messages.extend(normalize_history_messages(history))
            messages.append({"role": Role.USER, "content": text})
            responses = Generation.call(
                model=self.model,
                messages=messages,
                result_format="message",
                temperature=temperature,
                stream=True,
                incremental_output=True,
            )
            for response in responses:
                if response.status_code != 200:
                    raise RuntimeError(f"{response.code} - {response.message}")
                delta = normalize_content(response.output.choices[0].message.content)
                if delta:
                    yield delta
        except Exception as exc:
            raise RuntimeError(f"调用流式API时发生错误: {exc}") from exc


class QwenVisionAgent:
    def __init__(self, api_key: str, model: Optional[str] = None):
        dashscope.api_key = api_key
        self.model = model or os.getenv("QWEN_VISION_MODEL", DEFAULT_VISION_MODEL)

    def extract_text_from_image(self, image_path: str) -> str:
        try:
            true_path = f"file://{image_path}"
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"image": true_path},
                        {
                            "text": (
                                "请完整识别图片中的题目文字、图中标注、已知条件和公式。"
                                "如果是电机学题目，请尽量保持原题结构。"
                                "只返回识别结果，不要额外解释。"
                            )
                        },
                    ],
                }
            ]
            response = MultiModalConversation.call(
                self.model,
                messages=messages,
                result_format="message",
            )
            if response.status_code == 200:
                return normalize_content(response.output.choices[0].message.content)
            return f"图片文字提取失败: {response.code} - {response.message}"
        except Exception as exc:
            return f"图片文字提取失败: {exc}"


class MotorTheoryWorkflow:
    def __init__(self, api_key: str, knowledge_agent: Optional[Any] = None):
        self.vision_agent = QwenVisionAgent(api_key)
        self.text_agent = QwenTextAgent(api_key)
        self.knowledge_agent = knowledge_agent

    def set_knowledge_agent(self, knowledge_agent: Optional[Any]) -> None:
        self.knowledge_agent = knowledge_agent

    def _get_reference_hits(self, question_text: str, knowledge_agent: Optional[Any], top_k: int) -> List[Dict[str, Any]]:
        agent = knowledge_agent or self.knowledge_agent
        if not agent:
            return []
        return agent.search_similar_questions(question_text, top_k=top_k, similarity_threshold=0.12)

    def _build_reference_context(self, reference_hits: List[Dict[str, Any]], knowledge_agent: Optional[Any]) -> str:
        agent = knowledge_agent or self.knowledge_agent
        if not reference_hits or not agent:
            return "未提供课程知识参考。"
        return agent.build_reference_context(reference_hits, max_items=3)

    def _analyze_problem(
        self,
        question_text: str,
        reference_context: str,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        prompt = (
            f"题目如下：\n{question_text}\n\n"
            f"课程知识参考如下：\n{reference_context}\n\n"
            f"{ANALYSIS_PROMPT}"
        )
        return self.text_agent.query(
            prompt,
            history=history,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            temperature=0.0,
        )

    @staticmethod
    def _build_draft_prompt(question_text: str, analysis: str, reference_context: str) -> str:
        return (
            f"题目：\n{question_text}\n\n"
            f"题意整理：\n{analysis}\n\n"
            f"课程知识参考：\n{reference_context}\n\n"
            "请基于题目和课程知识给出正式解答。请遵守以下要求：\n"
            "1. 先明确题目所求的是总量、支路量还是折算量。\n"
            "2. 先判断是否必须计入励磁电流/励磁支路；如果不计入，必须写出近似前提。\n"
            "3. 对直流并励机，不能把电枢电流直接当线路电流；对异步电机，不能把转子折算电流直接当定子总电流。\n"
            "4. 明确所用公式和公式适用条件。\n"
            "5. 给出推导或代入过程，并保留关键中间量。\n"
            "6. 结论必须带单位，并做一个合理性检查。\n"
            "7. 如果题目条件不足以支撑忽略励磁支路，就不能忽略。"
        )

    def _draft_solution(
        self,
        question_text: str,
        analysis: str,
        reference_context: str,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        prompt = (
            self._build_draft_prompt(
                question_text=question_text,
                analysis=analysis,
                reference_context=reference_context,
            )
        )
        return self.text_agent.query(
            prompt,
            history=history,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            temperature=0.05,
        )

    def _review_solution(
        self,
        question_text: str,
        draft_solution: str,
        reference_context: str,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        prompt = (
            f"题目：\n{question_text}\n\n"
            f"课程知识参考：\n{reference_context}\n\n"
            f"待复核答案：\n{draft_solution}\n\n"
            f"{REVIEW_PROMPT}"
        )
        review_text = self.text_agent.query(
            prompt,
            history=history,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            temperature=0.0,
        )
        payload = extract_json_object(review_text) or {}
        payload.setdefault("confidence", 55)
        payload.setdefault("grounded", bool(reference_context and reference_context != "未提供课程知识参考。"))
        payload.setdefault("issues", [])
        payload.setdefault("corrected_answer", draft_solution)
        payload["raw_review"] = review_text
        return payload

    @staticmethod
    def _build_fast_prompt(question_text: str, reference_context: str) -> str:
        return (
            f"题目：\n{question_text}\n\n"
            f"课程知识参考：\n{reference_context}\n\n"
            f"{FAST_SOLVE_PROMPT}"
        )

    @staticmethod
    def _contains_any(text: str, keywords: List[str]) -> bool:
        lowered = normalize_content(text).lower()
        return any(keyword in lowered for keyword in keywords)

    def _is_excitation_sensitive_question(self, question_text: str) -> bool:
        return self._contains_any(
            question_text,
            [
                "励磁",
                "并励",
                "他励",
                "复励",
                "空载",
                "磁化支路",
                "励磁支路",
                "励磁电流",
                "i_f",
                "i0",
                "i_0",
                "xm",
                "x_m",
                "r0",
                "rc",
                "r_c",
            ],
        )

    def _answer_mentions_excitation(self, answer_text: str) -> bool:
        return self._contains_any(
            answer_text,
            [
                "励磁",
                "磁化支路",
                "励磁支路",
                "空载支路",
                "空载电流",
                "i_f",
                "i0",
                "i_0",
                "xm",
                "x_m",
                "r0",
                "rc",
                "r_c",
            ],
        )

    @staticmethod
    def _answer_explicitly_approximates_excitation(answer_text: str) -> bool:
        normalized = normalize_content(answer_text)
        return any(
            re.search(pattern, normalized, flags=re.IGNORECASE)
            for pattern in [
                r"忽略.{0,6}励磁",
                r"不计.{0,6}励磁",
                r"励磁.{0,10}(可忽略|忽略不计)",
                r"近似.{0,12}(励磁|磁化支路|空载支路)",
            ]
        )

    def _collect_quality_issues(self, question_text: str, solution_text: str) -> List[str]:
        question = normalize_content(question_text).strip()
        solution = normalize_content(solution_text).strip()
        issues: List[str] = []

        if not solution:
            issues.append("答案为空。")
            return issues

        if self._is_excitation_sensitive_question(question):
            mentions_excitation = self._answer_mentions_excitation(solution)
            approximates_excitation = self._answer_explicitly_approximates_excitation(solution)
            if not mentions_excitation and not approximates_excitation:
                issues.append("题目涉及励磁支路/励磁电流，但答案未显式处理。")

        question_has_multi_current_context = self._contains_any(question, ["总电流", "线电流", "输入电流"]) and self._contains_any(
            question,
            ["电枢", "励磁", "支路", "转子", "定子", "折算"],
        )
        if question_has_multi_current_context and not self._contains_any(
            solution,
            [
                "总电流",
                "线电流",
                "电枢电流",
                "励磁电流",
                "定子电流",
                "转子折算电流",
                "i = ia + if",
                "i=ia+if",
                "i_a",
                "i_f",
            ],
        ):
            issues.append("题目存在多种电流定义，但答案未明确区分总量与支路量。")

        if self._contains_any(question, ["效率", "功率因数", "输入功率", "电磁功率", "转矩"]) and not self._contains_any(
            solution,
            ["效率", "功率因数", "输入功率", "电磁功率", "转矩", "p_in", "cos", "eta", "t_e", "te"],
        ):
            issues.append("功率或转矩题建议给出关键公式与单位检查。")

        return issues

    @staticmethod
    def _build_quality_repair_prompt(
        question_text: str,
        reference_context: str,
        original_solution: str,
        issues: List[str],
    ) -> str:
        issue_lines = "\n".join(f"- {item}" for item in issues)
        return (
            "请你作为电机学解题纠偏助手，修正下面这份答案。\n"
            "目标：保留可用步骤，重点修正遗漏与概念混淆，尤其是励磁支路/励磁电流和电流定义区分。\n\n"
            f"题目：\n{question_text}\n\n"
            f"课程知识参考：\n{reference_context}\n\n"
            f"发现的问题：\n{issue_lines}\n\n"
            f"原答案：\n{original_solution}\n\n"
            "输出要求：\n"
            "1) 已知与待求\n"
            "2) 模型与电流定义（总量/支路量/折算量）\n"
            "3) 公式与代入过程\n"
            "4) 结论（带单位）+ 合理性检查\n"
            "5) 若忽略励磁支路，必须说明近似前提及其影响\n"
            "请直接输出修正后的完整答案。"
        )

    def enforce_solution_quality(
        self,
        question_text: str,
        solution_text: str,
        reference_context: str,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        normalized_solution = normalize_content(solution_text).strip()
        issues = self._collect_quality_issues(question_text, normalized_solution)
        if not issues:
            return {
                "solution": normalized_solution,
                "notes": [],
                "auto_repaired": False,
                "triggered_issues": [],
                "remaining_issues": [],
            }

        repair_prompt = self._build_quality_repair_prompt(
            question_text=question_text,
            reference_context=reference_context,
            original_solution=normalized_solution,
            issues=issues,
        )
        repaired_solution = self.text_agent.query(
            repair_prompt,
            history=history,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            temperature=0.0,
        )
        if contains_error_marker(repaired_solution):
            return {
                "solution": normalized_solution,
                "notes": [f"自动复核已触发，但纠偏调用失败：{issues[0]}"],
                "auto_repaired": False,
                "triggered_issues": issues,
                "remaining_issues": issues,
            }

        repaired_text = normalize_content(repaired_solution).strip() or normalized_solution
        remaining_issues = self._collect_quality_issues(question_text, repaired_text)
        if not remaining_issues:
            quality_note = "已自动复核并补强关键电流与励磁支路判断。"
        else:
            quality_note = "已自动复核并尝试纠偏，请重点核对电流定义与励磁支路处理。"

        return {
            "solution": repaired_text,
            "notes": [quality_note],
            "auto_repaired": repaired_text != normalized_solution,
            "triggered_issues": issues,
            "remaining_issues": remaining_issues,
        }

    def _solve_single_pass(
        self,
        question_text: str,
        reference_context: str,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        prompt = (
            self._build_fast_prompt(
                question_text=question_text,
                reference_context=reference_context,
            )
        )
        return self.text_agent.query(
            prompt,
            history=history,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            temperature=0.05,
        )

    def extract_question_from_image(self, image_path: str) -> str:
        return self.vision_agent.extract_text_from_image(image_path)

    def prepare_chat_solution(
        self,
        question_text: str,
        history: Optional[List[Dict[str, Any]]] = None,
        knowledge_agent: Optional[Any] = None,
        top_k: int = 3,
        solve_mode: str = "standard",
    ) -> Dict[str, Any]:
        normalized_question = normalize_content(question_text)
        sanitized_history = normalize_history_messages(history)
        reference_hits = self._get_reference_hits(normalized_question, knowledge_agent, top_k=top_k)
        reference_context = self._build_reference_context(reference_hits, knowledge_agent)
        selected_mode = (solve_mode or os.getenv("SOLVE_MODE", "standard")).strip().lower()

        analysis = ""
        if selected_mode == "standard":
            analysis = self._analyze_problem(
                normalized_question,
                reference_context,
                history=sanitized_history,
            )
            prompt = self._build_draft_prompt(
                question_text=normalized_question,
                analysis=analysis,
                reference_context=reference_context,
            )
        else:
            prompt = self._build_fast_prompt(
                question_text=normalized_question,
                reference_context=reference_context,
            )

        return {
            "question_text": normalized_question,
            "history": sanitized_history,
            "reference_hits": reference_hits,
            "reference_context": reference_context,
            "analysis": analysis,
            "prompt": prompt,
            "solve_mode": selected_mode,
        }

    def stream_prepared_solution(self, prepared: Dict[str, Any]) -> Iterator[str]:
        return self.text_agent.stream_query(
            prepared["prompt"],
            history=prepared.get("history"),
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            temperature=0.05,
        )

    @staticmethod
    def build_result_from_prepared(
        prepared: Dict[str, Any],
        solution: str,
        *,
        display_question: Optional[str] = None,
        image_path: Optional[str] = None,
        quality_notes: Optional[List[str]] = None,
        auto_repaired: bool = False,
    ) -> Dict[str, Any]:
        reference_hits = prepared.get("reference_hits") or []
        solve_mode = str(prepared.get("solve_mode") or "standard")
        confidence = 82 if solve_mode == "standard" else 70
        analysis = prepared.get("analysis") or ""
        base_review_note = (
            "当前为流式对话模式：已使用强化提示词和上下文，但未执行二次 JSON 复核链路。"
            if solve_mode == "standard"
            else "当前为快速流式模式：优先响应速度，建议对关键题再做一次标准核对。"
        )
        review_note_lines = [base_review_note]
        review_note_lines.extend(str(item).strip() for item in (quality_notes or []) if str(item).strip())
        review_notes = "\n".join(review_note_lines)
        return SolveResult(
            success=True,
            extracted_text=display_question or prepared.get("question_text") or "",
            solution=normalize_content(solution),
            image_path=image_path,
            error=None,
            analysis=analysis or None,
            review_notes=review_notes,
            confidence=confidence if reference_hits else max(confidence - 10, 60),
            knowledge_hits=reference_hits,
            metadata={
                "grounded": bool(reference_hits),
                "reference_count": len(reference_hits),
                "solve_mode": solve_mode,
                "response_mode": "stream",
                "auto_repaired": bool(auto_repaired),
            },
        ).to_dict()

    def solve_from_text(
        self,
        question_text: str,
        history: Optional[List[Dict[str, Any]]] = None,
        knowledge_agent: Optional[Any] = None,
        top_k: int = 3,
        solve_mode: str = "fast",
    ) -> Dict[str, Any]:
        normalized_question = normalize_content(question_text)
        reference_hits = self._get_reference_hits(normalized_question, knowledge_agent, top_k=top_k)
        reference_context = self._build_reference_context(reference_hits, knowledge_agent)
        sanitized_history = normalize_history_messages(history)

        selected_mode = (solve_mode or os.getenv("SOLVE_MODE", "fast")).strip().lower()
        if selected_mode != "standard":
            quick_solution = self._solve_single_pass(
                normalized_question,
                reference_context,
                history=sanitized_history,
            )
            if contains_error_marker(quick_solution):
                return SolveResult(
                    success=False,
                    extracted_text=normalized_question,
                    solution="",
                    image_path=None,
                    error=quick_solution,
                ).to_dict()
            quality = self.enforce_solution_quality(
                normalized_question,
                quick_solution,
                reference_context,
                history=sanitized_history,
            )
            final_quick_solution = quality.get("solution") or quick_solution
            quick_notes = [str(item).strip() for item in (quality.get("notes") or []) if str(item).strip()]
            quick_confidence = 80 if reference_hits else 65
            review_note_lines = ["若用于正式作业提交，建议切换“标准模式”再次核对。"]
            review_note_lines.extend(quick_notes)
            return SolveResult(
                success=True,
                extracted_text=normalized_question,
                solution=final_quick_solution,
                image_path=None,
                error=None,
                analysis="快速模式：已跳过分析与复核链路，以降低延迟。",
                review_notes="\n".join(review_note_lines),
                confidence=quick_confidence,
                knowledge_hits=reference_hits,
                metadata={
                    "grounded": bool(reference_hits),
                    "reference_count": len(reference_hits),
                    "solve_mode": "fast",
                    "auto_repaired": bool(quality.get("auto_repaired")),
                    "quality_remaining_issues": quality.get("remaining_issues", []),
                },
            ).to_dict()

        analysis = self._analyze_problem(
            normalized_question,
            reference_context,
            history=sanitized_history,
        )
        if contains_error_marker(analysis):
            return SolveResult(
                success=False,
                extracted_text=normalized_question,
                solution="",
                image_path=None,
                error=analysis,
            ).to_dict()

        draft_solution = self._draft_solution(
            normalized_question,
            analysis,
            reference_context,
            history=sanitized_history,
        )
        if contains_error_marker(draft_solution):
            return SolveResult(
                success=False,
                extracted_text=normalized_question,
                solution="",
                image_path=None,
                error=draft_solution,
                analysis=analysis,
            ).to_dict()

        review = self._review_solution(
            normalized_question,
            draft_solution,
            reference_context,
            history=sanitized_history,
        )
        final_solution = normalize_content(review.get("corrected_answer") or draft_solution)
        quality = self.enforce_solution_quality(
            normalized_question,
            final_solution,
            reference_context,
            history=sanitized_history,
        )
        final_solution = quality.get("solution") or final_solution
        confidence = int(review.get("confidence", 55))
        review_issues = review.get("issues", [])
        quality_notes = [str(item).strip() for item in (quality.get("notes") or []) if str(item).strip()]
        review_note_lines: List[str] = []
        review_note_seen = set()
        for item in [*review_issues, *quality_notes]:
            text = str(item).strip()
            if not text or text in review_note_seen:
                continue
            review_note_seen.add(text)
            review_note_lines.append(text)

        return SolveResult(
            success=True,
            extracted_text=normalized_question,
            solution=final_solution,
            image_path=None,
            error=None,
            analysis=analysis,
            review_notes="\n".join(review_note_lines),
            confidence=confidence,
            knowledge_hits=reference_hits,
            metadata={
                "grounded": bool(review.get("grounded", False)),
                "reference_count": len(reference_hits),
                "raw_review": review.get("raw_review", ""),
                "solve_mode": "standard",
                "auto_repaired": bool(quality.get("auto_repaired")),
                "quality_remaining_issues": quality.get("remaining_issues", []),
            },
        ).to_dict()

    def solve_motor_problem(
        self,
        image_path: str,
        history: Optional[List[Dict[str, Any]]] = None,
        knowledge_agent: Optional[Any] = None,
        top_k: int = 3,
        solve_mode: str = "fast",
    ) -> Dict[str, Any]:
        extracted_text = self.extract_question_from_image(image_path)
        if contains_error_marker(extracted_text):
            return SolveResult(
                success=False,
                extracted_text=None,
                solution="",
                image_path=image_path,
                error=extracted_text,
            ).to_dict()

        result = self.solve_from_text(
            extracted_text,
            history=history,
            knowledge_agent=knowledge_agent,
            top_k=top_k,
            solve_mode=solve_mode,
        )
        result["image_path"] = image_path
        return result
