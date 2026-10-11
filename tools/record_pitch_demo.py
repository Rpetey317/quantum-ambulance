"""Record the real local app for the middle of the three-minute pitch.

One local BasicSimulator job; no Qollab, IonQ, remote jobs or fabricated results.
Requires the project's Python dependencies, Playwright and its FFmpeg runtime.
The output has no narration. See pitch/DEMO.md for the human voiceover plan.
"""

import argparse
import json
import subprocess
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.preview_ui import Handler  # noqa: E402


class QuietHandler(Handler):
    def log_message(self, *_):
        pass


def record(browser_path, output):
    from playwright.sync_api import expect, sync_playwright

    output.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    evidence = {
        "environment": "Local Chrome and Qiskit BasicSimulator; no remote execution",
        "runtime_base_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "sampled_jobs": 0,
    }
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, executable_path=browser_path)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                record_video_dir=str(output / "raw"),
                record_video_size={"width": 1920, "height": 1080},
            )
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))

            def quantum_response(response):
                if response.url.endswith("/api/quantum"):
                    evidence["quantum_result"] = response.json()
                    evidence["sampled_jobs"] += 1

            page.on("response", quantum_response)
            page.goto(f"http://127.0.0.1:{server.server_port}")
            greedy = page.locator('[data-method="greedy"]')
            exact = page.locator('[data-method="exact"]')
            quantum = page.locator('[data-method="qaoa"]')
            expect(exact.locator(".percentage")).to_have_text("85.1%")
            page.evaluate("document.body.style.zoom = '0.9'")
            page.locator("#shots").fill("64")
            started = time.monotonic()
            evidence["recording_start_note"] = "Trim the brief page-loading lead-in before the first clean map frame."

            def until(seconds):
                page.wait_for_timeout(max(0, seconds - (time.monotonic() - started)) * 1000)

            def overview():
                page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")

            def compare():
                page.evaluate(
                    "window.scrollTo({top: document.querySelector('#comparison-heading')"
                    ".getBoundingClientRect().top + window.scrollY - 42, behavior: 'instant'})"
                )

            overview()
            until(4)
            page.locator("#map-algorithm").select_option("exact")
            page.screenshot(path=str(output / "01-comuna4-map.png"))
            until(8)
            compare()
            page.screenshot(path=str(output / "02-comuna4-comparison.png"))
            evidence["comuna4_comparison"] = page.locator("#methods").inner_text()
            until(20)
            overview()
            page.locator(".source-details summary").click()
            page.locator("#provenance").scroll_into_view_if_needed()
            until(29)
            overview()
            page.locator("#run").click()
            expect(quantum.locator(".status")).to_have_text("Current case", timeout=60000)
            compare()
            evidence["quantum_comparison"] = quantum.inner_text()
            page.screenshot(path=str(output / "03-local-quantum-metrics.png"))
            if time.monotonic() - started > 60:
                raise RuntimeError("Tuning exceeded the recording budget. Use the screenshots or a separately recorded quantum clip.")
            until(58)
            overview()
            page.locator("#candidate").select_option(index=0)
            page.locator("#x").fill("27.0496")
            page.locator("#coordinates button").click()
            expect(quantum.locator(".status")).to_have_text("Stale after a case edit")
            expect(page.locator("#case-summary")).to_contain_text("revision 2")
            compare()
            page.screenshot(path=str(output / "04-edited-case-stale.png"))
            evidence["edited_comparison"] = page.locator("#methods").inner_text()
            until(69)
            page.locator("#dataset").select_option("caba")
            expect(page.locator("#case-summary")).to_contain_text("3,552 demand zones")
            expect(exact.locator(".percentage")).to_have_text("58.2%")
            expect(greedy.locator(".percentage")).to_have_text("58.2%")
            page.locator("#map-algorithm").select_option("exact")
            overview()
            page.screenshot(path=str(output / "05-full-city-map.png"))
            until(79)
            compare()
            page.screenshot(path=str(output / "06-full-city-comparison.png"))
            evidence["full_city_comparison"] = page.locator("#methods").inner_text()
            until(89)
            assert evidence["sampled_jobs"] == 1
            assert not errors, errors
            evidence["action_timeline_seconds"] = [0, 4, 8, 20, 29, 58, 69, 79, 89]
            video = page.video
            context.close()
            video.save_as(str(output / "demo-local.webm"))
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        (output / "evidence.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Recorded real local demo and evidence in {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", default="C:/Program Files/Google/Chrome/Application/chrome.exe")
    parser.add_argument("--output", type=Path, default=ROOT / "pitch" / "media")
    args = parser.parse_args()
    record(args.browser, args.output)
