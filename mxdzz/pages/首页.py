import time
from Libs import get_tomorrow_timestamp
from main import app, state


class 首页:
    points = [
        [752, 18, 0xE1A864],
        [797, 34, 0xF8E092],
        [796, 186, 0xFFFFFE],
        [815, 266, 0xD48420],
        [815, 345, 0xFB7C4A],
    ]
    jthb = [20, 750]
    bmdy = [336, 806]
    lysd = [336, 806]
    zdfb = [185, 806]
    click = [261, 805]  # 进入家园

    @classmethod
    def zxjl(cls):
        state.set_state("zxjl", time.time() + 60 * 60 * app.config["qtgn"]["zxjl"])
        app.click_xy(411, 350)

    link = ["家园", "首页", "聊天", "家族", "副本"]


class 家园:
    points = [
        [743, 392, 0xF2F2F4],
        [704, 76, 0xF9DBA9],
        [160, 386, 0xF6D15C],
    ]
    click = [261, 805]
    zdtc = [146, 542]
    zdsc = [146, 542]
    zdkj = [385, 176]
    zdwk = [127, 182]
    zdcw = [369, 388]
    cwqd = [369, 388]
    gbss = [385, 578]
    link = ["首页", "庄园", "科技园", "矿山", "姑姑车位", "跟班宿舍"]


class 聊天:
    points = [
        [733, 44, 0xD0CCB5],
        [727, 57, 0x744D3A],
        [744, 48, 0xD0CCB5],
        [753, 64, 0x744D3A],
    ]
    有红包 = [
        [631, 58, 0xD41F0A],
        [644, 48, 0xFCAA53],
        [655, 36, 0xFE4546],
    ]
    游荡哥布林 = [
        [148, 318, 0xFCEFBB],
        [155, 326, 0xD4B472],
        [124, 321, 0x68B052],
        [112, 298, 0x63AD4C],
    ]
    助力 = [
        [536, 367, 0xFFFFFF],
        [537, 335, 0x6E9A2A],
        [537, 415, 0x6E9A2A],
    ]
    选中家族 = [
        [537, 38, 0xFFFFFF],
        [538, 40, 0x67594F],
        [550, 39, 0xFCFBFB],
        [554, 39, 0xDBCCAE],
    ]
    家族 = [
        [528, 40, 0x564432],
        [530, 33, 0x544231],
        [534, 66, 0x544231],
        [538, 67, 0x77654E],
        [536, 54, 0xA39277],
    ]
    click = [261, 805]

    @classmethod
    def jthb(cls):
        app.keep_screen(True)
        if points := app.find_multi_color_in_region(
            cls.游荡哥布林, 85, [100, 0, 200, 450]
        ):
            return app.click_yx(*points[0])
        if app.config["qtgn"]["xyzp"]:
            if state.get_sleep_time("xyzp") == 0:
                return app.click_xy(22, 144)
        if app.config["qtgn"]["zdzl"]:
            if app.find_multi_color_in_region(cls.选中家族, 85):
                if points := app.find_multi_color_in_region(
                    cls.助力, 85, [440, 335, 715, 420]
                ):
                    return app.click_yx(*points[0])
            else:
                if points := app.find_multi_color_in_region(
                    cls.家族, 85, [440, 30, 715, 80]
                ):
                    return app.click_yx(*points[0])
        if app.is_multi_color(cls.有红包, 85):
            return app.click_xy(48, 644)
        if state.get_sleep_time("jthb") == 0:
            return app.click_xy(48, 644)
        time.sleep(2)

    link = ["家园", "首页", "聊天", "红包列表", "首页菜单"]


class 首页菜单:
    points = [
        [114, 47, 0x805842],
        [223, 12, 0xEEDAB4],
        [268, 44, 0xDA634C],
        [289, 77, 0x583F30],
    ]
    zp = [
        [590, 44, 0xADBAC2],
        [581, 48, 0xFBDD7D],
        [593, 28, 0xCB8841],
    ]

    @classmethod
    def action(cls):
        if state.get_sleep_time("xyzp") == 0:
            if points := app.find_multi_color_in_region(cls.zp, 85, [241, 21, 690, 80]):
                return app.click_yx(*points[0])
        return app.click_xy(48, 113)

    link = ["聊天", "首页菜单", "首页", "幸运转盘"]


class 幸运转盘:
    points = [
        [124, 180, 0xFEFCCD],
        [129, 279, 0xFEF8A0],
        [340, 223, 0x9EACB7],
        [332, 381, 0xFEF8A1],
    ]

    ljcj = [
        [540, 275, 0xD41E09],
        [556, 270, 0x6E9B2A],
    ]
    mfgg = [
        [559, 213, 0xFEFEFE],
        [540, 275, 0xD41E09],
    ]
    mtzl = [
        [559, 213, 0xFEFEFE],
        [540, 275, 0x6E9B2A],
    ]

    @classmethod
    def action(cls):
        app.keep_screen(True)
        for colors in [cls.ljcj, cls.mfgg]:
            if app.is_multi_color(colors, 85):
                app.click_xy(225, 555)
                state.set_state("xyzp", time.time() + 5 * 60)
                return time.sleep(2)

        if app.is_multi_color(cls.mtzl, 85):
            state.set_state("xyzp", get_tomorrow_timestamp())
        return app.click_xy(225, 685)

    link = ["聊天", "首页菜单", "幸运转盘"]


class 红包列表:
    points = [
        [170, 202, 0xFD4242],
        [141, 234, 0xFF6651],
        [698, 373, 0xCC6742],
        [760, 227, 0x931B09],
    ]
    红包 = [
        [312, 93, 0xF5C369],
        [312, 105, 0xF5BC58],
        [320, 89, 0x924C19],
        [329, 111, 0xFAF9FB],
    ]
    我的红包 = [
        [698, 325, 0xD41F0A],
        [701, 325, 0xD41F0A],
    ]
    click = [225, 760]
    # zdsc = [225, 760]

    @classmethod
    def jthb(cls):
        state.set_state("jthb", time.time() + 5 * 60)
        if points := app.find_multi_color_in_region(cls.红包, 85):
            app.click_yx(*points[0])
            time.sleep(0.5)
            app.click_xy(225, 760)
        elif app.is_multi_color(cls.我的红包, 85):
            app.click_xy(285, 708)
        else:
            app.click_xy(225, 760)

    link = ["聊天", "红包列表", "红包详情"]


class 红包详情:
    points = [
        [416, 202, 0xFA5F8F],
        [310, 322, 0xEBDFB7],
        [415, 310, 0xF67962],
        [706, 241, 0xF25853],
    ]
    click = [225, 760]
    link = ["红包列表"]
