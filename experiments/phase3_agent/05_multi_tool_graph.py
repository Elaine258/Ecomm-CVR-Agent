import os
import pandas as pd

from dotenv import load_dotenv

from langchain_openai import ChatOpenAI

from langchain_core.tools import tool

from langchain_core.messages import (
    HumanMessage,
    SystemMessage
)
# 导入 MessagesState
from langgraph.graph import (
    StateGraph,
    START,
    END,
    MessagesState
)

from langgraph.prebuilt import ToolNode


load_dotenv()


# ==========================
# 1. 数据
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
# 2. Tools
# ==========================


@tool
def query_sales_data(category:str):
    """
    查询销售数据
    """

    ids = products[
        products["category"].str.lower()
        ==
        category.lower()
    ]["id"]


    items = order_items[
        order_items["product_id"]
        .isin(ids)
    ]


    return {

        "sales":
            round(
                items["sale_price"]
                .sum(),
                2
            ),

        "items":
            len(items)

    }




@tool
def query_product_info(category:str):
    """
    查询商品结构
    """


    data = products[
        products["category"].str.lower()
        ==
        category.lower()
    ]


    return {

        "products":
            len(data),

        "brands":
            data["brand"]
            .nunique(),

        "avg_price":
            round(
                data["retail_price"]
                .mean(),
                2
            )
    }




@tool
def query_user_behavior(category:str):
    """
    查询用户行为
    """


    ids = products[
        products["category"].str.lower()
        ==
        category.lower()
    ]["id"]


    items = order_items[
        order_items["product_id"]
        .isin(ids)
    ]


    return {

        "users":
            items["user_id"]
            .nunique()
    }



tools = [

    query_sales_data,

    query_product_info,

    query_user_behavior

]



# ==========================
# 3. LLM
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
# 4. State【修复点：使用MessagesState自带add_messages归约器】
# ==========================
class State(MessagesState):
    pass


# ==========================
# 5. Agent Node
# ==========================


def agent_node(state):
    response = llm_with_tools.invoke(
        state["messages"]
    )
    return {
        "messages":[response]
    }



# ==========================
# 6. Conditional Edge
# ==========================


def router(state):
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
# 8. Graph
# ==========================


builder = StateGraph(
    State
)


builder.add_node(
    "agent",
    agent_node
)


builder.add_node(
    "tool",
    tool_node
)



builder.add_edge(
    START,
    "agent"
)



builder.add_conditional_edges(

    "agent",

    router,

    {

        "tool":
        "tool",

        "end":
        END

    }

)



builder.add_edge(
    "tool",
    "agent"
)



graph = builder.compile()



# ==========================
# 9. 测试
# ==========================


result = graph.invoke(

{

"messages":[

SystemMessage(
content="""
你是电商分析专家。

根据问题选择需要的工具。
不要编造数据。
"""
),


HumanMessage(
content=
"""
分析 Dresses 当前销售表现，
从销售、商品、用户三个角度分析
"""
)

]

}

)



# ==========================
# 10. 输出
# ==========================


for msg in result["messages"]:

    print("\n============")

    print(
        type(msg).__name__
    )

    print(
        msg.content
    )


    if hasattr(
        msg,
        "tool_calls"
    ) and msg.tool_calls:
        print(
            msg.tool_calls
        )




'''
完整流转过程:
1. SystemMessage + HumanMessage：系统提示 + 用户提问「从销售、商品、用户三个角度分析 Dresses」
2. AIMessage 一次性输出 3 个 tool_call：同时调用 query_sales_data、query_product_info、query_user_behavior
   LangGraph 的ToolNode原生支持并行多工具调用，一次收到多个 tool_calls，并行执行全部 tool，依次返回多条ToolMessage。
3. 3 条 ToolMessage 分别返回三份 csv 真实业务数据：
销售数据：{"sales": 465606.87, "items": 5591}
商品结构：{"products": 955, "brands": 180, "avg_price": 84.2}
用户行为：{"users": 5185}
4. LLM 拿到全部三份工具返回结果，输出最终 markdown 综合业务分析，tool_calls=[]（不再调用工具）
5. router检测无 tool_calls，返回end，图走到END结束。
'''

"output"
'''

============
SystemMessage

你是电商分析专家。

根据问题选择需要的工具。
不要编造数据。


============
HumanMessage

分析 Dresses 当前销售表现，
从销售、商品、用户三个角度分析


============
AIMessage
我来分析 Dresses 品类的销售表现，需要从销售数据、商品结构和用户行为三个角度进行。让我先获取相关数据。
[{'name': 'query_sales_data', 'args': {'category': 'Dresses'}, 'id': 'call_00_PFHHcGA93vngXTraKCDY1085', 'type': 'tool_call'}, {'name': 'query_product_info', 'args': {'category': 'Dresses'}, 'id': 'call_01_gVjbnRMmVRYeHG0wnk8i8605', 'type': 'tool_call'}, {'name': 'query_user_behavior', 'args': {'category': 'Dresses'}, 'id': 'call_02_K3IRLsdA8zMCxfELs8bO1611', 'type': 'tool_call'}]

============
ToolMessage
{"sales": 465606.87, "items": 5591}

============
ToolMessage
{"products": 955, "brands": 180, "avg_price": 84.2}

============
ToolMessage
{"users": 5185}

============
AIMessage
根据获取到的数据，我对 Dresses 品类的当前销售表现从三个角度进行分析：

## 📊 Dresses 销售表现分析

### 一、销售角度

| 指标 | 数值 |
|------|------|
| **总销售额** | ¥465,606.87 |
| **销售件数** | 5,591 件 |

**分析：**
- 整体销售额约 **46.6万元**，件数超 **5,500件**。
- 平均客单价约：¥465,606.87 ÷ 5,591 ≈ **¥83.3/件**，属于中低价位带，具备一定走量基础。

---

### 二、商品角度

| 指标 | 数值 |
|------|------|
| **在售商品数** | 955 款 |
| **品牌数** | 180 个 |
| **平均售价** | ¥84.2 |

**分析：**
- **动销率**：5,591件 ÷ 955款 ≈ **每款约5.9件销量**，SKU 较多但单品销量较为分散，说明商品丰富但缺乏爆款集中度。
- **品牌布局**：180个品牌，平均每品牌约5.3款产品，品牌和款式都较分散。
- **价格带**：平均售价 ¥84.2，与销售客单价基本一致，定价较为统一，说明品类定位集中在中端偏亲民价位。

---

### 三、用户角度

| 指标 | 数值 |
|------|------|
| **活跃用户数** | 5,185 人 |

**分析：**
- **人均购买件数**：5,591 ÷ 5,185 ≈ **1.08件/人**，说明大多数用户仅购买1件，复购率相对偏低。
- **人均贡献销售额**：¥465,606.87 ÷ 5,185 ≈ **¥89.8/人**。

---

## 🎯 综合结论与建议

**总体表现：** Dresses 品类处于**稳步运营**状态，销售额约46.6万元，商品供给充足（955款/180品牌），用户基础约5千余人。

**主要问题：**
1. **爆款缺失**：商品分散，单品销量偏低，缺少头部爆款拉动整体。
2. **复购偏低**：人均仅约1.08件，用户忠诚度有待提升。
3. **转化集中度低**：品牌和SKU数量多，需要聚焦核心款式。

**优化建议：**
- 🔹 **打造爆款**：聚焦表现较好的款式，强化资源倾斜，提升单品集中度。
- 🔹 **提升复购**：通过会员/搭配推荐/新品推荐等策略促进二次购买。
- 🔹 **优化SKU结构**：清理低效SKU，集中价格带（80-90元附近）优势。

如需进一步深入某个维度（如具体价格带分布、品牌排名等），可以继续分析。
'''
