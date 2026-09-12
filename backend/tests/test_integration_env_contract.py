from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ENV_TEMPLATES = (
    ".env.example",
    ".env.production.example",
    "deploy/env/inventory-backend.env.example",
)


def _template(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_environment_templates_document_all_inbound_tokens():
    required = {
        "STAFF_INTEGRATION_TOKEN",
        "COMMAND_CENTER_INTEGRATION_TOKEN",
        "ACCOUNTING_INTEGRATION_TOKEN",
        "POS_INTEGRATION_TOKEN",
    }
    for name in ENV_TEMPLATES:
        text = _template(name)
        for variable in required:
            assert f"{variable}=" in text, f"{name} is missing {variable}"


def test_environment_templates_match_outbound_worker_contract():
    for name in ENV_TEMPLATES:
        text = _template(name)
        assert '"accounting":"https://accounting.hiddenoasis.app"' in text
        assert '"operations":"https://operations.hiddenoasis.app"' in text
        assert "INTEGRATION_API_KEY=" in text
        assert "OPERATIONS_INTEGRATION_KEY=" in text
        assert '"command-center":' not in text
        assert '"staff":' not in text
        assert '"pos":' not in text
