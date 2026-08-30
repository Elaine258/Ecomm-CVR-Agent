import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY")

if not api_key:
    raise ValueError("未找到 DEEPSEEK_API_KEY，请检查 .env")

client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com",
)

response = client.chat.completions.create(
    model="deepseek-v4-flash",
    messages=[
        {"role": "system", "content":"只用简体中文回答"},
        {
            "role": "user",
            "content": "你是一名AI产品经理。请用“输入 → 思考 → 工具 → 结果 → 下一步决策”的结构，解释什么是 Agent。不要使用过于技术化的术语。",
        }
    ],
)

print(response.choices[0].message.content)
