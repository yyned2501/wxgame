import time
from main import app, state
from Libs import get_tomorrow_timestamp


class 庄园:
    points = [[ 113,  26,0xb84139],[ 112, 135,0xc42c61],[ 797, 218,0x94d6eb],[ 804, 395,0xffffff],]
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

    一键种植 = [
        [723, 64, 0xF6EDED],
        [727, 54, 0x50638D],
        [750, 67, 0xFEE4A6],
    ]
    一键收获 = [
        [720, 63, 0xE14A30],
        [735, 82, 0xCFD7CB],
        [752, 64, 0xEED59B],
    ]
    一键采摘 = [
        [720, 66, 0xE7CC9B],
        [735, 84, 0x98A6AD],
        [753, 63, 0xFFE5A7],
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
    zz_regions = {
        "cj": [105, 45, 119, 85],
        "gj": [105, 155, 119, 189],
        "tj": [105, 262, 119, 295],
    }

    @classmethod
    def action(cls):
        if app.config["gnsz"]["zdsc"]:
            app.keep_screen(True)
            for colors in [cls.一键采摘, cls.一键收获]:
                if points := app.find_multi_color_in_region(colors, 85):
                    app.click_yx(*points[0])

                    if colors == cls.一键采摘:
                        time.sleep(6)
                    else:
                        time.sleep(3)
                    return True
            if points := app.find_multi_color_in_region(cls.zhongcai, 85):
                if time.time() >= state.state["mzz"]:
                    state.state["shoucai"][cls.init_zctd(points[0])] = 0
                return True
        return app.click_xy(392, 809)

    @classmethod
    def zdsc(cls):
        app.keep_screen(True)
        for colors in [cls.一键采摘, cls.一键收获]:
            if points := app.find_multi_color_in_region(colors, 85):
                app.click_yx(*points[0])
                    
                if colors == cls.一键采摘:
                    time.sleep(6)
                return True
        t = time.time()
        yjzz = app.find_multi_color_in_region(cls.一键种植, 85)
        if yjzz:
            points = app.find_multi_color_in_region(cls.zhongcai, 85)
            if points:
                points = app.clean_coordinates(points)
                zctds = cls.get_zctds(points)
                if t < state.state["mzz"]:
                    if zctds:
                        for i in zctds:
                            state.state["shoucai"][i] = state.state["mzz"]
                    state.save()
                else:
                    if zctds:
                        for i in zctds:
                            state.state["shoucai"][i] = 0
                    app.click_yx(*yjzz[0])
                    time.sleep(1)
            else:
                time.sleep(1)
        else:
            cls.check_shoucai()
            state.state["shoucai"] = [
                i if i > t else t + cls.delta_time for i in state.state["shoucai"]
            ]
        state.save()

    @classmethod
    def check_shoucai(cls):
        now = time.time()
        cls.delta_time = 120 * 60 / (1 + app.config["scsz"]["czjc"])
        ret = False
        for i, shoucai_time in enumerate(state.state["shoucai"]):
            if shoucai_time < now:
                if now >= state.state["zhongcai"][i] >= now - cls.delta_time / 2:
                    cls.check_zw(i)
                    ret = True
        return ret

    @classmethod
    def check_zw(cls, zctd):
        x = zctd // 3
        y = zctd % 3
        region = [440 + x * 139, 20 + y * 136, 579 + x * 139, 156 + y * 136]
        for i, zw in enumerate(cls.作物):
            if app.find_multi_color_in_region(cls.作物[zw], 85, region):
                app.print(f"{zctd+1}号土地种了{zw}")
                state.update_shoucai(zctd, cls.delta_time * (2**i))
                return

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

    @classmethod
    def get_zctds(cls, points):
        zctds = [cls.init_zctd(point) for point in points]
        cls.zctds = zctds
        return zctds

    @classmethod
    def init_zctd(cls, point):
        x = (point[0] - 475) // 139
        y = (point[1] - 85) // 136
        zctd = int(x * 3 + y)
        return zctd

    link = [
        "庄园",
        "种菜",
        "种菜2",
        "偷菜",
        "好友偷菜",
        "家园",
        "首页",
        "农作物详情",
        "正在偷取中",
    ]


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
    种植 = [225, 522]

    @classmethod
    def zdsc(cls):
        app.click_xy(117, 417)
        time.sleep(0.5)
        if (not app.config["scsz"]["tjzz"]) and app.is_multi_color(cls.xztjzz, 85):
            state.set_state(
                "mzz", min([time.time() + 60 * 60, get_tomorrow_timestamp()])
            )
            app.click_xy(225, 700)
            return
        app.click_xy(*cls.种植)
        for zctd in 庄园.zctds:
            state.state["zhongcai"][zctd] = time.time()
        state.save()
        time.sleep(3)
        if app.is_multi_color(cls.没种子, 85):
            state.set_state(
                "mzz", min([time.time() + 60 * 60, get_tomorrow_timestamp()])
            )
            app.click_xy(225, 700)
            return

    # @classmethod
    # def action(cls):
    #     app.click_xy(117, 417)
    #     time.sleep(0.5)
    #     if (not app.config["scsz"]["tjzz"]) and app.is_multi_color(cls.xztjzz, 85):
    #         state.set_state(
    #             "mzz", min([time.time() + 60 * 60, get_tomorrow_timestamp()])
    #         )
    #         app.click_xy(225, 700)
    #         return
    #     app.click_xy(*cls.种植)
    #     time.sleep(0.5)
    #     if app.is_multi_color(cls.没种子, 85):
    #         state.set_state(
    #             "mzz", min([time.time() + 60 * 60, get_tomorrow_timestamp()])
    #         )
    #         app.click_xy(225, 700)
    #         return
    #     state.set_state("zcsj", time.time())
    #     time.sleep(3 + 5 / (1 + app.config["scsz"]["czjc"]))
    #     cls.check_zw()

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


class 种菜2(种菜):
    points = [
        [299, 170, 0x482F21],
        [298, 200, 0xFFFFF6],
        [340, 254, 0xD7CBAD],
        [311, 408, 0x95794F],
    ]
    种植 = [225, 590]
    link = ["庄园", "种菜2"]


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
                if cls.has_bypz():
                    app.print("没找到菜，30秒后使用备用方案重试")
                    state.add_toucai(0.1)
                    别人家.bypz = time.time()
                else:
                    app.print("没找到菜，不使用备用品种，15分钟后后重试")
                    state.add_toucai(3)
                cls.scroll_n = 0

    @staticmethod
    def has_bypz():
        bypz = app.config["tcsz"]["bypz"]
        for zw in bypz:
            if bypz[zw]:
                return True
        return False

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


class 农作物详情:
    points = [
        [311, 172, 0x4E3626],
        [308, 234, 0xFFFFF6],
        [620, 226, 0x406191],
    ]

    zdsc = [225, 620]
    click = [225, 750]

    link = ["农作物详情", "庄园", "肥料选择"]


class 肥料选择:
    points = [
        [299, 192, 0x4E3625],
        [309, 194, 0xFFFFF6],
        [463, 308, 0xE8B82D],
        [544, 254, 0x6E9B2A],
    ]

    zdsc = [225, 545]
    click = [225, 750]

    link = ["庄园", "肥料选择"]


class 正在偷取中:
    points = [
        [310, 156, 0x4E3626],
        [305, 264, 0xFAF9F1],
        [447, 130, 0x6E4437],
        [495, 205, 0xCEAD7C],
    ]

    zdsc = [116, 537]
    click = [225, 750]

    link = ["庄园", "肥料选择"]
