# -*- coding: utf-8 -*-
"""广告相关封装 (激励视频/领取按钮/看广告状态机).

旧逻辑在 `pages/base.py`:
    - ad_close_pos(img) -> (x, y) | None         # 广告页右上角 [关闭] 药丸
    - ad_claim_pos(img) -> (x, y) | None         # 结算页 [领取](看广告)
    - ad_pill_state(img) -> str                   # 'show'/'over'/unknown
    - ad_pill_right(img) -> int                   # 状态药丸右边界
    - ad_black_frac(img) -> float                # 整帧非黑像素占比
    - is_ad_black(img) -> bool                    # 是否黑屏广告
    - screen_div_frac(pw, sc) -> float            # 屏幕通道分歧度

封装成 AdHelper 类. 内部 import pages.base 复用函数 (双轨).

用法:
    ad = AdHelper()
    pos = ad.close_pos(img)               # 找广告页右上 [关闭]
    pos = ad.claim_pos(img)               # 找结算页 [领取]
    state = ad.pill_state(img)            # 'show'/'over' 看广告状态机
    black = ad.is_ad_black(img)           # 是否在看黑屏广告
"""
from pages.base import (
    ad_close_pos, ad_claim_pos,
    ad_pill_state, ad_pill_right,
    ad_black_frac, is_ad_black,
    screen_div_frac,
)


# 实际从 base 抓所有 AD_* / *PILL* 常量 (动态捕获, 避免漏)
def _collect_ad_constants():
    """从 pages.base 抓所有 AD_* / *PILL* 常量."""
    import pages.base as _b
    out = {}
    for name in dir(_b):
        if name.isupper() and ('AD_' in name or 'PILL' in name):
            out[name] = getattr(_b, name)
    return out


_AD_CONSTS = _collect_ad_constants()
globals().update(_AD_CONSTS)


class AdHelper:
    """激励视频广告辅助."""

    # ---- 关闭药丸 ----
    def close_pos(self, img):
        """广告页右上角 [关闭] 药丸 -> (x, y); 没有则 None."""
        return ad_close_pos(img)

    # ---- 领取按钮 ----
    def claim_pos(self, img):
        """结算页 [领取](看广告) -> (x, y); 没有则 None."""
        return ad_claim_pos(img)

    # ---- 状态机 ----
    def pill_state(self, img):
        """状态药丸 -> 'show'/'over'/其他. 看广告状态机核心."""
        return ad_pill_state(img)

    def pill_right(self, img):
        """状态药丸右边界 x 坐标."""
        return ad_pill_right(img)

    # ---- 黑屏判据 ----
    def black_frac(self, img):
        """整帧非黑像素占比 (0~1)."""
        return ad_black_frac(img)

    def is_ad_black(self, img):
        """这一帧是否黑屏广告 (>= 75% 黑色)."""
        return is_ad_black(img)

    # ---- 屏幕通道分歧度 ----
    def screen_div(self, pw_img, sc_img):
        """两条屏幕通道(PrintWindow vs PrintScreen)分歧度 (0~1)."""
        return screen_div_frac(pw_img, sc_img)


__all__ = ['AdHelper',
           # 函数
           'ad_close_pos', 'ad_claim_pos',
           'ad_pill_state', 'ad_pill_right',
           'ad_black_frac', 'is_ad_black', 'screen_div_frac',
           # 常量 (动态从 pages.base 抓)
           *_AD_CONSTS.keys()]