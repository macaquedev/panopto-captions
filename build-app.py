#!/usr/bin/env python3
import argparse
import importlib.util
import os
import platform
import subprocess
import sys
import venv
from pathlib import Path


APP_NAME = "Panopto Offline Captions"
BOOTSTRAP_ENV = "PANOPTO_CAPTIONS_BUILD_BOOTSTRAPPED"


def parse_args():
    parser = argparse.ArgumentParser(description="Build a standalone GUI app with PyInstaller.")
    parser.add_argument("--onefile", action="store_true", help="Build a single executable instead of an app folder.")
    parser.add_argument("--console", action="store_true", help="Keep a console window for debugging.")
    parser.add_argument("--venv-dir", default=os.environ.get("PANOPTO_CAPTIONS_BUILD_VENV", ".venv-build"))
    parser.add_argument("--no-install", action="store_true", help="Skip dependency install when already prepared.")
    return parser.parse_args()


def venv_python(venv_dir):
    if platform.system().lower() == "windows":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def running_in_venv():
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def ensure_build_venv(args, repo_dir):
    if args.no_install or os.environ.get(BOOTSTRAP_ENV) == "1" or running_in_venv():
        return

    venv_dir = Path(args.venv_dir).expanduser()
    if not venv_dir.is_absolute():
        venv_dir = repo_dir / venv_dir

    python = venv_python(venv_dir)
    if not python.exists():
        print(f"Creating build virtual environment: {venv_dir}", file=sys.stderr)
        venv.create(venv_dir, with_pip=True)

    env = os.environ.copy()
    env[BOOTSTRAP_ENV] = "1"
    command = [str(python), str(Path(__file__).resolve()), *sys.argv[1:]]
    raise SystemExit(subprocess.call(command, cwd=repo_dir, env=env))


def main():
    args = parse_args()
    repo_dir = Path(__file__).resolve().parent
    ensure_build_venv(args, repo_dir)

    if not args.no_install:
        subprocess.check_call([
            sys.executable,
            "-m",
            "pip",
            "install",
            "-r",
            str(repo_dir / "offline-requirements.txt"),
            "-r",
            str(repo_dir / "packaging-requirements.txt"),
        ])

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        APP_NAME,
        "--hidden-import",
        "caption_backend",
        "--collect-all",
        "yt_dlp",
    ]

    for package in [
        "faster_whisper",
        "ctranslate2",
        "tokenizers",
        "huggingface_hub",
        "av",
        "secretstorage",
        "jeepney",
        "cryptography",
    ]:
        if importlib.util.find_spec(package):
            command.extend(["--collect-all", package])

    if args.onefile:
        command.append("--onefile")

    if not args.console:
        command.append("--windowed")

    if platform.system().lower() == "darwin":
        command.extend(["--osx-bundle-identifier", "uk.ac.cam.panopto-offline-captions"])

    command.append(str(repo_dir / "panopto-caption-gui.py"))
    subprocess.check_call(command, cwd=repo_dir)

    print()
    print("Build finished.")
    print(f"Output directory: {repo_dir / 'dist'}")


if __name__ == "__main__":
    main()
