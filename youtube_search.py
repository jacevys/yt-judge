#!/usr/bin/env python3
"""搜尋 YouTube 候選影片，供 agent 先篩選再抓逐字稿。"""

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from typing import Any

import yt_dlp


@dataclass
class SearchResult:
    title: str
    channel: str
    url: str
    video_id: str
    duration: int | None
    view_count: int | None
    upload_date: str
    description: str


def _clean_text(value: Any) -> str:
    return str(value or "").replace("\n", " ").strip()


def _entry_to_result(entry: dict[str, Any]) -> SearchResult:
    video_id = entry.get("id") or ""
    url = entry.get("webpage_url") or entry.get("url") or ""
    if video_id and not url.startswith("http"):
        url = f"https://www.youtube.com/watch?v={video_id}"

    return SearchResult(
        title=_clean_text(entry.get("title")),
        channel=_clean_text(entry.get("channel") or entry.get("uploader")),
        url=url,
        video_id=video_id,
        duration=entry.get("duration"),
        view_count=entry.get("view_count"),
        upload_date=_clean_text(entry.get("upload_date")),
        description=_clean_text(entry.get("description")),
    )


def search_youtube(query: str, limit: int = 10) -> list[SearchResult]:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)

    entries = info.get("entries") or []
    return [_entry_to_result(entry) for entry in entries if entry]


def format_markdown(results: list[SearchResult]) -> str:
    lines = [
        "| # | 標題 | 頻道 | 時長 | 觀看數 | URL |",
        "|---:|---|---|---:|---:|---|",
    ]
    for idx, result in enumerate(results, 1):
        duration = str(result.duration or "")
        view_count = str(result.view_count or "")
        title = result.title.replace("|", "\\|")
        channel = result.channel.replace("|", "\\|")
        lines.append(f"| {idx} | {title} | {channel} | {duration} | {view_count} | {result.url} |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="搜尋 YouTube 候選影片")
    parser.add_argument("query", help="搜尋關鍵字")
    parser.add_argument("--limit", type=int, default=10, help="搜尋結果數量，預設 10")
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="輸出格式，預設 markdown",
    )
    args = parser.parse_args()

    if args.limit < 1:
        print("--limit 必須大於 0", file=sys.stderr)
        sys.exit(1)

    results = search_youtube(args.query, args.limit)
    if args.format == "json":
        print(json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2))
    else:
        print(format_markdown(results))


if __name__ == "__main__":
    main()
