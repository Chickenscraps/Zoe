
try:
    import playwright
    print("Playwright is installed.")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        print("Playwright engine is working.")
except ImportError:
    print("Playwright is NOT installed.")
except Exception as e:
    print(f"Playwright error: {e}")
