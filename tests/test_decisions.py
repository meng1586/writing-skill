"""Semantic regressions for candidate retrieval, status boundaries and card wrappers."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/writing-decision/scripts/decide.py"
SPEC = importlib.util.spec_from_file_location("reviewed_decide", SCRIPT)
DECIDE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DECIDE)
CARD_SCRIPT = ROOT / "skills/scene-modules/scripts/query.py"


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.data = DECIDE.load_data()

    def select(self, data=None, tags=None, limit=4):
        return DECIDE.select(data or self.data, tags or ["玄幻"], "主角第一次杀人", "", "", limit)

    def cli(self, data, *args):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "decisions.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return subprocess.check_output(
                [sys.executable, "-B", str(SCRIPT), "--data", str(path), *args],
                text=True,
            )

    def test_repository_decisions_follow_source_and_effect_evidence_contract(self):
        decisions = self.data["decisions"]
        ids = [decision["id"] for decision in decisions]
        self.assertEqual(len(ids), len(set(ids)), "决策ID必须唯一")
        for decision in decisions:
            with self.subTest(decision=decision["id"]):
                self.assertTrue(decision["id"].strip())
                self.assertIn(decision["status"], DECIDE.STATUS_LABELS)
                self.assertTrue(decision["case"]["book"].strip())
                self.assertTrue(decision["case"]["chapters"].strip())
                self.assertIsInstance(decision["move"], list)
                self.assertTrue(decision["move"])
                self.assertTrue(all(isinstance(move, str) and move.strip()
                                    for move in decision["move"]))
                if decision["status"] == "conditional":
                    evidence = decision.get("effect_evidence")
                    self.assertIsInstance(evidence, list)
                    self.assertTrue(evidence, "有条件有用必须有可追溯的效果记录")
                    for record in evidence:
                        for field in ("condition", "draft_a_ref", "draft_b_ref", "feedback_ref"):
                            self.assertTrue(isinstance(record.get(field), str) and record[field].strip(),
                                            f"效果记录缺少{field}")

    def test_explicit_genre_exclusion_also_suppresses_original_combo(self):
        picked, _, _ = self.select(tags=["甜宠"])
        ids = {r["decision"]["id"] for r in picked}
        self.assertTrue(ids)
        self.assertNotIn("D-014", ids)
        self.assertNotIn("D-021", ids)
        self.assertIsNone(DECIDE.find_combo(self.data, ids, "主角第一次杀人"))

    def test_dropped_retired_and_legacy_rejected_do_not_reenter_via_combo(self):
        original_note = self.data["combos"][0]["note"]
        for status in ("dropped", "retired", "rejected"):
            with self.subTest(status=status):
                data = copy.deepcopy(self.data)
                next(d for d in data["decisions"] if d["id"] == "D-014")["status"] = status
                args = ("--tags", "玄幻", "--scene", "主角第一次杀人")
                result = json.loads(self.cli(data, *args, "--json"))
                self.assertNotIn("D-014", {d["id"] for d in result["matches"]})
                self.assertIsNone(result["combo"])
                self.assertNotIn(original_note, self.cli(data, *args))

    def test_partial_limit_does_not_emit_steps_outside_matches(self):
        picked, _, _ = self.select(limit=2)
        self.assertEqual(len(picked), 2)
        self.assertIsNone(DECIDE.find_combo(self.data, {r["decision"]["id"] for r in picked}, "主角第一次杀人"))

    def test_complete_combo_is_identical_in_text_and_json(self):
        args = ("--tags", "玄幻", "--scene", "主角第一次杀人")
        result = json.loads(self.cli(self.data, *args, "--json"))
        text = self.cli(self.data, *args)
        self.assertIsNotNone(result["combo"])
        self.assertTrue(set(result["combo"]["order"]) <= {d["id"] for d in result["matches"]})
        self.assertIn(" → ".join(result["combo"]["order"]), text)
        self.assertIn(result["combo"]["note"], text)

    def test_list_labels_all_states_without_reviving_retired_combinations(self):
        data = copy.deepcopy(self.data)
        for decision, status in zip(data["decisions"], DECIDE.STATUS_LABELS):
            decision["status"] = status
        # This combination must disappear from the usable combination catalog.
        next(d for d in data["decisions"] if d["id"] == "D-014")["status"] = "retired"
        text = DECIDE.render_list(data, "")
        for label in DECIDE.STATUS_LABELS.values():
            self.assertIn(label, text)
        line = next(line for line in text.splitlines() if "D-014  " in line)
        self.assertIn("已退役", line)
        self.assertNotIn("待验证", line)
        self.assertNotIn(self.data["combos"][0]["name"], text)
        self.assertNotIn("有原文出处", text)

    def test_legacy_statuses_are_read_without_claiming_effect_validation(self):
        data = copy.deepcopy(self.data)
        for decision, status in zip(data["decisions"], ("verified", "derived", "rejected")):
            decision["status"] = status
        result = json.loads(self.cli(data, "--list", "--json"))
        for decision, legacy, canonical in zip(result["decisions"],
                                                ("verified", "derived", "rejected"),
                                                ("untested", "untested", "dropped")):
            self.assertEqual(decision["status"], canonical)
            self.assertEqual(decision["legacy_status"], legacy)
        self.assertEqual(result["decisions"][0]["case"], data["decisions"][0]["case"])

    def test_unknown_status_fails_closed(self):
        decision = copy.deepcopy(self.data["decisions"][0])
        decision["status"] = "typo-state"
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            DECIDE.status_of(decision)

    def test_json_preserves_condition_evidence_separately_from_source_case(self):
        data = copy.deepcopy(self.data)
        decision = next(d for d in data["decisions"] if d["id"] == "D-014")
        decision["status"] = "conditional"
        decision["effect_evidence"] = [{"condition": "test fixture", "feedback_ref": "fixture-reader-note"}]
        decision["effect_review_required"] = True
        result = json.loads(self.cli(data, "--tags", "玄幻", "--scene", "主角第一次杀人", "--json"))
        found = next(d for d in result["matches"] if d["id"] == "D-014")
        self.assertEqual(found["case"], decision["case"])
        self.assertEqual(found["effect_evidence"], decision["effect_evidence"])
        self.assertTrue(found["effect_review_required"])
        text = self.cli(data, "--tags", "玄幻", "--scene", "主角第一次杀人")
        self.assertIn("test fixture", text)
        self.assertIn("fixture-reader-note", text)
        self.assertIn("结果存在分歧", text)

    def test_both_outputs_require_context_review_before_adoption(self):
        args = ("--tags", "玄幻", "--scene", "主角第一次杀人")
        result = json.loads(self.cli(self.data, *args, "--json"))
        text = self.cli(self.data, *args)
        self.assertTrue(result["context_review"]["required"])
        for question in result["context_review"]["questions"]:
            self.assertIn(question, text)
        self.assertIn("确认、加深、维持或改变", result["context_review"]["questions"][0])
        self.assertIn("可全部不用", text)
        self.assertNotIn("全知写不了", text)
        self.assertTrue(all(d["status_label"] == "待试验" for d in result["matches"]))


class CardWrapperTests(unittest.TestCase):
    def test_wrapper_exposes_candidate_boundary_without_rewriting_card(self):
        args = [sys.executable, "-B", str(CARD_SCRIPT), "--type", "告别"]
        result = json.loads(subprocess.check_output(args + ["--json"], text=True))
        text = subprocess.check_output(args, text=True)
        card = ROOT / "skills/scene-modules/data/modules/告别.md"
        self.assertEqual(result["modules"][0]["content"], card.read_text(encoding="utf-8"))
        self.assertIn(result["usage_note"], text)
        self.assertIn("未套五步", result["usage_note"])
        self.assertIn("不是真实读者情绪验证", result["usage_note"])

    def test_list_and_search_json_keep_usage_boundary(self):
        for args in (("--list",), ("--search", "倒叙")):
            with self.subTest(args=args):
                result = json.loads(subprocess.check_output(
                    [sys.executable, "-B", str(CARD_SCRIPT), *args, "--json"], text=True))
                self.assertIn("候选路径", result["usage_note"])


if __name__ == "__main__":
    unittest.main()
