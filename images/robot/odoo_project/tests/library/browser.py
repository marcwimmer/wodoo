from selenium import webdriver
from robot.libraries.BuiltIn import BuiltIn


BROWSER_NAMES = {
    'googlechrome': "chrome",
    'gc': "chrome",
    'chrome': "chrome",
    'headlesschrome': 'chrome',
    'ff': 'firefox',
    'firefox': 'firefox',
    'headlessfirefox': 'firefox',
}


class BrowserDriver(object):

    def __init__(self, browser, path):
        if browser in BROWSER_NAMES:
            driver = BROWSER_NAMES[browser]
            self.browser = browser
            self.path = path
            self.headless = 'headless' in browser

            self.driverClass = driver.capitalize()
            self.optionsClass = '{}Options'.format(driver.capitalize())
            self.optionsMethod = '_add_options_for_{}'.format(driver)
        else:
            raise ValueError('{} is not a supported browser.'.format(browser))

    def create_webdriver(self):
        options = self.create_options()
        instance = BuiltIn().get_library_instance('SeleniumLibrary')
        driver = instance.create_webdriver(self.driverClass, options=options)
        if self.headless and self.driverClass == 'Chrome':
            self._enable_download_in_headless_chrome(instance._drivers.current)
        return driver

    def _enable_download_in_headless_chrome(self, driver):
        """
        There is currently a "feature" in chrome where
        headless does not allow file download:
        https://bugs.chromium.org/p/chromium/issues/detail?id=696481
        This method is a hacky work-around until the official chromedriver
        support for this.
        Requires chrome version 62.0.3196.0 or above.
        """
        driver.command_executor._commands["send_command"] = (
            "POST", '/session/$sessionId/chromium/send_command'
        )
        params = {
            'cmd': 'Page.setDownloadBehavior',
            'params': {'behavior': 'allow', 'downloadPath': self.path}
        }
        driver.execute("send_command", params)

    def create_options(self):
        options = getattr(webdriver, self.optionsClass)()
        if self.headless:
            options.add_argument("--headless")
            options.add_argument("--window-size=1920,3840")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-popup-blocking")
        return getattr(self, self.optionsMethod)(options)

    def _add_options_for_chrome(self, options):
        options.add_experimental_option("prefs", {
            "download.default_directory": self.path,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "download.extensions_to_open": "",
            "plugins.always_open_pdf_externally": True
        })
        if self.headless:
            pass
        return options

    def _add_options_for_firefox(self, options):
        options.set_preference(
            "browser.download.folderList", 2
        )
        options.set_preference(
            "browser.download.manager.showWhenStarting", False
        )
        options.set_preference(
            "browser.download.dir", self.path
        )
        options.set_preference(
            "browser.helperApps.neverAsk.saveToDisk", 'application/pdf'
        )
        options.set_preference(
            "pdfjs.disabled", True
        )
        return options


def get_driver_for_browser(browser, path):
    bd = BrowserDriver(browser, get_absolute_path(path))
    return bd.create_webdriver()


def get_absolute_path(path):
    absolute_path = []
    for level in path.split('/'):
        if level == '..':
            absolute_path = absolute_path[:-1]
        else:
            absolute_path.append(level)
    return '/'.join(absolute_path)


def get_selenium_browser_log():
    instance = BuiltIn().get_library_instance('SeleniumLibrary')
    return instance.driver.get_log('browser')
