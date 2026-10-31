import asyncio
import json
import urllib.request
import os
from playwright.async_api import async_playwright

FRONTEND_URL = "http://localhost:3100"
BACKEND_URL = "http://127.0.0.1:8000/api/v1"
ANALYSIS_ID = "AI-2026-466F63"
DOCTOR_EMAIL = "doctor.arjun@clinixai.com"
DOCTOR_PASS = "Doctor@123"

network_log = []
console_log = []

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

async def main():
    tokens = get_doctor_tokens()
    print("Obtained doctor tokens:", tokens["accessToken"][:25] + "...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        page.on("console", lambda msg: console_log.append({"type": msg.type, "text": msg.text}))
        
        async def on_response(response):
            req = response.request
            url = req.url
            if any(k in url for k in ["ai-analyses", "medical-records", "documents", "image", "gradcam"]):
                try:
                    headers = response.headers
                    status = response.status
                    content_type = headers.get("content-type", "")
                    content_len = headers.get("content-length", "")
                    network_log.append({
                        "url": url,
                        "method": req.method,
                        "status": status,
                        "content_type": content_type,
                        "content_length": content_len,
                    })
                except Exception as e:
                    pass

        page.on("response", on_response)

        # Pre-seed localStorage with authenticated tokens
        await page.goto(f"{FRONTEND_URL}/", wait_until="domcontentloaded")
        await page.evaluate(f"""tokens => {{
            localStorage.setItem('clinixai.tokens', JSON.stringify(tokens));
        }}""", tokens)

        print(f"Navigating to {FRONTEND_URL}/app/ai-analysis/{ANALYSIS_ID}...")
        await page.goto(f"{FRONTEND_URL}/app/ai-analysis/{ANALYSIS_ID}", wait_until="domcontentloaded")
        await page.wait_for_timeout(6000)

        # Find all img tags
        imgs = await page.locator("img").all()
        img_info = []
        for idx, img in enumerate(imgs):
            src = await img.get_attribute("src")
            alt = await img.get_attribute("alt")
            visible = await img.is_visible()
            box = await img.bounding_box()
            img_info.append({
                "index": idx,
                "alt": alt,
                "src_preview": (src[:100] + "...") if src and len(src) > 100 else src,
                "is_blob": src.startswith("blob:") if src else False,
                "is_empty": not src,
                "visible": visible,
                "box": box
            })

        body_text = await page.locator("main").text_content()

        # Capture MedicalImageViewer specific elements
        viewer_html = ""
        viewer_elem = page.locator("div:has-text('Original Scan'), div:has-text('Explainability Heatmap')").first
        if await viewer_elem.is_visible():
            viewer_html = await viewer_elem.inner_html()

        results = {
            "analysis_id": ANALYSIS_ID,
            "url": page.url,
            "title": await page.title(),
            "rendered_images": img_info,
            "network_requests": network_log,
            "console_logs": console_log,
            "viewer_html_snippet": viewer_html[:1500] if viewer_html else None,
            "body_snippet": body_text[:2000] if body_text else None,
        }

        with open("backend/scratch/browser_audit_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        print("BROWSER_AUDIT_SUCCESS")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
