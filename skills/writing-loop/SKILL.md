---
name: writing-loop
description: "写作闭环：按需查技法和场景出处、统计文风差异、组织模型审阅与真人反馈，记录试用和有条件的对照结果。适用于写后检查、局部改稿和反馈回填；没有实测不阻塞原创写作。"
metadata: {"version": "0.2.0"}
---

# writing-loop：写作闭环

按当前问题选择需要的环节，不必每章跑完整流程：

1. 构思或卡住时，可查 writing-decision 与 scene-modules 的候选技法、适用条件、出处和风险。
2. 需要对照原例时，用 `scripts/index.py find --scene 场景` 查出处；查不到可继续原创，不能编造原文依据。
3. 写完后按需做文风统计、模型审阅或真人试读。已写前文是阅读语境，后续大纲和作者预设答案不是读者材料。
4. 用 `scripts/writeback.py` 留下使用、修改与反馈记录；效果结论取决于证据类型，不取决于用了几次。

场景卡可用于写前选路、写后定位问题，或只改一个已识别问题；不是必须照做的施工步骤。未测、没有匹配卡或没有真人读者时，可正常写作并保留验证状态。

## 查出处与文风统计

```bash
python3 skills/writing-loop/scripts/index.py find --scene 告别
python3 skills/writing-loop/scripts/style.py profile --book 十日终焉 --chapters 1-50
python3 skills/writing-loop/scripts/style.py check --file 正文/第001章.md --target 十日终焉
```

profile 写入文风档案，check 比较十项统计。选择与当前目标相关的样本和范围；题材、视角、场景功能不同，差异可能有合理原因。统计用于提出待核对的问题，不能证明风格相同、稿子更好或情绪有效，也不要求把稿子改到某个数值范围。

## 模型审阅与真人试读

需要时读取 [references/reader-prompts.md](references/reader-prompts.md)：

- 阅读反应检查：给当前章和目标读者实际已读的前文，不给后续大纲、作者意图或期待答案。模型输出标为模型推演；真人反馈单独记录。
- 一致性检查：另给已定人物、规则、时间线及可追溯的前文事实。让审阅者指出本章与对照材料的位置，证据不足时保留待确认。
- 两种审阅不互相灌输结论；意见先核对原文和任务目标，再决定是否改。没有固定追更分数或句式阈值决定质量。

## 使用记录与效果证据

普通使用、作者自检、模型审阅均可先记录：

```bash
python3 skills/writing-loop/scripts/writeback.py add \
  --chapter "试写第1章" --used D-014 --reviewer-type model \
  --effect "模型指出第二处身体反应可能重复，尚未真人试读" --verdict 一般
```

`--reviewer-type` 默认 usage（普通使用），author 是作者自检，model 是模型评审。`--verdict 好/一般/崩` 保留为记录者描述，不作为投票。旧日志，包括只有 `--compared yes` 的记录，继续作为使用记录，不冒充真人对照证据。

若确有真人对照反馈，可以补齐本条技法在 B 相对 A 的结果：

```bash
python3 skills/writing-loop/scripts/writeback.py add \
  --chapter "试写第1章" --used D-014 --reviewer-type reader \
  --draft-a-ref "试写/A.md@版本1" --draft-b-ref "试写/B.md@版本1" \
  --feedback-ref "反馈/读者原话.md#本次试读" \
  --condition "人物试图维持镇定，限知视角可呈现身体感受" \
  --comparison-result better --confirm-result \
  --effect "读者更容易看出B稿人物在维持镇定，原话和起始句见反馈" --verdict 好
```

引用应能找回固定版本的两稿与实际反馈；无法定位起始句可如实留空。reader 只指真人，不能把读者模型代理改名为真人。confirm-result 表示记录者已核对引用与结论，不是把技法升级为普遍规律。一次效果对照只对应一条决策；多技法共同使用可另作普通记录，不能把整场效果归给每条技法。

```bash
python3 skills/writing-loop/scripts/writeback.py report --json
python3 skills/writing-loop/scripts/writeback.py apply --dry-run
python3 skills/writing-loop/scripts/writeback.py apply
```

apply 只更新决策状态与证据摘要，不改正文或历史记录：

| 状态 | 含义 |
|---|---|
| untested | 候选技法，尚未试用；有原文出处也不代表有效 |
| tried | 已使用或自检，尚无完整的真人对照结论 |
| conditional | 真人对照在所记录条件下支持 B，保留条件和反馈引用 |
| dropped | 记录条件下暂不采用，不能推广为所有场景无效 |
| no-diff | 真人对照明确反馈两版看不出区别 |
| retired | 已退役，不被普通记录或一条好评自动复活 |

普通记录不覆盖已有 conditional/dropped/no-diff/retired。相反结果保留各自条件并标记需复核，不用好坏票数抵消成“无差异”。旧 derived/verified 按待试验理解，旧 rejected 按暂不采用理解，迁移时保留 legacy_status。

## 数据与边界

- data/index.jsonl：场景与出处索引；关键词命中不是对原文效果的验证。
- data/profiles.json：描述性统计档案；建档会覆盖同名档案，按需执行。
- data/writebacks.jsonl：只追加的使用与反馈记录。
- apply 会修改 writing-decision/data/decisions.json，先查看 dry-run；测试用 writebacks/decisions 参数指向临时夹具。

新格式只向后用于未写单元或新反馈；不为补字段重写旧笔记、旧日志、正式副本或重置阅读进度。
