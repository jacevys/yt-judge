#!/usr/bin/env python3
"""抓 YouTube 逐字稿（含標題、頻道），有快取則直接讀本地
優先用 YouTube 字幕，沒有字幕則用 Whisper 語音轉文字"""

import sys
import re
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

CACHE_DIR = Path(__file__).parent / "cache" / "youtube"
WHISPER_MODEL = "small"  # tiny / base / small / medium / large-v3

_video_locks: dict[str, threading.Lock] = {}
_locks_mutex = threading.Lock()


def _get_video_lock(video_id: str) -> threading.Lock:
    with _locks_mutex:
        if video_id not in _video_locks:
            _video_locks[video_id] = threading.Lock()
        return _video_locks[video_id]


def extract_video_id(url_or_id: str) -> str:
    for pattern in [r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})"]:
        m = re.search(pattern, url_or_id)
        if m:
            return m.group(1)
    if re.match(r"^[A-Za-z0-9_-]{11}$", url_or_id):
        return url_or_id
    raise ValueError(f"無法解析 video ID：{url_or_id}")


def fetch_metadata(url: str) -> dict:
    opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return {
        "title": info.get("title", "（無標題）"),
        "channel": info.get("channel", "（無頻道）"),
        "upload_date": info.get("upload_date", ""),
        "duration": info.get("duration", 0),
    }


def fetch_transcript_from_youtube(video_id: str) -> str:
    api = YouTubeTranscriptApi()
    transcript_list = api.list(video_id)
    try:
        transcript = transcript_list.find_transcript(["zh-TW", "zh-Hans", "zh", "en"])
    except Exception:
        transcript = transcript_list.find_generated_transcript(["zh-TW", "zh-Hans", "zh", "en"])
    return "\n".join(entry.text for entry in transcript.fetch())


def fetch_transcript_via_whisper(url: str) -> str:
    from faster_whisper import WhisperModel

    print(f"[Whisper] 載入模型 {WHISPER_MODEL}，首次使用需下載...", file=sys.stderr)
    model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = str(Path(tmpdir) / "audio.m4a")
        print("[Whisper] 下載音訊中...", file=sys.stderr)
        opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio[ext=m4a]/bestaudio",
            "outtmpl": audio_path,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

        print("[Whisper] 語音轉文字中...", file=sys.stderr)
        segments, info = model.transcribe(audio_path, language="zh", beam_size=5)
        print(f"[Whisper] 偵測語言：{info.language}（信心度 {info.language_probability:.0%}）", file=sys.stderr)

        total = info.duration
        texts = []
        last_pct = -1
        for seg in segments:
            texts.append(seg.text.strip())
            pct = int(seg.end / total * 100) if total else 0
            if pct // 5 > last_pct // 5:
                bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                print(f"\r[Whisper] [{bar}] {pct:3d}%", end="", file=sys.stderr, flush=True)
                last_pct = pct
        print(file=sys.stderr)
        return "\n".join(texts)


def format_duration(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def get_transcript(url_or_id: str) -> str:
    video_id = extract_video_id(url_or_id)
    cache_file = CACHE_DIR / f"{video_id}.md"

    if cache_file.exists():
        print(f"[快取] 直接讀取 {cache_file.name}", file=sys.stderr)
        return cache_file.read_text(encoding="utf-8")

    with _get_video_lock(video_id):
        # 再次確認，避免等 lock 時另一線程已完成
        if cache_file.exists():
            print(f"[快取] 直接讀取 {cache_file.name}", file=sys.stderr)
            return cache_file.read_text(encoding="utf-8")

        full_url = f"https://www.youtube.com/watch?v={video_id}"
        print(f"[抓取中] {full_url}", file=sys.stderr)

        meta = fetch_metadata(full_url)
        date = meta["upload_date"]
        date_str = f"{date[:4]}-{date[4:6]}-{date[6:]}" if len(date) == 8 else date

        header = (
            f"標題：{meta['title']}\n"
            f"頻道：{meta['channel']}\n"
            f"日期：{date_str}　時長：{format_duration(meta['duration'])}\n"
            f"網址：{full_url}\n"
            f"{'─' * 40}\n"
        )

        # 優先用 YouTube 字幕，失敗才用 Whisper
        try:
            print("[字幕] 嘗試抓取 YouTube 字幕...", file=sys.stderr)
            text = fetch_transcript_from_youtube(video_id)
            print("[字幕] 成功", file=sys.stderr)
        except (TranscriptsDisabled, NoTranscriptFound, Exception) as e:
            print(f"[字幕] 無字幕（{type(e).__name__}），改用 Whisper", file=sys.stderr)
            text = fetch_transcript_via_whisper(full_url)

        full_output = header + text
        CACHE_DIR.mkdir(exist_ok=True)
        cache_file.write_text(full_output, encoding="utf-8")
        print(f"[已快取] {cache_file}", file=sys.stderr)

    return full_output


def main():
    urls = sys.argv[1:]
    if not urls:
        print("用法：uv run transcript.py <URL1> [URL2] ...")
        sys.exit(1)

    if len(urls) == 1:
        print(get_transcript(urls[0]))
        return

    results: list[str | None] = [None] * len(urls)
    max_workers = min(len(urls), 5)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {executor.submit(get_transcript, url): i for i, url in enumerate(urls)}
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                results[idx] = f"[錯誤] {urls[idx]}\n{e}"

    sep = "\n" + "═" * 60 + "\n"
    print(sep.join(results))  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
