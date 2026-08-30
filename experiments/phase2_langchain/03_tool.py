import os

from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool


load_dotenv()


# ======================
# 定义 Tool
# ======================

@tool
def get_sales_data(product_category: str) -> dict:
    """
    查询指定商品类别的销售数据
    """

    database = {
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

    return database.get(
        product_category,
        {}
    )


# ======================
# 初始化模型
# ======================

llm = ChatOpenAI(
    model="deepseek-v4-flash",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
    extra_body={
        "thinking": {
            "type": "disabled"
        }
    }
)


# 绑定工具

llm_with_tools = llm.bind_tools(
    [
        get_sales_data
    ]
)


response = llm_with_tools.invoke(
    """
帮我分析女装销售情况
"""
)

#这段后加入，对应output2
if response.tool_calls:
    tool_call = response.tool_calls[0]
    tool_result = get_sales_data.invoke(
        tool_call["args"]
    )
    print(tool_result)


print(response)

print("----------------")

print(
    "tool_calls:",
    response.tool_calls
)



"output1"
'''
content='我来帮您分析女装销售数据。首先让我查询一下女装类别的销售数据。'
additional_kwargs={'refusal': None} response_metadata={'token_usage': {'completion_tokens': 67,
'prompt_tokens': 286, 'total_tokens': 353, 'completion_tokens_details': None,
'prompt_tokens_details': {'audio_tokens': None, 'cache_write_tokens': None, 'cached_tokens': 0},
'prompt_cache_hit_tokens': 0, 'prompt_cache_miss_tokens': 286},
'model_provider': 'openai', 'model_name': 'deepseek-v4-flash', 'system_fingerprint': 'a26a7955944dc5c60445bff77fac9c8e',
'id': '62f68f90-6626-4ed4-8772-552bc8c083d6', 'finish_reason': 'tool_calls', 'logprobs': None}
id='lc_run--01a01095-a8e7-7ff2-9532-0022b6399648-0' tool_calls=[{'name': 'get_sales_data', 'args': {'product_category': '女装'},
'id': 'call_00_JfRq5VTCMAtQLwU0Pz435337', 'type': 'tool_call'}]
invalid_tool_calls=[] usage_metadata={'input_tokens': 286, 'output_tokens': 67, 'total_tokens': 353,
'input_token_details': {'cache_read': 0}, 'output_token_details': {}}
----------------
tool_calls: [{'name': 'get_sales_data', 'args': {'product_category': '女装'}, 'id': 'call_00_JfRq5VTCMAtQLwU0Pz435337', 'type': 'tool_call'}]
'''

"output2"
'''
{'sales': 100000, 'orders': 1200, 'conversion_rate': 0.035}
content='我先帮你查询女装类别的销售数据。' additional_kwargs={'refusal': None}
response_metadata={'token_usage': {'completion_tokens': 57, 'prompt_tokens': 286, 'total_tokens': 343, 'completion_tokens_details': None,
'prompt_tokens_details': {'audio_tokens': None, 'cache_write_tokens': None, 'cached_tokens': 256},
'prompt_cache_hit_tokens': 256, 'prompt_cache_miss_tokens': 30},
'model_provider': 'openai', 'model_name': 'deepseek-v4-flash', 'system_fingerprint': 'a26a7955944dc5c60445bff77fac9c8e',
'id': '67b44d54-19c7-4772-9bb0-cb2a0aa0c160', 'finish_reason': 'tool_calls', 'logprobs': None}
id='lc_run--01a0135a-148c-7153-a152-b503c4f38fdd-0' tool_calls=[{'name': 'get_sales_data', 'args': {'product_category': '女装'},
'id': 'call_00_GRoQChvj7gitQHlia1ui7108', 'type': 'tool_call'}]
invalid_tool_calls=[] usage_metadata={'input_tokens': 286, 'output_tokens': 57, 'total_tokens': 343,
'input_token_details': {'cache_read': 256}, 'output_token_details': {}}
----------------
tool_calls: [{'name': 'get_sales_data', 'args': {'product_category': '女装'}, 'id': 'call_00_GRoQChvj7gitQHlia1ui7108', 'type': 'tool_call'}]
'''
