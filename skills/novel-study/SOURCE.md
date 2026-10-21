# SOURCE — novel-study 从哪来，为什么自己写

## 1. 先搜再做（工作区规则）

2026-10-20 用 `find-skill` 本地目录（642 条，14 个来源）按关键词
`reading / book / novel / study / learning / 拆书 / 读书 / 小说 / web novel / scrape / crawler`
检索，命中 18 条，逐条评估后没有可直接安装的候选：

| 候选 | 来源 | 为什么不用 |
|---|---|---|
| `teach` | mxyhi | 通用教学工作区（missions / lessons / learning records），不含网文平台采集，也没有拆解网文的维度 |
| `writing-guidelines` | vercel-labs | 面向文档/技术写作规范，不是中文网文 |
| `notebooklm` / `kaggle-skill` / `x-twitter-scraper` 等 | BehiSecc | 领域完全不相关 |
| Claude Cookbooks / move-code-quality-skill 等 | travisvn 等 | 不相关 |

GitHub 侧没有找到「自动找中文网文 + 拆解 + 沉淀写作规则」的现成技能；`oh-story`
（zenstory-ai/oh-story-claudecode）已经部署在本项目，覆盖了**扫榜**与**拆文**，
但它解决的是「写这本书」而不是「长期、跨书地读书学习」。

## 2. 结论：自建调度层，复用已有能力

本技能自身不重复造轮子，定位是**长期读书学习的调度与沉淀层**：

- 采集：复用 `story-long-scan/scripts/qidian-rank-scraper.js`（起点扫榜找书）；
  番茄官方 SSR 与 tianxi 免费源的抓取在本技能 `scripts/fetch.py` 内实现（已实测）。
- 拆解方法：沿用 `story-long-analyze` 的拆解维度思路，但产出物是本技能的读书笔记与规则库。
- 去 AI 味对照：引用 `story-deslop` 的禁用词/句式清单，写进笔记「语言与描写」维度。
- 文风沉淀：与 `06-素材/文风卡/` 打通（`wjs-distilling-style` 的无意识文风指纹）。

这些外部 skill 是原工作区的可选协作能力，本仓库不附带它们。缺失时使用本模块模板和已提供文本，不调用不存在的命令。脚本路径基于当前克隆目录，不指向原作者工作区。

## 规则来源与证据状态

旧规则中的章号与摘句用于定位原文；它们不能单独证明阅读效果，也不能证明移用于另一背景仍有效。新候选卡分原文事实、效果解释（推测）、写作假设（待试验）。旧「可用」标签由调用器显示为待试验并保留原标签，不自动验证或改写旧数据。

情绪方法调整保留七条旧编号及来源为候选案例；本次未重读其所引章节，相关线索标待核对。方法更新只向未写单元和后续写作生效，既有笔记及正式副本不迁移、不重写。

## 3. 上游与许可

- 本技能为**本项目原创**，无上游仓库，无外部许可证约束。
- 复用部分：`story-long-scan`（oh-story，MIT，已由本项目部署）只以命令方式调用，不复制其代码。
- 数据来源：番茄小说官方页面 SSR、公开免费小说站；抓取遵守限速与 robots 礼貌
  原则，仅用于个人学习分析，不二次分发正文。

## 4. 变更记录

- 2026-10-20：初版。Lead 定契约（CONTRACT.md）、collector 实现 fetch.py、
  curator 实现 shelf.py 与模板，Lead 实现 plan.py、文档与调度。
