---
name: novel-study
version: 1.1.0
description: "长期读书学习：先会挑好书（分级+止损），再按三层阅读法真读（感受→拆解→写作），蒸馏成可执行规则，写正文前自动把规则翻出来。触发方式：/novel-study、/学习写小说、「看书学习」「读书打卡」「检查读书进度」「补笔记」「写作前翻规则」。"
metadata: {"local":true,"project":"写点小说","reuses":["story-long-scan","story-long-analyze","story-deslop","wjs-distilling-style"]}
---

# novel-study：长期读书学习

主人说「有事没事去看看书学习怎么写好小说」。这个技能就是本鲸的读书桌：

**挑好书 → 抓正文 → 三层真读 → 蒸馏规则 → 写作前自动调用**

不是扫榜（那是 `story-long-scan`），不是写书（那是 `story-long-write`）。
它只干一件事：**让本鲸越读越会写**。

三条铁律：
1. **差书不学**。读烂书只会把烂手感练熟。选书有门槛，试读有止损。
2. **先当读者，再当拆解者**。不先真读，拆出来的全是套路，没有体温。
3. **读过的东西必须能进写作**。规则库不是摆设，写正文前要翻一次。

---

## 触发词

- `/novel-study`、`/学习写小说`、`/看书学习`、`/读书打卡`
- 「今天学点什么」「检查读书进度」「这周的笔记补一下」「给我找几本书拆」
- 「写作前翻一下规则」「这本书值不值得学」

## 五步循环

```
① 选书   shelf.py next / plan.py           → 今天读哪本、读哪几章
② 抓章   fetch.py book --from --to         → 正文落到 .cache/novel-study/books/
③ 真读   三层阅读法（见下）                 → data/notes/{书名}.md
④ 沉淀   蒸馏规则 + 更新文风卡               → data/rules/{维度}.md
⑤ 复用   写正文前跑 apply.py                → 06-素材/写作/备忘/{日期}.md
```

一轮 30–40 分钟，默认 3 章。**宁可少读、读透，不要一次吞十本。**

---

## ① 选书：先会挑，再谈学

完整门槛见 `references/选书标准.md`。加书时过三关：

1. **硬性排除**：AI 代写感、拼接洗稿、断更、数据不可信 → 直接不读
2. **数据 + 口碑**：番茄在读 ≥ 50 万 / 起点月票畅销榜前 100 / 出版改编获奖；口碑要有具体正反评价
3. **试读**：抓前 3 章，回答「有没有我写不出来的东西？有没有想偷的结构？想不想翻第 4 章？」

读完前 3 章**必须给评级和结论**，不许「先放着」：

```bash
python3 $SKILL_DIR/scripts/shelf.py judge --key fanqie-7143038691944959011 \
    --quality 5 --verdict keep --verdict-reason "数字矛盾开局，可偷"
```

`verdict = keep / watch / drop`。drop 的书不再推，但**要留一条「差在哪」**——知道什么不能写和知道什么该写一样值钱。

---

## ③ 三层阅读法（核心）

模板：`references/note-template.md`。顺序不能换：

| 层 | 干什么 | 禁忌 |
|---|---|---|
| 1 读者层 | 先写「这一段大概讲了什么」（3–5 句纯情节），再写感受、哪里停下、疑问、想起什么、会不会追 | **不许用「节奏/钩子/人设/爽点」这些分析词**；梗概只讲事、不评判 |
| 2 拆解层 | 每个维度回答「作者**怎么做到的**」，不是「有什么」 | 写「有悬念」是废话；写「把答案拆成三份，每章末给一份」才算拆解 |
| 3 写作层 | 能落笔的 3 条动作 + 写不出来的 1 句原文 + 下次要试的一件事 + 这本书的「味道」 | 写不出动作的，不算带走 |

为什么这样分：只拆元素，学到的只是骨架；只谈感受，学不到能落笔的东西。**先被它打动，再研究它怎么打动你。**

---

## ⑤ 复用到写作（读写打通的关键）

写正文前跑一次，把读过的规则按当前题材筛出来：

```bash
python3 $SKILL_DIR/scripts/apply.py --tags 玄幻,悬疑 --book 我的书
# 产物：06-素材/写作/备忘/{日期}-{标签}.md
```

它会给你：匹配的规则（含正例反例）+ 文风卡路径 + 写作前自检清单。
**这就是「写的时候不会忘掉读过的」的机制**——不靠记性，靠命令。

---

## 命令参考

所有命令在项目根 `/Users/meng/Desktop/deepseek相关/写点小说` 执行，`SKILL_DIR=skills/novel-study`。

### 书架与进度

```bash
python3 $SKILL_DIR/scripts/shelf.py add --key fanqie-7143038691944959011 \
    --name 十日终焉 --source fanqie --book-id 7143038691944959011 \
    --quality 5 --verdict keep

python3 $SKILL_DIR/scripts/shelf.py list            # 全部书架（含星级/结论）
python3 $SKILL_DIR/scripts/shelf.py next            # 下一本该读的（不推 drop）
python3 $SKILL_DIR/scripts/shelf.py judge --key <key> --quality 4 --verdict watch
python3 $SKILL_DIR/scripts/shelf.py log --key <key> --chapters 3 --minutes 38 --note "…"
python3 $SKILL_DIR/scripts/shelf.py report          # 统计 + 评分分布
python3 $SKILL_DIR/scripts/shelf.py recover         # shelf.json 损坏时从 .bak 恢复
```

### 找书与抓正文

```bash
# 脚本 search 只能给榜单线索；书名→bookId 靠 agent 的 web_search
python3 $SKILL_DIR/scripts/fetch.py search "十日终焉" --platform all --json
python3 $SKILL_DIR/scripts/fetch.py info --source fanqie --book-id {bookId} --json
python3 $SKILL_DIR/scripts/fetch.py book --source fanqie \
    --book-id 7143038691944959011 --from 1 --to 3 --json
# 起点正文拿不到正版时走免费源
python3 $SKILL_DIR/scripts/fetch.py book --source tianxi --book-id <id> --from 1 --to 3
```

### 计划、备忘与同步

```bash
python3 $SKILL_DIR/scripts/plan.py            # 今天学什么
python3 $SKILL_DIR/scripts/plan.py --json     # 给 agent 的结构化清单
python3 $SKILL_DIR/scripts/plan.py --sync     # 笔记/规则同步到 06-素材/读/
python3 $SKILL_DIR/scripts/apply.py --tags 玄幻,悬疑   # 写作前翻规则
```

---

## 数据与输出目录

**读归读，写归写，但中间有桥。**

| 位置 | 内容 |
|---|---|
| `skills/novel-study/data/shelf.json` | 书架 + 评级（唯一权威） |
| `skills/novel-study/data/notes/{书名}.md` | 三层阅读笔记 |
| `skills/novel-study/data/rules/{维度}.md` | 可执行写作规则库 |
| `.cache/novel-study/books/{key}/` | 抓下来的正文缓存（可随时删） |
| `06-素材/读/笔记/` | 笔记正式版（`plan.py --sync`） |
| `06-素材/读/规则/` | 规则正式版（`plan.py --sync`） |
| `06-素材/读/选书/` | 选书评估记录 |
| `06-素材/写作/备忘/` | `apply.py` 生成的写作前备忘 |
| `06-素材/文风卡/` | 与 `wjs-distilling-style` 打通的文风指纹 |

为什么不把读写放同一个目录：读要越攒越多、可检索；写要干净、按书按章组织。分开不丢信息，靠 `apply.py` 在写作时把读过的捞出来。

---

## 沉淀的检查线

- 笔记第 1 层**不许出现分析词**；出现就说明你没先读。
- 第 3 层「我能落笔的 3 条」必须是动词开头、能直接照做。
- 规则库每条都有正例/反例/出处，缺一条退回。
- 「语言指纹」要写到能拿去对照自己的稿子；只写「文笔好」不算。
- 「风格指纹」的味道必须是一句具体的话（像什么），不许用「好看/精彩/带感」。
- 锚点原句挑最「像它」的，不是最激烈的；每句标章号。
- 同一维度攒到 5 条规则，回头合并去重一遍。

---

## 持续阅读模式（正文不进主会话）

长篇正文一次读几万字，塞进主会话很快就满。所以改用「子代理读书」：

1. 子代理读 `references/read-cycle.md`，按它读一个单元（默认 10 章）、写笔记、更新进度、提交；
2. 主会话只收一行摘要：`已读完 A-B 章｜笔记文件名｜一句话观察`；
3. 重复调用即可读完全书。

配套文件：
- `data/state/reading-progress.json` — 读到哪了（唯一权威）
- `data/notes/{书名}-前情提要.md` — 设定/人物/线索摘要，子代理不用重读前文
- `references/read-cycle.md` — 子代理的操作手册

好处：主会话上下文只增长「每单元一行」，读 100 万字也不会爆。

## 调度（长期跑起来）

**理解必须本鲸来做，脚本只做采集预热。** 两层：

1. **launchd 预热（无人值守，只抓数据）**
   `scripts/study_daemon.sh`：读 shelf.json → 抓下一批章节 → 写 `data/state/prefetch.log`。
   安装：`bash $SKILL_DIR/scripts/install_study_job.sh --yes`（09:00 每天）。
2. **会话提醒（到了就真读）**
   DSH 定时提醒每天 21:00 唤起本鲸，读 `plan.py --json` 接着干。

> 为什么不 launchd 直接拆解？脚本不会理解文本。抓取可以无人，真读必须 agent。

---

## 登录态与账号

- 主人扫码登录：本鲸用 `browser-cdp` 起 Chrome，主人扫番茄/起点二维码；登录态只在浏览器 profile，**不存明文账号密码**。
- 番茄大部分章节免登录可读；需登录章节返回 `needPay/isChapterLock`，`fetch.py` 明确报告不静默。
- 起点正文走免费源；抓不到降级为「主人手动粘贴章节」。

---

## 合法性与礼貌

- 抓取只用于个人学习分析，不二次分发正文。
- 限速 0.8–1.5s/请求、单次最多 20 章、失败重试 3 次即停。
- 免费源域名会失效，配在 `config.json` 的 `source_priority`，失效就换，不硬编码。

---

## 已验证记录（2026-10-20）

- ✅ 番茄作品页 SSR 元数据可解析（书名/作者/简介/字数/在读/分类）
- ✅ 番茄目录 API `api/reader/directory/detail` 返回全部 itemId
- ✅ 番茄章节页 SSR `reader.chapterData.content` 含完整正文
- ✅ 番茄正文有**字体反爬**：常用字换成私有区码位，`fetch.py` 已内置 362 字映射表解码（实测 0 残留）
- ✅ 天禧真实域名 `www.tianxixsw.com`，可抓正文（单章分页自动拼接）
- ✅ 三层阅读法已用《十日终焉》跑通，产出笔记 + 5 条规则
- ❌ `69shu.com` Cloudflare 403；`baidu.com` 直连触发验证
- ❌ 起点本站正文 curl 返回 202 挑战页（正文走免费源）

## 已知坑

- `window.__INITIAL_STATE__` 用正则截取会被正文里的 `{}` 截断，必须括号平衡扫描。
- **番茄字体反爬**：正文常用字是私有区码位（`\ue4de` 这种），直接读是乱码。换字体会自动重建；本机无 fontTools 时只解约 32% 并在 stderr 警告。
- 番茄作品页 `page.itemIds` 是**倒序**（最新在前），章节顺序一律以目录 API `allItemIds` 为准。
- 番茄正文夹 `<img>` 占位和广告行（「本章未完，请点击下一页继续阅读」），清洗时要滤掉。
- `shelf.json` 是唯一权威，脚本原子写；手改坏了用 `recover`。
- 三层阅读第 1 层最容易写成拆解——写的时候先问自己「这是我作为读者想说的，还是我在分析？」
