import subprocess
import sys


def test_package_imports_from_workspace_root():
    result = subprocess.run(
        [sys.executable, "-c", "import base_agent_system"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
