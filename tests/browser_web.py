"""Browser smoke test for the public Vercel transport; one local simulator job.

python tests/browser_web.py --url https://quantum-ambulance.vercel.app
"""

import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def check(url, browser_path, artifacts):
    artifacts.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=browser_path)
        page = browser.new_page(viewport={"width": 1440, "height": 1050})
        errors = []
        jobs = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: jobs.append(request) if "action=quantum" in request.url else None)
        page.goto(url)
        greedy = page.locator('[data-method="greedy"]')
        exact = page.locator('[data-method="exact"]')
        quantum = page.locator('[data-method="qaoa"]')
        expect(greedy.locator(".percentage")).to_have_text("81.0%", timeout=60000)
        expect(exact.locator(".percentage")).to_have_text("85.1%")
        expect(page.locator("#backend-note")).to_contain_text("Web simulator")
        expect(page.locator("#shots")).to_have_attribute("max", "128")
        expect(page.locator("#map-credit")).to_contain_text("OpenStreetMap")
        page.locator("#map-background").select_option("satellite")
        expect(page.locator("#map-credit")).to_contain_text("Sentinel-2")
        page.locator("#map-background").select_option("streets")
        page.locator("#shots").fill("16")
        with page.expect_response(lambda response: "action=quantum" in response.url, timeout=90000) as response:
            page.locator("#run").click()
        result = response.value.json()
        q = result["qaoa"]
        assert q["status"] == "ok", q
        assert q["backend_run_calls"] == 1
        assert q["valid_shots"] == 16
        assert q["case_revision"] == result["case_revision"]
        assert q["input_fingerprint"] == result["input_fingerprint"]
        assert len(jobs) == 1
        expect(quantum.locator(".percentage")).not_to_have_text("Not evaluated")
        page.screenshot(path=str(artifacts / "desktop.png"), full_page=True)
        page.locator("#k").fill("2")
        page.locator("#k").dispatch_event("change")
        expect(page.locator("#case-summary")).not_to_contain_text("revision 1", timeout=15000)
        expect(quantum).to_contain_text("Stale after a case edit", timeout=15000)
        page.locator("#add").click()
        expect(page.locator("#backend-note")).to_contain_text("up to 8", timeout=15000)
        expect(page.locator("#run")).to_be_disabled()
        expect(exact.locator(".percentage")).not_to_have_text("Not evaluated")
        page.locator("#dataset").select_option("synthetic")
        expect(greedy.locator(".percentage")).to_have_text("79.7%", timeout=15000)
        expect(exact.locator(".percentage")).to_have_text("90.1%")
        page.locator("#dataset").select_option("caba")
        expect(exact.locator(".percentage")).to_have_text("58.2%", timeout=15000)
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        page.screenshot(path=str(artifacts / "mobile.png"), full_page=True)
        assert not errors, errors
        (artifacts / "quantum-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps({"url": url, "quantum_requests": len(jobs), "valid_shots": q["valid_shots"],
                          "coverage_pct": q["coverage_pct"], "timings": q["timings"], "browser_errors": errors}))
        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--browser", default="C:/Program Files/Google/Chrome/Application/chrome.exe")
    parser.add_argument("--artifacts", type=Path, default=Path(".vercel/browser-qa"))
    args = parser.parse_args()
    check(args.url, args.browser, args.artifacts)
