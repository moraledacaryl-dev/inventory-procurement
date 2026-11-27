"""Fail closed before importing application settings or opening any database."""
import json
import os
from pathlib import Path
import secrets
import sys


def configure(root: Path) -> Path:
    if root.is_symlink():
        raise RuntimeError("Training data directory cannot be a symlink")
    root = root.expanduser().resolve()
    if os.environ.get("APP_ENV", "training") != "training":
        raise RuntimeError("Training requires APP_ENV=training")
    if root.name != "inventory-training" or root.is_symlink():
        raise RuntimeError("Use a dedicated inventory-training data directory")
    forbidden = [key for key, value in os.environ.items() if value and (
        key in {"DATABASE_URL", "JWT_SECRET", "BOOTSTRAP_OWNER_PASSWORD", "INTERNAL_API_URL", "NEXT_PUBLIC_API_URL"}
        or "INTEGRATION" in key or key.startswith(("PGHOST", "PGDATABASE", "PGUSER", "PGPASSWORD"))
    )]
    if forbidden:
        raise RuntimeError("Training refuses inherited database, API, credential or integration configuration: " + ", ".join(sorted(forbidden)))
    if (Path.cwd().parent / ".env").exists() or (Path.cwd() / ".env").exists():
        raise RuntimeError("Run training from a separate checkout without an operational .env file")
    training_origin = os.environ.get("INVENTORY_TRAINING_ORIGIN", "")
    if training_origin not in {"", "https://inventory-training.hiddenoasis.app"}:
        raise RuntimeError("Only the dedicated Inventory training origin is allowed")
    # An adjacent production .env must never be read by BaseSettings.
    from app.core.config import Settings
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name=="posix":root.chmod(0o700)
    marker = root / "training-only.json"
    expected = {"application": "hidden-oasis-inventory-training", "schema": 1}
    if marker.exists():
        if marker.is_symlink() or json.loads(marker.read_text()) != expected:
            raise RuntimeError("Invalid training directory marker")
    elif any(root.iterdir()):
        raise RuntimeError("Refusing an unmarked nonempty training directory")
    else:
        marker.write_text(json.dumps(expected))
    secret_file = root / "session-key"
    if secret_file.is_symlink():
        raise RuntimeError("Training session key cannot be a symlink")
    if not secret_file.exists():
        descriptor = os.open(secret_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(secrets.token_hex(48))
    secret = secret_file.read_text().strip()
    if len(secret) < 64:
        raise RuntimeError("Invalid training session key")
    # Clear the cached instance made on importing config; no DB module has loaded.
    import app.core.config as config
    config.get_settings.cache_clear()
    config.settings = Settings(_env_file=None, app_env="training",
        database_url=f"sqlite:///{root / 'registry.db'}", jwt_secret=secret,
        cors_origins=["http://127.0.0.1:3400", "http://localhost:3400"] + ([training_origin] if training_origin else []),
        trusted_hosts=["localhost", "127.0.0.1", "testserver"] + (["inventory-training.hiddenoasis.app"] if training_origin else []))
    return root


def deny_network(event, args):
    # socket.connect covers HTTP clients and raw sockets, including loopback,
    # private addresses and DNS rebinding. Accepted inbound sockets still work.
    if event in {"socket.connect", "socket.getaddrinfo", "socket.gethostbyname", "socket.sendto"}:
        raise PermissionError("Training cannot initiate network connections")


def install_network_guard():
    sys.addaudithook(deny_network)
