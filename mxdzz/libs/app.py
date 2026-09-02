import os
import random
import time
import win32con
import win32gui
import pyautogui
import numpy as np
import datetime
from PIL import Image, ImageFilter
from config import read_config


class App:
    keep = False

    def __init__(self, window_name) -> None:
        self.window_name = window_name
        self.config = read_config()
        self.location = self.get_location()
        self.img = np.empty([0, 0, 0])

    def restart(self):
        self.close_app()
        self.location = self.get_location()

    def close_app(self):
        if self.hwnd != 0:
            try:
                win32gui.PostMessage(self.hwnd, win32con.WM_CLOSE, 0, 0)
            except:
                self.hwnd = win32gui.FindWindow(None, self.window_name)
                return self.close_app()
            self.hwnd = 0

    def start_app(self):
        os.system(self.config["jcsz"]["qdlj"])
        time.sleep(1)

    def get_location(self):
        hwnd = win32gui.FindWindow(None, self.window_name)
        self.hwnd = hwnd
        if hwnd == 0:
            self.start_app()
            return self.get_location()
        else:
            localtion = win32gui.GetWindowRect(hwnd)
            if localtion[0] != 0 or localtion[1] != 0:
                location = [
                    0,
                    0,
                    localtion[2] - localtion[0],
                    localtion[3] - localtion[1],
                ]
                win32gui.MoveWindow(
                    hwnd,
                    *location,
                    True,
                )
            return localtion

    def keep_screen(self, b):
        self.keep = b
        if not b:
            self.img = np.empty([0, 0, 0])

    def click_yx(self, y, x):
        y += self.location[1]
        x += self.location[0]
        _x, _y = pyautogui.position()
        pyautogui.click(x, y)
        pyautogui.moveTo(_x, _y)

    def click_xy(self, x, y):
        x += self.location[0]
        y += self.location[1]
        _x, _y = pyautogui.position()
        pyautogui.click(x, y)
        pyautogui.moveTo(_x, _y)

    def scroll_xy(self, c, x, y):
        x += self.location[0]
        y += self.location[1]
        _x, _y = pyautogui.position()
        pyautogui.moveTo(x, y)
        pyautogui.scroll(c, x, y)
        pyautogui.moveTo(_x, _y)

    def touch_move_xy(self, x0, y0, x1, y1, d=1):
        x0 += self.location[0]
        x1 += self.location[0]
        y0 += self.location[1]
        y1 += self.location[1]
        _x, _y = pyautogui.position()
        pyautogui.moveTo(x0, y0)
        pyautogui.dragTo(x1, y1, d)
        pyautogui.moveTo(_x, _y)

    def capture(self) -> np.ndarray:
        if self.keep and self.img.shape[0] > 1:
            return self.img
        location = self.location
        try:
            img = pyautogui.screenshot(
                region=(
                    location[0],
                    location[1],
                    location[2] - location[0],
                    location[3] - location[1],
                )
            )
        except:
            return self.capture()
        # img.save("screenshot.png")
        np_img = np.array(img)
        if self.keep:
            self.img = np_img
        return np_img

    def region_img(self, region):
        img = self.capture()
        _img = img[region[0] : region[2], region[1] : region[3]]
        return Image.fromarray(_img)

    def region_img_b(self, region, threshold=127, reverse=False):
        img_arr = self.capture()
        _img_arr = img_arr[region[0] : region[2], region[1] : region[3]]
        _img = Image.fromarray(_img_arr).convert("L")
        _img = _img.filter(ImageFilter.SHARPEN)
        _img_arr = np.array(_img)
        ret_img_arr = np.full(_img_arr.shape, False)
        ret_img_arr[np.where(_img_arr > threshold)] = True
        if reverse:
            ret_img_arr = np.logical_not(ret_img_arr)  # 反色
        return Image.fromarray(ret_img_arr)

    def screenshot(self, name="screenshot.png") -> None:
        location = self.location
        pyautogui.screenshot(
            imageFilename=name,
            region=(
                location[0],
                location[1],
                location[2] - location[0],
                location[3] - location[1],
            ),
        )

    def same_color(self, color0, color1, degree=85):
        delta = (256 - 256 * degree // 100) // 2
        for i, v in enumerate(color1):
            if not v - delta <= color0[i] <= v + delta:
                return False
        return True

    def is_multi_color(self, points, degree=85):
        keep = self.keep
        self.keep_screen(True)
        for p in points:
            if not self.is_color(*p, degree=degree):
                self.keep_screen(keep)
                return False
        self.keep_screen(keep)
        return True

    def find_multi_color_in_region(self, points, degree=85, region=None):
        img = self.capture()
        if region is None:
            region = [0, 0, img.shape[0], img.shape[1]]
        _img = img[region[0] : region[2], region[1] : region[3]]
        delta = (256 - 256 * degree // 100) // 2
        boolean_imgs_list = []
        for point in points:
            delta_img = _img - self.c2rgb(point[2])
            boolean_img = ((delta_img < delta) * (delta_img > -delta)).prod(2)
            move_img = reshape_same_size(
                boolean_img, point[0] - points[0][0], point[1] - points[0][1]
            )
            boolean_imgs_list.append(move_img)

        boolean_imgs = np.array(boolean_imgs_list).prod(0)
        ret_tuple = np.where(boolean_imgs == 1)
        if (ret_len := len(ret_tuple[0])) > 0:
            ret_list = []
            for i in range(ret_len):
                ret_list.append(
                    [ret_tuple[0][i] + region[0], ret_tuple[1][i] + region[1]]
                )
            return ret_list
        else:
            return False

    @staticmethod
    def c2rgb(c):
        r = c // 0x10000
        g = c // 0x100 - r * 0x100
        b = c - r * 0x10000 - g * 0x100
        return [r, g, b]

    @staticmethod
    def rgb2c(rgb_list):
        r, g, b = rgb_list
        c = r * 0x10000 + g * 0x100 + b
        return c

    def get_points(self, region, n):
        img = self.capture()
        _img = img[region[0] : region[2], region[1] : region[3]]
        c, r, _ = _img.shape
        random_points = random.sample(range(c * r), n)
        return [[region[0], region[1], self.rgb2c(_img[0, 0])]] + [
            [
                (_c := i // r) + region[0],
                (_r := i % r) + region[1],
                self.rgb2c(_img[_c, _r]),
            ]
            for i in random_points
        ]

    def is_color(self, x, y, color, degree):
        c = self.capture()[x, y]
        _c = self.c2rgb(color)
        delta = (256 - 256 * degree // 100) // 2
        for i, v in enumerate(_c):
            if not v - delta <= c[i] <= v + delta:
                return False
        return True

    @staticmethod
    def clean_coordinates(coord_list, distance_limit=10):
        cleaned_list = []

        for coord in coord_list:
            add_coord = True
            for existing_coord in cleaned_list:
                # 计算两个坐标之间的距离
                distance = (
                    (existing_coord[0] - coord[0]) ** 2
                    + (existing_coord[1] - coord[1]) ** 2
                ) ** 0.5
                if distance < distance_limit:
                    add_coord = False
                    break
            if add_coord:
                cleaned_list.append(coord)
        return cleaned_list

    @staticmethod
    def is_today(timestamp):
        try:
            date_from_timestamp = datetime.datetime.fromtimestamp(timestamp)
            current_date = datetime.datetime.now()
            return date_from_timestamp.date() == current_date.date()
        except Exception as e:
            print(f"An error occurred: {e}")
            return False


def reshape_same_size(org_np, x, y):
    tmp_np = org_np[
        max(0, x) : None if x >= 0 else x, max(0, y) : None if y >= 0 else y
    ]
    ret_np = np.pad(tmp_np, ((max(-x, 0), max(x, 0)), (max(-y, 0), max(y, 0))))
    return ret_np
