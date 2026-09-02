import datetime
import time
import pytesseract
import numpy as np
from main import app, state
from Libs import get_tomorrow_timestamp


def get_aim():
    methods = {
        "zdfb": ["zdfb"],
        "bmdy": ["bmdy"],
        "lysd": ["lysd"],
        "zdcw": ["zdcw", "cwsc"],
        "cwqd": ["cwqd"],
        "zdwk": ["zdwk"],
        "zdkj": ["zdkj"],
        "jthb": ["jthb"],
        "zxjl": ["zxjl"],
    }
    if app.config["gnsz"]["zdsc"]:
        if state.shoucai_sleep_time == 0:
            return "zdsc"
    if app.config["gnsz"]["zdtc"]:
        if state.toucai_sleep_time == 0:
            return "zdtc"
    for method in methods:
        if app.config["gnsz"][method]:
            for state_key in methods[method]:
                if state.get_sleep_time(state_key) == 0:
                    return method

    if app.config["gnsz"]["zxjl"]:
        if app.config["gnsz"]["jthb"]:
            return "jthb"


class 首页:
    points = [
        [137, 19, 0xF5E3C0],
        [746, 21, 0x80674C],
        [801, 184, 0xFEFEFC],
        [808, 338, 0xCF9F5E],
    ]
    jthb = [20, 750]
    bmdy = [336, 806]
    lysd = [336, 806]
    zdfb = [185, 806]
    click = [261, 805]  # 进入家园

    @classmethod
    def zxjl(cls):
        state.set_state("zxjl", time.time() + 60 * 60 * app.config["qtgn"]["zxjl"])
        app.click_xy(225, 350)

    link = ["家园", "首页", "聊天", "家族", "副本"]


class 家园:
    points = [
        [804, 259, 0x8B1D1F],
        [750, 137, 0x46C3C3],
        [704, 73, 0xFADBAA],
    ]
    click = [261, 805]
    zdtc = [146, 542]
    zdsc = [146, 542]
    zdkj = [385, 176]
    zdwk = [127, 182]
    zdcw = [369, 388]
    cwqd = [369, 388]
    link = ["首页", "庄园", "科技园", "矿山", "姑姑车位"]


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
    获取资源 = [[ 462,  88,0x82b535],]
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
        if points := app.find_multi_color_in_region(cls.游荡哥布林, 85, [100, 0, 200, 450]):
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


class 庄园:
    points = [
        [63, 14, 0x985925],
        [68, 417, 0x3C6A77],
        [60, 311, 0xE3C48B],
        [802, 395, 0xFFFFFF],
        [804, 219, 0xF0CC8A],
        [798, 128, 0x9DB960],
    ]
    zhaicai = [
        [618, 365, 0x704B42],
        [589, 360, 0xED6D53],
        [588, 369, 0xE0CF9F],
        [595, 377, 0x3A1C0E],
    ]
    shoucai = [
        [618, 365, 0x704B42],
        [583, 343, 0xFFF9A2],
        [577, 352, 0xC14B2B],
        [577, 373, 0xFEEDCB],
    ]
    zhongcai = [
        [618, 365, 0x704B42],
        [602, 366, 0x976734],
        [580, 377, 0x7DBF0B],
        [592, 359, 0xFEEDCA],
    ]

    zz_regions = {
        "cj": [105, 45, 119, 85],
        "gj": [105, 155, 119, 189],
        "tj": [105, 262, 119, 295],
    }

    @classmethod
    def yzz(cls):
        zzsl = cls.get_zzsl()
        app.print(
            f"剩余：初级种子{(cj := zzsl['cj']//100)}，高级种子{(gj:=zzsl['gj'])}，特级种子{(tj:=zzsl['tj'])}"
        )
        if cj > 0:
            return True
        if gj > 0:
            return True
        if tj > app.config["scsz"]["tjzz"]:
            return True
        return False

    @classmethod
    def get_zzsl(cls) -> dict[str, int]:
        ret = {}
        for zz in cls.zz_regions:
            region = cls.zz_regions[zz]
            img = app.region_img_b(region, reverse=True)
            zzsl = pytesseract.image_to_string(
                img,
                lang="eng",
                config="--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789",
            ).strip()
            try:
                ret[zz] = int(zzsl)
            except:
                app.region_img(region).save(f"{zz}_o.png")
                img.save(f"{zz}.png")
                ret[zz] = 0
        return ret

    @classmethod
    def action(cls):
        if app.config["gnsz"]["zdsc"]:
            app.keep_screen(True)
            for colors in [cls.zhaicai, cls.shoucai]:
                if points := app.find_multi_color_in_region(colors, 85):
                    for point in app.clean_coordinates(points):
                        app.click_yx(*point)
                    if colors == cls.zhaicai:
                        time.sleep(6)
                    return True
        return app.click_xy(392, 809)

    @classmethod
    def zdsc(cls):
        app.keep_screen(True)
        if points := app.find_multi_color_in_region(cls.zhaicai, 85):
            # 摘菜
            for point in app.clean_coordinates(points):
                app.click_yx(*point)
            return time.sleep(6)
        if points := app.find_multi_color_in_region(cls.shoucai, 85):
            # 收菜
            for point in app.clean_coordinates(points):
                app.click_yx(*point)
            return time.sleep(3)
        points = app.find_multi_color_in_region(cls.zhongcai, 85)
        if points:
            points = app.clean_coordinates(points)
        t = time.time()
        if t < state.state["mzz"]:
            if points:
                for point in app.clean_coordinates(points):
                    i = cls.init_zctd(point)
                    state.state["zhongcai"][i] = state.state["mzz"]
            state.save()
        else:
            if points:
                app.click_yx(*points[0])
                cls.init_zctd(points[0])
                return
        for i, sc_time in enumerate(state.state["zhongcai"]):
            if sc_time <= t:
                app.print(f"第{i+1}块地历史数据出错，1分钟后检查收菜")
                state.state["zhongcai"][i] = t + 60
        state.save()

    @classmethod
    def zdtc(cls):
        偷菜.scroll_n = 0
        好友偷菜.scroll_n = 0
        偷菜.del_sctc()
        好友偷菜.del_sctc()
        if app.config["tcsz"]["tcrk"]["cr"]:
            app.click_xy(221, 809)
        elif app.config["tcsz"]["tcrk"]["hy"]:
            app.click_xy(136, 805)
        else:
            app.print("未选择偷菜，自动全选，先查找仇人列表")
            app.click_xy(221, 809)

    @staticmethod
    def init_zctd(point):
        x = (point[0] - 475) // 139
        y = (point[1] - 85) // 136
        zctd = int(x * 3 + y)
        state.set_state("zctd", zctd)
        return zctd

    link = ["庄园", "种菜", "偷菜", "好友偷菜", "家园", "首页"]


class 种菜:
    points = [
        [304, 180, 0x4E3626],
        [300, 190, 0xFCFCF3],
        [512, 317, 0xD7CBAD],
        [376, 365, 0xEBE5CB],
    ]
    作物 = {
        "白菜": [
            [457, 255, 0x67A63E],
            [455, 250, 0xE7CB8E],
            [473, 248, 0xA7D391],
        ],
        "茄子": [
            [606, 91, 0x81AD3C],
            [609, 95, 0x31481E],
            [609, 100, 0x81AA49],
            [601, 91, 0xD2A063],
        ],
        "葫芦": [
            [619, 234, 0xAB8169],
            [601, 224, 0x46AA5F],
            [614, 233, 0x32794A],
            [606, 230, 0x396F48],
        ],
    }
    xztjzz = [
        [382, 318, 0xFEEA95],
        [432, 318, 0xFEEA95],
        [407, 293, 0xFEEA95],
        [407, 343, 0xFEEA95],
    ]
    没种子 = [
        [522, 201, 0x6C6C6C],
        [507, 229, 0x6C6C6C],
        [523, 273, 0x686867],
    ]

    @classmethod
    def action(cls):
        app.click_xy(117, 417)
        time.sleep(0.5)
        if (not app.config["scsz"]["tjzz"]) and app.is_multi_color(cls.xztjzz, 85):
            state.set_state(
                "mzz", min([time.time() + 60 * 60, get_tomorrow_timestamp()])
            )
            app.click_xy(225, 700)
            return
        app.click_xy(225, 522)
        time.sleep(0.5)
        if app.is_multi_color(cls.没种子, 85):
            state.set_state(
                "mzz", min([time.time() + 60 * 60, get_tomorrow_timestamp()])
            )
            app.click_xy(225, 700)
            return
        state.set_state("zcsj", time.time())
        time.sleep(3 + 5 / (1 + app.config["scsz"]["czjc"]))
        cls.check_zw()

    @classmethod
    def check_zw(cls):
        zctd = state.get_state("zctd")
        x = zctd // 3
        y = zctd % 3
        region = [440 + x * 139, 20 + y * 136, 579 + x * 139, 156 + y * 136]
        for i, zw in enumerate(cls.作物):
            if app.find_multi_color_in_region(cls.作物[zw], 85, region):
                app.print(f"种了{zw}")
                state.add_scsj(i, app)
                return True

    link = ["庄园", "种菜"]


class 偷菜:
    points = [
        [126, 212, 0xFFEC79],
        [797, 227, 0xFAEBB1],
        [814, 133, 0xF3E3C3],
    ]
    有菜偷 = [
        [332, 382, 0x281A15],
        [318, 267, 0x869EBB],
        [335, 264, 0xE0CF9F],
    ]
    scroll_n = 0

    @classmethod
    def del_sctc(cls):
        if hasattr(cls, "sctc"):
            del cls.sctc

    @classmethod
    def action(cls):
        if hasattr(cls, "sctc"):
            region = [cls.sctc[0] + 10, 0, app.location[3], app.location[2]]
        if points := app.find_multi_color_in_region(
            cls.有菜偷, 85, region if hasattr(cls, "sctc") else None
        ):
            # 摘菜
            app.click_yx(*points[0])
            state.set_state("tcrk", "cr")
            cls.sctc = points[0]
        else:
            if cls.scroll_n < app.config["tcsz"]["fycs"]["cr"]:
                cls.del_sctc()
                app.scroll_xy(-12000, 225, 600)
                cls.scroll_n += 1
            else:
                if app.config["tcsz"]["tcrk"]["hy"]:
                    app.click_xy(136, 805)
                elif app.config["tcsz"]["tcrk"]["cr"]:
                    app.click_xy(221, 809)
                    app.print("没找到菜，30秒后使用备用方案重试")
                    state.add_toucai(0.1)
                    别人家.bypz = time.time()
                else:
                    app.print("未选择偷菜，自动全选，先查找仇人列表")
                    app.click_xy(221, 809)
                cls.scroll_n = 0

    link = ["偷菜", "别人家", "好友偷菜"]


class 好友偷菜:
    points = [
        [119, 186, 0xCB4538],
        [125, 215, 0xFFDE77],
        [711, 239, 0xEFE3C4],
        [729, 253, 0x7E5132],
    ]

    有菜偷 = [
        [332, 382, 0x281A15],
        [318, 267, 0x869EBB],
        [335, 264, 0xE0CF9F],
    ]
    scroll_n = 0

    click = [392, 809]

    @classmethod
    def del_sctc(cls):
        if hasattr(cls, "sctc"):
            del cls.sctc

    @classmethod
    def zdtc(cls):
        if hasattr(cls, "sctc"):
            region = [cls.sctc[0] + 10, 0, app.location[3], app.location[2]]
        if points := app.find_multi_color_in_region(
            cls.有菜偷, 85, region if hasattr(cls, "sctc") else None
        ):
            # 摘菜
            app.click_yx(*points[0])
            cls.sctc = points[0]
            state.set_state("tcrk", "hy")
        else:
            if cls.scroll_n < app.config["tcsz"]["fycs"]["hy"]:
                cls.del_sctc()
                app.scroll_xy(-12000, 225, 600)
                cls.scroll_n += 1
            else:
                app.click_xy(136, 805)
                app.print("没找到菜，30秒后使用备用方案重试")
                state.add_toucai(0.1)
                别人家.bypz = time.time()
                cls.scroll_n = 0

    link = ["别人家", "好友偷菜"]


class 别人家:
    points = [
        [58, 110, 0xAA805F],
        [817, 400, 0xEDB425],
        [813, 321, 0xCFD7CA],
        [776, 34, 0x836030],
    ]
    偷菜 = [
        [619, 233, 0x6D473F],
        [580, 245, 0x220A04],
        [580, 239, 0x869EBB],
        [594, 225, 0xA27A44],
    ]
    偷葫芦 = [
        [618, 365, 0x704B42],
        [629, 364, 0xB99235],
        [606, 368, 0xFEEDCB],
        [594, 364, 0xE0CF9F],
    ]
    偷茄子 = [
        [480, 378, 0x6D473F],
        [491, 380, 0x81B141],
        [461, 389, 0xFEEDC8],
        [454, 379, 0xE0CF9F],
    ]
    bypz = 0
    click = [391, 811]

    @classmethod
    def zdtc(cls):
        if state.toucai_sleep_time == 0:
            tcpz = app.config["tcsz"]["tcpz"]
            bypz = app.config["tcsz"]["bypz"]
            t = time.time()
            if tcpz["hl"] or (t - cls.bypz < 120 and bypz["hl"]):
                if points := app.find_multi_color_in_region(
                    cls.偷葫芦, 85, [400, 0, 700, 450]
                ):
                    return app.click_yx(*points[0])
            if tcpz["qz"] or (t - cls.bypz < 120 and bypz["qz"]):
                if points := app.find_multi_color_in_region(
                    cls.偷茄子, 85, [400, 0, 700, 450]
                ):
                    return app.click_yx(*points[0])
            if tcpz["bc"] or (t - cls.bypz < 120 and bypz["bc"]):
                if points := app.find_multi_color_in_region(
                    cls.偷菜, 85, [400, 0, 700, 450]
                ):
                    return app.click_yx(*points[0])
            app.print("未找到指定类别的菜，查找下一个")
            match state.get_state("tcrk"):
                case "cr":
                    app.click_xy(221, 809)
                case "hy":
                    app.click_xy(136, 805)
                case _:
                    app.click_xy(391, 811)
        else:
            app.click_xy(391, 811)

    link = ["庄园", "别人家", "偷菜详情", "偷菜", "好友偷菜"]


class 偷菜详情:
    points = [
        [312, 211, 0xBDB4A8],
        [353, 226, 0xD4C6A5],
        [620, 254, 0x6E9B2A],
        [618, 225, 0x324C17],
    ]
    作物 = {
        "白菜": [
            [386, 92, 0x8C519D],
        ],
        "茄子": [
            [386, 92, 0xCA9F27],
        ],
        "葫芦": [
            [386, 92, 0xB96B1F],
        ],
    }
    click_point = [225, 616]

    @classmethod
    def action(cls):
        if state.toucai_sleep_time == 0:
            for i, zw in enumerate(cls.作物):
                if app.is_multi_color(cls.作物[zw], 85):
                    app.click_xy(*cls.click_point)
                    app.print(f"偷{zw}")
                    state.add_toucai(i + 1)
                    return True
            app.click_xy(*cls.click_point)
            app.print(f"未能匹配偷取作物15分钟后再次偷菜")
            state.add_toucai(i + 1)
        else:
            app.print("历史数据出错，1分钟后重试")
            state.add_toucai(0.2)
            app.click_xy(225, 700)

    link = ["偷菜", "别人家"]


class 姑姑车位:
    points = [
        [800, 50, 0xF8E3CD],
        [800, 130, 0xCD9845],
        [800, 230, 0x498ED6],
        [800, 310, 0xD5AE9C],
        [800, 400, 0xFFFFFF],
    ]
    列表缩进 = [
        [208, 4, 0x724D39],
        [205, 8, 0xF4DFC1],
        [203, 14, 0x724C39],
    ]
    一号停车 = [[249, 76, 0xE8DCC4]]
    五号停车 = [
        [230, 375, 0xE8DEC1],
    ]
    攻击下降 = [
        [134, 267, 0xFFFFFF],
        [142, 276, 0xFFFFFF],
        [147, 255, 0xFAEED6],
    ]
    掠夺失败 = [
        [132, 270, 0xDDD5EA],
        [134, 277, 0xDDD5EA],
        [143, 263, 0x1C1637],
    ]
    check_color = [
        [385, 22, 0xFDF9C0],
        [391, 15, 0xC306],
        [401, 19, 0xA1BAC1],
        [409, 20, 0xC47118],
    ]
    tstc = False

    @staticmethod
    def next_time(n):
        now = time.time() + 8 * 60 * 60  # +UTC+8
        time_delta = 60 * 60 * n
        t = (now // time_delta + 1) * time_delta - 8 * 60 * 60  # -UTC+8
        return t

    @classmethod
    def zdcw(cls):
        if app.is_multi_color(cls.列表缩进, 85):
            app.click_xy(6, 208)
            return
        if state.get_sleep_time("cwsc") == 0:
            if app.is_multi_color(cls.一号停车, 85):
                app.click_xy(44, 209)
            else:
                state.set_state("cwsc", cls.next_time(app.config["cwsz"]["scsj"]))
                state.set_state("zdcw", 0)
                cls.tstc = False
            return
        if state.get_sleep_time("zdcw") == 0:
            if not app.is_multi_color(cls.一号停车, 85) and not cls.tstc:
                app.scroll_xy(12000, 225, 600)
                app.keep_screen(True)
                for i in range(4):
                    if not app.is_multi_color(好友车场.time_color_list[i]):
                        cls.tstc = True
                        return app.click_xy(*好友车场.cw_point[i])
            if not app.is_multi_color(cls.五号停车, 85):
                好友车场.top = False
                app.click_xy(225, 805)
            else:
                state.set_state("zdcw", time.time() + app.config["cwsz"]["jtjg"] * 60)
            return

    @classmethod
    def cwqd(cls):
        if app.is_multi_color(cls.攻击下降, 85) or app.is_multi_color(cls.掠夺失败, 85):
            state.set_state("cwqd", time.time() + 5 * 60)
            app.print("还在惩罚时间，5分钟后重试")
        else:
            好友车场.top = False
            app.click_xy(225, 805)

    click = [400, 800]
    link = ["姑姑车位", "家园", "停车收益", "好友车位", "停车管理"]


class 停车收益:
    points = [
        [154, 100, 0x354064],
        [271, 287, 0x7B5231],
        [660, 348, 0x6E9A2A],
    ]

    click = [308, 664]
    link = ["停车收益"]


class 好友车位:
    points = [
        [111, 170, 0xFFE98C],
        [119, 324, 0xE8DDC0],
        [803, 226, 0xA2261D],
        [700, 74, 0xAE5226],
    ]
    前往好友 = [
        [190, 384, 0x4A95E0],
        [196, 366, 0xF5B270],
        [203, 388, 0xB57D5B],
        [218, 391, 0xEF707E],
    ]
    爆满 = [
        [349, 50, 0x8F3900],
        [356, 39, 0x753900],
        [357, 51, 0xF7D05C],
    ]
    scroll_n = 0
    region = [155, 353, 667, 418]

    @classmethod
    def del_scqw(cls):
        if hasattr(cls, "scqw"):
            del cls.scqw

    zdcw = [176, 711]
    # @classmethod
    # def zdcw(cls):
    #     app.keep_screen(True)
    #     eregion = cls.region.copy()
    #     if hasattr(cls, "scqw"):
    #         eregion[0] = cls.scqw[0] + 10

    #     if points := app.find_multi_color_in_region(cls.前往好友, 85, region):
    #         for point in app.clean_coordinates(points):
    #             y = point[0]
    #             if not app.find_multi_color_in_region(
    #                 cls.爆满, 85, [y - 20, 35, y + 10, 55]
    #             ):
    #                 cls.scqw = point
    #                 return app.click_yx(*point)
    #     cls.del_scqw()
    #     app.scroll_xy(-12000, 225, 600)

    @classmethod
    def cwqd(cls):
        app.keep_screen(True)
        region = cls.region.copy()
        if hasattr(cls, "scqw"):
            region[0] = cls.scqw[0] + 10

        if points := app.find_multi_color_in_region(cls.前往好友, 85, region):
            for point in app.clean_coordinates(points):
                cls.scqw = point
                return app.click_yx(*point)
        if cls.scroll_n > 10:
            app.print("没找到车位，30秒后抢夺备用时间。")
            t = time.time() + 30
            好友车场.bysc = t
            state.set_state("cwqd", t)
            cls.scroll_n = 0
        else:
            cls.del_scqw()
            app.scroll_xy(-12000, 225, 600)
            cls.scroll_n += 1

    click = [391, 809]
    link = ["姑姑车位", "好友车场", "好友车位", "搜索车位"]


class 搜索车位:
    points = [
        [119, 148, 0xC24238],
        [113, 204, 0xFFE383],
        [711, 177, 0xFCFCFC],
        [804, 227, 0x8B1D1F],
    ]
    前往好友 = [
        [260, 382, 0xFBFBF9],
        [277, 369, 0xBA8562],
        [284, 390, 0xEE717E],
    ]
    爆满 = [
        [354, 38, 0x963B00],
        [355, 45, 0xE9C152],
        [355, 55, 0xF0C957],
    ]
    scroll_n = 0
    region = [155, 353, 667, 418]
    收藏车位 = [
        [480, 190, 0xFFFFFF],
        [475, 212, 0xFCFBFB],
        [479, 259, 0x9A8571],
        [486, 254, 0xFEFEFE],
    ]

    @classmethod
    def del_scqw(cls):
        if hasattr(cls, "scqw"):
            del cls.scqw

    @classmethod
    def zdcw(cls):
        app.keep_screen(True)
        if points := app.find_multi_color_in_region(cls.收藏车位, 85, [180, 189, 496, 260]):
            return app.scroll_xy(-3000, 225, 600)

        region = cls.region.copy()
        if hasattr(cls, "scqw"):
            region[0] = cls.scqw[0] + 10

        if points := app.find_multi_color_in_region(cls.前往好友, 85, region):
            for point in app.clean_coordinates(points):
                y = point[0]
                if not app.find_multi_color_in_region(
                    cls.爆满, 85, [y - 20, 35, y + 10, 55]
                ):
                    cls.scqw = point
                    return app.click_yx(*point)
        cls.del_scqw()
        app.scroll_xy(-12000, 225, 600)

    click = [391, 809]
    link = ["姑姑车位", "好友车场", "好友车位", "搜索车位"]


class 好友车场:
    points = [
        [800, 50, 0xF8E3CD],
        [800, 130, 0xCC8F48],
        [800, 230, 0x498ED6],
        [800, 310, 0xD7B699],
        [800, 400, 0x947F73],
    ]
    check_region = [70, 160, 120, 290]
    check_color = [
        [385, 22, 0xFDF9C0],
        [391, 15, 0xC306],
        [401, 19, 0xA1BAC1],
        [409, 20, 0xC47118],
    ]

    tstc = False
    qddh = -1
    time_list_region = [
        [412 + y * 186, 82 + x * 248, 429 + y * 186, 142 + x * 248]
        for y in range(2)
        for x in range(2)
    ]
    time_color_list = [
        [
            [417 + y * 186, 57 + x * 248, 0xFFFFFF],
            [424 + y * 186, 61 + x * 248, 0xFFFFFF],
            [420 + y * 186, 62 + x * 248, 0x1E2D64],
        ]
        for y in range(2)
        for x in range(2)
    ]
    cw_point = [[100 + x * 260, 510 + y * 185] for y in range(2) for x in range(2)]
    top = False
    bysc = 0

    @classmethod
    def zdcw(cls):
        if cls.tstc:
            cls.tstc = False
            停车管理.tstc = False
            return app.click_xy(225, 805)

        app.keep_screen(True)
        # if not cls.top:
        #     if app.is_multi_color(cls.check_color, 85):
        #         cls.top = True
        #     else:
        #         cls.check_color = app.get_points(cls.check_region, 5)
        #         app.scroll_xy(12000, 225, 600)
        #         return
        app.scroll_xy(12000, 225, 600)
        if app.is_multi_color(姑姑车位.列表缩进, 85):
            app.click_xy(6, 208)
            return
        if not app.is_multi_color(姑姑车位.五号停车, 85):
            for i in range(4):
                if not app.is_multi_color(cls.time_color_list[i]):
                    cls.tstc = True
                    return app.click_xy(*cls.cw_point[i])
        else:
            state.set_state("zdcw", time.time() + app.config["cwsz"]["jtjg"] * 60)

        return app.click_xy(*cls.click)

    @staticmethod
    def get_total_seconds(time_string):
        if len(time_string.split(":")) == 2:
            time_object = datetime.datetime.strptime(time_string, "%M:%S")
            seconds = (
                time_object.second + time_object.hour * 3600 + time_object.minute * 60
            )
        elif len(time_string.split(":")) == 3:
            time_object = datetime.datetime.strptime(time_string, "%H:%M:%S")
            seconds = (
                time_object.second + time_object.hour * 3600 + time_object.minute * 60
            )
        else:
            raise ValueError("Invalid time format")
        return seconds

    @classmethod
    def cwqd(cls):
        qdsc = app.config["cwsz"]["qdsc"]
        bysc = qdsc - 1
        t = time.time()

        # if not cls.top:
        #     if app.is_multi_color(cls.check_color, 85):
        #         cls.top = True
        #     else:
        #         cls.check_color = app.get_points(cls.check_region, 5)
        #         app.scroll_xy(12000, 225, 600)
        #         return
        app.scroll_xy(12000, 225, 600)
        app.keep_screen(True)
        for i in range(cls.qddh + 1, 4):
            r = cls.time_list_region[i]
            time_string = pytesseract.image_to_string(
                app.region_img(r),
                lang="eng",
                config="--psm 7 -c tessedit_char_whitelist=0123456789:",
            ).strip()
            time_string = "".join(
                list(filter(lambda x: x if x in "0123456789:" else "", time_string))
            )
            try:
                if cls.get_total_seconds(time_string) >= (
                    3600 * qdsc if (t - cls.bysc) > 300 else bysc
                ):
                    app.print(f"第{i+1}个车位识别时间{time_string},点击抢夺")
                    cls.qddh = i
                    return app.click_xy(*cls.cw_point[i])
            except:
                pass
        cls.qddh = -1
        return app.click_xy(225, 805)

    click = [400, 800]
    link = ["姑姑车位", "停车管理", "好友车位", "好友车场", "抢夺收益"]


class 抢夺收益:
    points = [
        [269, 202, 0xFFFFFF],
        [281, 304, 0x7C5331],
        [644, 121, 0x6E9A2A],
        [648, 220, 0xD6C6A6],
    ]
    ocr_region = [506, 244, 520, 315]

    @classmethod
    def cwqd(cls):
        zdl = pytesseract.image_to_string(
            app.region_img(cls.ocr_region),
            lang="eng",
            config="--psm 7 -c tessedit_char_whitelist=0123456789.",
        ).strip()
        zdl = "".join(list(filter(lambda x: x if x in "1234567890." else "", zdl)))
        if len(zdl) > 0:
            if zdl[-1] == ".":
                zdl = zdl[:-1]
        else:
            zdl = 99999
        app.print(f"识别战力为{zdl}")
        try:
            zdl_number = float(zdl)
            if zdl_number < app.config["cwsz"]["qdzl"]:
                state.set_state("cwqd", time.time() + 30 * 60)
                好友车位.scroll_n = 0
                return app.click_xy(134, 646)
        except:
            pass
        return app.click_xy(*cls.click)

    click = [225, 800]
    link = ["好友车场", "缴保护费", "停车管理"]


class 停车管理:
    points = [
        [114, 150, 0xC1443A],
        [115, 209, 0xFFF37F],
        [789, 225, 0xA5271E],
        [384, 36, 0xF6E6B8],
    ]
    right = False
    tstc = False
    right_points = [[600, 390 - i * 63] for i in range(5)]
    left_points = [[600, 314 - i * 63] for i in range(5)]
    kstc = [
        [703, 228, 0xFFFFFF],
        [690, 214, 0x6E9A2A],
    ]

    @classmethod
    def zdcw(cls):
        now = datetime.datetime.now()
        hour = now.hour
        if cls.tstc:
            cls.tstc = False
            好友车场.tstc = True
            return app.click_xy(225, 763)
        if hour < 12:
            if cls.right:
                for point in cls.right_points:
                    app.click_yx(*point)
                    if app.is_multi_color(cls.kstc, 85):
                        app.click_xy(226, 704)
                        cls.right = False
                        cls.tstc = True
                        return
                cls.tstc = True
                return
            else:
                app.touch_move_xy(390, 600, 70, 600)
                cls.right = True
        else:
            for point in cls.left_points:
                app.click_yx(*point)
                if app.is_multi_color(cls.kstc, 85):
                    app.click_xy(226, 704)
                    cls.tstc = True
                    return
            cls.tstc = True
            return

    click = [225, 762]
    link = ["好友车场", "停车管理", "缴保护费", "姑姑车位"]


class 缴保护费:
    points = [
        [296, 161, 0x4E3626],
        [294, 230, 0xFCFBF3],
        [558, 141, 0xD7CBAD],
        [557, 227, 0x909688],
    ]
    tstc = False

    @classmethod
    def zdcw(cls):
        if cls.tstc:
            app.click_xy(*cls.click)
            cls.tstc = False
        else:
            app.click_xy(225, 559)
            cls.tstc = True

    click = [225, 762]
    link = ["好友车场", "缴保护费", "停车管理"]


class 家族:
    points =[[ 797, 111,0xfae17c],[ 798, 185,0xfefefd],[ 804, 335,0x8a1d1f],]
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
            # State.set_state("lysd", time.time() // 3600 * 3600 + 3600 + 55 * 60)
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


class 副本:
    points = [
        [87, 185, 0xFFDB66],
        [84, 170, 0xC44039],
        [804, 184, 0x8B1D1F],
    ]
    fb = None
    top = True
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
    }
    cygcgg = [
        [472, 358, 0x4570AB],
        [476, 349, 0xFFFFFF],
        [413, 51, 0x72EFF7],
        [404, 55, 0x4CA2AB],
    ]
    kgg = False

    @classmethod
    def zdfb(cls):
        zdfb = app.config["fbsz"]["zdfb"].copy()
        if "syzm" in zdfb:
            if state.get_sleep_time("syzm") > 0:
                del zdfb["syzm"]
            elif time.time() % 3600 // 60 > 19:
                del zdfb["syzm"]
        app.keep_screen(True)
        for fb in zdfb:
            if zdfb[fb]:
                if points := app.find_multi_color_in_region(cls.find_colors[fb], 85):
                    cls.fb = fb
                    return app.click_yx(*points[0])
        if not cls.kgg:
            if points := app.find_multi_color_in_region(cls.cygcgg, 85):
                cls.kgg = True
                return app.click_yx(*points[0])
        cls.fb = None
        if cls.top:
            cls.top = False
            return app.scroll_xy(-12000, 225, 600)
        else:
            cls.kgg = False
            cls.top = True
            state.set_state("zdfb", time.time() // 3600 * 3600 + 3600)

    click = [184, 804]
    link = ["副本", "首页", "深渊之门", "副本入口", "护卫小队"]


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


class 副本入口:
    points = [[ 177, 230,0xb8ce79],[ 270, 314,0xe5c68c],[ 323, 331,0xbca079],[ 690, 225,0xa3271d],]
    yys = [[ 586, 171,0x4671ad],[ 591, 266,0x6e9a2a],[ 591, 210,0xfafafb],]
    mcs = [[ 609, 230,0xffffff],[ 609, 231,0xa6afbe],[ 609, 232,0x1e365a],]

    @classmethod
    def zdfb(cls):
        app.keep_screen(True)
        if 副本.fb and not app.is_multi_color(cls.mcs):
            if not app.find_multi_color_in_region(cls.yys):
                return app.click_xy(225, 600)
            if app.config["fbsz"]["sdfb"][副本.fb]:
                return app.click_xy(162,  595)
            else:
                return app.click_xy(287, 595)
        return app.click_xy(225, 690)

    click = [225, 672]
    link = ["副本入口", "副本"]


class 护卫小队:
    points = [
        [109, 135, 0xFFEA91],
        [112, 323, 0xF2E7C9],
        [798, 225, 0xAC4523],
    ]
    sjpp = [
        [622, 145, 0xF5F6F8],
        [622, 120, 0xFFFFFF],
        [623, 95, 0x4570AC],
    ]
    zbzd = [
        [701, 224, 0x598024],
        [695, 193, 0xF8F8F7],
        [686, 189, 0x699428],
    ]

    @classmethod
    def zdfb(cls):
        app.keep_screen(True)
        if app.is_multi_color(cls.sjpp):
            return app.click_xy(143, 622)
        if app.is_multi_color(cls.zbzd):
            return app.click_xy(225, 700)

    click = [225, 800]
    link = ["护卫小队", "深渊之门", "副本"]
