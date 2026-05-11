import os
import sys
import asyncio
from playwright.async_api import async_playwright

async def generate_card(hook_text, category_text, output_path):
    """Renders the HTML template with dynamic text and captures a high-res screenshot."""
    template_path = os.path.abspath("scripts/templates/social_card.html")
    
    if not os.path.exists(template_path):
        print(f"Error: Template not found at {template_path}")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1200, 'height': 627})
        
        # Load template
        await page.goto(f"file://{template_path}")
        
        # Inject content using safe template literals
        # We escape backticks to prevent injection issues in the evaluate string
        safe_hook = hook_text.replace("`", "\\`").replace("${", "\\${")
        safe_category = category_text.replace("`", "\\`").replace("${", "\\${")
        
        await page.evaluate(f"""
            document.getElementById('hook-text').innerText = `{safe_hook}`;
            document.getElementById('category-text').innerText = `{safe_category}`;
        """)
        
        # Wait for fonts and styles to settle
        await page.wait_for_timeout(1500)
        
        # Capture screenshot
        await page.screenshot(path=output_path, type="png")
        await browser.close()
        print(f"Successfully generated social card: {output_path}")

if __name__ == "__main__":
    # Check for required arguments
    if len(sys.argv) < 3:
        print("Usage: python generate_social_card.py <hook_text> <category_text> [output_path]")
        sys.exit(1)
        
    hook = sys.argv[1]
    category = sys.argv[2]
    output = sys.argv[3] if len(sys.argv) > 3 else "reports/linkedin/social_card.png"
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output), exist_ok=True)
    
    asyncio.run(generate_card(hook, category, output))
