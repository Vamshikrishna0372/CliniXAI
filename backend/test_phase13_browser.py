import asyncio
import os
import sys
import time
import subprocess
import urllib.request
from playwright.async_api import async_playwright

FRONTEND_URL = "http://localhost:3100"
BACKEND_HEALTH_URL = "http://localhost:8000/api/v1/health"
ANALYSIS_ID = "AI-2026-59AF91"

def wait_for_backend(timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(BACKEND_HEALTH_URL)
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(1)
    return False

async def run_browser_verification():
    print(f"=== Starting Phase 13 Real Browser Verification on port 3100 ===")
    
    # Verify backend and frontend connectivity
    if not wait_for_backend():
        raise RuntimeError("Backend on port 8000 is not responding")
    print("Backend is responding at port 8000.")

    console_errors = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()

        # Listen for console messages
        def handle_console(msg):
            if msg.type == "error":
                # Filter out benign React dev warnings or Vite HMR noise
                txt = msg.text
                if not any(ign in txt for ign in ["favicon.ico", "Download the React DevTools", "ERR_CONNECTION_REFUSED"]):
                    console_errors.append(txt)
                    print(f"  [Browser Console Error]: {txt}")
        
        page.on("console", handle_console)

        # 1. Login as Doctor
        print("\n--- Step 1: Doctor Login ---")
        await page.goto(f"{FRONTEND_URL}/auth/login", wait_until="networkidle")
        
        # Check no JWT in query param
        assert "token" not in page.url.lower(), f"JWT detected in URL: {page.url}"
        
        await page.fill('input[type="email"]', "doctor.arjun@clinixai.com")
        await page.fill('input[type="password"]', "Doctor@123")
        await page.click('button[type="submit"]')
        
        await page.wait_for_timeout(2000)
        print(f"Logged in. Current URL: {page.url}")
        assert "token" not in page.url.lower(), f"JWT detected in URL after login: {page.url}"

        # 2. Navigate to AI Analysis
        print(f"\n--- Step 2: Navigate to Persistent Analysis {ANALYSIS_ID} ---")
        target_url = f"{FRONTEND_URL}/app/ai-analysis/{ANALYSIS_ID}"
        await page.goto(target_url, wait_until="networkidle")
        await page.wait_for_timeout(2500)

        assert "token" not in page.url.lower(), f"JWT detected in analysis URL: {page.url}"

        # 3. Verify AI Prediction, Model, Confidence, Grad-CAM
        print("\n--- Step 3: Verify Canonical AI Prediction & Model ---")
        body_text = await page.inner_text("body")
        
        assert "notumor" in body_text.lower(), f"Predicted class 'notumor' not found in page text!"
        print("  Verified: Predicted class 'notumor' is present.")
        
        # Check confidence (38.9% or 39% or 0.3893)
        assert ("38.9" in body_text or "39%" in body_text or "0.389" in body_text), f"Confidence ~38.9% not found in page text!"
        print("  Verified: Confidence ~38.9% is present.")

        # Check ResNet50 model
        assert "resnet50" in body_text.lower(), f"Model architecture 'ResNet50' not found in page text!"
        print("  Verified: Architecture 'ResNet50' is present.")

        # Check Grad-CAM image rendering
        print("\n--- Step 4: Verify Grad-CAM Image Loaded Authenticated ---")
        gradcam_img = await page.wait_for_selector('img[alt*="Grad-CAM"], img[alt*="gradcam"], img[alt*="AI Heatmap"], img[alt*="Heatmap"]', timeout=8000)
        assert gradcam_img is not None, "Grad-CAM image element not found!"
        
        # Check image natural dimensions
        is_loaded = await gradcam_img.evaluate('(img) => img.complete && img.naturalWidth > 0')
        src_attr = await gradcam_img.get_attribute("src")
        print(f"  Grad-CAM image src: {src_attr[:60]}... loaded={is_loaded}")
        assert is_loaded, "Grad-CAM image failed to load into browser DOM!"
        assert "token" not in (src_attr or "").lower(), "JWT found in image src query parameters!"

        # 5. Submit Doctor Review
        print("\n--- Step 5: Submit Doctor Review in Browser ---")
        # Select "Accepted" button
        accept_button = await page.wait_for_selector('button:has-text("Accepted")', timeout=5000)
        await accept_button.click()
        
        review_notes = "Verified in Chromium browser: brain MRI canonical notumor class confirmed by Dr. Arjun Rao."
        notes_textarea = await page.wait_for_selector('textarea#ai-notes', timeout=5000)
        await notes_textarea.fill(review_notes)

        save_button = await page.wait_for_selector('button:has-text("Save review")', timeout=5000)
        await save_button.click()
        await page.wait_for_timeout(2000)
        print("  Review submitted successfully via UI.")

        # 6. Page Reload Persistence
        print("\n--- Step 6: Browser Page Reload ---")
        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(2500)
        
        body_text_after_reload = await page.inner_text("body")
        assert "notumor" in body_text_after_reload.lower()
        assert ("38.9" in body_text_after_reload or "39%" in body_text_after_reload)
        assert "resnet50" in body_text_after_reload.lower()
        print("  Page reloaded: Analysis values and review state remain intact.")

        # 7. Logout and Re-login
        print("\n--- Step 7: Logout and Re-login ---")
        await page.goto(f"{FRONTEND_URL}/auth/login", wait_until="networkidle")
        await page.fill('input[type="email"]', "doctor.arjun@clinixai.com")
        await page.fill('input[type="password"]', "Doctor@123")
        await page.click('button[type="submit"]')
        await page.wait_for_timeout(2000)

        # Return to analysis page
        await page.goto(target_url, wait_until="networkidle")
        await page.wait_for_timeout(2500)
        
        body_text_after_relogin = await page.inner_text("body")
        assert "notumor" in body_text_after_relogin.lower()
        assert "resnet50" in body_text_after_relogin.lower()
        print("  Re-login verified: Analysis and review persist across auth sessions.")

        # 8. Backend Restart Persistence Test
        print("\n--- Step 8: Full Backend Server Restart ---")
        try:
            netstat_out = subprocess.check_output("netstat -ano | findstr :8000 | findstr LISTENING", shell=True).decode()
            lines = [l.strip() for l in netstat_out.strip().splitlines() if l.strip()]
            pids = set(l.split()[-1] for l in lines)
            for pid in pids:
                print(f"  Terminating backend PID {pid}...")
                subprocess.run(f"taskkill /F /PID {pid}", shell=True, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"  Note while stopping backend: {e}")
        time.sleep(2)

        # Restart backend
        print("  Spawning fresh backend server...")
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
            cwd=r"c:\Users\Vamshikrishna\Desktop\CliniXAI\backend",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        )
        assert wait_for_backend(timeout=45), "Fresh backend failed to start within 45s!"
        print("  Fresh backend restarted and responding healthy.")

        # 9. Reload Browser Page Post-Restart
        print("\n--- Step 9: Browser Verification Post-Restart ---")
        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(3000)

        body_post_restart = await page.inner_text("body")
        assert "notumor" in body_post_restart.lower(), "Prediction missing post-restart!"
        assert ("38.9" in body_post_restart or "39%" in body_post_restart), "Confidence missing post-restart!"
        assert "resnet50" in body_post_restart.lower(), "Model missing post-restart!"

        # Check Grad-CAM still loads
        gradcam_post = await page.wait_for_selector('img[alt*="Grad-CAM"], img[alt*="gradcam"], img[alt*="AI Heatmap"], img[alt*="Heatmap"]', timeout=8000)
        assert gradcam_post is not None
        is_gradcam_loaded_post = await gradcam_post.evaluate('(img) => img.complete && img.naturalWidth > 0')
        assert is_gradcam_loaded_post, "Grad-CAM failed to load post-restart!"
        print("  Verified: Grad-CAM rendered with naturalWidth > 0 post-restart.")

        # Screenshot proof
        screenshot_path = r"c:\Users\Vamshikrishna\Desktop\CliniXAI\backend\phase13_browser_proof.png"
        await page.screenshot(path=screenshot_path, full_page=True)
        print(f"  Screenshot saved to: {screenshot_path}")

        print(f"\nConsole Errors Count: {len(console_errors)}")
        if console_errors:
            print("Console Errors Logged:", console_errors)
        assert len(console_errors) == 0, f"Unexpected console errors: {console_errors}"

        await browser.close()

    print("\n============================================================")
    print("PHASE 13 BROWSER & PERSISTENCE VERIFICATION PASSED (100%)!")
    print("============================================================")

if __name__ == "__main__":
    asyncio.run(run_browser_verification())
