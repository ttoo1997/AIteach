import hashlib
import json
import os
import pickle
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import dashscope
import numpy as np
from dashscope import Generation, TextEmbedding

from app_config import DEFAULT_CACHE_DIR, DEFAULT_EMBEDDING_MODEL, DEFAULT_KB_PATH, DEFAULT_QA_MODEL
from runtime_env import clear_invalid_proxy_env
from schemas.contracts import RetrievalHit, RetrievalResponse


clear_invalid_proxy_env()


class JSONLQAAgent:
    def __init__(self, api_key: str, knowledge_base_path: Optional[str] = None):
        self.api_key = api_key
        dashscope.api_key = api_key
        self.embedding_model = os.getenv("QWEN_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
        self.qa_model = os.getenv("QWEN_QA_MODEL", DEFAULT_QA_MODEL)
        self.qa_pairs: List[Dict[str, Any]] = []
        self.question_embeddings: List[Optional[List[float]]] = []
        self.loaded_files: List[str] = []
        self.embedding_enabled = True
        self.direct_match_threshold = min(max(float(os.getenv("QA_DIRECT_MATCH_THRESHOLD", "0.82")), 0.5), 0.98)
        self.load_warnings: List[str] = []
        self.last_load_summary: Dict[str, Any] = {}
        self.knowledge_base_path = self.resolve_knowledge_base_path(knowledge_base_path)
        self.cache_dir = Path(os.getenv("KB_CACHE_DIR", DEFAULT_CACHE_DIR))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.embedding_cache_path = self.cache_dir / "embedding_cache.pkl"
        self._embedding_cache = self.load_embedding_cache()
        self.load_knowledge_base()

    @staticmethod
    def resolve_knowledge_base_path(knowledge_base_path: Optional[str]) -> str:
        if knowledge_base_path:
            return knowledge_base_path

        env_path = os.getenv("KNOWLEDGE_BASE_PATH")
        if env_path:
            return env_path

        cwd = Path.cwd()
        project_root = Path(__file__).resolve().parents[1]
        candidates = [
            Path(DEFAULT_KB_PATH),
            project_root / "knowledge_base",
            cwd / "knowledge_base",
            project_root / "knowledge_base.jsonl",
            cwd / "knowledge_base.jsonl",
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return str(project_root / "knowledge_base")

    def load_embedding_cache(self) -> Dict[str, List[float]]:
        if self.embedding_cache_path.exists():
            try:
                with open(self.embedding_cache_path, "rb") as file:
                    data = pickle.load(file)
                    if isinstance(data, dict):
                        return data
            except Exception:
                pass
        return {}

    def save_embedding_cache(self) -> None:
        try:
            with open(self.embedding_cache_path, "wb") as file:
                pickle.dump(self._embedding_cache, file)
        except Exception:
            pass

    def cached_embedding_count(self) -> int:
        return len(self._embedding_cache)

    @staticmethod
    def embedding_key(text: str) -> str:
        return hashlib.md5(text.strip().encode("utf-8")).hexdigest()

    def reset_kb(self) -> None:
        self.qa_pairs = []
        self.question_embeddings = []
        self.loaded_files = []
        self.embedding_enabled = True
        self.load_warnings = []

    def load_knowledge_base(self, force_reload: bool = False) -> Dict[str, Any]:
        if force_reload:
            self._embedding_cache = self.load_embedding_cache()
        self.reset_kb()
        kb_path = Path(self.knowledge_base_path)

        if kb_path.is_file() and kb_path.suffix.lower() == ".jsonl":
            loaded = self.load_jsonl_qa_file(str(kb_path))
            self.loaded_files = [str(kb_path)] if loaded >= 0 else []
            self.last_load_summary = {
                "level": "success",
                "message": f"知识库已从 {kb_path} 加载，共 {loaded} 条问答。",
                "loaded_count": loaded,
                "file_count": len(self.loaded_files),
            }
            return self.last_load_summary

        if not kb_path.exists():
            kb_path.mkdir(parents=True, exist_ok=True)
            self.last_load_summary = {
                "level": "warning",
                "message": f"知识库目录不存在，已创建空目录：{kb_path}",
                "loaded_count": 0,
                "file_count": 0,
            }
            return self.last_load_summary

        jsonl_files = sorted([path for path in kb_path.iterdir() if path.suffix.lower() == ".jsonl"])
        if not jsonl_files:
            self.last_load_summary = {
                "level": "warning",
                "message": f"目录 {kb_path} 下未找到 JSONL 文件。",
                "loaded_count": 0,
                "file_count": 0,
            }
            return self.last_load_summary

        total_loaded = 0
        self.loaded_files = [str(path) for path in jsonl_files]
        for jsonl_file in jsonl_files:
            total_loaded += self.load_jsonl_qa_file(str(jsonl_file))
        self.last_load_summary = {
            "level": "success",
            "message": f"知识库已加载，共 {total_loaded} 条问答，来自 {len(jsonl_files)} 个文件。",
            "loaded_count": total_loaded,
            "file_count": len(jsonl_files),
        }
        return self.last_load_summary

    def load_jsonl_qa_file(self, file_path: str) -> int:
        loaded_count = 0
        file_name = os.path.basename(file_path)
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                for line_num, line in enumerate(file, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError as exc:
                        self.load_warnings.append(f"{file_name} 第 {line_num} 行 JSON 解析失败：{exc}")
                        continue

                    if not self.validate_jsonl_format(data):
                        self.load_warnings.append(f"{file_name} 第 {line_num} 行格式不符合 messages 问答结构。")
                        continue

                    if self.add_qa_pair(data, file_name, line_num):
                        loaded_count += 1
        except Exception as exc:
            self.load_warnings.append(f"加载文件 {file_path} 失败：{exc}")
        return loaded_count

    @staticmethod
    def validate_jsonl_format(data: Dict[str, Any]) -> bool:
        if not isinstance(data, dict) or "messages" not in data:
            return False
        messages = data["messages"]
        if not isinstance(messages, list) or len(messages) < 2:
            return False
        has_user = any(
            isinstance(msg, dict) and msg.get("role") == "user" and str(msg.get("content", "")).strip()
            for msg in messages
        )
        has_assistant = any(
            isinstance(msg, dict) and msg.get("role") == "assistant" and str(msg.get("content", "")).strip()
            for msg in messages
        )
        return has_user and has_assistant

    @staticmethod
    def extract_qa_from_jsonl(data: Dict[str, Any]) -> Dict[str, str]:
        question = ""
        answer = ""
        for msg in data["messages"]:
            if msg["role"] == "user":
                question = str(msg["content"])
            elif msg["role"] == "assistant":
                answer = str(msg["content"])
        return {"question": question, "answer": answer}

    def add_qa_pair(self, data: Dict[str, Any], source: str, line_num: int) -> bool:
        qa_pair = self.extract_qa_from_jsonl(data)
        embedding = self.get_text_embedding(qa_pair["question"]) if self.embedding_enabled else None
        qa_id = hashlib.md5(f"{qa_pair['question']}{source}{line_num}".encode()).hexdigest()[:8]
        self.qa_pairs.append(
            {
                "id": qa_id,
                "question": qa_pair["question"],
                "answer": qa_pair["answer"],
                "source": source,
                "line_number": line_num,
            }
        )
        self.question_embeddings.append(embedding)
        return True

    def get_text_embedding(self, text: str) -> Optional[List[float]]:
        key = self.embedding_key(text)
        if key in self._embedding_cache:
            return self._embedding_cache[key]
        try:
            resp = TextEmbedding.call(model=self.embedding_model, input=text)
            if resp.status_code == 200:
                embedding = resp.output["embeddings"][0]["embedding"]
                self._embedding_cache[key] = embedding
                self.save_embedding_cache()
                return embedding
            self.embedding_enabled = False
            self.load_warnings.append(f"Embedding 接口失败，已退化为关键词检索：{resp.message}")
        except Exception as exc:
            self.embedding_enabled = False
            self.load_warnings.append(f"Embedding 接口异常，已退化为关键词检索：{exc}")
        return None

    @staticmethod
    def tokenize(text: str) -> List[str]:
        tokens = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", text.lower())
        return [token for token in tokens if token.strip()]

    @staticmethod
    def extract_formula_terms(text: str) -> List[str]:
        terms = re.findall(r"[A-Za-z][A-Za-z0-9_]*", text)
        important = {"r2", "x2", "e2", "s", "n", "t", "i", "u", "p", "cos", "phi"}
        return [term.lower() for term in terms if term.lower() in important or len(term) > 2]

    @staticmethod
    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        v1, v2 = np.array(vec1), np.array(vec2)
        denom = np.linalg.norm(v1) * np.linalg.norm(v2)
        if denom == 0:
            return 0.0
        return float(np.dot(v1, v2) / denom)

    def lexical_similarity(self, query: str, question: str) -> float:
        q_tokens = set(self.tokenize(query))
        d_tokens = set(self.tokenize(question))
        if not q_tokens or not d_tokens:
            return 0.0
        overlap = len(q_tokens & d_tokens)
        coverage = overlap / max(len(q_tokens), 1)
        precision = overlap / max(len(d_tokens), 1)
        score = (0.7 * coverage) + (0.3 * precision)
        if query.strip() and query.strip() in question:
            score += 0.2
        return min(score, 1.0)

    def formula_similarity(self, query: str, question: str) -> float:
        q_terms = set(self.extract_formula_terms(query))
        d_terms = set(self.extract_formula_terms(question))
        if not q_terms or not d_terms:
            return 0.0
        return len(q_terms & d_terms) / max(len(q_terms), 1)

    def search_similar_questions(
        self,
        query: str,
        top_k: int = 5,
        similarity_threshold: float = 0.18,
    ) -> List[Dict[str, Any]]:
        if not self.qa_pairs:
            return []

        query_embedding = None
        use_embedding = self.embedding_enabled and any(vec is not None for vec in self.question_embeddings)
        if use_embedding:
            query_embedding = self.get_text_embedding(query)
            if query_embedding is None:
                use_embedding = False

        results: List[RetrievalHit] = []
        normalized_query = query.strip().lower()
        for index, qa_pair in enumerate(self.qa_pairs):
            search_text = f"{qa_pair['question']} {qa_pair['answer']}"
            embedding_score = 0.0
            if use_embedding and self.question_embeddings[index] is not None:
                embedding_score = self.cosine_similarity(query_embedding, self.question_embeddings[index])  # type: ignore[arg-type]

            lexical_score = self.lexical_similarity(query, search_text)
            formula_score = self.formula_similarity(query, search_text)
            exact_boost = 0.08 if normalized_query and normalized_query in search_text.lower() else 0.0

            if use_embedding:
                final_score = (0.55 * embedding_score) + (0.30 * lexical_score) + (0.15 * formula_score) + exact_boost
            else:
                final_score = (0.75 * lexical_score) + (0.25 * formula_score) + exact_boost

            final_score = min(final_score, 1.0)
            if final_score < similarity_threshold:
                continue

            results.append(
                RetrievalHit(
                    id=qa_pair["id"],
                    question=qa_pair["question"],
                    answer=qa_pair["answer"],
                    source=qa_pair["source"],
                    line_number=qa_pair["line_number"],
                    embedding_score=embedding_score,
                    lexical_score=lexical_score,
                    formula_score=formula_score,
                    score=final_score,
                    confidence=min(final_score * 100, 100.0),
                )
            )

        results.sort(key=lambda item: item.score, reverse=True)
        return [item.to_dict() for item in results[:top_k]]

    def build_reference_context(self, similar_qa_pairs: List[Dict[str, Any]], max_items: int = 3) -> str:
        if not similar_qa_pairs:
            return "未找到可用课程知识参考。"

        lines = ["以下是知识库中最相关的课程依据：", ""]
        for index, qa_pair in enumerate(similar_qa_pairs[:max_items], 1):
            lines.extend(
                [
                    f"参考 {index}：",
                    f"- 问题：{qa_pair['question']}",
                    f"- 答案：{qa_pair['answer']}",
                    f"- 来源：{qa_pair['source']} 第 {qa_pair['line_number']} 行",
                    f"- 综合相关度：{qa_pair['score']:.3f}",
                    "",
                ]
            )
        return "\n".join(lines).strip()

    def generate_enhanced_answer(self, query: str, similar_qa_pairs: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not similar_qa_pairs:
            return {
                "answer": "知识库中没有找到与该问题足够相关的依据，请补充课程资料或换一种问法。",
                "source": "system",
                "confidence": 0,
                "type": "未找到依据",
            }

        best_match = similar_qa_pairs[0]
        if best_match["score"] >= self.direct_match_threshold and best_match["lexical_score"] > 0.45:
            return {
                "answer": best_match["answer"],
                "source": best_match["source"],
                "confidence": best_match["confidence"],
                "type": "直接匹配",
                "matched_question": best_match["question"],
            }

        context = self.build_reference_context(similar_qa_pairs, max_items=4)
        messages = [
            {
                "role": "system",
                "content": (
                    "你是电机学知识库问答助手。必须基于给出的课程依据回答。"
                    "如果资料不足，请直接说明资料不足，不要编造。"
                    "输出要简洁清楚，并在末尾列出参考来源。"
                ),
            },
            {
                "role": "user",
                "content": f"{context}\n\n用户问题：{query}\n\n请基于以上依据作答。",
            },
        ]

        try:
            response = Generation.call(
                model=self.qa_model,
                messages=messages,
                result_format="message",
                temperature=0.1,
            )
            if response.status_code == 200:
                answer = response.output.choices[0].message.content
                return {
                    "answer": answer if isinstance(answer, str) else str(answer),
                    "source": "multiple",
                    "confidence": best_match["confidence"],
                    "type": "检索增强回答",
                    "reference_count": len(similar_qa_pairs),
                }
            return {
                "answer": f"生成回答失败：{response.message}",
                "source": "system",
                "confidence": 0,
                "type": "错误",
            }
        except Exception as exc:
            return {
                "answer": f"调用模型时出错：{exc}",
                "source": "system",
                "confidence": 0,
                "type": "错误",
            }

    def ask_question(self, question: str, top_k: int = 3, similarity_threshold: float = 0.18) -> Dict[str, Any]:
        if not self.qa_pairs:
            return RetrievalResponse(
                question=question,
                answer="知识库为空，当前无法完成问答。",
                sources=[],
                confidence=0,
                answer_type="系统提示",
                similar_questions=[],
                total_matches=0,
                timestamp=datetime.now().isoformat(),
                kb_path=self.knowledge_base_path,
                loaded_files=self.loaded_files,
                embedding_enabled=self.embedding_enabled,
                metadata={"load_warnings": self.load_warnings},
            ).to_dict()

        similar_qa_pairs = self.search_similar_questions(question, top_k=top_k, similarity_threshold=similarity_threshold)
        answer_result = self.generate_enhanced_answer(question, similar_qa_pairs)
        return RetrievalResponse(
            question=question,
            answer=answer_result["answer"],
            sources=list(dict.fromkeys([qa["source"] for qa in similar_qa_pairs])),
            confidence=float(answer_result["confidence"]),
            answer_type=answer_result["type"],
            similar_questions=similar_qa_pairs,
            total_matches=len(similar_qa_pairs),
            timestamp=datetime.now().isoformat(),
            kb_path=self.knowledge_base_path,
            loaded_files=self.loaded_files,
            embedding_enabled=self.embedding_enabled,
            metadata={
                "matched_question": answer_result.get("matched_question"),
                "reference_count": answer_result.get("reference_count"),
                "load_warnings": self.load_warnings,
            },
        ).to_dict()
