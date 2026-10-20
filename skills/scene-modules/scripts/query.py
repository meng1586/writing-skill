#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scene-modules 查询工具（仅标准库）。

用法：
    python3 scripts/query.py --list
    python3 scripts/query.py --type 打脸
    python3 scripts/query.py --type 告别 --json
    python3 scripts/query.py --search 倒叙
    python3 scripts/query.py --search 蒙太奇 --json

约定：
- 卡片放在 data/modules/*.md，文件名即类型名。
- 卡片首行：# 场景模块：{类型}
- 元数据行：> 一句话：… / > 别名：A、B / > 素材来源：…
"""

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "data" / "modules"
MAX_HITS_PER_MODULE = 6

# 列表展示顺序：按「一场戏从起手到收尾」的常见调用顺序排，新模块追加在末尾。
PREFERRED_ORDER = [
    "打脸", "反转", "告别", "绝境", "托孤", "翻盘",
    "谈判", "追逐", "揭示", "爆发", "立威", "交易",
]


class Module:
    def __init__(self, path: Path, content: str):
        self.path = path
        self.content = content
        self.type = path.stem
        self.summary = ""
        self.aliases = []
        self._parse()

    def _parse(self) -> None:
        for line in self.content.splitlines():
            s = line.strip()
            if not self.summary and s.startswith("> 一句话："):
                self.summary = s[len("> 一句话："):].strip()
            elif s.startswith("> 别名："):
                raw = s[len("> 别名："):].strip()
                self.aliases = [a.strip() for a in re.split(r"[、,，/]", raw) if a.strip()]
            if self.summary and self.aliases:
                break

    def matches(self, term: str) -> bool:
        t = normalize(term)
        if not t:
            return False
        if t in normalize(self.type):
            return True
        return any(t in normalize(a) for a in self.aliases)

    def search(self, term: str):
        hits = []
        for i, line in enumerate(self.content.splitlines(), start=1):
            if term in line:
                hits.append({"line": i, "text": line.strip()})
                if len(hits) >= MAX_HITS_PER_MODULE:
                    break
        return hits

    def meta(self) -> dict:
        return {
            "type": self.type,
            "summary": self.summary,
            "aliases": self.aliases,
            "path": str(self.path),
        }


def normalize(text: str) -> str:
    return re.sub(r"[\s「」『』：:]+", "", text or "")


def load_modules(directory: Path):
    if not directory.is_dir():
        sys.exit(f"[scene-modules] 找不到卡片目录：{directory}")
    modules = []
    for p in sorted(directory.glob("*.md")):
        modules.append(Module(p, p.read_text(encoding="utf-8")))

    def order_key(m):
        try:
            return (0, PREFERRED_ORDER.index(m.type), m.type)
        except ValueError:
            return (1, 0, m.type)

    return sorted(modules, key=order_key)


def available(modules):
    return "、".join(m.type for m in modules)


def cmd_list(modules, as_json: bool) -> int:
    if as_json:
        print(json.dumps(
            {"query": "list", "count": len(modules),
             "modules": [m.meta() for m in modules]},
            ensure_ascii=False, indent=2))
        return 0
    if not modules:
        print("[scene-modules] 还没有卡片。")
        return 0
    width = max(len(m.type) for m in modules)
    print(f"共 {len(modules)} 个场景模块（卡片目录：{modules[0].path.parent}）\n")
    for m in modules:
        aliases = f"  （别名：{'、'.join(m.aliases)}）" if m.aliases else ""
        print(f"  {m.type:<{width}}  {m.summary}{aliases}")
    print("\n取卡片：python3 scripts/query.py --type <类型>")
    return 0


def cmd_type(modules, term: str, as_json: bool) -> int:
    matched = [m for m in modules if m.matches(term)]
    if not matched:
        sys.exit(f"[scene-modules] 没找到「{term}」。现有模块：{available(modules)}")
    if as_json:
        data = []
        for m in matched:
            item = m.meta()
            item["content"] = m.content
            data.append(item)
        print(json.dumps(
            {"query": "type", "term": term, "count": len(data), "modules": data},
            ensure_ascii=False, indent=2))
        return 0
    if len(matched) > 1:
        print(f"> 模糊匹配到 {len(matched)} 张卡片：{'、'.join(m.type for m in matched)}\n")
    for idx, m in enumerate(matched):
        if idx:
            print("\n" + "=" * 60 + "\n")
        print(m.content.rstrip())
    return 0


def cmd_search(modules, term: str, as_json: bool) -> int:
    if not term.strip():
        sys.exit("[scene-modules] --search 需要一个关键词。")
    results = []
    for m in modules:
        hits = m.search(term)
        if hits:
            results.append((m, hits))
    if not results:
        sys.exit(f"[scene-modules] 没有卡片包含「{term}」。")
    if as_json:
        print(json.dumps(
            {"query": "search", "term": term, "count": len(results),
             "matches": [
                 dict(m.meta(), hits=hits) for m, hits in results
             ]},
            ensure_ascii=False, indent=2))
        return 0
    print(f"「{term}」命中 {len(results)} 个模块：\n")
    for m, hits in results:
        print(f"【{m.type}】{m.summary}")
        for h in hits:
            print(f"    L{h['line']}: {h['text']}")
        print()
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="query.py",
        description="查询场景模块卡片（打脸、告别、谈判……写作前直接调）。",
        epilog="示例：python3 scripts/query.py --type 打脸",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--list", action="store_true", help="列出所有场景模块")
    group.add_argument("--type", metavar="类型", help="按类型/别名取整张卡片")
    group.add_argument("--search", metavar="关键词", help="全文搜索关键词，返回模块与命中行")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    parser.add_argument("--dir", metavar="目录", help="卡片目录（默认 data/modules）")
    args = parser.parse_args(argv)

    if not (args.list or args.type or args.search):
        parser.print_help()
        return 0

    directory = Path(args.dir).expanduser().resolve() if args.dir else DEFAULT_DIR
    modules = load_modules(directory)

    if args.list:
        return cmd_list(modules, args.json)
    if args.type:
        return cmd_type(modules, args.type, args.json)
    return cmd_search(modules, args.search, args.json)


if __name__ == "__main__":
    sys.exit(main())
