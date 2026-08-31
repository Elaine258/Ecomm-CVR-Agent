import os
import json
import uuid

from datetime import datetime
from dotenv import load_dotenv


load_dotenv()

ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        ".."
    )
)

DATA_DIR = os.path.abspath(
    os.getenv(
        "ECOMM_DATA_DIR",
        os.path.join(ROOT, "data")
    )
)

HISTORY_PATH = os.path.join(
    DATA_DIR,
    "diagnosis_history.jsonl"
)


# ==================================================
# 1. 保存诊断历史
# ==================================================

def save_diagnosis_history(
    result: dict
) -> dict:

    """
    保存一次诊断记录。

    JSONL：
    每一行代表一次独立诊断。
    """

    record = {
        "diagnosis_id":
            str(uuid.uuid4()),

        "diagnosed_at":
            datetime.now().isoformat(
                timespec="seconds"
            ),

        "product_id":
            result.get(
                "product_id"
            ),

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
                "status"
            ),

        "severity":
            result.get(
                "severity"
            ),

        "product_sessions":
            result.get(
                "product_sessions"
            ),

        "purchase_cvr":
            result.get(
                "purchase_cvr"
            ),

        "category_cvr":
            result.get(
                "category_cvr"
            ),

        "cvr_deviation":
            result.get(
                "cvr_deviation"
            ),

        "weak_stage":
            result.get(
                "weak_stage"
            ),

        "price_status":
            result.get(
                "price_status"
            ),

        "next_action":
            result.get(
                "next_action"
            ),

        "next_round_action":
            result.get(
                "next_round_action"
            ),

        "effective_action":
            result.get(
                "effective_action"
            ),

        "action_status":
            "pending"
    }


    os.makedirs(
        DATA_DIR,
        exist_ok=True
    )


    with open(
        HISTORY_PATH,
        "a",
        encoding="utf-8"
    ) as f:

        f.write(
            json.dumps(
                record,
                ensure_ascii=False
            )
            + "\n"
        )


    return record


# ==================================================
# 2. 获取商品历史
# ==================================================

def get_product_history(
    product_id: int
) -> list:

    """
    获取某个商品的全部历史诊断记录。
    """

    if not os.path.exists(
        HISTORY_PATH
    ):
        return []


    records = []


    with open(
        HISTORY_PATH,
        "r",
        encoding="utf-8"
    ) as f:

        for line in f:

            line = line.strip()

            if not line:
                continue


            record = json.loads(
                line
            )


            if (
                record.get("product_id")
                == product_id
            ):
                records.append(
                    record
                )


    records.sort(
        key=lambda x:
            x.get(
                "diagnosed_at",
                ""
            )
    )


    return records


# ==================================================
# 3. 获取上一条诊断
# ==================================================

def get_previous_diagnosis(
    product_id: int,
    current_diagnosis_id: str
):

    """
    获取当前诊断之前最近的一次诊断。
    """

    records = get_product_history(
        product_id
    )


    previous_records = [
        record
        for record in records
        if record.get(
            "diagnosis_id"
        )
        != current_diagnosis_id
    ]


    if not previous_records:
        return None


    return previous_records[-1]


# ==================================================
# 4. Diagnosis Comparison
# 前后诊断对比
# ==================================================

def compare_diagnosis(
    current: dict,
    previous: dict | None
) -> dict:

    """
    比较当前诊断与上一次诊断。
    """

    if previous is None:

        return {
            "has_previous":
                False,

            "status_changed":
                False,

            "previous_status":
                None,

            "current_status":
                current.get(
                    "status"
                ),

            "purchase_cvr_change":
                None,

            "cvr_deviation_change":
                None,

            "weak_stage_changed":
                False,

            "previous_weak_stage":
                None,

            "current_weak_stage":
                current.get(
                    "weak_stage"
                )
        }


    current_cvr = current.get(
        "purchase_cvr"
    )

    previous_cvr = previous.get(
        "purchase_cvr"
    )


    if (
        current_cvr is not None
        and previous_cvr is not None
    ):
        purchase_cvr_change = (
            current_cvr
            -
            previous_cvr
        )

    else:
        purchase_cvr_change = None


    current_deviation = current.get(
        "cvr_deviation"
    )

    previous_deviation = previous.get(
        "cvr_deviation"
    )


    if (
        current_deviation is not None
        and previous_deviation is not None
    ):
        cvr_deviation_change = (
            current_deviation
            -
            previous_deviation
        )

    else:
        cvr_deviation_change = None


    return {
        "has_previous":
            True,

        "status_changed":
            previous.get(
                "status"
            )
            != current.get(
                "status"
            ),

        "previous_status":
            previous.get(
                "status"
            ),

        "current_status":
            current.get(
                "status"
            ),

        "purchase_cvr_change":
            purchase_cvr_change,

        "cvr_deviation_change":
            cvr_deviation_change,

        "weak_stage_changed":
            previous.get(
                "weak_stage"
            )
            != current.get(
                "weak_stage"
            ),

        "previous_weak_stage":
            previous.get(
                "weak_stage"
            ),

        "current_weak_stage":
            current.get(
                "weak_stage"
            )
    }


# ==================================================
# 5. Follow-up Summary
# 复诊摘要
# ==================================================

def build_follow_up_summary(
    comparison: dict
) -> dict:

    """
    根据前后诊断对比结果，
    生成确定性的复诊结论。
    """

    if not comparison.get(
        "has_previous"
    ):

        return {
            "follow_up_status":
                "first_diagnosis",

            "summary":
                "当前为首次诊断，暂无历史结果可用于复诊比较。"
        }


    previous_status = comparison.get(
        "previous_status"
    )

    current_status = comparison.get(
        "current_status"
    )

    purchase_cvr_change = comparison.get(
        "purchase_cvr_change"
    )

    weak_stage_changed = comparison.get(
        "weak_stage_changed"
    )

    previous_weak_stage = comparison.get(
        "previous_weak_stage"
    )

    current_weak_stage = comparison.get(
        "current_weak_stage"
    )


    # ==========================================
    # CVR变化判断
    # ==========================================

    if purchase_cvr_change is None:

        cvr_trend = "unknown"

    elif purchase_cvr_change > 0:

        cvr_trend = "improved"

    elif purchase_cvr_change < 0:

        cvr_trend = "worsened"

    else:

        cvr_trend = "unchanged"


    # ==========================================
    # 综合复诊状态
    # ==========================================

    if (
        current_status == "normal"
        and previous_status
        in [
            "low",
            "severe"
        ]
    ):

        follow_up_status = "recovered"


    elif (
        previous_status == "severe"
        and current_status == "low"
    ):

        follow_up_status = "improved"


    elif (
        previous_status == "low"
        and current_status == "severe"
    ):

        follow_up_status = "worsened"


    elif (
        current_status
        == previous_status
        and cvr_trend == "improved"
    ):

        follow_up_status = "improved_but_same_status"


    elif (
        current_status
        == previous_status
        and cvr_trend == "worsened"
    ):

        follow_up_status = "worsened_but_same_status"


    elif (
        current_status
        == previous_status
        and cvr_trend == "unchanged"
    ):

        follow_up_status = "unchanged"


    else:

        follow_up_status = "changed"


    # ==========================================
    # 文本摘要
    # ==========================================

    summary_parts = []


    if previous_status == current_status:

        summary_parts.append(
            f"异常状态未变化，仍为 {current_status}。"
        )

    else:

        summary_parts.append(
            f"异常状态由 {previous_status} 变为 {current_status}。"
        )


    if purchase_cvr_change is None:

        summary_parts.append(
            "当前无法比较前后Purchase CVR变化。"
        )

    elif purchase_cvr_change > 0:

        summary_parts.append(
            f"Purchase CVR较上次提高 "
            f"{purchase_cvr_change:.2%}。"
        )

    elif purchase_cvr_change < 0:

        summary_parts.append(
            f"Purchase CVR较上次下降 "
            f"{abs(purchase_cvr_change):.2%}。"
        )

    else:

        summary_parts.append(
            "Purchase CVR与上次一致。"
        )


    if weak_stage_changed:

        summary_parts.append(
            f"主要弱环节由 "
            f"{previous_weak_stage} "
            f"变为 "
            f"{current_weak_stage}。"
        )

    else:

        if current_weak_stage is not None:

            summary_parts.append(
                f"主要弱环节未变化，仍为 "
                f"{current_weak_stage}。"
            )


    return {
        "follow_up_status":
            follow_up_status,

        "cvr_trend":
            cvr_trend,

        "summary":
            " ".join(
                summary_parts
            )
    }


# ==================================================
# 6. Action Status
# 行动状态更新
# ==================================================

def update_action_status(
    diagnosis_id: str,
    new_status: str
) -> dict:

    """
    更新某次诊断对应的行动状态。
    """

    allowed_status = [
        "pending",
        "in_progress",
        "completed",
        "validated"
    ]


    if new_status not in allowed_status:

        raise ValueError(
            f"不支持的action_status: {new_status}"
        )


    if not os.path.exists(
        HISTORY_PATH
    ):

        raise FileNotFoundError(
            "diagnosis_history.jsonl不存在"
        )


    records = []
    updated_record = None


    with open(
        HISTORY_PATH,
        "r",
        encoding="utf-8"
    ) as f:

        for line in f:

            line = line.strip()

            if not line:
                continue


            record = json.loads(
                line
            )


            if (
                record.get("diagnosis_id")
                == diagnosis_id
            ):

                record[
                    "action_status"
                ] = new_status

                updated_record = record


            records.append(
                record
            )


    if updated_record is None:

        raise ValueError(
            f"找不到diagnosis_id={diagnosis_id}"
        )


    with open(
        HISTORY_PATH,
        "w",
        encoding="utf-8"
    ) as f:

        for record in records:

            f.write(
                json.dumps(
                    record,
                    ensure_ascii=False
                )
                + "\n"
            )


    return updated_record


# ==================================================
# 7. Validation Result
# 效果验证结果
# ==================================================

def build_validation_result(
    comparison: dict
) -> str:

    """
    根据复诊前后对比结果，
    判断Action验证结果。

    返回：
    improved  = 改善
    unchanged = 无变化
    worsened  = 恶化
    unknown   = 无法判断
    """

    if not comparison.get(
        "has_previous"
    ):
        return "unknown"


    previous_status = comparison.get(
        "previous_status"
    )

    current_status = comparison.get(
        "current_status"
    )

    purchase_cvr_change = comparison.get(
        "purchase_cvr_change"
    )


    status_rank = {
        "normal": 0,
        "low": 1,
        "severe": 2
    }


    previous_rank = status_rank.get(
        previous_status
    )

    current_rank = status_rank.get(
        current_status
    )


    # ==========================================
    # 优先看异常等级变化
    # ==========================================

    if (
        previous_rank is not None
        and current_rank is not None
    ):

        if current_rank < previous_rank:

            return "improved"


        if current_rank > previous_rank:

            return "worsened"


    # ==========================================
    # 异常等级没变化，再看CVR
    # ==========================================

    if purchase_cvr_change is None:

        return "unknown"


    if purchase_cvr_change > 0:

        return "improved"


    if purchase_cvr_change < 0:

        return "worsened"


    return "unchanged"


# ==================================================
# 8. Validate Action
# 行动效果验证
# ==================================================

def validate_action(
    diagnosis_id: str,
    comparison: dict
) -> dict:

    """
    将某次Action标记为validated，
    并记录validation_result。
    """

    validation_result = build_validation_result(
        comparison
    )


    if not os.path.exists(
        HISTORY_PATH
    ):

        raise FileNotFoundError(
            "diagnosis_history.jsonl不存在"
        )


    records = []
    updated_record = None


    with open(
        HISTORY_PATH,
        "r",
        encoding="utf-8"
    ) as f:

        for line in f:

            line = line.strip()

            if not line:
                continue


            record = json.loads(
                line
            )


            if (
                record.get("diagnosis_id")
                == diagnosis_id
            ):

                current_action_status = record.get(
                    "action_status"
                )


                if current_action_status != "completed":

                    raise ValueError(
                        "只有completed（已完成）的Action"
                        "才能进入validated（已验证）"
                    )


                record[
                    "action_status"
                ] = "validated"

                record[
                    "validation_result"
                ] = validation_result

                updated_record = record


            records.append(
                record
            )


    if updated_record is None:

        raise ValueError(
            f"找不到diagnosis_id={diagnosis_id}"
        )


    with open(
        HISTORY_PATH,
        "w",
        encoding="utf-8"
    ) as f:

        for record in records:

            f.write(
                json.dumps(
                    record,
                    ensure_ascii=False
                )
                + "\n"
            )


    return updated_record


# ==================================================
# 9. Next Round Action
# 下一轮行动
# ==================================================

def build_next_round_action(
    validation_result: str,
    current_diagnosis: dict,
    previous_action: dict | None
) -> dict:

    """
    根据验证结果，生成下一轮结构化行动。

    validation_result:
    improved  = 改善
    unchanged = 无变化
    worsened  = 恶化
    unknown   = 无法判断
    """


    # ==========================================
    # Defensive Check 1
    # validation_result必须属于合法状态
    # ==========================================

    valid_validation_results = {
        "improved",
        "unchanged",
        "worsened",
        "unknown"
    }


    if (
        validation_result
        not in valid_validation_results
    ):

        raise ValueError(
            f"未识别的 validation_result: "
            f"{validation_result}"
        )


    # ==========================================
    # Defensive Check 2
    # current_diagnosis必须是dict
    # ==========================================

    if not isinstance(
        current_diagnosis,
        dict
    ):

        raise TypeError(
            "current_diagnosis必须是dict"
        )


    # ==========================================
    # Defensive Check 3
    # previous_action允许None
    # 但如果存在必须是dict
    # ==========================================

    if (
        previous_action is not None
        and not isinstance(
            previous_action,
            dict
        )
    ):

        raise TypeError(
            "previous_action必须是dict或None"
        )


    # ==========================================
    # Target Stage Fallback
    # 目标阶段回退机制
    #
    # 优先使用当前诊断weak_stage
    # 如果当前缺失，则使用上一轮实际行动target_stage
    # ==========================================

    current_stage = current_diagnosis.get(
        "weak_stage"
    )


    previous_stage = (
        previous_action.get(
            "target_stage"
        )
        if previous_action
        else None
    )


    target_stage = (
        current_stage
        or previous_stage
    )


    current_status = current_diagnosis.get(
        "status"
    )


    # ==========================================
    # 1. 改善 improved
    # ==========================================

    if validation_result == "improved":

        return {
            "priority":
                "P2",

            "action_type":
                "monitor_after_improvement",

            "target_stage":
                target_stage,

            "required_data": [
                "historical_conversion_trend"
            ],

            "reason":
                "复诊结果显示当前转化表现较上一轮改善",

            "goal":
                "继续观察改善是否能够稳定保持"
        }


    # ==========================================
    # 2. 无变化 unchanged
    # ==========================================

    if validation_result == "unchanged":

        required_data = []


        if target_stage == "cart_to_purchase":

            required_data = [
                "same_category_sku_comparison",
                "same_price_band_benchmark",
                "historical_conversion_trend"
            ]


        elif target_stage == "product_to_cart":

            required_data = [
                "same_category_sku_comparison",
                "traffic_source_data",
                "historical_conversion_trend"
            ]


        elif target_stage == "both":

            required_data = [
                "same_category_sku_comparison",
                "traffic_source_data",
                "historical_conversion_trend"
            ]


        else:

            required_data = [
                "historical_conversion_trend",
                "same_category_sku_comparison"
            ]


        return {
            "priority":
                "P1"
                if current_status == "severe"
                else "P2",

            "action_type":
                "expand_investigation",

            "target_stage":
                target_stage,

            "required_data":
                required_data,

            "reason":
                "上一轮行动完成后，复诊结果未观察到转化改善",

            "goal":
                "扩大验证范围，继续定位尚未被当前证据解释的转化阻力"
        }


    # ==========================================
    # 3. 恶化 worsened
    # ==========================================

    if validation_result == "worsened":

        return {
            "priority":
                "P1",

            "action_type":
                "escalate_investigation",

            "target_stage":
                target_stage,

            "required_data": [
                "historical_conversion_trend",
                "traffic_source_data",
                "same_category_sku_comparison"
            ],

            "reason":
                "复诊结果显示当前转化表现较上一轮进一步恶化",

            "goal":
                "提高调查优先级并重新确认异常阶段及影响因素"
        }


    # ==========================================
    # 4. 无法判断 unknown
    # ==========================================

    if validation_result == "unknown":

        return {
            "priority":
                "P2",

            "action_type":
                "collect_validation_data",

            "target_stage":
                target_stage,

            "required_data": [
                "historical_conversion_trend"
            ],

            "reason":
                "当前复诊数据不足以判断上一轮行动后的变化",

            "goal":
                "补充可用于效果验证的数据后重新进行复诊"
        }


# ==================================================
# 10. 获取最新诊断
# ==================================================

def get_latest_diagnosis(
    product_id: int
):

    records = get_product_history(
        product_id
    )


    if not records:

        return None


    return records[-1]


'''
Diagnosis（诊断）
↓
Next Action（原始行动）
↓
Effective Action（最终生效行动）
↓
Action Status（执行状态）
↓
completed
↓
Re-diagnosis（复诊）
↓
Comparison（前后对比）
↓
Validation Result（效果验证）
↓
Next Round Action（下一轮行动）
↓
新的 Effective Action
↓
继续下一轮
'''
