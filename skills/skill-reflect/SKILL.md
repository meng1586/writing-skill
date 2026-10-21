---
name: skill-reflect
version: 0.1.0-public
description: "记录工具或流程的实际问题，汇总证据和受影响文件，帮助决定下一项最小改动。触发：记录skill问题、看看哪里不好用、记一笔、流程改进。"
metadata: {"project":"写作学习"}
---

# skill-reflect：记录使用问题

记录具体卡点 → 汇总相关证据 → 选择最小改动 → 核对结果。

报告用于排查和排序，不自动证明设计有问题，也不会自行修改技能。高影响且可复现的单个错误可以立即处理；多次相似反馈也可能来自同一原因，不能只按次数下结论。

## 命令

在本包根目录执行：

```bash
python3 skills/skill-reflect/scripts/log.py   --skill novel-study --stage 查询   --issue "给定场景未返回预期条目" --suggestion "核对场景词和条目条件" --impact medium --dry-run

python3 skills/skill-reflect/scripts/report.py
python3 skills/skill-reflect/scripts/report.py --skill novel-study --json
```

去掉 `log.py` 的 `--dry-run` 会追加本地记录。报告的 `--threshold` 是可调整的汇总提示阈值，不是“达到次数就必须改”的规则。

## 记录什么

- 在哪个环节、用什么输入、预期发生什么。
- 实际结果与可复现步骤。
- 对写作或阅读造成的具体影响。
- 受影响的文件与一个尽量小的修改建议。

记录位于本模块 `data/usage/`，按使用生成。日志和报告可以包含本地项目细节，不自动纳入公开发布。

## 怎样决定修改

先区分数据缺失、输入不适用、工具错误和效果判断。只修有证据支持的问题；修改后复查该问题及受影响的调用，不把通过的历史检查反复铺开。

对写作候选效果的判断仍需独立的试用条件和反馈，不能因为工具用起来顺手就称写法有效。
