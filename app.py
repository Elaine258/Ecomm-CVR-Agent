import os
import sys
import pandas as pd
import streamlit as st
import altair as alt
from dotenv import load_dotenv


# ==================================================
# 0. 项目路径
# ==================================================

ROOT = os.path.abspath(
    os.path.dirname(__file__)
)

if ROOT not in sys.path:
    sys.path.insert(
        0,
        ROOT
    )

load_dotenv()


# ==================================================
# 1. 正式业务History与开发测试History分离
# ==================================================

DATA_DIR = os.path.abspath(
    os.getenv(
        "ECOMM_DATA_DIR",
        os.path.join(ROOT, "data")
    )
)

BUSINESS_HISTORY_PATH = os.path.join(
    DATA_DIR,
    "diagnosis_history_business.jsonl"
)


import src.diagnosis_history as diagnosis_history

diagnosis_history.DATA_DIR = DATA_DIR
diagnosis_history.HISTORY_PATH = (
    BUSINESS_HISTORY_PATH
)


from src.conversion_diagnosis_agent import (
    diagnose_product
)


get_product_history = (
    diagnosis_history.get_product_history
)

update_action_status = (
    diagnosis_history.update_action_status
)


# ==================================================
# 2. 页面配置
# ==================================================

st.set_page_config(
    page_title="电商转化率诊断 Agent",
    page_icon="📊",
    layout="wide"
)


# ==================================================
# 3. 页面样式
# ==================================================

st.markdown(
    """
    <style>

    .block-container {
        padding-top: 2rem;
        padding-bottom: 4rem;
        max-width: 1450px;
    }

    .section-title {
        font-size: 1.45rem;
        font-weight: 700;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }

    div[data-testid="stMetric"] {
        border: 1px solid #e5e7eb;
        padding: 14px 16px;
        border-radius: 10px;
        min-height: 118px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ==================================================
# 4. 中文业务翻译
# ==================================================

STATUS_MAP = {
    "severe":
        "严重异常",

    "low":
        "轻度异常",

    "normal":
        "未触发异常",

    "insufficient_data":
        "数据不足",

    None:
        "—"
}


STAGE_MAP = {
    "cart_to_purchase":
        "购物车 → 购买",

    "product_to_cart":
        "商品页 → 购物车",

    "both":
        "两个阶段均异常",

    "none":
        "暂无明确弱环节",

    None:
        "—"
}


PRICE_MAP = {
    "high":
        "价格位置偏高",

    "low":
        "价格位置偏低",

    "normal":
        "正常区间",

    None:
        "—"
}


ACTION_STATUS_MAP = {
    "pending":
        "待执行",

    "in_progress":
        "执行中",

    "completed":
        "已完成",

    "validated":
        "已验证",

    None:
        "—"
}


VALIDATION_MAP = {
    "improved":
        "改善",

    "unchanged":
        "无变化",

    "worsened":
        "恶化",

    "unknown":
        "无法判断",

    None:
        "尚未验证"
}


ACTION_TYPE_MAP = {
    "collect_data":
        "收集诊断数据",

    "collect_more_sessions":
        "继续积累样本",

    "monitor":
        "常规监控",

    "investigate":
        "进一步调查",

    "monitor_after_improvement":
        "改善后持续监控",

    "expand_investigation":
        "扩大调查范围",

    "escalate_investigation":
        "升级调查",

    "collect_validation_data":
        "补充验证数据",

    "manual_review":
        "人工复核"
}


DATA_MAP = {
    "checkout_step_funnel":
        "结账步骤漏斗",

    "cart_abandon_reason":
        "购物车放弃原因",

    "shipping_tax_data":
        "运费与税费数据",

    "payment_method_data":
        "支付方式数据",

    "inventory_delivery_data":
        "库存与配送数据",

    "same_price_band_benchmark":
        "同价格带商品对比",

    "same_category_sku_comparison":
        "同品类商品对比",

    "historical_conversion_trend":
        "历史转化趋势",

    "traffic_source_data":
        "流量来源数据",

    "product_page_behavior":
        "商品页行为数据",

    "product_content_data":
        "商品内容数据",

    "product_sessions":
        "商品页访问样本"
}


DATA_QUESTION_MAP = {
    "checkout_step_funnel":
        "结账流程中是否存在明显流失步骤？",

    "cart_abandon_reason":
        "用户主要因为什么原因放弃购物车？",

    "shipping_tax_data":
        "运费或税费是否可能形成额外购买阻力？",

    "payment_method_data":
        "支付方式覆盖是否存在限制？",

    "inventory_delivery_data":
        "库存或配送时效是否可能影响完成购买？",

    "same_price_band_benchmark":
        "同价格带商品的转化表现是否存在明显差异？",

    "same_category_sku_comparison":
        "同品类其他商品是否存在相同问题？",

    "historical_conversion_trend":
        "当前异常是长期存在还是短期波动？",

    "traffic_source_data":
        "不同流量来源的转化是否存在结构性差异？",

    "product_page_behavior":
        "商品页行为是否显示上游转化阻力？",

    "product_content_data":
        "商品内容是否需要进一步验证？",

    "product_sessions":
        "继续积累足够的商品页访问样本。"
}


# ==================================================
# 5. 工具函数
# ==================================================

def pct(
    value
):

    if value is None:
        return "—"

    return f"{value:.2%}"


def deviation_text(
    value
):

    if value is None:
        return "—"

    return f"{value:.2%}"


def get_current_history_record(
    product_id,
    diagnosis_id
):

    history = get_product_history(
        product_id
    )

    for record in reversed(
        history
    ):

        if (
            record.get(
                "diagnosis_id"
            )
            == diagnosis_id
        ):

            return record

    return None


def get_previous_history_record(
    product_id,
    current_diagnosis_id
):

    history = get_product_history(
        product_id
    )

    current_index = None


    for index, record in enumerate(
        history
    ):

        if (
            record.get(
                "diagnosis_id"
            )
            == current_diagnosis_id
        ):

            current_index = index
            break


    if (
        current_index is None
        or current_index == 0
    ):

        return None


    return history[
        current_index - 1
    ]


# ==================================================
# 6. 完整报告业务中文展示层
# ==================================================

def businessize_report(
    report
):

    if not report:
        return report


    replacements = [

        # ======================================
        # 漏斗指标
        # ======================================

        (
            "Product→Purchase CVR",
            "商品页→购买转化率"
        ),

        (
            "Product→Cart Rate",
            "商品页→购物车转化率"
        ),

        (
            "Cart→Purchase Rate",
            "购物车→购买转化率"
        ),

        (
            "Product→Purchase",
            "商品页→购买"
        ),

        (
            "Product→Cart",
            "商品页→购物车"
        ),

        (
            "Cart→Purchase",
            "购物车→购买"
        ),


        # ======================================
        # Benchmark / Sessions
        # ======================================

        (
            "Category Benchmark",
            "品类基准"
        ),

        (
            "Category CVR",
            "品类购买转化率"
        ),

        (
            "Product Sessions",
            "商品页访问样本数"
        ),

        (
            "Product ID",
            "商品 ID"
        ),


        # ======================================
        # Action字段
        # ======================================

        (
            "same_category_sku_comparison",
            "同品类商品对比"
        ),

        (
            "same_price_band_benchmark",
            "同价格带商品对比"
        ),

        (
            "historical_conversion_trend",
            "历史转化趋势"
        ),

        (
            "checkout_step_funnel",
            "结账步骤漏斗"
        ),

        (
            "cart_abandon_reason",
            "购物车放弃原因"
        ),

        (
            "shipping_tax_data",
            "运费与税费数据"
        ),

        (
            "payment_method_data",
            "支付方式数据"
        ),

        (
            "inventory_delivery_data",
            "库存与配送数据"
        ),

        (
            "traffic_source_data",
            "流量来源数据"
        ),

        (
            "product_page_behavior",
            "商品页行为数据"
        ),

        (
            "product_content_data",
            "商品内容数据"
        ),

        (
            "expand_investigation",
            "扩大调查范围"
        ),

        (
            "monitor_after_improvement",
            "改善后持续监控"
        ),

        (
            "escalate_investigation",
            "升级调查"
        ),

        (
            "collect_validation_data",
            "补充验证数据"
        ),

        (
            "collect_more_sessions",
            "继续积累样本"
        ),

        (
            "collect_data",
            "收集诊断数据"
        ),

        (
            "manual_review",
            "人工复核"
        ),

        (
            "cart_to_purchase",
            "购物车→购买"
        ),

        (
            "product_to_cart",
            "商品页→购物车"
        ),


        # ======================================
        # State字段
        # ======================================

        (
            "next_action",
            "下一步行动"
        ),

        (
            "required_data",
            "所需数据"
        ),

        (
            "target_stage",
            "目标阶段"
        ),

        (
            "action_type",
            "行动类型"
        ),

        (
            "priority",
            "优先级"
        ),

        (
            "reason",
            "规则依据"
        ),

        (
            "goal",
            "行动目标"
        ),

        (
            "State",
            "诊断状态数据"
        ),


        # ======================================
        # 状态
        # ======================================

        (
            "insufficient_data",
            "数据不足"
        ),

        (
            "severe",
            "严重异常"
        ),

        (
            "normal",
            "正常区间"
        ),

        (
            "pending",
            "待执行"
        ),

        (
            "in_progress",
            "执行中"
        ),

        (
            "completed",
            "已完成"
        ),

        (
            "validated",
            "已验证"
        ),

        (
            "unchanged",
            "无变化"
        ),

        (
            "worsened",
            "恶化"
        ),

        (
            "improved",
            "改善"
        ),


        # ======================================
        # 常见展示词
        # ======================================

        (
            "SKU",
            "当前商品"
        ),

        (
            "Category",
            "品类"
        ),

        (
            "CVR deviation",
            "购买转化率相对偏离"
        ),

        (
            "deviation",
            "相对偏离"
        )
    ]


    translated = report


    for old, new in replacements:

        translated = translated.replace(
            old,
            new
        )


    return translated


# ==================================================
# 7. 诊断结论
# ==================================================

def build_diagnosis_summary(
    result
):

    status = result.get(
        "status"
    )

    weak_stage = result.get(
        "weak_stage"
    )

    purchase_cvr = result.get(
        "purchase_cvr"
    )

    category_cvr = result.get(
        "category_cvr"
    )

    cvr_deviation = result.get(
        "cvr_deviation"
    )


    # ==========================================
    # 数据不足
    # ==========================================

    if status == "insufficient_data":

        return {
            "headline":
                "当前数据不足，暂不能进行可靠的异常诊断。",

            "evidence":
                (
                    f"当前商品页访问样本为 "
                    f"{result.get('product_sessions')}，"
                    f"尚未达到最低诊断门槛 20。"
                ),

            "location":
                (
                    "本轮不定位具体异常阶段，"
                    "也不判断价格或其他可能原因。"
                ),

            "boundary":
                (
                    "待商品页访问样本累计至至少 20 后，"
                    "重新运行诊断。"
                )
        }


    # ==========================================
    # 正常
    # ==========================================

    if status == "normal":

        return {
            "headline":
                (
                    "当前整体购买转化表现"
                    "未触发本 Agent 的异常诊断阈值。"
                ),

            "evidence":
                (
                    f"当前商品购买转化率为 "
                    f"{pct(purchase_cvr)}，"
                    f"品类基准为 "
                    f"{pct(category_cvr)}。"
                ),

            "location":
                (
                    "本轮没有进入深度异常诊断路径，"
                    "因此不对某一子漏斗阶段进行异常定位。"
                ),

            "boundary":
                (
                    "未触发当前规则不代表商品不存在其他业务问题。"
                )
        }


    # ==========================================
    # low / severe
    # ==========================================

    headline = (
        f"当前商品整体购买转化表现"
        f"已达到{STATUS_MAP.get(status, status)}标准。"
    )


    evidence = (
        f"购买转化率为 "
        f"{pct(purchase_cvr)}，"
        f"品类基准为 "
        f"{pct(category_cvr)}，"
        f"相对偏离 "
        f"{deviation_text(cvr_deviation)}。"
    )


    if weak_stage == "cart_to_purchase":

        location = (
            "进一步拆解漏斗后，"
            "主要问题定位在「购物车 → 购买」阶段。"
            f"该阶段相对品类基准偏离 "
            f"{deviation_text(result.get('cart_to_purchase_deviation'))}，"
            "达到当前子漏斗异常判定标准。"
            "商品页 → 购物车虽然低于品类水平，"
            "但尚未达到当前异常阈值。"
        )


    elif weak_stage == "product_to_cart":

        location = (
            "进一步拆解漏斗后，"
            "主要问题定位在「商品页 → 购物车」阶段。"
            f"该阶段相对品类基准偏离 "
            f"{deviation_text(result.get('product_to_cart_deviation'))}，"
            "达到当前异常判定标准。"
        )


    elif weak_stage == "both":

        location = (
            "商品页 → 购物车和购物车 → 购买"
            "两个阶段均达到当前异常标准，"
            "说明问题同时存在于漏斗上游和下游。"
        )


    else:

        location = (
            "整体购买转化率已经触发异常，"
            "但当前子漏斗规则还没有定位出"
            "明确的主要异常阶段。"
        )


    boundary = (
        "当前数据能够确认异常状态和异常阶段，"
        "但现有证据不足以确定因果原因。"
        "具体原因仍需结合后续数据继续验证。"
    )


    return {
        "headline":
            headline,

        "evidence":
            evidence,

        "location":
            location,

        "boundary":
            boundary
    }


# ==================================================
# 8. 页面顶部
# ==================================================

st.title(
    "📊 电商转化率诊断 Agent"
)

st.caption(
    "基于商品转化漏斗、品类基准、价格位置和历史反馈，"
    "定位转化异常并生成下一步行动。"
)


with st.form(
    "diagnosis_form"
):

    input_col, button_col = st.columns(
        [4, 1]
    )


    with input_col:

        product_id = st.number_input(
            "商品 ID",
            min_value=1,
            value=7498,
            step=1
        )


    with button_col:

        st.write("")
        st.write("")

        submit = st.form_submit_button(
            "开始诊断",
            width="stretch"
        )


# ==================================================
# 9. 执行诊断
# ==================================================

if submit:

    with st.spinner(
        "Agent 正在分析商品转化表现..."
    ):

        try:

            result = diagnose_product(
                int(product_id)
            )

            st.session_state[
                "diagnosis_result"
            ] = result


        except Exception as e:

            st.error(
                f"诊断失败：{e}"
            )


# ==================================================
# 10. 尚未诊断
# ==================================================

if (
    "diagnosis_result"
    not in st.session_state
):

    st.info(
        "输入商品 ID 后点击“开始诊断”。"
    )

    st.stop()


result = st.session_state[
    "diagnosis_result"
]


# ==================================================
# 11. 当前正式业务History
# ==================================================

current_record = get_current_history_record(
    product_id=
        result.get(
            "product_id"
        ),

    diagnosis_id=
        result.get(
            "diagnosis_id"
        )
)


action_status = (
    current_record.get(
        "action_status"
    )
    if current_record
    else None
)


# ==================================================
# ① 商品 + 诊断总览
# ==================================================

st.markdown(
    '<div class="section-title">'
    '① 商品 + 诊断总览'
    '</div>',
    unsafe_allow_html=True
)


st.subheader(
    result.get(
        "product_name"
    )
    or "未知商品"
)


st.caption(
    f'商品 ID：{result.get("product_id")} '
    f'｜ 品类：{result.get("category")}'
)


# ==================================================
# 第一行：核心状态
# ==================================================

overview_row1 = st.columns(
    3
)


with overview_row1[0]:

    st.metric(
        "诊断状态",
        STATUS_MAP.get(
            result.get(
                "status"
            ),
            "—"
        )
    )


with overview_row1[1]:

    st.metric(
        "购买转化率",
        pct(
            result.get(
                "purchase_cvr"
            )
        )
    )


with overview_row1[2]:

    st.metric(
        "品类基准",
        pct(
            result.get(
                "category_cvr"
            )
        )
    )


# ==================================================
# 第二行：问题定位
# ==================================================

overview_row2 = st.columns(
    3
)


with overview_row2[0]:

    st.metric(
        "主要弱环节",
        STAGE_MAP.get(
            result.get(
                "weak_stage"
            ),
            "—"
        )
    )


with overview_row2[1]:

    st.metric(
        "价格状态",
        PRICE_MAP.get(
            result.get(
                "price_status"
            ),
            "—"
        )
    )


with overview_row2[2]:

    st.metric(
        "行动状态",
        ACTION_STATUS_MAP.get(
            action_status,
            "—"
        )
    )


# ==================================================
# ② 核心转化漏斗
# ==================================================

st.markdown(
    '<div class="section-title">'
    '② 核心转化漏斗'
    '</div>',
    unsafe_allow_html=True
)


st.caption(
    "当前商品与同品类转化水平对比。"
)


funnel_rows = []


funnel_configs = [
    (
        "商品页 → 购物车",
        result.get(
            "cart_rate"
        ),
        result.get(
            "category_cart_rate"
        )
    ),

    (
        "购物车 → 购买",
        result.get(
            "cart_to_purchase_rate"
        ),
        result.get(
            "category_cart_to_purchase_rate"
        )
    ),

    (
        "商品页 → 购买",
        result.get(
            "purchase_cvr"
        ),
        result.get(
            "category_cvr"
        )
    )
]


for (
    stage,
    sku_value,
    benchmark_value
) in funnel_configs:

    if sku_value is not None:

        funnel_rows.append(
            {
                "阶段":
                    stage,

                "对比对象":
                    "当前商品",

                "转化率":
                    sku_value
                    * 100,

                "显示值":
                    f"{sku_value:.2%}"
            }
        )


    if benchmark_value is not None:

        funnel_rows.append(
            {
                "阶段":
                    stage,

                "对比对象":
                    "品类基准",

                "转化率":
                    benchmark_value
                    * 100,

                "显示值":
                    f"{benchmark_value:.2%}"
            }
        )


funnel_df = pd.DataFrame(
    funnel_rows
)


stage_order = [
    "商品页 → 购物车",
    "购物车 → 购买",
    "商品页 → 购买"
]


base_chart = (
    alt.Chart(
        funnel_df
    )
    .encode(

        y=alt.Y(
            "阶段:N",
            sort=stage_order,
            title=None
        ),

        yOffset=
            "对比对象:N",

        x=alt.X(
            "转化率:Q",
            title="转化率（%）",
            scale=alt.Scale(
                zero=True
            )
        ),

        color=alt.Color(
            "对比对象:N",
            title=None
        )
    )
)


bar_chart = (
    base_chart
    .mark_bar(
        size=18
    )
)


text_chart = (
    base_chart
    .mark_text(
        align="left",
        baseline="middle",
        dx=5
    )
    .encode(
        text=
            "显示值:N"
    )
)


funnel_chart = (
    bar_chart
    +
    text_chart
).properties(
    height=240
)


st.altair_chart(
    funnel_chart,
    width="stretch"
)


# ==================================================
# 漏斗指标
# 不使用st.metric delta
# 避免负偏离显示绿色向上箭头
# ==================================================

detail_cols = st.columns(
    3
)


with detail_cols[0]:

    st.metric(
        "商品页 → 购物车",
        pct(
            result.get(
                "cart_rate"
            )
        )
    )

    st.caption(
        "相对品类："
        +
        deviation_text(
            result.get(
                "product_to_cart_deviation"
            )
        )
    )


with detail_cols[1]:

    st.metric(
        "购物车 → 购买",
        pct(
            result.get(
                "cart_to_purchase_rate"
            )
        )
    )

    st.caption(
        "相对品类："
        +
        deviation_text(
            result.get(
                "cart_to_purchase_deviation"
            )
        )
    )


with detail_cols[2]:

    st.metric(
        "商品页 → 购买",
        pct(
            result.get(
                "purchase_cvr"
            )
        )
    )

    st.caption(
        "相对品类："
        +
        deviation_text(
            result.get(
                "cvr_deviation"
            )
        )
    )


weak_stage = result.get(
    "weak_stage"
)


if weak_stage not in [
    None,
    "none"
]:

    st.warning(
        "当前主要异常阶段："
        +
        STAGE_MAP.get(
            weak_stage,
            "—"
        )
    )


# ==================================================
# 外部行业参考
# ==================================================

industry_reference = (
    result.get(
        "industry_reference"
    )
)


if industry_reference:

    with st.expander(
        "查看外部行业参考"
    ):

        st.write(
            industry_reference
        )

        st.caption(
            "外部行业数据与当前数据集统计口径不同，"
            "仅作为背景参考，"
            "不参与当前异常阈值判断。"
        )


# ==================================================
# ③ 诊断结论
# ==================================================

st.markdown(
    '<div class="section-title">'
    '③ 诊断结论'
    '</div>',
    unsafe_allow_html=True
)


diagnosis_summary = (
    build_diagnosis_summary(
        result
    )
)


with st.container(
    border=True
):

    st.markdown(
        "#### 诊断判断"
    )

    st.write(
        diagnosis_summary[
            "headline"
        ]
    )


    st.markdown(
        "**判断依据**"
    )

    st.write(
        diagnosis_summary[
            "evidence"
        ]
    )


    st.markdown(
        "**问题定位**"
    )

    st.write(
        diagnosis_summary[
            "location"
        ]
    )


    st.markdown(
        "**当前判断边界**"
    )

    st.write(
        diagnosis_summary[
            "boundary"
        ]
    )

# ==================================================
# ④ 可能影响因素
# ==================================================

st.markdown(
    '<div class="section-title">'
    '④ 可能影响因素（待验证）'
    '</div>',
    unsafe_allow_html=True
)


status = result.get(
    "status"
)


if status in [
    "low",
    "severe"
]:

    evidence_col, verify_col = st.columns(
        2
    )


    with evidence_col:

        with st.container(
            border=True
        ):

            st.markdown(
                "#### 当前已经确认"
            )

            st.write(
                "✓ 整体转化状态："
                +
                STATUS_MAP.get(
                    status,
                    "—"
                )
            )

            st.write(
                "✓ 主要异常阶段："
                +
                STAGE_MAP.get(
                    result.get(
                        "weak_stage"
                    ),
                    "—"
                )
            )

            st.write(
                "✓ 当前价格位置："
                +
                PRICE_MAP.get(
                    result.get(
                        "price_status"
                    ),
                    "—"
                )
            )


    with verify_col:

        with st.container(
            border=True
        ):

            st.markdown(
                "#### 下一步需要验证"
            )


            effective_action = (
                result.get(
                    "effective_action"
                )
                or {}
            )


            required_data = (
                effective_action.get(
                    "required_data",
                    []
                )
            )


            if required_data:

                for item in required_data:

                    st.write(
                        "• "
                        +
                        DATA_QUESTION_MAP.get(
                            item,
                            DATA_MAP.get(
                                item,
                                item
                            )
                        )
                    )


            else:

                st.write(
                    "当前暂无额外验证项。"
                )


elif status == "normal":

    st.info(
        "当前商品未进入深度异常诊断路径，"
        "因此本轮不生成异常原因假设。"
    )


else:

    st.info(
        "当前样本不足，暂不进行原因分析。"
    )


# ==================================================
# ⑤ 下一步行动
# ==================================================

st.markdown(
    '<div class="section-title">'
    '⑤ 下一步行动'
    '</div>',
    unsafe_allow_html=True
)


effective_action = (
    result.get(
        "effective_action"
    )
    or {}
)


action_type = (
    effective_action.get(
        "action_type"
    )
)


target_stage = (
    effective_action.get(
        "target_stage"
    )
)


action_cols = st.columns(
    4
)


with action_cols[0]:

    st.metric(
        "优先级",
        effective_action.get(
            "priority"
        )
        or "—"
    )


with action_cols[1]:

    st.metric(
        "行动类型",
        ACTION_TYPE_MAP.get(
            action_type,
            action_type or "—"
        )
    )


with action_cols[2]:

    st.metric(
        "目标阶段",
        STAGE_MAP.get(
            target_stage,
            target_stage or "—"
        )
    )


with action_cols[3]:

    st.metric(
        "当前状态",
        ACTION_STATUS_MAP.get(
            action_status,
            "—"
        )
    )


with st.container(
    border=True
):

    st.markdown(
        "#### 为什么做"
    )

    st.write(
        effective_action.get(
            "reason"
        )
        or "—"
    )


    st.markdown(
        "#### 希望解决什么"
    )

    st.write(
        effective_action.get(
            "goal"
        )
        or "—"
    )


st.markdown(
    "#### 需要补充的数据"
)


required_data = (
    effective_action.get(
        "required_data",
        []
    )
)


if required_data:

    data_cols = st.columns(
        min(
            3,
            len(
                required_data
            )
        )
    )


    for index, item in enumerate(
        required_data
    ):

        with data_cols[
            index
            %
            len(
                data_cols
            )
        ]:

            st.info(
                DATA_MAP.get(
                    item,
                    item
                )
            )


else:

    st.write(
        "当前行动无需补充额外数据。"
    )


# ==================================================
# 行动执行
# ==================================================

st.markdown(
    "#### 行动执行"
)


if current_record is None:

    st.warning(
        "当前未找到对应的诊断历史记录，"
        "暂时无法更新行动状态。"
    )


elif action_status == "pending":

    st.write(
        "当前行动尚未开始执行。"
    )


    if st.button(
        "▶ 开始执行",
        width="stretch"
    ):

        update_action_status(
            diagnosis_id=
                current_record[
                    "diagnosis_id"
                ],

            new_status=
                "in_progress"
        )

        st.rerun()


elif action_status == "in_progress":

    st.info(
        "当前行动正在执行中。"
    )


    if st.button(
        "✓ 标记为已完成",
        width="stretch"
    ):

        update_action_status(
            diagnosis_id=
                current_record[
                    "diagnosis_id"
                ],

            new_status=
                "completed"
        )

        st.rerun()


elif action_status == "completed":

    st.success(
        "当前行动已经执行完成。"
    )

    st.info(
        "下一步：等待新的业务数据后，"
        "再次点击页面顶部的「开始诊断」。"
        "系统会使用新的诊断结果验证上一轮行动效果。"
    )


elif action_status == "validated":

    validation_result = (
        current_record.get(
            "validation_result"
        )
    )

    st.success(
        "当前行动已经完成效果验证。"
    )

    st.write(
        "验证结果："
        +
        VALIDATION_MAP.get(
            validation_result,
            validation_result
            or "无法判断"
        )
    )


else:

    st.warning(
        "当前行动状态无法识别。"
    )


# ==================================================
# 底部：诊断历史与闭环
# ==================================================

st.divider()


with st.expander(
    "🔄 查看诊断历史与闭环"
):

    history = get_product_history(
        result.get(
            "product_id"
        )
    )


    previous_record = (
        get_previous_history_record(
            product_id=
                result.get(
                    "product_id"
                ),

            current_diagnosis_id=
                result.get(
                    "diagnosis_id"
                )
        )
    )


    comparison = (
        result.get(
            "comparison"
        )
        or {}
    )


    validation_result = (
        result.get(
            "validation_result"
        )
    )


    current_effective_action = (
        result.get(
            "effective_action"
        )
        or {}
    )


    # ==================================================
    # A. 本轮闭环
    # ==================================================

    st.markdown(
        "### 本轮闭环"
    )


    # ==========================================
    # 首次正式诊断
    # ==========================================

    if previous_record is None:

        st.info(
            "当前为首次正式业务诊断。"
            "完成当前行动并进行下一次复诊后，"
            "这里会形成完整的闭环验证流程。"
        )


        first_cols = st.columns(
            3
        )


        with first_cols[0]:

            with st.container(
                border=True
            ):

                st.caption(
                    "① 当前诊断"
                )

                st.markdown(
                    "### "
                    +
                    STATUS_MAP.get(
                        result.get(
                            "status"
                        ),
                        "—"
                    )
                )

                st.write(
                    "主要异常阶段"
                )

                st.write(
                    STAGE_MAP.get(
                        result.get(
                            "weak_stage"
                        ),
                        "—"
                    )
                )


        with first_cols[1]:

            with st.container(
                border=True
            ):

                st.caption(
                    "② 当前行动"
                )

                first_action_type = (
                    current_effective_action.get(
                        "action_type"
                    )
                )

                st.markdown(
                    "### "
                    +
                    ACTION_TYPE_MAP.get(
                        first_action_type,
                        first_action_type
                        or "—"
                    )
                )

                st.write(
                    "目标阶段"
                )

                st.write(
                    STAGE_MAP.get(
                        current_effective_action.get(
                            "target_stage"
                        ),
                        "—"
                    )
                )


        with first_cols[2]:

            with st.container(
                border=True
            ):

                st.caption(
                    "③ 执行状态"
                )

                st.markdown(
                    "### "
                    +
                    ACTION_STATUS_MAP.get(
                        action_status,
                        "—"
                    )
                )

                st.write(
                    "完成后等待新数据，"
                    "再次进行诊断。"
                )


    # ==========================================
    # 已有上一轮诊断
    # ==========================================

    else:

        previous_action = (
            previous_record.get(
                "effective_action"
            )
            or previous_record.get(
                "next_round_action"
            )
            or previous_record.get(
                "next_action"
            )
            or {}
        )


        previous_action_type = (
            previous_action.get(
                "action_type"
            )
        )


        current_action_type = (
            current_effective_action.get(
                "action_type"
            )
        )


        previous_status = (
            comparison.get(
                "previous_status"
            )
        )


        current_status = (
            comparison.get(
                "current_status"
            )
        )


        previous_cvr = (
            previous_record.get(
                "purchase_cvr"
            )
        )


        current_cvr = (
            result.get(
                "purchase_cvr"
            )
        )


        # ==========================================
        # 已形成效果验证
        # ==========================================

        if validation_result is not None:

            flow_cols = st.columns(
                [
                    1.3,
                    0.25,
                    1.3,
                    0.25,
                    1.3,
                    0.25,
                    1.3,
                    0.25,
                    1.3
                ]
            )


            # ----------------------------------
            # 1. 上一轮行动
            # ----------------------------------

            with flow_cols[0]:

                with st.container(
                    border=True
                ):

                    st.caption(
                        "① 上一轮行动"
                    )

                    st.markdown(
                        "### "
                        +
                        ACTION_TYPE_MAP.get(
                            previous_action_type,
                            previous_action_type
                            or "—"
                        )
                    )

                    st.write(
                        "目标阶段"
                    )

                    st.write(
                        STAGE_MAP.get(
                            previous_action.get(
                                "target_stage"
                            ),
                            "—"
                        )
                    )


            with flow_cols[1]:

                st.markdown(
                    "<div style='"
                    "font-size:28px;"
                    "text-align:center;"
                    "padding-top:55px;'>"
                    "→"
                    "</div>",
                    unsafe_allow_html=True
                )


            # ----------------------------------
            # 2. 行动执行
            # ----------------------------------

            with flow_cols[2]:

                with st.container(
                    border=True
                ):

                    st.caption(
                        "② 行动执行"
                    )

                    st.markdown(
                        "### 已完成"
                    )

                    st.write(
                        "上一轮行动已执行完成，"
                        "并进入复诊验证。"
                    )


            with flow_cols[3]:

                st.markdown(
                    "<div style='"
                    "font-size:28px;"
                    "text-align:center;"
                    "padding-top:55px;'>"
                    "→"
                    "</div>",
                    unsafe_allow_html=True
                )


            # ----------------------------------
            # 3. 本轮复诊
            # ----------------------------------

            with flow_cols[4]:

                with st.container(
                    border=True
                ):

                    st.caption(
                        "③ 本轮复诊"
                    )

                    st.markdown(
                        "### "
                        +
                        STATUS_MAP.get(
                            previous_status,
                            "—"
                        )
                        +
                        " → "
                        +
                        STATUS_MAP.get(
                            current_status,
                            "—"
                        )
                    )


                    if (
                        previous_cvr is not None
                        and current_cvr is not None
                    ):

                        st.write(
                            "购买转化率"
                        )

                        st.write(
                            f"{previous_cvr:.2%}"
                            " → "
                            f"{current_cvr:.2%}"
                        )


            with flow_cols[5]:

                st.markdown(
                    "<div style='"
                    "font-size:28px;"
                    "text-align:center;"
                    "padding-top:55px;'>"
                    "→"
                    "</div>",
                    unsafe_allow_html=True
                )


            # ----------------------------------
            # 4. 效果验证
            # ----------------------------------

            with flow_cols[6]:

                with st.container(
                    border=True
                ):

                    st.caption(
                        "④ 效果验证"
                    )

                    validation_text = (
                        VALIDATION_MAP.get(
                            validation_result,
                            validation_result
                            or "—"
                        )
                    )


                    st.markdown(
                        "### "
                        +
                        validation_text
                    )


                    if validation_result == "improved":

                        st.write(
                            "上一轮行动后，"
                            "转化表现出现改善。"
                        )


                    elif validation_result == "unchanged":

                        st.write(
                            "上一轮行动后，"
                            "暂未观察到转化改善。"
                        )


                    elif validation_result == "worsened":

                        st.write(
                            "上一轮行动后，"
                            "转化表现进一步恶化。"
                        )


                    else:

                        st.write(
                            "当前数据不足以判断"
                            "上一轮行动效果。"
                        )


            with flow_cols[7]:

                st.markdown(
                    "<div style='"
                    "font-size:28px;"
                    "text-align:center;"
                    "padding-top:55px;'>"
                    "→"
                    "</div>",
                    unsafe_allow_html=True
                )


            # ----------------------------------
            # 5. 当前策略
            # ----------------------------------

            with flow_cols[8]:

                with st.container(
                    border=True
                ):

                    st.caption(
                        "⑤ 当前策略"
                    )

                    st.markdown(
                        "### "
                        +
                        ACTION_TYPE_MAP.get(
                            current_action_type,
                            current_action_type
                            or "—"
                        )
                    )

                    st.write(
                        "当前状态"
                    )

                    st.write(
                        ACTION_STATUS_MAP.get(
                            action_status,
                            "—"
                        )
                    )


            # ==================================
            # 本轮闭环总结
            # ==================================

            st.markdown(
                "#### 本轮闭环结论"
            )


            if validation_result == "improved":

                st.success(
                    "上一轮行动后转化表现改善。"
                    "当前策略调整为持续观察，"
                    "确认改善是否能够稳定保持。"
                )


            elif validation_result == "unchanged":

                st.warning(
                    "上一轮行动已经完成，"
                    "但本轮复诊未观察到转化改善。"
                    "因此系统已扩大调查范围，"
                    "继续定位尚未被当前证据解释的转化阻力。"
                )


            elif validation_result == "worsened":

                st.error(
                    "本轮复诊显示转化表现进一步恶化。"
                    "系统已提高调查优先级并升级调查范围。"
                )


            elif validation_result == "unknown":

                st.info(
                    "当前数据不足以判断上一轮行动效果。"
                    "下一步需要补充验证数据后再次复诊。"
                )


        # ==========================================
        # 尚未形成验证
        # ==========================================

        else:

            st.info(
                "当前存在历史诊断记录，"
                "但尚未形成新的行动效果验证结果。"
            )


            pending_cols = st.columns(
                3
            )


            with pending_cols[0]:

                with st.container(
                    border=True
                ):

                    st.caption(
                        "上一轮"
                    )

                    st.markdown(
                        "### "
                        +
                        STATUS_MAP.get(
                            previous_status,
                            "—"
                        )
                    )


            with pending_cols[1]:

                with st.container(
                    border=True
                ):

                    st.caption(
                        "本轮"
                    )

                    st.markdown(
                        "### "
                        +
                        STATUS_MAP.get(
                            current_status,
                            "—"
                        )
                    )


            with pending_cols[2]:

                with st.container(
                    border=True
                ):

                    st.caption(
                        "效果验证"
                    )

                    st.markdown(
                        "### 尚未验证"
                    )

                    st.write(
                        "需先完成上一轮行动，"
                        "再通过新的业务数据进行复诊。"
                    )


    # ==================================================
    # B. 历史购买转化率趋势
    # ==================================================

    st.markdown(
        "### 购买转化率历史趋势"
    )


    if len(
        history
    ) < 2:

        st.info(
            "至少需要两轮正式业务诊断后，"
            "才能展示历史变化趋势。"
        )


    else:

        chart_history = history[
            -12:
        ]


        total_count = len(
            history
        )


        start_round = (
            total_count
            -
            len(
                chart_history
            )
            +
            1
        )


        trend_rows = []


        for index, record in enumerate(
            chart_history
        ):

            round_number = (
                start_round
                +
                index
            )


            purchase_cvr = (
                record.get(
                    "purchase_cvr"
                )
            )


            category_cvr = (
                record.get(
                    "category_cvr"
                )
            )


            if purchase_cvr is not None:

                trend_rows.append(
                    {
                        "诊断轮次":
                            round_number,

                        "指标":
                            "当前商品",

                        "转化率":
                            purchase_cvr
                            *
                            100
                    }
                )


            if category_cvr is not None:

                trend_rows.append(
                    {
                        "诊断轮次":
                            round_number,

                        "指标":
                            "品类基准",

                        "转化率":
                            category_cvr
                            *
                            100
                    }
                )


        trend_df = pd.DataFrame(
            trend_rows
        )


        trend_chart = (
            alt.Chart(
                trend_df
            )
            .mark_line(
                point=True
            )
            .encode(

                x=alt.X(
                    "诊断轮次:Q",

                    title=
                        "诊断轮次",

                    axis=alt.Axis(
                        tickMinStep=1,
                        labelAngle=0
                    )
                ),

                y=alt.Y(
                    "转化率:Q",

                    title=
                        "购买转化率（%）",

                    scale=alt.Scale(
                        zero=True
                    )
                ),

                color=alt.Color(
                    "指标:N",
                    title=None
                ),

                tooltip=[
                    alt.Tooltip(
                        "诊断轮次:Q",
                        title="诊断轮次",
                        format=".0f"
                    ),

                    alt.Tooltip(
                        "指标:N",
                        title="指标"
                    ),

                    alt.Tooltip(
                        "转化率:Q",
                        title="转化率",
                        format=".2f"
                    )
                ]
            )
            .properties(
                height=320
            )
        )


        st.altair_chart(
            trend_chart,
            width="stretch"
        )


        sku_values = [
            record.get(
                "purchase_cvr"
            )

            for record in chart_history

            if record.get(
                "purchase_cvr"
            )
            is not None
        ]


        if (
            sku_values
            and len(
                set(
                    sku_values
                )
            )
            == 1
        ):

            st.caption(
                "最近几轮正式诊断中，"
                "购买转化率没有发生变化，"
                "因此当前商品趋势线保持水平。"
            )


    # ==================================================
    # C. 历史轮次
    # ==================================================

    st.markdown(
        "### 历史轮次"
    )


    if not history:

        st.write(
            "暂无正式业务历史。"
        )


    else:

        display_history = history[
            -6:
        ]


        total_count = len(
            history
        )


        start_round = (
            total_count
            -
            len(
                display_history
            )
            +
            1
        )


        for index, record in enumerate(
            display_history
        ):

            round_number = (
                start_round
                +
                index
            )


            record_action = (
                record.get(
                    "effective_action"
                )
                or record.get(
                    "next_round_action"
                )
                or record.get(
                    "next_action"
                )
                or {}
            )


            history_action_type = (
                record_action.get(
                    "action_type"
                )
            )


            diagnosed_at = (
                record.get(
                    "diagnosed_at"
                )
                or ""
            )


            try:

                time_text = (
                    pd.to_datetime(
                        diagnosed_at
                    )
                    .strftime(
                        "%Y-%m-%d %H:%M"
                    )
                )

            except Exception:

                time_text = diagnosed_at


            with st.container(
                border=True
            ):

                header_cols = st.columns(
                    [1, 4]
                )


                with header_cols[0]:

                    st.markdown(
                        f"**第 {round_number} 轮**"
                    )


                with header_cols[1]:

                    st.caption(
                        time_text
                    )


                history_cols = st.columns(
                    4
                )


                with history_cols[0]:

                    st.caption(
                        "诊断结果"
                    )

                    st.write(
                        STATUS_MAP.get(
                            record.get(
                                "status"
                            ),
                            "—"
                        )
                    )


                with history_cols[1]:

                    st.caption(
                        "最终行动"
                    )

                    st.write(
                        ACTION_TYPE_MAP.get(
                            history_action_type,
                            history_action_type
                            or "—"
                        )
                    )


                with history_cols[2]:

                    st.caption(
                        "行动状态"
                    )

                    st.write(
                        ACTION_STATUS_MAP.get(
                            record.get(
                                "action_status"
                            ),
                            "—"
                        )
                    )


                with history_cols[3]:

                    st.caption(
                        "验证结果"
                    )

                    st.write(
                        VALIDATION_MAP.get(
                            record.get(
                                "validation_result"
                            ),
                            "尚未验证"
                        )
                    )

# ==================================================
# 完整诊断报告
# ==================================================

final_report = result.get(
    "final_report"
)


if final_report:

    with st.expander(
        "📄 查看完整诊断报告"
    ):

        st.markdown(
            businessize_report(
                final_report
            )
        )
