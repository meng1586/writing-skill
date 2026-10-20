#!/usr/bin/env python3
"""skill-reflect / report.py — 聚合使用记录，出 skill 改进报告。

做什么：

- 扫 `data/usage/*.jsonl`，按 `skill + issue` 聚合（issue 去空白/标点，少量同义词合并）
- 同类 issue 证据 ≥ 阈值（默认 3）→ 状态「待改」
- 输出 markdown：问题排行、证据条数、建议改动、受影响文件；`--json` 给机器读

用法：

    python3 skills/skill-reflect/scripts/report.py
    python3 skills/skill-reflect/scripts/report.py --skill novel-study
    python3 skills/skill-reflect/scripts/report.py --threshold 2
    python3 skills/skill-reflect/scripts/report.py --json
    python3 skills/skill-reflect/scripts/report.py --out .cache/skill-reflect/report.md
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

DEFAULT_THRESHOLD = 3
IMPACTS = ("high", "medium", "low")
IMPACT_WEIGHT = {"high": 3, "medium": 2, "low": 1, "unknown": 0}
REQUIRED = ("ts", "skill", "stage", "issue", "impact")

# 归一化后仍写法不同的少量同义词；只做精确合并，不做模糊匹配，避免误并。
ISSUE_ALIASES = {
    "重复": "重复太多",
    "内容重复": "重复太多",
    "重复内容": "重复太多",
    "太慢": "慢",
    "速度慢": "慢",
    "读得慢": "慢",
    "跑得慢": "慢",
    "太贵": "token太贵",
    "贵": "token太贵",
    "token贵": "token太贵",
}

# stage 关键词 → 该 skill 里最可能需要改的文件（相对 skills/{skill}/）。
# 只在日志没带 files 时用来兜底推断，报告里会明确标出。
FILE_HINTS = {
    "novel-study": [
        (("笔记",), ["data/notes/*.md", "references/note-template.md"]),
        (("前情", "提要"), ["data/notes/*-前情提要.md", "references/read-cycle.md"]),
        (("读正文", "阅读", "读章"), ["references/read-cycle.md", "scripts/fetch.py"]),
        (("抓取", "下载", "补抓"), ["scripts/fetch.py", "config.json"]),
        (("选书", "书架", "评级"), ["data/shelf.json", "references/选书标准.md", "scripts/shelf.py"]),
        (("规则", "蒸馏"), ["data/rules/*.md", "references/rules-guide.md"]),
        (("写作前", "复用", "apply"), ["scripts/apply.py"]),
        (("计划", "调度", "提醒"), ["scripts/plan.py", "scripts/study_daemon.sh"]),
    ],
    "*": [
        (("笔记", "记录"), ["SKILL.md"]),
        (("审查", "review"), ["SKILL.md"]),
        (("输出", "排版", "格式", "太长"), ["SKILL.md"]),
        (("盲测", "蒸馏", "文风"), ["SKILL.md"]),
        (("场景", "描写"), ["SKILL.md"]),
        (("命令", "脚本"), ["scripts/", "SKILL.md"]),
    ],
}

STRIP_CHARS = " \t\r\n。，、！？；：,.!?;:()（）[]【】\"'“”‘’<>《》"


# ---------------------------------------------------------------------------
# 读记录
# ---------------------------------------------------------------------------


@dataclass
class Record:
    ts: datetime
    skill: str
    stage: str
    issue: str
    suggestion: str
    impact: str
    files: list = field(default_factory=list)
    source: str = ""

    @property
    def ts_text(self) -> str:
        return self.ts.strftime("%Y-%m-%d %H:%M")


def display_path(path: Path) -> str:
    path = Path(path)
    try:
        rel = os.path.relpath(path, Path.cwd())
    except ValueError:
        return str(path)
    return rel if not rel.startswith("..") else str(path)


def parse_ts(value) -> datetime:
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt


def issue_key(text: str) -> str:
    """归一化 issue：去所有空白、首尾标点、ASCII 转小写，再套同义词表。"""
    s = re.sub(r"\s+", "", str(text)).strip(STRIP_CHARS).lower()
    return ISSUE_ALIASES.get(s, s)


def display_issue(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


def load_records(data_dir: Path):
    """返回 (records, bad_lines, dir_exists)。坏行跳过并记录，不中断。"""
    records: list[Record] = []
    bad: list[dict] = []
    exists = data_dir.is_dir()
    if not exists:
        return records, bad, exists

    for path in sorted(data_dir.glob("*.jsonl")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            bad.append({"path": str(path), "line": 0, "error": f"读取失败：{exc}", "preview": ""})
            continue

        for lineno, raw in enumerate(lines, 1):
            text = raw.strip()
            if not text:
                continue
            try:
                obj = json.loads(text)
            except json.JSONDecodeError as exc:
                bad.append(
                    {
                        "path": str(path),
                        "line": lineno,
                        "error": f"JSON 解析失败：{exc.msg}",
                        "preview": text[:120],
                    }
                )
                continue
            if not isinstance(obj, dict):
                bad.append(
                    {"path": str(path), "line": lineno, "error": "不是 JSON 对象", "preview": text[:120]}
                )
                continue

            missing = [k for k in REQUIRED if not str(obj.get(k, "")).strip()]
            if missing:
                bad.append(
                    {
                        "path": str(path),
                        "line": lineno,
                        "error": "缺字段：" + ",".join(missing),
                        "preview": text[:120],
                    }
                )
                continue

            try:
                ts = parse_ts(obj["ts"])
            except ValueError as exc:
                bad.append(
                    {"path": str(path), "line": lineno, "error": f"ts 非法：{exc}", "preview": text[:120]}
                )
                continue

            impact = str(obj["impact"]).strip().lower()
            if impact not in IMPACTS:
                impact = "unknown"

            files = obj.get("files") or obj.get("file") or []
            if isinstance(files, str):
                files = [files]
            if not isinstance(files, list):
                files = []
            files = [str(f).strip() for f in files if str(f).strip()]

            records.append(
                Record(
                    ts=ts,
                    skill=str(obj["skill"]).strip(),
                    stage=str(obj["stage"]).strip(),
                    issue=str(obj["issue"]).strip(),
                    suggestion=str(obj.get("suggestion") or "").strip(),
                    impact=impact,
                    files=files,
                    source=path.name,
                )
            )

    return records, bad, exists


# ---------------------------------------------------------------------------
# 聚合
# ---------------------------------------------------------------------------


@dataclass
class IssueGroup:
    skill: str
    key: str
    display: str
    records: list = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.records)

    @property
    def impacts(self) -> dict:
        counter = Counter(r.impact for r in self.records)
        return {k: counter.get(k, 0) for k in ("high", "medium", "low", "unknown")}

    @property
    def high_count(self) -> int:
        return self.impacts["high"]

    @property
    def impact_score(self) -> int:
        return sum(IMPACT_WEIGHT.get(r.impact, 0) for r in self.records)

    @property
    def stages(self) -> Counter:
        return Counter(r.stage for r in self.records)

    @property
    def suggestions(self) -> list:
        out, seen = [], set()
        for r in sorted(self.records, key=lambda x: x.ts):
            s = re.sub(r"\s+", " ", r.suggestion).strip()
            if s and s not in seen:
                seen.add(s)
                out.append(s)
        return out

    @property
    def explicit_files(self) -> list:
        out, seen = [], set()
        for r in self.records:
            for f in r.files:
                if f not in seen:
                    seen.add(f)
                    out.append(f)
        return out

    @property
    def last_ts(self) -> datetime:
        return max(r.ts for r in self.records)

    @property
    def first_ts(self) -> datetime:
        return min(r.ts for r in self.records)

    def status(self, threshold: int) -> str:
        return "待改" if self.count >= threshold else "观察中"


def group_records(records: list) -> list:
    groups: dict = {}
    for r in records:
        key = (r.skill, issue_key(r.issue))
        group = groups.get(key)
        if group is None:
            group = IssueGroup(skill=r.skill, key=key[1], display=display_issue(r.issue))
            groups[key] = group
        group.records.append(r)
    return list(groups.values())


def group_sort_key(group: IssueGroup, threshold: int) -> tuple:
    return (
        0 if group.count >= threshold else 1,
        -group.count,
        -group.high_count,
        -group.impact_score,
        -group.last_ts.timestamp(),
    )


def sort_groups(groups: list, threshold: int) -> list:
    return sorted(groups, key=lambda g: group_sort_key(g, threshold))


def resolve_files(group: IssueGroup) -> list:
    """受影响文件：日志显式给的优先，再按 stage 兜底推断，最后落到 SKILL.md。"""
    out, seen = [], set()

    def add(p):
        p = str(p).strip()
        if not p:
            return
        if not (p.startswith("skills/") or p.startswith("/")):
            p = f"skills/{group.skill}/{p}"
        if p not in seen:
            seen.add(p)
            out.append(p)

    for f in group.explicit_files:
        add(f)

    rules = FILE_HINTS.get(group.skill, []) + FILE_HINTS.get("*", [])
    for stage, _count in group.stages.most_common():
        for keywords, paths in rules:
            if any(k and (k in stage or stage in k) for k in keywords):
                for p in paths:
                    add(p)

    if not out:
        add("SKILL.md")
    return out


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------


def cell(text) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def fmt_impacts(impacts: dict) -> str:
    parts = [f"{k} {v}" for k, v in impacts.items() if v]
    return " / ".join(parts) if parts else "（无）"


def fmt_counter(counter: Counter) -> str:
    if not counter:
        return "（无）"
    return "、".join(f"{k} {v}" for k, v in counter.most_common())


def render_markdown(groups: list, records: list, bad: list, threshold: int, top: int, generated: datetime, data_dir: Path) -> str:
    lines = []
    skills: dict = {}
    for g in groups:
        skills.setdefault(g.skill, []).append(g)

    skill_rows = []
    for skill, gs in skills.items():
        skill_rows.append(
            {
                "skill": skill,
                "records": sum(g.count for g in gs),
                "issues": len(gs),
                "pending": sum(1 for g in gs if g.count >= threshold),
                "high": sum(g.high_count for g in gs),
            }
        )
    skill_rows.sort(key=lambda x: (-x["pending"], -x["records"], x["skill"]))

    pending_total = sum(1 for g in groups if g.count >= threshold)
    high_total = sum(g.high_count for g in groups)

    lines.append("# Skill 改进报告")
    lines.append("")
    lines.append(f"- 生成时间：{generated.strftime('%Y-%m-%d %H:%M %z')}")
    lines.append(f"- 数据目录：`{display_path(data_dir)}`")
    lines.append(
        f"- 记录：{len(records)} 条｜Skill：{len(skill_rows)} 个｜问题类型：{len(groups)} 类｜待改：{pending_total}"
    )
    lines.append(f"- 判定阈值：同类问题 ≥{threshold} 条证据｜高影响记录：{high_total} 条")
    if bad:
        lines.append(f"- 坏行：{len(bad)} 条（已跳过，见文末）")
    lines.append("")

    # 总览
    lines.append("## 总览")
    lines.append("")
    if skill_rows:
        lines.append("| Skill | 记录 | 问题类型 | 待改 | 观察中 | 高影响 |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for row in skill_rows:
            lines.append(
                f"| {cell(row['skill'])} | {row['records']} | {row['issues']} | "
                f"{row['pending']} | {row['issues'] - row['pending']} | {row['high']} |"
            )
    else:
        lines.append("（还没有记录）")
    lines.append("")

    # 问题排行
    lines.append("## 问题排行")
    lines.append("")
    ranked = sort_groups(groups, threshold)
    shown = ranked[:top] if top > 0 else ranked
    if shown:
        lines.append("| # | Skill | 问题 | 证据 | 高影响 | 状态 |")
        lines.append("|---:|---|---|---:|---:|---|")
        for i, g in enumerate(shown, 1):
            lines.append(
                f"| {i} | {cell(g.skill)} | {cell(g.display)} | {g.count} | {g.high_count} | {g.status(threshold)} |"
            )
        if len(shown) < len(ranked):
            lines.append("")
            lines.append(f"> 只显示前 {len(shown)} 条，共 {len(ranked)} 条。")
    else:
        lines.append("（还没有记录）")
    lines.append("")

    # 按 skill 分节
    for row in skill_rows:
        skill = row["skill"]
        gs = sorted(skills[skill], key=lambda g: group_sort_key(g, threshold))
        pending = [g for g in gs if g.count >= threshold]
        watching = [g for g in gs if g.count < threshold]

        lines.append(f"## {skill}")
        lines.append("")
        lines.append(
            f"**{row['records']} 条记录，{len(gs)} 类问题，待改 {len(pending)} 个。**"
        )
        lines.append("")

        sections = [
            ("待改（同类 ≥%d 条证据）" % threshold, pending),
            ("观察中（同类 < %d 条证据）" % threshold, watching),
        ]
        for title, items in sections:
            if not items:
                continue
            lines.append(f"### {title}")
            lines.append("")
            for i, g in enumerate(items, 1):
                lines.append(f"#### {i}. {g.display} — {g.count} 条证据")
                lines.append("")
                lines.append(f"- **状态**：{g.status(threshold)}")
                lines.append(f"- **影响**：{fmt_impacts(g.impacts)}")
                lines.append(f"- **阶段**：{fmt_counter(g.stages)}")
                if g.suggestions:
                    lines.append("- **建议改动**：")
                    for s in g.suggestions:
                        lines.append(f"  - {s}")
                else:
                    lines.append("- **建议改动**：（未填建议，需人工判断）")
                lines.append("- **受影响文件**：")
                for f in resolve_files(g):
                    lines.append(f"  - `{f}`")
                lines.append("- **证据**：")
                for r in sorted(g.records, key=lambda x: x.ts):
                    lines.append(
                        "  - "
                        + "｜".join(
                            [
                                f"`{r.ts_text}`",
                                f"阶段 {r.stage}",
                                f"{r.impact}",
                                f"建议：{r.suggestion or '（未填）'}",
                            ]
                        )
                    )
                lines.append("")

    # 下一步
    lines.append("## 下一步")
    lines.append("")
    pending_groups = [g for g in ranked if g.count >= threshold]
    if pending_groups:
        lines.append(f"- 有 {len(pending_groups)} 个问题攒够证据，可以动刀：")
        for g in pending_groups:
            lines.append(f"  - `{g.skill}` / `{g.display}`（{g.count} 条）")
        no_sugg = [g for g in pending_groups if not g.suggestions]
        if no_sugg:
            lines.append("- 其中这些还没有建议，先补一条再改：")
            for g in no_sugg:
                lines.append(f"  - `{g.skill}` / `{g.display}`")
        lines.append(
            "- 改对应文件（优先 `SKILL.md`，其次 `references/`），改完在 `skills/skill-reflect/SKILL.md` 的「改进记录」加一行；下次继续记录，看同类问题是否停止增长。"
        )
    elif ranked:
        closest = ranked[0]
        need = threshold - closest.count
        lines.append(
            f"- 暂无待改。最接近的是 `{closest.skill}` / `{closest.display}`（{closest.count}/{threshold}），再记录 {need} 条同类就能升级。"
        )
        lines.append("- 现在不要提前改流程；先继续用、继续记。")
    else:
        lines.append("- 还没有记录。用某个 skill 时觉得不顺，先跑 `log.py` 记一条。")
    lines.append("")

    # 坏行
    if bad:
        lines.append("## 坏行（已跳过）")
        lines.append("")
        for item in bad[:5]:
            lines.append(
                f"- `{display_path(Path(item['path']))}:{item['line']}` — {item['error']}｜`{item['preview']}`"
            )
        if len(bad) > 5:
            lines.append(f"- …还有 {len(bad) - 5} 条")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("> 记录只追加不改写；报告只给建议，改不改由主人定。")
    lines.append("")
    return "\n".join(lines)


def build_payload(groups: list, records: list, bad: list, threshold: int, generated: datetime, data_dir: Path) -> dict:
    ranked = sort_groups(groups, threshold)
    skills: dict = {}
    for g in groups:
        skills.setdefault(g.skill, []).append(g)

    skill_payload = []
    for skill in sorted(skills):
        gs = skills[skill]
        gs_sorted = sorted(
            gs,
            key=lambda g: (
                0 if g.count >= threshold else 1,
                -g.count,
                -g.high_count,
                -g.impact_score,
                -g.last_ts.timestamp(),
            ),
        )
        skill_payload.append(
            {
                "skill": skill,
                "records": sum(g.count for g in gs),
                "issue_types": len(gs),
                "pending": sum(1 for g in gs if g.count >= threshold),
                "issues": [
                    {
                        "issue": g.display,
                        "key": g.key,
                        "status": g.status(threshold),
                        "count": g.count,
                        "impacts": g.impacts,
                        "stages": dict(g.stages),
                        "suggestions": g.suggestions,
                        "affected_files": resolve_files(g),
                        "first_seen": g.first_ts.isoformat(timespec="seconds"),
                        "last_seen": g.last_ts.isoformat(timespec="seconds"),
                        "evidence": [
                            {
                                "ts": r.ts.isoformat(timespec="seconds"),
                                "source": r.source,
                                "stage": r.stage,
                                "issue": r.issue,
                                "suggestion": r.suggestion,
                                "impact": r.impact,
                                "files": r.files,
                            }
                            for r in sorted(g.records, key=lambda x: x.ts)
                        ],
                    }
                    for g in gs_sorted
                ],
            }
        )

    return {
        "generated_at": generated.isoformat(timespec="seconds"),
        "data_dir": display_path(data_dir),
        "threshold": threshold,
        "totals": {
            "records": len(records),
            "skills": len(skills),
            "issue_types": len(groups),
            "pending": sum(1 for g in groups if g.count >= threshold),
            "high_impact": sum(g.high_count for g in groups),
            "bad_lines": len(bad),
        },
        "ranking": [
            {
                "rank": i,
                "skill": g.skill,
                "issue": g.display,
                "count": g.count,
                "high": g.high_count,
                "status": g.status(threshold),
            }
            for i, g in enumerate(ranked, 1)
        ],
        "skills": skill_payload,
        "bad_lines": bad,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="report.py",
        description="聚合 skill 使用记录，找出攒够证据、该改的 skill 问题。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python3 skills/skill-reflect/scripts/report.py\n"
            "  python3 skills/skill-reflect/scripts/report.py --skill novel-study\n"
            "  python3 skills/skill-reflect/scripts/report.py --threshold 2 --json\n"
            "  python3 skills/skill-reflect/scripts/report.py --out .cache/skill-reflect/report.md"
        ),
    )
    parser.add_argument(
        "--data-dir",
        default=str(Path(__file__).resolve().parent.parent / "data" / "usage"),
        help="记录目录（默认 data/usage）",
    )
    parser.add_argument("--skill", default=None, help="只看某个 skill")
    parser.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_THRESHOLD,
        help=f"同类问题升级为待改所需证据条数（默认 {DEFAULT_THRESHOLD}）",
    )
    parser.add_argument("--top", type=int, default=20, help="问题排行最多显示几条（默认 20，0 表示全部）")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    parser.add_argument("--out", default=None, help="把结果写入文件（而不是打印到 stdout）")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.threshold < 1:
        print("错误：--threshold 至少为 1", file=sys.stderr)
        return 2
    if args.top < 0:
        print("错误：--top 不能为负", file=sys.stderr)
        return 2

    data_dir = Path(args.data_dir).expanduser()
    records, bad, exists = load_records(data_dir)
    if not exists:
        print(f"提示：数据目录不存在，按空报告输出：{display_path(data_dir)}", file=sys.stderr)
    if bad:
        print(f"提示：跳过 {len(bad)} 条坏行（格式错误），详见报告末尾。", file=sys.stderr)

    if args.skill:
        wanted = args.skill.strip()
        records = [r for r in records if r.skill == wanted]
        if not records:
            print(f"提示：没有 skill={wanted} 的记录。", file=sys.stderr)

    groups = group_records(records)
    generated = datetime.now().astimezone()

    if args.json:
        content = json.dumps(
            build_payload(groups, records, bad, args.threshold, generated, data_dir),
            ensure_ascii=False,
            indent=2,
        )
        if args.out:
            _write_out(args.out, content)
        else:
            print(content)
        return 0

    content = render_markdown(
        groups, records, bad, args.threshold, args.top, generated, data_dir
    )
    if args.out:
        _write_out(args.out, content)
    else:
        print(content, end="" if content.endswith("\n") else "\n")
    return 0


def _write_out(path_value: str, content: str) -> None:
    out = Path(path_value).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")
    print(f"已写入 → {display_path(out)}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
