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

DIMENSIONS = ["开篇", "节奏", "人物", "对话", "章末钩子", "语言", "结构"]

SELF_CHECK = [
    "第一句/第一段给了「谁 + 正在失去什么」吗？",
    "这一章的主角目标清楚吗？读者知道他想干嘛吗？",
    "爽点给了吗？间隔是否超过 3 章？",
    "章末钩子是哪一类？和上一章是不是同一个类型？",
    "有没有连续两段以上纯解释、纯设定？砍掉一半还通吗？",
    "对话在推进什么？随便抽三句，能不能删？",
    "有没有 AI 味：等长段落、比喻堆叠、每段总结句、人物一个腔调？",
    "用的是什么「味道」？和文风卡对得上吗？",
]


def parse_rules(path):
    """把一个维度文件拆成规则列表。"""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    parts = re.split(r"(?m)^#{2,3} (R-[^\n]+)$", text)
    rules = []
    for i in range(1, len(parts) - 1, 2):
        title = parts[i].strip()
        body = parts[i + 1].strip()
        tags = ""
        m = re.search(r"- 适用题材：(.+)", body)
        if m:
            tags = m.group(1).strip()
        status = "可用"
        m2 = re.search(r"- 状态：(.+)", body)
        if m2:
            status = m2.group(1).strip()
        rules.append({"title": title, "body": body, "tags": tags, "status": status})
    return rules


def load_all_rules():
    out = {}
    for dim in DIMENSIONS:
        path = os.path.join(RULES_DIR, f"{dim}.md")
        if os.path.isfile(path):
            out[dim] = parse_rules(path)
    return out


def is_match(rule_tags, want):
    """want 任一出现在规则适用题材里即匹配；通用也算匹配。"""
    if not want:
        return True
    if not rule_tags:
        return False
    if "通用" in rule_tags:
        # 「通用，除 X」里若 want 命中排除项，则不匹配
        m = re.search(r"除(.+?)(?:外|$)", rule_tags)
        if m and any(w in m.group(1) for w in want):
            return False
        return True
    return any(w in rule_tags for w in want)


def build(tags, book):
    all_rules = load_all_rules()
    picked = []
    for dim in DIMENSIONS:
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
    lines.append("## 一、本次写作要用的规则")
    if not data["rules"]:
        lines.append("")
        lines.append("> 规则库没有匹配项。先去读一本书、拆一条规则，别空手写。")
    for dim, r in data["rules"]:
        lines.append("")
        lines.append(f"### [{dim}] {r['title']}")
        lines.append("")
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
        all_rules = load_all_rules()
        for dim in DIMENSIONS:
            n = len(all_rules.get(dim, []))
            print(f"{dim}: {n} 条")
        return 0

    data = build(tags, args.book)

    if args.json:
        out = {
            "generated": data["generated"],
            "book": data["book"],
            "tags": data["tags"],
            "rules": [{"dimension": d, "title": r["title"], "tags": r["tags"]}
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
