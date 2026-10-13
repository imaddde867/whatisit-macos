import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "tools/roihu_teacher_pilot.sbatch"


class RoihuTeacherPilotTest(unittest.TestCase):
    def test_requires_model_revision_before_loading_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            module_marker = root / "module-called"
            module = bin_dir / "module"
            module.write_text(f"#!/bin/sh\ntouch '{module_marker}'\n")
            module.chmod(0o755)

            env = os.environ | {
                "PATH": f"{bin_dir}:{os.environ['PATH']}",
                "SLURM_JOB_ACCOUNT": "project_test",
                "SLURM_JOB_ID": "test",
                "MODEL_REV": "",
                "P": str(root / "pilot"),
                "TMPDIR": str(root),
            }
            result = subprocess.run(
                ["bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=5
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("MODEL_REV is required", result.stderr + result.stdout)
            self.assertFalse(module_marker.exists())

    def test_pins_model_and_tokenizer_to_required_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            args_file = root / "srun-args"
            sample_args_file = root / "sample-args"
            for name, body in {
                "module": "#!/bin/sh\nexit 0\n",
                "srun": '#!/bin/sh\nprintf "%s\\n" "$@" > "$SRUN_ARGS_FILE"\n',
                "curl": '#!/bin/sh\nfor _ in $(seq 100); do [ -s "$SRUN_ARGS_FILE" ] && exit 0; sleep 0.01; done\nexit 1\n',
                "python3": '#!/bin/sh\nif [ "$1" = "$P/teacher_sample.py" ]; then printf "%s\\n" "$@" > "$SAMPLE_ARGS_FILE"; fi\n',
            }.items():
                command = bin_dir / name
                command.write_text(body)
                command.chmod(0o755)

            env = os.environ | {
                "PATH": f"{bin_dir}:{os.environ['PATH']}",
                "SLURM_JOB_ACCOUNT": "project_test",
                "SLURM_JOB_ID": "test",
                "MODEL_REV": "0123456789abcdef",
                "P": str(root / "pilot"),
                "SAMPLE_ARGS_FILE": str(sample_args_file),
                "SIF": "test.sif",
                "SRUN_ARGS_FILE": str(args_file),
                "TMPDIR": str(root),
            }
            result = subprocess.run(
                ["bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=5
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue(args_file.exists())
            self.assertTrue(sample_args_file.exists())
            args = args_file.read_text().splitlines()
            self.assertEqual(args[args.index("--revision") + 1], "0123456789abcdef")
            self.assertEqual(args[args.index("--tokenizer-revision") + 1], "0123456789abcdef")
            sample_args = sample_args_file.read_text().splitlines()
            self.assertEqual(sample_args[sample_args.index("--quant") + 1], "FP8 checkpoint, revision 0123456789abcdef")


if __name__ == "__main__":
    unittest.main()
