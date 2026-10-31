import asyncio, json, urllib.request
from playwright.async_api import async_playwright

FRONTEND_URL = 'http://localhost:3100'
BACKEND_URL = 'http://127.0.0.1:8000/api/v1'

def get_tokens():
    req = urllib.request.Request(
        f'{BACKEND_URL}/auth/login',
        data=json.dumps({'email': 'doctor.arjun@clinixai.com', 'password': 'Doctor@123'}).encode(),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

async def run():
    tok = get_tokens()
    t = {'accessToken': tok['access_token'], 'refreshToken': tok['refresh_token']}
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(viewport={'width': 1400, 'height': 900})
        page = await ctx.new_page()
        page.on('console', lambda m: print('CONSOLE:', m.type, m.text))
        await page.goto(FRONTEND_URL, wait_until='domcontentloaded')
        await page.evaluate("""t => {
            localStorage.setItem('clinixai.tokens', JSON.stringify(t));
        }""", t)
        
        print("Navigating to /app/ai-analysis/AI-2026-466F63...")
        await page.goto(f'{FRONTEND_URL}/app/ai-analysis/AI-2026-466F63', wait_until='domcontentloaded')
        await page.wait_for_timeout(3000)

        # Check images
        imgs = await page.query_selector_all('img')
        print(f'Total images for AI-2026-466F63: {len(imgs)}')
        for idx, img in enumerate(imgs):
            src = await img.get_attribute('src')
            alt = await img.get_attribute('alt')
            w = await img.evaluate('el => el.naturalWidth')
            h = await img.evaluate('el => el.naturalHeight')
            print(f'Img {idx}: alt={alt} size={w}x{h} src={(src[:60] if src else None)}')

        await page.screenshot(path='backend/scratch/ai_466f63.png')
        await b.close()

if __name__ == "__main__":
    asyncio.run(run())

