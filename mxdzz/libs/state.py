import json
import time

from libs.normal import format_seconds, get_tomorrow_timestamp


class State:
    file = "state.json"
    xtsl = 2

    time_keys = [
        "zxjl",
        "zdkj",
        "zdwk",
        "jthb",
        "zdcw",
        "cwsc",
        "cwqd",
        "xyzp",
        "lysd",
        "bmdy",
        "zdfb",
        "syzm",
        "ggwk",
        "gbss",
    ]
    other_keys = [
        "zctd",
        "zcsj",
        "mzz",
    ]

    def __init__(self):
        self.state = self.read()

    def read(self):
        try:
            with open(self.file, "r") as f:
                ret = json.loads(f.read())
        except:
            ret = {}
        return ret

    def save(self):
        with open(self.file, "w") as f:
            f.write(json.dumps(self.state))

    def check_state(self):
        state = self.state
        if "toucai" not in state:
            state["toucai"] = []
        if "zhongcai" not in state:
            state["zhongcai"] = [0, 0, 0, 0, 0, 0]
        if "shoucai" not in state:
            state["shoucai"] = [0, 0, 0, 0, 0, 0]
        for k in self.time_keys:
            if k not in state:
                state[k] = 0
        for k in self.other_keys:
            if k not in state:
                state[k] = 0
        state["toucai"] = list(filter(lambda x: x > time.time(), state["toucai"]))
        self.save()
        return state

    def add_toucai(self, n):
        state = self.check_state()
        state["toucai"].append(time.time() + 5 * 60 * n)
        self.save()

    @property
    def toucai_sleep_time(self):
        state = self.check_state()
        if self.get_state("lcbtc") and (time.time() + 8 * 3600) // 3600 % 24 < 7:
            return 1
        else:
            if len(state["toucai"]) < self.get_state("xtsl"):
                return 0
            else:
                return int(min(state["toucai"]) - time.time())

    @property
    def shoucai_sleep_time(self):
        state = self.check_state()
        return max([int(min(state["shoucai"]) - time.time()), 0])

    def set_state(self, state_name, state_value):
        state = self.state
        state[state_name] = state_value
        self.save()

    def get_state(self, state_name):
        state = self.state
        return state[state_name]

    def add_scsj(self, i, app):
        t = (120 * 60 / (1 + app.config["scsz"]["czjc"])) * (2**i)
        state = self.check_state()
        zcsj = state["zcsj"]
        zctd = state["zctd"]
        app.print(f"第{zctd+1}块地{format_seconds(t)}后检测收菜")
        state["zhongcai"][zctd] = zcsj + t
        state["zcsj"] = 0
        state["zctd"] = 0
        self.save()

    def update_shoucai(self, tdbh:int, czsj:int):
        self.state["shoucai"][tdbh] = self.state["zhongcai"][tdbh] + czsj
        self.save()

    def add_mtzc(self, app):
        state = self.state
        zctd = state["zctd"]
        app.print(f"没有种子了第{zctd+1}块地明天再种")
        state["zhongcai"][zctd] = get_tomorrow_timestamp()
        state["zctd"] = 0
        self.save(state)

    def get_sleep_time(self, time_key):
        state = self.check_state()
        return max([int(state[time_key] - time.time()), 0])
