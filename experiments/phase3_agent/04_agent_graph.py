import os
import json

import pandas as pd

from dotenv import load_dotenv

from langchain_openai import ChatOpenAI

from langchain_core.tools import tool

from langchain_core.messages import (
    HumanMessage,
    SystemMessage
)

from langgraph.graph import (
    StateGraph,
    START,
    END,
    MessagesState
)

from langgraph.prebuilt import ToolNode


load_dotenv()


# ==========================
# 1. 加载TheLook数据
# ==========================

DATA_DIR = r"E:\agent\data"


order_items = pd.read_csv(
    os.path.join(
        DATA_DIR,
        "order_items.csv"
    )
)


products = pd.read_csv(
    os.path.join(
        DATA_DIR,
        "products_old.csv"
    )
)



# ==========================
# 2. 定义Tool
# ==========================


@tool
def query_sales_data(category: str) -> dict:
    """
    查询商品类别销售数据
    """

    category_products = products[
        products["category"].str.lower()
        ==
        category.lower()
    ]


    if category_products.empty:

        return {
            "error":
            f"没有找到{category}"
        }


    product_ids = category_products["id"]


    items = order_items[
        order_items["product_id"]
        .isin(product_ids)
    ]


    return {

        "category":
            category,

        "sales":
            round(
                float(
                    items["sale_price"]
                    .sum()
                ),
                2
            ),

        "items":
            len(items)
    }



tools = [
    query_sales_data
]



# ==========================
# 3. 初始化LLM
# ==========================


llm = ChatOpenAI(

    model="deepseek-v4-flash",

    api_key=os.getenv(
        "DEEPSEEK_API_KEY"
    ),

    base_url=
    "https://api.deepseek.com",

    extra_body={
        "thinking":{
            "type":"disabled"
        }
    }

)


llm_with_tools = llm.bind_tools(
    tools
)



# ==========================
# 4. 定义State 使用MessagesState，自带add_messages归约器
# ==========================
class AgentState(MessagesState):
    pass


# ==========================
# 5. Agent Node
# ==========================


def agent_node(
    state: AgentState
):
    response = llm_with_tools.invoke(
        state["messages"]
    )
    # 只返回新产生消息，归约器自动追加到历史，不会覆盖
    return {
        "messages":[response]
    }



# ==========================
# 6. 判断是否调用Tool
# ==========================


def should_continue(
    state: AgentState
):

    last_message = (
        state["messages"][-1]
    )

    if last_message.tool_calls:
        return "tool"
    return "end"



# ==========================
# 7. Tool Node
# ==========================


tool_node = ToolNode(
    tools
)



# ==========================
# 8. 创建Graph
# ==========================


builder = StateGraph(
    AgentState
)

# 添加节点
builder.add_node(
    "agent",
    agent_node
)

builder.add_node(
    "tool",
    tool_node
)

# START → Agent
builder.add_edge(
    START,
    "agent"
)

# Agent条件分流
builder.add_conditional_edges(

    "agent",

    should_continue,

    {
        "tool":"tool",
        "end":END
    }

)

# Tool → Agent
builder.add_edge(
    "tool",
    "agent"
)

# 编译
graph = builder.compile()



# ==========================
# 9. 执行
# ==========================


result = graph.invoke(

    {

        "messages":[

            SystemMessage(
                content="""
你是一名电商数据分析专家。

需要真实数据时调用工具。
禁止编造数据。
"""
            ),

            HumanMessage(
                content=
                "分析 Dresses 当前销售表现"
            )

        ]

    }

)



# ==========================
# 10. 查看执行结果
# ==========================


print(
    "\n========== Messages =========="
)

for msg in result["messages"]:

    print("\n------")

    print(
        type(msg).__name__
    )

    print(
        msg.content
    )

    if hasattr(
        msg,
        "tool_calls"
    ):
        print("Tool Calls:")
        print(msg.tool_calls)


'''
消息完整链路
`SystemMessage → HumanMessage → AIMessage(带tool_calls) → ToolMessage → AIMessage(最终分析，tool_calls为空)`

AIMessage（发起工具调用）
↓
ToolMessage（工具返回Dresses真实csv数据）
↓
AIMessage（拿到工具返回，输出完整markdown业务分析，tool_calls:[]，代表不再调用工具，流程结束）
'''


"output"
'''

========== Messages ==========

------
SystemMessage

你是一名电商数据分析专家。

需要真实数据时调用工具。
禁止编造数据。


------
HumanMessage
分析 Dresses 当前销售表现

------
AIMessage
I'll analyze the current sales performance of Dresses. Let me query the sales data for this category.
Tool Calls:
[{'name': 'query_sales_data', 'args': {'category': 'Dresses'}, 'id': 'call_00_eHMLd4Kk93EUlfoj2tzC1501', 'type': 'tool_call'}]

------
ToolMessage
{"category": "Dresses", "sales": 465606.87, "items": 5591}

------
AIMessage
## Dresses 销售表现分析

以下是根据查询到的数据对 **Dresses（连衣裙）** 品类的当前销售表现分析：

### 📊 关键数据指标

| 指标 | 数值 |
|------|------|
| **销售额（Sales）** | $465,606.87 |
| **销售件数（Items）** | 5,591 件 |

### 📈 核心指标计算

- **平均客单价**：$465,606.87 ÷ 5,591 ≈ **$83.28/件**

### 🔍 销售表现解读

1. **销售规模**：Dresses 品类当前实现了约 **46.6万美元** 的销售额，售出超过 **5,500件** 商品，整体销售体量较为可观。

2. **客单价水平**：每件连衣裙的平均售价约为 **$83**，属于中端价位区间。这说明该品类在定价上既有合理的利润空间，同时也具备较强的市场渗透力。

3. **品类健康度**：从销售额与销量配比来看，该品类表现稳定，没有出现"高销量低客单"或"高客单低销量"的失衡情况。

### 💡 建议关注方向

- **SKU 动销分析**：可进一步分析这 5,591 件销量在不同款式、颜色、尺码间的分布，识别畅销款与滞销款。
- **价格带优化**：当前约 $83 的客单价表现不错，可评估是否通过组合销售（如搭配配饰）或会员策略进一步提升客单价。
- **库存与补货**：根据销售节奏评估库存是否充足，避免爆款断货。

---

如需针对该品类进行**更深入的分析**（如分款式、分价格带、分时段趋势等），请告诉我具体方向，我可以进一步为您拆解。
Tool Calls:
[]
'''
