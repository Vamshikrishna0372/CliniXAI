import asyncio
import os
import sys

# Ensure backend directory in path
sys.path.insert(0, "backend")

from playwright.async_api import async_playwright
from app.core.security import create_access_token

FRONTEND_URL = "http://localhost:3100"
ARTIFACT_DIR = r"C:\Users\Vamshikrishna\.gemini\antigravity\brain\ba39a4de-b6aa-4c95-9ea6-ee009b5c1563"

async def run_browser_verification():
    krish_token = create_access_token("USR-2026-E66A3C", "patient")
    tokens = {
        "accessToken": krish_token,
        "refreshToken": krish_token,
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))

        print("\n--- 1. Seed auth tokens in localStorage ---")
        await page.goto(f"{FRONTEND_URL}/", wait_until="domcontentloaded")
        await page.evaluate("""tokens => {
            localStorage.setItem('clinixai.tokens', JSON.stringify(tokens));
        }""", tokens)

        print("\n--- 2. Krish opens /app/ai-reports ---")
        await page.goto(f"{FRONTEND_URL}/app/ai-reports", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        # Assert no forbidden error
        body_text = await page.inner_text("body")
        assert "Access denied" not in body_text, "Hit Access Denied on /app/ai-reports!"
        assert "AI Reports" in body_text, "Page header 'AI Reports' not found!"
        assert "AI-2026-AC679D" in body_text, "Released report AI-2026-AC679D not found in list!"
        assert "notumor" in body_text, "Prediction 'notumor' not found in report card!"
        print("[PASS] Krish sees released AI analysis AI-2026-AC679D in /app/ai-reports list.")

        list_screenshot = os.path.join(ARTIFACT_DIR, "patient_ai_reports_list.png")
        await page.screenshot(path=list_screenshot, full_page=True)
        print(f"Captured list screenshot: {list_screenshot}")

        print("\n--- 3. Krish clicks 'Open' to view detail ---")
        open_btn = page.locator("a[href*='/app/ai-reports/AI-2026-AC679D']")
        if await open_btn.count() > 0:
            await open_btn.first.click()
        else:
            await page.goto(f"{FRONTEND_URL}/app/ai-reports/AI-2026-AC679D", wait_until="networkidle")

        await page.wait_for_timeout(4000)
        detail_text = await page.inner_text("body")
        assert "AI-2026-AC679D" in detail_text, "Analysis ID not found on detail page!"
        assert "Doctor Reviewed" in detail_text or "Reviewed & Released" in detail_text, "Review status not found on detail page!"
        assert "AI results are advisory" in detail_text, "Advisory safety disclaimer not found!"
        assert "INTERNAL CLINICAL NOTE" not in detail_text, "LEAKED INTERNAL CLINICAL NOTE TO PATIENT!"

        # Verify images are loaded (not broken)
        images = await page.locator("img").all()
        print(f"Found {len(images)} images on report detail page.")
        image_srcs = [await img.get_attribute("src") for img in images]
        blob_urls = [s for s in image_srcs if s and s.startswith("blob:")]
        print(f"Blob image URLs loaded: {blob_urls}")
        assert len(blob_urls) >= 2, f"Expected at least 2 blob images (Original + Grad-CAM), found {len(blob_urls)}!"

        detail_screenshot = os.path.join(ARTIFACT_DIR, "patient_ai_report_detail.png")
        await page.screenshot(path=detail_screenshot, full_page=True)
        print(f"Captured detail screenshot: {detail_screenshot}")

        print("\n--- 4. Test Krish directly accessing /app/ai-analysis ---")
        await page.goto(f"{FRONTEND_URL}/app/ai-analysis", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        curr_url = page.url
        print(f"Current URL after navigating to /app/ai-analysis: {curr_url}")
        assert "/app/ai-reports" in curr_url, f"Expected redirect to /app/ai-reports, got {curr_url}!"
        body_redirect = await page.inner_text("body")
        assert "Access denied" not in body_redirect, "Hit Access Denied when routing from /app/ai-analysis!"
        print("[PASS] Smooth redirect from /app/ai-analysis to /app/ai-reports without 'Access denied'.")

        print("\n--- 5. Test Krish directly accessing /app/ai-analysis/AI-2026-AC679D ---")
        await page.goto(f"{FRONTEND_URL}/app/ai-analysis/AI-2026-AC679D", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        curr_detail_url = page.url
        print(f"Current URL after navigating to /app/ai-analysis/AI-2026-AC679D: {curr_detail_url}")
        assert "/app/ai-reports/AI-2026-AC679D" in curr_detail_url, f"Expected redirect to /app/ai-reports/AI-2026-AC679D, got {curr_detail_url}!"
        body_detail_redirect = await page.inner_text("body")
        assert "Access denied" not in body_detail_redirect, "Hit Access Denied when routing from /app/ai-analysis/$id!"
        print("[PASS] Smooth redirect from /app/ai-analysis/$id to /app/ai-reports/$id without 'Access denied'.")

        print("\n--- 6. Test browser refresh on /app/ai-reports/AI-2026-AC679D ---")
        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(4000)
        reloaded_text = await page.inner_text("body")
        assert "AI-2026-AC679D" in reloaded_text, "Analysis ID not found after reload!"
        reloaded_images = await page.locator("img").all()
        reloaded_srcs = [await img.get_attribute("src") for img in reloaded_images]
        reloaded_blobs = [s for s in reloaded_srcs if s and s.startswith("blob:")]
        print(f"Blob image URLs after reload: {reloaded_blobs}")
        assert len(reloaded_blobs) >= 2, f"Expected at least 2 blob images after reload, found {len(reloaded_blobs)}!"

        refreshed_screenshot = os.path.join(ARTIFACT_DIR, "patient_ai_report_refreshed.png")
        await page.screenshot(path=refreshed_screenshot, full_page=True)
        print(f"Captured refreshed screenshot: {refreshed_screenshot}")

        print("\n=== ALL BROWSER E2E TESTS PASSED SUCCESSFULLY! ===")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_browser_verification())

