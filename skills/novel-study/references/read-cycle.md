# 单元阅读执行手册（给读书子代理）

> 目标：一次只读一个单元（默认 10 章），产出笔记并更新进度，
> 让主会话不必把正文塞进上下文。**正文只在你这里读，读完就丢。**

## 前置

工作目录：`/Users/meng/Desktop/deepseek相关/写点小说`
所有路径相对这个目录。

## 步骤

### 1. 取单元

读 `skills/novel-study/data/state/reading-progress.json`：

- `last_read_chapter` 是已读完的最后一章。
- 本次范围 = `[last_read_chapter+1, last_read_chapter+unit_size]`。
- 若范围上限超过 `total_chapters`，只读到 `total_chapters`。
- 若 `last_read_chapter >= total_chapters`，直接返回「全书读完」，不再读。

### 2. 读前情

读 `skills/novel-study/data/notes/{书名}/前情提要.md`（如《十日终焉》就是
`十日终焉/前情提要.md`）。**不要重读前面的章节正文。**

### 3. 读正文

```
.cache/novel-study/books/{book_key}/chapters/0001.txt … 1496.txt
```

文件名是四位数字，按章节号取。若某章文件不存在或不足 500 字，说明抓取失败：
先跑
`python3 skills/novel-study/scripts/fetch.py book --source fanqie --book-id {book_key} --from N --to M --json`
补抓；补不到就在笔记里标注「本章缺失」，不要编。

### 4. 写笔记

文件名：`skills/novel-study/data/notes/{书名}/第{A:03d}-{B:03d}章.md`（每本书一个目录）

结构严格按 `skills/novel-study/references/note-template.md`，重点是：

- **1. 读者层**：第一条必须是「这一段大概讲了什么」（3–5 句纯情节，只讲事不评判），
  然后才是感受、哪里停下、疑问、想起什么、会追吗、想抄的一句。**不许出现分析词。**
- **2. 拆解层**：每个维度回答「作者怎么做到的」，不是「有什么」。
- **2.7 语言指纹**：句长/标点/用词/比喻取材/感官/对话/视角/描写配比/去 AI 味对照。
- **2.8 风格指纹**：一句话味道 + 3 句锚点原句（标章号）+ 模仿三件事 + 学不来的东西。
- **3. 写作层**：能落笔的 3 条（动词开头）+ 写不出来的 1 句 + 下次要试 + 味道。
- **4. 不适用**。

**质量线**：
- 至少 3 句原文摘引，标章号。
- 「语言指纹」要具体到能照着模仿。
- 不写剧情复述当分析。

参考已完成的笔记（读 1–2 篇找手感，别全读）：`十日终焉.md`、`十日终焉-第41-50章.md`。

### 4.5 更新前情提要

读 `data/notes/{书名}/前情提要.md`，把本单元出现的**新人物、新设定、新线索、本单元已回收的伏笔**追加进去，
并把文件开头的「截至第 X 章」改成新的章号。

要求：
- 只写设定/人物/线索，不写情节细节（情节细节留给单元笔记）。
- 已回收的伏笔从「未回收」挪到「已回收」，附一句怎么回收的。
- 如果前情提要明显落后（比如落后两个单元以上），先读最近两篇单元笔记把它补到当前进度再写本单元。

### 5. 更新进度

改 `reading-progress.json`：`last_read_chapter` 改成新读完的最后一章，
`units_done` 追加 `{"range":[A,B],"note":"文件名"}`，`updated` 写当前时间。

### 6. 同步与提交

```bash
python3 skills/novel-study/scripts/plan.py --sync
python3 skills/novel-study/scripts/shelf.py log --key {book_key} --chapters {章数} --minutes {估计分钟数} --note "读完 {A}-{B} 章"
cd /Users/meng/Desktop/deepseek相关
git add 写点小说/skills/novel-study/data 写点小说/06-素材/读
git commit -q -m "feat(小说): 读完第{A}-{B}章"
```

### 7. 返回

只返回一行：

```
已读完 {A}-{B} 章｜笔记 {文件名}｜一句话：{本单元最值钱的一条写作观察}
```

不要把正文、不要贴长段笔记。主会话只看这一行。

## 禁止

- 不要改 `SKILL.md`、`fetch.py`、`shelf.py`、模板。
- 不要一次读超过 20 章（会爆上下文）。
- 不要在前情提要之外重读旧章节。
- 笔记里不要抄大段原文，摘句不超过 3 句/处。
