# Project Research Mode

## 1. 背景

本项目基于 EvoMap/AutoResearch 改造。

AutoResearch 原始定位是：

> 研究信号 → 学术 Idea → 多模型交叉评审 → 实验计划 → 实验执行 → Code Review → Critic → Paper-ready Evidence

本项目需要新增一种独立模式：

> **Project Research**

用于 GitHub / 开源项目正式开发前的：

- 用户痛点发现
- 项目机会发现
- Idea 生成
- 竞品分析
- 需求真实性验证
- 技术可行性判断
- MVP 范围评估
- Idea 反方验证
- Project Brief 输出

Project Research **只负责“这个项目值不值得做、应该做什么”**。

不负责：

- 编写项目业务代码
- Code Review
- 自动执行开发
- Pilot Experiment
- Benchmark 实验
- Critic / Blind Review
- Paper Plan
- `ar-runtime`

---

# 2. 核心目标

系统输入：

1. GitHub / Hacker News / Reddit / 技术社区等外部信号；
2. 用户自己的技术能力、项目偏好和资源约束；
3. 可选的用户指定研究主题。

系统输出若干经过验证的：

```text
Project Idea
    +
Problem Evidence
    +
Competitor Evidence
    +
Differentiation
    +
MVP Scope
    +
Risks
    +
GO / HOLD / REJECT
```

最终输出称为：

```text
Project Research Brief
```

---

# 3. 设计原则

## 3.1 Evidence First

模型的判断不能作为 Idea 成立的主要依据。

优先级：

```text
真实用户证据
>
竞品事实
>
GitHub / 社区数据
>
模型推理
>
模型投票
```

例如：

三个模型都认为某个 Idea 很好，

但：

```text
没有用户讨论
没有 Issue
没有实际需求
已有成熟竞品
```

则应判定为低优先级。

---

## 3.2 默认单模型

Project Research 不采用 AutoResearch 原来的：

```text
3+ models
    ↓
cross review
    ↓
majority vote
```

默认：

```text
1 × Ideator
```

负责：

- 理解信号
- 提取问题
- 生成候选项目 Idea
- 初步分析价值

---

## 3.3 Red Team 按需运行

只对排名靠前的候选进行第二模型反方审查。

默认：

```text
Top 3 → Red Team
```

Red Team 的目标不是重新评分，也不是帮助完善 Idea。

它的任务是：

> 尽可能证明这个项目不值得做。

重点寻找：

- 伪需求
- 成熟竞品
- 没有迁移理由
- 差异化太弱
- MVP 实际成本被低估
- 用户获取困难
- 长期维护成本过高
- API / 数据 / 平台依赖风险
- 项目只是现有产品的简单 Wrapper

---

# 4. 总体流程

```text
External Signals
       │
       ▼
Collect
       │
       ▼
Normalize
       │
       ▼
Deduplicate
       │
       ▼
Opportunity Screener
       │
       ▼
Problem / Pain Point Extraction
       │
       ▼
Project Idea Generation
       │
       ▼
Evidence Collection
       │
       ├──── User Evidence
       ├──── GitHub Evidence
       ├──── Competitor Evidence
       └──── Trend Evidence
       │
       ▼
Evidence-based Validation
       │
       ▼
Rank
       │
       ▼
Top K Red Team
       │
       ▼
GO / HOLD / REJECT
       │
       ▼
Project Research Brief
```

---

# 5. 与原 AutoResearch 的关系

不要删除原来的：

```text
idea_generation.py
src/idea_forge/
ar-runtime/
```

第一版采用新增模式方式实现。

新增：

```text
project_research.py

src/project_research/
├── __init__.py
├── pipeline.py
├── ideation.py
├── validation.py
├── evidence.py
├── red_team.py
├── ranking.py
├── brief.py
├── schemas.py
└── prompts.py
```

这样：

```text
python idea_generation.py
```

仍然执行原 AutoResearch。

而：

```text
python project_research.py
```

执行新的 Project Research。

Project Research 不 import、不启动 `ar-runtime`。

---

# 6. 尽量复用的现有模块

优先复用：

```text
src/channels.py
src/collectors/
src/llm_client.py
src/providers.py
src/api_retry.py
knowledge_base/
```

可以复用或抽取：

```text
normalize_post()
collect_all_channels()
全局 URL 去重
标题去重
checkpoint 写入
provider role routing
并发控制
```

不要重复实现：

- LLM Provider
- Retry
- Endpoint 配置
- 基础 Collector 注册机制

---

# 7. 数据源调整

Project Research 应优先使用开发者需求相关信号。

## P0

### GitHub

不仅关注 Trending。

长期目标需要支持：

```text
Repositories
Issues
Discussions
README
Release
Stars
Forks
Last Commit
Archived
Open Issues
Issue Comments
```

重点寻找：

```text
重复 Feature Request
长期未解决 Issue
高互动 Issue
用户 workaround
用户抱怨
维护停滞
迁移需求
API 缺口
兼容性问题
```

---

### Hacker News

重点：

```text
Ask HN
Show HN
开发工具讨论
产品替代方案讨论
```

需要关注正文和评论中的痛点，而不仅仅是热度。

---

### Reddit

降低对：

```text
r/MachineLearning
```

的硬绑定。

Project Research 应允许配置 Subreddit，例如：

```json
[
  "LocalLLaMA",
  "selfhosted",
  "opensource",
  "Python",
  "golang",
  "webdev"
]
```

具体列表通过配置决定。

---

## P1

未来可以增加：

```text
Stack Overflow
PyPI
npm
Product Hunt
Lobsters
Dev.to
框架官方 Forum
GitHub Discussions Search
```

第一版不要为了覆盖数据源导致范围失控。

---

# 8. Signal 数据模型

统一 Signal：

```json
{
  "id": "stable-id",
  "source": "github_issue",
  "source_type": "community",
  "title": "...",
  "url": "...",
  "summary": "...",
  "author": "...",
  "published_at": "...",

  "metrics": {
    "score": 0,
    "comments": 0,
    "stars": 0
  },

  "repository": {
    "name": null,
    "stars": null,
    "open_issues": null,
    "last_updated": null,
    "archived": null
  },

  "raw_metadata": {}
}
```

所有 collector 最终应转换到统一 Schema。

---

# 9. Opportunity Screener

原 AutoResearch Screener 判断：

> 是否包含研究 insight。

Project Research 改为判断：

> 是否包含值得进一步研究的真实项目机会。

重点保留：

```text
用户明确描述问题
用户正在寻找替代方案
用户使用 workaround
多人重复遇到类似问题
现有工具使用复杂
现有项目维护停滞
某个新技术变化产生新的工具需求
多个项目重复造相似轮子
```

过滤：

```text
纯新闻
纯营销
纯 Release Announcement
没有问题描述的 Show Case
单纯模型排行榜
纯观点争论
没有目标用户的问题
```

Screener 应偏向高 Recall。

宁愿留下少量噪音，不应在第一层过度删除候选。

---

# 10. Problem Extraction

对通过 Screener 的 Signal 提取：

```json
{
  "problem": "...",
  "target_user": "...",
  "current_solution": "...",
  "pain": "...",
  "workaround": "...",
  "desired_outcome": "...",
  "evidence_quote_or_summary": "...",
  "evidence_url": "...",
  "confidence": 0.0
}
```

关键要求：

Problem 和 Solution 分开。

错误：

```text
用户需要一个 AI Agent observability platform
```

正确：

```text
Problem:
Agent 开发者难以定位一次复杂 Tool Calling 失败发生在哪个子 Agent。

Current solution:
查看分散日志或手动增加 tracing。

Potential solution:
暂时未知。
```

不能在 Problem Extraction 阶段提前把某个解决方案当成事实。

---

# 11. Project Ideation

输入：

```text
Problem Evidence
+
External Signal
+
Knowledge Base
+
Project Constraints
```

输出每个问题最多：

```text
1～3 个 Idea
```

不要为了数量制造 Idea。

Idea Schema：

```json
{
  "id": "...",

  "name": "...",

  "one_liner": "...",

  "problem": "...",

  "target_user": "...",

  "current_solution": "...",

  "proposed_solution": "...",

  "why_now": "...",

  "differentiation_hypothesis": "...",

  "mvp": [
    "...",
    "...",
    "..."
  ],

  "non_goals": [
    "...",
    "..."
  ],

  "source_signal_ids": []
}
```

---

# 12. Project Idea 生成要求

Ideator 必须遵守：

### 必须

- 解决明确问题
- 明确目标用户
- 描述用户现在如何解决
- 能指出现有方法的缺口
- MVP 范围较小
- 个人或小团队可以实现
- 能明确解释差异化

### 禁止

默认拒绝：

```text
通用 AI Assistant
通用 AI Agent
ChatGPT Wrapper
只换 Prompt 的项目
现有开源项目轻量套壳
没有用户场景的基础设施
只有技术炫技、没有使用场景
需要大规模 GPU 训练才能验证
```

---

# 13. Evidence Validation

这是整个系统最重要的部分。

模型投票不能替代 Evidence。

每个候选 Idea 建立：

```text
Evidence Pack
```

---

## 13.1 Problem Evidence

至少回答：

```text
谁遇到了问题？
在哪里表达？
问题是什么？
出现过多少个独立来源？
是否有 workaround？
问题现在还存在吗？
```

---

## 13.2 Competitor Evidence

至少找到主要：

```text
GitHub Repository
Commercial Product
Library
Framework feature
```

记录：

```json
{
  "name": "...",
  "url": "...",
  "type": "opensource",
  "stars": null,
  "last_updated": null,
  "strengths": [],
  "weaknesses": [],
  "overlap": "...",
  "gap": "..."
}
```

---

## 13.3 Evidence 独立性

同一个 GitHub Issue 的 20 条评论不能算作 20 个独立需求证据。

按来源聚类：

```text
repository
discussion thread
community post
author
```

计算：

```text
independent_evidence_count
```

---

# 14. Validation 维度

不要使用原 AutoResearch：

```text
D1 机制深度
D2 方法简洁
D3 实验充分
D4 Benchmark 时新性
```

替换为：

## P1 Problem Reality

问题是否真实存在？

---

## P2 Evidence Strength

是否存在多个独立证据？

---

## P3 Competitor Gap

已有工具是否没有很好解决？

---

## P4 Differentiation

新项目是否有明确的不同？

---

## P5 Feasibility

个人 / 小团队是否能实现？

---

## P6 MVP Clarity

MVP 是否可以控制范围？

---

## P7 Distribution

目标用户在哪里？

项目发布后是否存在自然分发渠道？

例如：

```text
GitHub Topic
Reddit Community
Hacker News
框架生态
已有 Issue 用户
```

---

## P8 Maintenance Risk

长期维护风险是否合理？

例如：

```text
频繁跟随第三方 API
浏览器自动化
大量第三方模型兼容
需要长期维护数据
平台 ToS 风险
```

---

# 15. 评分体系

模型输出具体理由，但最终分数应使用结构化结果。

建议：

```text
Problem Reality       20
Evidence Strength     20
Competitor Gap        15
Differentiation       15
Feasibility           10
MVP Clarity           10
Distribution           5
Maintenance            5

TOTAL                 100
```

建议：

```text
>= 75   GO candidate

60-74   HOLD / requires more evidence

< 60    REJECT
```

但存在 Hard Reject。

---

# 16. Hard Reject

无论总分多少，以下情况直接 REJECT：

```text
没有明确 target_user

没有任何外部需求证据

主要竞品已经完整覆盖核心需求且没有明显缺口

Idea 本质只是已有产品 Wrapper

MVP 明显超出 project constraints

核心依赖不可用或许可证不允许

关键差异化仅来自“使用更强模型”
```

---

# 17. Red Team

只有 Top K 执行。

默认：

```json
{
  "enabled": true,
  "top_k": 3
}
```

Red Team 输入：

```text
Idea
Evidence Pack
Competitor Analysis
Score
```

任务：

> 假设团队已经非常喜欢这个 Idea。你的工作是阻止团队因为确认偏误而投入几周开发。

必须检查：

1. Problem 是否可能是少数人的特殊需求；
2. Evidence 是否重复；
3. Competitor 是否遗漏；
4. 用户是否真的有迁移动机；
5. 差异化是否可以被竞品快速复制；
6. MVP 是否实际比预估复杂；
7. 用户是否愿意安装或部署；
8. 项目是否有天然 Distribution；
9. 维护成本是否会持续上升；
10. 是否存在更简单的解决方式。

输出：

```json
{
  "fatal_flaws": [],
  "major_risks": [],
  "missing_evidence": [],
  "counter_arguments": [],
  "verdict": "PASS | HOLD | REJECT"
}
```

---

# 18. 最终决策

系统输出：

```text
GO
HOLD
REJECT
```

含义：

## GO

证据已经足够支持制作 MVP。

不是表示：

> 这个项目一定会成功。

而是：

> 当前证据足够支持投入下一阶段的小成本开发。

---

## HOLD

Idea 看起来有价值，但还缺关键证据。

必须同时返回：

```text
下一步需要验证什么
```

例如：

```text
找 3 个独立用户
分析某竞品 Issue
发布 Landing Page
验证 API 可行性
```

---

## REJECT

当前不值得投入开发。

必须记录原因。

未来如果市场、技术或竞争格局发生变化，可以重新评估。

---

# 19. Project Research Brief

最终每个 Top Idea 输出 Markdown。

格式：

```markdown
# Project Research Brief

## 1. Project

Name:

One-liner:

Decision:

Score:

---

## 2. Target User

...

## 3. Problem

...

## 4. Problem Evidence

### Evidence 1
Source:
URL:
Finding:

### Evidence 2
...

Independent evidence count:

---

## 5. Current Solutions

...

## 6. Competitors

| Competitor | What it does | Strength | Weakness | Gap |
|---|---|---|---|---|

---

## 7. Proposed Solution

...

## 8. Differentiation

...

## 9. Why Now

...

## 10. MVP

1.
2.
3.

## 11. Non-goals

1.
2.

## 12. Technical Feasibility

...

## 13. Distribution

...

## 14. Risks

...

## 15. Red Team

Fatal flaws:

Major risks:

Missing evidence:

---

## 16. Decision

GO / HOLD / REJECT

Reason:

## 17. Next Validation Step

...
```

同时保存对应 JSON，Markdown 只用于人类阅读。

---

# 20. 输出目录

新增：

```text
data/project_research/
├── signals/
├── problems/
├── ideas/
├── evidence/
├── briefs/
└── runs/
```

一次运行：

```text
data/project_research/runs/20260910_120000.json
```

应记录：

```json
{
  "started_at": "...",
  "config": {},
  "signals": 0,
  "problems": 0,
  "ideas": 0,
  "validated": 0,
  "go": 0,
  "hold": 0,
  "reject": 0
}
```

---

# 21. Checkpoint

保留 AutoResearch 的断点恢复思想。

每个 Stage 完成后写入磁盘。

推荐：

```text
collect
screen
extract_problem
ideate
collect_evidence
validate
red_team
brief
```

如果：

```text
red_team
```

失败，重新执行时不应该再次调用前面所有 LLM。

---

# 22. 配置

建议新增：

```json
{
  "project_research": {
    "enabled": true,

    "lookback_days": 30,

    "max_signals": 200,

    "max_problems": 30,

    "max_ideas": 20,

    "top_k": 5,

    "min_independent_evidence": 2,

    "red_team": {
      "enabled": true,
      "top_k": 3
    },

    "decision_thresholds": {
      "go": 75,
      "hold": 60
    },

    "sources": {
      "github": true,
      "hackernews": true,
      "reddit": true,
      "academic": false,
      "media": false
    },

    "knowledge_directions": []
  }
}
```

Academic source 第一版默认：

```text
false
```

因为目标是项目需求，而不是论文 Idea。

用户可以针对 AI 基础设施项目重新开启。

---

# 23. LLM Roles

新增：

```json
{
  "project_ideator": {
    "models": [
      "..."
    ]
  },

  "project_validator": {
    "models": [
      "..."
    ]
  },

  "project_red_team": {
    "_optional": true,
    "models": [
      "..."
    ]
  },

  "project_brief_writer": {
    "models": [
      "..."
    ]
  }
}
```

这些 role 都采用：

```text
ordered fallback
```

而不是：

```text
all candidates used
```

因此：

```text
project_ideator
```

只调用第一个可用模型。

失败后才 fallback。

不要要求：

```text
_min_available = 3
```

---

# 24. 是否允许同一模型承担多个角色

允许。

例如：

```text
project_ideator = GPT-X
project_validator = GPT-X
project_brief_writer = GPT-X
```

因为核心 Validation 是 Evidence-based。

Red Team 如果开启，推荐使用不同模型，但不作为第一版硬约束。

---

# 25. Prompts

所有 Project Research Prompt 独立放：

```text
src/project_research/prompts.py
```

不要把长 Prompt 内嵌到 pipeline function。

至少包含：

```text
OPPORTUNITY_SCREEN_PROMPT
PROBLEM_EXTRACTION_PROMPT
PROJECT_IDEATION_PROMPT
VALIDATION_PROMPT
RED_TEAM_PROMPT
BRIEF_PROMPT
```

---

# 26. Project Ideator Prompt 核心约束

System intent：

```text
你是一名擅长开发者工具和开源产品发现的 Product Researcher。

你的目标不是提出听起来创新的 Idea，而是寻找：
真实存在的问题 + 现有方案明显缺口 + 可以低成本验证的项目机会。

任何没有用户证据支撑的假设都必须明确标记为 hypothesis。

不要因为技术有趣就建议开发。
```

必须回答：

```text
用户是谁
问题是什么
现在如何解决
为什么现有方法不够好
项目做什么
项目不做什么
为什么现在值得做
最小 MVP 是什么
需要进一步验证什么
```

---

# 27. Evidence Validator Prompt 核心约束

```text
不要评价 Idea 听起来是否有趣。

只能根据提供的 Evidence 判断。

区分：
FACT
INFERENCE
HYPOTHESIS

如果证据不足，必须降低评分。

不得自行编造：
GitHub Star
Issue 数
用户数量
竞品功能
发布日期
```

---

# 28. Red Team Prompt 核心约束

```text
你的目标不是改善 Idea。

你的目标是发现停止开发这个项目的充分理由。

优先寻找：
伪需求
重复证据
遗漏竞品
更简单替代方案
迁移成本
维护风险
Distribution 风险

如果没有致命问题，也不要为了完成任务捏造问题。
```

---

# 29. Knowledge Base

继续使用：

```text
knowledge_base/
```

但 Project Research 不要求使用原来的 academic directions。

建议增加：

```text
knowledge_base/project/
├── project_profile.md
├── preferred_domains.md
├── anti_patterns.md
└── known_opportunities.md
```

---

# 30. project_profile.md

用于描述：

```text
技术能力
可以投入的时间
算力
预算
项目偏好
目标用户
不希望开发什么
```

Project Ideator 和 Feasibility Validator 必须读取该文件。

---

# 31. CLI

第一版：

```bash
python project_research.py
```

支持：

```bash
python project_research.py \
  --topic "AI Agent developer tools"
```

可选：

```bash
python project_research.py \
  --topic "MCP observability" \
  --top-k 5
```

建议支持：

```text
--resume
--no-red-team
--sources
--lookback-days
--top-k
```

但第一版不需要一次实现所有 CLI 参数。

---

# 32. Topic 模式

当用户指定：

```bash
--topic "MCP observability"
```

Screener、Problem Extraction 和 Idea Generation 都应围绕 Topic。

但不能要求 Signal 标题必须包含完全相同关键词。

采用语义相关性，而不是 substring filter。

---

# 33. Candidate Ranking

排序发生在 Red Team 前。

Rank Score：

```text
Validation Score
+
Evidence Diversity Bonus
+
Strong Problem Signal Bonus
-
Maintenance Risk
-
Competition Saturation
```

第一版可以简单使用：

```text
validation_score
```

不要过早设计复杂公式。

---

# 34. 去重

必须支持：

## Signal Deduplication

```text
URL
Normalized Title
```

---

## Problem Deduplication

使用 LLM 或 embedding 合并：

```text
语义上属于同一个用户问题
```

---

## Idea Deduplication

避免：

```text
MCP Debugger
MCP Inspector
MCP Tool Debug Platform
```

被当成三个不同 Idea。

---

# 35. Provenance

每个 Idea 必须可追溯到：

```text
Idea
↓
Problem
↓
Evidence
↓
Signal URL
```

禁止出现：

```text
Idea 有一个“社区需求很高”的判断
```

但不知道这个判断来自哪里。

---

# 36. 明确不做的事情

第一阶段严禁 Scope Creep。

不实现：

```text
自动 Coding
代码生成
自动创建 GitHub Repo
自动提交 PR
Code Review
Pilot
自动部署
用户访谈 Agent
自动发帖
自动论文研究
复杂向量数据库
Agent Graph 框架重构
Web UI 重写
```

先把：

```text
Signal → Evidence → Idea → Decision
```

跑通。

---

# 37. 测试

新增：

```text
tests/project_research/
```

至少覆盖：

### Schema

- Signal serialization
- Problem serialization
- Idea serialization
- Evidence serialization
- Brief serialization

### Validation

- 没有 evidence → cannot GO
- competitor fully covers problem → hard reject
- duplicated evidence → independent count 不增加
- score threshold 正确

### Red Team

- disabled 时不调用模型
- 只对 Top K 调用

### Pipeline

mock LLM + mock collectors：

```text
Signal
→ Problem
→ Idea
→ Evidence
→ Validation
→ Brief
```

可完整运行。

---

# 38. Backward Compatibility

必须保证：

```bash
python idea_generation.py
```

原行为不被改变。

Project Research 不修改：

```text
ar-runtime
```

除非确实存在共享模块兼容问题。

不要删除原角色：

```text
ideator
planner
critic
code_reviewer
```

只新增 Project Research 角色。

---

# 39. Logging

日志应清楚显示：

```text
[Collect] 153 signals

[Screen] 31 opportunities

[Problem] 18 unique problems

[Ideate] 12 project ideas

[Evidence] 12/12 completed

[Validate]
GO candidate: 4
HOLD: 5
REJECT: 3

[Red Team] reviewing top 3

[Brief] 5 briefs generated
```

不要让用户需要阅读原始 JSON 才知道系统执行到哪里。

---

# 40. Error Handling

Collector 单路失败：

```text
warning + continue
```

除非用户显式配置该 Source 为 required。

LLM 调用失败：

```text
retry
→ fallback model
→ stage failure
```

不能因为：

```text
Red Team model failure
```

丢弃前面已采集的 Evidence。

---

# 41. 第一版优先级

## Phase 1

先完成：

```text
project_research.py
schemas
pipeline
Project Prompt
单模型 Ideation
Validation
Brief
```

使用现有 Collector。

目标：

> 新模式可以完整运行。

---

## Phase 2

实现：

```text
Red Team
Project Profile
Checkpoint
结构化评分
```

---

## Phase 3

强化 GitHub Evidence：

```text
GitHub Issue Search
GitHub Discussion
Repository metadata
Competitor Search
```

这会显著提升 Idea 质量。

---

## Phase 4

再考虑：

```text
StackOverflow
npm
PyPI
Product Hunt
其他开发者社区
Dashboard
```

---

# 42. Definition of Done

第一版达到以下条件即算完成：

1. 可以执行：

```bash
python project_research.py
```

2. 不需要配置 3 个不同模型。

3. 不调用原 Idea Forge 多模型 cross review。

4. 不调用：

```text
ar-runtime
code_reviewer
critic
pilot
experiment planner
```

5. 至少产生：

```text
signals
problems
ideas
validation
project brief
```

6. 每个 Idea 可以追溯到真实 Signal URL。

7. 没有真实 Evidence 的 Idea 不能被标为 GO。

8. Red Team 可以：

```text
enabled / disabled
```

9. 原：

```bash
python idea_generation.py
```

继续可运行。

10. 自动测试通过。

---

# 43. 最终产品定位

不要把 Project Research 做成：

> AI 帮我想几个创业点子。

真正目标是：

> **从开发者社区和真实开源生态信号中发现问题，通过证据、竞品和可行性分析，把模糊机会收敛为值得进入 MVP 阶段的 GitHub 项目。**

核心原则：

> **LLM discovers and challenges. Evidence validates. Human decides.**