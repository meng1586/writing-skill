#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""style.py — 网文文风量化器。

把「感觉像不像」变成「可测量地差多少」。

用法:
    python3 scripts/style.py profile --book 目标作品 --chapters 1-100
    python3 scripts/style.py check --file 我的章节.md --target 目标作品 [--json]
    python3 scripts/style.py list

统计口径（与 novel-study 笔记一致）:
  * 只统计正文，剔除首行「# 标题」、markdown 注释与空行；
  * 句子按「。！？…」整串切分（含半角 !? 与 ASCII ...），换行也是句子边界；
  * 句长按「汉字数」计（不含标点、数字、空白），与笔记的实测值可直接对照；
  * 对话段 = 含有「」或“”的正文段落（一行算一段）；
  * 标点频率 = 出现次数 / 汉字总数 × 1000；
    省略号按整串算一次（…… / ...），破折号按整串算一次（—— / -）。

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

    q_count = text.count("？") + text.count("?")
    ex_count = text.count("！") + text.count("!")
    ellipsis_count = len(ELLIPSIS_RE.findall(text))
    dash_count = len(DASH_RE.findall(text))

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
    for n in chapters:
        path = chap_dir / f"{n:04d}.txt"
        if not path.exists():
            missing.append(n)
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

# key, 显示名, 单位, 是否百分点型
METRIC_DEFS = [
    ("avg_sentence_len", "平均句长", "字", False),
    ("median_sentence_len", "句长中位数", "字", False),
    ("short_sentence_ratio", "≤5 字短句占比", "%", True),
    ("long_sentence_ratio", "≥30 字长句占比", "%", True),
    ("dialogue_ratio", "对话段占比", "%", True),
    ("para_avg_len", "段落平均长度", "字", False),
    ("q_per_1k", "问号密度", "‰", False),
    ("ex_per_1k", "感叹号密度", "‰", False),
    ("ellipsis_per_1k", "省略号密度", "‰", False),
    ("dash_per_1k", "破折号密度", "‰", False),
]

# 目标值几乎为零时，用绝对差判断（避免 0.0 被除出无穷大）
ZERO_TARGET_TOL = 0.05
ZERO_TARGET_ABS = 1.0
REL_TOL = 25.0  # 百分点 / 相对差阈值


def human_comment(key: str, draft: float, target: float, direction: int, rel: float, delta: float) -> str:
    """给一项差距配一句人话。direction: 1 你偏大，-1 你偏小。"""
    pct = f"{abs(rel):.0f}%"
    abs_d = f"{abs(delta):.1f}"
    if target <= ZERO_TARGET_TOL:
        if key == "dash_per_1k":
            return f"目标几乎不用破折号，你却有 {draft:.1f}‰，句子被打断得有点多"
        if key == "ex_per_1k":
            return f"目标几乎不用感叹号，你却有 {draft:.1f}‰，情绪外放得比目标吵"
        if key == "ellipsis_per_1k":
            return f"目标几乎不用省略号，你却有 {draft:.1f}‰，停顿多了，说话变虚"
        if key == "q_per_1k":
            return f"目标几乎不用问号，你却有 {draft:.1f}‰，追问感比目标重"
        return f"目标几乎为零，你却有 {draft:.2f}{('‰' if 'per_1k' in key else '')}"

    if direction > 0:
        table = {
            "avg_sentence_len": f"你的句子比目标长 {pct}，读起来会更闷、更拖",
            "median_sentence_len": f"你的中位句长比目标长 {pct}，长句是常态而不是点缀",
            "short_sentence_ratio": f"≤5 字短句比目标多 {abs_d} 个百分点，碎句敲得勤，节奏更急",
            "long_sentence_ratio": f"≥30 字长句比目标多 {abs_d} 个百分点，长句压场，手机上容易读滑",
            "dialogue_ratio": f"对话段比目标多 {abs_d} 个百分点，更热闹，但也可能显得碎嘴",
            "para_avg_len": f"段落比目标长 {pct}，手机上是一整坨字，眼睛更累",
            "q_per_1k": f"问号密度比目标高 {pct}，追问感更重，也可能显得急躁",
            "ex_per_1k": f"感叹号比目标多 {pct}，情绪外放，容易吵",
            "ellipsis_per_1k": f"省略号比目标多 {pct}，停顿多，人物说话更虚",
            "dash_per_1k": f"破折号比目标多 {pct}，插入语多，句子老被打断",
        }
    else:
        table = {
            "avg_sentence_len": f"你的句子比目标短 {pct}，读起来更碎、更赶",
            "median_sentence_len": f"你的中位句长比目标短 {pct}，几乎没有喘气的长句",
            "short_sentence_ratio": f"≤5 字短句比目标少 {abs_d} 个百分点，节奏起伏会变平",
            "long_sentence_ratio": f"≥30 字长句比目标少 {abs_d} 个百分点，铺陈和压迫感不够",
            "dialogue_ratio": f"对话段比目标少 {abs_d} 个百分点，叙事更闷、独白感更重",
            "para_avg_len": f"段落比目标短 {pct}，一行一行翻得快，但可能不够沉",
            "q_per_1k": f"问号密度比目标低 {pct}，交锋和悬念被压住了",
            "ex_per_1k": f"感叹号比目标少 {pct}，高潮可能不够响",
            "ellipsis_per_1k": f"省略号比目标少 {pct}，人物说话太干脆，缺犹豫",
            "dash_per_1k": f"破折号比目标少 {pct}，叙述更直，少了插话感",
        }
    return table[key]


def compare(draft: dict, target: dict) -> list[dict]:
    rows = []
    for key, label, unit, is_point in METRIC_DEFS:
        d = float(draft[key])
        t = float(target[key])
        delta = d - t
        if t > ZERO_TARGET_TOL:
            rel = delta / t * 100
        else:
            rel = 0.0

        flagged = False
        if key in ("dash_per_1k", "ex_per_1k", "ellipsis_per_1k", "q_per_1k") and t <= ZERO_TARGET_TOL:
            flagged = d > ZERO_TARGET_ABS
            direction = 1 if d > t else 0
        else:
            if t > ZERO_TARGET_TOL:
                flagged = abs(rel) > REL_TOL
                direction = 1 if delta > 0 else (-1 if delta < 0 else 0)
            else:
                flagged = False
                direction = 0
        # 百分点型的相对差用自身数值算，避免 0 目标
        if is_point and t > ZERO_TARGET_TOL:
            rel = delta / t * 100

        comment = human_comment(key, d, t, direction, rel, delta) if flagged else ""

        rows.append({
            "key": key,
            "label": label,
            "unit": unit,
            "draft": round(d, 2),
            "target": round(t, 2),
            "delta": round(delta, 2),
            "rel_pct": round(rel, 1),
            "direction": direction,
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


def fmt_num(key: str, value: float, unit: str) -> str:
    if unit == "%":
        return f"{value:.1f}%"
    if unit == "‰":
        return f"{value:.1f}‰"
    return f"{value:.1f} 字"


def render_check(draft_info: dict, target_name: str, target_entry: dict,
                 rows: list[dict], note: str = "") -> str:
    m = draft_info["metrics"]
    t = target_entry["metrics"]
    lines: list[str] = []
    lines.append("═" * 62)
    lines.append(f" 文风体检：{draft_info['name']}  vs  《{target_name}》")
    lines.append("═" * 62)
    lines.append(f" 稿子：{m['hanzi_count']:,} 汉字 · {m['sentence_count']:,} 句 · "
                 f"{m['paragraph_count']:,} 段")
    lines.append(f" 目标：第 {target_entry['chapters']} 章 · {t['hanzi_count']:,} 汉字 · "
                 f"{t['sentence_count']:,} 句（{target_entry['generated_at'][:10]} 建档）")
    if note:
        lines.append(f" 注意：{note}")
    lines.append("")

    header = ["指标", "你的稿子", "目标", "差距"]
    widths = [max(disp_width(header[0]), *(disp_width(r["label"]) for r in rows)),
              max(disp_width(header[1]), *(disp_width(fmt_num(r["key"], r["draft"], r["unit"])) for r in rows)),
              max(disp_width(header[2]), *(disp_width(fmt_num(r["key"], r["target"], r["unit"])) for r in rows)),
              14]
    lines.append(" " + " ".join(pad(h, w, "right" if i else "left")
                                for i, (h, w) in enumerate(zip(header, widths))))
    lines.append(" " + "─" * (sum(widths) + 3 * len(widths)))

    for r in rows:
        d_str = fmt_num(r["key"], r["draft"], r["unit"])
        t_str = fmt_num(r["key"], r["target"], r["unit"])
        if r["key"] in ("q_per_1k", "ex_per_1k", "ellipsis_per_1k",
                        "dash_per_1k", "avg_sentence_len", "median_sentence_len",
                        "para_avg_len") and r["target"] > ZERO_TARGET_TOL:
            gap = f"{r['rel_pct']:+.0f}%"
        elif r["unit"] == "%":
            gap = f"{r['delta']:+.1f} 点"
        else:
            gap = f"{r['delta']:+.1f}"
        mark = "⚠" if r["flagged"] else "✓"
        lines.append(" " + " ".join([
            pad(r["label"], widths[0]),
            pad(d_str, widths[1], "right"),
            pad(t_str, widths[2], "right"),
            pad(f"{gap} {mark}", widths[3], "right"),
        ]))

    flagged = [r for r in rows if r["flagged"]]
    lines.append("")
    if flagged:
        lines.append(f" ── 差距超过 {REL_TOL:.0f}% 的 {len(flagged)} 项 ──")
        for r in flagged:
            lines.append(f"  ⚠ {r['label']}：{r['comment']}")
    else:
        lines.append(f" ── 十项全部在 ±{REL_TOL:.0f}% 以内，文风很贴 ──")

    lines.append("")
    lines.append(f" 一句话：{summarize(flagged, draft_info['name'])}")
    return "\n".join(lines)


def summarize(flagged: list[dict], draft_name: str) -> str:
    if not flagged:
        return "十项都在目标区间里，可以直接往下写；剩下的是句子本身好不好看。"
    ranked = sorted(
        flagged,
        key=lambda r: abs(r["rel_pct"]) if r["target"] > ZERO_TARGET_TOL else 100.0,
        reverse=True,
    )
    top = ranked[:2]
    parts = []
    for r in top:
        if r["target"] <= ZERO_TARGET_TOL:
            parts.append(f"{r['label']}（目标几乎为零）")
        elif r["unit"] == "%":
            parts.append(f"{r['label']}（{r['delta']:+.1f} 点）")
        else:
            parts.append(f"{r['label']}（{r['rel_pct']:+.0f}%）")
    tail = "，先改这两项再谈味道。" if len(flagged) > 2 else "，改完再看一遍。"
    return "、".join(parts) + " 差得最多" + tail


# ---------------------------------------------------------------------------
# list 子命令
# ---------------------------------------------------------------------------

def cmd_list(args) -> None:
    data = load_profiles()
    profiles = data.get("profiles", {})
    if not profiles:
        print("还没有文风档案。先跑：")
        print("  python3 scripts/style.py profile --book 目标作品 --chapters 1-100")
        return

    print(f" 已有文风档案（{len(profiles)} 本）  ·  {PROFILE_PATH}")
    print(" " + "─" * 74)
    rows = []
    for name, entry in sorted(profiles.items()):
        m = entry.get("metrics", {})
        rows.append([
            name,
            f"[{entry.get('chapters', '?')}]",
            f"{entry.get('chapter_count', 0)} 章",
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


# ---------------------------------------------------------------------------
# check 主流程
# ---------------------------------------------------------------------------

def cmd_check(args) -> None:
    path = Path(args.file).expanduser()
    if not path.exists():
        fail(f"稿子不存在：{path}")
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
            "draft": {k: v for k, v in draft.items() if k != "punct_counts"},
            "target_metrics": target["metrics"],
            "metrics": rows,
            "flagged_count": len(flagged),
            "summary": summarize(flagged, path.name),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    draft_info = {"name": path.name, "metrics": draft}
    print(render_check(draft_info, args.target, target, rows, note=run_note))


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
            "  python3 scripts/style.py profile --book 目标作品 --chapters 1-100\n"
            "  python3 scripts/style.py check --file 我的章节.md --target 目标作品\n"
            "  python3 scripts/style.py check --file ch001.md --target 目标作品 --json\n"
            "  python3 scripts/style.py list\n\n"
            "统计口径:\n"
            "  只算正文（剔除 # 标题行、注释、空行）；按 。！？… 整串切句，换行也是边界；\n"
            "  句长与段落长只数汉字；对话段 = 含「」或“”的段落；\n"
            "  标点频率 = 次数 / 汉字数 × 1000，省略号与破折号按整串算一次。\n"
            "  这跟 novel-study 读书笔记的实测口径一致，档案可直接对照。\n"
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
                           help="书名、book_id 或缓存目录名，如 目标作品")
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
                         help="目标作者的书，如 目标作品（需先 profile）")
    p_check.add_argument("--json", action="store_true", help="输出 JSON，方便脚本消费")
    p_check.add_argument("--cache-dir", metavar="目录", help="书库缓存目录（一般不用给）")
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
