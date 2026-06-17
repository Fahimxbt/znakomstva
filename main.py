from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError
import asyncio
import os
import sys
import random
import time

# ========== CONFIG FROM ENVIRONMENT VARIABLES ==========
STRING_SESSION = os.environ.get('STRING_SESSION', '')
API_ID = int(os.environ.get('API_ID', '0'))
API_HASH = os.environ.get('API_HASH', '')
# Optional: set BOT_ID to a unique number (1-5) for each bot to stagger timing
BOT_ID = int(os.environ.get('BOT_ID', 1))
# ========================================================

# Validate config
if not STRING_SESSION or not API_ID or not API_HASH:
    print("[!] ERROR: Missing environment variables!")
    print("    Required: STRING_SESSION, API_ID, API_HASH")
    sys.exit(1)

client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)

bot_entity = None
sticker_msg_id = None

# State machine from Script 1
STATE_IDLE = 'idle'
STATE_FINDING = 'finding'
STATE_MATCHED = 'matched'
STATE_WAITING_PARTNER = 'waiting_partner'

current_state = STATE_IDLE
state_lock = asyncio.Lock()
partner_skipped = False
last_processed_msg_id = 0
last_click_time = 0

# Anti-self-match: track recent partner IDs to avoid matching same bot
recent_partner_ids = set()
MAX_RECENT_PARTNERS = 20

# Rate limiting protection from Script 2
MIN_PARTNER_INTERVAL = 15  # Minimum seconds between finding new partners
last_partner_time = 0


async def safe_send_message(entity, message, retries=3):
    """Send message with flood wait handling"""
    for attempt in range(retries):
        try:
            return await client.send_message(entity, message)
        except FloodWaitError as e:
            wait_time = e.seconds
            print(f"[!] FloodWait: Waiting {wait_time} seconds...")
            await asyncio.sleep(wait_time + 2)
        except Exception as e:
            print(f"[!] Send error (attempt {attempt+1}): {e}")
            if attempt < retries - 1:
                await asyncio.sleep(5)
    return None


async def safe_forward_messages(entity, msg_id, from_peer, retries=3):
    """Forward message with flood wait handling"""
    for attempt in range(retries):
        try:
            return await client.forward_messages(entity, msg_id, from_peer)
        except FloodWaitError as e:
            wait_time = e.seconds
            print(f"[!] FloodWait: Waiting {wait_time} seconds...")
            await asyncio.sleep(wait_time + 2)
        except Exception as e:
            print(f"[!] Forward error (attempt {attempt+1}): {e}")
            if attempt < retries - 1:
                await asyncio.sleep(5)
    return None


async def safe_click(message, text, retries=3):
    """Click button with flood wait handling"""
    for attempt in range(retries):
        try:
            return await message.click(text=text)
        except FloodWaitError as e:
            wait_time = e.seconds
            print(f"[!] FloodWait on click: Waiting {wait_time} seconds...")
            await asyncio.sleep(wait_time + 2)
        except Exception as e:
            print(f"[!] Click error (attempt {attempt+1}): {e}")
            if attempt < retries - 1:
                await asyncio.sleep(5)
    return None


async def find_sticker():
    """Find sticker message in Saved Messages"""
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


async def click_find_partner():
    global current_state, last_click_time, last_partner_time

    async with state_lock:
        if current_state in (STATE_MATCHED, STATE_WAITING_PARTNER):
            print(f"[*] In match (state={current_state}), skipping Find a Partner click")
            return False

        now = time.time()
        if now - last_click_time < 5:
            print(f"[*] Click cooldown active ({now - last_click_time:.1f}s), skipping...")
            return False
        last_click_time = now

        if current_state == STATE_FINDING:
            print("[*] Already finding partner, skipping...")
            return False

        current_state = STATE_FINDING

    # Rate limit: ensure minimum interval between partner searches (from Script 2)
    elapsed = time.time() - last_partner_time
    if elapsed < MIN_PARTNER_INTERVAL:
        wait = MIN_PARTNER_INTERVAL - elapsed
        print(f"[*] Rate limit: waiting {wait:.1f}s before next search...")
        await asyncio.sleep(wait)

    # ANTI-SELF-MATCH: staggered random delay based on BOT_ID (from Script 1)
    base_delay = BOT_ID * 1.5  # Bot 1=1.5s, Bot 2=3s, Bot 3=4.5s, etc.
    random_delay = random.uniform(0, 3)
    total_delay = base_delay + random_delay
    print(f"[*] Anti-self-match: waiting {total_delay:.1f}s before clicking (bot_id={BOT_ID})...")
    await asyncio.sleep(total_delay)

    # Re-check state after delay
    async with state_lock:
        if current_state in (STATE_MATCHED, STATE_WAITING_PARTNER):
            print(f"[*] State changed to match during delay, aborting click")
            return False

    print("[*] Looking for Find a Partner button...")

    try:
        for attempt in range(5):
            async with state_lock:
                if current_state in (STATE_MATCHED, STATE_WAITING_PARTNER):
                    print(f"[*] State changed to match during search, aborting click")
                    return False

            msgs = await client.get_messages(bot_entity, limit=15)
            for m in msgs:
                if not m.reply_markup:
                    continue
                for row in m.reply_markup.rows:
                    for btn in row.buttons:
                        btn_text = btn.text or ''
                        if 'Find a Partner' in btn_text or 'Find' in btn_text:
                            result = await safe_click(m, btn.text)
                            if result:
                                print(f"[→] Find a Partner clicked (attempt {attempt+1})")
                                last_partner_time = time.time()
                                await asyncio.sleep(3)
                                return True
                            continue

            if attempt < 4:
                print(f"[*] Button not found, waiting... (attempt {attempt+1})")
                await asyncio.sleep(2)

        async with state_lock:
            if current_state == STATE_FINDING:
                print("[!] Button not found, using /search fallback")
                await safe_send_message(bot_entity, '/search')
                last_partner_time = time.time()
                await asyncio.sleep(3)
                return True

    except Exception as e:
        print(f"[!] Find partner error: {e}")
        async with state_lock:
            if current_state == STATE_FINDING:
                current_state = STATE_IDLE

    return False


async def handle_match():
    """Handle match: forward sticker only, then wait for partner response"""
    global current_state, partner_skipped

    async with state_lock:
        if current_state != STATE_MATCHED:
            print(f"[*] Not in match (state={current_state}), aborting handle_match")
            return
        current_state = STATE_WAITING_PARTNER
        partner_skipped = False

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

    print("[*] Waiting 3 seconds for partner response...")
    await asyncio.sleep(3)

    async with state_lock:
        skipped = partner_skipped
        state = current_state

    if skipped:
        print("[✓] Partner skipped us (sent message), finding new match in 3 seconds...")
        await asyncio.sleep(3)
        async with state_lock:
            current_state = STATE_IDLE
        await click_find_partner()
        return

    if state != STATE_WAITING_PARTNER:
        print(f"[*] State changed to {state} during wait, aborting")
        return

    print("[*] Partner didn't skip, sending /stop...")
    try:
        await safe_send_message(bot_entity, '/stop')
        print("[→] /stop sent")
    except Exception as e:
        print(f"[!] Stop error: {e}")

    await asyncio.sleep(2)

    async with state_lock:
        current_state = STATE_IDLE

    await click_find_partner()


async def handle_finding_timeout():
    global current_state
    await asyncio.sleep(10)

    try:
        async with state_lock:
            state = current_state

        if state != STATE_FINDING:
            return

        print("[!] Finding timeout! No match after 10 seconds.")

        await safe_send_message(bot_entity, '/stop')
        print("[→] /stop sent (timeout)")
        await asyncio.sleep(2)

        async with state_lock:
            current_state = STATE_IDLE

        await click_find_partner()
    except Exception as e:
        print(f"[!] Finding timeout error: {e}")


async def recovery_watchdog():
    global current_state
    while True:
        await asyncio.sleep(30)

        try:
            async with state_lock:
                state = current_state

            if state == STATE_IDLE:
                print("[!] Watchdog: Idle state detected, finding partner...")
                await click_find_partner()
        except Exception as e:
            print(f"[!] Watchdog error: {e}")


@client.on(events.NewMessage(chats='@znakomstva_anon_bot'))
async def handler(event):
    global current_state, partner_skipped, last_processed_msg_id

    if event.id <= last_processed_msg_id:
        return
    last_processed_msg_id = event.id

    text = event.text or ''

    if event.out:
        return

    # ========== COMMAND NOT AVAILABLE IN CHAT ==========
    if 'This command is not available in chat' in text:
        print("[!] Command not available in chat — we are still in a match!")

        async with state_lock:
            current_state = STATE_MATCHED

        await asyncio.sleep(1)
        try:
            await safe_send_message(bot_entity, '/stop')
            print("[→] /stop sent (recovery)")
            await asyncio.sleep(2)
        except Exception as e:
            print(f"[!] Recovery /stop error: {e}")

        async with state_lock:
            current_state = STATE_IDLE

        await click_find_partner()
        return

    # ========== PARTNER ENDED CHAT ==========
    if 'Your partner ended the chat' in text:
        print("[✓] Partner ended chat")

        async with state_lock:
            current_state = STATE_IDLE

        await asyncio.sleep(2)
        await click_find_partner()
        return

    # ========== WE LEFT CHAT ==========
    if 'You left the chat' in text:
        print("[✓] We left the chat")

        async with state_lock:
            current_state = STATE_IDLE

        await asyncio.sleep(2)
        await click_find_partner()
        return

    # ========== BOT WELCOME / MENU ==========
    if "I'm an anonymous chat bot" in text or "Use the menu or enter the" in text:
        print("[*] Bot welcome/menu shown")

        async with state_lock:
            current_state = STATE_IDLE

        await asyncio.sleep(1)
        await click_find_partner()
        return

    # ========== FINDING PARTNER ==========
    if 'Finding a partner soon' in text:
        print("[...] Searching for partner...")

        async with state_lock:
            current_state = STATE_FINDING

        asyncio.create_task(handle_finding_timeout())
        return

    # ========== MATCH STARTED ==========
    if 'Start chatting' in text:
        print("[+] Match started!")

        async with state_lock:
            current_state = STATE_MATCHED
            partner_skipped = False

        asyncio.create_task(handle_match())
        return

    # ========== PARTNER SENT MESSAGE DURING MATCH ==========
    async with state_lock:
        state = current_state

    if state == STATE_WAITING_PARTNER:
        print("[+] Partner sent message/sticker — they skipped us!")
        async with state_lock:
            partner_skipped = True
        return

    if state == STATE_MATCHED:
        print("[+] Partner sent message before our sticker!")
        async with state_lock:
            partner_skipped = True
        return


async def main():
    global bot_entity
    await client.start()
    print(f"[*] Russian Bot (znakomstva_anon_bot) started! BOT_ID={BOT_ID}")
    print("[*] Connected to Telegram successfully!")

    bot_entity = await client.get_entity('@znakomstva_anon_bot')
    await find_sticker()
    await click_find_partner()

    asyncio.create_task(recovery_watchdog())

    await client.run_until_disconnected()


if __name__ == '__main__':
    try:
        with client:
            client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\n[*] Bot stopped by user.")
    except Exception as e:
        print(f"[!] Fatal error: {e}")
        sys.exit(1)
