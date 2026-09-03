# -*- coding: utf-8 -*-
"""离线「动作层零 OCR」回归: result / chest_open / lobby / chest_info / levelup / hero_level 六页 act() 全程不碰文字识别

用户定案(2026-09-03): OCR 准确率太低而且速度太慢 —— 定页面用点色指纹, 点哪里也必须用点色。
本脚本把 ctx 换成假桩, need_text() 与 f.find()/f.has() 一被调用就抛, 于是同时钉死几件事:
  1) 这几页的 act_needs_ocr 必须是 False(主循环据此决定要不要为本页跑一次 OCR, 真机 369~675ms)
  2) act() 里不许偷偷去读字 —— 读了就当场抛, 记一条失败
  3) 每帧点到的坐标必须等于人工核对过的真值(点色取按钮外接框中心, 两种版式中心差 80px, 写死必错)
  4) 该不动作的帧(广告盖脸、两处白块都未出)一次都不许点
用法(项目根目录): python -X utf8 test_act_zero_ocr.py     # 退出码 0 = 全通过
"""
import glob
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from PIL import Image, ImageDraw

import pick_print as pp
from pages import ALL_PAGES
from pages.chest_info import ChestInfoPage
from pages.chest_open import ChestOpenPage
from pages.hero_level import HeroLevelPage
from pages.levelup import LevelUpPage
from pages.lobby import CHEST_SLOTS, LobbyPage
from pages.result import ResultPage
from vision import ScreenFeature

PVP = (180, 675)                    # [玩家对战]按钮外接框中心(33 帧实测恒定)
ALLOWED = set(CHEST_SLOTS) | {PVP}  # 大厅唯一允许的 5 个落点

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print('  FAIL  ' + msg)


class ZeroOcr(Exception):
    """动作层想去读文字 —— 纯点色页出现即失败"""


class NoText(ScreenFeature):
    """只给一张图, 不给文字框: 任何按文字定位的写法都会当场抛 ZeroOcr"""

    def find(self, *a, **k):
        raise ZeroOcr('f.find()')

    def find_boxes(self, *a, **k):
        raise ZeroOcr('f.find_boxes()')

    def has(self, *a, **k):
        raise ZeroOcr('f.has()')

    def near(self, *a, **k):
        raise ZeroOcr('f.near()')


class Ctx:
    """假 ctx: 记录点击与被问过的节流键; need_text() 直接抛(真机上那是一次 ROI/全图 OCR)"""

    dry_run = False

    def __init__(self, img, blocked=()):
        self.f = NoText(img=img, boxes=[], joined='')
        self.clicks = []
        self.keys = []
        self.battles = 0
        self._done = set(blocked)
        self.chest_target = None
        self._blacklist = set()
        self.ad_watch = []               # start_ad_watch() 的调用原因(= 看广告窗口被 arm 过)

    # ---- 拉黑接口(与 App.block/is_blocked 同语义, 见 pages/base.py chest_slot_key) ----
    def block(self, key, sec, why=''):
        self._blacklist.add(key)

    def is_blocked(self, key):
        return key in self._blacklist

    def click(self, x, y):
        self.clicks.append((int(x), int(y)))

    def acted(self, key, gap=6.0):
        # 与 App.acted 同语义: 首次 False(可以点), 同一键重复问 True(被节流, 别动)
        self.keys.append(key)
        if key in self._done:
            return True
        self._done.add(key)
        return False

    def start_ad_watch(self, why=''):
        self.ad_watch.append(why)

    def need_text(self):
        raise ZeroOcr('ctx.need_text()')


def label_frames(label):
    """语料标签 -> {帧名主干: PIL 图}(只认真实存在的 shots/*.png)"""
    out = {}
    for nm in pp.LABELS[label]:
        path = pp.img_path(nm)
        if not path or not os.path.isfile(path):
            continue
        out[os.path.basename(path).rsplit('.', 1)[0]] = Image.open(path).convert('RGB')
    return out


def run(page, img, ctx):
    """跑一次 act(), 把 ZeroOcr 折算成失败项"""
    try:
        return bool(page.act(ctx))
    except ZeroOcr as e:
        check(False, '%s.act() 读了文字: %s' % (page.name, e))
        return False


def blank(img, box):
    im = img.copy()
    ImageDraw.Draw(im).rectangle(box, fill=(0x2E, 0x26, 0x5F))   # 该处底色 = 把这块白色抠掉
    return im


def main():
    print('[1] 声明自检: 纯点色页必须声明 act_needs_ocr=False, 主循环才不会为它跑 OCR')
    for cls in (ResultPage, ChestOpenPage, LobbyPage, ChestInfoPage, LevelUpPage, HeroLevelPage):
        p = cls()
        check(p.act_needs_ocr is False, '%s.act_needs_ocr 应为 False' % p.name)
    left = ' '.join(p.name for p in ALL_PAGES if p.act_needs_ocr)
    print('    动作层仍需读文字的页: %s' % (left or '(无)'))

    print('[2] 结算页: 亮紫按钮外接框中心 —— 有礼包横幅 830 / 无横幅 912 / 真机 910'
          ' (带黄色[领取]的先去看广告)')
    # 逐帧真值来源 scratch/scripts/act_truth.py (2026-09-03 dump, 明细 scratch/o_act.txt)
    # watch_124707: 激励视频盖在结算页上, 扫不到那块亮紫 -> 本帧必须不动作
    #   (旧版靠 OCR 找"点击继续", 读到遮罩上的广告文案就瞎点一次, 真机就是这样把广告点开的)
    EXPECT = {
        'flow3_end1': (275, 830), 'flow3_r1': (275, 830), 'flow4_s0_result': (275, 830),
        'now': (275, 912), 'st_1': (275, 912), 'help_live': (275, 912),
        'watch_124652': (275, 912), 'watch_124654': (275, 912), 'watch_124656': (275, 912),
        'watch_124658': (275, 912), 'watch_124700': (275, 912), 'watch_124705': (275, 912),
        'watch_124707': None,
        'result_live005639': (275, 910), 'result_live010726': (275, 910),
        'result_live010729': (275, 910),
        # 2026-09-03 03:09/03:14 真机三帧(同一版式, 亮紫按钮中心 910)
        'result_live030901': (275, 910), 'result_live030920': (275, 910),
        'result_live031408': (275, 910),
        # 2026-09-03 03:11/03:54/04:08 真机三帧: 核对过裁图, 亮紫块是[点击继续],
        # 不是"看广告翻倍"(那一颗在更上面, 且 WATCH_ADS=False 时永远不该碰)
        'result_live031108': (275, 910), 'result_live035436': (275, 910),
        'result_live040817': (275, 910),
        # 真机第 24 轮 20:14: 定页那帧原本只能靠 OCR —— 指纹 unit0 站在 MVP 角色动画上
        #   (红龙 + 闪光盖住), 已换到 (26,192) 纯背景 -> pages/result.py.
        #   动作层没问题: 这一帧**没有**礼包横幅, 所以亮紫[继续]在 829(= 无横幅版式的 830)。
        'result_live201449': (275, 829),
    }
    # 带黄色[领取]药丸的帧(ad_claim_pos 实测命中, 明细 scratch/scripts/claim_frames_0903.py):
    # act() 必须先点 (412,782) 去看广告, 而且这一轮**不算一场**(battles 不动), 同时把
    # "看广告窗口" arm 起来 —— 用户 2026-09-03 12:47 定案"可以看广告的地方就自动看完"。
    CLAIMED = {
        'now', 'help_live', 'watch_124652', 'watch_124654', 'watch_124656', 'watch_124658',
        'watch_124700', 'watch_124705', 'result_live005639', 'result_live010726',
        'result_live010729', 'result_live030901', 'result_live030920', 'result_live031108',
        'result_live031408', 'result_live035436', 'result_live040817',
    }
    CLAIM = (412, 782)
    rp = ResultPage()
    frames = label_frames('result')
    check(set(frames) == set(EXPECT),
          'result 语料帧(%d)与码表(%d)脱节: %s'
          % (len(frames), len(EXPECT), sorted(set(frames) ^ set(EXPECT))))
    for nm, want in sorted(EXPECT.items()):
        img = frames.get(nm)
        if img is None:
            continue
        want = CLAIM if nm in CLAIMED else want
        ctx = Ctx(img)
        hit = run(rp, img, ctx)
        got = ctx.clicks[0] if len(ctx.clicks) == 1 else None
        near = (want is not None and got is not None
                and abs(got[0] - want[0]) <= 3 and abs(got[1] - want[1]) <= 3)
        check(near if want else not ctx.clicks,
              'result/%s 点击 %s != %s' % (nm, ctx.clicks, want))
        check(hit == (want is not None),
              'result/%s act 返回 %s 与是否点击不一致' % (nm, hit))
        check(ctx.battles == (1 if (want is not None and nm not in CLAIMED) else 0),
              'result/%s 场次计数 %d 不应对(去看广告那一轮不算一场, 真点了[继续]才算)'
              % (nm, ctx.battles))
        check((ctx.ad_watch == ['结算礼包']) == (nm in CLAIMED),
              'result/%s 看广告窗口 %s 与黄色[领取]在不在不一致' % (nm, ctx.ad_watch))
    print('    %d 帧零 OCR: %d 帧先去看广告, %d 帧直接点[继续], '
          'watch_124707(广告盖脸)正确地一次没点' % (len(EXPECT), len(CLAIMED),
                                                    len(EXPECT) - len(CLAIMED) - 1))

    print('[3] 开箱动画: 底部白色按钮块 -> 领取/关闭同一点; 左上[跳过]只在按钮未出时点')
    EXPECT = {
        'chest_open_claim': ((275, 917), 'chest_open_claim'),
        'chest_open_live014202': ((275, 917), 'chest_open_claim'),
        'chest_open_close': ((275, 917), 'chest_open_close'),
        'chest_open_reward': ((275, 917), 'chest_open_close'),
        'chest_open_live005718': ((275, 917), 'chest_open_close'),
        'chest_open_live014205': ((275, 917), 'chest_open_close'),
        # 真机 01:08:03: 左上[跳过]已消失 = 关闭态(人眼核对 scratch/images/co_010803.png)
        'chest_open_live010803': ((275, 917), 'chest_open_close'),
        # 真机 03:51:01: 底部白字=点击关闭, bot=1394 skip=0(核对 scratch/chk_co_bot.png)
        'chest_open_live035101': ((275, 917), 'chest_open_close'),
    }
    co = ChestOpenPage()
    frames = label_frames('chest_open')
    check(set(frames) == set(EXPECT),
          'chest_open 语料帧(%d)与码表(%d)脱节: %s'
          % (len(frames), len(EXPECT), sorted(set(frames) ^ set(EXPECT))))
    for nm, (want, tag) in sorted(EXPECT.items()):
        img = frames.get(nm)
        if img is None:
            continue
        ctx = Ctx(img)
        run(co, img, ctx)
        check(ctx.clicks == [want], 'chest_open/%s 点击 %s != %s' % (nm, ctx.clicks, want))
        check(ctx.keys and ctx.keys[-1] == tag,
              'chest_open/%s 节流键 %s != %s(领取/关闭认反会漏领或提前关)' % (nm, ctx.keys, tag))
    # 语料 6 帧底部按钮都已出现, 走不到[跳过]分支 -> 抠掉底带造一帧"动画还在放"的假帧
    claim = frames.get('chest_open_claim')
    if claim is not None:
        ctx = Ctx(blank(claim, co.BOT_BOX))
        run(co, ctx.f.img, ctx)
        check(ctx.clicks == [(82, 142)],
              '动画期(底部按钮未出)应点左上[跳过] {0}, 实际 {1}'.format((82, 142), ctx.clicks))
        ctx = Ctx(blank(blank(claim, co.BOT_BOX), co.SKIP_BOX))
        run(co, ctx.f.img, ctx)
        check(ctx.clicks == [], '两处白块都没有时必须不动作, 实际 %s' % (ctx.clicks,))

    print('[4] 大厅: 免费宝箱优先, 无免费格则试探点 p 格, [AD]加速格一律不点, 实在没得点才打一局')
    # 槽位状态码(o=[开启] U=[点击解锁]+红角标=免费 p=[点击解锁]无角标=要宝石 a=[AD]加速 .=空)
    # 的逐帧真值回归在 test_print_route.py [9]
    # 这里只钉 act 的落点: 冷却/空槽帧必须退到[玩家对战], 半程帧必须跳到可点那一格
    EXPECT = {
        'lobby_clean': CHEST_SLOTS[0],              # UUUU
        'guide_live2': CHEST_SLOTS[0],              # oUUU
        # 2026-09-03 晚用户口径: 三格白字[点击解锁]全都没红角标 -> **试探点最左那格 p**,
        #   免费/付费由 chest_info 面板的宝石像素硬闸判(付费只关面板+拉黑该格, 不会花宝石)
        'live_lobby': CHEST_SLOTS[0],               # pppa  试探槽1(p); 槽4 是[AD], 更不许点
        'live_now2': CHEST_SLOTS[0],                # UUUo
        'lobby_live010733': CHEST_SLOTS[0],         # Uo..
        'flow4_s1_after_continue': CHEST_SLOTS[0],  # U...
        'live_20260902_a': CHEST_SLOTS[0],          # o...
        'lobby_chest_ready_2355': CHEST_SLOTS[0],   # o...
        'lobby_mixed_0019': CHEST_SLOTS[1],         # ap..  槽1 冷却 -> 试探槽2 那格 p
        'lobby_live004222': CHEST_SLOTS[1],         # .u..
        'lobby_cooling_2335': PVP,                  # a...  唯一一格要点的是看广告(没 p 可试) -> 打一局
        'lobby_live010807': PVP,                    # a...
        'lobby_live014209': PVP,                    # ....
        'step0_main': PVP,                          # ....
        'after_click': PVP,                         # ....
    }
    frames = label_frames('lobby')
    lp = LobbyPage()
    for nm, want in sorted(EXPECT.items()):
        img = frames.get(nm)
        if img is None:
            check(False, 'lobby 码表帧 %s 不在语料里(改名了?)' % nm)
            continue
        ctx = Ctx(img)
        run(LobbyPage(), img, ctx)   # 逐帧判落点必须用新实例: 轮换游标是实例状态
        check(ctx.clicks == [want], 'lobby/%s 点击 %s != %s' % (nm, ctx.clicks, want))
    # 全量兜底: 每帧必须只点一次, 落点只能在 4 个宝箱槽或玩家对战按钮上, 且绝不点[AD]格
    n = 0
    for nm, img in sorted(frames.items()):
        ctx = Ctx(img)
        run(lp, img, ctx)
        n += 1
        check(len(ctx.clicks) == 1 and ctx.clicks[0] in ALLOWED,
              'lobby/%s 落点异常 %s' % (nm, ctx.clicks))
        st = lp.chest_states(img)
        for i, ch in enumerate(st):
            if ch == 'a':
                check(ctx.clicks[0] != CHEST_SLOTS[i],
                      'lobby/%s 把第 %d 格[AD]加速点成了免费开箱' % (nm, i + 1))
    print('    %d 帧: 每帧恰好一次点击, 落点只在 4 槽 + 玩家对战, 从不点[AD]格' % n)
    # 轮换: 真机教训 —— 旧版死点 ready[0], 那一格若点了没跳转就永远卡在同一坐标
    img = frames.get('lobby_clean')
    if img is not None:
        lp2 = LobbyPage()
        got = []
        for _ in range(len(CHEST_SLOTS)):
            ctx = Ctx(img)
            run(lp2, img, ctx)
            got.extend(ctx.clicks)
        check(got == list(CHEST_SLOTS), '4 格全可点时应左->右轮换, 实际 %s' % (got,))
        ctx = Ctx(img)
        run(lp2, img, ctx)                 # 第 5 次: 游标绕回槽1, 仍然要有动作
        check(ctx.clicks == [CHEST_SLOTS[0]], '轮换绕回后应回到槽1, 实际 %s' % (ctx.clicks,))

    print('[5] WATCH_ADS 开关: 默认必须开着, 且两个方向都零 OCR(点色认[领取], 不再读字)')
    import pages.result as res
    img = label_frames('result').get('result_live005639')   # 带黄色[领取]横幅的帧
    if img is not None:
        old = res.WATCH_ADS
        try:
            res.WATCH_ADS = False
            ctx = Ctx(img)
            run(rp, img, ctx)
            check(ctx.clicks == [(275, 910)] and not ctx.ad_watch,
                  'WATCH_ADS=False 应直接点[继续]且不开广告窗口, 实际 %s 窗口=%s'
                  % (ctx.clicks, ctx.ad_watch))
            res.WATCH_ADS = True
            ctx = Ctx(img)
            run(rp, img, ctx)
            check(len(ctx.clicks) == 1 and abs(ctx.clicks[0][0] - 412) <= 3
                  and abs(ctx.clicks[0][1] - 782) <= 3,
                  'WATCH_ADS=True 应先点黄色[领取](412,782), 实际 %s' % (ctx.clicks,))
            check(ctx.ad_watch == ['结算礼包'], '点了[领取]却没 arm 看广告窗口: %s' % (ctx.ad_watch,))
        finally:
            res.WATCH_ADS = old
    check(res.WATCH_ADS is True, 'WATCH_ADS 默认必须开(用户 2026-09-03 12:47 定案: 能看就自动看完)')

    print('[6] 宝箱面板: 黄按钮用点色找 / 付费用带内宝石像素判 —— 价格护栏也脱开文字了')
    # 旧版护栏全靠 OCR 读"钻石/宝石/￥", 又慢又不准: 真机 00:57 把"紫宝石图标+30"读成裸数字
    # 漏判, 机器人真替玩家花掉 30 宝石。现在主判据是颜色, 本节点死"整页一个字都不读"。
    ci = ChestInfoPage()
    # 真值 = 语料文件名(命名即身份, 见 tools/pick_print.py LABELS):
    #   chest_info_paid_*   要花钱的面板(人眼核对: 按钮带内紫宝石像素 362)
    #   其余 chest_info_*   免费面板
    # 注: 以前这里是 glob 整个 shots_live/ 再配一张硬编码付费名单 —— 每跑一次真机就多出一堆
    #     同版面帧, 名单没跟上就假失败(2026-09-03 04:00 挂了 17 项)。真值只准从 shots/ 来。
    frames = dict(label_frames('chest_info'))
    n_ci = 0
    for nm, img in sorted(frames.items()):
        is_paid = '_paid' in nm
        ctx = Ctx(img)
        run(ci, img, ctx)
        x, y = ctx.clicks[0] if len(ctx.clicks) == 1 else (-1, -1)
        on_btn = ci.BTN_BOX[0] <= x <= ci.BTN_BOX[2] and ci.BTN_BOX[1] <= y <= ci.BTN_BOX[3]
        check(on_btn != is_paid, 'chest_info/%s 点击 %s(应该%s)'
              % (nm, ctx.clicks, '只点关闭' if is_paid else '点中黄按钮'))
        n_ci += 1
    n_paid = sum(1 for nm in frames if '_paid' in nm)
    check(n_paid >= 4 and n_ci >= 14,
          'chest_info 真值帧太少(共 %d, 付费 %d) -> 语料被清了?' % (n_ci, n_paid))
    print('    %d 帧(含 %d 张付费)全程没读一个字' % (n_ci, n_paid))

    print(u'[7] 升级领奖页: 黄色"领取"按钮 —— 必须和宝箱面板那块同色按钮划清界限')
    lu_frames = label_frames('levelup')
    check(len(lu_frames) >= 3, u'levelup 语料帧太少(%d) -> 语料被清了?' % len(lu_frames))
    for nm, img in sorted(lu_frames.items()):
        ctx = Ctx(img)
        got = run(LevelUpPage(), img, ctx)
        check(got and ctx.clicks == [(275, 776)],
              u'levelup/%s 点击 %s != [(275, 776)]' % (nm, ctx.clicks))
    # 反向互斥: 宝箱面板那块是**同一颜色**(#FDCA33)的黄按钮, 付费面板点一次就花 30 紫宝石,
    # 所以本页的动作层必须永远不在 chest_info 帧上出手(中心 y 带 + 像素数上限两条尺子)。
    ci_frames = label_frames('chest_info')
    for nm, img in sorted(ci_frames.items()):
        ctx = Ctx(img)
        run(LevelUpPage(), img, ctx)
        check(not ctx.clicks,
              u'levelup.act 在 chest_info/%s 上出手了 %s -> 两页黄按钮互斥判据失效' % (nm, ctx.clicks))
    print(u'    %d 帧领取 + %d 帧面板反向互斥, 全程没读一个字' % (len(lu_frames), len(ci_frames)))

    print(u'[8] 英雄等级面板: 右上角红底关闭徽章 —— 必须和宝箱面板那颗同款徽章划清界限')
    hl_frames = label_frames('hero_level')
    check(len(hl_frames) >= 3, u'hero_level 语料帧太少(%d) -> 语料被清了?' % len(hl_frames))
    for nm, img in sorted(hl_frames.items()):
        ctx = Ctx(img)
        got = run(HeroLevelPage(), img, ctx)
        check(got and ctx.clicks == [(469, 172)],
              u'hero_level/%s 点击 %s != [(469, 172)]' % (nm, ctx.clicks))
    # 反向互斥: chest_info 的关闭徽章是**同色同形状**, 中心只比本页低 13px(159 vs 172);
    # vip_popup 月卡弹窗的徽章在 y454, vip_month 的在 y300 —— 全都出不了本页那条 y 带。
    n_guard = 0
    for lbl in ('chest_info', 'vip_popup', 'vip_month'):
        for nm, img in sorted(label_frames(lbl).items()):
            ctx = Ctx(img)
            run(HeroLevelPage(), img, ctx)
            check(not ctx.clicks,
                  u'hero_level.act 在 %s/%s 上出手了 %s -> 徽章 y 带互斥判据失效' % (lbl, nm, ctx.clicks))
            n_guard += 1
    print(u'    %d 帧关面板 + %d 帧反向互斥, 全程没读一个字' % (len(hl_frames), n_guard))

    print('')
    if FAILS:
        print('不通过 %d 项:' % len(FAILS))
        for m in FAILS:
            print('  - ' + m)
        return 1
    print(u'全部通过 (result/chest_open/lobby/chest_info/levelup/hero_level 动作层零 OCR)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
