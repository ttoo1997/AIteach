import dashscope
from dashscope import Generation
from dashscope.api_entities.dashscope_response import Role
import os
from dashscope import MultiModalConversation
from PIL import Image
import json
from typing import Optional, Dict, Any


class QwenTextAgent:

    def __init__(self, api_key: str):
        """
        初始化文本智能体

        Args:
            api_key: 通义千问API密钥
        """
        dashscope.api_key = api_key
        self.model = "qwen2.5-7b-instruct-ft-202510071758-b854"

    def query(self, text: str, history: Optional[list] = None) -> str:
        try:
            if history is None:
                history = []

            # 构建消息列表
            messages = history + [
                {"role": Role.SYSTEM, "content":"你是一个电机学解题高手，你要解决这个题目，并且将解答中的算式用纯文本格式输出，要求有详细解析过程，不要只有算式"},
                {"role": Role.USER, "content": text}]

            response = Generation.call(
                model=self.model,
                messages=messages,
                result_format='message'
            )

            if response.status_code == 200:
                return response.output.choices[0].message.content
            else:
                return f"错误: {response.code} - {response.message}"

        except Exception as e:
            return f"调用API时发生错误: {str(e)}"


class QwenVisionAgent:

    def __init__(self, api_key: str):
        """
        Args:
            api_key: 通义千问API密钥
        """
        dashscope.api_key = api_key
        self.model = "qwen3-vl-plus"



    def extract_text_from_image(self, image_path: str) -> str:
        """
        Args:
            image_path: 图片文件路径
        Returns:
            str: 提取的文字内容
        """
        try:
            local_path = image_path
            true_path = f"file://{local_path}"
            # 构建消息内容
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            'image': true_path,
                        },
                        {
                            "text": "请仔细识别这张图片中的所有文字内容，特别是如果这是一道电机学相关的题目，请完整准确地提取题目文字。只需要返回识别的文字内容，不要添加其他解释。"
                        }
                    ]
                }
            ]

            response = MultiModalConversation.call(
                self.model,
                messages=messages,
                result_format='message'
            )


            return response.output.choices[0].message.content


        except Exception as e:
            return f"图片文字提取失败: {str(e)}"


class MotorTheoryWorkflow:
    """工作流"""
    def __init__(self, api_key: str):
        """
            api_key: 通义千问API密钥
        """
        self.vision_agent = QwenVisionAgent(api_key)
        self.text_agent = QwenTextAgent(api_key)

        # 电机学专家提示词
        self.expert_prompt = """你是一个电机学解题高手，你要解决这个题目，并且将解答中的算式用纯文本格式输出，要求有详细解析过程，不要只有算式


请开始解答："""

    def solve_motor_problem(self, image_path: str) -> Dict[str, Any]:
        """
        Args:
            image_path: 电机学题目图片路径

        Returns:
            Dict: 包含提取的题目和解答结果的字典
        """
        print("开始处理电机学题目图片...")

        # 第一步：使用视觉智能体提取题目文字
        print("正在从图片中提取题目文字...")
        extracted_text = self.vision_agent.extract_text_from_image(image_path)

        if "错误" in extracted_text or "失败" in extracted_text:
            return {
                "success": False,
                "error": extracted_text,
                "extracted_text": None,
                "solution": None
            }

        print("题目文字提取成功！")
        print(f"提取的题目: {extracted_text}")

        # 第二步：使用文本智能体解答题目
        print("正在使用电机学专家模型解答题目...")
        solution = self.text_agent.query(extracted_text)

        print("题目解答完成！")

        return {
            "success": True,
            "extracted_text": extracted_text,
            "solution": solution,
            "image_path": image_path
        }

    def print_solution(self, result: Dict[str, Any]):
        """输出解答结果"""
        if result["success"]:
            print(f"\n图片路径: {result['image_path']}")
            print(f"\n提取的题目:")
            print(result['extracted_text'])
            print(f"\nAI解答:")
            print(result['solution'])
        else:
            print(f"\n处理失败: {result['error']}")


def main():
    # 设置API密钥
    API_KEY = os.getenv("DASHSCOPE_API_KEY")  # 请在此处填入您的通义千问API密钥

    # 初始化工作流
    workflow = MotorTheoryWorkflow(API_KEY)

    # 示例1：处理电机学题目图片
    image_path = "C:/Users/ttoo1997/Desktop/example.jpg"  # 请替换为实际的图片路径

    if os.path.exists(image_path):
        print(f"处理图片: {image_path}")
        result = workflow.solve_motor_problem(image_path)
        workflow.print_solution(result)
    else:
        print(f"图片文件不存在: {image_path}")
        print("请确保图片路径正确，或者使用以下示例测试文本功能:")

if __name__ == "__main__":
    main()