import time
from main import app, state


class 副本:
    points = [
        [87, 185, 0xFFDB66],
        [84, 170, 0xC44039],
        [804, 184, 0x8B1D1F],
    ]
    fb = None
    find_colors = {
        "syzm": [
            [344, 357, 0x6D9A2A],
            [216, 49, 0xF5F5F0],
            [206, 52, 0xD13948],
        ],
        "sdxt": [
            [482, 358, 0x6E9A2A],
            [427, 50, 0xF5A10A],
            [422, 44, 0xE0AA34],
        ],
        "blcx": [
            [619, 358, 0x6E9A2A],
            [564, 49, 0xF95E98],
            [552, 52, 0xD23948],
        ],
        "cygc": [
            [389, 358, 0x324D18],
            [333, 51, 0xEBF7FB],
            [328, 40, 0x4B9AA4],
        ],
        "ddsxt": [
            [523, 356, 0x6E9A2A],
            [471, 53, 0xF39E0B],
            [465, 53, 0x45969C],
        ],
        "fysd": [
            [527, 358, 0x6E9A2A],
            [469, 46, 0xE47E80],
            [465, 36, 0xEFB636],
        ],
        "hasl": [
            [526, 357, 0x6E9A2A],
            [462, 44, 0xE3AD3C],
            [470, 52, 0xF9F9FA],
        ],
    }
    cygcgg = [
        [341, 354, 0x4671AD],
        [292, 54, 0x47979F],
        [292, 42, 0x4ED7DC],
    ]
    # kgg = False
    kgg = [
        [609, 343, 0x1C3755],
        [609, 339, 0xE0DDE4],
        [609, 335, 0xFFFFFF],
        [615, 344, 0xFFFFFF],
        [553, 277, 0xFEFBE6],
    ]
    end = [
        [637, 181, 0x988D7F],
        [702, 16, 0xDAC47B],
        [648, 269, 0x968B7D],
        [589, 432, 0xDAC07F],
    ]
    last_gg_points = None

    @classmethod
    def zdfb(cls):
        zdfb = app.config["fbsz"]["zdfb"].copy()
        if "syzm" in zdfb:
            if state.get_sleep_time("syzm") > 0:
                del zdfb["syzm"]
            elif time.time() % 3600 // 60 > 19:
                del zdfb["syzm"]
        for fb in zdfb:
            if zdfb[fb]:
                if points := app.find_multi_color_in_region(cls.find_colors[fb], 90):
                    cls.fb = fb
                    cls.last_gg_points = None
                    return app.click_yx(*points[0])
        if points := app.find_multi_color_in_region(cls.kgg, 85):
            if cls.last_gg_points != app.clean_coordinates(points):
                cls.last_gg_points = app.clean_coordinates(points)
                for point in app.clean_coordinates(points):
                    print(point)
                    app.click_yx(*point)
                return
        cls.fb = None
        if not app.is_multi_color(cls.end):
            return app.scroll_xy(-8000, 225, 600)
        state.set_state("zdfb", time.time() // 3600 * 3600 + 3600)

    click = [184, 804]
    link = ["副本", "首页", "深渊之门", "副本入口", "护卫小队", "黑暗试炼"]


class 深渊之门:
    points = [
        [166, 157, 0x482F21],
        [168, 322, 0xE3C895],
        [691, 199, 0xFFFFFE],
        [766, 225, 0xA4271D],
    ]
    zdfb = [225, 700]
    click = [225, 767]
    link = ["深渊之门", "副本"]


class 黑暗试炼:
    points = [
        [105, 163, 0xFEFBA6],
        [111, 127, 0xEBDBBB],
        [645, 318, 0xFEFBE6],
        [777, 224, 0xA83520],
    ]
    mcs = [
        [456, 268, 0x6C6C6C],
    ]
    click_point = [258, 456]

    @classmethod
    def zdfb(cls):
        if app.is_multi_color(cls.mcs):
            state.set_state("zdfb", time.time() // 3600 * 3600 + 3600)
            return app.click_xy(*cls.click)
        app.click_xy(*cls.click_point)

    click = [225, 777]
    link = ["黑暗试炼", "副本"]


class 副本入口:
    points = [
        [200, 148, 0xB8CE79],
        [269, 336, 0xCB4438],
        [737, 225, 0xA3271D],
    ]
    # 有钥匙
    yys = [
        [641, 165, 0xFFFFFF],
        [638, 165, 0x4671AD],
        [638, 305, 0x6E9A2A],
    ]
    mcs = [
        [658, 231, 0x95A0B1],
        [658, 232, 0x1E365A],
        [658, 233, 0x98A3B4],
    ]

    @classmethod
    def zdfb(cls):
        app.keep_screen(True)
        if 副本.fb and not app.is_multi_color(cls.mcs):
            if not app.find_multi_color_in_region(cls.yys):
                return app.click_xy(225, 650)
            if app.config["fbsz"]["sdfb"][副本.fb]:
                return app.click_xy(162, 640)
            else:
                return app.click_xy(287, 640)
        return app.click_xy(*cls.click)

    click = [225, 737]
    link = ["副本入口", "副本"]


class 护卫小队:
    points = [
        [112, 323, 0xEBE4CA],
        [109, 135, 0xFFEA91],
        [798, 225, 0xB02713],
    ]
    sjpp = [
        [619, 136, 0x3D669E],
        [622, 92, 0x4470AC],
        [621, 168, 0xF6F7F9],
    ]
    zbzd = [
        [693, 311, 0xFBFBFB],
        [693, 269, 0x6F9B2A],
        [694, 346, 0xC1C8BB],
    ]

    @classmethod
    def zdfb(cls):
        app.keep_screen(True)
        if app.is_multi_color(cls.sjpp):
            return app.click_xy(137, 619)
        if app.is_multi_color(cls.zbzd):
            return app.click_xy(313, 695)

    click = [225, 800]
    link = ["护卫小队", "深渊之门", "副本"]
