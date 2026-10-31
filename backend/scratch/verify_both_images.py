import asyncio
import json
import urllib.request
from playwright.async_api import async_playwright

FRONTEND_URL = "http://localhost:3100"
BACKEND_URL = "http://127.0.0.1:8000/api/v1"
DOCTOR_EMAIL = "doctor.arjun@clinixai.com"
DOCTOR_PASS = "Doctor@123"
ANALYSIS_ID = "AI-2026-AC679D"

def get_doctor_tokens():
    req = urllib.request.Request(
        f"{BACKEND_URL}/auth/login",
        data=json.dumps({"email": DOCTOR_EMAIL, "password": DOCTOR_PASS}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        return {
            "accessToken": data["access_token"],
            "refreshToken": data["refresh_token"]
        }

async def run_verification():
    tokens = get_doctor_tokens()
    print("1. Authenticated Dr. Rao:", tokens["accessToken"][:25] + "...", flush=True)

    network_events = []
    console_errors = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await context.new_page()

        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        def handle_response(response):
            url = response.url
            if any(k in url for k in ["/image", "/gradcam", "/ai-analyses"]):
                network_events.append({
                    "url": url,
                    "status": response.status,
                    "content_type": response.headers.get("content-type", "")
                })

        page.on("response", handle_response)

        # 2. Seed token and go directly to analysis URL
        print(f"2. Navigating directly to {FRONTEND_URL}/app/ai-analysis/{ANALYSIS_ID}...", flush=True)
        await page.goto(f"{FRONTEND_URL}/", wait_until="domcontentloaded")
        await page.evaluate("""tokens => {
            localStorage.setItem('clinixai.tokens', JSON.stringify(tokens));
        }""", tokens)

        await page.goto(f"{FRONTEND_URL}/app/ai-analysis/{ANALYSIS_ID}", wait_until="domcontentloaded")
        await page.wait_for_timeout(3500)

        # 3. Verify Network Requests
        print("3. Checking Network Requests...", flush=True)
        orig_reqs = [e for e in network_events if f"/ai-analyses/{ANALYSIS_ID}/image" in e["url"]]
        grad_reqs = [e for e in network_events if f"/ai-analyses/{ANALYSIS_ID}/gradcam" in e["url"]]

        print(f"   Original image responses: {len(orig_reqs)}")
        for r in orig_reqs:
            print(f"     Status: {r['status']}, Content-Type: {r['content_type']}")
            assert r["status"] == 200, f"Expected 200 for original image, got {r['status']}"

        print(f"   Grad-CAM responses: {len(grad_reqs)}")
        for r in grad_reqs:
            print(f"     Status: {r['status']}, Content-Type: {r['content_type']}")
            assert r["status"] == 200, f"Expected 200 for Grad-CAM, got {r['status']}"

        # 4. Check View Modes & Images
        print("4. Testing Side-by-side mode (default)...", flush=True)
        imgs = await page.query_selector_all("img")
        print(f"   Found {len(imgs)} rendered images")
        assert len(imgs) >= 2, f"Expected at least 2 images (original and heatmap), found {len(imgs)}"

        for idx, img in enumerate(imgs):
            alt = await img.get_attribute("alt")
            src = await img.get_attribute("src")
            w = await img.evaluate("el => el.naturalWidth")
            h = await img.evaluate("el => el.naturalHeight")
            print(f"     Image {idx} ({alt}): {w}x{h} px, src: {src[:45]}...")
            assert w > 0, f"Image {idx} ({alt}) has naturalWidth 0 (blank)!"
            assert h > 0, f"Image {idx} ({alt}) has naturalHeight 0 (blank)!"

        await page.screenshot(path="backend/scratch/verify_side_by_side.png")
        print("   Captured verify_side_by_side.png", flush=True)

        # 5. Test Overlay Mode
        print("5. Testing Overlay mode...", flush=True)
        overlay_btn = await page.query_selector('button:has-text("Overlay")')
        if overlay_btn:
            await overlay_btn.click()
            await page.wait_for_timeout(1000)
            await page.screenshot(path="backend/scratch/verify_overlay.png")
            print("   Captured verify_overlay.png", flush=True)

        # 6. Test Original Only Mode
        print("6. Testing Original only mode...", flush=True)
        orig_btn = await page.query_selector('button:has-text("Original only")')
        if orig_btn:
            await orig_btn.click()
            await page.wait_for_timeout(1000)
            orig_imgs = await page.query_selector_all("img")
            print(f"   Original only mode images: {len(orig_imgs)}")
            assert len(orig_imgs) >= 1
            w = await orig_imgs[0].evaluate("el => el.naturalWidth")
            assert w > 0
            await page.screenshot(path="backend/scratch/verify_original_only.png")
            print("   Captured verify_original_only.png", flush=True)

        # 7. Test Zoom & Reset
        print("7. Testing Zoom...", flush=True)
        zoom_in_btn = await page.query_selector('button[aria-label="Zoom in"]')
        if zoom_in_btn:
            await zoom_in_btn.click()
            await zoom_in_btn.click()
            await page.wait_for_timeout(500)
            await page.screenshot(path="backend/scratch/verify_zoomed.png")
            print("   Captured verify_zoomed.png", flush=True)

        reset_btn = await page.query_selector('button[aria-label="Reset zoom and pan"]')
        if reset_btn:
            await reset_btn.click()
            await page.wait_for_timeout(500)

        # 8. Test Refresh
        print("8. Testing Page Refresh...", flush=True)
        await page.reload(wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        reloaded_imgs = await page.query_selector_all("img")
        print(f"   After refresh, images rendered: {len(reloaded_imgs)}")
        assert len(reloaded_imgs) >= 2
        for idx, img in enumerate(reloaded_imgs):
            w = await img.evaluate("el => el.naturalWidth")
            h = await img.evaluate("el => el.naturalHeight")
            assert w > 0 and h > 0
        await page.screenshot(path="backend/scratch/verify_after_refresh.png")
        print("   Captured verify_after_refresh.png", flush=True)

        # 9. Verify Console Errors and 500s
        print("9. Checking Console & Server Errors...", flush=True)
        http_500s = [e for e in network_events if e["status"] >= 500]
        print(f"   Console errors: {len(console_errors)}")
        for err in console_errors:
            print(f"     Console error: {err}")
        print(f"   HTTP 500 responses: {len(http_500s)}")
        assert len(console_errors) == 0, f"Found console errors: {console_errors}"
        assert len(http_500s) == 0, f"Found 500 responses: {http_500s}"

        print("\nALL VERIFICATIONS PASSED WITH ZERO ERRORS!", flush=True)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_verification())

