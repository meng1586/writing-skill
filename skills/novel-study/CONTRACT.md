# novel-study 内部接口契约

> 本文件是协作契约，不是给主人看的文档。改接口先改这里，再改实现。

## 目录与归属

```
写点小说/
├── skills/novel-study/
│   ├── SKILL.md                 # lead
│   ├── SOURCE.md                # lead
│   ├── README.md                # lead
│   ├── config.json              # lead
│   ├── scripts/
│   │   ├── fetch.py             # collector
│   │   ├── shelf.py             # curator
│   │   └── plan.py              # lead
│   ├── references/
│   │   ├── note-template.md     # curator
│   │   └── rules-guide.md       # curator
│   └── data/
│       ├── shelf.json           # curator（唯一写者）
│       ├── notes/               # 本鲸按模板写笔记
│       ├── rules/               # 本鲸按结构沉淀规则
│       └── state/               # 调度状态
├── .cache/novel-study/books/    # collector 抓取缓存
│   └── {bookKey}/
│       ├── meta.json
│       └── chapters/0001.txt …
└── 06-素材/
    ├── 读/
    │   ├── 笔记/                # 笔记正式版（从 data/notes 同步）
    │   ├── 规则/                # 规则正式版（从 data/rules 同步）
    │   └── 选书/                # 选书评估记录
    ├── 写作/
    │   └── 备忘/                # apply.py 生成的写作前备忘
    └── 文风卡/                  # wjs-distilling-style 产物
```

`bookKey = f"{source}-{book_id}"`，例如 `fanqie-7143038691944959011`。

## 抓取缓存格式（collector 产出）

`meta.json`：

```json
{
  "key": "fanqie-7143038691944959011",
  "source": "fanqie",
  "book_id": "7143038691944959011",
  "name": "十日终焉",
  "author": "杀虫队队员",
  "desc": "简介…",
  "tags": ["悬疑", "无限流"],
  "word_count": 3201288,
  "read_count": 1761118,
  "creation_status": "连载中",
  "chapter_total": 300,
  "url": "https://fanqienovel.com/page/7143038691944959011",
  "fetched_at": "2026-10-20T14:40:00+02:00",
  "source_note": "官方SSR"
}
```

`chapters/0001.txt` 第一行固定为章节标题（`# 第1章 空屋`），空行后是正文纯文本（无 HTML、无广告行）。

下载范围外的章节不写文件；`failed` 只记录真正失败的章节号。

## fetch.py（collector 负责）

```bash
python3 scripts/fetch.py search "十日终焉" [--platform fanqie|tianxi|qidian|all] [--json]
python3 scripts/fetch.py info   --source fanqie --book-id 7143038691944959011 [--json]
python3 scripts/fetch.py book   --source fanqie --book-id 7143038691944959011 --from 1 --to 10 [--outdir DIR] [--json]
python3 scripts/fetch.py book   --source tianxi --book-id 94098167 --from 1 --to 10 [--json]
```

- 默认 `--outdir` 为 `<项目根>/.cache/novel-study/books`。
- 所有命令 `--json` 时 stdout 只输出一个 JSON 对象，日志走 stderr；不加 `--json` 输出人读文本。
- `search` 返回：`{"query": str, "results": [{"source","book_id","key","name","author","desc","word_count","url"}]}`
- `info` 返回：`{"ok": bool, "meta": {…同 meta.json…}, "error": str|null}`
- `book` 返回：`{"ok": bool, "key","outdir","downloaded":[int],"failed":[int],"chapter_total":int,"error":str|null}`
- 源适配必须可插拔：新源 = 一个函数/类，注册到 `SOURCES` 字典。

### 已验证事实（本鲸 2026-10-20 实测，直接用）

- 番茄作品页 `https://fanqienovel.com/page/{bookId}` SSR 内 `window.__INITIAL_STATE__.page` 有：`bookName/author/description/categoryV2/wordNumber/readCount/creationStatus/abstract`。
- 番茄目录 API：`https://fanqienovel.com/api/reader/directory/detail?bookId={bookId}` → `{"data":{"allItemIds":[...]}}`。
- 番茄章节页 `https://fanqienovel.com/reader/{itemId}` SSR 内 `window.__INITIAL_STATE__.reader.chapterData` 有 `title/content/bookName/chapterWordNumber/needPay/isChapterLock`；`content` 是 `<p>…</p>` HTML，需清洗。
- `__INITIAL_STATE__` 提取要用「括号平衡扫描」，不要用正则 `{.*?}`（正文里有花括号会截断）。
- 番茄搜索页/搜索 API 直连拿不到；`找书` 由 agent 用 web_search 或扫榜补，脚本 `search --platform fanqie` 允许走「网页搜索兜底」并在 stderr 说明。
- **番茄正文有字体反爬**：`chapterData.content` 里常用字是私有区码位（`\ue4de` 等），字体全站共用 `dc027189e0ba4cd`（思源黑体 SC 2.002R 子集，name-keyed CFF，glyph 名不可反查 GID）。`fetch.py` 内置 362 字 bootstrap 表；换字体会下载子集+参考字体动态重建（有 fontTools 时 362/362，无则约 117/362 并 stderr 警告）。参考字体缓存在 `.cache/novel-study/fonts/`（16.8MB，OFL）。
- 番茄作品页 `page.itemIds` 倒序，章节顺序以目录 API `allItemIds` 为准。
- 起点本站 curl 返回 202 挑战页；起点只用 `story-long-scan/scripts/qidian-rank-scraper.js` 扫榜找书，正文走免费源。
- 天禧真实域名是 `www.tianxixsw.com`（`www.tianxibook.com` 301 跳过去）；站内搜索已被站长关闭，单章会分页需跟随 `rel="next"` 拼接。
- 三个源的 `search` 都拿不到可靠结果：番茄搜索接口封死、天禧站内搜索关闭、起点只有畅销榜前 20。**找书交给 agent 的 web_search，脚本只负责 info/book。**
- `69shu.com` Cloudflare 403；`baidu.com` 直连触发安全验证；**不要**把这两个做成硬依赖。
- `www.tianxibook.com` 200，站内结构为 `/book/{id}/`，需 collector 自行探清搜索与目录。

## shelf.json（curator 负责，schema 冻结）

```json
{
  "version": 1,
  "settings": {"daily_chapters": 3, "time_budget_min": 40, "retention_days": 30},
  "books": [
    {
      "key": "fanqie-7143038691944959011",
      "name": "十日终焉",
      "author": "杀虫队队员",
      "source": "fanqie",
      "book_id": "7143038691944959011",
      "status": "reading",
      "quality": 5,
      "verdict": "keep",
      "verdict_reason": "数字矛盾开局可偷",
      "added": "2026-10-20",
      "chapters_done": 0,
      "chapter_total": 300,
      "local_dir": ".cache/novel-study/books/fanqie-7143038691944959011",
      "tags": ["悬疑", "无限流"],
      "sessions": [
        {"date": "2026-10-20", "chapters": 3, "minutes": 25, "note": "开篇钩子分析"}
      ],
      "last_studied": "2026-10-20"
    }
  ]
}
```

约束：
- `key` 唯一；重复 `add` 报错退出码 2。
- `status ∈ {unread, reading, done, dropped}`。
- `quality ∈ 0..5`（0 = 未评）。
- `verdict ∈ {keep, watch, drop}`（默认 watch）；`drop` 的书 `next` 不推。
- `verdict_reason` 为什么这么判，一句话。
- `sessions` 只追加，不改历史。
- 所有命令写文件用「临时文件 + 原子替换」，损坏时能从 `.bak` 恢复。
- `next`：优先 `reading` 里 `last_studied` 最早或 `chapters_done/chapter_total` 最低的；没有 `reading` 则给 `unread`；全空返回 `{"book": null, "reason": "shelf_empty"}`。

## apply.py（lead 负责）

```bash
python3 scripts/apply.py --tags 玄幻,悬疑 [--book 命烛] [--json] [--no-write]
```

- 从 `data/rules/{维度}.md` 按「适用题材」筛规则（「通用」也匹配；「通用，除 X」排除 X）。
- 输出到 `06-素材/写作/备忘/{日期}-{标签}.md`，内容 = 匹配规则 + 文风卡列表 + 写作前自检。
- 被 `- 状态：已淘汰` 标记的规则跳过。

## plan.py（lead 负责）

```bash
python3 scripts/plan.py [--json]   # 生成「今天学什么」清单：今日书目、下一批章节号、笔记待补清单
```

## 笔记与规则（curator 定义格式，本鲸填内容）

- 笔记：`data/notes/{书名}.md`，按 `references/note-template.md` 的**三层阅读法**（读者层不许用分析词）。
- 规则：`data/rules/{维度}.md`，按 `references/rules-guide.md`；每条规则必须带「出处：《书名》第N章」和「反例/正例」。
- 同步：`scripts/plan.py --sync` 把 `data/notes/*`、`data/rules/*` 复制到 `06-素材/读书笔记/`、`06-素材/写作规则库/`。
