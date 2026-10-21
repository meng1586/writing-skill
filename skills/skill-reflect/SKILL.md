---
name: skill-reflect
description: "Skill 自我改进：记录每次「哪里不好用」，同类问题攒到 3 条证据就升级为待改，输出带证据的改进报告（问题排行/建议改动/受影响文件），最后据此改 SKILL.md。触发：记录 skill 问题 / 看看 skill 哪里不好用 / skill 改进 / 这个 skill 卡在哪 / 记一笔。"
metadata: {"local": true, "project": "写点小说", "version": "0.1.0"}
---

# skill-reflect：让 skill 自己变好

本鲸的 skill 用起来总有不顺手的地方：读得慢、笔记重复、token 贵。
以前这些感觉聊完就散了；这个技能把它们变成证据，证据够了再动刀。

**记录 → 聚合 → 过阈值 → 出报告 → 改 SKILL.md → 再记录**

三条原则：

1. **先记录，后判断**：使用感受先留下依据，不凭一次不顺就扩改流程；已明确的实现错误可直接核验修复。
2. **同版本同类 ≥3 次使用可列为「待改」**：这是安排复核的默认阈值，不证明根因；已明确的实现错误可直接修复。
3. **改完留痕**：改了什么、为什么、证据是哪几条，写进本文件末尾的「改进记录」。

## 触发词

- 「记录一下 skill 问题」「记一笔」「这个 skill 哪里不好用」
- 「看看 skill 哪里不好用」「skill 改进」「skill 自检」「哪个 skill 该改了」
- `/skill-reflect`、`/skill 改进`

主人说「刚才那个 skill 太慢了/太贵了/老是重复」时，先记一条，再决定改不改。

## 30 秒上手

在当前克隆仓库根目录执行以下命令，不切换到原作者的工作区。

```bash
# 1) 用得不顺，记一条（只追加，不改任何 skill 文件）
python3 skills/skill-reflect/scripts/log.py \
    --skill novel-study --stage 笔记 \
    --issue "重复太多" --suggestion "0 节只写一次" --impact high

# 2) 随时看聚合报告（默认 markdown）
python3 skills/skill-reflect/scripts/report.py

# 3) 某个问题攒够 3 条 → 报告标「待改」→ 按建议改 SKILL.md
```

## 记录格式

路径：`data/usage/{skill}-{YYYY-MM-DD}.jsonl`，一行一条 JSON。

```json
{"ts":"2026-10-20T21:58:33+02:00","skill":"novel-study","stage":"笔记","issue":"重复太多","suggestion":"0 节只写一次","impact":"high"}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `ts` | 是 | ISO 8601 时间，带时区；补录可用 `--ts` |
| `skill` | 是 | skill 名，如 `novel-study` |
| `stage` | 是 | 出问题的环节，如 `笔记` / `读正文` / `审查` |
| `issue` | 是 | 问题是什么，越短越容易聚合，如 `重复太多` |
| `suggestion` | 否 | 建议怎么改，一句能落地的话 |
| `impact` | 是 | `high` / `medium` / `low` |
| `files` | 否 | 受影响文件数组；不填时报告按 `stage` 推断 |
| `skill_version` | 否 | 使用的版本或提交引用；旧记录保留为空，与新版本分别汇总 |
| `use_id` | 否 | 一次真实使用的标识，同版本同问题同次使用只计一次 |

**记录粒度**：一次使用最多记 1–2 条，只记真实卡点（耗时、返工、token 超预期、输出没法直接用）。
同一件事拆成 5 条刷阈值，等于骗自己。

## 命令

### log.py — 追加一条

```bash
python3 skills/skill-reflect/scripts/log.py \
    --skill novel-study --stage 笔记 \
    --issue "重复太多" --suggestion "0 节只写一次" --impact high \
    --file "skills/novel-study/data/notes/*.md"
```

| 参数 | 说明 |
|---|---|
| `--skill` | 必填，记录哪个 skill |
| `--stage` | 环节（默认「未标注」） |
| `--issue` | 必填，问题 |
| `--suggestion` | 建议改动（默认空） |
| `--impact` | `high`/`medium`/`low`（默认 medium） |
| `--file` | 受影响文件，可重复 |
| `--ts` | 补录时间，ISO 8601 |
| `--dry-run` | 只打印，不落盘 |
| `--json` | 机器可读输出 |
| `--data-dir` | 换记录目录（自测/归档用） |
| `--skill-version` | 使用的版本或提交引用 |
| `--use-id` | 一次真实使用的标识，用于防止重复计数 |

### report.py — 聚合报告

```bash
python3 skills/skill-reflect/scripts/report.py
python3 skills/skill-reflect/scripts/report.py --skill novel-study
python3 skills/skill-reflect/scripts/report.py --threshold 2 --json
python3 skills/skill-reflect/scripts/report.py --out .cache/skill-reflect/report.md
```

| 参数 | 说明 |
|---|---|
| `--skill` | 只看某个 skill |
| `--threshold` | 升级为待改所需证据数（默认 3） |
| `--top` | 问题排行显示条数（默认 20，0 = 全部） |
| `--json` | 输出 JSON（`skills[].issues[].evidence` 可审计） |
| `--out` | 写文件而不是打印 |
| `--data-dir` | 换记录目录 |

聚合规则：

- 同一 `skill`、同一版本下，`issue` 先归一化（去空白/首尾标点、ASCII 小写），再套少量同义词表
  （`太慢`→`慢`、`贵`/`太贵`→`token 太贵`、`内容重复`→`重复太多`）。
- 同类 `issue` 证据 ≥ 阈值 → **待改**；否则 **观察中**。
- 有 use_id 时同次使用不重复计数。未标版本的历史记录单独分组，不为补字段重写旧日志。修复前后的证据分别看；无新增日志也可能只是没有继续使用，不能单凭停止增长宣布修好。
- 排序：待改优先 → 证据条数 → high 影响数 → 最近一次出现时间。
- 坏行（JSON 错、缺字段、时间非法）跳过并在报告末尾列出，不影响其他记录。

报告里有：总览（每个 skill 的记录/问题类型/待改数）、问题排行（跨 skill）、
每个问题的证据条数、阶段分布、建议改动、受影响文件、逐条证据。文末给「下一步」。

## 报告长什么样（自测真实输出，节选）

```markdown
## 问题排行

| # | Skill | 问题 | 证据 | 高影响 | 状态 |
|---:|---|---|---:|---:|---|
| 1 | novel-study | 重复太多 | 4 | 3 | 待改 |
| 2 | novel-study | token 太贵 | 1 | 1 | 观察中 |
...

### 待改（同类 ≥3 条证据）

#### 1. 重复太多 — 4 条证据

- **状态**：待改
- **影响**：high 3 / medium 1
- **阶段**：笔记 2、前情提要 1、规则 1
- **建议改动**：
  - 0 节只在第一篇写，后续写「沿用全书判断」
  - 前情提要每 5 个单元重写一次，目标 ≤300 行
- **受影响文件**：
  - `skills/novel-study/data/notes/*.md`
  - `skills/novel-study/references/note-template.md`
- **证据**：
  - `2026-10-20 21:58`｜阶段 笔记｜high｜建议：0 节只在第一篇写…
```

## 改 SKILL.md 的落地清单

报告标「待改」之后，按这个顺序动刀：

1. **只改报告指向的地方**：优先 `SKILL.md`，其次 `references/`，最后才动脚本；别顺手重构。
2. **一条建议对应一处改动**：比如「0 节只在第一篇写」就只改模板/流程里 0 节那一段。
3. **保留证据**：日志不删不改，改完还能回看当时为什么改。
4. **跑一次该 skill 的现有命令**（如 `plan.py --json`），确认没把流程改坏。
5. **留痕**：在本文件「改进记录」加一行——日期、skill、证据条数、改了什么、怎么验证的。
6. **继续记录**：改进后记录新版本的真实使用和问题，再核对原问题是否仍出现；无继续使用或无人记录时，不能判断已经修好。

**不自动改文件**：`report.py` 只出报告，不写 `SKILL.md`。改不改、怎么改由主人和主会话定——
自动改自己的指令很容易越改越偏。

## 与 read-cycle 的关系

`read-cycle` 是 novel-study 的「子代理读书手册」，管**怎么读一个单元**；skill-reflect 是跨 skill 的
**元技能**，管**用完怎么把卡点沉淀成改进**。两者不重叠，也不改同一批文件。

- **子代理按读书授权写阅读产物，不改技能实现**：依照 `read-cycle.md` 写本次新笔记、必要的前情补充，
  通过 `shelf.py log` 记录实际读完范围并按规则同步；不在读书任务中改 `SKILL.md`、脚本或模板。
  返回可带一句使用卡点，**skill-reflect 的日志由主会话用 `log.py` 记录**。
- **读前情/写笔记的卡点**，主会话在单元结束后记一条：

  ```bash
  python3 skills/skill-reflect/scripts/log.py --skill novel-study --stage 笔记 \
      --issue "重复太多" --suggestion "0 节只在第一篇写" --impact high
  ```

- **进度与反思分开**：阅读进度以 `skills/novel-study/data/shelf.json` 的所选书 `chapters_done` 为准；
  历史 `data/state/reading-progress.json` 不再作为新书进度来源，也不自动迁移或重写。
  skill-reflect 日志只写 `skills/skill-reflect/data/usage/`，不代替笔记或阅读进度。
- **改 read-cycle 的判断**：同版本多次真实使用出现同类卡点时，报告可提高复核优先级；
  已明确的错误不必等满三次。改动由主会话按当前授权执行并留痕，不由读书子代理顺手修改。
- **顺序**：read-cycle 跑完 → 返回结果 → 主会话按需记日志 → 报告复核 → 按授权改进并检查新版本。

## 目录

```
skills/skill-reflect/
├── SKILL.md                 # 本文件
├── README.md                # 30 秒上手 + 设计取舍
├── SOURCE.md                # 为什么自研、检索记录
├── scripts/
│   ├── log.py               # 追加一条记录
│   └── report.py            # 聚合 + 报告 / JSON
└── data/usage/
    ├── novel-study-2026-10-20.jsonl
    ├── story-review-2026-10-20.jsonl
    ├── wjs-distilling-style-2026-10-19.jsonl
    └── scene-craft-2026-10-19.jsonl
```

## 现状（2026-10-20）

正式数据 6 条示例（novel-study 的慢/重复/贵 + 3 个其他 skill 各 1 条）。
自测追加 3 条「重复太多」后，`report.py` 把它标成待改，结果见
`.cache/skill-reflect-selftest/report.md`。正式数据目前没有待改项。

## 改进记录

| 日期 | 被改的 skill | 证据 | 改了什么 | 验证 |
|---|---|---|---|---|
| — | — | — | 暂无（等第一个攒够 3 条的问题） | — |

## 自测记录（2026-10-20）

- `python3 -m py_compile scripts/log.py scripts/report.py` → OK
- 隔离目录 `.cache/skill-reflect-selftest/usage/`：复制 6 条示例，再 `log.py` 追加 3 条
  `novel-study / 重复太多`（笔记、前情提要、规则各 1 条）。
- `report.py` 输出：记录 9 条，`重复太多` 4 条证据（high 3 / medium 1）→ **待改**，
  受影响文件列出 notes、note-template、read-cycle、rules；文末「下一步」提示可以动刀。
- `--json` 输出 totals/ranking/evidence 正常；`--skill` 过滤、`--threshold 2` 正常。
- 坏行测试：乱码行、缺字段行、非法时间行均被跳过并写入「坏行」附录，其余记录正常聚合。
- 同义词测试：`慢` + `太慢` 合并为 2 条，`贵` + `token 太贵` 合并为 2 条。

## 已知限制

- `issue` 是自由文本，靠归一化 + 少量同义词表合并；写法差太远会分成两类（如「慢」和「卡」）。
  记录时尽量用报告里出现过的高频词。
- 阈值 3 是默认值，长期跑可以按 skill 调（`--threshold`），但别为了「看起来该改」往下调。
- 记录不会自动清理；长期用建议按月归档：`mv data/usage/2026-10-*.jsonl data/usage/archive/`。
- 不自动改文件，也不自动跑被改 skill 的测试；落地这一步需要主会话/主人参与。
- 跨 skill 的同名问题不合并（例如 novel-study 的「慢」和 story-review 的「慢」是两件事）。
