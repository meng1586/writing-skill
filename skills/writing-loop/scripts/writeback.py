#!/usr/bin/env python3
"""记录使用与反馈；有可追溯的真人对照证据，才形成带条件的效果状态。

普通使用、作者自检、模型评审以及旧日志都保留为试用记录，不按好坏票数
判定效果。真人对照须注明两版引用、反馈引用、适用条件、明确比较结果，
并由记录者 --confirm-result 确认；这不证明普遍有效。

记录只追加；apply 先 --dry-run。自测可用 --writebacks/--decisions 指向临时文件。
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
VALID_STATUS.add("retired")
LEGACY_STATUS = {"derived": "untested", "verified": "untested", "rejected": "dropped"}
EFFECT_STATUS = {"conditional", "dropped", "no-diff", "retired"}
COMPARISON_RESULTS = {"better": "conditional", "worse": "dropped", "no-diff": "no-diff"}


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
            if (not isinstance(rec, dict) or not isinstance(rec.get("used"), list)
                    or not rec["used"] or any(not isinstance(i, str) or not i.strip() for i in rec["used"])):
                raise WritebackError(f"{path} 第 {lineno} 行 used 必须是非空决策 ID 数组")
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
    if not data.get("decisions"):
        die("决策数据里没有 decisions 数组")
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
    record["reviewer_type"] = args.reviewer_type
    for field in ("draft_a_ref", "draft_b_ref", "feedback_ref", "comparison_result"):
        value = getattr(args, field, "")
        if value and value.strip():
            record[field] = value.strip()
    if args.confirm_result:
        record["result_confirmed"] = True
    if args.note and args.note.strip():
        record["note"] = args.note.strip()

    path = args.writebacks
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    # 追加前先确认现有记录可读，避免坏文件越写越乱
    load_writebacks(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"已回填：{record['chapter']} · {'、'.join(used)} · {verdict}")
    if not qualified_evidence(record):
        print("作为使用/自检记录保留；不据此升级效果状态，也不阻塞继续写作。")
    print(f"记录：{path}")


def canonical_status(status):
    return LEGACY_STATUS.get(status, status if status in VALID_STATUS else "untested")


def qualified_evidence(record):
    """证据引用由记录者核实；未声明来源的旧记录不默认为真人反馈。"""
    refs = ("draft_a_ref", "draft_b_ref", "feedback_ref", "condition")
    return (record.get("reviewer_type") == "reader"
            and record.get("result_confirmed") is True
            and record.get("comparison_result") in COMPARISON_RESULTS
            and all(isinstance(record.get(k), str) and record[k].strip() for k in refs)
            and record["draft_a_ref"].strip() != record["draft_b_ref"].strip()
            and len(set(record.get("used", []))) == 1)


def evidence_summary(record):
    return {k: record.get(k, "") for k in (
        "ts", "chapter", "reviewer_type", "result_confirmed", "condition", "comparison_result",
        "draft_a_ref", "draft_b_ref", "feedback_ref"
    )}


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
                "evidence": [],
                "chapters": [],
                "last_ts": "",
            })
            item["uses"] += 1
            item["verdicts"][verdict] += 1
            if qualified_evidence(rec):
                summary = evidence_summary(rec)
                if summary not in item["evidence"]:
                    item["evidence"].append(summary)
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
        current = canonical_status((decision or {}).get("status", "untested"))
        existing = (decision or {}).get("effect_evidence", [])
        evidence = [e for e in existing if isinstance(e, dict) and e.get("comparison_result") in COMPARISON_RESULTS]
        evidence += [e for e in item["evidence"] if e not in evidence]
        # 决策库里没有这条（多半是 ID 写错）：不给建议，apply 也会跳过
        suggestion = suggest_status(evidence, current, item["uses"] > 0) if decision else None
        mixed = len({e["comparison_result"] for e in evidence}) > 1
        rows.append({
            "id": did,
            "title": (decision or {}).get("title", ""),
            "uses": item["uses"],
            "verdicts": {v: item["verdicts"].get(v, 0) for v in VERDICTS},
            "chapters": item["chapters"],
            "last_ts": item["last_ts"],
            "current": current if decision else "未知",
            "suggestion": suggestion,
            "effect_evidence": evidence,
            "effect_review_required": mixed,
        })
    return rows


def suggest_status(evidence, current, any_use=True):
    current = canonical_status(current)
    # 退役需要显式的单独处置，普通使用或新一条好评不得复活它。
    if current == "retired":
        return current
    results = {e["comparison_result"] for e in evidence}
    if len(results) == 1:
        return COMPARISON_RESULTS[next(iter(results))]
    # 相反结果需要看适用条件，不等于同一对照没有区别。
    if current in EFFECT_STATUS:
        return current
    return "tried" if any_use else current


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
        print('  python3 skills/writing-loop/scripts/writeback.py add --chapter "命烛第1章" \\')
        print('      --used D-014 --effect "手抖只写一处" --verdict 好')
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
    for row in rows:
        if row["effect_review_required"]:
            print(f"{row['id']}：真人对照结果不一致，保留各条件，需复核；不抵消为无差异。")

    pending = [r for r in rows if r["suggestion"] and r["suggestion"] != r["current"]]
    print()
    if pending:
        print(f"有 {len(pending)} 条决策的 status 可以更新：")
        for r in pending:
            print(f"  {r['id']}  {r['current']} → {r['suggestion']}"
                  f"（好 {r['verdicts']['好']} / 崩 {r['verdicts']['崩']}）")
        print("确认后跑：python3 skills/writing-loop/scripts/writeback.py apply")
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
        updated = dict(decision, status=new)
        if old in LEGACY_STATUS:
            updated.setdefault("legacy_status", old)
        if row["effect_evidence"] and old != "retired":
            existing = decision.get("effect_evidence", [])
            evidence = existing + [e for e in row["effect_evidence"] if e not in existing]
            updated["effect_evidence"] = evidence
            # 已保存的证据也参与冲突检查，防分批日志抹掉旧结论。
            results = {e.get("comparison_result") for e in evidence}
            updated["effect_review_required"] = len(results) > 1
            if len(results) > 1:
                updated["status"] = canonical_status(old) if canonical_status(old) in EFFECT_STATUS else "tried"
        if updated != decision:
            changes.append((row["id"], old, updated, row))

    if not changes:
        print("回填已生效，没有需要改的 status。")
        return

    print(f"{'[dry-run] ' if args.dry_run else ''}准备更新 {len(changes)} 条决策：")
    for did, old, updated, row in changes:
        print(f"  {did}  {old} → {updated['status']}"
              f"（用了 {row['uses']} 次：好 {row['verdicts']['好']} / "
              f"一般 {row['verdicts']['一般']} / 崩 {row['verdicts']['崩']}）")
        if args.dry_run:
            continue
        decisions_by_id[did].update(updated)

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
            "  python3 skills/writing-loop/scripts/writeback.py add --chapter \"命烛第1章\" --used D-014 "
            "--effect \"手抖太长了\" --verdict 一般\n"
            "  python3 skills/writing-loop/scripts/writeback.py report --json\n"
            "  python3 skills/writing-loop/scripts/writeback.py apply --dry-run\n"
            "  python3 skills/writing-loop/scripts/writeback.py apply\n"
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
                       help='章节标识，例如 "命烛第1章"')
    p_add.add_argument("--used", required=True, action="append", metavar="ID",
                       help="用到的决策 ID，可写多个：--used D-014,D-003，或重复 --used")
    p_add.add_argument("--effect", required=True, metavar="一句话",
                       help="实际效果，写具体的：哪里好、哪里过了、读者什么反应")
    p_add.add_argument("--verdict", required=True, metavar="好|一般|崩",
                       help="这条决策在这章的效果：好 / 一般 / 崩")
    p_add.add_argument("--compared", choices=("yes", "no"), default="", metavar="yes|no",
                       help="兼容旧记录的对照标记；单独 yes 不构成效果证据")
    p_add.add_argument("--condition", default="", metavar="有效条件",
                       help="如：人物想维持镇定、视角允许身体感受")
    p_add.add_argument("--reviewer-type", choices=("usage", "author", "model", "reader"), default="usage",
                       help="普通使用（默认）/ 作者自检 / 模型评审 / 真人读者；模型代理不能标 reader")
    p_add.add_argument("--draft-a-ref", default="", help="对照 A 稿的路径及版本或提交引用")
    p_add.add_argument("--draft-b-ref", default="", help="对照 B 稿的路径及版本或提交引用")
    p_add.add_argument("--feedback-ref", default="", help="真人反馈原话及具体位置的保存引用")
    p_add.add_argument("--comparison-result", choices=tuple(COMPARISON_RESULTS), default="",
                       help="本条技法在 B 相对 A 的明确结果：better / worse / no-diff")
    p_add.add_argument("--confirm-result", action="store_true",
                       help="记录者已核对上述版本、真人反馈、条件和对照结果；只适用于单条决策")
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
            "普通使用仅记 tried；有完整且明确确认的真人对照证据才更新带条件的效果状态。"
            "相反结果保留条件并标需复核；retired 不自动复活。"
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
