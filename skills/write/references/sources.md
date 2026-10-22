# 方法来源与接入取舍

本包采用一个入口和内部引用，外部资料仅作设计参考，不是运行依赖。未安装或链接任何外部大纲 skill；以下方法均重新写成适合本包的中文流程。

## 外部公开大纲方法

| 原始资料 | 吸收 | 不采用 |
|---|---|---|
| [story-skills / Outlining Ladder](https://github.com/danjdewhurst/story-skills/blob/main/skills/plot-structure/references/outlining-ladder.md) | 大纲逐层加深；因果可连接、足够落笔就停 | 每层都必须走完，或把完整细纲当开写前提 |
| [story-skills / Short Story Form](https://github.com/danjdewhurst/story-skills/blob/main/skills/plot-structure/references/short-story-form.md) | 短篇需要更集中的叙事范围，不能照搬长篇篇幅结构 | 固定人物/地点数量、英语字数标准，以及每个词都必须产生单一效果 |
| [story-skills / Premise Workshop](https://github.com/danjdewhurst/story-skills/blob/main/skills/premise-workshop/SKILL.md) | 保留原始念头的吸引力；将构思视为可发展的假设 | 固定问题数量、强制对标、额外项目注册与其他 skill 调用 |

资料价值按与本次问题是否相符判断，不按安装量宣称文学效果。

## 本地现有方法

只读参考 DS 工作区已有 `story-short-write/references/` 的 `workflow-design.md`、`story-logic.md`、`short-reversal.md`、`narrative-focus.md`，吸收欲望与限制、因果、信息公平、自然场景和必要的慢处。

只读参考已有 `story-long-write/references/` 的 `workflow-setup.md`、`workflow-volume.md`、`workflow-outline.md`、`outline-methods.md`、`artifact-protocols.md`，吸收全书方向、当前卷剧情单元、滚动近章、阶段兑现和卷间承接。

没有复制它们的工具链、会话机制、事务状态或审核配额。固定章数、固定高潮比例、付费点、支线数量、逐章反转与钩子要求不接入本包。来源工作区未作修改。

## 内部资源种子

`data/rules/` 的 8 个维度、`data/decisions.json` 的 24 条候选与 `data/modules/` 的 12 张卡，是通用方法摘要，来源为本项目早期公开候选与本鲸私有规则库的改写整理。规则 ID 与待试验状态保留；新增工作流不构成效果认证。

这里只带通用方法与工具；不携带小说正文、私人阅读笔记、原文摘录、读者身份或具体案例。私有库的原案例、出处与状态冲突保留在原处，不由摘要覆盖。

本包现为 DS 工作区主库 `skills/write/`，由本鲸维护；Codex 只读复核。公开版只导出通用方法/工具/摘要/虚构格式例，不含私人绝对路径、正文与私有笔记。

两个表达层补充（与编辑共识一致）：

- 表达优先级：作者当前具体要求 → 本书已定文风 → 适用偏好 → 通用技巧。表达偏好不覆盖已定事实、人物知情范围与已选剧情。
- 旧稿反推：已有长稿但缺规划时，从现稿反推必要的最小大纲与当前事实/未决后果即可，不强制先做完整拆书或资料迁移。

## 范围补正（2026-10-22）

方法为重新表述，不复制旧 skill 的工具链、会话机制、事务状态或审核配额。`scripts/` 下三个检测器（check-ai-patterns.js、check-degeneration.js、style-whitelist.js）是从 oh-story-claudecode@7408014 原样复制的 MIT 文件，许可见 `THIRD_PARTY_NOTICES.md`。旧外部入口（story-*、scene-craft、wjs-distilling-style、line-editor、prose-rhythm）已移至归档，不再作为活动入口。
