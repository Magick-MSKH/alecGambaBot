import time
import asyncio
from playwright.async_api import async_playwright

class YouTubeChatSender:
    def __init__(self, live_url):
        self.live_url = live_url
        self.browser = None
        self.page = None
        self.playwright = None
        self.seen_message_ids = set()

    async def start(self):
        """Launches a persistent browser window so you can log in once manually."""
        print("\n🌐 Opening a dedicated browser window for chat output...")
        self.playwright = await async_playwright().start()

        stealth_args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-infobars',
            '--no-default-browser-check',
            '--test-type'
        ]
        
        self.browser = await self.playwright.chromium.launch_persistent_context(
            user_data_dir="./user_data",
            headless=False,
            channel="chrome",
            args=stealth_args,
            ignore_default_args=["--enable-automation"]
        )
        
        pages = self.browser.pages
        self.page = pages[0] if pages else await self.browser.new_page()
        await self.page.goto(self.live_url)
        
        print("🔒 ACTION REQUIRED: If you aren't logged in, log into your YouTube Streaming account in the browser window that just popped up!")
        print("Once you are on your stream chat page, leave the browser open in the background.")


    async def get_new_messages(self):
        """Scrapes new live chat messages directly off the Chrome screen window natively."""
        new_items = []
        try:
            # Locate all active chat message render blocks currently on screen
            cards = await self.page.query_selector_all('yt-live-chat-text-message-renderer, yt-live-chat-paid-message-renderer, yt-live-chat-membership-item-renderer')
            
            # Keep only the last 20 messages on screen to save computing memory
            if len(cards) > 20:
                cards = cards[-20:]

            for card in cards:
                # Use YouTube's internal element ID as a unique fingerprint tracking code
                msg_id = await card.get_attribute('id')
                if not msg_id or msg_id in self.seen_message_ids:
                    continue
                
                self.seen_message_ids.add(msg_id)
                
                # Extract the sender's display name string
                author_elem = await card.query_selector('#author-name')
                username = await author_elem.inner_text() if author_elem else ""
                username = username.strip()

                # Extract the chat text message content string
                msg_elem = await card.query_selector('#message')
                message_text = await msg_elem.inner_text() if msg_elem else ""
                message_text = message_text.strip()

                if not username:
                    continue

                # Determine the event type tag based on YouTube's HTML layout wrappers
                tag_name = await card.evaluate('node => node.tagName.toLowerCase()')
                message_type = "textMessageEvent"
                details = {}

                if tag_name == "yt-live-chat-paid-message-renderer":
                    message_type = "superChatEvent"
                    amt_elem = await card.query_selector('#purchase-amount')
                    if amt_elem:
                        raw_amt = await amt_elem.inner_text()
                        try: details["amount"] = float(raw_amt.replace('$', '').strip())
                        except Exception: details["amount"] = 5.0

                elif tag_name == "yt-live-chat-membership-item-renderer":
                    # Detects both initial joins and month milestones
                    header_elem = await card.query_selector('#header-text')
                    header_text = await header_elem.inner_text() if header_elem else ""
                    
                    if "milestone" in header_text.lower() or "member for" in header_text.lower():
                        message_type = "memberMilestoneChatEvent"
                        details["months"] = 1 # Safe default baseline
                    else:
                        message_type = "membershipGIFTEvent"

                # Check if the sender has an active channel member sponsor badge layout item
                badge_elem = await card.query_selector('yt-live-chat-author-badge-renderer[type="sponsor"]')
                is_member = badge_elem is not None

                new_items.append({
                    "username": username,
                    "message_text": message_text,
                    "message_type": message_type,
                    "details": details,
                    "is_member": is_member
                })

            # Clean memory tracking cache if it gets too large
            if len(self.seen_message_ids) > 500:
                self.seen_message_ids = set(list(self.seen_message_ids)[-200:])

        except Exception as e:
            print(f"⚠️ Screen scrape warning: {e}")
            
        return new_items

    async def send_message(self, text):
        """Finds the YouTube pop-out chat box, types the response, and presses Enter."""
        try:
            chat_input_selector = 'div#input[contenteditable="true"], yt-live-chat-text-input-field-renderer div#input'
            await self.page.wait_for_selector(chat_input_selector, timeout=5000)
            await self.page.click(chat_input_selector)
            await self.page.fill(chat_input_selector, "")
            await self.page.type(chat_input_selector, text, delay=10) 
            await self.page.keyboard.press("Enter")
            print(f"📡 SENT TO YOUTUBE: {text}")
        except Exception as e:
            print(f"❌ Failed to send message to YouTube window: {e}")

    async def stop(self):
        """Safely winds down the browser context asynchronously with zero warnings."""
        print("🛑 Closing automated browser window context...")
        try:
            if self.browser: await self.browser.close()
        except Exception: pass
        try:
            if self.playwright: await self.playwright.stop()
        except Exception: pass

    async def get_formatted_cookies(self):
        """ Extract active browser session cookies and format them for httpx client """
        try:
            # Grab raw cookie array from Playwright's persistent context memory
            playwright_cookies = await self.browser.cookies()
            # Format them into a standard key-value dict for httpx
            formatted_cookies = {}
            for cookie in playwright_cookies:
                formatted_cookies[cookie['name']] = cookie['value']
            return formatted_cookies
        except Exception as e:
            print(f"⚠️ Failed to extract browser session cookies: {e}")
            return {}