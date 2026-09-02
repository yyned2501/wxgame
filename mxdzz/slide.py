from PIL import Image, ImageFilter
import numpy as np
import time, os
os.makedirs("slide", exist_ok=True)

def get_slide_pix(img_arr: np.ndarray):
    t = int(time.time())
    img = Image.fromarray(img_arr)
    img_L = img.convert("L")
    img_LS = img_L.filter(ImageFilter.SHARPEN)
    find_img_left = img_LS.crop([60, 356, 61, 524])
    find_img_left_arr = np.array(find_img_left)
    y0 = None
    for lc in range(0, 255, 10):
        left_where = np.where(find_img_left_arr < lc)[0]
        if len(left_where) > 50:
            y0, y1 = left_where[0], left_where[-1]
            break
    if not y0:
        img.save(f"slide/unfind_slide_{t}.png")
        return np.random.randint(10, 80)
    img_slide = img_LS.crop([64, 356, 387, 524])
    img_slide_arr = np.array(img_slide)
    img_slide_arr_cut = img_slide_arr[y0:y1, :].astype(np.intc)
    delta_arr_cut = img_slide_arr_cut[:, :-1] - img_slide_arr_cut[:, 1:]
    right_img_slide_arr_cut = img_slide_arr_cut[:15, :]
    delta_right_arr_cut = (
        right_img_slide_arr_cut[:, 1:] - right_img_slide_arr_cut[:, :-1]
    )
    left_pix, right_pix = None, None
    for lc in range(0, 200, 10):
        pix_where = np.where((delta_arr_cut > (255 - lc)).all(0))[0]
        right_pix_where = np.where((delta_right_arr_cut > (255 - lc)).all(0))[0]
        if len(pix_where) > 0:
            left_pix = pix_where[0]
            if left_pix > 74:
                img.save(f"slide/find_slide_{t}_l{left_pix}.png")
                return left_pix
        if len(right_pix_where) > 0:
            right_pix = right_pix_where[0]
            if right_pix <= 145:
                img.save(f"slide/find_slide_{t}_r{right_pix}.png")
                return right_pix - 66
    img.save(f"slide/unfind_slide_{y0}_{y1}_{t}.png")
    return np.random.randint(10, 80)
