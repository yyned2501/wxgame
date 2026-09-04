# -*- coding: utf-8 -*-
"""页面轮询/OCR 配置 (CPU 优化核心)

roi:     (fx0, fy0, fx1, fy1) 窗口坐标比例, None=全图
scale:   ROI 缩放比例(喂给 OCR)
poll:    主循环 sleep 间隔(秒)
ocr_gap: 两次 OCR 最小间隔(秒); 战斗用颜色扫描所以给超大值
"""
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
SHOTS_DIR = os.path.join(ROOT, 'shots')      # 截图输出目录(兜底截图也写这里)

# 是否点"看广告/领取礼包"类按钮。
# 2026-09-03 12:47 用户定案: **打开** —— "点击黄色的看广告领取, 可以看广告的地方就自动看完"。
# 配套改动(不是简单翻这个开关):
#   1) 结算页[领取]改纯点色识别(ad_claim_pos), 不再 OCR 找"领取"两个字;
#   2) 广告页不再点[放弃], 改成"看完再关"(auto_bot 的看广告窗口 + ad_pill_right 放奖判据);
#   3) 中途关广告会弹"是否继续观看视频"挽留框 -> 那一屏现在点[继续观看]而不是[放弃]。
WATCH_ADS = True

# 点[领取]之前要不要先把游戏窗口带到前台(= 广告能不能出量的前提)。
# 依据(两批真机帧对比):
#   2026-08-24 12:47 用户在场、窗口在前台 -> 点[领取]后结算页原地停留 ~12s, 然后真的盖上黑屏广告
#     (shots/watch_124707 非黑 37.6% = 黑屏正在盖上, watch_124711/124723 非黑 5~6% = 广告在放);
#   2026-09-04 03:49~04:08 后台跑了 7 次点[领取] -> 每一次 +3s 的取证帧非黑都是 96%
#     (= 还是游戏自己的页), 一条广告都没起来。目前唯一的差别就是有没有在前台。
# 微信激励视频是 XWEB 的独立渲染层, 小程序被判定不可见时可能直接不给量。
# 真机若证明抢前台没用(照样无量), 这里改 False 关掉, 别让它白抢焦点。
AD_FOCUS = True

PAGE_CFG = {
    'lobby':        dict(roi=(0.0, 0.55, 1.0, 0.90), scale=0.6, poll=3.0, ocr_gap=10.0),
    'battle':       dict(roi=(0.0, 0.46, 1.0, 0.90), scale=0.5, poll=3.0, ocr_gap=600.0),
    'matching':     dict(roi=(0.0, 0.15, 1.0, 0.90), scale=0.5, poll=4.0, ocr_gap=8.0),
    'result':       dict(roi=None, scale=0.5, poll=3.0, ocr_gap=6.0),
    'chest_info':   dict(roi=(0.0, 0.10, 1.0, 0.90), scale=0.5, poll=3.0, ocr_gap=6.0),
    'chest_open':   dict(roi=None, scale=0.5, poll=3.0, ocr_gap=6.0),  # 底部按钮文字 y~917 / 跳过 y~143: 必须全图
    'claim_popup':  dict(roi=None, scale=0.5, poll=3.0, ocr_gap=6.0),
    'diamond_popup': dict(roi=None, scale=0.5, poll=3.0, ocr_gap=6.0),
    'vip_popup':    dict(roi=None, scale=0.5, poll=3.0, ocr_gap=6.0),
    'ad_popup':     dict(roi=None, scale=0.5, poll=3.0, ocr_gap=3.0),  # 放弃/关闭 分布在 y88~609: 必须全图
    'levelup':      dict(roi=None, scale=0.5, poll=3.0, ocr_gap=999.0),  # 纯点色页: 指纹定页 + 黄按钮点色 -> 永不跑 OCR
    'hero_level':   dict(roi=None, scale=0.5, poll=3.0, ocr_gap=999.0),  # 纯点色页: 指纹定页 + 关闭徽章点色 -> 永不跑 OCR
    'versus':       dict(roi=None, scale=0.5, poll=3.0, ocr_gap=999.0),  # VS 页只等游戏自己进战斗: 指纹定页 -> 永不跑 OCR
    'unknown':      dict(roi=None, scale=0.5, poll=8.0, ocr_gap=15.0),
}
