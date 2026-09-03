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
