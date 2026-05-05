import streamlit as st
import json
import pandas as pd
import requests
from typing import List, Dict, Tuple
import numpy as np
import os


class KnowledgeBaseQA:
    def __init__(self, knowledge_file: str, api_key: str = None):
        self.knowledge_file = knowledge_file
        self.qa_pairs = []
        self.questions = []
        self.answers = []
        self.api_key = api_key

        # 加载知识库
        self._load_knowledge_base()

    def _load_knowledge_base(self):
        """加载JSONL格式的知识库"""
        try:
            with open(self.knowledge_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line.strip())
                        user_content = ""
                        assistant_content = ""

                        for message in data.get('messages', []):
                            if message.get('role') == 'user':
                                user_content = message.get('content', '')
                            elif message.get('role') == 'assistant':
                                assistant_content = message.get('content', '')

                        if user_content and assistant_content:
                            self.qa_pairs.append({
                                'question': user_content,
                                'answer': assistant_content
                            })
                            self.questions.append(user_content)
                            self.answers.append(assistant_content)

            st.success(f"成功加载 {len(self.qa_pairs)} 个问答对")

        except Exception as e:
            st.error(f"加载知识库失败: {e}")

    def set_api_key(self, api_key: str):
        """设置API密钥"""
        self.api_key = os.getenv("DASHSCOPE_API_KEY")

    def rerank_with_qwen(self, query: str, top_k: int = 5) -> List[Dict]:
        """直接使用Qwen重排序模型对所有知识库内容进行检索和排序"""
        if not self.api_key:
            st.error("请先配置Qwen API密钥")
            return []

        try:
            # 准备所有问题作为候选文档
            candidate_texts = self.questions

            # Qwen重排序API调用
            api_url = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            data = {
                "query": query,
                "documents": candidate_texts,
                "top_n": min(top_k, len(candidate_texts)),
                "model": "qwen3-rerank"  # 根据实际模型名称调整
            }

            # 这里假设API可以一次性处理所有文档
            with st.spinner(f"正在使用Qwen重排序模型处理 {len(candidate_texts)} 个候选文档..."):
                response = requests.post(api_url, headers=headers, json=data, timeout=60)

            if response.status_code == 200:
                result = response.json()
                reranked_results = []

                for item in result.get('results', []):
                    index = item.get('index', 0)
                    score = item.get('score', 0.0)

                    if index < len(self.qa_pairs):
                        reranked_results.append({
                            'question': self.questions[index],
                            'answer': self.answers[index],
                            'similarity_score': score,
                            'rank': len(reranked_results) + 1
                        })

                return reranked_results
            else:
                st.error(f"重排序API调用失败: {response.status_code} - {response.text}")
                return []

        except Exception as e:
            st.error(f"重排序失败: {e}")
            return []

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """直接使用Qwen重排序模型搜索知识库"""
        if not self.qa_pairs:
            st.warning("知识库为空")
            return []

        if not self.api_key:
            st.error("请先配置Qwen API密钥")
            return []

        return self.rerank_with_qwen(query, top_k)


def initialize_session_state():
    """初始化会话状态"""
    if 'qa_system' not in st.session_state:
        if os.path.exists('knowledge_base.jsonl'):
            st.session_state.qa_system = KnowledgeBaseQA('knowledge_base.jsonl')
        else:
            st.session_state.qa_system = None

    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []

    if 'current_results' not in st.session_state:
        st.session_state.current_results = []

    if 'api_key_configured' not in st.session_state:
        st.session_state.api_key_configured = False


def api_key_configuration():
    """API密钥配置界面"""
    st.subheader("API密钥配置")

    # 说明
    st.markdown("""
    为了使用Qwen重排序功能，您需要配置API密钥。
    请按照以下步骤获取API密钥：
    1. 访问 [阿里云百炼](https://bailian.aliyun.com/) 或 [DashScope](https://dashscope.aliyun.com/)
    2. 注册账号并登录
    3. 在控制台中创建API密钥
    4. 将API密钥粘贴到下方输入框中
    """)

    # API密钥输入
    api_key = st.text_input(
        "Qwen API密钥",
        type="password",
        placeholder="请输入您的Qwen API密钥",
        help="您的API密钥将仅用于当前会话，不会被保存"
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("保存API密钥", type="primary"):
            if api_key:
                st.session_state.api_key_configured = True
                if st.session_state.qa_system:
                    st.session_state.qa_system.set_api_key(api_key)
                st.success("API密钥已保存！")
            else:
                st.error("请输入有效的API密钥")

    with col2:
        if st.button("重置API密钥"):
            st.session_state.api_key_configured = False
            if st.session_state.qa_system:
                st.session_state.qa_system.set_api_key(None)
            st.info("API密钥已重置")

    return api_key


def main():
    st.set_page_config(
        page_title="智能知识库问答系统",
        layout="wide"
    )

    st.title("智能知识库问答系统")
    st.markdown("基于Qwen重排序模型的精准问答系统")

    # 初始化会话状态
    initialize_session_state()

    # 侧边栏
    with st.sidebar:
        st.header("系统配置")

        # API密钥配置
        api_key_configuration()

        # 知识库文件上传
        st.subheader("📚 知识库管理")
        uploaded_file = st.file_uploader("上传知识库文件 (JSONL格式)", type=['jsonl'])

        if uploaded_file is not None:
            # 保存上传的文件
            with open('knowledge_base.jsonl', 'wb') as f:
                f.write(uploaded_file.getvalue())

            # 重新初始化QA系统
            st.session_state.qa_system = KnowledgeBaseQA('knowledge_base.jsonl')
            if st.session_state.api_key_configured:
                st.session_state.qa_system.set_api_key(st.session_state.get('api_key', ''))
            st.session_state.chat_history = []
            st.success("知识库文件上传成功！")

        # 如果没有知识库文件，创建示例
        if st.session_state.qa_system is None:
            if st.button("使用示例知识库"):
                create_sample_knowledge_base()
                st.session_state.qa_system = KnowledgeBaseQA('knowledge_base.jsonl')
                if st.session_state.api_key_configured:
                    st.session_state.qa_system.set_api_key(st.session_state.get('api_key', ''))
                st.rerun()

        # 搜索参数配置
        st.subheader("搜索参数")
        top_k = st.slider("返回结果数量", 1, 10, 5)

        if st.button("清空对话历史"):
            st.session_state.chat_history = []
            st.rerun()

        # 系统信息
        st.subheader("📊 系统信息")
        if st.session_state.qa_system:
            st.info(f"知识库大小: {len(st.session_state.qa_system.qa_pairs)} 个问答对")
            st.info(f"API状态: {'✅ 已配置' if st.session_state.api_key_configured else '❌ 未配置'}")
            st.info("检索方式: 直接使用Qwen重排序")

    # 主界面
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("对话界面")

        # 检查API密钥是否已配置
        if not st.session_state.api_key_configured:
            st.warning("请先在侧边栏配置Qwen API密钥以使用问答功能")

        # 用户输入
        user_query = st.text_area(
            "请输入您的问题：",
            placeholder="例如：磁路的欧姆定律表达式是什么？",
            height=100,
            disabled=not st.session_state.api_key_configured
        )

        if st.button("发送问题", type="primary", disabled=not st.session_state.api_key_configured) and user_query:
            if st.session_state.qa_system is None:
                st.error("请先上传知识库文件或使用示例知识库")
            else:
                # 搜索知识库
                results = st.session_state.qa_system.search(user_query, top_k=top_k)

                if results:
                    best_answer = results[0]['answer']

                    # 添加到对话历史
                    st.session_state.chat_history.append({
                        'question': user_query,
                        'answer': best_answer,
                        'timestamp': pd.Timestamp.now()
                    })

                    st.session_state.current_results = results
                    st.success(f"找到 {len(results)} 个相关结果")
                else:
                    st.warning("未在知识库中找到相关答案")

        # 显示对话历史
        st.subheader("对话历史")
        if st.session_state.chat_history:
            for i, chat in enumerate(reversed(st.session_state.chat_history[-10:])):
                with st.expander(f"Q: {chat['question']}"):
                    st.write(f"**A:** {chat['answer']}")
                    st.caption(f"时间: {chat['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            st.info("暂无对话历史")

    with col2:
        st.subheader("检索结果详情")

        if st.session_state.current_results:
            st.info(f"检索范围: 全部 {len(st.session_state.qa_system.questions)} 个问题")

            for i, result in enumerate(st.session_state.current_results):
                with st.container():
                    st.markdown(f"**结果 #{result['rank']}** (相似度: {result['similarity_score']:.3f})")
                    st.text_area(
                        f"问题 {i}",
                        value=result['question'],
                        height=80,
                        key=f"question_{i}",
                        disabled=True
                    )
                    st.text_area(
                        f"答案 {i}",
                        value=result['answer'],
                        height=120,
                        key=f"answer_{i}",
                        disabled=True
                    )
                    st.divider()
        else:
            st.info("暂无检索结果")

    # 系统状态显示
    with st.expander("系统状态"):
        if st.session_state.qa_system:
            st.success(f"知识库已加载: {len(st.session_state.qa_system.qa_pairs)} 个问答对")
            st.info(f"API状态: {'已配置' if st.session_state.api_key_configured else '未配置'}")
            st.info("检索方式: 直接Qwen重排序")
        else:
            st.error("知识库未加载")


if __name__ == "__main__":
    main()