import requests as r
import json
import time
import random
import logging
import asyncio
import os

from dotenv import load_dotenv

from playwright.async_api import async_playwright, Playwright, expect


# Import Dune-related funcs
from dune_client.types import QueryParameter
from dune_client.client import DuneClient
from dune_client.query import QueryBase

# Secret Environment Variables
load_dotenv('secret.env')

# Create an instance of the logger
logger = logging.getLogger()

# Check if there are existing handlers
if not logger.handlers:
    # Logging set up 
    log_format = logging.Formatter('%(asctime)-15s %(levelname)-2s %(message)s')
    sh = logging.StreamHandler()
    sh.setFormatter(log_format)

    # Add the handler
    logger.addHandler(sh)
    logger.setLevel(logging.INFO)


async def run(playwright: Playwright):
    chromium = playwright.chromium
    browser = await chromium.launch(headless=True)
    try:
        # Set initial browser context to avoid detection
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},  # Set desired window size
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15'  # Set custom user agent
        )

        # Create a new page
        page = await context.new_page()

        # Navigate to Dune Analytics Site
        await page.goto("https://dune.com/discover/content/trending",wait_until="networkidle", timeout=120000)

        # Locate navigation panel in the form of ul tag
        await expect(page.locator("ul[class='SidePanel_panel__bZFcx']")).to_be_visible(timeout=20000) 
        nav_locator = page.locator("ul[class='SidePanel_panel__bZFcx']")  # Adjust the selector as needed

        # Get all nav bar items within the unordered list
        nav_items = nav_locator.locator("li[class='SidePanel_section__tKVhT']")

        # Category items
        category_items = nav_items.nth(0)

        logger.info(f"Nav panel item count: {await nav_items.count()}")

        # We will press up to 5 buttons on the nav panel randomly to simulate human action
        # May lead to sign in page automatically sometimes
        logger.info("Starting random clicks...")
        for i in range(5):
            category_choice = random.choice([0,1,2])
            category = category_items.locator('li')
            await category.nth(category_choice).click()
            try:
                await page.wait_for_function("window.location.href.includes('login')",timeout=10000)
                break
            except:
                pass
            sub_category_choice = random.choice([1,2])
            options = nav_items.nth(sub_category_choice)
            option_items = options.locator('li')
            option_choice = random.choice(list(range(0,await option_items.count())))
            chosen = option_items.nth(option_choice)
            await chosen.click()
            try:
                await page.wait_for_function("window.location.href.includes('login')",timeout=10000)
                break
            except:
                pass
        logger.info("Random clicking ended!")

        # Skip login btn click if already auto directed to login page
        if 'login' not in page.url:
            logger.info("Clicking Login button...")
            sign_in_locator = page.locator("a[class='Button_button__MJ5pb "+\
                                        "buttonThemes_button__jfRFC "+\
                                        "buttonThemes_theme-secondary-light__KAHJx "+\
                                        "Button_size-M__fDw4z']")
            # Cannot use usual locator.click() method, use javascript to force click
            await page.evaluate("element => element.click()", await sign_in_locator.element_handle())
            logger.info("Login Button clicked...")


        # Fill up login credentials
        logger.info("Filling up credentials...")
        username_locator = page.locator('input[name="username"]')
        await username_locator.fill(os.getenv('dune-username'))

        password_locator = page.locator('input[name="password"]')
        await password_locator.fill(os.getenv('dune-pw'))
        logger.info("Filled up credentials!")

        # Submit login credentials
        submit_btn_locator = page.locator('button[type="submit"]')
        await submit_btn_locator.click()
        logger.info("Clicked Submit!")

        # Navigate to personal queries page
        library_btn_locator = page.locator('div[class="HeaderDesktop_headerLink__txGSd"]').filter(has_text="Library")
        await library_btn_locator.click()
        logger.info("Clicked Library button!")

        # Search for Solana query
        search_locator = page.locator('input[placeholder="Search content"]')
        await search_locator.fill('top trading memecoins (solana)')
        time.sleep(3)
        logger.info("Filled search bar!")

        # Click for Solana query
        query_locator =  page.locator('a[class="ContentList_contentName__OAzIv"]').filter(has_text="Top Trading Memecoins (Solana)")
        await query_locator.click()
        logger.info("Clicked solana query!")

        # Trigger Solana query run
        run_btn_locator = page.locator('button[id="run-query-button"]')
        await run_btn_locator.click()
        await page.wait_for_selector("button[class='Button_button__MJ5pb buttonThemes_button__jfRFC buttonThemes_loading__XjQdr buttonThemes_theme-tertiary__v7VoN Button_size-M__fDw4z']", timeout=120000)
        logger.info("Triggered query run...")
        await expect(run_btn_locator).to_have_text(expected="Cancel",timeout=60000)
        logger.info("Button text changed from 'Run' to 'Cancel'.")
        await expect(run_btn_locator).to_have_text(expected="Run",timeout=240000)
        logger.info("Button text changed from 'Cancel' to 'Run'.")
        logger.info("Query Run Completed!")
        
        # Check if its query time out and retry if so, else skip if fail again
        query_box = page.locator('div[class="visual_result__6q0xu"]')
        box_text = await query_box.inner_text()
        if 'Query execution timed out' in box_text:
            await run_btn_locator.click()
            await page.wait_for_selector("button[class='Button_button__MJ5pb buttonThemes_button__jfRFC buttonThemes_loading__XjQdr buttonThemes_theme-tertiary__v7VoN Button_size-M__fDw4z']", timeout=120000)
            logger.info("Triggered query run...")
            await expect(run_btn_locator).to_have_text(expected="Cancel",timeout=60000)
            logger.info("Button text changed from 'Run' to 'Cancel'.")
            await expect(run_btn_locator).to_have_text(expected="Run",timeout=240000)
            logger.info("Button text changed from 'Cancel' to 'Run'.")
            logger.info("Query Run Completed!")
            box_text = await query_box.inner_text()
            if 'Query execution timed out' in box_text:
                logger.info("Query execution failed twice, skipping this iteration!")
                raise Exception("Query execution failed! Skipping now...")

        # Retrieve query result
        dune = DuneClient(os.getenv('dune-api-key'))
        query_result = dune.get_latest_result_dataframe(os.getenv('dune-solana-query')).sort_values(by='pool_created', ascending=False)
        logger.info("Retrieved result!")
        
        # result placeholder for checks
        result_cnt = 0
        
        # Set up telegram api


        logger.info("Running through query result")
        if len(query_result):
            for _, row in query_result.iterrows():
                # Initialise empty placeholders
                token_name = None
                token_symbol = None
                token_address = row['token_address']
                pool_created = row['elapsed_time']
                top10_holder = 0.0
                holder_cnt = None
                current_change = None
                mkt_cap = None
                volume = None
                liquidity = None
                gecko_url = None
                swap_url = None
                gmgn_ai_url = None
                misc = None
                
                solsniffer = None
                gecko_terminal = None

                solana_message = "📈 New Potential 🟣 SOL 🟣 Tokens to APE!!! 📈\n\n"

                logger.info(f"Looking into token: {row['token_address']}")
                logger.info("Calling security API...")
                # Check for security, if fail skip token
                try:
                    await page.goto(f"https://solsniffer.com/scanner/{row['token_address']}", wait_until="load", timeout=60000) # let solsniffer trigger checks
                    await page.goto(f"https://solsniffer.com/api/v1/sniffer/token/{row['token_address']}", wait_until="load", timeout=60000)
                    solsniffer = await page.evaluate("document.body.innerText")
                    logger.info("Calling security API 1st try...")
                    solsniffer = json.loads(solsniffer)['tokenData']
                    if solsniffer == {}:
                        logger.info("Empty Security Data!")
                        raise Exception
                except: # Remedy if rate limit is hit, else error pop up again if api changes
                    time.sleep(10)
                    await page.goto(f"https://solsniffer.com/api/v1/sniffer/token/{row['token_address']}", wait_until="load", timeout=60000)
                    logger.info("Calling security API 2nd try...")
                    solsniffer = await page.evaluate("document.body.innerText")
                
                try:
                    solsniffer = json.loads(solsniffer)['tokenData']
                    audit = solsniffer['auditRisk']
                    logger.info("Retrieved security data!")
                    logger.info(f"audit data checker: {audit.keys()}")
                    if (audit['mintDisabled'] == True) and (audit['freezeDisabled'] == True) and (audit['lpBurned'] == True):
                        if len(solsniffer['ownersList']) >= 11:
                            for e in solsniffer['ownersList'][1:11]: # exclude pool %
                                top10_holder += float(e['percentage'])
                        else:
                            for e in solsniffer['ownersList'][1:]: # exclude pool %
                                top10_holder += float(e['percentage'])      
                    else:
                        logger.info("Skipped with audit failed!")
                        continue
                except Exception as e:
                    # solsniffer might not have enough time to check all newly launched tokens
                    # need to manually trigger and check ourselves unfortunately
                    # include manual security check alert!
                    logger.error(e, stack_info=True, exc_info=True)
                    logger.info("Manual security and holder checks needed!")
                    top10_holder = f"[Check solscan OR GMGN manually for top10 and audit data!!!](https://solsniffer.com/scanner/{row['token_address']})"
                    misc = f"[Check solsniffer manually!!!](https://solsniffer.com/api/v1/sniffer/token/{row['token_address']})"
                
                logger.info("Calling Gecko API...")
                try:
                    await page.goto(f"https://app.geckoterminal.com/api/p1/solana/pools/{row['pool_address']}"+\
                                    "?include=dex%2Cdex.network.explorers%2Cdex_link_services"+\
                                    "%2Cnetwork_link_services%2Cpairs%2Ctoken_link_services%2Ctokens.token_security_metric"+\
                                    "%2Ctokens.tags%2Cpool_locked_liquidities&base_token=0", wait_until="load", timeout=60000)
                    gecko_terminal = await page.evaluate("document.body.innerText")
                    gecko_terminal = json.loads(gecko_terminal)
                except: # Remedy if rate limit is hit, else error pop up again if api changes which then require intervention
                    time.sleep(10)
                    await page.goto(f"https://app.geckoterminal.com/api/p1/solana/pools/{row['pool_address']}"+\
                                    "?include=dex%2Cdex.network.explorers%2Cdex_link_services"+\
                                    "%2Cnetwork_link_services%2Cpairs%2Ctoken_link_services%2Ctokens.token_security_metric"+\
                                    "%2Ctokens.tags%2Cpool_locked_liquidities&base_token=0", wait_until="load", timeout=60000)
                    gecko_terminal = await page.evaluate("document.body.innerText")
                    gecko_terminal = json.loads(gecko_terminal)
                logger.info("Market data retrieved!")
                logger.info(f"gecko terminal checker: {gecko_terminal.keys()}")
                
                # Check for negative roi, if true, reject as token already dumped
                if '-' in gecko_terminal['data']['attributes']['price_percent_change']:
                    logger.info("Token skipped with negative price change!")
                    continue
                
                for e in gecko_terminal['included']:
                    if 'soul_scanner_data' in e['attributes'] and e['attributes']['soul_scanner_data']['deployer']:
                        holder_cnt = e['attributes']['holder_count']
                    elif e['type'] == 'pair':
                        token_name = e['attributes']['base_name'] if 'base_name' in e['attributes'].keys() else e['attributes']['name']
                        token_symbol = e['attributes']['base_symbol'] if 'base_symbol' in e['attributes'].keys() else e['attributes']['symbol']
                
                current_change = gecko_terminal['data']['attributes']['price_percent_change']
                
                mkt_cap = round(float(gecko_terminal['data']['attributes']['fully_diluted_valuation']),2)
                if mkt_cap >= 1000000:
                    mkt_cap = f"{mkt_cap / 1000000.0:.2f}M"  # Convert to millions
                elif mkt_cap >= 1000:
                    mkt_cap = f"{mkt_cap / 1000.0:.2f}K"      # Convert to thousands

                volume = round(float(gecko_terminal['data']['attributes']['from_volume_in_usd']),2)
                if volume >= 1000000:
                    volume = f"{volume / 1000000.0:.2f}M"  # Convert to millions
                elif volume >= 1000:
                    volume = f"{volume / 1000.0:.2f}K"      # Convert to thousands

                liquidity = round(float(gecko_terminal['data']['attributes']['reserve_in_usd']),2)
                if liquidity >= 1000000:
                    liquidity = f"{liquidity / 1000000.0:.2f}M"  # Convert to millions
                elif liquidity >= 1000:
                    liquidity = f"{liquidity / 1000.0:.2f}K"      # Convert to thousands
                
                gecko_url = f"https://www.geckoterminal.com/solana/pools/{row['pool_address']}"
                gmgn_ai_url = f"https://gmgn.ai/sol/token/{token_address}"
                swap_url = f"https://www.raydium.io/swap/?inputMint=So11111111111111111111111111111111111111112&outputMint={token_address}"

                # Add to main message
                # Constructing the message with Markdown formatting
                # Split message into 2 parts cause character limitations via API
                solana_message_1 = solana_message + f"👉 *{token_name}* -- ${token_symbol}\n"+\
                    f"📌 Address: `{token_address}`\n"+\
                    f"🕒 Pool Created: {pool_created}\n"+\
                    f"👑 Top 10 Holder: {round(top10_holder, 2) if type(top10_holder) == float else top10_holder}%\n"+\
                    f"💎 Holder Count: {holder_cnt}\n"+\
                    f"📈 Price Change: {current_change}\n"+\
                    f"🏛️ Market Cap: ${mkt_cap}\n"+\
                    f"📊 Volume: ${volume}\n"+\
                    f"💰 Liquidity: ${liquidity}\n"
                solana_message_2 = f"🦎 [Gecko Terminal]({gecko_url})\n"+\
                    f"🌞🌚 [GMGN.AI]({gmgn_ai_url})\n"+\
                    f"🔄 [Raydium Link]({swap_url})\n"+\
                    f"Misc: {misc}"
                
                logger.info(solana_message_1)
                logger.info(solana_message_2)
                logger.info("Main Message appended!")
                result_cnt += 1
                logger.info(f"Result Count: {result_cnt}")

                logger.info("Sending results via Telegram API...")
                for i, msg in enumerate([solana_message_1,solana_message_2]):
                    url = f"https://api.telegram.org/bot{os.getenv('telegram-bot-api-key')}/sendMessage?chat_id={os.getenv('solana-chat-id')}&text={msg}&parse_mode=Markdown"
                    SentMessageResult = r.get(url).json()
                    if SentMessageResult['ok']:
                        logger.info(f"Telegram Message Part {i} sent!")
                        #SentMessageID = int(SentMessageResult['result']['message_id'])
                        pass
                    else:
                        logger.info(f"Telegram Message Part {i} sent!")
                        #SentMessageID = 0

        logger.info("Finished screening through query!")

    except Exception as e:
        logger.error(e, stack_info=True, exc_info=True)
    
    finally:
        await browser.close()
        await playwright.stop()
    
    logger.info("Script execution completed!")


async def main():
    async with async_playwright() as playwright:
        await run(playwright)

asyncio.run(main())