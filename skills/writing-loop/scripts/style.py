#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""style.py — 网文文风量化器。

把「感觉像不像」变成「可测量地差多少」。

用法:
    python3 scripts/style.py profile --book 十日终焉 --chapters 1-100
    python3 scripts/style.py check --file 我的章节.md --target 十日终焉 [--json]
    python3 scripts/style.py list

统计口径（与 novel-study 笔记一致）:
  * 只统计正文，剔除首行「# 标题」、markdown 注释与空行；
  * 句子按「。！？…」整串切分（含半角 !? 与 ASCII ...），换行也是句子边界；
  * 句长按「汉字数」计（不含标点、数字、空白），与笔记的实测值可直接对照；
  * 对话段 = 含有「」或“”的正文段落（一行算一段）；
  * 标点频率 = 出现次数 / 汉字总数 × 1000；
    省略号按整串算一次（…… / ...），破折号按整串算一次（—— / -）。

注：句长与标点口径跟 novel-study 读书笔记一致，数值可直接对照；
对话段口径不同（笔记记的是「对话起始段落」），两项不要直接比较。

依赖: 仅 Python 3 标准库（3.8+）。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

VERSION = "1.0"

# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve()
PROFILE_PATH = HERE.parents[1] / "data" / "profiles.json"


def find_books_dir(explicit: str | None = None) -> Path:
    """定位 .cache/novel-study/books：显式参数 > 环境变量 > 脚本上溯 > 当前目录。"""
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if not p.is_dir():
            fail(f"缓存目录不存在：{p}")
        return p

    env = os.environ.get("NOVEL_STUDY_CACHE")
    if env:
        p = Path(env).expanduser().resolve()
        if (p / "books").is_dir():
            return p / "books"
        if p.name == "books" and p.is_dir():
            return p

    for parent in HERE.parents:
        cand = parent / ".cache" / "novel-study" / "books"
        if cand.is_dir():
            return cand

    cand = Path.cwd() / ".cache" / "novel-study" / "books"
    if cand.is_dir():
        return cand

    fail(
        "找不到书库缓存 .cache/novel-study/books。\n"
        "  用 --cache-dir 指定，或设置 NOVEL_STUDY_CACHE 环境变量。"
    )
    raise AssertionError  # 不可达，仅供类型检查


def fail(msg: str, code: int = 2) -> None:
    print(f"✗ {msg}", file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------------------
# 文本清洗与统计
# ---------------------------------------------------------------------------

HANZI_RE = re.compile(r"[\u4e00-\u9fff]")
SENT_DELIM_RE = re.compile(r"(?:[。！？!?…]+|\.{3,})")
ELLIPSIS_RE = re.compile(r"…+|\.{3,}")
DASH_RE = re.compile(r"—+|--")
BLANK_WRAP = " \t\r\n\u3000「」『』“”‘’\"'"


def clean_lines(text: str) -> list[str]:
    """去掉章节标题、markdown 注释/引用符号和空行，返回正文段落列表。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    lines = []
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):          # 章节标题 / markdown 标题
            continue
        if line.startswith("```"):        # 代码围栏
            continue
        if re.fullmatch(r"[-=*_]{3,}", line):  # 分隔线
            continue
        if line.startswith("> "):         # 引用符号
            line = line[2:].strip()
        lines.append(line)
    return lines


def hanzi_count(text: str) -> int:
    return len(HANZI_RE.findall(text))


def split_sentences(text: str) -> list[str]:
    """按中文句末标点切句，返回去掉引号与空白的句子文本。"""
    pieces = SENT_DELIM_RE.split(text)
    out = []
    for piece in pieces:
        piece = piece.strip().strip(BLANK_WRAP)
        if hanzi_count(piece):
            out.append(piece)
    return out


def analyze(text: str) -> dict:
    """统计一份正文的文体指标。"""
    lines = clean_lines(text)

    sentences: list[str] = []
    for line in lines:
        sentences.extend(split_sentences(line))

    body = "\n".join(lines)  # 标点只统计正文，不把标题/注释里的标点算进来
    hanzi = sum(hanzi_count(line) for line in lines)
    if hanzi == 0 or not sentences:
        fail("正文里几乎没有可统计的中文内容，检查文件格式或章节是否为空。")

    sent_lens = [hanzi_count(s) for s in sentences]
    sent_lens = [n for n in sent_lens if n > 0]

    para_lens = [hanzi_count(line) for line in lines]
    para_lens = [n for n in para_lens if n > 0]

    dialogue_paras = sum(
        1 for line in lines if "「" in line or "“" in line
    )

    q_count = body.count("？") + body.count("?")
    ex_count = body.count("！") + body.count("!")
    ellipsis_count = len(ELLIPSIS_RE.findall(body))
    dash_count = len(DASH_RE.findall(body))

    def per1k(n: int) -> float:
        return round(n / hanzi * 1000, 2)

    return {
        "hanzi_count": hanzi,
        "sentence_count": len(sent_lens),
        "paragraph_count": len(para_lens),
        "dialogue_paragraph_count": dialogue_paras,
        "punct_counts": {
            "question": q_count,
            "exclaim": ex_count,
            "ellipsis": ellipsis_count,
            "dash": dash_count,
        },
        "avg_sentence_len": round(statistics.mean(sent_lens), 2),
        "median_sentence_len": round(float(statistics.median(sent_lens)), 2),
        "short_sentence_ratio": round(
            sum(1 for n in sent_lens if n <= 5) / len(sent_lens) * 100, 2
        ),
        "long_sentence_ratio": round(
            sum(1 for n in sent_lens if n >= 30) / len(sent_lens) * 100, 2
        ),
        "dialogue_ratio": round(dialogue_paras / len(para_lens) * 100, 2),
        "para_avg_len": round(statistics.mean(para_lens), 2),
        "q_per_1k": per1k(q_count),
        "ex_per_1k": per1k(ex_count),
        "ellipsis_per_1k": per1k(ellipsis_count),
        "dash_per_1k": per1k(dash_count),
    }


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        fail(f"读不了文件 {path}：{exc}")


def is_dataless(path: Path) -> bool:
    """iCloud/云盘占位文件：大小不为 0 但没有数据块，读它会卡在下载上。"""
    try:
        st = path.stat()
    except OSError:
        return False
    return st.st_size > 0 and st.st_blocks == 0


# ---------------------------------------------------------------------------
# 书库与档案
# ---------------------------------------------------------------------------

def find_book(books_dir: Path, name: str) -> dict:
    matches = []
    for meta_path in sorted(books_dir.glob("*/meta.json")):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        keys = {
            str(meta.get("name", "")),
            str(meta.get("key", "")),
            str(meta.get("book_id", "")),
            meta_path.parent.name,
        }
        if name.strip() in keys:
            meta["_dir"] = meta_path.parent
            matches.append(meta)

    if not matches:
        names = []
        for meta_path in sorted(books_dir.glob("*/meta.json")):
            try:
                names.append(json.loads(meta_path.read_text(encoding="utf-8")).get("name", meta_path.parent.name))
            except (OSError, json.JSONDecodeError):
                pass
        fail(f"书库里没有《{name}》。已有：" + ("、".join(names) if names else "（空）"))
    if len(matches) > 1:
        fail(f"《{name}》匹配到多本书，请用目录名/book_id 精确指定。")
    return matches[0]


def parse_chapters(spec: str, total: int) -> list[int]:
    """解析 '1-50' / '1,5,9-12' / 'all'，返回升序章节号。"""
    spec = spec.strip().lower()
    if spec == "all":
        return list(range(1, total + 1))

    nums: set[int] = set()
    for part in re.split(r"[，,\s]+", spec):
        if not part:
            continue
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", part)
        if not m:
            fail(f"章节范围写法看不懂：{part!r}（例：1-50 / 1,5,9-12 / all）")
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else start
        if start < 1 or end < start:
            fail(f"章节范围不合法：{part!r}")
        nums.update(range(start, end + 1))

    chosen = sorted(n for n in nums if n <= total)
    if not chosen:
        fail(f"章节范围 {spec!r} 在这本书里没有命中（全书 {total} 章）。")
    return chosen


def load_profiles() -> dict:
    if not PROFILE_PATH.exists():
        return {"version": 1, "profiles": {}}
    try:
        data = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"档案文件损坏，先备份再删掉它：{PROFILE_PATH}（{exc}）")
    if not isinstance(data, dict) or "profiles" not in data:
        return {"version": 1, "profiles": {}}
    return data


def save_profiles(data: dict) -> None:
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROFILE_PATH.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    tmp.replace(PROFILE_PATH)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# profile 子命令
# ---------------------------------------------------------------------------

def cmd_profile(args) -> None:
    books_dir = find_books_dir(args.cache_dir)
    meta = find_book(books_dir, args.book)
    book_dir: Path = meta["_dir"]
    chap_dir = book_dir / "chapters"

    total = int(meta.get("chapter_total") or 0)
    if total <= 0:
        files = sorted(chap_dir.glob("*.txt"))
        total = max((int(f.stem) for f in files if f.stem.isdigit()), default=0)
    if total <= 0:
        fail(f"《{args.book}》没有可用的章节文件：{chap_dir}")

    chapters = parse_chapters(args.chapters, total)

    texts: list[str] = []
    skipped: list[int] = []
    missing: list[int] = []
    dataless: list[int] = []
    for n in chapters:
        path = chap_dir / f"{n:04d}.txt"
        if not path.exists():
            missing.append(n)
            continue
        if is_dataless(path):
            dataless.append(n)
            continue
        text = read_text(path)
        if hanzi_count(text) < 50:   # 残章/占位章，统计会被噪声带偏
            skipped.append(n)
            continue
        texts.append(text)

    if not texts:
        fail(f"选中的 {len(chapters)} 章里没有可用正文（全部缺失或过短）。")

    metrics = analyze("\n\n".join(texts))
    name = str(meta.get("name") or book_dir.name)
    range_label = args.chapters.strip()

    data = load_profiles()
    entry = {
        "book": name,
        "author": meta.get("author", ""),
        "book_dir": book_dir.name,
        "book_id": meta.get("book_id", ""),
        "chapters": range_label,
        "chapter_count": len(texts),
        "skipped_chapters": skipped,
        "missing_chapters": missing,
        "dataless_chapters": dataless,
        "generated_at": now_iso(),
        "tool": f"style.py {VERSION}",
        "metrics": metrics,
    }
    existed = name in data["profiles"]
    data["profiles"][name] = entry
    save_profiles(data)

    m = metrics
    print(f"✓ 已写档案：{PROFILE_PATH}")
    print(f"  《{name}》 {range_label} · {len(texts)} 章 · {m['hanzi_count']:,} 汉字")
    if skipped:
        print(f"  跳过过短章节：{short_ranges(skipped)}")
    if missing:
        print(f"  缺失章节：{short_ranges(missing)}")
    if dataless:
        print(f"  ⚠ 未下载到本地的章节（iCloud 占位文件，已跳过）：{short_ranges(dataless)}")
        print("    要统计它们，先在 Finder 里把缓存目录下载到本地。")
    print(f"  平均句长 {m['avg_sentence_len']} 字 · 中位 {m['median_sentence_len']} 字"
          f" · ≤5 字 {m['short_sentence_ratio']}% · ≥30 字 {m['long_sentence_ratio']}%")
    print(f"  对话段 {m['dialogue_ratio']}% · 段落均长 {m['para_avg_len']} 字")
    print(f"  每千字：问号 {m['q_per_1k']} · 感叹号 {m['ex_per_1k']}"
          f" · 省略号 {m['ellipsis_per_1k']} · 破折号 {m['dash_per_1k']}")
    if existed:
        print("  （同名档案已覆盖）")


def short_ranges(nums: list[int]) -> str:
    """[1,2,3,7] -> '1-3, 7'"""
    if not nums:
        return ""
    nums = sorted(nums)
    out, start, prev = [], nums[0], nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
            continue
        out.append(f"{start}" if start == prev else f"{start}-{prev}")
        start = prev = n
    out.append(f"{start}" if start == prev else f"{start}-{prev}")
    return "、".join(out)


# ---------------------------------------------------------------------------
# check 子命令
# ---------------------------------------------------------------------------

# key, 显示名（带单位）, 单位, 类型：len=数值型，pct=百分点型
METRIC_DEFS = [
    ("avg_sentence_len", "平均句长（字）", "字", "len"),
    ("median_sentence_len", "句长中位数（字）", "字", "len"),
    ("short_sentence_ratio", "≤5 字短句（%）", "%", "pct"),
    ("long_sentence_ratio", "≥30 字长句（%）", "%", "pct"),
    ("dialogue_ratio", "对话段占比（%）", "%", "pct"),
    ("para_avg_len", "段落均长（字）", "字", "len"),
    ("q_per_1k", "问号（‰/千字）", "‰", "len"),
    ("ex_per_1k", "感叹号（‰/千字）", "‰", "len"),
    ("ellipsis_per_1k", "省略号（‰/千字）", "‰", "len"),
    ("dash_per_1k", "破折号（‰/千字）", "‰", "len"),
]

DENSITY_KEYS = {"q_per_1k", "ex_per_1k", "ellipsis_per_1k", "dash_per_1k"}

# 目标值几乎为零时，用绝对差判断（避免 0.0 被除出无穷大）
ZERO_TARGET_TOL = 0.05
DENSITY_ZERO = 0.5   # 目标密度低于 0.5‰ 时，百分比没意义，改看绝对差
DENSITY_ABS = 0.5    # 密度绝对差阈值（‰）
REL_TOL = 25.0       # 相对差阈值（%）


def human_comment(key: str, draft: float, target: float, direction: int, rel: float, delta: float) -> str:
    """统计只定位待核对之处，不由分布推断阅读效果。"""
    side = "高于" if direction > 0 else "低于"
    difference = (f"{abs(delta):.2f}‰" if key in DENSITY_KEYS and target < DENSITY_ZERO
                  else f"{abs(rel):.0f}%" if target > ZERO_TARGET_TOL else f"{abs(delta):.2f}")
    checks = {
        "avg_sentence_len": "可核对长短句安排是否符合本场叙述目的",
        "median_sentence_len": "可核对典型句子与特殊长短句各承担什么作用",
        "short_sentence_ratio": "可核对短句出现的位置及其信息是否完整",
        "long_sentence_ratio": "可核对长句的信息组织和具体可读性",
        "dialogue_ratio": "可核对对话是否符合人物、信息与关系需要",
        "para_avg_len": "可核对实际阅读版式与段落的信息组织",
        "q_per_1k": "可逐处核对问句是否符合人物与场景",
        "ex_per_1k": "可逐处核对感叹号是否符合当前语气",
        "ellipsis_per_1k": "可逐处核对停顿是否有语境依据",
        "dash_per_1k": "可逐处核对插入、转折或打断是否清楚",
    }
    return f"统计值{side}目标 {difference}；{checks[key]}，差异本身不要求修改"


def compare(draft: dict, target: dict) -> list[dict]:
    rows = []
    for key, label, unit, kind in METRIC_DEFS:
        d = float(draft[key])
        t = float(target[key])
        delta = d - t
        rel = delta / t * 100 if t > ZERO_TARGET_TOL else 0.0
        direction = 1 if delta > 0 else (-1 if delta < 0 else 0)

        if key in DENSITY_KEYS and t < DENSITY_ZERO:
            # 目标本来就几乎不用这种标点，百分比会算出「少 100%」这种废话
            flagged = abs(delta) > DENSITY_ABS
            gap_mode = "abs"
        elif t <= ZERO_TARGET_TOL:
            flagged = abs(delta) > 1.0
            gap_mode = "abs"
        else:
            flagged = abs(rel) > REL_TOL
            gap_mode = "point" if kind == "pct" else "rel"

        comment = human_comment(key, d, t, direction, rel, delta) if flagged else ""

        rows.append({
            "key": key,
            "label": label,
            "unit": unit,
            "kind": kind,
            "draft": round(d, 2),
            "target": round(t, 2),
            "delta": round(delta, 2),
            "rel_pct": round(rel, 1),
            "direction": direction,
            "gap_mode": gap_mode,
            "flagged": flagged,
            "comment": comment,
        })
    return rows


# ---------------------------------------------------------------------------
# 显示工具
# ---------------------------------------------------------------------------

def disp_width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in s)


def pad(s: str, width: int, align: str = "left") -> str:
    s = str(s)
    gap = max(0, width - disp_width(s))
    return (" " * gap + s) if align == "right" else (s + " " * gap)


def fmt_num(value: float, unit: str) -> str:
    """数值列只放数字，单位已经在指标名里，避免宽度计算被中文单位带偏。"""
    return f"{value:.1f}"


def gap_text(r: dict) -> str:
    if r["gap_mode"] == "abs" and abs(r["delta"]) < 0.005:
        return "0"
    if r["gap_mode"] == "rel":
        return f"{r['rel_pct']:+.1f}%"
    if r["gap_mode"] == "point":
        return f"{r['delta']:+.1f} 点"
    if r["unit"] == "‰":
        return f"{r['delta']:+.2f}‰"
    if r["unit"] == "%":
        return f"{r['delta']:+.1f} 点"
    return f"{r['delta']:+.1f}"


def chapter_label(spec: str) -> str:
    return "全书" if str(spec).strip().lower() == "all" else f"第 {spec} 章"


def render_check(draft_info: dict, target_name: str, target_entry: dict,
                 rows: list[dict], note: str = "") -> str:
    m = draft_info["metrics"]
    t = target_entry["metrics"]
    lines: list[str] = []
    lines.append("═" * 66)
    lines.append(f" 文风体检：{draft_info['name']}  vs  {target_name}")
    lines.append("═" * 66)
    lines.append(f" 稿子：{m['hanzi_count']:,} 汉字 · {m['sentence_count']:,} 句 · "
                 f"{m['paragraph_count']:,} 段")
    lines.append(f" 目标：《{target_name.strip('《》')}》 {chapter_label(target_entry['chapters'])}"
                 f" · {t['hanzi_count']:,} 汉字 · {t['sentence_count']:,} 句"
                 f"（{target_entry['generated_at'][:10]} 建档）")
    if note:
        lines.append(f" 注意：{note}")
    lines.append("")

    header = ["指标", "你的稿子", "目标", "差距"]
    widths = [
        max(disp_width(header[0]), *(disp_width(r["label"]) for r in rows)),
        max(disp_width(header[1]), *(disp_width(fmt_num(r["draft"], r["unit"])) for r in rows)),
        max(disp_width(header[2]), *(disp_width(fmt_num(r["target"], r["unit"])) for r in rows)),
        max(disp_width(header[3]), *(disp_width(gap_text(r) + " ⚠") for r in rows)),
    ]
    lines.append(" " + "   ".join(
        pad(h, w, "left" if i == 0 else "right")
        for i, (h, w) in enumerate(zip(header, widths))
    ))
    lines.append(" " + "─" * (sum(widths) + 3 * (len(widths) - 1)))

    for r in rows:
        mark = "⚠" if r["flagged"] else "✓"
        lines.append(" " + "   ".join([
            pad(r["label"], widths[0]),
            pad(fmt_num(r["draft"], r["unit"]), widths[1], "right"),
            pad(fmt_num(r["target"], r["unit"]), widths[2], "right"),
            pad(f"{gap_text(r)} {mark}", widths[3], "right"),
        ]))

    flagged = [r for r in rows if r["flagged"]]
    lines.append("")
    if flagged:
        lines.append(f" ── 差距超过 {REL_TOL:.0f}% 的 {len(flagged)} 项 ──")
        for r in flagged:
            lines.append(f"  ⚠ {r['label']}：{r['comment']}")
    else:
        lines.append(" ── 十项统计均在当前差异阈值内 ──")

    lines.append("")
    lines.append(f" 一句话：{summarize(flagged)}")
    return "\n".join(lines)


def summarize(flagged: list[dict]) -> str:
    if not flagged:
        return "十项统计在比较区间内；这不判断人物、结构、情绪效果或整体文风。"
    ranked = sorted(
        flagged,
        key=lambda r: abs(r["rel_pct"]) if r["target"] > ZERO_TARGET_TOL else 100.0,
        reverse=True,
    )
    parts = []
    for r in ranked[:2]:
        short = r["label"].split("（")[0]
        if r["gap_mode"] == "abs" and r["unit"] == "‰":
            detail = f"{r['delta']:+.2f}‰"
        else:
            detail = gap_text(r)
        parts.append(f"{short} {detail}")
    return "、".join(parts) + " 的统计差异最大；按场景目的核对相关段落，无需为对齐数值改稿。"


# ---------------------------------------------------------------------------
# list 子命令
# ---------------------------------------------------------------------------

def cmd_list(args) -> None:
    data = load_profiles()
    profiles = data.get("profiles", {})
    if not profiles:
        print("还没有文风档案。先跑：")
        print("  python3 scripts/style.py profile --book 十日终焉 --chapters 1-100")
        return

    print(f" 已有文风档案（{len(profiles)} 本）  ·  {PROFILE_PATH}")
    print(" " + "─" * 74)
    rows = []
    for name, entry in sorted(profiles.items()):
        m = entry.get("metrics", {})
        requested = (entry.get("chapter_count", 0)
                     + len(entry.get("skipped_chapters", []))
                     + len(entry.get("missing_chapters", [])))
        used = entry.get("chapter_count", 0)
        chap_cell = f"{used}/{requested} 章" if requested and requested != used else f"{used} 章"
        rows.append([
            name,
            f"[{entry.get('chapters', '?')}]",
            chap_cell,
            f"{m.get('hanzi_count', 0):,} 字",
            f"均句 {m.get('avg_sentence_len', 0)}",
            f"对话 {m.get('dialogue_ratio', 0)}%",
            entry.get("generated_at", "")[:16].replace("T", " "),
        ])
    widths = [max(disp_width(r[i]) for r in rows + [[
        "书名", "章节", "章数", "字数", "均句", "对话", "建档时间"]])
        for i in range(7)]
    print(" " + "  ".join(pad(h, w) for h, w in zip(
        ["书名", "章节", "章数", "字数", "均句", "对话", "建档时间"], widths)))
    for r in rows:
        print(" " + "  ".join(pad(v, w) for v, w in zip(r, widths)))

    notes = []
    for name, entry in sorted(profiles.items()):
        dl = len(entry.get("dataless_chapters", []))
        if dl:
            notes.append(f"⚠ 《{name}》有 {dl} 章还没下载到本地，本次统计没有覆盖它们。")
    if notes:
        print()
        for note in notes:
            print(" " + note)
        print("  要补全：在 Finder 里把 .cache/novel-study/books 对应目录下载到本地，再重新 profile。")


# ---------------------------------------------------------------------------
# check 主流程
# ---------------------------------------------------------------------------

def cmd_check(args) -> None:
    path = Path(args.file).expanduser()
    if not path.exists():
        fail(f"稿子不存在：{path}")
    if is_dataless(path):
        fail(f"稿子还没有下载到本地（iCloud/云盘占位文件），读它会卡住：{path}")
    text = read_text(path)
    draft = analyze(text)
    run_note = ""
    if draft["hanzi_count"] < 300:
        run_note = f"稿子只有 {draft['hanzi_count']} 汉字，样本偏小，差距仅供参考"

    data = load_profiles()
    profiles = data.get("profiles", {})
    target = profiles.get(args.target)
    if target is None:
        names = "、".join(sorted(profiles)) or "（空）"
        fail(f"没有《{args.target}》的文风档案。已有：{names}\n"
             f"  先跑：python3 scripts/style.py profile --book {args.target} --chapters 1-100")

    rows = compare(draft, target["metrics"])
    flagged = [r for r in rows if r["flagged"]]

    if args.json:
        payload = {
            "tool": f"style.py {VERSION}",
            "generated_at": now_iso(),
            "file": str(path),
            "file_name": path.name,
            "target": args.target,
            "target_chapters": target.get("chapters"),
            "draft": draft,
            "target_metrics": target["metrics"],
            "metrics": rows,
            "flagged_count": len(flagged),
            "summary": summarize(flagged),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    draft_info = {"name": path.name, "metrics": draft}
    print(render_check(draft_info, f"《{args.target}》", target, rows, note=run_note))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="style.py",
        description="网文文风量化器：把「读起来像不像」变成可测量的指标差距。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "例子:\n"
            "  python3 scripts/style.py profile --book 十日终焉 --chapters 1-100\n"
            "  python3 scripts/style.py check --file 我的章节.md --target 十日终焉\n"
            "  python3 scripts/style.py check --file ch001.md --target 十日终焉 --json\n"
            "  python3 scripts/style.py list\n\n"
            "统计口径:\n"
            "  只算正文（剔除 # 标题行、注释、空行）；按 。！？… 整串切句，换行也是边界；\n"
            "  句长与段落长只数汉字；对话段 = 含「」或“”的段落；\n"
            "  标点频率 = 次数 / 汉字数 × 1000，省略号与破折号按整串算一次。\n"
            "  句长/标点口径与 novel-study 读书笔记一致（可直接对照数值）；\n  对话段按「含引号的段落」算，笔记里是「对话起始段落」，两者不可直接比。\n"
        ),
    )
    parser.add_argument("-V", "--version", action="version", version=f"style.py {VERSION}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="<子命令>")

    p_profile = sub.add_parser(
        "profile",
        help="统计一本书的正文文风，写入 data/profiles.json",
        description="统计一本书指定章节的正文文风，并写入 data/profiles.json（同名档案覆盖）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_profile.add_argument("--book", required=True, metavar="书名",
                           help="书名、book_id 或缓存目录名，如 十日终焉")
    p_profile.add_argument("--chapters", default="1-100", metavar="范围",
                           help="章节范围：1-100 / 1,5,9-12 / all（默认 1-100）")
    p_profile.add_argument("--cache-dir", metavar="目录",
                           help="书库缓存目录（默认自动找 .cache/novel-study/books）")
    p_profile.set_defaults(func=cmd_profile)

    p_check = sub.add_parser(
        "check",
        help="拿稿子和目标作者对比，输出差异报告",
        description="把稿子和已有文风档案逐项对比，标出差距超过 25% 的项并给人话判断。",
    )
    p_check.add_argument("--file", required=True, metavar="文件",
                         help="你的稿子（.md / .txt 都行）")
    p_check.add_argument("--target", required=True, metavar="书名",
                         help="目标作者的书，如 十日终焉（需先 profile）")
    p_check.add_argument("--json", action="store_true", help="输出 JSON，方便脚本消费")
    p_check.set_defaults(func=cmd_check)

    p_list = sub.add_parser("list", help="列出已有文风档案",
                            description="列出 data/profiles.json 里已有的文风档案。")
    p_list.set_defaults(func=cmd_list)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        os._exit(0)
