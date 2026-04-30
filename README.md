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

---

## Example — 峰哥 vs 藍泉媽媽（5 videos）

**Videos analyzed:**

| 頻道 | 標題 | 日期 |
|---|---|---|
| 峰哥 Fege | 錫蘭開噴老高！藍泉媽媽翻車了？ | 2024/10/25 |
| 藍泉媽媽 | 誰在說謊？大回應 | 2024/11/02 |
| 峰哥實況精華 | 我被嗆爆了！峰哥不再是贏家 | 2024/11/03 |
| 藍泉媽媽 | 泉面開戰大回應 | 2024/11/10 |
| 藍泉媽媽 | 在 YouTube 的最後一天前，我選擇站出來講出真相 | 2024/12/29 |

**Background**

老高發片稱比格斯對川普遇刺的預言「史上最精準」，並引用光明會卡牌作為佐證。藍泉媽媽發片反駁，主張比格斯是亂槍打鳥，並聲稱那張像川普的卡（Enough is Enough）是 2020 年才發行，因此根本不算預言——還開出一萬美元賞金，稱「全球只有 5 人知道這件事」。錫蘭隨即在直播查證，找到 2016 年的開箱影片直接打臉。峰哥看到機會，做了影片說藍泉媽媽翻車。藍泉媽媽反擊，指峰哥選擇性剪輯，事情越吵越大。

**Analysis**

**錫蘭**（旁觀查證者）：這場爭議最客觀的角色。他的直播有 30 分鐘在肯定藍泉媽媽，只有最後段才點出卡牌日期的錯誤，查證方式清楚、有一手影像佐證。

**藍泉媽媽**：比格斯預言的批評大致正確，錫蘭也認同；但在最關鍵的事實——卡牌發行年份——講錯了，而且是帶著極度自信講錯的。11/02 影片仍暗示「另有蹊蹺」硬撐；到 11/10 才正式認錯，承認卡牌日期錯誤、異色檔案的疏漏、對館長的人身攻擊，並宣布六大整改，是這場事件裡收尾最乾淨的一方。12/29 的最終影片首次公開說明不給錫蘭證據的原因——他看完直播後感受到錫蘭粉絲只在等他出錯，認為交出證據也不會有公正結果。這個理由可以理解，但與他自己「有理有據」的標榜有所矛盾。

**峰哥**：他指出的錯誤確實是錯的，但影片只剪了翻車片段，把錫蘭 40 分鐘直播中 30 分鐘的肯定全部略去，製造了「藍泉媽媽全錯」的印象。他從這場衝突拿到頻道史上最高播放量，卻沒有付出任何調查成本。另外，他曾在直播承認自己替小墨澄清後「好像被打臉了」，但從未公開說明。

**Verdict**

| 維度 | 結論 |
|---|---|
| 卡牌日期事實 | 錫蘭對，藍泉媽媽錯 |
| 比格斯預言批評 | 藍泉媽媽對，老高誇大 |
| 峰哥剪輯公正性 | 藍泉媽媽的批評成立 |
| 認錯與處理方式 | 藍泉媽媽最完整，峰哥幾乎沒有 |
| 整體誠信 | 藍泉媽媽 > 峰哥 |

藍泉媽媽在最關鍵的事實上犯了最大的錯，但在整件事的是非脈絡上，他比峰哥更在理。峰哥在技術上說的是對的，但選擇性剪輯讓他在道理上站不住腳。這場事件最終的最大贏家是錫蘭——查得最準、沒有捲入口水戰、全身而退。
