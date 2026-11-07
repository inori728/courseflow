"""Check public source grammar, punctuation, local paths, and bundled resources."""
from __future__ import annotations

import ast
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
PUNCTUATION = set("\uff0c\u3002\uff1b\uff1a\uff1f\uff01\u3001\uff08\uff09\u3010\u3011\u300a\u300b\u201c\u201d\u2018\u2019\u2026\u2014\u2013")
LOCAL_PATH = re.compile(r"(?i)(?:[a-z]:[/\\](?:users|anaconda|courseflow-build)[/\\]|/Users/[^/]+/)")
SECRET = re.compile(r"(?:sk-[A-Za-z0-9_-]{24,}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----)")


def public_files():
    try:
        result = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                                cwd=ROOT, check=True, capture_output=True)
        return sorted({ROOT / name for name in result.stdout.decode("utf-8").split("\0") if name})
    except (OSError, subprocess.CalledProcessError):
        folders = [ROOT / name for name in ("courseflow", "scripts", "tests", "docs", "examples", ".github")]
        return sorted({path for folder in folders for path in folder.rglob("*") if path.is_file()
                       and "__pycache__" not in path.parts} | {path for path in ROOT.glob("*") if path.is_file()
                       and path.name in {"README.md", "ARCHITECTURE.md", "CONTRIBUTING.md", "CHANGELOG.md",
                                         "THIRD_PARTY.md", "pyproject.toml", "requirements.txt", ".gitignore",
                                         "launch_gui.py", "Start-CourseFlow.ps1", "LICENSE"}})


def main():
    errors = []
    files = public_files()
    python_count = 0
    for path in files:
        if not path.is_file() or path.suffix.lower() in {".png", ".ico", ".gif", ".xlsx", ".jpg"}:
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            continue
        relative = path.relative_to(ROOT).as_posix()
        if path.suffix == ".py":
            python_count += 1
            try:
                ast.parse(text, filename=relative, feature_version=(3, 9))
            except SyntaxError as exc:
                errors.append(f"{relative}:{exc.lineno}: Python 3.9 grammar: {exc.msg}")
        code = path.suffix.lower() in {".py", ".ps1", ".toml", ".txt", ".html", ".yml", ".yaml"} or path.name == ".gitignore"
        exempt = "examples" in path.relative_to(ROOT).parts or path.name == "示例课表.yaml"
        for number, line in enumerate(text.splitlines(), 1):
            if code and not exempt and not (path.name == "parsing.py" and line.startswith("_EDGE = ")):
                chars = PUNCTUATION.intersection(line)
                if chars:
                    errors.append(f"{relative}:{number}: use ASCII punctuation or functional Unicode escapes")
            # These are test patterns, not actual private paths or credentials.
            if path.name != "check_source.py" and (LOCAL_PATH.search(line) or SECRET.search(line)):
                errors.append(f"{relative}:{number}: possible private path, identifier, or secret")
    data = ROOT / "courseflow" / "data"
    for name in ("示例课表.yaml", "holidays-2026.json", "availability.html", "icon.png", "icon.ico"):
        if not (data / name).is_file():
            errors.append(f"missing bundled resource: {name}")
    if (ROOT / "docs" / "index.html").read_bytes() != (data / "availability.html").read_bytes():
        errors.append("point-grid copies differ")
    if errors:
        print("\n".join(errors))
        return 1
    print(f"Checked {len(files)} public files, {python_count} Python files: grammar, punctuation, privacy patterns, resources OK.")
    print("Pattern checks supplement manual review; they do not prove the absence of all sensitive data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
