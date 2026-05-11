import html
import os
import platform
import shutil
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def default_cookie_browser():
    if os.environ.get("COOKIES_FROM_BROWSER"):
        return os.environ["COOKIES_FROM_BROWSER"]

    if platform.system().lower() == "linux":
        return "vivaldi+gnomekeyring"
    return "chrome"


def video_id_from_url(url):
    query = parse_qs(urlparse(url).query)
    return (query.get("id") or ["lecture"])[0]


def is_video_file(value):
    return Path(value).expanduser().exists()


def run_offline_caption_job(
    input_value,
    output_dir,
    model="base.en",
    language="en",
    device="cpu",
    compute_type="int8",
    beam_size=5,
    vad_filter=False,
    cookies_from_browser=None,
    no_play=False,
    log=None,
):
    output_dir = Path(output_dir).expanduser().resolve()
    if is_video_file(input_value):
        video_path = Path(input_value).expanduser().resolve()
    else:
        video_path = download_video(
            input_value,
            output_dir,
            cookies_from_browser or default_cookie_browser(),
            log=log,
        ).resolve()

    srt_path, vtt_path = transcribe_video(
        video_path,
        model=model,
        language=language,
        device=device,
        compute_type=compute_type,
        beam_size=beam_size,
        vad_filter=vad_filter,
        log=log,
    )
    open_video(video_path, srt_path, no_play=no_play, log=log)
    return video_path, srt_path, vtt_path


def download_video(url, output_dir, cookies_from_browser, log=None):
    try:
        from yt_dlp import YoutubeDL
    except ImportError as exc:
        raise RuntimeError("yt-dlp is not installed") from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    video_id = video_id_from_url(url)
    output_template = str(output_dir / "%(title).180B [%(id)s].%(ext)s")

    emit(log, "Downloading lecture with yt-dlp...")
    emit(log, f"Using browser cookies: {cookies_from_browser}")

    ydl_opts = {
        "outtmpl": output_template,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "logger": YtdlpLogger(log),
        "progress_hooks": [lambda data: ytdlp_progress(data, log)],
    }
    if cookies_from_browser:
        ydl_opts["cookiesfrombrowser"] = parse_cookies_from_browser(cookies_from_browser)

    with YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(url, download=True)

    matches = sorted(output_dir.glob(f"*{video_id}*.mp4"))
    if not matches:
        raise RuntimeError(f"Could not locate downloaded MP4 for {video_id}")
    return matches[0]


def parse_cookies_from_browser(value):
    container = None
    browser_part = value
    if "::" in browser_part:
        browser_part, container = browser_part.split("::", 1)

    profile = None
    if ":" in browser_part:
        browser_part, profile = browser_part.split(":", 1)

    keyring = None
    browser = browser_part
    if "+" in browser_part:
        browser, keyring = browser_part.split("+", 1)
        keyring = keyring.replace("-", "").replace("_", "").upper()

    return browser, profile or None, keyring or None, container or None


def ytdlp_progress(data, log):
    status = data.get("status")
    if status == "downloading":
        percent = data.get("_percent_str")
        speed = data.get("_speed_str")
        eta = data.get("_eta_str")
        if percent:
            emit(log, f"Download: {percent.strip()} at {(speed or '').strip()} ETA {(eta or '').strip()}")
    elif status == "finished":
        emit(log, "Download finished; preparing video file...")


class YtdlpLogger:
    def __init__(self, log):
        self.log = log

    def debug(self, message):
        if message.startswith("[debug] "):
            return
        emit(self.log, message)

    def warning(self, message):
        emit(self.log, f"WARNING: {message}")

    def error(self, message):
        emit(self.log, f"ERROR: {message}")


def transcribe_video(
    video_path,
    model="base.en",
    language="en",
    device="cpu",
    compute_type="int8",
    beam_size=5,
    vad_filter=False,
    log=None,
):
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("faster-whisper is not installed") from exc

    video_path = Path(video_path).expanduser().resolve()
    srt_path = video_path.with_suffix(".srt")
    vtt_path = video_path.with_suffix(".vtt")

    emit(log, f"Loading Whisper model: {model}")
    whisper_model = WhisperModel(
        model,
        device=device,
        compute_type=compute_type,
    )

    emit(log, f"Transcribing {video_path.name}...")
    segment_iter, info = whisper_model.transcribe(
        str(video_path),
        language=language,
        beam_size=beam_size,
        condition_on_previous_text=True,
        vad_filter=vad_filter,
    )

    segments = []
    for segment in segment_iter:
        text = segment.text.strip()
        if not text:
            continue
        emit(log, f"[{format_srt_time(segment.start)} --> {format_srt_time(segment.end)}] {text}")
        segments.append({
            "start": segment.start,
            "end": segment.end,
            "text": text,
        })

    write_srt(srt_path, segments)
    write_vtt(vtt_path, segments)
    emit(log, f"Detected language: {info.language}")
    emit(log, f"Wrote subtitles: {srt_path}")
    emit(log, f"Wrote web captions: {vtt_path}")
    return srt_path, vtt_path


def format_srt_time(seconds):
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


def format_vtt_time(seconds):
    return format_srt_time(seconds).replace(",", ".")


def write_srt(path, segments):
    with path.open("w", encoding="utf-8") as handle:
        for index, segment in enumerate(segments, start=1):
            text = segment["text"].strip()
            if not text:
                continue
            handle.write(f"{index}\n")
            handle.write(
                f"{format_srt_time(segment['start'])} --> {format_srt_time(segment['end'])}\n"
            )
            handle.write(f"{text}\n\n")


def write_vtt(path, segments):
    with path.open("w", encoding="utf-8") as handle:
        handle.write("WEBVTT\n\n")
        for segment in segments:
            text = segment["text"].strip()
            if not text:
                continue
            handle.write(
                f"{format_vtt_time(segment['start'])} --> {format_vtt_time(segment['end'])}\n"
            )
            handle.write(f"{html.escape(text)}\n\n")


def open_video(video_path, srt_path, no_play=False, log=None):
    if no_play:
        print_done(video_path, srt_path, log=log)
        return

    mpv = shutil.which("mpv")
    if mpv:
        emit(log, "Opening in mpv with generated subtitles...")
        subprocess.call([mpv, f"--sub-file={srt_path}", str(video_path)])
        return

    print_done(video_path, srt_path, log=log)
    emit(log, "mpv was not found; opening the video with the OS default app.")
    emit(log, "Most players auto-load a same-named .srt file next to the video.")

    system = platform.system().lower()
    if system == "windows":
        os.startfile(str(video_path))  # type: ignore[attr-defined]
    elif system == "darwin":
        subprocess.Popen(["open", str(video_path)])
    else:
        opener = shutil.which("xdg-open")
        if opener:
            subprocess.Popen([opener, str(video_path)])


def print_done(video_path, srt_path, log=None):
    emit(log, "")
    emit(log, "Done:")
    emit(log, f"  Video: {video_path}")
    emit(log, f"  Subtitles: {srt_path}")


def emit(log, message):
    if log:
        log(str(message))
    else:
        print(message)
