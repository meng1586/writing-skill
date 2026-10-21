# 写作学习系统（writing-skill）

从阅读中提出候选写法、按具体场景试用、再记录反馈的实验性工作流。能生成笔记和检索案例，不等于已经证明写作效果更好。

先读[系统总览](写作系统-总览.md)，方法依据见[写作方法论 v2](写作方法论-v2.md)。[v1](写作方法论.md)仅作历史记录。

## 五个部分

| 目录 | 职责 |
|---|---|
| `skills/novel-study/` | 选书、采集、阅读、新笔记和候选办法 |
| `skills/writing-decision/` | 按事件、题材和位置检索，再结合目标、人物和视角选择 |
| `skills/scene-modules/` | 写前、写中、写后按需查路径与风险 |
| `skills/writing-loop/` | 案例索引、描述性文风统计、分来源评审和反馈 |
| `skills/skill-reflect/` | 记录实际使用的问题与改进证据 |

在仓库根目录工作并保留上述同级布局。具体运行要求和采集限制见 [novel-study](skills/novel-study/SKILL.md)。安装不会自动采集、安装定时器或写小说。

## 三项方法入口

- [情绪方法](skills/novel-study/data/rules/情绪.md)：表达问题 → 背景条件下的选择 → 技法案例。建议明确且可调整，不按情绪名称绑定固定写法。
- [卷纲模板](skills/novel-study/references/卷纲模板.md)：等待／选择与代价／局面变化／本卷回应与下卷承接。倒计时和通用节拍只是可选工具。
- [场景卡调用](skills/scene-modules/SKILL.md)：写前缺方案、写中卡住、写后有疑问时各取所需；未采用某个五步写法不构成写坏。

更新只对未写单元向后生效。已完成笔记和正式副本不重写、不重置进度。案例曾出现过与照用有效是两种结论。

## 证据边界

原文事实、效果解释和写作假设分开；作者自检、模型模拟和真人反馈分开。对照应关联稿件版本、反馈来源与适用条件，状态不由“好/崩”的票数决定。

检索分数是关键词相关性，文风数值只描述与样本的差异，都不直接决定质量。没有匹配材料时可以继续写并注明未测，不为凑规则改人物或剧情。

## 快速试用

```bash
python3 -B skills/novel-study/scripts/plan.py --json
python3 -B skills/writing-decision/scripts/decide.py --tags 玄幻 --scene "主角第一次杀人"
python3 -B skills/scene-modules/scripts/query.py --type 告别
python3 -B skills/writing-loop/scripts/index.py find --scene 托孤
python3 -B skills/writing-loop/scripts/writeback.py report
```

样本索引与候选数据来自已有阅读记录；完整参考小说、私人笔记、账号凭据和私人写作项目不在仓库内。不能因查到索引就声称已读原文。

## 验证

```bash
python3 -B -m unittest discover -s tests -v
```

回归检查覆盖状态、证据、组合排除和跨模块格式等可观察行为，不验证真实读者情绪、作品质量或平台追读。方法仍待实际写作和真人反馈检验。

## 许可

待定（默认保留所有权利）。
