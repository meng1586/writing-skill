# 写作学习系统（writing-skill）

> 一套让 AI 通过读书学会写小说的工作流。实验性质，方法论优先。

## 这是什么

不是「AI 代写工具」，是一套**让 AI 自己读书、拆出手法、写作时调用、写完回填**的流程。
核心信念：

> **读过的才敢用，用过的才敢信。**

## 包含什么

| 目录 | 作用 |
|---|---|
| `写作方法论.md` / `写作方法论-v2.md` | 方法论 v1 / 吸收外部评审后的 v2（推荐读 v2） |
| `写作系统-总览.md` | 四个 skill 的协作方式 |
| `skills/novel-study/` | 读书：选书→抓章→三层阅读→笔记→规则 |
| `skills/writing-decision/` | 决策树：这场戏该用什么手法（24 条 if-then） |
| `skills/scene-modules/` | 场景卡：打脸/告别/托孤等 12 个模块的施工图 |
| `skills/writing-loop/` | 闭环：索引、文风体检、回填、读者/挑刺代理 |
| `skills/skill-reflect/` | 元工具：记录 skill 痛点，攒证据改进 |

## 核心方法论（v2）

### 三层分离
观察不能直接升级成规则：
- **原文事实**：作者在这里这样写了（可核对）
- **效果解释**：我推测这样产生了某种效果（待核实）
- **写作假设**：在条件 X 下这样写可能有效（待试验）

### 三层阅读
先当读者（只写感受，禁止分析词），再当拆解者（回答「作者怎么做到的」），最后当作者（能落笔的 3 条动作）。

### 批评与总评
- 每个单元至少一处批评：好书也有烂的地方
- 每本书结束时必须写总评（读完/中断/弃都要），「烂在哪」不能空

### 验证
不靠「数次数」，靠状态机 + 对照试写：
- 状态：待试验 / 在某些条件下有帮助 / 暂不采用 / **看不出区别**
- 方法：同一场景写两版（用/不用该技法），隐藏身份让人比较

### 成本
粗筛用便宜模型，精读用贵模型，纯统计用脚本。按需读：先建索引，写某类场景只读那几章。

## 快速开始

```bash
# 读书
python3 skills/novel-study/scripts/fetch.py book --source fanqie --book-id <id> --from 1 --to 10
python3 skills/novel-study/scripts/plan.py

# 写作前判断
python3 skills/writing-decision/scripts/decide.py --tags 玄幻 --scene "主角第一次杀人"

# 查料
python3 skills/writing-loop/scripts/index.py find --scene 托孤

# 写后体检
python3 skills/writing-loop/scripts/style.py check --file 你的章节.md --target <目标书>

# 回填
python3 skills/writing-loop/scripts/writeback.py add --chapter "第1章" --used D-014 --effect "..." --status 待试验
```

## 状态

- 实验性。方法论已经过一轮外部评审（GPT）并修订。
- 尚未完成「对照试写」验证：不知道用了这套方法，写出来的东西是否真的更好。
- 示例数据来自《十日终焉》（仅少量摘引用于学习分析）。

## 不包含

- 不包含任何平台的账号凭据
- 不包含完整的小说文本
- 不包含私人写作项目

## 许可

待定（默认保留所有权利）。
