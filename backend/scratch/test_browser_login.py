import asyncio
import os
import sys
from playwright.async_api import async_playwright

async def run():
    print("Starting Playwright...", flush=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        console_logs = []
        network_logs = []
        network_errors = []
        
        page.on('console', lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        page.on('requestfailed', lambda req: network_errors.append(f"FAILED: {req.method} {req.url} -> {req.failure}"))
        page.on('response', lambda res: network_logs.append(f"{res.request.method} {res.url} -> {res.status}"))
        
        print("1. Navigating to http://localhost:3100/auth/login...", flush=True)
        await page.goto("http://localhost:3100/auth/login", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        
        # Test in-browser fetch directly to verify browser network connectivity
        print("2. Testing in-browser fetch to backend /api/v1/health...", flush=True)
        health_test = await page.evaluate("""async () => {
            try {
                const res = await fetch("http://localhost:8000/api/v1/health");
                return { status: res.status, data: await res.json() };
            } catch (e) {
                return { error: e.message };
            }
        }""")
        print("In-browser fetch /health result:", health_test, flush=True)
        
        print("3. Testing in-browser fetch to backend /api/v1/auth/me (unauthenticated)...", flush=True)
        auth_me_test = await page.evaluate("""async () => {
            try {
                const res = await fetch("http://localhost:8000/api/v1/auth/me");
                return { status: res.status, data: await res.json() };
            } catch (e) {
                return { error: e.message };
            }
        }""")
        print("In-browser fetch /auth/me result:", auth_me_test, flush=True)
        
        print("4. Testing in-browser fetch to backend /api/v1/auth/register...", flush=True)
        register_test = await page.evaluate("""async () => {
            try {
                const res = await fetch("http://localhost:8000/api/v1/auth/register", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({})
                });
                return { status: res.status, data: await res.json() };
            } catch (e) {
                return { error: e.message };
            }
        }""")
        print("In-browser fetch /auth/register result:", register_test, flush=True)
        
        print("5. Filling credentials & logging in via UI...", flush=True)
        # Click the demo admin button
        demo_btn = page.locator("button:has-text('Primary (admin)')")
        if await demo_btn.count() > 0:
            await demo_btn.click()
            print("Clicked demo button!", flush=True)
        else:
            await page.fill("#email", "admin@clinixai.com")
            await page.fill("#password", "admin123")
            
        await page.wait_for_timeout(500)
        
        submit_btn = page.locator("button[type='submit']")
        print(f"Submit button disabled: {await submit_btn.is_disabled()}", flush=True)
        await submit_btn.click()
        
        print("Waiting 5 seconds for login to process...", flush=True)
        await page.wait_for_timeout(5000)
        
        print("Current URL:", page.url, flush=True)
        print("Current Title:", await page.title(), flush=True)
        
        tokens = await page.evaluate("() => localStorage.getItem('clinixai.tokens')")
        print("Tokens in localStorage:", tokens is not None, flush=True)
        if tokens:
            print("Token preview:", tokens[:80] + "...", flush=True)
            
        print("\n--- Network Errors ---", flush=True)
        if not network_errors:
            print("None (0 network errors)", flush=True)
        for err in network_errors:
            print(err, flush=True)
            
        print("\n--- Console Errors/Warnings ---", flush=True)
        errors = [msg for msg in console_logs if any(k in msg.lower() for k in ["error", "refused"])]
        if not errors:
            print("None (0 console errors)", flush=True)
        for msg in errors:
            print(msg, flush=True)
            
        os.makedirs("backend/scratch", exist_ok=True)
        await page.screenshot(path="backend/scratch/login_success_proof.png")
        print("Screenshot saved to backend/scratch/login_success_proof.png", flush=True)
        
        await browser.close()
        print("Playwright test complete.", flush=True)

if __name__ == "__main__":
    asyncio.run(run())
