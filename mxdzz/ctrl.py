import inspect
import threading
import time
from Libs import App

running_event = threading.Event()


class Ctrl:
    timeout = 5
    sleep = 0.5
    err = 0
    Error = 5
    link = []
    pages = {}
    pages_other = {}
    app: App

    def __init__(self, app, get_aim_func) -> None:
        self.app = app
        self.get_aim = get_aim_func

    def add(self, page_module):
        page_classes = inspect.getmembers(page_module, inspect.isclass)
        for page_class in page_classes:
            self.pages[page_class[0]] = page_class[1]

    def add_other(self, page_module):
        page_classes = inspect.getmembers(page_module, inspect.isclass)
        for page_class in page_classes:
            self.pages_other[page_class[0]] = page_class[1]

    def match(self):
        if len(self.link) == 0:
            self.init_link()
        self.app.keep_screen(True)
        for page_name in self.link:
            page = self.pages[page_name]
            if self.app.is_multi_color(page.points):
                return page
        return False

    def match_other(self):
        for page_name in self.pages_other:
            page = self.pages_other[page_name]
            if self.app.is_multi_color(page.points):
                return page

    def init_link(self):
        self.link = [page_class_name for page_class_name in self.pages]

    def run_aim(self):
        aim = getattr(self.page, self.aim)
        if isinstance(aim, list):
            self.app.click_xy(*aim)
        else:
            aim()

    def run(self):
        self.t0 = time.time()
        while self.err < self.Error:
            if not running_event.is_set():
                self.app.print("stop")
                return False
            self.aim = self.get_aim()
            if not self.aim:
                self.app.close_app()
                time.sleep(10)
            else:
                print(self.aim)
                self.app.keep_screen(False)
                self.page = self.match()
                self.app.keep_screen(False)
                if self.page:
                    self.act()
                else:
                    self.page_other = self.match_other()
                    if self.page_other:
                        if not self.act_other():
                            self.app.print(f"其他界面超时")
                            self.err = self.Error
                    elif time.time() - self.t0 > self.timeout:
                        self.err += 1
                        self.app.print(f"未匹配界面{self.err}次")
                        self.app.location = self.app.get_location()
                        self.init_link()
                        self.t0 = time.time()
            time.sleep(self.sleep)
        self.app.screenshot(f"screenshot_{int(time.time())}.png")
        self.app.close_app()
        self.t0 = time.time()
        self.err = 0
        return self.run()

    def act(self):
        self.app.print(f"执行{self.page.__name__}")
        if self.aim and hasattr(self.page, self.aim):
            self.run_aim()
        elif "click" in dir(self.page):
            self.app.click_xy(*self.page.click)
        elif "action" in dir(self.page):
            self.page.action()
        self.link = self.page.link
        self.err = 0
        self.t0 = time.time()

    def act_other(self):
        self.app.print(f"执行其他-{self.page_other.__name__}")
        if "click" in dir(self.page_other):
            self.app.click_xy(*self.page_other.click)
        elif "action" in dir(self.page_other):
            self.page_other.action()
        if time.time() - self.t0 > 3 * 60:
            return False
        return True
        # self.t0 = time.time()
