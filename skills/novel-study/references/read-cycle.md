# 单元阅读手册

用于把一段有明确范围的阅读交给子代理或独立会话。只处理主会话指定的书与范围，不自行扩成全库阅读，也不改已有笔记。

## 1. 核对对象与范围

主会话先明确书架 key、阅读目标、章节范围和可写目录。运行：

```bash
python3 skills/novel-study/scripts/plan.py --json
python3 skills/novel-study/scripts/shelf.py list
```

`plan.py` 只有 `--json` 和 `--sync`；不要传 `--book-key` 或 `--chapters`。将计划输出与指定的 key、已有进度对照，确认没有接到另一部作品。阅读范围需要调整时先说明原因。

## 2. 读取必要语境

读该材料的本地前情提要、与本次目标相关的设定和上一单元结论。需要讨论场景效果时补足铺垫和后果；不要只截取一个精彩片段就判断整条叙事线。

正文一般位于包根目录的 `.cache/novel-study/books/{key}/chapters/`，或书架条目指定的位置。缺失、乱码或范围不符时如实报告，不补造正文。已有本地材料可直接使用，联网采集是可选步骤。

## 3. 写新笔记

使用 [笔记模板](note-template.md)，写到 `skills/novel-study/data/notes/{书名}/`。区分文本事实、效果推测和写作假设；只记值得保留的内容，不要求所有维度齐全。

具体原文、来源和项目细节属于本地阅读记录，不自动复制到公开摘要。情绪分析可记录关切、已知信息与判断变化，但不要求每场完成同一条链路。

## 4. 记录进度

确认本次确实完成的章数和用时，再运行：

```bash
python3 skills/novel-study/scripts/shelf.py log --help
```

按实际 key 用 `log --key ... --chapters ... --minutes ... --note ...` 追加记录。不要通过修改另一份历史单书状态文件来代替当前书架进度。

## 5. 按需同步与交接

```bash
python3 skills/novel-study/scripts/plan.py --sync
```

同步目标由 `skills/novel-study/config.json` 指定：包根目录的 `06-素材/读/笔记/` 与 `06-素材/读/规则/`。这个操作会写入副本，按任务范围使用；不自行提交 Git、安装定时任务或发布材料。

返回：已完成范围、笔记路径、一句话观察、缺失或待核对事项。主会话不需要接收整段正文。
