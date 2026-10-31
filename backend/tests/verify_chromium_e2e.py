import asyncio
import sys

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

from playwright.async_api import async_playwright

async def run():
    print("=== STARTING PLAYWRIGHT CHROMIUM E2E VERIFICATION ===")
    network_requests = []
    console_messages = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()
        
        # Intercept network & console
        def on_request(req):
            if "gradcam" in req.url or "ai-analyses" in req.url or "auth" in req.url:
                network_requests.append({
                    "url": req.url,
                    "method": req.method,
                    "headers": req.headers
                })
        
        def on_console(msg):
            console_messages.append({"type": msg.type, "text": msg.text})
            print(f"[CONSOLE {msg.type.upper()}] {msg.text}")
            
        def on_request_failed(req):
            print(f"[REQ FAILED] {req.method} {req.url} -> {req.failure}")
            
        def on_response(res):
            if "auth" in res.url or "gradcam" in res.url:
                print(f"[RES {res.status}] {res.url}")
            
        page.on("request", on_request)
        page.on("requestfailed", on_request_failed)
        page.on("response", on_response)
        page.on("console", on_console)
        
        # 1. Login to CliniXAI
        print("1. Navigating to http://localhost:3100/auth/login")
        await page.goto("http://localhost:3100/auth/login", wait_until="networkidle")
        title = await page.title()
        print(f"Page title: {title}")
        assert "CliniXAI" in title or "Sign in" in title
        
        print("2. Clicking Arjun (doctor) demo button...")
        demo_btn = page.locator('button:has-text("Arjun (doctor)")')
        if await demo_btn.count() > 0:
            await demo_btn.click()
            print("[OK] Clicked demo account button")
        else:
            await page.fill('input#email', "doctor.arjun@clinixai.com")
            await page.fill('input#password', "Doctor@123")
            
        print("3. Clicking Sign In...")
        await page.click('button[type="submit"]')
        
        print("4. Waiting for 3 seconds...")
        await page.wait_for_timeout(3000)
        print(f"Current URL after submit: {page.url}")
        
        # Check any error text on screen
        error_text = await page.locator("p.text-error").all_inner_texts()
        if error_text:
            print(f"Found error text on login page: {error_text}")
            
        if "/app" not in page.url:
            print("Did not auto-navigate, navigating directly to /app/ai-analysis/AI-2026-E66B2C...")
        
        # 2. Navigate to AI Analysis
        target_url = "http://localhost:3100/app/ai-analysis/AI-2026-E66B2C"
        print(f"5. Navigating to {target_url}...")
        await page.goto(target_url, wait_until="networkidle")
        await page.wait_for_timeout(3000)
        
        current_url = page.url
        print(f"Current URL: {current_url}")
        assert "AI-2026-E66B2C" in current_url
        
        # 3. Check DOM content
        body_text = await page.locator("body").inner_text()
        print(f"Body text preview (first 500 chars):\n{body_text[:500]}")
        print("--- DOM CHECKS ---")
        assert "AI-2026-E66B2C" in body_text, f"Analysis ID not in DOM. Full body text:\n{body_text}"
        print("[OK] Analysis ID found in DOM")
        
        assert "notumor" in body_text, "Prediction not found in DOM"
        print("[OK] Prediction 'notumor' found in DOM")
        
        assert "38.93%" in body_text or "39%" in body_text or "0.3893" in body_text or "38.9%" in body_text, "Confidence percentage not found"
        print("[OK] Confidence percentage found in DOM")
        
        assert "Grad-CAM" in body_text, "'Grad-CAM' not found in DOM"
        print("[OK] 'Grad-CAM' label found in DOM")
        
        # 4. Check Grad-CAM image element
        print("--- IMAGE ATTRIBUTE CHECKS ---")
        gradcam_img = page.locator('img[alt*="Grad-CAM"]')
        count = await gradcam_img.count()
        print(f"Found {count} Grad-CAM img element(s)")
        assert count > 0, "No Grad-CAM img element found"
        
        src = await gradcam_img.first.get_attribute("src")
        print(f"Grad-CAM img src: {src}")
        
        assert src.startswith("blob:"), f"Expected blob: URL, got: {src}"
        print("[OK] Grad-CAM img src starts with 'blob:'")
        
        assert "token=" not in src, f"token found in src: {src}"
        print("[OK] Grad-CAM img src contains NO token query parameter")
        
        natural_w = await gradcam_img.first.evaluate("el => el.naturalWidth")
        natural_h = await gradcam_img.first.evaluate("el => el.naturalHeight")
        print(f"Image natural dimensions: {natural_w}x{natural_h}")
        assert natural_w > 0 and natural_h > 0, f"Image failed to render (dimensions: {natural_w}x{natural_h})"
        print(f"[OK] Image rendered properly ({natural_w}x{natural_h})")
        
        # 5. Check Network Requests for Grad-CAM
        print("--- NETWORK REQUEST CHECKS ---")
        gradcam_requests = [r for r in network_requests if "gradcam" in r["url"]]
        print(f"Total Grad-CAM requests captured: {len(gradcam_requests)}")
        assert len(gradcam_requests) > 0, "No network request for Grad-CAM was captured"
        
        for req in gradcam_requests:
            print(f"Request URL: {req['url']}")
            assert "token=" not in req["url"], f"Query token in request URL: {req['url']}"
            print("[OK] Request URL has no query token")
            auth_header = req["headers"].get("authorization", "")
            assert auth_header.startswith("Bearer "), f"Missing or invalid Authorization header: {auth_header}"
            print("[OK] Request sent with Authorization: Bearer <JWT> header")
            
        # 6. Test viewer modes (Side-by-side / Overlay)
        print("--- VIEWER MODE INTERACTION ---")
        side_by_side_btn = page.locator('button:has-text("Side-by-side")')
        if await side_by_side_btn.count() > 0:
            await side_by_side_btn.click()
            await page.wait_for_timeout(1000)
            print("[OK] Clicked 'Side-by-side' button successfully")
            
        overlay_btn = page.locator('button:has-text("Overlay")')
        if await overlay_btn.count() > 0:
            await overlay_btn.click()
            await page.wait_for_timeout(1000)
            print("[OK] Clicked 'Overlay' button successfully")
            
        # 7. Reload page to verify persistence
        print("--- RELOAD PERSISTENCE CHECK ---")
        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(3000)
        
        reloaded_img = page.locator('img[alt*="Grad-CAM"]')
        reloaded_src = await reloaded_img.first.get_attribute("src")
        print(f"Reloaded Grad-CAM img src: {reloaded_src}")
        assert reloaded_src.startswith("blob:"), f"Expected blob URL after reload, got {reloaded_src}"
        assert "token=" not in reloaded_src
        
        r_w = await reloaded_img.first.evaluate("el => el.naturalWidth")
        r_h = await reloaded_img.first.evaluate("el => el.naturalHeight")
        print(f"Reloaded Image natural dimensions: {r_w}x{r_h}")
        assert r_w > 0 and r_h > 0
        print("[OK] Grad-CAM image rendered after page reload")
        
        # 8. Check console error messages
        print("--- CONSOLE CHECK ---")
        errors = [m for m in console_messages if m["type"] == "error"]
        print(f"Console errors: {len(errors)}")
        for err in errors:
            print(f"  Error: {err['text']}")
        assert len(errors) == 0, f"Found console errors: {errors}"
        print("[OK] Zero console errors detected")
        
        await browser.close()
        print("=== ALL PLAYWRIGHT CHROMIUM E2E VERIFICATIONS PASSED ===")

if __name__ == "__main__":
    asyncio.run(run())
