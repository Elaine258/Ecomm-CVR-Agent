import os

from typing import TypedDict, Literal
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from langgraph.graph import (
    StateGraph,
    START,
    END
)

from langchain_openai import ChatOpenAI


load_dotenv()


# ==================================================
# 1. Agent State
# ==================================================

class AgentState(TypedDict):

    # 用户输入
    user_question: str

    # 商品数据
    product_id: str
    ctr: float
    cvr: float

    # Diagnose结果
    diagnosis: str
    next_action: str

    # Image Tool结果
    image_score: float
    image_problem: str

    # Price Tool结果
    price_score: float
    price_problem: str

    # 中间分析记录
    analysis_history: list[str]

    # 最终输出
    final_report: str


# ==================================================
# 2. Structured Output Schema
# ==================================================

class DiagnosisResult(BaseModel):

    diagnosis: str = Field(
        description="基于当前数据得到的初步诊断"
    )

    next_action: Literal[
        "image",
        "price",
        "report"
    ] = Field(
        description="下一步执行方向"
    )


# ==================================================
# 3. LLM
# ==================================================

llm = ChatOpenAI(
    model="deepseek-v4-flash",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
    extra_body={
        "thinking": {
            "type": "disabled"
        }
    }
)


diagnosis_llm = llm.with_structured_output(
    DiagnosisResult,
    method="function_calling"
)


# ==================================================
# 4. Diagnose Node
# ==================================================

def diagnose_node(state: AgentState):

    print("\n========== Diagnose Node ==========")

    prompt = f"""
你是一名电商数据分析专家。

用户问题：
{state["user_question"]}

商品ID：
{state["product_id"]}

CTR：
{state["ctr"]}

CVR：
{state["cvr"]}

请进行初步诊断。

规则：

1. CTR明显偏低：
优先检查图片问题，next_action=image。

2. CTR正常或较高，但CVR明显偏低：
优先检查价格问题，next_action=price。

3. 没有明显异常，或者已有信息足够：
next_action=report。

只能根据已知信息判断。
禁止编造额外数据。
"""

    result = diagnosis_llm.invoke(prompt)

    history = state["analysis_history"].copy()

    history.append(
        f"初步诊断：{result.diagnosis}"
    )

    return {
        "diagnosis": result.diagnosis,
        "next_action": result.next_action,
        "analysis_history": history
    }


# ==================================================
# 5. Image Tool Node
# ==================================================

def image_tool_node(state: AgentState):

    print("\n========== Image Tool Node ==========")

    # 模拟视觉模型结果
    image_score = 0.42

    image_problem = (
        "商品主体占比偏小，背景干扰较明显，"
        "视觉聚焦能力不足。"
    )

    history = state["analysis_history"].copy()

    history.append(
        f"图片分析：score={image_score}，"
        f"problem={image_problem}"
    )

    return {
        "image_score": image_score,
        "image_problem": image_problem,
        "analysis_history": history
    }


# ==================================================
# 6. Price Tool Node
# ==================================================

def price_tool_node(state: AgentState):

    print("\n========== Price Tool Node ==========")

    # 模拟真实价格分析工具结果
    price_score = 0.58

    price_problem = (
        "当前商品价格高于同类商品平均水平，"
        "可能影响转化效率。"
    )

    history = state["analysis_history"].copy()

    history.append(
        f"价格分析：score={price_score}，"
        f"problem={price_problem}"
    )

    return {
        "price_score": price_score,
        "price_problem": price_problem,
        "analysis_history": history
    }


# ==================================================
# 7. Router
# ==================================================

def router(
    state: AgentState
) -> Literal[
    "image_tool",
    "price_tool",
    "report"
]:

    print("\n========== Router ==========")

    action = state["next_action"]

    print("next_action:", action)

    if action == "image":
        return "image_tool"

    if action == "price":
        return "price_tool"

    return "report"


# ==================================================
# 8. Report Node
# ==================================================

def report_node(state: AgentState):

    print("\n========== Report Node ==========")

    history_text = "\n".join(
        state["analysis_history"]
    )

    prompt = f"""
你是一名电商运营分析专家。

用户问题：
{state["user_question"]}

商品ID：
{state["product_id"]}

基础指标：

CTR：
{state["ctr"]}

CVR：
{state["cvr"]}

完整分析过程：

{history_text}

请生成最终报告。

要求：

1. 区分：
   - 已知事实
   - 工具结果
   - 合理推断

2. 不允许编造数据。

3. 如果图片工具没有运行，
不要分析图片问题。

4. 如果价格工具没有运行，
不要分析价格问题。

5. 最后输出：
   - 核心问题
   - 判断依据
   - 优化建议
   - 下一步还需要补充什么数据
"""

    response = llm.invoke(prompt)

    return {
        "final_report": response.content
    }


# ==================================================
# 9. Build Graph
# ==================================================

builder = StateGraph(
    AgentState
)


builder.add_node(
    "diagnose",
    diagnose_node
)

builder.add_node(
    "image_tool",
    image_tool_node
)

builder.add_node(
    "price_tool",
    price_tool_node
)

builder.add_node(
    "report",
    report_node
)


# ==================================================
# 10. Edges
# ==================================================

builder.add_edge(
    START,
    "diagnose"
)


builder.add_conditional_edges(
    "diagnose",
    router,
    {
        "image_tool": "image_tool",
        "price_tool": "price_tool",
        "report": "report"
    }
)


builder.add_edge(
    "image_tool",
    "report"
)

builder.add_edge(
    "price_tool",
    "report"
)

builder.add_edge(
    "report",
    END
)


# ==================================================
# 11. Compile
# ==================================================

graph = builder.compile()


# ==================================================
# 12. Invoke
# ==================================================

initial_state: AgentState = {

    "user_question":
        "为什么这个商品表现不好？",

    "product_id":
        "SKU001",

    "ctr":
        0.012,

    "cvr":
        0.035,

    "diagnosis":
        "",

    "next_action":
        "",

    "image_score":
        0.0,

    "image_problem":
        "",

    "price_score":
        0.0,

    "price_problem":
        "",

    "analysis_history":
        [],

    "final_report":
        ""
}


result = graph.invoke(
    initial_state
)


# ==================================================
# 13. Debug输出
# ==================================================

print(
    "\n\n========== Analysis History =========="
)

for i, item in enumerate(
    result["analysis_history"],
    start=1
):

    print(
        f"{i}. {item}"
    )


print(
    "\n\n========== Final State =========="
)

print(
    "next_action:",
    result["next_action"]
)

print(
    "image_score:",
    result["image_score"]
)

print(
    "price_score:",
    result["price_score"]
)


print(
    "\n\n========== Final Report =========="
)

print(
    result["final_report"]
)


"output"
'''

========== Diagnose Node ==========

========== Router ==========
next_action: image

========== Image Tool Node ==========

========== Report Node ==========


========== Analysis History ==========
1. 初步诊断：该商品CTR为0.012（1.2%），明显偏低。根据行业经验，正常CTR通常在3%-5%左右，1.2%的点击率说明商品在搜索结果或推荐位中的吸引力不足。CTR偏低优先考虑商品主图、标题、价格展示等视觉和文案因素是否吸引用户点击。由于CTR明显偏低，优先排查图片问题（如主图不清晰、卖点不突出、与竞品差异不明显等），暂不将CVR偏低（0.035）作为优先处理对象。
2. 图片分析：score=0.42，problem=商品主体占比偏小，背景干扰较明显，视觉聚焦能力不足。


========== Final State ==========
next_action: image
image_score: 0.42
price_score: 0.0


========== Final Report ==========
# 商品SKU001表现诊断报告


## 一、已知事实

| 指标 | 数值 | 说明 |
|------|------|------|
| CTR | 0.012（1.2%） | 商品曝光后的点击率 |
| CVR | 0.035（3.5%） | 点击后的转化率 |

**行业参考（经验值）** ：正常CTR通常在3%–5%，1.2%显著低于常规水平。


## 二、工具结果

图片分析已运行，输出如下：

| 维度 | 结果 |
|------|------|
| 图片评分 | 0.42 / 1.0 |
| 识别问题 | 商品主体占比偏小，背景干扰较明显，视觉聚焦能力不足 |

> 说明：价格工具未运行，本报告不涉及任何价格维度分析。


## 三、合理推断

基于上述事实与工具结果，形成以下逻辑链：

1. CTR（1.2%）显著偏低 → 用户看到商品后点击意愿弱，问题出在“曝光转点击”环节；
2. 图片评分仅0.42，且明确提示**主体占比小、背景干扰强、聚焦不足** → 这在视觉层面直接削弱了商品的辨识度和吸引力，是导致CTR偏低的直接嫌疑因素；
3. CVR（3.5%）虽不算优秀，但**在低CTR前提下，点击进来的用户购买意愿尚可**，说明商品本身（详情页、价格、评价等）并非当前最紧迫的问题；
4. 因此推断：**当前阶段核心瓶颈在“点击率”，而非“转化率”** ，优先解决图片视觉问题是性价比最高的切入点。价格、评价等维度需后续工具验证，当前不作判断。


## 四、结论汇总

### 核心问题
**商品主图视觉吸引力不足，导致CTR远低于正常水平，是当前表现不佳的首要瓶颈。**

### 判断依据
| 依据 | 具体内容 |
|------|----------|
| 数据层面 | CTR = 1.2%，显著低于3%–5%的经验正常区间 |
| 工具层面 | 图片评分仅0.42/1.0，明确指出主体占比小、背景干扰、聚焦不足 |
| 逻辑层面 | 点击率是转化的前提，图片是影响点击的第一要素；CVR尚可，说明商品内功并非当前最大短板 |


## 五、优化建议

**优先级：P0（立即执行）**

1. **重做主图：放大商品主体**，确保商品占画面核心位置（建议面积占比≥70%）
2. **简化背景**：去除多余装饰元素，使用纯色或浅景深背景，减少干扰
3. **强化视觉焦点**：一句话核心卖点（如“限时5折”“爆款TOP1”）以角标形式突出，但不超过画面10%面积
4. **A/B测试验证**：制作2–3个不同风格的主图方案，小流量测试（各分配10%–20%曝光），以CTR提升幅度确定最优方案

**P1（同步推进）**
5. 检查标题前20个字符是否清晰传达核心卖点与搜索关键词，与主图形成配合
6. 观察竞品主图风格，确保自身在缩略图尺寸下有足够辨识度


## 六、下一步还需补充的数据

| 数据类型 | 用途 | 优先级 |
|----------|------|--------|
| **主图A/B测试数据** | 验证优化后的主图是否有效提升CTR | 高 |
| **商品曝光位置分布** | 判断是否因展示位置差（如翻页靠后）导致CTR低 | 高 |
| **价格工具分析结果** | 排除价格竞争力因素，与图片问题形成交叉验证 | 中 |
| **竞品CTR对比数据** | 校准该类目下真实CTR基准，确认差距程度 | 中 |
| **流量结构数据**（自然搜索/推荐/付费占比） | 判断不同渠道CTR差异，精准定位薄弱场景 | 中 |
| **商品评价数量与评分** | 辅助判断CVR的天花板，为下一阶段优化做铺垫 | 低 |

---

> **一句话总结：** 图片是当前的主要矛盾——主体小、背景乱、聚焦差，先把主图改到位，再看数据说话。CVR不是当前优先处理对象，但也需在后续迭代中持续关注。
'''
