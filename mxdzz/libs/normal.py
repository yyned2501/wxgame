import datetime


def get_tomorrow_timestamp():
    now = datetime.datetime.now()
    tomorrow = now + datetime.timedelta(days=1)
    tomorrow_midnight = datetime.datetime(tomorrow.year, tomorrow.month, tomorrow.day)
    timestamp = tomorrow_midnight.timestamp()
    return timestamp


def is_today(timestamp):
    try:
        date_from_timestamp = datetime.datetime.fromtimestamp(timestamp)
        current_date = datetime.datetime.now()
        return date_from_timestamp.date() == current_date.date()
    except Exception as e:
        print(f"An error occurred: {e}")
        return False


def format_seconds(seconds):
    # 转换秒数为时分秒
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    remaining_seconds = seconds % 60

    # 格式化时分秒
    time_str = f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"

    return time_str
