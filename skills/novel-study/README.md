# novel-study — 让本鲸自己读书、学着写好小说

一个长期跑的小系统：**挑好书 → 抓正文 → 三层真读 → 蒸馏规则 → 写作前自动调用**。
不是扫榜工具，也不是代写工具；它只让本鲸越读越会写。

## 三条铁律

1. **差书不学**：选书有门槛，试读有止损，读完前 3 章必须给评级和 keep/watch/drop。
2. **先当读者，再当拆解者**：笔记第一层只写感受，不许用「节奏/钩子/人设」这些分析词。
3. **读过必须能进写作**：写正文前跑 `apply.py`，把相关规则、文风卡、自检清单捞出来。

## 30 秒上手

```bash
# 在当前克隆仓库根目录执行

# 1) 今天读哪本、读哪几章
python3 skills/novel-study/scripts/plan.py
# 交给单元阅读代理时明确书目与本次章数
python3 skills/novel-study/scripts/plan.py --book-key fanqie-7143038691944959011 --chapters 10 --json

# 2) 抓正文
python3 skills/novel-study/scripts/fetch.py book --source fanqie \
  --book-id 7143038691944959011 --from 4 --to 6

# 3) 读完按三层模板写笔记，然后给这本书判级
python3 skills/novel-study/scripts/shelf.py judge --key fanqie-7143038691944959011 \
  --quality 5 --verdict keep --verdict-reason "数字矛盾开局可偷"

# 4) 写正文前，把读过的规则翻出来
python3 skills/novel-study/scripts/apply.py --tags 玄幻,悬疑 --book 命烛
```

## 目录

| 位置 | 是什么 |
|---|---|
| `SKILL.md` | 完整操作手册（三层阅读法、选书、命令） |
| `references/选书标准.md` | 什么样的书值得学、什么时候止损 |
| `references/note-template.md` | 三层阅读笔记模板 |
| `references/rules-guide.md` | 规则库格式 |
| `references/卷纲模板.md` | 完整冲突/卷/全书的承诺、选择与代价、局面变化、回应与承接 |
| `data/rules/情绪.md` | 表达问题→条件选择→候选案例，按背景选办法 |
| `scripts/fetch.py` | 找书元数据、抓章正文 |
| `scripts/shelf.py` | 书架、评级、进度、统计 |
| `scripts/plan.py` | 今日计划、同步到 `06-素材/读/` |
| `scripts/apply.py` | 写作前把规则翻出来，生成备忘 |
| `scripts/study_daemon.sh` | 可选：launchd 定时预热抓章 |
| `06-素材/读/笔记/` | 笔记正式版 |
| `06-素材/读/规则/` | 规则正式版 |
| `06-素材/写作/备忘/` | 写作前备忘 |

**读归读，写归写，但中间有桥**：读的产物按题材攒在 `06-素材/读/`，写作时用 `apply.py` 按题材筛出来，落到 `06-素材/写作/备忘/`。不靠记性，靠命令。

`apply.py` 同时支持 `## R-维度-编号` 与 `## C-编号` 候选卡；输出保留状态、出处、条件和正文。旧「可用」标签仅表示入库，调用时按「待试验」处理。命中题材不证明本场适用，没有匹配也可继续写。

新方法只向未写单元及后续写作生效，不回填旧笔记及正式副本。实际读书进度来自按 `book_key` 选择的书架条目；仓库附带的历史单书 `reading-progress.json` 不作为新书的当前进度。示例已完成时应另行登记要读的书，不重置旧样本。

## 每天怎么跑

- **09:00**（可选）`study_daemon.sh` 预热：只抓章节，不写笔记。
- **21:00** 本鲸收到会话提醒，读 `plan.py --json`，三层阅读 → 写笔记 → 记进度。

脚本不会理解文本，真读必须本鲸来做——这正是这套设计的分工。

## 注意

- 登录态靠浏览器扫码，本技能不存明文账号密码。
- 抓取只用于个人学习，限速、限量、不二次分发。
- 免费源域名会失效，改 `config.json` 的 `source_priority`，别硬编码。
