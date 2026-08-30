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
请严格根据以下已经计算完成的 State 数据生成诊断报告。

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


必须遵守以下规则：

【1. 数据边界】
- 只能使用 State 中明确存在的数据和分析结果。
- 不得创造输入中不存在的数据。
- Tool / Node 未执行，不等于原始数据不存在。
- 未执行的分析必须表述为“本次流程未执行该分析”，不得写成“没有该数据”。
- 不得自行计算 p值、置信区间、统计显著性、推荐样本量或其他未提供的统计结论。


【2. 样本量规则】
- Product Sessions < 20：
  anomaly_status 应视为 insufficient_data。
  只展示原始指标，不判断高低、正常、异常，不定位 weak_stage，不分析价格或原因。
  下一步唯一必要条件是 Product Sessions 达到至少20后重新运行诊断。
  达标后重新判断异常状态，再由 Router 决定是否继续深度分析。
- Product Sessions >= 20：
  仅表示通过当前项目最低诊断样本量门槛，不得表述为统计显著或统计稳定。


【3. 异常状态规则】
- anomaly_status = normal：
  明确说明整体CVR未触发异常，本次不执行深度诊断。
  可以展示原始漏斗Rate及Category Benchmark，但不得自行给子阶段定义 low、weak、abnormal，也不得模拟 funnel_analysis。
- anomaly_status = low / severe：
  可以根据 State 中已有的 weak_stage、deviation 等结果说明主要异常漏斗阶段。
- funnel_analysis 未执行时，不得使用“弱环节”“达到异常阈值”“暂未发现异常”等子漏斗诊断性表述。


【4. 指标语义规则】
- 必须严格区分：
  转化率、相对偏离、百分点差、用户流失率。
- xxx_deviation 表示：
  (SKU指标 - Category Benchmark) / Category Benchmark
  是相对偏离比例，不代表用户流失比例。
- 不得把 deviation 改写成“X%的用户流失”。
- 若描述百分点差，必须使用两个Rate直接相减。
- 不得使用“显著”“统计显著”等措辞，除非输入中明确提供统计检验结果。
  优先使用“明显低于”“达到当前异常阈值”。


【5. 漏斗解释规则】
- weak_stage 只代表当前异常主要集中在哪个漏斗阶段。
- 如果 Product→Cart 未达到异常标准，只能说明该阶段未被当前规则识别为主要异常阶段。
  不得据此判断图片、标题、描述没有问题。
- 不得根据漏斗Rate自行推断用户心理或行为原因，例如：
  “用户犹豫”“购买意愿下降”。
  只能描述实际转化比例及其与Benchmark的差异。


【6. 价格解释规则】
- 当前价格字段为 retail_price，只能称为“零售价/标价”，不得称为成交价。
- price_status = high：
  只能说“价格偏高是可能影响因素之一”，不得说价格导致转化下降。
- price_status = normal：
  只能说明价格位置未达到当前价格异常标准。
  不得表述为“价格因素已排除”或“价格不会影响转化”。
- price_analysis 未执行时，不得推断价格状态。


【7. 外部Benchmark规则】
- Dynamic Yield 与 TheLook 统计口径不同。
- 只能作为行业背景参考。
- 不得直接进行高低比较。
- 不得通过 Dynamic Yield 数值推算 TheLook 指标。
- 不得用 Dynamic Yield 参与 low / severe 异常阈值判断。


【8. 因果与建议规则】
- 事实、规则判断、假设必须分开表达。
- 现有数据无法确认具体原因时，必须明确写：
  “现有证据不足以确定因果原因。”
- 建议分为：
  1）当前数据直接支持的排查方向；
  2）需要更多数据验证的假设。
- 不得把“异常阶段已定位”直接写成“具体原因已确定”。


报告结构：

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
#prompt重构后，失败案例，测试4个case导致串规则

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

该商品（Anne Klein Women's Petite Tweed Jacket, Product ID: 7498）本次诊断样本量为 23 次 Product Sessions，达到当前项目最低诊断样本量门槛（≥20），因此本次诊断结果有效。

商品整体购买转化率（Product→Purchase CVR）为 13.04%，与品类基准（Category CVR: 26.57%）相比，相对偏离为 -0.5091，即低于品类基准约 50.91%，异常状态被判定为 **severe（严重）**。整体转化漏斗存在明显异常，本次执行深度诊断。

主要异常集中在 **购物车至购买（cart_to_purchase）** 阶段。需要说明的是，当前结论基于现有数据及规则判断，现有证据不足以确定因果原因，仅能定位异常发生的漏斗环节。

---

二、已知事实

| 指标（SKU） | 数值 |
|---|---|
| Product Sessions | 23 |
| SKU Product→Cart Rate | 47.83% |
| SKU Product→Purchase CVR | 13.04% |
| SKU Cart→Purchase Rate | 27.27% |
| SKU 零售价 | $69.97 |
| Category 零售价中位数 | $59.99 |
| 价格分位 | 0.515（处于品类价格分布的约第51.5百分位） |

| 品类基准（Benchmark） | 数值 |
|---|---|
| Category Product→Cart Rate | 63.77% |
| Category CVR | 26.57% |
| Category Cart→Purchase Rate | 41.66% |

| 偏离指标 | 数值 |
|---|---|
| Product→Cart 相对偏离（deviation） | -0.2500（即低于品类基准 25.00%） |
| Cart→Purchase 相对偏离（deviation） | -0.3454（即低于品类基准 34.54%） |
| 整体 CVR 相对偏离 | -0.5091（即低于品类基准 50.91%） |

| 价格状态 | 结论 |
|---|---|
| price_status | normal（价格位置未达到当前价格异常标准） |

注：以上相对偏离均为 (SKU指标 - Category Benchmark) / Category Benchmark 计算得出，表示与品类基准的**相对差距比例**，不代表用户流失比例。

---

三、漏斗异常定位

根据当前诊断规则，主要异常阶段为 **cart_to_purchase（购物车→购买）**。

具体数据表现如下：

- **Product→Cart 阶段**：SKU 加购率为 47.83%，品类基准为 63.77%，两者百分点差为 **-15.94 个百分点**，相对偏离为 **-25.00%**。
- **Cart→Purchase 阶段**：SKU 购物车完成购买率为 27.27%，品类基准为 41.66%，两者百分点差为 **-14.39 个百分点**，相对偏离为 **-34.54%**。

从偏离幅度来看，**Cart→Purchase 阶段的相对偏离（-34.54%）明显大于 Product→Cart 阶段的相对偏离（-25.00%）**，当前规则将异常主要归因于 cart_to_purchase 阶段。

需要强调的是：

- weak_stage 仅代表当前异常主要集中在哪个漏斗阶段，不代表另一个阶段没有问题。
- Product→Cart 阶段未达到当前异常识别标准，仅说明该阶段未被规则识别为主要异常环节，**不得据此判断商品图片、标题、详情页等不存在问题**。
- 现有数据仅反映各阶段实际转化比例与品类基准之间的差异，**不足以推断用户心理或行为原因**（如“用户犹豫”“购买意愿下降”等均属于推测，不得作为事实结论）。

---

四、可能影响因素

1. **价格因素**
   - 当前 SKU 零售价为 $69.97，品类零售价中位数为 $59.99，价格分位为 0.515，price_status 判定为 **normal**。
   - 根据规则，价格状态为 normal 仅代表该商品零售价位置未达到当前价格异常标准，**不得表述为“价格因素已排除”或“价格不会影响转化”**。价格对转化仍可能存在影响，只是当前规则未将其识别为异常因素。

2. **漏斗阶段因素**
   - Cart→Purchase 阶段（购物车完成购买率）相对偏离达到 -34.54%，是本次诊断的主要异常环节。
   - 该阶段对应的是用户将商品加入购物车后、实际完成购买之间的流失。
   - 现有证据无法确定该阶段转化偏低的具体原因，可能涉及结账流程、运费、支付选项、库存状态、竞争对手比价等多种因素，但当前数据**不足以支持任何具体归因**。

3. **本次流程未执行价格深度分析（price_analysis）**
   - 当前仅依据价格分位及 price_status 判断价格位置是否异常，未进行更深入的价格弹性或价格敏感度分析。

---

五、外部行业参考

Dynamic Yield Fashion/Apparel 2025 外部行业参考数据如下：

- 商品页浏览口径加购率：6.58%
- 访客口径购买转化率：3.03%
- 购物车完成率代理（派生）：21.87%
- 购物车放弃率：78.13%

**重要说明**：Dynamic Yield 数据与 TheLook 数据统计口径不同，不可直接用于高低比较，也不得通过 Dynamic Yield 数值推算 TheLook 指标。以上数据仅作为行业背景参考，**不参与本次异常状态的阈值判断**。

---

六、下一步需要补充的数据

基于当前诊断结果，建议补充以下数据以进一步定位 Cart→Purchase 阶段转化偏低的原因：

1. **结账流程数据**
   - 商品加入购物车后，用户到达结算页、填写收货信息、选择支付方式、最终提交订单等各步骤的转化/流失情况。

2. **购物车放弃原因数据**
   - 是否因运费过高、税费、优惠券不可用、库存变化、支付失败等原因放弃购买。

3. **同品类可比商品漏斗对比**
   - 选择同品类价格带相近的其他 SKU，对比其 Cart→Purchase Rate，以确认问题是否具有普遍性还是商品特有。

4. **用户行为数据**
   - 加入购物车至购买之间的平均时长、是否反复访问、是否与其他商品对比（如浏览了竞品页面）等。

5. **价格敏感度测试数据**
   - 当前价格状态为 normal，但如需进一步确认价格是否对转化产生影响，可考虑促销/折扣测试结果数据。

6. **商品详情页与评价数据**
   - 虽然 Product→Cart 阶段未被识别为主要异常环节，但不能排除该阶段存在潜在问题，若后续需要全面优化，可补充详情页点击分布、评价数量与评分等数据。

---

**总结**：

- 商品整体转化率（13.04%）明显低于品类基准（26.57%），严重偏离 -50.91%，判定为 severe 异常。
- 主要异常集中在 **购物车→购买** 阶段，该阶段转化率（27.27%）低于品类基准（41.66%）14.39 个百分点，相对偏离 -34.54%。
- 当前价格状态为 normal，仅代表价格未达到当前异常标准，不排除价格对转化存在间接影响。
- 现有数据仅支持异常阶段定位，**不足以确认具体因果原因**，需结合结账流程、放弃原因、同类对比等补充数据进行进一步排查。


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
# 电商转化率诊断报告

**商品名称**：MiH Jeans Women's Marrakesh Jean
**Product ID**：4680
**品类**：Jeans
**报告生成时间**：基于当前 State 数据


## 一、诊断结论

该商品（MiH Jeans Women's Marrakesh Jean）的 Product Sessions 为 20，已达到当前项目最低诊断样本量门槛（≥20），可进行异常状态判断。

**整体购买转化率（Product→Purchase CVR）为 15.00%**，品类基准为 26.68%，CVR 相对偏离为 **-0.4378**（即低于品类基准约 43.78%），当前异常状态判定为 **low**，整体转化率明显低于品类基准，触发异常关注。

**主要异常漏斗阶段：Cart→Purchase（购物车→购买）** 。该阶段转化率为 27.27%，品类基准为 42.14%，相对偏离为 -0.3528（低于基准约 35.28%），是当前异常的主要集中环节。

**需要特别说明的是：** 本次流程未执行 funnel_analysis 深度分析，以上关于主要异常阶段的判断严格基于 State 中已有的 weak_stage 及 deviation 结果。现有证据足以定位异常集中的漏斗阶段，但**不足以确定因果原因**。


## 二、已知事实

### 2.1 基础流量数据

| 指标 | 数值 |
|------|------|
| Product Sessions | 20 |
| SKU 零售价 | $189.00 |
| Category 零售价中位数 | $78.00 |
| 价格分位 | 0.912（即高于约 91.2% 的品类价格） |

### 2.2 漏斗转化率与品类基准对比

| 漏斗阶段 | SKU 转化率 | Category 基准 | 相对偏离 | 百分点差 |
|----------|-----------|--------------|---------|---------|
| Product→Cart | 55.00% | 63.31% | -13.13% | -8.31 pp |
| Cart→Purchase | 27.27% | 42.14% | -35.28% | -14.87 pp |
| Product→Purchase | 15.00% | 26.68% | -43.78% | -11.68 pp |

### 2.3 价格定位

该商品零售价为 $189.00，品类零售价中位数为 $78.00，价格分位为 0.912，price_status 判定为 **high**，即该商品在品类中处于高价格区间。


## 三、漏斗异常定位

### 3.1 主要异常阶段

根据 State 中已有的 weak_stage 判定结果，**Cart→Purchase（购物车→购买）** 是当前的主要异常环节。

- SKU Cart→Purchase 转化率为 **27.27%**，品类基准为 **42.14%**，相对偏离 **-0.3528**（低于品类基准约 35.28%），百分点差为 **-14.87 个百分点**。
- 该阶段偏离幅度明显大于 Product→Cart 阶段的偏离幅度（-13.13% vs -35.28%），是拖累整体转化率的主要环节。

### 3.2 非主要异常阶段说明

Product→Cart 阶段转化率为 55.00%，品类基准为 63.31%，相对偏离为 -0.1313（低于基准约 13.13%）。该阶段**未被当前规则识别为主要异常阶段**，但这只能说明该阶段未触发当前异常判定标准，**不得据此判断商品页图片、标题、描述等内容不存在问题**——现有数据无法对该阶段的用户行为原因做出任何归因判断。


## 四、可能影响因素

### 4.1 价格因素

该商品零售价为 **$189.00**，品类零售价中位数为 **$78.00**，价格处于品类约 **91.2%** 分位，price_status 判定为 **high**。

**价格偏高是可能影响因素之一**，但现有证据不足以确定价格与转化率下降之间存在因果关系。价格分位高仅说明该商品在品类中定位高端，是否以及如何影响用户在购物车阶段的完成决策，需要进一步数据验证。

### 4.2 漏斗阶段差异事实

- 用户从商品页到加购的流失比例：100% - 55.00% = 45.00%
- 用户从加购到购买的流失比例：100% - 27.27% = 72.73%

上述为实际用户流失比例，为直接根据转化率计算。相较之下，加购后的用户流失比例（72.73%）明显高于加购前的用户流失比例（45.00%），与该商品主要异常环节在 Cart→Purchase 阶段的定位一致。

### 4.3 原因边界声明

**现有证据不足以确定因果原因。** 当前数据仅能定位异常集中于 Cart→Purchase 阶段，但无法回答以下问题：

- 是价格因素导致用户放弃购买？
- 是运费、税费等额外成本因素？
- 是竞品比价行为？
- 是库存或尺码可用性问题？
- 是支付流程问题？

以上均属假设，需要更多数据验证。


## 五、外部行业参考

Dynamic Yield Fashion/Apparel 2025 行业参考数据：加购率（商品页浏览口径）6.58%，购买转化率（访客口径）3.03%，购物车完成率代理 21.87%，购物车放弃率 78.13%。

**重要说明：** Dynamic Yield 与 TheLook 统计口径不同，**不可直接进行数值高低比较**，也不得用于判断异常阈值。该组数据仅供行业背景参考。从购物车完成率代理（21.87%）来看，购物车阶段用户流失是该行业普遍面临的挑战，但其口径与 TheLook 不同，不能据此推断该 SKU 的 Cart→Purchase 表现是否偏离行业常态。


## 六、下一步需要补充的数据

### 6.1 当前数据直接支持的排查方向

以下方向基于现有诊断结果（Cart→Purchase 为主要异常阶段、价格为 high 状态）直接推导：

1. **购物车放弃原因调查**：优先针对“已加购但未完成购买”的用户进行流失原因追踪。可考虑退出问卷、Session 录制回放等方式。
2. **结算流程体验排查**：重点检查从加购到支付完成的整个结算链路，是否有技术障碍、额外费用不透明、支付方式缺失等问题。
3. **价格竞争力评估**：该商品零售价 $189.00 显著高于品类中位数 $78.00，建议与同价位段竞品的类似商品进行价格、价值主张、折扣策略对比。
4. **商品评价与信任信号核查**：高价位商品在购物车阶段对信任信号（评价数量与质量、品牌背书、退换货政策等）更敏感，建议核查该SKU的信任要素是否充分。

### 6.2 需要更多数据验证的假设

以下方向需要补充数据后才能验证，当前无法确认：

| 假设 | 所需数据 |
|------|---------|
| 价格是导致购物车放弃的主要原因 | 同价位段竞品转化率对比；用户价格敏感度调研 |
| 运费/税费等额外成本影响购买决策 | 结算页弃单数据；运费政策与竞品对比 |
| 用户加购后流失至竞品 | 用户行为追踪数据（如比价工具、竞品访问记录） |
| 库存或尺码可用性影响购买完成 | SKU 各尺码库存状态与购买失败记录 |
| 商品详情页信息未能充分支撑高价合理性 | 商品页内容质量评估、用户停留时长与热图分析、用户调研反馈 |

### 6.3 流程性建议

1. **持续监测样本量**：当前 Product Sessions 为 20，仅达到最低诊断门槛，不代表统计稳定。建议持续积累流量，待 Sessions 进一步增加后重新运行诊断，确认异常状态是否持续。
2. **优先优化购物车到购买的转化**：根据当前定位的主要异常环节，建议优先从结算流程和价格价值沟通两方面切入排查。
3. **定期复查**：在优化措施落地后，建议以固定周期重新运行诊断，评估 Cart→Purchase 偏离是否收窄。


## 附：报告中使用的关键指标定义

| 指标 | 定义 |
|------|------|
| Product→Cart Rate | 商品页浏览用户中加购的比例 |
| Cart→Purchase Rate | 加购用户中完成购买的比例 |
| Product→Purchase CVR | 商品页浏览用户中完成购买的比例（整体转化率） |
| xxx_deviation | (SKU指标 - Category Benchmark) / Category Benchmark，为相对偏离比例，不代表用户流失比例 |
| 百分点差 | 两个 Rate 直接相减，反映绝对差异 |

---

*本报告基于当前 State 数据分析生成。现有证据足以定位异常漏斗阶段和识别价格偏高这一可能影响因素，但不足以确定因果原因，具体归因需进一步数据支持。*


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

本次诊断判定 SKU **Fred Perry Men's Vintage Marl Crew Neck Sweater** 的当前转化状态为 **normal**，即整体CVR未触发当前异常规则，因此本次流程**不执行深度诊断**。

需说明：当前 Product Sessions 为 **31**，已达当前项目最低诊断样本量门槛（≥20），但该量级仅代表满足当前最小诊断要求，**不构成统计稳定或统计显著**。若后续希望得到更可靠判断，建议持续累积访问量后重新运行诊断。

## 二、已知事实

| 指标 | SKU | Category Benchmark |
|------|-----|---------------------|
| Product→Cart Rate | 70.97% | 62.93% |
| Cart→Purchase Rate | 36.36% | 41.93% |
| Product→Purchase CVR | 25.81% | 26.38% |
| Product Sessions | 31 | — |

- 若用两个Rate直接相减：SKU Product→Cart Rate 高于 Category 基准 **8.04个百分点**；SKU Cart→Purchase Rate 低于 Category 基准 **5.57个百分点**；SKU Product→Purchase CVR 低于 Category 基准 **0.57个百分点**。
- **整体CVR相对偏离为 -0.0218**，该值为 (SKU CVR − Category CVR) / Category CVR，表示相对偏离比例约 **-2.18%**，是相对比例而非用户流失比例。

## 三、漏斗异常定位

由于整体异常状态为 **normal**，且状态数据中 **funnel_analysis 未执行**，本次流程未对子漏斗阶段进行异常定位，无法识别主要弱环节。

需要特别区分：

- **Product→Cart Rate** 和 **Cart→Purchase Rate** 的偏离判断结果均为 **None**，表示当前规则未将任何子阶段识别为主要异常阶段。
- 该结果仅说明当前数据未触发子阶段异常判定阈值，**不能据此判断商品图片、标题、描述等方面不存在问题**。

本次流程中 **未执行子漏斗分析**，因此不得输出“弱环节”“达到异常阈值”等子漏斗诊断性表述。

## 四、可能影响因素

- **价格分析未执行**：State 中 price_status 为“未执行”，因此本次流程不推断价格因素状态，不判断价格是否对转化存在影响。
- **因果说明**：现有证据不足以确定影响转化的因果原因。本次仅确认整体CVR处于正常区间，且各子阶段未触发异常规则。

## 五、外部行业参考

外部行业参考未调用，本次不提供行业Benchmark对照。

## 六、下一步需要补充的数据

1. **交叉引用类数据**（假设验证方向，需要更多数据）：商品详情页停留时间、加购后未支付的时间分布、促销/折扣信息是否处于生效状态、是否有库存/尺码显示问题记录。
2. **访客结构化数据**：来源渠道（付费/自然/社媒）、设备类型（移动端/PC端）、访客地域，用于比较不同来源下的CVR差异。
3. **素材与体验数据**：商品主图、详情页截图、评价数量和评分，可在后续诊断中纳入分析。
4. **持续累积访问量**：建议在 Product Sessions 进一步增加后重新运行诊断，以提升当前判断的稳定性。
5. **如后续异常状态转为 low/severe**，可再执行价格分析和外部行业参考调用，定位更具体的漏斗异常阶段。
6. **现有数据直接支持的排查方向**：可优先检查 Cart→Purchase 环节中是否存在支付/结算流程层面的障碍（如运费不透明、支付方式有限等），因为该子阶段SKU与Category的百分点差（-5.57个百分点）虽然未触发异常阈值，但相对而言是当前漏斗中与基准差距最大的环节。


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
## 一、诊断结论

当前 SKU 的 Product Sessions 为 19，低于当前项目最低诊断样本量门槛（20），因此异常状态判定为 **insufficient_data**。本次流程不执行深度诊断，不做任何高低、正常或异常判断，不定位主要弱环节，不分析价格状态或外部行业数据。唯一结论是：**当前样本量不足以支撑可靠诊断，需要继续积累数据后重新运行诊断流程。**

**注意**：样本量达标仅表示通过当前项目最低诊断样本量门槛，不代表统计显著或统计稳定。

---

## 二、已知事实

以下数据为当前流程已生成的真实结果，全部来自本轮 State 的原始指标输出，不做任何方向性解读：

- **商品**：IZOD Men's Slim Fit Long Sleeve Mini Check Button Down Shirt
- **Product ID**：16599
- **Category**：Tops & Tees
- **Product Sessions**：19
- **SKU Product→Cart Rate**：63.16%（SKU 加入购物车转化率）
- **Category Product→Cart Rate**：63.50%（同 Category 加入购物车转化率的平均水平）
- **SKU Product→Purchase CVR**：21.05%（SKU 浏览到购买的最终转化率）
- **Category CVR**：26.93%（同 Category 浏览到购买的最终转化率平均水平）
- **SKU Cart→Purchase Rate**：33.33%（SKU 从加入购物车到完成购买的转化率）
- **Category Cart→Purchase Rate**：42.40%（同 Category 从加入购物车到完成购买的转化率平均水平）

**说明**：
- SKU Product→Cart Rate 与 Category 对应值相差 63.16% - 63.50% = **-0.34 个百分点**。
- SKU Cart→Purchase Rate 与 Category 对应值相差 33.33% - 42.40% = **-9.07 个百分点**。
- 上述仅为原始指标与基准之间的差异描述，不作为异常判断依据。

此外，本次流程中以下分析**未执行**，仅列出名称，不作任何推断：
- 转化率相对偏离分析（CVR 相对偏离 = None）
- 主要弱环节定位（weak_stage = 未执行）
- Product→Cart 偏离分析（Product→Cart 偏离 = None）
- Cart→Purchase 偏离分析（Cart→Purchase 偏离 = None）
- 价格分析（价格状态 = 未执行，SKU 零售价 = None，Category 零售价中位数 = None，价格分位 = None）
- 外部行业参考调用（= 未调用）

---

## 三、漏斗异常定位

由于 Product Sessions < 20，异常状态为 **insufficient_data**，漏斗分析未执行。

- 不定位 weak_stage；
- 不作任何子漏斗阶段（Product→Cart 或 Cart→Purchase）的 low / weak / abnormal 判断；
- 不使用“主要异常环节”“弱环节”等表述。

**唯一下一步**：待 Product Sessions 达到 **20** 后重新运行诊断，再由 Router 判断异常状态并决定是否继续深度分析。

---

## 四、可能影响因素

由于本次流程被判定为 insufficient_data，价格分析未执行，不进行任何价格状态推断；也不基于漏斗变化做用户行为归因。

**现有证据不足以确定因果原因。**

不提供关于价格、页面、描述或其他因素的任何假设性判断。

---

## 五、外部行业参考

本次流程**未调用外部行业参考**。因此不引入 Dynamic Yield 或其他外部 Benchmark 数据。

---

## 六、下一步需要补充的数据

为使诊断流程进入下一阶段，需满足以下条件：

1. **首要条件**：Product Sessions 达到 **20 或以上**，重新运行诊断。
2. 若达标后异常状态为 low / severe，应补充以下数据以支持深度诊断：
   - Product→Cart 偏离值（SKU Product→Cart Rate 相对 Category Benchmark 的偏离比例）；
   - Cart→Purchase 偏离值（SKU Cart→Purchase Rate 相对 Category Benchmark 的偏离比例）；
   - weak_stage 定位结果；
   - 价格分析结果（SKU 零售价、Category 零售价中位数、价格分位、价格状态）；
   - 可选：外部行业参考数据（如 Dynamic Yield），仅作行业背景使用，不参与异常阈值判断。
3. 若达标后异常状态为 normal，则按规则仅输出整体 CVR 未触发异常的结论，不开展子漏斗深度诊断。
'''
