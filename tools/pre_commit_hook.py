#!/usr/bin/env python3
"""
Pre-commit Hook for Jarvis V1
================================
Runs linting, formatting, and tests before allowing commits.

Install: python tools/install_hooks.py
Bypass:  git commit --no-verify
"""

import subprocess
import sys


def run_command(cmd: list[str], description: str) -> bool:
    """Run a command and return success status."""
    print(f"\n🔍 {description}...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")
        if result.returncode != 0:
            print(f"❌ {description} failed:")
            print(result.stdout)
            print(result.stderr)
            return False
        print(f"✅ {description} passed")
        return True
    except Exception as e:
        print(f"❌ {description} error: {e}")
        return False


def main():
    """Run pre-commit checks."""
    print("=" * 60)
    print("🔐 Running pre-commit checks...")
    print("=" * 60)

    checks = [
        (
            ["python", "-m", "black", "--check", "main.py", "ui.py", "wake_word.py", "setup.py", "actions/", "agent/", "core/", "memory/"],
            "Black formatting check",
        ),
        (
            ["python", "-m", "pylint", "--rcfile=.pylintrc", "main.py"],
            "Pylint code quality check",
        ),
        (
            ["python", "-m", "pytest", "tests/", "-v", "--tb=short"],
            "Unit tests",
        ),
    ]

    results = [run_command(cmd, desc) for cmd, desc in checks]

    print("\n" + "=" * 60)
    if all(results):
        print("✅ All checks passed! Commit allowed.")
        print("=" * 60)
        return 0
    else:
        print("❌ Some checks failed. Fix them before committing.")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
