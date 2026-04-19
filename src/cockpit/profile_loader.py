"""Load and validate workspace profiles from YAML config files."""
from __future__ import annotations
from pathlib import Path
import yaml


def load_profile(name: str, profiles_dir: Path) -> dict:
    path = profiles_dir / f"{name}.yaml"
    if not path.exists():
        available = [p.stem for p in profiles_dir.glob("*.yaml")]
        hint = f"  Available: {', '.join(available)}" if available else "  No profiles found."
        raise FileNotFoundError(f"Profile '{name}' not found at {path}\n{hint}")
    with path.open() as f:
        profile = yaml.safe_load(f)
    if profile is None:
        raise ValueError(f"Profile '{name}' is empty.")
    _expand_paths(profile)
    return profile


def _expand_paths(profile: dict) -> None:
    if "repo_root" in profile:
        profile["repo_root"] = str(Path(profile["repo_root"]).expanduser().resolve())
    for pane in profile.get("panes", {}).values():
        if "cwd" in pane:
            pane["cwd"] = str(Path(pane["cwd"]).expanduser().resolve())


def validate_profile(profile: dict) -> list[str]:
    errors: list[str] = []
    for key in ("name", "session_name", "repo_root"):
        if key not in profile:
            errors.append(f"Missing required field: {key}")
    if "repo_root" in profile:
        rr = Path(profile["repo_root"])
        if not rr.exists():
            errors.append(f"repo_root does not exist: {rr}")
        elif not rr.is_dir():
            errors.append(f"repo_root is not a directory: {rr}")
    return errors
