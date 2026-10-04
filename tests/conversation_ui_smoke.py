"""End-to-end smoke test for account-scoped AI conversation history."""

from pathlib import Path

from playwright.sync_api import sync_playwright


ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
ARTIFACT_DIR.mkdir(exist_ok=True)
TEST_MESSAGE = "会话恢复测试：请从本地新闻库推荐一条人工智能新闻"


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        headless=True,
        executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    )
    page = browser.new_page(viewport={"width": 390, "height": 844})
    errors: list[str] = []
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)

    page.goto("http://127.0.0.1:5173/login", wait_until="networkidle")
    page.get_by_placeholder("请输入用户名").fill("admin")
    page.get_by_placeholder("请输入密码").fill("123456")
    page.get_by_role("button", name="登录", exact=True).click()
    page.wait_for_url("**/home")
    page.get_by_text("AI问答", exact=True).click()
    page.wait_for_url("**/aichat")
    page.wait_for_load_state("networkidle")

    assert page.get_by_role("button", name="新建对话").is_visible()
    assert "已登录 · 对话自动保存" in page.locator(".composer-shell > p").inner_text()
    page.get_by_role("button", name="新建对话").click()
    page.locator("textarea").fill(TEST_MESSAGE)
    page.locator("button.send-button").click()
    page.locator(".thinking").wait_for(state="hidden", timeout=180_000)
    assert page.locator(".message-row.user").get_by_text(TEST_MESSAGE, exact=True).is_visible()

    page.get_by_role("button", name="打开对话记录").click()
    item = page.locator(".history-item.active")
    item.wait_for()
    assert "会话恢复测试" in item.inner_text()
    page.wait_for_timeout(350)
    page.screenshot(path=str(ARTIFACT_DIR / "conversation-history-drawer.png"))
    page.get_by_role("button", name="关闭对话记录").click()

    page.reload(wait_until="networkidle")
    page.locator(".message-row.user").get_by_text(TEST_MESSAGE, exact=True).wait_for()
    restored_sources = page.locator(".source-list button").count()
    restored_actions = page.locator(".action-trace span").count()

    page.get_by_role("button", name="打开对话记录").click()
    item = page.locator(".history-item.active")
    item.get_by_role("button", name="删除这条对话").click()
    page.get_by_role("button", name="确认").click()
    item.wait_for(state="detached")

    print(
        {
            "restoredMessage": True,
            "restoredSources": restored_sources,
            "restoredActions": restored_actions,
            "deletedFromHistory": True,
            "consoleErrors": errors,
        }
    )
    browser.close()
