from libs.app import App
from libs.state import State
from config import DOMAIN, read_config
from ctrl import Ctrl, running_event

app = App(DOMAIN)
state = State()
app.print = print
from pages import 首页, 家族, 矿山, 科技园, 庄园, 姑姑车位, 副本, 跟班宿舍, 其他
from pages.libs import get_aim, app, state


def start(log=None):
    if log:
        _print = log
        app.print = log
    else:
        _print = print
        app.print = print
    _print("start")
    running_event.set()
    ctrl = Ctrl(app, get_aim)
    state.state = state.read()
    app.config = read_config()
    state.set_state("xtsl", app.config["tcsz"]["xtsl"])
    state.set_state("lcbtc", app.config["tcsz"]["lcbtc"])
    ctrl.add(首页)
    ctrl.add(家族)
    ctrl.add(矿山)
    ctrl.add(科技园)
    ctrl.add(庄园)
    ctrl.add(姑姑车位)
    ctrl.add(副本)
    ctrl.add(跟班宿舍)
    ctrl.add_other(其他)
    ctrl.run()


if __name__ == "__main__":
    start()
