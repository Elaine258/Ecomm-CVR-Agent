import os
import sys

ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "../.."
    )
)

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.conversion_diagnosis_agent import (
    diagnose_product
)

# ==================================================
# 3. 测试 Agent 入口
# ==================================================

result = diagnose_product(
    product_id=7498
)


# ==================================================
# 4. 输出诊断结果
# ==================================================

print(
    "\n========== Diagnosis Result =========="
)

print(
    "Product ID:",
    result["product_id"]
)

print(
    "Product Name:",
    result["product_name"]
)

print(
    "Category:",
    result["category"]
)

print(
    "Status:",
    result["status"]
)

print(
    "Product Sessions:",
    result["product_sessions"]
)

print(
    "Purchase CVR:",
    f'{result["purchase_cvr"]:.2%}'
)

print(
    "Category CVR:",
    f'{result["category_cvr"]:.2%}'
)

print(
    "Weak Stage:",
    result["weak_stage"]
)

print(
    "Price Status:",
    result["price_status"]
)


print(
    "\n========== Next Action =========="
)

print(
    result["next_action"]
)

print(
    "\n========== Final Report =========="
)

print(
    result["final_report"]
)

print(
    "\n========== Comparison =========="
)

print(
    result["comparison"]
)

print(
    "\n========== Follow Up Summary =========="
)

print(
    result["follow_up_summary"]
)

print(
    "\n========== Validation Result =========="
)

print(
    result[
        "validation_result"
    ]
)


print(
    "\n========== Next Round Action =========="
)

print(
    result[
        "next_round_action"
    ]
)

print(
    "\n========== Effective Action =========="
)

print(
    result[
        "effective_action"
    ]
)



"output"
#已跑通，输出没有明显的数学或逻辑错误
#有两个小问题，但 Phase 5 Step 1 本身已经跑通了。统一入口 diagnose_product()、Graph、Router、深度诊断链路都正常。
#
# 第一处：
# “该环节相对偏离为 -0.3454，在漏斗各环节中偏离幅度最大”
# 这句话不严谨。因为整体 Product→Purchase 的偏离是 -0.5091，绝对值其实更大。你真正想表达的是：
# 在两个子漏斗阶段中，Cart→Purchase 的相对偏离幅度更大，因此被定位为主要异常阶段。
# 把“在漏斗各环节中”改成“在两个子漏斗阶段中”即可。

# 第二处：
# “价格分位 0.5152，略高于类目中位数”
# 51.52% 基本就是中间位置，“略高”虽然数学上没错，但没必要强调。建议改成：
# 价格分位约51.5%，处于类目价格分布中间位置。

# 展示层的小优化：
# 终端现在打印的是，
# Purchase CVR: 0.13043478260869565
# Category CVR: 0.26568077511473737
# 后面 Streamlit 界面展示时不直接显示float，统一格式成：
# f"{result['purchase_cvr']:.2%}"
# f"{result['category_cvr']:.2%}"
# 也就是：
# Purchase CVR: 13.04%
# Category CVR: 26.57%



'''
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

========== Diagnosis Result ==========
Product ID: 7498
Product Name: Anne Klein Women's Petite Tweed Jacket
Category: Blazers & Jackets
Status: severe
Product Sessions: 23
Purchase CVR: 0.13043478260869565
Category CVR: 0.26568077511473737
Weak Stage: cart_to_purchase
Price Status: normal

========== Final Report ==========
# 电商转化率异常诊断报告

**商品名称：** Anne Klein Women's Petite Tweed Jacket
**Product ID：** 7498
**类目：** Blazers & Jackets
**报告日期：** 基于当前最新State数据


## 一、异常状态总览

当前SKU被判定为 **severe**（重度）转化异常，核心依据为：

- **CVR相对偏离：** -0.5091（SKU整体购买转化率低于类目基准约50.91%）
- **主要弱环节定位：** cart_to_purchase（购物车→购买环节）

> **说明：** 上述偏离值表示SKU指标与类目基准之间的相对差距比例，并非用户流失比例。


## 二、漏斗分段表现与异常定位

| 环节 | SKU | 类目基准 | 绝对差距（百分点） | 相对偏离 |
|---|---|---|---|---|
| Product→Cart | 47.83% | 63.77% | -15.94 | -0.2500 |
| Cart→Purchase | 27.27% | 41.66% | -14.39 | -0.3454 |
| Product→Purchase（整体） | 13.04% | 26.57% | -13.53 | -0.5091 |

**异常阶段定位：** 当前数据将 **cart_to_purchase（购物车→购买）** 识别为主要异常弱环节。该环节相对偏离为 **-0.3454**，在漏斗各环节中偏离幅度最大，拉低了整体转化表现。


## 三、Product→Cart环节说明

Product→Cart环节的相对偏离为 **-0.2500**，绝对值未达到当前异常阈值标准，因此**未被当前规则识别为主要异常阶段**。

**需要特别说明的是：** 该环节未达异常标准，只能说明当前规则未将其定位为主要异常环节，**不能判断**商品图片、标题、描述等前端展示要素不存在问题。具体原因仍需要进一步排查。


## 四、价格定位分析

| 维度 | 数值 |
|---|---|
| SKU零售价（标价） | $69.97 |
| 类目零售价中位数 | $59.99 |
| 价格分位 | 0.5152 |
| 价格状态 | **normal** |

当前SKU零售价（标价）在类目中处于约第51.5百分位，略高于类目中位数，但**未达到当前价格异常判定标准**。

**说明：** 价格状态为normal，仅表示价格位置未触发当前价格异常阈值，**不能据此排除价格因素的潜在影响**。价格因素仍可能与该商品转化表现偏低有关，需要进一步验证。


## 五、外部行业参考背景

根据Dynamic Yield Fashion/Apparel 2025外部行业参考数据：加购率（商品页浏览口径）为6.58%，购买转化率（访客口径）为3.03%，购物车完成率代理（派生）为21.87%，购物车放弃率78.13%。

**注意：** Dynamic Yield与TheLook统计口径不同，上述数据**仅作为行业背景参考**，不直接参与当前SKU的异常阈值判断，也不得用于直接比较高低或推算TheLook指标。


## 六、事实、规则判断与待验证假设

### 已确认事实

1. SKU处于severe异常状态，CVR相对偏离为-0.5091。
2. Product→Cart偏离为-0.2500，Cart→Purchase偏离为-0.3454。
3. 当前主要弱环节定位为cart_to_purchase。

### 规则判断

1. 基于当前偏离数据，cart_to_purchase被识别为主要异常阶段。
2. Product→Cart未被当前规则识别为主要异常阶段。
3. 价格状态为normal，未达到价格异常判定标准。

### 假设（需进一步验证）

以下因素**可能**与cart_to_purchase环节表现偏低有关，但**现有证据不足以确定因果原因**，需逐一排查验证：

- **结账流程：** 结账步骤复杂、加载缓慢或信息填写要求过多等因素，可能导致部分已加购用户未能完成购买。
- **运费与税费透明度：** 运费、税费等在结算时高于用户预期，可能影响购物车完成率。
- **支付方式覆盖：** 支付选项不足或不符合目标用户习惯，可能与该环节偏低有关。
- **库存状况：** 用户在结算时遇到库存不足或显示缺货，可能导致交易中断。
- **竞品与比价行为：** 用户在加购后可能对比其他渠道价格或替代品，影响最终购买决策。
- **信任与售后因素：** 退换货政策、配送时效、客服可及性等不确定性，可能构成购买阻碍。


## 七、结论总结

1. **异常定位（规则判断）：** 当前规则将 **cart_to_purchase（购物车→购买环节）** 判定为SKU主要异常阶段。
2. **价格（规则判断）：** 零售价（标价）处于normal状态，未达到当前价格异常标准，但不能排除价格相关影响。
3. **因果归因（事实）：** **现有证据不足以确定因果原因**。当前数据直接支持的是异常状态和异常漏斗阶段定位，无法进一步确认是何种具体因素导致了该环节的表现偏低。
4. **建议动作（排查方向）：** 建议优先围绕结账流程、运费透明度、支付方式、库存状态、竞品比价及售后政策等方面进行排查验证，以定位cart_to_purchase环节表现偏低的具体原因。
'''
