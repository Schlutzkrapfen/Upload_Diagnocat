import asyncio
import shutil
from pathlib import Path
from typing import Dict
from playwright.async_api import BrowserContext, Page, async_playwright
from webcrawler import add_patient, click_new_patient_button, get_patient_amount, go_to_patient_report, login, upload_patient_picture


USER_DATA_DIR = "user_data"
PICTURE_DIR = Path("./input_pictures")
OUTPUT_DIR = Path("./used_pictures")
async def main():
    """Runs the patient-creation and picture-upload workflow.

        Launches a persistent Chromium browser context, logs in, then for
        each picture in `PICTURE_DIR`: creates a new patient, opens their
        report page, uploads the picture, and moves the picture to
        `OUTPUT_DIR` once done.
        """
    async with async_playwright() as p:
        context: BrowserContext = await p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=False,
        )

        page: Page = await context.new_page()
        failed_pictures = []


        try:
            await login(page)
            patient_amount = await get_patient_amount()+1
            pictures = await asyncio.to_thread(lambda: list(PICTURE_DIR.iterdir()))

            for i, picture in enumerate(pictures):
                await click_new_patient_button()
                info = get_info(picture)
                await add_patient(info["first_name"], info["last_name"], info["birthday"], info["sex"], external_id=str(patient_amount+i))
                current_user = await go_to_patient_report(0)
                await upload_patient_picture(picture,current_user)
                move_picture(picture, OUTPUT_DIR)
        except TimeoutError as e:
            print(f"Login timed out: {e}")
        finally:
            print(f"Finished uploading pictures. Failed: {len(failed_pictures)}")



def get_info(picture_path: Path):
    parts = picture_path.stem.split("-")
    dictionary: dict[str, str] = {}
    dictionary["first_name"] = parts[0]
    dictionary["last_name"] = parts[1]
    if parts[3] == "M":
        dictionary["sex"] = "Männlich"
    else:
        dictionary["sex"] = "Weiblich"
    dictionary["age"] = parts[4]
    year =  2026 - int(dictionary["age"])
    dictionary["birthday"] = f"01-01-{year}"
    return dictionary

def move_picture(picture_path: Path, destination_path: Path):
    """Moves a picture file into the destination directory.

        Creates `destination_path` if it doesn't exist yet.

        Args:
            picture_path: Path to the picture file to move.
            destination_path: Directory to move the picture into.
        """
    if not destination_path.exists():
        destination_path.mkdir(parents=True, exist_ok=True)

    shutil.move(str(picture_path), str(destination_path / picture_path.name))


if __name__ == "__main__":
    asyncio.run(main())
