# File: pajacyk_clicker_reused_context_local.py
# Hackathon Version: Reuses a single context and page for multiple attempts.
# Runs LOCALLY using Playwright, without Steel API integration.
# NOTE: Expected to fail after the first successful click on Pajacyk due to website tracking.

import asyncio
import logging
import os
import sys
import time
import signal

from playwright.async_api import (
    async_playwright,
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError
)

# --- Configuration ---
TARGET_URL = os.getenv('TARGET_URL', "https://www.pajacyk.pl/")
CLICK_ELEMENT_SELECTOR = os.getenv('CLICK_SELECTOR', ".pajacyk__clickbox")
SUCCESS_ELEMENT_SELECTOR = os.getenv('SUCCESS_SELECTOR', ".pajacyk__thankyou")
COUNT_SPAN_SELECTOR = os.getenv('COUNT_SPAN_SELECTOR', "main > p > span")
WAIT_TIMEOUT_MS = int(os.getenv('WAIT_TIMEOUT', "15")) * 1000 # Shorter default for faster failure detection
SHORT_TIMEOUT_MS = 5000
MAX_CYCLES_IN_CONTEXT = int(os.getenv('MAX_CYCLES', "5")) # How many times to try within the same context

# --- Resource Blocking ---
RESOURCE_EXCLUSIONS = [
    "*.jpg", "*.jpeg", "*.png", "*.gif", "*.webp", "*.svg", "*.ico",
    "*.css",
    "*.woff", "*.woff2", "*.ttf", "*.otf",
    "*google-analytics.com*", "*googletagmanager.com*", "*facebook.net*",
    "*googleadservices.com*", "*doubleclick.net*",
    "*youtube.com*", "*ytimg.com*",
]

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(taskName)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)
DEFAULT_TASK_NAME = "LOCAL_LOOP"

# --- Global State ---
abort_event = asyncio.Event()

# --- Signal Handling ---
def handle_signal():
    logger.warning("Abort signal received! Stopping loop...", extra={'taskName': 'SIGNAL'})
    abort_event.set()

# --- Main Function ---
async def main():
    # Set task name for main logic
    asyncio.current_task().set_name(DEFAULT_TASK_NAME)
    log_extra = {'taskName': DEFAULT_TASK_NAME}

    loop = asyncio.get_running_loop()
    try:
        loop.add_signal_handler(signal.SIGINT, handle_signal)
        loop.add_signal_handler(signal.SIGTERM, handle_signal)
    except NotImplementedError:
        logger.warning("Signal handlers for SIGTERM not fully supported on this platform.", extra=log_extra)

    playwright_instance = None
    browser = None
    context = None
    page = None
    exit_code = 0
    total_success_clicks = 0

    logger.info("--- Pajacyk Reused Context Clicker (Local Mode) ---", extra=log_extra)
    logger.info(f"Target URL: {TARGET_URL}", extra=log_extra)
    logger.info(f"Max Cycles in Reused Context: {MAX_CYCLES_IN_CONTEXT}", extra=log_extra)
    logger.info("Running with locally launched browser.", extra=log_extra)

    try:
        # --- Start Playwright ---
        logger.info("Starting Playwright...", extra=log_extra)
        playwright_instance = await async_playwright().start()

        # --- Launch Local Browser ---
        logger.info("Launching local Chromium browser...", extra=log_extra)
        browser = await playwright_instance.chromium.launch(
            headless=False, # Set to False to easily observe the reuse failure
            args=[ # Optional args
                '--no-sandbox',
                '--disable-dev-shm-usage',
                # '--disable-gpu', # Often fine to leave enabled locally unless issues arise
                '--window-size=1280,720',
                # '--blink-settings=imagesEnabled=false', # Disable if you don't need to see images
            ]
        )
        logger.info("Local browser launched successfully.", extra=log_extra)

        # --- Create ONE Reusable Context ---
        logger.info("Creating single reusable BrowserContext...", extra=log_extra)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36', # Example UA
            java_script_enabled=True,
            accept_downloads=False,
            bypass_csp=True
            # Note: Cookies, localStorage, etc. will persist across loops!
        )
        logger.info("BrowserContext created. Applying resource blocking...", extra=log_extra)

        # Apply resource blocking to the single context
        blocked_count = 0
        for pattern in RESOURCE_EXCLUSIONS:
            try:
                await context.route(pattern, lambda route: route.abort())
                blocked_count += 1
            except Exception as e_route:
                logger.error(f"Error setting up route for pattern '{pattern}': {e_route}", extra=log_extra)
        logger.info(f"Resource blocking applied for {blocked_count} patterns.", extra=log_extra)

        # --- Create ONE Reusable Page ---
        logger.info("Creating single reusable Page...", extra=log_extra)
        page = await context.new_page()
        logger.info("Page created. Starting the loop...", extra=log_extra)

        # --- The Reused Context Loop ---
        for i in range(1, MAX_CYCLES_IN_CONTEXT + 1):
            if abort_event.is_set():
                logger.warning(f"Abort signal detected before starting Cycle {i}. Breaking loop.", extra=log_extra)
                break

            logger.info(f"--- Starting Cycle {i}/{MAX_CYCLES_IN_CONTEXT} within the same context ---", extra=log_extra)
            cycle_success = False
            extracted_count = "N/A"
            cycle_start_time = time.monotonic()

            try:
                # 1. Go to Page (Every Time)
                logger.info(f"Navigating to {TARGET_URL}...")
                nav_start_time = time.monotonic()
                await page.goto(TARGET_URL, wait_until='domcontentloaded', timeout=WAIT_TIMEOUT_MS)
                nav_duration = time.monotonic() - nav_start_time
                logger.info(f"Navigation complete in {nav_duration:.2f}s.")

                # 2. Try to Find and Click
                click_locator = page.locator(CLICK_ELEMENT_SELECTOR)
                logger.info(f"Waiting for click element: '{CLICK_ELEMENT_SELECTOR}'")
                try:
                    # ** This is the step MOST LIKELY TO FAIL after the first cycle **
                    await click_locator.wait_for(state="visible", timeout=WAIT_TIMEOUT_MS)
                    logger.info("Click element visible. Attempting click...")
                    await click_locator.click(timeout=SHORT_TIMEOUT_MS)
                    logger.info("Click action performed.")
                except PlaywrightTimeoutError:
                    logger.error(f"Timeout waiting for CLICK element ('{CLICK_ELEMENT_SELECTOR}') to be visible. Site likely changed state due to previous click.", extra=log_extra)
                    # Break the loop - no point continuing if the click element isn't found
                    break

                # 3. Verify Success
                success_locator = page.locator(SUCCESS_ELEMENT_SELECTOR)
                logger.info(f"Waiting for success element: '{SUCCESS_ELEMENT_SELECTOR}'")
                try:
                     # ** This may also fail if the click was blocked server-side **
                    await success_locator.wait_for(state="visible", timeout=WAIT_TIMEOUT_MS)
                    cycle_success = True
                    logger.info("Success element visible.")
                    total_success_clicks += 1
                except PlaywrightTimeoutError:
                    logger.error(f"Timeout waiting for SUCCESS element ('{SUCCESS_ELEMENT_SELECTOR}') after click. Click might have been ignored by server.", extra=log_extra)
                    # Break the loop if success isn't verified
                    break

                # 4. Extract Count (Only if successful)
                if cycle_success:
                    try:
                        count_span_locator = success_locator.locator(COUNT_SPAN_SELECTOR)
                        await count_span_locator.wait_for(state="visible", timeout=SHORT_TIMEOUT_MS)
                        raw_count = await count_span_locator.inner_text(timeout=SHORT_TIMEOUT_MS / 2)
                        extracted_count = ''.join(filter(str.isdigit, raw_count)) or "N/A"
                        logger.info(f"Successfully extracted count: {extracted_count}")
                    except PlaywrightTimeoutError:
                        logger.warning("Could not find/get text from count span after success.", extra=log_extra)
                        extracted_count = "Timeout"
                    except Exception as e_count:
                        logger.warning(f"Error extracting count text: {e_count}", extra=log_extra)
                        extracted_count = "Error"

                cycle_duration = time.monotonic() - cycle_start_time
                logger.info(f"Cycle {i} FINISHED. Success: {cycle_success}, Count: {extracted_count}, Duration: {cycle_duration:.2f}s", extra=log_extra)

            except PlaywrightTimeoutError as e_timeout:
                # Catch timeouts during navigation or initial waits
                cycle_duration = time.monotonic() - cycle_start_time
                logger.error(f"Cycle {i} FAILED: Timeout during navigation or waiting for element. Duration: {cycle_duration:.2f}s. Error: {e_timeout}", extra=log_extra)
                break # Stop loop on navigation/wait failure
            except PlaywrightError as e_playwright:
                # Catch errors like page crash, etc.
                cycle_duration = time.monotonic() - cycle_start_time
                logger.error(f"Cycle {i} FAILED: PlaywrightError. Duration: {cycle_duration:.2f}s. Error: {e_playwright}", extra=log_extra)
                exit_code = 1
                break # Stop loop on critical playwright errors
            except Exception as e_general:
                cycle_duration = time.monotonic() - cycle_start_time
                logger.error(f"Cycle {i} FAILED: Unexpected Error. Duration: {cycle_duration:.2f}s. Error: {e_general}", exc_info=True, extra=log_extra)
                exit_code = 1
                break # Stop loop on unexpected errors

            # Optional small delay before the next attempt in the loop
            if not abort_event.is_set():
                 await asyncio.sleep(1) # Wait 1 second before next iteration

        # Determine final loop iteration count correctly
        final_attempt_count = i if 'i' in locals() else 0
        logger.info(f"--- Loop finished after {final_attempt_count} attempts ---", extra=log_extra)

    except asyncio.CancelledError:
         logger.warning("Main task cancelled, shutting down.", extra=log_extra)
         exit_code = 1 # Indicate abnormal termination
    except Exception as e_fatal:
        logger.critical(f"Fatal error during setup or loop: {e_fatal}", exc_info=True, extra=log_extra)
        exit_code = 1 # Indicate fatal error
    finally:
        logger.info("--- Shutdown Sequence Initiated ---", extra=log_extra)

        # Close page and context FIRST
        logger.info("Closing Page and Context...", extra=log_extra)
        # Add checks to ensure page/context exist before closing
        if page:
            try: await page.close()
            except Exception as e_pg: logger.warning(f"Error closing page: {e_pg}", extra=log_extra)
        if context:
            try: await context.close()
            except Exception as e_ctx: logger.warning(f"Error closing context: {e_ctx}", extra=log_extra)

        # Close browser instance
        logger.info("Closing Browser instance...", extra=log_extra)
        if browser: # Check if browser object exists
            try:
                await browser.close()
            except Exception as e_brws:
                 # Log error but continue shutdown
                 logger.warning(f"Error closing browser: {e_brws}", extra=log_extra)

        # Stop Playwright
        if playwright_instance:
            logger.info("Stopping Playwright...", extra=log_extra)
            try:
                await playwright_instance.stop()
            except Exception as e_pw:
                 # Log error but continue shutdown
                 logger.warning(f"Error stopping Playwright: {e_pw}", extra=log_extra)

        logger.info(f"--- Run Finished ---", extra=log_extra)
        logger.info(f"Total successful clicks recorded in this context: {total_success_clicks}", extra=log_extra)
        logger.info(f"Exiting with code {exit_code}.", extra=log_extra)
        # Use os._exit for a potentially faster exit in simple scripts or containers
        os._exit(exit_code) # Consider sys.exit(exit_code) if more complex cleanup needed


if __name__ == "__main__":
    # Optional: Install uvloop for potential minor performance gains
    # try:
    #     import uvloop
    #     uvloop.install()
    #     logger.info("Using uvloop if available.", extra={'taskName': 'SETUP'})
    # except ImportError:
    #     logger.info("uvloop not found, using default asyncio loop.", extra={'taskName': 'SETUP'})
    #     pass
    asyncio.run(main())