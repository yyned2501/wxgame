# -*- coding: utf-8 -*-
"""激励视频广告业务 (从 pages/base.py 抽出).

含 22 个常量 + 7 个函数:
- ad_close_pos(img): 黑屏广告右上角 [关闭] 药丸
- ad_claim_pos(img): 结算页 [领取](看广告) 按钮
- ad_pill_state(img): 广告页左上状态药丸 -> (右边界x, 白像素, 左边界x)
- ad_pill_right(img): 状态药丸右边界
- ad_black_frac(img): 整帧非黑像素占比
- is_ad_black(img): 是否黑屏广告
- screen_div_frac(pw, sc): 屏幕通道 vs PrintWindow 分歧度

调用: from business.ad import ad_close_pos
旧代码兼容: from pages.base import ad_close_pos (pages/base.py re-export)
"""
from colorprint import to_arr, color_mask, _clip_box


# ---- 黑屏广告主体判据 (抽自 pages/base.py L569-582) ----
AD_BODY_Y0 = 50
AD_BODY_MEAN_MAX = 30.0
AD_BODY_WHITE_MAX = 0.03


# ---- 广告页右上角[关闭]药丸 (L583-605) ----
AD_CLOSE_BAND = (45, 118)
AD_CLOSE_X0 = 432
AD_CLOSE_WHITE_MIN = 10
AD_CLOSE_BOX = ((30, 60), (30, 60))


def ad_close_pos(img):
    """黑屏广告页右上角[关闭]药丸的中心 -> (x, y); 认不出返回 None. 纯点色, ~1ms"""
    import numpy as np
    a = to_arr(img)
    h, w = a.shape[:2]
    # 前置: 主体必须是黑的。正常页的顶栏同样有白字(大厅/商店/行会实测全部误命中),
    # 而这张页除了顶栏整片是纯黑 —— 这条既是身份判据, 也是防误点的保险。
    body = a[AD_BODY_Y0:min(AD_BODY_Y0 + 700, h), :]
    if float(body.mean()) > AD_BODY_MEAN_MAX or float((body.max(axis=2) > 190).mean()) > AD_BODY_WHITE_MAX:
        return None
    y0, y1 = AD_CLOSE_BAND
    x0 = min(AD_CLOSE_X0, w - 1)
    reg = a[y0:min(y1, h), x0:w]
    m = (reg[..., 0] > 190) & (reg[..., 1] > 190) & (reg[..., 2] > 190)
    if int(m.sum()) < AD_CLOSE_WHITE_MIN:
        return None
    ys, xs = np.nonzero(m)
    bw, bh = int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)
    (w_lo, w_hi), (h_lo, h_hi) = AD_CLOSE_BOX
    if not (w_lo <= bw <= w_hi and h_lo <= bh <= h_hi):
        return None
    return int(x0 + (xs.min() + xs.max() + 1) // 2), int(y0 + (ys.min() + ys.max() + 1) // 2)


# ---- 结算页[领取]黄按钮 (L608-646) ----
AD_CLAIM_BOX = (300, 700, 552, 880)
AD_CLAIM_COLOR = 0xFDCA33
AD_CLAIM_DEGREE = 90
AD_CLAIM_MIN_PX = 2200
AD_CLAIM_W = (108, 145)
AD_CLAIM_H = (26, 50)


def ad_claim_pos(img):
    """黄色[领取](看广告)按钮中心 -> (x, y); 这一帧没有横幅/按钮已灰掉 -> None. 纯点色 ~1ms"""
    import numpy as np
    b = _clip_box(img, AD_CLAIM_BOX)
    if b is None:
        return None
    x0, y0 = b[0], b[1]
    m = color_mask(img, AD_CLAIM_BOX, AD_CLAIM_COLOR, AD_CLAIM_DEGREE)
    if int(m.sum()) < AD_CLAIM_MIN_PX:
        return None
    ys, xs = np.nonzero(m)
    bw, bh = int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)
    if not (AD_CLAIM_W[0] <= bw <= AD_CLAIM_W[1] and AD_CLAIM_H[0] <= bh <= AD_CLAIM_H[1]):
        return None
    return int(x0 + (xs.min() + xs.max() + 1) // 2), int(y0 + (ys.min() + ys.max() + 1) // 2)


# ---- 广告页左上角状态药丸 (L649-678) ----
AD_PILL_BAND = (55, 118, 0, 330)
AD_PILL_MIN_COLS = 2
AD_PILL_SHRINK = 28
AD_PILL_SHRINK_PCT = 0.15
AD_PILL_LOW_HOLD = 4.0
AD_PILL_LEFT_TOL = 20


# ---- 黑屏广告判据 (L679-707) ----
AD_BLACK_MAX_FRAC = 0.25
AD_DIVERGE_FRAC = 0.25
AD_DIVERGE_PIX = 40


def ad_black_frac(img):
    """整帧非黑像素占比(0~1)。黑 = R/G/B 最大值 <= 24。"""
    import numpy as np
    a = to_arr(img)[:, :, :3]
    return float((a.max(2) > 24).mean())


def is_ad_black(img):
    """这一帧是不是"黑屏广告"(纯黑画布 + 顶栏) -> 见 AD_BLACK_MAX_FRAC 的实测依据"""
    return ad_black_frac(img) < AD_BLACK_MAX_FRAC


def screen_div_frac(pw_img, sc_img):
    """屏幕像素 与 PrintWindow 像素 的分歧度 = 逐像素最大通道差 > AD_DIVERGE_PIX 的比例."""
    import numpy as np
    if pw_img.size != sc_img.size:
        sc_img = sc_img.resize(pw_img.size)
    a = to_arr(pw_img)[:, :, :3].astype('int16')
    b = to_arr(sc_img)[:, :, :3].astype('int16')
    return float((np.abs(a - b).max(2) > AD_DIVERGE_PIX).mean())


def ad_pill_state(img):
    """广告页左上状态药丸 -> (右边界 x, 带内白像素数, 左边界 x); 这一帧没有顶栏 -> None"""
    import numpy as np
    y0, y1, x0, x1 = AD_PILL_BAND
    a = to_arr(img)
    h, w = a.shape[:2]
    reg = a[y0:min(y1, h), x0:min(x1, w), :3].astype(np.int16)
    if reg.size == 0:
        return None
    m = (reg.max(axis=2) > 170)
    cols = m.sum(axis=0)
    nz = np.nonzero(cols >= AD_PILL_MIN_COLS)[0]
    if not len(nz):
        return None
    return int(nz.max()) + x0, int(m.sum()), int(nz.min()) + x0


def ad_pill_right(img):
    """药丸右边界(第一把尺子); 这一帧没有顶栏(不是广告页) -> None"""
    st = ad_pill_state(img)
    return st[0] if st else None


__all__ = [
    # 函数
    'ad_close_pos', 'ad_claim_pos',
    'ad_pill_state', 'ad_pill_right',
    'ad_black_frac', 'is_ad_black', 'screen_div_frac',
    # 常量
    'AD_BODY_Y0', 'AD_BODY_MEAN_MAX', 'AD_BODY_WHITE_MAX',
    'AD_CLOSE_BAND', 'AD_CLOSE_X0', 'AD_CLOSE_WHITE_MIN', 'AD_CLOSE_BOX',
    'AD_CLAIM_BOX', 'AD_CLAIM_COLOR', 'AD_CLAIM_DEGREE',
    'AD_CLAIM_MIN_PX', 'AD_CLAIM_W', 'AD_CLAIM_H',
    'AD_PILL_BAND', 'AD_PILL_MIN_COLS', 'AD_PILL_SHRINK',
    'AD_PILL_SHRINK_PCT', 'AD_PILL_LOW_HOLD', 'AD_PILL_LEFT_TOL',
    'AD_BLACK_MAX_FRAC', 'AD_DIVERGE_FRAC', 'AD_DIVERGE_PIX',
]