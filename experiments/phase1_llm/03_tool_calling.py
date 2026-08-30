import os
import json

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)


# 这是我们的工具
def get_sales_data(product_category: str):
    """
    查询销售数据
    """

    fake_database = {
        "女装": {
            "sales": 100000,
            "orders": 1200,
            "conversion_rate": 0.035
        },
        "手机": {
            "sales": 500000,
            "orders": 3000,
            "conversion_rate": 0.025
        }
    }

    return fake_database.get(
        product_category,
        {}
    )


tools = [
    {
        "type": "function",
        "function": {
            "name": "get_sales_data",
            "description": "查询指定商品类别的销售数据",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_category": {
                        "type": "string",
                        "description": "商品类别"
                    }
                },
                "required": [
                    "product_category"
                ]
            }
        }
    }
]


response = client.chat.completions.create(
    model="deepseek-v4-flash",
    messages=[
        {
            "role": "user",
            "content":
            "帮我分析女装销售情况"
        }
    ],
    tools=tools
)


message = response.choices[0].message


print(message)


'''
ChatCompletionMessage(content='我来帮您分析女装销售情况，让我先获取相关数据。',
refusal=None, role='assistant', annotations=None, audio=None, function_call=None,
tool_calls=[ChatCompletionMessageFunctionToolCall(id='call_00_VkPKaOYEsZKj5sDqmpK01313',
function=Function(arguments='{"product_category": "女装"}', name='get_sales_data'), type='function', index=0)])
'''
