import asyncio
from playwright.async_api import BrowserContext, Page, async_playwright
from webcrawler import login


USER_DATA_DIR = "user_data"
async def main():
    async with async_playwright() as p:
        context: BrowserContext = await p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=False,
        )

        page: Page = await context.new_page()


        try:
            await login(page)
        except TimeoutError as e:
            print(f"Login timed out: {e}")




if __name__ == "__main__":
    asyncio.run(main())
