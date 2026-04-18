import os
import discord
from dotenv import load_dotenv
import sys
import re
import requests

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from database.crud import insert_raw_data, update_raw_data_preview
from ingestion.chat_batcher import flush_chat_batch, process_single_news

load_dotenv()
TOKEN = os.getenv('DISCORD_USER_TOKEN')
CHANNEL_IDS_ENV = os.getenv('DISCORD_CHANNEL_IDS', '')
TARGET_CHANNELS = [cid.strip() for cid in CHANNEL_IDS_ENV.split(',')] if CHANNEL_IDS_ENV else []

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}


def extract_urls(text: str) -> list:
    """从文本中提取所有 URL"""
    url_pattern = re.compile(
        r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s\)\"\'\]]*',
        re.IGNORECASE
    )
    return url_pattern.findall(text)


def fetch_preview(url: str) -> dict:
    """获取 URL 的 title 和 description"""
    result = {"title": None, "description": None}
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        resp.encoding = resp.apparent_encoding or 'utf-8'
        html = resp.text

        # og:title
        match = re.search(r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']*)["\']', html, re.IGNORECASE)
        if not match:
            match = re.search(r'<meta[^>]*content=["\']([^"\']*)["\'][^>]*property=["\']og:title["\']', html, re.IGNORECASE)
        if match:
            result["title"] = match.group(1).strip()[:100]

        # og:description 或 description
        match = re.search(r'<meta[^>]*property=["\']og:description["\'][^>]*content=["\']([^"\']*)["\']', html, re.IGNORECASE)
        if not match:
            match = re.search(r'<meta[^>]*content=["\']([^"\']*)["\'][^>]*property=["\']og:description["\']', html, re.IGNORECASE)
        if not match:
            match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', html, re.IGNORECASE)
        if match:
            result["description"] = match.group(1).strip()[:300]

        # 如果没有 og:title，用 <title>
        if not result["title"]:
            title_tag = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
            if title_tag:
                result["title"] = title_tag.group(1).strip()[:100]
    except Exception as e:
        print(f"[Preview] Failed: {e}")
    return result


class NexusSelfClient(discord.Client):
    async def on_ready(self):
        print(f'Logged on safely as self-bot user: {self.user}!')
        if TARGET_CHANNELS:
            print(f"Listening exclusively to channel IDs: {TARGET_CHANNELS}")
        else:
            print("No target channels configured. Listening to all incoming traffic across all servers.")

        # Drain any pending news from before the bot was running
        from ingestion.chat_batcher import process_all_pending_news
        await self.loop.run_in_executor(None, process_all_pending_news)

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

        has_link = "http://" in content or "https://" in content
        intel_type = "news" if (has_link or message.embeds) else "chat"

        print(f'[{intel_type.upper()}] from {message.author}: {content[:80]}...')

        raw_id = insert_raw_data(
            source='discord_selfbot',
            content=content,
            author=str(message.author),
            intel_type=intel_type
        )

        # 抓取链接预览
        if intel_type == "news":
            urls = extract_urls(content)
            if urls:
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
