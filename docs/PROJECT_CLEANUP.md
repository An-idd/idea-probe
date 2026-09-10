# IdeaProbe 独立项目清理记录

日期：2026-09-10。目标：保留项目机会研究及必要依赖，移除原学术研究、Forge 和实验运行代码。

## 结果

- 移除 175 个原有受 Git 跟踪的文件。
- 清理前后可发布代码（`.py`、`.ts`、`.sh`）从 177 个文件、38,869 行缩减到 44 个文件、4,373 行。统计包含测试，不包含数据、环境和备份。
- 默认运行依赖为 `httpx` 和 `beautifulsoup4`；开发依赖放在 `requirements-dev.txt`，学术/媒体可选依赖放在 `requirements-sources.txt`。
- 仓库本地 Git 身份设置为 `MaKik <y1203454599@gmail.com>`，使用 `git config --local`，未修改全局身份。

## 移除内容

- `ar-runtime/` 实验运行器及对应脚本、测试。
- `src/idea_forge/`、旧 `pipeline_v4.py`、`llm_client.py`、`providers.py` 和相关路由、评分、调度模块。
- 旧 `idea_generation.py`、`check_idea.py`、定时运行及 Forge 入口。
- 仪表盘生成器、模板、旧流程图与截图。
- 原模型网关配置示例、投影/预检/研究转知识脚本及仅服务旧模式的测试。
- 采集器中未被研究流程使用的独立文件保存、储备池和演示入口。

采集器保留为真正使用的依赖，包括默认社区来源及可选学术/媒体背景来源；它们没有被当作旧实验流程一起删除。

## 独立化改动

配置由 `src/project_research/config.py` 直接读取，默认模板为 `config/project.example.json`。本地 `config/project.local.json` 支持嵌套覆盖，显式文件使用自己的设置及类型默认值。兼容旧 `config/providers.local.json` 中的项目区块和 `AUTORESEARCH_CONFIG`，新增 `IDEAPROBE_CONFIG`。配置读取支持 UTF-8 BOM。

采集渠道注册表移除了仪表盘专用元数据与格式化功能，按需导入采集模块。HTML 解析使用标准解析器，默认社区研究不再依赖由学术 SDK 间接安装的 `lxml`。

README、架构、贡献说明和 CI 已围绕 IdeaProbe 更新。CI 配置在 Windows/Linux 的 Python 3.12 环境安装最小开发依赖，执行测试、Ruff、编译与密钥扫描；本次实际执行的是本地 Windows 验证，没有声称已运行远端 Linux CI。

密钥扫描保留，已删除随旧测试一起失效的白名单项，并将路径统一为 POSIX 格式，修复此前 Windows 白名单路径不匹配的问题。

保留原 LICENSE，通过 NOTICE 和 `docs/UPSTREAM_CITATION.cff` 保存上游来源与作者引用。根 CITATION 改为当前项目。早期实现计划和报告标注为历史记录。

## 保留与恢复

原 Git 历史、remote、`ProjectProfile.md`、`Task.md`、需求规格、知识参考材料和真实研究数据保留。

删除前的工作树和未提交差异保存在被 Git 忽略的：

` .local-backups/before-ideaprobe-cleanup-20260910-180342/ `

- `working-tree.zip`：清理前受跟踪及可发布的未跟踪文件快照。
- `uncommitted.patch`：清理前相对 HEAD 的差异。
- `files.json`：快照路径清单。
- `legacy-local-state/`：旧目录中的剩余本地状态和缓存，保留而非销毁。

临时干净验证环境位于 `.local-backups/verify-env/`；现有 `.venv` 未卸载旧依赖，新克隆按精简后的 requirements 安装即可。

## 验证

- 干净虚拟环境仅安装 `requirements-dev.txt`，全量 **83 项测试通过**。
- Ruff、Python 编译检查、密钥扫描和 `git diff --check` 通过。
- 使用安装了可选依赖的原 `.venv`，全部 11 个来源模块导入成功。
- 原真实运行 `20260910_050645_7a9fb527` 用干净环境及普通 CLI 成功恢复，跳过全部 10 阶段，无新增模型调用。
- 原运行审计通过：67 条观察、71 条证据引文、4 份评分、3 份 Red Team、3 份 Markdown Brief 保持规则与产物一致，累计模型调用仍为 34 次。

本次聚焦独立化清理。此前效果评估中发现的主题采集预算、问题排序和需求证据相关性问题仍见 [真实运行评估](PROJECT_RESEARCH_AGENT_CONTEXT_EVALUATION.md)。
