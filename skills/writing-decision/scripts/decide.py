#!/usr/bin/env python3
"""decide.py — 写作决策树：这一场戏该怎么写

按题材、场景、章节位置检索候选；是否采用仍须复核本场目标、人物状态和视角。

用法：
  python3 scripts/decide.py --tags 玄幻 --scene "主角第一次杀人"
  python3 scripts/decide.py --tags 玄幻,悬疑 --scene "章末没钩子" --position 章末
  python3 scripts/decide.py --scene "反派登场" --limit 5
  python3 scripts/decide.py --list
  python3 scripts/decide.py --list --dimension 对话
  python3 scripts/decide.py --tags 玄幻 --scene "主角第一次杀人" --json

只依赖标准库。数据在 ../data/decisions.json。
"""
import argparse
import json
import os
import re
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DATA = os.path.join(SKILL_DIR, "data", "decisions.json")
DIMENSIONS = ["开篇", "节奏", "人物", "对话", "章末钩子", "语言"]
POSITION_WORDS = [
    ("开篇", ["开篇", "开头", "第一章", "第一段", "第一句", "楔子", "开局"]),
    ("章末", ["章末", "章尾", "结尾", "收章", "最后一句", "断章", "钩子"]),
    ("卷末", ["卷末", "卷尾", "本卷结束", "终章", "大结局"]),
]
STATUS_LABELS = {
    "untested": "待试验",
    "tried": "已试用，效果未定",
    "conditional": "有条件有用",
    "dropped": "暂不采用",
    "no-diff": "对照看不出区别",
    "retired": "已退役",
}
# 旧 verified 只表示有原文出处，不能据此认定写作效果经过验证。
LEGACY_STATUSES = {"derived": "untested", "verified": "untested", "rejected": "dropped"}
CONTEXT_REVIEW = {
    "required": True,
    "questions": [
        "本场希望读者在乎什么？要确认、加深、维持或改变哪些判断？候选动作是否服务这个目标？",
        "人物此刻的目标、能力、关系和反应是否支持这条写法？",
        "当前视角允许谁知道、感到什么？信息和感受的表达是否一致？",
    ],
    "note": "关键词只负责召回候选；语境不符可全部不用，未套动作或组合不构成写坏的证据。",
}


def die(msg):
    print(f"decide.py: {msg}", file=sys.stderr)
    sys.exit(2)


def status_of(decision):
    raw = decision.get("status", "untested")
    status = LEGACY_STATUSES.get(raw, raw)
    if status not in STATUS_LABELS:
        die(f"未知状态「{raw}」（{decision.get('id', '无编号')}）")
    return status


def status_label(decision):
    label = STATUS_LABELS[status_of(decision)]
    legacy = decision.get("legacy_status")
    if not legacy and decision.get("status") in LEGACY_STATUSES:
        legacy = decision["status"]
    return f"{label}；兼容旧状态 {legacy}" if legacy else label


def is_active(decision):
    return status_of(decision) not in ("dropped", "retired")


def load_data(path=DEFAULT_DATA):
    if not os.path.isfile(path):
        die(f"找不到决策数据：{path}")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        die(f"决策数据不是合法 JSON：{e}")
    if not data.get("decisions"):
        die("决策数据里没有 decisions 数组")
    for decision in data["decisions"]:
        raw = decision.get("status", "untested")
        decision["status"] = status_of(decision)
        if raw in LEGACY_STATUSES:
            decision["legacy_status"] = raw
    return data


def split_tags(raw):
    if not raw:
        return []
    tags = [t.strip() for t in re.split(r"[,，、/\s]+", raw) if t.strip()]
    # 去重，保序
    seen, out = set(), []
    for t in tags:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def infer_position(scene):
    for name, words in POSITION_WORDS:
        if any(w in scene for w in words):
            return name
    return ""


def build_concepts(data, scene_text):
    """把自由文本扩展成命中的场景概念：concept -> 权重（3=概念名直接出现，2=同义词命中）。"""
    aliases = dict(data.get("scene_aliases") or {})
    for d in data["decisions"]:
        for c in d["trigger"].get("scenes", []):
            aliases.setdefault(c, [])
    hits = {}
    for concept, words in aliases.items():
        if concept and concept in scene_text:
            hits[concept] = 3.0
            continue
        for w in words:
            if w and w in scene_text:
                hits[concept] = 2.0
                break
    return hits


def genre_score(d, tags):
    """返回 (分数, 命中的题材, 是否因排除题材被排除)。"""
    trig = d["trigger"]
    genres = trig.get("genres", [])
    exclude = trig.get("exclude_genres", [])
    if tags and exclude and any(t in exclude for t in tags):
        return 0.0, [], True
    if not tags:
        return 0.0, [], False
    hit = [t for t in tags if t in genres]
    if hit:
        return 1.0 + 0.3 * (len(hit) - 1), hit, False
    if "通用" in genres:
        return 0.3, ["通用"], False
    return 0.0, [], False


def score_one(d, concepts, tags, position):
    scenes = d["trigger"].get("scenes", [])
    scene_hits = [c for c in scenes if c in concepts]
    if scene_hits:
        weights = [concepts[c] for c in scene_hits]
        scene_score = max(weights) + 0.5 * (len(weights) - 1)
        # 每条决策的第一个场景是它的主场景：命中主场景，优先级高一档
        if scenes and scenes[0] in concepts:
            scene_score += 1.5
    else:
        scene_score = 0.0

    g_score, g_hit, excluded = genre_score(d, tags)
    p_hit = bool(position) and position in d["trigger"].get("positions", [])
    p_score = 1.5 if p_hit else 0.0

    return {
        "decision": d,
        "scene_hits": scene_hits,
        "genre_hits": g_hit,
        "position_hit": p_hit,
        "scene_score": round(scene_score, 2),
        "score": round(scene_score + g_score + p_score, 2),
        "excluded": excluded,
    }


def select(data, tags, scene, position, dimension, limit):
    concepts = build_concepts(data, scene)
    rows = []
    for i, d in enumerate(data["decisions"]):
        # v2：淘汰/暂不采用的决策不再推荐
        if not is_active(d):
            continue
        if dimension and d["dimension"] != dimension:
            continue
        r = score_one(d, concepts, tags, position)
        if r["excluded"]:
            continue
        if r["score"] <= 0:
            continue
        r["order"] = i
        rows.append(r)

    rows.sort(key=lambda r: (-r["score"], -r["scene_score"], r["order"]))
    direct = [r for r in rows if r["scene_hits"]]
    fallback = [r for r in rows if not r["scene_hits"]]

    if not scene:
        # 只给了题材/位置：按维度轮转取样，避免四条全是「开篇」
        by_dim = {}
        for r in rows:
            by_dim.setdefault(r["decision"]["dimension"], []).append(r)
        picked, round_i = [], 0
        while len(picked) < limit and any(len(v) > round_i for v in by_dim.values()):
            for dim in DIMENSIONS:
                bucket = by_dim.get(dim, [])
                if len(bucket) > round_i:
                    picked.append(bucket[round_i])
                    if len(picked) >= limit:
                        break
            round_i += 1
    else:
        picked = direct[:limit]
        floor = min(3, limit)
        if len(picked) < floor:
            # 只补「题材精确命中」或「位置相关」的条目；通用技巧不硬凑
            precise = [r for r in fallback
                       if (r["genre_hits"] and r["genre_hits"] != ["通用"])
                       or r["position_hit"]]
            seen = {r["decision"]["id"] for r in picked}
            for r in precise:
                if len(picked) >= floor:
                    break
                if r["decision"]["id"] not in seen:
                    picked.append(r)
                    seen.add(r["decision"]["id"])
    if position and len(picked) >= 2 and not any(r["position_hit"] for r in picked):
        # 用户明确指定了章节位置：至少留一条位置相关的决策，替换掉末位
        pos_pool = [r for r in fallback if r["position_hit"]]
        # 主场景就是该位置的优先，其次按分数
        pos_pool.sort(key=lambda r: (
            0 if r["decision"]["trigger"].get("scenes", [])[:1] == [position] else 1,
            -r["score"]))
        if pos_pool:
            picked[-1] = pos_pool[0]
    picked.sort(key=lambda r: (-r["score"], -r["scene_score"], r["order"]))
    return picked, len(direct), len(fallback)


def combo_is_eligible(data, combo, picked_ids=None):
    """说明覆盖整条组合；任一成员被过滤或未入选时，不输出残缺组合。"""
    order = combo.get("order", [])
    active = {d["id"] for d in data["decisions"] if is_active(d)}
    return len(order) >= 2 and set(order) <= active and (picked_ids is None or set(order) <= picked_ids)


def find_combo(data, picked_ids, scene=""):
    """只返回本轮完整入选且可用的候选组合，文本和 JSON 共用这个结果。"""
    best, best_hit = None, 0
    for combo in data.get("combos", []):
        if not combo_is_eligible(data, combo, picked_ids):
            continue
        trig = combo.get("triggers") or []
        if trig and not any(t in (scene or "") for t in trig):
            continue
        hit = [x for x in combo["order"] if x in picked_ids]
        if len(hit) > best_hit:
            best, best_hit = combo, len(hit)
    if best and best_hit >= 2:
        return best
    return None


def match_line(r):
    parts = []
    if r["scene_hits"]:
        parts.append("场景：" + "、".join(f"「{c}」" for c in r["scene_hits"]))
    if r["genre_hits"]:
        if r["genre_hits"] == ["通用"]:
            parts.append("题材：通用")
        else:
            parts.append("题材：" + "、".join(f"「{t}」" for t in r["genre_hits"]))
    if r["position_hit"]:
        parts.append("位置：命中")
    if not r["scene_hits"]:
        parts.append("不是本场直击，只作题材/位置补位")
    return "｜".join(parts)


def fmt_case(case):
    book = case.get("book", "")
    ch = case.get("chapters", "")
    quote = case.get("quote", "")
    qtype = case.get("quote_type", "")
    suffix = "" if qtype in ("", "原文") else f"（{qtype}）"
    if qtype in ("反例", "反例对照") and "反例" in quote[:4]:
        quote = quote.split("：", 1)[-1]
    return f"{book}{ch}{suffix} —— {quote}"


def render_match(r, idx):
    d = r["decision"]
    lines = []
    lines.append(f"{idx}) {d['id']} [{d['dimension']}] {d['title']}（{status_label(d)}）")
    lines.append(f"   匹配：{match_line(r)}")
    when = d["trigger"].get("when", "")
    if when:
        lines.append(f"   什么时候用：{when}")
    lines.append("   候选动作（按本场取舍）：")
    for step in d["move"]:
        lines.append(f"     - {step}")
    lines.append(f"   机理假设：{d['why']}")
    lines.append(f"   参考：{fmt_case(d['case'])}")
    if d["case"].get("note"):
        lines.append(f"         {d['case']['note']}")
    for evidence in d.get("effect_evidence", []):
        lines.append(f"   已记录对照：{evidence.get('condition', '条件未记录')}｜"
                     f"{evidence.get('comparison_result', '结果未记录')}｜"
                     f"反馈：{evidence.get('feedback_ref', '来源未记录')}")
    if status_of(d) == "conditional" and not d.get("effect_evidence"):
        lines.append("   效果条件未附记录，采用前需复核，不能据此声称已获真人验证。")
    if d.get("effect_review_required"):
        lines.append("   已记录结果存在分歧，需按情境复核，不作普遍有效结论。")
    risks = [x.rstrip("。；;") for x in d["risk"]]
    lines.append("   崩法：" + "；".join(risks) + "。")
    return "\n".join(lines)


def render_text(data, query, picked, n_direct, n_fallback):
    tags = query["tags"]
    scene = query["scene"]
    head = "写作决策"
    if tags:
        head += " · " + "、".join(tags)
    if scene:
        head += f" · 「{scene}」"
    width = max(40, min(78, len(head) * 2 + 20))
    out = [head, "=" * width]

    if not picked:
        out.append("这场戏还没有直接对应的决策。本鲸不硬凑：通用技巧套到不合适的场景，比没有建议更糟。")
        out.append("")
        out.append("你可以：")
        out.append("  - 换一个更具体的场景词，比如「第一次杀人」「章末没钩子」「反派登场」「损友对话」")
        out.append("  - 补题材再试：--tags 玄幻")
        out.append("  - 先看全部 24 条，人工挑：--list")
        return "\n".join(out)

    picked_direct = sum(1 for r in picked if r["scene_hits"])
    if scene:
        out.append(f"共 {len(picked)} 条｜场景直击 {picked_direct} 条 · 补位 {len(picked) - picked_direct} 条")
    else:
        out.append(f"共 {len(picked)} 条｜按题材相关度排序，已跨维度取样（没给场景）")
    out.append("以下是检索候选，分数不代表效果或适用性已经验证。")
    out.append("落笔前先复核本场语境：")
    out.extend(f"{i}. {question}" for i, question in enumerate(CONTEXT_REVIEW["questions"], 1))
    out.append(CONTEXT_REVIEW["note"])
    out.append("")

    for i, r in enumerate(picked, 1):
        out.append(render_match(r, i))
        out.append("")

    combo = find_combo(data, {r["decision"]["id"] for r in picked}, scene)
    if combo:
        out.append("——— 候选组合（语境复核后可取舍） ———")
        out.append(f"[{combo['name']}] 全部 {len(combo['order'])} 条均在本轮候选中")
        out.append("参考顺序：" + " → ".join(combo["order"]))
        out.append(combo["note"])
        out.append("")
    out.append("下一步：只把语境相符的候选带进场景；写后用具体文本核对效果假设，保留未测和失效情况。")
    return "\n".join(out)


def render_list(data, dimension):
    groups = {d: [] for d in DIMENSIONS}
    for d in data["decisions"]:
        groups.setdefault(d["dimension"], []).append(d)
    total = sum(len(v) for v in groups.values())
    counts = {status: sum(status_of(d) == status for d in data["decisions"])
              for status in STATUS_LABELS}
    if dimension:
        n = len(groups.get(dimension, []))
        out = [f"写作决策树 · {dimension} · {n} 条", ""]
    else:
        summary = " · ".join(f"{STATUS_LABELS[s]} {n}" for s, n in counts.items() if n)
        out = [f"写作决策树 · {total} 条（{summary}）", "案例出处与效果状态分别记录。", ""]
    shown = 0
    for dim in DIMENSIONS:
        rows = groups.get(dim, [])
        if dimension and dim != dimension:
            continue
        if not rows:
            continue
        out.append(f"[{dim}] {len(rows)} 条")
        for d in rows:
            shown += 1
            trig = d["trigger"]
            scenes = " / ".join(trig.get("scenes", [])[:4]) or "—"
            genres = "、".join(trig.get("genres", [])) or "—"
            out.append(f"  {d['id']}  {d['title']}  [{status_label(d)}]")
            out.append(f"        触发：{scenes}｜题材：{genres}")
        out.append("")
    if not shown:
        out.append("这个维度还没有决策。")
        return "\n".join(out)
    if not dimension and data.get("combos"):
        out.append("成员状态可用的组合候选（仍需本场语境复核）：")
        for c in data["combos"]:
            if combo_is_eligible(data, c):
                out.append(f"  - {c['name']}：" + " → ".join(c["order"]))
    return "\n".join(out)


def to_json_match(r):
    d = dict(r["decision"])
    return {
        **d,
        "status": status_of(d),
        "status_label": status_label(d),
        "effect_review_required": bool(d.get("effect_review_required")) or
                                  (status_of(d) == "conditional" and not d.get("effect_evidence")),
        **({"legacy_status": d["legacy_status"]} if d.get("legacy_status") else {}),
        "score": r["score"],
        "matched": {
            "scenes": r["scene_hits"],
            "genres": r["genre_hits"],
            "position": r["position_hit"],
            "direct": bool(r["scene_hits"]),
        },
        "related": d.get("related", []),
    }


def main():
    ap = argparse.ArgumentParser(
        description="写作决策树：这一场戏该怎么写",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""例子：
  python3 scripts/decide.py --tags 玄幻 --scene "主角第一次杀人"
  python3 scripts/decide.py --scene "章末没钩子" --position 章末
  python3 scripts/decide.py --list
  python3 scripts/decide.py --tags 玄幻 --scene "反派登场" --json""",
    )
    ap.add_argument("--tags", default="", help="题材，逗号分隔，如 玄幻,悬疑")
    ap.add_argument("--scene", default="", help="场景/情境，自由文本，如「主角第一次杀人」")
    ap.add_argument("--position", default="", help="章节位置：开篇/中段/章末/卷末（也可从 --scene 推断）")
    ap.add_argument("--dimension", default="", help="只看某个维度：开篇/节奏/人物/对话/章末钩子/语言")
    ap.add_argument("--limit", type=int, default=4, help="返回条数，默认 4（建议 3–5）")
    ap.add_argument("--list", action="store_true", help="列出全部决策")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--data", default=DEFAULT_DATA, help="决策数据路径（默认 data/decisions.json）")
    args = ap.parse_args()

    data = load_data(args.data)
    tags = split_tags(args.tags)
    scene = (args.scene or "").strip()
    position = args.position.strip() or infer_position(scene)
    dimension = args.dimension.strip()

    if dimension and dimension not in DIMENSIONS:
        die(f"未知维度「{dimension}」，可选：{'、'.join(DIMENSIONS)}")

    if args.list:
        if args.json:
            decisions = [d for d in data["decisions"] if not dimension or d["dimension"] == dimension]
            print(json.dumps({"count": len(decisions), "decisions": decisions,
                              "status_labels": STATUS_LABELS,
                              "note": "列表包含暂不采用及退役条目；案例出处不代表效果已验证。"},
                             ensure_ascii=False, indent=2))
        else:
            print(render_list(data, dimension))
        return 0

    if not tags and not scene and not position:
        print("给一个场景或题材，本鲸才能翻决策。例如：")
        print('  python3 scripts/decide.py --tags 玄幻 --scene "主角第一次杀人"')
        print("  python3 scripts/decide.py --list")
        return 0

    limit = max(1, min(8, args.limit))
    picked, n_direct, n_fallback = select(data, tags, scene, position, dimension, limit)

    if args.json:
        combo = find_combo(data, {r["decision"]["id"] for r in picked}, scene)
        out = {
            "query": {"tags": tags, "scene": scene, "position": position,
                      "dimension": dimension, "limit": limit},
            "count": len(picked),
            "direct": sum(1 for r in picked if r["scene_hits"]),
            "fallback": sum(1 for r in picked if not r["scene_hits"]),
            "matches": [to_json_match(r) for r in picked],
            "combo": combo,
            "context_review": CONTEXT_REVIEW,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    print(render_text(data, {"tags": tags, "scene": scene}, picked, n_direct, n_fallback))
    return 0


if __name__ == "__main__":
    sys.exit(main())
