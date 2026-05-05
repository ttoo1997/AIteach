import os
import json
import numpy as np
from typing import List, Dict, Any
import dashscope
from dashscope import TextEmbedding
from dashscope import Generation
import streamlit as st
from datetime import datetime
import hashlib


class JSONLQAAgent:
    def __init__(self, api_key: str, knowledge_base_path: str = "knowledge_base/"):
        """
        初始化JSONL格式知识库问答智能体

        Args:
            api_key: 通义千问API密钥
            knowledge_base_path: 知识库文件路径
        """
        self.api_key = api_key
        dashscope.api_key = api_key
        self.knowledge_base_path = knowledge_base_path
        self.qa_pairs = []  # 存储所有问答对
        self.question_embeddings = []  # 问题嵌入向量
        self.embedding_model = "text-embedding-v1"
        self.qa_model = "qwen-max"

        # 初始化知识库
        self.load_knowledge_base()

    def load_knowledge_base(self):
        """加载JSONL格式的知识库文件"""
        if not os.path.exists(self.knowledge_base_path):
            os.makedirs(self.knowledge_base_path)
            st.warning(f"知识库目录 {self.knowledge_base_path} 已创建，请添加JSONL格式的问答对文件")
            return

        # 查找所有JSONL文件
        jsonl_files = [f for f in os.listdir(self.knowledge_base_path)
                       if f.endswith('.jsonl')]

        if not jsonl_files:
            st.warning("未找到JSONL格式的知识库文件")
            return

        total_loaded = 0
        for jsonl_file in jsonl_files:
            file_path = os.path.join(self.knowledge_base_path, jsonl_file)
            loaded_count = self.load_jsonl_qa_file(file_path)
            total_loaded += loaded_count

        st.success(f"成功加载 {total_loaded} 个问答对，来自 {len(jsonl_files)} 个文件")

    def load_jsonl_qa_file(self, file_path: str) -> int:
        """加载单个JSONL问答对文件"""
        try:
            loaded_count = 0
            file_name = os.path.basename(file_path)

            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)

                        # 验证JSONL格式
                        if self.validate_jsonl_format(data):
                            self.add_qa_pair(data, file_name, line_num)
                            loaded_count += 1
                        else:
                            st.warning(f"文件 {file_name} 第 {line_num} 行格式不正确，已跳过")

                    except json.JSONDecodeError as e:
                        st.warning(f"文件 {file_name} 第 {line_num} 行JSON解析错误: {str(e)}")
                        continue

            return loaded_count

        except Exception as e:
            st.error(f"加载文件 {file_path} 时出错: {str(e)}")
            return 0

    def validate_jsonl_format(self, data: Dict) -> bool:
        """验证JSONL格式是否正确"""
        if not isinstance(data, dict):
            return False

        if 'messages' not in data:
            return False

        messages = data['messages']
        if not isinstance(messages, list) or len(messages) < 2:
            return False

        # 我们检查是否包含用户和助手的消息
        has_user = False
        has_assistant = False
        user_content = ""
        assistant_content = ""

        for msg in messages:
            if not isinstance(msg, dict):
                return False
            if 'role' not in msg or 'content' not in msg:
                return False
            if msg['role'] == 'user':
                has_user = True
                user_content = msg['content']
            elif msg['role'] == 'assistant':
                has_assistant = True
                assistant_content = msg['content']

        if not has_user or not has_assistant:
            return False

        if not user_content.strip() or not assistant_content.strip():
            return False

        return True

    def extract_qa_from_jsonl(self, data: Dict) -> Dict:
        """从JSONL数据中提取问答对"""
        question = ""
        answer = ""

        for msg in data['messages']:
            if msg['role'] == 'user':
                question = msg['content']
            elif msg['role'] == 'assistant':
                answer = msg['content']

        return {
            'question': question,
            'answer': answer
        }

    def add_qa_pair(self, data: Dict, source: str, line_num: int):
        """添加问答对并生成问题嵌入"""
        # 提取问答对
        qa_pair = self.extract_qa_from_jsonl(data)

        # 为问答对添加唯一ID和源信息
        qa_id = hashlib.md5(f"{qa_pair['question']}{source}{line_num}".encode()).hexdigest()[:8]
        enhanced_qa = {
            'id': qa_id,
            'question': qa_pair['question'],
            'answer': qa_pair['answer'],
            'source': source,
            'line_number': line_num
        }

        # 生成问题嵌入
        question_embedding = self.get_text_embedding(qa_pair['question'])
        if question_embedding is not None:
            self.qa_pairs.append(enhanced_qa)
            self.question_embeddings.append(question_embedding)

    def get_text_embedding(self, text: str) -> List[float]:
        """获取文本的嵌入向量"""
        try:
            resp = TextEmbedding.call(
                model=self.embedding_model,
                input=text
            )
            if resp.status_code == 200:
                return resp.output['embeddings'][0]['embedding']
            else:
                st.error(f"获取嵌入向量失败: {resp.message}")
                return None
        except Exception as e:
            st.error(f"调用嵌入模型时出错: {str(e)}")
            return None

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)

    def search_similar_questions(self, query: str, top_k: int = 5,
                                 similarity_threshold: float = 0.7) -> List[Dict]:
        """搜索相似问题，返回排序后的问答对"""
        if not self.qa_pairs:
            return []

        query_embedding = self.get_text_embedding(query)
        if query_embedding is None:
            return []

        # 计算相似度
        results = []
        for i, qa_pair in enumerate(self.qa_pairs):
            similarity = self.cosine_similarity(query_embedding, self.question_embeddings[i])
            if similarity >= similarity_threshold:
                result = qa_pair.copy()
                result['similarity'] = similarity
                result['confidence'] = min(similarity * 100, 100)  # 转换为百分比
                results.append(result)

        # 按相似度排序
        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:top_k]

    def generate_enhanced_answer(self, query: str, similar_qa_pairs: List[Dict]) -> Dict:
        """基于相似问答对生成增强答案"""
        if not similar_qa_pairs:
            return {
                'answer': "抱歉，在知识库中没有找到与您问题相关的信息。",
                'source': '无',
                'confidence': 0,
                'type': '未找到'
            }

        # 如果找到高度匹配的问题，直接返回答案
        best_match = similar_qa_pairs[0]
        if best_match['similarity'] > 0.9:
            return {
                'answer': best_match['answer'],
                'source': best_match['source'],
                'confidence': best_match['confidence'],
                'type': '直接匹配',
                'matched_question': best_match['question']
            }

        # 否则使用大模型综合多个相似问答对生成答案
        context = "以下是从知识库中找到的相关问答对：\n\n"
        for i, qa_pair in enumerate(similar_qa_pairs):
            context += f"相关问题 {i + 1} (相似度: {qa_pair['similarity']:.2f}):\n"
            context += f"问题: {qa_pair['question']}\n"
            context += f"答案: {qa_pair['answer']}\n\n"

        prompt = f"""{context}
基于以上相关知识，请回答以下问题：

用户问题：{query}

要求：
1. 严格基于提供的知识库内容回答
2. 如果知识库内容不足以回答，请说明并指出缺少的信息
3. 保持答案准确、专业
4. 不要编造知识库中没有的信息

请给出专业、准确的回答："""

        try:
            response = Generation.call(
                model=self.qa_model,
                prompt=prompt,
                max_length=1500,
                temperature=0.1  # 低温度确保准确性
            )

            if response.status_code == 200:
                return {
                    'answer': response.output.text,
                    'source': '综合多个来源',
                    'confidence': best_match['confidence'],
                    'type': '综合生成',
                    'reference_count': len(similar_qa_pairs)
                }
            else:
                return {
                    'answer': f"生成回答时出错: {response.message}",
                    'source': '系统',
                    'confidence': 0,
                    'type': '错误'
                }

        except Exception as e:
            return {
                'answer': f"调用模型时出错: {str(e)}",
                'source': '系统',
                'confidence': 0,
                'type': '错误'
            }

    def ask_question(self, question: str) -> Dict:
        """回答问题的完整流程"""
        if not self.qa_pairs:
            return {
                'answer': "知识库为空，无法回答问题。请先添加JSONL格式的问答对文件。",
                'sources': [],
                'confidence': 0,
                'type': '系统提示',
                'similar_questions': []
            }

        # 搜索相似问题
        similar_qa_pairs = self.search_similar_questions(question)

        # 生成答案
        answer_result = self.generate_enhanced_answer(question, similar_qa_pairs)

        # 构建完整结果
        result = {
            'question': question,
            'answer': answer_result['answer'],
            'sources': list(set([qa['source'] for qa in similar_qa_pairs])),
            'confidence': answer_result['confidence'],
            'answer_type': answer_result['type'],
            'timestamp': datetime.now().isoformat(),
            'similar_questions': similar_qa_pairs,
            'total_matches': len(similar_qa_pairs)
        }

        # 添加额外信息
        if 'matched_question' in answer_result:
            result['matched_question'] = answer_result['matched_question']
        if 'reference_count' in answer_result:
            result['reference_count'] = answer_result['reference_count']

        return result