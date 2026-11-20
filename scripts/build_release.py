"""Build locally, without publishing or modifying any Git references."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


RUNTIME_PACKAGES = ("pillow", "openpyxl", "et_xmlfile", "PyYAML", "customtkinter", "darkdetect", "packaging", "pypdf")


def copy_licenses(application):
    target = application / "licenses"
    target.mkdir(parents=True, exist_ok=True)
    for name in RUNTIME_PACKAGES + ("pyinstaller",):
        distribution = metadata.distribution(name)
        found = []
        for file in distribution.files or []:
            if re.match(r"(?i)^(licen[sc]e|copying|notice)([._-].*)?$", file.name):
                source = Path(distribution.locate_file(file))
                if source.is_file():
                    dest = target / name / file.name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, dest)
                    found.append(dest)
        if not found:
            raise RuntimeError(f"Installed license text missing for {name}.")
    base = Path(sys.base_prefix)
    python_license = next((base / name for name in ("LICENSE_PYTHON.txt", "LICENSE.txt") if (base / name).is_file()), None)
    if python_license is None:
        raise RuntimeError("Python runtime license text was not found.")
    shutil.copyfile(python_license, target / "Python-LICENSE.txt")
    tk_sources = [base / "Library" / "lib" / "tk8.6" / "license.terms", base / "tcl" / "tk8.6" / "license.terms"]
    tk_license = next((path for path in tk_sources if path.is_file()), None)
    if tk_license:
        shutil.copyfile(tk_license, target / "Tk-license.terms")
    # Match the actual bundled native files, including transitive libraries,
    # to Anaconda's package notices instead of maintaining a partial list.
    native = {path.name.lower() for path in application.rglob("*")
              if path.is_file() and path.suffix.lower() in {".dll", ".pyd"}}
    for record in (base / "conda-meta").glob("*.json"):
        value = json.loads(record.read_text(encoding="utf-8"))
        if not any(Path(name).name.lower() in native for name in value.get("files", [])):
            continue
        package = value["name"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", package):
            raise RuntimeError("Invalid runtime package name.")
        cache = value.get("link", {}).get("source")
        folder = Path(cache) / "info" / "licenses" if cache else None
        notices = [path for path in folder.rglob("*") if path.is_file()] if folder else []
        if not notices:
            raise RuntimeError(f"Cached runtime license text missing for {package}.")
        for path in notices:
            dest = target / ("runtime-" + package) / path.relative_to(folder)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dest)


def copy_harness_bundle(root, application, release):
    plugin = Path("integrations") / "deepseek-harness"
    for name in ("package.json", "cordis.patch.yml", "host.js", "client.js", "locale/en.json", "locale/zh.json"):
        path = plugin / name
        target = application / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / path, target)

    launcher = "Start-CourseFlow-Harness.ps1"
    (application / launcher).write_text((root / launcher).read_text(encoding="utf-8-sig"), encoding="utf-8-sig")
    guide = root / "docs" / "使用说明.md"
    shutil.copyfile(guide, application / "使用说明.md")
    sample = "插件示例课表.yaml"
    shutil.copyfile(root / "examples" / sample, application / sample)
    (application / "harness-release.json").write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")


def public_data_arguments(root):
    from courseflow.backgrounds import BACKGROUNDS

    data = root / "courseflow" / "data"
    names = ["README.md", "availability.html", "示例课表.yaml", "icon.png", "icon.ico"]
    names.extend(f"wallpaper-{preset}-{layout}.png" for preset in BACKGROUNDS for layout in ("desktop", "phone"))
    names.extend(sorted(path.name for path in data.glob("holidays-*.json") if re.fullmatch(r"holidays-[0-9]{4}\.json", path.name)))
    return [item for name in names for item in ("--add-data", f"{data / name}:courseflow/data")]


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Build a local CourseFlow bundle without publishing.")
    parser.add_argument("--output-dir", default="dist", help="Output directory inside the project.")
    parser.add_argument("--harness-plugin", action="store_true", help="Build the independent Harness plugin package.")
    args = parser.parse_args()
    sys.path.insert(0, str(root))
    from courseflow import __version__
    work = root / ".dev" / "build"
    output = root / args.output_dir
    name = "CourseFlow-Harness" if args.harness_plugin else "CourseFlow"
    application = output / name
    version = __version__
    if args.harness_plugin:
        package = json.loads((root / "integrations/deepseek-harness/package.json").read_text(encoding="utf-8"))
        version = package["version"]
        release = {"version": version, "courseflow": __version__, "harness": package["engines"]["dsh"]}
    config = root / ".dev" / "pyinstaller-cache"
    temporary = root / ".dev" / "tmp"
    for target in (work, output, config, temporary):
        if not target.resolve().is_relative_to(root):
            raise SystemExit("Build output must remain inside the project.")
        target.mkdir(parents=True, exist_ok=True)
    if args.harness_plugin and application.exists():
        raise SystemExit("Choose a fresh --output-dir for the plugin so an existing installation is preserved.")
    env = dict(os.environ, TEMP=str(temporary), TMP=str(temporary), PYINSTALLER_CONFIG_DIR=str(config))
    runtime = Path(sys.base_prefix) / "Library" / "bin"
    binaries = []
    if runtime.is_dir():
        # A venv derived from Anaconda does not carry conda-meta. Seed the
        # base runtime DLLs explicitly and expose their dependency directory
        # to this build subprocess only; never modify the user's PATH.
        env["PATH"] = str(runtime) + os.pathsep + env.get("PATH", "")
        native_libraries = ("ffi.dll", "libmpdec-4.dll")
        if not args.harness_plugin:
            native_libraries += ("tcl86t.dll", "tk86t.dll")
        for library in native_libraries:
            path = runtime / library
            if path.is_file():
                binaries.extend(["--add-binary", str(path) + ":."])
    if args.harness_plugin:
        entry = "launch_harness.py"
        options = ["--console", "--hide-console=hide-early"]
    else:
        subprocess.run([sys.executable, str(root / "scripts" / "create_icon.py")], check=True, cwd=root, env=env)
        entry = "launch_gui.py"
        options = ["--windowed", "--collect-all", "customtkinter", "--collect-submodules", "courseflow"]
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onedir", "--name", name, *options,
               "--collect-submodules", "pypdf", "--icon", str(root / "courseflow" / "data" / "icon.ico"),
               "--distpath", str(output), "--workpath", str(work), "--specpath", str(root / ".dev" / "spec"),
               *public_data_arguments(root), *binaries, str(root / entry)]
    subprocess.run(command, check=True, cwd=root, env=env)
    shutil.copyfile(root / "LICENSE", application / "LICENSE.txt")
    shutil.copyfile(root / "THIRD_PARTY.md", application / "THIRD_PARTY.md")
    shutil.copyfile(root / "courseflow" / "data" / "README.md", application / "holiday-data-license.md")
    guide = root / "docs" / "使用说明.md"
    if args.harness_plugin:
        copy_harness_bundle(root, application, release)
    elif guide.exists():
        shutil.copyfile(guide, application / "使用说明.md")
    copy_licenses(application)
    records = []
    for path in sorted(application.rglob("*")):
        if path.is_file():
            records.append({"file": path.relative_to(application).as_posix(), "bytes": path.stat().st_size,
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    dependencies = {name: metadata.version(name) for name in RUNTIME_PACKAGES + ("pyinstaller",)}
    manifest = {"version": version, "python": sys.version, "dependencies": dependencies, "files": records}
    manifest_name = "harness-build-manifest.json" if args.harness_plugin else "build-manifest.json"
    (root / ".dev" / manifest_name).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    archive = Path(shutil.make_archive(str(output / f"{name}-{version}-windows-x64"), "zip", root_dir=output, base_dir=name))
    if args.harness_plugin:
        sha256 = hashlib.sha256(archive.read_bytes()).hexdigest()
        (output / "SHA256SUMS.txt").write_bytes(f"{sha256}  {archive.name}\n".encode("ascii"))
    print("Built for local review:", archive)


if __name__ == "__main__":
    main()
