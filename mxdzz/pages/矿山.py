import time
from main import app, state
from Libs import get_tomorrow_timestamp


class 矿山:
    points = [
        [179, 102, 0x362527],
        [118, 278, 0x2C1C1D],
        [798, 419, 0xFFFFFF],
    ]
    kgg = True
    gg = [
        [800, 245, 0x4570AC],
        [798, 197, 0xEAC26D],
        [798, 294, 0xEAC26D],
        [775, 245, 0x253D47],
    ]
    click = [419, 798]

    @classmethod
    def zdwk(cls):
        from zdwk import run

        def kgg():
            if points := app.find_multi_color_in_region(
                cls.gg, 85, [774, 60, 801, 390]
            ):
                points = app.clean_coordinates(points)
                [app.click_yx(*point) for point in points]
                cls.kgg = False

        if cls.kgg:
            kgg()
        if run():
            return
        else:
            kgg()
        state.set_state("zdwk", time.time() + 60 * app.config["wksz"]["jgsj"])
        cls.kgg = True

    link = ["家园", "矿山", "自动挖矿"]


class 自动挖矿:
    points = [
        [253, 177, 0x4E3626],
        [253, 198, 0xFCFCF3],
        [555, 212, 0xFFFFFF],
    ]
    获取资源 = [
        [462, 88, 0x82B535],
    ]
    看广告 = [
        [552, 190, 0x4671AD],
    ]

    @classmethod
    def zdwk(cls):
        if not app.is_multi_color(cls.获取资源):
            return app.click_xy(88, 462)
        if app.is_multi_color(cls.看广告):
            state.set_state("ggwk", get_tomorrow_timestamp())
        return app.click_xy(225, 550)

    click = [225, 700]
    link = ["自动挖矿", "矿山"]

