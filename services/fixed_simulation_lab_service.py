import math
from copy import deepcopy
from typing import Any, Dict, List

import numpy as np

from simulation.motor_simulator import InductionMotorParams, simulate_torque_curve


LAB_LIBRARY: List[Dict[str, Any]] = [
    {
        "id": "dc_motor_torque_speed",
        "machine_type": "直流电机（并励）",
        "title": "直流电机：T-n 机械特性实验",
        "subtitle": "观察负载转矩变化对电机转速和电枢电流的影响",
        "description": "采用并励直流电机近似模型，输出转矩-转速曲线与电枢电流变化。",
        "circuit_image": "/assets/sim-lab-dc-circuit.png",
        "curve_image": "/assets/sim-lab-dc-curve.svg",
        "tutorial_steps": [
            "先用默认参数运行，记录空载转速和堵转转矩。",
            "逐步增大负载转矩，观察转速是否近似线性下降。",
            "结合电枢压降 Va - Ia*Ra，解释转速变化原因。",
        ],
        "focus_points": ["机械特性斜率", "电枢电流增长", "堵转工况"],
        "parameters": [
            {"key": "va_v", "label": "电枢电压 Va (V)", "type": "number", "default": 220.0, "min": 50.0, "max": 600.0, "step": 1.0},
            {"key": "ra_ohm", "label": "电枢电阻 Ra (Ω)", "type": "number", "default": 0.8, "min": 0.05, "max": 5.0, "step": 0.01},
            {"key": "k_phi", "label": "反电势常数 kΦ", "type": "number", "default": 1.2, "min": 0.2, "max": 5.0, "step": 0.01},
            {"key": "torque_min_nm", "label": "最小负载转矩 (N·m)", "type": "number", "default": 0.0, "min": 0.0, "max": 300.0, "step": 0.5},
            {"key": "torque_max_nm", "label": "最大负载转矩 (N·m)", "type": "number", "default": 120.0, "min": 5.0, "max": 600.0, "step": 1.0},
            {"key": "n_points", "label": "采样点数", "type": "number", "default": 40, "min": 20, "max": 240, "step": 1},
        ],
    },
    {
        "id": "transformer_regulation_efficiency",
        "machine_type": "变压器",
        "title": "变压器：电压调整率与效率实验",
        "subtitle": "观察负载率与功率因数对输出电压和效率的影响",
        "description": "基于等效电路近似，计算不同负载率下二次侧电压和效率曲线。",
        "circuit_image": "/assets/sim-lab-transformer-circuit.png",
        "curve_image": "/assets/sim-lab-transformer-curve.svg",
        "tutorial_steps": [
            "先保持功率因数不变，扫描负载率 0~1.2。",
            "重点对比额定负载点附近的电压调整率。",
            "再修改功率因数，观察效率峰值和电压降变化。",
        ],
        "focus_points": ["电压调整率", "铜耗与铁耗分配", "效率峰值负载率"],
        "parameters": [
            {"key": "v2_rated_v", "label": "二次额定电压 V2 (V)", "type": "number", "default": 220.0, "min": 50.0, "max": 1000.0, "step": 1.0},
            {"key": "i2_rated_a", "label": "二次额定电流 I2 (A)", "type": "number", "default": 20.0, "min": 1.0, "max": 500.0, "step": 0.5},
            {"key": "r_eq_ohm", "label": "等效电阻 Req (Ω)", "type": "number", "default": 0.18, "min": 0.001, "max": 10.0, "step": 0.001},
            {"key": "x_eq_ohm", "label": "等效电抗 Xeq (Ω)", "type": "number", "default": 0.42, "min": 0.001, "max": 20.0, "step": 0.001},
            {"key": "p_core_w", "label": "铁耗 Pcore (W)", "type": "number", "default": 120.0, "min": 1.0, "max": 5000.0, "step": 1.0},
            {"key": "p_cu_full_w", "label": "满载铜耗 Pcu,FL (W)", "type": "number", "default": 220.0, "min": 1.0, "max": 8000.0, "step": 1.0},
            {"key": "power_factor", "label": "负载功率因数 cosφ", "type": "number", "default": 0.8, "min": 0.2, "max": 1.0, "step": 0.01},
            {"key": "load_max_pu", "label": "最大负载率 (p.u.)", "type": "number", "default": 1.2, "min": 0.6, "max": 2.0, "step": 0.05},
            {"key": "n_points", "label": "采样点数", "type": "number", "default": 50, "min": 20, "max": 240, "step": 1},
        ],
    },
    {
        "id": "induction_motor_torque_slip",
        "machine_type": "异步电机",
        "title": "异步电机：T-s 特性实验",
        "subtitle": "观察转矩随滑差变化规律并识别峰值点",
        "description": "使用异步电机等效电路参数生成转矩-滑差曲线。",
        "circuit_image": "/assets/sim-induction-circuit.png",
        "curve_image": "/assets/sim-torque-map.svg",
        "tutorial_steps": [
            "运行默认参数，记录 max_torque、max_slip 与 start_torque。",
            "增大 R2 后再次运行，比较峰值点位置变化。",
            "解释为何启动点 s=1 不是全程最大转矩点。",
        ],
        "focus_points": ["最大转矩点", "启动转矩", "R2 对峰值位置影响"],
        "parameters": [
            {"key": "r2", "label": "转子电阻 R2", "type": "number", "default": 0.5, "min": 0.05, "max": 3.0, "step": 0.01},
            {"key": "x2", "label": "转子漏抗 X2", "type": "number", "default": 1.2, "min": 0.05, "max": 6.0, "step": 0.01},
            {"key": "e2", "label": "转子感应电势 E2 (V)", "type": "number", "default": 220.0, "min": 20.0, "max": 1200.0, "step": 1.0},
            {"key": "s_min", "label": "最小滑差 s_min", "type": "number", "default": 0.01, "min": 0.001, "max": 0.4, "step": 0.001},
            {"key": "s_max", "label": "最大滑差 s_max", "type": "number", "default": 1.0, "min": 0.1, "max": 1.0, "step": 0.01},
            {"key": "n_points", "label": "采样点数", "type": "number", "default": 200, "min": 40, "max": 2000, "step": 1},
        ],
    },
    {
        "id": "synchronous_motor_power_angle",
        "machine_type": "同步电机",
        "title": "同步电机：P-δ 功角特性实验",
        "subtitle": "观察电磁功率随功角变化规律并识别稳定运行区",
        "description": "根据同步机功角方程，输出 P-δ 曲线并定位最大电磁功率点。",
        "circuit_image": "/assets/sim-lab-synchronous-circuit.png",
        "curve_image": "/assets/sim-lab-synchronous-curve.svg",
        "tutorial_steps": [
            "先用默认参数运行，找到功角约 90° 附近的峰值。",
            "改变 Xs 或 E，比较 Pmax 的变化方向。",
            "结合稳定运行要求，解释为何通常不在大功角长期运行。",
        ],
        "focus_points": ["功角稳定性", "Pmax 位置", "E/Xs 对曲线影响"],
        "parameters": [
            {"key": "e_phase_v", "label": "内部电势 E (V/相)", "type": "number", "default": 260.0, "min": 50.0, "max": 800.0, "step": 1.0},
            {"key": "v_phase_v", "label": "端电压 V (V/相)", "type": "number", "default": 220.0, "min": 50.0, "max": 800.0, "step": 1.0},
            {"key": "xs_ohm", "label": "同步电抗 Xs (Ω)", "type": "number", "default": 1.6, "min": 0.05, "max": 15.0, "step": 0.01},
            {"key": "delta_max_deg", "label": "最大功角 δmax (°)", "type": "number", "default": 120.0, "min": 60.0, "max": 175.0, "step": 1.0},
            {"key": "n_points", "label": "采样点数", "type": "number", "default": 80, "min": 30, "max": 240, "step": 1},
        ],
    },
]


LAB_INDEX = {row["id"]: row for row in LAB_LIBRARY}


def _to_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except Exception:
        parsed = default
    parsed = max(minimum, min(maximum, parsed))
    return float(parsed)


def _to_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(float(value))
    except Exception:
        parsed = default
    parsed = max(minimum, min(maximum, parsed))
    return int(parsed)


class FixedSimulationLabService:
    def list_labs(self) -> List[Dict[str, Any]]:
        return [deepcopy(item) for item in LAB_LIBRARY]

    def get_lab(self, lab_id: str) -> Dict[str, Any]:
        key = str(lab_id or "").strip().lower()
        row = LAB_INDEX.get(key)
        if not row:
            raise ValueError(f"未找到实验：{lab_id}")
        return deepcopy(row)

    def normalize_params(self, lab_id: str, raw_params: Dict[str, Any]) -> Dict[str, Any]:
        lab = self.get_lab(lab_id)
        normalized: Dict[str, Any] = {}
        for field in lab.get("parameters", []):
            key = field["key"]
            value = raw_params.get(key, field.get("default"))
            if field.get("type") == "number":
                if float(field.get("step", 1)).is_integer() and key == "n_points":
                    normalized[key] = _to_int(
                        value,
                        int(field.get("default", 10)),
                        int(field.get("min", 1)),
                        int(field.get("max", 10000)),
                    )
                else:
                    normalized[key] = _to_float(
                        value,
                        float(field.get("default", 0.0)),
                        float(field.get("min", -1e9)),
                        float(field.get("max", 1e9)),
                    )
            else:
                normalized[key] = str(value).strip()
        return normalized

    def run_lab(self, lab_id: str, params: Dict[str, Any], backend: str = "auto") -> Dict[str, Any]:
        key = str(lab_id or "").strip().lower()
        normalized = self.normalize_params(key, params)
        if key == "dc_motor_torque_speed":
            return self._run_dc_motor(normalized)
        if key == "transformer_regulation_efficiency":
            return self._run_transformer(normalized)
        if key == "induction_motor_torque_slip":
            return self._run_induction(normalized, backend=backend)
        if key == "synchronous_motor_power_angle":
            return self._run_synchronous(normalized)
        raise ValueError(f"不支持的实验：{lab_id}")

    def _base_result(self, lab_id: str, backend: str) -> Dict[str, Any]:
        lab = self.get_lab(lab_id)
        return {
            "ok": True,
            "lab_id": lab["id"],
            "title": lab["title"],
            "machine_type": lab["machine_type"],
            "backend": backend,
            "series": {},
            "key_metrics": {},
            "notes": [],
            "report_markdown": "",
        }

    def _run_dc_motor(self, p: Dict[str, Any]) -> Dict[str, Any]:
        va = float(p["va_v"])
        ra = max(float(p["ra_ohm"]), 1e-6)
        k_phi = max(float(p["k_phi"]), 1e-6)
        t_min = float(p["torque_min_nm"])
        t_max = max(float(p["torque_max_nm"]), t_min + 1e-3)
        n_points = int(p["n_points"])

        torque = np.linspace(t_min, t_max, n_points, dtype=float)
        ia = torque / k_phi
        omega = np.maximum((va - ia * ra) / k_phi, 0.0)
        speed_rpm = omega * 60.0 / (2.0 * math.pi)

        stall_torque = va * k_phi / ra
        no_load_speed_rpm = (va / k_phi) * 60.0 / (2.0 * math.pi)

        result = self._base_result("dc_motor_torque_speed", backend="python-analytic")
        result["series"] = {
            "torque_nm": torque.tolist(),
            "speed_rpm": speed_rpm.tolist(),
            "armature_current_a": ia.tolist(),
        }
        result["key_metrics"] = {
            "no_load_speed_rpm": float(no_load_speed_rpm),
            "stall_torque_nm": float(stall_torque),
            "max_armature_current_a": float(np.max(ia)),
        }
        result["notes"] = [
            "模型：并励直流电机近似模型（磁通恒定）。",
            "关系：T≈kΦIa，ω≈(Va-IaRa)/kΦ。",
        ]
        result["report_markdown"] = (
            "### 直流电机 T-n 实验结果\n"
            f"- 空载转速约：**{no_load_speed_rpm:.2f} rpm**\n"
            f"- 估算堵转转矩约：**{stall_torque:.2f} N·m**\n"
            f"- 最大电枢电流约：**{np.max(ia):.2f} A**\n"
            "- 结论：负载转矩上升时，电枢电流增大，电枢压降加重，转速下降。"
        )
        return result

    def _run_transformer(self, p: Dict[str, Any]) -> Dict[str, Any]:
        v2_rated = float(p["v2_rated_v"])
        i2_rated = max(float(p["i2_rated_a"]), 1e-6)
        r_eq = float(p["r_eq_ohm"])
        x_eq = float(p["x_eq_ohm"])
        p_core = float(p["p_core_w"])
        p_cu_full = float(p["p_cu_full_w"])
        pf = max(min(float(p["power_factor"]), 1.0), 0.2)
        load_max = max(float(p["load_max_pu"]), 0.1)
        n_points = int(p["n_points"])

        load_pu = np.linspace(0.0, load_max, n_points, dtype=float)
        i2 = load_pu * i2_rated
        sin_phi = math.sqrt(max(0.0, 1.0 - pf * pf))
        v_drop = i2 * (r_eq * pf + x_eq * sin_phi)
        v2 = np.maximum(v2_rated - v_drop, 0.0)
        p_out = v2 * i2 * pf
        p_cu = p_cu_full * np.square(load_pu)
        eta = np.divide(
            p_out,
            np.maximum(p_out + p_core + p_cu, 1e-9),
            out=np.zeros_like(p_out),
            where=(p_out + p_core + p_cu) > 0,
        )
        eta_percent = eta * 100.0

        i_full = i2_rated
        v_fl = max(v2_rated - i_full * (r_eq * pf + x_eq * sin_phi), 1e-6)
        regulation_pct = (v2_rated - v_fl) / v_fl * 100.0
        idx_eta = int(np.argmax(eta_percent))

        result = self._base_result("transformer_regulation_efficiency", backend="python-analytic")
        result["series"] = {
            "load_pu": load_pu.tolist(),
            "v2_v": v2.tolist(),
            "efficiency_percent": eta_percent.tolist(),
            "output_power_w": p_out.tolist(),
        }
        result["key_metrics"] = {
            "regulation_percent_at_full_load": float(regulation_pct),
            "peak_efficiency_percent": float(eta_percent[idx_eta]),
            "peak_efficiency_load_pu": float(load_pu[idx_eta]),
        }
        result["notes"] = [
            "模型：变压器等效电路近似（二次侧折算）。",
            "电压调整率按额定电压与满载端电压估算。",
        ]
        result["report_markdown"] = (
            "### 变压器 调整率-效率实验结果\n"
            f"- 满载电压调整率约：**{regulation_pct:.2f}%**\n"
            f"- 峰值效率约：**{eta_percent[idx_eta]:.2f}%**（负载率约 **{load_pu[idx_eta]:.2f} p.u.**）\n"
            f"- 当前设定功率因数：**{pf:.2f}**\n"
            "- 结论：随负载上升，铜耗按平方增长，效率先升后趋缓；端电压受等效阻抗压降影响。"
        )
        return result

    def _run_induction(self, p: Dict[str, Any], backend: str = "auto") -> Dict[str, Any]:
        params = InductionMotorParams(
            r2=float(p["r2"]),
            x2=float(p["x2"]),
            e2=float(p["e2"]),
            s_min=float(p["s_min"]),
            s_max=float(p["s_max"]),
            n_points=int(p["n_points"]),
        )
        base = simulate_torque_curve(params=params, backend=backend)
        slip = np.array(base.get("slip", []), dtype=float).flatten()
        torque = np.array(base.get("torque", []), dtype=float).flatten()

        result = self._base_result("induction_motor_torque_slip", backend=str(base.get("backend", backend)))
        result["series"] = {
            "slip": slip.tolist(),
            "torque": torque.tolist(),
        }
        result["key_metrics"] = {
            "max_slip": float(base.get("max_slip", 0.0)),
            "max_torque": float(base.get("max_torque", 0.0)),
            "start_torque": float(base.get("start_torque", 0.0)),
        }

        # Always attach a T-s curve plot.  If the base result already has one
        # (e.g. from MATLAB or Python analytical), keep it; otherwise generate
        # one from the series data via matplotlib so the front-end always shows
        # a chart.
        if base.get("plot_image_data_url"):
            result["plot_image_data_url"] = base["plot_image_data_url"]
            result["plot_caption"] = base.get("plot_caption", "异步电机 T-s 曲线")
        # Fallback: generate chart from the returned slip/torque arrays using
        # matplotlib directly.  The previous code called _attach_curve_plot()
        # which looks for slip/torque at the *top level* of the dict, but
        # _run_induction stores them under result["series"], so the function
        # silently returned without generating a plot.
        if not result.get("plot_image_data_url") and slip.size > 0 and torque.size > 0:
            from simulation.motor_simulator import _render_torque_plot_with_matplotlib
            max_slip_val = float(base.get("max_slip", slip[int(np.argmax(torque))]))
            max_torque_val = float(base.get("max_torque", np.max(torque)))
            result["plot_image_data_url"] = _render_torque_plot_with_matplotlib(
                params=params,
                slip=slip,
                torque=torque,
                max_slip=max_slip_val,
                max_torque=max_torque_val,
            )
            result["plot_caption"] = "异步电机 T-s 曲线（本地绘制）"

        max_slip = result["key_metrics"]["max_slip"]
        max_torque = result["key_metrics"]["max_torque"]
        start_torque = result["key_metrics"]["start_torque"]
        torque_ratio = start_torque / max(max_torque, 1e-9)
        result["notes"] = [
            f"当滑差从较小值逐步增大时，转矩通常先上升后下降，峰值出现在 s≈{max_slip:.4f} 附近。",
            f"当前启动转矩约为最大转矩的 {torque_ratio:.2%}，可据此判断直接起动时的起动能力。",
            "若继续增大转子电阻，峰值位置通常会向更大滑差方向移动，便于观察参数对特性的影响。",
        ]
        result["report_markdown"] = (
            "### 异步电机 T-s 实验结果\n"
            f"- 最大转矩：**{result['key_metrics']['max_torque']:.2f}**\n"
            f"- 峰值对应滑差：**{result['key_metrics']['max_slip']:.4f}**\n"
            f"- 启动转矩（s=1）：**{result['key_metrics']['start_torque']:.2f}**\n"
            "- 结论：T-s 曲线通常先升后降，峰值点位置与转子参数相关。"
        )
        return result

    def _run_synchronous(self, p: Dict[str, Any]) -> Dict[str, Any]:
        e = float(p["e_phase_v"])
        v = float(p["v_phase_v"])
        xs = max(float(p["xs_ohm"]), 1e-6)
        delta_max = max(float(p["delta_max_deg"]), 10.0)
        n_points = int(p["n_points"])

        delta_deg = np.linspace(0.0, delta_max, n_points, dtype=float)
        delta_rad = np.deg2rad(delta_deg)
        power_w = 3.0 * e * v / xs * np.sin(delta_rad)
        power_kw = power_w / 1000.0

        idx = int(np.argmax(power_kw))
        pmax_kw = float(power_kw[idx])
        delta_at_pmax = float(delta_deg[idx])

        result = self._base_result("synchronous_motor_power_angle", backend="python-analytic")
        result["series"] = {
            "delta_deg": delta_deg.tolist(),
            "power_kw": power_kw.tolist(),
        }
        result["key_metrics"] = {
            "max_power_kw": pmax_kw,
            "delta_at_max_power_deg": delta_at_pmax,
            "static_stability_margin_deg": float(max(0.0, 90.0 - delta_at_pmax)),
        }
        result["notes"] = [
            "模型：P≈3EV/Xs·sinδ（忽略电阻）。",
            "稳定运行通常要求功角保留裕度，不建议长期逼近大功角。",
        ]
        result["report_markdown"] = (
            "### 同步电机 P-δ 实验结果\n"
            f"- 最大电磁功率约：**{pmax_kw:.2f} kW**\n"
            f"- 峰值对应功角约：**{delta_at_pmax:.2f}°**\n"
            f"- 静稳裕度参考：**{max(0.0, 90.0 - delta_at_pmax):.2f}°**\n"
            "- 结论：P 随 δ 增大先升后降，功角过大将降低稳定裕度。"
        )
        return result


FIXED_SIM_LAB_SERVICE = FixedSimulationLabService()
