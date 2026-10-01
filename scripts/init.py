#!/usr/bin/env python3
"""Create local credentials and initial service configs without replacing user data."""

import json
import os
import re
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRET_KEYS = (
    "NAPCAT_WEBUI_TOKEN",
    "ASTRBOT_DASHBOARD_INITIAL_PASSWORD",
    "ONEBOT_ACCESS_TOKEN",
)


def read_env(text: str) -> dict[str, str]:
    """Read this template's literal KEY=value format; never execute shell input."""
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep:
            raise ValueError(f"Invalid .env line for {key!r}")
        values[key.strip()] = value.strip().strip("\"'")
    return values


def create_json(path: Path, value: dict) -> None:
    if path.exists():
        print(f"Preserved {path.relative_to(ROOT)}")
        return
    # Readable by the container's configured user; data/ itself is private.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(f"Created {path.relative_to(ROOT)}")


def main() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        # Refuse to silently rotate credentials for an existing installation.
        data_path = ROOT / "data"
        if data_path.exists() and any(data_path.iterdir()):
            raise ValueError("data/ already exists: restore its original .env before initializing.")
        template = (ROOT / ".env.example").read_text(encoding="utf-8")
        defaults = read_env(template)
        for key in SECRET_KEYS:
            template = template.replace(defaults[key], "Ab1_" + secrets.token_urlsafe(32))
        template = template.replace("NAPCAT_UID=1000", f"NAPCAT_UID={os.getuid()}")
        template = template.replace("NAPCAT_GID=1000", f"NAPCAT_GID={os.getgid()}")
        fd = os.open(env_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(template)
        print("Created .env (credentials are not printed)")

    values = read_env(env_path.read_text(encoding="utf-8"))
    for key in SECRET_KEYS:
        value = values.get(key, "")
        if value.startswith("CHANGE_ME") or not re.fullmatch(r"[A-Za-z0-9_-]{24,}", value):
            raise ValueError(f"{key} must be a generated credential, not an example placeholder.")

    (ROOT / "data").mkdir(mode=0o700, exist_ok=True)
    for folder in ("astrbot", "napcat/config", "napcat/qq"):
        (ROOT / "data" / folder).mkdir(parents=True, exist_ok=True)

    napcat = json.loads((ROOT / "config/napcat-onebot.example.json").read_text())
    napcat["network"]["websocketClients"][0]["token"] = values["ONEBOT_ACCESS_TOKEN"]
    create_json(ROOT / "data/napcat/config/onebot11.json", napcat)

    astrbot = json.loads((ROOT / "config/astrbot.example.json").read_text())
    astrbot["platform"][0]["ws_reverse_token"] = values["ONEBOT_ACCESS_TOKEN"]
    create_json(ROOT / "data/astrbot/cmd_config.json", astrbot)

    print("Ready. Run: docker compose up -d")
    print("Next: QQ QR login, AstrBot administrator and conversation whitelist, then /ping.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Initialization stopped: {exc}") from exc
