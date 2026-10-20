#!/usr/bin/env python3
"""review.py — 一本书结束时的总评流程

每本书不管读完、中断、弃，都要写总评。这个脚本负责：
  new    从模板生成总评骨架（填好书名、进度）
  finish 标记结束：更新 shelf.json 的 status + 评分 + 结论
  list   列出已有总评

用法：
  python3 scripts/review.py new --key fanqie-7143038691944959011
  python3 scripts/review.py finish --key fanqie-7143038691944959011 \\
      --reason 读完 --rating 5 --verdict keep --chapters 1496
  python3 scripts/review.py list

只依赖标准库。
"""
import argparse
import json
import os
import sys
from datetime import date

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = os.path.dirname(os.path.dirname(SKILL_DIR))
DATA = os.path.join(SKILL_DIR, "data")
SHELF = os.path.join(DATA, "shelf.json")
NOTES = os.path.join(DATA, "notes")
TEMPLATE = os.path.join(SKILL_DIR, "references", "book-review-template.md")

REASONS = ("读完", "中断", "弃")


def load_shelf():
    with open(SHELF, encoding="utf-8") as f:
        return json.load(f)


def save_shelf(shelf):
    tmp = SHELF + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(shelf, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SHELF)
    # 备份
    try:
        with open(SHELF + ".bak", "w", encoding="utf-8") as f:
            json.dump(shelf, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def find_book(shelf, key):
    for b in shelf.get("books", []):
        if b.get("key") == key:
            return b
    return None


def cmd_new(args):
    shelf = load_shelf()
    book = find_book(shelf, args.key)
    if not book:
        print(f"错误：书架里没有 {args.key}", file=sys.stderr)
        return 2
    name = book.get("name") or args.key
    os.makedirs(NOTES, exist_ok=True)
    path = os.path.join(NOTES, f"{name}-总评.md")
    if os.path.exists(path) and not args.force:
        print(f"已存在：{path}（加 --force 覆盖）")
        return 0
    try:
        with open(TEMPLATE, encoding="utf-8") as f:
            tpl = f.read()
    except OSError:
        print("错误：找不到总评模板", file=sys.stderr)
        return 2
    done = book.get("chapters_done", 0)
    total = book.get("chapter_total", 0)
    tpl = tpl.replace("# 《书名》总评", f"# 《{name}》总评")
    tpl = tpl.replace("- 总字数 / 已读章数：", f"- 总字数 / 已读章数：{done} / {total}")
    tpl = tpl.replace("## 0. 基本信息", f"## 0. 基本信息\n\n> 生成于 {date.today().isoformat()}")
    with open(path, "w", encoding="utf-8") as f:
        f.write(tpl)
    print(f"已生成总评骨架：{path}")
    print("下一步：把 2/3 节（好在哪、烂在哪）填满，烂在哪不能空。")
    return 0


def cmd_finish(args):
    shelf = load_shelf()
    book = find_book(shelf, args.key)
    if not book:
        print(f"错误：书架里没有 {args.key}", file=sys.stderr)
        return 2
    if args.reason not in REASONS:
        print(f"错误：--reason 只能是 {'/'.join(REASONS)}", file=sys.stderr)
        return 2
    if args.chapters is not None:
        book["chapters_done"] = int(args.chapters)
    if args.rating is not None:
        book["quality"] = int(args.rating)
    if args.verdict:
        book["verdict"] = args.verdict
    if args.note:
        book["verdict_reason"] = args.note
    book["status"] = "done" if args.reason == "读完" else "dropped"
    book["finished"] = date.today().isoformat()
    book["finish_reason"] = args.reason
    save_shelf(shelf)
    print(f"已结束《{book.get('name')}》：{args.reason}｜{book.get('chapters_done')} 章｜"
          f"{'★' * (book.get('quality') or 0)}{'☆' * (5 - (book.get('quality') or 0))} {book.get('verdict')}")
    print("记得写总评：python3 scripts/review.py new --key " + args.key)
    return 0


def cmd_list(args):
    shelf = load_shelf()
    rows = []
    for b in shelf.get("books", []):
        p = os.path.join(NOTES, f"{b.get('name')}-总评.md")
        rows.append((b.get("name"), b.get("finish_reason", "-"),
                     b.get("status"), os.path.exists(p)))
    print(f"{'书名':<14}{'结束原因':<8}{'状态':<8}总评")
    for name, reason, status, has in rows:
        print(f"{name:<14}{reason:<8}{status:<8}{'✓' if has else '✗'}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="书籍总评流程")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pn = sub.add_parser("new", help="生成总评骨架")
    pn.add_argument("--key", required=True)
    pn.add_argument("--force", action="store_true")
    pn.set_defaults(func=cmd_new)

    pf = sub.add_parser("finish", help="标记这本书结束")
    pf.add_argument("--key", required=True)
    pf.add_argument("--reason", required=True, choices=REASONS)
    pf.add_argument("--rating", type=int, help="1-5")
    pf.add_argument("--verdict", choices=("keep", "watch", "drop"))
    pf.add_argument("--chapters", type=int, help="实际读到的章数")
    pf.add_argument("--note", help="一句话结束理由")
    pf.set_defaults(func=cmd_finish)

    pl = sub.add_parser("list", help="列出总评状态")
    pl.set_defaults(func=cmd_list)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
