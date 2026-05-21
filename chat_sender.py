import time
from playwright.sync_api import sync_playwright

class YouTubeChatSender:
    def __init__(self, live_url):
        self.live_url = live_url
        self.browser = None
        self.page = None
        self.playwright = None

    def start(self):
        """Launches a persistent browser window so you can log in once manually."""
        print("\n🌐 Opening a dedicated browser window for chat output...")
        self.playwright = sync_playwright().start()
        
        # Use native Chrome installation instead of debug/dev one
        self.browser = self.playwright.chromium.launch_persistent_context(
            user_data_dir="./user_data",
            headless=False,
            channel="chrome"
        )
        
        self.page = self.browser.pages[0]
        self.page.goto(self.live_url)
        
        print("🔒 ACTION REQUIRED: If you aren't logged in, log into your YouTube Streaming account in the browser window that just popped up!")
        print("Once you are on your stream chat page, leave the browser open in the background.")

    def send_message(self, text):
        """Finds the YouTube chat box, types the response, and presses Enter """
        try:
            # Universal selector that targets the main live chat input box field
            chat_input_selector = 'div#input[contenteditable="true"]'
            
            self.page.wait_for_selector(chat_input_selector, timeout=5000)
            self.page.click(chat_input_selector)
            self.page.fill(chat_input_selector, text)
            self.page.keyboard.press("Enter")
            print(f"📡 SENT TO YOUTUBE: {text}")
        except Exception as e:
            print(f"❌ Failed to send message to YouTube window: {e}")

    def stop(self):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
