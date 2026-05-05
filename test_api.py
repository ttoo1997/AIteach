import requests

url = "http://127.0.0.1:8090/api/simulate/lab-run"
payload = {
    "lab_id": "induction_motor_torque_slip",
    "params": {
        "r2": 0.5,
        "x2": 1.2,
        "e2": 220.0,
        "s_min": 0.01,
        "s_max": 1.0,
        "n_points": 200
    },
    "backend": "matlab"
}

try:
    response = requests.post(url, json=payload, timeout=60)
    data = response.json()
    print("Status:", response.status_code)
    print("Keys in result:", data.keys())
    print("Plot URL exists:", "plot_image_data_url" in data)
    if "plot_image_data_url" in data:
        url_val = data["plot_image_data_url"]
        print("Plot URL length:", len(url_val))
        print("Plot URL starts with:", url_val[:30])
        if len(url_val) == 0:
            print("Plot URL IS EMPTY STRING")
except Exception as e:
    print("Error:", e)
