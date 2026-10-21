#!/usr/bin/env python3
"""writeback.py — 写完回填：这一章用了哪条决策，效果如何

写作决策的试用状态：
  untested    — 尚未试用
  tried       — 已使用，尚无倾向性的对照结果
  conditional — 对照反馈中「好」多于「崩」，只在记录的条件下参考
  dropped     — 对照反馈中「崩」多于「好」，暂不采用
  no-diff     — 对照反馈中「好」「崩」均有记录且次数相同

每写完一章，把「用了哪条、效果如何、什么条件下」记一行，再跑 apply。
状态只汇总当前对照反馈的方向，不证明普遍有效；效果和条件保留在原始回填记录中。

用法：
  # 记一条：填写实际效果，未做对照就填 no
  python3 scripts/writeback.py add --chapter "示例作品第1章" --used D-001 \
      --effect "填写观察到的实际效果" --verdict 一般 --compared no

  # 一次用了几条，可以逗号分隔，也可以重复 --used
  python3 scripts/writeback.py add --chapter "示例作品第2章" --used D-001,D-002 \
      --effect "填写对照前后的差异" --verdict 好 --compared yes \
      --condition "填写本次有效的场景条件" --note "下次继续核对"

  # 看聚合：每条决策被用几次，好/一般/崩怎么分布
  python3 scripts/writeback.py report
  python3 scripts/writeback.py report --json

  # 回填到 decisions.json（先 dry-run 看会动哪几条）
  python3 scripts/writeback.py apply --dry-run
  python3 scripts/writeback.py apply

判定规则（apply）：
  没有「好」或「崩」的对照记录 → tried
  对照记录中 好 > 崩           → conditional
  对照记录中 崩 > 好           → dropped
  对照记录中 好 = 崩，且均非零 → no-diff
  没有使用记录                 → 保持原状态（默认 untested）

只依赖标准库。回填记录默认写 ../data/writebacks.jsonl（一行一条，只追加），
apply 默认改 ../../writing-decision/data/decisions.json。
"""
import argparse
import json
import os
import sys
import unicodedata
from collections import Counter, OrderedDict
from datetime import date, datetime

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_WRITEBACKS = os.path.join(SKILL_DIR, "data", "writebacks.jsonl")
DEFAULT_DECISIONS = os.path.normpath(
    os.path.join(SKILL_DIR, "..", "writing-decision", "data", "decisions.json")
)

VERDICTS = ["好", "一般", "崩"]
VERDICT_ALIASES = {
    "good": "好", "ok": "好", "nice": "好", "好": "好",
    "meh": "一般", "soso": "一般", "so-so": "一般", "一般": "一般",
    "bad": "崩", "broken": "崩", "崩": "崩",
}
VALID_STATUS = {"untested", "tried", "conditional", "dropped", "no-diff"}


class WritebackError(Exception):
    pass


def die(msg, code=2):
    print(f"writeback.py: {msg}", file=sys.stderr)
    sys.exit(code)


def today_iso():
    return date.today().isoformat()


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def display_width(text):
    """终端显示宽度：中日韩全角字符按 2 列算。"""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
               for ch in text)


def pad(text, width):
    return text + " " * max(0, width - display_width(text))


def split_ids(raw_list):
    """把 ['D-014,D-003', 'D-015'] 拆成 ['D-014', 'D-003', 'D-015']，去重保序。"""
    out, seen = [], set()
    for raw in raw_list or []:
        for part in raw.replace("，", ",").replace("、", ",").split(","):
            token = part.strip()
            if not token:
                continue
            if token not in seen:
                seen.add(token)
                out.append(token)
    return out


def normalize_verdict(raw):
    key = (raw or "").strip()
    verdict = VERDICT_ALIASES.get(key.lower(), VERDICT_ALIASES.get(key))
    if not verdict:
        die(f"verdict 只能是 {'/'.join(VERDICTS)}（收到：{raw!r}）")
    return verdict


def load_writebacks(path):
    """读 JSONL；坏行直接报错，避免悄悄丢记录。"""
    if not os.path.isfile(path):
        return []
    records = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                raise WritebackError(f"{path} 第 {lineno} 行不是合法 JSON：{exc}")
            if not isinstance(rec, dict) or not rec.get("used"):
                raise WritebackError(f"{path} 第 {lineno} 行缺 used 字段")
            records.append(rec)
    return records


def load_decisions(path):
    if not os.path.isfile(path):
        die(f"找不到决策数据：{path}")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        die(f"决策数据不是合法 JSON：{exc}")
    if not isinstance(data, dict):
        die(f"决策数据的根节点必须是对象，实际是 {type(data).__name__}")
    if "decisions" not in data:
        die("决策数据缺少 decisions 字段（空数组是合法的）")
    if not isinstance(data.get("decisions"), list):
        die("decisions 必须是数组")
    data.setdefault("combos", [])
    return data


def write_json_atomic(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def cmd_add(args):
    used = split_ids(args.used)
    if not used:
        die("--used 至少要给一个决策 ID，例如 --used D-014")
    verdict = normalize_verdict(args.verdict)
    if not args.chapter.strip():
        die("--chapter 不能为空")
    if not args.effect.strip():
        die("--effect 不能为空：写清楚这条决策在这一章的实际效果")

    # 决策 ID 写错时不拦路，但提醒一声
    decisions_path = args.decisions
    if os.path.isfile(decisions_path):
        known = {d["id"] for d in load_decisions(decisions_path)["decisions"]}
        unknown = [u for u in used if u not in known]
        if unknown:
            print(f"提醒：决策库里没有 {'、'.join(unknown)}，仍会记录，"
                  f"report/apply 会把它标为「未知」", file=sys.stderr)

    record = OrderedDict([
        ("ts", now_iso()),
        ("chapter", args.chapter.strip()),
        ("used", used),
        ("effect", args.effect.strip()),
        ("verdict", verdict),
    ])
    if getattr(args, "compared", ""):
        record["compared"] = args.compared
    if getattr(args, "condition", "") and args.condition.strip():
        record["condition"] = args.condition.strip()
    if args.note and args.note.strip():
        record["note"] = args.note.strip()

    path = args.writebacks
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    # 追加前先确认现有记录可读，避免坏文件越写越乱
    load_writebacks(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"已回填：{record['chapter']} · {'、'.join(used)} · {verdict}")
    print(f"记录：{path}")


def aggregate(records, decisions_by_id):
    """按决策聚合：uses / 好一般崩 / 章节 / 当前状态 / 建议状态。"""
    agg = {}
    for rec in records:
        verdict = normalize_verdict(rec.get("verdict", "一般"))
        for did in rec["used"]:
            item = agg.setdefault(did, {
                "id": did,
                "uses": 0,
                "verdicts": Counter(),
                "compared": Counter(),
                "chapters": [],
                "last_ts": "",
            })
            item["uses"] += 1
            item["verdicts"][verdict] += 1
            if str(rec.get("compared", "")).lower() in ("yes", "是", "true", "1"):
                item["compared"][verdict] += 1
            chapter = rec.get("chapter", "")
            if chapter and chapter not in item["chapters"]:
                item["chapters"].append(chapter)
            ts = rec.get("ts", "")
            if ts > item["last_ts"]:
                item["last_ts"] = ts

    rows = []
    for did in sorted(agg):
        item = agg[did]
        decision = decisions_by_id.get(did)
        current = (decision or {}).get("status", "untested")
        # 决策库里没有这条（多半是 ID 写错）：不给建议，apply 也会跳过
        suggestion = suggest_status(item.get("compared", Counter()), current, item["uses"] > 0) if decision else None
        rows.append({
            "id": did,
            "title": (decision or {}).get("title", ""),
            "uses": item["uses"],
            "verdicts": {v: item["verdicts"].get(v, 0) for v in VERDICTS},
            "chapters": item["chapters"],
            "last_ts": item["last_ts"],
            "current": current if decision else "未知",
            "suggestion": suggestion,
        })
    return rows


def suggest_status(compared_counts, current, any_use=True):
    """状态只由「做过对照试写」的记录决定；没做对照的只算 tried。
    反馈方向只对记录的条件负责，不证明普遍有效。"""
    good = compared_counts.get("好", 0)
    bad = compared_counts.get("崩", 0)
    if good + bad == 0:
        return "tried" if any_use else (current or "untested")
    if good > bad:
        return "conditional"
    if bad > good:
        return "dropped"
    return "no-diff"


def cmd_report(args):
    decisions = load_decisions(args.decisions)
    decisions_by_id = {d["id"]: d for d in decisions["decisions"]}
    try:
        records = load_writebacks(args.writebacks)
    except WritebackError as exc:
        die(str(exc))
    rows = aggregate(records, decisions_by_id)

    if args.json:
        payload = {
            "generated_at": now_iso(),
            "total_writebacks": len(records),
            "decisions_covered": len(rows),
            "decisions": rows,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if not rows:
        print(f"还没有回填记录（{args.writebacks}）。")
        print("写完一章后这样记：")
        print('  python3 scripts/writeback.py add --chapter "示例作品第1章" \\')
        print('      --used D-001 --effect "填写实际效果" --verdict 一般 --compared no')
        return

    header = ["决策", "次数", "好", "一般", "崩", "当前", "建议"]
    table = [header] + [
        [r["id"], str(r["uses"]), str(r["verdicts"]["好"]),
         str(r["verdicts"]["一般"]), str(r["verdicts"]["崩"]),
         r["current"], r["suggestion"] or "—"]
        for r in rows
    ]
    widths = [max(display_width(row[i]) for row in table) + 2
              for i in range(len(header))]

    print(f"回填报告：{len(records)} 条记录，覆盖 {len(rows)} 条决策")
    print()
    for row in table:
        print("".join(pad(cell, widths[i]) for i, cell in enumerate(row)).rstrip())

    pending = [r for r in rows if r["suggestion"] and r["suggestion"] != r["current"]]
    print()
    if pending:
        print(f"有 {len(pending)} 条决策的 status 可以更新：")
        for r in pending:
            print(f"  {r['id']}  {r['current']} → {r['suggestion']}"
                  f"（好 {r['verdicts']['好']} / 崩 {r['verdicts']['崩']}）")
        print("确认后跑：python3 scripts/writeback.py apply")
    else:
        print("没有需要改 status 的决策（回填还不够，或已经是最新）。")
    print()
    print(f"数据：{args.writebacks}")


def cmd_apply(args):
    decisions = load_decisions(args.decisions)
    try:
        records = load_writebacks(args.writebacks)
    except WritebackError as exc:
        die(str(exc))
    if not records:
        print("还没有回填记录，decisions.json 不动。")
        return

    decisions_by_id = {d["id"]: d for d in decisions["decisions"]}
    rows = aggregate(records, decisions_by_id)
    changes = []
    for row in rows:
        decision = decisions_by_id.get(row["id"])
        if decision is None:
            print(f"跳过 {row['id']}：决策库里没有这条（可能是 ID 写错）",
                  file=sys.stderr)
            continue
        old = decision.get("status", "untested")
        new = row["suggestion"]
        if new != old:
            changes.append((row["id"], old, new, row))

    if not changes:
        print("回填已生效，没有需要改的 status。")
        return

    print(f"{'[dry-run] ' if args.dry_run else ''}准备更新 {len(changes)} 条决策：")
    for did, old, new, row in changes:
        print(f"  {did}  {old} → {new}"
              f"（用了 {row['uses']} 次：好 {row['verdicts']['好']} / "
              f"一般 {row['verdicts']['一般']} / 崩 {row['verdicts']['崩']}）")
        if args.dry_run:
            continue
        decisions_by_id[did]["status"] = new

    if args.dry_run:
        print("dry-run：没有写入。去掉 --dry-run 才会改 decisions.json。")
        return

    decisions["updated"] = today_iso()
    write_json_atomic(args.decisions, decisions)
    print(f"已写回：{args.decisions}")
    print("决策库里的 status 已更新；下次 decide.py 会按新状态排序。")


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--writebacks", default=DEFAULT_WRITEBACKS, metavar="PATH",
        help=f"回填记录文件（默认 {DEFAULT_WRITEBACKS}）")
    common.add_argument(
        "--decisions", default=DEFAULT_DECISIONS, metavar="PATH",
        help=f"决策库 JSON（默认 {DEFAULT_DECISIONS}）")

    parser = argparse.ArgumentParser(
        prog="writeback.py",
        description="写完回填：记录每章用了哪条写作决策、效果如何，再把结果回填到决策库。",
        epilog=(
            "示例：\n"
            "  writeback.py add --chapter \"示例作品第1章\" --used D-001 "
            "--effect \"填写实际效果\" --verdict 一般 --compared no\n"
            "  writeback.py report --json\n"
            "  writeback.py apply --dry-run\n"
            "  writeback.py apply\n"
            "\n自测时可加 --writebacks/--decisions 指向临时副本，不动正式数据。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", metavar="命令")

    p_add = sub.add_parser(
        "add", parents=[common],
        help="追加一条回填记录",
        description="写完一章后记一条：这章用了哪条决策，效果如何。只追加，不改旧记录。",
    )
    p_add.add_argument("--chapter", required=True, metavar="书名第N章",
                       help='章节标识，例如 "示例作品第1章"')
    p_add.add_argument("--used", required=True, action="append", metavar="ID",
                       help="用到的决策 ID，可写多个：--used D-014,D-003，或重复 --used")
    p_add.add_argument("--effect", required=True, metavar="一句话",
                       help="实际效果，写具体的：哪里好、哪里过了、读者什么反应")
    p_add.add_argument("--verdict", required=True, metavar="好|一般|崩",
                       help="这条决策在这章的效果：好 / 一般 / 崩")
    p_add.add_argument("--compared", choices=("yes", "no"), default="", metavar="yes|no",
                       help="是否做过对照试写；未做对照只记为 tried，yes 的好/崩用于汇总反馈方向")
    p_add.add_argument("--condition", default="", metavar="有效条件",
                       help="记录本次效果成立的场景条件，保留在回填记录中")
    p_add.add_argument("--note", default="", metavar="备注",
                       help="可选：下次怎么调整")
    p_add.set_defaults(func=cmd_add)

    p_report = sub.add_parser(
        "report", parents=[common],
        help="按决策聚合：用了几次，好/一般/崩分布",
        description="汇总所有回填记录，按决策输出使用次数与好/一般/崩分布，并给出建议 status。",
    )
    p_report.add_argument("--json", action="store_true", help="输出 JSON，便于别的脚本消费")
    p_report.set_defaults(func=cmd_report)

    p_apply = sub.add_parser(
        "apply", parents=[common],
        help="把聚合结果回填到 decisions.json 的 status",
        description=(
            "按对照反馈汇总试用状态：好>崩 → conditional；崩>好 → dropped；"
            "好=崩且均非零 → no-diff；没有好/崩的对照记录 → tried。"
        ),
    )
    p_apply.add_argument("--dry-run", action="store_true",
                         help="只打印会改哪几条，不写文件")
    p_apply.set_defaults(func=cmd_apply)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
