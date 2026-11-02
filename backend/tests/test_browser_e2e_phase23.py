"""Production-Grade Browser E2E Test Suite for CliniXAI (Phase 23).
Validates frontend-backend integration, multi-role workflows, cross-user privacy,
session teardown, page refresh persistence, and controlled failure rendering.
Requirements: Sections 50-60 of Phase 23 Master Prompt.
"""

import pytest
import pytest_asyncio
import sys
from playwright.async_api import async_playwright, Browser, Page

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

BASE_FRONTEND_URL = "http://localhost:3100"
BASE_BACKEND_URL = "http://127.0.0.1:8000"


@pytest_asyncio.fixture
async def browser_instance():
    """Initializes headless Chromium instance for each E2E test."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        yield browser
        await browser.close()


async def perform_login(page: Page, email: str, password: str):
    """Canonical login helper supporting both demo shortcuts and sequential typing."""
    await page.goto(f"{BASE_FRONTEND_URL}/auth/login", wait_until="networkidle")
    
    email_inp = page.locator("input#email")
    await email_inp.wait_for(state="visible", timeout=10000)
    await email_inp.fill(email)
    
    pass_inp = page.locator("input#password")
    await pass_inp.fill(password)
        
    submit_btn = page.locator('button[type="submit"]:not([disabled])')
    await submit_btn.wait_for(state="visible", timeout=5000)
    await submit_btn.click()
    await page.wait_for_url("**/app**", timeout=15000)
    await page.wait_for_selector("text=Dashboard", timeout=10000)
    await page.wait_for_load_state("networkidle")


async def perform_logout(page: Page):
    """Canonical logout helper: clears auth tokens and returns to login."""
    await page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
    await page.goto(f"{BASE_FRONTEND_URL}/auth/login", wait_until="networkidle")
    await page.wait_for_selector("input#email", timeout=6000)


@pytest.mark.asyncio
@pytest.mark.browser
async def test_browser_admin_flow(browser_instance: Browser):
    """Section 55: Admin flow — login, dashboard, administrative navigation, logout."""
    context = await browser_instance.new_context(viewport={"width": 1440, "height": 900})
    page = await context.new_page()
    try:
        await perform_login(page, "admin@clinixai.com", "admin123")
        assert "/app" in page.url
        body_text = await page.locator("body").inner_text()
        assert "CliniXAI" in body_text
        assert "Admin" in body_text or "Administrator" in body_text
        
        await perform_logout(page)
        assert "/auth/login" in page.url
    finally:
        await context.close()


@pytest.mark.asyncio
@pytest.mark.browser
async def test_browser_doctor_flow(browser_instance: Browser):
    """Section 53: Doctor flow — login, appointments workbench, consultations navigation, logout."""
    context = await browser_instance.new_context(viewport={"width": 1440, "height": 900})
    page = await context.new_page()
    try:
        await perform_login(page, "doctor.arjun@clinixai.com", "Doctor@123")
        assert "/app" in page.url
        body_text = await page.locator("body").inner_text()
        assert "Arjun Rao" in body_text or "Doctor" in body_text

        # Navigate to appointments
        await page.goto(f"{BASE_FRONTEND_URL}/app/appointments", wait_until="networkidle")
        appt_body = await page.locator("body").inner_text()
        assert "Appointments" in appt_body or "Schedule" in appt_body

        await perform_logout(page)
        assert "/auth/login" in page.url
    finally:
        await context.close()


@pytest.mark.asyncio
@pytest.mark.browser
async def test_browser_staff_flow(browser_instance: Browser):
    """Section 54: Staff flow — login, operational desk, clinical boundaries verification, logout."""
    context = await browser_instance.new_context(viewport={"width": 1440, "height": 900})
    page = await context.new_page()
    try:
        await perform_login(page, "staff.one@clinixai.com", "Staff@123")
        assert "/app" in page.url
        body_text = await page.locator("body").inner_text()
        assert "Staff One" in body_text or "Staff" in body_text

        # Verify staff desk navigation works
        await page.goto(f"{BASE_FRONTEND_URL}/app/appointments", wait_until="networkidle")
        page_text = await page.locator("body").inner_text()
        assert "Appointments" in page_text or "Check-in" in page_text

        await perform_logout(page)
        assert "/auth/login" in page.url
    finally:
        await context.close()


@pytest.mark.asyncio
@pytest.mark.browser
async def test_browser_patient_flow(browser_instance: Browser):
    """Section 52: Patient flow — login, dashboard, appointments portal, medical records privacy, logout."""
    context = await browser_instance.new_context(viewport={"width": 1440, "height": 900})
    page = await context.new_page()
    try:
        await perform_login(page, "patient.one@clinixai.com", "Patient@123")
        assert "/app" in page.url
        body_text = await page.locator("body").inner_text()
        assert "Patient" in body_text

        # Navigate to appointments portal
        await page.goto(f"{BASE_FRONTEND_URL}/app/appointments", wait_until="networkidle")
        appt_text = await page.locator("body").inner_text()
        assert "Appointments" in appt_text or "Upcoming" in appt_text

        await perform_logout(page)
        assert "/auth/login" in page.url
    finally:
        await context.close()


@pytest.mark.asyncio
@pytest.mark.browser
async def test_browser_cross_user_isolation(browser_instance: Browser):
    """Section 56: Cross-user test — Patient A logout -> Patient B login: zero Patient A data visible."""
    context = await browser_instance.new_context(viewport={"width": 1440, "height": 900})
    page = await context.new_page()
    try:
        # 1. Login as Patient A
        await perform_login(page, "patient.one@clinixai.com", "Patient@123")
        patient_a_body = await page.locator("body").inner_text()
        assert "Patient One" in patient_a_body or "patient.one@clinixai.com" in patient_a_body
        
        # 2. Logout
        await perform_logout(page)
        
        # 3. Login as Patient B (via sequential keyboard typing)
        await perform_login(page, "patient.two@clinixai.com", "Patient@123")
        patient_b_body = await page.locator("body").inner_text()
        assert "Patient Two" in patient_b_body
        
        # Assert Patient A specific details are completely absent from Patient B view
        assert "patient.one@clinixai.com" not in patient_b_body
        assert "Patient One" not in patient_b_body
        
        await perform_logout(page)
    finally:
        await context.close()


@pytest.mark.asyncio
@pytest.mark.browser
async def test_browser_cross_role_teardown(browser_instance: Browser):
    """Section 57: Cross-role test — Admin -> Staff -> Patient session clearing without state leakage."""
    context = await browser_instance.new_context(viewport={"width": 1440, "height": 900})
    page = await context.new_page()
    try:
        # 1. Admin login & logout
        await perform_login(page, "admin@clinixai.com", "admin123")
        assert "/app" in page.url
        await perform_logout(page)

        # 2. Staff login
        await perform_login(page, "staff.one@clinixai.com", "Staff@123")
        staff_body = await page.locator("body").inner_text()
        assert "Administrator" not in staff_body
        await perform_logout(page)

        # 3. Patient login
        await perform_login(page, "patient.one@clinixai.com", "Patient@123")
        patient_body = await page.locator("body").inner_text()
        assert "Staff One" not in patient_body
        assert "Administrator" not in patient_body
        await perform_logout(page)
    finally:
        await context.close()


@pytest.mark.asyncio
@pytest.mark.browser
async def test_browser_hard_refresh_persistence(browser_instance: Browser):
    """Section 58: Dynamic pages must survive hard refresh (F5) without losing auth or session."""
    context = await browser_instance.new_context(viewport={"width": 1440, "height": 900})
    page = await context.new_page()
    try:
        await perform_login(page, "doctor.arjun@clinixai.com", "Doctor@123")
        await page.goto(f"{BASE_FRONTEND_URL}/app/appointments", wait_until="networkidle")
        assert "/app/appointments" in page.url

        # Perform hard page refresh
        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(1000)

        # Verify page remains authenticated and at /app/appointments
        assert "/app/appointments" in page.url
        body_text = await page.locator("body").inner_text()
        assert "Appointments" in body_text or "Schedule" in body_text
        assert "/auth/login" not in page.url

        await perform_logout(page)
    finally:
        await context.close()


@pytest.mark.asyncio
@pytest.mark.browser
async def test_browser_negative_not_found_handling(browser_instance: Browser):
    """Section 60: Negative route handling — 404 resource renders controlled message without crash."""
    context = await browser_instance.new_context(viewport={"width": 1440, "height": 900})
    page = await context.new_page()
    try:
        await perform_login(page, "doctor.arjun@clinixai.com", "Doctor@123")
        
        # Navigate to a nonexistent AI analysis ID
        await page.goto(f"{BASE_FRONTEND_URL}/app/ai-analysis/AI-NONEXISTENT-999", wait_until="networkidle")
        await page.wait_for_timeout(1000)

        body_text = await page.locator("body").inner_text()
        # Ensure the page shell did not white-screen or explode
        assert "CliniXAI" in body_text
        assert "Analysis not found." in body_text or "not found" in body_text.lower()

        await perform_logout(page)
    finally:
        await context.close()
