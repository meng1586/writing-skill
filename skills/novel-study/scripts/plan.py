#!/usr/bin/env python3
"""plan.py — novel-study 今日学习计划与同步

用法：
  python3 scripts/plan.py            # 人读清单
  python3 scripts/plan.py --json     # 给 agent 的结构化清单
  python3 scripts/plan.py --sync     # 把 data/notes、data/rules 同步到 06-素材/

契约见同目录 CONTRACT.md。只依赖标准库。
"""
import argparse
import json
import os
import re
import shutil
import sys
from datetime import date, datetime

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = os.path.dirname(os.path.dirname(SKILL_DIR))  # skills/novel-study -> 写点小说
DATA_DIR = os.path.join(SKILL_DIR, "data")
CACHE_DIR = os.path.join(PROJECT_DIR, ".cache", "novel-study", "books")
SHELF = os.path.join(DATA_DIR, "shelf.json")
CONFIG = os.path.join(SKILL_DIR, "config.json")
NOTES_DIR = os.path.join(DATA_DIR, "notes")
RULES_DIR = os.path.join(DATA_DIR, "rules")

RULE_DIMENSIONS = ["开篇", "节奏", "人物", "对话", "章末钩子", "语言", "结构", "情绪"]
DEFAULT_CONFIG = {"daily_chapters": 3, "time_budget_min": 40, "note_sync_dirs": {
    "notes": "06-素材/读/笔记", "rules": "06-素材/读/规则"}}
RULE_GAP_THRESHOLD = 3  # 少于 3 条规则的维度算缺口


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        print(f"[warn] {path} 解析失败，按空数据处理", file=sys.stderr)
        return default


def load_shelf():
    shelf = load_json(SHELF, None)
    if not isinstance(shelf, dict):
        return {"version": 1, "settings": {}, "books": []}
    shelf.setdefault("books", [])
    return shelf


def downloaded_chapters(book):
    """返回已下载的章节号集合。local_dir 支持相对项目根或绝对路径。"""
    local = book.get("local_dir") or os.path.join(CACHE_DIR, book["key"])
    if not os.path.isabs(local):
        local = os.path.join(PROJECT_DIR, local)
    ch_dir = os.path.join(local, "chapters")
    if not os.path.isdir(ch_dir):
        return set()
    nums = set()
    for name in os.listdir(ch_dir):
        m = re.match(r"^(\d+)\.txt$", name)
        if m:
            nums.add(int(m.group(1)))
    return nums


def build_plan(book_key=None, chapters=None):
    cfg = {**DEFAULT_CONFIG, **load_json(CONFIG, {})}
    daily = int(chapters if chapters is not None else cfg.get("daily_chapters", 3) or 3)
    if not 1 <= daily <= int(cfg.get("max_chapters_per_run", 20)):
        raise ValueError("本次章数必须在 1 与 max_chapters_per_run 之间")
    shelf = load_shelf()
    books = shelf.get("books", [])
    today = date.today().isoformat()

    plan = {
        "date": today,
        "shelf_empty": not books,
        "daily_chapters": daily,
        "time_budget_min": cfg.get("time_budget_min", 40),
        "today": [],
        "notes_todo": [],
        "rules_gap": {},
        "shelf_summary": {},
        "selected_book": None,
    }

    if book_key:
        selected = next((b for b in books if b.get("key") == book_key), None)
        if selected is None:
            raise ValueError(f"书架里没有 {book_key}；先用 shelf.py add 登记")
        if selected.get("verdict") == "drop" or selected.get("status") == "dropped":
            raise ValueError(f"{book_key} 已停止阅读；请先确认是否继续")
        plan["selected_book"] = {k: selected.get(k) for k in (
            "key", "name", "source", "book_id", "status", "chapters_done", "chapter_total")}
    if not books:
        plan["shelf_summary"] = {"total": 0}
        return plan

    # 今日书目：reading 优先，按 last_studied 最早 / 进度比最低
    # 止损的书（verdict=drop）不再推
    def incomplete(book):
        total = int(book.get("chapter_total", 0) or 0)
        return not total or int(book.get("chapters_done", 0) or 0) < total
    eligible = [b for b in books if b.get("verdict") != "drop" and incomplete(b)]
    if book_key:
        reading = [selected] if selected.get("status") in ("reading", "unread") and incomplete(selected) else []
    else:
        reading = [b for b in eligible if b.get("status") == "reading"]
        if not reading:
            reading = [b for b in eligible if b.get("status") == "unread"]
    reading.sort(key=lambda b: (
        b.get("last_studied") or "0000-00-00",
        (b.get("chapters_done", 0) or 0) /
        max(b.get("chapter_total", 1) or 1, 1),
    ))
    for book in reading[:2]:
        done = int(book.get("chapters_done", 0) or 0)
        total = int(book.get("chapter_total", 0) or 0)
        start = done + 1
        end = start + daily - 1
        if total > 0:
            end = min(end, total)
        have = downloaded_chapters(book)
        need = [n for n in range(start, end + 1) if n not in have]
        plan["today"].append({
            "key": book.get("key"),
            "book_key": book.get("key"),
            "source": book.get("source"),
            "book_id": book.get("book_id"),
            "name": book.get("name"),
            "last_read_chapter": done,
            "chapter_total": total,
            "from": start,
            "to": end,
            "already_downloaded": [n for n in range(start, end + 1) if n in have],
            "need_fetch": need,
            "local_dir": book.get("local_dir") or os.path.join(CACHE_DIR, book.get("key", "")),
        })

    # 待补笔记：reading 的书没有笔记文件
    for book in books:
        if book.get("status") not in ("reading", "done") or book.get("verdict") == "drop":
            continue
        book_dir = os.path.join(NOTES_DIR, book.get("name") or "")
        has_note = os.path.isdir(book_dir) and any(
            f.endswith(".md") and f not in ("总评.md", "前情提要.md", "README.md")
            for f in os.listdir(book_dir))
        if not has_note:
            plan["notes_todo"].append(book.get("name"))

    # 规则库缺口
    for dim in RULE_DIMENSIONS:
        path = os.path.join(RULES_DIR, f"{dim}.md")
        count = 0
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                text = f.read()
            # 每条规则以 "## " 或 "### " 或 "- **规则" 开头
            count = len(re.findall(r"^#{2,3}[ \t]+(?:R|C)-", text, re.M))
        if count < RULE_GAP_THRESHOLD:
            plan["rules_gap"][dim] = count

    plan["shelf_summary"] = {
        "total": len(books),
        "reading": sum(1 for b in books if b.get("status") == "reading"),
        "done": sum(1 for b in books if b.get("status") == "done"),
        "dropped": sum(1 for b in books if b.get("status") == "dropped"),
    }
    return plan


def sync_outputs():
    """data/notes、data/rules -> 06-素材/。返回同步的文件列表。"""
    cfg = {**DEFAULT_CONFIG, **load_json(CONFIG, {})}
    dirs = cfg.get("note_sync_dirs", {})
    pairs = [
        (NOTES_DIR, os.path.join(PROJECT_DIR, dirs.get("notes", "06-素材/读/笔记"))),
        (RULES_DIR, os.path.join(PROJECT_DIR, dirs.get("rules", "06-素材/读/规则"))),
    ]
    synced = []
    pending = []
    for src, dst in pairs:
        if not os.path.isdir(src):
            continue
        for root, _dirs, files in os.walk(src):
            rel = os.path.relpath(root, src)
            for name in sorted(files):
                if not name.endswith(".md"):
                    continue
                s = os.path.join(root, name)
                d = os.path.join(dst, rel, name) if rel != "." else os.path.join(dst, name)
                # 已完成的正式笔记不可被同步重写；前情提要是持续更新的当前摘要。
                if src == NOTES_DIR and name != "前情提要.md" and os.path.isfile(d):
                    with open(s, "rb") as source_file, open(d, "rb") as target_file:
                        if source_file.read() != target_file.read():
                            raise ValueError(f"正式笔记已存在且内容不同，未覆盖：{d}")
                    continue
                if not os.path.isfile(d) or os.path.getmtime(s) > os.path.getmtime(d) or \
                        os.path.getsize(s) != os.path.getsize(d):
                    pending.append((s, d))
    # 先完成冲突检查，再进行复制，避免失败时只发布半套材料。
    for s, d in pending:
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copy2(s, d)
        synced.append(os.path.relpath(d, PROJECT_DIR))
    return synced


def print_human(plan):
    print(f"📚 novel-study 今日计划  {plan['date']}")
    print(f"预算 {plan['time_budget_min']} 分钟 · 每天 {plan['daily_chapters']} 章\n")
    if plan["shelf_empty"]:
        print("书架是空的。先加一本：")
        print("  python3 skills/novel-study/scripts/shelf.py add --key ... --name ... --source ... --book-id ...")
        return
    if not plan["today"]:
        print("没有在读/未读的书。")
    for item in plan["today"]:
        print(f"📖 《{item['name']}》 第 {item['from']}–{item['to']} 章")
        if item["need_fetch"]:
            print(f"   待抓：{format_ranges(item['need_fetch'])}")
        else:
            print("   正文已就绪，直接拆解")
        print(f"   目录：{item['local_dir']}")
    if plan["notes_todo"]:
        print(f"\n📝 待补笔记：{'、'.join(plan['notes_todo'])}")
        print("   模板：skills/novel-study/references/note-template.md")
    if plan["rules_gap"]:
        gaps = "、".join(f"{k}({v})" for k, v in plan["rules_gap"].items())
        print(f"\n📐 规则库缺口（<{RULE_GAP_THRESHOLD} 条）：{gaps}")
    s = plan["shelf_summary"]
    print(f"\n书架：共 {s.get('total', 0)} 本 · 在读 {s.get('reading', 0)} · 读完 {s.get('done', 0)} · 弃 {s.get('dropped', 0)}")
    print("\n下一步：fetch.py 抓章 → 读正文 → 按模板写笔记 → shelf.py log 记进度 → plan.py --sync")


def format_ranges(nums):
    nums = sorted(set(nums))
    if not nums:
        return "无"
    parts, start, prev = [], nums[0], nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
        else:
            parts.append(f"{start}" if start == prev else f"{start}-{prev}")
            start = prev = n
    parts.append(f"{start}" if start == prev else f"{start}-{prev}")
    return ",".join(parts)


def main():
    ap = argparse.ArgumentParser(description="novel-study 今日学习计划")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--sync", action="store_true", help="同步笔记/规则到 06-素材/")
    ap.add_argument("--book-key", help="明确选择一本已登记书；单元阅读时必传，避免沿用其他书的进度")
    ap.add_argument("--chapters", type=int, help="本单元章数；默认使用 config.json 的 daily_chapters")
    args = ap.parse_args()

    if args.sync:
        try:
            synced = sync_outputs()
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps({"synced": synced, "count": len(synced)},
                             ensure_ascii=False, indent=2))
        else:
            if synced:
                print(f"已同步 {len(synced)} 个文件：")
                for p in synced:
                    print(f"  {p}")
            else:
                print("没有需要同步的文件。")
        return 0

    try:
        plan = build_plan(args.book_key, args.chapters)
    except ValueError as exc:
        ap.error(str(exc))
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print_human(plan)
    return 0


if __name__ == "__main__":
    sys.exit(main())
