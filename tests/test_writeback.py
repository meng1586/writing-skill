"""Meaningful feedback/state regressions; all mutations use temporary fixtures."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import runpy
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
WB = runpy.run_path(str(ROOT / "skills/writing-loop/scripts/writeback.py"))
STYLE = runpy.run_path(str(ROOT / "skills/writing-loop/scripts/style.py"))
REFLECT = runpy.run_path(str(ROOT / "skills/skill-reflect/scripts/report.py"))


def use(**overrides):
    record = {"ts": "2026-10-21T12:00:00+00:00", "chapter": "试写第1章",
              "used": ["D-001"], "effect": "一条具体观察", "verdict": "好"}
    record.update(overrides)
    return record


def comparison(result="better", condition="人物试图维持镇定", **overrides):
    fields = dict(reviewer_type="reader", result_confirmed=True,
                  draft_a_ref="A.md@v1", draft_b_ref="B.md@v1", feedback_ref="feedback.md#reader1",
                  comparison_result=result, condition=condition)
    fields.update(overrides)
    return use(**fields)


class WritebackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="writeback-test-")
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.decisions = self.directory / "decisions.json"
        self.logs = self.directory / "writebacks.jsonl"

    def apply(self, records, decision=None, dry_run=False):
        if decision is not None:
            self.decisions.write_text(json.dumps({"decisions": [decision]}), encoding="utf-8")
        self.logs.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
        args = argparse.Namespace(decisions=str(self.decisions), writebacks=str(self.logs), dry_run=dry_run)
        with contextlib.redirect_stdout(io.StringIO()):
            WB["cmd_apply"](args)
        return json.loads(self.decisions.read_text())["decisions"][0]

    def test_legacy_or_model_feedback_is_usage_only(self):
        for record in (use(compared="yes"), comparison(reviewer_type="model")):
            result = self.apply([record], {"id": "D-001", "status": "untested"})
            self.assertEqual(result["status"], "tried")
            self.assertNotIn("effect_evidence", result)

    def test_each_evidence_field_is_required_for_effect(self):
        for field in ("reviewer_type", "result_confirmed", "draft_a_ref", "draft_b_ref",
                      "feedback_ref", "condition", "comparison_result"):
            record = comparison()
            del record[field]
            self.assertFalse(WB["qualified_evidence"](record), field)

    def test_explicit_reader_results_have_distinct_states(self):
        for outcome, expected in (("better", "conditional"), ("worse", "dropped"), ("no-diff", "no-diff")):
            result = self.apply([comparison(outcome)], {"id": "D-001", "status": "untested"})
            self.assertEqual(result["status"], expected)
            self.assertEqual(result["effect_evidence"][0]["condition"], "人物试图维持镇定")
            self.assertEqual(result["effect_evidence"][0]["feedback_ref"], "feedback.md#reader1")

    def test_mixed_conditions_are_not_no_difference(self):
        records = [comparison("better", "条件X"), comparison("worse", "条件Y", verdict="崩")]
        result = self.apply(records, {"id": "D-001", "status": "untested"})
        self.assertEqual(result["status"], "tried")
        self.assertTrue(result["effect_review_required"])
        self.assertEqual({e["condition"] for e in result["effect_evidence"]}, {"条件X", "条件Y"})

    def test_ordinary_usage_preserves_existing_effect_states(self):
        for status in ("conditional", "dropped", "no-diff", "retired"):
            result = self.apply([use()], {"id": "D-001", "status": status})
            self.assertEqual(result["status"], status)

    def test_retired_is_not_revived_by_reader_comparison(self):
        result = self.apply([comparison()], {"id": "D-001", "status": "retired"})
        self.assertEqual(result, {"id": "D-001", "status": "retired"})

    def test_split_logs_do_not_erase_prior_conditions(self):
        first = self.apply([comparison("better", "条件X")], {"id": "D-001", "status": "untested"})
        report = WB["aggregate"]([comparison("worse", "条件Y", verdict="崩")], {"D-001": first})[0]
        self.assertEqual(report["suggestion"], "conditional")
        self.assertTrue(report["effect_review_required"])
        result = self.apply([comparison("worse", "条件Y", verdict="崩")])
        self.assertEqual(result["status"], "conditional")
        self.assertTrue(result["effect_review_required"])
        self.assertEqual(len(result["effect_evidence"]), 2)

    def test_same_version_or_multiple_techniques_is_not_effect_evidence(self):
        same = comparison()
        same["draft_b_ref"] = same["draft_a_ref"]
        self.assertFalse(WB["qualified_evidence"](same))
        self.assertFalse(WB["qualified_evidence"](comparison(used=["D-001", "D-002"])))

    def test_dry_run_and_repeat_apply_do_not_rewrite_files(self):
        initial = {"id": "D-001", "status": "untested"}
        self.decisions.write_text(json.dumps({"decisions": [initial]}), encoding="utf-8")
        before = self.decisions.read_bytes()
        self.apply([comparison()], dry_run=True)
        self.assertEqual(self.decisions.read_bytes(), before)
        self.apply([comparison()])
        applied = self.decisions.read_bytes()
        self.apply([comparison()])
        self.assertEqual(self.decisions.read_bytes(), applied)

    def test_legacy_status_is_preserved_without_claiming_effect(self):
        for legacy, expected in (("verified", "tried"), ("derived", "tried"), ("rejected", "dropped")):
            result = self.apply([use()], {"id": "D-001", "status": legacy})
            self.assertEqual(result["status"], expected)
            self.assertEqual(result["legacy_status"], legacy)

    def test_cli_records_feedback_metadata_without_modifying_decisions(self):
        self.decisions.write_text(json.dumps({"decisions": [{"id": "D-001", "status": "untested"}]}))
        original = self.decisions.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()):
            WB["main"](["add", "--writebacks", str(self.logs), "--decisions", str(self.decisions),
                        "--chapter", "试写第1章", "--used", "D-001", "--effect", "具体反馈", "--verdict", "好",
                        "--reviewer-type", "reader", "--draft-a-ref", "A@1", "--draft-b-ref", "B@1",
                        "--feedback-ref", "reader.md#1", "--condition", "条件X",
                        "--comparison-result", "better", "--confirm-result"])
        record = json.loads(self.logs.read_text())
        self.assertTrue(WB["qualified_evidence"](record))
        self.assertEqual(self.decisions.read_bytes(), original)

    def test_versioned_reflection_does_not_mix_or_double_count_uses(self):
        usage = self.directory / "usage"
        usage.mkdir()
        records = [dict(ts="2026-10-21T12:00:00+00:00", skill="demo", stage="写作", issue="慢",
                        impact="medium", skill_version=v, use_id=u)
                   for v, u in (("v1", "use1"), ("v1", "use1"), ("v2", "use1"))]
        records.append(dict(ts="2026-10-21T12:00:00+00:00", skill="demo", stage="写作", issue="慢", impact="medium"))
        (usage / "demo.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
        loaded, bad, _ = REFLECT["load_records"](usage)
        groups = REFLECT["group_records"](loaded)
        self.assertFalse(bad)
        self.assertEqual({g.skill_version: g.count for g in groups}, {"v1": 1, "v2": 1, "": 1})

    def test_style_reports_difference_without_instructing_a_rewrite(self):
        target = STYLE["analyze"]("他说：‘今天下雨。’\n她点头。")
        draft = dict(target)
        draft["avg_sentence_len"] = target["avg_sentence_len"] * 2
        rows = STYLE["compare"](draft, target)
        flagged = [r for r in rows if r["flagged"]]
        self.assertTrue(flagged)
        self.assertTrue(all(r["draft"] == round(draft[r["key"]], 2) for r in rows))
        self.assertIn("不要求修改", flagged[0]["comment"])
        self.assertIn("无需为对齐数值改稿", STYLE["summarize"](flagged))


if __name__ == "__main__":
    unittest.main()
