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


from src.conversion_diagnosis_agent import diagnose_product

from src.diagnosis_history import (
    get_product_history,
    get_latest_diagnosis,
    update_action_status
)


PRODUCT_ID = 7498


print(
    "\n========== Step 1: First Diagnosis =========="
)

first_result = diagnose_product(
    PRODUCT_ID
)

first_record = get_latest_diagnosis(
    PRODUCT_ID
)

first_diagnosis_id = first_record[
    "diagnosis_id"
]

print(
    "First Diagnosis ID:",
    first_diagnosis_id
)

print(
    "First Effective Action:",
    first_record.get(
        "effective_action"
    )
)

print(
    "First Action Status:",
    first_record.get(
        "action_status"
    )
)


print(
    "\n========== Step 2: Mark First Action Completed =========="
)

update_action_status(
    diagnosis_id=
        first_diagnosis_id,

    new_status=
        "completed"
)

history = get_product_history(
    PRODUCT_ID
)

completed_record = next(
    record
    for record in history
    if record.get(
        "diagnosis_id"
    ) == first_diagnosis_id
)

print(
    "Action Status:",
    completed_record.get(
        "action_status"
    )
)


print(
    "\n========== Step 3: Re-diagnosis =========="
)

second_result = diagnose_product(
    PRODUCT_ID
)


print(
    "Validation Result:",
    second_result.get(
        "validation_result"
    )
)

print(
    "Next Round Action:",
    second_result.get(
        "next_round_action"
    )
)


print(
    "\n========== Step 4: Check Old History Record =========="
)

history = get_product_history(
    PRODUCT_ID
)

old_record = next(
    record
    for record in history
    if record.get(
        "diagnosis_id"
    ) == first_diagnosis_id
)

print(
    "Old Diagnosis ID:",
    old_record.get(
        "diagnosis_id"
    )
)

print(
    "Old Effective Action:",
    old_record.get(
        "effective_action"
    )
)

print(
    "Old Action Status:",
    old_record.get(
        "action_status"
    )
)

print(
    "Old Validation Result:",
    old_record.get(
        "validation_result"
    )
)


print(
    "\n========== Step 5: Check New History Record =========="
)

new_record = get_latest_diagnosis(
    PRODUCT_ID
)

print(
    "New Diagnosis ID:",
    new_record.get(
        "diagnosis_id"
    )
)

print(
    "New Effective Action:",
    new_record.get(
        "effective_action"
    )
)

print(
    "New Action Status:",
    new_record.get(
        "action_status"
    )
)


print(
    "\n========== Step 6: Lifecycle Check =========="
)

old_is_validated = (
    old_record.get(
        "action_status"
    )
    ==
    "validated"
)

validation_result_match = (
    old_record.get(
        "validation_result"
    )
    ==
    second_result.get(
        "validation_result"
    )
)

new_is_pending = (
    new_record.get(
        "action_status"
    )
    ==
    "pending"
)


print(
    "Old Action Is Validated:",
    old_is_validated
)

print(
    "Validation Result Match:",
    validation_result_match
)

print(
    "New Action Is Pending:",
    new_is_pending
)


if (
    old_is_validated
    and validation_result_match
    and new_is_pending
):

    print(
        "\nStep 4.7 PASS"
    )

else:

    print(
        "\nStep 4.7 FAIL"
    )



"output"
'''
========== Step 1: First Diagnosis ==========

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

========== Next Action ==========
{'priority': 'P1', 'action_type': 'collect_data', 'target_stage': 'cart_to_purchase', 'required_data': ['checkout_step_funnel', 'cart_abandon_reason', 'shipping_tax_data', 'payment_method_data', 'inventory_delivery_data'], 'reason': 'Cart→Purchase被识别为当前主要异常阶段', 'goal': '进一步定位购物车至购买环节中的具体转化阻力'}

========== Report ==========
First Diagnosis ID: 2cb0b8d2-e8a7-45a2-a94e-e5e135bfcd83
First Effective Action: {'priority': 'P1', 'action_type': 'collect_data', 'target_stage': 'cart_to_purchase', 'required_data': ['checkout_step_funnel', 'cart_abandon_reason', 'shipping_tax_data', 'payment_method_data', 'inventory_delivery_data'], 'reason': 'Cart→Purchase被识别为当前主要异常阶段', 'goal': '进一步定位购物车至购买环节中的具体转化阻力'}
First Action Status: pending

========== Step 2: Mark First Action Completed ==========
Action Status: completed

========== Step 3: Re-diagnosis ==========

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

========== Next Action ==========
{'priority': 'P1', 'action_type': 'collect_data', 'target_stage': 'cart_to_purchase', 'required_data': ['checkout_step_funnel', 'cart_abandon_reason', 'shipping_tax_data', 'payment_method_data', 'inventory_delivery_data'], 'reason': 'Cart→Purchase被识别为当前主要异常阶段', 'goal': '进一步定位购物车至购买环节中的具体转化阻力'}

========== Report ==========
Validation Result: unchanged
Next Round Action: {'priority': 'P1', 'action_type': 'expand_investigation', 'target_stage': 'cart_to_purchase', 'required_data': ['same_category_sku_comparison', 'same_price_band_benchmark', 'historical_conversion_trend'], 'reason': '上一轮行动完成后，复诊结果未观察到转化改善', 'goal': '扩大验证范围，继续定位尚未被当前证据解释的转化阻力'}

========== Step 4: Check Old History Record ==========
Old Diagnosis ID: 2cb0b8d2-e8a7-45a2-a94e-e5e135bfcd83
Old Effective Action: {'priority': 'P1', 'action_type': 'collect_data', 'target_stage': 'cart_to_purchase', 'required_data': ['checkout_step_funnel', 'cart_abandon_reason', 'shipping_tax_data', 'payment_method_data', 'inventory_delivery_data'], 'reason': 'Cart→Purchase被识别为当前主要异常阶段', 'goal': '进一步定位购物车至购买环节中的具体转化阻力'}
Old Action Status: validated
Old Validation Result: unchanged

========== Step 5: Check New History Record ==========
New Diagnosis ID: 2bdcdeab-83e7-4d5e-aaf3-05e69aae5cd8
New Effective Action: {'priority': 'P1', 'action_type': 'expand_investigation', 'target_stage': 'cart_to_purchase', 'required_data': ['same_category_sku_comparison', 'same_price_band_benchmark', 'historical_conversion_trend'], 'reason': '上一轮行动完成后，复诊结果未观察到转化改善', 'goal': '扩大验证范围，继续定位尚未被当前证据解释的转化阻力'}
New Action Status: pending

========== Step 6: Lifecycle Check ==========
Old Action Is Validated: True
Validation Result Match: True
New Action Is Pending: True

Step 4.7 PASS
'''
