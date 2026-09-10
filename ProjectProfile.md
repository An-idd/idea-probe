# Project Profile

## 1. Goal

寻找适合个人或小团队开发、能够快速验证，并具有真实开发者需求的 GitHub 开源项目。

优先：

- Developer Tools
- AI Agent Infrastructure
- MCP Ecosystem
- RAG / LLM Reliability
- AI Evaluation
- Automation
- SaaS Developer Infrastructure
- OCR / PDF Workflow
- Backend / Infrastructure Tooling

---

# 2. Technical Capability

主要技术能力：

- Python
- Java
- FastAPI
- Spring
- Docker
- Kubernetes

AI / LLM：

- LLM Application Development
- AI Agent
- LangChain
- LangGraph
- MCP
- Tool / Function Calling
- Agent State / Checkpoint
- Human-in-the-Loop
- RAG
- Dense + Sparse Hybrid Retrieval
- Reranker
- Vector Database
- LLM Eval
- Structured Output
- Prompt / Input Validation
- LLM Reliability Engineering

---

# 3. Preferred Project Characteristics

优先考虑：

- 一个开发者可以独立完成第一版；
- MVP 可以在较短周期内完成；
- 能开源；
- 有明确目标用户；
- 可以通过 GitHub / Hacker News / Reddit 等渠道找到早期用户；
- 不依赖大量人工运营；
- 不需要大规模 GPU 训练；
- 能直接通过真实用户使用验证价值；
- 核心价值不是单纯调用某个 LLM API。

---

# 4. Preferred Users

优先服务：

- AI Application Developers
- AI Agent Developers
- Backend Engineers
- Open-source Developers
- Small Engineering Teams
- SaaS Engineering Teams

---

# 5. Resource Constraints

默认假设：

- 个人或小团队开发；
- 优先使用公开数据；
- 优先使用成熟开源依赖；
- 避免高额 GPU 成本；
- 避免需要大量付费数据；
- MVP 应尽量可以在普通云服务器或本地环境运行。

---

# 6. Anti-patterns

默认降低优先级：

- 通用聊天机器人；
- ChatGPT Wrapper；
- 只是替换 Prompt；
- 只是替换模型；
- 没有明确 Target User；
- 没有真实 Problem Evidence；
- 为了使用 Agent 而使用 Agent；
- “All-in-one AI Platform”；
- 需要很多模块才能体现价值；
- 一开始就需要复杂分布式架构；
- 主要竞争优势只是 UI 更好看；
- 已有成熟开源项目完整覆盖需求。

---

# 7. MVP Preference

好的 MVP 通常：

```text
一个明确问题
+
一个核心 Workflow
+
少量关键功能
```

优先：

```text
CLI
Library
API
Developer Dashboard
Plugin
MCP Server
Testing / Eval Tool
Observability Tool
Automation Tool
```

不要第一版同时包含：

```text
平台
Marketplace
Team Collaboration
Billing
复杂 RBAC
多租户
移动端
十几个集成
```

除非这些能力本身就是被验证的核心需求。

---

# 8. Idea Evaluation Preference

发现项目 Idea 时按以下顺序思考：

1. 是否存在真实 Problem；
2. 是否有多个独立 Evidence；
3. 用户当前如何解决；
4. 现有工具有什么明显缺口；
5. 是否存在真正 Differentiation；
6. MVP 是否足够小；
7. 开发完成后在哪里找到第一批用户；
8. 维护成本是否合理。

不要把：

```text
技术新颖度
```

放在：

```text
用户问题真实性
```

之前。

---

# 9. Final Principle

项目不是因为：

> “AI 可以做到”

就值得开发。

只有满足：

> **有人确实遇到问题 + 当前解决方式不够好 + 可以做出明显更好的小型方案**

才应进入 GO。