# AITeach 项目启动与使用说明

AITeach 是一个面向电机学课程学习的 Web 端教学辅助原型，功能包括：
- AI 图像与文本解题
- 电机学知识库问答
- 四组基础参数仿真实验与 AI 仿真工坊
- 错题本与 AI 错题教练

## 1. 快速一键启动（推荐）

首次使用前，请先确认电脑已安装 `Python 3.10+`，并且已添加至系统环境变量。

1. 双击项目根目录下的 `start_aiteach.bat`（或 `start_aiteach.ps1`）。
2. 首次启动会自动完成以下步骤：
   - 创建 `.venv` 虚拟环境并安装 `requirements.txt` 依赖。
   - 自动生成 `.env.local` 配置文件模板。
   - 启动主 Web 服务并自动打开浏览器。

默认访问地址：[http://127.0.0.1:8090/](http://127.0.0.1:8090/)
如需停止服务，请双击：`stop_aiteach.bat`（或 `stop_aiteach.ps1`）。

## 2. API 密钥配置

首次启动后，请打开项目根目录下的 `.env.local` 文件，至少填写阿里云千问大模型的 API Key：

```env
DASHSCOPE_API_KEY=你的千问_API_Key
```
*(提示：若不填写此项，所有的 AI 解题、问答、错题分析和仿真助手均将无法使用。)*

其他可选项（无需强制修改）：
```env
SIMULATION_BACKEND=auto
WRONG_QUESTION_DB=data/wrong_questions.db
MATLAB_EXE_PATH=
QWEN_SIM_COACH_MODEL=qwen-max-latest
```

## 3. 手动启动与独立仿真服务

如果你不想使用 BAT 脚本，可以在终端中手动执行启动：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m uvicorn api.web_app:app --host 127.0.0.1 --port 8090
```

### 独立仿真服务部署（进阶）
系统支持将仿真计算层剥离出主 Web 服务独立运行，适用于在特定的计算节点（如具备 MATLAB 环境的服务器）上单独提供仿真支持：
```powershell
.\.venv\Scripts\python -m uvicorn api.simulation_api:app --host 127.0.0.1 --port 8000
```
主应用可以通过配置调用此独立服务进行仿真解算。

## 4. MATLAB / Simulink 仿真配置说明

AITeach 的电机学仿真支持基于公式解析的 Python 引擎与高保真 MATLAB 引擎。

如果你的电脑安装了 MATLAB，我们强烈推荐启用它：
1. 打开浏览器进入 AITeach 的“参数仿真”页面。
2. 在左侧的 `MATLAB CLI 路径` 配置块中，选择 `自动探测（推荐）`，或选择 `手动指定` 并填入 MATLAB 根目录（例如 `D:\Program Files\MATLAB\R2023b`）或 `matlab.exe` 的绝对路径。
3. 此配置仅保存在你的浏览器本地，不污染代码。

**注意**：即使本地并未安装 MATLAB，系统也会自动降级回退到内置的 Python 公式引擎，不会阻断核心实验（转矩曲线、参数扫描等）的展示。

### 面向开发者的 MATLAB 拓展
系统默认调用 `matlab/aiteach_motor_torque_curve.m` 脚本。如果后续想要升级到真实的 Simulink 高保真模型，只需要替换此函数的内部逻辑：
- 在脚本内 `sim(...)` 加载 Simulink 模型。
- 将输出结果解析为 JSON。
AITeach Web 端的接口无需作任何修改即可无缝兼容高级仿真结果。

## 5. 项目功能验收与测试流程

为确认项目已完整启动并正常工作，建议按以下流程进行验收测试：

1. **AI 解题**：上传一张包含公式的试卷图片或直接输入题目文字，测试 OCR 与极速解答能力，确认带空格的 LaTeX 公式和 Markdown 表格均能正确渲染显示。
2. **知识问答**：提问课程核心概念，确认系统能从本地知识库召回关联内容。
3. **仿真实验**：进入初学者工坊，载入“异步电机T-s曲线”模板，点击运行，观察生成的绘图。
4. **错题本**：在解题页面将错误或未掌握的题目“加入错题本”，前往错题本页面查看紧凑排版，并在编辑态保存修改，体验页面“抗抖动”无缝刷新。使用 AI 教练生成变式练习。
