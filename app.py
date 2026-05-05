import os
import re
import tempfile
import time
from datetime import datetime

import matplotlib.pyplot as plt
import streamlit as st

from app_config import (
    APP_SUBTITLE,
    APP_TITLE,
    DEFAULT_DB_PATH,
    DEFAULT_SIMULATION_BACKEND,
    SUPPORTED_IMAGE_TYPES,
)
from services.knowledge_base_service import JSONLQAAgent
from services.solver_service import MotorTheoryWorkflow
from simulation.motor_simulator import InductionMotorParams, explain_curve_text, simulate_torque_curve
from storage.wrong_question_repository import WrongQuestionDB


class AiteachApp:
    def __init__(self):
        st.set_page_config(page_title=APP_TITLE, layout="wide", initial_sidebar_state="expanded")
        self.init_state()

    @staticmethod
    def init_state():
        defaults = {
            "api_key": "",
            "history": [],
            "chat_history": [],
            "current_image": None,
            "workflow": None,
            "qa_agent": None,
            "db": None,
            "last_result": None,
            "last_result_id": None,
            "feedback_mode": None,
            "feedback_done": False,
            "feedback_message": "",
            "simulation_backend": DEFAULT_SIMULATION_BACKEND,
        }
        for k, v in defaults.items():
            if k not in st.session_state:
                st.session_state[k] = v

    def ensure_agents(self):
        api_key = os.getenv("DASHSCOPE_API_KEY", "")
        db_path = os.getenv("WRONG_QUESTION_DB", DEFAULT_DB_PATH)

        if st.session_state.db is None:
            st.session_state.db = WrongQuestionDB(db_path)

        if api_key and api_key != st.session_state.api_key:
            st.session_state.api_key = api_key
            st.session_state.qa_agent = JSONLQAAgent(api_key)
            st.session_state.workflow = MotorTheoryWorkflow(api_key, knowledge_agent=st.session_state.qa_agent)
        elif st.session_state.workflow and st.session_state.qa_agent:
            st.session_state.workflow.set_knowledge_agent(st.session_state.qa_agent)

    @staticmethod
    def build_result_id(result: dict) -> str:
        question = result.get("extracted_text") or ""
        image_path = result.get("image_path") or "manual"
        stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        return f"{image_path}-{len(question)}-{stamp}"

    def set_last_result(self, result: dict, add_to_history: bool = False):
        st.session_state.last_result = result
        st.session_state.last_result_id = self.build_result_id(result)
        st.session_state.feedback_mode = None
        st.session_state.feedback_done = False
        st.session_state.feedback_message = ""
        if add_to_history and result.get("success"):
            st.session_state.history.append(
                {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "question": result.get("extracted_text") or "",
                    "answer": result.get("solution") or "",
                    "image_path": result.get("image_path"),
                }
            )

    @staticmethod
    def looks_like_formula(text: str) -> bool:
        formula_markers = [r"\\frac", r"\\sum", r"\\sqrt", r"\\text", "^", "_", "=", r"\\omega", r"\\phi"]
        return any(marker in text for marker in formula_markers)

    def render_rich_answer(self, answer: str):
        if not answer:
            st.write("")
            return

        # 统一换行，先处理显示型公式 \[ ... \]
        text = answer.replace("\r\n", "\n")
        pattern = re.compile(r"\\\[(.*?)\\\]", re.DOTALL)
        last = 0
        found_any = False

        for match in pattern.finditer(text):
            found_any = True
            before = text[last:match.start()].strip()
            formula = match.group(1).strip()
            if before:
                st.markdown(before)
            if formula:
                st.latex(formula)
            last = match.end()

        tail = text[last:].strip()
        if found_any:
            if tail:
                st.markdown(tail)
            return

        # 如果模型输出成 [ ... ] 且内部明显像公式，也转成公式展示
        lines = text.split("\n")
        for line in lines:
            stripped = line.strip()
            m = re.match(r"^\[(.+)\]$", stripped)
            if m and self.looks_like_formula(m.group(1)):
                st.latex(m.group(1).strip())
            else:
                if stripped:
                    st.markdown(stripped)
                else:
                    st.write("")

    def render_sidebar(self):
        with st.sidebar:
            st.header("⚙️ 系统设置")
            self.ensure_agents()
            if st.session_state.api_key:
                st.success("✅ API 已读取")
            else:
                st.warning("请在环境变量中设置 DASHSCOPE_API_KEY")

            if st.button("重新加载知识库", use_container_width=True) and st.session_state.qa_agent:
                summary = st.session_state.qa_agent.load_knowledge_base(force_reload=True)
                st.success(summary.get("message", "知识库已重新加载"))

            st.markdown("---")
            wrong_count = st.session_state.db.count_wrong_questions() if st.session_state.db else 0
            st.metric("错题本记录数", wrong_count)
            st.caption(f"仿真后端默认值：{st.session_state.simulation_backend}")
            if st.session_state.qa_agent:
                st.caption(f"知识库路径：{st.session_state.qa_agent.knowledge_base_path}")
                if st.session_state.qa_agent.loaded_files:
                    st.caption(f"已发现文件数：{len(st.session_state.qa_agent.loaded_files)}")
                st.caption(f"检索模式：{'嵌入检索' if st.session_state.qa_agent.embedding_enabled else '关键词回退'}")
            st.caption("建议答辩演示顺序：知识库问答 → 图像解题 → 参数仿真 → 错题本")

    def render_image_solver(self):
        st.header("图像题目解答")
        col1, col2 = st.columns([2, 1])

        with col1:
            uploaded_file = st.file_uploader("上传题目图片", type=SUPPORTED_IMAGE_TYPES, key="image_uploader")
            if uploaded_file is not None:
                suffix = os.path.splitext(uploaded_file.name)[1] or ".jpg"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(uploaded_file.getvalue())
                    st.session_state.current_image = tmp.name
                st.image(uploaded_file, caption="上传的题目图片", use_container_width=True)
                if st.button("获取图片题目答案", type="primary"):
                    self.process_image()

            st.markdown("### 手动输入题目")
            manual_question = st.text_area("请输入题目", height=140, key="manual_question")
            if st.button("解答手动输入题目", use_container_width=True):
                if not manual_question.strip():
                    st.warning("请输入题目内容")
                elif not st.session_state.workflow:
                    st.error("系统未初始化")
                else:
                    with st.spinner("正在生成解答..."):
                        result = st.session_state.workflow.solve_from_text(
                            manual_question.strip(),
                            knowledge_agent=st.session_state.qa_agent,
                        )
                    self.set_last_result(result, add_to_history=True)
                    st.rerun()

            if st.session_state.last_result:
                self.render_last_result(st.session_state.last_result)

        with col2:
            st.subheader("系统状态")
            st.metric("题目解答数量", len(st.session_state.history))
            if st.session_state.workflow:
                st.success("图像解题模块就绪")
            else:
                st.warning("图像解题模块未初始化")
            st.markdown("---")
            st.info("解答完成后，可标记“做对了”或“做错了”。做错时可记录错误原因，并自动进入错题本。")

    def render_last_result(self, result):
        with st.expander("提取的题目", expanded=True):
            st.text_area("题目文本", result.get("extracted_text") or "", height=140, disabled=True)
        st.markdown("### AI解答")
        if result["success"]:
            if result.get("confidence"):
                st.caption(f"解题置信度：{result['confidence']}%")
            self.render_rich_answer(result["solution"])
            if result.get("analysis"):
                with st.expander("题意分析", expanded=False):
                    st.markdown(result["analysis"])
            if result.get("review_notes"):
                st.info(f"复核提示：\n\n{result['review_notes']}")
            self.render_feedback_panel(result)
        else:
            st.error(result.get("error", "未知错误"))

    def render_feedback_panel(self, result: dict):
        st.markdown("### 学习反馈")
        result_id = st.session_state.last_result_id or "current"

        if st.session_state.feedback_done:
            st.success(st.session_state.feedback_message or "已记录本题反馈")
            return

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("我做对了", use_container_width=True, key=f"correct_{result_id}"):
                st.session_state.feedback_done = True
                st.session_state.feedback_mode = "correct"
                st.session_state.feedback_message = "已记录：本题你标记为做对了。"
                st.rerun()
        with col_b:
            if st.button("我做错了", use_container_width=True, key=f"wrong_{result_id}"):
                st.session_state.feedback_mode = "wrong"
                st.rerun()

        if st.session_state.feedback_mode == "wrong":
            reason = st.text_area(
                "请填写做错的原因",
                height=120,
                key=f"wrong_reason_{result_id}",
                placeholder="例如：转差率概念混淆；公式代入时漏掉了极对数；相量关系理解错误……",
            )
            save_col, cancel_col = st.columns(2)
            with save_col:
                if st.button("保存到错题本", type="primary", use_container_width=True, key=f"save_wrong_{result_id}"):
                    if not reason.strip():
                        st.warning("请先填写做错原因")
                    elif not st.session_state.db:
                        st.error("错题本数据库未初始化")
                    else:
                        source_type = "image" if result.get("image_path") else "manual"
                        st.session_state.db.add_wrong_question(
                            question_text=result.get("extracted_text") or "",
                            answer_text=result.get("solution") or "",
                            error_reason=reason.strip(),
                            source_type=source_type,
                            image_path=result.get("image_path"),
                        )
                        st.session_state.feedback_done = True
                        st.session_state.feedback_mode = "wrong"
                        st.session_state.feedback_message = "已保存到错题本。"
                        st.rerun()
            with cancel_col:
                if st.button("取消", use_container_width=True, key=f"cancel_wrong_{result_id}"):
                    st.session_state.feedback_mode = None
                    st.rerun()

    def process_image(self):
        if not st.session_state.workflow or not st.session_state.current_image:
            st.error("系统未初始化或未上传图片")
            return
        progress = st.progress(0)
        status = st.empty()
        status.text("正在识别图片...")
        progress.progress(40)
        result = st.session_state.workflow.solve_motor_problem(
            st.session_state.current_image,
            knowledge_agent=st.session_state.qa_agent,
        )
        progress.progress(85)
        self.set_last_result(result, add_to_history=True)
        progress.progress(100)
        status.text("处理完成")
        time.sleep(0.4)
        progress.empty()
        status.empty()

    def render_qa_system(self):
        st.header("知识库问答")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("知识库条目", len(st.session_state.qa_agent.qa_pairs) if st.session_state.qa_agent else 0)
        with col2:
            st.metric("问答记录", len(st.session_state.chat_history))
        with col3:
            st.metric("知识库状态", "就绪" if st.session_state.qa_agent else "未就绪")

        if st.session_state.qa_agent:
            st.caption(f"当前知识库路径：{st.session_state.qa_agent.knowledge_base_path}")
            if st.session_state.qa_agent.loaded_files:
                st.caption("已加载文件：")
                for fp in st.session_state.qa_agent.loaded_files:
                    st.code(fp)

        question = st.text_area("请输入知识库问题", height=100, key="qa_question")
        top_k = st.slider("返回候选数量", 1, 8, 3)
        similarity_threshold = st.slider("相似度阈值", 0.1, 0.95, 0.18)
        if st.button("搜索答案", type="primary"):
            if not st.session_state.qa_agent:
                st.error("问答系统未初始化")
            elif not question.strip():
                st.warning("请输入问题")
            else:
                with st.spinner("正在搜索知识库..."):
                    result = st.session_state.qa_agent.ask_question(
                        question.strip(), top_k=top_k, similarity_threshold=similarity_threshold
                    )
                st.session_state.chat_history.append(result)
                self.display_answer_result(result)

        if st.session_state.chat_history:
            st.markdown("### 最近一条问答")
            self.display_answer_result(st.session_state.chat_history[-1])

    def display_answer_result(self, result: dict):
        confidence = result["confidence"]
        if confidence > 80:
            st.success(f"高置信度回答 ({confidence:.1f}%)")
        elif confidence > 50:
            st.warning(f"中等置信度回答 ({confidence:.1f}%)")
        else:
            st.error(f"低置信度回答 ({confidence:.1f}%)")

        self.render_rich_answer(result["answer"])
        if result.get("sources"):
            st.markdown("**参考来源**")
            for source in result["sources"]:
                st.write(f"- {source}")
        if result.get("similar_questions"):
            with st.expander(f"查看候选问答（{result['total_matches']}条）"):
                for item in result["similar_questions"]:
                    st.markdown(f"**问题**：{item['question']}")
                    self.render_rich_answer(item["answer"])
                    st.caption(
                        "来源："
                        f"{item['source']} 第{item['line_number']}行，"
                        f"综合相关度={item.get('score', 0):.3f}，"
                        f"embedding={item.get('embedding_score', 0):.3f}，"
                        f"词项={item.get('lexical_score', 0):.3f}，"
                        f"公式={item.get('formula_score', 0):.3f}"
                    )
                    st.markdown("---")

    def render_simulation(self):
        st.header("异步电机参数仿真")
        col1, col2 = st.columns([1, 2])
        with col1:
            st.selectbox(
                "仿真后端",
                options=["auto", "python", "service", "matlab"],
                key="simulation_backend",
            )
            r2 = st.number_input("转子电阻 R2", min_value=0.01, value=0.50, step=0.05)
            x2 = st.number_input("转子漏抗 X2", min_value=0.01, value=1.20, step=0.05)
            e2 = st.number_input("感应电势 E2", min_value=1.0, value=220.0, step=10.0)
            s_min = st.number_input("最小滑差", min_value=0.001, max_value=1.0, value=0.01, step=0.01)
            s_max = st.number_input("最大滑差", min_value=0.01, max_value=1.0, value=1.0, step=0.05)
            run_btn = st.button("运行仿真")
        with col2:
            if run_btn:
                params = InductionMotorParams(r2=r2, x2=x2, e2=e2, s_min=s_min, s_max=s_max)
                result = simulate_torque_curve(params, backend=st.session_state.simulation_backend)
                fig, ax = plt.subplots()
                ax.plot(result["slip"], result["torque"])
                ax.set_xlabel("Slip s")
                ax.set_ylabel("Relative Torque")
                ax.set_title("异步电机转矩-滑差曲线")
                ax.grid(True)
                st.pyplot(fig)
                st.caption(f"仿真后端：{result.get('backend', st.session_state.simulation_backend)}")
                st.markdown(f"**最大转矩滑差**：{result['max_slip']:.3f}  ")
                st.markdown(f"**最大相对转矩**：{result['max_torque']:.3f}")
                for note in result.get("notes", []):
                    st.caption(note)
                st.info(explain_curve_text(result))
                if st.session_state.workflow:
                    prompt = (
                        f"请用本科答辩能听懂的方式解释一个异步电机近似仿真结果："
                        f"R2={r2}, X2={x2}, E2={e2}, 最大转矩滑差={result['max_slip']:.3f}, 最大转矩={result['max_torque']:.3f}。"
                        "请解释参数变化趋势，不要编造精确工程结论。"
                    )
                    with st.spinner("正在生成AI解释..."):
                        explanation = st.session_state.workflow.text_agent.query(prompt)
                    st.markdown("### AI解释")
                    self.render_rich_answer(explanation)

    def render_wrong_book(self):
        st.header("错题本")
        if not st.session_state.db:
            st.error("错题本数据库未初始化")
            return

        records = st.session_state.db.list_wrong_questions()
        col1, col2 = st.columns(2)
        with col1:
            st.metric("错题数量", len(records))
        with col2:
            if st.button("刷新错题本", use_container_width=True):
                st.rerun()

        if not records:
            st.info("当前还没有错题记录。你可以在“图像题目解答”页将题目标记为做错。")
            return

        for record in records:
            title = f"错题 #{record['id']} | {record['source_type']} | {record['created_at']}"
            with st.expander(title, expanded=False):
                q_key = f"edit_question_{record['id']}"
                a_key = f"edit_answer_{record['id']}"
                r_key = f"edit_reason_{record['id']}"

                st.text_area("题目", value=record["question_text"], height=140, key=q_key)
                st.text_area("答案", value=record["answer_text"], height=180, key=a_key)
                st.text_area("错误原因", value=record["error_reason"], height=120, key=r_key)
                st.caption(f"创建时间：{record['created_at']} | 更新时间：{record['updated_at']}")

                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    if st.button("保存修改", use_container_width=True, key=f"save_edit_{record['id']}"):
                        ok = st.session_state.db.update_wrong_question(
                            record_id=record["id"],
                            question_text=st.session_state[q_key],
                            answer_text=st.session_state[a_key],
                            error_reason=st.session_state[r_key],
                        )
                        if ok:
                            st.success("修改已保存")
                            st.rerun()
                        else:
                            st.error("保存失败")
                with btn_col2:
                    if st.button("删除这条记录", use_container_width=True, key=f"delete_{record['id']}"):
                        ok = st.session_state.db.delete_wrong_question(record["id"])
                        if ok:
                            st.success("已删除")
                            st.rerun()
                        else:
                            st.error("删除失败")

    def run(self):
        self.render_sidebar()
        st.title(APP_TITLE)
        st.caption(APP_SUBTITLE)
        tab1, tab2, tab3, tab4 = st.tabs(["图像题目解答", "知识库问答", "参数仿真", "错题本"])
        with tab1:
            self.render_image_solver()
        with tab2:
            self.render_qa_system()
        with tab3:
            self.render_simulation()
        with tab4:
            self.render_wrong_book()


def main():
    app = AiteachApp()
    app.run()


if __name__ == "__main__":
    main()
