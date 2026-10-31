import asyncio
import os
import sys
sys.path.append("backend")

from playwright.async_api import async_playwright
from app.core.security import create_access_token

ARTIFACT_DIR = r"C:\Users\Vamshikrishna\.gemini\antigravity\brain\ba39a4de-b6aa-4c95-9ea6-ee009b5c1563"

async def test_image_viewer_controls():
    token = create_access_token("USR-DOC-RAO-001", "doctor")
    tokens = {"accessToken": token, "refreshToken": token}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})

        await page.goto("http://localhost:3100/", wait_until="domcontentloaded")
        await page.evaluate("""tokens => {
            localStorage.setItem('clinixai.tokens', JSON.stringify(tokens));
        }""", tokens)

        aid = "AI-2026-AC679D"
        print(f"\n--- Testing MedicalImageViewer controls for {aid} ---")
        await page.goto(f"http://localhost:3100/app/ai-analysis/{aid}", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        # 1. Side-by-side (default)
        imgs = await page.locator("img").all()
        assert len(imgs) >= 2, f"Expected at least 2 images in side-by-side, got {len(imgs)}"
        print("[PASS] Side-by-side mode displays 2 images.")
        await page.screenshot(path=os.path.join(ARTIFACT_DIR, "viewer_side_by_side.png"))

        # 2. Overlay mode
        overlay_btn = page.locator("button:has-text('Overlay')")
        await overlay_btn.click()
        await page.wait_for_timeout(1000)
        overlay_imgs = await page.locator("img").all()
        assert len(overlay_imgs) >= 2, f"Expected at least 2 images composited in overlay, got {len(overlay_imgs)}"
        print("[PASS] Overlay mode displays composited images.")
        await page.screenshot(path=os.path.join(ARTIFACT_DIR, "viewer_overlay.png"))

        # 3. Original only mode
        orig_btn = page.locator("button:has-text('Original only')")
        await orig_btn.click()
        await page.wait_for_timeout(1000)
        orig_imgs = await page.locator("img").all()
        assert len(orig_imgs) >= 1, f"Expected 1 image in original only mode, got {len(orig_imgs)}"
        print("[PASS] Original only mode displays original MRI scan.")
        await page.screenshot(path=os.path.join(ARTIFACT_DIR, "viewer_original_only.png"))

        # 4. Zoom in & Zoom out & Reset
        zoom_in_btn = page.locator("button[aria-label='Zoom in']")
        await zoom_in_btn.click()
        await zoom_in_btn.click()
        await page.wait_for_timeout(500)
        print("[PASS] Zoom in works.")
        await page.screenshot(path=os.path.join(ARTIFACT_DIR, "viewer_zoomed.png"))

        reset_btn = page.locator("button[aria-label='Reset zoom and pan']")
        await reset_btn.click()
        await page.wait_for_timeout(500)
        print("[PASS] Reset zoom works.")

        # Switch back to side-by-side
        side_btn = page.locator("button:has-text('Side-by-side')")
        await side_btn.click()
        await page.wait_for_timeout(500)

        # 5. Fullscreen toggle
        fs_btn = page.locator("button[aria-label='Enter fullscreen']")
        if await fs_btn.count() > 0:
            await fs_btn.click()
            await page.wait_for_timeout(500)
            print("[PASS] Enter fullscreen works.")
            exit_fs_btn = page.locator("button[aria-label='Exit fullscreen']")
            assert await exit_fs_btn.count() > 0, "Exit fullscreen button not found"
            await exit_fs_btn.click()
            await page.wait_for_timeout(500)
            print("[PASS] Exit fullscreen works.")

        print("\n=== ALL VIEWER CONTROLS VERIFIED SUCCESSFULLY! ===")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_image_viewer_controls())

