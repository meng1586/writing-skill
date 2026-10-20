#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""场景索引器 —— 「没读过怎么知道哪本书有哪个场景？」

边读边建索引：把 novel-study 单元笔记里「读者层：这一段大概讲了什么」
抽出来，用场景词表匹配出「哪个单元有什么场景」，写进 data/index.jsonl。

子命令
  add       追加一条手动索引（边读边记）
  find      查某个场景出现在哪些单元
  list      列出所有场景类型和条数
  rebuild   从 novel-study 笔记批量重建索引

示例
  python3 scripts/index.py add --book 十日终焉 --chapters 971-980 --scene 托孤 --note "白羊托孤"
  python3 scripts/index.py find --scene 托孤
  python3 scripts/index.py find --scene 告别 --book 十日终焉 --json
  python3 scripts/index.py list
  python3 scripts/index.py rebuild

数据格式
  data/index.jsonl，每行一个 JSON 对象，字段固定为
  book / chapters / scene / note / added
  add 只追加；rebuild 会整体重写该文件。

匹配规则（为什么不是字面匹配）
  笔记梗概写的是「发生了什么」，几乎不会出现「托孤」「打脸」这类评论词。
  所以每个场景 = 一组强信号 + 一组弱信号：
    · 命中任一强信号 → 记一条
    · 只命中弱信号 → 需同时命中 2 个才记，压住误报
  note 里保留命中的信号，方便人工复核。

依赖：仅标准库。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, OrderedDict
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------- 路径

BASE_DIR = Path(__file__).resolve().parent.parent          # skills/writing-loop
DATA_DIR = BASE_DIR / "data"
INDEX_FILE = DATA_DIR / "index.jsonl"
NOTES_DIR = BASE_DIR.parent / "novel-study" / "data" / "notes"

# 笔记里梗概段的标记
SUMMARY_MARK = "这一段大概讲了什么"
# 笔记文件名 / 梗概标题里的章节范围：第971-980章、第 971–980 章、1-10章
RANGE_RE = re.compile(r"第\s*(\d+)\s*[-–—~至]\s*(\d+)\s*章")
CHAPTER_HEAD_RE = re.compile(r"(\d+)")

# ---------------------------------------------------------------- 场景词表
#
# 依据：对 119 篇十日终焉单元笔记的梗概做词频摸底后手工校准。
# 故意不用「死」「血」之外的单字宽词，也故意删掉了「记忆」「合作」这类
# 一命中就满屏误报的词（「保住记忆」不是失忆，「羊=说谎、狗=合作」不是结盟）。

SCENE_LEXICON = {
    "打脸": (
        ("打脸", "扇耳光", "扇了他", "巴掌", "耳光", "羞辱", "哑口无言", "低头认错", "下不来台", "颜面"),
        ("嘲讽", "讥讽", "冷笑", "当众", "破口大骂", "难堪", "奚落"),
    ),
    "反转": (
        ("反转", "出人意料", "意想不到", "反将一军", "局势逆转", "计划是假的", "从头到尾都是",
         "原来自始至终", "翻了过来", "将计就计", "反将", "识破", "骗过了", "原来是故意",
         "真正的目的", "另有目的"),
        ("竟然", "居然", "没想到", "原来", "其实"),
    ),
    "告别": (
        ("告别", "道别", "永别", "诀别", "最后一面", "送别", "临别", "说再见", "再见了",
         "离开之前", "最后一程"),
        # 「离开」「走了」是同义叠加，一起出现也证明不了告别场景
        # （「离开前从尸体口袋摸走一样东西」就被误报过），只留「再见」做弱信号。
        ("再见",),
    ),
    "绝境": (
        ("绝境", "走投无路", "退无可退", "无路可走", "孤注一掷", "背水一战", "最后一搏",
         "活不过今晚", "只剩一口气", "必死", "死局", "撑不住了", "撑不下去"),
        ("拼命", "濒死", "绝望", "赌上"),
    ),
    "托孤": (
        ("托孤", "托付", "交代后事", "后事", "临终", "遗言", "遗志", "身后事",
         "如果他死了", "如果他死了之后", "如果我不在了", "我死了之后", "我若是死了",
         "要是我死了", "如果我死了", "他死了之后", "我走了之后", "替我照顾", "照顾好",
         "交给你了", "收尸"),
        ("交代", "拜托", "把妹妹", "把孩子", "把家人", "临死", "要死"),
    ),
    "翻盘": (
        ("翻盘", "反杀", "逆转", "反败为胜", "赢回来", "扭转", "绝地反击", "逆风", "翻过来",
         "反超", "扳回", "最后赢了", "赢了", "打赢"),
        ("最后一步", "反过来", "绝地"),
    ),
    "谈判": (
        ("谈判", "谈条件", "开价", "讨价还价", "会谈", "坐下来谈", "交涉", "提条件", "协议",
         "谈判桌"),
        ("交易", "条件", "商量", "答应"),
    ),
    "追逐": (
        ("追杀", "追捕", "甩掉", "逃命", "追赶", "跑掉", "追上来", "追进", "追着", "追",
         "逃", "逃出", "躲进"),
        (),
    ),
    "揭示": (
        ("真相", "揭穿", "底牌", "道破", "说穿", "坦白", "秘密", "情报", "身份是",
         "真相大白", "才明白", "这才知道"),
        ("承认", "告诉", "原来"),
    ),
    "爆发": (
        ("爆发", "炸开", "崩了", "失控", "打起来", "大打出手", "撕破脸", "暴走", "怒吼",
         "发作", "发疯", "拍桌", "吼了"),
        ("打斗", "血"),
    ),
    "立威": (
        ("立威", "震慑", "杀鸡儆猴", "镇住", "威压", "震住", "不敢再", "杀一儆百", "无人敢"),
        ("让所有人", "威严", "畏惧"),
    ),
    "交易": (
        ("交易", "筹码", "买卖", "交换", "等价", "换走", "付出代价", "代价是", "买"),
        ("条件", "答应", "换"),
    ),
    "死亡": (
        ("死", "尸体", "牺牲", "阵亡", "咽气", "断气", "送葬", "杀死", "死掉", "死亡"),
        ("血", "亡"),
    ),
    "背叛": (
        ("背叛", "出卖", "叛变", "反水", "内鬼", "卧底", "倒戈", "背刺", "捅刀", "骗了他",
         "利用"),
        (),
    ),
    "结盟": (
        ("结盟", "联手", "同盟", "结伴", "达成一致", "站到一边", "同一阵线", "拉拢", "合流",
         "归顺", "一起干"),
        ("合作", "答应"),
    ),
    "失忆": (
        ("失忆", "忘记", "记不起", "想不起来", "忘掉", "记不住", "忘了", "记忆被改",
         "丧失记忆", "忘光"),
        ("记忆", "不记得"),
    ),
    "赌局": (
        ("赌局", "押注", "下注", "一局", "赌博", "赌上", "赌一把", "赌注", "赌"),
        (),
    ),
    "越狱": (
        ("越狱", "逃狱", "牢房", "监狱", "关在", "关着", "破门", "狱中", "出狱", "打开牢门"),
        ("逃出", "逃出去", "脱身", "冲出"),
    ),
    "审判": (
        ("审判", "宣判", "判决", "处决", "指控", "法庭", "审问", "审讯", "罪名", "有罪",
         "定罪", "审判庭"),
        (),
    ),
    "认亲": (
        ("认亲", "亲生", "血缘", "父女", "母女", "父子", "兄妹", "亲属", "相认",
         "亲妹妹", "亲弟弟", "亲姐姐"),
        (),
    ),
}

SCENE_ORDER = list(SCENE_LEXICON.keys())

# ---------------------------------------------------------------- 小工具


def now_iso() -> str:
    """本地时间，精确到秒，例如 2026-10-21T00:12:03。"""
    return datetime.now().isoformat(timespec="seconds")


def chapter_start(chapters: str) -> int:
    """把 '971-980' 排成 '971'，用于稳定排序。"""
    m = CHAPTER_HEAD_RE.search(chapters or "")
    return int(m.group(1)) if m else 10 ** 9


def normalize_chapters(raw: str) -> str:
    """'971–980 章' / '第971-980章' 统一成 '971-980'；认不出就原样返回。"""
    if not raw:
        return ""
    m = RANGE_RE.search(raw)
    if m:
        return "%s-%s" % (m.group(1), m.group(2))
    return raw.strip()


# ---------------------------------------------------------------- 笔记解析


def extract_summary(text: str) -> str:
    """取「- **这一段大概讲了什么**：」后面的正文。

    两种写法都要吃：
      · 冒号后直接跟正文（常见于早期笔记，还带「（11–20 章）」前缀）
      · 冒号后换行、正文缩进两格（多段）
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if SUMMARY_MARK not in line:
            continue
        m = re.search(r"[：:]\s*(.*)$", line)
        first = (m.group(1).strip() if m else "")
        parts = [first] if first else []
        for nxt in lines[i + 1:]:
            if not nxt.strip():
                continue
            if nxt[:1] in (" ", "\t"):
                parts.append(nxt.strip())
            else:
                break
        return "\n".join(parts).strip()
    return ""


def resolve_meta(path: Path, text: str):
    """从文件名（必要时从梗概标题）解析出 (书名, 章节范围)。解析不到返回 (书名, '')。"""
    book = path.stem
    m = RANGE_RE.search(book)
    if m:
        name = book[: m.start()].rstrip("-_· ,，、")
        return (name or "未知书目"), "%s-%s" % (m.group(1), m.group(2))

    # 书名-前情提要.md 这类没有章号：试试梗概标题里的「（1–10 章）」
    m2 = re.search(r"%s[^\n（]{0,80}?（\s*(\d+)\s*[-–—~至]\s*(\d+)\s*章" % SUMMARY_MARK, text)
    if m2:
        name = re.split(r"[-_]", book, maxsplit=1)[0].strip() or "未知书目"
        return name, "%s-%s" % (m2.group(1), m2.group(2))
    return (re.split(r"[-_]", book, maxsplit=1)[0].strip() or "未知书目"), ""


def match_scenes(summary: str):
    """返回 [(场景, [触发的信号词...]), ...]，一个单元可以命中多个场景。

    强信号命中就够了，note 里只列强信号；只靠弱信号命中时，要求 2 个叠加，
    并且 note 里列的就是这 2 个。这样查到的每一条都能看到「凭什么记它」。
    """
    hits = []
    for scene, (strong, weak) in SCENE_LEXICON.items():
        s_hits = [w for w in dict.fromkeys(strong) if w in summary]
        w_hits = [w for w in dict.fromkeys(weak) if w in summary]
        if s_hits:
            hits.append((scene, s_hits))
        elif len(w_hits) >= 2:
            hits.append((scene, w_hits))
    return hits


def build_note(terms, summary: str, limit: int = 72) -> str:
    """note = 命中依据 + 梗概摘要，查的时候一眼能看到证据。"""
    snippet = re.sub(r"\s+", " ", summary).strip()
    if len(snippet) > limit:
        snippet = snippet[:limit] + "…"
    return "命中「%s」｜%s" % ("、".join(terms), snippet)


# ---------------------------------------------------------------- 存取


def load_rows():
    """读 index.jsonl；文件不存在或坏行都容错。"""
    rows = []
    if not INDEX_FILE.exists():
        return rows
    with INDEX_FILE.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                print("  ! 跳过坏行 %d: %s" % (lineno, line[:60]), file=sys.stderr)
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def append_row(row) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with INDEX_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_rows(rows) -> None:
    """整体重写（rebuild 用），先写临时文件再替换，避免写一半。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = INDEX_FILE.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    os.replace(tmp, INDEX_FILE)


# ---------------------------------------------------------------- 子命令


def cmd_add(args) -> int:
    scene = args.scene.strip()
    if not scene:
        print("场景不能为空。", file=sys.stderr)
        return 2
    row = {
        "book": args.book.strip(),
        "chapters": normalize_chapters(args.chapters),
        "scene": scene,
        "note": (args.note or "").strip(),
        "added": now_iso(),
    }
    append_row(row)
    print("已追加索引：%s %s · %s" % (row["book"], row["chapters"], row["scene"]))
    if row["note"]:
        print("  备注：%s" % row["note"])
    if scene not in SCENE_LEXICON:
        print("  提示：「%s」不在预置场景词表里，find/list 仍能查到，但 rebuild 不会自动抽它。"
              % scene, file=sys.stderr)
    return 0


def _filter_rows(rows, scene, book):
    q = (scene or "").strip()
    sel = []
    for row in rows:
        s = str(row.get("scene", ""))
        if not (s == q or q in s or s in q):
            continue
        if book:
            b = str(row.get("book", ""))
            if not (b == book or book in b):
                continue
        sel.append(row)
    return sel


def cmd_find(args) -> int:
    rows = load_rows()
    if not rows:
        msg = "索引还是空的，先跑一次：python3 scripts/index.py rebuild"
        if args.json_out:
            print(json.dumps({
                "total": 0,
                "query": {"scene": args.scene, "book": args.book},
                "message": msg,
                "items": [],
            }, ensure_ascii=False, indent=1))
        else:
            print(msg + "（或先用 add 手动记一条）")
        return 0

    sel = _filter_rows(rows, args.scene, args.book)
    q = args.scene.strip()
    # 精确匹配排前面，其次按书名 / 章节 / 场景排
    sel.sort(key=lambda r: (
        0 if str(r.get("scene", "")) == q else 1,
        str(r.get("book", "")),
        chapter_start(str(r.get("chapters", ""))),
        str(r.get("scene", "")),
    ))

    if args.json_out:
        items = sel[: args.limit] if args.limit > 0 else sel
        print(json.dumps({
            "total": len(sel),
            "returned": len(items),
            "query": {"scene": q, "book": args.book},
            "items": items,
        }, ensure_ascii=False, indent=1))
        return 0

    if not sel:
        hint = "（试过模糊匹配：场景名互相包含）"
        print("没有找到「%s」的场景记录。%s" % (q, hint))
        if args.book:
            print("  过滤条件：book=%s" % args.book)
        print("  当前索引里的场景类型：" + "、".join(sorted({str(r.get("scene")) for r in rows})))
        return 0

    head = "共 %d 条 · 场景「%s」" % (len(sel), q)
    if args.book:
        head += " · 书「%s」" % args.book
    if args.limit > 0 and len(sel) > args.limit:
        head += "（只显示前 %d 条）" % args.limit
    print(head)
    print()
    for row in (sel[: args.limit] if args.limit > 0 else sel):
        print("  %s  %s" % (row.get("book", "?"), row.get("chapters", "?")))
        note = str(row.get("note", ""))
        if note:
            print("    " + note)
        print()
    return 0


def cmd_list(args) -> int:
    rows = load_rows()
    counts = Counter(str(r.get("scene", "")) for r in rows)
    books = Counter(str(r.get("book", "")) for r in rows)
    units = {(str(r.get("book", "")), str(r.get("chapters", ""))) for r in rows}

    if args.json_out:
        print(json.dumps({
            "total": len(rows),
            "scene_types": len(counts),
            "units": len(units),
            "books": dict(books),
            "scenes": [{"scene": s, "count": c} for s, c in
                       sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))],
        }, ensure_ascii=False, indent=1))
        return 0

    if not rows:
        print("索引还是空的，先跑一次：python3 scripts/index.py rebuild")
        return 0

    print("场景索引：%d 条 / %d 种场景 / %d 个单元" % (len(rows), len(counts), len(units)))
    if books:
        print("  书目：" + "、".join("%s(%d)" % (b, c) for b, c in books.most_common()))
    print()

    top = max(counts.values()) if counts else 1
    width = max(len(s) for s in counts) + 2
    rank = 0
    for scene, cnt in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        rank += 1
        bar_len = max(1, round(cnt / top * 24))
        bar = "█" * bar_len
        print("  %2d  %-*s %4d  %s" % (rank, width, scene, cnt, bar))
    return 0


def cmd_rebuild(args) -> int:
    if not NOTES_DIR.exists():
        print("找不到笔记目录：%s" % NOTES_DIR, file=sys.stderr)
        print("（场景索引依赖 novel-study 的单元笔记）", file=sys.stderr)
        return 2

    files = sorted(NOTES_DIR.glob("*.md"))
    rows, skipped, no_summary, no_hit = [], [], [], []
    covered = set()

    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            skipped.append("%s（读取失败：%s）" % (path.name, exc))
            continue

        book, chapters = resolve_meta(path, text)
        if not chapters:
            skipped.append("%s（文件名/梗概里没有章节范围）" % path.name)
            continue

        summary = extract_summary(text)
        if not summary:
            no_summary.append(path.name)
            continue

        hits = match_scenes(summary)
        if not hits:
            no_hit.append("%s %s" % (book, chapters))
            continue
        for scene, terms in hits:
            rows.append(OrderedDict([
                ("book", book),
                ("chapters", chapters),
                ("scene", scene),
                ("note", build_note(terms, summary)),
                ("added", now_iso()),
            ]))
            covered.add(scene)

    # 稳定排序：书名 → 章节起始 → 场景在词表里的顺序
    order = {s: i for i, s in enumerate(SCENE_ORDER)}
    rows.sort(key=lambda r: (r["book"], chapter_start(r["chapters"]), order.get(r["scene"], 999), r["chapters"]))

    write_rows(rows)

    counts = Counter(r["scene"] for r in rows)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    units = {(r["book"], r["chapters"]) for r in rows}
    empty = [s for s in SCENE_LEXICON if s not in counts]

    if args.json_out:
        print(json.dumps({
            "index_file": str(INDEX_FILE),
            "files_scanned": len(files),
            "entries": len(rows),
            "scene_types": len(covered),
            "scene_types_total": len(SCENE_LEXICON),
            "units": len(units),
            "skipped": skipped,
            "no_summary": no_summary,
            "no_scene_hit": no_hit,
            "zero_hit_scenes": empty,
            "distribution": [{"scene": s, "count": c} for s, c in ranked],
        }, ensure_ascii=False, indent=1))
        return 0

    print("重建索引：扫描 %d 个笔记文件" % len(files))
    print("  写入 %s" % INDEX_FILE)
    print("  抽取 %d 条，覆盖 %d/%d 种场景" % (len(rows), len(covered), len(SCENE_LEXICON)))
    if skipped:
        print("  跳过 %d 个文件：" % len(skipped))
        for item in skipped:
            print("    · " + item)
    if no_summary:
        print("  无梗概 %d 个：%s" % (len(no_summary), "、".join(no_summary)))
    if no_hit:
        print("  无场景命中的单元 %d 个：%s" % (len(no_hit), "、".join(no_hit)))
    print()

    print("  分布：" + " · ".join("%s %d" % (s, c) for s, c in ranked))
    if empty:
        print("  零命中场景：" + "、".join(empty))
    print("  覆盖 %d 个单元" % len(units))
    return 0


# ---------------------------------------------------------------- CLI


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="index.py",
        description="场景索引器：边读边建索引，回答「哪本书哪个单元有什么场景」。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python3 scripts/index.py add --book 十日终焉 --chapters 971-980 --scene 托孤 --note \"白羊托孤\"\n"
            "  python3 scripts/index.py find --scene 托孤\n"
            "  python3 scripts/index.py find --scene 告别 --book 十日终焉 --json\n"
            "  python3 scripts/index.py list\n"
            "  python3 scripts/index.py rebuild\n\n"
            "场景词表（20 种）：\n  " + "、".join(SCENE_ORDER) + "\n"
        ),
    )
    sub = p.add_subparsers(dest="command", metavar="{add,find,list,rebuild}")

    a = sub.add_parser("add", help="追加一条索引（边读边记）",
                       description="往 data/index.jsonl 追加一条场景记录。")
    a.add_argument("--book", required=True, help="书名，例如 十日终焉")
    a.add_argument("--chapters", required=True, help="章节范围，例如 971-980")
    a.add_argument("--scene", required=True, help="场景类型，例如 托孤")
    a.add_argument("--note", default="", help="备注，例如「白羊托孤」")
    a.set_defaults(func=cmd_add)

    f = sub.add_parser("find", help="查某个场景出现在哪些单元",
                       description="按场景名查找索引条目，默认模糊匹配（场景名互相包含）。")
    f.add_argument("--scene", required=True, help="要查的场景，例如 托孤")
    f.add_argument("--book", default="", help="只看某本书")
    f.add_argument("--limit", type=int, default=0, help="最多显示 N 条（0 = 全部）")
    f.add_argument("--json", dest="json_out", action="store_true", help="输出 JSON")
    f.set_defaults(func=cmd_find)

    l = sub.add_parser("list", help="列出所有场景类型和条数",
                       description="统计索引里每种场景的条数，按条数排行。")
    l.add_argument("--json", dest="json_out", action="store_true", help="输出 JSON")
    l.set_defaults(func=cmd_list)

    r = sub.add_parser("rebuild", help="从 novel-study 笔记批量重建索引",
                       description="读 novel-study 的单元笔记，抽取梗概、匹配场景词表，整体重建 data/index.jsonl。")
    r.add_argument("--json", dest="json_out", action="store_true", help="以 JSON 输出摘要（备用）")
    r.set_defaults(func=cmd_rebuild)

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
