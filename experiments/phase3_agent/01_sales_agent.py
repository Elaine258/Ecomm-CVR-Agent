from typing import TypedDict


class AgentState(TypedDict):
    user_question:str
    ctr:float
    cvr:float
    diagnosis:str
    next_action:str
    image_problem:str

def analyze_data(state):
    ctr = state["ctr"]
    cvr = state["cvr"]
    if ctr > 0.05 and cvr < 0.02:
        state["diagnosis"] = \
        "点击正常但转化率低"
        state["next_action"] = \
        "check_image"
    else:
        state["diagnosis"] = \
        "数据正常"
    return state

def image_check(state):
    state["image_problem"] = \
    "商品主体不突出"
    return state

def generate_report(state):
    print(
    f"""
    问题:
    {state['diagnosis']}
    建议:
    优化商品图片
    """
    )
    return state

from langgraph.graph import StateGraph


graph = StateGraph(AgentState)


graph.add_node(
"analyze",
analyze_data
)


graph.add_node(
"image",
image_check
)


graph.add_node(
"report",
generate_report
)


graph.set_entry_point(
"analyze"
)


graph.add_edge(
"analyze",
"image"
)


graph.add_edge(
"image",
"report"
)


app = graph.compile()
