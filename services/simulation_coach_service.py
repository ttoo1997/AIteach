import json
import os
from typing import Any, Dict, List, Optional, Tuple

import dashscope
from dashscope import Generation

from app_config import DEFAULT_SIM_COACH_MODEL, DEFAULT_TEXT_MODEL
from runtime_env import clear_invalid_proxy_env
from services.fixed_simulation_lab_service import FIXED_SIM_LAB_SERVICE


clear_invalid_proxy_env()


def _normalize_history(history: List[Dict[str, Any]], limit: int = 8) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for item in history:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if role not in {"user", "assistant"} or not content:
            continue
        rows.append({"role": role, "content": content})
    return rows[-limit:]


class SimulationCoachService:
    def __init__(self, api_key: str, model: Optional[str] = None):
        dashscope.api_key = api_key
        candidates = [
            model,
            os.getenv("QWEN_SIM_COACH_MODEL"),
            os.getenv("QWEN_REASONING_MODEL"),
            os.getenv("QWEN_QA_MODEL"),
            DEFAULT_SIM_COACH_MODEL,
            "qwen3-max",
            DEFAULT_TEXT_MODEL,
        ]
        self.model_candidates: List[str] = []
        for item in candidates:
            value = str(item or "").strip()
            if value and value not in self.model_candidates:
                self.model_candidates.append(value)

    def _call_generation(self, messages: List[Dict[str, str]]) -> Tuple[Optional[str], Optional[str], str]:
        errors: List[str] = []
        for model_name in self.model_candidates:
            try:
                response = Generation.call(
                    model=model_name,
                    messages=messages,
                    result_format="message",
                    temperature=0.2,
                )
                if response.status_code != 200:
                    errors.append(f"{model_name}: {response.code} - {response.message}")
                    continue
                content = response.output.choices[0].message.content
                if isinstance(content, list):
                    merged = "".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
                    return merged.strip(), None, model_name
                return str(content).strip(), None, model_name
            except Exception as exc:
                errors.append(f"{model_name}: {exc}")
        fallback_model = self.model_candidates[0] if self.model_candidates else "unknown"
        return None, " | ".join(errors[-3:]) if errors else "unknown error", fallback_model

    @staticmethod
    def _build_system_prompt() -> str:
        return (
            "你是 AITeach 的电机学仿真实验助教，只负责以下四类固定实验："
            "直流电机 T-n、变压器电压调整率与效率、异步电机 T-s、同步电机 P-δ。"
            "回答要求："
            "1) 先给结论，再给步骤；2) 语言面向初学者，避免空话；"
            "3) 涉及公式时写出变量含义与单位；4) 严禁编造不存在的实验与参数；"
            "5) 若用户目标不清晰，先追问一个关键澄清问题；"
            "6) 结构尽量使用短段落或短条目，便于直接照着做。"
        )

    @staticmethod
    def _build_user_prompt(lab: Dict[str, Any], message: str, history: List[Dict[str, str]]) -> str:
        lab_snapshot = {
            "id": lab.get("id"),
            "title": lab.get("title"),
            "machine_type": lab.get("machine_type"),
            "description": lab.get("description"),
            "focus_points": lab.get("focus_points", []),
            "tutorial_steps": lab.get("tutorial_steps", []),
            "parameters": [
                {
                    "key": row.get("key"),
                    "label": row.get("label"),
                    "default": row.get("default"),
                    "min": row.get("min"),
                    "max": row.get("max"),
                }
                for row in (lab.get("parameters") or [])
            ],
        }
        return (
            "当前实验信息：\n"
            f"{json.dumps(lab_snapshot, ensure_ascii=False)}\n\n"
            "最近对话（按时间顺序）：\n"
            f"{json.dumps(history, ensure_ascii=False)}\n\n"
            "用户本轮问题：\n"
            f"{message}\n\n"
            "请按“结论 -> 操作步骤 -> 注意事项”的顺序回答。"
        )

    @staticmethod
    def _fallback_answer(lab: Dict[str, Any]) -> str:
        steps = "\n".join(f"- {item}" for item in (lab.get("tutorial_steps") or [])[:3]) or "- 先运行默认参数观察结果。"
        points = "、".join(str(item) for item in (lab.get("focus_points") or [])[:4]) or "关键指标变化"
        return (
            f"当前先做「{lab.get('title', '电机实验')}」。\n\n"
            f"建议步骤：\n{steps}\n\n"
            f"重点观察：{points}。\n"
            "如果你把本次参数和结果贴给我，我可以继续帮你写出规范结论。"
        )

    def chat(self, *, lab_id: str, message: str, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        clean_message = str(message or "").strip()
        if not clean_message:
            raise ValueError("问题不能为空。")
        lab = FIXED_SIM_LAB_SERVICE.get_lab(lab_id)
        clean_history = _normalize_history(history)
        messages = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user", "content": self._build_user_prompt(lab, clean_message, clean_history)},
        ]
        answer, error, model_used = self._call_generation(messages)
        if error:
            return {
                "ok": True,
                "lab_id": lab.get("id"),
                "answer": self._fallback_answer(lab),
                "model_used": model_used,
                "degraded": True,
                "error": error,
            }
        return {
            "ok": True,
            "lab_id": lab.get("id"),
            "answer": answer or self._fallback_answer(lab),
            "model_used": model_used,
            "degraded": False,
        }
