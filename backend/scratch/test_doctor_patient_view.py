import asyncio
import json
from playwright.async_api import async_playwright

async def run():
    print("Starting doctor patient view test...", flush=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        console_logs = []
        network_logs = []
        page.on("console", lambda m: console_logs.append(f"[{m.type}] {m.text}"))
        page.on("response", lambda r: network_logs.append(f"{r.request.method} {r.url} -> {r.status}"))
        
        # 1. Login via backend API and inject token into localStorage
        print("1. Authenticating as Dr. Arjun Rao...", flush=True)
        res = await page.request.post(
            "http://localhost:8000/api/v1/auth/login",
            data=json.dumps({"email": "doctor.arjun@clinixai.com", "password": "Doctor@123"}),
            headers={"Content-Type": "application/json"}
        )
        auth_data = await res.json()
        tokens = {"accessToken": auth_data["access_token"], "refreshToken": auth_data["refresh_token"]}
        
        # Navigate to homepage to set localStorage
        await page.goto("http://localhost:3100", wait_until="domcontentloaded")
        await page.evaluate("(tokens) => localStorage.setItem('clinixai.tokens', JSON.stringify(tokens))", tokens)
        print("Tokens injected into localStorage.", flush=True)
        
        # 2. Open Patient PAT-2026-85014E directly
        target_url = "http://localhost:3100/app/patients/PAT-2026-85014E"
        print(f"2. Navigating to {target_url}...", flush=True)
        await page.goto(target_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        print("URL:", page.url, flush=True)
        print("Title:", await page.title(), flush=True)
        
        # Check if error message is displayed
        err_state = page.locator("text='Clinical Access Restricted'")
        if await err_state.count() > 0:
            print("ERROR: Clinical Access Restricted shown on page!", flush=True)
        not_found = page.locator("text='Patient Record Not Found'")
        if await not_found.count() > 0:
            print("ERROR: Patient Record Not Found shown on page!", flush=True)
            
        # 3. Click on Documents & Imaging tab
        doc_tab = page.locator("button[role='tab']:has-text('Documents')")
        if await doc_tab.count() > 0:
            print("Found Documents tab! Clicking...", flush=True)
            await doc_tab.click()
            await page.wait_for_timeout(2000)
        else:
            print("Documents tab button not found!", flush=True)
            
        # 4. Check for document cards under All
        doc_cards = page.locator("[data-testid^='doc-card-']")
        count = await doc_cards.count()
        print(f"Document cards found on page under 'all': {count}", flush=True)
        for i in range(count):
            card = doc_cards.nth(i)
            testid = await card.get_attribute("data-testid")
            text = await card.inner_text()
            print(f"Card {i} ({testid}):\n{text}\n", flush=True)
            
        # 5. Check filter buttons (All, MRI, X-Ray, etc.)
        mri_btn = page.locator("button:has-text('mri')")
        if await mri_btn.count() > 0:
            print("Clicking 'mri' category filter...", flush=True)
            await mri_btn.click()
            await page.wait_for_timeout(1000)
            mri_count = await page.locator("[data-testid^='doc-card-']").count()
            print(f"Document cards under 'mri' filter: {mri_count}", flush=True)
            empty_state = page.locator("text='No Documents or Imaging Found'")
            if await empty_state.count() > 0:
                print("EMPTY STATE SHOWN UNDER MRI FILTER!", flush=True)
                
        # 6. Check console errors and network requests
        print("\n--- Console Errors ---", flush=True)
        for log in console_logs:
            if "error" in log.lower() or "fail" in log.lower():
                print(log, flush=True)
                
        print("\n--- Relevant Network Responses ---", flush=True)
        for net in network_logs:
            if "8000" in net:
                print(net, flush=True)
                
        await page.screenshot(path="backend/scratch/doctor_patient_workspace.png")
        print("Screenshot saved to backend/scratch/doctor_patient_workspace.png", flush=True)
        
        await browser.close()
        print("Test complete.", flush=True)

if __name__ == "__main__":
    asyncio.run(run())
