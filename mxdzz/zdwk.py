from copy import deepcopy
import time
import numpy as np
import heapq
from main import app, state

if not hasattr(app, "print"):
    app.print = print
a = {  # 第一位：1：连通 2：不连通 第二位：0空地 1土地 2砖地 3铜矿 4银矿 5金矿 6技能券 7同伴券 8钻头 9炸弹 A钻石 B黄金2 C空地2
    "10": [77, 67, 60],
    "11": [163, 113, 66],
    "12": [144, 141, 136],
    "13": [49, 36, 21],
    "14": [233, 232, 231],
    "15": [253, 232, 60],
    "16": [133, 49, 27],
    "17": [249, 249, 250],
    "18": [115, 76, 37],
    "19": [198, 159, 98],
    "1A": [74, 43, 37],
    "1B": [252, 192, 42],
    # "1C": [81, 60, 34],
    "20": [41, 35, 31],
    "21": [84, 59, 34],
    "22": [75, 74, 71],
    "23": [26, 19, 11],
    "24": [123, 123, 122],
    "25": [132, 122, 31],
    "26": [69, 26, 14],
    "27": [130, 130, 131],
    "28": [60, 39, 20],
    "29": [104, 83, 51],
    "2A": [39, 22, 19],
}


def dijkstra(array, start):
    rows = len(array)
    cols = len(array[0])
    start_distance = array[start[0]][start[1]]
    visited = [[False for _ in range(cols)] for _ in range(rows)]
    distances = [[float("inf") for _ in range(cols)] for _ in range(rows)]
    distances[start[0]][start[1]] = start_distance
    queue = [(start_distance, start)]
    while queue:
        current_distance, current_position = heapq.heappop(queue)
        if visited[current_position[0]][current_position[1]]:
            continue
        visited[current_position[0]][current_position[1]] = True
        if current_distance > distances[current_position[0]][current_position[1]]:
            continue
        for i in range(-1, 2):
            for j in range(-1, 2):
                next_i, next_j = current_position[0] + i, current_position[1] + j
                next_position = (next_i, next_j)
                if abs(i) + abs(j) < 2:
                    if 0 <= next_i < rows and 0 <= next_j < cols:
                        next_distance = current_distance + array[next_i][next_j]
                        if next_distance < distances[next_i][next_j]:
                            distances[next_i][next_j] = next_distance
                            heapq.heappush(queue, (next_distance, next_position))
    return distances


score = {
    "3": 1,
    "4": 2,
    "5": 5,
    "6": 1,
    "7": 1,
    "8": 3,
    "9": 4,
    "A": 5,
    "B": 99,
}


def get_map():
    img = app.capture()
    map_list = [["10" for y in range(7)] for x in range(6)]
    for c in range(6):
        for r in range(7):
            x = c * 75 + 45
            y = r * 75 + 272
            for i in a:
                if app.same_color(img[y, x], a[i], 95):
                    if map_list[c][r] == "10":
                        map_list[c][r] = i
                    else:
                        app.print(map_list[c][r], i)
    return map_list


def check_around(c, r, arr: np.ndarray):
    cols, rows = arr.shape
    points = [[i, j] for i in range(-1, 2) for j in range(-1, 2) if abs(i + j) == 1]
    for point in points:
        _c = c + point[0]
        _r = r + point[1]
        if 0 <= _c < cols and 0 <= _r < rows:
            if arr[_c, _r] == 1:
                return True
    return False


def connectedComponents(arr: np.ndarray, start_col=0, start_row=0, visited=None):
    if visited is None:
        visited = np.full(arr.shape, np.nan)

    if visited[start_col][start_row] == 1:
        # print(f"[{start_col}, {start_row}]checked")
        return visited
    elif visited[start_col][start_row] == 0:
        # print(f"[{start_col}, {start_row}]checked")
        return visited
    else:
        if arr[start_col][start_row] == 1:
            visited[start_col][start_row] = 1
        else:
            visited[start_col][start_row] = 0

    if arr[start_col][start_row] == 1:
        points = [[i, j] for i in range(-1, 2) for j in range(-1, 2) if abs(i + j) == 1]
    else:
        points = []
    for _c, _r in points:
        new_col, new_row = start_col + _c, start_row + _r
        if (0 <= new_col < arr.shape[0]) and (0 <= new_row < arr.shape[1]):
            # print(f"[{start_col}, {start_row}]->[{new_col}, {new_row}]")
            connectedComponents(arr, new_col, new_row, visited)

    return visited


class ZDWK:
    score = score = {
        "3": 1,
        "4": 2,
        "5": 5,
        "6": 1,
        "7": 1,
        "8": 3,
        "9": 4,
        "A": 5,
        "B": 99,
    }

    def __init__(self, map_list=None) -> None:
        self.get_map(map_list)
        self.methods = init_methods()

    def get_map(self, map_list=None):
        if map_list:
            self.map_list = map_list
        else:
            self.map_list = get_map()
        self.map_arr = np.array(self.map_list)

    def init_arrs(self):
        self.dj_use_arr = self.init_dj_use_map()
        self.tq_arr = self.init_tq_map()
        self.tq_use_arr = self.init_tq_use_map()
        self.empty_arr = self.init_empty_map()
        self.aim_arr = self.init_aim_map()
        self.aim_list = self.init_aim_list()
        self.aim_step_arr = self.init_aim_step_map()

    def init_tq_map(self):
        if not hasattr(self, "dj_use_arr"):
            self.dj_use_arr = self.init_dj_use_map()
        emtpy_arr = self.dj_use_arr
        tq_arr = np.array(
            [
                np.nan if i == "10" else 1 if i[0] == "1" else np.nan
                for i in self.map_arr.reshape(-1)
            ]
        ).reshape(self.map_arr.shape)
        tq_arr_check = np.where(tq_arr == 1)
        if len(tq_arr_check[0]) > 0:
            for i in range(len(tq_arr_check[0])):
                c, r = tq_arr_check[0][i], tq_arr_check[1][i]
                if r > 0:
                    if not check_around(c, r, emtpy_arr):
                        tq_arr[c, r] = np.nan
        # print(tq_arr)
        return tq_arr

    def init_empty_map(self):
        return np.array(
            [1 if i[1] == "0" else np.nan for i in self.map_arr.reshape(-1)]
        ).reshape(self.map_arr.shape)

    def init_tq_use_map(self):
        return np.array(
            [
                0 if i[1] == "0" else 1 if i[1] == "1" else 2 if i[1] == "2" else 0
                for i in self.map_arr.reshape(-1)
            ]
        ).reshape(self.map_arr.shape)

    def init_dj_use_map(self):
        empty_arr = np.full(self.map_arr.shape, np.nan)
        empty_arr[self.map_arr == "10"] = 1
        cols, rows = self.map_arr.shape
        for i in range(cols):
            if empty_arr[i, rows - 1] == 1:
                empty_arr[i, rows - 1] = np.nan
                self.map_arr[i, rows - 1] = "11"
        visited = None
        for i in range(cols):
            visited = connectedComponents(empty_arr, start_col=i, visited=visited)
        visited[visited == 0] = np.nan
        # print(visited)
        return visited

    def init_aim_map(self):
        return np.array(
            [score[i[1]] if i[1] in self.score else 0 for i in self.map_arr.reshape(-1)]
        ).reshape(self.map_arr.shape)

    def init_aim_list(self):
        find = np.where(self.aim_arr > 0)
        if (find_len := len(find[0])) > 0:
            ret_list = []
            for i in range(find_len):
                ret_list.append([find[0][i], find[1][i]])
            return ret_list
        return []

    def init_aim_step_map(self):
        ret = np.zeros_like(self.aim_arr)
        for point in self.aim_list:
            step = np.array(dijkstra(self.tq_use_arr, point)) * self.tq_arr
            step[np.isnan(step)] = np.inf
            ret[*point] = step.min()
        return ret

    def set_zt_map(self, col):
        map = np.zeros_like(self.aim_arr)
        c, r = self.aim_arr.shape
        map[col] = 1
        if col > 0:
            map[col - 1, r - 1] = 1
        if col < c - 1:
            map[col + 1, r - 1] = 1
        return map

    def set_zd_map(self, col, row):
        map = np.zeros_like(self.aim_arr)
        c, r = self.aim_arr.shape
        for _c in range(c):
            for _r in range(r):
                if abs(_c - col) + abs(_r - row) <= 2:
                    map[_c, _r] = 1
        return map

    def check_zt_steps(self, steps=2, clear_sum=2):
        ret_list = []
        max = 0
        for c in range(self.dj_use_arr.shape[0]):
            if np.any(self.dj_use_arr[c] == 1):
                zt_map = self.set_zt_map(c)
                clear_map = zt_map * self.aim_arr

                clear_steps = (
                    np.count_nonzero(clear_map) + (zt_map * self.aim_step_arr).max()
                )
                clear_dj = clear_map.sum()
                if clear_steps > steps and clear_dj > clear_sum:
                    sum_dj = clear_steps + clear_dj
                    if sum_dj > max:
                        ret_list = [c, np.where(self.dj_use_arr[c] == 1)[0][0]]
                        max = sum_dj
                    else:
                        if sum_dj == max:
                            if abs(c - 2.5) < abs(ret_list[0] - 2.5):
                                ret_list = [c, np.where(self.dj_use_arr[c] == 1)[0][0]]
        return ret_list

    def check_zd_steps(self, steps=2, clear_sum=2, rows_min=0):
        ret_list = []
        max = 0
        find = np.where(self.dj_use_arr == 1)
        if (find_len := len(find[0])) > 0:
            for i in range(find_len):
                c, r = find[0][i], find[1][i]
                if r >= rows_min:
                    zd_map = self.set_zd_map(c, r)
                    clear_map = zd_map * self.aim_arr
                    clear_steps = (
                        np.count_nonzero(clear_map) + (zd_map * self.aim_step_arr).max()
                    )
                    clear_dj = clear_map.sum()
                    if clear_steps > steps and clear_dj > clear_sum:
                        sum_dj = clear_steps + clear_dj
                        if sum_dj > max:
                            ret_list = [c, r]
                            max = sum_dj
        return ret_list

    def check_aim_step(self):
        ret = []
        for point in self.aim_list:
            step = np.array(dijkstra(self.tq_use_arr, point)) * self.tq_arr
            step[np.isnan(step)] = np.inf
            ret[*point] = step.min()
        return ret

    def check_tq_steps(self):
        app.print("检查明矿")
        mk = self.aim_arr * self.tq_arr
        mk[np.isnan(mk)] = -np.inf
        if find_point := min_row_numpy_where_ret(np.where(mk > 0)):
            return find_point
        app.print("检查暗矿")
        if find_point := min_row_numpy_where_ret(
            np.where(self.aim_step_arr < self.aim_arr)
        ):
            return self.get_ak(find_point)
        return []

    def set_tf_map(self, like_arr: np.ndarray, col=False, row=False):
        c, r = like_arr.shape
        ret = [
            [
                ((int(abs(_c - 2.5)) if col else 0) + (_r if row else 0) * 0.1) * 0.01
                for _r in range(r)
            ]
            for _c in range(c)
        ]
        return np.array(ret)

    def check_tq_down(self, steps=2):
        tq_use_arr = self.tq_use_arr.copy()
        tq_use_arr = np.column_stack((tq_use_arr, np.zeros(6)))
        tq_arr = np.column_stack((self.tq_arr, np.full(6, np.nan)))
        down_steps = np.array(
            dijkstra(tq_use_arr, [0, tq_use_arr.shape[1] - 1])
        ) * tq_arr + self.set_tf_map(tq_arr, col=True)
        return min_step_numpy_ret(down_steps, steps)

    def find_aim_point(self):
        app.print("开始找矿")
        if "tq" in self.methods:
            app.print("检查奖励金矿拿矿")
            find = np.where(self.aim_arr == 99)
            if len(find[0]) > 0:
                click([find[0][0], find[1][0]])
                return True
        if "zd" in self.methods:
            app.print("检查炸弹拿矿")
            if len(point := self.check_zd_steps()) > 0:
                app.click_xy(314, 806)
                click(point)
                return True
        if "zt" in self.methods:
            app.print("检查钻头拿矿")
            if len(point := self.check_zt_steps()) > 0:
                app.click_xy(141, 804)
                click(point)
                time.sleep(1)
                return True
        if "tq" in self.methods:
            app.print("检查铁锹拿矿")
            if len(point := self.check_tq_steps()) > 0:
                click(point)
                return True

    def get_ak(self, point):
        ak_steps = np.array(
            dijkstra(self.tq_use_arr, point)
        ) * self.tq_arr + self.set_tf_map(self.tq_arr, True)
        return min_step_numpy_ret(ak_steps, self.aim_arr[*point])

    def find_down_point(self):
        app.print("开始往下挖")
        if "tq" in self.methods:
            app.print("检查铁锹1下挖")
            if len(point := self.check_tq_down()) > 0:
                click(point)
                # print(point)
                return True
        if "zd" in self.methods:
            app.print("检查炸弹下挖")
            if len(point := self.check_zd_steps(0, 1, 4)) > 0:
                app.click_xy(314, 806)
                click(point)
                return True
        if "zt" in self.methods:
            app.print("检查钻头下挖")
            if len(point := self.check_zt_steps(0, 1)) > 0:
                app.click_xy(141, 804)
                click(point)
                return True
        if "tq" in self.methods:
            app.print("检查铁锹2下挖")
            if len(point := self.check_tq_down(3)) > 0:
                click(point)
                return True


def min_step_numpy_ret(steps_ndarray: np.ndarray, steps):
    steps_ndarray[np.isnan(steps_ndarray)] = np.inf
    min_step = steps_ndarray.min()
    if min_step < steps:
        point = np.where(steps_ndarray == min_step)
        return point[0][0], point[1][0]
    else:
        return []


def min_row_numpy_where_ret(where_tuple: tuple):
    if (count := len(where_tuple[0])) > 0:
        if count == 1:
            return [where_tuple[0][0], where_tuple[1][0]]
        else:
            min_i = 0
            min_n = 10
            for i in range(count):
                if where_tuple[1][i] < min_n:
                    min_n = where_tuple[1][i]
                    min_i = i
            return [where_tuple[0][min_i], where_tuple[1][min_i]]
    return False


def click(point):
    app.print(point)
    c, r = point
    x = c * 75 + 45
    y = r * 75 + 272
    app.click_xy(x, y)


def init_methods():
    color = {
        "zt": [
            [795, 121, 0xAF8028],
            [794, 140, 0xDA9E2E],
            [810, 142, 0x7C8290],
        ],
        "zd": [
            [792, 320, 0xE8714B],
            [801, 313, 0xE8714B],
            [816, 305, 0x9D7340],
        ],
        "tq": [
            [790, 222, 0x615672],
            [788, 237, 0x6D627D],
            [818, 235, 0x924833],
        ],
    }

    ret_methods = {}
    app.keep_screen(True)
    for method in color:
        if app.find_multi_color_in_region(color[method], 85, [768, 80, 829, 353]):
            ret_methods[method] = True
    app.keep_screen(False)
    return ret_methods


def compare_lists(list1, list2):
    if len(list1) != len(list2):
        return False

    for i in range(len(list1)):
        if len(list1[i]) != len(list2[i]):
            return False

        for j in range(len(list1[i])):
            if list1[i][j] != list2[i][j]:
                return False

    return True


def deal_error(map_list):
    cols, rows = len(map_list), len(map_list[0])
    for _c, col_list in enumerate(map_list):
        for _r, point in enumerate(col_list):
            # app.print(_r, rows, point)
            if point == "1B":
                click([_c, _r])
                return False
            if _r == rows - 1:
                if point == "10":
                    # click([_c, _r])
                    return False
    return True


def run_old():
    zdwk = ZDWK()
    old_map = []
    _old_map = []
    while "tq" in zdwk.methods:
        zdwk.get_map()
        if compare_lists(_old_map, zdwk.map_list):
            if deal_error(zdwk.map_list) or compare_lists(old_map, zdwk.map_list):
                if not zdwk.find_aim_point():
                    zdwk.find_down_point()
                old_map = []
                time.sleep(2)
            else:
                old_map = deepcopy(zdwk.map_list)
        else:
            _old_map = deepcopy(zdwk.map_list)
            time.sleep(0.5)


def run(old_map=[], err=0):
    app.keep_screen(True)
    zdwk = ZDWK()
    if "tq" in zdwk.methods:
        if (
            (len(zdwk.methods) == 1)
            and app.config["wksz"]["wdjzd"]
            and (state.get_sleep_time("ggwk") == 0)
        ):
            app.click_xy(420, 190)
            return True
        if compare_lists(old_map, zdwk.map_list):
            zdwk.init_arrs()
            if not zdwk.find_aim_point():
                zdwk.find_down_point()
            time.sleep(1)
        else:
            app.keep_screen(False)
            if err < 3:
                run(zdwk.map_list, err + 1)
                time.sleep(0.5)
            else:
                app.print("识别地图失败")
                return False
        return True
    return False


if __name__ == "__main__":
    map_list = [
        ["11", "12", "10", "10", "10", "10", "13"],
        ["11", "10", "11", "10", "12", "10", "11"],
        ["10", "10", "12", "10", "1B", "13", "22"],
        ["10", "10", "10", "10", "11", "21", "20"],
        ["11", "10", "11", "11", "23", "27", "21"],
        ["12", "10", "10", "11", "21", "21", "13"],
    ]
    # t0 = time.time()
    zdwk = ZDWK()
    run()
    # zdwk.init_arrs()
    # find = np.where(zdwk.aim_arr == 99)
    # print(zdwk.tq_use_arr)
    # print(zdwk.aim_step_arr + zdwk.aim_arr)
    # print(zdwk.aim_arr)
    # print(zdwk.check_zt_steps())
    # if len(find[0]) > 0:
    #     app.print(find[0][0], find[1][0])
    # app.print(zdwk.map_arr)
    # app.print(zdwk.dj_use_arr)
    # # app.print(zdwk.tq_use_arr)
    # app.print(zdwk.tq_arr)
    # app.print(zdwk.tq_use_arr)
    # app.print(zdwk.aim_step_arr)
    # app.print(-t0 + (t0 := time.time()))
    # zdwk.check_zd_steps()
    # app.print(-t0 + (t0 := time.time()))
    # if not zdwk.find_aim_point():
    #     zdwk.find_down_point()
    # run()
