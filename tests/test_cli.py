import subprocess
import sys


def invoke(*args):
    return subprocess.run([sys.executable, "-m", "quoteguard", *args],
                          text=True, capture_output=True, timeout=30)


def test_cli_bad_parameters_and_missing_file(tmp_path):
    assert invoke("collect", "--minutes", "nan", "--out", str(tmp_path / "x")).returncode == 2
    assert invoke("analyze", "--input", str(tmp_path / "missing"), "--out", str(tmp_path / "r")).returncode == 2
    result = invoke("--help")
    assert result.returncode == 0 and "collect" in result.stdout


def test_demo_then_analyze_cli(tmp_path):
    demo = tmp_path / "demo"
    first = invoke("demo", "--out", str(demo))
    assert first.returncode == 0, first.stderr
    assert '"source": "synthetic"' in first.stdout
    second = invoke("analyze", "--input", str(demo / "synthetic.jsonl"), "--out", str(tmp_path / "replay"))
    assert second.returncode == 0, second.stderr
    assert (demo / "summary.json").read_bytes() == (tmp_path / "replay" / "summary.json").read_bytes()
