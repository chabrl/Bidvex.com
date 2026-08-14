"""
Focused Playwright QA script for iter484.2 Gate 2 retest.

Purpose:
- Verify /vehicle-auctions/iter484-2-gate2-{no-reserve,reserve-not-met,reserve-met}
  no longer crashes to ErrorBoundary after the VehicleReserveBadge fix.
- Verify buyer-safe reserve badges render with the expected data-state/text.
- Verify raw reserve amount tokens are not present in DOM text.

This file is a durable copy of the script executed through mcp_browser_automation.
"""

# Executed inside the mcp_browser_automation async context with `page` available.
await page.set_viewport_size({"width": 1920, "height": 1080})

consent_script = """() => {
  const consent = JSON.stringify({
    version: 2, accepted: true, necessary: true,
    analytics: true, marketing: true, preferences: true,
    timestamp: Date.now(),
  });
  localStorage.setItem('bidvex_cookie_consent', consent);
  localStorage.setItem('bidvex_cookie_consent_v2', consent);
}"""

cases = [
  {
    "slug": "iter484-2-gate2-no-reserve",
    "expected_state": "none",
    "expected_texts": ["No Reserve"],
  },
  {
    "slug": "iter484-2-gate2-reserve-not-met",
    "expected_state": "not_met",
    "allowed_states": ["not_met", "set"],
    "expected_texts": ["Reserve Not Met", "Reserve Set"],
  },
  {
    "slug": "iter484-2-gate2-reserve-met",
    "expected_state": "met",
    "expected_texts": ["Reserve Met"],
  },
]

raw_tokens = ["$25,000", "$20,000", "25000", "20000"]
results = []

try:
  await page.goto("/", wait_until="domcontentloaded")
  await page.evaluate(consent_script)
  print("Set cookie consent localStorage")

  for case in cases:
    url = f"/vehicle-auctions/{case['slug']}"
    print(f"Testing {url}")
    await page.goto(url, wait_until="domcontentloaded")
    await page.wait_for_timeout(2500)

    title = await page.title()
    body_text = await page.locator("body").inner_text(timeout=10000)
    error_boundary = "Something went wrong" in body_text
    reserve_ref_error = "reserveMet is not defined" in body_text

    badges = await page.locator('[data-testid="vehicle-reserve-badge"]').evaluate_all("""
      els => els.map((el, index) => ({
        index,
        state: el.getAttribute('data-state'),
        text: el.textContent.trim(),
        tag: el.tagName,
        visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length),
      }))
    """)
    print(f"Badges for {case['slug']}: {badges}")

    states = [b.get("state") for b in badges]
    allowed_states = case.get("allowed_states", [case["expected_state"]])
    state_ok = any(s in allowed_states for s in states)
    text_ok = any(t in body_text for t in case["expected_texts"])
    leaked_tokens = [t for t in raw_tokens if t in body_text]

    # Get error messages using specific selectors
    error_text = await page.evaluate("""() => {
      const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));
      return errorElements.map(el => el.textContent).join(", ");
    }""")
    if error_text:
      print(f"Found error message: {error_text}")
    else:
      print("No error messages found on the page")

    result = {
      "slug": case["slug"],
      "title": title,
      "error_boundary": error_boundary,
      "reserve_ref_error_in_dom": reserve_ref_error,
      "badges": badges,
      "state_ok": state_ok,
      "text_ok": text_ok,
      "leaked_tokens": leaked_tokens,
      "error_text": error_text,
    }
    results.append(result)

    assert not error_boundary, f"ErrorBoundary visible on {case['slug']}"
    assert not reserve_ref_error, f"reserveMet ReferenceError visible on {case['slug']}"
    assert len(badges) >= 1, f"No vehicle reserve badge rendered on {case['slug']}"
    assert state_ok, f"Expected data-state {allowed_states}, got {states} on {case['slug']}"
    assert text_ok, f"Expected reserve text {case['expected_texts']} missing on {case['slug']}"
    assert leaked_tokens == [], f"Raw reserve token leak {leaked_tokens} on {case['slug']}"
    print(f"PASS {case['slug']}")

  print(f"ITER484_2_GATE2_RETEST_RESULTS={results}")
  print("OVERALL PASS: all 3 vehicle detail reserve routes render without ErrorBoundary, badges are present, and raw reserve tokens are absent")
except Exception as exc:
  print(f"TEST FAILURE: {exc}")
  raise