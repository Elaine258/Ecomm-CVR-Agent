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
17. 当 anomaly_status == "insufficient_data" 时：
    - 只允许说明 Product Sessions 未达到最低样本量20。
    - 可以展示当前原始转化指标，但不得判断其高、低、异常或正常。
    - 不得自行计算或解释 CVR deviation。
    - 不得定位 weak_stage。
    - 不得分析价格、漏斗原因或其他潜在原因。
    - 不得给出50、100等新的建议样本量。
    - 只允许建议“Product Sessions达到至少20后重新诊断”。
18. 当 anomaly_status == "normal" 时：
    - 不得自行执行深度漏斗诊断。
    - 可以展示各漏斗原始指标及Category Benchmark。
    - 不得自行给某个子阶段定义 low、weak、abnormal。
    - 明确说明“整体CVR未触发异常，因此本次未执行深度诊断”。
19. 如果 funnel_analysis 未执行：
    不得自行根据原始Rate重新模拟 funnel_analysis 的判断逻辑。
20. 如果 price_analysis 未执行：
    不得推断价格状态。
21. 只有 state 中明确存在的分析结果，
    才允许作为诊断结论使用。
22. price_status == "normal" 时：
    - 只能说明当前SKU价格位置未达到价格异常标准。
    - 不得表述为“价格因素已排除”“价格不会影响转化”。
    - 可以表述为“当前价格数据暂不支持将价格定位异常作为主要解释因素”。
23. 必须区分“相对偏离”和“百分点差”。
    cvr_deviation 是相对偏离比例：
    (SKU CVR - Category CVR) / Category CVR
    例如：
        SKU CVR = 25.81%
        Category CVR = 26.38%
        cvr_deviation = -2.18%
    正确：
    “相对偏离约-2.18%。”
    若要描述百分点差，必须使用：
        SKU CVR - Category CVR
        本例约为-0.57个百分点。
        禁止将-2.18%写成“低2.18个百分点”。

24. Tool未执行不等于数据缺失。
    必须表述为“本次流程未执行该分析”，
    不得自动改写成“当前没有该数据”。

25. 当 funnel_analysis 未执行时：
    - 可以展示 SKU 与 Category 的原始漏斗Rate。
    - 不得计算、描述或判断子漏斗是否达到异常阈值。
    - 不得使用“弱环节”“暂未发现异常”“达到异常标准”等诊断性表述。

26. “节点未执行”和“数据不存在”必须严格区分。
    如果原始数据已经存在，只是由于Router没有调用某分析节点，
    必须写“本次流程未执行该分析”，
    不得写成“需要补充该数据”或“当前没有该数据”。

27. 当 anomaly_status == "insufficient_data" 时，
    下一步唯一必要条件是 Product Sessions 达到至少20后重新运行诊断；
    不得额外要求补充当前系统已经拥有的数据。

28. 不得使用“显著”“统计显著”等措辞，
    除非输入中明确提供统计显著性检验结果。
    优先使用“明显低于”“达到当前异常阈值”。

29. 不得根据漏斗Rate自行推断用户心理或行为原因，
    例如“用户犹豫”“用户购买意愿下降”。
    只能描述实际转化完成比例及其与Benchmark的差异。

30. 当 anomaly_status == "normal" 时，
    按当前自动诊断策略无需继续执行深度分析。
    不得建议“下次执行funnel_analysis/price_analysis”
    作为正常诊断流程的一部分。
    如提及，只能说明是独立的探索性分析需求。

31. 分析节点未执行时，
    不得说原始字段为空或不存在。
    应表述为：
    “当前State中没有该分析结果，因为对应Node本次未执行。”

32. insufficient_data 达标后重新运行时，
    不得承诺一定执行Funnel/Price等深度分析。
    应说明：
    “重新判断异常状态，再由Router决定后续路径。”

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

for expected_status, product_id in test_cases.items():

    print("\n")
    print("=" * 70)
    print(
        f"TEST CASE: {expected_status}"
    )
    print(
        f"PRODUCT ID: {product_id}"
    )
    print("=" * 70)

    result = graph.invoke(
        {
            "user_question":
                "诊断这个SKU的转化表现",

            "product_id":
                product_id
        }
    )

    actual_status = result[
        "anomaly_status"
    ]

    print("\n========== Test Result ==========")

    print(
        "Expected:",
        expected_status
    )

    print(
        "Actual:",
        actual_status
    )

    print(
        "PASS:"
        if expected_status == actual_status
        else "FAIL:"
    )

    print(
        expected_status == actual_status
    )

    print(
        "\nFinal Report:"
    )

    print(
        result["final_report"]
    )




"output"

'''
========== Test Cases ==========
severe → product_id: 7498
low → product_id: 4680
normal → product_id: 19681
insufficient_data → product_id: 16599


======================================================================
TEST CASE: severe
PRODUCT ID: 7498
======================================================================

========== Conversion Metrics ==========
product_id: 7498
category: Blazers & Jackets
product_sessions: 23
purchase_cvr: 13.04%
category_cvr: 26.57%

========== Anomaly Detection ==========
status: severe
deviation: -0.5091

Anomaly Router: severe

========== Funnel Analysis ==========
Product→Cart deviation: -25.00%
Cart→Purchase deviation: -34.54%
weak_stage: cart_to_purchase

========== Price Analysis ==========
sku_price: 69.97000122070312
category_median: 59.9900016784668
percentile: 51.52%
price_status: normal

========== Industry Benchmark ==========
Dynamic Yield Fashion/Apparel 2025外部行业参考：加购率（商品页浏览口径）: 6.58%；购买转化率（访客口径）: 3.03%；购物车完成率代理（派生）: 21.87%；购物车放弃率: 78.13%。注意：与TheLook统计口径不同，不可直接用于异常阈值判断。

========== Report ==========

========== Test Result ==========
Expected: severe
Actual: severe
PASS:
True

Final Report:
一、诊断结论

该商品 **Anne Klein Women's Petite Tweed Jacket** 当前整体购买转化率 (CVR) 为 **13.04%**，相对品类基准 (26.57%) 的**相对偏离为 -50.91%**，属于 **severe（严重异常）** 状态。

基于可用数据，漏斗异常主要集中于**购物车到支付环节（cart_to_purchase）**。该环节为当前最大的转化短板，其相对偏离幅度大于商品页到购物车环节。

二、已知事实

- 商品页浏览次数：**23**，已达到（≥ 20）当前项目最低样本量门槛。
- SKU 商品页→加购率：**47.83%**。
- 品类 Benchmark 商品页→加购率：**63.77%**。
- SKU 商品页→购买转化率：**13.04%**。
- 品类 Benchmark 购买转化率：**26.57%**。
- SKU 加购→支付率：**27.27%**。
- 品类 Benchmark 加购→支付率：**41.66%**。
- 商品页→加购环节相对偏离：**-0.25**（较品类基准低 25.00%）。
- 加购→支付环节相对偏离：**-0.35**（较品类基准低 34.54%）。
- SKU 零售价/标价：**69.97 美元**。
- 品类零售价/标价中位数：**59.99 美元**。
- 价格分位：**0.52**（处于品类中等偏高位置）。
- 价格状态：**normal（正常）**。

三、漏斗异常定位

**主要异常环节：加购→支付 (Cart→Purchase)**。

- 该环节 SKU 转化率为 **27.27%**，品类基准为 **41.66%**。SKU 在此环节的转化率较品类基准低 **34.54%**，是当前整体 CVR 严重偏低的主要拖累项。
- 需要注意的是，商品页→加购环节 (Product→Cart) 转化率为 **47.83%**，亦低于品类基准 (63.77%) 达 **25.00%**。该偏差虽未超过主要异常环节的相对偏离值，但同样构成负向贡献。依据规则，若该环节未达到更高异常标准，仅能说明**该阶段暂未发现更明显异常**，不能据此判断商品图片、标题或描述没有问题。

四、可能影响因素

**1. 购物车完成率偏低（当前数据直接相关）**
现有的加购→支付数据显示该环节转化效率显著低于品类平均。现有证据表明该环节存在系统性障碍，但**具体原因（如运费、支付方式、退换货政策等）无法由当前数据直接确认**。

**2. 价格因素（需谨慎解读）**
当前 SKU 零售价/标价为 **69.97 美元**，高于品类中位数 (59.99 美元)，处于品类价格分位的 **0.52**。但价格状态显示为 **normal**，并非显著高价。因此，价格只能作为**可能的影响因素之一**，但不能据此断言价格导致转化下降。

**3. 其他假设（需要更多数据验证）**
- 商品在购物车环节的实际结算费用是否超出用户预期（如运费、税费）。
- 是否存在加购后临时缺货/取消订单等情况。
- 支付方式是否有限，或支付流程是否过长。
- 用户可能在加购后对比其他款式，导致放弃结算。
- 商品评价、尺码、库存数量是否在结算前对用户产生负面影响。

现有证据不足以确定上述假设的因果原因。

五、外部行业参考

根据 Dynamic Yield Fashion/Apparel 2025 外部行业参考（注意：该口径与 TheLook 统计口径不同）：
- 加购率（商品页浏览口径）：**6.58%**
- 购买转化率（访客口径）：**3.03%**
- 购物车完成率代理（派生）：**21.87%**
- 购物车放弃率：**78.13%**

由于统计口径不同，该行业参考数值**不可直接与本次 SKU 或品类 Benchmark 进行高低比较**，仅可作为行业背景参考，不能用于推算本报告中的异常阈值或作为诊断依据。

六、下一步需要补充的数据

为进一步定位购物车环节的卡点，需补充以下数据：

1. **购物车放弃原因追踪**：如用户离开购物车的页面路径，是否停留在支付页、运费页或登录页。
2. **结算流程各步骤转化数据**：从点击结账→填写地址→支付方式选择→支付确认各步的流失率。
3. **流量来源与用户意图分层**：如是否来自广告、促销、收藏夹或直接访问，用于判断加购用户是否为强购买意图。
4. **用户画像与历史行为资料**：包括是否复购用户、是否加入购物车多次后才购买，以及来自桌面端或移动端的差异。
5. **同品类高转化商品对照数据**：该商品与同品类转化较优的类似款式间，在价格、评价数量、主图点击率上的差异。
6. **价格弹性测试数据**：如果未来测试降价或打折，记录 CVR 与购物车完成率的变化以验证价格影响程度。


======================================================================
TEST CASE: low
PRODUCT ID: 4680
======================================================================

========== Conversion Metrics ==========
product_id: 4680
category: Jeans
product_sessions: 20
purchase_cvr: 15.00%
category_cvr: 26.68%

========== Anomaly Detection ==========
status: low
deviation: -0.4378

Anomaly Router: low

========== Funnel Analysis ==========
Product→Cart deviation: -13.13%
Cart→Purchase deviation: -35.28%
weak_stage: cart_to_purchase

========== Price Analysis ==========
sku_price: 189.0
category_median: 78.0
percentile: 91.25%
price_status: high

========== Industry Benchmark ==========
Dynamic Yield Fashion/Apparel 2025外部行业参考：加购率（商品页浏览口径）: 6.58%；购买转化率（访客口径）: 3.03%；购物车完成率代理（派生）: 21.87%；购物车放弃率: 78.13%。注意：与TheLook统计口径不同，不可直接用于异常阈值判断。

========== Report ==========

========== Test Result ==========
Expected: low
Actual: low
PASS:
True

Final Report:
一、诊断结论

该SKU（MiH Jeans Women‘s Marrakesh Jean，Product ID：4680）当前转化整体表现异常（状态：low），核心异常漏斗阶段为**购物车→购买（cart_to_purchase）**。SKU购物车→购买转化率为27.27%，相对品类基准（42.14%）低35.28%，偏离程度较大，是拖累整体购买转化率的主要环节。Product→Cart阶段转化率为55.00%，相对品类基准（63.31%）低13.13%，偏离相对较小。整体购买转化率（15.00%）较品类基准（26.68%）低43.78%。当前样本量（20次Product Sessions）已达到最低样本量门槛，结论具有初步参考性。

二、已知事实

- Product Sessions：20（已达到最低样本量门槛，不作样本不足处理）
- SKU Product→Cart Rate：55.00%；Category Benchmark：63.31%；相对偏离：-13.13%
- SKU Cart→Purchase Rate：27.27%；Category Benchmark：42.14%；相对偏离：-35.28%
- SKU Product→Purchase CVR：15.00%；Category CVR：26.68%；相对偏离：-43.78%
- SKU零售价/标价：189.0美元；品类零售价/标价中位数：78.0美元；价格分位：0.912（高于品类大多数商品）
- 异常状态：low；主要弱环节：cart_to_purchase

三、漏斗异常定位

- **主要异常阶段：购物车→购买环节。** SKU Cart→Purchase Rate为27.27%，Category Benchmark为42.14%，相对偏离-35.28%，是各阶段中偏离最大的环节，构成主要漏斗短板。
- **次要观察阶段：商品页→购物车环节。** SKU Product→Cart Rate为55.00%，Category Benchmark为63.31%，相对偏离-13.13%，存在一定差距，但未达到明显异常标准。该阶段暂未发现明显异常。
- **整体影响：** 由于购物车→购买环节的显著偏低，SKU整体Product→Purchase CVR为15.00%，较品类基准（26.68%）低43.78%。

四、可能影响因素

1. **价格偏高是可能影响因素之一。** 该SKU零售价/标价为189.0美元，处于品类价格分位约91.2%（高于品类约91%的商品），显著高于品类零售价中位数（78.0美元）。价格偏高可能影响用户在下单决策（购物车→购买环节）的转化意愿，但现有数据不能确认价格与转化下降之间的因果路径。
2. **购物车→购买环节本身可能存在转化障碍。** 该环节相对偏离达-35.28%，可能存在运费、税费、支付方式、库存、配送时效等结账体验方面的阻力，也可能与前述价格因素叠加。但**现有证据不足以确定因果原因**。

五、外部行业参考

根据Dynamic Yield Fashion/Apparel 2025外部行业参考：商品页浏览口径加购率为6.58%，访客口径购买转化率为3.03%，购物车完成率（派生）为21.87%，购物车放弃率为78.13%。该数据与TheLook统计口径不同，不可直接进行数值高低比较，仅作行业背景参考，不可据此推算TheLook体系下的具体指标。

六、下一步需要补充的数据

1. **购物车放弃原因数据：** 购物车→购买环节的用户退出原因（如运费、价格、支付方式、登录要求等），用于验证结账环节是否存在结构性障碍。
2. **价格敏感度测试数据：** 同款或同类商品在价格调整后的转化率对比，或用户对价格维度的反馈（如评论、退单原因），用于判断价格高是否实际影响下单决策。
3. **流量来源与用户画像数据：** 该SKU的流量渠道、访客类型（新客/老客）、设备类型等，以判断是否因流量质量差异导致购买意愿偏低。
4. **购买路径行为数据：** 用户从加购到最终支付的会话时长、是否多次访问、是否使用优惠码等行为数据，辅助识别购物车环节的具体摩擦点。
5. **竞品同价位段对比数据：** 同品类中接近该价位区间的SKU转化表现，用于判断高价位本身是否构成转化瓶颈。
6. **商品页面与详情数据：** 如尺码信息完整性、用户评价数量与评分、库存状态等，用于排查商品页→购物车环节是否存在隐性障碍（尽管该环节暂未达到异常标准）。


======================================================================
TEST CASE: normal
PRODUCT ID: 19681
======================================================================

========== Conversion Metrics ==========
product_id: 19681
category: Sweaters
product_sessions: 31
purchase_cvr: 25.81%
category_cvr: 26.38%

========== Anomaly Detection ==========
status: normal
deviation: -0.0218

Anomaly Router: normal

========== Report ==========

========== Test Result ==========
Expected: normal
Actual: normal
PASS:
True

Final Report:
## 一、诊断结论

该SKU **Fred Perry Men's Vintage Marl Crew Neck Sweater（Product ID: 19681）** 当前状态为 **normal（正常）**，未检测到明确异常。Product Sessions为31，已达到当前项目最低样本量门槛（≥20），基于现有数据可以进行分析。

整体来看，SKU Product→Cart Rate（70.97%）表现优于Category Benchmark（62.93%），“商品详情页→加入购物车”阶段表现良好；但SKU Cart→Purchase Rate（36.36%）低于Category Benchmark（41.93%），在“购物车→支付完成”环节相对偏弱，尚未达到异常判定标准。

## 二、已知事实

| 指标 | SKU数值 | Category Benchmark | 相对偏离 |
|------|---------|-------------------|----------|
| Product Sessions | 31 | — | — |
| Product→Cart Rate | 70.97% | 62.93% | — |
| Cart→Purchase Rate | 36.36% | 41.93% | — |
| Product→Purchase CVR | 25.81% | 26.38% | -0.0218 |

- CVR相对偏离为 **-0.0218**，表明SKU整体下单转化率略低于品类基准，但幅度较小。
- 异常状态判定为 **normal**，未达异常标准。
- 主要弱环节：**未执行**（当前数据未明确识别出漏斗主异常阶段）。
- 价格状态：**未执行**，当前未获取到SKU零售价及品类零售价中位数数据。

## 三、漏斗异常定位

整体漏斗定位如下：

1. **Product→Cart（商品详情→加入购物车）阶段**：SKU转化率为70.97%，Category Benchmark为62.93%，SKU表现优于品类基准。**该阶段暂未发现明显异常。** 但不能据此判断商品图片、标题、商品描述没有问题。

2. **Cart→Purchase（购物车→支付完成）阶段**：SKU转化率为36.36%，Category Benchmark为41.93%，相对偏离为负值，说明该阶段表现低于品类基准。但由于未达到异常标准，当前判定为**弱环节不明确**，尚不能定位为显著异常阶段。

3. **整体Product→Purchase CVR**：SKU为25.81%，Category为26.38%，相对偏离-0.0218。整体转化水平与品类基准基本持平。

## 四、可能影响因素

基于现有数据，**现有证据不足以确定因果原因**。可提出以下待验证假设：

**当前数据直接支持的方向：**

- SKU在“商品详情→加购”阶段表现优于品类基准，说明商品页面在吸引用户加购方面没有明显问题。
- SKU在“购物车→支付”阶段转化率低于品类基准，可能存在加购后流失的隐患，但与品类基准差异未达异常标准，需更多数据验证。

**需要更多数据验证的假设：**

- 购物车→支付阶段的偏低是否与价格因素相关（当前未获取价格数据，无法判断）。
- 是否与运费、支付方式、库存状态、用户评价等非页面因素有关。
- 是否与流量来源质量、用户购买意向强弱有关。

## 五、外部行业参考

外部行业参考**未调用**，当前报告中不引用Dynamic Yield或TheLook数据作为外部基准，避免口径不一致导致的误判。

## 六、下一步需要补充的数据

为更精确诊断该SKU的转化表现，建议补充以下数据：

1. **价格数据**：SKU零售价/标价，Category零售价中位数，计算价格分位，判断价格定位是否对转化构成影响。
2. **购物车→支付阶段细分数据**：进入购物车后放弃支付的节点（如填写地址、选择物流、支付环节），用于定位具体流失位置。
3. **流量来源数据**：各渠道（自然搜索、广告、社交媒体等）的Sessions与CVR分布。
4. **用户行为数据**：商品页平均停留时长、跳出率、加购后放弃时长等。
5. **库存与物流信息**：SKU库存状态、预计发货时间、是否影响购买决策。
6. **评价与评分数据**：该SKU的商品评分、评论数量及内容情感倾向。
7. **竞品对照数据**：同品类下相近价位、相近风格SKU的Cart→Purchase Rate，用于参考对照。

在补充上述数据之前，当前诊断结论维持为：**整体表现正常，购物车→支付环节相对偏弱但未达异常标准，需持续监测。**


======================================================================
TEST CASE: insufficient_data
PRODUCT ID: 16599
======================================================================

========== Conversion Metrics ==========
product_id: 16599
category: Tops & Tees
product_sessions: 19
purchase_cvr: 21.05%
category_cvr: 26.93%

========== Anomaly Detection ==========
status: insufficient_data
deviation: None

Anomaly Router: insufficient_data

========== Report ==========

========== Test Result ==========
Expected: insufficient_data
Actual: insufficient_data
PASS:
True

Final Report:
一、诊断结论

当前商品 **IZOD Men's Slim Fit Long Sleeve Mini Check Button Down Shirt（Product ID: 16599）** 数据样本不足，暂无法给出可靠的转化率诊断结论。由于 Product Sessions 仅为 **19**，未达到当前项目最低样本量门槛（20 sessions），因此所有转化率数据均存在较高的随机波动风险，不具备统计稳定性。

建议在积累了足够的访问样本后再进行诊断。现有证据不足以确定因果原因。

二、已知事实

| 指标 | SKU | Category Benchmark | 相对偏离 |
|------|-----|-------------------|----------|
| Product Sessions | **19** | - | - |
| Product→Cart Rate | 63.16% | 63.50% | 无偏离（-0.54%） |
| Product→Purchase CVR | 21.05% | 26.93% | -21.83% |
| Cart→Purchase Rate | 33.33% | 42.40% | -21.39% |

- 基于 19 次访问，发生了 12 次加购（63.16%）、4 次购买（21.05%）。
- Product→Cart Rate 与品类基准基本持平（63.16% vs 63.50%）。
- Cart→Purchase Rate 低于品类基准（33.33% vs 42.40%）。
- Product→Purchase CVR 低于品类基准（21.05% vs 26.93%）。

三、漏斗异常定位

由于样本量不足（Sessions=19 < 20），**暂不定位主要弱环节**。

就现有数据观察：
- **Product→Cart 阶段**：SKU 加购率为 63.16%，Category Benchmark 为 63.50%，相对偏离仅 -0.54%，该阶段相对品类基准基本持平，暂未发现明显异常。
- **Cart→Purchase 阶段**：SKU 转化率为 33.33%，Category Benchmark 为 42.40%，相对偏离 -21.39%，该阶段目前表现明显低于品类基准，但需在样本量充足后进一步确认。

四、可能影响因素

需要对更多数据验证的假设：
1. **购物车至购买环节转化偏低（假设）**：现有数据显示 SKU Cart→Purchase Rate（33.33%）低于品类基准（42.40%），可能涉及支付流程、运费、尺码/退换政策等购物车环节因素，也可能仅由样本量过小引起的随机波动所致。**现有证据不足以确定因果原因。**
2. **价格因素（假设）**：当前未获取到 SKU 零售价及品类零售价中位数，无法评估价格定位对转化率的影响。
3. **Product→Cart 阶段表现与品类持平（事实）**：基于当前数据，该阶段暂未发现明显异常。但样本量不足，不能据此判断图片、标题、商品描述没有问题。

五、外部行业参考

外部行业参考（Dynamic Yield 等）**未调用**。

根据规则，Dynamic Yield 与 TheLook 口径不一致，无法进行直接比较或推算，且在本次诊断中未获取相关外部数据，故不提供外部行业参考信息。

六、下一步需要补充的数据

1. **增加访问样本量**：优先将 Product Sessions 提升至 **20 以上**，建议持续积累至 50–100 sessions 以获得更稳定的转化率估计。
2. **价格与定位数据**：
   - SKU 零售价/标价
   - 品类零售价中位数
   - 价格分位
3. **购物车放弃原因**：通过用户调查或退出问卷，了解用户未完成购买的具体原因。
4. **商品页面行为数据**（可选）：图片点击率、评价数量与评分、库存状态、尺码可用性，辅助判断 Product→Cart 上游因素。
5. **流量来源结构**：区分自然搜索、广告、社交等渠道的流量质量，排除渠道差异干扰。

> 注意：上述建议中，第 1、2 项为当前数据缺失或不足所直接支持的补充需求；第 3–5 项为需要更多数据才能验证的假设方向，在数据补齐前，不应作为因果判断依据。


========== Final Report ==========
一、诊断结论

当前商品 **IZOD Men's Slim Fit Long Sleeve Mini Check Button Down Shirt（Product ID: 16599）** 数据样本不足，暂无法给出可靠的转化率诊断结论。由于 Product Sessions 仅为 **19**，未达到当前项目最低样本量门槛（20 sessions），因此所有转化率数据均存在较高的随机波动风险，不具备统计稳定性。

建议在积累了足够的访问样本后再进行诊断。现有证据不足以确定因果原因。

二、已知事实

| 指标 | SKU | Category Benchmark | 相对偏离 |
|------|-----|-------------------|----------|
| Product Sessions | **19** | - | - |
| Product→Cart Rate | 63.16% | 63.50% | 无偏离（-0.54%） |
| Product→Purchase CVR | 21.05% | 26.93% | -21.83% |
| Cart→Purchase Rate | 33.33% | 42.40% | -21.39% |

- 基于 19 次访问，发生了 12 次加购（63.16%）、4 次购买（21.05%）。
- Product→Cart Rate 与品类基准基本持平（63.16% vs 63.50%）。
- Cart→Purchase Rate 低于品类基准（33.33% vs 42.40%）。
- Product→Purchase CVR 低于品类基准（21.05% vs 26.93%）。

三、漏斗异常定位

由于样本量不足（Sessions=19 < 20），**暂不定位主要弱环节**。

就现有数据观察：
- **Product→Cart 阶段**：SKU 加购率为 63.16%，Category Benchmark 为 63.50%，相对偏离仅 -0.54%，该阶段相对品类基准基本持平，暂未发现明显异常。
- **Cart→Purchase 阶段**：SKU 转化率为 33.33%，Category Benchmark 为 42.40%，相对偏离 -21.39%，该阶段目前表现明显低于品类基准，但需在样本量充足后进一步确认。

四、可能影响因素

需要对更多数据验证的假设：
1. **购物车至购买环节转化偏低（假设）**：现有数据显示 SKU Cart→Purchase Rate（33.33%）低于品类基准（42.40%），可能涉及支付流程、运费、尺码/退换政策等购物车环节因素，也可能仅由样本量过小引起的随机波动所致。**现有证据不足以确定因果原因。**
2. **价格因素（假设）**：当前未获取到 SKU 零售价及品类零售价中位数，无法评估价格定位对转化率的影响。
3. **Product→Cart 阶段表现与品类持平（事实）**：基于当前数据，该阶段暂未发现明显异常。但样本量不足，不能据此判断图片、标题、商品描述没有问题。

五、外部行业参考

外部行业参考（Dynamic Yield 等）**未调用**。

根据规则，Dynamic Yield 与 TheLook 口径不一致，无法进行直接比较或推算，且在本次诊断中未获取相关外部数据，故不提供外部行业参考信息。

六、下一步需要补充的数据

1. **增加访问样本量**：优先将 Product Sessions 提升至 **20 以上**，建议持续积累至 50–100 sessions 以获得更稳定的转化率估计。
2. **价格与定位数据**：
   - SKU 零售价/标价
   - 品类零售价中位数
   - 价格分位
3. **购物车放弃原因**：通过用户调查或退出问卷，了解用户未完成购买的具体原因。
4. **商品页面行为数据**（可选）：图片点击率、评价数量与评分、库存状态、尺码可用性，辅助判断 Product→Cart 上游因素。
5. **流量来源结构**：区分自然搜索、广告、社交等渠道的流量质量，排除渠道差异干扰。

> 注意：上述建议中，第 1、2 项为当前数据缺失或不足所直接支持的补充需求；第 3–5 项为需要更多数据才能验证的假设方向，在数据补齐前，不应作为因果判断依据。
'''






"output2"
#新增第17-21条prompt
'''
========== Test Cases ==========
severe → product_id: 7498
low → product_id: 4680
normal → product_id: 19681
insufficient_data → product_id: 16599


======================================================================
TEST CASE: severe
PRODUCT ID: 7498
======================================================================

========== Conversion Metrics ==========
product_id: 7498
category: Blazers & Jackets
product_sessions: 23
purchase_cvr: 13.04%
category_cvr: 26.57%

========== Anomaly Detection ==========
status: severe
deviation: -0.5091

Anomaly Router: severe

========== Funnel Analysis ==========
Product→Cart deviation: -25.00%
Cart→Purchase deviation: -34.54%
weak_stage: cart_to_purchase

========== Price Analysis ==========
sku_price: 69.97000122070312
category_median: 59.9900016784668
percentile: 51.52%
price_status: normal

========== Industry Benchmark ==========
Dynamic Yield Fashion/Apparel 2025外部行业参考：加购率（商品页浏览口径）: 6.58%；购买转化率（访客口径）: 3.03%；购物车完成率代理（派生）: 21.87%；购物车放弃率: 78.13%。注意：与TheLook统计口径不同，不可直接用于异常阈值判断。

========== Report ==========

========== Test Result ==========
Expected: severe
Actual: severe
PASS:
True

Final Report:
## 一、诊断结论

严重异常（severe）。当前商品整体购买转化率显著低于同品类基准，主要异常集中在**购物车到支付**环节，需要优先干预。部分加购环节也有一定差距，但严重程度低于支付环节。

## 二、已知事实

- **样本情况**：Product Sessions 为 23，已达到当前项目最低样本量门槛（≥20），可以进行有效诊断。
- **价格状态**：正常（normal），SKU 零售价为 $69.97，品类零售价中位数为 $59.99，价格分位为 0.515。
- **异常状态**：severe
- **主要弱环节**：cart_to_purchase

## 三、漏斗异常定位

| 漏斗阶段 | SKU 实际转化率 | Category Benchmark | 相对偏离 | 状态判断 |
|---------|--------------|-------------------|---------|---------|
| Product → Cart | 47.83% | 63.77% | -25.00% | 偏离但未达异常标准，暂未发现明显异常 |
| Cart → Purchase | 27.27% | 41.66% | -34.54% | **主要异常环节，明显低于品类基准** |
| Product → Purchase（整体） | 13.04% | 26.57% | -50.91% | 严重异常 |

**核心发现**：SKU 整体购买转化率为 13.04%，较 Category Benchmark（26.57%）相对偏离 -50.91%。其中：

- **购物车到支付环节**构成主要瓶颈。SKU Cart→Purchase Rate 为 27.27%，Category Benchmark 为 41.66%，相对偏离 -34.54%，该阶段表现明显低于品类基准。说明已加购用户完成支付的意愿或能力显著弱于品类平均水平。
- Product→Cart 阶段（47.83% vs 63.77%，相对偏离 -25.00%）虽然存在差距，但未触发异常标准，**该阶段暂未发现明显异常**。注意，这不能据此判断图片、标题、商品描述没有问题，仅说明在当前数据下该阶段不是主要异常集中点。

**需要特别说明的是**：相对偏离（-50.91%、-34.54% 等）是 SKU 指标相对于品类基准的差异程度，**不代表用户流失比例**。现有数据中未提供对应流失率的直接计算结果，不可将其解读为"超过 X% 的用户在购物车环节流失"。

## 四、可能影响因素

**（一）购物车到支付环节（cart_to_purchase）显著偏低的可能原因**

1. **当前数据直接支持的因素**：
   - 该商品加购后支付转化率显著低于品类基准，说明用户"加购但未支付"的倾向明显高于品类平均水平，是当前漏斗中最需要优先优化的环节。
   - 价格状态为正常（价格分位 0.515，处于品类中位水平），但需注意：价格数据充足且价格状态判定为 normal，说明价格并非拉低该环节表现的主要因素（因此在本次诊断中价格不作为重点归因方向）。

2. **需要更多数据验证的假设**：
   - **支付环节存在额外费用或结算复杂度高**：运费、税费等结账时新增费用是否高于同类目其他商品，需通过订单数据辅助验证。
   - **售后/退换货政策**：如该商品退换货限制较多，可能影响用户最终支付决策。
   - **购物车中同时与其他商品竞争**：用户是否将该商品与竞品同时加购后择一购买，需要用户行为数据验证。
   - **商品详情页已展示的信息与支付时预期的落差**：如尺码、版型、面料等预期管理问题，需要结合评价和售后数据。
   - **库存/物流信息**：是否在购物车结算时出现库存紧张或配送时效差异，属于需要订单环节数据验证的假设。

**（二）Product→Cart 阶段的说明**

该阶段相对偏离为 -25.00%，但未达到异常标准，**暂未发现明显异常**。现有证据不足以确定该阶段存在具体问题，也不足以确认其没有问题。

**（三）因果判断声明**

现有证据仅能定位异常发生的漏斗环节及偏离幅度，**不足以确定导致购物车→支付转化率偏低的因果原因**。价格因素已排除（价格状态为 normal），但其他潜在原因（物流、竞品、支付体验等）需要进一步数据支持。

## 五、外部行业参考

根据 Dynamic Yield Fashion/Apparel 2025 外部行业数据：

- 加购率（商品页浏览口径）：6.58%
- 购买转化率（访客口径）：3.03%
- 购物车完成率代理（派生）：21.87%
- 购物车放弃率：78.13%

**参考时应特别注意**：Dynamic Yield 与 TheLook 统计口径不同，以上数据仅作为行业背景参考，**不得与当前 SKU 或品类指标进行直接高低比较**，也不得通过 Dynamic Yield 数值推算 TheLook 指标。

从行业背景来看，服饰类目购物车放弃率通常在较高水平（约 78%），说明"加购未支付"是服装品类中普遍存在的现象，但在本商品中该环节的表现仍明显落后于 TheLook 品类基准，需要针对性关注。

## 六、下一步需要补充的数据

以下是建议补充的数据，用于进一步验证购物车→支付环节异常的具体原因：

| 数据类型 | 用途 | 优先级 |
|---------|------|-------|
| **购物车放弃用户的行为数据**（放弃时间点、放弃前最后交互页面） | 定位用户在结算流程中卡在哪一步 | 高 |
| **运费/税费等附加费用数据** | 验证结账新增费用是否是放弃原因之一 | 高 |
| **同类目下其他 SKU 的 Cart→Purchase 明细**（排除品类整体趋势影响） | 确认该 SKU 属于个别问题还是品类共性问题 | 高 |
| **用户评价/退货数据**（尤其是尺码、版型、面料相关反馈） | 验证商品预期管理是否影响最终支付意愿 | 中 |
| **库存/物流时效信息** | 验证是否因配送问题放弃购买 | 中 |
| **竞品同类型商品的价格与促销对比** | 验证是否因促销力度不足导致用户转向竞品 | 低 |
| **复购用户 vs 新用户在该商品上的支付差异** | 判断是否为认知度/信任度问题 | 低 |

**优先建议下一步动作**：先聚焦购物车→支付环节的优化，建议优先补充用户购物车放弃行为数据和结算附加费用数据，以验证支付环节是否存在结构性阻碍。Product→Cart 阶段当前未发现明显异常，在未获得更多数据前，暂不列入优先优化方向。


======================================================================
TEST CASE: low
PRODUCT ID: 4680
======================================================================

========== Conversion Metrics ==========
product_id: 4680
category: Jeans
product_sessions: 20
purchase_cvr: 15.00%
category_cvr: 26.68%

========== Anomaly Detection ==========
status: low
deviation: -0.4378

Anomaly Router: low

========== Funnel Analysis ==========
Product→Cart deviation: -13.13%
Cart→Purchase deviation: -35.28%
weak_stage: cart_to_purchase

========== Price Analysis ==========
sku_price: 189.0
category_median: 78.0
percentile: 91.25%
price_status: high

========== Industry Benchmark ==========
Dynamic Yield Fashion/Apparel 2025外部行业参考：加购率（商品页浏览口径）: 6.58%；购买转化率（访客口径）: 3.03%；购物车完成率代理（派生）: 21.87%；购物车放弃率: 78.13%。注意：与TheLook统计口径不同，不可直接用于异常阈值判断。

========== Report ==========

========== Test Result ==========
Expected: low
Actual: low
PASS:
True

Final Report:
一、诊断结论

该商品（MiH Jeans Women's Marrakesh Jean）当前整体购买转化率（CVR）为15.00%，相对品类基准（26.68%）偏离-43.78%，触发异常状态（low）。主要异常环节集中在购物车到购买阶段（cart_to_purchase）：SKU Cart→Purchase Rate为27.27%，品类基准为42.14%，相对偏离-35.28%，该阶段表现明显低于品类基准。同时，商品页到加购环节亦存在一定偏离（相对偏离-13.13%），但根据规则，仅将最薄弱的漏斗环节定位为购物车至购买阶段。

二、已知事实

- Product Sessions：20（已达到当前项目最低样本量门槛20，不属于样本不足情形）。
- SKU Product→Cart Rate：55.00%（品类基准：63.31%），相对偏离-13.13%。
- SKU Cart→Purchase Rate：27.27%（品类基准：42.14%），相对偏离-35.28%。
- SKU Product→Purchase CVR：15.00%（品类基准：26.68%），相对偏离-43.78%。
- 价格状态：high（SKU零售价189.0美元，品类零售价中位数78.0美元，价格分位0.912，即处于品类价格分布的较高位置）。

三、漏斗异常定位

根据输入数据，主要异常漏斗阶段为购物车到购买（cart_to_purchase）：
- SKU Cart→Purchase Rate为27.27%，Category Benchmark为42.14%，相对偏离-35.28%，该阶段表现明显低于品类基准。
- 商品页到加购（product_to_cart）阶段SKU Product→Cart Rate为55.00%，品类基准63.31%，相对偏离-13.13%，未达到异常判定标准（未触发异常阈值），因此该阶段暂未发现明显异常，但不能据此判断图片、标题、商品描述没有问题。
- 整体CVR为15.00%，相对品类基准偏离-43.78%，为low异常。

四、可能影响因素

当前数据分析中，价格状态为high：该商品零售价/标价为189.0美元，显著高于品类中位数（78.0美元），处于品类价格的高分位（价格分位0.912）。因此，价格偏高是可能影响因素之一，但不能据此认定价格直接导致转化下降。现有证据不足以确定因果原因，需结合价格弹性测试或同价位竞品对比进一步验证。

五、外部行业参考

Dynamic Yield Fashion/Apparel 2025外部行业参考（仅作背景）：加购率（商品页浏览口径）6.58%；购买转化率（访客口径）3.03%；购物车完成率代理（派生）21.87%；购物车放弃率78.13%。注意：该数据与TheLook统计口径不同，不可直接用于异常阈值判断，也不得通过该数值推算TheLook指标。

六、下一步需要补充的数据

- 购物车至购买阶段的详细行为数据：如进入购物车后的停留时长、是否使用优惠券、运费/税费显示时机、支付方式可用性、库存状态等，以定位该环节转化偏低的具体原因。
- 价格敏感度数据：如同一商品在不同价格点（如折扣价、促销价）下的加购率与购买转化率，用于验证高零售价/标价是否为影响转化的重要因素。
- 商品页与购物车页的用户行为录屏或热力图：用于排查是否存在页面加载、信息展示、信任元素（如退换货政策）等方面的体验问题。
- 同品类高转化商品的对比数据：包括价格、评分、评论数、促销策略等，辅助判断差异来源。
- 如后续希望进行统计推断，需补充更大样本量（满足项目最低样本量后继续累积），同时可考虑采集时间维度数据（如是否受季节、活动影响）。


======================================================================
TEST CASE: normal
PRODUCT ID: 19681
======================================================================

========== Conversion Metrics ==========
product_id: 19681
category: Sweaters
product_sessions: 31
purchase_cvr: 25.81%
category_cvr: 26.38%

========== Anomaly Detection ==========
status: normal
deviation: -0.0218

Anomaly Router: normal

========== Report ==========

========== Test Result ==========
Expected: normal
Actual: normal
PASS:
True

Final Report:
一、诊断结论

该商品整体转化表现未触发异常。SKU Product→Purchase CVR为25.81%，Category CVR为26.38%，相对偏离-0.0218，处于正常波动范围。因此本次未执行深度漏斗诊断，也未定位主要弱环节。

需要强调的是，整体CVR未触发异常，仅表明该商品在整体转化层面与品类基准无显著差距，不能据此推断商品详情页、图片、标题或描述等维度不存在优化空间。

二、已知事实

- Product Sessions为31，已达到当前项目最低样本量门槛。
- SKU Product→Cart Rate为70.97%，Category Product→Cart Rate为62.93%，SKU高于品类基准。
- SKU Product→Purchase CVR为25.81%，Category CVR为26.38%，两者接近，相对偏离为-2.18个百分点（即SKU较品类基准低2.18个百分点，此处为CVR相对偏离，不代表用户流失比例）。
- SKU Cart→Purchase Rate为36.36%，Category Cart→Purchase Rate为41.93%，SKU低于品类基准。
- 价格分析未执行，当前无SKU零售价及品类价格基准数据。
- 外部行业参考未调用。

三、漏斗异常定位

由于整体CVR未触发异常，且funnel_analysis未执行，本次不定位具体弱环节，也不对Product→Cart或Cart→Purchase子阶段进行异常判定。仅呈现原始指标对比：

- Product→Cart阶段：SKU为70.97%，Category为62.93%，SKU高于品类基准。
- Cart→Purchase阶段：SKU为36.36%，Category为41.93%，SKU低于品类基准。

尽管Cart→Purchase阶段SKU低于品类基准，但根据规则，整体CVR未触发异常，因此本次不将该阶段判定为异常或“弱环节”。

四、可能影响因素

价格分析未执行，无法判断当前SKU零售价/标价与品类价格中位数的相对位置，因此不推断价格是否为影响因素。

现有证据不足以确定导致任何转化波动的因果原因。

五、外部行业参考

外部行业参考未调用，本次不进行任何行业对比。

六、下一步需要补充的数据

- 价格分析所需数据：SKU零售价/标价、Category零售价中位数，以完成价格分位判断。
- Funnel分析所需数据：若需进一步定位子阶段异常，可提供足够的样本量（当前Sessions为31，已达到最低门槛），并结合多周期数据验证Cart→Purchase阶段偏低是否稳定。
- 外部行业参考（如Dynamic Yield）可作为行业背景参考，但不得用于直接推算或对比本SKU指标。
- 如需验证假设（如价格敏感度、购物车页转化阻力），需要补充AB测试或用户行为数据（如加购后放弃结算的路径数据）。


======================================================================
TEST CASE: insufficient_data
PRODUCT ID: 16599
======================================================================

========== Conversion Metrics ==========
product_id: 16599
category: Tops & Tees
product_sessions: 19
purchase_cvr: 21.05%
category_cvr: 26.93%

========== Anomaly Detection ==========
status: insufficient_data
deviation: None

Anomaly Router: insufficient_data

========== Report ==========

========== Test Result ==========
Expected: insufficient_data
Actual: insufficient_data
PASS:
True

Final Report:
一、诊断结论

当前商品 **IZOD Men's Slim Fit Long Sleeve Mini Check Button Down Shirt（Product ID: 16599）** 因 **Product Sessions 仅为 19（<20）**，未达到本次项目设定的最低样本量门槛，数据量不足以支持可靠诊断。因此，本次诊断**不执行漏斗异常定位、价格分析及归因判断**，现有数据仅作展示，不代表任何高、低、正常或异常结论。

二、已知事实

| 指标 | SKU 数值 | Category Benchmark |
| --- | --- | --- |
| Product Sessions | 19 | - |
| Product → Cart Rate | 63.16% | 63.50% |
| Product → Purchase CVR | 21.05% | 26.93% |
| Cart → Purchase Rate | 33.33% | 42.40% |
| CVR 相对偏离（xxx_deviation） | 未执行 | - |

以上为当前全部可用原始数据。由于样本量不足，**不对上述任何数值进行高低、优劣或异常判断**，亦不得据此解读为任何因果结论。

三、漏斗异常定位

未执行。当前 **anomaly_status = insufficient_data**，在 Product Sessions 达到 20 以前，不定位 weak_stage，不识别主要弱环节。

四、可能影响因素

未执行。现有证据不足以确定任何因果原因，不做价格、商品描述、图片、标题或任何其他维度的可能性推测。

五、外部行业参考

未调用。本次不提供任何行业基准对比。

六、下一步需要补充的数据

当前唯一可执行的建议是：

- **继续积累流量，待 Product Sessions 达到至少 20 后重新诊断。**

补充说明：在重新诊断时，建议同步确认以下字段齐全，以便完整分析：

- SKU 零售价 / Category 零售价中位数
- Product → Cart 相对偏离值
- Cart → Purchase 相对偏离值
- 价格分位及价格状态
- 外部行业参考数据

在数据未达标前，不预设、不推断任何结论。


========== Final Report ==========
一、诊断结论

当前商品 **IZOD Men's Slim Fit Long Sleeve Mini Check Button Down Shirt（Product ID: 16599）** 因 **Product Sessions 仅为 19（<20）**，未达到本次项目设定的最低样本量门槛，数据量不足以支持可靠诊断。因此，本次诊断**不执行漏斗异常定位、价格分析及归因判断**，现有数据仅作展示，不代表任何高、低、正常或异常结论。

二、已知事实

| 指标 | SKU 数值 | Category Benchmark |
| --- | --- | --- |
| Product Sessions | 19 | - |
| Product → Cart Rate | 63.16% | 63.50% |
| Product → Purchase CVR | 21.05% | 26.93% |
| Cart → Purchase Rate | 33.33% | 42.40% |
| CVR 相对偏离（xxx_deviation） | 未执行 | - |

以上为当前全部可用原始数据。由于样本量不足，**不对上述任何数值进行高低、优劣或异常判断**，亦不得据此解读为任何因果结论。

三、漏斗异常定位

未执行。当前 **anomaly_status = insufficient_data**，在 Product Sessions 达到 20 以前，不定位 weak_stage，不识别主要弱环节。

四、可能影响因素

未执行。现有证据不足以确定任何因果原因，不做价格、商品描述、图片、标题或任何其他维度的可能性推测。

五、外部行业参考

未调用。本次不提供任何行业基准对比。

六、下一步需要补充的数据

当前唯一可执行的建议是：

- **继续积累流量，待 Product Sessions 达到至少 20 后重新诊断。**

补充说明：在重新诊断时，建议同步确认以下字段齐全，以便完整分析：

- SKU 零售价 / Category 零售价中位数
- Product → Cart 相对偏离值
- Cart → Purchase 相对偏离值
- 价格分位及价格状态
- 外部行业参考数据

在数据未达标前，不预设、不推断任何结论。
'''




"output3"
#新增第22-24条prompt

'''
========== Test Cases ==========
severe → product_id: 7498
low → product_id: 4680
normal → product_id: 19681
insufficient_data → product_id: 16599


======================================================================
TEST CASE: severe
PRODUCT ID: 7498
======================================================================

========== Conversion Metrics ==========
product_id: 7498
category: Blazers & Jackets
product_sessions: 23
purchase_cvr: 13.04%
category_cvr: 26.57%

========== Anomaly Detection ==========
status: severe
deviation: -0.5091

Anomaly Router: severe

========== Funnel Analysis ==========
Product→Cart deviation: -25.00%
Cart→Purchase deviation: -34.54%
weak_stage: cart_to_purchase

========== Price Analysis ==========
sku_price: 69.97000122070312
category_median: 59.9900016784668
percentile: 51.52%
price_status: normal

========== Industry Benchmark ==========
Dynamic Yield Fashion/Apparel 2025外部行业参考：加购率（商品页浏览口径）: 6.58%；购买转化率（访客口径）: 3.03%；购物车完成率代理（派生）: 21.87%；购物车放弃率: 78.13%。注意：与TheLook统计口径不同，不可直接用于异常阈值判断。

========== Report ==========

========== Test Result ==========
Expected: severe
Actual: severe
PASS:
True

Final Report:
一、诊断结论

该SKU（Anne Klein Women's Petite Tweed Jacket，Product ID: 7498）当前处于**severe（严重）异常状态**，整体购买转化率（CVR）为13.04%，相对品类基准（26.57%）**相对偏离-50.91%**，即SKU的购买转化率较Category Benchmark低50.91%。当前Product Sessions为23，已达到最低样本量门槛（≥20），因此本次诊断基于现有数据执行。

主要异常漏斗阶段为**cart_to_purchase（购物车至购买环节）**。

二、已知事实

- Product Sessions：23（已达到最低样本量门槛）。
- SKU Product→Cart Rate：47.83%；Category Product→Cart Rate：63.77%。
- SKU Product→Purchase CVR：13.04%；Category CVR：26.57%。
- SKU Cart→Purchase Rate：27.27%；Category Cart→Purchase Rate：41.66%。
- CVR相对偏离：-0.5091（即-50.91%）。
- 主要弱环节：cart_to_purchase。
- Product→Cart偏离：-0.2500（即-25.00%）。
- Cart→Purchase偏离：-0.3454（即-34.54%）。
- 价格状态：normal。
- SKU零售价：$69.97；Category零售价中位数：$59.99；价格分位：0.5152（处于品类价格分布的约第51.5百分位）。

三、漏斗异常定位

1. **加购环节（Product→Cart）**：
   - SKU Product→Cart Rate为47.83%，Category Benchmark为63.77%，相对偏离**-25.00%**。
   - 该阶段表现低于品类基准，但未达到异常判定标准，因此本次诊断中**该阶段暂未发现明显异常**。需注意，这并不代表商品图片、标题、描述没有问题，仅说明当前数据不足以将该阶段定位为异常主因。

2. **购物车至购买环节（Cart→Purchase）**：
   - SKU Cart→Purchase Rate为27.27%，Category Benchmark为41.66%，相对偏离**-34.54%**。
   - 该阶段表现明显低于品类基准，是当前漏斗中异常最集中的位置，被定位为**主要弱环节**。

综上，整体CVR的严重异常主要由**购物车至购买环节**表现不佳驱动。

四、可能影响因素

1. **价格因素**：
   - 当前价格状态为normal（未达异常标准），SKU零售价为$69.97，高于品类零售价中位数（$59.99），价格分位为0.5152。
   - 当前数据仅支持说明：**价格未达到异常标准，暂不支持将价格定位异常作为主要解释因素**。不能据此排除价格对转化存在任何影响。

2. **购物车至购买环节的潜在原因（需更多数据验证）**：
   - 现有证据表明购物车至购买环节转化率显著低于品类基准，但**现有证据不足以确定因果原因**。可能涉及运费、税费、支付方式、库存状态、退换货政策、用户购买意愿等，但均未在当前数据中直接体现，需要补充数据验证。

五、外部行业参考

根据Dynamic Yield Fashion/Apparel 2025外部行业参考：
- 加购率（商品页浏览口径）：6.58%
- 购买转化率（访客口径）：3.03%
- 购物车完成率代理（派生）：21.87%
- 购物车放弃率：78.13%

注意：Dynamic Yield与TheLook统计口径不同，上述数值**仅作为行业背景参考**，不得进行直接高低比较，也不得通过Dynamic Yield数值推算TheLook指标。

六、下一步需要补充的数据

1. **购物车至购买环节的行为数据**：
   - 用户进入购物车后的放弃原因（如运费、税费、支付方式、库存等）。
   - 购物车页面停留时间、退出页面位置。
   - 是否使用优惠券或促销码。

2. **商品页面数据**：
   - 商品详情页跳出率、浏览量分布。
   - 用户评价数量及评分、尺码/颜色选择行为。

3. **流量来源数据**：
   - 各渠道（自然搜索、广告、社交媒体等）的流量占比及对应转化率，验证是否存在渠道质量差异。

4. **竞品或同类商品对比数据**：
   - 同品类中价格相近商品的转化表现，用于进一步区分价格影响。

当前数据直接支持的建议：重点优化购物车至购买环节的转化体验，如简化结账流程、明确运费及退换货政策、提供多种支付方式等（需通过行为数据验证具体方向）。同时，现有证据不足以确定因果原因，建议补充上述数据后再做深度归因。


======================================================================
TEST CASE: low
PRODUCT ID: 4680
======================================================================

========== Conversion Metrics ==========
product_id: 4680
category: Jeans
product_sessions: 20
purchase_cvr: 15.00%
category_cvr: 26.68%

========== Anomaly Detection ==========
status: low
deviation: -0.4378

Anomaly Router: low

========== Funnel Analysis ==========
Product→Cart deviation: -13.13%
Cart→Purchase deviation: -35.28%
weak_stage: cart_to_purchase

========== Price Analysis ==========
sku_price: 189.0
category_median: 78.0
percentile: 91.25%
price_status: high

========== Industry Benchmark ==========
Dynamic Yield Fashion/Apparel 2025外部行业参考：加购率（商品页浏览口径）: 6.58%；购买转化率（访客口径）: 3.03%；购物车完成率代理（派生）: 21.87%；购物车放弃率: 78.13%。注意：与TheLook统计口径不同，不可直接用于异常阈值判断。

========== Report ==========

========== Test Result ==========
Expected: low
Actual: low
PASS:
True

Final Report:
一、诊断结论

本品（MiH Jeans Women's Marrakesh Jean）整体购买转化率（CVR）为15.00%，相对品类基准（26.68%）偏离-43.78%，触发**low**异常。主要异常漏斗环节为**购物车至支付（Cart→Purchase）**：该环节SKU转化率为27.27%，显著低于品类基准（42.14%），相对偏离-35.28%。现有证据表明，转化瓶颈集中在顾客已将商品加入购物车后、但未完成购买的环节。

二、已知事实

- **样本量**：Product Sessions为20，已达到当前项目最低样本量门槛，本次诊断有效。
- **价格数据**：SKU零售价/标价为189.0美元，品类零售价中位数为78.0美元，价格分位为0.912，价格状态判定为**high**，即该商品定价处于品类较高水平。
- **Product→Cart（加购环节）**：SKU加购率为55.00%，品类基准为63.31%，相对偏离-13.13%。该环节未触发异常判定标准（Product→Cart偏离未达异常阈值）。
- **Cart→Purchase（购物车至支付环节）**：SKU转化率为27.27%，品类基准为42.14%，相对偏离-35.28%，为本品主要弱环节。
- **整体CVR**：SKU为15.00%，品类基准为26.68%，相对偏离-43.78%。

三、漏斗异常定位

1. **整体层面**：Product→Cart偏离为-13.13%，未达异常标准，因此加购环节暂未发现明显异常；但不能据此判断商品图片、标题或描述没有问题，仅表示数据未支持该环节成为主要短板。
2. **核心瓶颈**：Cart→Purchase环节的相对偏离为-35.28%，是漏斗中异常主要集中位置。即当用户将商品加入购物车后，从购物车到完成购买的转化效率明显弱于品类正常水平。
3. **需要区分**：上述-35.28%为“相对偏离”（SKU Cart→Purchase Rate 27.27% 对比 Category Benchmark 42.14% 的相对差距），并非“35.28%的用户流失”。数据不支持也无权推断具体用户流失比例。

四、可能影响因素

- **价格因素（仅作为可能影响因素之一）**：SKU零售价/标价（189.0美元）显著高于品类中位数（78.0美元），价格分位达0.912。价格偏高是可能影响因素之一，但现有数据不支持“价格直接导致转化下降”的因果结论。
- **购物车阶段体验或支付阻力**：购物车至支付环节转化偏低，可能与运费、税费、支付方式、库存变化、用户比价行为、或商品在购物车中的最终结算价格有关。但当前数据无法区分具体是哪种机制。
- **现有证据不足以确定因果原因**：目前仅能确认“购物车至支付环节表现弱于品类基准”，无法确定是价格、支付流程、促销缺失或其他因素所致。

五、外部行业参考

Dynamic Yield Fashion/Apparel 2025外部行业参考显示：加购率（商品页浏览口径）6.58%，购买转化率（访客口径）3.03%，购物车完成率（派生）21.87%，购物车放弃率78.13%。
**注意**：该外部口径与TheLook统计口径不同，不可直接进行高低比较，也不可通过Dynamic Yield数值推算TheLook指标，仅供行业背景参考。

六、下一步需要补充的数据

以下为需要更多数据验证的假设，而非当前数据直接支持的结论：

1. **价格敏感度测试数据**：如需验证价格是否为购物车转化瓶颈的关键因素，可补充同品类不同价位段商品的Cart→Purchase表现，或开展A/B价格测试。当前数据无法证实价格因素的具体影响权重。
2. **购物车放弃原因数据**：建议补充购物车放弃原因调研、支付失败率、运费试算后放弃率、或用户离开购物车后的去向（是否转向竞品/收藏/等待降价）等行为数据。
3. **商品详情页行为数据**：虽然加购环节未触发异常，但如需排除详情页问题，可补充商品页内的图片点击热力图、视频播放完成率、尺寸/材质信息查询频率等数据，用于后续验证。
4. **竞争环境数据**：可补充同价位竞品的购物车完成率或促销策略（如免邮门槛、折扣码），以判断本品在结算阶段是否存在竞争劣势。
5. **复购与评价数据**：如有历史订单或评价数据，可分析已购用户的评价关键词（如版型、质量），辅助判断商品与价格是否匹配。当前数据未覆盖该维度。


======================================================================
TEST CASE: normal
PRODUCT ID: 19681
======================================================================

========== Conversion Metrics ==========
product_id: 19681
category: Sweaters
product_sessions: 31
purchase_cvr: 25.81%
category_cvr: 26.38%

========== Anomaly Detection ==========
status: normal
deviation: -0.0218

Anomaly Router: normal

========== Report ==========

========== Test Result ==========
Expected: normal
Actual: normal
PASS:
True

Final Report:
一、诊断结论

根据当前已计算完成的数据，该商品整体CVR未触发异常：SKU Product→Purchase CVR为25.81%，Category CVR为26.38%，相对偏离-2.18%。由于整体转化率未达到异常标准，本次未执行深度漏斗诊断，也未对具体弱环节进行定位。

当前证据表明该商品转化表现与品类基准基本持平，整体未出现明显异常信号。

二、已知事实

- Product Sessions：31，已达到当前项目最低样本量门槛（≥20）。
- SKU Product→Cart Rate：70.97%；Category Product→Cart Rate：62.93%。SKU该阶段转化率高于品类基准8.04个百分点。
- SKU Product→Purchase CVR：25.81%；Category CVR：26.38%。相对偏离约-2.18%，即百分点差约-0.57个百分点。
- SKU Cart→Purchase Rate：36.36%；Category Cart→Purchase Rate：41.93%。SKU该阶段转化率低于品类基准5.57个百分点。
- 异常状态：normal。
- 主要弱环节：未执行。
- 价格状态：未执行（本次流程未执行价格分析）。

三、漏斗异常定位

整体异常状态为normal，因此本次不执行深度漏斗诊断，也不对Product→Cart或Cart→Purchase阶段进行异常定性。

可展示的各阶段原始指标及品类基准如下：

- Product→Cart：SKU为70.97%，Category Benchmark为62.93%，SKU阶段表现高于品类基准。
- Cart→Purchase：SKU为36.36%，Category Benchmark为41.93%，SKU阶段表现低于品类基准，相对偏离未达异常阈值。
- 整体Product→Purchase：SKU为25.81%，Category CVR为26.38%，相对偏离-2.18%，未触发异常。

四、可能影响因素

- Product→Cart阶段暂未发现明显异常；但需注意，该结论仅基于漏斗数据，不能据此判断图片、标题、商品描述没有问题。
- 整体CVR未触发异常，因此不定位具体弱环节，也不推断具体影响因素。
- 价格分析本次流程未执行，无法对价格因素进行判断。

现有证据不足以确定因果原因。当前数据仅支持“整体转化表现与品类基准基本一致”这一结论。

五、外部行业参考

外部行业参考未调用。本次未参考Dynamic Yield或TheLook等外部数据。按照口径要求，即使后续引入外部行业参考，也仅作为行业背景使用，不与当前数据进行直接数值比较。

六、下一步需要补充的数据

- 当前Product Sessions为31，已满足最低样本量门槛，无需等待更多流量即可维持当前判断。
- 若希望进一步排查Cart→Purchase阶段略低于品类基准的原因，可补充以下数据：
  - 购物车放弃原因（如运费、支付方式、登录要求等）；
  - 用户从加购到下单的时间间隔及流失节点；
  - 商品评价、尺码反馈、库存状态等信息；
  - 价格分析尚未执行，如需评估价格影响，可补充该商品的零售价/标价及所在品类的价格分布数据。
- 以上补充数据属于“需要更多数据验证的假设”，当前数据不足以确认Cart→Purchase阶段低5.57个百分点是否构成实际问题。


======================================================================
TEST CASE: insufficient_data
PRODUCT ID: 16599
======================================================================

========== Conversion Metrics ==========
product_id: 16599
category: Tops & Tees
product_sessions: 19
purchase_cvr: 21.05%
category_cvr: 26.93%

========== Anomaly Detection ==========
status: insufficient_data
deviation: None

Anomaly Router: insufficient_data

========== Report ==========

========== Test Result ==========
Expected: insufficient_data
Actual: insufficient_data
PASS:
True

Final Report:
一、诊断结论

当前商品 **IZOD Men's Slim Fit Long Sleeve Mini Check Button Down Shirt (ID: 16599)** 的 Product Sessions 为 **19**，未达到本项目最低样本量门槛（20）。根据规则，**样本不足，本次无法执行可靠的转化率诊断**。当前各项转化指标仅作展示，不做高低或正常与否的判断，也不定位异常漏斗阶段。

二、已知事实

- **商品**：IZOD Men's Slim Fit Long Sleeve Mini Check Button Down Shirt
- **Product ID**：16599
- **品类**：Tops & Tees
- **Product Sessions**：19（< 20，未达最低样本量）
- **SKU Product→Cart Rate**：63.16%
- **Category Product→Cart Rate**：63.50%
- **SKU Product→Purchase CVR**：21.05%
- **Category CVR**：26.93%
- **SKU Cart→Purchase Rate**：33.33%
- **Category Cart→Purchase Rate**：42.40%

三、漏斗异常定位

**未执行。**
由于 Product Sessions 未达到最低样本量20，本次不执行漏斗异常定位。现有证据不足以判断 Product→Cart 或 Cart→Purchase 阶段是否存在异常。

四、可能影响因素

**未执行。**
本次流程未执行价格分析，未执行外部行业参考调用。现有证据不足以确定因果原因。本次不分析价格、漏斗原因或其他潜在因素。

五、外部行业参考

**未调用。**
本次流程未执行该分析。

六、下一步需要补充的数据

- **Product Sessions 达到至少20后重新诊断。** 在达到最低样本量门槛前，不进行结论性判断。
- 重新诊断时，需同时获取并确认以下数据：
  - SKU Product→Cart Rate 及 Category Benchmark
  - SKU Product→Purchase CVR 及 Category CVR
  - SKU Cart→Purchase Rate 及 Category Benchmark
  - SKU 零售价（retail_price）及 Category 零售价中位数（当前未提供）
  - 外部行业参考数据（如需调用，需明确来源与口径，仅作背景参考，不与 TheLook 指标直接比较）
'''






"output4"
#新增第25-27条prompt

'''
========== Test Cases ==========
severe → product_id: 7498
low → product_id: 4680
normal → product_id: 19681
insufficient_data → product_id: 16599


======================================================================
TEST CASE: severe
PRODUCT ID: 7498
======================================================================

========== Conversion Metrics ==========
product_id: 7498
category: Blazers & Jackets
product_sessions: 23
purchase_cvr: 13.04%
category_cvr: 26.57%

========== Anomaly Detection ==========
status: severe
deviation: -0.5091

Anomaly Router: severe

========== Funnel Analysis ==========
Product→Cart deviation: -25.00%
Cart→Purchase deviation: -34.54%
weak_stage: cart_to_purchase

========== Price Analysis ==========
sku_price: 69.97000122070312
category_median: 59.9900016784668
percentile: 51.52%
price_status: normal

========== Industry Benchmark ==========
Dynamic Yield Fashion/Apparel 2025外部行业参考：加购率（商品页浏览口径）: 6.58%；购买转化率（访客口径）: 3.03%；购物车完成率代理（派生）: 21.87%；购物车放弃率: 78.13%。注意：与TheLook统计口径不同，不可直接用于异常阈值判断。

========== Report ==========

========== Test Result ==========
Expected: severe
Actual: severe
PASS:
True

Final Report:
# 电商转化率诊断报告

**商品名称**：Anne Klein Women's Petite Tweed Jacket
**Product ID**：7498
**Category**：Blazers & Jackets
**诊断日期**：基于当前可用数据


## 一、诊断结论

该SKU整体转化率（Product→Purchase CVR）为 **13.04%**，品类基准为 **26.57%**，相对偏离 **-50.91%**，异常状态为 **severe（严重）**。

当前数据表明该商品转化漏斗存在严重异常，主要薄弱环节集中在 **购物车至支付（Cart→Purchase）** 阶段。


## 二、已知事实

| 漏斗指标 | SKU | Category Benchmark | 相对偏离 |
|---------|-----|-------------------|---------|
| Product→Cart Rate | 47.83% | 63.77% | -25.00% |
| Product→Purchase CVR | 13.04% | 26.57% | -50.91% |
| Cart→Purchase Rate | 27.27% | 41.66% | -34.54% |

**价格数据**：SKU零售价为 **$69.97**，品类零售价中位数为 **$59.99**，价格分位 **0.515**（处于品类价格分布中位偏上位置），价格状态判定为 **normal**。

**样本情况**：Product Sessions = **23**，已达到当前项目最低样本量门槛（≥20）。


## 三、漏斗异常定位

**主要异常阶段：Cart→Purchase（购物车至支付）**

具体表现如下：

- **Product→Cart阶段**：SKU加购率为 **47.83%**，品类基准为 **63.77%**，相对偏离 **-25.00%**。该阶段存在一定程度偏离，但未达到主要异常环节的判定标准。根据规则，该阶段仅说明存在偏离，暂不能据此判断商品页图片、标题、描述等要素存在问题。
- **Cart→Purchase阶段**：SKU购物车完成支付率为 **27.27%**，品类基准为 **41.66%**，相对偏离 **-34.54%**。该阶段为漏斗中偏离最大的环节，是当前异常的主要集中位置。

以上使用的偏离均为相对偏离比例（相对品类基准的百分比变化），不代表实际用户流失比例。


## 四、可能影响因素

### 1. 当前数据直接支持的因素

- **购物车至支付环节转化效率偏低**：SKU Cart→Purchase Rate为 **27.27%**，显著低于品类基准 **41.66%**，相对偏离 **-34.54%**。当前证据表明，已加购用户完成支付的比例明显偏低，问题集中在用户加购之后到完成支付之间的环节。
- **价格因素定位**：当前价格状态为 **normal**（价格分位0.515），当前价格数据暂不支持将价格定位异常作为该商品转化不佳的主要解释因素。但需注意，这并不代表价格因素已被排除或确认不影响转化，只是现有价格数据未达到异常判定标准。

### 2. 需要更多数据验证的假设

以下可能性需要进一步数据验证，当前数据不足以确认其是否为因果原因：

- **结算流程体验问题**：是否在结算页、支付环节存在额外阻力（如运费过高、支付方式缺失、结算流程复杂等），需要结合用户行为数据或页面分析验证。
- **竞争性比价行为**：用户加购后可能在竞品处找到更优价格或替代品，导致放弃支付，需要竞品价格跟踪数据验证。
- **库存或配送信息影响**：加购后是否因尺码、配送时效、库存状态等因素犹豫，需要结合商品详情页及结算页行为数据验证。

**重点提示**：现有证据足以确定Cart→Purchase阶段存在显著转化短板，但不足以确定导致该短板的因果原因。要定位具体原因，建议优先针对加购后未支付用户展开行为追踪和调研。


## 五、外部行业参考

Dynamic Yield Fashion/Apparel 2025外部行业参考数据如下：

- 加购率（商品页浏览口径）：6.58%
- 购买转化率（访客口径）：3.03%
- 购物车完成率代理（派生）：21.87%
- 购物车放弃率：78.13%

**重要声明**：上述数据与TheLook统计口径不同，仅作为行业背景参考，不用于直接高低比较，也不可通过该数据推算TheLook指标。该参考数据不用于本报告的异常阈值判断。


## 六、下一步需要补充的数据

基于当前诊断结果，为定位Cart→Purchase阶段的具体原因，建议补充以下数据（需注意：这些数据是用于进一步归因分析，并非判断当前结果有效性所必需）：

1. **加购后未支付用户的退出页面**：确认用户停留在结算流程的哪个环节退出。
2. **运费与税费展示信息**：结算时是否因额外费用导致放弃支付。
3. **竞品同款/相似款价格对比**：验证是否存在价格竞争劣势。
4. **商品评价与信任信号数据**：确认是否存在质量顾虑影响支付决策。
5. **库存与配送信息**：尺码不全、配送时间过长是否导致放弃购买。
6. **用户画像与复购行为数据**：新客/老客的转化差异，是否某些客群支付意愿低。
7. **营销渠道数据**：不同来源访客的加购后支付率是否存在显著差异。

> 以上数据为可选的进一步分析方向，当前诊断结论基于现有数据已经成立。


======================================================================
TEST CASE: low
PRODUCT ID: 4680
======================================================================

========== Conversion Metrics ==========
product_id: 4680
category: Jeans
product_sessions: 20
purchase_cvr: 15.00%
category_cvr: 26.68%

========== Anomaly Detection ==========
status: low
deviation: -0.4378

Anomaly Router: low

========== Funnel Analysis ==========
Product→Cart deviation: -13.13%
Cart→Purchase deviation: -35.28%
weak_stage: cart_to_purchase

========== Price Analysis ==========
sku_price: 189.0
category_median: 78.0
percentile: 91.25%
price_status: high

========== Industry Benchmark ==========
Dynamic Yield Fashion/Apparel 2025外部行业参考：加购率（商品页浏览口径）: 6.58%；购买转化率（访客口径）: 3.03%；购物车完成率代理（派生）: 21.87%；购物车放弃率: 78.13%。注意：与TheLook统计口径不同，不可直接用于异常阈值判断。

========== Report ==========

========== Test Result ==========
Expected: low
Actual: low
PASS:
True

Final Report:
一、诊断结论

SKU **MiH Jeans Women's Marrakesh Jean**（Product ID：4680）整体购买转化率（CVR）为15.00%，品类基准为26.68%，相对偏离**-43.78%**，判定为**low（偏低）**异常。

主要异常漏斗阶段为**购物车→下单（cart_to_purchase）**，该环节表现明显低于品类基准，是拖累整体转化的核心环节。

当前样本量（Product Sessions = 20）已达到项目最低样本量门槛，本诊断结论基于现有数据有效。

---

二、已知事实

| 指标 | SKU | Category Benchmark |
|---|---|---|
| Product Sessions | 20 | — |
| Product→Cart Rate | 55.00% | 63.31% |
| Cart→Purchase Rate | 27.27% | 42.14% |
| Product→Purchase CVR | 15.00% | 26.68% |
| 零售价/标价 | $189.0 | 中位数 $78.0 |
| 价格分位 | 0.912（即高于约91%的品类SKU） | — |

---

三、漏斗异常定位

1. **Product→Cart 环节**：SKU加购率55.00%，Category Benchmark为63.31%，相对偏离**-13.13%**。该环节尚未达到异常判定标准，本次诊断暂未发现明显异常。
2. **Cart→Purchase 环节**：SKU购物车→下单转化率为27.27%，Category Benchmark为42.14%，相对偏离**-35.28%**。该环节为本次诊断的**主要弱环节**，显著低于品类基准。
3. 以上偏离均为“相对偏离比例”，例如Cart→Purchase相对偏离-35.28%表示SKU该环节转化率较品类基准低35.28%，并非用户流失比例。

---

四、可能影响因素

1. **价格因素**：当前SKU零售价/标价为$189.0，品类中位数为$78.0，价格分位处于0.912（高价区间），价格状态判定为**high**。**价格偏高是可能影响因素之一**，但现有证据不足以确定价格与转化偏低之间存在因果关联，不构成唯一解释。
2. **购物车环节转化阻力**：SKU加购后最终完成下单的比例（27.27%）显著低于品类基准（42.14%），表明用户加购后犹豫或放弃的可能性较大，但现有数据无法确认具体原因（如运费、税费、竞品比价、支付便利性等）。

---

五、外部行业参考

Dynamic Yield Fashion/Apparel 2025外部行业参考显示：加购率6.58%，购买转化率（访客口径）3.03%，购物车完成率21.87%，购物车放弃率78.13%。

该数据与TheLook口径不同，**不可直接用于高低比较**，仅作为行业背景参考。例如，Dynamic Yield的购物车完成率为21.87%，而当前SKU购物车→下单率为27.27%，两者口径存在差异，不构成直接可比关系。

---

六、下一步需要补充的数据

**当前数据直接支持的补充项：**

1. **竞品/同品类同价位段对比**：补充与当前SKU价格区间相近（如$150-$200）的品类SKU的CVR和Cart→Purchase Rate，以进一步验证高价位是否对该环节构成普遍性压力。
2. **SKU维度历史趋势**：补充该SKU近30-90天的日/周维度CVR、加购率、购物车→下单率走势，判断当前表现是短期波动还是持续偏低。

**需要更多数据验证的假设：**

3. **用户行为数据**：补充该SKU购物车放弃原因（如运费门槛、库存变化、支付失败等）或用户调研数据，用于验证购物车环节转化偏低的具体诱因。
4. **价格弹性测试数据**：如有条件，补充该SKU在促销价或折扣场景下的转化数据，用于判断价格敏感度。

**注意：** 现有证据不足以确定购物车→下单环节偏低的因果原因，以上补充项仅为验证假设所需，不代表当前数据缺失。


======================================================================
TEST CASE: normal
PRODUCT ID: 19681
======================================================================

========== Conversion Metrics ==========
product_id: 19681
category: Sweaters
product_sessions: 31
purchase_cvr: 25.81%
category_cvr: 26.38%

========== Anomaly Detection ==========
status: normal
deviation: -0.0218

Anomaly Router: normal

========== Report ==========

========== Test Result ==========
Expected: normal
Actual: normal
PASS:
True

Final Report:
一、诊断结论

本商品 **Fred Perry Men's Vintage Marl Crew Neck Sweater**（Product ID: 19681）整体转化率未触发异常（anomaly_status = normal）。SKU Product→Purchase CVR为25.81%，Category Benchmark为26.38%，CVR相对偏离仅为-2.18%，SKU表现与品类基准基本持平，差异幅度很小。当前无证据支持该商品存在需要优先干预的转化漏斗异常。**整体CVR未触发异常，因此本次未执行深度诊断。**

二、已知事实

| 指标 | SKU | Category Benchmark | 相对偏离（CVR Deviation） |
|---|---|---|---|
| Product Sessions | 31 | — | — |
| Product→Cart Rate | 70.97% | 62.93% | — |
| Product→Purchase CVR | 25.81% | 26.38% | **-2.18%** |
| Cart→Purchase Rate | 36.36% | 41.93% | — |

说明：

- SKU Product→Purchase CVR（25.81%）较Category CVR（26.38%）低约0.57个百分点，相对偏离约-2.18%。
- Product Sessions为31次，已达到当前项目最低样本量门槛（≥20），本次诊断基于有效样本量进行。

三、漏斗异常定位

**不适用。** 因整体CVR未触发异常（anomaly_status = normal），且funnel_analysis节点本次未执行，因此本次流程不定义具体弱环节，也不对Product→Cart、Cart→Purchase子阶段进行异常判定。本次仅展示上述原始漏斗Rate供参考，不做深度诊断。

四、可能影响因素

- 本次流程未执行funnel_analysis，因此无法基于子漏斗数据定位主要异常环节。
- 本次流程未执行price_analysis，因此无法确认当前SKU零售价/标价在品类中的相对位置，不推断价格状态。
- 现有证据不足以确定因果原因。

五、外部行业参考

本次流程未调用外部行业参考数据。Dynamic Yield与TheLook口径不同，仅可作为行业背景参考，不得直接进行高低比较，也不得通过任一平台数值推算另一平台指标。当前报告不引用外部行业数据。

六、下一步需要补充的数据

鉴于当前整体CVR未触发异常，且funnel_analysis与price_analysis均未执行，若后续希望进一步排查潜在优化空间，建议在下次诊断时：

1. **执行funnel_analysis**：当前SKU Product→Cart Rate与Cart→Purchase Rate原始数据已存在，但该分析节点本次未调用，需在下次诊断流程中启用，以便定位是否存在靠近漏斗上层或下层的相对薄弱环节。
2. **执行price_analysis**：需获取SKU零售价/标价及Category零售价中位数、价格分位数据，以便评估价格位置是否构成潜在影响因素之一。
3. **保持或扩大Product Sessions**：当前31次Session已满足最低样本量门槛，但若后续需要更稳健的子阶段对比，可在流量自然积累后重新运行诊断。

注意：上述补充项为可选优化分析，并非本次诊断判定为异常所需的必要条件。


======================================================================
TEST CASE: insufficient_data
PRODUCT ID: 16599
======================================================================

========== Conversion Metrics ==========
product_id: 16599
category: Tops & Tees
product_sessions: 19
purchase_cvr: 21.05%
category_cvr: 26.93%

========== Anomaly Detection ==========
status: insufficient_data
deviation: None

Anomaly Router: insufficient_data

========== Report ==========

========== Test Result ==========
Expected: insufficient_data
Actual: insufficient_data
PASS:
True

Final Report:
# IZOD Men's Slim Fit Long Sleeve Mini Check Button Down Shirt — 电商转化率诊断报告

**Product ID:** 16599
**Category:** Tops & Tees
**诊断时间:** 基于当前数据快照


## 一、诊断结论

**当前状态：样本不足（insufficient_data），无法执行有效诊断。**

该SKU的Product Sessions仅为19，未达到当前项目最低样本量门槛20。在样本量达标之前，任何针对转化漏斗、价格定位或异常环节的判断均不具备可靠性，本次不予执行。

根据规则，本报告仅陈述已观测到的原始数据，不对其高低、正常与否、异常程度或潜在原因做出任何推断。


## 二、已知事实

### 2.1 流量与样本概况

| 指标 | 数值 |
|------|------|
| Product Sessions | 19 |
| 样本量状态 | 未达到最低门槛（< 20） |

### 2.2 原始转化漏斗指标（仅展示，不做判断）

| 漏斗阶段 | SKU原始指标 | Category Benchmark |
|----------|------------|-------------------|
| Product→Cart Rate | 63.16% | 63.50% |
| Product→Purchase CVR | 21.05% | 26.93% |
| Cart→Purchase Rate | 33.33% | 42.40% |

> 注：以上数据仅为当前快照的原始观测值，鉴于样本量不足，本次不判断其高低、正常与否或是否达到异常阈值。


## 三、漏斗异常定位

**本次流程未执行漏斗异常定位分析。**

原因：当前 anomaly_status = insufficient_data，Product Sessions（19）未达到最低样本量要求（≥20）。基于规则，不对任何子阶段进行强弱判断，不定位weak_stage，不计算或解释CVR deviation。

> 说明：funnel_analysis本次未执行，因此“主要弱环节”不可判定，任何关于“哪个环节最弱”的结论均不在本报告范围内。


## 四、可能影响因素

**本次不进行影响因素分析。**

当前样本量不足以支撑任何关于价格、商品详情、图片、评价或竞争环境的因果推断。现有证据不足以确定任何因果原因。

- **价格分析：** 本次流程未执行该分析（price_analysis未执行），不得推断价格状态。SKU零售价及Category零售价中位数等字段均为空值，且该分析节点未被调用，因此无法也不得对价格因素做出任何判断。
- **漏斗分析：** 由于样本量不足，漏斗分析未执行，不得根据原始Rate自行模拟判断逻辑。


## 五、外部行业参考

**本次流程未调用外部行业参考。**

根据规则，外部行业参考（如Dynamic Yield等）仅作为行业背景参考，不用于直接比较或推算。本次未调用该数据源，因此本报告不包含任何外部基准信息。


## 六、下一步需要补充的数据

| 优先序 | 所需条件 | 说明 |
|--------|---------|------|
| **唯一必要条件** | **Product Sessions ≥ 20** | 这是当前唯一需要满足的条件。达到后重新运行诊断，即可执行完整的漏斗异常定位、CVR偏离分析及价格诊断。 |

**重要说明：** 当前系统已具备该SKU的会话、转化、购物车及品类基准数据，唯一不足是访问量未达最低门槛。因此，不需要补充当前系统尚未调用的其他数据字段。

> 当Product Sessions达到至少20后，请重新运行诊断流程。


**免责声明：** 本报告中所有转化率值均为原始观测数据，仅作客观呈现。在样本量达标之前，任何关于该SKU表现优劣的结论均不具有可靠性，请勿基于当前数据做出运营决策。
'''
