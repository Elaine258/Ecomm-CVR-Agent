import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from langchain_openai import ChatOpenAI


load_dotenv()


class UserIntent(BaseModel):
    """
    用户需求分析结果
    """

    intent: str = Field(
        description="用户意图"
    )

    object: str = Field(
        description="分析对象"
    )

    time_range: str = Field(
        description="时间范围"
    )

    analysis_type: str = Field(
        description="分析类型"
    )


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


structured_llm = llm.with_structured_output(
    UserIntent,
    method="function_calling"
)


result = structured_llm.invoke(
    """
帮我分析最近30天女装销售额下降的原因
"""
)


print(result)

print("----------------")

print("intent:", result.intent)
print("object:", result.object)
print("time_range:", result.time_range)
print("analysis_type:", result.analysis_type)



"output1"
'''
intent='分析销售额下降的原因' object='女装' time_range='最近30天' analysis_type='原因分析'
----------------
intent: 分析销售额下降的原因
object: 女装
time_range: 最近30天
analysis_type: 原因分析
'''
