# IdeaProbe

用真实需求和证据，寻找值得开发的项目。本机 `codex exec` 负责结构化分析，Python 负责采集、引用校验和最终决策。

[English](README.md) · [完整使用说明](docs/PROJECT_RESEARCH_USAGE.md) · [真实运行评估](docs/PROJECT_RESEARCH_AGENT_CONTEXT_EVALUATION.md)

## 快速开始

使用 Python 3.12 创建虚拟环境，单独安装并登录 Codex CLI：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
codex login
.\.venv\Scripts\python.exe project_research.py --topic "Agent 上下文管理"
```

Linux 使用 `python3.12 -m venv .venv`，解释器路径改为 `.venv/bin/python`。

默认配置是 [config/project.example.json](config/project.example.json)，本地覆盖配置写入被 Git 忽略的 `config/project.local.json`。也可用 `--config` 或 `IDEAPROBE_CONFIG` 指定独立文件。旧的 `config/providers.local.json` 只读取其中的 `project_research` 区块，保留 `AUTORESEARCH_CONFIG` 环境变量兼容。

模型使用本机 Codex 的登录状态和默认模型，可配置角色模型名称。运行会消耗 Codex 使用额度；完整预算可能产生较多调用，建议先阅读真实运行评估。

## 研究流程

社区信号 → 主题筛选 → 问题提炼与去重 → 创意 → 证据验证 → 评分 → Red Team → GO / HOLD / REJECT 报告。

- 默认只采集 Hacker News，使用你提供的 `--topic` 和可选的 `queries` 定向搜索；未提供时会提示补充。
- Reddit 和 GitHub Trending 需手动开启；批量学术、资讯与博客采集器已移除。
- 数据源取舍及围绕已有想法的后续开发顺序见[数据源策略](docs/PROJECT_SOURCE_STRATEGY.md)。
- 用 [ProjectProfile.md](ProjectProfile.md) 描述自己的能力、约束和目标用户。
- 研究结果保存在 `data/project_research/`，包含 JSON、Markdown 和阶段检查点。
- 使用相同配置并追加 `--resume RUN_ID` 恢复；完成阶段会跳过。
- 用 `--no-red-team` 关闭复核，或用 `--top-k` 控制输出报告数量。

原文引用与来源去重保证可追溯性，仍需人工判断材料是否证明同一需求。缺少竞品验证、渠道访问失败或证据不足时，不应仅凭高分立项。

## 开发与测试

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest tests/ -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe scripts/secret_scan.py .
```

测试使用模拟采集结果和模型响应，不访问外网。CI 配置覆盖 Windows 与 Linux；真实 Codex 调用单独验证。

## 来源与许可

维护者：MaKik。部分采集器和工具函数源自 [AutoResearch](https://github.com/EvoMap/AutoResearch)。当前发行内容已移除原学术研究流水线、Forge、实验运行器和仪表盘。

保留 [LICENSE](LICENSE)、[来源说明](NOTICE) 和 [上游引用](docs/UPSTREAM_CITATION.cff)。独立化改动见 [清理记录](docs/PROJECT_CLEANUP.md)。
