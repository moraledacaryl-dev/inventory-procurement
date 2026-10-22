"""Guard the production release and Actions certification contract.

Only reads repository files. Never executes a native deploy or touches live data.
"""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
WORKFLOWS=(
    "ci.yml", "browser-acceptance.yml", "resilience-assurance.yml",
    "deployment-validation.yml", "native-deployment-validation.yml",
    "visual-certification.yml",
)


def test_required_release_checks_keep_main_push_and_pr_triggers():
    for name in WORKFLOWS:
        text=(ROOT / ".github" / "workflows" / name).read_text()
        assert "  push:" in text, name
        assert "    branches: [main]" in text, name
        assert "  pull_request:" in text, name
        assert "  group: ${{ github.workflow }}-${{ github.event_name }}-${{ github.ref }}" in text, name
        assert "  cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in text, name
        # Main runs cannot be cancelled by a newer main commit, because every
        # exact-SHA source release requires five independently green push gates.
        assert "github.ref != 'refs/heads/main'" not in text, name


def test_native_installer_restores_generated_file_on_any_exit():
    script=(ROOT / "deploy" / "install-native.sh").read_text()
    assert "trap restore_generated_frontend_declaration EXIT" in script
    assert 'local original_status=$?' in script
    assert 'git -C "$APP_DIR" restore -- frontend/next-env.d.ts' in script
    assert 'exit "$original_status"' in script
    assert script.index("trap restore_generated_frontend_declaration EXIT") < script.index('rm -rf "$APP_DIR/frontend/node_modules"')
