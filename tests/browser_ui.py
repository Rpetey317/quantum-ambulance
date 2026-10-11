"""Real Chrome + Python bridge integration. No remote or paid jobs.

Run with Qiskit dependencies and playwright available:
python tests/browser_ui.py --browser "C:/Program Files/Google/Chrome/Application/chrome.exe"
"""

import argparse
import json
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ambulance.bridge import preview  # noqa: E402
from tools.preview_ui import Handler  # noqa: E402


def check(browser_path, artifacts):
    from playwright.sync_api import expect, sync_playwright

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    artifacts.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as playwright:
            options = {"executable_path": browser_path} if browser_path else {}
            browser = playwright.chromium.launch(headless=True, **options)
            page = browser.new_page(viewport={"width": 1440, "height": 1050})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{server.server_port}")
            greedy = page.locator('[data-method="greedy"]')
            exact = page.locator('[data-method="exact"]')
            quantum = page.locator('[data-method="qaoa"]')
            expect(greedy.locator(".percentage")).to_have_text("81.0%")
            expect(exact.locator(".percentage")).to_have_text("85.1%")
            expect(page.locator("#add")).to_be_enabled()
            algorithm = page.locator("#map-algorithm")
            expect(algorithm).to_have_value("greedy")
            expect(algorithm.locator('option[value="qaoa"]')).to_have_js_property("disabled", True)
            background = page.locator("#map-background")
            expect(background).to_have_value("streets")
            expect(page.locator("#map-credit")).to_contain_text("OpenStreetMap")

            def painted_fraction():
                return page.evaluate(
                    """() => {
                    const c = document.querySelector('#map canvas');
                    const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
                    let painted = 0, total = 0;
                    for (let i = 3; i < d.length; i += 397 * 4) {
                        total++;
                        if (d[i] > 100) painted++;
                    }
                    return painted / total;
                }"""
                )

            assert painted_fraction() > 0.4
            background.select_option("satellite")
            expect(page.locator("#map-credit")).to_contain_text("Sentinel-2")
            assert painted_fraction() > 0.4
            background.select_option("plain")
            expect(page.locator("#map-credit")).to_be_hidden()
            assert painted_fraction() < 0.3
            background.select_option("streets")
            expect(page.locator("#map-credit")).to_contain_text("OpenStreetMap")
            exact.get_by_role("button").click()
            expect(algorithm).to_have_value("exact")
            algorithm.select_option("greedy")
            expect(greedy.get_by_role("button")).to_have_attribute("aria-pressed", "true")
            algorithm.select_option("exact")
            assert page.locator(".marker.selected").count() == 3
            page.locator(".source-details summary").click()
            expect(page.locator("#provenance")).to_contain_text("One point per census tract")
            expect(page.locator("#provenance")).to_contain_text("2010 National Census")
            expect(page.locator("#provenance")).to_contain_text("Información Censal por Radio")
            assert "un punto por" not in page.locator("#provenance").inner_text()
            page.screenshot(path=str(artifacts / "desktop.png"), full_page=True)

            # Drag -> revision bump -> real Python recomputation -> matching overlay.
            marker = page.locator(".marker").first
            marker.scroll_into_view_if_needed()
            box = marker.bounding_box()
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.mouse.down()
            page.mouse.move(
                box["x"] + box["width"] / 2 + 20, box["y"] + box["height"] / 2, steps=4
            )
            page.mouse.up()
            expect(page.locator("#case-summary")).to_contain_text("revision 2")
            expect(exact.locator(".status")).to_have_text("Current case")
            page.locator("#export").click()
            snapshot = json.loads(page.locator("#snapshot").input_value())
            page.context.grant_permissions(["clipboard-read", "clipboard-write"])
            page.locator("#copy").click()
            expect(page.locator("#copy-status")).to_contain_text("Copied")
            assert json.loads(page.evaluate("navigator.clipboard.readText()")) == snapshot
            expected = json.loads(preview(json.dumps(snapshot)))["exact"]
            selected = [
                int(text)
                for text in page.locator(".marker.selected").all_text_contents()
            ]
            assert sorted(selected) == expected["selected_site_indices"]
            expect(exact.locator(".percentage")).to_have_text(
                f"{expected['coverage_pct']:.1f}%"
            )

            # Duplicates and numeric edits; validation must keep rejected inputs out.
            duplicate = snapshot["sites"][1]
            page.locator("#x").fill(str(duplicate["x_km"]))
            page.locator("#y").fill(str(duplicate["y_km"]))
            page.get_by_role("button", name="Apply coordinates").click()
            expect(page.locator("#error")).to_contain_text("1 metre")
            expect(page.locator("#case-summary")).to_contain_text("revision 2")
            page.locator("#x").fill(str(snapshot["sites"][0]["x_km"] + 0.02))
            page.locator("#y").fill(str(snapshot["sites"][0]["y_km"]))
            page.get_by_role("button", name="Apply coordinates").click()
            expect(page.locator("#case-summary")).to_contain_text("revision 3")
            expect(page.locator("#error")).to_be_hidden()

            page.locator("#k").fill("8")
            page.locator("#k").dispatch_event("change")
            page.locator("#remove").click()
            expect(page.locator("#k")).to_have_value("7")
            expect(page.locator("#add")).to_be_enabled()
            page.locator("#add").click()
            expect(page.locator("#site-limit")).to_contain_text("8 / 16")
            for _ in range(8):
                page.locator("#add").click()
            expect(page.locator("#add")).to_be_disabled()
            assert page.locator(".marker").count() == 16

            # Full-resolution large case, then mobile layout and a numeric edit.
            page.locator("#dataset").select_option("caba")
            expect(page.locator("#case-summary")).to_contain_text("3,552 demand zones")
            expect(exact.locator(".status")).to_have_text("Current case")
            assert not page.evaluate(
                "document.documentElement.scrollWidth > innerWidth"
            )
            page.screenshot(path=str(artifacts / "large.png"), full_page=True)
            large_marker = page.locator(".marker").first
            large_marker.scroll_into_view_if_needed()
            box = large_marker.bounding_box()
            page.mouse.move(box["x"] + 18, box["y"] + 18)
            page.mouse.down()
            page.mouse.move(box["x"] + 30, box["y"] + 18, steps=8)
            page.mouse.up()
            expect(page.locator("#case-summary")).to_contain_text("revision 2")
            expect(exact.locator(".status")).to_have_text("Current case")
            page.set_viewport_size({"width": 390, "height": 844})
            assert not page.evaluate(
                "document.documentElement.scrollWidth > innerWidth"
            )
            page.locator("#k").fill("2")
            page.locator("#k").dispatch_event("change")
            expect(page.locator("#case-summary")).to_contain_text("revision 3")
            expect(exact.locator(".status")).to_have_text("Current case")
            page.screenshot(path=str(artifacts / "mobile.png"), full_page=True)

            # Real sampled local BasicSimulator, then an edit removes its old layer.
            page.locator("#dataset").select_option("synthetic")
            expect(background).to_have_value("abstract")
            expect(background.locator('option[value="streets"]')).to_have_js_property("disabled", True)
            expect(background.locator('option[value="satellite"]')).to_have_js_property("disabled", True)
            expect(page.locator("#map-credit")).to_contain_text("Illustrated")
            assert painted_fraction() > 0.4
            expect(greedy.locator(".percentage")).to_have_text("79.7%")
            expect(exact.locator(".percentage")).to_have_text("90.1%")
            page.locator("#shots").fill("8")
            page.locator("#run").click()
            expect(quantum.locator(".status")).to_have_text(
                "Current case", timeout=60000
            )
            expect(quantum).to_contain_text("Backend / job wall time")
            expect(quantum).to_contain_text("8 / 8")
            expect(algorithm.locator('option[value="qaoa"]')).to_have_js_property("disabled", False)
            quantum.get_by_role("button").click()
            expect(algorithm).to_have_value("qaoa")
            assert page.locator(".marker.selected").count() == 3
            page.locator("#k").fill("2")
            page.locator("#k").dispatch_event("change")
            expect(quantum.locator(".status")).to_have_text("Stale after a case edit")
            expect(quantum.locator(".percentage")).to_have_text("—")
            expect(algorithm.locator('option[value="qaoa"]')).to_have_js_property("disabled", True)
            expect(algorithm).to_have_value("greedy")
            assert page.locator(".marker.selected").count() == 2

            # Restoring a saved candidate snapshot reloads trusted demand zones.
            page.locator("#snapshot").fill(json.dumps(snapshot))
            page.locator("#restore").click()
            expect(page.locator("#dataset")).to_have_value("caba-comuna4")
            expect(page.locator("#x")).to_have_value(str(snapshot["sites"][0]["x_km"]))
            expect(exact.locator(".status")).to_have_text("Current case")
            custom = json.loads(json.dumps(snapshot))
            custom["meta"]["id"] = "imported-case"
            custom["meta"]["revision"] = "draft-3"
            custom["meta"]["zone_resolution"] = "Custom demand centroids"
            custom["zones"][0]["weight"] += 1000
            page.locator("#snapshot").fill(json.dumps(custom))
            page.locator("#load-json").click()
            expect(page.locator("#dataset")).to_have_value("imported")
            expect(background).to_have_value("streets")
            expect(page.locator("#revision-note")).to_contain_text("imported-case · revision draft-3")
            expect(page.locator("#provenance")).to_contain_text("Custom demand centroids")
            expect(greedy.locator(".status")).to_have_text("Current case")
            expect(algorithm.locator('option[value="qaoa"]')).to_have_js_property("disabled", True)
            page.locator("#export").click()
            assert json.loads(page.locator("#snapshot").input_value())["zones"][0]["weight"] == custom["zones"][0]["weight"]
            page.locator("#snapshot").fill("{not json")
            page.locator("#load-json").click()
            expect(page.locator("#error")).to_contain_text("Cannot load JSON")
            expect(page.locator("#dataset")).to_have_value("imported")
            page.locator("#k").fill("2")
            page.locator("#k").dispatch_event("change")
            expect(page.locator("#case-summary")).to_contain_text("revision draft-3:edit")
            page.locator("#reset").click()
            expect(page.locator("#k")).to_have_value(str(custom["k_default"]))
            expect(page.locator("#case-summary")).to_contain_text("revision draft-3")
            page.locator("#dataset").select_option("synthetic")
            expect(greedy.locator(".status")).to_have_text("Current case")
            page.locator("#dataset").select_option("imported")
            expect(page.locator("#revision-note")).to_contain_text("imported-case")
            page.locator("#snapshot").fill(json.dumps(custom))
            page.locator("#restore").click()
            expect(page.locator("#error")).to_contain_text("Cannot restore")
            page.locator("#snapshot").fill(json.dumps(snapshot))
            page.locator("#restore").click()
            expect(page.locator("#dataset")).to_have_value("caba-comuna4")
            page.locator("#export").click()
            assert json.loads(page.locator("#snapshot").input_value())["zones"][0]["weight"] == snapshot["zones"][0]["weight"]

            # Test-only injected transport results exercise honest unavailable/invalid/error UI.
            from ambulance.core import evaluate_case, prepare_case
            from ambulance.quantum import summarize_counts

            def bounded_preview(route):
                data = route.request.post_data_json
                route.fulfill(json=evaluate_case(data, max_combinations=1))

            page.route("**/api/preview", bounded_preview)
            page.locator("#k").fill("2")
            page.locator("#k").dispatch_event("change")
            expect(exact.locator(".status")).to_have_text("Exact search unavailable")
            expect(exact).to_contain_text("cost bound")
            expect(algorithm.locator('option[value="exact"]')).to_have_js_property("disabled", True)

            def invalid_samples(route):
                data = route.request.post_data_json["data"]
                comparison = evaluate_case(data, max_combinations=1)
                comparison["qaoa"] = summarize_counts(
                    prepare_case(data), {"00000000": 8}, comparison["exact"]
                )
                route.fulfill(json=comparison)

            page.route("**/api/quantum", invalid_samples)
            page.locator("#run").click()
            expect(quantum.locator(".status")).to_have_text("No valid exactly-K sample")
            expect(algorithm.locator('option[value="qaoa"]')).to_have_js_property("disabled", True)
            expect(quantum.locator(".percentage")).to_have_text("—")
            expect(quantum).to_contain_text("Not evaluated")
            expect(quantum.get_by_role("button")).to_be_disabled()
            page.unroute("**/api/quantum", invalid_samples)
            page.route(
                "**/api/quantum",
                lambda route: route.fulfill(
                    status=400, json={"error": "Unsupported test backend"}
                ),
            )
            page.locator("#run").click()
            expect(quantum.locator(".status")).to_have_text("Failed / unsupported")
            expect(quantum).to_contain_text("Unsupported test backend")
            page.unroute("**/api/preview", bounded_preview)
            page.route(
                "**/api/case?*",
                lambda route: route.fulfill(
                    status=400, json={"error": "Test asset unavailable"}
                ),
            )
            page.locator("#dataset").select_option("caba")
            expect(page.locator("#error")).to_contain_text("Test asset unavailable")
            expect(page.locator("#map-empty")).to_be_visible()
            expect(page.locator("#run")).to_be_disabled()
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    print(f"Browser integration passed; screenshots: {artifacts}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser")
    parser.add_argument(
        "--artifacts",
        type=Path,
        default=Path(tempfile.gettempdir()) / "ambulance-ui-qa",
    )
    args = parser.parse_args()
    check(args.browser, args.artifacts)
