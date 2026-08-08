from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = sorted((ROOT / "scripts").glob("vps_worker_*.sh"))


class VpsWorkerScriptTests(unittest.TestCase):
    def test_all_worker_scripts_have_valid_bash_syntax(self) -> None:
        subprocess.run(["bash", "-n", *(str(path) for path in SCRIPTS)], check=True)

    def test_common_rejects_destructive_repo_target_override(self) -> None:
        env = {
            **os.environ,
            "VPS_HOST": "test-host",
            "REMOTE_REPO_DIR": "/workspace/repos/not-the-requested-repo",
        }
        result = subprocess.run(
            ["bash", "-c", "source scripts/vps_worker_common.sh"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("REMOTE_REPO_DIR must be exactly", result.stderr)

    def test_container_selection_requires_exactly_one_or_an_explicit_name(self) -> None:
        env = {**os.environ, "VPS_HOST": "test-host"}
        result = subprocess.run(
            ["bash", "-c", "source scripts/vps_worker_common.sh; agentbox_remote_prefix"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertIn("expected exactly one running agentbox container", result.stdout)
        self.assertNotIn("head -n1", result.stdout)

    def test_run_notifies_when_worker_exits_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fake_python = root / "python"
            event_log = root / "events.log"
            fake_python.write_text(
                "#!/usr/bin/env bash\n"
                'if [[ "$1" == "scripts/index_cbs_exes.py" ]]; then exit 7; fi\n'
                "while [[ $# -gt 0 ]]; do\n"
                '  if [[ "$1" == "--event" ]]; then printf \'%s\\n\' "$2" >> "$EVENT_LOG"; exit 0; fi\n'
                "  shift\n"
                "done\n"
                "exit 0\n",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)
            env = {
                **os.environ,
                "PYTHON_BIN": str(fake_python),
                "EVENT_LOG": str(event_log),
                "OUT_DIR": str(root / "results"),
                "TMP_DIR": str(root / "tmp"),
                "STATUS_INTERVAL_SECONDS": "1",
            }
            result = subprocess.run(
                ["bash", "scripts/vps_worker_run.sh"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 7)
            self.assertEqual(event_log.read_text(encoding="utf-8").splitlines(), ["start", "error"])


if __name__ == "__main__":
    unittest.main()
