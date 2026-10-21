#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""novel-study 书架工具（使用约定见 ../CONTRACT.md）。

子命令：
    add     把一本书加进书架（key 唯一，重复 add 退出码 2）
    list    列出书架（可按状态过滤）
    log     追加一次研读记录（sessions 只追加，不改历史）
    next    按契约规则挑下一本该读/该继续的书
    judge   给已有书打分/改判（quality 0-5、verdict keep/watch/drop）
    report  统计报告（总量、近 N 天、进度、评分分布、待判、止损）
    recover 从 shelf.json.bak 恢复损坏的 shelf.json

约定：
- 仅用标准库；所有命令支持 --json（stdout 只输出一个 JSON 对象，日志走 stderr）。
- 写盘一律「临时文件 + os.replace」原子替换；替换前把最后一个好版本备份为
  shelf.json.bak。主文件损坏时不会用坏数据覆盖 .bak。
- 退出码：0 成功；2 用法错误 / 业务错误 / shelf.json 损坏；1 其它意外错误。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import tempfile
from pathlib import Path

SCHEMA_VERSION = 1
STATUSES = ("unread", "reading", "done", "dropped")
VERDICTS = ("keep", "watch", "drop")
DEFAULT_VERDICT = "watch"
QUALITY_UNRATED = 0
QUALITY_MAX = 5
DEFAULT_SETTINGS = {
    "daily_chapters": 3,
    "time_budget_min": 40,
    "retention_days": 30,
}
class ShelfError(Exception):
    """可预期的用户错误，统一映射到退出码 2。"""

    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------- 路径与结构


def project_root() -> Path:
    """skills/novel-study/scripts/shelf.py -> 项目根（写点小说/）。"""
    return Path(__file__).resolve().parents[3]


def default_shelf_path() -> Path:
    env = os.environ.get("NOVEL_STUDY_SHELF")
    if env:
        return Path(env).expanduser()
    return project_root() / "skills" / "novel-study" / "data" / "shelf.json"


def default_cache_dir() -> Path:
    env = os.environ.get("NOVEL_STUDY_CACHE")
    if env:
        return Path(env).expanduser()
    return project_root() / ".cache" / "novel-study" / "books"


def bak_path(path: Path) -> Path:
    return Path(str(path) + ".bak")


def today() -> str:
    return dt.date.today().isoformat()


def empty_shelf() -> dict:
    return {
        "version": SCHEMA_VERSION,
        "settings": dict(DEFAULT_SETTINGS),
        "books": [],
    }


def quality_stars(quality) -> str:
    """0/None 显示空星，1–5 显示实星。"""
    value = int(quality or 0)
    value = max(0, min(QUALITY_MAX, value))
    return "★" * value + "☆" * (QUALITY_MAX - value)


def quality_label(quality) -> str:
    return quality_stars(quality) if quality else "未评"


def _as_int(value, field: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ShelfError(f"字段 {field} 必须是整数，实际为 {value!r}")
    if minimum is not None and value < minimum:
        raise ShelfError(f"字段 {field} 不能小于 {minimum}，实际为 {value}")
    return value


def normalize_session(raw, book_key: str, index: int) -> dict:
    if not isinstance(raw, dict):
        raise ShelfError(f"{book_key}.sessions[{index}] 必须是对象")
    date = raw.get("date", "")
    try:
        dt.date.fromisoformat(str(date))
    except ValueError as exc:
        raise ShelfError(
            f"{book_key}.sessions[{index}].date 不是 YYYY-MM-DD：{date!r}"
        ) from exc
    chapters = raw.get("chapters")
    minutes = raw.get("minutes")
    if chapters is None and minutes is None:
        raise ShelfError(f"{book_key}.sessions[{index}] 至少要有一项记录")
    session = {
        "date": str(date),
        "chapters": _as_int(chapters or 0, f"{book_key}.sessions[{index}].chapters", minimum=0),
        "minutes": _as_int(minutes or 0, f"{book_key}.sessions[{index}].minutes", minimum=0),
        "note": str(raw.get("note") or ""),
    }
    return session


def normalize_book(raw, index: int) -> dict:
    if not isinstance(raw, dict):
        raise ShelfError(f"books[{index}] 必须是对象")
    key = raw.get("key")
    if not isinstance(key, str) or not key.strip():
        raise ShelfError(f"books[{index}].key 必须是非空字符串")
    status = raw.get("status", "unread")
    if status not in STATUSES:
        raise ShelfError(
            f"{key}.status 非法：{status!r}（只允许 {'/'.join(STATUSES)}）"
        )
    added = str(raw.get("added") or today())
    try:
        dt.date.fromisoformat(added)
    except ValueError as exc:
        raise ShelfError(f"{key}.added 不是 YYYY-MM-DD：{added!r}") from exc
    book = {
        "key": key,
        "name": str(raw.get("name") or key),
        "author": str(raw.get("author") or ""),
        "source": str(raw.get("source") or ""),
        "book_id": str(raw.get("book_id") or ""),
        "status": status,
        "added": added,
        "chapters_done": _as_int(raw.get("chapters_done", 0), f"{key}.chapters_done", minimum=0),
        "chapter_total": None,
        "local_dir": str(raw.get("local_dir") or ""),
        "tags": [],
        "sessions": [],
        "last_studied": raw.get("last_studied"),
        "quality": QUALITY_UNRATED,
        "verdict": DEFAULT_VERDICT,
        "verdict_reason": "",
    }
    total = raw.get("chapter_total")
    if total is not None:
        book["chapter_total"] = _as_int(total, f"{key}.chapter_total", minimum=1)
    quality = raw.get("quality")
    if quality is not None:
        book["quality"] = _as_int(quality, f"{key}.quality", minimum=QUALITY_UNRATED)
        if book["quality"] > QUALITY_MAX:
            raise ShelfError(f"{key}.quality 只允许 0–{QUALITY_MAX}，实际为 {book['quality']}")
    verdict = raw.get("verdict") or DEFAULT_VERDICT
    if verdict not in VERDICTS:
        raise ShelfError(f"{key}.verdict 非法：{verdict!r}（只允许 {'/'.join(VERDICTS)}）")
    book["verdict"] = verdict
    book["verdict_reason"] = str(raw.get("verdict_reason") or "")
    tags = raw.get("tags") or []
    if not isinstance(tags, list) or any(not isinstance(t, str) for t in tags):
        raise ShelfError(f"{key}.tags 必须是字符串列表")
    book["tags"] = list(tags)
    sessions = raw.get("sessions") or []
    if not isinstance(sessions, list):
        raise ShelfError(f"{key}.sessions 必须是列表")
    book["sessions"] = [normalize_session(s, key, i) for i, s in enumerate(sessions)]
    if book["last_studied"] is not None:
        try:
            dt.date.fromisoformat(str(book["last_studied"]))
        except ValueError as exc:
            raise ShelfError(f"{key}.last_studied 不是 YYYY-MM-DD") from exc
        book["last_studied"] = str(book["last_studied"])
    # 保留未知字段（向前兼容），已知字段以规范值为准。
    for extra_key, value in raw.items():
        if extra_key not in book:
            book[extra_key] = value
    return book


def normalize_shelf(data, source: str = "shelf.json") -> dict:
    if not isinstance(data, dict):
        raise ShelfError(f"{source} 顶层必须是 JSON 对象")
    version = data.get("version", SCHEMA_VERSION)
    if version != SCHEMA_VERSION:
        raise ShelfError(f"{source} version={version!r}，本工具只支持 version={SCHEMA_VERSION}")
    settings = dict(DEFAULT_SETTINGS)
    raw_settings = data.get("settings") or {}
    if not isinstance(raw_settings, dict):
        raise ShelfError(f"{source}.settings 必须是对象")
    for name in DEFAULT_SETTINGS:
        if name not in raw_settings:
            continue
        value = raw_settings[name]
        settings[name] = _as_int(value, f"settings.{name}", minimum=1)
    raw_books = data.get("books", [])
    if not isinstance(raw_books, list):
        raise ShelfError(f"{source}.books 必须是列表")
    books = [normalize_book(b, i) for i, b in enumerate(raw_books)]
    seen: set[str] = set()
    for book in books:
        if book["key"] in seen:
            raise ShelfError(f"{source} 中 key 重复：{book['key']}（schema 要求 key 唯一）")
        seen.add(book["key"])
    shelf = {"version": SCHEMA_VERSION, "settings": settings, "books": books}
    for extra_key, value in data.items():
        if extra_key not in shelf:
            shelf[extra_key] = value
    return shelf


# ---------------------------------------------------------------- 读 / 写


def load_shelf(path: Path) -> dict:
    """读取并校验书架。文件不存在时返回空书架（视作首次使用）。"""
    if not path.exists():
        return empty_shelf()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ShelfError(f"读取 {path} 失败：{exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        bak = bak_path(path)
        script = Path(__file__).resolve()
        hint = (
            f"；可运行 `python3 {script} recover --shelf {path}` 从 .bak 恢复"
            if bak.exists()
            else "；且没有可用的 .bak 备份"
        )
        raise ShelfError(
            f"{path} 不是合法 JSON（第 {exc.lineno} 行第 {exc.colno} 列：{exc.msg}）{hint}"
        ) from exc
    return normalize_shelf(data, source=str(path))


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def save_shelf(path: Path, shelf: dict) -> None:
    """原子保存；保存成功后把同一份好数据备份为 .bak。

    .bak 语义 =「最近一次成功保存的版本」，所以主文件被手改坏时，
    从 .bak 恢复不会丢掉最近一次写入。主文件已损坏时先留档为
    shelf.json.corrupt-<时间戳>，不静默丢弃证据。
    """
    payload = json.dumps(shelf, ensure_ascii=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # 主文件已损坏：留一份带时间戳的证据，再覆盖。
            stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            try:
                os.replace(path, str(path) + f".corrupt-{stamp}")
                log_stderr(f"原 {path.name} 已损坏，移存为 {path.name}.corrupt-{stamp}")
            except OSError:
                pass
    _atomic_write(path, payload)
    try:
        _atomic_write(bak_path(path), payload)
    except OSError as exc:
        log_stderr(f"备份 {bak_path(path).name} 失败（主文件已保存）：{exc}")


# ---------------------------------------------------------------- 输出


def log_stderr(message: str) -> None:
    print(message, file=sys.stderr)


class Output:
    """统一 --json / 人读两种输出。"""

    def __init__(self, as_json: bool):
        self.as_json = as_json

    def emit(self, payload: dict, human: str) -> None:
        if self.as_json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(human)


# ---------------------------------------------------------------- 业务


def load_meta(cache_dir: Path, key: str) -> dict | None:
    meta_path = cache_dir / key / "meta.json"
    if not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log_stderr(f"警告：{meta_path} 读取失败，跳过自动补全（{exc}）")
        return None
    return meta if isinstance(meta, dict) else None


def split_key(key: str) -> tuple[str, str]:
    """key = f"{source}-{book_id}"，按第一个 '-' 拆分。"""
    if "-" not in key:
        raise ShelfError(f"key 格式应为 '<source>-<book_id>'，实际为 {key!r}")
    source, book_id = key.split("-", 1)
    if not source or not book_id:
        raise ShelfError(f"key 格式应为 '<source>-<book_id>'，实际为 {key!r}")
    return source, book_id


def resolve_target(args) -> tuple[str, str, str]:
    """返回 (source, book_id, key)。--key 与 --source/--book-id 冲突时报错。"""
    if args.key:
        source, book_id = split_key(args.key)
        if args.source and args.source != source:
            raise ShelfError(
                f"--key={args.key} 里的 source 是 {source!r}，与 --source={args.source!r} 不一致"
            )
        if args.book_id and args.book_id != book_id:
            raise ShelfError(
                f"--key={args.key} 里的 book_id 是 {book_id!r}，与 --book-id={args.book_id!r} 不一致"
            )
        return source, book_id, args.key
    if not args.source or not args.book_id:
        raise ShelfError("add 需要 --source 和 --book-id（或直接给 --key）")
    return args.source, args.book_id, f"{args.source}-{args.book_id}"


def parse_tags(values) -> list[str]:
    tags: list[str] = []
    for raw in values or []:
        for piece in str(raw).replace("，", ",").replace("、", ",").split(","):
            piece = piece.strip()
            if piece and piece not in tags:
                tags.append(piece)
    return tags


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(project_root()))
    except ValueError:
        return str(path)


def progress(book: dict) -> float:
    total = book.get("chapter_total")
    if not total:
        return 0.0
    return min(1.0, max(0.0, book["chapters_done"] / total))


def progress_label(book: dict) -> str:
    total = book.get("chapter_total")
    if total:
        return f"{book['chapters_done']}/{total} ({progress(book) * 100:.1f}%)"
    return f"{book['chapters_done']}/? (未知总章数)"


def find_book(shelf: dict, key: str) -> dict:
    for book in shelf["books"]:
        if book["key"] == key:
            return book
    raise ShelfError(f"书架里没有这本书：{key}（先用 add 加入）")


def book_row(book: dict, settings: dict) -> dict:
    row = {
        "key": book["key"],
        "name": book["name"],
        "author": book["author"],
        "status": book["status"],
        "chapters_done": book["chapters_done"],
        "chapter_total": book.get("chapter_total"),
        "progress": round(progress(book), 4),
        "last_studied": book.get("last_studied"),
        "added": book["added"],
        "tags": list(book["tags"]),
        "quality": book["quality"],
        "quality_stars": quality_stars(book["quality"]),
        "verdict": book["verdict"],
        "verdict_reason": book["verdict_reason"],
    }
    if book["status"] == "reading":
        done = book["chapters_done"]
        row["next_chapters"] = {
            "from": done + 1,
            "to": done + settings["daily_chapters"],
        }
    return row


# ---------------------------------------------------------------- 子命令


def cmd_add(args, out: Output) -> int:
    source, book_id, key = resolve_target(args)
    cache_dir = Path(args.cache_dir).expanduser() if args.cache_dir else default_cache_dir()
    cache_dir = cache_dir.resolve()
    meta = load_meta(cache_dir, key)
    meta_filled: list[str] = []
    path = Path(args.shelf).expanduser() if args.shelf else default_shelf_path()

    name = args.name
    author = args.author
    chapter_total = args.chapter_total
    tags = parse_tags(args.tags)
    local_dir = display_path(cache_dir / key)

    if meta:
        if not name and meta.get("name"):
            name = str(meta["name"])
            meta_filled.append("name")
        if not author and meta.get("author"):
            author = str(meta["author"])
            meta_filled.append("author")
        if chapter_total is None and meta.get("chapter_total") is not None:
            try:
                chapter_total = int(meta["chapter_total"])
            except (TypeError, ValueError):
                log_stderr(f"警告：meta.json 的 chapter_total 不是整数：{meta['chapter_total']!r}，已忽略")
            else:
                if chapter_total < 1:
                    chapter_total = None
                else:
                    meta_filled.append("chapter_total")
        if not tags and meta.get("tags"):
            tags = [str(t) for t in meta["tags"]]
            meta_filled.append("tags")
        meta_filled.append("local_dir")

    if args.status and args.status not in STATUSES:
        raise ShelfError(f"--status 非法：{args.status!r}（只允许 {'/'.join(STATUSES)}）")
    if chapter_total is not None and chapter_total < 1:
        raise ShelfError("--chapter-total 必须 >= 1")
    quality = args.quality if args.quality is not None else QUALITY_UNRATED
    if not (QUALITY_UNRATED <= quality <= QUALITY_MAX):
        raise ShelfError(
            f"--quality 只允许 {QUALITY_UNRATED}–{QUALITY_MAX}（0 表示未评），实际为 {quality}"
        )
    verdict = args.verdict or DEFAULT_VERDICT
    if verdict not in VERDICTS:
        raise ShelfError(f"--verdict 非法：{verdict!r}（只允许 {'/'.join(VERDICTS)}）")
    verdict_reason = args.verdict_reason or ""
    if not name:
        raise ShelfError(
            f"缺少书名：没有找到 {cache_dir / key / 'meta.json'}，请补 --name"
        )

    added = args.added or today()
    try:
        dt.date.fromisoformat(added)
    except ValueError as exc:
        raise ShelfError(f"--added 不是 YYYY-MM-DD：{added!r}") from exc

    def mutate(shelf: dict) -> dict:
        if any(b["key"] == key for b in shelf["books"]):
            raise ShelfError(f"key 已存在：{key}（重复 add；sessions 请用 log 追加）")
        book = {
            "key": key,
            "name": name,
            "author": author or "",
            "source": source,
            "book_id": book_id,
            "status": args.status or "unread",
            "added": added,
            "chapters_done": 0,
            "chapter_total": chapter_total,
            "local_dir": local_dir,
            "tags": tags,
            "sessions": [],
            "last_studied": None,
            "quality": quality,
            "verdict": verdict,
            "verdict_reason": verdict_reason,
        }
        shelf["books"].append(book)
        return book

    book = mutate_loaded(path, mutate)
    human = (
        f"已加入书架：{book['name']}（{book['key']}）\n"
        f"  状态 {book['status']} · 总章数 {book['chapter_total'] or '未知'} · 标签 {', '.join(book['tags']) or '无'}\n"
        f"  质量 {quality_label(book['quality'])} · 判断 {book['verdict']}"
        + (f"（{book['verdict_reason']}）" if book["verdict_reason"] else "")
        + f"\n  缓存目录 {book['local_dir']}"
    )
    if meta_filled:
        human += f"\n  已从 meta.json 补全：{', '.join(dict.fromkeys(meta_filled))}"
    out.emit({"ok": True, "created": True, "book": book, "meta_filled": list(dict.fromkeys(meta_filled))}, human)
    return 0


def cmd_list(args, out: Output) -> int:
    path = Path(args.shelf).expanduser() if args.shelf else default_shelf_path()
    shelf = load_shelf(path)
    status_filter = args.status
    verdict_filter = args.verdict
    if status_filter and status_filter not in STATUSES:
        raise ShelfError(f"--status 非法：{status_filter!r}（只允许 {'/'.join(STATUSES)}）")
    if verdict_filter and verdict_filter not in VERDICTS:
        raise ShelfError(f"--verdict 非法：{verdict_filter!r}（只允许 {'/'.join(VERDICTS)}）")
    books = [
        b
        for b in shelf["books"]
        if (not status_filter or b["status"] == status_filter)
        and (not verdict_filter or b["verdict"] == verdict_filter)
    ]
    books.sort(key=lambda b: (b["added"], b["key"]))
    rows = [book_row(b, shelf["settings"]) for b in books]
    if not rows:
        if not shelf["books"]:
            human = "书架是空的。"
        else:
            filters = []
            if status_filter:
                filters.append(f"status={status_filter}")
            if verdict_filter:
                filters.append(f"verdict={verdict_filter}")
            human = "没有符合条件的书" + (f"（{'，'.join(filters)}）" if filters else "") + "。"
        out.emit({"ok": True, "count": 0, "books": []}, human)
        return 0
    header = f"书架共 {len(books)} 本"
    filters = []
    if status_filter:
        filters.append(f"status={status_filter}")
    if verdict_filter:
        filters.append(f"verdict={verdict_filter}")
    if filters:
        header += f"（{'，'.join(filters)}）"
    lines = [header + "："]
    for row in rows:
        mark = {"unread": "○", "reading": "▶", "done": "✓", "dropped": "✗"}[row["status"]]
        last = row["last_studied"] or "未研读"
        quality = row["quality_stars"] if row["quality"] else "未评"
        lines.append(
            f"  {mark} {row['name']}  [{row['status']}]  {quality} {row['verdict']}  "
            f"{progress_label(row)}  上次 {last}  {row['key']}"
        )
    out.emit({"ok": True, "count": len(rows), "books": rows}, "\n".join(lines))
    return 0


def cmd_log(args, out: Output) -> int:
    path = Path(args.shelf).expanduser() if args.shelf else default_shelf_path()
    if args.key:
        key = args.key
    elif args.source and args.book_id:
        key = f"{args.source}-{args.book_id}"
    else:
        raise ShelfError("log 需要 --key（或 --source 配 --book-id）")
    if args.chapters is None or args.minutes is None:
        raise ShelfError("log 需要 --chapters 和 --minutes")
    if args.chapters < 1:
        raise ShelfError("--chapters 必须 >= 1")
    if args.minutes < 0:
        raise ShelfError("--minutes 不能为负")
    date = args.date or today()
    try:
        dt.date.fromisoformat(date)
    except ValueError as exc:
        raise ShelfError(f"--date 不是 YYYY-MM-DD：{date!r}") from exc

    def mutate(shelf: dict) -> tuple[dict, dict, str | None]:
        book = find_book(shelf, key)
        session = {
            "date": date,
            "chapters": args.chapters,
            "minutes": args.minutes,
            "note": args.note or "",
        }
        book["sessions"].append(session)
        book["chapters_done"] += session["chapters"]
        book["last_studied"] = date
        warning = None
        if book["status"] == "unread":
            book["status"] = "reading"
        if book.get("chapter_total") and book["chapters_done"] > book["chapter_total"]:
            warning = (
                f"注意：已读 {book['chapters_done']} 章，超过登记总章数 {book['chapter_total']}；"
                "如已读完，可自行把 status 改为 done"
            )
        return book, session, warning

    book, session, warning = mutate_loaded(path, mutate)
    if warning:
        log_stderr(warning)
    human = (
        f"已记录：{book['name']} {session['date']} 研读 "
        f"{session['chapters']} 章 / {session['minutes']} 分钟"
        + (f"（{session['note']}）" if session["note"] else "")
        + f"\n  累计 {book['chapters_done']} 章，进度 {progress_label(book)}，状态 {book['status']}"
    )
    out.emit(
        {"ok": True, "book": book, "session": session, "warning": warning},
        human,
    )
    return 0


def cmd_judge(args, out: Output) -> int:
    path = Path(args.shelf).expanduser() if args.shelf else default_shelf_path()
    if not args.key:
        raise ShelfError("judge 需要 --key（bookKey）")
    if args.quality is None and args.verdict is None and args.verdict_reason is None:
        raise ShelfError("judge 至少给一项：--quality / --verdict / --verdict-reason")
    if args.quality is not None and not (QUALITY_UNRATED <= args.quality <= QUALITY_MAX):
        raise ShelfError(
            f"--quality 只允许 {QUALITY_UNRATED}–{QUALITY_MAX}（0 表示未评），实际为 {args.quality}"
        )
    if args.verdict is not None and args.verdict not in VERDICTS:
        raise ShelfError(f"--verdict 非法：{args.verdict!r}（只允许 {'/'.join(VERDICTS)}）")

    def mutate(shelf: dict) -> tuple[dict, dict]:
        book = find_book(shelf, args.key)
        changes: dict[str, dict] = {}
        for field, value in (
            ("quality", args.quality),
            ("verdict", args.verdict),
            ("verdict_reason", args.verdict_reason),
        ):
            if value is None or book[field] == value:
                continue
            changes[field] = {"from": book[field], "to": value}
            book[field] = value
        return book, changes

    book, changes = mutate_loaded(path, mutate)
    if not changes:
        human = (
            f"{book['name']} 的评分/判断没有变化"
            f"（quality={book['quality']}，verdict={book['verdict']}）。"
        )
    else:
        lines = [f"已更新：{book['name']}（{book['key']}）"]
        for field in ("quality", "verdict", "verdict_reason"):
            if field in changes:
                lines.append(f"  {field}: {changes[field]['from']!r} → {changes[field]['to']!r}")
        lines.append(
            f"  现在 {quality_label(book['quality'])} {book['verdict']}"
            f"（{book['verdict_reason'] or '无理由'}）"
        )
        human = "\n".join(lines)
    out.emit({"ok": True, "book": book, "changes": changes}, human)
    return 0


def sort_key_for_next(book: dict) -> tuple:
    # keep 优先于 watch；同类里 last_studied 越早越优先，再看进度比、加入时间、key。
    verdict_rank = 0 if book.get("verdict") == "keep" else 1
    last = book.get("last_studied") or ""
    return (verdict_rank, last, progress(book), book.get("added") or "", book["key"])


def cmd_next(args, out: Output) -> int:
    path = Path(args.shelf).expanduser() if args.shelf else default_shelf_path()
    shelf = load_shelf(path)
    settings = shelf["settings"]
    books = shelf["books"]
    rule = "reading 里先跳过 verdict=drop；keep 优先于 watch，同类按 last_studied 最早、同日期进度比最低"
    reading = [
        b for b in books if b["status"] == "reading" and b["verdict"] != "drop"
    ]
    if reading:
        book = sorted(reading, key=sort_key_for_next)[0]
        done = book["chapters_done"]
        payload = {
            "book": book,
            "reason": "reading",
            "rule": rule,
            "next_chapters": {"from": done + 1, "to": done + settings["daily_chapters"]},
            "settings": settings,
        }
        human = (
            f"下一本：{book['name']}（{book['key']}）\n"
            f"  质量 {quality_label(book['quality'])} · 判断 {book['verdict']}\n"
            f"  理由：reading 里 last_studied 最早（{book.get('last_studied') or '从未记录'}），"
            f"进度 {progress_label(book)}；已跳过 verdict=drop 的书\n"
            f"  下一批章节：第 {done + 1}–{done + settings['daily_chapters']} 章"
            f"（上限 {settings['daily_chapters']} 章 / {settings['time_budget_min']} 分钟）"
        )
        out.emit({"ok": True, **payload}, human)
        return 0
    unread = [
        b for b in books if b["status"] == "unread" and b["verdict"] != "drop"
    ]
    if unread:
        book = sorted(unread, key=sort_key_for_next)[0]
        payload = {
            "book": book,
            "reason": "unread",
            "rule": "没有可读的 reading 时取 unread 中 keep 优先、最早加入的一本",
            "next_chapters": {"from": 1, "to": settings["daily_chapters"]},
            "settings": settings,
        }
        human = (
            f"下一本：{book['name']}（{book['key']}）\n"
            f"  理由：书架没有可读的 reading，取 unread 中 keep 优先、最早加入的一本\n"
            f"  从第 1 章开始，今天读 1–{settings['daily_chapters']} 章"
        )
        out.emit({"ok": True, **payload}, human)
        return 0
    if not books:
        payload = {"book": None, "reason": "shelf_empty", "settings": settings}
        human = "书架没有可读的书（没有 reading 也没有 unread）。先用 add 加一本。"
    else:
        dropped = [
            b for b in books
            if b["status"] in ("reading", "unread") and b["verdict"] == "drop"
        ]
        if dropped:
            names = "、".join(f"《{b['name']}》" for b in dropped)
            payload = {"book": None, "reason": "all_dropped", "settings": settings}
            human = (
                f"没有可推的书：{names}已被判 drop（不值得学）。\n"
                f"  想反悔就 judge 改判，或 add 一本新书。"
            )
        else:
            payload = {"book": None, "reason": "no_candidate", "settings": settings}
            human = "没有可推的书：reading/unread 都读完了或没有，先用 add 加一本。"
    out.emit(payload, human)
    return 0


def cmd_report(args, out: Output) -> int:
    path = Path(args.shelf).expanduser() if args.shelf else default_shelf_path()
    shelf = load_shelf(path)
    settings = shelf["settings"]
    books = shelf["books"]
    by_status = {status: 0 for status in STATUSES}
    by_verdict = {verdict: 0 for verdict in VERDICTS}
    quality_counts = {"unrated": 0, **{str(i): 0 for i in range(1, QUALITY_MAX + 1)}}
    for book in books:
        by_status[book["status"]] += 1
        by_verdict[book["verdict"]] += 1
        if book["quality"]:
            quality_counts[str(book["quality"])] += 1
        else:
            quality_counts["unrated"] += 1
    total_chapters = sum(b["chapters_done"] for b in books)
    total_minutes = sum(s["minutes"] for b in books for s in b["sessions"])
    total_sessions = sum(len(b["sessions"]) for b in books)

    days = settings["retention_days"]
    since = dt.date.today() - dt.timedelta(days=days - 1)
    recent_chapters = 0
    recent_minutes = 0
    recent_sessions = 0
    for book in books:
        for session in book["sessions"]:
            if dt.date.fromisoformat(session["date"]) >= since:
                recent_chapters += session["chapters"]
                recent_minutes += session["minutes"]
                recent_sessions += 1

    stale = []
    for book in books:
        last = book.get("last_studied")
        if not last:
            # 从未研读的书用加入日期判断，避免刚 add 就被说「久未研读」。
            added = dt.date.fromisoformat(book["added"])
            if book["status"] in ("reading", "unread") and added < since:
                stale.append(
                    {
                        "key": book["key"],
                        "name": book["name"],
                        "last_studied": None,
                        "added": book["added"],
                    }
                )
        elif dt.date.fromisoformat(last) < since:
            stale.append({"key": book["key"], "name": book["name"], "last_studied": last})

    pending_judge = [
        {
            "key": b["key"],
            "name": b["name"],
            "status": b["status"],
            "chapters_done": b["chapters_done"],
        }
        for b in books
        if not b["quality"] and b["status"] in ("reading", "done")
    ]
    dropped = [
        {"key": b["key"], "name": b["name"], "verdict_reason": b["verdict_reason"]}
        for b in books
        if b["verdict"] == "drop"
    ]

    rows = []
    for book in sorted(books, key=lambda b: (b.get("last_studied") or "", b["key"])):
        rows.append(
            {
                **book_row(book, settings),
                "sessions": len(book["sessions"]),
                "minutes": sum(s["minutes"] for s in book["sessions"]),
            }
        )

    hints = []
    candidates = [
        b for b in books if b["status"] == "reading" and b["verdict"] != "drop"
    ]
    if candidates:
        next_book = sorted(candidates, key=sort_key_for_next)[0]
        hints.append(
            f"今天建议继续《{next_book['name']}》第 {next_book['chapters_done'] + 1}–"
            f"{next_book['chapters_done'] + settings['daily_chapters']} 章"
        )
    if pending_judge:
        names = "、".join(f"《{b['name']}》" for b in pending_judge[:3])
        hints.append(f"{len(pending_judge)} 本已读但没评分（{names}），用 judge 打分：0–5")
    if dropped:
        hints.append(f"已止损 {len(dropped)} 本（verdict=drop），next 不会推它们")
    if by_status["unread"]:
        hints.append(f"书架里还有 {by_status['unread']} 本 unread，等 reading 清空后自动轮换")
    if stale:
        hints.append(f"{len(stale)} 本超过 {days} 天没研读，可考虑 dropped 或安排回看")

    payload = {
        "ok": True,
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "shelf": display_path(path),
        "settings": settings,
        "totals": {
            "books": len(books),
            "by_status": by_status,
            "by_verdict": by_verdict,
            "chapters_done": total_chapters,
            "minutes": total_minutes,
            "sessions": total_sessions,
        },
        "quality_distribution": quality_counts,
        "recent": {
            "days": days,
            "since": since.isoformat(),
            "chapters": recent_chapters,
            "minutes": recent_minutes,
            "sessions": recent_sessions,
        },
        "books": rows,
        "pending_judge": pending_judge,
        "dropped": dropped,
        "stale": stale,
        "hints": hints,
    }

    quality_line = " · ".join(
        [f"未评 {quality_counts['unrated']}"]
        + [f"★{i} {quality_counts[str(i)]}" for i in range(1, QUALITY_MAX + 1)]
    )
    lines = [
        f"书架报告（{dt.date.today().isoformat()}）",
        f"  书 {len(books)} 本 · "
        f"unread {by_status['unread']} / reading {by_status['reading']} / "
        f"done {by_status['done']} / dropped {by_status['dropped']}",
        f"  判断 keep {by_verdict['keep']} / watch {by_verdict['watch']} / drop {by_verdict['drop']}",
        f"  评分 {quality_line}",
        f"  累计 {total_chapters} 章 · {total_minutes} 分钟 · {total_sessions} 次研读",
        f"  近 {days} 天：{recent_chapters} 章 · {recent_minutes} 分钟 · {recent_sessions} 次",
    ]
    if rows:
        lines.append("")
        lines.append("进度：")
        for row in rows:
            quality = row["quality_stars"] if row["quality"] else "未评"
            lines.append(
                f"  {row['name']} [{row['status']}] {quality} {row['verdict']}"
                f" · {progress_label(row)}"
                f" · {row['sessions']} 次 / {row['minutes']} 分钟"
                f" · 上次 {row['last_studied'] or '未研读'}"
            )
    if pending_judge:
        lines.append("")
        lines.append("待判：")
        for item in pending_judge:
            read_state = (
                f"已读 {item['chapters_done']} 章" if item["chapters_done"] else "还没读"
            )
            lines.append(f"  {item['name']}（{read_state}，未评分）")
    if dropped:
        lines.append("")
        lines.append("已止损：")
        for item in dropped:
            lines.append(f"  {item['name']}（{item['verdict_reason'] or '无理由'}）")
    if hints:
        lines.append("")
        lines.append("建议：")
        lines.extend(f"  - {hint}" for hint in hints)
    out.emit(payload, "\n".join(lines))
    return 0


def cmd_recover(args, out: Output) -> int:
    path = Path(args.shelf).expanduser() if args.shelf else default_shelf_path()
    bak = bak_path(path)
    if not path.exists():
        raise ShelfError(f"{path} 不存在，没有可恢复的对象")
    if not bak.exists():
        raise ShelfError(f"{bak} 不存在，无法恢复")
    try:
        data = json.loads(bak.read_text(encoding="utf-8"))
        shelf = normalize_shelf(data, source=str(bak))
    except (OSError, json.JSONDecodeError) as exc:
        raise ShelfError(f"备份 {bak} 也损坏了：{exc}") from exc
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    corrupt = Path(str(path) + f".corrupt-{stamp}")
    try:
        os.replace(path, corrupt)
    except OSError as exc:
        raise ShelfError(f"无法移走损坏文件 {path}：{exc}") from exc
    _atomic_write(path, json.dumps(shelf, ensure_ascii=False, indent=2) + "\n")
    human = (
        f"已从备份恢复：{display_path(path)}\n"
        f"  书 {len(shelf['books'])} 本；损坏文件留档 {display_path(corrupt)}\n"
        f"  注意：已恢复到最近一次成功保存的状态；之后手改过的内容需重新补录"
    )
    out.emit(
        {
            "ok": True,
            "shelf": display_path(path),
            "books": len(shelf["books"]),
            "corrupt_saved": display_path(corrupt),
        },
        human,
    )
    return 0


def mutate_loaded(path: Path, mutate):
    """读 -> 改 -> 原子保存。单进程 CLI，并发冲突靠「最后写入者生效」兜底。"""
    shelf = load_shelf(path)
    result = mutate(shelf)
    save_shelf(path, shelf)
    return result


# ---------------------------------------------------------------- CLI


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--shelf",
        default=argparse.SUPPRESS,
        help="shelf.json 路径（默认 skills/novel-study/data/shelf.json，可用 NOVEL_STUDY_SHELF 覆盖）",
    )
    common.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help="stdout 只输出一个 JSON 对象",
    )

    parser = argparse.ArgumentParser(
        prog="shelf.py",
        description="novel-study 书架：add / list / log / judge / next / report / recover",
        epilog="使用约定见 skills/novel-study/CONTRACT.md；写盘为原子替换并保留 shelf.json.bak。",
    )
    parser.add_argument(
        "--shelf",
        default=None,
        help="shelf.json 路径（默认 skills/novel-study/data/shelf.json，也可用 NOVEL_STUDY_SHELF）",
    )
    parser.add_argument("--json", action="store_true", help="stdout 只输出一个 JSON 对象")
    sub = parser.add_subparsers(dest="command", metavar="命令")

    def add_parser(name: str, help_text: str, parents=(common,)) -> argparse.ArgumentParser:
        return sub.add_parser(name, parents=list(parents), help=help_text)

    # add
    p_add = add_parser("add", "把一本书加进书架（key 唯一）")
    p_add.add_argument("--source", help="来源，例如 fanqie / tianxi")
    p_add.add_argument("--book-id", help="来源内的书号")
    p_add.add_argument("--key", help="直接给 bookKey（source-book_id），可替代 --source/--book-id")
    p_add.add_argument("--name", help="书名；meta.json 存在时可省略")
    p_add.add_argument("--author", help="作者；meta.json 存在时可省略")
    p_add.add_argument("--tags", action="append", help="标签，逗号分隔，可重复")
    p_add.add_argument("--chapter-total", type=int, help="总章数；meta.json 存在时可省略")
    p_add.add_argument("--status", choices=STATUSES, help="初始状态，默认 unread")
    p_add.add_argument("--quality", type=int, help="质量 0–5（0 表示未评），默认 0")
    p_add.add_argument(
        "--verdict", choices=VERDICTS, help="判断 keep/watch/drop，默认 watch"
    )
    p_add.add_argument("--verdict-reason", help="判断理由，一句话")
    p_add.add_argument("--added", help="加入日期 YYYY-MM-DD，默认今天")
    p_add.add_argument("--cache-dir", help="抓取缓存目录（默认 .cache/novel-study/books）")
    p_add.set_defaults(func=cmd_add)

    # list
    p_list = add_parser("list", "列出书架")
    p_list.add_argument("--status", choices=STATUSES, help="只看某个状态")
    p_list.add_argument("--verdict", choices=VERDICTS, help="只看某个判断")
    p_list.set_defaults(func=cmd_list)

    # log
    p_log = add_parser("log", "追加一次研读记录")
    p_log.add_argument("--key", help="bookKey")
    p_log.add_argument("--source", help="配合 --book-id 定位")
    p_log.add_argument("--book-id", help="配合 --source 定位")
    p_log.add_argument("--chapters", type=int, help="本次读了几章")
    p_log.add_argument("--minutes", type=int, help="本次花了几分钟")
    p_log.add_argument("--note", default="", help="一句话记录，例如「开篇钩子分析」")
    p_log.add_argument("--date", help="研读日期 YYYY-MM-DD，默认今天")
    p_log.set_defaults(func=cmd_log)

    # judge
    p_judge = add_parser("judge", "给已有书打分/改判（可只改一项）")
    p_judge.add_argument("--key", required=True, help="bookKey")
    p_judge.add_argument("--quality", type=int, help="质量 0–5（0 表示未评）")
    p_judge.add_argument("--verdict", choices=VERDICTS, help="keep/watch/drop")
    p_judge.add_argument("--verdict-reason", help="判断理由，一句话")
    p_judge.set_defaults(func=cmd_judge)

    # next
    p_next = add_parser("next", "挑下一本该读/该继续的书")
    p_next.set_defaults(func=cmd_next)

    # report
    p_report = add_parser("report", "统计报告（评分分布、待判、止损）")
    p_report.set_defaults(func=cmd_report)

    # recover
    p_recover = add_parser("recover", "从 shelf.json.bak 恢复损坏的 shelf.json")
    p_recover.set_defaults(func=cmd_recover)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 2
    out = Output(args.json)
    try:
        return args.func(args, out)
    except ShelfError as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
            print(str(exc), file=sys.stderr)
        else:
            print(f"错误：{exc}", file=sys.stderr)
        return exc.code
    except KeyboardInterrupt:
        print("已中断", file=sys.stderr)
        return 130
    except OSError as exc:
        print(f"错误：文件操作失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
