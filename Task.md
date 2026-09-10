# Codex Implementation Task — Project Research Mode

## Goal

在当前 AutoResearch Repository 中实现一个新的：

```text
Project Research Mode
```

它用于 GitHub / 开源项目开发之前的：

```text
机会发现
→ 用户问题提取
→ Project Idea
→ Evidence Validation
→ Competitor Validation
→ Optional Red Team
→ Project Research Brief
```

阅读：

```text
docs/PROJECT_RESEARCH_SPEC.md
```

并以该文档为产品和架构规范。

---

## Important

这是新增模式。

不要把原 AutoResearch Research Mode 改成 Project Research。

必须保持：

```bash
python idea_generation.py
```

原有行为兼容。

新增：

```bash
python project_research.py
```

---

## Do Not Implement

不要实现或调用：

```text
ar-runtime
automatic coding
code review
pilot experiment
experiment execution
critic
blind review
paper planning
```

Project Research 到：

```text
Project Research Brief
```

为止。

---

## Architecture

优先新增：

```text
project_research.py

src/project_research/
├── __init__.py
├── schemas.py
├── prompts.py
├── pipeline.py
├── ideation.py
├── evidence.py
├── validation.py
├── ranking.py
├── red_team.py
└── brief.py
```

不要把所有代码塞进：

```text
project_research.py
```

入口文件只负责：

```text
parse args
load config
run pipeline
print summary
```

---

## Reuse

在写新代码之前先阅读和理解：

```text
idea_generation.py
src/pipeline_v4.py
src/channels.py
src/collectors/
src/llm_client.py
src/providers.py
src/roles.py
src/idea_forge/forge.py
config/providers.example.json
```

优先复用：

```text
collector registry
normalization
deduplication
LLM role routing
retry
model fallback
concurrency
atomic JSON persistence
```

不要重复造 Provider / Retry 基础设施。

---

## LLM Design

Project Research 默认：

```text
single-model ideation
```

不要要求：

```text
3 models
cross review
majority voting
```

需要新增 Role：

```text
project_ideator
project_validator
project_brief_writer
```

以及 Optional：

```text
project_red_team
```

Project Role 使用 ordered fallback。

不要配置：

```text
_min_available: 3
_all_candidates_used: true
```

---

## Pipeline

实现：

```text
collect_signals()
      ↓
screen_opportunities()
      ↓
extract_problems()
      ↓
deduplicate_problems()
      ↓
generate_project_ideas()
      ↓
collect_evidence()
      ↓
validate_ideas()
      ↓
rank_ideas()
      ↓
red_team_top_k()
      ↓
generate_briefs()
```

每个阶段使用清晰的数据类型。

禁止在 function 之间大量传递无约束：

```python
dict[str, Any]
```

优先：

```text
dataclass
TypedDict
Pydantic
```

请根据当前项目现有依赖选择最轻方案。

不要为了 schema 引入大型新依赖。

---

## Evidence Requirement

系统必须遵守：

```text
No evidence → No GO
```

任何 Idea 如果：

```text
independent_evidence_count == 0
```

不能输出：

```text
GO
```

即使 LLM 给出很高评分。

---

## Evidence Types

至少支持：

```text
problem evidence
competitor evidence
source provenance
```

每条 evidence 必须保存：

```text
source
url
finding
evidence type
```

---

## Validation

实现维度：

```text
Problem Reality       /20
Evidence Strength     /20
Competitor Gap        /15
Differentiation       /15
Feasibility           /10
MVP Clarity           /10
Distribution          /5
Maintenance Risk      /5
```

总分：

```text
100
```

默认：

```text
>=75 GO candidate
60-74 HOLD
<60 REJECT
```

Hard Reject 优先于 Score。

---

## Hard Reject

至少实现：

```text
missing target user
zero external evidence
no differentiation
wrapper-only idea
competitor fully covers core problem
obviously outside project constraints
```

Hard Reject 不允许被 LLM 高分覆盖。

---

## Red Team

配置：

```json
{
  "red_team": {
    "enabled": true,
    "top_k": 3
  }
}
```

只对 Validation 排名前 Top K 调用。

如果：

```text
enabled=false
```

不得发生任何 `project_red_team` LLM 调用。

Red Team 结果：

```text
PASS
HOLD
REJECT
```

以及：

```text
fatal_flaws
major_risks
missing_evidence
```

---

## Project Brief

同时输出：

```text
JSON
Markdown
```

Markdown 放入：

```text
data/project_research/briefs/
```

至少包含：

```text
Project
Decision
Score
Target User
Problem
Problem Evidence
Current Solutions
Competitors
Proposed Solution
Differentiation
Why Now
MVP
Non-goals
Technical Feasibility
Distribution
Risks
Red Team
Final Decision
Next Validation Step
```

---

## Provenance

实现完整：

```text
Brief
↓
Idea
↓
Problem
↓
Evidence
↓
Signal URL
```

不要让 LLM 生成无法追溯来源的：

```text
“社区普遍认为……”
“很多开发者需要……”
```

如果没有来源，则标记：

```text
hypothesis
```

不能标记：

```text
fact
```

---

## Prompts

全部集中：

```text
src/project_research/prompts.py
```

禁止在：

```text
pipeline.py
validation.py
ideation.py
```

散落大量 Prompt 字符串。

Prompt 应明确区分：

```text
FACT
INFERENCE
HYPOTHESIS
```

Validator 不允许自行补充不存在的外部事实。

---

## Configuration

扩展：

```text
config/providers.example.json
```

以及正常的 local config 支持。

新增：

```json
{
  "project_research": {
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
    }
  }
}
```

不要硬编码这些数值到 Prompt。

---

## Source Strategy

第一版优先复用当前：

```text
GitHub Trending
Hacker News
Reddit
```

不要第一轮同时实现大量新 Collector。

但设计接口时，应允许未来增加：

```text
GitHub Issues
GitHub Discussions
Stack Overflow
PyPI
npm
Product Hunt
```

GitHub Issue / Discussion 是后续最高优先级。

---

## Knowledge Base

Project Research 可以读取：

```text
knowledge_base/project/
```

至少支持：

```text
project_profile.md
```

Project Profile 用于判断：

```text
Feasibility
MVP scope
project constraints
```

找不到该文件时：

```text
使用默认空 profile
warning
继续运行
```

不能直接失败。

---

## Persistence

输出：

```text
data/project_research/
```

保留中间结果。

至少：

```text
signals
problems
ideas
evidence
briefs
runs
```

使用 atomic write。

不要在中途失败时破坏已经完成的数据。

---

## Tests

新增：

```text
tests/project_research/
```

必须使用 Mock，避免测试真实调用 LLM / 网络。

至少测试：

### test_no_evidence_no_go

Idea 没 Evidence，即使 LLM Score 高，也不能 GO。

### test_duplicate_evidence

同一个 Thread 的多个评论不能增加 independent evidence count。

### test_hard_reject

触发 Hard Reject 后最终必须 REJECT。

### test_red_team_disabled

关闭 Red Team 后调用次数为 0。

### test_red_team_top_k

10 个 Idea，top_k=3，只调用三次。

### test_pipeline_smoke

Mock：

```text
collector
LLM
evidence provider
```

完整执行：

```text
Signal → Brief
```

### test_original_mode_unchanged

至少确保原：

```text
idea_generation.py
```

import / CLI 基础行为没有因为新模式损坏。

---

## Implementation Order

严格按这个顺序实施。

### Step 1

阅读 Repository。

输出内部 implementation plan。

不要修改代码。

### Step 2

实现：

```text
schemas
config
directory structure
```

### Step 3

实现：

```text
pipeline skeleton
```

全部 Stage 可使用 Mock。

### Step 4

接入现有：

```text
channels
collectors
llm_client
```

### Step 5

实现：

```text
screen
problem extraction
ideation
```

### Step 6

实现：

```text
evidence
validation
hard reject
```

### Step 7

实现：

```text
ranking
red team
brief
```

### Step 8

实现测试。

### Step 9

更新：

```text
README / docs
providers.example.json
```

### Step 10

运行：

```text
existing tests
new tests
lint
```

修复 Regression。

---

## Coding Requirements

遵循当前 Repository 风格。

要求：

```text
small functions
明确类型
可测试
无不必要 abstraction
无重复 provider logic
无硬编码 model vendor
无 silent failure
```

错误必须记录原因。

避免：

```text
except Exception:
    pass
```

---

## Scope Discipline

如果在实现过程中发现：

```text
Web UI
Dashboard
GitHub OAuth
Embedding DB
Agent framework
Background scheduler
```

不是完成核心 Pipeline 必须的，

暂不实现。

记录 TODO 即可。

---

## Completion Report

实现完成后输出：

### Changed Files

逐个说明主要变化。

### Architecture

说明实际 Pipeline。

### Configuration

给出最小可运行配置。

### Commands

给出：

```bash
python project_research.py
```

运行方式。

### Tests

列出实际执行的测试和结果。

### Known Limitations

尤其说明：

```text
第一版 Evidence 数据源能力
GitHub Issue / Discussion 是否已实现
```

不要宣称未实现能力已经完成。

---

## Acceptance Criteria

任务只有同时满足以下条件才算完成：

- `project_research.py` 可以独立执行；
- Project mode 不要求三个模型；
- Project mode 不调用原 cross-review；
- Project mode 不调用 `ar-runtime`；
- Project mode 不调用 Code Review；
- Project mode 有真实 Evidence 概念；
- zero evidence 不可能 GO；
- 有 Competitor Analysis；
- 有 Optional Red Team；
- 有 GO / HOLD / REJECT；
- 有 JSON + Markdown Brief；
- 有 provenance；
- 新测试通过；
- 原 Research mode 不因改造失效。

不要通过删除原有测试来解决失败。