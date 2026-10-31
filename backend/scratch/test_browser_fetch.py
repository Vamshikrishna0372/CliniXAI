import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        page.on('console', lambda msg: print(f"CONSOLE [{msg.type}]: {msg.text}"))
        
        await page.goto("http://localhost:3100/auth/login", wait_until="networkidle")
        
        # Test fetch directly inside the browser page context
        res = await page.evaluate("""async () => {
            try {
                const response = await fetch("http://localhost:8000/api/v1/health");
                const data = await response.json();
                return { ok: response.ok, status: response.status, data };
            } catch (err) {
                return { error: err.message, stack: err.stack };
            }
        }""")
        print("Browser fetch to backend /health:", res)
        
        # Test fetch to /auth/me
        res_me = await page.evaluate("""async () => {
            try {
                const response = await fetch("http://localhost:8000/api/v1/auth/me");
                const data = await response.json();
                return { ok: response.ok, status: response.status, data };
            } catch (err) {
                return { error: err.message, stack: err.stack };
            }
        }""")
        print("Browser fetch to backend /auth/me:", res_me)
        
        # Test fetch to /auth/login
        res_login = await page.evaluate("""async () => {
            try {
                const response = await fetch("http://localhost:8000/api/v1/auth/login", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ email: "admin@clinixai.com", password: "admin123" })
                });
                const data = await response.json();
                return { ok: response.ok, status: response.status, data };
            } catch (err) {
                return { error: err.message, stack: err.stack };
            }
        }""")
        print("Browser fetch to backend /auth/login:", res_login)
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
