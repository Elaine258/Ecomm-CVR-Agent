'''
from typing import TypedDict, Literal
from langgraph.graph import (
    StateGraph,
    START,
    END
)


# ==================================================
# 1. 定义 Agent State
# ==================================================

class AgentState(TypedDict):

    # 用户问题
    user_question: str

    # 商品数据
    product_id: str
    ctr: float
    cvr: float

    # Agent中间结果
    diagnosis: str
    next_action: str

    # 工具结果：图片
    image_score: float
    image_problem: str

    # 【实验2新增】价格工具字段
    price_score: float
    price_problem: str

    # 最终输出
    final_report: str

# ==================================================
# 2. 节点 Node
# ==================================================


# -------------------------------
# Node 1:
# 数据分析节点
# -------------------------------

def analyze_data(
        state: AgentState
):

    print("\n--- 数据分析节点 ---")
    ctr = state["ctr"]
    cvr = state["cvr"]

    # 实验1：曝光不足
    if ctr < 0.01:
        state["diagnosis"] = "曝光不足，点击率过低"
        state["next_action"] = "finish"

    elif ctr > 0.05 and cvr < 0.02:
        # CVR低：这里演示两种分支，这里示例走价格；你也可以改成check_image
        # 业务场景：CTR正常、CVR低，有可能图片问题 / 价格问题
        state["diagnosis"] = "点击率正常，但是转化率异常下降"
        state["next_action"] = "check_price"

    else:
        state["diagnosis"] = "当前指标没有明显异常"
        state["next_action"] = "finish"
    return state


# -------------------------------
# Node 2:
# 图片质量检测 Tool
# -------------------------------

def image_quality_check(
        state: AgentState
):
    print("\n--- 图片检测节点 ---")
    state["image_score"] = 65
    state["image_problem"] = "商品主体不突出，背景干扰较强"
    return state


# -------------------------------
# Node 3:【实验2新增】价格检测 Tool
# -------------------------------
def check_price(state: AgentState):
    print("\n--- 价格检测节点 ---")
    # 模拟价格分析工具返回
    state["price_score"] = 48
    state["price_problem"] = "商品定价高于同类竞品，价格竞争力弱"
    return state


# -------------------------------
# Node 4:
# 最终报告节点
# -------------------------------

def generate_report(
        state: AgentState
):

    print("\n--- 报告生成节点 ---")

    report = f"""
商品诊断报告

商品ID:
{state['product_id']}
数据分析:
{state['diagnosis']}

图片评分:
{state.get('image_score','无')}
图片问题:
{state.get('image_problem','无')}

价格评分:
{state.get('price_score','无')}
价格问题:
{state.get('price_problem','无')}

优化建议:
"""
    # 根据工具结果拼接建议
    if state.get("image_problem"):
        report += "优化商品主图，提升商品主体表达。\n"
    if state.get("price_problem"):
        report += "评估定价，参考竞品调整价格，提升价格竞争力。\n"

    state["final_report"] = report
    return state


# ==================================================
# 3. 条件判断 Router
# ==================================================

def decide_next_step(
        state: AgentState
) -> Literal["image", "price", "report"]:
    """实验2：新增price分支返回值"""
    print("\n--- 判断下一步 ---")
    action = state["next_action"]
    if action == "check_image":
        return "image"
    elif action == "check_price":
        return "price"
    else:
        return "report"


# ==================================================
# 4. 创建 LangGraph
# ==================================================

workflow = StateGraph(
    AgentState
)

# 添加节点
workflow.add_node("analyze", analyze_data)
workflow.add_node("image", image_quality_check)
workflow.add_node("price", check_price)   # 实验2新增价格节点
workflow.add_node("report", generate_report)

# 设置入口
workflow.add_edge(START, "analyze")

# 条件边：analyze出来，3个路由方向 image / price / report
workflow.add_conditional_edges(
    "analyze",
    decide_next_step,
    {
        "image": "image",
        "price": "price",
        "report": "report"
    }
)

workflow.add_edge("image", "report")
workflow.add_edge("price", "report")  # 价格工具跑完流向报告

workflow.add_edge("report", END)

# 编译
app = workflow.compile()


# ==================================================
# 5. 运行 Agent
# ==================================================

if __name__ == "__main__":
    # CTR正常 CVR低，会走到 check_price
    input_state = {
        "user_question": "为什么商品销量下降？",
        "product_id": "SKU001",
        "ctr": 0.08,
        "cvr": 0.01,
        "diagnosis": "",
        "next_action": "",
        "image_score": 0,
        "image_problem": "",
        "price_score": 0,
        "price_problem": "",
        "final_report": ""
    }

    result = app.invoke(input_state)

    print("\n====================")
    print(result["final_report"])
'''



"outout"
'''
--- 数据分析节点 ---

--- 判断下一步 ---

--- 图片检测节点 ---

--- 报告生成节点 ---

====================

商品诊断报告

商品ID:
SKU001
数据分析:
点击率正常，但是转化率异常下降
图片评分:
65
图片问题:
商品主体不突出，背景干扰较强

优化建议:
优化商品主图，
提升商品主体表达。
'''


'''
#增加实验1,不变;又增加实验2--output

--- 数据分析节点 ---

--- 判断下一步 ---

--- 价格检测节点 ---

--- 报告生成节点 ---

====================

商品诊断报告

商品ID:
SKU001
数据分析:
点击率正常，但是转化率异常下降

图片评分:
0
图片问题:


价格评分:
48
价格问题:
商品定价高于同类竞品，价格竞争力弱

优化建议:
评估定价，参考竞品调整价格，提升价格竞争力。
'''




from typing import TypedDict, Literal
from dotenv import load_dotenv
import os
from langgraph.graph import (
    StateGraph,
    START,
    END
)
from langchain_openai import ChatOpenAI

load_dotenv()

# ==================================================
# 1. 定义 Agent State
# ==================================================

class AgentState(TypedDict):

    # 用户问题
    user_question: str

    # 商品数据
    product_id: str
    ctr: float
    cvr: float

    # Agent中间结果
    diagnosis: str
    next_actions:list[str]

    # 工具结果：图片
    image_score: float
    image_problem: str

    # 价格工具字段
    price_score: float
    price_problem: str

    # 最终输出
    final_report: str

# ==================================================
# LLM初始化
# ==================================================
llm = ChatOpenAI(
    model="deepseek-v4-flash",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

# ==================================================
# 2. 节点 Node
# ==================================================

# -------------------------------
# Node1：LLM决策节点（实验3，移除硬编码if‑else）
# -------------------------------
def llm_analyze_data(state: AgentState):
    print("\n--- LLM数据分析决策节点 ---")
    ctr = state["ctr"]
    cvr = state["cvr"]

    prompt = f"""
你是商品投放诊断专家。
输入指标：
ctr={ctr}, cvr={cvr}

业务常识：
1. ctr <0.01：曝光不足，无需调用工具，action=finish
2. ctr>0.05 同时 cvr<0.02：点击率正常但转化率低，可能是图片问题或者价格问题
3. 其他情况：指标无明显异常，action=finish

严格只返回JSON，不要额外文字：
{{
"problem":"问题描述",
"action":"check_image | check_price | finish"
}}
"""
    resp = llm.invoke(prompt)
    import json
    res = json.loads(resp.content)

    state["diagnosis"] = res["problem"]
    state["next_action"] = res["action"]
    return state


# -------------------------------
# Node2: 图片质量检测 Tool
# -------------------------------
def image_quality_check(state: AgentState):
    print("\n--- 图片检测节点 ---")
    state["image_score"] = 65
    state["image_problem"] = "商品主体不突出，背景干扰较强"
    return state


# -------------------------------
# Node3: 价格检测 Tool
# -------------------------------
def check_price(state: AgentState):
    print("\n--- 价格检测节点 ---")
    state["price_score"] = 48
    state["price_problem"] = "商品定价高于同类竞品，价格竞争力弱"
    return state


# -------------------------------
# Node4: 最终报告节点
# -------------------------------
def generate_report(state: AgentState):
    print("\n--- 报告生成节点 ---")

    report = f"""
商品诊断报告

商品ID:
{state['product_id']}
数据分析:
{state['diagnosis']}

图片评分:
{state.get('image_score','无')}
图片问题:
{state.get('image_problem','无')}

价格评分:
{state.get('price_score','无')}
价格问题:
{state.get('price_problem','无')}

优化建议:
"""
    if state.get("image_problem"):
        report += "优化商品主图，提升商品主体表达。\n"
    if state.get("price_problem"):
        report += "评估定价，参考竞品调整价格，提升价格竞争力。\n"

    state["final_report"] = report
    return state


# ==================================================
# 3. 条件判断 Router
# ==================================================
def decide_next_step(state: AgentState) -> Literal["image", "price", "report"]:
    print("\n--- 判断下一步 ---")
    action = state["next_action"]
    if action == "check_image":
        return "image"
    elif action == "check_price":
        return "price"
    else:
        return "report"


# ==================================================
# 4. 创建 LangGraph
# ==================================================
workflow = StateGraph(AgentState)

# 添加节点，节点名改为 llm_analyze
workflow.add_node("llm_analyze", llm_analyze_data)
workflow.add_node("image", image_quality_check)
workflow.add_node("price", check_price)
workflow.add_node("report", generate_report)

workflow.add_edge(START, "llm_analyze")

workflow.add_conditional_edges(
    "llm_analyze",
    decide_next_step,
    {
        "image": "image",
        "price": "price",
        "report": "report"
    }
)

workflow.add_edge("image", "report")
workflow.add_edge("price", "report")
workflow.add_edge("report", END)

app = workflow.compile()


# ==================================================
# 5. 运行 Agent
# ==================================================
if __name__ == "__main__":
    # case1：ctr正常cvr低，LLM自行选择check_image / check_price
    input_state = {
        "user_question": "为什么商品销量下降？",
        "product_id": "SKU001",
        "ctr": 0.08,
        "cvr": 0.01,
        "diagnosis": "",
        "next_action": "",
        "image_score": 0,
        "image_problem": "",
        "price_score": 0,
        "price_problem": "",
        "final_report": ""
    }

    # case2：曝光不足，ctr=0.005，LLM输出action=finish，直接进报告
    # input_state = {
    #     "user_question": "为什么商品销量下降？",
    #     "product_id": "SKU002",
    #     "ctr": 0.005,
    #     "cvr": 0.03,
    #     "diagnosis": "",
    #     "next_action": "",
    #     "image_score": 0,
    #     "image_problem": "",
    #     "price_score": 0,
    #     "price_problem": "",
    #     "final_report": ""
    # }

    result = app.invoke(input_state)

    print("\n====================")
    print(result["final_report"])


"output"
'''

--- LLM数据分析决策节点 ---

--- 判断下一步 ---

--- 图片检测节点 ---

--- 报告生成节点 ---

====================

商品诊断报告

商品ID:
SKU001
数据分析:
点击率正常但转化率低，可能是图片问题或者价格问题

图片评分:
65
图片问题:
商品主体不突出，背景干扰较强

价格评分:
0
价格问题:


优化建议:
优化商品主图，提升商品主体表达。
'''
