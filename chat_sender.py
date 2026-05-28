import time
import asyncio
from playwright.async_api import async_playwright

class YouTubeChatSender:
    def __init__(self, live_url):
        self.live_url = live_url
        self.browser = None
        self.page = None
        self.playwright = None

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
            channel="chrome", # Points directly to the Chrome installation
            args=stealth_args, # Inject anti-bot detection arguments
            ignore_default_args=["--enable-automation"]
        )
        
        pages = self.browser.pages
        self.page = pages[0] if pages else await self.browser.new_page()
        await self.page.goto(self.live_url)

        ### OLD VERSION -- ABOVE REWRITE IS UNTESTED! ###
#       self.page = self.browser.pages[0]
#       self.page.goto(self.live_url)
        
        print("🔒 ACTION REQUIRED: If you aren't logged in, log into your YouTube Streaming account in the browser window that just popped up!")
        print("Once you are on your stream chat page, leave the browser open in the background.")

    async def send_message(self, text):
        """Finds the YouTube chat box, types the response, and presses Enter """
        try:
            chat_input_selector = 'div#input[contenteditable="true"], yt-live-chat-text-input-field-renderer div#input'
            
            ### NEW -- Non-blocking async wait for the selector to load
            await self.page.wait_for_selector(chat_input_selector, timeout=5000)
            await self.page.click(chat_input_selector)
            await self.page.fill(chat_input_selector, "") # Clear box first
            await self.page.type(chat_input_selector, text, delay=10) 
            await self.page.keyboard.press("Enter")
            print(f"📡 SENT TO YOUTUBE: {text}")
        except Exception as e:
            print(f"❌ Failed to send message to YouTube window: {e}")

    async def stop(self):
        """ Safely winds down the browser context asynchronously """
        print("🛑 Closing automated browser window context...")
        try:    
            if self.browser:
                self.browser.close()
        except Exception:
            pass # Supresses driver pipe disconnect complaints on sudden manual shutdown
        
        try:
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass # Same as above
