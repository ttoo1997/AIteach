import sys
import os
from streamlit.web import cli as stcli


def resolve_path(path):
    # 处理打包后的路径问题
    if getattr(sys, "frozen", False):
        basedir = sys._MEIPASS
    else:
        basedir = os.path.dirname(__file__)
    return os.path.join(basedir, path)


if __name__ == "__main__":
    # 1. 设置你的主程序文件名 (假设你的入口文件叫 main.py)
    app_path = resolve_path("UI0.py")

    # 2. 伪造命令行参数
    # 等同于在命令行执行：streamlit run main.py --global.developmentMode=false
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--global.developmentMode=false",
    ]

    # 3. 启动 Streamlit
    sys.exit(stcli.main())