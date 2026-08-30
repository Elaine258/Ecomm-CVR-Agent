import os

import pandas as pd

from dotenv import load_dotenv

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent


load_dotenv()


DATA_DIR = r"E:\agent\data"


# =========================
# 加载数据
# =========================

order_items = pd.read_csv(
    os.path.join(DATA_DIR, "order_items.csv")
)

products = pd.read_csv(
    os.path.join(DATA_DIR, "products_old.csv")
)


# =========================
# 定义真实数据 Tool
# =========================

@tool
def query_sales_data(category: str) -> dict:
    """
    查询指定商品类别的销售数据。

    category:
    商品类别，例如 Dresses、Jeans。
    """

    category_products = products[
        products["category"].str.lower()
        ==
        category.lower()
    ]


    if category_products.empty:
        return {
            "error": "没有找到该商品类别"
        }


    product_ids = category_products["id"]


    category_items = order_items[
        order_items["product_id"]
        .isin(product_ids)
    ]


    if category_items.empty:
        return {
            "error": "没有销售数据"
        }


    return {
        "category": category,
        "sales": round(
            float(category_items["sale_price"].sum()),
            2
        ),
        "orders": len(category_items),
        "average_price": round(
            float(category_items["sale_price"].mean()),
            2
        )
    }



# =========================
# 初始化模型
# =========================

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



# =========================
# 创建 Agent
# =========================

agent = create_agent(
    model=llm,
    tools=[
        query_sales_data
    ],
    system_prompt="""
你是一名电商数据分析助手。

你的任务：
1. 用户询问销售数据时，必须先调用数据查询工具。
2. 不允许凭空编造数据。
3. 根据工具返回结果进行业务分析。
"""
)



# =========================
# 调用 Agent
# =========================

result = agent.invoke(
    {
        "messages":[
            {
                "role":"user",
                "content":
                "帮我分析一下 Dresses 的销售情况"
            }
        ]
    }
)
for msg in result["messages"]:
    print("\n---")
    print(type(msg).__name__)
    print(msg.content)

print(
    result["messages"][-1].content
)



"output"
'''
---
HumanMessage
帮我分析一下 Dresses 的销售情况

---
AIMessage
我来帮您查询 Dresses（连衣裙）的销售数据，请稍等。

---
ToolMessage
{"category": "Dresses", "sales": 465606.87, "orders": 5591, "average_price": 83.28}

---
AIMessage
根据查询到的 Dresses（连衣裙）销售数据，我为您进行以下业务分析：

## 📊 Dresses 销售数据分析

### 核心销售指标
| 指标 | 数值 |
|------|------|
| 💰 总销售额 | **$465,606.87** |
| 🛒 订单数量 | **5,591 单** |
| 💵 平均单价 | **$83.28** |

### 业务洞察

**1. 销售额表现**
- Dresses 总销售额达到 **46.5 万美元**，属于较为可观的销售规模。

**2. 客单价分析**
- 平均单价为 **$83.28**，处于中等价位区间。这个价位对于连衣裙来说相对合理。

**3. 订单转化**
- 共产生 **5,591 个订单**，销售订单量较大，说明该品类有较好的市场接受度。

### 💡 建议方向
1. **提升客单价**：可考虑通过搭配销售（如配饰、鞋子）或推出中高端系列来拉高平均订单金额。
2. **扩大销量**：结合平均价格，若推出促销或组合优惠，可能进一步刺激订单量增长。

---

请问您是否需要进一步分析其他品类，或者对某个具体维度（如价格区间、时间趋势等）做深入分析？
根据查询到的 Dresses（连衣裙）销售数据，我为您进行以下业务分析：

## 📊 Dresses 销售数据分析

### 核心销售指标
| 指标 | 数值 |
|------|------|
| 💰 总销售额 | **$465,606.87** |
| 🛒 订单数量 | **5,591 单** |
| 💵 平均单价 | **$83.28** |

### 业务洞察

**1. 销售额表现**
- Dresses 总销售额达到 **46.5 万美元**，属于较为可观的销售规模。

**2. 客单价分析**
- 平均单价为 **$83.28**，处于中等价位区间。这个价位对于连衣裙来说相对合理。

**3. 订单转化**
- 共产生 **5,591 个订单**，销售订单量较大，说明该品类有较好的市场接受度。

### 💡 建议方向
1. **提升客单价**：可考虑通过搭配销售（如配饰、鞋子）或推出中高端系列来拉高平均订单金额。
2. **扩大销量**：结合平均价格，若推出促销或组合优惠，可能进一步刺激订单量增长。

---

请问您是否需要进一步分析其他品类，或者对某个具体维度（如价格区间、时间趋势等）做深入分析？
'''
