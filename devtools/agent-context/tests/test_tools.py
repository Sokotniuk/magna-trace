"""Offline checks with independent bounds and synthetic usage records."""

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


context = load_module("b_context_pack", HERE / "context_pack.py")
usage = load_module("b_usage_gate", HERE / "usage_gate.py")


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        subprocess.run(["git", "init", "-q", "-b", "feature/student-b-local-ready", str(self.repo)], check=True)
        self.task_path = HERE / "examples/b4-review.json"
        self.task = context.parse_task(self.task_path)
        self.write("student_b/cases.py", "# case expiry lock\n# Контекст B4\n" + "case\n" * 30)
        self.write("unrelated.txt", "unrelated words\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)

    def write(self, name, text):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def pack(self, files=None, budget=12000):
        return context.build_pack(self.task, self.repo, "case expiry lock", files or ["student_b/cases.py"], budget)

    def test_actual_cli_bytes_and_exact_budget(self):
        pack = self.pack()
        size = pack["used_bytes"]
        cmd = [sys.executable, str(HERE / "context_pack.py"), str(self.task_path), str(self.repo), "case expiry lock", "--file", "student_b/cases.py", "--budget-bytes", str(size)]
        run = subprocess.run(cmd, capture_output=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout)
        self.assertEqual(len(run.stdout), result["used_bytes"])
        self.assertLessEqual(len(run.stdout), size)
        self.assertEqual(result["mandatory"]["must_not"], list(self.task.must_not))
        self.assertEqual(result["optional"][0]["path"], "student_b/cases.py")

    def test_mandatory_too_large_fails_without_output(self):
        with self.assertRaises(context.ContextError):
            self.pack(budget=256)

    def test_low_budget_omits_excerpt_without_shortening_task(self):
        full = self.pack()
        small = self.pack(budget=full["used_bytes"] - 10)
        self.assertEqual(small["mandatory"], full["mandatory"])
        self.assertEqual(small["optional"], [])
        self.assertEqual(small["omitted"], ["student_b/cases.py"])

    def test_working_file_version_and_hash_are_used(self):
        before = self.pack()["optional"][0]
        self.write("student_b/cases.py", "# case expiry lock changed\n")
        after = self.pack()["optional"][0]
        self.assertNotEqual(before["sha256"], after["sha256"])
        self.assertIn("changed", after["excerpt"])

    def test_invalid_candidates(self):
        self.write("untracked.py", "case")
        self.write("binary.dat", "case\0")
        self.write("large.txt", "x" * 65_537)
        (self.repo / "link.py").symlink_to(self.repo / "student_b/cases.py")
        subprocess.run(["git", "-C", str(self.repo), "add", "binary.dat", "large.txt", "link.py"], check=True)
        for name in ("../escape.py", "/etc/passwd", "untracked.py", "binary.dat", "large.txt", "link.py", ".git/config"):
            with self.subTest(name=name), self.assertRaises(context.ContextError):
                self.pack([name])

    def test_branch_mismatch_and_non_git_root(self):
        subprocess.run(["git", "-C", str(self.repo), "checkout", "-q", "-b", "feature/wrong"], check=True)
        with self.assertRaises(context.ContextError):
            self.pack()
        with self.assertRaises(context.ContextError):
            context.build_pack(self.task, self.repo / "student_b", "case", ["cases.py"], 12000)

    def test_duplicates_and_irrelevant_candidates(self):
        with self.assertRaises(context.ContextError):
            self.pack(["student_b/cases.py"] * 2)
        result = self.pack(["unrelated.txt"])
        self.assertEqual(result["optional"], [])
        self.assertEqual(result["omitted"], ["unrelated.txt"])

    def test_task_rejects_unknown_or_duplicate_fields(self):
        path = self.write("task.json", '{"identifier":"B4","identifier":"B5"}')
        with self.assertRaises(context.TaskError):
            context.parse_task(path)
        path.write_text('{"unexpected":true}')
        with self.assertRaises(context.TaskError):
            context.parse_task(path)


class UsageTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads((HERE / "examples/usage-record.json").read_text())

    def test_synthetic_totals(self):
        result = usage.decide(self.record)
        self.assertEqual(result["decision"], "ALLOW_NEXT_CONTROLLED_STEP")
        self.assertEqual((result["input_tokens"], result["output_tokens"], result["cost_usd"]), (100, 20, "0.01"))

    def test_step_time_and_cost_stops(self):
        for key, value, reason in (("max_steps", 1, "MAX_STEPS_REACHED"), ("max_elapsed_ms", 1000, "MAX_ELAPSED_REACHED"), ("soft_cost_usd", "0.01", "SOFT_COST_REACHED")):
            record = copy.deepcopy(self.record)
            record["limits"][key] = value
            with self.subTest(reason=reason):
                result = usage.decide(record)
                self.assertEqual(result["decision"], "SOFT_STOP")
                self.assertIn(reason, result["reasons"])

    def test_unknown_cost_stops_under_cap(self):
        step = self.record["steps"][0]
        step.update(cost_usd=None, cost_provenance="unknown", price_source=None, input_tokens=None)
        result = usage.decide(self.record)
        self.assertEqual(result["decision"], "SOFT_STOP")
        self.assertIn("COST_UNKNOWN_UNDER_SOFT_CAP", result["reasons"])
        self.assertEqual(result["input_tokens"], "UNKNOWN")

    def test_mismatched_selection_rejected(self):
        self.record["steps"][0]["model"] = "OTHER_MODEL"
        with self.assertRaises(usage.GateError):
            usage.decide(self.record)

    def test_soft_stop_cli_still_returns_zero(self):
        self.record["limits"]["max_steps"] = 1
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "usage.json"
            path.write_text(json.dumps(self.record))
            run = subprocess.run([sys.executable, str(HERE / "usage_gate.py"), str(path)], capture_output=True)
        self.assertEqual(run.returncode, 0)
        self.assertEqual(json.loads(run.stdout)["decision"], "SOFT_STOP")


if __name__ == "__main__":
    unittest.main()
