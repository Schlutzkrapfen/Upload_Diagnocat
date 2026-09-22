from pathlib import Path

from playwright.async_api import  Page

page:Page
user_page:Page | None = None


async def login(page1: Page):
    """
       Ensure the browser session is logged in to Diagnocat.

       Navigates to the sign-in page. If the session is already
       authenticated (auto-redirect away from sign-in), skips the manual
       step. Otherwise, waits for manual login and for the browser to
       redirect to the patients page.

       Args:
           page1 (Page): Playwright page object used to navigate and check
               login status.
       """
    print("Checking login status...")
    global page
    page = page1
    _website = await page.goto("https://app.diagnocat.eu/sign-in")

    # If we are already logged in, the site might auto-redirect to /patients
    if "sign-in" not in page.url:
        print("Already logged in. Skipping manual step.")
    else:
        print("Please log in manually in the browser window...")
        # Wait for the URL to change to the patients page
        await page.wait_for_url("**/patients**", timeout=0)
        # Crucial: Wait a moment for cookies to sync to the 'user_data' folder
        print("Login successful!")



async def click_new_patient_button():
    """Navigates to the patients page and clicks the 'New Patient' button.

        If the current page is not already the patients page, navigates to it
        first. Then waits for the 'New Patient' button to appear and clicks it.

        Raises:
            LookupError: If the 'New Patient' button is not found on the page.
        """
    if page.url.rstrip("/") != "https://app.diagnocat.eu/patients".rstrip("/"):
        print("Opening data page...")
        _website = await page.goto(
        "https://app.diagnocat.eu/patients",
        wait_until="domcontentloaded",
        timeout=10000,
        )
    button = await page.wait_for_selector("button.Patients-module_newPatientButton_ACBBZ")
    if button is None:
        raise LookupError("New patient button not found")
    await button.click()
    print("button clicked")


async def add_patient(
    first_name: str,
    last_name: str,
    dob: str,                      # format: "DD.MM.YYYY" or whatever the datepicker expects
    gender: str = "Männlich",      # "Männlich" | "Weiblich" | "Andere"
    email: str = "",
    external_id: str = "",
    doctor_name: str | None = None # None = keep the pre-filled default
):
    """Fills out and submits the patient creation form.

        Waits for the patient form to become visible, then fills in the
        required fields (first name, last name, date of birth, gender) and
        any optional fields that are provided (email, external ID, doctor).
        Finally submits the form.

        Args:
            first_name: Patient's first name.
            last_name: Patient's last name.
            dob: Date of birth, in the format expected by the datepicker
                (e.g. "DD.MM.YYYY").
            gender: Patient's gender. One of "Männlich", "Weiblich", or
                "Andere". Defaults to "Männlich".
            email: Patient's email address. Skipped if empty.
            external_id: External patient ID. Skipped if empty.
            doctor_name: Name of the doctor to assign via the doctor
                react-select field. If None, the pre-filled default doctor
                is kept and the field is not touched.
    """

    form = page.locator("#patient-form")
    await form.wait_for(state="visible")

    await form.locator('input[name="firstName"]').fill(first_name)
    await form.locator('input[name="lastName"]').fill(last_name)

    # 3. Email (optional)
    if email:
        await form.locator('input[name="email"]').fill(email)



    # 5. External patient ID (optional)
    if external_id:
        await form.locator('input[name="patientExternalID"]').fill(external_id)

    # 6. Gender radio
    await form.locator(f'label:has(input[name="gender"][label="{gender}"])').click()
    # force=True because the actual <input> is visually hidden behind the styled <span>

    # 7. Doctor (react-select) — only touch it if a specific doctor is requested
    if doctor_name:
        doctor_select = form.locator(".DoctorsSelect-module_container_SXraQ")
        # remove the currently selected doctor chip, if any
        remove_btn = doctor_select.locator('[aria-label^="Remove"]')
        if await remove_btn.count() > 0:
            await remove_btn.click()
        select_input = doctor_select.locator("input#react-select-5-input")
        await select_input.click()
        await select_input.fill(doctor_name)
        await page.get_by_text(doctor_name, exact=False).click()
    # 4. Date of birth (react-datepicker)
    dob_input = form.locator(".DatePicker-module_input_nXZlF")
    await dob_input.click()
    await dob_input.fill(dob)
        #await dob_input.press("Escape")  # closes the calendar popup without changing focus issues
    # 8. Submit
    submit_btn = page.locator('button[form="patient-form"][type="submit"]')

    await submit_btn.click()

    print(f"Patient '{first_name} {last_name}' submitted")


async def upload_patient_picture(picture_dir:Path):
    """Uploads a Pano study image for the current patient.

       Clicks the "Pano" button, sets the given file on the upload input,
       and submits the form.

       Args:
           picture_dir: Path to the image file to upload.
       """

    button = page.locator('button[type="button"]').filter(has_text="Pano")
    await button.click()
    file_input = page.locator('#upload-study-form input[type="file"]')
    await file_input.set_input_files(picture_dir)
    submit_btn = page.locator('button[type="submit"]')
    await submit_btn.click()
    await page.wait_for_timeout(5000)


async def check_preview_image(page, expected_alt: str = "Pano AI")-> bool:
    """Checks whether a preview image or loading indicator with the given alt text is present.

        Args:
            page: Playwright page to search in.
            expected_alt: Alt text of the image to look for. Defaults to "Pano AI".

        Returns:
            True if at least one matching image, loading or preview is found, False otherwise.
        """
    await page.wait_for_timeout(500)
    loading = page.locator('.ReportGenerationStatus-module_container_6AYLt')
    preview = page.locator('[data-testid^="preview-report-Pano-"]')
    locator = page.locator(f'img[alt="{expected_alt}"]')

    return  await locator.count() != 0 or await preview.count() != 0 or await loading.count() != 0


async def go_to_patient_report( user_id: int,max_retries:int=20):
    """Opens a patient's page by row index in the patients table.

        Reloads the patients list, scrolls the infinite-scroll table until
        the row at `user_id` is loaded, extracts that patient's ID from the
        row's React props, and navigates to their patient page.

        Retries recursively on failure: a timeout waiting for the page/table
        reloads and retries with `max_retries` decremented; a preview image
        already present, or a missing row (`IndexError`), restarts from
        `user_id + 1` or `0` respectively.

        Args:
            user_id: Index of the patient row to open in the table.
            max_retries: Max retry attempts on page load/timeout errors.
                Defaults to 20.

        Raises:
            OSError: If the patients page/row can't be loaded after
                exhausting `max_retries`.
        """
    await page.reload()
    await page.wait_for_timeout(500)

    try:
        if page.url.rstrip("/") != "https://app.diagnocat.eu/patients".rstrip("/"):
            print("Opening data page...")
            _website = await page.goto(
            "https://app.diagnocat.eu/patients",
            wait_until="domcontentloaded",
            timeout=10000,
            )

        row_selector = "tr.TableWithInfiniteScroll-module_tableRow_7Ru4e"

        _body = await page.wait_for_selector("body", timeout=15000)
        _row = await page.wait_for_selector(row_selector, timeout=15000)
    except TimeoutError as e:
        print(f"couldn't find body/row,skipping page: {e}")
        if max_retries <= 0:
            raise OSError("Window is closed or can't be seen")
        await go_to_patient_report(user_id ,max_retries -1)
        return


    # Scroll until we have enough rows loaded to reach user_id
    # Wait for the next page
    while True:
            rows = await page.query_selector_all(row_selector)

            if len(rows) > user_id:
                break  # We have enough rows, stop scrolling

            # Not enough rows yet — scroll down to load more
            await rows[-1].scroll_into_view_if_needed()


    try:
        # await rows[user_id].click()
        row_data_json = await rows[user_id].evaluate("""
        el => {
            const key = Object.keys(el).find(k => k.startsWith('__reactProps$'));
            if (!key) return null;
            const props = el[key];
            return JSON.stringify(props, (k, v) => typeof v === 'function' ? undefined : v);
        }
        """)
        import json
        row_data = json.loads(row_data_json)
        patient_id = row_data["children"][0]["props"]["children"]["props"]["row"]["original"]["ID"]
        patient_url = f"https://app.diagnocat.eu/patients/{patient_id}"

        await page.goto(patient_url, wait_until="domcontentloaded", timeout=10000)
        await page.wait_for_timeout(500)
        if await check_preview_image(page):
            print("Something is wrong: the picute is already there")
            await go_to_patient_report(user_id+1,max_retries)
            return


    except IndexError as e:
        print(f"User_id: {user_id} the picture wasn't there: {e} ")
        await page.close()
        await go_to_patient_report(0,max_retries)
        return






async def get_patient_amount()->int:
    """Gets the total patient count from Diagnocat.

       Tries to read the count directly from the active filter badge first.
       If that element isn't found (or raises a Playwright `Error`), falls
       back to scrolling the patient table until no new rows load for
       `max_stable_checks` consecutive polls, then returns the row count.


       Returns:
           int: The total number of patients.

       Raises:
           LookupError: If the filter badge amount is 0, or if the
               filter badge element could not be located (this is caught
               internally and triggers the scroll-based fallback).
       """
    try:
        amount_el = await page.wait_for_selector(
            "span.Filters-module_amount_zjpHX.Filters-module_amountActive_ysGOs"
        )
        if amount_el:
            amount_text = (await amount_el.inner_text()).strip()
            amount = int(amount_text)
            print(f"Active filter amount: {amount}")
            if amount == 0:
                raise LookupError("amount of 0")
            return(amount)
        else:
            amount = None
            raise LookupError("No type found")
    except LookupError as e :
        print(f"{e}, tried to find amount out with scrooling " )

        row_selector = "tr.TableWithInfiniteScroll-module_tableRow_7Ru4e"

        _row = await page.wait_for_selector(row_selector)

        # Keep scrolling until no new rows appear
        previous_count = 0
        max_stable_checks = 200  # how many consecutive "no growth" checks before giving up
        poll_interval = 50  # ms between checks
        stable_checks = 0

        while True:
            rows = await page.query_selector_all(row_selector)
            current_count = len(rows)

            if current_count > previous_count:
                # still growing — reset patience, keep going
                previous_count = current_count
                stable_checks = 0
                await rows[-1].scroll_into_view_if_needed()
            else:
                # no growth this check — don't give up immediately,
                # could just be a slow network round-trip

                stable_checks += 1
                if stable_checks >= max_stable_checks:
                    break
                # nudge scroll again in case loader needs re-triggering
                if rows:
                    await rows[-1].scroll_into_view_if_needed()

            await page.wait_for_timeout(poll_interval)

        return previous_count
