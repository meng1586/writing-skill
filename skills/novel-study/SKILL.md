---
name: novel-study
description: "按学习目标选材、阅读、记录观察并提炼候选技法；写作时按条件查询规则摘要。触发：/novel-study、学习写小说、读书学习、检查阅读进度、写作前翻规则。"
metadata: {"version":"1.2.0-public","project":"写作学习"}
---

# novel-study：阅读与候选技法

选材 → 读相关正文 → 区分观察与解释 → 提出候选 → 按需试写与回填。

阅读范围由目标决定：句法可抽样，场景效果需要铺垫与后果，人物弧线或宏观结构可能需要完整叙事线。没有找到合适材料或候选时，仍可继续写作。

## 三层阅读

| 层 | 记录什么 | 结论边界 |
|---|---|---|
| 阅读反应 | 发生了什么、哪里停下、疑问和具体反应 | 模型判断不是独立真人反馈 |
| 文本拆解 | 哪些句子、动作或信息安排支持观察；哪些效果只是推测 | 原文存在某种写法，不直接证明其效果 |
| 写作假设 | 在什么条件下可试哪一步，什么时候可能不适用 | 不要求填满所有维度或凑固定数量 |

使用 [笔记模板](references/note-template.md)。先记录可定位的反应，再讨论写法；这个顺序用于减少先套术语的倾向，不是阅读质量的自动判据。

## 查询候选

以下命令均在本包根目录执行：

```bash
python3 skills/novel-study/scripts/plan.py
python3 skills/novel-study/scripts/plan.py --json
python3 skills/novel-study/scripts/apply.py --tags 玄幻,悬疑 --book 我的作品 --no-write
python3 skills/novel-study/scripts/apply.py --list
```

`apply.py` 输出匹配摘要及本地已有的文风卡、可选自检清单。题材命中只说明检索相关，不保证适合当前场景。去掉 `--no-write` 才会生成写作备忘。

公开规则摘要位于 `data/rules/{维度}.md`；原文和来源留在本地完整版中。规则格式见 [摘要说明](references/rules-guide.md)。

## 书架、阅读范围与进度

```bash
python3 skills/novel-study/scripts/shelf.py list
python3 skills/novel-study/scripts/shelf.py next
python3 skills/novel-study/scripts/shelf.py report
python3 skills/novel-study/scripts/shelf.py add --help
python3 skills/novel-study/scripts/shelf.py log --help
```

`plan.py` 只接受 `--json` 和 `--sync`。需要交给子代理阅读时，由主会话明确指定书架 key 和章节范围，再用 `plan.py --json` 核对计划与现有进度；不要给它不存在的 `--book-key` 或 `--chapters` 参数。操作顺序见 [单元阅读手册](references/read-cycle.md)。

联网采集可用 `fetch.py search/info/book`，运行前阅读对应 `--help`。来源不可用或正文缺失时如实标注，可使用自己已有的本地文本，不补造内容。外部 `story-*` 或文风蒸馏技能不随包提供，不作为本模块可运行的前置条件。

## 文件分工

| 位置 | 用途 |
|---|---|
| `data/shelf.json` | 使用者本地的书架与进度 |
| `data/notes/` | 本地阅读笔记与上下文 |
| `data/rules/` | 可查询的规则摘要 |
| `.cache/novel-study/books/`（包根目录下） | 使用者本地正文缓存 |
| `06-素材/读/笔记/`、`06-素材/读/规则/`（包根目录下） | 按 `config.json` 同步的副本 |
| `06-素材/写作/备忘/`（包根目录下） | 按需生成的写作备忘 |

```bash
python3 skills/novel-study/scripts/plan.py --sync
```

同步会写入本包配置指定的位置。公开整理不回写原项目，也不迁移或重写旧笔记。

## 情绪与宏观结构

情绪分析可以从关切对象、人物与读者已知信息、判断和情绪变化入手；这些是提问视角，不是每场必走的固定链条。人物异常平静、静场或幽默也可能承担不同功能，需要结合语境判断。

将候选路径、效果推测、作者自检和真人反馈分开记录；一个读者的反应只支持该次条件下的观察。宏观结构参照 [卷纲模板](references/卷纲模板.md)，按自然转折选择问题，不要求每章填满表格。

## 维护

- 新笔记和候选保留原编号、适用条件及调整理由。
- 来源覆盖与试用状态分开：更多阅读案例不自动升级试用效果。
- 合并前核对条件与动作是否真正相同，保留旧编号指路。
- 后台采集是可选配置；本包不会因普通查询而安装或启用定时任务。
