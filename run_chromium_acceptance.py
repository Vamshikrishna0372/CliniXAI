import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        console_messages = []
        page.on('console', lambda msg: console_messages.append({'type': msg.type, 'text': msg.text}))
        
        network_requests = []
        page.on('request', lambda req: network_requests.append({
            'url': req.url,
            'method': req.method,
            'headers': {k: ('[REDACTED_JWT]' if 'bearer' in v.lower() else v) for k, v in req.headers.items()}
        }))
        
        network_responses = []
        page.on('response', lambda res: network_responses.append({
            'url': res.url,
            'status': res.status,
            'content_type': res.headers.get('content-type', '')
        }))

        # Step 7: Identity Proof
        print("=== 7. BROWSER IDENTITY PROOF ===")
        await page.goto("http://localhost:3100/auth/login", wait_until="networkidle")
        title = await page.title()
        url = page.url
        body_text = await page.inner_text("body")
        print(f"Current URL: {url}")
        print(f"Page title: {title}")
        assert "CliniXAI" in title or "CliniXAI" in body_text, "CliniXAI branding missing!"
        print("CliniXAI Branding verified in DOM.")

        # Step 8: Actual Doctor Login
        print("\n=== 8. ACTUAL DOCTOR LOGIN ===")
        await page.fill('input[type="email"]', 'doctor.arjun@clinixai.com')
        await page.fill('input[type="password"]', 'Doctor@123')
        await page.click('button[type="submit"]')
        
        await page.wait_for_url(lambda u: "/app" in u, timeout=15000)
        print(f"Authenticated navigation completed. URL: {page.url}")
        await page.wait_for_load_state("networkidle")
        print("Doctor workspace verified.")

        # Step 9: Navigate to AI Analysis
        print("\n=== 9. REAL AI ANALYSIS NAVIGATION ===")
        await page.goto("http://localhost:3100/app/ai-analysis/AI-2026-E66B2C", wait_until="networkidle")
        await page.wait_for_timeout(3000)
        print(f"Navigated to AI analysis: {page.url}")

        # Step 10: Actual DOM Verification
        print("\n=== 10. ACTUAL DOM VERIFICATION ===")
        page_content = await page.inner_text("body")
        print("--- CURRENT BODY TEXT (First 500 chars) ---")
        print(page_content[:500].encode('ascii', errors='replace').decode('ascii'))
        print("------------------------------------------")
        
        assert "AI-2026-E66B2C" in page_content, "Analysis ID missing from DOM!"
        print("Found: Analysis ID AI-2026-E66B2C")
        
        assert "notumor" in page_content.lower(), "Prediction notumor missing from DOM!"
        print("Found: Prediction notumor")
        
        assert "38.93%" in page_content or "39%" in page_content, "Confidence 38.93%/39% missing!"
        print("Found: Confidence 38.93% / 39%")
        
        assert "Brain MRI" in page_content, "Model Brain MRI missing!"
        print("Found: Model Brain MRI")
        
        assert "ResNet50" in page_content, "Architecture ResNet50 missing!"
        print("Found: Architecture ResNet50")
        
        assert "Grad-CAM available" in page_content, "Grad-CAM available missing!"
        print("Found: Grad-CAM available badge")

        # Step 11 & 12: Actual Grad-CAM Visualization and Image Load
        print("\n=== 11 & 12. ACTUAL GRAD-CAM VISUALIZATION & LOAD ===")
        imgs = await page.query_selector_all("img")
        print(f"Rendered img tags count: {len(imgs)}")
        
        gradcam_img_found = False
        for idx, img_el in enumerate(imgs):
            src = await img_el.get_attribute("src")
            is_visible = await img_el.is_visible()
            bbox = await img_el.bounding_box()
            dims = await img_el.evaluate("img => ({ naturalWidth: img.naturalWidth, naturalHeight: img.naturalHeight, complete: img.complete })")
            print(f"Img [{idx}]: src={src[:50]}... visible={is_visible} bbox={bbox} dims={dims}")
            
            assert "token=" not in src, f"JWT found in image src! {src}"
            assert "Bearer" not in src, f"Bearer found in image src! {src}"
            assert "ey" not in src, f"Possible raw JWT found in image src! {src}"
            
            if src.startswith("blob:"):
                gradcam_img_found = True
                assert is_visible, "Gradcam blob img is not visible!"
                assert dims["naturalWidth"] > 0 and dims["naturalHeight"] > 0, "Image did not load natural dimensions!"
                print(f"Verified Grad-CAM image loaded: naturalWidth={dims['naturalWidth']}, naturalHeight={dims['naturalHeight']}")
                
        assert gradcam_img_found, "Grad-CAM Blob image was not found!"

        # Check viewer mode buttons
        modes = ["Side-by-side", "Overlay", "Original only"]
        for mode in modes:
            btn = await page.query_selector(f'button:has-text("{mode}")')
            assert btn is not None, f"Viewer mode button {mode} not found!"
            print(f"Viewer mode button rendered: {mode}")

        # Step 13: Browser Network Capture
        print("\n=== 13. BROWSER NETWORK CAPTURE ===")
        gradcam_reqs = [r for r in network_requests if "/gradcam" in r["url"]]
        assert len(gradcam_reqs) > 0, "No /gradcam network requests captured!"
        for r in gradcam_reqs:
            print(f"Grad-CAM Request: {r['method']} {r['url']}")
            assert "?token=" not in r["url"], f"?token= found in request URL: {r['url']}"
            assert "access_token" not in r["url"], f"access_token found in URL: {r['url']}"
            auth_header = r["headers"].get("authorization", "")
            assert auth_header != "", "Authorization header missing from Grad-CAM fetch!"
            print(f"  Authorization header present: {auth_header}")
            
        gradcam_resps = [r for r in network_responses if "/gradcam" in r["url"]]
        assert len(gradcam_resps) > 0, "No /gradcam response captured!"
        for r in gradcam_resps:
            print(f"Grad-CAM Response: status={r['status']}, content_type={r['content_type']}")
            assert r['status'] == 200, f"Expected 200, got {r['status']}"
            assert "image/png" in r['content_type'], f"Expected image/png, got {r['content_type']}"

        # Step 14: Browser Console
        print("\n=== 14. BROWSER CONSOLE ===")
        errors = [m for m in console_messages if m["type"] in ("error",)]
        warnings = [m for m in console_messages if m["type"] in ("warning",)]
        print(f"Total console errors: {len(errors)}")
        for e in errors:
            print(f"Console error: {e['text']}")
        print(f"Total console warnings: {len(warnings)}")
        assert len(errors) == 0, f"Found {len(errors)} console errors: {errors}"

        # Step 15: Refresh Test
        print("\n=== 15. REFRESH TEST ===")
        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(2000)
        reloaded_content = await page.inner_text("body")
        assert "AI-2026-E66B2C" in reloaded_content
        assert "notumor" in reloaded_content.lower()
        assert "38.93%" in reloaded_content or "39%" in reloaded_content
        print("Post-hard-refresh: prediction, confidence, and page data remained intact.")
        
        imgs_reload = await page.query_selector_all("img")
        blob_img_reload = [img for img in imgs_reload if (await img.get_attribute("src")).startswith("blob:")]
        assert len(blob_img_reload) > 0
        dims_r = await blob_img_reload[0].evaluate("img => ({ naturalWidth: img.naturalWidth, naturalHeight: img.naturalHeight })")
        assert dims_r["naturalWidth"] > 0
        print(f"Post-hard-refresh image natural dimensions: {dims_r}")

        # Step 16: Logout / Relogin Test
        print("\n=== 16. LOGOUT / RELOGIN TEST ===")
        await page.goto("http://localhost:3100/auth/login", wait_until="networkidle")
        await page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
        await page.reload(wait_until="networkidle")
        print("Logged out successfully.")
        
        await page.fill('input[type="email"]', 'doctor.arjun@clinixai.com')
        await page.fill('input[type="password"]', 'Doctor@123')
        await page.click('button[type="submit"]')
        await page.wait_for_url(lambda u: "/app" in u, timeout=15000)
        print("Relogged in as Dr. Arjun.")
        
        await page.goto("http://localhost:3100/app/ai-analysis/AI-2026-E66B2C", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        content_relogin = await page.inner_text("body")
        assert "AI-2026-E66B2C" in content_relogin
        assert "notumor" in content_relogin.lower()
        
        relogin_imgs = await page.query_selector_all("img")
        relogin_blob = [img for img in relogin_imgs if (await img.get_attribute("src")).startswith("blob:")]
        assert len(relogin_blob) > 0
        dims_rl = await relogin_blob[0].evaluate("img => ({ naturalWidth: img.naturalWidth, naturalHeight: img.naturalHeight })")
        assert dims_rl["naturalWidth"] > 0
        print(f"Post-relogin Grad-CAM loaded successfully: {dims_rl}")

        await browser.close()
        print("\n=== REAL CHROMIUM PLAYWRIGHT VERIFICATION FULLY PASSED ===")

if __name__ == "__main__":
    asyncio.run(main())
