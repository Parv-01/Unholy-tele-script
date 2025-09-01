# pip install pyrogram tgcrypto
import asyncio
import os
import math
import tempfile
from pathlib import Path
from datetime import datetime
from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait, UserNotParticipant, ChatWriteForbidden

# USER CONFIG
API_ID = #Telegram app id from telegram api
API_HASH = "Telegram hash from telegram api"

SOURCE_CHAT_ID = -100XXXXXXXXXX   # FROM (private group/channel)
TARGET_CHAT_ID = -100YYYYYYYYYY   # TO (target group/channel)

START_ID = XYXY #Strt mssg id
END_ID = NMNM #end mssg id

# Behavior
DELAY_BETWEEN = 1.0
RETRIES = 3
DOWNLOAD_TIMEOUT = 60 * 45
UPLOAD_TIMEOUT = 60 * 60
MAX_UPLOAD_BYTES = 1_990 * 1024 * 1024
FORCE_DOCUMENT_FOR_VIDEO = True
ADD_SOURCE_INFO = True

def fmt_size(n: int) -> str:
    return f"{n/(1024*1024):.1f} MB"

async def progress_print(prefix: str, current: int, total: int):
    if total <= 0:
        return
    pct = current * 100 / total
    if int(pct) % 5 == 0:
        print(f"{prefix}: {pct:.0f}% ({fmt_size(current)}/{fmt_size(total)})")

async def safe_download(msg: Message, suffix: str) -> str:
    last_exc = None
    for attempt in range(1, RETRIES + 1):
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                temp_path = tmp.name

            async def dl_prog(current, total):
                await progress_print(f"↓ Download {msg.id}", current, total)

            result = await asyncio.wait_for(
                msg.download(file_name=temp_path, progress=dl_prog),
                timeout=DOWNLOAD_TIMEOUT
            )
            if not result or not Path(result).exists():
                raise RuntimeError("Download returned no file")
            return result
        except FloodWait as e:
            print(f"⏰ FloodWait during download {msg.id}. Sleeping {e.x}s...")
            await asyncio.sleep(e.x)
        except Exception as e:
            last_exc = e
            print(f"⚠️ Download attempt {attempt}/{RETRIES} failed for {msg.id}: {e}")
        finally:
            if temp_path and not Path(temp_path).exists():
                pass
        await asyncio.sleep(2)
    raise RuntimeError(f"Download failed after {RETRIES} attempts: {last_exc}")

async def safe_upload(app: Client, kind: str, file_path: str, msg: Message, caption: str = "", as_document: bool = False):
    file_size = Path(file_path).stat().st_size
    if file_size > MAX_UPLOAD_BYTES:
        raise RuntimeError(f"File exceeds cap {fmt_size(file_size)} > {fmt_size(MAX_UPLOAD_BYTES)}")

    last_exc = None
    for attempt in range(1, RETRIES + 1):
        try:
            async def ul_prog(current, total):
                await progress_print(f"↑ Upload {msg.id}", current, total)

            if as_document or kind == "document":
                await asyncio.wait_for(
                    app.send_document(
                        chat_id=TARGET_CHAT_ID,
                        document=file_path,
                        caption=caption or "",
                        file_name=Path(file_path).name,
                        progress=ul_prog
                    ),
                    timeout=UPLOAD_TIMEOUT
                )
            elif kind == "video":
                await asyncio.wait_for(
                    app.send_video(
                        chat_id=TARGET_CHAT_ID,
                        video=file_path,
                        caption=caption or "",
                        supports_streaming=True,
                        progress=ul_prog
                    ),
                    timeout=UPLOAD_TIMEOUT
                )
            elif kind == "photo":
                await asyncio.wait_for(
                    app.send_photo(
                        chat_id=TARGET_CHAT_ID,
                        photo=file_path,
                        caption=caption or "",
                        progress=ul_prog
                    ),
                    timeout=UPLOAD_TIMEOUT
                )
            elif kind == "audio":
                await asyncio.wait_for(
                    app.send_audio(
                        chat_id=TARGET_CHAT_ID,
                        audio=file_path,
                        caption=caption or "",
                        progress=ul_prog
                    ),
                    timeout=UPLOAD_TIMEOUT
                )
            elif kind == "voice":
                await asyncio.wait_for(
                    app.send_voice(
                        chat_id=TARGET_CHAT_ID,
                        voice=file_path,
                        progress=ul_prog
                    ),
                    timeout=UPLOAD_TIMEOUT
                )
            elif kind == "animation":
                await asyncio.wait_for(
                    app.send_animation(
                        chat_id=TARGET_CHAT_ID,
                        animation=file_path,
                        caption=caption or "",
                        progress=ul_prog
                    ),
                    timeout=UPLOAD_TIMEOUT
                )
            elif kind == "video_note":
                await asyncio.wait_for(
                    app.send_video_note(
                        chat_id=TARGET_CHAT_ID,
                        video_note=file_path
                    ),
                    timeout=UPLOAD_TIMEOUT
                )
            else:
                await asyncio.wait_for(
                    app.send_document(
                        chat_id=TARGET_CHAT_ID,
                        document=file_path,
                        caption=caption or "",
                        file_name=Path(file_path).name,
                        progress=ul_prog
                    ),
                    timeout=UPLOAD_TIMEOUT
                )
            return
        except FloodWait as e:
            print(f"⏰ FloodWait during upload {msg.id}. Sleeping {e.x}s...")
            await asyncio.sleep(e.x)
        except Exception as e:
            last_exc = e
            print(f"⚠️ Upload attempt {attempt}/{RETRIES} failed for {msg.id}: {e}")
        await asyncio.sleep(2)
    raise RuntimeError(f"Upload failed after {RETRIES} attempts: {last_exc}")

def classify_media(msg: Message):
    if msg.photo: return "photo", ".jpg"
    if msg.video: return "video", ".mp4"
    if msg.document:
        name = msg.document.file_name or "document.bin"
        suf = Path(name).suffix or ".bin"
        return "document", suf
    if msg.audio: return "audio", ".mp3"
    if msg.voice: return "voice", ".ogg"
    if msg.video_note: return "video_note", ".mp4"
    if msg.sticker: return "sticker", ".webp"
    if msg.animation: return "animation", ".gif"
    return "media", ".bin"

async def process_message(app: Client, msg: Message) -> bool:

    prefix = f"📢 From Source (ID: {msg.id})\n\n" if ADD_SOURCE_INFO else ""
    caption = prefix + (msg.caption or "")

    if (msg.text and not msg.media) or (msg.caption and not msg.media):
        await app.send_message(TARGET_CHAT_ID, prefix + (msg.text or msg.caption or ""), disable_web_page_preview=True)
        return True

    if msg.media:
        kind, suffix = classify_media(msg)

        as_document = FORCE_DOCUMENT_FOR_VIDEO and (kind == "video")

        print(f"↓ Start download {msg.id} ({kind})")
        file_path = await safe_download(msg, suffix)
        try:
            size = Path(file_path).stat().st_size
            print(f"✔ Downloaded {msg.id}: {fmt_size(size)} -> {file_path}")

            if size > MAX_UPLOAD_BYTES:
                print(f"⛔ Skipping {msg.id}: {fmt_size(size)} exceeds 1.99 GB cap")
                return False

            print(f"↑ Start upload {msg.id} ({'document' if as_document else kind})")
            await safe_upload(
                app=app,
                kind=kind,
                file_path=file_path,
                msg=msg,
                caption=caption,
                as_document=as_document
            )
            print(f"✔ Uploaded {msg.id}")
            return True
        finally:
            try:
                Path(file_path).unlink(missing_ok=True)
            except:
                pass
    if msg.poll:
        lines = [f"{prefix}📊 Poll: {msg.poll.question}", "Options:"]
        for i, opt in enumerate(msg.poll.options, 1):
            lines.append(f"{i}. {opt.text}")
        await app.send_message(TARGET_CHAT_ID, "\n".join(lines))
        return True
    if msg.contact:
        await app.send_contact(TARGET_CHAT_ID, msg.contact.phone_number, msg.contact.first_name, msg.contact.last_name or "")
        return True
    if msg.location:
        await app.send_location(TARGET_CHAT_ID, msg.location.latitude, msg.location.longitude)
        return True
    if msg.venue:
        await app.send_message(TARGET_CHAT_ID, f"{prefix}🏟️ Venue: {msg.venue.title}\n{msg.venue.address}")
        return True

    await app.send_message(TARGET_CHAT_ID, f"{prefix}❓ Unsupported message type ({msg.id})")
    return True

async def main():
    print("🚀 Forwarder (Bypass) | Large Video Handling ≤ ~1.99 GB")
    print(f"Range: {START_ID} .. {END_ID}")

    async with Client("forwarder_session", api_id=API_ID, api_hash=API_HASH) as app:

        async for _ in app.get_dialogs():
            break

        try:
            s = await app.get_chat(SOURCE_CHAT_ID)
            t = await app.get_chat(TARGET_CHAT_ID)
            print("Source:", s.title, "| Target:", t.title)
        except UserNotParticipant:
            print("❌ Join both chats with this account first.")
            return
        except Exception as e:
            print("❌ Chat access error:", e)
            return

        try:
            await app.send_message(
                TARGET_CHAT_ID,
                f"🤖 Forwarder started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Cap: {fmt_size(MAX_UPLOAD_BYTES)} per file\n"
                f"Method: re-upload (bypass restrictions)"
            )
        except ChatWriteForbidden:
            print("❌ No permission to send in target chat.")
            return

        total = END_ID - START_ID + 1
        processed = ok = fail = 0

        for mid in range(START_ID, END_ID + 1):
            try:
                msg = await app.get_messages(SOURCE_CHAT_ID, mid)
                if not msg or msg.empty:
                    processed += 1
                    await asyncio.sleep(DELAY_BETWEEN)
                    continue

                success = await process_message(app, msg)
                ok += 1 if success else 0
                fail += 0 if success else 1
            except FloodWait as e:
                print(f"⏰ FloodWait {e.x}s at message {mid}")
                await asyncio.sleep(e.x)
            except Exception as e:
                fail += 1
                print(f"❌ Error message {mid}: {e}")
            finally:
                processed += 1
                if processed % 5 == 0:
                    pct = processed * 100 / total
                    print(f"📊 Progress {processed}/{total} ({pct:.1f}%) | OK {ok} | Fail {fail}")
                await asyncio.sleep(DELAY_BETWEEN)

        print("\n🎉 Done")
        print(f"Processed: {processed}, OK: {ok}, Fail: {fail}")

if __name__ == "__main__":
    asyncio.run(main())
