---
name: writing-decision
version: 0.1.0-public
description: "按题材、场景和章节位置查询写作决策摘要，返回可尝试动作、解释与风险。触发：/writing-decision、写作决策、这一场戏怎么写、写这章用什么手法。"
metadata: {"project":"写作学习","builds_on":["novel-study"]}
---

# writing-decision：写作决策摘要

把候选技法整理成可查询的 if-then：触发条件 → 可尝试的动作 → 效果解释（推测）→ 风险与边界。

检索给的是候选，不是写作命令；没有匹配时允许返回空。采用前核对本场目标、人物状态、读者已知信息和叙述视角。

## 命令

在本包根目录执行：

```bash
python3 skills/writing-decision/scripts/decide.py --scene 告别
python3 skills/writing-decision/scripts/decide.py --tags 悬疑 --scene 反派登场 --position 开篇
python3 skills/writing-decision/scripts/decide.py --list
python3 skills/writing-decision/scripts/decide.py --list --dimension 对话
python3 skills/writing-decision/scripts/decide.py --scene 告别 --json
```

| 参数 | 用途 |
|---|---|
| `--tags` | 题材，逗号、顿号等分隔 |
| `--scene` | 当前场景的具体描述 |
| `--position` | 开篇、中段、章末或卷末 |
| `--dimension` | 只查某个维度 |
| `--limit` | 限制返回数量，默认 4 |
| `--list` | 列出已有决策 |
| `--data` | 指定另一份决策 JSON |
| `--json` | 输出结构化结果 |

匹配使用关键词、同义词和位置规则，不是语义模型。匹配分数表示检索相关性，不表示写法质量或已验证程度。

## 数据格式

公开数据位于 `data/decisions.json`。保留原编号、触发条件、动作、解释、风险和关联；具体原文与书名章号保留在本地完整版。公开查询允许没有 `case`。

以下仅演示字段，不是实测写作经验：

```json
{
  "id": "D-DEMO-001",
  "dimension": "对话",
  "title": "在谈话目标发生变化时，检查回应是否随之调整",
  "trigger": {
    "genres": ["通用"],
    "exclude_genres": [],
    "scenes": ["谈话目标变化"],
    "positions": [],
    "when": "人物在对话中改变了想争取的结果"
  },
  "move": ["比较目标变化前后的回应是否承担同一功能"],
  "why": "推测：回应的变化可能帮助呈现人物此刻的取舍，仍需结合语境试用。",
  "risk": ["人物也可能有意维持原来的说法，不能只因没有变化就判错"],
  "related": [],
  "status": "untested"
}
```

`scene_aliases` 保存概念与同义词，`combos` 保存可选组合顺序。主场景应放在 `trigger.scenes` 的首位；新增同义词后，检查一个具体查询是否命中。组合也只是候选顺序，不要求整组采用。

## 状态与反馈

随包摘要从 `untested`（待试验）起步。阅读出处或跨书重复不是对照试写，不据此标为有条件有效。

使用记录、效果条件和调整方式见 [writing-loop](../writing-loop/SKILL.md)。已淘汰条目保留编号，不再推荐。对查询程序的验证与对写法效果的验证分别记录。
