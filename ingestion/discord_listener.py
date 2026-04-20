import os
import sys

import discord
from dotenv import load_dotenv

# Ensure DB schema is up to date before any other module touches the DB.
from database.init_db import init_db
init_db()
import re
import requests

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from database.crud import insert_raw_data, update_raw_data_preview, insert_processed_intel, insert_memory, mark_raw_data_processed
from ingestion.chat_batcher import flush_chat_batch, process_single_news

load_dotenv()
TOKEN = os.getenv('DISCORD_USER_TOKEN')
CHANNEL_IDS_ENV = os.getenv('DISCORD_CHANNEL_IDS', '')
TARGET_CHANNELS = [cid.strip() for cid in CHANNEL_IDS_ENV.split(',')] if CHANNEL_IDS_ENV else []

# Trusted channels: messages here skip the AI pipeline and go straight to intel DB.
TRUSTED_CHANNEL_IDS = {"1458971743472451584"}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}


def extract_urls(text: str) -> list:
    url_pattern = re.compile(
        r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s\)"\'\]]*',
        re.IGNORECASE
    )
    return url_pattern.findall(text)


def fetch_preview(url: str) -> dict:
    result = {"title": None, "description": None}
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        resp.encoding = resp.apparent_encoding or 'utf-8'
        html = resp.text

        match = re.search(r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']*)["\']', html, re.IGNORECASE)
        if not match:
            match = re.search(r'<meta[^>]*content=["\']([^"\']*)["\'][^>]*property=["\']og:title["\']', html, re.IGNORECASE)
        if match:
            result["title"] = match.group(1).strip()[:100]

        match = re.search(r'<meta[^>]*property=["\']og:description["\'][^>]*content=["\']([^"\']*)["\']', html, re.IGNORECASE)
        if not match:
            match = re.search(r'<meta[^>]*content=["\']([^"\']*)["\'][^>]*property=["\']og:description["\']', html, re.IGNORECASE)
        if not match:
            match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', html, re.IGNORECASE)
        if match:
            result["description"] = match.group(1).strip()[:300]

        if not result["title"]:
            title_tag = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
            if title_tag:
                result["title"] = title_tag.group(1).strip()[:100]
    except Exception as e:
        print(f"[Preview] Failed: {e}")
    return result


def extract_embed_data(embeds: list) -> dict:
    """
    Pull the most useful fields out of a list of discord embeds.
    Handles embeds from X/Twitter, news sites, and article cards.

    Returns:
        dict with keys: title, description, url, author, footer, fields, content_snippet
    """
    def score_embed(embed) -> int:
        score = 0
        if embed.title:
            score += 10
        if embed.description:
            score += len(embed.description)
        if embed.author.name:
            score += 5
        if embed.fields:
            score += sum(len(f.value) for f in embed.fields) * 2
        return score

    best = {}
    for embed in sorted(embeds, key=score_embed, reverse=True):
        d = {}
        # title: dedicated field OR author name as fallback (X/Twitter style).
        raw_title = embed.title.strip() if embed.title and str(embed.title).strip() else ""
        d["title"] = raw_title or (embed.author.name.strip() if embed.author.name and str(embed.author.name).strip() else "")
        if embed.description:
            d["description"] = embed.description.strip()
        if embed.url:
            d["url"] = embed.url.strip()
        if embed.author.name:
            d["author"] = embed.author.name.strip()
        if embed.footer.text:
            d["footer"] = embed.footer.text.strip()
        if embed.fields:
            d["fields"] = [
                (f.name.strip(), f.value.strip())
                for f in embed.fields
            ]
        if d.get("title") or d.get("description"):
            best = d
            break
    return best


def parse_trusted_content(content: str, embed_data: dict) -> tuple[str, str]:
    """
    Extract (title, summary) from a trusted channel message.
    Priority:
      1. embed.title  (or embed.author as fallback title for X embeds)
      2. embed.description  (tweet正文 / 新闻正文)
      3. content body 里解析出的标题行
      4. content body 里解析出的摘要行
      5. content 截断

    Handles formats from:
      - FaytuksBot "Quote extracted by..." 转发
      - FaytuksBot "Translated from..." 翻译
      - 直接 embed 新闻卡片
      - X/Twitter 推文（title=author, description=正文）
    """
    SKIP_PREFIXES = (
        "quote extracted by",
        "media and quote extracted by",
        "translated from",
        "[attached previews]",
        "original found here:",
        "source:",
    )

    # ── Step 1: embed title ──────────────────────────────────────────────────
    title = embed_data.get("title", "") if embed_data else ""
    description = embed_data.get("description", "") if embed_data else ""

    # ── Step 2: if embed has no description, look in content body ───────────
    if not description and content:
        description = _extract_body_from_forward(content)

    # ── Step 3: if still no title, derive from content ─────────────────────
    if not title and content:
        title = _derive_title_from_content(content, SKIP_PREFIXES)

    # ── Step 4: if still no description, grab first meaningful body line ────
    if not description and content:
        description = _derive_summary_from_content(content, SKIP_PREFIXES)

    # ── Step 5: last resort ─────────────────────────────────────────────────
    if not title:
        title = embed_data.get("author", "") if embed_data else ""
    if not description:
        description = content.strip()[:300] if content else ""

    return title[:120], description[:1000]


def _extract_body_from_forward(content: str) -> str:
    """
    Pull the actual tweet/post body out of a FaytuksBot forward.
    Handles:
      - "Quote extracted by FaytuksBot\n<author>\n<body>\nQuote from: <source>"
      - "Translated from: <lang>\n<body>\nSource: <url>"
    """
    if not content:
        return ""

    lines = [l.strip() for l in content.strip().split('\n')]
    # Find the body: lines between the first skip-line and the "Quote from:" / "Source:" trailer.
    collecting = False
    body_lines = []
    for i, line in enumerate(lines):
        lower = line.lower()
        # Skip headers like "Quote extracted by...", "Translated from:", "[Attached..."
        if any(lower.startswith(p) for p in ("quote extracted", "translated from", "[attached", "original found")):
            collecting = True
            continue
        if lower.startswith("quote from:") or lower.startswith("source:") or lower.startswith("original found"):
            break
        if collecting and line:
            body_lines.append(line)

    # Also check for the embedded author line (e.g. "JaxAlemany | Quote extracted...").
    # Skip lines that look like handle-only (no punctuation, short).
    cleaned = [l for l in body_lines if len(l) > 5]

    return "\n".join(cleaned)[:800]


def _derive_title_from_content(content: str, skip_prefixes: tuple) -> str:
    """First meaningful non-meta line as title."""
    if not content:
        return ""
    for line in content.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        if any(line.lower().startswith(p) for p in skip_prefixes):
            continue
        # Skip lines that look like bare URLs.
        if line.startswith("http://") or line.startswith("https://"):
            continue
        return line[:120]
    return ""


def _derive_summary_from_content(content: str, skip_prefixes: tuple) -> str:
    """First paragraph-length chunk that is not a title or URL."""
    if not content:
        return ""
    buf = []
    for line in content.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        if any(line.lower().startswith(p) for p in skip_prefixes):
            continue
        if line.startswith("http://") or line.startswith("https://"):
            continue
        buf.append(line)
        if len(buf) >= 3:
            break
    return " ".join(buf)[:300]


def _is_empty_forward(content: str, title: str) -> bool:
    """
    Skip messages with no real content:
      - title is the default fallback ("Channel ...")
      - content is just a reference link ("Original found here: ...")
    """
    title_is_fallback = title.startswith("Channel ")
    content_is_ref = content.strip().lower().startswith("original found here:")
    return title_is_fallback and content_is_ref


def ingest_trusted_channel(raw_id: int, content: str, urls: list, channel_id: str, author: str, embed_data: dict = None):
    """
    Trusted channel path: parse content with rule-based extraction, insert into DB.
    Skips the AI pipeline entirely.
    """
    title, summary = parse_trusted_content(content, embed_data)

    if not summary:
        summary = content.strip()[:200]

    if not title:
        title = f"Channel {channel_id}"

    if _is_empty_forward(content, title):
        print(f"[TrustedChannel] Skipped empty reference message in {channel_id}")
        mark_raw_data_processed(raw_id)
        return

    intel_id = insert_processed_intel(
        raw_data_id=raw_id,
        title=title,
        summary=summary,
        red_team_analysis="",
        blue_team_analysis="",
        synthesis="",
        tags="trusted",
        team_assignment='center',
        intel_type='trusted',
        batch_count=1
    )
    insert_memory(
        team='general',
        author=title,
        context=summary,
        source=f"channel:{channel_id}"
    )
    print(f"[TrustedChannel] channel={channel_id} title={title[:60]} intel_id={intel_id}")
    mark_raw_data_processed(raw_id)


class NexusSelfClient(discord.Client):
    async def on_ready(self):
        print(f'Logged on safely as self-bot user: {self.user}!')
        if TARGET_CHANNELS:
            print(f"Listening exclusively to channel IDs: {TARGET_CHANNELS}")
        else:
            print("No target channels configured. Listening to all incoming traffic across all servers.")
        if TRUSTED_CHANNEL_IDS:
            print(f"Trusted channels (no AI): {TRUSTED_CHANNEL_IDS}")

        from ingestion.chat_batcher import process_all_pending_news
        await self.loop.run_in_executor(None, process_all_pending_news)

    async def _fetch_discord_message(self, message_url: str) -> str | None:
        """
        Use the bot's own HTTP session to fetch the content of a message
        from a discord.com/channels/<guild>/<channel>/<message> URL.
        Falls back to None on failure.
        """
        m = re.match(
            r'https://discord(?:\.com)?/channels/(\d+)/(\d+)/(\d+)',
            message_url
        )
        if not m:
            return None
        guild_id, channel_id, msg_id = m.group(1), m.group(2), m.group(3)
        try:
            msg = await self.http.get_message(channel_id, msg_id)
            return msg.get("content") or ""
        except Exception:
            return None

    async def on_message(self, message):
        if message.author == self.user:
            return

        if TARGET_CHANNELS and str(message.channel.id) not in TARGET_CHANNELS:
            return

        content = message.content.strip()

        embed_texts = []
        for embed in message.embeds:
            if embed.title:
                embed_texts.append(f"Embed Title: {embed.title}")
            if embed.description:
                embed_texts.append(f"Embed Description: {embed.description}")

        if embed_texts:
            content += "\n\n[Attached Previews]:\n" + "\n".join(embed_texts)

        if not content:
            return

        # Skip Discord's own auto-generated system messages:
        # - Author named "Discord" = invite/link preview embeds Discord auto-generates
        # - Author named "Webhook" = webhook posts (also auto-generated)
        author_name = str(message.author).lower()
        if author_name == "discord" or author_name == "webhook":
            return

        channel_id = str(message.channel.id)
        urls = extract_urls(content)
        has_link = "http://" in content or "https://" in content
        intel_type = "news" if (has_link or message.embeds) else "chat"

        # Trusted channel → skip AI, direct ingest
        if channel_id in TRUSTED_CHANNEL_IDS:
            # If the message contains a discord.com/channels/ reference, use the API
            # to pull the real content instead of the preview page.
            real_content = content
            for url in urls:
                if "discord.com/channels/" in url:
                    fetched = await self._fetch_discord_message(url)
                    if fetched:
                        real_content = fetched
                        break

            # Extract structured embed data for rich card content.
            embed_data = extract_embed_data(message.embeds)

            print(f'[TRUSTED] from {message.author} in #{channel_id}: {real_content[:80]}...')
            raw_id = insert_raw_data(
                source='discord_selfbot',
                content=real_content,
                author=str(message.author),
                intel_type=intel_type,
                source_key=channel_id
            )
            ingest_trusted_channel(raw_id, real_content, urls, channel_id, str(message.author), embed_data)
            return

        print(f'[{intel_type.upper()}] from {message.author}: {content[:80]}...')

        raw_id = insert_raw_data(
            source='discord_selfbot',
            content=content,
            author=str(message.author),
            intel_type=intel_type
        )

        if intel_type == "news":
            # Use embed data for richer preview if available.
            embed_data = extract_embed_data(message.embeds)
            if embed_data.get("title") or embed_data.get("description"):
                update_raw_data_preview(raw_id, embed_data.get("title"), embed_data.get("description"))
                print(f"[Preview] Title: {embed_data.get('title', 'N/A')[:60]}")
            elif urls:
                preview = fetch_preview(urls[0])
                if preview["title"] or preview["description"]:
                    update_raw_data_preview(raw_id, preview.get("title"), preview.get("description"))
                    print(f"[Preview] Title: {preview.get('title', 'N/A')[:60]}")

            process_single_news({'id': raw_id, 'content': content, 'source': 'discord_selfbot'})
        else:
            flush_chat_batch()


def run_discord_listener():
    if not TOKEN:
        print("Error: DISCORD_USER_TOKEN not found in .env")
        return

    print("Initiating Discord Self-Bot context...")
    client = NexusSelfClient()

    try:
        client.run(TOKEN)
    except discord.errors.LoginFailure:
        print("[!] Critical Error: Invalid User Token. Does the token require bypassing 2FA? Did it change?")

if __name__ == '__main__':
    run_discord_listener()
