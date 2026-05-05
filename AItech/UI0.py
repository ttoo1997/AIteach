import streamlit as st
import os
import tempfile
from PIL import Image
import json
import time
from datetime import datetime
from main import MotorTheoryWorkflow, QwenTextAgent, QwenVisionAgent
from main2 import JSONLQAAgent


class CombinedMotorTheoryUI:
    def __init__(self):
        self.setup_page_config()
        self.initialize_session_state()

    def setup_page_config(self):
        """设置页面配置"""
        st.set_page_config(
            page_title="电机学智能学习平台",
            layout="wide",
            initial_sidebar_state="expanded"
        )

    def initialize_session_state(self):
        """初始化会话状态"""
        # 共享状态
        if 'api_key' not in st.session_state:
            st.session_state.api_key = ""

        # 第一个UI的状态
        if 'history' not in st.session_state:
            st.session_state.history = []
        if 'current_image' not in st.session_state:
            st.session_state.current_image = None
        if 'workflow' not in st.session_state:
            st.session_state.workflow = None

        # 第二个UI的状态
        if 'qa_agent' not in st.session_state:
            st.session_state.qa_agent = None
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []

    def render_sidebar(self):
        """渲染侧边栏"""
        with st.sidebar:
            st.header("⚙️ 系统设置")

            # API密钥输入
            api_key = os.getenv("DASHSCOPE_API_KEY")

            if api_key and api_key != st.session_state.api_key:
                st.session_state.api_key = api_key
                try:
                    # 初始化两个工作流
                    st.session_state.workflow = MotorTheoryWorkflow(api_key)
                    st.session_state.qa_agent = JSONLQAAgent(api_key)
                    st.success("✅ 系统初始化成功！")
                except Exception as e:
                    st.error(f"初始化失败: {str(e)}")

            # 重新加载知识库按钮
            if st.button("重新加载知识库", use_container_width=True):
                if st.session_state.qa_agent:
                    st.session_state.qa_agent.load_knowledge_base()
                    st.success("知识库已重新加载！")

            st.markdown("---")

            # 选项卡选择器
            st.subheader("对话历史功能导航")
            selected_tab = st.radio(
                "选择功能模块:",
                ["图像题目解答", "知识库问答"],
                label_visibility="collapsed"
            )

            st.markdown("---")

            # 历史记录部分 - 根据选择的选项卡显示对应的历史记录
            if selected_tab == "图像题目解答":
                self.render_image_history()
            else:
                self.render_qa_history()

    def render_image_history(self):
        """渲染图像解答历史记录"""
        st.subheader("📚 题目解答历史")
        if st.session_state.history:
            for i, record in enumerate(st.session_state.history[-5:]):  # 显示最近5条
                with st.expander(f"记录 {i + 1} - {record['timestamp']}"):
                    st.text_area(f"题目 {i + 1}", record['question'], height=100, key=f"img_q_{i}")
                    st.text_area(f"解答 {i + 1}", record['answer'], height=150, key=f"img_a_{i}")

            if st.button("清空题目历史", type="secondary", use_container_width=True):
                st.session_state.history = []
                st.rerun()
        else:
            st.info("暂无题目解答历史")

    def render_qa_history(self):
        """渲染问答历史记录"""
        st.subheader("💬 对话历史")
        if st.session_state.chat_history:
            for i, chat in enumerate(st.session_state.chat_history[-8:]):
                with st.expander(f"Q{len(st.session_state.chat_history) - i}: {chat['question'][:30]}...",
                                 expanded=False):
                    st.write(f"**问题**: {chat['question']}")
                    st.write(f"**回答**: {chat['answer'][:200]}...")
                    st.write(f"**置信度**: {chat['confidence']:.1f}%")
                    st.write(f"**类型**: {chat['answer_type']}")

            if st.button("清空对话历史", type="secondary", use_container_width=True):
                st.session_state.chat_history = []
                st.rerun()
        else:
            st.info("暂无对话历史")

    def render_main_content(self):
        """渲染主内容区域"""
        st.title("电机学智能学习平台")
        st.markdown("多功能电机学学习助手，支持图像题目解答和知识库问答")

        # 创建选项卡
        tab1, tab2 = st.tabs(["图像题目解答", "知识库问答"])

        with tab1:
            self.render_image_solver()

        with tab2:
            self.render_qa_system()

    def render_image_solver(self):
        """渲染图像题目解答功能"""
        st.header("图像题目解答")
        st.markdown("上传电机学题目图片，获取详细解答")

        # 创建两列布局
        col1, col2 = st.columns([2, 1])

        with col1:
            self.render_upload_section()
            self.render_result_section()

        with col2:
            self.render_image_info_section()

    def render_upload_section(self):
        """渲染上传区域"""
        st.subheader("📁 上传题目图片")

        # 文件上传器
        uploaded_file = st.file_uploader(
            "选择电机学题目图片",
            type=['png', 'jpg', 'jpeg', 'bmp'],
            help="支持格式: PNG, JPG, JPEG, BMP",
            key="image_uploader"
        )

        if uploaded_file is not None:
            # 保存上传的文件到临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                st.session_state.current_image = tmp_file.name

            # 显示图片预览
            st.image(uploaded_file, caption="上传的题目图片", use_container_width=True)

            # 解答按钮
            if st.button("获取答案", type="primary", use_container_width=True, key="solve_image"):
                if not st.session_state.api_key:
                    st.error("请先设置API密钥")
                    return

                self.process_image()

    def render_result_section(self):
        """渲染结果展示区域"""
        if 'last_result' in st.session_state:
            result = st.session_state.last_result

            st.subheader("识别结果")

            # 提取的题目
            with st.expander("提取的题目内容", expanded=True):
                st.text_area(
                    "题目",
                    result['extracted_text'],
                    height=150,
                    key="extracted_question"
                )

            # AI解答
            st.subheader("AI解答")
            st.markdown("---")

            # 解答内容区域
            answer_container = st.container()
            with answer_container:
                if result['success']:
                    # 美化解答显示
                    st.markdown("#### 详细解答")
                    st.write(result['solution'])

                    # 添加复制功能
                    st.download_button(
                        "复制解答内容",
                        result['solution'],
                        file_name=f"电机学解答_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain"
                    )
                else:
                    st.error("❌ 处理失败")
                    st.error(f"错误信息: {result.get('error', '未知错误')}")

    def render_image_info_section(self):
        """渲染图像解答信息面板"""
        # 系统状态
        st.subheader("系统状态")
        if st.session_state.api_key and st.session_state.workflow:
            st.success("✅ 图像解答系统就绪")
        else:
            st.warning("⚠️ 图像解答系统未初始化")

        st.metric("题目解答数量", len(st.session_state.history))

        # 手动输入区域
        st.markdown("---")
        self.render_manual_input_section()

    def render_manual_input_section(self):
        """渲染手动输入区域"""
        st.subheader("手动输入题目")

        manual_question = st.text_area(
            "请输入电机学题目：",
            height=150,
            placeholder="例如：一台三相异步电动机，额定电压380V，额定功率15kW...",
            help="直接输入题目文字，跳过图片识别步骤",
            key="manual_question"
        )

        if st.button("解答手动输入题目", use_container_width=True, key="solve_manual"):
            if manual_question and st.session_state.workflow:
                with st.spinner("正在生成解答..."):
                    result = st.session_state.workflow.solve_from_text(manual_question)
                    st.session_state.last_result = result
                    st.rerun()

    def process_image(self):
        """处理图片并获取解答"""
        if not st.session_state.workflow or not st.session_state.current_image:
            return

        # 显示进度
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            status_text.text("正在处理图片...")
            progress_bar.progress(25)

            # 调用工作流处理图片
            status_text.text("识别题目文字...")
            progress_bar.progress(50)

            result = st.session_state.workflow.solve_motor_problem(
                st.session_state.current_image
            )

            status_text.text("生成解答...")
            progress_bar.progress(75)

            # 保存结果到会话状态
            st.session_state.last_result = result

            # 添加到历史记录
            if result['success']:
                st.session_state.history.append({
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'question': result['extracted_text'],
                    'answer': result['solution'],
                    'image_path': result['image_path']
                })

            status_text.text("✅ 处理完成！")
            progress_bar.progress(100)

            # 短暂延迟后清除进度显示
            time.sleep(1)
            progress_bar.empty()
            status_text.empty()

        except Exception as e:
            status_text.error(f"❌ 处理过程中发生错误: {str(e)}")
            progress_bar.empty()

    def render_qa_system(self):
        """渲染知识库问答系统"""
        st.header("知识库问答")
        st.markdown("基于JSONL知识库的智能问答系统")

        # 系统状态
        self.render_qa_status_section()

        st.markdown("---")

        # 问答区域
        self.render_qa_section()

    def render_qa_status_section(self):
        """渲染问答系统状态区域"""
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.session_state.qa_agent:
                if st.session_state.qa_agent.qa_pairs:
                    st.success("✅ 问答系统就绪")
                else:
                    st.warning("⚠️ 知识库为空")
            else:
                st.error("❌ 问答系统未初始化")

        with col2:
            st.metric("对话记录", len(st.session_state.chat_history))

        with col3:
            if st.session_state.qa_agent and st.session_state.qa_agent.qa_pairs:
                st.metric("知识库条目", len(st.session_state.qa_agent.qa_pairs))
            else:
                st.metric("知识库条目", 0)

    def render_qa_section(self):
        """渲染问答区域"""
        st.subheader("智能问答")

        # 问题输入
        question = st.text_area(
            "请输入您的问题：",
            height=80,
            placeholder="例如：磁路的欧姆定律表达式是什么？",
            help="系统将在JSONL知识库中搜索最相关的问答对",
            key="qa_question"
        )

        # 高级选项
        with st.expander("高级选项"):
            col1, col2 = st.columns(2)
            with col1:
                top_k = st.slider("返回结果数量", 1, 10, 3, key="top_k")
            with col2:
                similarity_threshold = st.slider("相似度阈值", 0.1, 0.9, 0.7, key="similarity_threshold")

        # 提交按钮
        if st.button("搜索答案", type="primary", use_container_width=True, key="search_answer"):
            if not question.strip():
                st.warning("请输入问题")
                return

            if not st.session_state.qa_agent:
                st.error("问答系统未初始化")
                return

            self.process_question(question, top_k, similarity_threshold)

    def process_question(self, question: str, top_k: int, similarity_threshold: float):
        """处理问题并生成回答"""
        with st.spinner("正在搜索知识库并生成回答..."):
            try:
                # 保存原始方法
                original_search_method = st.session_state.qa_agent.search_similar_questions

                # 临时替换方法以使用自定义参数
                def custom_search(question):
                    return original_search_method(question, top_k, similarity_threshold)

                st.session_state.qa_agent.search_similar_questions = custom_search

                # 调用问答方法
                result = st.session_state.qa_agent.ask_question(question)

                # 恢复原始方法
                st.session_state.qa_agent.search_similar_questions = original_search_method

                # 保存到历史记录
                st.session_state.chat_history.append(result)

                # 显示结果
                self.display_answer_result(result)

            except Exception as e:
                st.error(f"处理问题时发生错误: {str(e)}")

    def display_answer_result(self, result: dict):
        """显示回答结果"""
        # 回答主体
        st.subheader("智能回答")

        # 置信度指示器
        confidence = result['confidence']
        if confidence > 80:
            st.success(f"✅ 高置信度回答 ({confidence:.1f}%)")
        elif confidence > 50:
            st.warning(f"⚠️ 中等置信度回答 ({confidence:.1f}%)")
        else:
            st.error(f"❌ 低置信度回答 ({confidence:.1f}%)")

        st.info(f"回答类型: {result['answer_type']}")

        # 答案内容
        st.write(result['answer'])

        # 来源信息
        if result['sources']:
            st.subheader("参考来源")
            for source in result['sources']:
                st.write(f"- {source}")

        # 相似问题
        if result['similar_questions']:
            with st.expander(f"相关问答对 (找到 {result['total_matches']} 个)"):
                for i, similar_qa in enumerate(result['similar_questions']):
                    st.markdown(f"**相关问答 {i + 1}** (相似度: {similar_qa['similarity']:.3f})")
                    st.write(f"**问题**: {similar_qa['question']}")
                    st.write(f"**答案**: {similar_qa['answer']}")
                    st.write(f"来源: {similar_qa['source']} | 行号: {similar_qa.get('line_number', 'N/A')}")
                    st.markdown("---")

    def run(self):
        """运行合并后的UI应用"""
        self.render_sidebar()
        self.render_main_content()


# 主程序入口
def main():
    ui = CombinedMotorTheoryUI()
    ui.run()


if __name__ == "__main__":
    main()