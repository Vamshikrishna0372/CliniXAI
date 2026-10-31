import asyncio
import sys
sys.path.append("backend")
from playwright.async_api import async_playwright
from app.core.security import create_access_token

async def test_doctor_view():
    token = create_access_token("USR-DOC-RAO-001", "doctor")
    tokens = {"accessToken": token, "refreshToken": token}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})

        page.on("console", lambda m: print(f"[CONSOLE {m.type}] {m.text}"))
        page.on("pageerror", lambda e: print(f"[PAGE ERROR] {e}"))

        await page.goto("http://localhost:3100/", wait_until="domcontentloaded")
        await page.evaluate("""tokens => {
            localStorage.setItem('clinixai.tokens', JSON.stringify(tokens));
        }""", tokens)

        for aid in ["AI-2026-AC679D", "AI-2026-466F63"]:
            print(f"\n--- Testing Doctor view for {aid} ---")
            await page.goto(f"http://localhost:3100/app/ai-analysis/{aid}", wait_until="networkidle")
            await page.wait_for_timeout(3000)

            # Check images
            imgs = await page.locator("img").all()
            print(f"Total images for {aid}: {len(imgs)}")
            for i, img in enumerate(imgs):
                src = await img.get_attribute("src")
                alt = await img.get_attribute("alt")
                box = await img.bounding_box()
                print(f"Img {i}: alt={alt}, src={src[:50] if src else None}..., box={box}")

            await page.screenshot(path=f"backend/scratch/doc_view_{aid}.png")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_doctor_view())

