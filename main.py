import asyncio
from playwright.async_api import BrowserContext, Page, async_playwright
from webcrawler import add_patient, click_new_patient_button, get_patient_amount, login


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
            patient_amount = await get_patient_amount()
            await click_new_patient_button()
            await add_patient(str(patient_amount), str(patient_amount), "01-01-2000")
        except TimeoutError as e:
            print(f"Login timed out: {e}")




if __name__ == "__main__":
    asyncio.run(main())
