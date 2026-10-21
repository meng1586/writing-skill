#!/usr/bin/env python3
"""skill-reflect / log.py — 给某个 skill 追加一条「哪里不好用」的记录。

记录写到 data/usage/{skill}-{YYYY-MM-DD}.jsonl，一行一条 JSON：

    {"ts":"2026-10-20T21:58:33+02:00","skill":"novel-study",
     "stage":"笔记","issue":"重复太多",
     "suggestion":"0 节只写一次","impact":"high"}

示例：

    python3 skills/skill-reflect/scripts/log.py \\
        --skill novel-study --stage 笔记 \\
        --issue "重复太多" --suggestion "0 节只写一次" --impact high

只追加、不改写历史；同一文件多进程追加有 fcntl 锁保护。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - 非 POSIX 平台退化为无锁
    fcntl = None

IMPACTS = ("high", "medium", "low")
SKILL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = SKILL_DIR / "data" / "usage"


def display_path(path: Path) -> str:
    """优先显示相对当前目录的路径；跨目录太远时退回绝对路径。"""
    path = Path(path)
    try:
        rel = os.path.relpath(path, Path.cwd())
    except ValueError:
        return str(path)
    return rel if not rel.startswith("..") else str(path)


def parse_ts(value: str) -> datetime:
    """解析 ISO 8601 时间；无时区的按本地时区处理。"""
    text = value.strip()
    if not text:
        raise ValueError("空时间")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"不是合法的 ISO 8601 时间：{value!r}") from exc
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="log.py",
        description="追加一条 skill 使用问题记录（jsonl，只追加不改写）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python3 skills/skill-reflect/scripts/log.py \\\n"
            "      --skill novel-study --stage 笔记 \\\n"
            "      --issue \"重复太多\" --suggestion \"0 节只写一次\" --impact high\n\n"
            "记录文件：data/usage/{skill}-{YYYY-MM-DD}.jsonl（可用 --data-dir 改目录）"
        ),
    )
    parser.add_argument("--skill", required=True, help="skill 名，如 novel-study")
    parser.add_argument("--stage", default="未标注", help="出问题的环节，如 笔记 / 读正文 / 审查")
    parser.add_argument("--issue", required=True, help="问题是什么，如 重复太多")
    parser.add_argument("--suggestion", default="", help="建议怎么改，如 0 节只写一次")
    parser.add_argument(
        "--impact",
        choices=IMPACTS,
        default="medium",
        help="影响程度：high / medium / low（默认 medium）",
    )
    parser.add_argument(
        "--file",
        action="append",
        dest="files",
        metavar="PATH",
        help="受影响文件，可重复；不填时由 report.py 按 stage 推断",
    )
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR), help="记录目录（默认 data/usage）")
    parser.add_argument("--ts", default=None, help="补录时间，ISO 8601（默认现在）")
    parser.add_argument("--skill-version", default="", help="本次使用的 skill 版本或提交引用")
    parser.add_argument("--use-id", default="", help="一次真实使用的标识；同问题同次使用重复记录只计一次")
    parser.add_argument("--dry-run", action="store_true", help="只打印将写入的内容，不落盘")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    skill = args.skill.strip()
    if not SKILL_RE.match(skill):
        print(f"错误：--skill 只允许字母/数字/._-，收到：{skill!r}", file=sys.stderr)
        return 2

    stage = (args.stage or "").strip() or "未标注"
    issue = (args.issue or "").strip()
    if not issue:
        print("错误：--issue 不能为空", file=sys.stderr)
        return 2
    suggestion = (args.suggestion or "").strip()

    try:
        dt = parse_ts(args.ts) if args.ts else datetime.now().astimezone()
    except ValueError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    record = {
        "ts": dt.isoformat(timespec="seconds"),
        "skill": skill,
        "stage": stage,
        "issue": issue,
        "suggestion": suggestion,
        "impact": args.impact,
    }
    files = [f.strip() for f in (args.files or []) if f and f.strip()]
    if files:
        record["files"] = files
    for name in ("skill_version", "use_id"):
        value = getattr(args, name).strip()
        if value:
            record[name] = value

    data_dir = Path(args.data_dir).expanduser()
    path = data_dir / f"{skill}-{dt.date().isoformat()}.jsonl"

    if not args.dry_run:
        data_dir.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            if fcntl:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            finally:
                if fcntl:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    if args.json:
        print(
            json.dumps(
                {
                    "ok": True,
                    "dry_run": bool(args.dry_run),
                    "path": display_path(path),
                    "record": record,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    prefix = "将写入" if args.dry_run else "已记录 →"
    print(f"{prefix} {display_path(path)}")
    print(f"  {skill}｜stage={stage}｜issue={issue}｜impact={args.impact}")
    if suggestion:
        print(f"  建议：{suggestion}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
