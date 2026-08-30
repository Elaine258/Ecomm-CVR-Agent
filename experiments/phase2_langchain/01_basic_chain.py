import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()
llm = ChatOpenAI(
    model="deepseek-v4-flash",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

prompt = ChatPromptTemplate.from_template(
    """
你是一名AI产品经理。
请解释：
{question}
"""
)

chain = prompt | llm
response = chain.invoke(
    {
        "question": "什么是Agent？"
    }
)
print(response.content)



"output1"
'''
作为AI产品经理，解释“Agent（智能体）”可以从三个层面展开：**概念定义、核心能力、产品视角的理解**。

---

## 一、概念定义

**Agent（智能体）** 是一种能够 **感知环境、做出决策、执行行动** 的AI系统。它不只是“回答问题”，而是为了完成某个目标，可以自主地：

- 理解用户意图
- 拆解任务
- 调用工具/API
- 获取信息
- 执行操作
- 根据结果自我修正

简单说：
**Chatbot 告诉你“怎么做”，Agent 直接帮你做。**

---

## 二、Agent 的核心能力

一个成熟的 Agent 通常具备以下五大能力：

| 能力 | 说明 | 举例 |
|---|---|---|
| **感知 Perception** | 理解用户输入、环境状态、多模态信息 | 读取邮件、识别图片、理解语音 |
| **规划 Planning** | 把复杂任务拆解为可执行的子步骤 | 制定旅行计划：订机票→订酒店→排行程 |
| **记忆 Memory** | 短期记忆（当前对话）+ 长期记忆（用户偏好/历史） | 记住用户常喝的咖啡口味 |
| **工具使用 Tool Use** | 调用外部API、数据库、网页、软件 | 查天气、发邮件、操作Excel |
| **反思与修正 Reflection** | 根据执行结果调整策略，失败后重试 | 下单失败→自动切换支付方式 |

---

## 三、Agent vs Chatbot 的区别

| 维度 | Chatbot | Agent |
|---|---|---|
| 目标 | 回答问题 | 完成任务 |
| 交互方式 | 一问一答 | 多轮自主执行 |
| 工具调用 | 很少 | 频繁 |
| 记忆 | 弱 | 强 |
| 主动性 | 被动响应 | 可主动推进 |
| 结果 | 信息 | 行动+结果 |

> 一句话：Chatbot 是“嘴”，Agent 是“嘴+手+脑”。

---

## 四、产品经理如何理解 Agent？

从产品视角，Agent 不是单一功能，而是一种**新的产品形态**。PM 需要关注：

### 1. 用户价值
Agent 的核心价值是 **帮用户省时间、省精力、完成目标**。
例如：
- 客服 Agent：自动退款、查询订单、安抚情绪
- 办公 Agent：自动整理会议纪要、发周报、安排日程
- 编程 Agent：根据需求写代码、跑测试、修复bug

### 2. 产品设计重点
- **目标设定**：Agent 要完成什么？边界在哪里？
- **工具设计**：它需要哪些权限？如何安全调用？
- **人机交互**：什么时候应该让用户确认？什么时候自主执行？
- **反馈机制**：如何让用户了解 Agent 的进展和决策依据？
- **失败兜底**：Agent 做错了怎么办？如何撤回、纠正、升级人工？

### 3. 风险管理
PM 必须关注：
- **可控性**：Agent 不能越权、不能乱操作
- **安全性**：防止 prompt 注入、恶意指令
- **透明性**：用户需要知道“AI 正在替你做什么”
- **责任归属**：Agent 出错，是产品责任还是用户责任？

---

## 五、一句话总结

**Agent 是一个以目标为导向、能够独立思考并使用工具采取行动的 AI 系统。**
对产品经理来说，Agent 意味着从“设计功能”转向“设计目标、边界和信任体系”。未来的好产品，不是功能最多的，而是**最懂用户、最可靠、最敢放手让它干事的 Agent**。
'''
