# AITeach 架构说明

更新时间: 2026-04-18

## 1. 系统概览

AITeach 当前是一套围绕电机学课程学习场景构建的 Web 教学辅助系统，核心能力包含:

- AI 解题
- 课程知识问答
- 错题本与 AI 错题教练
- 电机学参数仿真实验

整体技术栈以 `FastAPI + 原生 Web 前端 + SQLite + DashScope/Qwen` 为主，并保留了 MATLAB 作为高保真仿真后端的可选能力。

## 2. 运行拓扑

### 2.1 默认运行模式

系统默认以单机 Web 应用方式运行:

1. 启动脚本创建或复用 `.venv`
2. 启动 `uvicorn api.web_app:app`
3. FastAPI 同时承担:
   - 静态资源分发
   - AI 解题 API
   - 错题本 API
   - 知识问答 API
   - 仿真 API
4. 浏览器访问 `http://127.0.0.1:8090/`

### 2.2 可扩展运行模式

若后续需要把计算层与页面层分离，可额外启动独立仿真服务:

- `api.web_app:app`: 主 Web 服务
- `api.simulation_api:app`: 仿真服务

这种模式下，主服务负责交互与业务编排，仿真服务负责更重的 MATLAB 或数值计算任务。

## 3. 目录分层

| 路径 | 职责 |
| --- | --- |
| `api/` | FastAPI 路由层，提供所有对外接口 |
| `services/` | AI 解题、知识问答、错题分析、仿真助教等业务逻辑 |
| `simulation/` | 电机学仿真引擎与 MATLAB 适配层 |
| `storage/` | 错题本 SQLite 读写与容错 |
| `schemas/` | 数据契约与结果结构 |
| `web_frontend/` | HTML、CSS、JavaScript 前端；当前已开始按 `app.js + app_coach.js + app_boot.js` 做职责拆分 |
| `matlab/` | MATLAB CLI 桥接脚本 |
| `knowledge_base/` | 本地知识库数据 |
| `runtime_env.py` | `.env.local` 读取与代理环境清理 |

## 4. 核心业务链路

### 4.1 AI 解题链路

AI 解题页是当前系统最复杂的一条链路。

前端侧:

1. `web_frontend/app.js` 收集用户输入、历史上下文和附件
2. 向 `/api/solve/chat/stream` 发起流式请求
3. 逐步接收 `meta / delta / done / error` 事件
4. 将消息实时渲染到聊天区域，并在合适时机触发 MathJax

后端侧:

1. `api/web_app.py` 解析历史消息和上传文件
2. 如有图片，先走 OCR 提取题干
3. `services/solver_service.py` 负责:
   - 课程知识召回
   - Prompt 组织
   - Qwen 流式解答
   - 结果质量复核与纠偏
4. 最终返回标准化结果对象，用于前端定稿和错题本回填

### 4.2 流式公式渲染机制

为了解决“公式在流式输出中显示异常”的问题，前端现在采用了两段式渲染策略:

1. 文本预处理
   - 统一 `$...$` / `$$...$$` 为 MathJax 友好的分隔符
   - 先把 LaTeX 片段保护起来，避免 markdown 清洗误伤公式
2. 渐进式排版
   - 先检测公式分隔符是否闭合
   - 再通过节流调度触发 MathJax
   - 最终 `done` 到达后再做一次完整排版

这样既保留了流式输出的即时感，也减少了公式半截渲染导致的闪烁和错位。

### 4.3 错题本与 AI 教练链路

错题本模块由两部分组成:

- 普通错题记录
- AI 教练练习闭环

普通链路:

1. 用户在解题页点击“加入错题本”
2. `/api/wrong-questions` 写入 SQLite
3. 错题列表支持分页、局部编辑与富文本显示

AI 教练链路:

1. `WrongbookAIService` 分析最近错题
2. 输出学情报告、薄弱点与建议
3. 按薄弱点生成练习题
4. 用户查看解析后，可自行决定是否点击“加入错题本”，把练习题、作答与解析沉淀进错题本，形成更可控的闭环复盘
5. 前端将这条链路独立整理为 `web_frontend/app_coach.js`，避免错题教练逻辑继续堆叠进通用脚本

### 4.4 仿真链路

仿真模块当前围绕四个固定实验组织:

- 直流电机
- 变压器
- 异步电机
- 同步电机

运行顺序:

1. 前端选择实验与参数
2. `/api/simulate/lab-run` 分发到 `FixedSimulationLabService`
3. 由实验服务决定使用:
   - Python 解析仿真
   - MATLAB Engine
   - MATLAB CLI
   - 远程仿真服务
4. 返回:
   - 关键指标
   - 数据序列
   - 备注与实验建议
   - 可选仿真图片

### 4.5 MATLAB 仿真图片输出

这是当前仿真模块的一个亮点:

- 后端不仅能返回数值结果
- 还可以让 MATLAB CLI 或 Python 回退链路生成图像
- 图像通过 `plot_image_data_url` 回传给前端展示

这意味着仿真结果不再只是“算一个值”，而是可以在页面里直接呈现图形化结果，为后续扩展成更完整的图表式实验页面留出了接口。

## 5. 稳定性设计

### 5.1 服务容器统一装配

`ServiceContainer` 统一托管:

- `MotorTheoryWorkflow`
- `JSONLQAAgent`
- `WrongbookAIService`
- `SimulationCoachService`

这样可以避免不同接口各自初始化同类服务，减少状态漂移和重复配置。

### 5.2 本地环境恢复能力

`runtime_env.py` 在启动时会:

- 自动读取 `.env.local`
- 清理明显错误的本地代理变量

这样能减少因代理污染导致的 DashScope 请求失败。

### 5.3 流式接口的收尾保障

`/api/solve/chat/stream` 现在具备:

- 流式 `delta`
- 稳定 `done`
- 错误 `error`
- `finally` 中的临时文件清理

前端则增加了收尾兜底逻辑，即使流式末尾没有拿到完整状态，也尽量把最终文本稳定落到界面上。

### 5.4 仿真计算三层降级

`simulation/motor_simulator.py` 当前采用三层能力优先级:

1. MATLAB Engine
2. MATLAB CLI
3. Python 回退

这保证了系统在不同机器上都能运行，同时保留了“真 MATLAB”能力。

## 6. 当前代码规模

排除 `.venv`、`__pycache__`、`.kb_cache` 后，当前项目统计如下:

- 代码与文档文件共 `44` 个
- 总行数 `9132`
- 其中 Markdown `315` 行
- 非 Markdown 代码约 `8817` 行

主要大文件:

- `web_frontend/styles.css`: `1701` 行
- `web_frontend/app.js`: `1620` 行
- `services/solver_service.py`: `724` 行
- `simulation/motor_simulator.py`: `705` 行
- `api/web_app.py`: `526` 行

从规模上看，AITeach 已经不是简单脚本集合，而是一个中等规模的课程产品原型。

## 7. 后续最值得继续拆分的模块

当前最值得继续细化的三个文件是:

1. `web_frontend/app.js`
   - 目前已经把错题教练与页面启动拆到 `app_coach.js`、`app_boot.js`
   - 后续仍可继续拆为解题、仿真、共享渲染三个更聚焦的模块
2. `web_frontend/styles.css`
   - 可拆为基础层、布局层、业务页样式层
3. `services/solver_service.py`
   - 可拆为 Prompt 生成、质量守卫、流式解题编排三个部分

这会比继续堆叠新功能更能提升维护性和可读性。
