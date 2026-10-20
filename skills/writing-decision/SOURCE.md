# SOURCE — writing-decision

## 结论

**自建，无上游。** 本技能是「写点小说」项目内的原型，不来自任何已安装技能或 GitHub 仓库。

## 写之前搜过什么

按工作区「先搜再做」规则：

1. **本地 find-skill 目录（4800+ 条）**
   - 查询词：`decision`、`writing`、`novel`、`story craft`、`outline`
   - 结果：有 `content-research-writer`、`avoid-ai-writing`、`writing-guidelines` 等通用写作技能；**没有**「按场景查写作手法 + 风险 + 案例」的决策库，也没有小说/网文向的 if-then 查询工具。
2. **GitHub / 技能市场**
   - [writing-decision-trees-as-skills](https://skills.rest/skill/writing-decision-trees-as-skills)：把决策树写成 SKILL.md 的**方法论**（编号谓词、显式分支），不提供网文技法内容，也没有查询 CLI。
   - [mave99a/novel-skill](https://github.com/mave99a/novel-skill)：整本小说生成流程，不是「写作时查判断」。
   - [vidanov/writing-craft-skill](https://github.com/vidanov/writing-craft-skill)：通用写作craft + AI 检测清单，不针对中文网文场景。
   - 其余为交互小说、日文小说、网文写作流程类，均不覆盖本需求。

**判断**：上述候选要么是流程/生成，要么是通用写作建议，缺「触发条件 → 手法 → 机理 → 案例 → 崩法」这种可查询结构。且本技能要和 `novel-study` 的规则库/笔记直接对接，自己定数据格式成本更低。

## 素材来源

只用了项目里**真读过**的材料，没有外部编造：

- `skills/novel-study/data/rules/开篇.md`（R-开篇-001、R-开篇-002）
- `skills/novel-study/data/rules/节奏.md`（R-节奏-001、R-节奏-002）
- `skills/novel-study/data/rules/章末钩子.md`（R-章末钩子-001）
- `skills/novel-study/data/notes/十日终焉-第11-20章.md`
- `skills/novel-study/data/notes/十日终焉-第41-50章.md`
- `skills/novel-study/data/notes/十日终焉-前情提要.md`
- 另参考 `skills/novel-study/references/note-template.md` 和 `rules-guide.md` 的拆解维度

案例统一指向《十日终焉》，章号来自上述笔记；转述和原文在 `case.quote_type` 里分开标注。唯一一条推演规则 D-014 标了 `derived`，没有伪装成已验证。

## 本项目改动

- 新增目录 `skills/writing-decision/`：`SKILL.md`、`SOURCE.md`、`data/decisions.json`、`scripts/decide.py`。
- 未修改 `skills/novel-study/` 下任何文件。
- 未做 git commit（按任务要求留给 Lead 统一提交）。
- 未创建 `.agents/skills/writing-decision` 软链；是否安装到项目级技能目录，由 Lead 决定。

## 后续可做

- `sync.py`：从 `data/rules/*.md` 增量生成候选决策，人工补 `trigger` 和 `risk` 后入库。
- 语义匹配：现在靠关键词 + 同义词；如果以后接本地 embedding，可保留 `decide.py` 的接口不变，只换 `build_concepts`。
- 写作回填：写完一章后，把「实际用了哪条、效果如何」记回 `decisions.json` 的 `notes`，让 `derived` 逐步转 `verified`。
