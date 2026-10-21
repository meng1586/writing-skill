"""Regression tests use disposable data; no fetching, scheduling, or real progress writes."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    path = ROOT / "skills" / "novel-study" / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"test_novel_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NovelStudyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="novel-study-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.apply = load_script("apply")
        self.plan = load_script("plan")
        self.notes = self.root / "data" / "notes"
        self.rules = self.root / "data" / "rules"
        self.notes.mkdir(parents=True)
        self.rules.mkdir(parents=True)
        for module, values in (
            (self.apply, {"PROJECT_DIR": str(self.root), "RULES_DIR": str(self.rules),
                          "STYLE_DIR": str(self.root / "styles")}),
            (self.plan, {"PROJECT_DIR": str(self.root), "SHELF": str(self.root / "shelf.json"),
                         "CONFIG": str(self.root / "config.json"), "NOTES_DIR": str(self.notes),
                         "RULES_DIR": str(self.rules), "CACHE_DIR": str(self.root / "cache")}),
        ):
            for key, value in values.items():
                setattr(module, key, value)

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def shelf(self, books):
        self.write(self.root / "shelf.json", json.dumps({"books": books}, ensure_ascii=False))

    @staticmethod
    def book(key, done=0, total=12, status="unread"):
        source, book_id = key.split("-", 1)
        return {"key": key, "source": source, "book_id": book_id, "name": key,
                "status": status, "verdict": "keep", "chapters_done": done,
                "chapter_total": total}

    def test_r_and_c_cards_preserve_conditions_evidence_and_status_in_json(self):
        self.write(self.rules / "情绪.md", """## R-情绪-001 旧案例
- 类型：候选案例
- 出处：《示例》第1章
- 适用条件：已有关系依据
- 适用题材：全题材
- 状态：可用

## C-014 新候选
- 原文事实：《示例》第2章，人物没有回答
- 写作假设：需要呈现回避时尝试
- 适用题材：通用
- 状态：待试验

## C-015 停用候选
- 适用题材：通用
- 状态：暂不采用
""")
        output = io.StringIO()
        with patch("sys.argv", ["apply.py", "--tags", "悬疑", "--json"]), contextlib.redirect_stdout(output):
            self.assertEqual(self.apply.main(), 0)
        rules = json.loads(output.getvalue())["rules"]
        self.assertEqual(len(rules), 2)
        self.assertEqual([r["status"] for r in rules], ["待试验", "待试验"])
        self.assertEqual(rules[0]["original_status"], "可用")
        self.assertEqual(rules[0]["kind"], "候选案例")
        self.assertEqual(rules[0]["conditions"], "已有关系依据")
        self.assertIn("第2章", rules[1]["source"])
        self.assertIn("写作假设", rules[1]["body"])
        self.assertEqual(rules[0]["source_path"], "data/rules/情绪.md")

    def test_malformed_card_among_valid_cards_is_not_silently_lost(self):
        path = self.rules / "人物.md"
        self.write(path, "## R-人物-001 有效标题\n- 状态：待试验\n\nC-002 缺少标题标记\n")
        with self.assertRaisesRegex(ValueError, "人物.md:4"):
            self.apply.parse_rules(path)

    def test_new_dimension_is_discovered_without_editing_a_whitelist(self):
        self.write(self.rules / "场景衔接.md", "## C-021 提供衔接依据\n- 适用题材：通用\n- 状态：待试验\n")
        picked = self.apply.build(["悬疑"], "")['rules']
        self.assertEqual(picked[0][0], "场景衔接")

    def test_explicit_book_identity_and_range_ignore_another_books_legacy_state(self):
        self.shelf([self.book("fanqie-old", 12, status="done"), self.book("tianxi-new", 3)])
        legacy = self.root / "data" / "state" / "reading-progress.json"
        self.write(legacy, '{"book_key":"fanqie-old","last_read_chapter":12,"total_chapters":12}')
        before = legacy.read_bytes()
        result = self.plan.build_plan("tianxi-new", chapters=5)
        self.assertEqual(result["selected_book"]["key"], "tianxi-new")
        item, = result["today"]
        self.assertEqual((item["book_key"], item["source"], item["book_id"]), ("tianxi-new", "tianxi", "new"))
        self.assertEqual((item["last_read_chapter"], item["from"], item["to"]), (3, 4, 8))
        self.assertEqual(legacy.read_bytes(), before)

    def test_completed_reading_book_does_not_block_next_book_or_create_reverse_range(self):
        self.shelf([self.book("fanqie-old", 12, status="reading"), self.book("tianxi-new")])
        self.assertEqual(self.plan.build_plan()["today"][0]["key"], "tianxi-new")
        self.assertEqual(self.plan.build_plan("fanqie-old")["today"], [])
        with self.assertRaises(ValueError):
            self.plan.build_plan("fanqie-missing")

    def test_only_a_summary_does_not_count_as_a_completed_unit_note(self):
        self.shelf([self.book("fanqie-new", status="reading")])
        self.write(self.notes / "fanqie-new" / "前情提要.md", "当前摘要")
        self.assertIn("fanqie-new", self.plan.build_plan()["notes_todo"])

    def test_sync_checks_old_note_conflicts_before_publishing_new_material(self):
        old_note = self.notes / "书" / "第001-010章.md"
        new_note = self.notes / "书" / "第011-020章.md"
        formal = self.root / "06-素材" / "读" / "笔记"
        old_formal = formal / "书" / old_note.name
        self.write(old_note, "源笔记与旧正式副本不同")
        self.write(old_formal, "受保护旧笔记")
        self.write(new_note, "新单元")
        self.write(self.rules / "情绪.md", "新候选")
        with self.assertRaisesRegex(ValueError, "未覆盖"):
            self.plan.sync_outputs()
        self.assertEqual(old_formal.read_text(encoding="utf-8"), "受保护旧笔记")
        self.assertFalse((formal / "书" / new_note.name).exists())
        self.assertFalse((self.root / "06-素材" / "读" / "规则").exists())
        self.write(old_note, "受保护旧笔记")
        self.plan.sync_outputs()
        self.assertEqual((formal / "书" / new_note.name).read_text(encoding="utf-8"), "新单元")
        self.assertEqual(old_formal.read_text(encoding="utf-8"), "受保护旧笔记")


if __name__ == "__main__":
    unittest.main()
