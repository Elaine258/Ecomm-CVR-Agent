import os

import pandas as pd

from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI


load_dotenv()


# =========================
# 数据路径
# =========================

DATA_DIR = r"E:\agent\data"


# =========================
# 加载数据
# =========================

orders = pd.read_csv(
    os.path.join(DATA_DIR, "orders.csv")
)

order_items = pd.read_csv(
    os.path.join(DATA_DIR, "order_items.csv")
)

products = pd.read_csv(
    os.path.join(DATA_DIR, "products_old.csv")
)


# =========================
# LangChain Tool
# =========================

@tool
def query_sales_data(category: str) -> dict:
    """
    查询指定商品类别的销售数据。

    参数：
    category: 商品类别，例如 Dresses、Jeans、Swim 等。

    返回：
    商品类别、销售额、订单商品数量、平均销售价格。
    """

    # 1. 找到指定类别的商品
    category_products = products[
        products["category"].str.lower() == category.lower()
    ]

    if category_products.empty:
        return {
            "error": f"没有找到商品类别：{category}"
        }

    # 2. 获取这些商品的 product_id
    product_ids = category_products["id"]

    # 3. 筛选订单商品
    category_items = order_items[
        order_items["product_id"].isin(product_ids)
    ]

    if category_items.empty:
        return {
            "error": f"商品类别 {category} 没有销售数据"
        }

    # 4. 计算销售指标
    sales = category_items["sale_price"].sum()

    item_count = len(category_items)

    average_price = category_items["sale_price"].mean()

    return {
        "category": category,
        "sales": round(float(sales), 2),
        "item_count": item_count,
        "average_sale_price": round(float(average_price), 2)
    }


# =========================
# 测试 Tool
# =========================

result = query_sales_data.invoke(
    {
        "category": "Dresses"
    }
)

print(result)


"output"
'''
{'category': 'Dresses', 'sales': 465606.87, 'item_count': 5591, 'average_sale_price': 83.28}
'''
