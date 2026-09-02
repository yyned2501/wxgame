import time
import numpy as np
from main import app, state


class 家族:
    points = [
        [798, 29, 0xD1E77F],
        [799, 111, 0xF8A59C],
        [801, 186, 0xA9ACAD],
        [797, 260, 0xEAD4B9],
        [803, 334, 0x97211C],
        [793, 410, 0xF3A945],
    ]
    胖头鱼 = [
        [564, 425, 0x264864],
        [559, 428, 0x5B8C98],
        [557, 420, 0xC8EFED],
    ]
    山洞 = [
        [511, 49, 0xFFF342],
        [505, 49, 0x7F5E61],
        [509, 42, 0x503432],
    ]

    @classmethod
    def lysd(cls):
        if points := app.find_multi_color_in_region(cls.山洞, 85, [470, 30, 800, 225]):
            point = app.clean_coordinates(points, 30)[0]
            app.click_yx(*point)
        else:
            app.touch_move_xy(225, 450, 150, 450 + np.random.randint(-50, 50), 1.5)

    @classmethod
    def bmdy(cls):
        if points := app.find_multi_color_in_region(cls.胖头鱼, 85, [500, 225, 800, 430]):
            point = app.clean_coordinates(points, 30)[0]
            app.click_yx(*point)

        else:
            app.touch_move_xy(225, 450, 300, 450 + np.random.randint(-50, 50), 1.5)

    click = [335, 803]

    link = ["家族", "首页", "烈焰山洞"]


class 烈焰山洞:
    points = [
        [171, 160, 0x4E3626],
        [172, 308, 0xE1C592],
        [501, 301, 0xF6B988],
        [768, 224, 0xA62C1E],
    ]
    tz0 = [
        [682, 280, 0xF0AFA8],
        [684, 279, 0xE26556],
        [684, 278, 0xFEFCFB],
    ]

    @classmethod
    def lysd(cls):
        if app.is_multi_color(cls.tz0, 85):
            return app.click_xy(302, 509)
        return app.click_xy(225, 700)

    click = [225, 768]
    link = ["烈焰山洞", "熔岩宝箱", "家族"]


class 熔岩宝箱:
    points = [
        [161, 163, 0x482F20],
        [158, 310, 0xDFC391],
        [202, 308, 0xE7DEC1],
        [745, 225, 0xA7311E],
    ]
    gjbx = [
        [481, 293, 0x6E9A2A],
        [480, 351, 0x6E9A2A],
        [483, 320, 0xFFFFFF],
    ]
    cjbx = [
        [637, 318, 0x344C1F],
        [634, 273, 0x6E9A2A],
        [633, 359, 0x6E9A2A],
    ]

    @classmethod
    def lysd(cls):
        if app.is_multi_color(cls.gjbx, 85):
            return app.click_xy(320, 483)
        if app.is_multi_color(cls.cjbx, 85):
            return app.click_xy(318, 637)
        state.set_state("lysd", time.time() // 3600 * 3600 + 3600 + 55 * 60)

    click = [225, 768]
    link = ["烈焰山洞", "熔岩宝箱"]
