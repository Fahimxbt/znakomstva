from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError
import asyncio
import os
import time

# ========== CONFIG FROM ENVIRONMENT VARIABLES ==========
STRING_SESSION = os.environ.get('STRING_SESSION', '')
API_ID = int(os.environ.get('API_ID', '0'))
API_HASH = os.environ.get('API_HASH', '')
# ========================================================

if not STRING_SESSION or not API_ID or not API_HASH:
    print("[!] ERROR: Missing environment variables!")
    print("    Required: STRING_SESSION, API_ID, API_HASH")
    exit(1)

client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)

bot_entity = None
sticker_msg_id = None

match_active = False
promo_sent = False
sending_lock = asyncio.Lock()


async def safe_send_message(entity, message, retries=3):
    for attempt in range(retries):
        try:
            return await client.send_message(entity, message)
        except FloodWaitError as e:
            print(f"[!] FloodWait: Waiting {e.seconds} seconds...")
            await asyncio.sleep(e.seconds + 2)
        except Exception as e:
            print(f"[!] Send error (attempt {attempt+1}): {e}")
            if attempt < retries - 1:
                await asyncio.sleep(5)
    return None


async def safe_forward_messages(entity, msg_id, from_peer, retries=3):
    for attempt in range(retries):
        try:
            return await client.forward_messages(entity, msg_id, from_peer)
        except FloodWaitError as e:
            print(f"[!] FloodWait: Waiting {e.seconds} seconds...")
            await asyncio.sleep(e.seconds + 2)
        except Exception as e:
            print(f"[!] Forward error (attempt {attempt+1}): {e}")
            if attempt < retries - 1:
                await asyncio.sleep(5)
    return None


async def safe_click(message, text, retries=3):
    for attempt in range(retries):
        try:
            return await message.click(text=text)
        except FloodWaitError as e:
            print(f"[!] FloodWait on click: Waiting {e.seconds} seconds...")
            await asyncio.sleep(e.seconds + 2)
        except Exception as e:
            print(f"[!] Click error (attempt {attempt+1}): {e}")
            if attempt < retries - 1:
                await asyncio.sleep(5)
    return None


async def find_sticker():
    global sticker_msg_id
    try:
        msgs = await client.get_messages('me', limit=50)
        for m in msgs:
            if m.sticker and not sticker_msg_id:
                sticker_msg_id = m.id
                print("[+] Sticker found!")

        if sticker_msg_id:
            return True

    except Exception as e:
        print(f"[!] Find error: {e}")

    print("[!] Send a sticker to Saved Messages first!")
    return False


async def click_find_partner_button(limit=15):
    """Click Find a Partner button. Returns True if clicked."""
    try:
        msgs = await client.get_messages(bot_entity, limit=limit)
        for m in msgs:
            if not m.reply_markup:
                continue
            for row in m.reply_markup.rows:
                for btn in row.buttons:
                    btn_text = (btn.text or '').lower()
                    if 'find a partner' in btn_text or 'find partner' in btn_text:
                        try:
                            await m.click(text=btn.text)
                            print(f"[→] Clicked: {btn.text}")
                            await asyncio.sleep(3)
                            return True
                        except Exception as e:
                            print(f"[!] Click error: {e}")
                            continue
    except Exception as e:
        print(f"[!] Button search error: {e}")
    return False


async def click_find_partner():
    print("[*] Looking for Find a Partner button...")

    if await click_find_partner_button(limit=15):
        return True

    print("[!] Button not found, using /search fallback")
    await safe_send_message(bot_entity, '/search')
    await asyncio.sleep(3)
    return True


async def handle_match():
    global match_active, promo_sent

    if sending_lock.locked() or promo_sent:
        return

    async with sending_lock:
        print("[*] Forwarding sticker...")
        try:
            if sticker_msg_id:
                await safe_forward_messages(bot_entity, sticker_msg_id, 'me')
                print("[+] Sticker forwarded!")
            else:
                await safe_send_message(bot_entity, "💜 @chatxbt_bot\nhttps://t.me/chatxbt_bot")
                print("[+] Text promo sent!")
        except Exception as e:
            print(f"[!] Sticker error: {e}")

        # Wait 2 seconds
        await asyncio.sleep(2)

        # ALWAYS send /stop first to end chat, then find new partner
        print("[→] Sending /stop to end chat...")
        await safe_send_message(bot_entity, '/stop')
        await asyncio.sleep(3)

        promo_sent = True
        match_active = False

    # Now find new partner
    await click_find_partner()


@client.on(events.NewMessage(chats='@znakomstva_anon_bot'))
async def handler(event):
    global match_active, promo_sent

    text = event.text or ''

    if event.out:
        return

    # ========== COMMAND NOT AVAILABLE IN CHAT ==========
    if 'This command is not available in chat' in text:
        print("[!] Command not available in chat — still in match!")
        # Just wait, /stop was already sent or will be sent
        return

    # ========== PARTNER ENDED CHAT ==========
    if 'Your partner ended the chat' in text:
        print("[✓] Partner ended chat")
        match_active = False
        promo_sent = False
        await asyncio.sleep(2)
        await click_find_partner()
        return

    # ========== WE LEFT CHAT ==========
    if 'You left the chat' in text:
        print("[✓] We left the chat")
        match_active = False
        promo_sent = False
        await asyncio.sleep(2)
        await click_find_partner()
        return

    # ========== BOT WELCOME / MENU ==========
    if "I'm an anonymous chat bot" in text or "Use the menu or enter the" in text:
        print("[*] Bot welcome/menu shown")
        match_active = False
        promo_sent = False
        await asyncio.sleep(1)
        await click_find_partner()
        return

    # ========== FINDING PARTNER ==========
    if 'Finding a partner soon' in text:
        print("[...] Searching for partner...")
        match_active = False
        promo_sent = False
        return

    # ========== MATCH STARTED ==========
    if 'Start chatting' in text:
        print("[+] Match started!")
        match_active = True
        promo_sent = False
        asyncio.create_task(handle_match())
        return

    # ========== PARTNER SENT MESSAGE DURING MATCH ==========
    if match_active and not promo_sent and not sending_lock.locked():
        print("[+] Partner messaged first!")
        asyncio.create_task(handle_match())
        return


async def main():
    global bot_entity
    await client.start()
    print("[*] Russian Bot (@znakomstva_anon_bot) started!")
    print("[*] Flow: sticker → 2s → /stop → 3s → Find a Partner")
    print("[*] Connected to Telegram successfully!")

    bot_entity = await client.get_entity('@znakomstva_anon_bot')
    await find_sticker()
    await click_find_partner()

    await client.run_until_disconnected()


if __name__ == '__main__':
    while True:
        try:
            with client:
                client.loop.run_until_complete(main())
        except KeyboardInterrupt:
            print("\n[*] Bot stopped by user.")
            break
        except Exception as e:
            print(f"[!] Fatal error: {e}")
            print("[*] Restarting in 10 seconds...")
            time.sleep(10)
