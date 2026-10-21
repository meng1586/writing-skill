# 公开候选文件清单

- 候选日期：2026-10-21。
- 固定代码及本地成果基线：`5096d298f49fd1e9d324c828a544b891cd7bec9f`。
- 实施依据：方案经 DeepSeek 校对后，由 Codex 在独立公开副本中整理。
- 内容：47条规则摘要（8维）、24条决策摘要、12张场景摘要；原编号、类型和别名保留。
- 所有随包候选的效果状态为“待试验”。同一写法被观察到，不代表已通过对照试写。
- 原文摘引、具体书名章号、完整阅读记录、原项目正文、文风档案和试用日志不包含在本包中。完整依据保留在本地版本。
- 清单共62个文件，包括本清单和 `SHA256SUMS`。`SHA256SUMS` 覆盖除自身以外的所有文件，便于核对固定版本。
- 本地候选已整理；许可证范围见 README，正式发布时再确认许可文件。

## 逐文件清单

| 相对路径 | 类型 | 来源与公开处理 |
|---|---|---|
| `.gitignore` | 公开说明或模板 | 本轮公开整理 |
| `README.md` | 公开说明或模板 | 本轮公开整理 |
| `examples/decision-example.md` | 独立虚构格式演示 | 本轮公开整理，效果未经验证 |
| `examples/rule-example.md` | 独立虚构格式演示 | 本轮公开整理，效果未经验证 |
| `skills/novel-study/CONTRACT.md` | 公开说明或模板 | 本轮公开整理 |
| `skills/novel-study/SKILL.md` | 公开说明或模板 | 本轮公开整理 |
| `skills/novel-study/config.json` | 公开运行适配 | 基线工具的兼容、路径或说明修正 |
| `skills/novel-study/data/notes/.gitkeep` | 空状态或目录标记 | 本轮生成，不含阅读进度 |
| `skills/novel-study/data/rules/README.md` | 公开说明或模板 | 本轮公开整理 |
| `skills/novel-study/data/rules/人物.md` | 规则公开摘要 | 同ID本地条目整理，原文不包含 |
| `skills/novel-study/data/rules/对话.md` | 规则公开摘要 | 同ID本地条目整理，原文不包含 |
| `skills/novel-study/data/rules/开篇.md` | 规则公开摘要 | 同ID本地条目整理，原文不包含 |
| `skills/novel-study/data/rules/情绪.md` | 规则公开摘要 | 同ID本地条目整理，原文不包含 |
| `skills/novel-study/data/rules/章末钩子.md` | 规则公开摘要 | 同ID本地条目整理，原文不包含 |
| `skills/novel-study/data/rules/结构.md` | 规则公开摘要 | 同ID本地条目整理，原文不包含 |
| `skills/novel-study/data/rules/节奏.md` | 规则公开摘要 | 同ID本地条目整理，原文不包含 |
| `skills/novel-study/data/rules/语言.md` | 规则公开摘要 | 同ID本地条目整理，原文不包含 |
| `skills/novel-study/data/shelf.json` | 空状态或目录标记 | 本轮生成，不含阅读进度 |
| `skills/novel-study/references/book-review-template.md` | 公开说明或模板 | 本轮公开整理 |
| `skills/novel-study/references/note-template.md` | 公开说明或模板 | 本轮公开整理 |
| `skills/novel-study/references/read-cycle.md` | 公开说明或模板 | 本轮公开整理 |
| `skills/novel-study/references/rules-guide.md` | 公开说明或模板 | 本轮公开整理 |
| `skills/novel-study/references/卷纲模板.md` | 公开说明或模板 | 本轮公开整理 |
| `skills/novel-study/references/改稿自检.md` | 公开说明或模板 | 本轮公开整理 |
| `skills/novel-study/references/选书标准.md` | 公开说明或模板 | 本轮公开整理 |
| `skills/novel-study/scripts/apply.py` | 公开运行适配 | 基线工具的兼容、路径或说明修正 |
| `skills/novel-study/scripts/fetch.py` | 公开运行适配 | 基线工具的兼容、路径或说明修正 |
| `skills/novel-study/scripts/install_study_job.sh` | 基线工具 | 基线原样保留 |
| `skills/novel-study/scripts/plan.py` | 公开运行适配 | 基线工具的兼容、路径或说明修正 |
| `skills/novel-study/scripts/review.py` | 公开运行适配 | 基线工具的兼容、路径或说明修正 |
| `skills/novel-study/scripts/shelf.py` | 公开运行适配 | 基线工具的兼容、路径或说明修正 |
| `skills/novel-study/scripts/study_daemon.sh` | 基线工具 | 基线原样保留 |
| `skills/scene-modules/SKILL.md` | 公开说明或模板 | 本轮公开整理 |
| `skills/scene-modules/data/modules/.gitkeep` | 空状态或目录标记 | 本轮生成，不含阅读进度 |
| `skills/scene-modules/data/modules/交易.md` | 场景公开摘要 | 同类型本地卡片整理，真实案例不包含 |
| `skills/scene-modules/data/modules/反转.md` | 场景公开摘要 | 同类型本地卡片整理，真实案例不包含 |
| `skills/scene-modules/data/modules/告别.md` | 场景公开摘要 | 同类型本地卡片整理，真实案例不包含 |
| `skills/scene-modules/data/modules/打脸.md` | 场景公开摘要 | 同类型本地卡片整理，真实案例不包含 |
| `skills/scene-modules/data/modules/托孤.md` | 场景公开摘要 | 同类型本地卡片整理，真实案例不包含 |
| `skills/scene-modules/data/modules/揭示.md` | 场景公开摘要 | 同类型本地卡片整理，真实案例不包含 |
| `skills/scene-modules/data/modules/爆发.md` | 场景公开摘要 | 同类型本地卡片整理，真实案例不包含 |
| `skills/scene-modules/data/modules/立威.md` | 场景公开摘要 | 同类型本地卡片整理，真实案例不包含 |
| `skills/scene-modules/data/modules/绝境.md` | 场景公开摘要 | 同类型本地卡片整理，真实案例不包含 |
| `skills/scene-modules/data/modules/翻盘.md` | 场景公开摘要 | 同类型本地卡片整理，真实案例不包含 |
| `skills/scene-modules/data/modules/谈判.md` | 场景公开摘要 | 同类型本地卡片整理，真实案例不包含 |
| `skills/scene-modules/data/modules/追逐.md` | 场景公开摘要 | 同类型本地卡片整理，真实案例不包含 |
| `skills/scene-modules/scripts/query.py` | 公开运行适配 | 基线工具的兼容、路径或说明修正 |
| `skills/skill-reflect/SKILL.md` | 公开说明或模板 | 本轮公开整理 |
| `skills/skill-reflect/scripts/log.py` | 基线工具 | 基线原样保留 |
| `skills/skill-reflect/scripts/report.py` | 基线工具 | 基线原样保留 |
| `skills/writing-decision/SKILL.md` | 公开说明或模板 | 本轮公开整理 |
| `skills/writing-decision/data/decisions.json` | 决策公开摘要 | 同ID本地决策整理，case与来源字段不包含 |
| `skills/writing-decision/scripts/decide.py` | 公开运行适配 | 基线工具的兼容、路径或说明修正 |
| `skills/writing-loop/SKILL.md` | 公开说明或模板 | 本轮公开整理 |
| `skills/writing-loop/data/index.jsonl` | 空状态或目录标记 | 本轮生成，不含阅读进度 |
| `skills/writing-loop/references/reader-prompts.md` | 公开说明或模板 | 本轮公开整理 |
| `skills/writing-loop/scripts/index.py` | 公开运行适配 | 基线工具的兼容、路径或说明修正 |
| `skills/writing-loop/scripts/style.py` | 公开运行适配 | 基线工具的兼容、路径或说明修正 |
| `skills/writing-loop/scripts/writeback.py` | 公开运行适配 | 基线工具的兼容、路径或说明修正 |
| `写作方法论-v2.md` | 公开说明或模板 | 本轮公开整理 |
| `MANIFEST.md` | 发布清单 | 本轮生成 |
| `SHA256SUMS` | 完整性校验 | 本轮生成；不包含自身哈希 |

## 状态与使用

书架和索引为空；笔记目录仅保留目录标记。查询摘要无需先导入原项目材料。后续运行产生的缓存、备忘、阅读记录和反馈属于使用者本地数据，不应直接混入新的公开候选。

规则 Markdown、决策 JSON、场景 Markdown 分别保留各自结构。查询脚本允许公开候选不带来源；字段、适用范围和反馈方式见各模块说明。公开副本独立整理，本地完整版无需删字段或迁移进度。
