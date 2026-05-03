#!/usr/bin/env python3
"""
Install Git Hooks
=================
Installs pre-commit hooks to enforce code quality.

Run: python tools/install_hooks.py
"""

import shutil
import subprocess
from pathlib import Path


def install_hooks():
    """Install git pre-commit hooks."""
    repo_root = Path(__file__).parent.parent
    hooks_dir = repo_root / ".git" / "hooks"
    hook_file = hooks_dir / "pre-commit"

    # Check if .git exists
    if not (repo_root / ".git").exists():
        print("❌ .git directory not found. Initialize git first.")
        return False

    # Create hooks directory
    hooks_dir.mkdir(parents=True, exist_ok=True)

    # Read hook script
    hook_script = repo_root / "tools" / "pre_commit_hook.py"
    if not hook_script.exists():
        print(f"❌ Hook script not found: {hook_script}")
        return False

    # Create wrapper that calls Python script
    hook_content = f"""#!/bin/bash
cd "{repo_root}"
python "{hook_script}" "$@"
"""

    # Write hook file
    hook_file.write_text(hook_content)
    hook_file.chmod(0o755)

    print(f"✅ Pre-commit hook installed at {hook_file}")
    print("   Checks: black formatting, pylint, pytest")
    print("   To bypass: git commit --no-verify")
    return True


if __name__ == "__main__":
    if install_hooks():
        print("\n✅ Git hooks installation complete!")
    else:
        print("\n❌ Git hooks installation failed!")
