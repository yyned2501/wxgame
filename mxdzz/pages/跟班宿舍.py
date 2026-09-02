import time
from main import app, state
from libs.bark import bark


class 跟班宿舍:
    points = [
        [792, 56, 0xF8E8C2],
        [782, 240, 0xAA734D],
        [799, 403, 0xFFFFFF],
    ]
    战利品 = [231, 758]
    跟班管理 = [378, 628]
    gbgl_flag = True

    @classmethod
    def gbss(cls):
        if cls.gbgl_flag:
            cls.gbgl_flag = False
            return app.click_xy(*cls.跟班管理)
        app.click_xy(150, 725)
        cls.gbgl_flag = True

    click = [403, 799]

    link = ["家园", "跟班宿舍", "跟班管理", "战利品"]


class 战利品:
    points = [
        [224, 224, 0x9A6C4B],
        [283, 280, 0xE2C58E],
        [718, 309, 0xD7CBAD],
    ]
    在线战利品 = [
        [332, 90, 0xFCF8D5],
        [333, 249, 0x735039],
    ]
    领取 = [
        [714, 224, 0x4F6828],
        [716, 194, 0x6E9A2A],
    ]
    lx_flag = False

    @classmethod
    def gbss(cls):
        if app.is_multi_color(cls.领取):
            return app.click_xy(225, 714)
        else:
            if cls.lx_flag:
                state.set_state("gbss", time.time() + 3600 * app.config["gbsz"]["jgsj"])
        if app.is_multi_color(cls.在线战利品):
            cls.lx_flag = True
            return app.click_xy(308, 334)

    click = [403, 799]

    link = ["战利品", "跟班宿舍"]


class 跟班管理:
    points = [
        [164, 159, 0x4E3626],
        [163, 278, 0xDEC18F],
        [237, 353, 0xF7E8CE],
        [745, 226, 0xA72719],
    ]
    有跟班 = [
        [262, 191, 0xFFFAE9],
        [264, 188, 0xDACCBB],
        [265, 202, 0xFFFAE9],
        [269, 199, 0xFAF4E3],
    ]

    @classmethod
    def gbss(cls):
        if not app.is_multi_color(cls.有跟班):
            bark("跟班数量不足", "")
        app.click_xy(225, 745)

    click = [225, 745]

    link = ["跟班管理", "跟班宿舍"]
