import datetime
import time


def next_time(hour=None, min=None, delta_hour=None, delta_min=None):
    now_time = time.time()
    now_utc8 = now_time + 3600 * 8
    if delta_hour > 0:
        hour = None
    if delta_min > 0:
        min = None
    if hour == 0 and min == 0:
        return now_time + delta_hour * 3600 + delta_min * 60
    if min > 0:
        t0 = now_utc8 - min * 60

    return t0 // 3600


def print_time(t):
    print(time.strftime("%y-%m-%d %H:%M:%S", time.localtime(t)))


tt = time.time()-7.6*3600
print_time(tt)
a = (tt + 8 * 3600) // 3600 // 12 * 3600 * 12 + 10 * 3600
print(a)
print_time(a)
