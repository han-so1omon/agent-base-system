from pathlib import Path


def test_container_files_define_runtime_and_cli_contract() -> None:
    dockerfile = Path("Dockerfile")
    dockerignore = Path(".dockerignore")
    pyproject = Path("pyproject.toml")
    smoke_script = Path("scripts/container-smoke.sh")

    assert dockerfile.exists(), "Dockerfile is missing"
    assert dockerignore.exists(), ".dockerignore is missing"
    assert pyproject.exists(), "pyproject.toml is missing"
    assert smoke_script.exists(), "container smoke script is missing"

    dockerfile_text = dockerfile.read_text()
    dockerignore_text = dockerignore.read_text()
    pyproject_text = pyproject.read_text()
    smoke_script_text = smoke_script.read_text()

    assert "EXPOSE 8000" in dockerfile_text
    assert 'CMD ["api"]' in dockerfile_text
    assert 'ENTRYPOINT ["python", "-m", "base_agent_system.container"]' in dockerfile_text
    assert "src/" in dockerfile_text
    assert "COPY docs/seed/ ./docs/seed/" in dockerfile_text

    container_entrypoint = Path("src/base_agent_system/container.py")
    assert container_entrypoint.exists(), "container entrypoint module is missing"
    entrypoint_text = container_entrypoint.read_text()
    assert "uvicorn" in entrypoint_text
    assert "base_agent_system.api.app:create_app" in entrypoint_text
    assert "os.execvp" in entrypoint_text
    assert "subprocess.call" not in entrypoint_text

    assert ".pytest_cache/" in dockerignore_text
    assert "__pycache__/" in dockerignore_text
    assert "docs/" not in dockerignore_text
    assert "psycopg[binary]" in pyproject_text

    assert "curl -fsS http://127.0.0.1:8000/live" in smoke_script_text
    assert "curl -fsS http://127.0.0.1:8000/ready" in smoke_script_text
