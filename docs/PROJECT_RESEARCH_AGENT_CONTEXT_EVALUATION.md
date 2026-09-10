# Agent 上下文管理：真实运行效果评估

日期：2026-09-10。主题：`AI agent context management`。

**结论：经过真实运行诊断、修复和恢复后，流程已完成；产出 4 个创意、3 份 Brief，最终 0 GO、1 HOLD、3 REJECT。可以辅助探索和排除薄弱方案，当前不能单凭分数自动立项。**

本次使用仓库 `.venv` 和本机 `codex exec` 的现有默认模型。所有采集与模型调用均为真实执行，未用合成数据代替研究结果。没有联系社区用户，也没有运行候选项目的产品实验。

## 运行配置与复现

- Run ID：`20260910_050645_7a9fb527`。
- 配置：[config.json](../data/project_research/agent-context/config.json)。
- 输出目录：`data/project_research/agent-context/`，由 Git 忽略。
- 近 90 天；40 条信号预算；最多 6 个问题、6 个创意；输出前 3 份 Brief；Red Team 开启，对前 3 名进行复核。
- 使用现有 `ProjectProfile.md`，目标是个人或小团队能验证的开发者工具。
- 查询包含 agent context、context compaction、agent memory、context engineering、agent checkpoint。

```powershell
.\.venv\Scripts\python.exe project_research.py --config data/project_research/agent-context/config.json --output-dir data/project_research/agent-context
```

追加 `--resume 20260910_050645_7a9fb527` 可以恢复本轮，已完成阶段不会重新执行模型调用。运行过程中发现并修复了页面解压问题；已启动的 Python 进程继续使用此前加载的代码，因此原始评分与修复后的页面复查分别保存，不混写证据。

## 采集与候选覆盖

Hacker News 搜索返回 98 条讨论，GitHub Trending 返回 23 个项目。Reddit 搜索返回 403，本轮没有 Reddit 证据。

限额后实际保留 HN 20 条、GitHub 20 条，共 104 份正文或评论文档。评论补充没有报告读取失败。主题筛选保留 19 条：HN 18 条、GitHub 1 条。提炼出 23 个问题，合并并按限额保留 6 个，最终生成 4 个创意。

这说明流程可以从社区讨论产生带出处的候选，但本轮覆盖明显偏向 HN，不能据此判断整个市场的需求规模。

## 实测发现与修复

### 已修复：压缩竞品页面被重复解压

`fetch_competitor()` 使用 `httpx` 的 `iter_bytes()` 获取的已解压内容，却在重建响应时保留 `Content-Encoding`，导致有效的 200 页面再次被解压并失败。修复是在重建响应时移除原来的内容编码和长度头，仍保留对解压后内容的 1 MB 限制。

新增普通 gzip 页面与解压后超限页面的回归测试。加上后述证据 ID Schema 回归，Project Research 全部 57 项测试通过，涉及文件的 Ruff 检查通过。

修复后的真实复查保存在 [competitor-rechecks.json](../data/project_research/agent-context/competitor-rechecks.json)：

- Meetless：成功读取 6,000 字符；该值达到配置的正文截断上限。
- APIMatic Context Marketplace：成功读取 3,597 字符。
- 原始 Nous GitHub 链接：实际返回 404，未将其解释为项目不存在或需求不存在。

Meetless 页面明确介绍了决策捕获、人工审批、冲突协调和向会话提供当前有效决策。这些公开描述与“上下文版本账本”候选明显重叠；这是功能描述层面的比较，未安装产品或独立验证其效果。[Meetless](https://meetless.ai/)

APIMatic 已提供面向具体 API 的上下文插件；这不能直接证明它覆盖候选提出的可执行行为契约测试，也不能从页面未提及测试推断它没有这一功能。[APIMatic Context Marketplace](https://context.apimatic.io/)

### 尚待改进：定向采集预算

20 个 GitHub Trending 名额仅留下 1 个相关候选，另外 19 个在筛选后丢弃。热门项目与主题查询没有关联，挤占了相关讨论的采集预算。HN 多个查询的结果也按查询顺序拼接后截断，后面的压缩、记忆与 checkpoint 查询不保证得到均衡覆盖。

优先改进：先按主题相关性分配信号预算，或让定向研究配置减少 Trending、增加相关讨论；随后在多个查询之间轮转取样。

### 已修复输出约束：原文 ID 与证据 ID 混用

评分阶段两次因 `Claim cites unknown evidence` 停止。保留的原始响应显示，模型在 `Claim.evidence_ids` 中使用了材料里的 `doc_...` 文档 ID，而该字段只接受 `ev_...` 证据 ID。系统正确拒绝结果，但原 Schema 仅要求字符串，未表达这两个命名空间的区别。

修复是在 Claim 的 JSON Schema 中增加说明与 `^ev_[0-9a-f]{20}$` 格式约束。这使本机 Codex 的结构化输出也约束证据 ID 格式；Python 仍验证 ID 是否属于当前 Evidence Pack，没有自动映射、补造或放宽引用。新增回归覆盖了两类 ID 的区别。

第二次恢复使用同一 Run ID 和已保存的前六阶段产物。没有变更 Prompt 文本、研究配置或历史证据；输出 Schema 的约束增强由本节记录。

随后第三个评分触发 `Competitor URL is not supported by competitor evidence`：Screenpipe 的证据是 HN 帖子，模型却填入产品官网。为 Competitor.url 的 Schema 增加了准确复制竞品证据 URL 的说明，明确社区帖子 URL 不能替换为产品主页。

为了避免再次调用已通过校验的前两个评分，本轮诊断恢复脚本 [resume_recorded.py](../data/project_research/agent-context/resume_recorded.py) 复用保存的原始 `024/025-ValidationDraft.json`，由正常 `decide()` 再校验。没有修改分数、引用或结果。这是本轮专用的恢复手段；普通 CLI 仍只有阶段级恢复，并未新增通用的逐调用缓存。

### 尚待改进：问题限额之前没有机会排序

问题去重后直接取前 `max_problems` 个。模型收到的是分组指令，没有被要求对所有问题按机会价值排序。本轮后半部分的共享私有边界、跨会话恢复和重复读取历史等问题未全部进入创意阶段，而桌面活动上下文相关问题占比较高。

因此，本轮前 3 名只是已进入候选集合的排名，不是全部 23 个问题的最优方向。应先明确问题优先级，再施加预算限额。

### 尚待改进：渠道失败没有进入 Brief

Reddit 的 403 被保存在运行日志中，但渠道级失败没有从采集阶段传递到每个 Evidence Pack。Brief 中的 Collection Gaps 目前主要包含正文、竞品抓取和检索截断信息，不能代表完整渠道健康状况。

### 证据解释仍需人工复核

发布者自己的痛点可以构成单一来源的报告，但不能当作独立客户验证。原文引用、证据 ID 和独立分组校验能保证追溯性，不能自动证明市场规模、付费意愿或竞品差异。作者自报的性能数字也不等于独立测量结果。

本轮发现一个具体、优先级更高的语义计数问题：模型已在 `finding` 中说明某条材料不能直接证明候选需求，却仍标记为 `problem`，Python 随后将它计入独立需求来源。

| 候选 | 自动独立来源数 | 人工保守复核 | 被扩大的证据范围 |
|---|---:|---:|---|
| 并行会话上下文版本账本 | 3 | 2 | 聊天 Agent 反复拉取历史，不直接证明并行编码监督需求 |
| API 集成上下文契约测试 | 2 | 1 | MCP 参数/返回契约缺失，不等于 API 重试、限流、鉴权行为测试需求 |
| 客户上下文快照库 | 2 | 1 | 个人桌面助手记忆需求，不等于 GTM 客户快照需求 |
| 按任务授权的活动上下文出口 | 3 | 1 | 生产事故审批疲劳与凭据保管，不直接证明桌面活动任务授权需求 |

人工数字按“同类用户、同一核心痛点”的保守口径得出，不是新的自动评分结果，也不证明有人愿意采用具体方案。所有来源均来自 HN；不同帖子不代表不同渠道。

应将直接需求证据与相邻背景材料分开，只有前者进入硬门槛计数。现有去重解决的是来源关联问题，尚未充分解决证据是否针对同一需求的问题。本轮原始 Evidence Pack 与评分未被人工数字覆盖。

## 效果判断与下一步

本轮适合验证“能否得到有出处、可被反驳的候选”，不足以验证“能否自动选出值得立项的项目”。需求规模、付费意愿、采用成本和候选方案效果均没有被本次运行证实。

有效的部分是原文引用校验、来源去重、保守决策和 Red Team。版本账本的 Red Team 自主指出：三组材料不能等同于三次验证跨会话决策过期的需求，并要求把登记、确认、冲突处理成本计入总人工时间。这与人工复核一致。

下一步优先修正直接需求证据的计数口径，以及限额之前的主题采集与问题排序。随后可缩小到“并行编码会话中的决策过期与人工巡查”，寻找多个独立用户的具体返工事件，比较共享文档/变更摘要与现有方案。当前材料不足以支持直接开发通用 Agent 记忆平台，也不足以支持把版本账本当作已验证的机会。

## 自动结果与结构校验

最终状态：`completed`。结果如下，分数保持原始自动评分；Red Team 不能升级原本的 REJECT。

| 候选 | 得分 / 100 | 最终决策 | 主要限制 |
|---|---:|---|---|
| [并行会话上下文版本账本](../data/project_research/agent-context/briefs/20260910_050645_7a9fb527_idea_3ef3bc6db574e851e44a.md) | 61 | HOLD | 痛点有依据，但版本账本差异化、净节省时间及竞品缺口未验证 |
| [API 集成上下文契约测试](../data/project_research/agent-context/briefs/20260910_050645_7a9fb527_idea_69fd460fd9d2cdc2936e.md) | 55 | REJECT | 直接需求主要来自单个构建者；相邻接口契约问题被计入背景支持 |
| [按任务授权的活动上下文出口](../data/project_research/agent-context/briefs/20260910_050645_7a9fb527_idea_1998d204aadd13f32d92.md) | 52 | REJECT | 隐私顾虑不等于采用任务授权出口的需求，竞品差异未验证 |
| 客户上下文快照库 | 50 | REJECT | 单个 GTM 团队自述，个人助手记忆材料不能补足同类需求验证 |

第四名保留在 [完整排名 JSON](../data/project_research/agent-context/ranking/20260910_050645_7a9fb527.json)，按 `top_k=3` 未生成 Brief，也未进入 Red Team。

审计结果保存在 [audit.json](../data/project_research/agent-context/audit.json)，复查脚本为 [audit_run.py](../data/project_research/agent-context/audit_run.py)：

- 10 个已完成阶段的 SHA256 与运行清单一致。
- 67 条问题观察、71 条 Evidence 引文均能匹配保留原文；后者是跨 Evidence Pack 的总条数，不是 71 个独立来源。
- 4 份评分按原有规则重新计算后相等；证据独立分组可复算。
- 3 份 Red Team 的引用有效，最终决策遵循只降级规则。
- 3 份 Markdown 与其 JSON Brief 重新渲染结果完全一致。
- 完成后用普通 CLI 的 `--resume` 再次运行成功，跳过全部 10 个阶段；模型调用仍为 34 次，没有新增调用。

这些是结构、追溯和规则一致性检查，不是对模型推理正确率或市场有效性的量化评测。

## 实际耗时与用量

- 从首轮开始到最终 Brief 完成：约 **38 分 26 秒**，包含采集、失败诊断、修复和恢复等待。
- 累计 **34 次真实 Codex 调用**，包括因后续语义校验失败而未采纳的响应。
- 输入 **857,639 tokens**，输出 **56,927 tokens**；CLI 另报告缓存输入 7,552、推理输出 6,323，这些字段不额外叠加成总 token 数。
- 累计模型调用耗时约 **33 分 31 秒**。
- 模型沿用本机配置；当前 CLI 事件未暴露实际模型身份，因此运行清单记为 `unknown`。未据此估算美元费用。

这轮成本偏高。原因包括多阶段携带重复原文、每个候选的多批证据分析、串行调用，以及失败后的阶段恢复。应在证据正确性基础上缩小相关材料和重复上下文，再评估日常运行预算。

## 失败记录与恢复边界

首次运行在 validation 阶段收到 `Claim cites unknown evidence`，系统拒绝该评分，未生成错误的成功结果；signals、screen、extract_problem、problems、ideas、evidence 六个阶段保留。原状态备份在 `first-attempt-state.json`。随后使用相同配置和 Run ID 恢复，并为模型返回对象增加本轮专用的本地记录，以便审计错误引用；该记录包装器不改变模型输入、输出或决策规则。
