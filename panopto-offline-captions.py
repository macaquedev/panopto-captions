#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
import venv
from pathlib import Path

from caption_backend import (
    default_cookie_browser,
    default_output_dir,
    is_video_file,
    run_offline_caption_job,
)


BOOTSTRAP_ENV = "PANOPTO_CAPTIONS_BOOTSTRAPPED"


def parse_bootstrap_args():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--venv-dir", default=os.environ.get("PANOPTO_CAPTIONS_VENV", ".venv-offline"))
    parser.add_argument("--no-install", action="store_true")
    return parser.parse_known_args()


def venv_python(venv_dir):
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def ensure_venv():
    if any(arg in ("-h", "--help") for arg in sys.argv[1:]):
        return

    bootstrap_args, remaining = parse_bootstrap_args()
    if os.environ.get(BOOTSTRAP_ENV) == "1" or bootstrap_args.no_install:
        return

    repo_dir = Path(__file__).resolve().parent
    venv_dir = Path(bootstrap_args.venv_dir).expanduser()
    if not venv_dir.is_absolute():
        venv_dir = repo_dir / venv_dir

    python = venv_python(venv_dir)
    if not python.exists():
        print(f"Creating virtual environment: {venv_dir}", file=sys.stderr)
        venv.create(venv_dir, with_pip=True)

    requirements = repo_dir / "offline-requirements.txt"
    print("Installing/updating Python dependencies...", file=sys.stderr)
    subprocess.check_call([
        str(python),
        "-m",
        "pip",
        "install",
        "-r",
        str(requirements),
    ])

    env = os.environ.copy()
    env[BOOTSTRAP_ENV] = "1"
    command = [str(python), str(Path(__file__).resolve()), *remaining]
    raise SystemExit(subprocess.call(command, env=env))


def parse_args():
    parser = argparse.ArgumentParser(
        description="Download a Panopto lecture, generate offline Whisper subtitles, and open it in a player."
    )
    parser.add_argument("input", help="Panopto URL or existing video file")
    parser.add_argument("output_dir", nargs="?", default=str(default_output_dir()))
    parser.add_argument("--model", default=os.environ.get("WHISPER_MODEL", "base.en"))
    parser.add_argument("--language", default="en")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--beam-size", type=int, default=5)
    parser.add_argument("--vad-filter", action="store_true")
    parser.add_argument("--cookies-from-browser", default=default_cookie_browser())
    parser.add_argument("--cookies", default=os.environ.get("COOKIES_FILE"))
    parser.add_argument("--no-play", action="store_true", default=os.environ.get("NO_PLAY") == "1")
    parser.add_argument("--venv-dir", default=os.environ.get("PANOPTO_CAPTIONS_VENV", ".venv-offline"))
    parser.add_argument("--no-install", action="store_true")
    return parser.parse_args()


def main():
    ensure_venv()
    args = parse_args()

    if is_video_file(args.input):
        print(f"Using existing video: {Path(args.input).expanduser().resolve()}")

    run_offline_caption_job(
        args.input,
        args.output_dir,
        model=args.model,
        language=args.language,
        device=args.device,
        compute_type=args.compute_type,
        beam_size=args.beam_size,
        vad_filter=args.vad_filter,
        cookies_from_browser=args.cookies_from_browser,
        cookies_file=args.cookies,
        no_play=args.no_play,
    )


if __name__ == "__main__":
    main()
