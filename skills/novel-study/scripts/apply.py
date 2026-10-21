#!/usr/bin/env python3
"""apply.py — 写作前把读过的规则翻出来

这是「读」和「写」之间的桥：写正文前跑一次，按当前题材从规则库筛出相关规则，
连同文风卡和自检清单生成一份写作备忘，避免「读的时候记了、写的时候想不起来」。

用法：
  python3 scripts/apply.py --tags 玄幻,悬疑
  python3 scripts/apply.py --book 目标作品 --tags 玄幻
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
        # 兼容加粗与「适用题材 / 适用场景」两种写法
        m = re.search(r"-\s*\*{0,2}(?:适用题材|适用场景)\*{0,2}\s*[：:]\s*(.+)", body)
        if m:
            tags = m.group(1).strip()
        status = "待试验"  # 没有状态字段时不能默认「可用」
        m2 = re.search(r"-\s*\*{0,2}(?:状态|效果状态|试用状态)\*{0,2}\s*[：:]\s*(.+)", body)
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


def load_check(check_file):
    """默认清单不存在 → 静默为空（公开版即此状态）。
    但显式 --check-file 指向不存在的文件 → 报错，不能假装加载了。"""
    explicit = bool(check_file)
    path = os.path.abspath(check_file) if explicit else os.path.join(SKILL_DIR, "data", "自检清单.md")
    if not os.path.isfile(path):
        if explicit:
            print(f"apply.py: --check-file 指定的文件不存在：{path}", file=sys.stderr)
            raise SystemExit(2)
        return []
    items = []
    for line in open(path, encoding="utf-8"):
        m = re.match(r"^\s*[-*]\s*(?:\[[ xX]?\]\s*)?(.+?)\s*$", line)
        if m and not line.strip().startswith("#"):
            items.append(m.group(1))
    return items


def build(tags, book, no_self_check=False, check_file=""):
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
            "check": [] if no_self_check else load_check(check_file),
            "generated": date.today().isoformat()}


def render_md(data):
    lines = [f"# 写作备忘 {data['generated']}",
             "",
             f"- 目标作品：{data['book'] or '（未指定）'}",
             f"- 题材标签：{'、'.join(data['tags']) or '（未指定，全部规则）'}",
             ""]
    lines.append("## 一、本次写作要用的规则")
    if not data["rules"]:
        lines.append("")
        lines.append("> 规则库没有匹配项。可以按当前作品目标继续写；想补规则，再去读一本书、拆一条。")
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
    if data["check"]:
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
    ap.add_argument("--rules", default="", help="规则目录（默认 skills/novel-study/data/rules）")
    ap.add_argument("--check-file", default="", help="自检清单文件（默认 data/自检清单.md；显式指定但不存在会报错）")
    ap.add_argument("--no-self-check", action="store_true",
                    help="不输出自检清单（清单来自 data/自检清单.md，默认没有就不输出）")
    args = ap.parse_args()

    global RULES_DIR
    if args.rules:
        RULES_DIR = os.path.abspath(args.rules)
    tags = [t.strip() for t in re.split(r"[,，、\s]+", args.tags) if t.strip()]

    if args.list:
        all_rules = load_all_rules()
        for dim in DIMENSIONS:
            n = len(all_rules.get(dim, []))
            print(f"{dim}: {n} 条")
        return 0

    data = build(tags, args.book, getattr(args, "no_self_check", False), getattr(args, "check_file", ""))

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
