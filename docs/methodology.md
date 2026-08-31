# Methodology

## 指标、异常规则与数据归因说明

本文档记录 Ecomm CVR Agent 使用的指标口径、确定性诊断规则以及 TheLook 数据归因前提。根目录 README 负责快速理解项目，本文件用于审阅具体方法。

## 1. 数据来源

项目使用 Google BigQuery Public Datasets 中的 TheLook Ecommerce 合成数据集，并以本地 CSV 快照运行分析。

核心应用读取：

- `events_old.csv`：Session 行为事件
- `products_old.csv`：商品、品类、品牌与零售价
- `industry_benchmark_comparison.xlsx`：外部行业背景参考

TheLook 是用于分析与功能验证的合成数据，不代表真实公司的线上交易。

## 2. Product Attribution

`product` Event 的 URI 包含商品 ID，例如：

```text
/product/7498
```

`cart` 和 `purchase` Event 没有直接提供 Product ID，因此项目先建立：

```text
session_id → product_id
```

再将 Session 是否发生 Cart/Purchase 映射到对应商品。

### 当前快照验证结果

- 单商品 Session：100%
- 多商品 Session：0%
- Cart 前存在 Product Event：100%
- Purchase Session 属于 Cart Session：100%

因此在当前数据快照中，Session-level Cart/Purchase 可以映射到 Session 内的唯一商品。

### 迁移约束

上述结论不能直接迁移到真实埋点数据。真实系统需要重新验证：

- 一个 Session 是否浏览多个商品
- Cart Event 是否包含 Product ID 和 Quantity
- Purchase 是否能通过 Order Item 回溯 Product ID
- 跨 Session 购买如何归因
- 多设备或匿名用户如何合并

## 3. 核心指标

### Product Sessions

访问过当前商品的唯一 Session 数：

```text
COUNT(DISTINCT session_id with product view)
```

### Product → Cart Rate

```text
发生 Cart 的唯一 Product Session
----------------------------------
          Product Sessions
```

### Product → Purchase CVR

```text
发生 Purchase 的唯一 Product Session
--------------------------------------
              Product Sessions
```

### Cart → Purchase Rate

```text
发生 Purchase 的唯一 Product Session
--------------------------------------
   发生 Cart 的唯一 Product Session
```

### Relative Deviation

SKU 指标相对 Category Benchmark 的偏离：

```text
(SKU Metric - Category Metric) / Category Metric
```

例如 SKU CVR 为 13%，Category CVR 为 26%：

```text
(13% - 26%) / 26% = -50%
```

`-50%` 表示相对于 Category Benchmark 低约 50%，不是低 50 个百分点。

## 4. Category Benchmark

Category Benchmark 基于当前品类下的 Session 与转化结果计算，用来回答：

- 当前 SKU 是否偏离同品类总体表现
- 整体 CVR 偏离程度
- Product→Cart 或 Cart→Purchase 哪个阶段更弱

它是当前 TheLook 数据快照中的内部对照，不等同于行业标准、目标值或因果基线。

## 5. 异常检测规则

规则定义在 `src/rules/conversion_anomaly.py`。

### 样本量保护

```text
Product Sessions < 20
→ insufficient_data
```

在 `insufficient_data` 状态下：

- 不判断正常、偏低或严重异常
- 不解释 CVR Deviation
- 不定位 Funnel Weak Stage
- 不执行 Price Analysis
- 不调用或解释 External Benchmark
- 下一步只要求积累至少 20 个 Product Sessions 后重新运行

达到 20 只代表可以重新执行异常规则，不保证一定进入深度诊断。

### 异常等级

当样本量达到当前门槛且 Category Benchmark 有效时：

| CVR Relative Deviation | 状态 |
|---|---|
| `≤ -50%` | `severe` |
| `≤ -30%` 且 `> -50%` | `low` |
| `> -30%` | `normal` |

这些阈值用于项目中的确定性分支，不是统计显著性检验结果。

## 6. Funnel Weak Stage

异常商品会继续计算两个子阶段相对 Category 的偏离：

```text
Product → Cart
Cart → Purchase
```

当前子阶段阈值为相对偏离 `≤ -30%`。

| 输出 | 含义 |
|---|---|
| `product_to_cart` | 商品页→购物车触发当前规则 |
| `cart_to_purchase` | 购物车→购买触发当前规则 |
| `both` | 两个阶段均触发当前规则 |
| `none` | 当前没有明确弱环节 |

弱环节定位是描述性判断，只说明问题集中在哪个阶段。

## 7. Price Analysis

价格分析计算：

- SKU Retail Price
- Category Average Price
- Category Median Price
- Price Deviation
- Price Percentile

当前 Price Status：

| Price Percentile | 状态 |
|---|---|
| `≥ 80%` | `high` |
| `≤ 20%` | `low` |
| 其他 | `normal` |

Price Status 只能描述商品在品类内的位置，不能证明价格导致转化变化。

## 8. External Industry Reference

项目读取 Dynamic Yield Fashion/Apparel Benchmark 作为行业背景。

由于 Dynamic Yield 与 TheLook 的数据来源、时间范围、样本结构和统计口径不同，外部 Benchmark：

- 不参与异常阈值
- 不与 SKU CVR 直接比较高低
- 不用于推算目标 CVR
- 不用于生成因果结论

## 9. 证据层级

项目将输出区分为：

```text
Fact（事实）
→ Rule Judgment（规则判断）
→ Hypothesis（待验证假设）
→ Causal Conclusion（因果结论）
```

当前系统可以输出前三层中的事实、规则判断和待验证方向，但不会把待验证因素包装成已经证实的因果结论。

