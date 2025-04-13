import time
import logging
import os
import random
import sys
import asyncio

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError


TARGET_URL = os.getenv('TARGET_URL', "https://www.pajacyk.pl/")
CLICK_ELEMENT_CLASS = os.getenv('CLICK_ELEMENT_CLASS', "pajacyk__clickbox")
SUCCESS_ELEMENT_SELECTOR = os.getenv('SUCCESS_SELECTOR', ".pajacyk__thankyou")
WAIT_TIMEOUT_MS = int(os.getenv('WAIT_TIMEOUT', 25)) * 1000


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

async def perform_one_attempt(browser):
    context = None
    page = None
    click_successful = False
    verification_successful = False
    attempt_success = False

    try:
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
            java_script_enabled=True,
            accept_downloads=False,
            bypass_csp=True
        )
        page = await context.new_page()

        await page.goto(TARGET_URL, wait_until='domcontentloaded', timeout=WAIT_TIMEOUT_MS)

        click_locator = page.locator(f".{CLICK_ELEMENT_CLASS}")
        await click_locator.wait_for(state="visible", timeout=WAIT_TIMEOUT_MS)

        await asyncio.sleep(random.uniform(0.1, 0.5))

        await click_locator.click(timeout=15000)
        click_successful = True

        success_locator = page.locator(SUCCESS_ELEMENT_SELECTOR)
        await success_locator.wait_for(state="visible", timeout=WAIT_TIMEOUT_MS)

        # ---- Add logging for the count back inside this block ----
        try:
            count_span_locator = success_locator.locator("main > p > span") # Selector for the span with the number
            count_text = await count_span_locator.inner_text(timeout=5000) # Short timeout to get text
            # ADDED BACK: Log the detected count
            logger.info(f"Success confirmation element found! Daily count detected: {count_text}")
        except Exception:
            # If parsing the count fails, still log general success confirmation
            logger.info("Success confirmation element found! (Count span not parsed).")
        # ---------------------------------------------------------

        verification_successful = True # Set success flag if the element appeared

    except PlaywrightTimeoutError:
        logger.warning(f"Timeout error during attempt (Click Element: {CLICK_ELEMENT_CLASS} or Success Element: {SUCCESS_ELEMENT_SELECTOR}).")
    except PlaywrightError as e:
        if "Target closed" not in str(e) and "canceled" not in str(e):
             logger.warning(f"Playwright error during attempt: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during attempt: {e}", exc_info=False)

    finally:
        if page:
            try: await page.close()
            except Exception: pass
        if context:
            try: await context.close()
            except Exception: pass

        attempt_success = click_successful and verification_successful
        return attempt_success


async def main():
    browser = None
    p = None

    logger.info("--- Pajacyk Playwright Clicker Container Starting (No Delay Mode) ---")
    logger.info(f"Target URL: {TARGET_URL}")
    logger.info("!!! WARNING: Running WITHOUT DELAY between attempts. This is highly aggressive. !!!")

    success_count = 0
    failure_count = 0
    attempt_number = 0

    try:
        p = await async_playwright().start()
        logger.info("Launching persistent headless Chromium browser...")
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
            ]
        )
        logger.info("Persistent browser launched successfully.")

        while True:
            attempt_number += 1
            start_time = time.time()
            if await perform_one_attempt(browser):
                success_count += 1
                duration = time.time() - start_time
                # The log message below already includes S/F counts
                logger.info(f"Attempt #{attempt_number} successful ({duration:.2f}s). [S: {success_count}, F: {failure_count}]")
            else:
                failure_count += 1
                duration = time.time() - start_time
                logger.warning(f"Attempt #{attempt_number} failed ({duration:.2f}s). [S: {success_count}, F: {failure_count}]")


            await asyncio.sleep(0.01)


    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down.")
    except Exception as e:
        logger.critical(f"Fatal error in main loop or browser launch: {e}", exc_info=True)
    finally:
        logger.info("Cleaning up main browser instance...")
        if browser:
            try: await browser.close()
            except Exception as e: logger.error(f"Error closing main browser: {e}")
        if p:
             try: await p.stop()
             except Exception as e: logger.error(f"Error stopping Playwright: {e}")
        logger.info("Shutdown complete.")

        if 'e' in locals() and not isinstance(e, KeyboardInterrupt):
             sys.exit(1)
        else:
             sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())