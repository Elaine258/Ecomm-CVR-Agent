import sys
import os

ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        ".."
    )
)

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


from src.diagnosis_history import (
    build_validation_result,
    build_next_round_action
)


# ==================================================
# 基础上一轮行动
# ==================================================

PREVIOUS_ACTION = {
    "priority": "P1",
    "action_type": "collect_data",
    "target_stage": "cart_to_purchase",
    "required_data": [
        "checkout_step_funnel",
        "cart_abandon_reason"
    ],
    "reason": "Cart→Purchase被识别为当前主要异常阶段",
    "goal": "进一步定位购物车至购买环节中的具体转化阻力"
}


# ==================================================
# 4个测试案例
# ==================================================

TEST_CASES = [

    # ------------------------------------------
    # Case 1
    # improved
    # severe → low
    # ------------------------------------------

    {
        "name": "improved",

        "comparison": {
            "has_previous": True,
            "status_changed": True,
            "previous_status": "severe",
            "current_status": "low",
            "purchase_cvr_change": 0.05,
            "cvr_deviation_change": 0.10,
            "weak_stage_changed": False,
            "previous_weak_stage": "cart_to_purchase",
            "current_weak_stage": "cart_to_purchase"
        },

        "current_diagnosis": {
            "status": "low",
            "weak_stage": "cart_to_purchase"
        },

        "expected_validation_result":
            "improved",

        "expected_action_type":
            "monitor_after_improvement"
    },


    # ------------------------------------------
    # Case 2
    # unchanged
    # severe → severe
    # CVR无变化
    # ------------------------------------------

    {
        "name": "unchanged",

        "comparison": {
            "has_previous": True,
            "status_changed": False,
            "previous_status": "severe",
            "current_status": "severe",
            "purchase_cvr_change": 0.0,
            "cvr_deviation_change": 0.0,
            "weak_stage_changed": False,
            "previous_weak_stage": "cart_to_purchase",
            "current_weak_stage": "cart_to_purchase"
        },

        "current_diagnosis": {
            "status": "severe",
            "weak_stage": "cart_to_purchase"
        },

        "expected_validation_result":
            "unchanged",

        "expected_action_type":
            "expand_investigation"
    },


    # ------------------------------------------
    # Case 3
    # worsened
    # low → severe
    # ------------------------------------------

    {
        "name": "worsened",

        "comparison": {
            "has_previous": True,
            "status_changed": True,
            "previous_status": "low",
            "current_status": "severe",
            "purchase_cvr_change": -0.05,
            "cvr_deviation_change": -0.10,
            "weak_stage_changed": False,
            "previous_weak_stage": "cart_to_purchase",
            "current_weak_stage": "cart_to_purchase"
        },

        "current_diagnosis": {
            "status": "severe",
            "weak_stage": "cart_to_purchase"
        },

        "expected_validation_result":
            "worsened",

        "expected_action_type":
            "escalate_investigation"
    },


    # ------------------------------------------
    # Case 4
    # unknown
    # 缺少可比较CVR变化
    # ------------------------------------------

    {
        "name": "unknown",

        "comparison": {
            "has_previous": True,
            "status_changed": False,
            "previous_status": "severe",
            "current_status": "severe",
            "purchase_cvr_change": None,
            "cvr_deviation_change": None,
            "weak_stage_changed": False,
            "previous_weak_stage": "cart_to_purchase",
            "current_weak_stage": "cart_to_purchase"
        },

        "current_diagnosis": {
            "status": "severe",
            "weak_stage": "cart_to_purchase"
        },

        "expected_validation_result":
            "unknown",

        "expected_action_type":
            "collect_validation_data"
    }
]


# ==================================================
# 执行测试
# ==================================================

all_passed = True


for index, case in enumerate(
    TEST_CASES,
    start=1
):

    print(
        f"\n========== Case {index}: {case['name']} =========="
    )


    # ------------------------------------------
    # 1. 生成 Validation Result
    # ------------------------------------------

    validation_result = (
        build_validation_result(
            case["comparison"]
        )
    )


    print(
        "Validation Result:",
        validation_result
    )

    print(
        "Expected Validation Result:",
        case[
            "expected_validation_result"
        ]
    )


    validation_passed = (
        validation_result
        ==
        case[
            "expected_validation_result"
        ]
    )


    # ------------------------------------------
    # 2. 生成 Next Round Action
    # ------------------------------------------

    next_round_action = (
        build_next_round_action(
            validation_result=
                validation_result,

            current_diagnosis=
                case[
                    "current_diagnosis"
                ],

            previous_action=
                PREVIOUS_ACTION
        )
    )


    print(
        "Next Round Action:",
        next_round_action
    )


    action_type = (
        next_round_action.get(
            "action_type"
        )
        if next_round_action
        else None
    )


    print(
        "Action Type:",
        action_type
    )

    print(
        "Expected Action Type:",
        case[
            "expected_action_type"
        ]
    )


    action_passed = (
        action_type
        ==
        case[
            "expected_action_type"
        ]
    )


    # ------------------------------------------
    # 3. 当前案例结果
    # ------------------------------------------

    case_passed = (
        validation_passed
        and action_passed
    )


    print(
        "Validation Check:",
        validation_passed
    )

    print(
        "Action Check:",
        action_passed
    )


    if case_passed:

        print(
            f"Case {index} PASS"
        )

    else:

        print(
            f"Case {index} FAIL"
        )

        all_passed = False


# ==================================================
# 最终结果
# ==================================================

print(
    "\n========== Step 4.8 Result =========="
)


if all_passed:

    print(
        "Step 4.8 PASS"
    )

else:

    print(
        "Step 4.8 FAIL"
    )



"output"
'''
========== Case 1: improved ==========
Validation Result: improved
Expected Validation Result: improved
Next Round Action: {'priority': 'P2', 'action_type': 'monitor_after_improvement', 'target_stage': 'cart_to_purchase', 'required_data': ['historical_conversion_trend'], 'reason': '复诊结果显示当前转化表现较上一轮改善', 'goal': '继续观察改善是否能够稳定保持'}
Action Type: monitor_after_improvement
Expected Action Type: monitor_after_improvement
Validation Check: True
Action Check: True
Case 1 PASS

========== Case 2: unchanged ==========
Validation Result: unchanged
Expected Validation Result: unchanged
Next Round Action: {'priority': 'P1', 'action_type': 'expand_investigation', 'target_stage': 'cart_to_purchase', 'required_data': ['same_category_sku_comparison', 'same_price_band_benchmark', 'historical_conversion_trend'], 'reason': '上一轮行动完成后，复诊结果未观察到转化改善', 'goal': '扩大验证范围，继续定位尚未被当前证据解释的转化阻力'}
Action Type: expand_investigation
Expected Action Type: expand_investigation
Validation Check: True
Action Check: True
Case 2 PASS

========== Case 3: worsened ==========
Validation Result: worsened
Expected Validation Result: worsened
Next Round Action: {'priority': 'P1', 'action_type': 'escalate_investigation', 'target_stage': 'cart_to_purchase', 'required_data': ['historical_conversion_trend', 'traffic_source_data', 'same_category_sku_comparison'], 'reason': '复诊结果显示当前转化表现较上一轮进一步恶化', 'goal': '提高调查优先级并重新确认异常阶段及影响因素'}
Action Type: escalate_investigation
Expected Action Type: escalate_investigation
Validation Check: True
Action Check: True
Case 3 PASS

========== Case 4: unknown ==========
Validation Result: unknown
Expected Validation Result: unknown
Next Round Action: {'priority': 'P2', 'action_type': 'collect_validation_data', 'target_stage': 'cart_to_purchase', 'required_data': ['historical_conversion_trend'], 'reason': '当前复诊数据不足以判断上一轮行动后的变化', 'goal': '补充可用于效果验证的数据后重新进行复诊'}
Action Type: collect_validation_data
Expected Action Type: collect_validation_data
Validation Check: True
Action Check: True
Case 4 PASS

========== Step 4.8 Result ==========
Step 4.8 PASS
'''
