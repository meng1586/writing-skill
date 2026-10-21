---
name: writing-loop
version: 0.1.0-public
description: "串联候选查询、可选文风统计、读者与事实校对、试写回填。触发：写作闭环、写完帮我体检、派个读者看看、记录用了哪条决策。"
---

# writing-loop：写作与反馈

按当前问题选择环节，不要求每章跑完整条流水线：

候选查询 → 写作或局部试改 → 回读与反馈 → 记录条件 → 调整候选。

没有索引或匹配卡片时可以正常写。检索成功只验证工具可用，反馈也不自动证明写法有效。

## 查询与索引

```bash
python3 skills/writing-decision/scripts/decide.py --scene 告别
python3 skills/scene-modules/scripts/query.py --type 告别
python3 skills/writing-loop/scripts/index.py find --scene 告别
python3 skills/writing-loop/scripts/index.py list
```

公开索引初始为空。使用者自己的本地笔记可用 `index.py rebuild` 重建索引，或用 `add` 记录一条；不要补造没有阅读过的定位信息。索引原文和具体来源不随公开摘要分发。

## 文风统计（可选）

```bash
python3 skills/writing-loop/scripts/style.py list
python3 skills/writing-loop/scripts/style.py profile --help
python3 skills/writing-loop/scripts/style.py check --help
```

文风建档需要使用者本地的文本缓存；公开包不预装原项目的作者档案。句长、标点和对话占比用于定位值得检查的差异，不是质量达标线，差异大也不意味着应该改稿。

## 阅读反馈与事实校对

模板见 [reader-prompts.md](references/reader-prompts.md)。

- 阅读反馈：明确测试的是首次接触，还是已经读过必要前文的阅读条件。按这个条件提供材料；缺少必要前情不能直接算章节缺陷。
- 事实校对：提供正文、相关设定与前文，检查因果、设定和时间线。
- 模型反馈是待核实的判断。分数、角色记忆或单个出戏句都不直接决定删改，先回到具体文本与创作目标核对。

## 记录与回填

以下写入的是使用者本地记录：

```bash
python3 skills/writing-loop/scripts/writeback.py add   --chapter "我的作品第1章" --used D-001   --effect "只记录这次试用观察，尚未做对照" --verdict 一般 --compared no

python3 skills/writing-loop/scripts/writeback.py report
python3 skills/writing-loop/scripts/writeback.py apply --dry-run
```

确认变更后再运行 `apply`。它会修改当前包的决策状态文件；公开整理不得回写原项目的完整库。

| 状态 | 说明 |
|---|---|
| `untested` | 尚未试用 |
| `tried` | 有使用记录，尚无对照结论 |
| `conditional` | 当前对照记录倾向有帮助，仍须核对具体条件 |
| `dropped` | 当前对照记录倾向不采用，保留编号与理由 |
| `no-diff` | 当前对照记录未显示明确差别 |

脚本对比的是记录中的评价，不是独立判断效果。`conditional` 也不表示普遍有效；阅读中发现多个案例不能替代试写。

## 数据分工

`data/index.jsonl` 是本地场景定位；`data/profiles.json` 是按需生成的文风档案；`data/writebacks.jsonl` 是追加式反馈记录。公开包带摘要数据，使用者的原文、正文和反馈记录继续保存在本地。
