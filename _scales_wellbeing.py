"""扩展题库（v1.1.0）· 状态与能力类：照搬公开量表原题，中文为本插件自译。

来源与许可
----------
- **PSS-10** 压力知觉量表（Cohen, Kamarck & Mermelstein, 1983）：学界公开发表，允许研究/教育用途免费使用；
  本插件不做商业分发。中文为自译，条目与计分键（第 4/5/7/8 题反向）按原量表。
- **DASS-21** 抑郁-焦虑-压力量表简版（Lovibond & Lovibond, 1995）：原作者声明可免费用于非商业研究/临床；
  三个分量表各 7 题，分级切点按原量表（未×2 的 21 题版本切点）。
- **PANAS** 积极消极情感量表（Watson, Clark & Tellegen, 1988）：研究用途免费；10 正 + 10 负。
- **SWLS** 生活满意度量表（Diener 等, 1985）：研究与非商业用途免费；5 题 7 点。
- **WHO-5** 幸福感指数（WHO, 1998）：免费使用（含非商业翻译）；5 题 0-5，×4 换算 0-100，≤50 为筛查线。
- **RSES** Rosenberg 自尊量表（1965）：研究用途免费；10 题 4 点，第 2/5/6/8/9 题反向。
- **GSES** 一般自我效能感量表（Schwarzer & Jerusalem, 1995）：作者声明免费用于研究/教育；10 题 4 点。
- **ISI** 失眠严重度指数（Morin, 1993）：研究与非商业临床用途免费；7 题 0-4，0-28 分四级。
- **BSMAS** Bergen 社交媒体成瘾量表（Andreassen 等, 2016）：研究用途免费；6 题 5 点。
- **BSCS-13** 简版自我控制量表（Tangney, Baumeister & Boone, 2004）：研究用途免费；13 题 5 点，9 题反向。
- **TIPI** 十项人格量表（Gosling, Rentfrow & Swann, 2003）：作者允许研究/非商业使用；10 题 7 点，5 题反向。
- **Mini-SPIN** 社交焦虑简筛（Connor 等, 2001）：研究用途免费；3 题 0-4，≥6 提示需进一步评估。
- **工作价值观**：六个维度取自 O*NET Work Values（美国劳工部，公共领域），条目按原维度**自编**并如实标注。

统一口径：这些量表都是**筛查/自评工具**，不是诊断；分数只作自我了解与追踪。
"""

from __future__ import annotations

FREQ_5 = [
    {"label": "从来没有", "value": 0},
    {"label": "很少", "value": 1},
    {"label": "有时", "value": 2},
    {"label": "经常", "value": 3},
    {"label": "总是", "value": 4},
]

DASS_4 = [
    {"label": "不符合", "value": 0},
    {"label": "有点符合", "value": 1},
    {"label": "很符合", "value": 2},
    {"label": "非常符合", "value": 3},
]

AGREE_5 = [
    {"label": "很不同意", "value": 1},
    {"label": "不太同意", "value": 2},
    {"label": "一般", "value": 3},
    {"label": "比较同意", "value": 4},
    {"label": "非常同意", "value": 5},
]

AGREE_4 = [
    {"label": "很不符合", "value": 1},
    {"label": "不太符合", "value": 2},
    {"label": "比较符合", "value": 3},
    {"label": "非常符合", "value": 4},
]

SWLS_7 = [
    {"label": "非常不同意", "value": 1},
    {"label": "不同意", "value": 2},
    {"label": "有点不同意", "value": 3},
    {"label": "中立", "value": 4},
    {"label": "有点同意", "value": 5},
    {"label": "同意", "value": 6},
    {"label": "非常同意", "value": 7},
]

WHO_6 = [
    {"label": "从未", "value": 0},
    {"label": "偶尔", "value": 1},
    {"label": "不到一半时间", "value": 2},
    {"label": "超过一半时间", "value": 3},
    {"label": "大部分时间", "value": 4},
    {"label": "一直", "value": 5},
]

ISI_5 = [
    {"label": "没有", "value": 0},
    {"label": "轻微", "value": 1},
    {"label": "中等", "value": 2},
    {"label": "严重", "value": 3},
    {"label": "非常严重", "value": 4},
]

TIPI_7 = [
    {"label": "完全不符合", "value": 1},
    {"label": "不太符合", "value": 2},
    {"label": "有点不符合", "value": 3},
    {"label": "说不好", "value": 4},
    {"label": "有点符合", "value": 5},
    {"label": "比较符合", "value": 6},
    {"label": "非常符合", "value": 7},
]

IMPORTANCE_5 = [
    {"label": "完全不重要", "value": 1},
    {"label": "不太重要", "value": 2},
    {"label": "一般", "value": 3},
    {"label": "比较重要", "value": 4},
    {"label": "极其重要", "value": 5},
]

SPIN_5 = [
    {"label": "完全不符合", "value": 0},
    {"label": "有一点符合", "value": 1},
    {"label": "比较符合", "value": 2},
    {"label": "很符合", "value": 3},
    {"label": "极其符合", "value": 4},
]

FFMQ_5 = [
    {"label": "几乎从不", "value": 1},
    {"label": "很少", "value": 2},
    {"label": "有时", "value": 3},
    {"label": "经常", "value": 4},
    {"label": "几乎总是", "value": 5},
]


def _likert(dim, rows):
    return [{"text": text, "dim": dim, "reverse": bool(rev)} for text, rev in rows]


def _adjectives(dim, words):
    """PANAS 原题是形容词表（"感兴趣的"），补句号让面板读起来一致。"""
    return [{"text": word + "。", "dim": dim, "reverse": False} for word in words]


# ════════════════════════════════════════════════════════════
# PSS-10 压力知觉（过去一个月）
#   维度按 NovoPsych 报告：无助感（1,2,3,6,9,10）／应对效能不足（4,5,7,8，反向）
# ════════════════════════════════════════════════════════════
PSS_ITEMS = [
    {"text": "过去一个月，你有多常因为突发的事情而感到心烦？", "dim": "hel", "reverse": False},
    {"text": "过去一个月，你有多常觉得自己无法掌控生活里重要的事？", "dim": "hel", "reverse": False},
    {"text": "过去一个月，你有多常感到紧张、有压力？", "dim": "hel", "reverse": False},
    {"text": "过去一个月，你有多常对自己处理个人问题的能力感到有信心？", "dim": "eff", "reverse": True},
    {"text": "过去一个月，你有多常觉得事情正按你的意思发展？", "dim": "eff", "reverse": True},
    {"text": "过去一个月，你有多常发现自己应付不完该做的事？", "dim": "hel", "reverse": False},
    {"text": "过去一个月，你有多常能控制住生活里的烦心事？", "dim": "eff", "reverse": True},
    {"text": "过去一个月，你有多常觉得自己掌控住了局面？", "dim": "eff", "reverse": True},
    {"text": "过去一个月，你有多常因为无法控制的事情而生气？", "dim": "hel", "reverse": False},
    {"text": "过去一个月，你有多常觉得困难堆得太高、自己跨不过去？", "dim": "hel", "reverse": False},
]

# ════════════════════════════════════════════════════════════
# DASS-21（过去一周）
# ════════════════════════════════════════════════════════════
DASS_ITEMS = []
DASS_ITEMS += _likert("dep", [
    ("我完全感受不到任何正面情绪。", False),                      # couldn't experience any positive feeling
    ("我觉得很难提起劲去做事情。", False),                         # difficult to work up initiative
    ("我觉得没有什么值得期待的事。", False),                       # nothing to look forward to
    ("我感到情绪低落、郁闷。", False),                            # down-hearted and blue
    ("我对任何事都提不起热情。", False),                           # unable to become enthusiastic
    ("我觉得自己这个人没什么价值。", False),                       # felt I wasn't worth much
    ("我觉得生活没有意义。", False),                              # life was meaningless
])
DASS_ITEMS += _likert("anx", [
    ("我感到口干。", False),                                     # dryness of mouth
    ("我感到呼吸困难（比如呼吸急促、没运动却喘不上气）。", False),   # breathing difficulty
    ("我出现手抖。", False),                                      # trembling
    ("我担心自己会在人前恐慌、出丑。", False),                      # worried about panic/fool of myself
    ("我觉得自己快要恐慌了。", False),                             # close to panic
    ("没运动我也能感觉到心跳（心跳加快、漏跳）。", False),            # aware of heart action
    ("我会没有理由地感到害怕。", False),                           # scared without good reason
])
DASS_ITEMS += _likert("str", [
    ("我很难让自己放松下来。", False),                            # hard to wind down
    ("我容易对事情反应过度。", False),                             # over-react
    ("我觉得自己消耗了很多神经能量。", False),                      # using a lot of nervous energy
    ("我变得很容易被激怒。", False),                               # rather touchy
    ("我发现很难放松。", False),                                   # difficult to relax
    ("我变得容易心烦意乱。", False),                               # getting easily upset
    ("我发现自己越来越烦躁、坐不住。", False),                      # getting agitated
])

# ════════════════════════════════════════════════════════════
# PANAS（过去一两周）
# ════════════════════════════════════════════════════════════
PANAS_ITEMS = []
PANAS_ITEMS += _adjectives("pa", [
    "感兴趣的", "兴奋的", "有干劲的", "热情的", "自豪的",
    "受启发的", "坚定的", "专注的", "活跃的", "精神饱满的",
])
PANAS_ITEMS += _adjectives("na", [
    "苦恼的", "心烦的", "内疚的", "害怕的", "有敌意的",
    "易怒的", "羞愧的", "紧张的", "坐立不安的", "提心吊胆的",
])

# ════════════════════════════════════════════════════════════
# SWLS 生活满意度
# ════════════════════════════════════════════════════════════
SWLS_ITEMS = _likert("swls", [
    ("总的来说，我的生活接近我理想的样子。", False),                # close to my ideal
    ("我的生活条件很好。", False),                                 # conditions excellent
    ("我对我的生活满意。", False),                                  # satisfied with my life
    ("到目前为止，我得到了生活里想要的重要东西。", False),           # gotten the important things
    ("如果能重来一次，我几乎不会改变什么。", False),                 # change almost nothing
])

# ════════════════════════════════════════════════════════════
# WHO-5 幸福感（过去两周）
# ════════════════════════════════════════════════════════════
WHO5_ITEMS = _likert("who5", [
    ("我感到心情愉快、精神振奋。", False),                          # cheerful and in good spirits
    ("我感到平静、放松。", False),                                  # calm and relaxed
    ("我感到有活力、有精力。", False),                              # active and vigorous
    ("我醒来时感到休息好了、神清气爽。", False),                     # fresh and rested
    ("我的日常生活里有很多让我感兴趣的事。", False),                 # daily life filled with interesting things
])

# ════════════════════════════════════════════════════════════
# RSES 自尊
# ════════════════════════════════════════════════════════════
RSES_ITEMS = _likert("rses", [
    ("总的来说，我对自己满意。", False),                            # satisfied with myself
    ("有时候我觉得自己一无是处。", True),                            # no good at all (R)
    ("我觉得自己有不少优点。", False),                              # a number of good qualities
    ("我能把事情做得和别人一样好。", False),                        # do things as well as most
    ("我觉得自己没什么值得骄傲的。", True),                          # not much to be proud of (R)
    ("我有时确实觉得自己很没用。", True),                            # useless at times (R)
    ("我觉得自己是个有价值的人，至少和别人一样。", False),            # person of worth
    ("我希望自己能更看得起自己一点。", True),                        # wish I could have more respect (R)
    ("总的来说，我倾向于觉得自己是个失败者。", True),                 # inclined to feel a failure (R)
    ("我对自己抱有积极的态度。", False),                            # positive attitude toward myself
])

# ════════════════════════════════════════════════════════════
# GSES 一般自我效能
# ════════════════════════════════════════════════════════════
GSES_ITEMS = _likert("gses", [
    ("只要足够努力，我总能解决难题。", False),                       # solve difficult problems
    ("如果别人反对我，我也能找到办法得到我想要的。", False),           # find means and ways
    ("坚持目标并把它们完成，对我来说不难。", False),                  # stick to aims
    ("遇到突发状况，我有信心处理得好。", False),                     # deal efficiently with unexpected events
    ("靠自己的应变，我知道怎么应付意外。", False),                    # resourcefulness
    ("只要投入必要的努力，大多数问题我都能解决。", False),             # solve most problems
    ("面对困难时我能保持冷静，因为我相信自己的应对能力。", False),      # remain calm
    ("遇到问题时，我通常能想出好几种解决办法。", False),               # several solutions
    ("如果陷入麻烦，我通常能想到出路。", False),                      # think of a solution
    ("无论遇到什么，我通常都能应付。", False),                        # handle whatever comes my way
])

# ════════════════════════════════════════════════════════════
# ISI 失眠严重度（最近两周）
# ════════════════════════════════════════════════════════════
ISI_ITEMS = [
    {"text": "入睡困难。", "dim": "isi", "reverse": False},
    {"text": "睡眠难以维持（半夜醒来、醒得太早）。", "dim": "isi", "reverse": False},
    {"text": "早醒后无法再睡。", "dim": "isi", "reverse": False},
    {"text": "你对目前的睡眠模式有多不满意？", "dim": "isi", "reverse": False},
    {"text": "别人能看出你的睡眠问题影响了日常状态吗？", "dim": "isi", "reverse": False},
    {"text": "你有多担心自己现在的睡眠问题？", "dim": "isi", "reverse": False},
    {"text": "睡眠问题对白天的工作/生活有多大干扰？", "dim": "isi", "reverse": False},
]

# ════════════════════════════════════════════════════════════
# BSMAS 社交媒体使用（最近一年）
# ════════════════════════════════════════════════════════════
BSMAS_ITEMS = _likert("bsmas", [
    ("你花很多时间想着社交媒体，或者计划着怎么用它。", False),        # a lot of time thinking about
    ("你越来越想用社交媒体。", False),                              # urge to use more and more
    ("你用社交媒体来忘记个人烦恼。", False),                        # in order to forget problems
    ("你试过少用社交媒体，但没成功。", False),                       # tried to cut down without success
    ("不能刷社交媒体时，你会烦躁或不安。", False),                    # restless if prohibited
    ("你用社交媒体多到影响了工作或学习。", False),                    # negative impact on job/studies
])

# ════════════════════════════════════════════════════════════
# BSCS-13 自我控制
# ════════════════════════════════════════════════════════════
BSCS_ITEMS = _likert("bscs", [
    ("我擅长抵挡诱惑。", False),                                   # good at resisting temptation
    ("我很难改掉坏习惯。", True),                                  # hard time breaking bad habits (R)
    ("我有点懒。", True),                                          # am lazy (R)
    ("我会说不合适的话。", True),                                   # say inappropriate things (R)
    ("只要好玩，我会做对自己不好的事。", True),                       # do bad things if fun (R)
    ("我会拒绝那些对我有害的东西。", False),                         # refuse things bad for me
    ("我希望自己更有自制力。", True),                                # wish more self-discipline (R)
    ("别人会说我很自律。", False),                                   # iron self-discipline
    ("玩乐常常让我做不完该做的事。", True),                           # pleasure keeps me from work (R)
    ("我很难集中注意力。", True),                                    # trouble concentrating (R)
    ("我能有效地为长期目标努力。", False),                            # work toward long-term goals
    ("有时明知不对，我还是停不下来。", True),                         # can't stop myself (R)
    ("我常常没想清其他选择就行动。", True),                           # act without thinking alternatives (R)
])

# ════════════════════════════════════════════════════════════
# TIPI 十项人格（Gosling）
# ════════════════════════════════════════════════════════════
TIPI_ITEMS = [
    {"text": "我认为自己是一个外向、热情的人。", "dim": "E", "reverse": False},
    {"text": "我认为自己是一个爱挑剔、爱争吵的人。", "dim": "A", "reverse": True},
    {"text": "我认为自己是一个可靠、自律的人。", "dim": "C", "reverse": False},
    {"text": "我认为自己是一个容易焦虑、容易心烦的人。", "dim": "N", "reverse": False},
    {"text": "我认为自己是一个乐于接受新经验、喜欢复杂事物的人。", "dim": "O", "reverse": False},
    {"text": "我认为自己是一个内敛、安静的人。", "dim": "E", "reverse": True},
    {"text": "我认为自己是一个有同情心、温和的人。", "dim": "A", "reverse": False},
    {"text": "我认为自己是一个散漫、粗心的人。", "dim": "C", "reverse": True},
    {"text": "我认为自己是一个平静、情绪稳定的人。", "dim": "N", "reverse": True},
    {"text": "我认为自己是一个保守、不太有创意的人。", "dim": "O", "reverse": True},
]

# ════════════════════════════════════════════════════════════
# 工作价值观（六维，条目按 O*NET 维度自编）
# ════════════════════════════════════════════════════════════
WORKVALUE_ITEMS = []
WORKVALUE_ITEMS += _likert("ach", [
    ("工作里能用到我最擅长的能力。", False),
    ("能看到自己做出实实在在的成果。", False),
    ("有机会把一件事从头做到尾。", False),
    ("做的事让我觉得自己有长进。", False),
])
WORKVALUE_ITEMS += _likert("ind", [
    ("能自己安排做事的节奏。", False),
    ("不用每一步都请示别人。", False),
    ("能按自己的方式把事做完。", False),
    ("有空间做自己的判断。", False),
])
WORKVALUE_ITEMS += _likert("rec", [
    ("做得好会被人看见。", False),
    ("努力能换来明确的认可。", False),
    ("别人知道我在这件事上的分量。", False),
    ("晋升和评价靠得住。", False),
])
WORKVALUE_ITEMS += _likert("rel", [
    ("同事之间能处成朋友。", False),
    ("工作里有人愿意听我说。", False),
    ("不用一直防着身边的人。", False),
    ("团队里有真实的互相照应。", False),
])
WORKVALUE_ITEMS += _likert("sup", [
    ("遇到问题时有上级能撑住我。", False),
    ("公司愿意为我的成长投入。", False),
    ("有清楚的规则和流程可依。", False),
    ("被公平对待。", False),
])
WORKVALUE_ITEMS += _likert("con", [
    ("工作环境安全、干净、舒服。", False),
    ("工作时间相对稳定。", False),
    ("收入和保障让我安心。", False),
    ("不用长期透支身体。", False),
])

# ════════════════════════════════════════════════════════════
# Mini-SPIN 社交焦虑简筛（过去一周）
# ════════════════════════════════════════════════════════════
SPIN_ITEMS = _likert("spin", [
    ("因为怕出丑，我会避免做某些事或跟人说话。", False),
    ("我会避开那些我会成为焦点的场合。", False),
    ("因为怕脸红、出汗、发抖被发现，我会避免做事或说话。", False),
])

DASS_BANDS = {
    "dep": [(0, 4, "正常", "这个范围内不必额外担心。"),
            (5, 6, "轻度", "留意睡眠与活动量，别让低谷拖长。"),
            (7, 10, "中度", "建议找专业的人聊聊，越早越省力。"),
            (11, 13, "偏重", "请尽快联系心理咨询师或医生。"),
            (14, 21, "重度", "请尽快寻求专业帮助，你不必一个人扛。")],
    "anx": [(0, 3, "正常", "这个范围内不必额外担心。"),
            (4, 5, "轻度", "试着减少咖啡因，给紧张安排出口。"),
            (6, 7, "中度", "值得找专业的人聊聊。"),
            (8, 9, "偏重", "请尽快寻求专业帮助。"),
            (10, 21, "重度", "请尽快寻求专业帮助，必要时就医。")],
    "str": [(0, 7, "正常", "这个范围内不必额外担心。"),
            (8, 9, "轻度", "给「放松」排进日程，而不是等有空。"),
            (10, 12, "中度", "睡眠和运动先修，再谈效率。"),
            (13, 16, "偏重", "请尽快寻求专业帮助。"),
            (17, 21, "重度", "请尽快寻求专业帮助。")],
}

# ════════════════════════════════════════════════════════════
# 正念五因素（FFMQ-15）与情绪调节（ERQ）
# ════════════════════════════════════════════════════════════
FFMQ_ITEMS = [
    # 1
    {"text": "我洗澡时，会留意水落在身上的感觉。", "dim": "obs", "reverse": False},
    # 2
    {"text": "我擅长用词句说清自己的感受。", "dim": "des", "reverse": False},
    # 3
    {"text": "我常因为走神、担心别的事，没注意自己正在做什么。", "dim": "act", "reverse": True},
    # 4
    {"text": "我觉得自己有些念头不正常、不该有。", "dim": "nonj", "reverse": True},
    # 5
    {"text": "出现难受的念头或画面时，我会「退后一步」，只是觉察它而不被卷走。", "dim": "nonr", "reverse": False},
    # 6
    {"text": "我能注意到食物和饮料怎样影响我的念头、身体感觉和情绪。", "dim": "obs", "reverse": False},
    # 7
    {"text": "我很难找到合适的词来表达自己对事情的感受。", "dim": "des", "reverse": True},
    # 8
    {"text": "我做事情常常是自动完成的，没意识到自己在做什么。", "dim": "act", "reverse": True},
    # 9
    {"text": "我觉得自己有些情绪是不好的、不该有的。", "dim": "nonj", "reverse": True},
    # 10
    {"text": "出现难受的念头或画面时，我能只是注意到它而不跟着反应。", "dim": "nonr", "reverse": False},
    # 11
    {"text": "我会留意风拂过头发、阳光落在脸上这类身体感觉。", "dim": "obs", "reverse": False},
    # 12
    {"text": "即使难受得厉害，我也能找到办法把它说出来。", "dim": "des", "reverse": False},
    # 13
    {"text": "我发现自己做事时心不在焉。", "dim": "act", "reverse": True},
    # 14
    {"text": "我会告诉自己「我不该有这种感受」。", "dim": "nonj", "reverse": True},
    # 15
    {"text": "出现难受的念头或画面时，我只是注意到它，然后让它过去。", "dim": "nonr", "reverse": False},
]

ERQ_ITEMS = [
    {"text": "想让自己更开心（比如更愉快、更有趣）时，我会改变自己在想的东西。", "dim": "rea", "reverse": False},
    {"text": "我把情绪留在心里，不表现出来。", "dim": "sup", "reverse": False},
    {"text": "想让自己少难过、少生气时，我会改变自己在想的东西。", "dim": "rea", "reverse": False},
    {"text": "有正面情绪时，我会小心不表现出来。", "dim": "sup", "reverse": False},
    {"text": "面对压力情境时，我会让自己换一种想法，好保持镇定。", "dim": "rea", "reverse": False},
    {"text": "我靠「不表达」来控制情绪。", "dim": "sup", "reverse": False},
    {"text": "想让自己更开心时，我会改变自己对所处情境的想法。", "dim": "rea", "reverse": False},
    {"text": "我通过改变对处境的想法来控制情绪。", "dim": "rea", "reverse": False},
    {"text": "有负面情绪时，我一定不表现出来。", "dim": "sup", "reverse": False},
    {"text": "想让自己少难过时，我会改变自己对处境的想法。", "dim": "rea", "reverse": False},
]

AGREE_7 = [
    {"label": "完全不同意", "value": 1},
    {"label": "不同意", "value": 2},
    {"label": "有点不同意", "value": 3},
    {"label": "中立", "value": 4},
    {"label": "有点同意", "value": 5},
    {"label": "同意", "value": 6},
    {"label": "完全同意", "value": 7},
]

SCALES_WELLBEING = [
    {
        "id": "pss10",
        "name": "压力知觉（PSS-10）",
        "category": "情绪健康",
        "minutes": 2,
        "kind": "clinical",
        "direction": "negative",
        "source": "PSS-10（Cohen, Kamarck & Mermelstein, 1983；PSS 版权 © 1994 Sheldon Cohen，经 ASA 授权重印）｜中文自译",
        "license": "PSS 受版权保护（© 1994 Sheldon Cohen）；研究/教育可按学界惯例使用并保留署名，公开分发需向 Mind Garden 取得授权",
        "tags": ["压力", "10 题", "过去一个月", "两维度"],
        "intro": "不是问你「有多忙」，而是问「你觉得失控了多少」。两条线分开看：无助感 / 应对效能不足。",
        "options": FREQ_5,
        "dimensions": [
            {"key": "hel", "name": "无助感", "low": "较少无力感", "high": "无力感偏多",
             "tip": "1、2、3、6、9、10 题：事情压过来时的失控感。"},
            {"key": "eff", "name": "应对效能不足", "low": "觉得还能应付", "high": "觉得应付不来",
             "tip": "4、5、7、8 题反向计分：你对自己处理能力的评价。"},
        ],
        "items": PSS_ITEMS,
        "bands": [
            (0, 13, "低压力", "当前知觉到的压力偏低，通常处在能掌控的范围内。（常用分档，非原量表官方切点）"),
            (14, 26, "中等压力", "压力已经影响到日常节奏，值得先修睡眠和「必须做完」的清单。"
                                 "（常用分档，非 Cohen 原文切点；原文献只给常模均值/标准差）"),
            (27, 40, "高压力", "压力偏高，建议尽快减负并找专业的人聊聊。（常用分档，非原量表官方切点）"),
        ],
    },
    {
        "id": "dass21",
        "name": "情绪状态（DASS-21）",
        "category": "情绪健康",
        "minutes": 3,
        "kind": "dimension",
        "direction": "negative",
        "source": "DASS-21（Lovibond 等, 1995）｜非商业研究/临床免费；中文自译",
        "license": "非商业研究/临床用途免费（原作者声明）",
        "tags": ["抑郁", "焦虑", "压力", "21 题"],
        "intro": "一次把三条线分开量：低落、紧张、烦躁。三条线互不等价，分开看才有用。",
        "options": DASS_4,
        "dimensions": [
            {"key": "dep", "name": "低落", "low": "情绪平稳", "high": "低落明显",
             "tip": "兴趣、动力、自我价值感这条线。"},
            {"key": "anx", "name": "紧张", "low": "不紧张", "high": "紧张明显",
             "tip": "身体的警报：心跳、呼吸、手抖、莫名的怕。"},
            {"key": "str", "name": "烦躁", "low": "松得下来", "high": "绷得很紧",
             "tip": "易怒、坐不住、消耗感这条线。"},
        ],
        "dim_bands": DASS_BANDS,
        "dim_bands_on": "score",
        "items": DASS_ITEMS,
    },
    {
        "id": "panas",
        "name": "积极与消极情感（PANAS）",
        "category": "情绪健康",
        "minutes": 2,
        "kind": "dimension",
        "source": "PANAS（Watson 等, 1988）｜研究用途免费；中文自译",
        "license": "研究用途免费（原作者声明）",
        "tags": ["情绪", "20 题", "两条线"],
        "intro": "正面情绪和负面情绪不是一根轴的两端——它们可以同时很高，也可以同时很低。",
        "options": AGREE_5,
        "dimensions": [
            {"key": "pa", "name": "积极情感", "low": "兴致偏低", "high": "兴致很高",
             "tip": "有劲、投入、想做事的那一侧。"},
            {"key": "na", "name": "消极情感", "low": "不太难受", "high": "难受偏多",
             "tip": "紧张、烦躁、内疚的那一侧。"},
        ],
        "items": PANAS_ITEMS,
    },
    {
        "id": "swls",
        "name": "生活满意度（SWLS）",
        "category": "情绪健康",
        "minutes": 1,
        "kind": "clinical",
        "source": "SWLS（Diener 等, 1985）｜作者允许免费使用，需署名；中文自译",
        "license": "可免费使用、无需申请，但必须保留署名（Diener 等, 1985）",
        "tags": ["满意度", "5 题", "7 点"],
        "intro": "不是问「你现在开心吗」，是问「回头看你的人生，你打几分」。",
        "options": SWLS_7,
        "dimensions": [{"key": "swls", "name": "生活满意度", "low": "不太满意", "high": "相当满意",
                        "tip": "这是一条相对稳定的判断，不会因为今天心情好就大幅跳动。"}],
        "items": SWLS_ITEMS,
        "bands": [
            (5, 9, "很不满意", "对目前的生活整体评价偏低。"),
            (10, 14, "不满意", "有明显不满意的部分，值得看看是哪一块。"),
            (15, 19, "略偏不满意", "接近中间，但偏冷。"),
            (20, 20, "中立", "刚好在中间。"),
            (21, 25, "略偏满意", "整体偏正面。"),
            (26, 30, "满意", "对生活整体评价不错。"),
            (31, 35, "非常满意", "整体评价很高。"),
        ],
    },
    {
        "id": "who5",
        "name": "总体幸福感（WHO-5）",
        "category": "情绪健康",
        "minutes": 1,
        "kind": "clinical",
        "source": "WHO-5（World Health Organization, 1998）｜免费使用；中文自译",
        "license": "WHO 允许非商业使用与翻译（需署名 WHO）",
        "tags": ["幸福感", "5 题", "两周"],
        "intro": "五个问题，问的是「这段时间你有没有活得有劲」。原始分 0-25，×4 换算成 0-100 分。",
        "options": WHO_6,
        "dimensions": [{"key": "who5", "name": "幸福感", "low": "能量偏低", "high": "状态不错",
                        "tip": "原始分 ≤12（指数 ≤48）通常被视为幸福感不良的筛查线；≤7 更严格。"}],
        "items": WHO5_ITEMS,
        "bands": [
            (0, 12, "低于筛查线", "这段时间的幸福感偏低（原始分 ≤12 ≈ 指数 ≤48）。"
                                  "值得认真照顾自己；必要时找专业的人聊聊。(WHO 常用切点)"),
            (13, 25, "在筛查线以上", "整体状态还可以，继续保持睡眠、运动和见人。"),
        ],
    },
    {
        "id": "rses",
        "name": "自尊（RSES）",
        "category": "人格",
        "minutes": 2,
        "kind": "clinical",
        "source": "Rosenberg 自尊量表（1965）｜学界通行研究使用；中文自译",
        "license": "原量表由 Rosenberg 发表，学界按引用作者方式使用（未见明确授权语句）",
        "tags": ["自尊", "10 题", "4 点"],
        "intro": "不是「我有多优秀」，是「我对自己这个人的基本评价」。",
        "options": AGREE_4,
        "dimensions": [{"key": "rses", "name": "自尊", "low": "自我评价偏低", "high": "自我接纳较好",
                        "tip": "第 2/5/6/8/9 题反向计分；分档是本插件为便于阅读设的，原量表没有官方切点。"}],
        "items": RSES_ITEMS,
        "bands": [
            (10, 19, "偏低", "对自己的评价偏苛刻。这更像一种状态，不是定论。（插件自设分档，非官方切点）"),
            (20, 30, "中等", "大多数人在这个区间：有起伏，但能站住。（插件自设分档）"),
            (31, 40, "偏高", "自我接纳较好。留意别把「感觉良好」当成不需要反省。（插件自设分档）"),
        ],
    },
    {
        "id": "gses",
        "name": "一般自我效能（GSES）",
        "category": "人格",
        "minutes": 2,
        "kind": "dimension",
        "source": "GSES（Schwarzer & Jerusalem, 1995）｜研究/教育用途免费；中文自译",
        "license": "研究/教育用途免费（作者声明）",
        "tags": ["自我效能", "10 题", "4 点"],
        "intro": "遇到新问题时，你有多相信「我能应付」——这是能被经验改变的。",
        "options": AGREE_4,
        "dimensions": [{"key": "gses", "name": "自我效能", "low": "信心偏低", "high": "信心充足",
                        "tip": "它靠「做成过小事」累积，不靠自我暗示。"}],
        "items": GSES_ITEMS,
        "dim_bands": {
            "gses": [(0, 40, "偏低", "先积累小胜：把任务切到「今天一定能做完」的粒度。"),
                     (41, 70, "中等", "大部分人的位置。"),
                     (71, 100, "偏高", "遇到新问题时会先动手试，而不是先怕。")],
        },
    },
    {
        "id": "isi",
        "name": "失眠严重度（ISI）",
        "category": "情绪健康",
        "minutes": 2,
        "kind": "clinical",
        "direction": "negative",
        "source": "ISI（Morin, 1993/1996；版权归作者，经 Mapi Research Trust 分发）｜中文自译",
        "license": "ISI 受版权保护（© Morin 1993/1996，Mapi Research Trust）；本插件仅供个人非商业自评，"
                   "公开分发或商用需向版权方取得授权",
        "tags": ["睡眠", "7 题", "两周", "受版权保护"],
        "intro": "失眠不只是「睡得少」，还包括「睡得不满意、白天被拖累」。",
        "options": ISI_5,
        "dimensions": [{"key": "isi", "name": "失眠严重度", "low": "睡眠尚可", "high": "影响明显",
                        "tip": "0-28 分四级：0-7 无临床意义，8-14 亚临床，15-21 中度，22-28 重度。"}],
        "items": ISI_ITEMS,
        "bands": [
            (0, 7, "无明显失眠", "睡眠基本不影响白天。"),
            (8, 14, "亚临床", "已经有影响，先修作息与睡前屏幕。"),
            (15, 21, "中度", "建议找专业的人评估（失眠的认知行为治疗比安眠药更持久）。"),
            (22, 28, "重度", "请尽快就医，别硬扛。"),
        ],
    },
    {
        "id": "bsmas",
        "name": "社交媒体使用（BSMAS）",
        "category": "情绪健康",
        "minutes": 2,
        "kind": "clinical",
        "direction": "negative",
        "source": "Bergen 社交媒体成瘾量表（Andreassen 等, 2016）｜研究用途免费；中文自译",
        "license": "研究用途免费",
        "tags": ["刷手机", "6 题", "行为"],
        "intro": "六个问题看「刷」有没有变成「停不下来」。",
        "options": AGREE_5,
        "dimensions": [{"key": "bsmas", "name": "社交媒体依赖", "low": "用得有分寸", "high": "有点停不下来",
                        "tip": "19 分及以上常被当作「有风险」的参考线。"}],
        "items": BSMAS_ITEMS,
        "bands": [
            (6, 11, "低", "使用基本在掌控里。"),
            (12, 18, "中等", "有些时段会被带着走，试试把首屏 App 挪走。"),
            (19, 30, "偏高", "已经出现「想停停不下来」的模式，值得给自己设硬规则。"),
        ],
    },
    {
        "id": "bscs",
        "name": "自我控制（BSCS-13）",
        "category": "人格",
        "minutes": 2,
        "kind": "dimension",
        "source": "简版自我控制量表（Tangney 等, 2004）｜研究用途免费；中文自译",
        "license": "研究用途免费",
        "tags": ["自控", "13 题"],
        "intro": "自控不是道德问题，是「现在爽」和「以后好」的取舍能力。",
        "options": AGREE_5,
        "dimensions": [{"key": "bscs", "name": "自我控制", "low": "靠环境约束", "high": "能管住当下",
                        "tip": "9 道反向题；分数高不代表更痛苦，通常代表更少后悔。"}],
        "items": BSCS_ITEMS,
        "dim_bands": {
            "bscs": [(0, 40, "偏低", "别靠意志力硬扛，改环境更有效：把诱惑移出视线。"),
                     (41, 70, "中等", "大部分人的位置。"),
                     (71, 100, "偏高", "你能为了长期目标放弃眼前舒服。")],
        },
    },
    {
        "id": "tipi",
        "name": "十项人格（TIPI）",
        "category": "人格",
        "minutes": 1,
        "kind": "dimension",
        "source": "Ten-Item Personality Inventory（Gosling 等, 2003）｜非商业研究可用；中文自译",
        "license": "研究/非商业用途可用（作者声明）",
        "tags": ["超短版", "10 题", "大五"],
        "intro": "两分钟版大五：只给轮廓，不给细节。想看清分面请用 120 题那版。",
        "options": TIPI_7,
        "dimensions": [
            {"key": "E", "name": "外向性", "low": "内敛", "high": "外放", "tip": "每题 1 正 1 反，信度低于长版。"},
            {"key": "A", "name": "宜人性", "low": "较自我", "high": "很体贴", "tip": "对合作与信任的倾向。"},
            {"key": "C", "name": "尽责性", "low": "随性", "high": "有条理", "tip": "自律与收尾。"},
            {"key": "N", "name": "情绪敏感性", "low": "平稳", "high": "易起伏", "tip": "警报系统灵不灵。"},
            {"key": "O", "name": "开放性", "low": "务实", "high": "爱探索", "tip": "对新经验的胃口。"},
        ],
        "items": TIPI_ITEMS,
    },
    {
        "id": "workvalues",
        "name": "工作价值观（O*NET 六维）",
        "category": "职业",
        "minutes": 3,
        "kind": "dimension_type",
        "source": "维度概念取自 O*NET Work Values（美国劳工部）｜O*NET 测评工具受版权保护，条目为本插件自编",
        "license": "仅六个价值观的构念与定义开放；O*NET 工具本身 © U.S. DOL/ETA，条目与计分为本插件原创",
        "tags": ["工作价值观", "24 题", "选方向"],
        "intro": "选工作时不只看「能不能做」，还要看「值不值得」。六个维度告诉你最在意哪一块。",
        "options": IMPORTANCE_5,
        "dimensions": [
            {"key": "ach", "name": "成就", "tip": "用上能力、看到成果"},
            {"key": "ind", "name": "自主", "tip": "自己安排、自己判断"},
            {"key": "rec", "name": "认可", "tip": "被看见、被承认"},
            {"key": "rel", "name": "关系", "tip": "同事能处成朋友"},
            {"key": "sup", "name": "支持", "tip": "有人撑、有规则可依"},
            {"key": "con", "name": "条件", "tip": "环境、时间与保障"},
        ],
        "items": WORKVALUE_ITEMS,
    },
    {
        "id": "minispin",
        "name": "社交焦虑简筛（Mini-SPIN）",
        "category": "情绪健康",
        "minutes": 1,
        "kind": "clinical",
        "direction": "negative",
        "source": "Mini-SPIN（Connor 等, 2001）｜研究用途免费；中文自译",
        "license": "研究用途免费",
        "tags": ["社交焦虑", "3 题", "筛查"],
        "intro": "三个问题，只做初筛：≥6 分提示值得进一步评估，不等于诊断。",
        "options": SPIN_5,
        "dimensions": [{"key": "spin", "name": "社交焦虑", "low": "不太回避", "high": "回避偏多",
                        "tip": "短筛的用途是「要不要再查」，不是贴标签。"}],
        "items": SPIN_ITEMS,
        "bands": [
            (0, 5, "未达筛查线", "目前不太像有显著的社交焦虑。"),
            (6, 12, "达到筛查线", "建议找专业的人做一次完整评估；这只是初筛，不是诊断。"),
        ],
    },
    {
        "id": "ffmq15",
        "name": "正念五因素（FFMQ-15）",
        "category": "情绪健康",
        "minutes": 2,
        "kind": "dimension",
        "source": "FFMQ-15（Baer 等, 2012；NovoPsych 公开问卷）｜中文自译",
        "license": "学界公开量表，按引用作者方式使用（未见到明确授权语句）",
        "tags": ["正念", "15 题", "5 个因素"],
        "intro": "正念不是「放空」，是五个可拆开的能力：观察、描述、带着觉察行动、不评判、不跟着反应。",
        "options": FFMQ_5,
        "dimensions": [
            {"key": "obs", "name": "观察", "low": "不太留意身体感觉", "high": "对感受很敏感",
             "tip": "1、6、11 题：能不能注意到身体与环境传来的信号。"},
            {"key": "des", "name": "描述", "low": "说不清感受", "high": "能说清感受",
             "tip": "2、7、12 题：把内在体验讲出来的能力。"},
            {"key": "act", "name": "带着觉察行动", "low": "常自动挡", "high": "做事时在场",
             "tip": "3、8、13 题反向：做事时有没有「人在」。"},
            {"key": "nonj", "name": "不评判", "low": "容易苛责自己", "high": "容许念头存在",
             "tip": "4、9、14 题反向：对念头和情绪加不加「不该」。"},
            {"key": "nonr", "name": "不反应", "low": "容易被卷走", "high": "能只是看着它",
             "tip": "5、10、15 题：难受念头来时，能不能不被拖着走。"},
        ],
        "items": FFMQ_ITEMS,
        "method": "5 点计分（几乎从不 ~ 几乎总是）。第 3/4/7/8/9/13/14 题反向。"
                  "每个因素 3 题，按 3 题满分换算百分比。原量表没有官方切点，只有常模均值"
                  "（大学生总均分约 3.18/5）；比较干预前后时，学界建议剔除「观察」分量表。",
    },
    {
        "id": "erq",
        "name": "情绪调节（ERQ）",
        "category": "情绪健康",
        "minutes": 2,
        "kind": "dimension",
        "source": "ERQ（Gross & John, 2003）｜学界公开量表；中文自译",
        "license": "学界公开量表，按引用作者方式使用（未见到明确授权语句）",
        "tags": ["情绪调节", "10 题", "两种策略"],
        "intro": "你怎么处理情绪：改想法（重评），还是压住不表现（抑制）。两者没有绝对好坏，代价不同。",
        "options": AGREE_7,
        "dimensions": [
            {"key": "rea", "name": "认知重评", "low": "很少换角度", "high": "常用换角度",
             "tip": "1、3、5、7、8、10 题：改变想法来改变情绪。通常和更好的关系与情绪结果相关。"},
            {"key": "sup", "name": "表达抑制", "low": "不太压着", "high": "习惯压着",
             "tip": "2、4、6、9 题：把情绪藏起来。短期有效，长期常伴随更高的负担。"},
        ],
        "items": ERQ_ITEMS,
        "method": "7 点同意度，无反向题，也没有总分——两个维度各自看。"
                  "按各自题数满分换算百分比：重评 6 题、抑制 4 题。",
    },
]

SCALE_ART_WELLBEING = {
    "pss10": {"emoji": "🫧", "from": "#9fb6f7", "to": "#c9a8f0"},
    "dass21": {"emoji": "🌡", "from": "#8fa8f7", "to": "#f0a8c8"},
    "panas": {"emoji": "🎭", "from": "#f7c46f", "to": "#8fb8f7"},
    "swls": {"emoji": "🌤", "from": "#7fd0e8", "to": "#b8f0c8"},
    "who5": {"emoji": "🌱", "from": "#7fd0a5", "to": "#a8e0f7"},
    "rses": {"emoji": "🪞", "from": "#c0a8f7", "to": "#f7b8d0"},
    "gses": {"emoji": "🧗", "from": "#8fd0b8", "to": "#9fb6f7"},
    "isi": {"emoji": "🌙", "from": "#9aa8e8", "to": "#c8b8f0"},
    "bsmas": {"emoji": "📱", "from": "#f0a8b8", "to": "#b8a8f7"},
    "bscs": {"emoji": "🧭", "from": "#7fb2f7", "to": "#8ee0c8"},
    "tipi": {"emoji": "🎯", "from": "#8d7ff3", "to": "#5ec8f0"},
    "workvalues": {"emoji": "🗂", "from": "#8f9ff7", "to": "#c0b0f7"},
    "minispin": {"emoji": "🫥", "from": "#a8b8f0", "to": "#d0b8f0"},
    "ffmq15": {"emoji": "🍃", "from": "#8fd0b8", "to": "#bfe8d8"},
    "erq": {"emoji": "🎚", "from": "#b0b8f7", "to": "#f0c0a8"},
}
