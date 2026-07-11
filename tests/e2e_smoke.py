from playwright.sync_api import sync_playwright


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    console_errors: list[str] = []
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.goto("http://127.0.0.1:8000")
    page.wait_for_load_state("networkidle")
    assert page.get_by_role("heading", name="Find the signal. Respect the uncertainty.").is_visible()
    page.get_by_role("button", name="Run three-model analysis").click()
    page.wait_for_selector(".opportunity")
    assert page.locator(".opportunity").count() == 5
    assert page.get_by_text("ENSEMBLE RESULT").is_visible()
    assert not console_errors, console_errors
    browser.close()
