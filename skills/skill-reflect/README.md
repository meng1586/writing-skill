# skill-reflect — 让 skill 自己变好

用 skill 时觉得不顺（慢、重复、贵、输出没法直接用），记一条；
同类问题攒到 3 条，自动升级成「待改」，出报告告诉你该改哪个文件的哪一段。

```
记录 → 聚合 → 过阈值 → 出报告 → 改 SKILL.md → 再记录
```

## 30 秒上手

```bash
cd /Users/meng/Desktop/deepseek相关/写点小说

# 记一条
python3 skills/skill-reflect/scripts/log.py \
    --skill novel-study --stage 笔记 \
    --issue "重复太多" --suggestion "0 节只写一次" --impact high

# 看报告
python3 skills/skill-reflect/scripts/report.py

# 机器读
python3 skills/skill-reflect/scripts/report.py --json
```

完整说明见 [SKILL.md](SKILL.md)。

## 设计取舍

1. **jsonl 而不是数据库**：一行一条、能 diff、能 grep、坏一行不坏整份。个人项目不需要 SQLite。
2. **只追加不改写**：日志是证据，改完还要能回看「当时为什么改」。report 不做任何写入。
3. **阈值 3**：一次不爽可能是偶然，三次才是设计问题；阈值可调，但默认不下调。
4. **不自动改文件**：报告只给建议。自动改自己的指令很容易越改越偏，落地必须有人参与。
5. **issue 归一化 + 小同义词表**：不做模糊匹配，避免把「慢」和「卡」误并成一条假证据。
6. **受影响文件两级兜底**：日志显式 `files` 优先；没填就按 `stage` 查表；再没有就落到 `SKILL.md`。
7. **保留 read-cycle 的边界**：子代理只读不记不改，记录由主会话做；日志和笔记物理隔离。

## 目录

| 位置 | 是什么 |
|---|---|
| `SKILL.md` | 完整手册：触发词、格式、命令、改 SKILL.md 清单、与 read-cycle 的关系 |
| `scripts/log.py` | 追加一条记录（带 fcntl 锁，`--dry-run`/`--json`） |
| `scripts/report.py` | 聚合、阈值判定、markdown/JSON 报告 |
| `data/usage/{skill}-{date}.jsonl` | 使用记录（只追加） |

## 自测（2026-10-20）

隔离目录跑通：6 条示例 + 追加 3 条 `novel-study / 重复太多` → 报告 4 条证据、
状态「待改」；`--json`、`--skill`、`--threshold 2`、坏行跳过、同义词合并均验证通过。
结果留在 `.cache/skill-reflect-selftest/report.md`。

## 已知限制

- 自由文本 `issue` 仍可能分叉，记录时尽量复用已有高频词。
- 不自动清理历史日志，长期用建议按月归档到 `data/usage/archive/`。
- 不自动改文件、不自动跑回归；这一步留给主会话。
