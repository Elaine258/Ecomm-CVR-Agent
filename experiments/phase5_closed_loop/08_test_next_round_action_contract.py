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
    build_next_round_action
)


# ==================================================
# Action Contract
# 下一轮行动必须具备的固定字段
# ==================================================

REQUIRED_FIELDS = {
    "priority",
    "action_type",
    "target_stage",
    "required_data",
    "reason",
    "goal"
}


# ==================================================
# 上一轮实际执行行动
# ==================================================

PREVIOUS_ACTION = {
    "priority": "P1",
    "action_type": "collect_data",
    "target_stage": "cart_to_purchase",
    "required_data": [
        "checkout_step_funnel",
        "cart_abandon_reason",
        "shipping_tax_data",
        "payment_method_data",
        "inventory_delivery_data"
    ],
    "reason":
        "Cart→Purchase被识别为当前主要异常阶段",
    "goal":
        "进一步定位购物车至购买环节中的具体转化阻力"
}


# ==================================================
# 当前诊断
# ==================================================

CURRENT_DIAGNOSIS = {
    "status": "severe",
    "weak_stage": "cart_to_purchase"
}


# ==================================================
# 预期结果
# ==================================================

TEST_CASES = [

    {
        "validation_result":
            "improved",

        "expected": {
            "priority":
                "P2",

            "action_type":
                "monitor_after_improvement",

            "target_stage":
                "cart_to_purchase",

            "required_data": [
                "historical_conversion_trend"
            ],

            "reason":
                "复诊结果显示当前转化表现较上一轮改善",

            "goal":
                "继续观察改善是否能够稳定保持"
        }
    },

    {
        "validation_result":
            "unchanged",

        "expected": {
            "priority":
                "P1",

            "action_type":
                "expand_investigation",

            "target_stage":
                "cart_to_purchase",

            "required_data": [
                "same_category_sku_comparison",
                "same_price_band_benchmark",
                "historical_conversion_trend"
            ],

            "reason":
                "上一轮行动完成后，复诊结果未观察到转化改善",

            "goal":
                "扩大验证范围，继续定位尚未被当前证据解释的转化阻力"
        }
    },

    {
        "validation_result":
            "worsened",

        "expected": {
            "priority":
                "P1",

            "action_type":
                "escalate_investigation",

            "target_stage":
                "cart_to_purchase",

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
    },

    {
        "validation_result":
            "unknown",

        "expected": {
            "priority":
                "P2",

            "action_type":
                "collect_validation_data",

            "target_stage":
                "cart_to_purchase",

            "required_data": [
                "historical_conversion_trend"
            ],

            "reason":
                "当前复诊数据不足以判断上一轮行动后的变化",

            "goal":
                "补充可用于效果验证的数据后重新进行复诊"
        }
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

    validation_result = (
        case[
            "validation_result"
        ]
    )

    expected = (
        case[
            "expected"
        ]
    )


    print(
        f"\n========== Case {index}: "
        f"{validation_result} =========="
    )


    action = build_next_round_action(
        validation_result=
            validation_result,

        current_diagnosis=
            CURRENT_DIAGNOSIS,

        previous_action=
            PREVIOUS_ACTION
    )


    print(
        "Generated Action:",
        action
    )


    # ==========================================
    # Check 1
    # 字段是否完整
    # ==========================================

    actual_fields = set(
        action.keys()
    )

    fields_complete = (
        actual_fields
        ==
        REQUIRED_FIELDS
    )


    print(
        "Fields Complete:",
        fields_complete
    )


    # ==========================================
    # Check 2
    # 每个字段是否与预期完全一致
    # ==========================================

    field_results = {}

    for field in REQUIRED_FIELDS:

        passed = (
            action.get(field)
            ==
            expected.get(field)
        )

        field_results[
            field
        ] = passed

        print(
            f"{field}:",
            passed
        )


    values_correct = all(
        field_results.values()
    )


    # ==========================================
    # Check 3
    # required_data必须是list
    # ==========================================

    required_data_is_list = isinstance(
        action.get(
            "required_data"
        ),
        list
    )


    print(
        "Required Data Is List:",
        required_data_is_list
    )


    # ==========================================
    # 当前Case最终结果
    # ==========================================

    case_passed = (
        fields_complete
        and values_correct
        and required_data_is_list
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
    "\n========== Step 4.9 Result =========="
)


if all_passed:

    print(
        "Step 4.9 PASS"
    )

else:

    print(
        "Step 4.9 FAIL"
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
(agent) PS E:\agent\experiments\phase5_closed_loop> python 08_test_next_round_action_contract.py

========== Case 1: improved ==========
Generated Action: {'priority': 'P2', 'action_type': 'monitor_after_improvement', 'target_stage': 'cart_to_purchase', 'required_data': ['historical_conversion_trend'], 'reason': '复诊结果显示当前转化表现较上一轮改善', 'goal': '继续观察改善是否能够稳定保持'}
Fields Complete: True
reason: True
goal: True
action_type: True
target_stage: True
required_data: True
priority: True
Required Data Is List: True
Case 1 PASS

========== Case 2: unchanged ==========
Generated Action: {'priority': 'P1', 'action_type': 'expand_investigation', 'target_stage': 'cart_to_purchase', 'required_data': ['same_category_sku_comparison', 'same_price_band_benchmark', 'historical_conversion_trend'], 'reason': '上一轮行动完成后，复诊结果未观察到转化改善', 'goal': '扩大验证范围，继续定位尚未被当前证据解释的转化阻力'}
Fields Complete: True
reason: True
goal: True
action_type: True
target_stage: True
required_data: True
priority: True
Required Data Is List: True
Case 2 PASS

========== Case 3: worsened ==========
Generated Action: {'priority': 'P1', 'action_type': 'escalate_investigation', 'target_stage': 'cart_to_purchase', 'required_data': ['historical_conversion_trend', 'traffic_source_data', 'same_category_sku_comparison'], 'reason': '复诊结果显示当前转化表现较上一轮进一步恶化', 'goal': '提高调查优先级并重新确认异常阶段及影响因素'}
Fields Complete: True
reason: True
goal: True
action_type: True
target_stage: True
required_data: True
priority: True
Required Data Is List: True
Case 3 PASS

========== Case 4: unknown ==========
Generated Action: {'priority': 'P2', 'action_type': 'collect_validation_data', 'target_stage': 'cart_to_purchase', 'required_data': ['historical_conversion_trend'], 'reason': '当前复诊数据不足以判断上一轮行动后的变化', 'goal': '补充可用于效果验证的数据后重新进行复诊'}
Fields Complete: True
reason: True
goal: True
action_type: True
target_stage: True
required_data: True
priority: True
Required Data Is List: True
Case 4 PASS

========== Step 4.9 Result ==========
Step 4.9 PASS
'''
