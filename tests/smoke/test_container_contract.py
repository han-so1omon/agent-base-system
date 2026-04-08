from pathlib import Path


def test_container_files_define_runtime_and_cli_contract() -> None:
    dockerfile = Path("Dockerfile")
    dockerignore = Path(".dockerignore")
    pyproject = Path("pyproject.toml")
    config = Path("src/base_agent_system/config.py")
    smoke_script = Path("scripts/container-smoke.sh")
    kind_deploy_script = Path("scripts/deploy-kind.sh")
    kind_bootstrap_script = Path("scripts/bootstrap-kind.sh")

    assert dockerfile.exists(), "Dockerfile is missing"
    assert dockerignore.exists(), ".dockerignore is missing"
    assert pyproject.exists(), "pyproject.toml is missing"
    assert config.exists(), "config.py is missing"
    assert smoke_script.exists(), "container smoke script is missing"
    assert kind_deploy_script.exists(), "kind deploy script is missing"
    assert kind_bootstrap_script.exists(), "kind bootstrap script is missing"

    dockerfile_text = dockerfile.read_text()
    dockerignore_text = dockerignore.read_text()
    pyproject_text = pyproject.read_text()
    config_text = config.read_text()
    smoke_script_text = smoke_script.read_text()
    kind_deploy_text = kind_deploy_script.read_text()
    kind_bootstrap_text = kind_bootstrap_script.read_text()

    assert "EXPOSE 8000" in dockerfile_text
    assert 'CMD ["api"]' in dockerfile_text
    assert 'ENTRYPOINT ["python", "-m", "base_agent_system.container"]' in dockerfile_text
    assert "FROM node:" in dockerfile_text
    assert "npm ci" in dockerfile_text
    assert "npm run build" in dockerfile_text
    assert "src/" in dockerfile_text
    assert "COPY docs/seed/ ./docs/seed/" in dockerfile_text
    assert "web/out" in dockerfile_text
    assert "./web-static/" in dockerfile_text

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
    assert '"langchain"' in pyproject_text
    assert '"langchain-openai"' in pyproject_text
    assert "psycopg[binary]" in pyproject_text
    assert "BASE_AGENT_SYSTEM_LLM_MODEL" in config_text
    assert "BASE_AGENT_SYSTEM_AI_GATEWAY_API_KEY_NAME" not in config_text
    assert "BASE_AGENT_SYSTEM_AI_GATEWAY_BASE_URL" not in config_text

    assert "curl -fsS http://127.0.0.1:8000/live" in smoke_script_text
    assert "curl -fsS http://127.0.0.1:8000/ready" in smoke_script_text
    assert 'IMAGE_TAG="${IMAGE_TAG:-kind-' in kind_deploy_text
    assert 'kind load docker-image "$IMAGE_REF"' in kind_deploy_text
    assert '--set image.tag="$IMAGE_TAG"' in kind_deploy_text
    assert './scripts/deploy-kind.sh' in kind_bootstrap_text
