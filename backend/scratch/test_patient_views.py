import asyncio
import json
import urllib.request
from playwright.async_api import async_playwright
import sys
sys.path.append("backend")
from app.core.security import create_access_token

FRONTEND_URL = "http://localhost:3100"

async def test_patient_views():
    # Krish tokens
    krish_token = create_access_token("USR-2026-E66A3C", "patient")
    tokens = {"accessToken": krish_token, "refreshToken": krish_token}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await context.new_page()

        page.on("console", lambda m: print("CONSOLE:", m.type, m.text))

        # 1. Seed localStorage
        await page.goto(f"{FRONTEND_URL}/", wait_until="domcontentloaded")
        await page.evaluate("""t => {
            localStorage.setItem('clinixai.tokens', JSON.stringify(t));
        }""", tokens)

        # 2. Open /app/ai-reports
        print("\n--- Testing /app/ai-reports as Krish ---")
        await page.goto(f"{FRONTEND_URL}/app/ai-reports", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        body_reports = await page.inner_text("body")
        print("Reports page body snippet:")
        print(body_reports.encode("ascii", errors="replace").decode("ascii")[:1500])
        await page.screenshot(path="backend/scratch/patient_ai_reports.png")

        # 3. Open /app/ai-analysis
        print("\n--- Testing /app/ai-analysis as Krish ---")
        await page.goto(f"{FRONTEND_URL}/app/ai-analysis", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        body_analysis = await page.inner_text("body")
        print("Analysis page body snippet:")
        print(body_analysis.encode("ascii", errors="replace").decode("ascii")[:1500])
        await page.screenshot(path="backend/scratch/patient_ai_analysis.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_patient_views())

