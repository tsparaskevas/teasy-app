from __future__ import annotations
import os, time, random, shutil
import requests
from typing import Protocol, Dict, List, Optional
from contextlib import contextmanager

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .utils import user_agent

class Fetcher(Protocol):
    def get(self, url: str, headers: Dict[str, str] | None = None, **kwargs) -> tuple[str, str]: ...

def _chrome_service() -> ChromeService:
    path = os.getenv("CHROMEDRIVER") or shutil.which("chromedriver")
    if path:
        return ChromeService(path)
    try:
        from webdriver_manager.chrome import ChromeDriverManager
    except ImportError as e:
        raise RuntimeError("ChromeDriver not found. Install webdriver-manager or set CHROMEDRIVER.") from e
    return ChromeService(ChromeDriverManager().install())

class RequestsFetcher:
    def __init__(self, timeout: int = 20, min_delay: float = 0.5, max_delay: float = 1.2,
                 total_retries: int = 2, backoff_factor: float = 0.5):
        self.timeout = timeout
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.session = requests.Session()
        retry = Retry(total=total_retries, backoff_factor=backoff_factor,
                      status_forcelist=[429,500,502,503,504],
                      allowed_methods=["GET","HEAD","OPTIONS"], raise_on_status=False)
        adapter = HTTPAdapter(max_retries=retry, pool_maxsize=10)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def get(self, url: str, headers: Dict[str, str] | None = None, **_) -> tuple[str, str]:
        time.sleep(random.uniform(self.min_delay, self.max_delay))
        h = {"User-Agent": user_agent(), "Accept-Language": "el-GR,el;q=0.9,en-US;q=0.8,en;q=0.7"}
        if headers:
            h.update(headers)
        r = self.session.get(url, headers=h, timeout=self.timeout)
        r.raise_for_status()
        return (r.url, r.text)

class SeleniumFetcher:
    def __init__(self, headless: bool = True, page_load_timeout: int = 30,
                 wait_after_load: float = 1.0, page_load_strategy: str = "eager",
                 window_size: str = "1400,1600"):
        self.headless = headless if os.environ.get("HEADLESS", "").lower() != "false" else False
        self.page_load_timeout = page_load_timeout
        self.wait_after_load = wait_after_load
        self.page_load_strategy = page_load_strategy
        self.window_size = window_size
        self._driver = None

    def _build_driver(self):
        opts = Options()
        if self.headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--lang=el-GR")
        opts.add_argument(f"--user-agent={user_agent()}")
        opts.add_argument(f"--window-size={self.window_size}")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        chrome_bin = os.getenv("GOOGLE_CHROME_BIN") or os.getenv("CHROME_BIN")
        if chrome_bin:
            opts.binary_location = chrome_bin
        service = _chrome_service()
        d = webdriver.Chrome(service=service, options=opts)
        d.set_page_load_timeout(self.page_load_timeout)
        try:
            d.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                          "window.chrome = { runtime: {} };"
                          "Object.defineProperty(navigator, 'languages', {get: () => ['el-GR','el','en-US','en']});"
                          "Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3]});"
            })
        except Exception:
            pass
        return d

    @contextmanager
    def session(self):
        self.start()
        try:
            yield self
        finally:
            self.stop()

    def start(self):
        if self._driver is None:
            self._driver = self._build_driver()

    def stop(self):
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None

    def _ensure_driver(self):
        if self._driver is None:
            return self._build_driver(), True
        return self._driver, False

    def _click_xpaths(self, d, xpaths: List[str]) -> int:
        cnt = 0
        for xp in xpaths:
            xp = xp.strip()
            if not xp: continue
            try:
                el = d.find_element(By.XPATH, xp)
                el.click()
                import time; time.sleep(0.5)
                cnt += 1
            except Exception:
                continue
        return cnt

    def get(self, url: str, headers: Dict[str, str] | None = None,
            wait_for_css: str | None = None, wait_timeout: int | None = None,
            consent_click_xpaths: Optional[List[str]] = None) -> tuple[str, str]:
        d, ephemeral = self._ensure_driver()
        try:
            d.get(url)
            if consent_click_xpaths:
                self._click_xpaths(d, consent_click_xpaths)
            if wait_for_css:
                try:
                    WebDriverWait(d, wait_timeout or self.page_load_timeout).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, wait_for_css))
                    )
                except TimeoutException:
                    pass
            import time; time.sleep(self.wait_after_load)
            return (d.current_url, d.page_source)
        except TimeoutException:
            return (d.current_url, d.page_source)
        finally:
            if ephemeral:
                try:
                    d.quit()
                except Exception:
                    pass

class HybridFetcher:
    def __init__(self, js_required: bool = False, **selenium_kwargs):
        self.req = RequestsFetcher()
        self.sel = SeleniumFetcher(**selenium_kwargs)
        self._use_selenium = js_required

    @contextmanager
    def session(self):
        if self._use_selenium:
            with self.sel.session():
                yield self
        else:
            try:
                yield self
            finally:
                self.sel.stop()

    def get(self, url: str, headers: Dict[str, str] | None = None, **sel_kwargs) -> tuple[str, str]:
        if self._use_selenium:
            return self.sel.get(url, headers=headers, **sel_kwargs)
        try:
            return self.req.get(url, headers=headers)
        except Exception:
            self._use_selenium = True
            self.sel.start()
            return self.sel.get(url, headers=headers, **sel_kwargs)
