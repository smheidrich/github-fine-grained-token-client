async def launch_ephemeral_chromium_context(p, headless: bool = True):
    """
    Ephemeral version of Playwright's chromium.launch_persistent_context.

    No idea why they didn't just include that themselves...
    """
    browser = await p.chromium.launch(headless=headless)
    context = await browser.new_context()
    await context.new_page()
    return context
