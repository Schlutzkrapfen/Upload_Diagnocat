import asyncio
from asyncio.timeouts import timeout
from types import BuiltinMethodType

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
    await page.wait_for_timeout(50000)


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
