from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

APP_TITLE = "AITeach 电机学智能学习平台"
APP_SUBTITLE = "结题演示版：图像解题、知识库问答、参数仿真、错题本"

DEFAULT_DB_PATH = str(BASE_DIR / "data" / "wrong_questions.db")
DEFAULT_KB_PATH = str(BASE_DIR / "knowledge_base")
DEFAULT_CACHE_DIR = str(BASE_DIR / ".kb_cache")

DEFAULT_TEXT_MODEL = "qwen3-max"
DEFAULT_VISION_MODEL = "qwen3-vl-plus"
DEFAULT_EMBEDDING_MODEL = "text-embedding-v1"
DEFAULT_QA_MODEL = "qwen3-max"
DEFAULT_WRONGBOOK_REASONING_MODEL = "qwen3-max"
DEFAULT_SIM_COACH_MODEL = "qwen-max-latest"
# DashScope 文本代码模型（稳定别名）。当前可按需切换为具体快照版本。
DEFAULT_SIM_DESIGN_MODEL = "qwen3-coder-plus"
DEFAULT_SIMULATION_BACKEND = "auto"
DEFAULT_MATLAB_FUNCTION = "aiteach_motor_torque_curve"
DEFAULT_SIMULATION_SERVICE_URL = "http://127.0.0.1:8000/api/simulate/motor"
DEFAULT_SIMULATION_SERVICE_HEALTH_URL = "http://127.0.0.1:8000/api/health"

SUPPORTED_IMAGE_TYPES = ["png", "jpg", "jpeg", "bmp"]
