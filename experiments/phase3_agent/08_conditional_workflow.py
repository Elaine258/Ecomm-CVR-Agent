import os

from typing import TypedDict, Literal
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langgraph.graph import (
    StateGraph,
    START,
    END
)


load_dotenv()


# ==================================================
# 1. 定义 State
# ==================================================

class AgentState(TypedDict):

    # 用户问题
    user_question: str

    # 商品基础数据
    product_id: str
    ctr: float
    cvr: float

    # Agent中间结果
    diagnosis: str
    next_action: str

    # 图片工具结果
    image_score: float
    image_problem: str

    # 价格工具结果
    price_score: float
    price_problem: str

    # 最终输出
    final_report: str


# ==================================================
# 2. LLM
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


# ==================================================
# 3. Diagnose Node
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

请根据现有信息进行初步诊断。

你必须选择下一步分析方向，只能选择：

image
price
report

判断原则：

- CTR明显偏低，优先检查图片问题 → image
- CTR尚可但CVR明显偏低，优先检查价格问题 → price
- 当前信息已经足够或没有明显异常 → report

最后严格按照以下格式输出：

诊断：xxx
下一步：image / price / report
"""

    response = llm.invoke(prompt)

    content = response.content

    print(content)

    # -------------------------------
    # 简单提取 next_action
    # -------------------------------

    lower_content = content.lower()

    if "下一步：image" in lower_content or "下一步: image" in lower_content:
        next_action = "image"

    elif "下一步：price" in lower_content or "下一步: price" in lower_content:
        next_action = "price"

    else:
        next_action = "report"

    return {
        "diagnosis": content,
        "next_action": next_action
    }


# ==================================================
# 4. Image Tool Node
# ==================================================

def image_tool_node(state: AgentState):

    print("\n========== Image Tool Node ==========")

    # 这里暂时模拟图片模型结果
    # 后面可以替换成真正图片分析模型 / API

    image_score = 0.42

    image_problem = (
        "商品主体占比偏小，背景干扰较强，"
        "主视觉吸引力不足。"
    )

    print("image_score:", image_score)
    print("image_problem:", image_problem)

    return {
        "image_score": image_score,
        "image_problem": image_problem
    }


# ==================================================
# 5. Price Tool Node
# ==================================================

def price_tool_node(state: AgentState):

    print("\n========== Price Tool Node ==========")

    # 暂时模拟价格分析结果
    # 后面可以替换成 TheLook / SQL / 竞品价格数据

    price_score = 0.58

    price_problem = (
        "当前商品价格高于同类商品平均水平，"
        "可能对转化率产生影响。"
    )

    print("price_score:", price_score)
    print("price_problem:", price_problem)

    return {
        "price_score": price_score,
        "price_problem": price_problem
    }


# ==================================================
# 6. Router
# ==================================================

def route_after_diagnosis(
    state: AgentState
) -> Literal[
    "image_tool",
    "price_tool",
    "report"
]:

    print("\n========== Router ==========")

    next_action = state["next_action"]

    print(
        "next_action:",
        next_action
    )

    if next_action == "image":
        return "image_tool"

    if next_action == "price":
        return "price_tool"

    return "report"


# ==================================================
# 7. Report Node
# ==================================================

def report_node(state: AgentState):

    print("\n========== Report Node ==========")

    prompt = f"""
你是一名电商运营分析专家。

请根据下面的信息生成最终诊断报告。

用户问题：
{state["user_question"]}

商品：
{state["product_id"]}

CTR：
{state["ctr"]}

CVR：
{state["cvr"]}

初步诊断：
{state["diagnosis"]}

图片分析结果：
image_score = {state["image_score"]}
image_problem = {state["image_problem"]}

价格分析结果：
price_score = {state["price_score"]}
price_problem = {state["price_problem"]}

要求：

1. 明确区分已知事实和推断。
2. 不允许编造不存在的数据。
3. 给出当前最可能的问题。
4. 给出下一步优化建议。
5. 如果某个工具没有执行，对应数据不要强行分析。
"""

    response = llm.invoke(prompt)

    return {
        "final_report":
            response.content
    }


# ==================================================
# 8. 创建 Graph
# ==================================================

builder = StateGraph(
    AgentState
)


# ==================================================
# 9. 添加 Nodes
# ==================================================

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
# 10. 添加 Edge
# ==================================================

builder.add_edge(
    START,
    "diagnose"
)


# Diagnose → 条件路由

builder.add_conditional_edges(
    "diagnose",
    route_after_diagnosis,
    {
        "image_tool":
            "image_tool",

        "price_tool":
            "price_tool",

        "report":
            "report"
    }
)


# Tool执行完统一进入Report

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

result = graph.invoke(
    {
        "user_question":
            "为什么这个商品表现不好？",

        "product_id":
            "SKU001",

        # CTR较低
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

        "final_report":
            ""
    }
)


# ==================================================
# 13. 查看最终 State
# ==================================================

print(
    "\n\n========== Final State =========="
)

for key, value in result.items():

    print(
        f"\n{key}:"
    )
    print(
        value
    )

print(
    "\n\n========== Final Report =========="
)
print(
    result["final_report"]
)
