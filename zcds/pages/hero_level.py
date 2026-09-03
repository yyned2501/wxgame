# -*- coding: utf-8 -*-
r"""英雄等级面板: 主页左上角那个等级六边形(30,113)点开的页面(真机 2026-09-03 补的第 13 页)

坑(真机 07:48 复现): 这一页根本不在指纹表里 -> 点色全表零命中 -> 白烧一次全图 OCR(675ms),
  而且 OCR 还把它判成 chest_info(日志 07:48:30 "[指纹] chest_info ocr 1.20") ——
  因为两页的面板标题是**同一张蓝横幅 + 白字**, chest_info 的 detect 只要撞上手就白给 1.2 分。
  那一帧的 act 侥幸只走了"关徽章"兜底没点到开箱按钮, 但那属于运气, 不能留。

指纹只取横幅带 y160~190: 面板主体(骑士立绘/六边形属性数字/底部奖励木箱)一升级就变, 不能进指纹。
  probe_hero_diff.py 拿 07:48 与 07:59 两帧逐行比对实测: 只有 y94~116(左上等级进度条
  0/220 -> 50/220) 和 y879~956(底部导航角标)在变, **面板本体 y140~880 完全一致**
  —— 横幅带是这一页唯一可靠的恒定区域。

标定方法(本页新招): tools/pick_print.py 直接选点最好也只有 margin 0.28~0.50, 原因就是上面
  那句"同款蓝横幅" —— chest_info/matching 的横幅只是整体低 ~10px, 点级评分看不出差别。
  于是改成"逐十字单元: 整单元在 188 张异页语料里零命中 + 点级重叠 <=阈值"来选单元
  (scratch/scripts/pick_hero_units2.py), 再用 compose_hero.py 按单元中心拼指纹并全语料复核:
  8 个单元 = 6 个横幅底色 + 2 个"英雄等级"字形笔画(有语义锚点), 共 40 判色点,
  本页 5/5 全中 / 异页误中 0 / margin 0.100(异页最高 matching 只中 4/40 点)。
  margin 偏低是这两页长得像的客观结果; 真正的保险是: 主循环要求连续 2 帧同页才动手,
  而且本页动作层只点右上角关闭徽章(chest_info 的开箱按钮在 y795), 判错也花不了钱。

动作层纯点色 —— 这页没有免费奖励可领, 唯一正确动作是关掉面板回大厅(留着只会卡页):
  红底 #EF4747(deg90) 在带 (430,150,505,205) 内实测 ->
    本页        中心 (469,172) n=262      (5 帧完全一致)
    chest_info  中心 (468,159) n=241~245  (同款徽章, 只比本页低 13px)
    vip_month/p0 该带内 None              (它们的徽章在 y454 / y300)
  中心 y 带 (160,190) + 像素数上下限 150~420 两条带子都不重叠 => 越带/超限一律不动。
"""
import logging

from .base import Page, color_button, color_pixels


class HeroLevelPage(Page):
    name = 'hero_level'
    next_pages = ('lobby', 'unknown')
    act_needs_ocr = False        # 纯点色页: 主循环不为本页跑 OCR

    # 点色指纹: scratch/scripts/compose_hero.py 按单元拼好后全语料复核(勿手改)
    # 1 种形态 x 8 个十字单元(每单元 5 点, 共 40 判色点/形态), 任一形态全中即判为 hero_level; 语料 5/5 全中 / 异页误中 0 / margin 0.12(异页最高只中 5/40 点) / 各形态覆盖 [5] 帧
    # 语料 5/5 全中 / 异页误中 0 / margin 0.100(异页最高只中 4/40 点) / 各形态覆盖 [5] 帧
    # 注意: 全部点都在标题横幅带 y160~190 内 —— 升级会改的内容区(立绘/属性数字/奖励箱)一个都没标
    points = [
        [150, 162, 0x3B469D], [152, 162, 0x3B469D], [148, 162, 0x3B469D],
        [150, 164, 0x3A459C], [150, 160, 0x3F4BA1], [190, 168, 0x3A459C],
        [192, 168, 0x3A459C], [188, 168, 0x3A459C], [190, 170, 0x3A459C],
        [190, 166, 0x3A459C], [350, 162, 0x3B469D], [352, 162, 0x3B469D],
        [348, 162, 0x3B469D], [350, 164, 0x3A459C], [350, 160, 0x3F4BA1],
        [166, 176, 0x3A459C], [168, 176, 0x3A459C], [164, 176, 0x3A459C],
        [166, 178, 0x3A459C], [166, 174, 0x3A459C], [330, 186, 0x3A459C],
        [332, 186, 0x3A459C], [328, 186, 0x303A85], [330, 188, 0x3A459C],
        [330, 184, 0x3A459C], [346, 172, 0x3A459C], [348, 172, 0x3A459C],
        [344, 172, 0x3A459C], [346, 174, 0x3A459C], [346, 170, 0x3A459C],
        [224, 174, 0xDFDFDF], [226, 174, 0xFFFFFF], [222, 174, 0x212760],
        [224, 176, 0x858585], [224, 172, 0x75767A], [324, 172, 0xC9C9C9],
        [326, 172, 0x666668], [322, 172, 0xC9C9C9], [324, 174, 0xFFFFFF],
        [324, 170, 0x272F70],
    ]

    # ---- 动作层点色(与 chest_info 那颗同款徽章靠 y 带划清界限, 数值见文件头实测) ----
    CLOSE_BOX = (430, 150, 505, 205)   # 右上角关闭徽章搜索框(不含顶栏资源图标)
    CLOSE_RED = 0xEF4747
    CLOSE_MIN_PX = 150                # 实测 n=262; 下限挡掉零碎红点(角标/血量)
    CLOSE_MAX_PX = 420                # 上限: 整片红底(广告条/血条)不属于关闭徽章
    CLOSE_Y = (160, 190)              # 中心 y 带; chest_info 恒 159 -> 排除在外

    def detect(self, f):
        # 只在 OCR 兜底分支用(改版/指纹没标上): 标题字样才算, 别指望它当主判据
        return 1.0 if f.has('英雄等级') else 0.0

    def act(self, ctx):
        img = getattr(ctx.f, 'img', None)
        if img is None:
            return False
        pos = color_button(img, self.CLOSE_BOX, self.CLOSE_RED, self.CLOSE_MIN_PX)
        if pos is None:
            return False
        n = color_pixels(img, self.CLOSE_BOX, self.CLOSE_RED)
        cx, cy = pos
        if n > self.CLOSE_MAX_PX or not (self.CLOSE_Y[0] <= cy <= self.CLOSE_Y[1]):
            # 长得像别的页的红块(chest_info 的徽章在 y159) -> 一律不动
            logging.info(f'[英雄等级] 红块 {pos} n={n} 不在关闭徽章带内 -> 不动')
            return False
        if ctx.acted('hero_close', gap=8.0):
            return True
        logging.info(f'[英雄等级] 点色命中关闭徽章 {pos} n={n}')
        ctx.click(cx, cy)
        return True