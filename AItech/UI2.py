import os
from typing import List, Dict, Any
import streamlit as st
from main2 import JSONLQAAgent


class JSONLQAUI:
    def __init__(self):
        self.setup_page_config()
        self.initialize_session_state()

    def setup_page_config(self):
        """设置页面配置"""
        st.set_page_config(
            page_title="JSONL知识库问答智能体",
            layout="wide",
            initial_sidebar_state="expanded"
        )

    def initialize_session_state(self):
        """初始化会话状态"""
        if 'qa_agent' not in st.session_state:
            st.session_state.qa_agent = None
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []
        if 'api_key' not in st.session_state:
            st.session_state.api_key = ""

    def render_sidebar(self):
        """渲染侧边栏"""
        with st.sidebar:
            st.header("⚙️ 系统设置")

            # API密钥输入
            api_key = os.getenv("DASHSCOPE_API_KEY")

            if api_key and api_key != st.session_state.api_key:
                st.session_state.api_key = api_key
                try:
                    st.session_state.qa_agent = JSONLQAAgent(api_key)
                    st.success("✅ 智能体初始化成功！")
                except Exception as e:
                    st.error(f"初始化失败: {str(e)}")

            # 重新加载按钮
            if st.button("重新加载知识库", use_container_width=True):
                if st.session_state.qa_agent:
                    st.session_state.qa_agent.load_knowledge_base()
                    st.rerun()

            # 对话历史
            st.subheader("对话历史")
            if st.session_state.chat_history:
                for i, chat in enumerate(st.session_state.chat_history[-8:]):
                    with st.expander(f"Q{len(st.session_state.chat_history) - i}: {chat['question'][:30]}...",
                                     expanded=False):
                        st.write(f"**问题**: {chat['question']}")
                        st.write(f"**回答**: {chat['answer'][:200]}...")
                        st.write(f"**置信度**: {chat['confidence']:.1f}%")
                        st.write(f"**类型**: {chat['answer_type']}")
                if st.button("清空对话历史", type="secondary"):
                    st.session_state.chat_history = []
                    st.rerun()
            else:
                st.info("暂无对话历史")

    def render_main_content(self):
        """渲染主内容区域"""
        st.title("电机学知识库问答智能体")
        st.markdown("电机学知识库问答智能体")

        # 系统状态
        self.render_status_section()

        st.markdown("---")

        # 问答区域
        self.render_qa_section()

    def render_status_section(self):
        """渲染系统状态区域"""
        col1, col2 = st.columns(2)

        with col1:
            if st.session_state.qa_agent:
                if st.session_state.qa_agent.qa_pairs:
                    st.success("✅ 系统就绪")
                else:
                    st.warning("⚠️ 知识库为空")
            else:
                st.error("❌ 未初始化")

        with col2:
            st.metric("对话记录", len(st.session_state.chat_history))

    def render_qa_section(self):
        """渲染问答区域"""
        st.subheader("智能问答")

        # 问题输入
        question = st.text_area(
            "请输入您的问题：",
            height=80,
            placeholder="例如：磁路的欧姆定律表达式是什么？",
            help="系统将在JSONL知识库中搜索最相关的问答对"
        )

        # 高级选项
        with st.expander("高级选项"):
            col1, col2 = st.columns(2)
            with col1:
                top_k = st.slider("返回结果数量", 1, 10, 3)
            with col2:
                similarity_threshold = st.slider("相似度阈值", 0.1, 0.9, 0.7)

        # 提交按钮
        if st.button("搜索答案", type="primary", use_container_width=True):
            if not question.strip():
                st.warning("请输入问题")
                return

            if not st.session_state.qa_agent:
                st.error("API密钥有误")
                return

            self.process_question(question, top_k, similarity_threshold)

    def process_question(self, question: str, top_k: int, similarity_threshold: float):
        """处理问题并生成回答"""
        with st.spinner("正在搜索知识库并生成回答..."):
            # 临时调整搜索参数
            original_method = st.session_state.qa_agent.search_similar_questions
            st.session_state.qa_agent.search_similar_questions = lambda q: original_method(q, top_k,
                                                                                           similarity_threshold)

            result = st.session_state.qa_agent.ask_question(question)

            # 恢复原始方法
            st.session_state.qa_agent.search_similar_questions = original_method

            # 保存到历史记录
            st.session_state.chat_history.append(result)

            # 显示结果
            self.display_answer_result(result)

    def display_answer_result(self, result: Dict):
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
            with st.expander(f"🔍 相关问答对 (找到 {result['total_matches']} 个)"):
                for i, similar_qa in enumerate(result['similar_questions']):
                    st.markdown(f"**相关问答 {i + 1}** (相似度: {similar_qa['similarity']:.3f})")
                    st.write(f"**问题**: {similar_qa['question']}")
                    st.write(f"**答案**: {similar_qa['answer']}")
                    st.write(f"来源: {similar_qa['source']} | 行号: {similar_qa.get('line_number', 'N/A')}")
                    st.markdown("---")

    def run(self):
        """运行UI应用"""
        self.render_sidebar()
        self.render_main_content()


# 主程序入口
def main():
    ui = JSONLQAUI()
    ui.run()


if __name__ == "__main__":
    main()