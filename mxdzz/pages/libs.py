from main import app, state


def get_aim():
    methods = {
        "zdfb": ["zdfb"],
        "bmdy": ["bmdy"],
        "lysd": ["lysd"],
        "zdcw": ["zdcw"],
        "cwqd": ["cwqd"],
        "zdwk": ["zdwk"],
        "zdkj": ["zdkj"],
        "jthb": ["jthb"],
        "zxjl": ["zxjl"],
        "gbss": ["gbss"],
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
