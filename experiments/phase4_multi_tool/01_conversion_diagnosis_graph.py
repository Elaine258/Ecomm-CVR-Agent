import sys
import os
import pandas as pd

from typing import TypedDict
from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(ROOT)
from src.rules.conversion_anomaly import (
    detect_conversion_anomaly
)

load_dotenv()

DATA_DIR = r"E:\agent\data"
EVENTS_PATH = os.path.join(DATA_DIR, "events_old.csv")
PRODUCTS_PATH = os.path.join(DATA_DIR, "products_old.csv")
BENCHMARK_PATH = os.path.join(
    DATA_DIR,
    "industry_benchmark_comparison.xlsx"
)

FUNNEL_LOW_THRESHOLD = -0.30


# ==================================================
# 1. 加载数据
# ==================================================

events = pd.read_csv(
    EVENTS_PATH,
    usecols=[
        "session_id",
        "event_type",
        "uri"
    ]
)

products = pd.read_csv(
    PRODUCTS_PATH,
    usecols=[
        "id",
        "name",
        "category",
        "brand",
        "retail_price"
    ]
)

products = products.rename(
    columns={"id": "product_id"}
)


# ==================================================
# 2. 预处理Session → Product
# ==================================================

product_events = events[
    events["event_type"] == "product"
].copy()

product_events["product_id"] = (
    product_events["uri"]
    .str.extract(r"/product/(\d+)")[0]
)

product_events["product_id"] = pd.to_numeric(
    product_events["product_id"],
    errors="coerce"
)

product_events = product_events.dropna(
    subset=["product_id"]
)

product_events["product_id"] = (
    product_events["product_id"]
    .astype(int)
)

session_products = (
    product_events[
        ["session_id", "product_id"]
    ]
    .drop_duplicates()
)

session_products = session_products.merge(
    products,
    on="product_id",
    how="left"
)

cart_sessions = set(
    events.loc[
        events["event_type"] == "cart",
        "session_id"
    ]
    .dropna()
    .unique()
)

purchase_sessions = set(
    events.loc[
        events["event_type"] == "purchase",
        "session_id"
    ]
    .dropna()
    .unique()
)

session_products["has_cart"] = (
    session_products["session_id"]
    .isin(cart_sessions)
)

session_products["has_purchase"] = (
    session_products["session_id"]
    .isin(purchase_sessions)
)


# ==================================================
# 3. State
# ==================================================

class DiagnosisState(TypedDict, total=False):

    user_question: str
    product_id: int

    product_name: str
    category: str

    product_sessions: int
    cart_sessions: int
    purchase_sessions: int

    cart_rate: float
    purchase_cvr: float
    cart_to_purchase_rate: float

    category_cart_rate: float
    category_cvr: float
    category_cart_to_purchase_rate: float

    anomaly_status: str
    severity: str | None
    cvr_deviation: float | None

    product_to_cart_deviation: float
    cart_to_purchase_deviation: float
    weak_stage: str

    sku_price: float
    category_avg_price: float
    category_median_price: float
    price_deviation: float
    price_percentile: float
    price_status: str

    industry_reference: str

    final_report: str


# ==================================================
# 4. Tool Node 1
# 获取SKU转化指标
# ==================================================

def conversion_metrics_node(
    state: DiagnosisState
):

    print("\n========== Conversion Metrics ==========")

    product_id = state["product_id"]

    sku_data = session_products[
        session_products["product_id"]
        == product_id
    ]

    if sku_data.empty:
        raise ValueError(
            f"找不到 product_id={product_id}"
        )

    category = sku_data["category"].iloc[0]
    product_name = sku_data["name"].iloc[0]

    product_sessions_count = (
        sku_data["session_id"].nunique()
    )

    cart_count = int(
        sku_data["has_cart"].sum()
    )

    purchase_count = int(
        sku_data["has_purchase"].sum()
    )

    cart_rate = (
        cart_count
        / product_sessions_count
    )

    purchase_cvr = (
        purchase_count
        / product_sessions_count
    )

    cart_to_purchase_rate = (
        purchase_count / cart_count
        if cart_count > 0
        else 0.0
    )


    # Category Benchmark

    category_data = session_products[
        session_products["category"]
        == category
    ]

    category_product_sessions = (
        category_data["session_id"]
        .nunique()
    )

    category_cart_sessions = int(
        category_data["has_cart"].sum()
    )

    category_purchase_sessions = int(
        category_data["has_purchase"].sum()
    )

    category_cart_rate = (
        category_cart_sessions
        / category_product_sessions
    )

    category_cvr = (
        category_purchase_sessions
        / category_product_sessions
    )

    category_cart_to_purchase_rate = (
        category_purchase_sessions
        / category_cart_sessions
    )


    print("product_id:", product_id)
    print("category:", category)
    print("product_sessions:", product_sessions_count)
    print("purchase_cvr:", f"{purchase_cvr:.2%}")
    print("category_cvr:", f"{category_cvr:.2%}")


    return {
        "product_name": product_name,
        "category": category,

        "product_sessions":
            product_sessions_count,

        "cart_sessions":
            cart_count,

        "purchase_sessions":
            purchase_count,

        "cart_rate":
            cart_rate,

        "purchase_cvr":
            purchase_cvr,

        "cart_to_purchase_rate":
            cart_to_purchase_rate,

        "category_cart_rate":
            category_cart_rate,

        "category_cvr":
            category_cvr,

        "category_cart_to_purchase_rate":
            category_cart_to_purchase_rate
    }


# ==================================================
# 5. Tool Node 2
# 异常检测
# ==================================================

def anomaly_node(
    state: DiagnosisState
):

    print("\n========== Anomaly Detection ==========")

    result = detect_conversion_anomaly(
        product_sessions=
            state["product_sessions"],

        purchase_cvr=
            state["purchase_cvr"],

        category_cvr=
            state["category_cvr"]
    )


    print("status:", result["status"])
    print(
        "deviation:",
        result["cvr_deviation"]
    )


    return {
        "anomaly_status":
            result["status"],

        "severity":
            result["severity"],

        "cvr_deviation":
            result["cvr_deviation"]
    }


# ==================================================
# 6. Router 1
# 是否需要深度诊断
# ==================================================

def anomaly_router(
    state: DiagnosisState
):

    status = state["anomaly_status"]

    print(
        "\nAnomaly Router:",
        status
    )

    if status in [
        "low",
        "severe"
    ]:
        return "funnel_analysis"

    return "report"


# ==================================================
# 7. Tool Node 3
# 漏斗阶段分析
# ==================================================

def funnel_analysis_node(
    state: DiagnosisState
):

    print("\n========== Funnel Analysis ==========")

    product_to_cart_deviation = (
        state["cart_rate"]
        - state["category_cart_rate"]
    ) / state["category_cart_rate"]

    cart_to_purchase_deviation = (
        state["cart_to_purchase_rate"]
        - state["category_cart_to_purchase_rate"]
    ) / state[
        "category_cart_to_purchase_rate"
    ]


    product_weak = (
        product_to_cart_deviation
        <= FUNNEL_LOW_THRESHOLD
    )

    purchase_weak = (
        cart_to_purchase_deviation
        <= FUNNEL_LOW_THRESHOLD
    )


    if product_weak and purchase_weak:
        weak_stage = "both"

    elif product_weak:
        weak_stage = "product_to_cart"

    elif purchase_weak:
        weak_stage = "cart_to_purchase"

    else:
        weak_stage = "none"


    print(
        "Product→Cart deviation:",
        f"{product_to_cart_deviation:.2%}"
    )

    print(
        "Cart→Purchase deviation:",
        f"{cart_to_purchase_deviation:.2%}"
    )

    print(
        "weak_stage:",
        weak_stage
    )


    return {
        "product_to_cart_deviation":
            product_to_cart_deviation,

        "cart_to_purchase_deviation":
            cart_to_purchase_deviation,

        "weak_stage":
            weak_stage
    }


# ==================================================
# 8. Tool Node 4
# 价格位置分析
# ==================================================

def price_analysis_node(
    state: DiagnosisState
):

    print("\n========== Price Analysis ==========")

    product_id = state["product_id"]
    category = state["category"]

    sku = products[
        products["product_id"]
        == product_id
    ].iloc[0]

    category_products = products[
        products["category"]
        == category
    ]

    sku_price = float(
        sku["retail_price"]
    )

    avg_price = float(
        category_products[
            "retail_price"
        ].mean()
    )

    median_price = float(
        category_products[
            "retail_price"
        ].median()
    )

    price_deviation = (
        sku_price - median_price
    ) / median_price

    price_percentile = float(
        (
            category_products[
                "retail_price"
            ]
            <= sku_price
        ).mean()
    )


    if price_percentile >= 0.80:
        price_status = "high"

    elif price_percentile <= 0.20:
        price_status = "low"

    else:
        price_status = "normal"


    print(
        "sku_price:",
        sku_price
    )

    print(
        "category_median:",
        median_price
    )

    print(
        "percentile:",
        f"{price_percentile:.2%}"
    )

    print(
        "price_status:",
        price_status
    )


    return {
        "sku_price":
            sku_price,

        "category_avg_price":
            avg_price,

        "category_median_price":
            median_price,

        "price_deviation":
            price_deviation,

        "price_percentile":
            price_percentile,

        "price_status":
            price_status
    }


# ==================================================
# 9. Tool Node 5
# 外部行业Benchmark
# ==================================================

def industry_benchmark_node(
    state: DiagnosisState
):

    print(
        "\n========== Industry Benchmark =========="
    )

    if not os.path.exists(
        BENCHMARK_PATH
    ):
        return {
            "industry_reference":
                "未找到外部行业Benchmark文件。"
        }


    benchmark = pd.read_excel(
        BENCHMARK_PATH,
        sheet_name="行业基准对比表"
    )


    fashion = benchmark[
        benchmark["行业范围"]
        .astype(str)
        .str.contains(
            "Fashion",
            case=False,
            na=False
        )
    ]


    if fashion.empty:
        reference = (
            "未找到Fashion/Apparel行业参考。"
        )

    else:

        records = []

        for _, row in fashion.iterrows():

            records.append(
                f'{row["指标"]}: '
                f'{row["Benchmark"]}'
            )

        reference = (
            "Dynamic Yield Fashion/Apparel "
            "2025外部行业参考："
            + "；".join(records)
            + "。注意：与TheLook统计口径不同，"
            "不可直接用于异常阈值判断。"
        )


    print(reference)


    return {
        "industry_reference":
            reference
    }


# ==================================================
# 10. LLM
# ==================================================

llm = ChatOpenAI(
    model="deepseek-v4-flash",
    api_key=os.getenv(
        "DEEPSEEK_API_KEY"
    ),
    base_url="https://api.deepseek.com",
    extra_body={
        "thinking": {
            "type": "disabled"
        }
    }
)


# ==================================================
# 11. Report Node
# ==================================================

def report_node(
    state: DiagnosisState
):

    print("\n========== Report ==========")

    prompt = f"""
你是一名电商转化率诊断专家。
请严格根据下面已经计算完成的数据生成诊断报告。

商品：
{state.get("product_name")}

Product ID：
{state["product_id"]}

Category：
{state.get("category")}

Product Sessions：
{state.get("product_sessions")}

SKU Product→Cart Rate：
{state.get("cart_rate", 0):.2%}

Category Product→Cart Rate：
{state.get("category_cart_rate", 0):.2%}

SKU Product→Purchase CVR：
{state.get("purchase_cvr", 0):.2%}

Category CVR：
{state.get("category_cvr", 0):.2%}

SKU Cart→Purchase Rate：
{state.get("cart_to_purchase_rate", 0):.2%}

Category Cart→Purchase Rate：
{state.get("category_cart_to_purchase_rate", 0):.2%}

CVR相对偏离：
{state.get("cvr_deviation")}

异常状态：
{state.get("anomaly_status")}

主要弱环节：
{state.get("weak_stage", "未执行")}

Product→Cart偏离：
{state.get("product_to_cart_deviation")}

Cart→Purchase偏离：
{state.get("cart_to_purchase_deviation")}

价格状态：
{state.get("price_status", "未执行")}

SKU零售价：
{state.get("sku_price")}

Category零售价中位数：
{state.get("category_median_price")}

价格分位：
{state.get("price_percentile")}

外部行业参考：
{state.get("industry_reference", "未调用")}

必须严格遵守以下规则：

1. Product Sessions < 20 时，才能说“样本不足”。
2. Product Sessions >= 20 时，表示已经通过当前项目最低样本量门槛，不得说“样本不足”。
3. 不得自行计算或编造：
   - p值
   - 置信区间
   - 统计显著性
   - 推荐样本量
4. 不得创造输入中不存在的数据。
5. low / severe 时说明主要异常漏斗阶段。
   描述异常程度时必须使用实际Rate和相对Category Benchmark的deviation，
   不得自行转换成用户流失比例。
6. weak_stage 只代表漏斗异常主要集中的位置。
7. 如果 Product→Cart 没有达到异常标准，只能说该阶段暂未发现明显异常；
   不能据此判断图片、标题、商品描述没有问题。
8. price_status=high 时，只能说“价格偏高是可能影响因素之一”，不能说价格导致转化下降。
9. 当前价格为 retail_price，应称为“零售价/标价”，不要称为实际成交价。
10. Dynamic Yield与TheLook口径不同：
    - 只能作为行业背景参考
    - 不得进行直接高低比较
    - 不得通过Dynamic Yield数值推算TheLook指标
11. 建议必须区分：
    - 当前数据直接支持的建议
    - 需要更多数据验证的假设
12. 如果当前数据无法确认具体原因，要明确写“现有证据不足以确定因果原因”。
13. 必须严格区分“转化率”“相对偏离”和“用户流失率”。
14. xxx_deviation 表示“SKU指标相对于Category Benchmark的相对偏离”，
    不代表用户流失比例。
    例如：
    Cart→Purchase deviation = -63.72%
    正确表述：
    “SKU Cart→Purchase转化率较Category Benchmark低63.72%。”
    禁止表述：
    “超过63%的用户在购物车环节流失。”
15. 描述漏斗异常时，优先直接报告原始指标和相对偏离。
    例如：
    “SKU Cart→Purchase Rate为15.38%，Category Benchmark为42.40%，
    相对偏离-63.72%，该阶段表现明显低于品类基准。”
16. 不得将“相对于Benchmark表现较弱”改写成“用户大量流失”
    “超过X%的用户流失”等用户行为结论，
    除非输入数据中明确提供并计算了对应的流失率。

报告结构只需要：
一、诊断结论
二、已知事实
三、漏斗异常定位
四、可能影响因素
五、外部行业参考
六、下一步需要补充的数据
"""

    response = llm.invoke(prompt)

    return {
        "final_report":
            response.content
    }


# ==================================================
# 12. Graph
# ==================================================

builder = StateGraph(
    DiagnosisState
)

builder.add_node(
    "conversion_metrics",
    conversion_metrics_node
)

builder.add_node(
    "anomaly_detection",
    anomaly_node
)

builder.add_node(
    "funnel_analysis",
    funnel_analysis_node
)

builder.add_node(
    "price_analysis",
    price_analysis_node
)

builder.add_node(
    "industry_benchmark",
    industry_benchmark_node
)

builder.add_node(
    "report",
    report_node
)


builder.add_edge(
    START,
    "conversion_metrics"
)

builder.add_edge(
    "conversion_metrics",
    "anomaly_detection"
)

builder.add_conditional_edges(
    "anomaly_detection",
    anomaly_router,
    {
        "funnel_analysis":
            "funnel_analysis",

        "report":
            "report"
    }
)

builder.add_edge(
    "funnel_analysis",
    "price_analysis"
)

builder.add_edge(
    "price_analysis",
    "industry_benchmark"
)

builder.add_edge(
    "industry_benchmark",
    "report"
)

builder.add_edge(
    "report",
    END
)


graph = builder.compile()



# 查找4个测试SKU
def find_test_cases():

    cases = {
        "severe": None,
        "low": None,
        "normal": None,
        "insufficient_data": None
    }

    product_ids = (
        session_products["product_id"]
        .dropna()
        .unique()
    )

    for product_id in product_ids:

        sku_data = session_products[
            session_products["product_id"] == product_id
        ]

        if sku_data.empty:
            continue

        category = sku_data["category"].iloc[0]

        product_sessions = (
            sku_data["session_id"].nunique()
        )

        purchase_sessions = int(
            sku_data["has_purchase"].sum()
        )

        purchase_cvr = (
            purchase_sessions
            / product_sessions
        )

        category_data = session_products[
            session_products["category"] == category
        ]

        category_product_sessions = (
            category_data["session_id"].nunique()
        )

        category_purchase_sessions = int(
            category_data["has_purchase"].sum()
        )

        category_cvr = (
            category_purchase_sessions
            / category_product_sessions
        )

        result = detect_conversion_anomaly(
            product_sessions=product_sessions,
            purchase_cvr=purchase_cvr,
            category_cvr=category_cvr
        )

        status = result["status"]

        if (
            status in cases
            and cases[status] is None
        ):
            cases[status] = int(product_id)

        if all(
            value is not None
            for value in cases.values()
        ):
            break

    return cases

test_cases = find_test_cases()

print("\n========== Test Cases ==========")

for status, product_id in test_cases.items():
    print(
        status,
        "→ product_id:",
        product_id
    )

# ==================================================
# 13. 测试
# ==================================================

result = graph.invoke(
    {
        "user_question":
            "为什么这个SKU转化率低？",

        # 先用真实SKU测试
        "product_id": 6
    }
)


print(
    "\n\n========== Final Report =========="
)

print(
    result["final_report"]
)


"output"
'''
========== Conversion Metrics ==========
product_id: 6
category: Tops & Tees
product_sessions: 23
purchase_cvr: 8.70%
category_cvr: 26.93%

========== Anomaly Detection ==========
status: severe
deviation: -0.6771

Anomaly Router: severe

========== Funnel Analysis ==========
Product→Cart deviation: -10.99%
Cart→Purchase deviation: -63.72%
weak_stage: cart_to_purchase

========== Price Analysis ==========
sku_price: 132.0
category_median: 30.734999656677246
percentile: 97.38%
price_status: high

========== Industry Benchmark ==========
Dynamic Yield Fashion/Apparel 2025外部行业参考：加购率（商品页浏览口径）: 6.58%；购买转化率（访客口径）: 3.03%；购物车完成率代理（派生）: 21.87%；购物车放弃率: 78.13%。注意：与TheLook统计口径不同，不可直接用于异常阈值判断。

========== Report ==========


========== Final Report ==========
一、诊断结论

该商品（Wilt Women's Color Blocked Big Mixed Slant Top）整体转化表现**严重异常**，核心问题集中在**购物车到支付环节**。用户从商品页加入购物车的意愿接近品类正常水平，但**超过六成的用户在购物车环节流失**，导致最终购买转化率远低于品类均值。当前现有证据表明，**购物车环节是转化效率的主要瓶颈**，但仅凭现有数据不足以确定导致用户弃购的具体因果原因。

二、已知事实

- 商品访客数为23，已达到当前项目最低样本量门槛，本报告不进行“样本不足”判定。
- 商品加购率（Product→Cart）为56.52%，品类加购率为63.50%，SKU相对品类偏离为-0.11，该阶段未达到严重异常标准，暂未发现明显异常。
- 商品支付转化率（Product→Purchase）为8.70%，品类支付转化率为26.93%，CVR相对偏离为-0.6771，偏离幅度大，异常状态为“severe”。
- 商品购物车完成率（Cart→Purchase）为15.38%，品类购物车完成率为42.40%，单向偏离达-0.6372，是漏斗中最薄弱的环节。
- 商品零售价/标价为132.0元，品类零售价/标价中位数为30.73元，该商品价格位于品类价格分布的97.4百分位，价格状态判定为“high”。
- 品类购物车完成率（42.40%）显著高于该商品购物车完成率（15.38%），说明其他同品类商品在购物车环节的转化效率普遍更高。

三、漏斗异常定位

- **主要异常阶段**：购物车到支付（cart_to_purchase）。该环节转化率仅为品类均值的约三分之一，流失严重。
- **次要观察**：商品页到加购（product_to_cart）的转化率与品类水平差距较小，暂未发现明显异常；但不能据此判断商品页的图片、标题、商品描述完全不存在优化空间，只是当前数据不支持该环节为主要问题。
- 根据现有数据，该商品的用户流失主要发生在“已加购但未支付”的阶段，而非浏览后不加购的阶段。

四、可能影响因素

- **价格因素**：该商品零售价/标价（132.0元）显著高于品类零售价/标价中位数（30.73元），处于品类价格分布的97.4百分位，属于高价位商品。**价格偏高是可能影响因素之一**，可能直接影响用户在下单前的支付意愿，但现有数据不能证明价格是导致购物车流失的唯一或决定性原因。
- **决策成本**：高价位商品通常伴随更高的购买决策成本，用户在加购后可能仍处于比价或犹豫状态，导致“加购后不支付”的行为模式。此为基于行业经验的推测，需要更多数据验证。
- **其他未验证假设**：支付流程阻力、运费/税费不透明、促销预期等均可能影响购物车完成率，但当前数据无法确认具体原因。**现有证据不足以确定因果原因。**

五、外部行业参考

Dynamic Yield Fashion/Apparel 2025外部行业参考数据显示：加购率（商品页浏览口径）为6.58%，购买转化率（访客口径）为3.03%，购物车完成率（派生代理）为21.87%，购物车放弃率为78.13%。

**注意**：该外部数据与TheLook统计口径不同，不可直接与本报告中的SKU或品类指标进行高低比较，也不可通过Dynamic Yield数值推算TheLook相关指标。此处仅作为行业背景参考，不用于异常阈值判断。

六、下一步需要补充的数据

当前数据只能定位异常集中在购物车环节，无法确认用户弃购的具体原因。建议补充以下数据以进一步验证假设：

1. **购物车弃购原因数据**：如弃购用户调查问卷、退出前弹窗原因采集、客服反馈，用于了解用户是“价格犹豫”“运费/税费顾虑”还是“支付流程受阻”。
2. **用户行为路径数据**：商品页→加购→到达结算页→离开，各步骤的退出率，用以判断购物车环节中具体是在“结算页”还是“信息填写页”流失。
3. **来源渠道与用户画像数据**：如广告流量占比、新客/老客比例、设备类型、地理位置，以排除流量质量问题。
4. **促销与优惠券使用数据**：如是否有多轮促销活动、用户是否领取优惠券但未使用，验证“等待降价”假设。
5. **同品类同价位商品的对比数据**：如该品类下价格分位>90%的其他商品的Cart→Purchase转化率，以判断当前表现是高价位商品的普遍现象还是该单品特有问题。
6. **价格敏感度测试数据**：如小范围测试折扣价（如10%-15% off）后的购物车完成率变化，用于验证价格假设的有效性。

以上补充数据的收集需保证样本量足够后，再进行下一轮诊断，当前不建议根据单点数据直接下结论。
'''







"output2"
#修改第5条prompt，新增第13、14、15、16条prompt

'''
========== Conversion Metrics ==========
product_id: 6
category: Tops & Tees
product_sessions: 23
purchase_cvr: 8.70%
category_cvr: 26.93%

========== Anomaly Detection ==========
status: severe
deviation: -0.6771

Anomaly Router: severe

========== Funnel Analysis ==========
Product→Cart deviation: -10.99%
Cart→Purchase deviation: -63.72%
weak_stage: cart_to_purchase

========== Price Analysis ==========
sku_price: 132.0
category_median: 30.734999656677246
percentile: 97.38%
price_status: high

========== Industry Benchmark ==========
Dynamic Yield Fashion/Apparel 2025外部行业参考：加购率（商品页浏览口径）: 6.58%；购买转化率（访客口径）: 3.03%；购物车完成率代理（派生）: 21.87%；购物车放弃率: 78.13%。注意：与TheLook统计口径不同，不可直接用于异常阈值判断。

========== Report ==========


========== Final Report ==========
一、诊断结论

该商品 **Wilt Women's Color Blocked Big Mixed Slant Top**（Product ID: 6，类目：Tops & Tees）当前转化漏斗处于 **severe（严重）异常** 状态。整体购买转化率（SKU Product→Purchase CVR 8.70%）显著低于类目基准（26.93%），相对偏离 **-67.71%**。漏斗主要异常集中在 **购物车至支付环节（cart_to_purchase）**，该阶段转化率较类目基准存在明显下滑。当前证据不足以确定因果原因，需结合更多数据进一步定位。

---

二、已知事实

- **样本量**：Product Sessions = 23，已通过当前项目最低样本量门槛（≥20），故不涉及“样本不足”判定。
- **加购阶段**：SKU Product→Cart Rate 为 56.52%，类目基准为 63.50%，相对偏离 **-10.99%**，该阶段未达异常判定标准（未触发low/severe），目前暂未发现明显异常。
- **支付阶段**：SKU Cart→Purchase Rate 为 15.38%，类目基准为 42.40%，相对偏离 **-63.72%**，为本次异常的主要集中环节。
- **整体转化**：SKU Product→Purchase CVR 为 8.70%，类目基准为 26.93%，相对偏离 **-67.71%**，整体表现严重落后于类目。
- **价格状态**：SKU 零售价/标价为 132.0 元，类目零售价中位数为 30.73 元，该商品价格处于类目价格的 **97.38% 分位**（即高于绝大多数同类商品），判定为 **high（偏高）**。

---

三、漏斗异常定位

- **weak_stage（主要弱环节）**：**cart_to_purchase（购物车至支付）**。
- **该阶段表现**：SKU Cart→Purchase Rate 为 15.38%，类目 Benchmark 为 42.40%，相对偏离 **-63.72%**，即 SKU 该阶段转化率较类目基准低 **63.72%**（此为相对偏离值，并非“用户流失比例”）。
- **对比加购阶段**：Product→Cart 相对偏离仅为 -10.99%，未触发异常阈值，说明漏斗异常并未集中在此环节；但需注意，该阶段暂未发现明显异常，并不等同于商品图片、标题、描述等本身没有问题，只是当前数据不支持此判断。

---

四、可能影响因素

1. **价格因素（现有数据直接支持）**
   该商品零售价/标价为 132.0 元，而类目零售价中位数为 30.73 元，价格分位高达 97.38%，处于类目极高水平。**价格偏高是可能影响因素之一**，但需注意：现有证据无法证明**是**价格直接导致转化下降，只能将其列为潜在影响因素。

2. **购物车环节体验或支付阻碍（属于假设，需更多数据验证）**
   加购阶段未现明显异常，但 Cart→Purchase 阶段严重偏低，可能涉及购物车页面的支付流程、运费、税费、支付方式、用户犹豫等，但 **现有数据不足以确认具体原因**，需要补充购物车页面行为数据、放弃原因调查等来验证。

3. **商品价值感与价格匹配度（属于假设，需更多数据验证）**
   商品标价极高，可能在用户加购后，结算前进行最终比价或价值评估时，导致购买意愿显著下降。此为合理假设，但当前数据无法验证。

---

五、外部行业参考

Dynamic Yield Fashion/Apparel 2025 外部行业参考数据如下（仅作背景参照）：
- 加购率（商品页浏览口径）：6.58%
- 购买转化率（访客口径）：3.03%
- 购物车完成率代理（派生）：21.87%
- 购物车放弃率：78.13%

**重要说明**：该外部参考（Dynamic Yield）与 TheLook 项目统计口径不同，**不可直接用于高低比较**，也不可通过其数值推算本SKU的预期表现。仅作为行业一般水平的背景信息。

---

六、下一步需要补充的数据

以下数据可以帮助进一步定位异常原因，但需注意当前证据不足以直接判断因果关系，需通过新数据验证：

1. **购物车放弃原因数据**：例如弃购用户调研、退出页面记录、支付失败日志等，用于判断 Cart→Purchase 下滑的具体阻碍点（如运费、支付方式、价格犹豫等）。
2. **加购后至结账的时间间隔与行为路径**：如是否多次访问、是否对比其他商品、是否使用优惠券等。
3. **同类高价格带商品（≥100元）的类目内转化表现**：用于判断是否为价格带普遍现象，而非本SKU特有异常。
4. **商品详情页停留时长、跳出率、评价数量与评分**：用于验证加购阶段是否存在隐性质量问题（当前该阶段未现明显异常，但不排除滞后影响）。
5. **竞品或同价位商品的 Cart→Purchase 数据**：用于判断是否为价格敏感型用户的普遍行为。
6. **复购与历史订单数据（如该用户群以往购买史）**：用于判断是否为价格首次暴露（如首次看到高价）导致的决策延迟。
'''





"output3"
#新增 def find_test_cases ，查找4个测试SKU
# severe            → 7498
# low               → 4680
# normal            → 19681
# insufficient_data → 16599

'''
========== Test Cases ==========
severe → product_id: 7498
low → product_id: 4680
normal → product_id: 19681
insufficient_data → product_id: 16599

========== Conversion Metrics ==========
product_id: 6
category: Tops & Tees
product_sessions: 23
purchase_cvr: 8.70%
category_cvr: 26.93%

========== Anomaly Detection ==========
status: severe
deviation: -0.6771

Anomaly Router: severe

========== Funnel Analysis ==========
Product→Cart deviation: -10.99%
Cart→Purchase deviation: -63.72%
weak_stage: cart_to_purchase

========== Price Analysis ==========
sku_price: 132.0
category_median: 30.734999656677246
percentile: 97.38%
price_status: high

========== Industry Benchmark ==========
Dynamic Yield Fashion/Apparel 2025外部行业参考：加购率（商品页浏览口径）: 6.58%；购买转化率（访客口径）: 3.03%；购物车完成率代理（派生）: 21.87%；购物车放弃率: 78.13%。注意：与TheLook统计口径不同，不可直接用于异常阈值判断。

========== Report ==========


========== Final Report ==========
# 电商转化率诊断报告

**商品：** Wilt Women's Color Blocked Big Mixed Slant Top
**Product ID：** 6
**Category：** Tops & Tees
**报告日期：** 2026-05-07


## 一、诊断结论

**该SKU（Product ID: 6）存在严重（severe）转化异常，核心异常集中在“购物车→购买”环节。**

该商品整体购买转化率（Product→Purchase CVR）为 **8.70%**，而品类基准为 **26.93%**，相对偏离达 **-67.71%**，属于严重异常水平。从漏斗分环节来看，Product→Cart 环节的转化率为 **56.52%**，品类基准为 **63.50%**，相对偏离仅 **-10.99%**，尚未达到明显异常标准；而 Cart→Purchase 环节的转化率仅为 **15.38%**，品类基准为 **42.40%**，相对偏离达到 **-63.72%**，是拖累整体转化率的核心薄弱环节。

此外，该商品零售价/标价为 **132.00美元**，处于品类价格分布的 **97.4百分位**，显著高于品类中位数（约30.73美元），价格偏高是可能影响因素之一，但价格与转化异常之间的因果关系无法由现有数据直接确认。


## 二、已知事实

| 指标 | SKU数值 | Category Benchmark | 相对偏离 |
|---|---|---|---|
| Product Sessions | 23 | — | 已达到最低样本量门槛 |
| Product→Cart Rate | 56.52% | 63.50% | -10.99% |
| Cart→Purchase Rate | 15.38% | 42.40% | **-63.72%** |
| Product→Purchase CVR | 8.70% | 26.93% | **-67.71%** |
| 零售价/标价 | 132.00美元 | 中位数 30.73美元 | 价格分位 **97.4%** |


- 商品访客数为23，已达到当前项目最低样本量门槛，本次诊断结论具备现有数据支撑；
- 异常状态为 **severe（严重）**；
- 主要弱环节为 **cart_to_purchase（购物车→购买）**；
- 价格状态为 **high（高）**。


## 三、漏斗异常定位

**结论：购物车→购买环节是本次转化异常的主要集中位置。**

### 漏斗分环节对比

**1. Product→Cart（商品浏览→加入购物车）**

SKU Product→Cart Rate 为 **56.52%**，Category Benchmark 为 **63.50%**，相对偏离为 **-10.99%**。

该阶段表现略低于品类基准，但偏离幅度有限，未达到异常判定标准。因此，**该阶段暂未发现明显异常**。需要特别说明的是，这并不等同于商品图片、标题或描述没有问题——仅表示在现有数据口径下，该阶段没有表现出显著的转化阻力。

**2. Cart→Purchase（加入购物车→完成购买）**

SKU Cart→Purchase Rate 为 **15.38%**，Category Benchmark 为 **42.40%**，相对偏离为 **-63.72%**。

该阶段表现明显低于品类基准——转化率不足品类基准的四成（15.38% vs 42.40%），是导致整体购买转化率严重偏低的最主要因素。上述偏离程度反映的是转化率与基准之间的差距，而非直接等同于用户流失比例。

**3. 整体：Product→Purchase CVR**

SKU Product→Purchase CVR 为 **8.70%**，Category Benchmark 为 **26.93%**，相对偏离为 **-67.71%**，整体转化效率严重低于品类正常水平，与购物车环节的显著落后高度一致。

### 异常严重程度

- **整体CVR相对偏离：-67.71%（severe）**
- **Cart→Purchase 相对偏离：-63.72%**
- **Product→Cart 相对偏离：-10.99%**
- **主要弱环节：** Cart→Purchase


## 四、可能影响因素

### 当前数据直接支持的因素

**1. 价格因素（价格偏高）**

该商品零售价/标价为 **132.00美元**，在品类中处于 **97.4百分位**，远高于品类中位数（约30.73美元）。价格偏高是可能影响因素之一。

在“加入购物车→完成购买”这一环节，消费者通常需要完成实际支付决策，对价格的敏感度显著提升。当商品价格远高于消费者对该品类的心理预期价位时，即使消费者已产生加购意愿，在结算环节仍可能因价格因素放弃购买——这与本次诊断中 Cart→Purchase 环节严重落后的表现相一致。

然而，需要明确的是：**现有证据不足以确定价格就是导致转化下降的因果原因**，只能判定“价格偏高是可能影响因素之一”。

### 需要更多数据验证的假设性因素

以下因素在逻辑上可能影响购物车→购买环节的转化，但当前数据无法验证，需补充数据后进一步确认：

- **运费与税费透明度：** 高单价商品在结算时叠加运费和税费，可能进一步加重消费者的支付压力，但当前数据中无相关信息。
- **竞争比价：** 消费者可能将商品加入购物车后，去其他平台比较同款或类似款的价格，导致购物车流失。当前数据无法验证。
- **库存或交付时效：** 该SKU是否存在库存紧张、发货周期长等影响购买决策的因素，需要通过后端数据确认。
- **优惠券/促销机制：** 是否存在针对该品类的优惠券或促销活动缺失，影响结算意愿。当前数据无相关信息。
- **商品评价与信任因素：** 消费者在结算前可能查看评价，差评或缺少评价可能影响最终购买。当前数据无法验证。
- **商品页面信息完整性：** 尺码表、面料成分、穿着效果等信息不足，可能导致消费者加购后犹豫。当前数据无法验证。


## 五、外部行业参考

根据 Dynamic Yield Fashion/Apparel 2025 外部行业数据：

- 加购率（商品页浏览口径）：**6.58%**
- 购买转化率（访客口径）：**3.03%**
- 购物车完成率代理（派生）：**21.87%**
- 购物车放弃率：**78.13%**

**重要说明：** Dynamic Yield 与 TheLook 的统计口径不同，以上数据仅作为行业背景参考，不可与本次 SKU 或品类基准数据进行直接高低比较，也不可通过 Dynamic Yield 数值推算 TheLook 指标。本次诊断结论完全基于 TheLook 内部品类基准数据。


## 六、下一步需要补充的数据

为深入定位购物车→购买环节转化严重偏低的根因，建议补充以下数据（按优先级排序）：

### 第一优先级（直接关系购物车流失原因）

1. **加购后到结算的时间分布及最终结果：** 加购后有多少比例进入结算页？有多少在结算页放弃？有多少最终完成购买？
2. **结算页放弃原因（如可追踪）：** 运费过高、无合适支付方式、页面报错、登录流程繁琐等退出原因数据。
3. **价格弹性相关数据：** 该SKU的历史促销价格、折扣力度与对应的转化率变化；同价格带商品的转化率对比。如果该SKU从未以低于132美元的价格销售过，可考虑设计A/B测试验证价格敏感度。

### 第二优先级（辅助判断价格与信任因素）

4. **同价格带商品对比：** 品类内价位相近（如100美元以上）的其他SKU的 Cart→Purchase Rate，以判断该偏低是价格带普遍现象还是该SKU的个体问题。若同价格带其他SKU也存在较低购物车完成率，则支持“高价格带天然结算流失更高”的判断；若仅该SKU偏低，则需要从商品本身因素排查。
5. **商品评价数据：** 评价数量、平均星级、近期新增评价；与品类平均水平对比。
6. **流量来源结构：** 该SKU的流量来自哪些渠道（搜索、推荐、广告、社交媒体等），不同渠道用户的购买意愿和价格敏感度可能存在差异。
7. **SKU历史数据：** 该SKU上架时长、历史转化趋势，判断是持续性问题还是近期波动。

### 第三优先级（长期优化参考）

8. **同类比价信息：** 该商品在外部平台（Amazon、独立站等）的售价对比，用于判断价格竞争力。
9. **用户反馈/退换货数据：** 该SKU的退换货率及用户评论中的共性反馈，辅助判断商品品质与预期落差问题。
10. **尺码与库存信息：** 热销尺码库存深度、断码情况，是否存在尺码不全导致消费者放弃购买的情况。


> **总结：** 该SKU存在严重的转化异常，主因集中在“加入购物车→完成购买”环节——即消费者愿意将商品加入购物车（该环节相对正常），但在最终结算前选择放弃。商品零售价/标价显著高于品类主流价位（97.4百分位）是最值得优先关注的可能影响因素之一，但现有数据尚不足以确认因果链条，需要通过上述补充数据进一步验证。建议优先从价格策略与结算体验两个方向开展排查与测试。
'''
