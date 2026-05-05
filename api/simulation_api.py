from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

from simulation.motor_simulator import (
    InductionMotorParams,
    MATLAB_ADAPTER,
    REMOTE_CLIENT,
    simulate_torque_curve,
    simulate_torque_curve_python,
)


app = FastAPI(title="AITeach Simulation Service", version="1.0.0")


class MotorSimulationRequest(BaseModel):
    r2: float = Field(0.5, gt=0)
    x2: float = Field(1.2, gt=0)
    e2: float = Field(220.0, gt=0)
    s_min: float = Field(0.01, gt=0)
    s_max: float = Field(1.0, gt=0, le=1.0)
    n_points: int = Field(200, ge=10, le=5000)
    backend: Literal["auto", "python", "matlab"] = "python"


@app.get("/api/health")
def health() -> dict:
    matlab_status = MATLAB_ADAPTER.status()
    return {
        "ok": True,
        "service": "simulation",
        "matlab_available": bool(matlab_status.get("available")),
        "matlab_mode": matlab_status.get("mode", "none"),
        "matlab_engine_available": bool(matlab_status.get("engine_available")),
        "matlab_cli_available": bool(matlab_status.get("cli_available")),
        "matlab_cli_executable": matlab_status.get("cli_executable", ""),
        "matlab_error": MATLAB_ADAPTER.get_last_error() if not matlab_status.get("available") else "",
        "matlab_engine_error": matlab_status.get("engine_error", ""),
        "matlab_cli_error": matlab_status.get("cli_error", ""),
        "service_url": REMOTE_CLIENT.service_url,
    }


@app.post("/api/simulate/motor")
def simulate_motor(request: MotorSimulationRequest) -> dict:
    params = InductionMotorParams(
        r2=request.r2,
        x2=request.x2,
        e2=request.e2,
        s_min=request.s_min,
        s_max=request.s_max,
        n_points=request.n_points,
    )

    if request.backend == "python":
        result = simulate_torque_curve_python(params)
    else:
        # 独立仿真服务内部禁止再次走 service 路由，避免自调用递归。
        result = simulate_torque_curve(params, backend=request.backend, allow_service=False)

    result["slip"] = result["slip"].tolist()
    result["torque"] = result["torque"].tolist()
    return result
