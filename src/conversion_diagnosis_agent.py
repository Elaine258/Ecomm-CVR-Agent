import sys
import os
import time
import logging
import pandas as pd

from functools import wraps

from typing import TypedDict, Optional
from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI


# ==================================================
# 0. 项目路径
# ==================================================

ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        ".."
    )
)

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


from src.rules.conversion_anomaly import (
    detect_conversion_anomaly
)

from src.diagnosis_history import (
    save_diagnosis_history,
    get_previous_diagnosis,
    get_latest_diagnosis,
    compare_diagnosis,
    build_follow_up_summary,
    validate_action,
    build_next_round_action
)


load_dotenv()


# ==================================================
# Logging
# ==================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger(__name__)


# 第三方日志降噪
logging.getLogger(
    "langchain_openai"
).setLevel(
    logging.WARNING
)

logging.getLogger(
    "openai"
).setLevel(
    logging.WARNING
)

logging.getLogger(
    "httpx"
).setLevel(
    logging.WARNING
)

logging.getLogger(
    "httpx2"
).setLevel(
    logging.WARNING
)

# ==================================================
# Diagnosis Observability
# 完整诊断可观测性
# ==================================================

def observe_diagnosis(func):

    @wraps(func)
    def wrapper(
        product_id,
        *args,
        **kwargs
    ):

        start_time = time.perf_counter()

        logger.info(
            "Diagnosis started | product_id=%s",
            product_id
        )

        try:

            result = func(
                product_id,
                *args,
                **kwargs
            )

            duration = (
                time.perf_counter()
                - start_time
            )

            logger.info(
                "Diagnosis completed | "
                "product_id=%s | "
                "status=%s | "
                "weak_stage=%s | "
                "duration=%.3fs",
                product_id,
                result.get("status"),
                result.get("weak_stage"),
                duration
            )

            return result


        except Exception:

            duration = (
                time.perf_counter()
                - start_time
            )

            logger.exception(
                "Diagnosis failed | "
                "product_id=%s | "
                "duration=%.3fs",
                product_id,
                duration
            )

            raise


    return wrapper

# ==================================================
# 数据路径
# ==================================================

DATA_DIR = os.path.abspath(
    os.getenv(
        "ECOMM_DATA_DIR",
        os.path.join(ROOT, "data")
    )
)
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
# 2. 预处理 Session → Product
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

    # 输入
    user_question: str
    product_id: int

    # 商品
    product_name: str
    category: str

    # SKU漏斗
    product_sessions: int
    cart_sessions: int
    purchase_sessions: int

    cart_rate: float
    purchase_cvr: float
    cart_to_purchase_rate: float

    # Category Benchmark
    category_cart_rate: float
    category_cvr: float
    category_cart_to_purchase_rate: float

    # 异常检测
    anomaly_status: str
    severity: Optional[str]
    cvr_deviation: Optional[float]

    # 漏斗定位
    product_to_cart_deviation: float
    cart_to_purchase_deviation: float
    weak_stage: str

    # 价格分析
    sku_price: float
    category_avg_price: float
    category_median_price: float
    price_deviation: float
    price_percentile: float
    price_status: str

    # 外部Benchmark
    industry_reference: str

    # 下一步行动
    next_action: dict

    # 最终报告
    final_report: str

# ==================================================
# 4. Node 1
# 获取SKU转化指标
# ==================================================

def conversion_metrics_node(
    state: DiagnosisState
):

    product_id = state["product_id"]

    logger.info(
        "Conversion Metrics started | product_id=%s",
        product_id
    )


    sku_data = session_products[
        session_products["product_id"]
        == product_id
    ]


    if sku_data.empty:

        logger.error(
            "Conversion Metrics failed | product_id=%s | reason=product_not_found",
            product_id
        )

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
        sku_data["session_id"]
        .nunique()
    )

    cart_count = (
        sku_data.loc[
            sku_data["has_cart"],
            "session_id"
        ]
        .nunique()
    )

    purchase_count = (
        sku_data.loc[
            sku_data["has_purchase"],
            "session_id"
        ]
        .nunique()
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


    # =========================
    # Category Benchmark
    # =========================

    category_data = session_products[
        session_products["category"]
        == category
    ]


    category_product_sessions = (
        category_data["session_id"]
        .nunique()
    )

    category_cart_sessions = (
        category_data.loc[
            category_data["has_cart"],
            "session_id"
        ]
        .nunique()
    )

    category_purchase_sessions = (
        category_data.loc[
            category_data["has_purchase"],
            "session_id"
        ]
        .nunique()
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
        if category_cart_sessions > 0
        else 0.0
    )


    logger.info(
        "Conversion Metrics completed | "
        "product_id=%s | "
        "category=%s | "
        "sessions=%s | "
        "purchase_cvr=%.2f%% | "
        "category_cvr=%.2f%%",
        product_id,
        category,
        product_sessions_count,
        purchase_cvr * 100,
        category_cvr * 100
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
# CVR异常检测
# ==================================================

def anomaly_node(
    state: DiagnosisState
):

    result = detect_conversion_anomaly(
        product_sessions=
            state["product_sessions"],

        purchase_cvr=
            state["purchase_cvr"],

        category_cvr=
            state["category_cvr"]
    )


    logger.info(
        "Anomaly Detection completed | "
        "product_id=%s | "
        "status=%s | "
        "deviation=%s",
        state.get("product_id"),
        result["status"],
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
# 6. Router
# ==================================================

def anomaly_router(
    state: DiagnosisState
):

    status = state.get(
        "anomaly_status"
    )


    logger.info(
        "Anomaly Router | "
        "product_id=%s | "
        "status=%s",
        state.get("product_id"),
        status
    )


    if status in [
        "low",
        "severe"
    ]:

        logger.info(
            "Anomaly Router decision | "
            "product_id=%s | "
            "route=funnel_analysis",
            state.get("product_id")
        )

        return "funnel_analysis"


    if status in [
        "normal",
        "insufficient_data"
    ]:

        logger.info(
            "Anomaly Router decision | "
            "product_id=%s | "
            "route=next_action",
            state.get("product_id")
        )

        return "next_action"


    logger.warning(
        "Anomaly Router fallback | "
        "product_id=%s | "
        "unknown_status=%s | "
        "route=next_action",
        state.get("product_id"),
        status
    )

    return "next_action"


# ==================================================
# 7. Node 3
# 漏斗阶段分析
# ==================================================

def funnel_analysis_node(
    state: DiagnosisState
):

    category_cart_rate = (
        state["category_cart_rate"]
    )

    if category_cart_rate == 0:
        product_to_cart_deviation = 0.0

    else:
        product_to_cart_deviation = (
            state["cart_rate"]
            -
            category_cart_rate
        ) / category_cart_rate


    category_cart_to_purchase = (
        state[
            "category_cart_to_purchase_rate"
        ]
    )

    if category_cart_to_purchase == 0:
        cart_to_purchase_deviation = 0.0

    else:
        cart_to_purchase_deviation = (
            state[
                "cart_to_purchase_rate"
            ]
            -
            category_cart_to_purchase
        ) / category_cart_to_purchase


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


    logger.info(
        "Funnel Analysis completed | "
        "product_id=%s | "
        "product_to_cart_deviation=%.4f | "
        "cart_to_purchase_deviation=%.4f | "
        "weak_stage=%s",
        state.get("product_id"),
        product_to_cart_deviation,
        cart_to_purchase_deviation,
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

    product_id = state[
        "product_id"
    ]

    category = state[
        "category"
    ]


    sku_data = products[
        products["product_id"]
        == product_id
    ]


    if sku_data.empty:

        logger.error(
            "Price Analysis failed | "
            "product_id=%s | "
            "reason=product_not_found",
            product_id
        )

        raise ValueError(
            f"products表中找不到 product_id={product_id}"
        )


    sku = sku_data.iloc[0]


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
        ]
        .mean()
    )

    median_price = float(
        category_products[
            "retail_price"
        ]
        .median()
    )


    if median_price == 0:
        price_deviation = 0.0

    else:
        price_deviation = (
            sku_price - median_price
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


    logger.info(
        "Price Analysis completed | "
        "product_id=%s | "
        "sku_price=%.2f | "
        "median_price=%.2f | "
        "percentile=%.4f | "
        "price_status=%s",
        product_id,
        sku_price,
        median_price,
        price_percentile,
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
# 外部行业Benchmark
# ==================================================

def industry_benchmark_node(
    state: DiagnosisState
):

    product_id = state.get(
        "product_id"
    )


    if not os.path.exists(
        BENCHMARK_PATH
    ):

        reference = (
            "未找到外部行业Benchmark文件。"
        )

        logger.warning(
            "Industry Benchmark unavailable | "
            "product_id=%s | "
            "reason=file_not_found",
            product_id
        )

        return {
            "industry_reference":
                reference
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

        logger.warning(
            "Industry Benchmark unavailable | "
            "product_id=%s | "
            "reason=fashion_reference_not_found",
            product_id
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

        logger.info(
            "Industry Benchmark completed | "
            "product_id=%s | "
            "source=Dynamic Yield | "
            "industry=Fashion/Apparel",
            product_id
        )


    return {
        "industry_reference":
            reference
    }


# ==================================================
# 10. Node 6
# 下一步行动生成
# ==================================================

def next_action_node(
    state: DiagnosisState
):

    status = state.get(
        "anomaly_status"
    )

    weak_stage = state.get(
        "weak_stage"
    )

    price_status = state.get(
        "price_status"
    )


    # ==========================================
    # insufficient_data
    # ==========================================

    if status == "insufficient_data":

        next_action = {
            "priority":
                "P1",

            "action_type":
                "collect_more_sessions",

            "target_stage":
                None,

            "required_data": [
                "product_sessions"
            ],

            "reason":
                "Product Sessions未达到最低诊断门槛20",

            "goal":
                "待Product Sessions累计至至少20后重新运行诊断"
        }


    # ==========================================
    # normal
    # ==========================================

    elif status == "normal":

        next_action = {
            "priority":
                "P3",

            "action_type":
                "monitor",

            "target_stage":
                None,

            "required_data":
                [],

            "reason":
                "整体CVR未触发当前异常诊断阈值",

            "goal":
                "保持常规监控，不进入当前自动深度诊断路径"
        }


    # ==========================================
    # low / severe
    # ==========================================

    elif status in [
        "low",
        "severe"
    ]:


        # Cart → Purchase
        if weak_stage == "cart_to_purchase":

            required_data = [
                "checkout_step_funnel",
                "cart_abandon_reason",
                "shipping_tax_data",
                "payment_method_data",
                "inventory_delivery_data"
            ]


            if price_status == "high":

                required_data.append(
                    "same_price_band_benchmark"
                )


            next_action = {
                "priority":
                    (
                        "P1"
                        if status == "severe"
                        else "P2"
                    ),

                "action_type":
                    "collect_data",

                "target_stage":
                    "cart_to_purchase",

                "required_data":
                    required_data,

                "reason":
                    "Cart→Purchase被识别为当前主要异常阶段",

                "goal":
                    "进一步定位购物车至购买环节中的具体转化阻力"
            }


        # Product → Cart
        elif weak_stage == "product_to_cart":

            next_action = {
                "priority":
                    (
                        "P1"
                        if status == "severe"
                        else "P2"
                    ),

                "action_type":
                    "collect_data",

                "target_stage":
                    "product_to_cart",

                "required_data": [
                    "product_page_behavior",
                    "product_content_data",
                    "traffic_source_data"
                ],

                "reason":
                    "Product→Cart被识别为当前主要异常阶段",

                "goal":
                    "进一步定位商品页至加购阶段中的具体转化阻力"
            }


        # 两个阶段都异常
        elif weak_stage == "both":

            next_action = {
                "priority":
                    "P1",

                "action_type":
                    "collect_data",

                "target_stage":
                    "both",

                "required_data": [
                    "product_page_behavior",
                    "checkout_step_funnel",
                    "cart_abandon_reason",
                    "traffic_source_data"
                ],

                "reason":
                    "Product→Cart与Cart→Purchase均达到当前异常阈值",

                "goal":
                    "分别定位上游加购与下游购买阶段的异常来源"
            }


        # CVR异常但子漏斗无明确异常
        else:

            next_action = {
                "priority":
                    (
                        "P1"
                        if status == "severe"
                        else "P2"
                    ),

                "action_type":
                    "investigate",

                "target_stage":
                    "overall",

                "required_data": [
                    "historical_conversion_trend",
                    "traffic_source_data",
                    "same_category_sku_comparison"
                ],

                "reason":
                    "整体CVR异常，但当前子漏斗未识别出明确主要弱环节",

                "goal":
                    "补充更多维度数据以继续定位异常来源"
            }


    # ==========================================
    # 安全兜底
    # ==========================================

    else:

        next_action = {
            "priority":
                "P1",

            "action_type":
                "manual_review",

            "target_stage":
                None,

            "required_data":
                [],

            "reason":
                f"无法识别anomaly_status={status}",

            "goal":
                "人工检查诊断流程状态"
        }


    logger.info(
        "Next Action generated | "
        "product_id=%s | "
        "priority=%s | "
        "action_type=%s | "
        "target_stage=%s",
        state.get("product_id"),
        next_action.get("priority"),
        next_action.get("action_type"),
        next_action.get("target_stage")
    )


    return {
        "next_action":
            next_action
    }


# ==================================================
# 11. LLM
# ==================================================

llm = ChatOpenAI(
    model="deepseek-v4-flash",

    api_key=os.getenv(
        "DEEPSEEK_API_KEY"
    ),

    base_url="https://api.deepseek.com",

    extra_body={
        "thinking": {
            "type":
                "disabled"
        }
    }
)


# ==================================================
# 12. Prompt 1
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

结构化下一步行动：
{state.get("next_action")}


严格遵守：

1.
Product Sessions < 20，
只能判定为 insufficient_data。

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

9.
报告中的下一步行动
必须严格来自 State 中的 next_action。

不得自行增加新的：
优先级、
行动类型、
目标阶段、
所需数据。

10.
next_action字段含义：

priority：
行动优先级。

action_type：
下一步行动类型。

target_stage：
目标漏斗阶段。

required_data：
需要补充或继续积累的数据。

reason：
采取该行动的规则依据。

goal：
希望达到的目标。

11.
当前 next_action 的核心含义是：
待 Product Sessions 累积至至少20后重新诊断。

达到20后，
由系统重新判断 anomaly_status，
再由Router决定是否进入深度诊断。

12.
Tool未执行不等于数据不存在。

13.
不得使用统计显著、
置信区间、
p值等未提供结果。

14.
术语必须统一：
Cart→Purchase统一称为“购物车→购买”，
不得称为“购物车→支付”。

报告结构：

一、诊断结论
二、已知事实
三、下一步行动
"""


# ==================================================
# 13. Prompt 2
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

结构化下一步行动：
{state.get("next_action")}


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
报告中的下一步行动
必须严格来自 State 中的 next_action。

不得自行新增另一套行动建议。

8.
next_action字段含义：

priority：
行动优先级。

action_type：
行动类型。

target_stage：
目标漏斗阶段。

required_data：
需要的数据。

reason：
规则依据。

goal：
行动目标。

9.
当前normal状态的next_action
只允许解释为常规监控。

如业务方希望额外探索子漏斗或价格，
只能说明属于独立探索性分析，
不能写入当前自动行动计划。

10.
严格区分相对偏离和百分点差。

11.
不得生成统计显著性、
置信区间、
p值或推荐样本量。

12.
不得根据Rate推断用户心理或行为原因。

13.
Tool未执行不等于数据不存在。

14.
不得表述为“无需业务干预”。

只能说明：
当前未触发本Agent的异常诊断阈值。

15.
术语统一：
Cart→Purchase统一称为“购物车→购买”，
不得称为“购物车→支付”。

报告结构：

一、诊断结论
二、已知事实
三、下一步行动
"""


# ==================================================
# 14. Prompt 3
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

结构化下一步行动：
{state.get("next_action")}


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
xxx_deviation表示：

(SKU指标 - Category Benchmark)
/
Category Benchmark

属于相对偏离比例，
不是用户流失比例。

不得自行把Rate转换成新的用户流失指标。

5.
若描述百分点差，
只能用两个Rate直接相减。

6.
不得使用：
“统计显著”
“显著低于”
等暗示统计检验的措辞。

优先使用：
“明显低于”
“达到当前异常阈值”。

7.
不得根据Rate推断：
用户犹豫、
购买意愿下降、
支付能力不足
等心理或行为原因。

8.
Product→Cart未达到异常标准时，
只能说明：
未被当前规则识别为主要异常阶段。

不能判断图片、标题、描述不存在问题。

9.
price_status = high：

只能说明：
价格偏高是可能影响因素之一。

不能说：
价格导致CVR下降。

10.
price_status = normal：

只能说明：
价格位置未达到当前价格异常标准。

不能说：
价格因素已排除。

11.
价格字段是retail_price。

只能称为：
零售价/标价。

不能称为：
成交价。

12.
Dynamic Yield与TheLook口径不同：

只能作为行业背景参考。

不得：
直接比较高低；
通过Dynamic Yield推算TheLook指标；
参与异常阈值判断；
根据Dynamic Yield进一步推导行业行为结论。

13.
事实、
规则判断、
假设
必须分开。

14.
如果无法确认具体原因，
必须明确写：

“现有证据不足以确定因果原因。”

15.
当前数据直接支持的是：

异常状态；
异常漏斗阶段定位；
价格位置状态；
结构化next_action。

16.
具体原因，
例如：

结账流程、
运费、
支付方式、
库存、
竞品等，

只能作为需要进一步验证的假设。

17.
报告中的“下一步行动”
必须严格基于 State 中的 next_action。

不得自行重新生成另一套行动计划。

18.
next_action字段含义：

priority：
行动优先级。

action_type：
行动类型。

target_stage：
行动针对的漏斗阶段。

required_data：
下一步需要补充的数据。

reason：
该行动由什么诊断结果触发。

goal：
完成该行动希望解决的问题。

19.
报告中的下一步行动，
必须保留next_action的核心结构：

优先级；
行动类型；
目标阶段；
所需数据；
规则依据；
行动目标。

20.
不得自行改变next_action中的优先级。

例如：
State中priority=P1，
报告必须保持P1。

21.
不得自行删除或新增
next_action.required_data中的项目。

可以将英文技术字段翻译成中文，
但语义必须一一对应。

22.
不得写：
“某因素导致用户未购买”。

只能写：
“某因素可能与该阶段表现偏低有关，
需要进一步验证。”

23.
子漏斗异常阈值只能根据 xxx_deviation 判断。

百分点差只用于描述两个Rate之间的绝对差异，
不得表述为“百分点差达到异常阈值”，
也不得说“百分点差低于Benchmark”。

正确示例：
“SKU Cart→Purchase Rate为27.27%，
Category Benchmark为41.66%，
相对偏离-34.54%，达到当前异常阈值；
两者百分点差为-14.39个百分点。”

24.
next_action中的 priority、action_type、target_stage、
required_data、reason、goal 均属于确定性结构化结果。

报告可以将英文技术字段翻译为中文，
但不得扩展、改写或增加其业务含义。

尤其是 goal，
必须保持与 State 中 goal 的原意一致，
不得额外增加新的行动目标。

25.
术语必须统一：
Cart→Purchase统一称为“购物车→购买”，
不得称为“购物车→支付”。

报告结构：

一、诊断结论
二、已知事实
三、漏斗异常定位
四、价格状态
五、可能影响因素
六、外部行业参考
七、下一步行动
八、诊断边界
"""


# ==================================================
# 15. Report Node
# ==================================================

def report_node(
    state: DiagnosisState
):

    status = state.get(
        "anomaly_status"
    )

    product_id = state.get(
        "product_id"
    )


    logger.info(
        "Report generation started | "
        "product_id=%s | "
        "status=%s",
        product_id,
        status
    )


    if status == "insufficient_data":

        prompt = build_insufficient_prompt(
            state
        )


    elif status == "normal":

        prompt = build_normal_prompt(
            state
        )


    elif status in [
        "low",
        "severe"
    ]:

        prompt = build_anomaly_prompt(
            state
        )


    else:

        logger.warning(
            "Report generation fallback | "
            "product_id=%s | "
            "unknown_status=%s",
            product_id,
            status
        )

        prompt = f"""
当前诊断状态无法识别。

status:
{status}

请只输出：

当前诊断状态异常，无法生成可靠报告。
"""


    response = llm.invoke(
        prompt
    )


    logger.info(
        "Report generation completed | "
        "product_id=%s | "
        "status=%s",
        product_id,
        status
    )


    return {
        "final_report":
            response.content
    }


# ==================================================
# 16. Graph
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
    "next_action",
    next_action_node
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

        "next_action":
            "next_action"
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
    "next_action"
)

builder.add_edge(
    "next_action",
    END
)


graph = builder.compile()


# ==================================================
# 17. 正式统一入口
# ==================================================

@observe_diagnosis
def diagnose_product(
    product_id: int
) -> dict:

    result = graph.invoke(
        {
            "user_question":
                "诊断这个SKU的转化表现",

            "product_id":
                int(product_id)
        }
    )


    diagnosis_result = {

        "product_id":
            product_id,

        "product_name":
            result.get(
                "product_name"
            ),

        "category":
            result.get(
                "category"
            ),

        "status":
            result.get(
                "anomaly_status"
            ),

        "severity":
            result.get(
                "severity"
            ),

        "product_sessions":
            result.get(
                "product_sessions"
            ),

        "cart_rate":
            result.get(
                "cart_rate"
            ),

        "purchase_cvr":
            result.get(
                "purchase_cvr"
            ),

        "cart_to_purchase_rate":
            result.get(
                "cart_to_purchase_rate"
            ),

        "category_cart_rate":
            result.get(
                "category_cart_rate"
            ),

        "category_cvr":
            result.get(
                "category_cvr"
            ),

        "category_cart_to_purchase_rate":
            result.get(
                "category_cart_to_purchase_rate"
            ),

        "cvr_deviation":
            result.get(
                "cvr_deviation"
            ),

        "product_to_cart_deviation":
            result.get(
                "product_to_cart_deviation"
            ),

        "cart_to_purchase_deviation":
            result.get(
                "cart_to_purchase_deviation"
            ),

        "weak_stage":
            result.get(
                "weak_stage"
            ),

        "sku_price":
            result.get(
                "sku_price"
            ),

        "category_median_price":
            result.get(
                "category_median_price"
            ),

        "price_percentile":
            result.get(
                "price_percentile"
            ),

        "price_status":
            result.get(
                "price_status"
            ),

        "industry_reference":
            result.get(
                "industry_reference"
            ),

        "next_action":
            result.get(
                "next_action"
            )
    }

    previous_record = get_latest_diagnosis(
        product_id
    )

    comparison = compare_diagnosis(
    current = diagnosis_result,
    previous = previous_record
    )

    follow_up_summary = build_follow_up_summary(
        comparison
    )

    diagnosis_result[
        "comparison"
    ] = comparison

    diagnosis_result[
        "follow_up_summary"
    ] = follow_up_summary

    # ==================================================
    # Closed Loop
    # 闭环反馈处理
    # ==================================================

    validation_result = None
    next_round_action = None

    if previous_record is not None:

        previous_action_status = previous_record.get(
            "action_status"
        )

        # 只有上一轮Action已经完成，
        # 当前这次诊断才能作为复诊结果进行验证
        if previous_action_status == "completed":

            validated_record = validate_action(
                diagnosis_id=previous_record[
                    "diagnosis_id"
                ],
                comparison=comparison
            )

            validation_result = validated_record.get(
                "validation_result"
            )

            previous_action = (
                previous_record.get(
                    "effective_action"
                )
                or previous_record.get(
                    "next_action"
                )
            )

            next_round_action = build_next_round_action(
                validation_result=
                    validation_result,

                current_diagnosis=
                    diagnosis_result,

                previous_action=
                    previous_action
            )

    diagnosis_result[
        "validation_result"
    ] = validation_result

    diagnosis_result[
        "next_round_action"
    ] = next_round_action


    # Effective Action
    effective_action = (
        next_round_action
        if next_round_action is not None
        else diagnosis_result.get(
            "next_action"
        )
    )

    diagnosis_result[
        "effective_action"
    ] = effective_action


    # 到这里才保存History
    history_record = save_diagnosis_history(
        diagnosis_result
    )

    diagnosis_result[
        "diagnosis_id"
    ] = history_record[
        "diagnosis_id"
    ]

    diagnosis_result[
        "diagnosed_at"
    ] = history_record[
        "diagnosed_at"
    ]

    # ==================================================
    # Final Report
    # 根据最终生效行动重新生成最终报告
    # ==================================================

    report_state = dict(
        result
    )

    # 把最终生效行动作为报告真正使用的next_action
    report_state[
        "next_action"
    ] = effective_action

    # 把闭环结果也传给报告上下文
    report_state[
        "comparison"
    ] = comparison

    report_state[
        "follow_up_summary"
    ] = follow_up_summary

    report_state[
        "validation_result"
    ] = validation_result

    report_state[
        "next_round_action"
    ] = next_round_action

    report_state[
        "effective_action"
    ] = effective_action

    final_report_result = report_node(
        report_state
    )

    diagnosis_result[
        "final_report"
    ] = final_report_result[
        "final_report"
    ]

    return diagnosis_result