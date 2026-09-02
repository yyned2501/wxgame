import time
from main import app, state
from slide import get_slide_pix


class 挂机:
    points = [
        [684, 143, 0xBCB9B6],
        [549, 192, 0x000000],
        [430, 200, 0xFFDF80],
    ]

    @classmethod
    def action(cls):
        app.touch_move_xy(70, 620, 390, 620)


class 偷菜成功:
    points = [
        [309, 145, 0xCB4538],
        [302, 184, 0xFFDE77],
        [296, 237, 0xFFED92],
        [336, 343, 0xCB4538],
    ]
    click = [225, 730]


class 快速挑战:
    points = [
        [167, 177, 0x482F21],
        [168, 239, 0xFDFDF4],
        [274, 344, 0xFEFBE6],
        [750, 225, 0xA4271D],
        [674, 194, 0x6E9A2A],
    ]
    click = [225, 670]


class 失败:
    points = [
        [223, 192, 0xD5E8FB],
        [248, 240, 0x465BB2],
        [332, 354, 0xF6F7F9],
        [406, 352, 0x6F9C2C],
    ]
    click = [225, 730]


class 胜利:
    points = [
        [295, 192, 0xFEF293],
        [302, 174, 0xCB4538],
        [271, 241, 0xE7C945],
    ]
    click = [225, 730]


class 限时礼包:
    points = [
        [572, 215, 0xFFFFFF],
        [562, 238, 0xDA9F63],
        [502, 264, 0x6E9B2A],
        [488, 325, 0xE3C08C],
    ]
    click = [225, 730]


class 游荡哥布林:
    points = [
        [412, 149, 0x825A3C],
        [418, 251, 0xFFF88A],
        [700, 224, 0xAF2712],
    ]
    click = [225, 615]


class 获得奖励:
    points = [
        [200, 168, 0xFFF2B0],
        [211, 156, 0xD24532],
        [210, 258, 0xFEDF77],
        # [249, 334, 0xFFE276],
    ]
    click = [225, 615]


class 获得奖励2:
    points = [
        [280, 159, 0xFFFCAC],
        [278, 205, 0xFFFFB2],
        [294, 287, 0xFCD65B],
        [312, 330, 0xE6C685],
    ]
    click = [225, 615]


class 获得奖励3:
    points = [
        [229, 152, 0xFFF883],
        [225, 174, 0xFEE283],
        [227, 248, 0xFEE283],
        [253, 311, 0xDF5D50],
    ]
    click = [225, 650]


class 获得奖励4:
    points = [
        [184, 152, 0x8E2220],
        [174, 174, 0xFEE890],
        [207, 309, 0xD9563E],
    ]
    click = [225, 800]


class 获得奖励5:
    points = [
        [258, 154, 0xFFEDAD],
        [256, 292, 0xFFF6B0],
        [271, 311, 0xCB4538],
    ]
    click = [225, 800]


class 公告:
    points = [
        [176, 195, 0x5C3F2E],
        [172, 237, 0xF7F3DD],
        [739, 244, 0xF0E3BC],
        [736, 229, 0xA62E1C],
    ]
    click = [228, 738]


class 公告2:
    points = [
        [200, 184, 0x462C21],
        [201, 263, 0x4E3126],
        [738, 224, 0xA83821],
        [201, 231, 0xFFFCE5],
    ]
    click = [228, 738]


class 离线奖励:
    points = [
        [623, 287, 0xD3C6A9],
        [625, 141, 0xD3C7AA],
        [649, 140, 0x9DA8B7],
        [654, 339, 0x6E9A2A],
    ]

    @classmethod
    def action(cls):
        app.click_xy(150, 653)
        app.click_xy(300, 653)


class 异地登录:
    points = [
        [298, 194, 0x4E3626],
        [299, 288, 0x4E3626],
        [505, 323, 0xD6C6A5],
        [504, 221, 0xFFFFFF],
    ]

    @classmethod
    def action(cls):
        app.close_app()
        t = app.config["qtgn"]["sbct"]
        app.print(f"等待{t}分钟")
        time.sleep(60 * t)


class 停服维护:
    points = [
        [366, 230, 0x2D2F2E],
        [502, 171, 0x6E9A2A],
        [506, 276, 0x4570AC],
    ]

    @classmethod
    def action(cls):
        t = app.config["qtgn"]["sbct"]
        app.print(f"等待{t}分钟")
        time.sleep(60 * t)
        app.click_xy(309, 508)


class 战斗画面:
    points = [
        [435, 9, 0xBD9671],
        [450, 347, 0xFAEACD],
        [516, 361, 0xEFDCC2],
        [683, 351, 0xF7E9CD],
    ]
    逃跑 = [
        [681, 215, 0xFCFAFA],
        [686, 230, 0xFAF8F8],
        [693, 235, 0xFFFFFF],
    ]
    跳过 = [
        [683, 209, 0xFFFFFF],
        [681, 232, 0xFFFFFF],
        [693, 242, 0xFFFFFF],
    ]

    @classmethod
    def action(cls):
        if app.is_multi_color(cls.跳过, 85):
            return app.click_xy(225, 687)


class 讨伐贡献:
    points = [
        [151, 169, 0x4E3626],
        [145, 225, 0xFFFFFF],
        [701, 270, 0xD2C7A9],
        [733, 227, 0xA5271E],
    ]
    click = [225, 733]


class 深渊之门战斗:
    points = [
        [793, 106, 0xFBEBD3],
        [59, 267, 0xFFFFFF],
        [817, 259, 0xC4413A],
    ]

    @classmethod
    def action(cls):
        time.sleep(1)


class 残垣古城:
    points = [
        [732, 42, 0xE19627],
        [816, 193, 0xC4413A],
        [817, 311, 0xF9EACE],
    ]

    @classmethod
    def action(cls):
        time.sleep(1)


class 征战熔岩巨兽:
    points = [
        [66, 226, 0x6A7E81],
        [117, 42, 0x1965D7],
        [103, 146, 0xFFFFFF],
        [643, 278, 0xFAE8D0],
        [689, 255, 0xC4413A],
    ]

    @classmethod
    def action(cls):
        time.sleep(1)


class 讨伐结束:
    points = [
        [269, 149, 0xCD4635],
        [258, 177, 0xFEF199],
        [273, 304, 0xF4E8EB],
    ]

    @classmethod
    def action(cls):
        state.set_state(
            "syzm", (time.time() + 8 * 3600) // 3600 // 24 * 3600 * 24 + 16 * 3600
        )
        app.click_xy(225, 520)


class 报名打鱼:
    points = [
        [152, 150, 0x4E3626],
        [150, 308, 0xE5C484],
        [472, 360, 0xF7E9AF],
        [736, 224, 0xA62A19],
        [334, 316, 0xE46939],
    ]
    bmdy = [
        [628, 233, 0xFFFFFF],
        [628, 172, 0x6F9B2A],
        [637, 253, 0x6F9A2A],
    ]

    @classmethod
    def action(cls):
        if app.is_multi_color(cls.bmdy, 85):
            return app.click_xy(225, 628)
        state.set_state(
            "bmdy", (time.time() + 8 * 3600) // 3600 // 12 * 3600 * 12 + 10 * 3600
        )  # 东八区的6点 18-8
        return app.click_xy(225, 737)


class 滑块验证:
    points = [
        [304, 43, 0x95794F],
        [326, 77, 0x544231],
        [560, 84, 0xFCEBA9],
    ]

    @classmethod
    def action(cls):
        img_arr = app.capture()
        pix = get_slide_pix(img_arr)
        x1 = 292 / 248 * pix + 60
        move = [60, 560, x1, 560]
        app.touch_move_xy(*move)


class 奖励说明:
    points = [
        [300, 189, 0x4E3626],
        [300, 284, 0x4E3626],
        [506, 199, 0x6E9A2A],
    ]

    click = [225, 505]


class 停车提示:
    points = [
        [300, 138, 0x4E3626],
        [303, 301, 0x462C25],
        [508, 340, 0x6E9A2A],
        [509, 111, 0xC4413A],
    ]

    click = [309, 505]


class 网络连接失败:
    points = [
        [383, 216, 0xF5EACC],
        [493, 177, 0x6E9B2A],
        [490, 332, 0x4570AD],
        [734, 423, 0x1397DB],
    ]

    click = [304, 492]
