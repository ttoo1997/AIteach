import streamlit as st
import os
import tempfile
from PIL import Image
import json
import time
from datetime import datetime
from main import MotorTheoryWorkflow, QwenTextAgent, QwenVisionAgent


class MotorTheoryUI:
    def __init__(self):
        self.setup_page_config()
        self.initialize_session_state()

    def setup_page_config(self):
        """设置页面配置"""
        st.set_page_config(
            page_title="电机学学习大平台",
            layout="wide",
            initial_sidebar_state="expanded"
        )

    def initialize_session_state(self):
        """初始化会话状态"""
        if 'history' not in st.session_state:
            st.session_state.history = []
        if 'current_image' not in st.session_state:
            st.session_state.current_image = None
        if 'api_key' not in st.session_state:
            st.session_state.api_key = ""
        if 'workflow' not in st.session_state:
            st.session_state.workflow = None

    def render_sidebar(self):
        """渲染侧边栏"""
        with st.sidebar:
            st.header("⚙️ 系统设置")

            # API密钥输入
            api_key = os.getenv("DASHSCOPE_API_KEY")

            if api_key != st.session_state.api_key:
                st.session_state.api_key = api_key
                if api_key:
                    try:
                        st.session_state.workflow = MotorTheoryWorkflow(api_key)
                    except Exception as e:
                        st.error(f"API密钥验证失败: {str(e)}")

            # 模型设置
            #st.subheader("模型设置")
            #detail_level = st.selectbox(
            #    "解答详细程度",
            #    ["简洁", "标准", "详细"],
            #    index=1
            #)

            # 历史记录
            st.subheader("📚 历史记录")
            if st.session_state.history:
                for i, record in enumerate(st.session_state.history[-5:]):  # 显示最近5条
                    with st.expander(f"记录 {i + 1} - {record['timestamp']}"):
                        st.text_area(f"题目 {i + 1}", record['question'], height=100, key=f"q_{i}")
                        st.text_area(f"解答 {i + 1}", record['answer'], height=150, key=f"a_{i}")
            else:
                st.info("暂无历史记录")

            # 清空历史按钮
            if st.session_state.history:
                if st.button("清空历史记录", type="secondary"):
                    st.session_state.history = []
                    st.rerun()

    def render_main_content(self):
        """主内容区域"""
        st.title("电机学学习大平台")
        st.markdown("上传电机学题目图片，获取解答")

        # 创建两列布局
        col1, col2 = st.columns([2, 1])

        with col1:
            self.render_upload_section()
            self.render_result_section()

        with col2:
            self.render_info_section()

    def render_upload_section(self):
        """渲染上传区域"""
        st.subheader("📁 上传题目图片")

        # 文件上传器
        uploaded_file = st.file_uploader(
            "选择电机学题目图片",
            type=['png', 'jpg', 'jpeg', 'bmp'],
            help="支持格式: PNG, JPG, JPEG, BMP"
        )

        if uploaded_file is not None:
            # 保存上传的文件到临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                st.session_state.current_image = tmp_file.name

            # 显示图片预览
            st.image(uploaded_file, caption="上传的题目图片", use_container_width=True)

            # 解答按钮
            if st.button("获取答案", type="primary", use_container_width=True):
                if not st.session_state.api_key:
                    st.error("请先在侧边栏设置API密钥")
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

    def render_info_section(self):
        """渲染信息面板"""
        # 系统状态
        st.subheader("系统状态")
        if st.session_state.api_key:
            st.success("✅ API密钥已设置")
        else:
            st.warning("⚠️ API密钥存在问题")

        st.metric("历史记录数量", len(st.session_state.history))

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

    def run(self):
        """运行UI应用"""
        self.render_sidebar()
        self.render_main_content()

    def render_manual_input_section(self):
        """渲染手动输入区域"""
        st.subheader("手动输入题目")

        manual_question = st.text_area(
            "请输入电机学题目：",
            height=150,
            placeholder="例如：一台三相异步电动机，额定电压380V，额定功率15kW...",
            help="直接输入题目文字，跳过图片识别步骤"
        )

        if st.button("解答手动输入题目", use_container_width=True):
            if manual_question and st.session_state.workflow:
                with st.spinner("正在生成解答..."):
                    result = st.session_state.workflow.solve_from_text(manual_question)
                    st.session_state.last_result = result
                    st.rerun()


# 主程序入口
def main():
    ui = MotorTheoryUI()
    ui.run()


if __name__ == "__main__":
    main()