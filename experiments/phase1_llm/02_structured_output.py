import os
import json

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


prompt = """
分析下面这条用户需求，并严格返回 JSON：

用户需求：
“把去年双11和今年双11的手机销售额进行对比，并找出增长最快的品牌”

JSON 必须包含以下字段：
- intent：用户意图
- object：分析对象
- time_range：时间范围
- analysis_type：分析类型
- metrics：指标
- dimensions：维度
- comparison：对比

不要输出 JSON 以外的任何内容。
"""


response = client.chat.completions.create(
    model="deepseek-v4-flash",
    messages=[
        {
            "role": "user",
            "content": prompt,
        }
    ],
)

content = response.choices[0].message.content

print("模型原始输出：")
print(content)

result = json.loads(content)

print("\nPython解析后的结果：")
print(result)

print("\n单独读取字段：")
print("intent =", result["intent"])
print("object =", result["object"])
print("time_range =", result["time_range"])
print("metrics =", result["metrics"])
print("dimensions =", result["dimensions"])
print("comparison =", result["comparison"])



'''
#output
模型原始输出：
{"intent": "对比分析用户提供的两个时间段的手机销售额，并识别增长最快的品牌", "object": "手机销售数据", "time_range": ["去年双11", "今年双11"], "analysis_type": "对比分析", "metrics": ["销售额"], "dimensions": ["品牌"], "comparison": {"type": "同比增长", "target": "销售额", "select": "增长最快的品牌"}}

Python解析后的结果：
{'intent': '对比分析用户提供的两个时间段的手机销售额，并识别增长最快的品牌', 'object': '手机销售数据', 'time_range': ['去年双11', '今年双11'], 'analysis_type': '对比分析', 'metrics': ['销售额'], 'dimensions': ['品牌'], 'comparison': {'type': '同比增长', 'target': '销售额', 'select': '增长最快的品牌'}}

单独读取字段：
intent = 对比分析用户提供的两个时间段的手机销售额，并识别增长最快的品牌
object = 手机销售数据
time_range = ['去年双11', '今年双11']
metrics = ['销售额']
dimensions = ['品牌']
comparison = {'type': '同比增长', 'target': '销售额', 'select': '增长最快的品牌'}
'''
