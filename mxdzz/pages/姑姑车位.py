import datetime
import time
import pytesseract
from main import app, state


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
    已达上限 = [
        [237, 27, 0x46EF72],
        [168, 78, 0xD41E09],
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
        if points := app.find_multi_color_in_region(
            cls.已达上限, region=[160, 20, 240, 449]
        ):
            state.set_state("zdcw", 0)
            return app.click_yx(*points[0])
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
    link = ["停车收益", "姑姑车位"]


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
            抢夺收益.byzl = t
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
    冷却中 = [
        [374, 151, 0xFFED9A],
        [373, 164, 0xFFED9A],
        [378, 181, 0xFFE27F],
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
                ) and not app.find_multi_color_in_region(
                    cls.冷却中, 85, [y - 20, 150, y + 55, 185]
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
        [422 + y * 186, 82 + x * 252, 439 + y * 186, 142 + x * 252]
        for y in range(2)
        for x in range(2)
    ]
    time_color_list = [
        [
            [421 + y * 186, 60 + x * 252, 0xFFFFFF],
            [433 + y * 186, 60 + x * 252, 0xFFFFFF],
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

        app.scroll_xy(12000, 225, 600)
        time.sleep(1)
        app.keep_screen(True)
        # app.screenshot(f"cw_{int(time.time())}.png")
        if app.is_multi_color(姑姑车位.列表缩进, 85):
            app.click_xy(6, 208)
            return
        if not app.is_multi_color(姑姑车位.五号停车, 85):
            for i in range(4):
                if not app.is_multi_color(cls.time_color_list[i], 80):
                    cls.tstc = True
                    停车管理.right = False
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
    byzl = 0

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
        t = time.time()
        config_zdl = app.config["cwsz"]["qdzl"]
        run_zdl = config_zdl if (t - cls.byzl) > 300 else config_zdl + 2000
        try:
            zdl_number = float(zdl)
            if zdl_number < run_zdl:
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
        [111, 128, 0xEDE4C8],
        [110, 179, 0xFFF59E],
        [788, 227, 0xA72619],
        [369, 310, 0xEDE3C4],
    ]
    没有未停 = False
    right = False
    tstc = False
    right_points = [[600, 75 + i * 63] for i in range(6)]
    left_points = [[600, 58 + i * 63] for i in range(6)]
    kstc = [
        [703, 228, 0xFFFFFF],
        [690, 214, 0x6E9A2A],
    ]
    今日未停 = [
        [551, 264, 0xD26D0A],
        [551, 265, 0xDFBD8C],
        [551, 267, 0xD47516],
        [545, 274, 0xD37212],
        [557, 271, 0xD5822B],
    ]

    @classmethod
    def zdcw(cls):
        缴保护费.tstc = False
        if cls.tstc:
            cls.tstc = False
            好友车场.tstc = True
            return app.click_xy(225, 763)
        if app.is_today(cls.没有未停):
            for point in cls.left_points:
                app.click_yx(*point)
                if app.is_multi_color(cls.kstc, 85):
                    app.click_xy(226, 704)
                    cls.tstc = True
                    return
        else:
            if cls.right:
                for point in cls.right_points:
                    app.click_yx(*point)
                    if app.is_multi_color(cls.今日未停, 85):
                        if app.is_multi_color(cls.kstc, 85):
                            app.click_xy(226, 704)
                            cls.tstc = True
                            return
                app.touch_move_xy(70, 600, 390, 600)
                cls.没有未停 = time.time()
                cls.right = False
            else:
                for point in cls.left_points:
                    app.click_yx(*point)
                    # time.sleep(0.5)
                    if app.is_multi_color(cls.今日未停, 85):
                        print("今日未停")
                        if app.is_multi_color(cls.kstc, 85):
                            app.click_xy(226, 704)
                            cls.tstc = True
                            return
                app.touch_move_xy(390, 600, 70, 600)
                cls.right = True

    @classmethod
    def zdcw_bak(cls):
        now = datetime.datetime.now()
        hour = now.hour
        缴保护费.tstc = False
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
