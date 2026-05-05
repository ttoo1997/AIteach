import json
import os
import re
from typing import Any, Dict, List, Optional

import dashscope
from dashscope import Generation

from app_config import DEFAULT_SIM_DESIGN_MODEL


ALLOWED_SCENARIOS = {
    "torque_curve",
    "parameter_sweep",
    "operating_point_compare",
    "startup_assessment",
}


BEGINNER_TEMPLATE_LIBRARY: List[Dict[str, Any]] = [
    {
        "id": "intro_torque_curve",
        "title": "实验 1：转矩-滑差基础体验",
        "subtitle": "先看曲线形状，再记住峰值点",
        "scenario": "torque_curve",
        "difficulty": "入门",
        "duration_min": 8,
        "goal": "直观看到转矩随滑差先升后降，并识别最大转矩点与启动点。",
        "focus": ["滑差 s", "最大转矩", "启动转矩"],
        "defaults": {
            "r2": 0.5,
            "x2": 1.2,
            "e2": 220.0,
            "s_min": 0.01,
            "s_max": 1.0,
            "n_points": 220,
        },
        "observe_points": [
            "最大转矩对应的滑差大约在哪个区间。",
            "启动点 (s=1) 的转矩与峰值相比高还是低。",
            "小滑差区域为何转矩变化更敏感。",
        ],
        "recommended_steps": [
            "先用默认参数运行一次并记录 max_slip、max_torque、start_torque。",
            "将 R2 从 0.5 改到 0.8，再运行并对比三项指标。",
            "用自己的话总结“滑差变大时转矩为什么不是一直增大”。",
        ],
        "student_task": "记录两组参数下的 max_torque 与 start_torque，并写 2 句趋势结论。",
    },
    {
        "id": "r2_sweep_starter",
        "title": "实验 2：R2 参数扫描",
        "subtitle": "理解转子电阻对起动与峰值位置的影响",
        "scenario": "parameter_sweep",
        "difficulty": "入门",
        "duration_min": 12,
        "goal": "观察 R2 增大时最大转矩与对应滑差的变化，形成“参数-现象”映射。",
        "focus": ["转子电阻 R2", "max_torque", "max_slip"],
        "defaults": {
            "r2": 0.5,
            "x2": 1.2,
            "e2": 220.0,
            "s_min": 0.01,
            "s_max": 1.0,
            "n_points": 220,
            "sweep_variable": "r2",
            "sweep_start": 0.2,
            "sweep_stop": 1.4,
            "sweep_points": 6,
        },
        "observe_points": [
            "R2 变化时 max_torque 是否显著变化。",
            "R2 增大时 max_slip 往哪个方向移动。",
            "启动转矩在扫描中的变化趋势。",
        ],
        "recommended_steps": [
            "先按默认扫描范围运行并记录每个采样点结果。",
            "把扫描点数改成 8，观察趋势是否更平滑。",
            "尝试把 X2 改小到 1.0，重新扫描并比较。",
        ],
        "student_task": "写出“R2 对 max_slip 的影响方向”并给出实验数据支撑。",
    },
    {
        "id": "operating_points_starter",
        "title": "实验 3：典型工况点对比",
        "subtitle": "把连续曲线变成可讨论的离散工况",
        "scenario": "operating_point_compare",
        "difficulty": "入门",
        "duration_min": 10,
        "goal": "通过少量典型滑差点建立“运行工况”直觉。",
        "focus": ["典型滑差点", "工况转矩", "区间比较"],
        "defaults": {
            "r2": 0.5,
            "x2": 1.2,
            "e2": 220.0,
            "s_min": 0.01,
            "s_max": 1.0,
            "n_points": 220,
            "slip_points": "0.02,0.05,0.1,0.2,0.4,1.0",
        },
        "observe_points": [
            "低滑差与中滑差工况的转矩差异。",
            "从 0.2 到 0.4 的变化是否仍然上升。",
            "启动点与正常运行点在转矩上的位置关系。",
        ],
        "recommended_steps": [
            "先看默认 6 个工况点，再增加一个 0.7 进行比较。",
            "把 R2 提高到 0.8，观察各点转矩变化幅度。",
            "总结“哪些滑差区间更适合稳态运行讨论”。",
        ],
        "student_task": "挑选 3 个工况点，用一句话描述它们的转矩相对关系。",
    },
    {
        "id": "startup_assessment_starter",
        "title": "实验 4：启动能力评估",
        "subtitle": "把结果转成“强/中/弱”可解释等级",
        "scenario": "startup_assessment",
        "difficulty": "入门",
        "duration_min": 8,
        "goal": "学会用 startup_ratio 快速判断启动能力，并给出改进方向。",
        "focus": ["startup_ratio", "启动等级", "参数优化方向"],
        "defaults": {
            "r2": 0.5,
            "x2": 1.2,
            "e2": 220.0,
            "s_min": 0.01,
            "s_max": 1.0,
            "n_points": 220,
        },
        "observe_points": [
            "当前 startup_ratio 落在哪个等级区间。",
            "R2 与 X2 哪个变化对等级影响更明显。",
            "建议文字是否与实验现象一致。",
        ],
        "recommended_steps": [
            "先运行默认参数，记录评估等级。",
            "把 R2 提高到 0.8，再运行并对比等级变化。",
            "把 X2 调低到 1.0，观察建议是否变化。",
        ],
        "student_task": "给出一组你认为“启动能力更强”的参数并说明理由。",
    },
]


def _as_float(value: Any, default: float, minimum: Optional[float] = None, maximum: Optional[float] = None) -> float:
    try:
        parsed = float(value)
    except Exception:
        parsed = default
    if minimum is not None:
        parsed = max(parsed, minimum)
    if maximum is not None:
        parsed = min(parsed, maximum)
    return float(parsed)


def _as_int(value: Any, default: int, minimum: Optional[int] = None, maximum: Optional[int] = None) -> int:
    try:
        parsed = int(float(value))
    except Exception:
        parsed = default
    if minimum is not None:
        parsed = max(parsed, minimum)
    if maximum is not None:
        parsed = min(parsed, maximum)
    return int(parsed)


def _extract_json_block(text: str) -> Optional[Dict[str, Any]]:
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


class SimulationStudioService:
    def __init__(self) -> None:
        self.api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
        self.model = (
            os.getenv("QWEN_SIM_DESIGN_MODEL")
            or os.getenv("QWEN_CODER_MODEL")
            or DEFAULT_SIM_DESIGN_MODEL
        )
        if self.api_key:
            dashscope.api_key = self.api_key

    @staticmethod
    def _base_controls() -> List[Dict[str, Any]]:
        return [
            {"key": "r2", "label": "R2", "type": "number", "default": 0.5, "min": 0.05, "max": 3.0, "step": 0.01},
            {"key": "x2", "label": "X2", "type": "number", "default": 1.2, "min": 0.05, "max": 6.0, "step": 0.01},
            {"key": "e2", "label": "E2", "type": "number", "default": 220.0, "min": 20.0, "max": 1200.0, "step": 1.0},
            {"key": "s_min", "label": "s_min", "type": "number", "default": 0.01, "min": 0.001, "max": 0.8, "step": 0.001},
            {"key": "s_max", "label": "s_max", "type": "number", "default": 1.0, "min": 0.05, "max": 1.0, "step": 0.01},
            {"key": "n_points", "label": "n_points", "type": "number", "default": 200, "min": 40, "max": 2000, "step": 1},
        ]

    def _build_spec(self, scenario: str, title: str, description: str) -> Dict[str, Any]:
        controls = self._base_controls()
        if scenario == "parameter_sweep":
            controls.extend(
                [
                    {
                        "key": "sweep_variable",
                        "label": "扫描变量",
                        "type": "select",
                        "default": "r2",
                        "options": [
                            {"label": "R2", "value": "r2"},
                            {"label": "X2", "value": "x2"},
                            {"label": "E2", "value": "e2"},
                        ],
                    },
                    {"key": "sweep_start", "label": "扫描起点", "type": "number", "default": 0.2, "min": 0.01, "max": 2000, "step": 0.01},
                    {"key": "sweep_stop", "label": "扫描终点", "type": "number", "default": 1.2, "min": 0.02, "max": 3000, "step": 0.01},
                    {"key": "sweep_points", "label": "扫描点数", "type": "number", "default": 6, "min": 3, "max": 12, "step": 1},
                ]
            )
        elif scenario == "operating_point_compare":
            controls.append(
                {
                    "key": "slip_points",
                    "label": "滑差点列表",
                    "type": "text",
                    "default": "0.05,0.1,0.2,0.3,0.5,1.0",
                    "placeholder": "用逗号分隔，例如 0.05,0.1,0.2",
                }
            )

        defaults = {control["key"]: control.get("default") for control in controls}
        return {
            "title": title,
            "description": description,
            "scenario": scenario,
            "controls": controls,
            "defaults": defaults,
            "run_label": "运行该仿真",
            "allowed_backends": ["auto", "python", "service", "matlab"],
            "safety_mode": "whitelist",
        }

    @staticmethod
    def list_beginner_templates() -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for template in BEGINNER_TEMPLATE_LIBRARY:
            rows.append(
                {
                    "id": template["id"],
                    "title": template["title"],
                    "subtitle": template.get("subtitle", ""),
                    "scenario": template["scenario"],
                    "difficulty": template.get("difficulty", "入门"),
                    "duration_min": int(template.get("duration_min", 10)),
                    "goal": template.get("goal", ""),
                    "focus": template.get("focus", []),
                }
            )
        return rows

    @staticmethod
    def _find_template(template_id: str) -> Optional[Dict[str, Any]]:
        normalized = template_id.strip().lower()
        for template in BEGINNER_TEMPLATE_LIBRARY:
            if str(template.get("id", "")).strip().lower() == normalized:
                return template
        return None

    def design_spec_from_template(self, template_id: str) -> Dict[str, Any]:
        template = self._find_template(template_id)
        if not template:
            raise ValueError(f"未找到模板：{template_id}")

        scenario = str(template["scenario"]).strip().lower()
        if scenario not in ALLOWED_SCENARIOS:
            raise ValueError(f"模板场景不受支持：{scenario}")

        spec = self._build_spec(
            scenario=scenario,
            title=str(template.get("title", "初学者仿真实验")),
            description=str(template.get("goal", "基于模板生成的入门仿真实验。")),
        )

        template_defaults = template.get("defaults", {}) or {}
        for key, value in template_defaults.items():
            if key in spec["defaults"]:
                spec["defaults"][key] = value

        for control in spec["controls"]:
            key = control.get("key")
            if key in template_defaults:
                control["default"] = template_defaults[key]

        spec["template_id"] = template["id"]
        spec["template_mode"] = "beginner"
        spec["generation_source"] = "template"
        spec["model_used"] = self.model
        spec["request"] = template.get("title", "")
        spec["learning_goal"] = template.get("goal", "")
        spec["observe_points"] = template.get("observe_points", [])
        spec["recommended_steps"] = template.get("recommended_steps", [])
        spec["student_task"] = template.get("student_task", "")
        spec["difficulty"] = template.get("difficulty", "入门")
        spec["duration_min"] = int(template.get("duration_min", 10))
        spec["subtitle"] = template.get("subtitle", "")
        spec["run_label"] = "开始实验"
        return spec

    @staticmethod
    def _detect_rule_scenario(user_request: str) -> str:
        lowered = user_request.lower()
        if any(token in lowered for token in ["扫描", "sweep", "变化", "对比"]):
            return "parameter_sweep"
        if any(token in lowered for token in ["工况", "滑差点", "运行点", "工况点"]):
            return "operating_point_compare"
        if any(token in lowered for token in ["启动", "起动", "堵转", "起动能力"]):
            return "startup_assessment"
        return "torque_curve"

    @staticmethod
    def _detect_sweep_variable(user_request: str) -> str:
        lowered = user_request.lower()
        if "x2" in lowered:
            return "x2"
        if "e2" in lowered:
            return "e2"
        return "r2"

    def _design_with_rules(self, user_request: str) -> Dict[str, Any]:
        scenario = self._detect_rule_scenario(user_request)
        titles = {
            "torque_curve": "智能仿真卡片：转矩-滑差曲线",
            "parameter_sweep": "智能仿真卡片：参数扫描分析",
            "operating_point_compare": "智能仿真卡片：工况点对比",
            "startup_assessment": "智能仿真卡片：启动性能评估",
        }
        desc = {
            "torque_curve": "用于查看异步电机在不同滑差下的转矩变化趋势。",
            "parameter_sweep": "用于分析单个关键参数变化时，最大转矩和滑差点如何变化。",
            "operating_point_compare": "用于对一组指定滑差点进行快速对比，便于教学讲解工况差异。",
            "startup_assessment": "用于评估启动转矩水平与启动能力等级。",
        }
        spec = self._build_spec(scenario, titles[scenario], desc[scenario])
        if scenario == "parameter_sweep":
            spec["defaults"]["sweep_variable"] = self._detect_sweep_variable(user_request)
        spec["generation_source"] = "rule"
        spec["model_used"] = self.model
        spec["request"] = user_request
        return spec

    def _design_with_llm(self, user_request: str) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None

        messages = [
            {
                "role": "system",
                "content": (
                    "你是电机学仿真产品设计器。只允许输出一个 JSON。"
                    "可选 scenario 仅有 torque_curve, parameter_sweep, operating_point_compare, startup_assessment。"
                    "JSON 字段只允许 title, description, scenario, sweep_variable。"
                ),
            },
            {"role": "user", "content": f"用户需求：{user_request}"},
        ]

        try:
            response = Generation.call(
                model=self.model,
                messages=messages,
                result_format="message",
                temperature=0.1,
            )
            if response.status_code != 200:
                return None
            content = response.output.choices[0].message.content
            payload = _extract_json_block(content if isinstance(content, str) else str(content))
            if not payload:
                return None
            scenario = str(payload.get("scenario", "")).strip().lower()
            if scenario not in ALLOWED_SCENARIOS:
                return None
            title = str(payload.get("title", "智能仿真卡片")).strip() or "智能仿真卡片"
            description = str(payload.get("description", "")).strip() or "已根据用户需求自动生成仿真配置。"
            spec = self._build_spec(scenario, title, description)
            if scenario == "parameter_sweep":
                sweep_variable = str(payload.get("sweep_variable", "r2")).lower()
                if sweep_variable in {"r2", "x2", "e2"}:
                    spec["defaults"]["sweep_variable"] = sweep_variable
            spec["generation_source"] = "llm"
            spec["model_used"] = self.model
            spec["request"] = user_request
            return spec
        except Exception:
            return None

    def design_spec(self, user_request: str) -> Dict[str, Any]:
        normalized = user_request.strip()
        if not normalized:
            fallback = self._build_spec(
                "torque_curve",
                "智能仿真卡片：转矩-滑差曲线",
                "未输入需求，已生成默认教学仿真卡片。",
            )
            fallback["generation_source"] = "default"
            fallback["model_used"] = self.model
            fallback["request"] = ""
            return fallback

        llm_spec = self._design_with_llm(normalized)
        if llm_spec:
            return llm_spec
        return self._design_with_rules(normalized)

    @staticmethod
    def parse_runtime_values(scenario: str, raw_values: Dict[str, Any]) -> Dict[str, Any]:
        values = raw_values or {}
        normalized: Dict[str, Any] = {
            "r2": _as_float(values.get("r2"), 0.5, minimum=0.05, maximum=3.0),
            "x2": _as_float(values.get("x2"), 1.2, minimum=0.05, maximum=6.0),
            "e2": _as_float(values.get("e2"), 220.0, minimum=20.0, maximum=1200.0),
            "s_min": _as_float(values.get("s_min"), 0.01, minimum=0.001, maximum=0.8),
            "s_max": _as_float(values.get("s_max"), 1.0, minimum=0.05, maximum=1.0),
            "n_points": _as_int(values.get("n_points"), 200, minimum=40, maximum=2000),
        }

        if normalized["s_max"] <= normalized["s_min"]:
            normalized["s_max"] = min(normalized["s_min"] + 0.05, 1.0)

        if scenario == "parameter_sweep":
            variable = str(values.get("sweep_variable", "r2")).lower()
            normalized["sweep_variable"] = variable if variable in {"r2", "x2", "e2"} else "r2"
            normalized["sweep_start"] = _as_float(values.get("sweep_start"), 0.2, minimum=0.01, maximum=2000)
            normalized["sweep_stop"] = _as_float(values.get("sweep_stop"), 1.2, minimum=0.02, maximum=3000)
            normalized["sweep_points"] = _as_int(values.get("sweep_points"), 6, minimum=3, maximum=12)

        if scenario == "operating_point_compare":
            raw_slip_points = values.get("slip_points", "0.05,0.1,0.2,0.3,0.5,1.0")
            if isinstance(raw_slip_points, list):
                tokens = [str(item) for item in raw_slip_points]
            else:
                tokens = re.split(r"[,\s;，]+", str(raw_slip_points))
            parsed: List[float] = []
            for token in tokens:
                if not token.strip():
                    continue
                slip = _as_float(token, 0.1, minimum=0.001, maximum=1.0)
                parsed.append(slip)
            unique = sorted(set(parsed))[:16]
            normalized["slip_points"] = unique or [0.05, 0.1, 0.2, 0.3, 0.5, 1.0]

        return normalized


SIMULATION_STUDIO = SimulationStudioService()
