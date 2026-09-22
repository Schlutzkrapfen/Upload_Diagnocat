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
