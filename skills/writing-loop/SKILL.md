---
name: writing-loop
version: 0.1.0
description: "写作闭环编排：写完一章后的索引查询、文风体检、读者/挑刺代理、决策回填。把 novel-study 读出来的技法、writing-decision 的判断、scene-modules 的施工图串成一条流水线。触发方式：/writing-loop、/写作闭环、「写完了帮我体检」「派个读者看看」「用了哪条决策」。"
---

# writing-loop：写作闭环

> 把「读到的技法」变成「写作时能调用的判断」，再把「写完的效果」回填成证据。
> 它是 novel-study / writing-decision / scene-modules 的**编排层**，不重复造轮子。

## 一条流水线

```
① 判断    decide.py     这场戏该用什么手法（24 条决策 + 组合顺序）
② 查料    index.py      这个手法哪本书第几章写过（场景索引）
③ 施工    scene-modules 这个场景怎么搭、什么时候会崩（12 张卡）
④ 写      你/agent 动笔
⑤ 体检    style.py      句长/对话/标点像不像目标作者
⑥ 读者    reader-prompts 派读者代理：只想不想追下一章
⑦ 挑刺    reader-prompts 派挑刺代理：找逻辑漏洞和设定冲突
⑧ 回填    writeback.py  用了哪条决策、效果如何，status 升/降
```

**核心原则**：读过的才敢用，用过的才敢信。
没有索引的场景不让写，没有回填的决策不算验证过。

## 四个组件

| 组件 | 文件 | 干什么 |
|---|---|---|
| 场景索引 | `scripts/index.py` + `data/index.jsonl` | 从读书笔记里抽「场景 → 书 → 章号」 |
| 文风量化 | `scripts/style.py` + `data/profiles.json` | 统计目标作者文风，对比你的稿子 |
| 写完回填 | `scripts/writeback.py` + `data/writebacks.jsonl` | 记录决策使用效果，回填状态 |
| 代理模板 | `references/reader-prompts.md` | 读者代理 / 挑刺代理的 prompt |

## 命令

### ① 判断
```bash
python3 skills/writing-decision/scripts/decide.py --tags 玄幻 --scene "主角第一次杀人"
```

### ② 查料（按需读的关键）
```bash
python3 skills/writing-loop/scripts/index.py find --scene 打脸
python3 skills/writing-loop/scripts/index.py find --scene 托孤 --book 十日终焉
python3 skills/writing-loop/scripts/index.py list        # 场景排行
```
索引是**读出来的**：`index.py rebuild` 会扫所有单元笔记，把场景和章号抽出来。
没读过的书，用搜索或粗标补，别硬编。

### ③ 施工
```bash
python3 skills/scene-modules/scripts/query.py --type 打脸
```

### ⑤ 体检
```bash
python3 skills/writing-loop/scripts/style.py profile --book 十日终焉 --chapters 1-50
python3 skills/writing-loop/scripts/style.py check --file 命烛/正文/第001章_开火.md --target 十日终焉
```
输出 9 项指标对比，差距 >25% 的会标出来，并给人话判断。

### ⑥⑦ 读者 / 挑刺
按 `references/reader-prompts.md` 里两段 prompt 派子代理。
- 读者代理只给三问，**禁修改建议**；
- 挑刺代理只找硬伤，**禁提文笔**；
- 两个都只给正文，不给设定（给了设定，读者代理就变成编辑）。

### ⑧ 回填
```bash
python3 skills/writing-loop/scripts/writeback.py add \
  --chapter "命烛第1章" --used D-014,D-003 \
  --effect "手抖写了两处，第二处偏长" --verdict 一般

python3 skills/writing-loop/scripts/writeback.py report
python3 skills/writing-loop/scripts/writeback.py apply --dry-run
python3 skills/writing-loop/scripts/writeback.py apply
```
- 崩 ≥2 次 → `rejected`
- 好 > 崩 → `verified`
- 其余不降级

## 数据

| 文件 | 内容 |
|---|---|
| `data/index.jsonl` | 场景索引，一行一条 |
| `data/profiles.json` | 文风档案 |
| `data/writebacks.jsonl` | 回填记录，只追加 |

## 已验证（2026-10-21）

- `index.py rebuild`：从 114 篇笔记抽出 **317 条 / 20 种场景**，死亡 85、追逐 37 等
- `style.py profile`：十日终焉 1–50 章建档，均句 18.95、对话 53.37%
- `style.py check`：9 项指标对比，9 项超阈值，输出可读
- `writeback.py`：add/report/apply 跑通，dry-run 与幂等验证过

## 与其它 skill 的关系

- `novel-study`：**产数据**（读书 → 笔记 → 规则）
- `writing-decision`：**判断层**（这场用什么）
- `scene-modules`：**施工层**（怎么搭）
- `writing-loop`：**编排层**（把上面串起来，再补体检/读者/回填）

## 注意

- 索引和文风档案都依赖「真读过」。没读过的书不要往索引里塞假条目。
- `writeback.py apply` 会改 `decisions.json`，先 `--dry-run`。
- 读者代理和挑刺代理都要**只给正文**，否则它们会开始分析结构。
- **文风体检要选对目标作者**：命烛是黑暗残酷玄幻，拿《十日终焉》（无限流悬疑）当目标是会测出「句子短 35%」的——那不是写坏了，是题材不同。要么先给目标书按题材建档，要么只比较「同题材」的书。
- 文风体检的 9 项指标没有绝对好坏，只有「像不像目标」。差距大不等于要改，只等于「你离目标有多远」。
