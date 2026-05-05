import json
import os
import tempfile
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app_config import APP_TITLE, DEFAULT_DB_PATH
from runtime_env import clear_invalid_proxy_env, load_local_env
from services.fixed_simulation_lab_service import FIXED_SIM_LAB_SERVICE
from services.knowledge_base_service import JSONLQAAgent
from services.simulation_coach_service import SimulationCoachService
from services.simulation_studio_service import ALLOWED_SCENARIOS, SIMULATION_STUDIO
from services.solver_service import MotorTheoryWorkflow, contains_error_marker
from services.wrongbook_ai_service import WrongbookAIService
from simulation.motor_simulator import (
    InductionMotorParams,
    MATLAB_ADAPTER,
    REMOTE_CLIENT,
    simulate_by_scenario,
    simulate_torque_curve,
)
from storage.wrong_question_repository import WrongQuestionDB


ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT_DIR / "web_frontend"

load_local_env()
clear_invalid_proxy_env()


def to_jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    return value


def to_ndjson_line(payload: Dict[str, Any]) -> str:
    return json.dumps(to_jsonable(payload), ensure_ascii=False) + "\n"


def remove_file_quietly(file_path: Optional[str]) -> None:
    """Best-effort temp file cleanup so failed requests do not leak scratch files."""
    if not file_path or not os.path.exists(file_path):
        return
    try:
        os.remove(file_path)
    except OSError:
        pass


def parse_history_json(raw_history: str) -> List[Dict[str, str]]:
    if not raw_history.strip():
        return []
    try:
        payload = json.loads(raw_history)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []

    rows: List[Dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if role not in {"user", "assistant"} or not content:
            continue
        rows.append({"role": role, "content": content})
    return rows[-10:]


class ServiceContainer:
    def __init__(self):
        self._lock = Lock()
        self._api_key: Optional[str] = None
        self._workflow: Optional[MotorTheoryWorkflow] = None
        self._qa_agent: Optional[JSONLQAAgent] = None
        self._wrongbook_ai: Optional[WrongbookAIService] = None
        self._simulation_coach: Optional[SimulationCoachService] = None
        self.db = WrongQuestionDB(os.getenv("WRONG_QUESTION_DB", DEFAULT_DB_PATH))

    def ensure_ai_services(self) -> tuple[Optional[MotorTheoryWorkflow], Optional[JSONLQAAgent]]:
        # Rebuild the AI bundle together when the key changes so every endpoint
        # stays on the same model/session configuration.
        api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
        if not api_key:
            return None, None

        with self._lock:
            if api_key != self._api_key or self._workflow is None or self._qa_agent is None:
                self._qa_agent = JSONLQAAgent(api_key)
                self._workflow = MotorTheoryWorkflow(api_key, knowledge_agent=self._qa_agent)
                self._wrongbook_ai = WrongbookAIService(api_key)
                self._simulation_coach = SimulationCoachService(api_key)
                self._api_key = api_key
            else:
                self._workflow.set_knowledge_agent(self._qa_agent)
        return self._workflow, self._qa_agent

    def ensure_wrongbook_ai(self) -> Optional[WrongbookAIService]:
        api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
        if not api_key:
            return None

        with self._lock:
            if api_key != self._api_key or self._wrongbook_ai is None:
                self._wrongbook_ai = WrongbookAIService(api_key)
                self._api_key = api_key
        return self._wrongbook_ai

    def ensure_simulation_coach(self) -> Optional[SimulationCoachService]:
        api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
        if not api_key:
            return None

        with self._lock:
            if api_key != self._api_key or self._simulation_coach is None:
                self._simulation_coach = SimulationCoachService(api_key)
                self._api_key = api_key
        return self._simulation_coach


def require_workflow_and_qa() -> tuple[MotorTheoryWorkflow, JSONLQAAgent]:
    # Keep a single guarded entry so every AI endpoint fails consistently.
    workflow, qa_agent = SERVICES.ensure_ai_services()
    if workflow is None or qa_agent is None:
        raise HTTPException(status_code=503, detail="未检测到 DASHSCOPE_API_KEY，AI 服务不可用。")
    return workflow, qa_agent


def require_qa_agent() -> JSONLQAAgent:
    _, qa_agent = require_workflow_and_qa()
    return qa_agent


def require_simulation_coach() -> SimulationCoachService:
    coach_service = SERVICES.ensure_simulation_coach()
    if coach_service is None:
        raise HTTPException(status_code=503, detail="未检测到 DASHSCOPE_API_KEY，仿真实验指导不可用。")
    return coach_service


def require_wrongbook_ai() -> WrongbookAIService:
    ai_service = SERVICES.ensure_wrongbook_ai()
    if ai_service is None:
        raise HTTPException(status_code=503, detail="未检测到 DASHSCOPE_API_KEY，错题 AI 功能不可用。")
    return ai_service


SERVICES = ServiceContainer()
app = FastAPI(title=f"{APP_TITLE} Web API", version="1.0.0")
app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")


class TextSolveRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = Field(3, ge=1, le=8)
    solve_mode: str = Field("fast")


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = Field(3, ge=1, le=10)
    similarity_threshold: float = Field(0.18, ge=0.1, le=0.95)


class MotorSimulationRequest(BaseModel):
    r2: float = Field(0.5, gt=0)
    x2: float = Field(1.2, gt=0)
    e2: float = Field(220.0, gt=0)
    s_min: float = Field(0.01, gt=0)
    s_max: float = Field(1.0, gt=0, le=1.0)
    n_points: int = Field(200, ge=10, le=5000)
    backend: str = Field("auto")


class SimulationDesignRequest(BaseModel):
    request: str = Field(..., min_length=1, max_length=500)


class SimulationTemplateRequest(BaseModel):
    template_id: str = Field(..., min_length=3, max_length=80)


class SimulationRunRequest(BaseModel):
    scenario: str = Field(..., min_length=1)
    values: Dict[str, Any] = Field(default_factory=dict)
    backend: str = Field("auto")


class SimulationLabRunRequest(BaseModel):
    lab_id: str = Field(..., min_length=3, max_length=80)
    params: Dict[str, Any] = Field(default_factory=dict)
    backend: str = Field("auto")


class MatlabCliConfigRequest(BaseModel):
    mode: str = Field("auto")
    executable_path: str = Field("")


class SimulationCoachHistoryMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=4000)


class SimulationCoachChatRequest(BaseModel):
    lab_id: str = Field(..., min_length=3, max_length=80)
    message: str = Field(..., min_length=1, max_length=4000)
    history: List[SimulationCoachHistoryMessage] = Field(default_factory=list)


class WrongQuestionCreateRequest(BaseModel):
    question_text: str
    answer_text: str
    error_reason: str
    source_type: str = "manual"
    image_path: Optional[str] = None


class WrongQuestionUpdateRequest(BaseModel):
    question_text: str
    answer_text: str
    error_reason: str


class WrongbookAnalyzeRequest(BaseModel):
    record_limit: int = Field(80, ge=5, le=200)


class WrongbookPracticeCreateRequest(BaseModel):
    focus: Optional[str] = Field(None, max_length=120)


class WrongbookPracticeExplainRequest(BaseModel):
    question_id: str = Field(..., min_length=6)
    user_answer: str = Field("", max_length=3000)


@app.get("/")
def web_home() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
def health() -> Dict[str, Any]:
    workflow, qa_agent = SERVICES.ensure_ai_services()
    return {
        "ok": True,
        "app": "AITeach Web",
        "ai_ready": workflow is not None and qa_agent is not None,
        "knowledge_count": len(qa_agent.qa_pairs) if qa_agent else 0,
        "wrong_question_count": SERVICES.db.count_wrong_questions(),
        "remote_simulation_service_online": REMOTE_CLIENT.is_available(),
    }


@app.post("/api/solve/text")
def solve_text(payload: TextSolveRequest) -> Dict[str, Any]:
    workflow, qa_agent = require_workflow_and_qa()
    result = workflow.solve_from_text(
        payload.question.strip(),
        knowledge_agent=qa_agent,
        top_k=payload.top_k,
        solve_mode=payload.solve_mode,
    )
    return to_jsonable(result)


@app.post("/api/solve/image")
def solve_image(file: UploadFile = File(...), top_k: int = 3, solve_mode: str = "fast") -> Dict[str, Any]:
    workflow, qa_agent = require_workflow_and_qa()

    suffix = Path(file.filename or "question.jpg").suffix or ".jpg"
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(file.file.read())
            temp_path = temp_file.name
        result = workflow.solve_motor_problem(
            temp_path,
            knowledge_agent=qa_agent,
            top_k=max(top_k, 1),
            solve_mode=solve_mode,
        )
        return to_jsonable(result)
    finally:
        remove_file_quietly(temp_path)


@app.post("/api/solve/chat/stream")
def solve_chat_stream(
    message: str = Form(""),
    history_json: str = Form("[]"),
    top_k: int = Form(3),
    solve_mode: str = Form("standard"),
    file: Optional[UploadFile] = File(None),
):
    workflow, qa_agent = require_workflow_and_qa()

    user_message = (message or "").strip()
    history = parse_history_json(history_json)
    if not user_message and file is None:
        raise HTTPException(status_code=400, detail="请先输入题目内容或上传题目图片。")

    suffix = Path(file.filename or "question.jpg").suffix if file else ""
    safe_suffix = suffix or ".jpg"
    temp_path: Optional[str] = None

    try:
        extracted_text = ""
        if file is not None:
            with tempfile.NamedTemporaryFile(delete=False, suffix=safe_suffix) as temp_file:
                temp_file.write(file.file.read())
                temp_path = temp_file.name
            extracted_text = workflow.extract_question_from_image(temp_path)
            if contains_error_marker(extracted_text):
                raise HTTPException(status_code=400, detail=extracted_text)

        solve_parts = []
        if user_message:
            solve_parts.append(f"用户补充说明：\n{user_message}")
        if extracted_text:
            solve_parts.append(f"图片识别题目：\n{extracted_text}")

        solve_input_text = "\n\n".join(part for part in solve_parts if part).strip() or user_message or extracted_text
        display_question = extracted_text.strip() or user_message
        prepared = workflow.prepare_chat_solution(
            solve_input_text,
            history=history,
            knowledge_agent=qa_agent,
            top_k=max(int(top_k or 3), 1),
            solve_mode=solve_mode,
        )

        def event_stream():
            solution_parts: List[str] = []
            try:
                if extracted_text:
                    yield to_ndjson_line({"type": "meta", "extracted_text": extracted_text})
                for delta in workflow.stream_prepared_solution(prepared):
                    solution_parts.append(delta)
                    yield to_ndjson_line({"type": "delta", "delta": delta})

                quality = workflow.enforce_solution_quality(
                    prepared.get("question_text") or solve_input_text,
                    "".join(solution_parts),
                    prepared.get("reference_context") or "",
                    history=prepared.get("history"),
                )
                final_result = workflow.build_result_from_prepared(
                    prepared,
                    quality.get("solution") or "".join(solution_parts),
                    display_question=display_question,
                    quality_notes=quality.get("notes"),
                    auto_repaired=bool(quality.get("auto_repaired")),
                )
                yield to_ndjson_line({"type": "done", "result": final_result})
            except Exception as exc:
                yield to_ndjson_line({"type": "error", "error": f"推理流中断：{exc}"})
            finally:
                # Streaming requests also need temp cleanup because the response
                # body may finish long after the outer function has returned.
                remove_file_quietly(temp_path)

        return StreamingResponse(event_stream(), media_type="application/x-ndjson")

    except Exception as exc:
        remove_file_quietly(temp_path)
        raise HTTPException(status_code=500, detail=f"流式解题失败：{exc}") from exc


@app.post("/api/qa/ask")
def ask_question(payload: AskRequest) -> Dict[str, Any]:
    qa_agent = require_qa_agent()
    result = qa_agent.ask_question(
        payload.question.strip(),
        top_k=payload.top_k,
        similarity_threshold=payload.similarity_threshold,
    )
    return to_jsonable(result)


@app.post("/api/simulate/motor")
def simulate_motor(payload: MotorSimulationRequest) -> Dict[str, Any]:
    params = InductionMotorParams(
        r2=payload.r2,
        x2=payload.x2,
        e2=payload.e2,
        s_min=payload.s_min,
        s_max=payload.s_max,
        n_points=payload.n_points,
    )
    result = simulate_torque_curve(params, backend=payload.backend)
    return to_jsonable(result)


@app.get("/api/simulate/matlab-status")
def matlab_status() -> Dict[str, Any]:
    local_status = MATLAB_ADAPTER.status()
    cli_preferences = MATLAB_ADAPTER.cli_preferences()
    local_available = bool(local_status.get("available"))
    local_error = str(local_status.get("engine_error") or local_status.get("cli_error") or MATLAB_ADAPTER.get_last_error())
    service_online = REMOTE_CLIENT.is_available()
    service_matlab_available = False
    service_matlab_error = ""
    service_health: Dict[str, Any] = {}

    if service_online:
        try:
            raw_health = REMOTE_CLIENT.health()
            if isinstance(raw_health, dict):
                service_health = raw_health
                service_matlab_available = bool(raw_health.get("matlab_available"))
                service_matlab_error = str(raw_health.get("matlab_error", "")).strip()
        except Exception as exc:
            service_matlab_error = str(exc)

    return {
        "local_matlab_available": local_available,
        "local_matlab_mode": str(local_status.get("mode", "none")),
        "local_engine_available": bool(local_status.get("engine_available")),
        "local_cli_available": bool(local_status.get("cli_available")),
        "local_cli_executable": str(local_status.get("cli_executable", "")),
        "local_cli_source": str(local_status.get("cli_source", "")),
        "local_matlab_error": "" if local_available else local_error,
        "local_engine_error": str(local_status.get("engine_error", "")),
        "local_cli_error": str(local_status.get("cli_error", "")),
        "cli_config_mode": str(cli_preferences.get("mode", "auto")),
        "cli_configured_path": str(cli_preferences.get("configured_path", "")),
        "cli_resolved_path": str(cli_preferences.get("resolved_path", "")),
        "cli_config_file": str(cli_preferences.get("config_file", "")),
        "service_online": service_online,
        "service_matlab_available": service_matlab_available,
        "service_matlab_error": service_matlab_error,
        "service_health": service_health,
    }


@app.post("/api/simulate/matlab-cli-config")
def update_matlab_cli_config(payload: MatlabCliConfigRequest) -> Dict[str, Any]:
    try:
        MATLAB_ADAPTER.configure_cli(mode=payload.mode, executable_path=payload.executable_path)
        status = matlab_status()
        status["message"] = "MATLAB CLI 路径配置已保存。"
        return status
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/simulate/labs")
def list_fixed_simulation_labs() -> Dict[str, Any]:
    labs = FIXED_SIM_LAB_SERVICE.list_labs()
    return {"items": labs, "count": len(labs)}


@app.post("/api/simulate/lab-run")
def run_fixed_simulation_lab(payload: SimulationLabRunRequest) -> Dict[str, Any]:
    try:
        result = FIXED_SIM_LAB_SERVICE.run_lab(
            lab_id=payload.lab_id,
            params=payload.params,
            backend=payload.backend,
        )
        result["lab"] = FIXED_SIM_LAB_SERVICE.get_lab(payload.lab_id)
        return to_jsonable(result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"固定实验运行失败：{exc}") from exc


@app.post("/api/simulate/lab-coach/chat")
def simulation_lab_coach_chat(payload: SimulationCoachChatRequest) -> Dict[str, Any]:
    coach_service = require_simulation_coach()

    try:
        history = [{"role": item.role, "content": item.content} for item in payload.history][-8:]
        result = coach_service.chat(
            lab_id=payload.lab_id,
            message=payload.message,
            history=history,
        )
        return to_jsonable(result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"仿真实验指导失败：{exc}") from exc


@app.get("/api/simulate/templates")
def list_simulation_templates() -> Dict[str, Any]:
    templates = SIMULATION_STUDIO.list_beginner_templates()
    return {"items": templates, "count": len(templates)}


@app.post("/api/simulate/design-template")
def design_simulation_from_template(payload: SimulationTemplateRequest) -> Dict[str, Any]:
    template_id = payload.template_id.strip()
    if not template_id:
        raise HTTPException(status_code=400, detail="模板 ID 不能为空。")
    try:
        spec = SIMULATION_STUDIO.design_spec_from_template(template_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return to_jsonable(spec)


@app.post("/api/simulate/design")
def design_simulation(payload: SimulationDesignRequest) -> Dict[str, Any]:
    request_text = payload.request.strip()
    if not request_text:
        raise HTTPException(status_code=400, detail="仿真需求不能为空。")
    spec = SIMULATION_STUDIO.design_spec(request_text)
    return to_jsonable(spec)


@app.post("/api/simulate/run-designed")
def run_designed_simulation(payload: SimulationRunRequest) -> Dict[str, Any]:
    scenario = payload.scenario.strip().lower()
    if scenario not in ALLOWED_SCENARIOS:
        raise HTTPException(status_code=400, detail=f"不支持的场景：{scenario}")

    normalized_values = SIMULATION_STUDIO.parse_runtime_values(scenario, payload.values)
    params = InductionMotorParams(
        r2=float(normalized_values["r2"]),
        x2=float(normalized_values["x2"]),
        e2=float(normalized_values["e2"]),
        s_min=float(normalized_values["s_min"]),
        s_max=float(normalized_values["s_max"]),
        n_points=int(normalized_values["n_points"]),
    )

    options: Dict[str, Any] = {}
    if scenario == "parameter_sweep":
        options = {
            "sweep_variable": normalized_values.get("sweep_variable", "r2"),
            "sweep_start": normalized_values.get("sweep_start", 0.2),
            "sweep_stop": normalized_values.get("sweep_stop", 1.2),
            "sweep_points": normalized_values.get("sweep_points", 6),
        }
    elif scenario == "operating_point_compare":
        options = {"slip_points": normalized_values.get("slip_points", [0.05, 0.1, 0.2, 0.3, 0.5, 1.0])}

    result = simulate_by_scenario(
        scenario=scenario,
        params=params,
        backend=payload.backend,
        options=options,
        allow_service=True,
    )
    result.setdefault("scenario", scenario)
    result["normalized_values"] = normalized_values
    return to_jsonable(result)


@app.get("/api/wrong-questions")
def list_wrong_questions(
    page: int = Query(1, ge=1),
    page_size: int = Query(6, ge=1, le=30),
) -> Dict[str, Any]:
    return SERVICES.db.list_wrong_questions_paginated(page=page, page_size=page_size)


@app.post("/api/wrong-questions")
def create_wrong_question(payload: WrongQuestionCreateRequest) -> Dict[str, Any]:
    row_id = SERVICES.db.add_wrong_question(
        question_text=payload.question_text,
        answer_text=payload.answer_text,
        error_reason=payload.error_reason,
        source_type=payload.source_type,
        image_path=payload.image_path,
    )
    return {"ok": True, "id": row_id}


@app.put("/api/wrong-questions/{record_id}")
def update_wrong_question(record_id: int, payload: WrongQuestionUpdateRequest) -> Dict[str, Any]:
    ok = SERVICES.db.update_wrong_question(
        record_id=record_id,
        question_text=payload.question_text,
        answer_text=payload.answer_text,
        error_reason=payload.error_reason,
    )
    if not ok:
        raise HTTPException(status_code=404, detail=f"未找到记录 {record_id}")
    return {"ok": True}


@app.delete("/api/wrong-questions/{record_id}")
def delete_wrong_question(record_id: int) -> Dict[str, Any]:
    ok = SERVICES.db.delete_wrong_question(record_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"未找到记录 {record_id}")
    return {"ok": True}


@app.post("/api/wrong-questions/analyze")
def analyze_wrong_questions(payload: WrongbookAnalyzeRequest) -> Dict[str, Any]:
    ai_service = require_wrongbook_ai()

    rows = SERVICES.db.list_wrong_questions()
    if not rows:
        raise HTTPException(status_code=400, detail="错题本为空，请先加入错题后再分析。")

    try:
        return to_jsonable(ai_service.analyze_wrongbook(rows, record_limit=payload.record_limit))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"错题分析失败：{exc}") from exc


@app.post("/api/wrong-questions/practice/new")
def generate_practice_question(payload: WrongbookPracticeCreateRequest) -> Dict[str, Any]:
    ai_service = require_wrongbook_ai()

    rows = SERVICES.db.list_wrong_questions()
    if not rows:
        raise HTTPException(status_code=400, detail="错题本为空，请先加入错题后再出题。")

    try:
        return to_jsonable(ai_service.generate_practice_question(rows, focus=(payload.focus or "").strip() or None))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"生成练习题失败：{exc}") from exc


@app.post("/api/wrong-questions/practice/explain")
def explain_practice_question(payload: WrongbookPracticeExplainRequest) -> Dict[str, Any]:
    ai_service = require_wrongbook_ai()

    result = ai_service.explain_practice_question(
        question_id=payload.question_id.strip(),
        user_answer=(payload.user_answer or "").strip(),
    )
    if result is None:
        raise HTTPException(status_code=404, detail="未找到对应练习题，请重新生成后再查看解析。")
    return to_jsonable(result)
