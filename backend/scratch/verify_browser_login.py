import asyncio
import os
import sys
from playwright.async_api import async_playwright

async def verify_browser():
    print("=== STARTING BROWSER VERIFICATION ===", flush=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        console_logs = []
        network_responses = []
        network_failures = []
        
        page.on("console", lambda msg: console_logs.append(f"[{msg.type.upper()}] {msg.text}"))
        page.on("requestfailed", lambda req: network_failures.append(f"{req.method} {req.url} -> {req.failure}"))
        page.on("response", lambda res: network_responses.append(f"{res.request.method} {res.url} -> {res.status}"))
        
        # 1. Direct browser fetch tests to backend
        print("\n--- 1. Testing browser direct fetch to backend ---", flush=True)
        await page.goto("http://localhost:3100", wait_until="domcontentloaded")
        await page.wait_for_timeout(1000)
        
        health_fetch = await page.evaluate("""async () => {
            try {
                const res = await fetch("http://localhost:8000/api/v1/health");
                return { status: res.status, ok: res.ok, data: await res.json() };
            } catch (err) {
                return { error: err.message };
            }
        }""")
        print("Browser fetch to /api/v1/health:", health_fetch, flush=True)
        
        ready_fetch = await page.evaluate("""async () => {
            try {
                const res = await fetch("http://localhost:8000/api/v1/health/ready");
                return { status: res.status, ok: res.ok, data: await res.json() };
            } catch (err) {
                return { error: err.message };
            }
        }""")
        print("Browser fetch to /api/v1/health/ready:", ready_fetch, flush=True)
        
        auth_me_fetch = await page.evaluate("""async () => {
            try {
                const res = await fetch("http://localhost:8000/api/v1/auth/me");
                return { status: res.status, ok: res.ok, data: await res.json() };
            } catch (err) {
                return { error: err.message };
            }
        }""")
        print("Browser fetch to /api/v1/auth/me (unauthenticated):", auth_me_fetch, flush=True)
        
        register_fetch = await page.evaluate("""async () => {
            try {
                const res = await fetch("http://localhost:8000/api/v1/auth/register", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({})
                });
                return { status: res.status, ok: res.ok, data: await res.json() };
            } catch (err) {
                return { error: err.message };
            }
        }""")
        print("Browser fetch to /api/v1/auth/register (empty payload validation check):", register_fetch, flush=True)
        
        # 2. Browser UI Login Verification
        print("\n--- 2. Testing real UI login on http://localhost:3100/auth/login ---", flush=True)
        await page.goto("http://localhost:3100/auth/login", wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)
        
        # Click the Primary (admin) demo account button to fill form
        demo_btn = page.locator("button:has-text('Primary (admin)')")
        if await demo_btn.count() > 0:
            await demo_btn.click()
            print("Clicked 'Primary (admin)' demo button.", flush=True)
        else:
            await page.fill("#email", "admin@clinixai.com")
            await page.fill("#password", "admin123")
            print("Filled credentials manually.", flush=True)
            
        await page.wait_for_timeout(500)
        
        submit_btn = page.locator("button[type='submit']")
        print(f"Submit button disabled status: {await submit_btn.is_disabled()}", flush=True)
        await submit_btn.click()
        print("Submitted login form. Waiting for navigation/response...", flush=True)
        
        # Wait for navigation or token storage
        for _ in range(20):
            await page.wait_for_timeout(500)
            tokens = await page.evaluate("() => localStorage.getItem('clinixai.tokens')")
            if tokens and "accessToken" in tokens:
                print("Found tokens in localStorage!", flush=True)
                break
                
        print("Final Page URL:", page.url, flush=True)
        print("Final Page Title:", await page.title(), flush=True)
        
        tokens_val = await page.evaluate("() => localStorage.getItem('clinixai.tokens')")
        print("Tokens stored in localStorage:", bool(tokens_val), flush=True)
        
        # 3. Authenticated /auth/me test from browser
        if tokens_val:
            auth_me_with_token = await page.evaluate("""async () => {
                const raw = localStorage.getItem('clinixai.tokens');
                const t = JSON.parse(raw);
                const res = await fetch("http://localhost:8000/api/v1/auth/me", {
                    headers: { "Authorization": `Bearer ${t.accessToken}` }
                });
                return { status: res.status, data: await res.json() };
            }""")
            print("Browser fetch to /api/v1/auth/me (WITH TOKEN):", auth_me_with_token, flush=True)
            
        # 4. Review network and console logs
        print("\n--- 3. Network Failures (ERR_CONNECTION_REFUSED check) ---", flush=True)
        refused = [f for f in network_failures if "ERR_CONNECTION_REFUSED" in f or "refused" in f.lower()]
        if not refused:
            print("ZERO ERR_CONNECTION_REFUSED failures detected! (PASS)", flush=True)
        else:
            for r in refused:
                print("REFUSED FAILURE:", r, flush=True)
                
        print("\n--- 4. Backend API Network Responses in Browser ---", flush=True)
        for r in network_responses:
            if "8000" in r:
                print(r, flush=True)
                
        print("\n--- 5. Console Error Logs ---", flush=True)
        err_logs = [l for l in console_logs if "ERROR" in l]
        if not err_logs:
            print("No console errors! (PASS)", flush=True)
        else:
            for l in err_logs:
                print(l, flush=True)
                
        os.makedirs("backend/scratch", exist_ok=True)
        proof_path = "backend/scratch/login_success_proof.png"
        await page.screenshot(path=proof_path)
        print(f"\nSaved proof screenshot to {proof_path}", flush=True)
        
        await browser.close()
        print("\n=== BROWSER VERIFICATION COMPLETED SUCCESSFULLY ===", flush=True)

if __name__ == "__main__":
    asyncio.run(verify_browser())
