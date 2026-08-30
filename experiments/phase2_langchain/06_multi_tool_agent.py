import os
import pandas as pd

from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent


load_dotenv()


DATA_DIR = r"E:\agent\data"


# ============ 加载数据 ============

order_items = pd.read_csv(
    os.path.join(DATA_DIR, "order_items.csv")
)

products = pd.read_csv(
    os.path.join(DATA_DIR, "products_old.csv")
)


# ============ Tool 1 销售数据 ============

@tool
def query_sales_data(category: str) -> dict:
    """
    查询商品类别销售数据。
    输入商品类别，例如 Dresses、Jeans。
    """

    category_products = products[
        products["category"].str.lower()
        ==
        category.lower()
    ]


    if category_products.empty:
        return {
            "error": f"没有找到商品类别: {category}"
        }


    product_ids = category_products["id"]


    items = order_items[
        order_items["product_id"]
        .isin(product_ids)
    ]


    if items.empty:
        return {
            "error": f"{category} 没有销售数据"
        }


    return {
        "category": category,
        "sales": round(
            float(items["sale_price"].sum()),
            2
        ),
        "items": len(items)
    }



# ============ Tool 2 商品结构 ============

@tool
def query_product_info(category: str) -> dict:
    """
    查询商品类别结构信息。
    包括商品数量、品牌数量、平均售价。
    """


    category_products = products[
        products["category"].str.lower()
        ==
        category.lower()
    ]


    if category_products.empty:
        return {
            "error": f"没有找到商品类别: {category}"
        }


    return {

        "product_count":
            len(category_products),

        "brand_count":
            int(
                category_products["brand"]
                .nunique()
            ),

        "avg_retail_price":
            round(
                float(
                    category_products[
                        "retail_price"
                    ].mean()
                ),
                2
            )
    }



# ============ Tool 3 用户行为 ============

@tool
def query_user_behavior(category: str) -> dict:
    """
    查询购买该商品类别的用户情况。
    """


    category_products = products[
        products["category"].str.lower()
        ==
        category.lower()
    ]


    if category_products.empty:
        return {
            "error": f"没有找到商品类别: {category}"
        }


    product_ids = category_products["id"]


    items = order_items[
        order_items["product_id"]
        .isin(product_ids)
    ]


    if items.empty:
        return {
            "error": f"{category} 没有购买记录"
        }


    users = items["user_id"].nunique()


    return {

        "unique_users":
            int(users),

        "avg_items_per_user":
            round(
                len(items) / users,
                2
            )
    }



# ============ Tool集合 ============

tools = [
    query_sales_data,
    query_product_info,
    query_user_behavior
]



# ============ 初始化模型 ============

llm = ChatOpenAI(
    model="deepseek-v4-flash",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",

    # DeepSeek Tool Calling需要关闭thinking
    extra_body={
        "thinking": {
            "type": "disabled"
        }
    }
)



# ============ 创建Agent ============

agent = create_agent(
    model=llm,

    tools=tools,

    system_prompt="""

你是一名电商数据分析专家。

工作流程：

1. 用户提出分析需求时，
优先调用工具获取真实数据。

2. 根据问题选择一个或多个工具。

3. 工具返回数据后，
再进行业务分析。

4. 禁止凭空编造数据。

"""
)



# ============ 调用Agent ============


question = """
分析 Dresses 当前销售表现
"""


result = agent.invoke(
    {
        "messages": [
            {
                "role": "user",
                "content": question
            }
        ]
    }
)



# ============ 调试完整Agent链路 ============

print("\n\n========== Agent执行链路 ==========")


for i, msg in enumerate(result["messages"]):

    print("\n==============================")
    print(f"消息 {i+1}")
    print("==============================")

    print("类型:")
    print(type(msg).__name__)


    print("\n内容:")
    print(msg.content)


    # 查看Tool调用
    if hasattr(msg, "tool_calls"):

        print("\nTool Calls:")

        print(
            msg.tool_calls
        )


    # 查看Tool返回
    if hasattr(msg, "name"):

        print("\nTool Name:")
        print(msg.name)



# ============ 最终回答 ============

print("\n\n========== 最终业务分析结果 ==========")

print(
    result["messages"][-1].content
)



"output"
'''
========== Agent执行链路 ==========

==============================
消息 1
==============================
类型:
HumanMessage

内容:

分析 Dresses 当前销售表现


Tool Name:
None

==============================
消息 2
==============================
类型:
AIMessage

内容:
我来分析 Dresses 当前的销售表现。首先需要获取相关的数据，包括销售数据、商品结构信息和用户行为数据。

让我同时查询这些数据：

Tool Calls:
[{'name': 'query_sales_data', 'args': {'category': 'Dresses'}, 'id': 'call_00_03SGQVIfRjLIOu2yFPGE3839',
'type': 'tool_call'}, {'name': 'query_product_info', 'args': {'category': 'Dresses'},
'id': 'call_01_886up8YIMNVPl27nJ8bC1995', 'type': 'tool_call'},
{'name': 'query_user_behavior', 'args': {'category': 'Dresses'},
'id': 'call_02_VOwNvjH156CnppeLBQfF0374', 'type': 'tool_call'}]

Tool Name:
None

==============================
消息 3
==============================
类型:
ToolMessage

内容:
{"category": "Dresses", "sales": 465606.87, "items": 5591}

Tool Name:
query_sales_data

==============================
消息 4
==============================
类型:
ToolMessage

内容:
{"product_count": 955, "brand_count": 180, "avg_retail_price": 84.2}

Tool Name:
query_product_info

==============================
消息 5
==============================
类型:
ToolMessage

内容:
{"unique_users": 5185, "avg_items_per_user": 1.08}

Tool Name:
query_user_behavior

==============================
消息 6
==============================
类型:
AIMessage

内容:
基于获取到的真实数据，我来对 Dresses 的当前销售表现进行全面的业务分析。

---

## Dresses 销售表现分析

### 一、整体销售概况

| 指标 | 数值 |
|------|------|
| 总销售额 | **¥465,606.87** |
| 销售件数 | **5,591 件** |
| 在售商品数 | 955 款 |
| 品牌数 | 180 个 |
| 平均零售价 | ¥84.2 |

### 二、核心表现解读

#### 1. 销售效率
- **平均单件售价** ≈ ¥465,606.87 ÷ 5,591 = **¥83.28**
- 这与商品平均零售价 **¥84.2** 基本吻合，说明**成交价格与标价接近**，商品定价合理，折扣力度不大，利润率保持较好。

#### 2. 商品结构表现
- 在售 **955 款**商品支撑 **5,591 件**销量，意味着 **平均每款商品售出约 5.85 件**。这属于相对集中的销售模式，说明存在**爆款商品驱动**的局面。
- **180 个品牌**参与竞争，市场供给较为丰富，竞争环境相对充分。

#### 3. 用户行为分析
- **5,185 位独立用户**完成了购买，人均购买量仅 **1.08 件**。
- 这说明：
  - 用户**单次购买基本只买一件**，交叉购买和捆绑销售潜力未被充分挖掘；
  - 客户**粘性有待提升**，缺少带动复购的机制。

### 三、关键洞察与建议

#### ✅ 优势
- 价格体系稳定，成交价贴近标价，毛利健康；
- 商品端供给充足，品牌多样，用户可选择余地大。

#### ⚠️ 改进方向
1. **提升客单价与连带率**：人均仅买 1.08 件，可设计**搭配/套装促销**（如连衣裙+配饰、上下装搭配），引导用户连带购买，提升件单价。

2. **打造更多爆款**：平均每款只卖约 5.85 件，可加强**爆款培育**，通过流量倾斜、促销资源集中到高潜力款式。

3. **增加复购**：可将购买用户进行分层运营，通过会员体系、新品推送、换季活动，提升老客二次回购。

---

**总结**：Dresses 整体销售规模可观，价格体系健康，但当前属于**多SKU、低连带、低复购**的销售格局，核心增长空间在于**提升客单件数**和**用户复购率**。

Tool Calls:
[]

Tool Name:
None


========== 最终业务分析结果 ==========
基于获取到的真实数据，我来对 Dresses 的当前销售表现进行全面的业务分析。

---

## Dresses 销售表现分析

### 一、整体销售概况

| 指标 | 数值 |
|------|------|
| 总销售额 | **¥465,606.87** |
| 销售件数 | **5,591 件** |
| 在售商品数 | 955 款 |
| 品牌数 | 180 个 |
| 平均零售价 | ¥84.2 |

### 二、核心表现解读

#### 1. 销售效率
- **平均单件售价** ≈ ¥465,606.87 ÷ 5,591 = **¥83.28**
- 这与商品平均零售价 **¥84.2** 基本吻合，说明**成交价格与标价接近**，商品定价合理，折扣力度不大，利润率保持较好。

#### 2. 商品结构表现
- 在售 **955 款**商品支撑 **5,591 件**销量，意味着 **平均每款商品售出约 5.85 件**。这属于相对集中的销售模式，说明存在**爆款商品驱动**的局面。
- **180 个品牌**参与竞争，市场供给较为丰富，竞争环境相对充分。

#### 3. 用户行为分析
- **5,185 位独立用户**完成了购买，人均购买量仅 **1.08 件**。
- 这说明：
  - 用户**单次购买基本只买一件**，交叉购买和捆绑销售潜力未被充分挖掘；
  - 客户**粘性有待提升**，缺少带动复购的机制。

### 三、关键洞察与建议

#### ✅ 优势
- 价格体系稳定，成交价贴近标价，毛利健康；
- 商品端供给充足，品牌多样，用户可选择余地大。

#### ⚠️ 改进方向
1. **提升客单价与连带率**：人均仅买 1.08 件，可设计**搭配/套装促销**（如连衣裙+配饰、上下装搭配），引导用户连带购买，提升件单价。

2. **打造更多爆款**：平均每款只卖约 5.85 件，可加强**爆款培育**，通过流量倾斜、促销资源集中到高潜力款式。

3. **增加复购**：可将购买用户进行分层运营，通过会员体系、新品推送、换季活动，提升老客二次回购。

---

**总结**：Dresses 整体销售规模可观，价格体系健康，但当前属于**多SKU、低连带、低复购**的销售格局，核心增长空间在于**提升客单件数**和**用户复购率**。
'''
