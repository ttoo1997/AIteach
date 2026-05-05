import requests

url = "http://127.0.0.1:8000/api/simulate/lab-run"
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
    "backend": "python"
}

try:
    response = requests.post(url, json=payload)
    data = response.json()
    print("Keys in result:", data.keys())
    print("Plot URL exists:", "plot_image_data_url" in data)
    if "plot_image_data_url" in data:
        url = data["plot_image_data_url"]
        print("Plot URL length:", len(url))
        print("Plot URL starts with:", url[:30])
    if "key_metrics" in data:
        print("max_slip:", data["key_metrics"]["max_slip"])
        
except Exception as e:
    print("Error:", e)
