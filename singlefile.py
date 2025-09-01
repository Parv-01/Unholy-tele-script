# pip install pyrogram tgcrypto
import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait, UserNotParticipant, MessageIdInvalid

# USER CONFIG
API_ID = #Telegram app id from telegram api
API_HASH = "Telegram hash from telegram api"

#REQ: Set the chat and the list of message IDs to download
CHAT_ID = -1000123456789  # e.g., from t.me/c/0123456789/... -> -1000123456789
MESSAGE_IDS_TO_DOWNLOAD: List[int] = [] #Message Id or IDs taken from the pct grp channel copy link of that message
#download folder
DOWNLOAD_DIR = Path(r"Path_To_Download")  # A different folder to avoid conflicts

# Network
REQUEST_TIMEOUT = 60
DELAY_BETWEEN_DOWNLOADS = 5
DOWNLOAD_RETRIES = 3

# Optional SOCKS proxy (uncomment to use)
# PROXY = dict(
#     scheme="socks5",
#     hostname="127.0.0.1",
#     port=1080,
# )
PROXY = None
BASE_DIR = Path(__file__).resolve().parent
SESSION_DIR = BASE_DIR / "session"
SESSION_DIR.mkdir(parents=True, exist_ok=True)
SESSION_FILE = str((SESSION_DIR / "specific_download_session").resolve())


def on_download_progress(current: int, total: int, msg_id: int):
    percentage = current * 100 / total
    bar_length = 30
    filled_length = int(bar_length * current // total)
    bar = '█' * filled_length + '-' * (bar_length - filled_length)

    progress_str = (
        f"\r  -> Downloading MSG {msg_id}: [{bar}] {percentage:.1f}% "
        f"({current / 1024 / 1024:.2f}MB / {total / 1024 / 1024:.2f}MB)"
    )

    sys.stdout.write(progress_str)
    sys.stdout.flush()


def out_path(msg: Message, kind: str, ext: str = "") -> Path:
    dt = msg.date.strftime("%Y-%m")
    folder = DOWNLOAD_DIR / dt / kind
    folder.mkdir(parents=True, exist_ok=True)
    base = f"msg_{msg.id}_{msg.date.strftime('%Y%m%d_%H%M%S')}"
    return folder / (base + (f".{ext}" if ext else ""))


def media_info(msg: Message):
    if msg.photo: return "photos", "jpg"
    if msg.video: return "videos", "mp4"
    if msg.document:
        ext = Path(msg.document.file_name or "").suffix.lstrip(".") or "bin"
        return "documents", ext
    if msg.audio: return "audio", "mp3"
    if msg.voice: return "voice", "ogg"
    if msg.video_note: return "video_notes", "mp4"
    if msg.sticker: return "stickers", "webp"
    if msg.animation: return "animations", "gif"
    return "media", "bin"


async def download_message(app: Client, chat_id: int, message_id: int):
    try:
        msg = await app.get_messages(chat_id, message_id)
        if not msg:
            print(f"❌ ERROR: Message with ID {message_id} could not be found or is empty.")
            return
    except MessageIdInvalid:
        print(f"❌ ERROR: The message ID {message_id} is invalid or does not exist.")
        return
    except Exception as e:
        print(f"❌ ERROR: An unexpected error occurred while fetching message {message_id}: {e}")
        return
    if not msg.media:
        print(f"  [!] The message with ID {msg.id} does not contain any downloadable media.")
        return
    kind, ext = media_info(msg)
    target_path = out_path(msg, kind, ext)
    print(f"  [i] Media found. Preparing to download to: {target_path}")
    for attempt in range(DOWNLOAD_RETRIES):
        try:
            path = await asyncio.wait_for(
                msg.download(
                    file_name=str(target_path),
                    progress=on_download_progress,
                    progress_args=(msg.id,)
                ),
                timeout=REQUEST_TIMEOUT * 60
            )
            sys.stdout.write('\n')
            sys.stdout.flush()

            if path:
                print(f"  [+] SUCCESS: File from message {message_id} downloaded to: {path}")
            else:
                print(f"  [-] FAILED: Download for message {message_id} returned no path.")
            return
        except asyncio.TimeoutError:
            sys.stdout.write('\n')
            print(f"\n  [-] FAILED: The download for message {message_id} timed out.")
        except FloodWait as e:
            sys.stdout.write('\n')
            print(f"\n  [-] FAILED: A FloodWait of {e.x}s was received. Please wait and try again later.")
        except Exception as e:
            sys.stdout.write('\n')
            print(f"\n  [-] FAILED: An error occurred during download for message {message_id}: {e}")
        if attempt < DOWNLOAD_RETRIES - 1:
            print(f"    ...retrying in 10 seconds (attempt {attempt + 2} of {DOWNLOAD_RETRIES})...")
            await asyncio.sleep(10)


async def main():
    print("🚀 Telegram Specific Files Downloader")
    print("This script will always re-download files, overwriting any existing versions.")
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    client_kwargs = dict(
        name=SESSION_FILE, api_id=API_ID, api_hash=API_HASH, workdir=str(SESSION_DIR),
    )
    if PROXY:
        client_kwargs["proxy"] = PROXY

    try:
        async with Client(**client_kwargs) as app:
            print("[i] Initializing session and warming up cache...")
            async for _ in app.get_dialogs():
                break
            print("[i] Cache warmed up.")

            try:
                chat = await app.get_chat(CHAT_ID)
                print(f"📡 Access confirmed for chat: {chat.title}")
            except UserNotParticipant:
                print(f"❌ ERROR: You are not a member of the chat (ID: {CHAT_ID}). Join it first.")
                return
            except Exception as e:
                print(f"❌ ERROR: Could not access chat {CHAT_ID}. Reason: {e}")
                return
            # Loop
            total_files = len(MESSAGE_IDS_TO_DOWNLOAD)
            print(f"\n[*] Found {total_files} message ID(s) to process.")
            for i, message_id in enumerate(MESSAGE_IDS_TO_DOWNLOAD):
                print(f"\n--- Processing file {i + 1} of {total_files} (ID: {message_id}) ---")
                await download_message(app, CHAT_ID, message_id)
                # delay
                if i < total_files - 1:
                    print(f"    ...waiting for {DELAY_BETWEEN_DOWNLOADS} seconds...")
                    await asyncio.sleep(DELAY_BETWEEN_DOWNLOADS)

            print("\n\n✅ DONE: All specified messages have been processed.")

    except Exception as e:
        print(f"🔁 An unexpected error occurred during client setup: {e}")


if __name__ == "__main__":
    if not MESSAGE_IDS_TO_DOWNLOAD:
        print("❌ Please set the MESSAGE_IDS_TO_DOWNLOAD list in the script before running.")
    else:
        asyncio.run(main())
