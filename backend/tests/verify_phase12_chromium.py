import asyncio
import sys

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

from playwright.async_api import async_playwright

async def run():
    print("=== STARTING PHASE 12 PLAYWRIGHT CHROMIUM E2E VERIFICATION ===")
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
                })
        
        def on_console(msg):
            console_messages.append({"type": msg.type, "text": msg.text})
            print(f"[CONSOLE {msg.type.upper()}] {msg.text}")
            
        def on_request_failed(req):
            print(f"[REQ FAILED] {req.method} {req.url} -> {req.failure}")
            
        def on_response(res):
            if "auth" in res.url or "ai-analyses" in res.url or "gradcam" in res.url:
                print(f"[RES {res.status}] {res.url}")
            
        page.on("request", on_request)
        page.on("requestfailed", on_request_failed)
        page.on("response", on_response)
        page.on("console", on_console)
        
        # 1. Login to CliniXAI on authoritative port 3100
        print("1. Navigating to http://localhost:3100/auth/login")
        await page.goto("http://localhost:3100/auth/login", wait_until="networkidle")
        title = await page.title()
        print(f"Page title: {title}")
        assert "CliniXAI" in title or "Sign in" in title
        
        print("2. Logging in as Doctor Arjun...")
        demo_btn = page.locator('button:has-text("Arjun (doctor)")')
        if await demo_btn.count() > 0:
            await demo_btn.click()
            print("[OK] Clicked demo account button")
        else:
            await page.fill('input#email', "doctor.arjun@clinixai.com")
            await page.fill('input#password', "Doctor@123")
            
        submit_btn = page.locator('button[type="submit"]:has-text("Sign in")')
        await submit_btn.click()
        print("[OK] Submitted login credentials")
        
        await page.wait_for_url("**/app**", timeout=15000)
        print(f"[OK] Authenticated navigation to: {page.url}")
        
        # 3. Navigate to AI Analysis main page (shows recent analyses)
        print("3. Navigating to http://localhost:3100/app/ai-analysis")
        await page.goto("http://localhost:3100/app/ai-analysis", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        
        # Verify AI Analysis page elements
        page_content = await page.content()
        assert "AI clinical decision support" in page_content
        print("[OK] Verified AI Analysis clinical decision support page")
        
        # 4. Navigate to AI Reports History Page
        print("4. Navigating to http://localhost:3100/app/ai-reports")
        await page.goto("http://localhost:3100/app/ai-reports", wait_until="networkidle")
        await page.wait_for_timeout(3000)
        reports_content = await page.content()
        assert "AI Reports" in reports_content
        print("[OK] Verified AI Reports history page loaded from server")
        
        # 5. Open AI-2026-E66B2C detail page directly
        print("5. Navigating to detail page http://localhost:3100/app/ai-analysis/AI-2026-E66B2C")
        await page.goto("http://localhost:3100/app/ai-analysis/AI-2026-E66B2C", wait_until="networkidle")
        await page.wait_for_timeout(3000)
        
        dom = await page.content()
        assert "AI-2026-E66B2C" in dom, "Analysis ID AI-2026-E66B2C not found in DOM"
        assert "notumor" in dom, "Predicted class 'notumor' not found in DOM"
        assert "38.93%" in dom or "39%" in dom or "0.3893" in dom or "38.9%" in dom, "Confidence not found in DOM"
        print("[OK] Verified persisted analysis details in DOM")
        
        # 6. Verify Grad-CAM Blob Rendering
        print("6. Verifying Grad-CAM Image Element and Blob decoding...")
        img_locator = page.locator('img[alt*="Grad-CAM"]')
        await img_locator.first.wait_for(state="visible", timeout=10000)
        img_src = await img_locator.first.get_attribute("src")
        print(f"Grad-CAM img src: {img_src}")
        assert img_src.startswith("blob:"), f"Expected blob URL, got {img_src}"
        assert "token=" not in img_src, "CRITICAL SECURITY BREACH: JWT in image src URL!"
        
        natural_w = await img_locator.first.evaluate("el => el.naturalWidth")
        natural_h = await img_locator.first.evaluate("el => el.naturalHeight")
        print(f"Image natural dimensions: {natural_w}x{natural_h}")
        assert natural_w > 0 and natural_h > 0, "Image failed to decode (natural dimensions == 0)"
        print("[OK] Grad-CAM image element is visible and validly decoded")
        
        # 7. Reload page to verify persistence across hard refresh
        print("7. Testing page reload persistence...")
        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(3000)
        
        reloaded_img = page.locator('img[alt*="Grad-CAM"]')
        reloaded_src = await reloaded_img.first.get_attribute("src")
        print(f"Reloaded Grad-CAM img src: {reloaded_src}")
        assert reloaded_src.startswith("blob:")
        assert "token=" not in reloaded_src
        
        r_w = await reloaded_img.first.evaluate("el => el.naturalWidth")
        r_h = await reloaded_img.first.evaluate("el => el.naturalHeight")
        assert r_w > 0 and r_h > 0
        print("[OK] Analysis and Grad-CAM image successfully persisted after refresh")
        
        # 8. Check console error messages
        print("8. Checking console error messages...")
        errors = [m for m in console_messages if m["type"] == "error"]
        print(f"Console errors: {len(errors)}")
        for err in errors:
            print(f"  Error: {err['text']}")
        assert len(errors) == 0, f"Found unexpected console errors: {errors}"
        print("[OK] Zero console errors detected")
        
        await browser.close()
        print("=== ALL PHASE 12 CHROMIUM E2E VERIFICATIONS PASSED ===")

if __name__ == "__main__":
    asyncio.run(run())
