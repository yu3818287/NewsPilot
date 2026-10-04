"""Mobile UI smoke test for AI recommendations and local news details."""

from pathlib import Path

from playwright.sync_api import sync_playwright


ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
ARTIFACT_DIR.mkdir(exist_ok=True)


with sync_playwright() as playwright:
    # Use the system browser so Windows profiles with non-ASCII user names do
    # not make Playwright's downloaded executable path ambiguous.
    browser = playwright.chromium.launch(
        headless=True,
        executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    )
    page = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1)
    errors: list[str] = []
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)

    page.goto("http://127.0.0.1:5173/home", wait_until="networkidle")
    page.get_by_role("button", name="AI 今日热榜").click()
    page.locator(".news-item").first.wait_for()
    page.wait_for_timeout(800)
    page.wait_for_function(
        "() => [...document.querySelectorAll('.news-item .news-image img')].filter(el => el.naturalWidth > 0).length >= 2"
    )

    image_data = page.locator(".news-item .news-image img").evaluate_all(
        "els => els.map(el => ({src: el.src, width: el.naturalWidth}))"
    )
    loaded_images = [item for item in image_data if item["width"] > 0]
    assert len(loaded_images) >= 2, f"expected at least two loaded recommendation images: {image_data}"
    assert len({item["src"] for item in loaded_images}) >= 2, "recommendation images are still duplicated"
    page.screenshot(path=str(ARTIFACT_DIR / "ai-recommendations-real-images.png"))

    clicked = page.locator(".news-item").evaluate_all(
        """els => {
          const item = els.find(el => {
            const r = el.getBoundingClientRect();
            return r.left >= 0 && r.right <= innerWidth && r.top < innerHeight && r.bottom > 0;
          });
          if (!item) return false;
          item.click();
          return true;
        }"""
    )
    assert clicked, "AI recommendation list has no item inside the viewport"
    page.wait_for_url("**/news/detail/**")
    page.locator(".detail-content").wait_for()
    local_copy = "".join(page.locator(".content p").all_inner_texts())
    source = page.locator("a.source-link")
    assert len(local_copy) >= 500, f"local article is too short: {len(local_copy)}"
    assert source.is_visible(), "optional source attribution is missing"
    assert "原始来源" in source.inner_text()
    assert "/news/detail/" in page.url, f"detail unexpectedly left the site: {page.url}"
    page.screenshot(path=str(ARTIFACT_DIR / "local-news-detail.png"), full_page=True)

    print(
        {
            "loadedImages": len(loaded_images),
            "uniqueImages": len({item["src"] for item in loaded_images}),
            "detailCharacters": len(local_copy),
            "detailUrl": page.url,
            "consoleErrors": errors,
        }
    )
    browser.close()
