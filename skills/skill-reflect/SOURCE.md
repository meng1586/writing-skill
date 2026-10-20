# SOURCE — skill-reflect 从哪来，为什么自己写

## 1. 先搜再做

### 本地技能目录（642 条，14 个来源）

2026-10-20 按 `reflect / retrospect / self-improve / usage log / feedback / lessons /
skill audit / eval` 检索，命中 5 条，逐条看后都不匹配：

| 候选 | 来源 | 为什么不用 |
|---|---|---|
| `crit` | BehiSecc | 评审 plan/code diff 并回传反馈，是「评别人的产出」，不是「记 skill 自己的毛病」 |
| `content-research-writer` | BehiSecc | 内容研究写作，领域不相关 |
| `buyer-eval` | BehiSecc | B2B 供应商评估，不相关 |
| `teach` | mxyhi | 教学工作区，带 learning records，但没有 skill 使用证据/阈值/改进报告 |
| `Evaluation checklist` | daymade | 只校验 frontmatter/资源，是一次性检查，不积累证据 |

### GitHub 侧（概念参考，未安装）

| 候选 | 做法 | 与本原型的差异 |
|---|---|---|
| [orchestkit / skill-evolution](https://github.com/yonatangross/orchestkit/blob/e172c03473ddb5fad0dea380da268f705233e0d4/src/skills/skill-evolution/SKILL.md) | 追踪「用户对输出的编辑模式」+ 成功率，置信度评分，版本快照/回滚，交互式 apply | 它从**编辑差异**推断模式，重、需要 hook 和版本目录；本原型记**使用卡点**，更轻、直接可行动，不做回滚（git 就是回滚） |
| [research-paper-lifecycle-skills / reflect-and-improve](https://github.com/ShaishavMaisuria/research-paper-lifecycle-skills/blob/main/skills/reflect-and-improve/references/reflection-loop.md) | 面向论文写作的反思循环 | 领域不相关，但「记录→反思→改」的思路一致 |
| [claude-skills-management](https://github.com/hardness1020/claude-skills-management) | 本地面板，跨项目统计和给 skill 打分 | 是**使用统计面板**，不产出「改哪一段 SKILL.md」的建议 |
| [dotagent / reflect-on-work](https://github.com/Clouder0/dotagent/blob/main/.claude/skills/reflect-on-work/SKILL.md) | 工作结束后的复盘 | 复盘对象是「这次工作」，不是「skill 本身」 |

结论：没有「按 skill 聚合 issue + 证据阈值 + 建议改动 + 受影响文件」的轻量本地实现。
本技能按主人 2026-10-20 的原型任务自研，不安装上述任何项目。

## 2. 设计来源（本项目内）

问题分类和「慢 / 重复 / 贵」三条真实证据，来自
`skills/novel-study/references/优化计划.md`（2026-10-20 主人指出，含实测数据：

- 每单元 4–5 分钟、全书约 10 小时 → **慢**
- 单篇笔记平均 207 行、0 节每篇重复、前情提要滚到 4095 行 → **重复**
- 每单元约 2 万 token、全书约 224 万 token → **贵**

本技能不复制 novel-study 的解决方案，只把「问题 → 证据 → 待改」这套流程产品化；
示例日志的 `suggestion` 字段引用了优化计划里的改法，便于报告直接可执行。

其余 3 条示例日志（story-review 输出太长、wjs-distilling-style 盲测说明不清、
scene-craft 建议太抽象）来自日常使用的典型卡点，作为「跨 skill 聚合」的样例。

## 3. 上游与许可

- 本技能为**本项目原创**，无上游仓库、无外部许可证约束。
- 设计上参考了上述公开项目的**思路**（append-only jsonl、证据阈值、改进建议），
  未复制其代码、规则文件或数据格式。
- 示例日志为人工编写的真实问题记录，不含正文、密钥或隐私。

## 4. 变更记录

- 2026-10-20：初版原型。`log.py` + `report.py` + 6 条示例日志 + SKILL/README；
  自测验证阈值升级、JSON、过滤、坏行容错、同义词合并。
