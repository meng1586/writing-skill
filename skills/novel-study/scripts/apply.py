#!/usr/bin/env python3
"""apply.py — 写作前把读过的规则翻出来

这是「读」和「写」之间的桥：写正文前跑一次，按当前题材从规则库筛出相关规则，
连同文风卡和自检清单生成一份写作备忘，避免「读的时候记了、写的时候想不起来」。

用法：
  python3 scripts/apply.py --tags 玄幻,悬疑
  python3 scripts/apply.py --book 命烛 --tags 玄幻
  python3 scripts/apply.py --tags 玄幻 --json
  python3 scripts/apply.py --list          # 只看规则库现状

产物：06-素材/写作/备忘/{日期}-{标签}.md，同时打印摘要。
只依赖标准库。
"""
import argparse
import glob
import json
import os
import re
import sys
from datetime import date

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = os.path.dirname(os.path.dirname(SKILL_DIR))
RULES_DIR = os.path.join(SKILL_DIR, "data", "rules")
STYLE_DIR = os.path.join(PROJECT_DIR, "06-素材", "文风卡")
OUT_DIR = os.path.join(PROJECT_DIR, "06-素材", "写作", "备忘")

DIMENSIONS = ["开篇", "节奏", "人物", "对话", "章末钩子", "语言", "结构", "情绪"]

SELF_CHECK = [
    "本场想表达什么？现有文本真正缺的是哪一条依据或选择？",
    "这一章的主角目标清楚吗？读者知道他想干嘛吗？",
    "人物的选择、关系或读者等待的事情，发生了什么变化？",
    "章末是否适合留下等待、回应旧问题，或让本场自然结束？",
    "说明是否重复了已经清楚的信息？删掉后是否损失必要理解？",
    "对话在推进什么？随便抽三句，能不能删？",
    "对话是否符合人物，比喻是否准确，旁白是否在重复动作？",
    "用的是什么「味道」？和文风卡对得上吗？",
]


def parse_rules(path):
    """兼容旧 R-规则和新 C-候选卡；保留状态、出处和条件。"""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    heading = r"^#{2,3}[ \t]+([RC]-\S+[ \t]+\S[^\n]*)$"
    for lineno, line in enumerate(text.splitlines(), 1):
        if re.match(r"^(?:#{1,6}[ \t]+)?[RC]-\S+", line) and not re.match(heading, line):
            raise ValueError(f"{path}:{lineno}: 候选卡请使用 '## C-编号 标题' 或 '## R-维度-编号 标题'")
    parts = re.split("(?m)" + heading, text)
    rules = []
    for i in range(1, len(parts) - 1, 2):
        title = parts[i].strip()
        body = parts[i + 1].strip()
        tags = ""
        m = re.search(r"- 适用题材：(.+)", body)
        if m:
            tags = m.group(1).strip()
        status = "待试验"
        m2 = re.search(r"- 状态：(.+)", body)
        if m2:
            status = m2.group(1).strip()
        original_status = status
        # 旧的「可用」只表示已经入库，没有独立效果验证。
        if status in ("可用", "待验证", "candidate", "derived"):
            status = "待试验"
        def field(name, default=""):
            found = re.search(r"(?m)^- " + re.escape(name) + r"：(.+)$", body)
            return found.group(1).strip() if found else default
        rules.append({"title": title, "body": body, "tags": tags, "status": status,
                      "original_status": original_status,
                      "kind": field("类型", "候选技法"),
                      "source": field("出处", field("原文事实")),
                      "conditions": field("适用条件", field("写作假设")),
                      "source_path": os.path.relpath(path, PROJECT_DIR)})
    if not rules and re.search(r"(?m)^(?:#{1,6}[ \t]+)?[RC]-\S+", text):
        raise ValueError(f"{path}: 候选卡标题未解析，请使用 '## C-编号 标题' 或 '## R-维度-编号 标题'")
    return rules


def load_all_rules():
    out = {}
    for path in sorted(glob.glob(os.path.join(RULES_DIR, "*.md"))):
        if os.path.basename(path) != "README.md":
            out[os.path.splitext(os.path.basename(path))[0]] = parse_rules(path)
    return out


def is_match(rule_tags, want):
    """want 任一出现在规则适用题材里即匹配；通用也算匹配。"""
    if not want:
        return True
    if not rule_tags:
        return False
    if "通用" in rule_tags or "全题材" in rule_tags:
        # 「通用，除 X」里若 want 命中排除项，则不匹配
        m = re.search(r"除(.+?)(?:外|$)", rule_tags)
        if m and any(w in m.group(1) for w in want):
            return False
        return True
    return any(w in rule_tags for w in want)


def build(tags, book):
    all_rules = load_all_rules()
    picked = []
    for dim in sorted(all_rules, key=lambda d: (DIMENSIONS.index(d) if d in DIMENSIONS else len(DIMENSIONS), d)):
        for r in all_rules.get(dim, []):
            if r["status"] in ("已淘汰", "暂不采用", "dropped", "rejected", "retired"):
                continue
            if is_match(r["tags"], tags):
                picked.append((dim, r))
    cards = []
    if os.path.isdir(STYLE_DIR):
        cards = sorted(glob.glob(os.path.join(STYLE_DIR, "*.md")))
        cards = [c for c in cards if os.path.basename(c) != "README.md"]
    return {"tags": tags, "book": book, "rules": picked, "cards": cards,
            "check": SELF_CHECK, "generated": date.today().isoformat()}


def render_md(data):
    lines = [f"# 写作备忘 {data['generated']}",
             "",
             f"- 目标作品：{data['book'] or '（未指定）'}",
             f"- 题材标签：{'、'.join(data['tags']) or '（未指定，全部规则）'}",
             ""]
    lines.append("## 一、按本场条件选择的候选技法与案例")
    lines.append("")
    lines.append("> 题材匹配只用于查找，不代表本场适用或效果已验证。先判断表达问题，再选择一个有依据的尝试；没有缺口就不用卡。")
    if not data["rules"]:
        lines.append("")
        lines.append("> 没有匹配的候选卡；可以依据当前场景直接写，不必为用卡补卡。")
    for dim, r in data["rules"]:
        lines.append("")
        lines.append(f"### [{dim}] {r['title']}")
        lines.append("")
        lines.append(f"- 调用状态：{r['status']}；类型：{r['kind']}")
        if r["original_status"] != r["status"]:
            lines.append(f"- 旧入库标签：{r['original_status']}（不表示效果已验证）")
        lines.append(r["body"])
    lines.append("")
    lines.append("## 二、文风卡")
    if data["cards"]:
        for c in data["cards"]:
            lines.append(f"- `{os.path.relpath(c, PROJECT_DIR)}`")
    else:
        lines.append("- （还没有文风卡，用 `wjs-distilling-style` 蒸一张）")
    lines.append("")
    lines.append("## 三、写作前自检")
    for q in data["check"]:
        lines.append(f"- [ ] {q}")
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="写作前把读过的规则翻出来")
    ap.add_argument("--tags", default="", help="逗号分隔的题材标签，如 玄幻,悬疑")
    ap.add_argument("--book", default="", help="正在写的书名")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--list", action="store_true", help="只看规则库现状")
    ap.add_argument("--no-write", action="store_true", help="只打印不落盘")
    args = ap.parse_args()

    tags = [t.strip() for t in re.split(r"[,，、\s]+", args.tags) if t.strip()]

    if args.list:
        try:
            all_rules = load_all_rules()
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        for dim in all_rules:
            n = len(all_rules.get(dim, []))
            print(f"{dim}: {n} 条")
        return 0

    try:
        data = build(tags, args.book)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.json:
        out = {
            "generated": data["generated"],
            "book": data["book"],
            "tags": data["tags"],
            "rules": [{"dimension": d, **r}
                      for d, r in data["rules"]],
            "cards": [os.path.relpath(c, PROJECT_DIR) for c in data["cards"]],
            "check": data["check"],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    md = render_md(data)
    print(md)
    if not args.no_write:
        os.makedirs(OUT_DIR, exist_ok=True)
        slug = "-".join(tags) if tags else "全部"
        path = os.path.join(OUT_DIR, f"{date.today().isoformat()}-{slug}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"\n（已写入 {os.path.relpath(path, PROJECT_DIR)}）", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
