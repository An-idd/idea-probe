> Historical record from the AutoResearch integration phase. Current standalone layout: [cleanup notes](PROJECT_CLEANUP.md).

# Project Research 实现计划

日期：2026-09-10
状态：首版实现完成；新增测试与相关回归通过，原项目完整 Linux 验证待在对应环境运行。

实际变更、验证结果和限制见 [实现报告](PROJECT_RESEARCH_IMPLEMENTATION_REPORT.md)，运行方式见 [使用说明](PROJECT_RESEARCH_USAGE.md)。

依据：[Task.md](../Task.md)、[PROJECT_RESEARCH_SPEC.md](PROJECT_RESEARCH_SPEC.md)。

用户已确认模型调用方式为本机 `codex exec`。本计划据此调整接入层；原规范中复用 HTTP LLM Provider 的要求由这一明确选择替代。产品范围、证据门槛和原 Research 兼容要求保持有效。

## 1. 目标与边界

新增独立的 Project Research Pipeline，从社区信号发现用户问题，经过证据、竞品与可行性验证，输出 Project Research Brief。

- 新入口：`python project_research.py`。
- 保持 `python idea_generation.py` 原有行为兼容。
- 默认通过本机 `codex exec` 使用单模型；各 Project Role 是业务阶段名称，允许共用一个模型。显式配置多个 CLI 模型时才使用 ordered fallback。
- 由代码执行证据门槛、评分汇总、Hard Reject 和最终决策，LLM 不得覆盖这些规则。
- 首版包含结构化评分、Optional Red Team、Project Profile、阶段持久化及恢复。
- 不调用原 Forge cross-review、ar-runtime、Code Review、Pilot、Critic、Blind Review、实验执行或论文规划。
- 不增加 Web UI、Dashboard、向量数据库、Agent 框架或后台调度器。

规范中的 Phase 1/2 作为内部里程碑；完整交付须满足 Task 的全部验收要求。

## 2. 已确认的仓库现状

已阅读主入口、`pipeline_v4.py`、`channels.py`、GitHub Trending/HN/Reddit 采集器、`llm_client.py`、`providers.py`、`roles.py`、Forge 主流程及辅助函数、示例配置、相关测试和 CI 约束。

| 现状 | 实现处理 |
|---|---|
| `llm_client.call_role_result()` 面向现有 HTTP Provider，没有本机 Codex CLI 适配 | 原模式继续使用；新模式通过独立 `codex_client.py` 调用 CLI，不把 CLI 模型名塞进 HTTP 路由 |
| 本机 `codex exec --help` 已确认支持 stdin、`--output-schema`、`-o` 和 `--ephemeral` | 使用这些 CLI 能力封装结构化调用；尚未验证真实模型调用 |
| `collect_all_channels()` 默认执行全部渠道，HN、Reddit 为 required | 复用渠道注册与调用机制，在新模式选择渠道并采用独立失败策略 |
| HN 查询固定偏 AI，返回结果缺正文 | 增加可选查询参数，补充正文和有限评论取证；保持旧默认行为 |
| Reddit 高层入口固定查询学术内容 | 复用底层搜索，允许配置 subreddit 和项目需求查询 |
| GitHub Trending 返回 `repo/description`，现有归一化读取 `title/summary` | 在新模式补字段映射，保留仓库 URL 和原始数据 |
| 归一化位于 `pipeline_v4.py`，原子写入与并发辅助函数位于 Forge | 小范围抽取无业务依赖的共享函数，保留旧调用接口，避免新模式导入 Forge |
| 根目录已有 `ProjectProfile.md` | 支持配置 Profile 路径，默认读取规范路径，并兼容已有文件 |
| 配置加载器对普通顶层配置块不做递归合并 | 在 Project 配置解析中补全嵌套默认值，不改写全局配置合并语义 |
| 知识库有公开 manifest，测试约束研究数据不能被提交 | 新增知识库文档时同步 manifest；测试产物使用临时目录，运行产物不提交 |

## 3. 模块与数据设计

主体使用规范要求的目录：

```text
project_research.py
src/project_research/
├── __init__.py
├── schemas.py
├── prompts.py
├── codex_client.py
├── pipeline.py
├── ideation.py
├── evidence.py
├── validation.py
├── ranking.py
├── red_team.py
└── brief.py
tests/project_research/
```

入口只负责解析参数、加载配置、运行 Pipeline 和打印摘要。共享辅助函数仅在确有复用需要时抽取，不建立通用工作流框架。

使用标准库 `dataclass`、`Enum` / `Literal` 定义：

- `Signal`、`Problem`、`ProjectIdea`。
- `Evidence`、`EvidencePack`、竞品记录。
- `ValidationResult`、`RedTeamResult`、`ProjectBrief`、`RunState`。
- Project 配置及各阶段需要的明确输入输出类型。

不增加 Schema 依赖。LLM 返回值在边界校验类型、必填字段、分数范围及引用 ID；开放字段限定在 `raw_metadata` 等原始数据边界。

所有实体保留稳定 ID 和引用关系：

```text
Brief → Idea → Problem → Evidence → Signal URL
```

去重时合并来源，不丢失原始讨论与证据。事实、推断、假设分别标记为 `FACT`、`INFERENCE`、`HYPOTHESIS`。

### Codex 调用边界

```text
Python Pipeline
├── 采集、内容取证、去重与 Checkpoint
├── codex_client.py → 本机 codex exec → 结构化 JSON
│   └── Screen / Extract / Ideate / Validate / Red Team / Brief
└── 引用校验、证据计数、评分汇总与最终决策
```

- 使用标准库 `subprocess`，以参数列表调用且 `shell=False`；Prompt 通过 stdin 输入，兼容 Windows 路径、中文和长文本。
- 使用 `--output-schema` 约束最终响应，`-o` 写入每次调用独有的临时结果文件，再由 Python 进行业务校验和原子持久化。不能把 `--json` 的事件流当成最终业务 JSON。
- 优先使用已有 Codex 登录和模型配置；可在 Project 配置显式覆盖 CLI 路径、模型、超时、并发和角色参数。项目不读取、复制或保存登录凭据，不要求配置 HTTP Provider 密钥。
- 每次阶段任务使用独立会话，传入所需材料；Red Team 不继承 Ideator 的会话。使用 `--ephemeral`，不通过 `resume --last` 恢复业务流程；恢复由 Python Checkpoint 控制。
- 在专用工作目录中运行，使用只读沙箱；显式控制可用工具及项目指令上下文，避免研究内容触发业务代码修改。只读沙箱不等于禁止所有工具或网络调用，实施时需核对实际配置。
- 首版外部取证由 Python 管理。Codex 输出的未经取证支持的事实不得进入 Evidence Pack；社区内容作为不可信数据提供给模型。
- 处理可执行文件缺失、超时、非零退出、空结果、无效 JSON 和引用错误；保留退出码及经过脱敏的诊断。超时或取消后清理子进程，避免遗留运行任务。
- 复用已有通用 `retry_call` 做有上限的调用重试，区分永久配置错误与暂时失败，不套用 HTTP 状态码策略，不叠加无界外层重试。只有显式设置备用模型才尝试 fallback。
- 默认 Codex 并发为 1，可按实际限额调整；不会因为独立业务角色就默认启动多个并发模型。记录请求模型及 CLI 可获得的实际模型信息，无法获得时明确标为未知。

官方依据：[Codex 非交互模式](https://learn.chatgpt.com/docs/non-interactive-mode)。已核对官方文档和本机 CLI 帮助；本机登录与最小结构化调用已验证通过。完整社区研究未作为本次验证执行。

## 4. 实施步骤

严格按照 Task 的顺序实施。

### Step 1：仓库阅读与设计

- [x] 阅读任务、产品规范及相关代码。
- [x] 明确复用点、现有能力缺口与兼容边界。
- [x] 输出实现计划。

Step 1 当时仅完成阅读与规划；后续实现和单独的真实 Codex 冒烟验证已执行。

### Step 2：Schema、配置和目录

- [x] 建立上述类型和目录结构。
- [x] 扩展 `config/providers.example.json`，增加 `project_research` 配置。
- [x] 在 `project_research` 配置块内声明 `project_ideator`、`project_validator`、`project_brief_writer` 和可选 `project_red_team` 的业务参数，不加入旧 HTTP `roles` 表。
- [x] 增加 `project_research.codex` 配置，复用已有配置文件加载方式；CLI 模型使用 Codex 可识别名称，不使用旧 HTTP Provider 别名。
- [x] 支持正常 local config 和现有显式配置加载方式。
- [x] 校验数量、阈值、来源配置，并补全局部配置缺失的嵌套默认值。
- [x] 支持 Profile 路径；缺失时 warning、使用空 Profile 并继续。

默认参数遵循规范：lookback 30 天、最多 200 signals / 30 problems / 20 ideas、输出 Top 5、最低独立证据数 2、Red Team 默认开启且 Top 3、GO/HOLD 阈值 75/60。

### Step 3：可 Mock 的 Pipeline 骨架

- [x] 串联所有阶段，并使用明确数据类型传递结果。
- [x] 通过普通函数参数注入采集、模型调用和取证能力，允许完全离线替换。
- [x] 设计阶段状态、计数、错误与运行摘要。

```text
collect_signals()
→ screen_opportunities()
→ extract_problems()
→ deduplicate_problems()
→ generate_project_ideas()
→ collect_evidence()
→ validate_ideas()
→ rank_ideas()
→ red_team_top_k()
→ generate_briefs()
```

Idea 语义去重在构思阶段完成。

### Step 4：接入共享基础设施

- [x] 复用 `channels` 注册机制，默认启用 GitHub Trending、HN、Reddit。
- [x] Academic 和 Media 默认关闭。
- [x] 为现有采集器增加必要的可选查询参数，保持旧调用默认值兼容。
- [x] 补齐 GitHub 字段映射及可获得的作者、发布时间信息，不把采集时间当成发布时间。
- [x] 保留社区讨论 URL 与外链，避免把指向同一产品的不同帖子误当成同一个讨论。
- [x] 复用归一化、URL/标题去重和采集 HTTP retry；抽取并发辅助函数时允许显式传入新模式的并发上限。
- [x] 实现 `codex_client.py`：stdin 输入、Schema 输出、会话隔离、超时、错误处理及显式配置的 ordered fallback。
- [x] 新模式单路采集失败时记录原因并继续；显式 required 的来源失败时中断。
- [x] 明确区分采集失败与成功返回零条；检查现有采集器内部吞错路径。

不直接调用旧 `run_pipeline_v4()`，避免继承学术筛选、历史研究黑名单和后续 Forge 逻辑。

### Step 5：机会筛选、问题提取与构思

- [x] 全部 Prompt 集中在 `prompts.py`。
- [x] 使用 `project_ideator` 完成机会筛选、问题提取、语义去重和项目构思。
- [x] Topic 贯穿筛选、提取与生成，使用语义相关性，不要求标题包含完全相同关键词。
- [x] 筛选偏向高召回，保留明确痛点、替代方案需求与 workaround。
- [x] Problem 与 Solution 分离，提取阶段不得把潜在方案当作需求事实。
- [x] 每个问题最多生成 1～3 个 Idea，并执行全局数量上限。
- [x] 合并语义重复 Problem 和 Idea，同时保留全部来源引用。
- [x] 将 Profile 提供给 Ideator 和可行性验证阶段。

### Step 6：Evidence、竞品验证与 Hard Reject

- [x] 从实际取得的帖子、正文、有限评论和关联项目页面建立 Evidence Pack。
- [x] 每条 Evidence 保存 source、URL、finding、type、来源摘录或内容引用及关联 ID。
- [x] 校验引用必须对应已取得的内容；模型自行提供的 URL 本身不算证据。
- [x] 对已发现的主要竞品取证和对比，记录覆盖范围、优势、弱点、重叠与缺口。
- [x] 按 Thread、作者、仓库及转载关系保守判断独立性，并保留计数依据。
- [x] 同一 Thread 多条评论只算一组；竞品存在、Star 和热度不增加独立需求证据数。
- [x] 由代码校验八维分数并求和：20/20/15/15/10/10/5/5，总分 100。
- [x] 代码执行所有 Hard Reject，模型高分不能覆盖。

决策规则：

| 条件 | 处理 |
|---|---|
| 没有明确目标用户、零外部需求证据、无差异化、纯 Wrapper、竞品完整覆盖且无缺口、明显超出约束 | Hard Reject，最终 `REJECT` |
| 核心依赖不可用、已核实许可证不允许，或差异化仅来自更强模型 | 按规范触发 Hard Reject，记录依据 |
| 有证据但低于 `min_independent_evidence` | 不得 `GO`；达到分数门槛也至多 `HOLD` |
| 无硬拒绝且证据门槛满足 | 按配置评分阈值得到 GO candidate / HOLD / REJECT |
| 关键竞品情况尚未核实 | 首版采用保守策略，至多 `HOLD`，列出下一步验证内容 |

“没有检索到竞品”不能解释成“没有竞品”。依赖、许可证、竞品功能等判断缺少来源时标为待验证，不能伪造事实。

### Step 7：排序、Red Team、Brief 与恢复

- [x] 按 Validation Score 稳定排序，不引入复杂加权排名公式。
- [x] Red Team 仅调用 Validation 排名前 K 个候选；disabled 时调用数为零。
- [x] 输出 PASS/HOLD/REJECT、fatal_flaws、major_risks、missing_evidence、counter_arguments。
- [x] 最终决策只允许被 Red Team 降级，PASS 不撤销 Hard Reject。
- [x] Red Team 失败记录为失败，不视为 PASS，并保留此前所有阶段结果。
- [x] Brief Writer 负责表述；分数、决策和有效引用由程序填入与校验。
- [x] 同时输出 JSON 和 Markdown，包含规范要求的全部 Brief 字段。
- [x] 各阶段完成后原子落盘，保留中间结果和运行摘要。
- [x] 实现恢复：记录阶段、配置指纹和产物引用，拒绝混用不兼容的运行配置。
- [x] 恢复时跳过已完成阶段；Red Team 失败后不重新执行前序全部 LLM。

输出放入 `data/project_research/`，至少保留 `signals/`、`problems/`、`ideas/`、`evidence/`、`briefs/`、`runs/`。Validation 等结果需有明确可恢复的产物记录。

### Step 8：离线测试

- [x] Schema 序列化及无效输入校验。
- [x] `test_no_evidence_no_go`：零证据、高模型分仍不能 GO。
- [x] `test_duplicate_evidence`：同 Thread 多评论不增加独立证据数。
- [x] `test_hard_reject`：触发任意硬拒绝，最终必须 REJECT。
- [x] `test_red_team_disabled`：关闭后调用次数为零。
- [x] `test_red_team_top_k`：10 个 Idea、Top K 为 3，仅调用三次。
- [x] `test_pipeline_smoke`：Mock collector、LLM、evidence provider，完整执行 Signal → Brief。
- [x] `test_original_mode_unchanged`：原入口 import 与 Mock main 路径兼容。
- [x] 分数阈值、证据不足、竞品未知、虚构引用和无效分数边界。
- [x] 语义去重后来源保留、Profile 缺失、嵌套配置局部覆盖。
- [x] 采集降级、原子写入失败、阶段恢复及配置不匹配。
- [x] 新模式不调用旧 Forge、实验与评审链路。
- [x] Mock subprocess 验证 stdin、参数列表、Unicode/带空格路径、独立结果文件及 Schema 参数；离线测试不要求安装或登录 Codex。
- [x] 覆盖 Codex 缺失、超时清理、非零退出、空输出、无效 JSON、重试上限和显式备用模型。
- [x] 验证新模式不要求 HTTP Provider 凭据，Red Team 关闭时不启动相应 Codex 进程。

全部测试使用 Mock 和临时目录，不访问真实网络或付费模型。原 `idea_generation.py` 没有 argparse，不能把 `--help` 当作安全的 CLI 冒烟方式；使用 Mock 验证入口。

### Step 9：文档与配置示例

- [x] 更新中英文 README 与必要架构说明。
- [x] 在 `providers.example.json` 的 `project_research` 块中提供本机 Codex 最小配置，说明无需配置旧 HTTP Role/Endpoint 即可运行新模式。
- [x] 说明 Profile 路径、空 Profile 行为、来源配置和证据限制。
- [x] 首版支持 `--topic`、`--top-k`、`--no-red-team`、`--resume`、`--sources`、`--lookback-days`。
- [x] 新增知识库文件时同步 `public_manifest.json` 及相关文档约束。
- [x] 新模式检查 CLI 可执行文件、参数和自身配置，不运行旧流程要求三模型及各 HTTP Endpoint 的全量 preflight；保留旧 preflight 行为。
- [x] 文档明确 GitHub Issue / Discussion 全面搜索尚未实现。

### Step 10：验收与回归

- [x] 运行新增 Project Research 测试。
- [x] 运行现有 Python 测试，修复由改动引入的回归，不删除原测试。
- [x] 运行 Ruff 与 Python 编译检查。
- [x] 运行仓库要求的模型引用、配置投影、公开知识库、发布树和秘密扫描检查。
- [ ] Linux/Bash 相关测试在对应环境验证：当前 Windows 无 WSL；已记录 Windows 基线和回归对照，Linux 验证待执行。
- [x] 输出实际变更文件、架构、最小配置、运行命令、测试结果和已知限制。
- [x] 实现完成后单独进行最小真实 Codex 结构化调用验证，并与离线测试结果分别记录；不以 CLI 帮助可用代替真实调用通过。

计划使用的检查命令以现有 CONTRIBUTING/CI 为依据，包括：

```bash
python -m pytest tests/project_research/ -q
python -m pytest tests/ ar-runtime/scripts/tests/ -q
ruff check .
python -m compileall -q project_research.py src scripts ar-runtime/scripts
python scripts/check_model_references.py
python scripts/render_env.py --check
python scripts/check_public_knowledge.py .
python scripts/check_release_tree.py .
python scripts/secret_scan.py .
```

上述检查已执行，实际结果见实现报告。秘密扫描仍存在既有 Windows 路径白名单问题；完整测试不能宣称全部通过。

## 5. 交付里程碑

1. **离线闭环**：单模型配置、Mock 数据完整执行 Signal → Brief；零证据的高分 Idea 仍被拒绝。
2. **真实取证闭环**：接入现有采集器及必要内容取证，每个判断可以追溯来源，竞品未知不会自动 GO。
3. **完整首版**：Optional Red Team、Profile、原子持久化、恢复、JSON + Markdown Brief 全部可用。
4. **兼容验收**：新增与现有测试、lint 和仓库检查完成，文档与实际能力一致。

## 6. 首版限制与后续优先级

- 首版证据覆盖受现有来源及有限内容取证能力限制，不承诺穷尽竞品或用户需求。
- GitHub Trending 只能提供其支持的时间窗口，不能保证任意 lookback 天数的完整历史覆盖。
- GitHub Issue Search、Discussion、系统化 Repository Metadata 和全面 Competitor Search 为后续最高优先级。
- Stack Overflow、npm、PyPI、Product Hunt 等扩展来源后续再做。
- Web UI、Dashboard、向量数据库及通用 Agent 框架不属于首版范围。
- 首版只实现本机 Codex CLI 接入；新模式的 HTTP 模型适配、Codex SDK 或 app-server 集成在出现实际需求后再考虑。
- 同一模型执行 Red Team 是独立任务上下文的反方检查，不宣称它构成独立模型共识。

核心验收原则：**LLM discovers and challenges. Evidence validates. Human decides.**

## 7. 实施补充

- 已建立 Python 3.12 `.venv`，安装原有 requirements；不新增依赖。
- 新增 `config.py`、`codex_client.py` 和 `signals.py`，分别承载配置、CLI 调用和采集适配。
- 每个 Idea 的取证文档数默认上限为 30，避免全量评论在每个 Idea 上重复产生过多模型调用。
- Profile 复用已有根文件；没有新增知识库文件，因此无需改变 manifest。
- 原子写入与并发辅助函数已抽取；新增测试覆盖 Windows 并发恢复锁和来源检索边界。
