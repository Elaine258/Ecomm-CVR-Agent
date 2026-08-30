from typing import TypedDict,List,Literal
from dotenv import load_dotenv
import os,json
from langgraph.graph import StateGraph,START,END
from langchain_openai import ChatOpenAI

load_dotenv()


# =========================
# 1. Agent State
# =========================

class AgentState(TypedDict):

    user_question:str

    product_id:str

    ctr:float
    cvr:float

    diagnosis:str

    next_actions:List[str]

    image_score:float
    image_problem:str

    price_score:float
    price_problem:str

    final_report:str



# =========================
# 2. LLM
# =========================

llm=ChatOpenAI(
    model="deepseek-v4-flash",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)



# =========================
# 3. LLM决策节点
# =========================

def llm_analyze_data(state:AgentState):

    print("\n--- LLM分析决策节点 ---")

    ctr=state["ctr"]
    cvr=state["cvr"]


    prompt=f"""
你是电商商品诊断专家。

当前数据:

CTR:{ctr}
CVR:{cvr}


判断销量下降原因。

业务规则:

1.
CTR < 0.01:
曝光不足
actions=["finish"]

2.
CTR > 0.05 且 CVR < 0.02:
点击正常但转化低
可能原因:
- 商品图片问题
- 商品价格问题

需要同时检查:
image
price


3.
其他情况:
actions=["finish"]


只返回JSON:

{{
"problem":"问题描述",
"actions":[
"check_image",
"check_price"
]
}}

"""

    response=llm.invoke(prompt)


    result=json.loads(response.content)


    state["diagnosis"]=result["problem"]

    state["next_actions"]=result["actions"]


    return state



# =========================
# 4. Tool1 图片检测
# =========================

def image_quality_check(state:AgentState):

    print("\n--- 图片检测Tool ---")


    state["image_score"]=65

    state["image_problem"]="商品主体不突出，背景干扰较强"


    return state



# =========================
# 5. Tool2 价格检测
# =========================

def price_check(state:AgentState):

    print("\n--- 价格检测Tool ---")


    state["price_score"]=48

    state["price_problem"]="价格高于竞品，竞争力不足"


    return state



# =========================
# 6. Router
# =========================

def route_tools(state:AgentState):

    print("\n--- Tool路由判断 ---")

    actions=state["next_actions"]


    if "check_image" in actions and "check_price" in actions:
        return "both"


    if "check_image" in actions:
        return "image"


    if "check_price" in actions:
        return "price"


    return "report"



# =========================
# 7. 多工具执行节点
# =========================

def run_tools(state:AgentState):

    actions=state["next_actions"]


    if "check_image" in actions:
        state=image_quality_check(state)


    if "check_price" in actions:
        state=price_check(state)


    return state



# =========================
# 8. 报告生成
# =========================

def generate_report(state:AgentState):

    print("\n--- 报告生成节点 ---")


    report=f"""
商品诊断报告

商品:
{state["product_id"]}


数据分析:
{state["diagnosis"]}


图片评分:
{state.get("image_score","无")}

图片问题:
{state.get("image_problem","无")}


价格评分:
{state.get("price_score","无")}

价格问题:
{state.get("price_problem","无")}


优化建议:

"""


    if state.get("image_problem"):
        report+="1. 优化商品主图，提高主体突出度。\n"


    if state.get("price_problem"):
        report+="2. 调整价格策略，提高竞争力。\n"


    state["final_report"]=report


    return state



# =========================
# 9. LangGraph
# =========================

workflow=StateGraph(AgentState)


workflow.add_node(
    "llm_analyze",
    llm_analyze_data
)


workflow.add_node(
    "tools",
    run_tools
)


workflow.add_node(
    "report",
    generate_report
)



workflow.add_edge(
    START,
    "llm_analyze"
)



workflow.add_conditional_edges(
    "llm_analyze",
    route_tools,
    {
        "both":"tools",
        "image":"tools",
        "price":"tools",
        "report":"report"
    }
)


workflow.add_edge(
    "tools",
    "report"
)


workflow.add_edge(
    "report",
    END
)


app=workflow.compile()



# =========================
# 10. Run
# =========================

if __name__=="__main__":


    input_state={

        "user_question":
        "为什么商品销量下降?",


        "product_id":
        "SKU001",


        "ctr":
        0.08,


        "cvr":
        0.01,


        "diagnosis":"",
        "next_actions":[],


        "image_score":0,
        "image_problem":"",


        "price_score":0,
        "price_problem":"",


        "final_report":""

    }
    result=app.invoke(input_state)
    print("\n====================")
    print(result["final_report"])



"output"
'''

--- LLM分析决策节点 ---

--- Tool路由判断 ---

--- 图片检测Tool ---

--- 价格检测Tool ---

--- 报告生成节点 ---

====================

商品诊断报告

商品:
SKU001


数据分析:
点击正常但转化低


图片评分:
65

图片问题:
商品主体不突出，背景干扰较强


价格评分:
48

价格问题:
价格高于竞品，竞争力不足


优化建议:

1. 优化商品主图，提高主体突出度。
2. 调整价格策略，提高竞争力。
'''
