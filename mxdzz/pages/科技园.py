import time
from main import app, state


class 科技园:
    points = [
        [201, 202, 0xAD4512],
        [203, 252, 0x3A715B],
        [795, 405, 0xFFFFFF],
    ]
    升级 = [
        [779, 185, 0x6E9B2A],
        [783, 267, 0x6E9B2A],
        [805, 257, 0x3F5D1C],
    ]

    @classmethod
    def zdkj(cls):
        if app.is_multi_color(cls.升级, 85):
            app.click_xy(225, 800)
            time.sleep(0.5)
            app.click_xy(346, 636)
        app.click_xy(150, 725)
        state.set_state("zdkj", time.time() + 60 * app.config["qtgn"]["zdkj"])

    click = [405, 795]

    link = ["家园", "科技园"]
