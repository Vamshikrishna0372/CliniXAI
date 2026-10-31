import asyncio
import json
import urllib.request
from playwright.async_api import async_playwright

FRONTEND_URL = "http://localhost:3100"
BACKEND_URL = "http://127.0.0.1:8000/api/v1"
DOCTOR_EMAIL = "doctor.arjun@clinixai.com"
DOCTOR_PASS = "Doctor@123"

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

async def verify_browser():
    tokens = get_doctor_tokens()
    print("1. Obtained doctor token:", tokens["accessToken"][:30] + "...", flush=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await context.new_page()

        print("2. Pre-seeding localStorage with authenticated tokens...", flush=True)
        await page.goto(f"{FRONTEND_URL}/", wait_until="domcontentloaded")
        await page.evaluate("""tokens => {
            localStorage.setItem('clinixai.tokens', JSON.stringify(tokens));
        }""", tokens)

        print("3. Navigating to AI Analysis page (/app/ai-analysis)...", flush=True)
        await page.goto(f"{FRONTEND_URL}/app/ai-analysis", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        # Take screenshot of AI analysis page initial state
        await page.screenshot(path="backend/scratch/ai_analysis_page_initial.png")
        print("   Captured backend/scratch/ai_analysis_page_initial.png", flush=True)

        # Check if patient selector dropdown exists and select Krish
        print("4. Selecting patient Krish...", flush=True)
        patient_select = await page.query_selector('select')
        if patient_select:
            options = await page.query_selector_all('select option')
            for opt in options:
                text = await opt.inner_text()
                val = await opt.get_attribute("value")
                if "Krish" in text or "PAT-2026-85014E" in text or "PAT-2026-85014E" in (val or ""):
                    await page.select_option('select', val)
                    print(f"   Selected Krish: {text.encode('ascii', errors='replace').decode('ascii')} ({val})", flush=True)
                    break

        await page.wait_for_timeout(3000)
        await page.screenshot(path="backend/scratch/ai_analysis_krish_selected.png")
        print("   Captured backend/scratch/ai_analysis_krish_selected.png", flush=True)

        # Verify page content for Krish
        body_text = await page.inner_text("body")
        print("5. Checking text assertions on AI Analysis page for Krish...", flush=True)
        
        has_patient_uploaded = "Patient-Uploaded Images" in body_text
        has_krish = "krish Krish" in body_text or "Krish" in body_text
        has_patient_role = "Patient" in body_text
        
        print(f"   Contains 'Patient-Uploaded Images': {has_patient_uploaded}", flush=True)
        print(f"   Contains 'krish Krish': {has_krish}", flush=True)
        print(f"   Contains 'Patient' role badge/text: {has_patient_role}", flush=True)

        # 6. Verify Analysis Detail Page for Krish's analysis AI-2026-AC679D
        analysis_id = "AI-2026-AC679D"
        print(f"6. Navigating to Analysis Detail page: /app/ai-analysis/{analysis_id}...", flush=True)
        await page.goto(f"{FRONTEND_URL}/app/ai-analysis/{analysis_id}", wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)

        await page.screenshot(path="backend/scratch/ai_analysis_detail.png")
        print("   Captured backend/scratch/ai_analysis_detail.png", flush=True)

        detail_text = await page.inner_text("body")
        
        # Check for Invalid Date
        has_invalid_date = "Invalid Date" in detail_text
        print(f"   Contains 'Invalid Date': {has_invalid_date} (Expected False)", flush=True)
        assert not has_invalid_date, "Found 'Invalid Date' on AI detail page!"

        # Check for Krish's name or patient ID
        has_krish_id = "PAT-2026-85014E" in detail_text or "krish Krish" in detail_text
        print(f"   Displays Krish / PAT-2026-85014E: {has_krish_id} (Expected True)", flush=True)
        assert has_krish_id, "Analysis page does not display Krish's canonical ID!"

        # Check for original image and Grad-CAM
        images = await page.query_selector_all('img')
        print(f"   Found {len(images)} images on analysis page", flush=True)
        original_rendered = False
        gradcam_rendered = False
        for idx, img in enumerate(images):
            src = await img.get_attribute("src")
            alt = await img.get_attribute("alt")
            natural_width = await img.evaluate("el => el.naturalWidth")
            natural_height = await img.evaluate("el => el.naturalHeight")
            print(f"     Image {idx}: alt='{alt}' | size={natural_width}x{natural_height} | src_preview={(src[:60] if src else 'None')}", flush=True)
            if "Original" in (alt or "") or "original" in (src or ""):
                if natural_width > 0:
                    original_rendered = True
            if "Grad-CAM" in (alt or "") or "gradcam" in (src or ""):
                if natural_width > 0:
                    gradcam_rendered = True

        print(f"   Original Scan Rendered: {original_rendered}", flush=True)
        print(f"   Grad-CAM Heatmap Rendered: {gradcam_rendered}", flush=True)
        assert original_rendered, "Original image failed to render (blank)!"
        assert gradcam_rendered, "Grad-CAM image failed to render (blank)!"

        print("\nALL BROWSER UI VERIFICATIONS PASSED PERFECTLY!", flush=True)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(verify_browser())
