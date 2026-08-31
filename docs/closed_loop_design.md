# Closed-loop Design

## 诊断历史、行动状态与复诊验证

本文档说明 Ecomm CVR Agent 如何把单次诊断结果连接成一个可追踪的闭环验证机制。

## 1. 闭环目标

项目不是在生成第一份诊断报告后结束，而是继续记录：

```text
Diagnosis
→ Action
→ Action Status
→ Re-diagnosis
→ Comparison
→ Validation Result
→ Next Round Action
```

闭环的作用是推动下一轮验证，不是自动证明建议有效。

## 2. Diagnosis History

每次调用统一入口：

```python
from src.conversion_diagnosis_agent import diagnose_product
```

系统会将结构化结果保存到 JSONL 历史文件。主要字段包括：

- `diagnosis_id`
- `diagnosed_at`
- `product_id`
- `status`
- `purchase_cvr`
- `category_cvr`
- `cvr_deviation`
- `weak_stage`
- `price_status`
- `next_action`
- `effective_action`
- `action_status`

JSONL 中每一行代表一次独立诊断，便于追加、回溯和比较。

## 3. Action Contract

每个行动使用统一结构：

```json
{
  "priority": "P1",
  "action_type": "expand_investigation",
  "target_stage": "cart_to_purchase",
  "required_data": [
    "same_category_sku_comparison",
    "same_price_band_benchmark",
    "historical_conversion_trend"
  ],
  "reason": "上一轮行动完成后，复诊结果未观察到转化改善",
  "goal": "扩大验证范围"
}
```

固定字段让行动可以继续被程序读取、展示、更新和验证。

## 4. Action Status

```text
pending
→ in_progress
→ completed
→ validated
```

| 状态 | 含义 |
|---|---|
| `pending` | 已生成行动，尚未开始 |
| `in_progress` | 行动正在执行 |
| `completed` | 行动已执行，等待新数据验证 |
| `validated` | 已完成复诊与效果判断 |

`completed` 不等于 `effective`。只有复诊结果才能判断是否观察到改善。

## 5. Re-diagnosis

只有上一轮 Action Status 为 `completed` 时，当前诊断才会作为验证轮次使用。

复诊仍然运行同一套确定性指标和异常规则，避免前后轮次使用不同口径。

如果底层数据没有变化，复诊得到相同结果属于预期行为。

## 6. Comparison

系统比较当前诊断与上一轮诊断，包括：

- 状态变化
- Purchase CVR 变化
- Category Benchmark 变化
- CVR Relative Deviation 变化
- Weak Stage 变化

Comparison 是 Validation Result 的输入，不直接由 LLM 决定。

## 7. Validation Result

| 结果 | 业务含义 |
|---|---|
| `improved` | 当前规则观察到表现改善 |
| `unchanged` | 当前规则未观察到明显变化 |
| `worsened` | 当前表现恶化 |
| `unknown` | 当前数据不足以判断 |

Validation Result 是项目规则下的效果分类，不等同于统计因果评估或线上 A/B 实验结论。

## 8. Next Round Action

不同验证分支生成不同策略：

### Improved

```text
improved
→ monitor_after_improvement
→ 继续观察改善是否稳定
```

### Unchanged

```text
unchanged
→ expand_investigation
→ 扩大数据与证据范围
```

### Worsened

```text
worsened
→ escalate_investigation
→ 提高优先级并升级调查
```

### Unknown

```text
unknown
→ collect_validation_data
→ 补充复诊所需数据
```

## 9. Effective Action

系统对最终生效行动采用以下优先级：

```text
next_round_action（如果存在）
否则 next_action
```

LLM 报告读取 `effective_action`，确保页面中的行动、历史记录和最终报告保持一致。

## 10. 当前能力边界

当前闭环属于 Decision-support Loop（决策辅助闭环）：

- 系统生成并追踪行动
- 用户更新行动状态
- 新数据产生后重新诊断
- 系统比较前后结果并生成下一轮行动

当前版本没有：

- 自动修改商品页面或价格
- 连接真实电商任务系统
- 自动执行营销操作
- 自动创建 A/B 实验
- 将指标变化直接解释为行动的因果效果

因此更准确的表述是“闭环验证机制原型”，而不是生产级自动运营系统。

