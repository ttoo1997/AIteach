import base64
import json
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, replace
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

import matplotlib
import numpy as np
from matplotlib.figure import Figure

from app_config import (
    DEFAULT_MATLAB_FUNCTION,
    DEFAULT_SIMULATION_BACKEND,
    DEFAULT_SIMULATION_SERVICE_HEALTH_URL,
    DEFAULT_SIMULATION_SERVICE_URL,
)
from schemas.contracts import SimulationResult

matplotlib.use("Agg")


SUPPORTED_SWEEP_VARIABLES = {"r2", "x2", "e2"}
SUPPORTED_SCENARIOS = {"torque_curve", "parameter_sweep", "operating_point_compare", "startup_assessment"}


@dataclass
class InductionMotorParams:
    r2: float = 0.5
    x2: float = 1.2
    e2: float = 220.0
    s_min: float = 0.01
    s_max: float = 1.0
    n_points: int = 200

    def to_payload(self) -> Dict[str, Any]:
        return {
            "r2": float(self.r2),
            "x2": float(self.x2),
            "e2": float(self.e2),
            "s_min": float(self.s_min),
            "s_max": float(self.s_max),
            "n_points": int(self.n_points),
        }


def _to_data_url(image_bytes: bytes, mime_type: str = "image/png") -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _render_torque_plot_with_matplotlib(
    params: InductionMotorParams,
    slip: np.ndarray,
    torque: np.ndarray,
    max_slip: float,
    max_torque: float,
) -> str:
    """Fallback chart renderer so the Web UI still gets a plot without MATLAB."""
    figure = Figure(figsize=(6.0, 3.8), dpi=160)
    axes = figure.subplots()
    axes.plot(slip, torque, color="#101828", linewidth=2.2)
    axes.scatter([max_slip], [max_torque], color="#2563eb", s=40, zorder=3)
    axes.annotate(
        f"peak s={max_slip:.3f}",
        xy=(max_slip, max_torque),
        xytext=(10, -18),
        textcoords="offset points",
        color="#1f4f97",
        fontsize=8,
    )
    axes.set_xlabel("Slip s")
    axes.set_ylabel("Torque T")
    axes.set_title(f"T-s curve (R2 = {params.r2:.3f})")
    axes.grid(True, linestyle="--", linewidth=0.7, alpha=0.35)
    axes.margins(x=0.03, y=0.08)
    figure.tight_layout()

    buffer = BytesIO()
    figure.savefig(buffer, format="png", facecolor="white", bbox_inches="tight")
    return _to_data_url(buffer.getvalue(), mime_type="image/png")


def _attach_curve_plot(result: Dict[str, Any], params: InductionMotorParams, *, preferred_caption: str) -> Dict[str, Any]:
    if result.get("plot_image_data_url"):
        result.setdefault("plot_caption", preferred_caption)
        return result

    slip = np.array(result.get("slip", []), dtype=float).flatten()
    torque = np.array(result.get("torque", []), dtype=float).flatten()
    if slip.size == 0 or torque.size == 0:
        return result

    result["plot_image_data_url"] = _render_torque_plot_with_matplotlib(
        params=params,
        slip=slip,
        torque=torque,
        max_slip=float(result.get("max_slip", slip[int(np.argmax(torque))])),
        max_torque=float(result.get("max_torque", np.max(torque))),
    )
    result["plot_caption"] = preferred_caption
    return result


class RemoteSimulationClient:
    def __init__(self):
        self.service_url = os.getenv("SIMULATION_SERVICE_URL", DEFAULT_SIMULATION_SERVICE_URL)
        self.health_url = os.getenv("SIMULATION_SERVICE_HEALTH_URL", DEFAULT_SIMULATION_SERVICE_HEALTH_URL)
        self.timeout = float(os.getenv("SIMULATION_SERVICE_TIMEOUT", "8"))

    def is_available(self) -> bool:
        try:
            request = Request(self.health_url, method="GET")
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return bool(payload.get("ok"))
        except Exception:
            return False

    def health(self) -> Dict[str, Any]:
        request = Request(self.health_url, method="GET")
        with urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError("仿真服务健康接口返回格式异常。")
        return payload

    def matlab_available(self) -> bool:
        try:
            payload = self.health()
            return bool(payload.get("matlab_available"))
        except Exception:
            return False

    def simulate(self, params: InductionMotorParams, preferred_backend: str = "python") -> Dict[str, Any]:
        payload = params.to_payload()
        payload["backend"] = preferred_backend
        request = Request(
            self.service_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
        result["slip"] = np.array(result["slip"], dtype=float)
        result["torque"] = np.array(result["torque"], dtype=float)
        return result


class MatlabSimulationAdapter:
    def __init__(self):
        self.function_name = os.getenv("MATLAB_SIMULATION_FUNCTION", DEFAULT_MATLAB_FUNCTION)
        self.cli_function_name = os.getenv("MATLAB_CLI_FUNCTION", "aiteach_motor_torque_cli")
        self.cli_timeout_seconds = int(float(os.getenv("MATLAB_CLI_TIMEOUT", "60")))
        self.engine_startup_timeout = int(float(os.getenv("MATLAB_ENGINE_STARTUP_TIMEOUT", "30")))
        self.engine_call_timeout = int(float(os.getenv("MATLAB_ENGINE_CALL_TIMEOUT", "60")))
        self.cli_executable_hint = os.getenv("MATLAB_EXE_PATH", "").strip()
        self.cli_config_path = Path(__file__).resolve().parents[1] / ".runtime_tmp" / "matlab_cli_config.json"
        self.cli_config_mode = "auto"
        self.cli_configured_path = ""
        self._engine: Optional[Any] = None
        self._engine_module: Optional[Any] = None
        self._engine_checked = False
        self._engine_available = False
        self._engine_error = ""
        self._cli_checked = False
        self._cli_available = False
        self._cli_error = ""
        self._cli_executable = ""
        self._cli_source = ""
        self._last_error = ""
        self._load_cli_config()

    @staticmethod
    def _matlab_dir() -> Path:
        return Path(__file__).resolve().parents[1] / "matlab"

    @staticmethod
    def _to_matlab_path(path: str) -> str:
        return path.replace("\\", "/").replace("'", "''")

    def _load_cli_config(self) -> None:
        try:
            if not self.cli_config_path.exists():
                return
            payload = json.loads(self.cli_config_path.read_text(encoding="utf-8"))
            mode = str(payload.get("mode", "auto")).strip().lower()
            if mode in {"auto", "custom"}:
                self.cli_config_mode = mode
            self.cli_configured_path = str(payload.get("path", "")).strip()
        except Exception:
            self.cli_config_mode = "auto"
            self.cli_configured_path = ""

    def _save_cli_config(self) -> None:
        self.cli_config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "mode": self.cli_config_mode,
            "path": self.cli_configured_path,
        }
        self.cli_config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _reset_cli_cache(self) -> None:
        self._cli_checked = False
        self._cli_available = False
        self._cli_error = ""
        self._cli_executable = ""
        self._cli_source = ""
        self._last_error = ""

    @staticmethod
    def _normalize_input_path(raw_path: str) -> str:
        return str(raw_path or "").strip().strip('"')

    def _resolve_cli_candidate(self, raw_path: str) -> Optional[str]:
        normalized = self._normalize_input_path(raw_path)
        if not normalized:
            return None

        candidate = Path(normalized).expanduser()
        possible: List[Path] = []
        if candidate.is_file():
            possible.append(candidate)
        elif candidate.is_dir():
            possible.append(candidate / "matlab.exe")
            possible.append(candidate / "bin" / "matlab.exe")
            possible.extend(sorted(candidate.glob("R*/bin/matlab.exe"), reverse=True))

        for item in possible:
            if item.exists() and item.name.lower() == "matlab.exe":
                return str(item)
        return None

    def cli_preferences(self) -> Dict[str, Any]:
        resolved_path = ""
        if self.cli_config_mode == "custom":
            resolved_path = self._resolve_cli_candidate(self.cli_configured_path) or ""
        return {
            "mode": self.cli_config_mode,
            "configured_path": self.cli_configured_path,
            "resolved_path": resolved_path,
            "config_file": str(self.cli_config_path),
            "env_hint": self.cli_executable_hint,
        }

    def configure_cli(self, mode: str = "auto", executable_path: str = "") -> Dict[str, Any]:
        normalized_mode = str(mode or "auto").strip().lower()
        if normalized_mode not in {"auto", "custom"}:
            raise ValueError("MATLAB 路径模式仅支持 auto 或 custom。")

        normalized_path = self._normalize_input_path(executable_path)
        if normalized_mode == "custom":
            if not normalized_path:
                raise ValueError("手动指定模式下，请填写 MATLAB 安装目录或 matlab.exe 路径。")
            resolved = self._resolve_cli_candidate(normalized_path)
            if not resolved:
                raise ValueError("未识别到有效的 MATLAB 路径。可填写安装目录或 matlab.exe 完整路径。")
            self.cli_configured_path = normalized_path
        else:
            self.cli_configured_path = ""

        self.cli_config_mode = normalized_mode
        self._save_cli_config()
        self._reset_cli_cache()
        return self.cli_preferences()

    def _discover_matlab_executable(self) -> Optional[str]:
        if self.cli_config_mode == "custom":
            configured = self._resolve_cli_candidate(self.cli_configured_path)
            if configured:
                self._cli_source = "custom"
                return configured
            return None

        if self.cli_executable_hint and Path(self.cli_executable_hint).exists():
            self._cli_source = "env"
            return self.cli_executable_hint

        found_in_path = shutil.which("matlab")
        if found_in_path:
            self._cli_source = "path"
            return found_in_path

        candidate_paths = [
            Path("C:/Program Files/MATLAB"),
            Path("D:/MATLAB"),
            Path("D:/Matlab"),
            Path("C:/MATLAB"),
        ]
        for base in candidate_paths:
            if not base.exists():
                continue
            if base.is_file() and base.name.lower() == "matlab.exe":
                self._cli_source = "common"
                return str(base)
            for candidate in sorted(base.glob("R*/bin/matlab.exe"), reverse=True):
                if candidate.exists():
                    self._cli_source = "common"
                    return str(candidate)
            direct_candidate = base / "bin" / "matlab.exe"
            if direct_candidate.exists():
                self._cli_source = "common"
                return str(direct_candidate)
        return None

    def is_engine_available(self) -> bool:
        if self._engine_checked:
            return self._engine_available
        self._engine_checked = True
        try:
            import matlab.engine as matlab_engine  # type: ignore[import-not-found]

            self._engine_module = matlab_engine
            self._engine_available = True
            self._engine_error = ""
        except Exception as exc:
            self._engine_available = False
            self._engine_error = str(exc)
        return self._engine_available

    def is_cli_available(self) -> bool:
        if self._cli_checked:
            return self._cli_available
        self._cli_checked = True
        self._cli_source = ""
        executable = self._discover_matlab_executable()
        if executable:
            self._cli_available = True
            self._cli_executable = executable
            self._cli_error = ""
        else:
            self._cli_available = False
            if self.cli_config_mode == "custom":
                if self.cli_configured_path:
                    self._cli_error = "当前手动路径未指向有效的 MATLAB 可执行文件。"
                else:
                    self._cli_error = "当前为手动指定模式，请填写 MATLAB 安装目录或 matlab.exe 路径。"
            else:
                self._cli_error = "未找到 MATLAB 可执行文件（matlab.exe）。"
        return self._cli_available

    def is_available(self) -> bool:
        return self.is_engine_available() or self.is_cli_available()

    def status(self) -> Dict[str, Any]:
        engine_available = self.is_engine_available()
        cli_available = self.is_cli_available()
        mode = "none"
        if engine_available:
            mode = "engine"
        elif cli_available:
            mode = "cli"
        return {
            "available": bool(engine_available or cli_available),
            "mode": mode,
            "engine_available": engine_available,
            "engine_error": self._engine_error,
            "cli_available": cli_available,
            "cli_error": self._cli_error,
            "cli_executable": self._cli_executable,
            "cli_source": self._cli_source,
        }

    def get_last_error(self) -> str:
        return self._last_error

    def _ensure_engine(self) -> Any:
        if not self.is_engine_available():
            raise RuntimeError(self._engine_error or "MATLAB Engine for Python 不可用。")
        if self._engine is None:
            assert self._engine_module is not None
            # start_matlab() can block for a very long time; apply a timeout.
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self._engine_module.start_matlab)
                try:
                    self._engine = future.result(timeout=self.engine_startup_timeout)
                except FutureTimeoutError:
                    self._engine_available = False
                    self._engine_error = f"MATLAB Engine 启动超时（{self.engine_startup_timeout}s）。"
                    raise RuntimeError(self._engine_error)
            matlab_dir = self._matlab_dir()
            if matlab_dir.exists():
                self._engine.addpath(str(matlab_dir), nargout=0)
        return self._engine

    def _simulate_with_engine(self, params: InductionMotorParams) -> Dict[str, Any]:
        engine = self._ensure_engine()

        def _run_feval():
            return engine.feval(
                self.function_name,
                float(params.r2),
                float(params.x2),
                float(params.e2),
                float(params.s_min),
                float(params.s_max),
                float(params.n_points),
                nargout=5,
            )

        # Apply a timeout so a stuck feval does not block forever.
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_run_feval)
            try:
                slip, torque, max_slip, max_torque, start_torque = future.result(
                    timeout=self.engine_call_timeout
                )
            except FutureTimeoutError:
                raise RuntimeError(
                    f"MATLAB Engine 仿真调用超时（{self.engine_call_timeout}s），请检查 MATLAB 状态或切换到 Python 后端。"
                )

        return SimulationResult(
            backend="matlab-engine",
            slip=np.array(slip, dtype=float).flatten(),
            torque=np.array(torque, dtype=float).flatten(),
            max_slip=float(max_slip),
            max_torque=float(max_torque),
            start_torque=float(start_torque),
            notes=[f"已通过 MATLAB Engine 调用函数 {self.function_name}。"],
        ).to_dict()

    def _simulate_with_cli(self, params: InductionMotorParams) -> Dict[str, Any]:
        if not self.is_cli_available():
            raise RuntimeError(self._cli_error or "MATLAB CLI 不可用。")
        assert self._cli_executable
        matlab_dir = self._matlab_dir()
        if not matlab_dir.exists():
            raise RuntimeError(f"未找到 MATLAB 脚本目录：{matlab_dir}")

        temp_root = Path(__file__).resolve().parents[1] / ".runtime_tmp" / "matlab_cli_tmp"
        temp_root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            prefix="matlab_cli_",
            dir=str(temp_root),
            delete=False,
            encoding="utf-8",
        ) as temp_file:
            output_path = Path(temp_file.name)
        plot_output_path = output_path.with_suffix(".png")

        try:
            matlab_dir_expr = self._to_matlab_path(str(matlab_dir))
            output_expr = self._to_matlab_path(str(output_path))
            plot_expr = self._to_matlab_path(str(plot_output_path))
            batch_command = (
                f"addpath('{matlab_dir_expr}');"
                f"{self.cli_function_name}({float(params.r2)}, {float(params.x2)}, {float(params.e2)}, "
                f"{float(params.s_min)}, {float(params.s_max)}, {int(params.n_points)}, '{output_expr}', '{plot_expr}');"
            )
            completed = subprocess.run(
                [self._cli_executable, "-batch", batch_command],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=max(self.cli_timeout_seconds, 30),
                check=False,
            )
            if completed.returncode != 0:
                stderr_tail = (completed.stderr or completed.stdout or "").strip()
                if len(stderr_tail) > 300:
                    stderr_tail = stderr_tail[-300:]
                raise RuntimeError(f"MATLAB CLI 执行失败（code={completed.returncode}）：{stderr_tail}")

            if not output_path.exists():
                raise RuntimeError("MATLAB CLI 未生成结果文件。")

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            slip = np.array(payload.get("slip", []), dtype=float).flatten()
            torque = np.array(payload.get("torque", []), dtype=float).flatten()
            if slip.size == 0 or torque.size == 0:
                raise RuntimeError("MATLAB CLI 返回结果缺少 slip/torque 数据。")
            plot_data_url = _to_data_url(plot_output_path.read_bytes(), mime_type="image/png") if plot_output_path.exists() else None
            return SimulationResult(
                backend="matlab-cli",
                slip=slip,
                torque=torque,
                max_slip=float(payload.get("max_slip", float(slip[int(np.argmax(torque))]))),
                max_torque=float(payload.get("max_torque", float(np.max(torque)))),
                start_torque=float(payload.get("start_torque", float(torque[-1]))),
                notes=[f"已通过 MATLAB CLI 调用函数 {self.cli_function_name}。"],
                plot_image_data_url=plot_data_url,
                plot_caption="异步电机 T-s 曲线（MATLAB 绘制）",
            ).to_dict()
        finally:
            try:
                if output_path.exists():
                    output_path.unlink()
            except OSError:
                pass
            try:
                if plot_output_path.exists():
                    plot_output_path.unlink()
            except OSError:
                pass

    def simulate(self, params: InductionMotorParams) -> Dict[str, Any]:
        engine_error = ""
        if self.is_engine_available():
            try:
                return self._simulate_with_engine(params)
            except Exception as exc:
                engine_error = str(exc)

        if self.is_cli_available():
            try:
                cli_result = self._simulate_with_cli(params)
                if engine_error:
                    cli_result.setdefault("notes", [])
                    cli_result["notes"].append(f"MATLAB Engine 不可用，已切换 MATLAB CLI：{engine_error}")
                return cli_result
            except Exception as exc:
                cli_error = str(exc)
                self._last_error = f"MATLAB Engine 错误：{engine_error or 'N/A'}；MATLAB CLI 错误：{cli_error}"
                raise RuntimeError(self._last_error) from exc

        self._last_error = engine_error or self._engine_error or self._cli_error or "MATLAB 后端不可用。"
        raise RuntimeError(self._last_error)


REMOTE_CLIENT = RemoteSimulationClient()
MATLAB_ADAPTER = MatlabSimulationAdapter()


def simulate_torque_curve_python(params: InductionMotorParams) -> Dict[str, Any]:
    slip = np.linspace(params.s_min, params.s_max, params.n_points)
    torque = (slip * (params.e2 ** 2) * params.r2) / (params.r2 ** 2 + (slip * params.x2) ** 2)
    idx = int(np.argmax(torque))
    return SimulationResult(
        backend="python-analytical",
        slip=slip,
        torque=torque,
        max_slip=float(slip[idx]),
        max_torque=float(torque[idx]),
        start_torque=float(torque[-1]),
        notes=["当前使用的是教学级解析公式仿真，适合说明趋势。"],
        plot_image_data_url=_render_torque_plot_with_matplotlib(
            params=params,
            slip=slip,
            torque=torque,
            max_slip=float(slip[idx]),
            max_torque=float(torque[idx]),
        ),
        plot_caption="异步电机 T-s 曲线（本地回退绘制）",
    ).to_dict()


def _normalize_backend(backend: Optional[str]) -> str:
    return (backend or os.getenv("SIMULATION_BACKEND", DEFAULT_SIMULATION_BACKEND)).lower()


def _simulate_via_service(params: InductionMotorParams, preferred_backend: str) -> Dict[str, Any]:
    try:
        result = REMOTE_CLIENT.simulate(params, preferred_backend=preferred_backend)
        result.setdefault("notes", [])
        result["notes"].append("当前结果来自独立仿真服务。")
        return _attach_curve_plot(
            result,
            params,
            preferred_caption="异步电机 T-s 曲线（服务端结果绘制）",
        )
    except URLError as exc:
        raise RuntimeError(f"独立仿真服务不可达：{exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"独立仿真服务调用失败：{exc}") from exc


def _torque_at_slip(params: InductionMotorParams, slip: float) -> float:
    safe_slip = float(max(min(slip, 1.0), 1e-4))
    numerator = safe_slip * (params.e2 ** 2) * params.r2
    denominator = (params.r2 ** 2) + ((safe_slip * params.x2) ** 2)
    return float(numerator / max(denominator, 1e-12))


def simulate_parameter_sweep(
    params: InductionMotorParams,
    variable: str,
    start: float,
    stop: float,
    points: int,
    backend: str = "python",
    allow_service: bool = True,
) -> Dict[str, Any]:
    selected_variable = variable.lower()
    if selected_variable not in SUPPORTED_SWEEP_VARIABLES:
        raise ValueError(f"不支持的扫描变量：{variable}。支持 {sorted(SUPPORTED_SWEEP_VARIABLES)}")

    sweep_points = int(max(3, min(points, 16)))
    sweep_start = float(start)
    sweep_stop = float(stop)
    if sweep_start == sweep_stop:
        sweep_stop = sweep_start + 0.01

    values = np.linspace(min(sweep_start, sweep_stop), max(sweep_start, sweep_stop), sweep_points)
    max_torque_series: List[float] = []
    max_slip_series: List[float] = []
    start_torque_series: List[float] = []
    backends_used: List[str] = []
    notes: List[str] = [
        f"参数扫描变量：{selected_variable}，样本点：{sweep_points}。",
    ]

    for value in values:
        local_params = replace(params, **{selected_variable: float(value)})
        result = simulate_torque_curve(local_params, backend=backend, allow_service=allow_service)
        backends_used.append(str(result.get("backend", "unknown")))
        max_torque_series.append(float(result["max_torque"]))
        max_slip_series.append(float(result["max_slip"]))
        start_torque_series.append(float(result["start_torque"]))

    dominant_backend = backends_used[-1] if backends_used else backend
    return {
        "scenario": "parameter_sweep",
        "backend": dominant_backend,
        "sweep_variable": selected_variable,
        "sweep_values": values,
        "series": {
            "max_torque": np.array(max_torque_series, dtype=float),
            "max_slip": np.array(max_slip_series, dtype=float),
            "start_torque": np.array(start_torque_series, dtype=float),
        },
        "notes": notes,
        "summary": (
            f"完成 {selected_variable} 扫描，共 {sweep_points} 组。"
            f"最大转矩范围约 {min(max_torque_series):.3f} 到 {max(max_torque_series):.3f}。"
        ),
    }


def simulate_operating_point_compare(params: InductionMotorParams, slips: Optional[List[float]] = None) -> Dict[str, Any]:
    slip_candidates = slips or [0.05, 0.1, 0.2, 0.3, 0.5, 1.0]
    sanitized = sorted({float(max(min(item, 1.0), 1e-4)) for item in slip_candidates})[:16]
    points = [{"slip": slip, "torque": _torque_at_slip(params, slip)} for slip in sanitized]
    return {
        "scenario": "operating_point_compare",
        "backend": "python-analytical",
        "operating_points": points,
        "notes": ["当前工况点比较使用解析模型，适合教学展示工况趋势。"],
        "summary": f"已完成 {len(points)} 个滑差工况点比较。",
    }


def simulate_startup_assessment(
    params: InductionMotorParams,
    backend: str = "auto",
    allow_service: bool = True,
) -> Dict[str, Any]:
    curve = simulate_torque_curve(params, backend=backend, allow_service=allow_service)
    max_torque = float(curve["max_torque"])
    start_torque = float(curve["start_torque"])
    ratio = start_torque / max(max_torque, 1e-12)

    if ratio >= 0.8:
        level = "强"
        suggestion = "启动能力较强，适合较重载起动场景。"
    elif ratio >= 0.55:
        level = "中"
        suggestion = "启动能力中等，建议结合启动电流与热约束综合评估。"
    else:
        level = "弱"
        suggestion = "启动能力偏弱，建议优化转子参数或增加启动策略。"

    notes = list(curve.get("notes", []))
    notes.append(f"启动转矩/最大转矩比值约为 {ratio:.3f}。")
    return {
        "scenario": "startup_assessment",
        "backend": curve.get("backend", backend),
        "max_torque": max_torque,
        "max_slip": float(curve["max_slip"]),
        "start_torque": start_torque,
        "startup_ratio": ratio,
        "assessment": level,
        "suggestion": suggestion,
        "notes": notes,
    }


def simulate_by_scenario(
    scenario: str,
    params: InductionMotorParams,
    backend: str = "auto",
    options: Optional[Dict[str, Any]] = None,
    allow_service: bool = True,
) -> Dict[str, Any]:
    selected = scenario.lower().strip()
    payload = options or {}

    if selected == "torque_curve":
        result = simulate_torque_curve(params, backend=backend, allow_service=allow_service)
        result["scenario"] = "torque_curve"
        return result

    if selected == "parameter_sweep":
        variable = str(payload.get("sweep_variable", "r2"))
        start = float(payload.get("sweep_start", 0.2))
        stop = float(payload.get("sweep_stop", 1.2))
        points = int(payload.get("sweep_points", 6))
        return simulate_parameter_sweep(
            params=params,
            variable=variable,
            start=start,
            stop=stop,
            points=points,
            backend=backend,
            allow_service=allow_service,
        )

    if selected == "operating_point_compare":
        slips = payload.get("slip_points")
        if isinstance(slips, list):
            parsed = [float(item) for item in slips]
        else:
            parsed = None
        return simulate_operating_point_compare(params, slips=parsed)

    if selected == "startup_assessment":
        return simulate_startup_assessment(params=params, backend=backend, allow_service=allow_service)

    raise ValueError(f"不支持的仿真场景：{scenario}。支持 {sorted(SUPPORTED_SCENARIOS)}")


def simulate_torque_curve(
    params: InductionMotorParams,
    backend: Optional[str] = None,
    allow_service: bool = True,
) -> Dict[str, Any]:
    selected_backend = _normalize_backend(backend)

    if selected_backend == "service":
        if allow_service:
            return _simulate_via_service(params, preferred_backend="auto")
        fallback = simulate_torque_curve_python(params)
        fallback["notes"].append("当前上下文禁用了 service 路由，已回退到本地 Python 仿真。")
        return fallback

    if selected_backend == "matlab":
        try:
            matlab_result = MATLAB_ADAPTER.simulate(params)
            return _attach_curve_plot(matlab_result, params, preferred_caption="异步电机 T-s 曲线（MATLAB 绘制）")
        except Exception as local_exc:
            if allow_service:
                try:
                    service_result = _simulate_via_service(params, preferred_backend="matlab")
                    service_result.setdefault("notes", [])
                    service_result["notes"].append(f"本地 MATLAB Engine 不可用，已切换到独立仿真服务 MATLAB 后端：{local_exc}")
                    return service_result
                except Exception as service_exc:
                    fallback = simulate_torque_curve_python(params)
                    fallback["notes"].append(
                        f"MATLAB 后端不可用：本地失败（{local_exc}），服务失败（{service_exc}），已回退到 Python 解析仿真。"
                    )
                    return fallback
            fallback = simulate_torque_curve_python(params)
            fallback["notes"].append(f"MATLAB 后端不可用，已回退到 Python 解析仿真：{local_exc}")
            return fallback

    if selected_backend == "auto":
        # Bound the total time spent attempting MATLAB so the user doesn't
        # wait forever.  The per-operation timeouts inside the adapter are the
        # primary safeguard; this is a catch-all safety net.
        auto_matlab_timeout = int(float(os.getenv("AUTO_MATLAB_TIMEOUT", "70")))
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(MATLAB_ADAPTER.simulate, params)
                matlab_result = future.result(timeout=auto_matlab_timeout)
            matlab_result.setdefault("notes", [])
            matlab_result["notes"].append("自动后端：已使用本地 MATLAB 计算。")
            return _attach_curve_plot(matlab_result, params, preferred_caption="异步电机 T-s 曲线（MATLAB 绘制）")
        except FutureTimeoutError:
            fallback = simulate_torque_curve_python(params)
            fallback["notes"].append(
                f"自动后端：MATLAB 整体执行超时（{auto_matlab_timeout}s），已切换到本地 Python 仿真。"
            )
            return fallback
        except Exception as local_exc:
            fallback = simulate_torque_curve_python(params)
            fallback["notes"].append(f"自动后端：MATLAB 暂时不可用，已切换到本地 Python 仿真：{local_exc}")
            return fallback

    return simulate_torque_curve_python(params)


def explain_curve_text(result: Dict[str, Any]) -> str:
    backend = result.get("backend", "unknown")
    return (
        f"当前仿真后端：{backend}。\n\n"
        f"最大转矩大约出现在滑差 \\( s={result['max_slip']:.3f} \\) 附近，"
        f"最大相对转矩约为 \\( {result['max_torque']:.3f} \\)。\n\n"
        f"当滑差从较小值增大时，转矩通常先上升后下降；"
        f"启动点的相对转矩约为 \\( {result['start_torque']:.3f} \\)。\n\n"
        "独立仿真服务方案适合后续接入 MATLAB / Simulink 或部署成正式 Web 后端。"
    )
