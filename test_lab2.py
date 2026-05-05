from services.fixed_simulation_lab_service import FIXED_SIM_LAB_SERVICE

payload = {
    "r2": 0.5,
    "x2": 1.2,
    "e2": 220.0,
    "s_min": 0.01,
    "s_max": 1.0,
    "n_points": 200
}

try:
    result = FIXED_SIM_LAB_SERVICE.run_lab("induction_motor_torque_slip", payload, "matlab")
    print("Keys:", result.keys())
    print("Has plot:", "plot_image_data_url" in result)
    if "plot_image_data_url" in result:
        print("Length:", len(result["plot_image_data_url"]))
except Exception as e:
    import traceback
    traceback.print_exc()
