import json
import threading
import tkinter as tk
from tkinter import ttk

lock = threading.Lock()
root = tk.Tk()
root.geometry("600x370")
root.resizable(width=False, height=False)
root.title("冒险脚本V0.3.00")
config = {
    "jcsz": {"qdlj": tk.StringVar()},
    "gnsz": {
        "jthb": tk.BooleanVar(),
        "zxjl": tk.BooleanVar(),
        "zdfb": tk.BooleanVar(),
        "zdsc": tk.BooleanVar(),
        "zdtc": tk.BooleanVar(),
        "zdkj": tk.BooleanVar(),
        "zdwk": tk.BooleanVar(),
        "zdcw": tk.BooleanVar(),
        "cwqd": tk.BooleanVar(),
        "lysd": tk.BooleanVar(),
        "bmdy": tk.BooleanVar(),
        "gbss": tk.BooleanVar(),
    },
    "scsz": {"czjc": tk.DoubleVar(), "tjzz": tk.BooleanVar()},
    "tcsz": {
        "xtsl": tk.IntVar(),
        "lcbtc": tk.BooleanVar(),
        "tcrk": {"cr": tk.BooleanVar(), "hy": tk.BooleanVar()},
        "fycs": {"cr": tk.IntVar(), "hy": tk.IntVar()},
        "tcpz": {"hl": tk.BooleanVar(), "qz": tk.BooleanVar(), "bc": tk.BooleanVar()},
        "bypz": {"hl": tk.BooleanVar(), "qz": tk.BooleanVar(), "bc": tk.BooleanVar()},
    },
    "wksz": {
        "jgsj": tk.IntVar(),
        "wdjzd": tk.BooleanVar(),
    },
    "cwsz": {
        "jtjg": tk.IntVar(),
        "scsj": tk.IntVar(),
        "qdsc": tk.IntVar(),
        "qdzl": tk.IntVar(),
    },
    "fbsz": {
        "zdfb": {
            "syzm": tk.BooleanVar(),
            "sdxt": tk.BooleanVar(),
            "blcx": tk.BooleanVar(),
            "cygc": tk.BooleanVar(),
            "ddsxt": tk.BooleanVar(),
            "fysd": tk.BooleanVar(),
            "hasl": tk.BooleanVar(),
        },
        "sdfb": {
            "sdxt": tk.BooleanVar(),
            "blcx": tk.BooleanVar(),
            "ddsxt": tk.BooleanVar(),
            "fysd": tk.BooleanVar(),
        },
    },
    "gbsz": {
        "jgsj": tk.IntVar(),
    },
    "qtgn": {
        "zdzl": tk.BooleanVar(),
        "xyzp": tk.BooleanVar(),
        "zxjl": tk.IntVar(),
        "zdkj": tk.IntVar(),
        "sbct": tk.IntVar(),
    },
}
notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True)

notebook.add(jcsz := tk.Frame(notebook), text="基础设置")
tk.Label(jcsz, text="启动路径", pady=5).grid(row=0, column=0)
tk.Entry(jcsz, textvariable=config["jcsz"]["qdlj"], width=76).grid(row=0, column=1)


notebook.add(gnsz := tk.Frame(notebook), text="功能设置")
tk.Checkbutton(gnsz, text="监听红包", variable=config["gnsz"]["jthb"]).grid(row=1, column=0)
tk.Checkbutton(gnsz, text="在线奖励", variable=config["gnsz"]["zxjl"]).grid(row=1, column=1)
tk.Checkbutton(gnsz, text="自动副本", variable=config["gnsz"]["zdfb"]).grid(row=1, column=2)
tk.Checkbutton(gnsz, text="自动收菜", variable=config["gnsz"]["zdsc"]).grid(row=2, column=0)
tk.Checkbutton(gnsz, text="自动偷菜", variable=config["gnsz"]["zdtc"]).grid(row=2, column=1)
tk.Checkbutton(gnsz, text="自动科技", variable=config["gnsz"]["zdkj"]).grid(row=3, column=0)
tk.Checkbutton(gnsz, text="自动挖矿", variable=config["gnsz"]["zdwk"]).grid(row=3, column=1)
tk.Checkbutton(gnsz, text="自动车位", variable=config["gnsz"]["zdcw"]).grid(row=4, column=0)
tk.Checkbutton(gnsz, text="车位抢夺", variable=config["gnsz"]["cwqd"]).grid(row=4, column=1)
tk.Checkbutton(gnsz, text="烈焰山洞", variable=config["gnsz"]["lysd"]).grid(row=5, column=0)
tk.Checkbutton(gnsz, text="报名打鱼", variable=config["gnsz"]["bmdy"]).grid(row=5, column=1)
tk.Checkbutton(gnsz, text="跟班宿舍", variable=config["gnsz"]["gbss"]).grid(row=6, column=0)

notebook.add(scsz := tk.Frame(notebook), text="偷菜设置")
tk.Label(scsz, text="偷菜入口", pady=5).grid(row=0, column=0)
tk.Checkbutton(scsz, text="仇人", variable=config["tcsz"]["tcrk"]["cr"]).grid(
    row=0, column=1
)
tk.Checkbutton(scsz, text="好友", variable=config["tcsz"]["tcrk"]["hy"]).grid(
    row=0, column=2
)
tk.Label(scsz, text="偷菜品种", pady=5).grid(row=1, column=0)
tk.Checkbutton(scsz, text="葫芦", variable=config["tcsz"]["tcpz"]["hl"]).grid(
    row=1, column=1
)
tk.Checkbutton(scsz, text="茄子", variable=config["tcsz"]["tcpz"]["qz"]).grid(
    row=1, column=2
)
tk.Checkbutton(scsz, text="白菜", variable=config["tcsz"]["tcpz"]["bc"]).grid(
    row=1, column=3
)
tk.Label(scsz, text="备用品种", pady=5).grid(row=2, column=0)
tk.Checkbutton(scsz, text="葫芦", variable=config["tcsz"]["bypz"]["hl"]).grid(
    row=2, column=1
)
tk.Checkbutton(scsz, text="茄子", variable=config["tcsz"]["bypz"]["qz"]).grid(
    row=2, column=2
)
tk.Checkbutton(scsz, text="白菜", variable=config["tcsz"]["bypz"]["bc"]).grid(
    row=2, column=3
)
tk.Label(scsz, text="小偷数量", pady=5).grid(row=3, column=0)
tk.Entry(scsz, textvariable=config["tcsz"]["xtsl"], width=1).grid(
    row=3, column=1, sticky="W", padx=[5, 0]
)
tk.Label(scsz, text="成长加成", pady=5).grid(row=3, column=2)
tk.Entry(scsz, textvariable=config["scsz"]["czjc"], width=3).grid(
    row=3, column=3, sticky="W", padx=[5, 0]
)
tk.Checkbutton(scsz, text="使用特级种子", variable=config["scsz"]["tjzz"]).grid(
    row=3, column=4
)
tk.Label(scsz, text="仇人翻页", pady=5).grid(row=4, column=0)
tk.Entry(scsz, textvariable=config["tcsz"]["fycs"]["cr"], width=1).grid(
    row=4, column=1, sticky="W", padx=[5, 0]
)
tk.Label(scsz, text="好友翻页", pady=5).grid(row=4, column=2)
tk.Entry(scsz, textvariable=config["tcsz"]["fycs"]["hy"], width=2).grid(
    row=4, column=3, sticky="W", padx=[5, 0]
)
tk.Checkbutton(scsz, text="凌晨不偷菜", variable=config["tcsz"]["lcbtc"]).grid(
    row=4, column=4, sticky="W"
)
notebook.add(wksz := tk.Frame(notebook), text="挖矿设置")
tk.Label(wksz, text="间隔时间（分钟）", pady=5).grid(row=1, column=0)
tk.Entry(wksz, textvariable=config["wksz"]["jgsj"], width=3).grid(
    row=1, column=1, sticky="W", padx=[5, 0]
)
tk.Checkbutton(wksz, text="无道具自动挖矿", variable=config["wksz"]["wdjzd"]).grid(
    row=0, column=0, columnspan=2
)

notebook.add(cwsz := tk.Frame(notebook), text="车位设置")
tk.Label(cwsz, text="监听间隔（分钟）", pady=5).grid(row=0, column=0)
tk.Entry(cwsz, textvariable=config["cwsz"]["jtjg"], width=5).grid(
    row=0, column=1, sticky="W", padx=[5, 0]
)
tk.Label(cwsz, text="收车时间（小时）", pady=5).grid(row=1, column=0)
tk.Entry(cwsz, textvariable=config["cwsz"]["scsj"], width=5).grid(
    row=1, column=1, sticky="W", padx=[5, 0]
)
tk.Label(cwsz, text="抢夺时间（小时）", pady=5).grid(row=2, column=0)
tk.Entry(cwsz, textvariable=config["cwsz"]["qdsc"], width=5).grid(
    row=2, column=1, sticky="W", padx=[5, 0]
)
tk.Label(cwsz, text="抢夺最大战力", pady=5).grid(row=3, column=0)
tk.Entry(cwsz, textvariable=config["cwsz"]["qdzl"], width=5).grid(
    row=3, column=1, sticky="W", padx=[5, 0]
)
notebook.add(fbsz := tk.Frame(notebook), text="副本设置")
tk.Label(fbsz, text="自动副本", pady=5).grid(row=0, column=0)
tk.Checkbutton(fbsz, text="穿越之门", variable=config["fbsz"]["zdfb"]["syzm"]).grid(
    row=0, column=1
)
tk.Checkbutton(fbsz, text="神灯小偷", variable=config["fbsz"]["zdfb"]["sdxt"]).grid(
    row=0, column=2
)
tk.Checkbutton(fbsz, text="冰龙巢穴", variable=config["fbsz"]["zdfb"]["blcx"]).grid(
    row=0, column=3
)
tk.Checkbutton(fbsz, text="残垣古城", variable=config["fbsz"]["zdfb"]["cygc"]).grid(
    row=0, column=4
)
tk.Checkbutton(fbsz, text="颠倒时序塔", variable=config["fbsz"]["zdfb"]["ddsxt"]).grid(
    row=0, column=5
)
tk.Checkbutton(fbsz, text="焚焰神殿", variable=config["fbsz"]["zdfb"]["fysd"]).grid(
    row=0, column=6
)
tk.Checkbutton(fbsz, text="黑暗试炼", variable=config["fbsz"]["zdfb"]["hasl"]).grid(
    row=0, column=7
)
tk.Label(fbsz, text="扫荡副本", pady=5).grid(row=1, column=0)
tk.Checkbutton(fbsz, text="神灯小偷", variable=config["fbsz"]["sdfb"]["sdxt"]).grid(
    row=1, column=1
)
tk.Checkbutton(fbsz, text="冰龙巢穴", variable=config["fbsz"]["sdfb"]["blcx"]).grid(
    row=1, column=2
)
tk.Checkbutton(fbsz, text="颠倒时序塔", variable=config["fbsz"]["sdfb"]["ddsxt"]).grid(
    row=1, column=3
)
tk.Checkbutton(fbsz, text="焚焰神殿", variable=config["fbsz"]["sdfb"]["fysd"]).grid(
    row=1, column=4
)
notebook.add(gbsz := tk.Frame(notebook), text="跟班设置")
tk.Label(gbsz, text="领取间隔时间（小时）", pady=5).grid(row=0, column=0)
tk.Entry(gbsz, textvariable=config["gbsz"]["jgsj"], width=5).grid(
    row=0, column=1, sticky="W", padx=[5, 0]
)
notebook.add(qtgn := tk.Frame(notebook), text="其他功能")
tk.Label(qtgn, text="需打开监听红包", pady=5).grid(row=0, column=0)
tk.Checkbutton(qtgn, text="自动助力", variable=config["qtgn"]["zdzl"]).grid(row=0, column=1)
tk.Checkbutton(qtgn, text="幸运转盘", variable=config["qtgn"]["xyzp"]).grid(row=0, column=2)

tk.Label(qtgn, text="在线奖励间隔（小时）", pady=5).grid(row=1, column=0)
tk.Entry(qtgn, textvariable=config["qtgn"]["zxjl"], width=1).grid(
    row=1, column=1, sticky="W", padx=[5, 0]
)
tk.Label(qtgn, text="科技升级间隔（分钟）", pady=5).grid(row=2, column=0)
tk.Entry(qtgn, textvariable=config["qtgn"]["zdkj"], width=3).grid(
    row=2, column=1, sticky="W", padx=[5, 0]
)
tk.Label(qtgn, text="设备冲突等待（分钟）", pady=5).grid(row=3, column=0)
tk.Entry(qtgn, textvariable=config["qtgn"]["sbct"], width=3).grid(
    row=3, column=1, sticky="W", padx=[5, 0]
)
tk.Label(root, text="操作日志", pady=2).pack()
text = tk.Text(root, height=6)
text.pack(fill=tk.X)


def run():
    lock.acquire()
    with open("config.json", "w") as f:
        f.write(json.dumps(get_state(config)))
    lock.release()

    from main import start
    from ctrl import running_event

    if running_event.is_set():
        running_event.clear()
        run_button.config(text="启动")
    else:
        running_event.set()
        threading.Thread(target=start, args=[log]).start()
        run_button.config(text="停止")
    pass


def refresh():
    pass


run_button = tk.Button(root, text="启动", command=run)
run_button.pack()


def get_state(config):
    config_value = {}
    for k in config:
        if isinstance(config[k], dict):
            config_value[k] = get_state(config[k])
        else:
            config_value[k] = config[k].get()
    return config_value


def set_state(config, config_value):
    for k in config:
        if isinstance(config[k], dict):
            if k in config_value:
                set_state(config[k], config_value[k])
        else:
            try:
                config[k].set(config_value[k])
            except KeyError:
                pass
    return config


last_str_data = ""


def log(*data):
    import time

    global last_str_data
    seconds_since_epoch = time.time()
    local_time = time.localtime(seconds_since_epoch)
    current_time = time.strftime("%H:%M:%S", local_time)
    str_data = " ".join([str(s) for s in data])
    if str_data != last_str_data:
        text.insert("0.0", f"[{current_time}]{str_data}\n")
        last_str_data = str_data


def get_config():
    try:
        with open("config.json", "r") as f:
            ret = json.loads(f.read())
    except:
        ret = {}
    return ret


def set_config(config):
    with open("config.json", "w") as f:
        f.write(json.dumps(get_state(config)))


if __name__ == "__main__":
    set_state(config, get_config())
    root.mainloop()
