import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print('Navigating...')
        await page.goto('https://www.canada.ca/en/innovation-science-economic-development/news.html', wait_until='networkidle')
        
        # Look for news articles on the page
        titles = await page.evaluate('''() => {
            return Array.from(document.querySelectorAll('a'))
                .filter(a => a.href.includes('/news/'))
                .map(a => a.innerText.trim())
                .filter(t => t.length > 10)
                .slice(0, 10);
        }''')
        print("Found titles:", titles)
        await browser.close()

asyncio.run(main())
