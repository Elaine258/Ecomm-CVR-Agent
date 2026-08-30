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

EVENTS_PATH = os.path.join(
    DATA_DIR,
    "events_old.csv"
)

PRODUCTS_PATH = os.path.join(
    DATA_DIR,
    "products_old.csv"
)

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
    columns={
        "id": "product_id"
    }
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
        [
            "session_id",
            "product_id"
        ]
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
# 4. Node 1
# 获取SKU转化指标
# ==================================================

def conversion_metrics_node(
    state: DiagnosisState
):

    print(
        "\n========== Conversion Metrics =========="
    )

    product_id = state["product_id"]

    sku_data = session_products[
        session_products["product_id"]
        == product_id
    ]

    if sku_data.empty:

        raise ValueError(
            f"找不到 product_id={product_id}"
        )

    category = (
        sku_data["category"]
        .iloc[0]
    )

    product_name = (
        sku_data["name"]
        .iloc[0]
    )

    product_sessions_count = (
        sku_data[
            "session_id"
        ]
        .nunique()
    )

    cart_count = int(
        sku_data[
            "has_cart"
        ]
        .sum()
    )

    purchase_count = int(
        sku_data[
            "has_purchase"
        ]
        .sum()
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
        purchase_count
        / cart_count
        if cart_count > 0
        else 0.0
    )


    # =========================
    # Category Benchmark
    # =========================

    category_data = session_products[
        session_products[
            "category"
        ]
        == category
    ]

    category_product_sessions = (
        category_data[
            "session_id"
        ]
        .nunique()
    )

    category_cart_sessions = int(
        category_data[
            "has_cart"
        ]
        .sum()
    )

    category_purchase_sessions = int(
        category_data[
            "has_purchase"
        ]
        .sum()
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


    print(
        "product_id:",
        product_id
    )

    print(
        "category:",
        category
    )

    print(
        "product_sessions:",
        product_sessions_count
    )

    print(
        "purchase_cvr:",
        f"{purchase_cvr:.2%}"
    )

    print(
        "category_cvr:",
        f"{category_cvr:.2%}"
    )


    return {

        "product_name":
            product_name,

        "category":
            category,

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
# 5. Node 2
# 异常检测
# ==================================================

def anomaly_node(
    state: DiagnosisState
):

    print(
        "\n========== Anomaly Detection =========="
    )

    result = detect_conversion_anomaly(

        product_sessions=
            state[
                "product_sessions"
            ],

        purchase_cvr=
            state[
                "purchase_cvr"
            ],

        category_cvr=
            state[
                "category_cvr"
            ]
    )

    print(
        "status:",
        result[
            "status"
        ]
    )

    print(
        "deviation:",
        result[
            "cvr_deviation"
        ]
    )

    return {

        "anomaly_status":
            result[
                "status"
            ],

        "severity":
            result[
                "severity"
            ],

        "cvr_deviation":
            result[
                "cvr_deviation"
            ]
    }


# ==================================================
# 6. Router
# ==================================================

def anomaly_router(
    state: DiagnosisState
):

    status = state.get(
        "anomaly_status"
    )

    print(
        "\nAnomaly Router:",
        status
    )

    if status in [
        "low",
        "severe"
    ]:

        return "funnel_analysis"

    if status in [
        "normal",
        "insufficient_data"
    ]:

        return "report"

    print(
        "Warning: 未识别状态，进入安全兜底。"
    )

    return "report"


# ==================================================
# 7. Node 3
# 漏斗阶段分析
# ==================================================

def funnel_analysis_node(
    state: DiagnosisState
):

    print(
        "\n========== Funnel Analysis =========="
    )

    product_to_cart_deviation = (

        state[
            "cart_rate"
        ]
        -
        state[
            "category_cart_rate"
        ]

    ) / state[
        "category_cart_rate"
    ]


    cart_to_purchase_deviation = (

        state[
            "cart_to_purchase_rate"
        ]
        -
        state[
            "category_cart_to_purchase_rate"
        ]

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
# 8. Node 4
# 价格分析
# ==================================================

def price_analysis_node(
    state: DiagnosisState
):

    print(
        "\n========== Price Analysis =========="
    )

    product_id = state[
        "product_id"
    ]

    category = state[
        "category"
    ]

    sku = products[
        products[
            "product_id"
        ]
        == product_id
    ].iloc[0]

    category_products = products[
        products[
            "category"
        ]
        == category
    ]

    sku_price = float(
        sku[
            "retail_price"
        ]
    )

    avg_price = float(
        category_products[
            "retail_price"
        ]
        .mean()
    )

    median_price = float(
        category_products[
            "retail_price"
        ]
        .median()
    )

    price_deviation = (
        sku_price
        - median_price
    ) / median_price

    price_percentile = float(
        (
            category_products[
                "retail_price"
            ]
            <= sku_price
        )
        .mean()
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
# 9. Node 5
# 行业Benchmark
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
        sheet_name=
            "行业基准对比表"
    )


    fashion = benchmark[
        benchmark[
            "行业范围"
        ]
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

        for _, row in (
            fashion.iterrows()
        ):

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


    print(
        reference
    )


    return {
        "industry_reference":
            reference
    }


# ==================================================
# 10. LLM
# ==================================================

llm = ChatOpenAI(

    model=
        "deepseek-v4-flash",

    api_key=
        os.getenv(
            "DEEPSEEK_API_KEY"
        ),

    base_url=
        "https://api.deepseek.com",

    extra_body={
        "thinking": {
            "type":
                "disabled"
        }
    }
)


# ==================================================
# 11. Prompt 1
# insufficient_data
# ==================================================

def build_insufficient_prompt(
    state: DiagnosisState
):

    return f"""
你是一名电商转化率诊断专家。

当前商品由于样本量不足，
本次只能生成极简诊断报告。

商品：
{state.get("product_name")}

Product ID：
{state.get("product_id")}

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


严格遵守：

1.
Product Sessions < 20，
只允许判定为 insufficient_data。

2.
可以展示原始转化指标，
但不得判断其高、低、正常或异常。

3.
不得计算或解释：
CVR deviation、
Product→Cart deviation、
Cart→Purchase deviation。

4.
不得定位 weak_stage。

5.
不得进行价格分析。

6.
不得分析可能原因。

7.
不得调用或解释外部行业Benchmark。

8.
不得自行增加推荐样本量。
下一步唯一必要条件是：
Product Sessions达到至少20后重新运行诊断。

9.
达到20后，
只能说明重新执行异常判断，
再由Router决定是否进入深度分析。
不得承诺一定执行Funnel或Price分析。

10.
Tool未执行不等于数据不存在。

11.
不得使用统计显著、
置信区间、p值等未提供结果。


报告结构：

一、诊断结论
二、已知事实
三、漏斗异常定位
四、可能影响因素
五、外部行业参考
六、下一步
"""


# ==================================================
# 12. Prompt 2
# normal
# ==================================================

def build_normal_prompt(
    state: DiagnosisState
):

    return f"""
你是一名电商转化率诊断专家。

当前商品整体CVR状态为normal，
请生成简洁基础报告。

商品：
{state.get("product_name")}

Product ID：
{state.get("product_id")}

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


严格遵守：

1.
整体CVR未触发异常，
明确说明本次自动诊断流程不执行深度诊断。

2.
可以展示原始漏斗Rate和Category Benchmark。

3.
funnel_analysis本次未执行。
不得：
- 判断子阶段是否异常
- 定义weak_stage
- 判断哪个阶段最弱
- 根据Rate重新模拟funnel_analysis

4.
price_analysis本次未执行。
不得推断价格状态。

5.
industry_benchmark本次未执行。
不得输出行业Benchmark数值。

6.
不得因为某个子阶段Rate低于Category，
就建议优先排查该阶段。

7.
如业务方希望额外探索子漏斗或价格，
只能说明属于独立探索性分析，
不属于当前自动诊断路径。

8.
严格区分相对偏离和百分点差。

9.
不得自行生成统计显著性、
置信区间、p值或推荐样本量。

10.
不得根据Rate推断用户心理或行为原因。

11.
Tool未执行不等于数据不存在。


报告结构：

一、诊断结论
二、已知事实
三、深度诊断状态
四、下一步
"""


# ==================================================
# 13. Prompt 3
# low / severe
# ==================================================

def build_anomaly_prompt(
    state: DiagnosisState
):

    return f"""
你是一名电商转化率诊断专家。

当前商品已经触发转化异常，
并已完成漏斗、价格和外部行业参考分析。

请严格根据以下State生成报告。


商品：
{state.get("product_name")}

Product ID：
{state.get("product_id")}

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
{state.get("weak_stage")}

Product→Cart偏离：
{state.get("product_to_cart_deviation")}

Cart→Purchase偏离：
{state.get("cart_to_purchase_deviation")}

价格状态：
{state.get("price_status")}

SKU零售价：
{state.get("sku_price")}

Category零售价中位数：
{state.get("category_median_price")}

价格分位：
{state.get("price_percentile")}

外部行业参考：
{state.get("industry_reference")}


严格遵守：

1.
只能使用State已有结果。
不得创造不存在的数据。

2.
本次已经执行funnel_analysis。
weak_stage可以作为主要异常阶段定位结果。

3.
不得把“异常阶段定位”
写成“具体原因已经确定”。

4.
xxx_deviation是：
(SKU指标 - Category Benchmark)
/
Category Benchmark

表示相对偏离比例，
不是用户流失比例。

不得自行把Rate转换成新的用户流失指标。

5.
若描述百分点差，
只能用两个Rate直接相减。

6.
不得使用“统计显著”等措辞，
除非State明确提供统计检验结果。

7.
不得根据Rate推断：
用户犹豫、
购买意愿下降、
支付能力不足等心理或行为原因。

8.
Product→Cart未达到异常标准时，
只能说明：
未被当前规则识别为主要异常阶段。
不能判断图片、标题、描述不存在问题。

9.
price_status = high：
只能说明价格偏高是可能影响因素之一。
不能说价格导致CVR下降。

10.
price_status = normal：
只能说明价格位置未达到当前异常标准。
不能说价格因素已排除。

11.
价格字段是retail_price，
只能称为零售价/标价，
不能称为成交价。

12.
Dynamic Yield与TheLook口径不同：
只能作为行业背景参考。
不得直接比较高低。
不得推算TheLook指标。
不得参与异常阈值判断。

13.
事实、规则判断、假设必须分开。

14.
如果无法确认具体原因，
必须明确写：
“现有证据不足以确定因果原因。”

15.
当前数据直接支持的是：
异常状态和异常漏斗阶段定位。

具体优化建议，
例如：
结账流程、
运费、
支付方式、
库存、
竞品等，
只能作为需要进一步验证的排查方向。


报告结构：

一、诊断结论
二、已知事实
三、漏斗异常定位
四、可能影响因素
五、外部行业参考
六、下一步需要补充的数据
"""


# ==================================================
# 14. Report Node
# 三路Prompt
# ==================================================

def report_node(
    state: DiagnosisState
):

    print(
        "\n========== Report =========="
    )

    status = state.get(
        "anomaly_status"
    )

    if status == "insufficient_data":

        prompt = (
            build_insufficient_prompt(
                state
            )
        )

    elif status == "normal":

        prompt = (
            build_normal_prompt(
                state
            )
        )

    elif status in [
        "low",
        "severe"
    ]:

        prompt = (
            build_anomaly_prompt(
                state
            )
        )

    else:

        prompt = f"""
当前诊断状态无法识别。

status:
{status}

请只输出：
“当前诊断状态异常，无法生成可靠报告。”
"""

    response = llm.invoke(
        prompt
    )

    return {
        "final_report":
            response.content
    }


# ==================================================
# 15. Graph
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


# ==================================================
# 16. 自动寻找四种测试Case
# ==================================================

def find_test_cases():

    cases = {

        "severe":
            None,

        "low":
            None,

        "normal":
            None,

        "insufficient_data":
            None
    }


    product_ids = (
        session_products[
            "product_id"
        ]
        .dropna()
        .unique()
    )


    for product_id in product_ids:

        sku_data = session_products[
            session_products[
                "product_id"
            ]
            == product_id
        ]

        if sku_data.empty:
            continue


        category = (
            sku_data[
                "category"
            ]
            .iloc[0]
        )


        product_sessions = (
            sku_data[
                "session_id"
            ]
            .nunique()
        )


        purchase_sessions_count = int(
            sku_data[
                "has_purchase"
            ]
            .sum()
        )


        purchase_cvr = (
            purchase_sessions_count
            / product_sessions
        )


        category_data = session_products[
            session_products[
                "category"
            ]
            == category
        ]


        category_product_sessions = (
            category_data[
                "session_id"
            ]
            .nunique()
        )


        category_purchase_sessions = int(
            category_data[
                "has_purchase"
            ]
            .sum()
        )


        category_cvr = (
            category_purchase_sessions
            / category_product_sessions
        )


        result = (
            detect_conversion_anomaly(

                product_sessions=
                    product_sessions,

                purchase_cvr=
                    purchase_cvr,

                category_cvr=
                    category_cvr
            )
        )


        status = result[
            "status"
        ]


        if (
            status in cases
            and
            cases[
                status
            ]
            is None
        ):

            cases[
                status
            ] = int(
                product_id
            )


        if all(
            value is not None
            for value
            in cases.values()
        ):
            break


    return cases


# ==================================================
# 17. 四Case测试
# ==================================================

test_cases = (
    find_test_cases()
)


print(
    "\n========== Test Cases =========="
)

for status, product_id in (
    test_cases.items()
):

    print(
        status,
        "→ product_id:",
        product_id
    )


for expected_status, product_id in (
    test_cases.items()
):

    print("\n")
    print(
        "=" * 70
    )

    print(
        f"TEST CASE: {expected_status}"
    )

    print(
        f"PRODUCT ID: {product_id}"
    )

    print(
        "=" * 70
    )


    result = graph.invoke(
        {
            "user_question":
                "诊断这个SKU的转化表现",

            "product_id":
                product_id
        }
    )


    actual_status = (
        result[
            "anomaly_status"
        ]
    )


    print(
        "\n========== Test Result =========="
    )

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
    )

    print(
        expected_status
        == actual_status
    )


    print(
        "\nFinal Report:"
    )

    print(
        result[
            "final_report"
        ]
    )




"output"
# prompt重构后，失败案例，测试4个case导致串规则
# prompt改为独立分开执行

'''
再次逐字审查：
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

## 一、诊断结论

该商品（Anne Klein Women's Petite Tweed Jacket，Product ID: 7498）当前被判定为**严重转化异常（severe）**，CVR相对偏离为 **-50.91%**（SKU 购买转化率 13.04% vs 品类基准 26.57%）。

根据漏斗分析结果，**主要异常环节为「购物车→购买」（cart_to_purchase）**，该环节相对偏离为 **-34.54%**，是当前漏斗中偏离最严重的阶段；「商品页→加购」（Product→Cart）环节相对偏离为 **-25.00%**，未达到当前规则的异常识别标准。

**现有证据足以确定的是**：该商品存在严重转化异常，且漏斗中最薄弱的环节为「购物车→购买」阶段。**现有证据不足以确定因果原因**——具体是何种因素导致用户加购后未完成购买，需要进一步数据验证。


## 二、已知事实

| 指标 | SKU | 品类基准 |
|---|---|---|
| Product→Cart Rate | 47.83% | 63.77% |
| Cart→Purchase Rate | 27.27% | 41.66% |
| Product→Purchase CVR | 13.04% | 26.57% |
| Product Sessions | 23 | — |

- **Product→Cart偏离**：-25.00%（(47.83% - 63.77%) / 63.77%）
- **Cart→Purchase偏离**：-34.54%（(27.27% - 41.66%) / 41.66%）
- **CVR相对偏离**：-50.91%（(13.04% - 26.57%) / 26.57%）
- **百分点差（Product→Cart）**：47.83% - 63.77% = -15.94个百分点
- **百分点差（Cart→Purchase）**：27.27% - 41.66% = -14.39个百分点

**价格状态**：normal。SKU 零售价为 $69.97，品类零售价中位数为 $59.99，价格分位为 0.515（处于品类价格分布约第51.5百分位）。


## 三、漏斗异常定位

### 3.1 阶段偏离汇总

| 漏斗阶段 | SKU | 品类基准 | 相对偏离 | 是否为主要异常 |
|---|---|---|---|---|
| Product→Cart | 47.83% | 63.77% | -25.00% | 否（未达异常识别标准） |
| Cart→Purchase | 27.27% | 41.66% | -34.54% | **是** |

### 3.2 定位解读

漏斗分析结果显示，主要异常阶段为 **cart_to_purchase（购物车→购买）**：

- 该阶段的相对偏离幅度（-34.54%）大于 Product→Cart 阶段的偏离幅度（-25.00%）。
- 当前规则将 cart_to_purchase 识别为主要弱环节。

**需要特别说明的是**：
- Product→Cart 阶段未被识别为主要异常阶段，**仅代表该环节未达到当前规则的异常阈值**，不能据此判断商品图片、标题或描述不存在问题。
- Cart→Purchase 阶段为主要异常环节，**仅代表数据定位结果**，不能据此推断用户在结账时存在犹豫、支付意愿下降等心理或行为原因。


## 四、可能影响因素

### 4.1 规则判断（基于State数据）

| 因素 | 判断 | 说明 |
|---|---|---|
| 价格因素 | **normal** | 零售价 $69.97 处于品类价格分布约第51.5百分位，价格位置未达到当前异常标准。**不能说价格因素已排除**，仅说明价格不是当前规则识别出的异常因素。 |

### 4.2 假设性排查方向（需进一步验证）

由于主要异常环节为「购物车→购买」，以下因素可能与该阶段转化率偏低有关，**但当前数据不足以确认因果关系，仅作为需要进一步验证的排查方向**：

1. **结账流程体验**：是否存在流程过长、步骤复杂等问题。
2. **运费与税费透明度**：加购后显示的运费/税费是否超出用户预期。
3. **支付方式覆盖**：是否缺少用户习惯的支付选项。
4. **库存状态**：加购后是否出现库存不足或无法配送的提示。
5. **竞品比价行为**：用户加购后是否转向同类替代品。
6. **商品页信息完整性**：加购后用户是否需要返回商品页再次确认尺码、材质等信息。

> ⚠️ 以上方向仅为假设性排查建议，**不得视为已确认的原因**。


## 五、外部行业参考

根据 Dynamic Yield Fashion/Apparel 2025 外部行业参考数据：

- 加购率（商品页浏览口径）：6.58%
- 购买转化率（访客口径）：3.03%
- 购物车完成率代理（派生）：21.87%
- 购物车放弃率：78.13%

**重要说明**：

- Dynamic Yield 与 TheLook 统计口径不同（如加购率的分母口径差异），**不可直接与本次数据进行比较**，也不得据此推算 TheLook 的对应指标。
- 该数据仅作为行业背景参考，**不参与本商品的异常阈值判断**。


## 六、下一步需要补充的数据

为深入定位「购物车→购买」阶段转化率偏低的具体原因，建议补充以下数据：

| 数据需求 | 目的 |
|---|---|
| 购物车放弃率（用户加购后未完成购买的漏斗数据） | 确认放弃发生的精确节点 |
| 结账流程各步骤转化数据（如进入结算页、填写信息、确认订单） | 定位流程中的具体流失步骤 |
| 运费/税费显示前后转化对比 | 验证隐性成本是否为影响因素 |
| 支付方式使用分布 | 排查支付环节是否存在障碍 |
| 库存/配送信息可用性数据 | 排除库存或物流导致的流失 |
| 同价格带竞品转化对比数据 | 评估竞争替代效应 |
| 该商品的历史转化趋势 | 判断异常是近期出现还是长期存在 |
| 商品页流量来源构成 | 排查流量质量因素 |


**报告日期**：基于当前 State 数据生成

**数据说明**：本报告中的所有偏离指标均为（SKU指标 - Category Benchmark）/ Category Benchmark 的相对偏离比例，而非用户流失比例。百分点差均直接由两个 Rate 相减获得。本报告未涉及任何统计显著性检验，所有结论仅基于当前 State 中提供的描述性数据。


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

## 一、诊断结论

商品 **MiH Jeans Women's Marrakesh Jean**（Product ID: 4680）当前处于**转化异常（low）状态**。

漏斗定位结果显示，主要弱环节为 **Cart→Purchase（购物车到支付）** 阶段，该环节的转化表现与品类基准存在明显偏离。同时，商品零售价处于高位区间，价格偏高被识别为可能影响因素之一。

需要明确的是：**现有证据不足以确定因果原因。** 当前数据直接支持的是异常状态和异常漏斗阶段的定位，具体原因仍需进一步验证。


## 二、已知事实

| 指标 | SKU | Category Benchmark | 偏离比例 |
|------|-----|-----|------|
| Product→Cart Rate | 55.00% | 63.31% | -13.13% |
| Cart→Purchase Rate | 27.27% | 42.14% | -35.28% |
| Product→Purchase CVR | 15.00% | 26.68% | -43.78% |

- **Product→Cart Rate 百分点差**：55.00% - 63.31% = **-8.31个百分点**
- **Cart→Purchase Rate 百分点差**：27.27% - 42.14% = **-14.87个百分点**
- **Product→Purchase CVR 百分点差**：15.00% - 26.68% = **-11.68个百分点**

商品零售价为 **189.0美元**，Category零售价中位数为 **78.0美元**，价格分位为 **0.912**，price_status = **high**。

**异常判定：**
- CVR相对偏离 = **-0.4378**，异常状态为 **low**
- Product→Cart偏离 = **-0.1313**，未达到当前规则设定的异常标准
- Cart→Purchase偏离 = **-0.3528**，为主要偏离项


## 三、漏斗异常定位

根据已完成的漏斗分析，weak_stage 为 **cart_to_purchase**。

具体表现为：
- SKU的加购后完成购买的比例（27.27%）显著低于品类基准（42.14%），相对偏离达到 **-35.28%**，百分点差为 **-14.87个百分点**。
- 相比之下，Product→Cart阶段虽也有负向偏离（-13.13%），但未被当前规则识别为主要异常阶段。

**说明：**
- Product→Cart阶段未达到异常标准，**仅说明该环节未被当前规则识别为主要异常阶段，不能据此判断商品页面、图片、标题或描述不存在问题。**
- Cart→Purchase为当前识别出的主要弱环节，但**不等于具体原因已经确定**。


## 四、可能影响因素

### 规则判断（基于State数据）：

1. **价格因素**：商品零售价189.0美元处于品类价格分布的较高位置（分位0.912），price_status为 **high**。根据规则，**仅能说明价格偏高是可能影响因素之一，不能推断价格导致CVR下降。**

### 假设性排查方向（需进一步验证，非结论）：

以下方向基于Cart→Purchase为主要弱环节这一事实推断，仅作为**需要进一步验证的排查方向**，不构成已确认的原因：

1. **结账流程**：需验证是否存在步骤繁琐、页面报错等技术性问题。
2. **运费与税费**：需验证结算时显示的附加费用是否超出消费者预期。
3. **支付方式**：需验证该SKU是否缺少目标用户常用的支付选项。
4. **库存状态**：需验证是否存在下单时发现库存不足或配送时间过长的情况。
5. **竞争对比**：需验证同价位或同品类竞品在结算环节是否具备优势。

**以上方向均需要补充对应数据后才能确认，当前证据不足以确定因果原因。** 由于Product→Cart阶段未被识别为异常，价格因素主要需要结合其在结算环节的影响进行评估，但其对该阶段的具体作用机制尚不明确。


## 五、外部行业参考

根据Dynamic Yield Fashion/Apparel 2025外部行业参考数据：
- 加购率（商品页浏览口径）：**6.58%**
- 购买转化率（访客口径）：**3.03%**
- 购物车完成率代理（派生）：**21.87%**
- 购物车放弃率：**78.13%**

**注意：** Dynamic Yield与TheLook统计口径不同，**不可直接用于比较高低，不可推算TheLook指标，不参与异常阈值判断。** 以上数据仅作为行业背景参考，帮助理解时尚/服装品类中购物车放弃率普遍较高是常见现象，但不作为本SKU异常与否的判定依据。


## 六、下一步需要补充的数据

为进一步定位Cart→Purchase阶段表现偏弱的实际原因，建议补充以下数据：

1. **漏斗各步骤的细分数据**：如在结算流程中，进入结算页、填写地址、确认订单、完成支付各步骤的转化率及退出点分布。
2. **弃购用户行为数据**：如弃购用户停留在结算页的时长、是否反复修改订单、是否有优惠码尝试行为等（仅作行为事实记录，不作心理推断）。
3. **运费与税费信息**：该SKU结算时的运费、税费金额及其占订单总额的比例，与品类其他商品对比。
4. **支付方式分布**：该SKU订单使用的支付方式分布、各支付方式的成功率及失败率。
5. **竞品对标数据**：同类高价位牛仔裤在Cart→Purchase阶段的转化率水平（需同一统计口径）。
6. **用户评价与退货数据**：该SKU的评价内容、评分分布及退货率，用于排查是否存在质量或预期管理问题。
7. **价格弹性测试数据**：如该SKU参与折扣或促销时的转化率变化，用于进一步验证价格因素的影响。


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

当前商品整体CVR状态为normal，未触发异常诊断阈值，因此本次自动诊断流程不执行深度诊断。该商品处于正常表现区间，无需系统级干预。

二、已知事实

| 指标 | SKU数值 | Category Benchmark |
|------|---------|-------------------|
| Product→Cart Rate | 70.97% | 62.93% |
| Product→Purchase CVR | 25.81% | 26.38% |
| Cart→Purchase Rate | 36.36% | 41.93% |
| CVR相对偏离 | -0.0218 | — |

注意：CVR相对偏离为-0.0218，表示SKU整体购买转化率低于类目基准的相对比例（约2.18%的相对差距），而非百分点差（绝对差为-0.57个百分点）。该偏离幅度处于normal区间。

三、深度诊断状态

- **funnel_analysis**：未执行。本次自动诊断不判断各子阶段是否异常、不定义weak_stage、不定位最弱阶段。
- **price_analysis**：未执行。本次自动诊断不推断价格状态。
- **industry_benchmark**：未执行。本次自动诊断不输出行业Benchmark数值。

当前仅呈现原始漏斗数据与Category对照，不据此推导任何结论。Tool未执行不等于相关数据不存在，仅表示不属于本次自动诊断路径。

四、下一步

1. **维持常态监控**：按常规周期关注该商品CVR走势，无需因单次normal状态启动额外操作。
2. **业务方可选探索**：如希望进一步拆解子漏斗（如Product→Cart、Cart→Purchase、商品详情页表现）或价格维度分析，可发起独立探索性分析。该分析不属于当前自动诊断路径，需另行安排。
3. **注意**：任何子阶段Rate低于Category仅为数据事实呈现，不作为优先排查该阶段的依据；是否排查由业务方基于独立分析决策。


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
**insufficient_data**：当前商品样本量不足（Product Sessions = 19 < 20），本次不予判定任何异常或定位。

二、已知事实
- 商品：IZOD Men's Slim Fit Long Sleeve Mini Check Button Down Shirt（Product ID: 16599）
- 类目：Tops & Tees
- Product Sessions：19
- SKU Product→Cart Rate：63.16%
- Category Product→Cart Rate：63.50%
- SKU Product→Purchase CVR：21.05%
- Category CVR：26.93%
- SKU Cart→Purchase Rate：33.33%
- Category Cart→Purchase Rate：42.40%

三、漏斗异常定位
**未定位**（样本量不足，不执行任何漏斗阶段判定）。

四、可能影响因素
**不分析**（样本量不足，不进行原因推测）。

五、外部行业参考
**不调用**（不引用外部Benchmark）。

六、下一步
**唯一必要条件**：将 Product Sessions 提升至至少 **20** 后，重新运行诊断程序。
届时仅执行异常判断，由Router决定是否进入深度分析（Funnel或Price分析不必然执行）。
'''
