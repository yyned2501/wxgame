import time
from Libs import App
from config import DOMAIN

app = App(DOMAIN)
if __name__ == '__main__':
    app.screenshot(f"{int(time.time())}.png") 