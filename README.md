# yt-judge

Too many takes, not enough time. Let the AI watch, read, and decide who actually makes sense.

A lightweight tool for Claude Code (or any agentic AI) to fetch YouTube transcripts and compare what multiple YouTubers said — then let the AI judge who makes more sense.

用 Claude Code 或任何 Agent AI 抓取 YouTube 逐字稿，分析比較多位 YouTuber 的論點，判斷誰比較有道理。

---

## How it works

1. Drop one or more YouTube URLs into your AI agent
2. The agent runs `transcript.py` to fetch the transcript:
   - **Built-in subtitles first** — pulls YouTube's own captions (prefers zh → en → any available language)
   - **Whisper fallback** — if no subtitles exist, downloads the audio and transcribes it locally via faster-whisper
3. Fetched transcripts are **cached as Markdown files** (`cache/<video_id>.md`), so repeat runs are instant — no re-downloading, no re-transcribing
4. Ask your agent anything across the cached videos: *"Who has the stronger argument?"*, *"What did A get wrong?"*, *"Summarize both sides"*

---

## Quickstart

```bash
# Prerequisites
brew install ffmpeg
pip install uv

# Clone and set up
git clone https://github.com/your-username/yt-judge
cd yt-judge
uv sync

# Fetch a transcript
uv run transcript.py https://www.youtube.com/watch?v=VIDEO_ID
```

Then hand the URL to Claude Code or your agent and start asking questions.

---

## Cache

Each fetched video is saved to `cache/<video_id>.md` and includes:

- Title, channel, upload date, duration, URL
- Full transcript text

On subsequent runs, the script detects the cache file and skips all network and Whisper processing — the agent reads the local file directly.

```
標題：...
頻道：...
日期：...　時長：...
網址：https://www.youtube.com/watch?v=...
────────────────────────────────────────
transcript content...
```

---

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)
- ffmpeg — `brew install ffmpeg` (required for Whisper fallback)

## Dependencies

| Package | Purpose |
|---|---|
| `youtube-transcript-api` | Fetch built-in YouTube subtitles |
| `yt-dlp` | Video metadata + audio download for Whisper |
| `faster-whisper` | Local speech-to-text when subtitles are unavailable |

---

## Whisper model

Default is `small` (244MB, good for most use cases). Change `WHISPER_MODEL` at the top of `transcript.py`:

| Model | Size | Speed | Quality |
|---|---|---|---|
| small | 244MB | Fast | OK |
| medium | 1.5GB | Medium | Good |
| large-v3 | 3GB | Slow | Best |

For non-English content, `medium` or above is recommended.
