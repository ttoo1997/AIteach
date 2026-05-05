import json
import os
import re
from datetime import datetime
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

import dashscope
from dashscope import Generation

from app_config import DEFAULT_TEXT_MODEL, DEFAULT_WRONGBOOK_REASONING_MODEL
from runtime_env import clear_invalid_proxy_env


clear_invalid_proxy_env()


def _safe_excerpt(value: Any, limit: int = 180) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _infer_question_type(text: str) -> str:
    lower = text.lower()
    if any(token in text for token in ("推导", "证明", "论证")):
        return "推导分析"
    if any(token in text for token in ("概念", "定义", "区别", "原理")):
        return "概念辨析"
    if any(token in text for token in ("仿真", "曲线", "扫描", "比较")):
        return "仿真分析"
    if any(token in lower for token in ("calculate", "compute", "torque", "slip")):
        return "计算应用"
    if any(token in text for token in ("计算", "求", "转矩", "滑差", "电流", "功率", "转速")):
        return "计算应用"
    return "综合题"


def _infer_error_tag(reason_text: str) -> str:
    lower = reason_text.lower()
    if any(token in reason_text for token in ("审题", "漏看", "看错", "条件")):
        return "审题遗漏"
    if any(token in reason_text for token in ("公式", "推导", "模型")):
        return "公式/模型选择"
    if any(token in reason_text for token in ("单位", "量纲", "换算")):
        return "单位换算"
    if any(token in reason_text for token in ("计算", "代入", "符号", "小数")):
        return "计算细节"
    if any(token in reason_text for token in ("概念", "理解", "记忆", "混淆")):
        return "概念理解"
    if any(token in lower for token in ("concept", "formula", "unit", "calculate")):
        return "基础理解"
    return "其他"


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _top_distribution(values: List[str], top_k: int = 6) -> List[Dict[str, Any]]:
    bucket: Dict[str, int] = {}
    for value in values:
        key = str(value or "其他")
        bucket[key] = bucket.get(key, 0) + 1
    pairs = sorted(bucket.items(), key=lambda item: item[1], reverse=True)
    return [{"name": name, "count": count} for name, count in pairs[:top_k]]


class WrongbookAIService:
    def __init__(self, api_key: str, model: Optional[str] = None):
        dashscope.api_key = api_key
        self.model = (
            model
            or os.getenv("QWEN_WRONGBOOK_MODEL")
            or os.getenv("QWEN_REASONING_MODEL")
            or os.getenv("QWEN_QA_MODEL")
            or os.getenv("QWEN_TEXT_MODEL")
            or DEFAULT_WRONGBOOK_REASONING_MODEL
            or DEFAULT_TEXT_MODEL
        )
        self._lock = Lock()
        self._practice_cache: Dict[str, Dict[str, Any]] = {}

    def _call_generation(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> Tuple[Optional[str], Optional[str]]:
        try:
            response = Generation.call(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                result_format="message",
                temperature=temperature,
            )
            if response.status_code != 200:
                return None, f"{response.code} - {response.message}"
            content = response.output.choices[0].message.content
            if isinstance(content, str):
                return content.strip(), None
            return str(content).strip(), None
        except Exception as exc:
            return None, str(exc)

    @staticmethod
    def _records_for_prompt(records: List[Dict[str, Any]], limit: int = 60) -> List[Dict[str, Any]]:
        sliced = records[: max(limit, 1)]
        normalized: List[Dict[str, Any]] = []
        for row in sliced:
            question_text = str(row.get("question_text", "")).strip()
            error_reason = str(row.get("error_reason", "")).strip()
            normalized.append(
                {
                    "id": row.get("id"),
                    "question_excerpt": _safe_excerpt(question_text, 200),
                    "error_reason_excerpt": _safe_excerpt(error_reason, 160),
                    "question_type": _infer_question_type(question_text),
                    "error_tag": _infer_error_tag(error_reason),
                    "created_at": row.get("created_at", ""),
                }
            )
        return normalized

    @staticmethod
    def _normalize_list(value: Any, fallback: Optional[List[str]] = None) -> List[str]:
        fallback = fallback or []
        if not isinstance(value, list):
            return fallback
        normalized = [str(item).strip() for item in value if str(item).strip()]
        return normalized or fallback

    def _fallback_analysis(
        self,
        *,
        record_count: int,
        type_distribution: List[Dict[str, Any]],
        error_distribution: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        top_type = type_distribution[0]["name"] if type_distribution else "综合题"
        top_error = error_distribution[0]["name"] if error_distribution else "概念理解"
        return {
            "mastery_level": "中等偏弱",
            "overview": f"当前累计 {record_count} 条错题，主要集中在 {top_type}，高频失分点是 {top_error}。",
            "strengths": ["能够持续记录错题，学习流程是完整的。"],
            "weaknesses": [f"{top_error} 类错误重复出现，需要专项修复。"],
            "recommendations": [
                "先用 15 分钟复盘今天新增错题，归纳 1 条固定检查清单。",
                "做题时先写“已知-所求-公式”三行，再开始代入。",
                "每做完一道题，最后单独检查单位和数量级。",
            ],
            "next_7_day_plan": [
                "Day1-2：集中训练同类型基础题，纠正公式选择和审题习惯。",
                "Day3-5：混合训练两类题型，强化迁移能力。",
                "Day6-7：做限时小测并复盘错因是否下降。",
            ],
            "risk_topics": [top_type, top_error],
            "confidence": 0.55,
        }

    @staticmethod
    def _build_analysis_text(
        *,
        record_count: int,
        mastery_level: str,
        overview: str,
        type_distribution: List[Dict[str, Any]],
        error_distribution: List[Dict[str, Any]],
        strengths: List[str],
        weaknesses: List[str],
        recommendations: List[str],
        plan: List[str],
    ) -> str:
        lines: List[str] = []
        lines.append(f"已分析错题：{record_count} 条")
        lines.append(f"总体掌握评估：{mastery_level}")
        lines.append("")
        lines.append("一、学习画像")
        lines.append(overview)
        lines.append("")
        lines.append("二、题型分布")
        for item in type_distribution:
            lines.append(f"- {item['name']}：{item['count']} 条")
        lines.append("")
        lines.append("三、高频错因")
        for item in error_distribution:
            lines.append(f"- {item['name']}：{item['count']} 次")
        lines.append("")
        lines.append("四、优势与短板")
        for item in strengths:
            lines.append(f"- 优势：{item}")
        for item in weaknesses:
            lines.append(f"- 短板：{item}")
        lines.append("")
        lines.append("五、改进建议")
        for item in recommendations:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("六、7天练习节奏")
        for item in plan:
            lines.append(f"- {item}")
        return "\n".join(lines).strip()

    def analyze_wrongbook(self, records: List[Dict[str, Any]], record_limit: int = 80) -> Dict[str, Any]:
        prompt_records = self._records_for_prompt(records, limit=record_limit)
        question_types = [row["question_type"] for row in prompt_records]
        error_tags = [row["error_tag"] for row in prompt_records]
        type_distribution = _top_distribution(question_types)
        error_distribution = _top_distribution(error_tags)
        record_count = len(prompt_records)

        if record_count == 0:
            raise ValueError("错题本为空，暂时无法分析。")

        system_prompt = (
            "你是电机学教研助教。请基于错题记录评估学生掌握情况，并输出严格 JSON。"
            "JSON 字段固定为：mastery_level, overview, strengths, weaknesses, recommendations, "
            "next_7_day_plan, risk_topics, confidence。"
            "其中 strengths/weaknesses/recommendations/next_7_day_plan/risk_topics 必须是字符串数组。"
            "mastery_level 用“高/中高/中等/中等偏弱/偏弱”之一。confidence 为 0~1 小数。"
        )
        user_prompt = (
            "以下是错题本抽样（按时间倒序）：\n"
            f"{json.dumps(prompt_records, ensure_ascii=False)}\n\n"
            "题型统计：\n"
            f"{json.dumps(type_distribution, ensure_ascii=False)}\n\n"
            "错因统计：\n"
            f"{json.dumps(error_distribution, ensure_ascii=False)}"
        )
        raw_text, error = self._call_generation(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.1)
        if error:
            analysis = self._fallback_analysis(
                record_count=record_count,
                type_distribution=type_distribution,
                error_distribution=error_distribution,
            )
            analysis["overview"] = f"{analysis['overview']}（AI 分析接口异常，已使用规则兜底）"
        else:
            payload = _extract_json_object(raw_text or "") or {}
            analysis = {
                "mastery_level": str(payload.get("mastery_level", "中等偏弱")).strip() or "中等偏弱",
                "overview": str(payload.get("overview", "")).strip()
                or f"当前累计 {record_count} 条错题，建议围绕高频错因做针对训练。",
                "strengths": self._normalize_list(payload.get("strengths"), ["有持续复盘习惯。"]),
                "weaknesses": self._normalize_list(payload.get("weaknesses"), ["存在重复错因。"]),
                "recommendations": self._normalize_list(
                    payload.get("recommendations"),
                    ["建立固定解题模板：已知-所求-公式-代入-校验。"],
                ),
                "next_7_day_plan": self._normalize_list(
                    payload.get("next_7_day_plan"),
                    ["先专项、后混合、再限时复盘。"],
                ),
                "risk_topics": self._normalize_list(payload.get("risk_topics"), [type_distribution[0]["name"]]),
                "confidence": float(payload.get("confidence", 0.6)),
            }

        analysis_text = self._build_analysis_text(
            record_count=record_count,
            mastery_level=analysis["mastery_level"],
            overview=analysis["overview"],
            type_distribution=type_distribution,
            error_distribution=error_distribution,
            strengths=analysis["strengths"],
            weaknesses=analysis["weaknesses"],
            recommendations=analysis["recommendations"],
            plan=analysis["next_7_day_plan"],
        )
        return {
            "ok": True,
            "generated_at": datetime.now().isoformat(),
            "model_used": self.model,
            "record_count": record_count,
            "type_distribution": type_distribution,
            "error_distribution": error_distribution,
            "analysis": analysis,
            "analysis_text": analysis_text,
        }

    @staticmethod
    def _fallback_practice(analysis: Dict[str, Any]) -> Dict[str, Any]:
        risk_topics = analysis.get("analysis", {}).get("risk_topics") or ["计算应用"]
        topic = str(risk_topics[0])
        question = (
            "一台三相异步电动机在某工况下已知："
            "转子电阻 R2=0.45，转子漏抗 X2=1.1，感应电势 E2=220V，滑差 s=0.08。"
            "请计算相对电磁转矩并说明如果滑差继续增大，转矩会如何变化。"
        )
        return {
            "title": f"针对训练：{topic}",
            "difficulty": "中等",
            "knowledge_points": ["转矩-滑差关系", "参数代入计算", "趋势判断"],
            "hint": "先写出转矩公式，再代入 R2/X2/s 的比值关系。",
            "question": question,
            "answer_outline": "按公式计算分子与分母，得到相对转矩，再结合曲线判断变化趋势。",
            "solution": "使用 T ∝ sE2^2R2 / (R2^2 + (sX2)^2) 计算即可，s 从较小值上升时转矩先增后减。",
        }

    def generate_practice_question(
        self,
        records: List[Dict[str, Any]],
        *,
        analysis_payload: Optional[Dict[str, Any]] = None,
        focus: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not records:
            raise ValueError("错题本为空，无法生成练习题。")

        if analysis_payload is None:
            first_row = records[0] if records else {}
            fallback_weakness = focus or _infer_error_tag(str(first_row.get("error_reason", "")))
            fallback_risk = _infer_question_type(str(first_row.get("question_text", "")))
            analysis_data = {
                "analysis": {
                    "weaknesses": [fallback_weakness],
                    "risk_topics": [fallback_risk],
                }
            }
        else:
            analysis_data = analysis_payload
        sampled = self._records_for_prompt(records, limit=20)
        weakness_focus = focus or "、".join((analysis_data.get("analysis", {}).get("weaknesses") or [])[:2])

        system_prompt = (
            "你是电机学训练题生成助手。请返回严格 JSON。字段固定为："
            "title, difficulty, knowledge_points, hint, question, answer_outline, solution。"
            "difficulty 只能是 基础/中等/进阶。knowledge_points 必须是字符串数组。"
            "题目要可计算或可推理，长度控制在 120~260 字。"
        )
        user_prompt = (
            f"学习薄弱点：{weakness_focus or '请按高频错因出题'}\n\n"
            "最近错题样本：\n"
            f"{json.dumps(sampled, ensure_ascii=False)}\n\n"
            "请生成 1 道可练习题，尽量贴合错因。"
        )
        raw_text, error = self._call_generation(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.35)
        if error:
            practice = self._fallback_practice(analysis_data)
            practice["hint"] = f"{practice['hint']}（AI 出题接口异常，已使用兜底题）"
        else:
            payload = _extract_json_object(raw_text or "") or {}
            fallback = self._fallback_practice(analysis_data)
            practice = {
                "title": str(payload.get("title", fallback["title"])).strip() or fallback["title"],
                "difficulty": str(payload.get("difficulty", fallback["difficulty"])).strip() or fallback["difficulty"],
                "knowledge_points": self._normalize_list(payload.get("knowledge_points"), fallback["knowledge_points"]),
                "hint": str(payload.get("hint", fallback["hint"])).strip() or fallback["hint"],
                "question": str(payload.get("question", fallback["question"])).strip() or fallback["question"],
                "answer_outline": str(payload.get("answer_outline", fallback["answer_outline"])).strip()
                or fallback["answer_outline"],
                "solution": str(payload.get("solution", fallback["solution"])).strip() or fallback["solution"],
            }

        question_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
        with self._lock:
            self._practice_cache[question_id] = {
                "created_at": datetime.now().isoformat(),
                "question": practice["question"],
                "hint": practice["hint"],
                "knowledge_points": practice["knowledge_points"],
                "difficulty": practice["difficulty"],
                "answer_outline": practice["answer_outline"],
                "solution": practice["solution"],
                "title": practice["title"],
            }
            while len(self._practice_cache) > 64:
                oldest_key = next(iter(self._practice_cache))
                self._practice_cache.pop(oldest_key, None)

        return {
            "ok": True,
            "model_used": self.model,
            "question_id": question_id,
            "title": practice["title"],
            "difficulty": practice["difficulty"],
            "knowledge_points": practice["knowledge_points"],
            "hint": practice["hint"],
            "question": practice["question"],
        }

    def explain_practice_question(self, question_id: str, user_answer: str = "") -> Optional[Dict[str, Any]]:
        with self._lock:
            snapshot = self._practice_cache.get(question_id)
        if not snapshot:
            return None

        system_prompt = (
            "你是电机学讲题老师。请根据题目和标准答案给出可读性高的讲解。"
            "要求：先点评学生作答，再给步骤化解析，最后给 2 条举一反三建议。"
        )
        user_prompt = (
            f"题目：\n{snapshot['question']}\n\n"
            f"参考思路：\n{snapshot['answer_outline']}\n\n"
            f"参考完整解析：\n{snapshot['solution']}\n\n"
            f"学生作答（可为空）：\n{user_answer.strip() or '（未提交作答）'}"
        )
        raw_text, error = self._call_generation(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.2)
        explanation = raw_text if raw_text and not error else snapshot["solution"]
        return {
            "ok": True,
            "question_id": question_id,
            "model_used": self.model,
            "explanation": explanation,
        }
