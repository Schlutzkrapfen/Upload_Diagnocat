import asyncio
import shutil
from pathlib import Path
from playwright.async_api import BrowserContext, Page, async_playwright
from webcrawler import add_patient, click_new_patient_button, get_patient_amount, go_to_patient_report, login, upload_patient_picture


USER_DATA_DIR = "user_data"
PICTURE_DIR = Path("./input_pictures")
OUTPUT_DIR = Path("./used_pictures")
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
            pictures = await asyncio.to_thread(lambda: list(PICTURE_DIR.iterdir()))

            for i, picture in enumerate(pictures):
                await click_new_patient_button()
                await add_patient(str(patient_amount+i), str(patient_amount+i), "01-01-2000",external_id=str(patient_amount+i))
                await go_to_patient_report(0)
                await upload_patient_picture(picture)
                move_picture(picture, OUTPUT_DIR)
        except TimeoutError as e:
            print(f"Login timed out: {e}")




def move_picture(picture_path: Path, destination_path: Path):
    if not destination_path.exists():
        destination_path.mkdir(parents=True, exist_ok=True)

    shutil.move(str(picture_path), str(destination_path / picture_path.name))


if __name__ == "__main__":
    asyncio.run(main())
