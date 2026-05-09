#!/usr/bin/env python3
"""搜尋 Threads 公開貼文，供 agent 先篩選再深入分析。"""

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from playwright.sync_api import sync_playwright

SESSION_FILE = Path(__file__).parent / "cache" / ".threads_session.json"
THREADS_CACHE_DIR = Path(__file__).parent / "cache" / "threads"


@dataclass
class ThreadsPost:
    """搜尋結果中的單則貼文（摘要）。"""
    username: str
    content: str
    timestamp: str
    likes: str
    replies: str
    url: str


@dataclass
class ThreadsReply:
    """貼文的單則回覆。"""
    username: str
    content: str
    timestamp: str
    likes: str
    url: str


@dataclass
class ThreadsRecord:
    """完整抓取的一則串文，含原帖全文與前 N 則回覆。"""
    username: str
    content: str          # 多段串文合併後的完整內容
    timestamp: str
    likes: str
    reply_count: str
    url: str
    post_id: str
    replies: list[ThreadsReply] = field(default_factory=list)


def _extract_post_id(url: str) -> str:
    """從 URL 取出 post ID。"""
    parts = url.rstrip("/").split("/")
    return parts[-1] if parts else ""


def _parse_container(el, full_content: bool = False) -> ThreadsPost | None:
    """解析單個 [data-pressable-container] 元素。"""
    try:
        link_el = el.query_selector("a[href*='/post/']")
        post_url, username = "", ""
        if link_el:
            href = link_el.get_attribute("href") or ""
            post_url = f"https://www.threads.com{href}" if href.startswith("/") else href
            parts = href.split("/")
            if len(parts) >= 2:
                username = parts[1].lstrip("@")

        time_el = el.query_selector("time")
        timestamp = ""
        if time_el:
            timestamp = time_el.get_attribute("datetime") or time_el.inner_text().strip()

        content_els = el.query_selector_all("span[dir]")
        content = max(
            (c.inner_text().strip() for c in content_els),
            key=len,
            default="",
        )
        if not content:
            return None

        likes, replies = "", ""
        for label, attr in [("讚", "likes"), ("回覆", "replies")]:
            svg = el.query_selector(f'svg[aria-label="{label}"]')
            if svg:
                val = svg.evaluate(
                    'svg => { const s = svg.parentElement?.querySelector("span"); return s ? s.innerText : ""; }'
                )
                if attr == "likes":
                    likes = val or ""
                else:
                    replies = val or ""

        return ThreadsPost(
            username=username,
            content=content if full_content else content[:400],
            timestamp=timestamp,
            likes=likes,
            replies=replies,
            url=post_url,
        )
    except Exception:
        return None


def login() -> None:
    """開有頭瀏覽器讓使用者手動登入，完成後儲存 session。"""
    SESSION_FILE.parent.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(locale="zh-TW")
        page = context.new_page()

        print("[Threads] 開啟瀏覽器，請手動登入 Threads 帳號嘛...", file=sys.stderr)
        page.goto("https://www.threads.com/", timeout=20000)

        print("[Threads] 登入完成後，回到這個終端機按 Enter 儲存 session 嘛", file=sys.stderr)
        input()
        time.sleep(1)

        context.storage_state(path=str(SESSION_FILE))
        browser.close()
        print(f"[Threads] Session 已儲存到 {SESSION_FILE} 嘛", file=sys.stderr)


def _make_browser_page(p):
    browser = p.chromium.launch(headless=True)
    storage = str(SESSION_FILE) if SESSION_FILE.exists() else None
    ctx_kwargs = {"locale": "zh-TW"}
    if storage:
        ctx_kwargs["storage_state"] = storage
    else:
        print("[Threads] 未登入，結果可能很少嘛（用 --login 先登入嘛）", file=sys.stderr)
    return browser, browser.new_page(**ctx_kwargs)


def search_threads(query: str, limit: int = 10, scroll_rounds: int = 10) -> list[ThreadsPost]:
    results: list[ThreadsPost] = []

    if SESSION_FILE.exists():
        print("[Threads] 使用已儲存的 session 嘛", file=sys.stderr)

    with sync_playwright() as p:
        browser, page = _make_browser_page(p)
        url = f"https://www.threads.com/search?q={query}&serp_type=default"
        print(f"[Threads] 搜尋中：{query}", file=sys.stderr)
        page.goto(url, timeout=20000)
        time.sleep(5)

        for _ in range(scroll_rounds):
            page.evaluate("window.scrollBy(0, 1000)")
            time.sleep(1.5)

        containers = page.query_selector_all("[data-pressable-container]")
        print(f"[Threads] 找到 {len(containers)} 個容器", file=sys.stderr)

        seen = set()
        for c in containers:
            result = _parse_container(c)
            if result and result.url not in seen and result.content:
                seen.add(result.url)
                results.append(result)
            if len(results) >= limit:
                break

        browser.close()

    return results


def fetch_post(post_url: str, reply_limit: int = 20, topic: str = "") -> str:
    """抓取一則完整串文（原帖全文 + 前 N 則回覆），並快取到本地。"""
    from datetime import date
    post_id = _extract_post_id(post_url)
    if topic:
        folder = THREADS_CACHE_DIR / f"{topic}{date.today().strftime('%Y%m%d')}"
    else:
        folder = THREADS_CACHE_DIR
    folder.mkdir(parents=True, exist_ok=True)
    cache_file = folder / f"{post_id}.md"

    if cache_file.exists():
        print(f"[快取] 直接讀取 {cache_file.name}", file=sys.stderr)
        # 從快取重建 ThreadsRecord（只回傳 markdown，讓 caller 直接 print）
        return cache_file.read_text(encoding="utf-8")  # type: ignore[return-value]

    print(f"[Threads] 抓取貼文：{post_url}", file=sys.stderr)

    with sync_playwright() as p:
        browser, page = _make_browser_page(p)
        page.goto(post_url, timeout=20000)
        time.sleep(4)

        scroll_rounds = max(3, reply_limit // 8)
        for _ in range(scroll_rounds):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1.5)

        containers = page.query_selector_all("[data-pressable-container]")
        print(f"[Threads] 找到 {len(containers)} 個容器", file=sys.stderr)

        if not containers:
            browser.close()
            raise RuntimeError("頁面沒有找到任何貼文容器嘛")

        # --- 原帖：合併連續同作者的容器 ---
        first = _parse_container(containers[0], full_content=True)
        if not first:
            browser.close()
            raise RuntimeError("無法解析原帖嘛")

        author = first.username
        merged_parts = [first.content]
        reply_start = 1

        for i, c in enumerate(containers[1:], start=1):
            p2 = _parse_container(c, full_content=True)
            if p2 and p2.username == author:
                merged_parts.append(p2.content)
                reply_start = i + 1
            else:
                break

        record = ThreadsRecord(
            username=author,
            content="\n\n".join(merged_parts),
            timestamp=first.timestamp,
            likes=first.likes,
            reply_count=first.replies,
            url=post_url,
            post_id=post_id,
        )

        # --- 回覆：取 reply_start 之後，前 reply_limit 則 ---
        seen: set[str] = set()
        for c in containers[reply_start:]:
            r = _parse_container(c, full_content=True)
            if r and r.url not in seen and r.content:
                seen.add(r.url)
                record.replies.append(ThreadsReply(
                    username=r.username,
                    content=r.content,
                    timestamp=r.timestamp,
                    likes=r.likes,
                    url=r.url,
                ))
            if len(record.replies) >= reply_limit:
                break

        browser.close()

    # --- 存成 Markdown ---
    md = _record_to_markdown(record)
    cache_file.write_text(md, encoding="utf-8")
    print(f"[已快取] {cache_file}", file=sys.stderr)

    return md  # type: ignore[return-value]


def _record_to_markdown(r: ThreadsRecord) -> str:
    ts = r.timestamp[:10] if len(r.timestamp) >= 10 else r.timestamp
    lines = [
        f"作者：@{r.username}",
        f"時間：{ts}　讚：{r.likes}　回覆數：{r.reply_count}",
        f"網址：{r.url}",
        "─" * 40,
        "【原帖】",
        r.content,
        "",
        "─" * 40,
        f"【回覆】前 {len(r.replies)} 則",
        "",
    ]
    for i, reply in enumerate(r.replies, 1):
        ts_r = reply.timestamp[:10] if len(reply.timestamp) >= 10 else reply.timestamp
        lines.append(f"[{i}] @{reply.username}　{ts_r}　讚: {reply.likes}")
        lines.append(reply.content)
        lines.append("")

    return "\n".join(lines)


def format_markdown(results: list[ThreadsPost]) -> str:
    lines = [
        "| # | 用戶 | 內容摘要 | 時間 | 讚 | 回覆 | 連結 |",
        "|---:|---|---|---|---:|---:|---|",
    ]
    for idx, post in enumerate(results, 1):
        content = post.content.replace("\n", " ").replace("|", "\\|")[:80]
        lines.append(
            f"| {idx} | {post.username} | {content} | {post.timestamp} "
            f"| {post.likes} | {post.replies} | {post.url} |"
        )
    return "\n".join(lines)


def fetch_all(query: str, topic: str, posts: int = 5, reply_limit: int = 20, scroll_rounds: int = 10) -> None:
    """搜尋關鍵字，對每則結果抓完整串文（含回覆）並快取。"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results = search_threads(query, limit=posts, scroll_rounds=scroll_rounds)
    if not results:
        print("搜尋沒有結果嘛", file=sys.stderr)
        return

    print(f"[Threads] 準備抓取 {len(results)} 則串文嘛", file=sys.stderr)

    def _fetch(post: ThreadsPost) -> tuple[str, str]:
        try:
            md = fetch_post(post.url, reply_limit=reply_limit, topic=topic)
            return post.url, "ok"
        except Exception as e:
            return post.url, f"錯誤：{e}"

    with ThreadPoolExecutor(max_workers=min(len(results), 3)) as executor:
        futures = {executor.submit(_fetch, p): p for p in results}
        for future in as_completed(futures):
            url, status = future.result()
            print(f"[Threads] {status}　{url}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="搜尋 Threads 貼文")
    parser.add_argument("query", nargs="?", help="搜尋關鍵字")
    parser.add_argument("--login", action="store_true", help="開瀏覽器登入並儲存 session")
    parser.add_argument("--fetch", metavar="URL", help="抓取並快取單則串文（原帖 + 回覆）")
    parser.add_argument("--fetch-all", action="store_true", help="搜尋後自動抓取所有結果的串文")
    parser.add_argument("--topic", metavar="名稱", default="", help="議題名稱，快取路徑為 threads/<名稱><日期>/")
    parser.add_argument("--posts", type=int, default=5, help="一次抓取的貼文數量，預設 5")
    parser.add_argument("--reply-limit", type=int, default=20, dest="reply_limit", help="每則串文抓取的回覆數量，預設 20")
    parser.add_argument("--limit", type=int, default=10, help="搜尋結果數量（純搜尋模式），預設 10")
    parser.add_argument("--scroll-rounds", type=int, default=10, dest="scroll_rounds", help="搜尋頁捲動輪數，預設 10")
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="輸出格式，預設 markdown",
    )
    args = parser.parse_args()

    if args.login:
        login()
        return

    if args.fetch:
        result = fetch_post(args.fetch, reply_limit=args.reply_limit, topic=args.topic)
        print(result)
        return

    if not args.query:
        parser.print_help()
        sys.exit(1)

    if args.fetch_all:
        fetch_all(args.query, topic=args.topic, posts=args.posts, reply_limit=args.reply_limit, scroll_rounds=args.scroll_rounds)
        return

    results = search_threads(args.query, args.limit, scroll_rounds=args.scroll_rounds)

    if not results:
        print("找不到任何貼文嘛", file=sys.stderr)
        sys.exit(1)

    if args.format == "json":
        print(json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2))
    else:
        print(format_markdown(results))


if __name__ == "__main__":
    main()
