"""
matcher.py —— 简历与岗位 JD 的匹配分析核心模块

【设计说明】
本模块是纯规则实现，不依赖任何网络请求或大模型。
它的职责是：从简历文本和岗位 JD 中提取技能关键词，
计算加权匹配度，并给出"命中了什么 / 缺了什么"。

之所以把这块做成纯规则：
1. 结果稳定、可复现，同样的输入永远得到同样的分数；
2. 不依赖外部服务，断网也能跑，演示不会翻车；
3. 面试时可以讲清楚"每一分是怎么算出来的"——
   这是大模型给不了的确定性，也是这个项目的设计取舍。
"""

import re

# ---------------------------------------------------------------------------
# 1. 技能词典
#    每一条包含：标准名称 name、所属类别 category、以及各种写法 aliases。
#    匹配时会统一转小写后做子串查找，所以 aliases 要覆盖常见写法。
# ---------------------------------------------------------------------------
SKILLS = [
    # ---- 编程语言 ----
    {"name": "Java",           "category": "编程语言", "aliases": ["java"]},
    {"name": "Python",         "category": "编程语言", "aliases": ["python"]},
    {"name": "C/C++",          "category": "编程语言", "aliases": ["c++", "c语言", "cpp"]},
    {"name": "C#",             "category": "编程语言", "aliases": ["c#"]},
    {"name": "JavaScript",     "category": "编程语言", "aliases": ["javascript", "js"]},
    {"name": "TypeScript",     "category": "编程语言", "aliases": ["typescript", "ts"]},
    {"name": "PHP",            "category": "编程语言", "aliases": ["php"]},
    {"name": "Go",             "category": "编程语言", "aliases": ["golang", "go语言"]},
    {"name": "SQL",            "category": "编程语言", "aliases": ["sql"]},
    {"name": "Shell",          "category": "编程语言", "aliases": ["shell", "bash"]},

    # ---- Web 前端 ----
    {"name": "HTML5",          "category": "Web前端",  "aliases": ["html5", "html"]},
    {"name": "CSS3",           "category": "Web前端",  "aliases": ["css3", "css"]},
    {"name": "Vue",            "category": "Web前端",  "aliases": ["vue"]},
    {"name": "React",          "category": "Web前端",  "aliases": ["react"]},
    {"name": "jQuery",         "category": "Web前端",  "aliases": ["jquery"]},
    {"name": "Bootstrap",      "category": "Web前端",  "aliases": ["bootstrap"]},
    {"name": "ECharts",        "category": "Web前端",  "aliases": ["echarts"]},
    {"name": "小程序",         "category": "Web前端",  "aliases": ["小程序", "miniprogram"]},

    # ---- 后端 / 框架 ----
    {"name": "Spring/SpringBoot", "category": "后端框架", "aliases": ["spring", "springboot", "spring boot", "ssm"]},
    {"name": "MyBatis",        "category": "后端框架", "aliases": ["mybatis"]},
    {"name": "Django",         "category": "后端框架", "aliases": ["django"]},
    {"name": "Flask",          "category": "后端框架", "aliases": ["flask"]},
    {"name": "FastAPI",        "category": "后端框架", "aliases": ["fastapi"]},
    {"name": "RESTful API",    "category": "后端框架", "aliases": ["restful", "rest api", "接口开发"]},
    {"name": "微服务",         "category": "后端框架", "aliases": ["微服务", "microservice"]},
    {"name": "Redis",          "category": "后端框架", "aliases": ["redis"]},
    {"name": "消息队列",       "category": "后端框架", "aliases": ["kafka", "rabbitmq", "rocketmq", "消息队列"]},
    {"name": "Docker",         "category": "后端框架", "aliases": ["docker", "容器"]},

    # ---- 数据库 ----
    {"name": "MySQL",          "category": "数据库",  "aliases": ["mysql"]},
    {"name": "PostgreSQL",     "category": "数据库",  "aliases": ["postgresql", "postgres", "pgsql"]},
    {"name": "Oracle",         "category": "数据库",  "aliases": ["oracle"]},
    {"name": "SQLite",         "category": "数据库",  "aliases": ["sqlite"]},
    {"name": "MongoDB",        "category": "数据库",  "aliases": ["mongodb", "mongo"]},
    {"name": "数据库设计",     "category": "数据库",  "aliases": ["数据库设计", "建表", "范式", "索引优化", "sql优化"]},

    # ---- AI / 数据 ----
    {"name": "机器学习",       "category": "AI与数据", "aliases": ["机器学习", "machine learning", "sklearn", "scikit-learn"]},
    {"name": "深度学习",       "category": "AI与数据", "aliases": ["深度学习", "deep learning", "神经网络", "cnn", "rnn"]},
    {"name": "PyTorch",        "category": "AI与数据", "aliases": ["pytorch", "torch"]},
    {"name": "TensorFlow",     "category": "AI与数据", "aliases": ["tensorflow", "keras"]},
    {"name": "大模型/LLM",     "category": "AI与数据", "aliases": ["大模型", "llm", "大语言模型", "gpt", "语言模型"]},
    {"name": "Prompt工程",     "category": "AI与数据", "aliases": ["prompt", "提示词", "提示工程"]},
    {"name": "RAG/知识库",     "category": "AI与数据", "aliases": ["rag", "检索增强", "向量数据库", "embedding", "faiss", "milvus", "知识库"]},
    {"name": "Agent/智能体",   "category": "AI与数据", "aliases": ["agent", "智能体", "langchain"]},
    {"name": "模型微调",       "category": "AI与数据", "aliases": ["微调", "finetune", "fine-tune", "lora", "sft"]},
    {"name": "计算机视觉",     "category": "AI与数据", "aliases": ["计算机视觉", "opencv", "图像识别", "目标检测", "yolo"]},
    {"name": "NLP",            "category": "AI与数据", "aliases": ["nlp", "自然语言处理", "文本分类", "分词"]},
    {"name": "数据分析",       "category": "AI与数据", "aliases": ["数据分析", "pandas", "numpy", "数据清洗", "数据可视化"]},
    {"name": "数据标注",       "category": "AI与数据", "aliases": ["数据标注", "标注", "标注规范"]},
    {"name": "爬虫",           "category": "AI与数据", "aliases": ["爬虫", "scrapy", "数据采集"]},

    # ---- 开发工具 / 工程能力 ----
    {"name": "Git",            "category": "开发工具", "aliases": ["git", "github", "gitlab", "gitee", "版本控制"]},
    {"name": "Linux",          "category": "开发工具", "aliases": ["linux", "shell脚本"]},
    {"name": "Postman",        "category": "开发工具", "aliases": ["postman"]},
    {"name": "单元测试",       "category": "开发工具", "aliases": ["单元测试", "junit", "pytest", "unittest"]},
    {"name": "CI/CD",          "category": "开发工具", "aliases": ["ci/cd", "jenkins", "持续集成"]},

    # ---- 测试 ----
    {"name": "软件测试",       "category": "测试",    "aliases": ["软件测试", "测试用例", "功能测试"]},
    {"name": "自动化测试",     "category": "测试",    "aliases": ["自动化测试", "selenium", "appium"]},
    {"name": "接口测试",       "category": "测试",    "aliases": ["接口测试", "jmeter", "压力测试", "性能测试"]},
    {"name": "缺陷管理",       "category": "测试",    "aliases": ["缺陷管理", "bug跟踪", "禅道"]},

    # ---- 移动端 / 其他 ----
    {"name": "Android",        "category": "移动端",  "aliases": ["android", "安卓"]},
    {"name": "UI设计",         "category": "移动端",  "aliases": ["ui设计", "交互设计", "axure", "原型设计", "figma"]},

    # ---- 软性能力（JD 中常出现的要求）----
    {"name": "沟通协作",       "category": "软性要求", "aliases": ["沟通能力", "沟通协作", "团队协作", "团队合作"]},
    {"name": "抗压能力",       "category": "软性要求", "aliases": ["抗压", "压力承受"]},
    {"name": "学习能力",       "category": "软性要求", "aliases": ["学习能力", "自学能力"]},
    {"name": "文档撰写",       "category": "软性要求", "aliases": ["文档撰写", "技术文档", "需求文档"]},
    {"name": "英语能力",       "category": "软性要求", "aliases": ["英语", "cet-4", "cet-6", "四级", "六级"]},
]

# 把词典转成便于查找的结构：别名 -> 技能名
_ALIAS_TO_NAME = {}
for _s in SKILLS:
    for _a in _s["aliases"]:
        _ALIAS_TO_NAME[_a.lower()] = _s["name"]

# 技能名 -> 类别
_NAME_TO_CATEGORY = {s["name"]: s["category"] for s in SKILLS}

# ---------------------------------------------------------------------------
# 2.1 类别权重系数
#     软技能（沟通、学习能力）在 JD 里几乎都会写，但它们不是简历筛选的硬指标。
#     如果和硬技能同权重，会把匹配度整体拉低，让分数失去参考价值。
#     所以这里给软性要求打个折。
# ---------------------------------------------------------------------------
CATEGORY_FACTOR = {
    "软性要求": 0.5,
}


def _contains(low_text: str, alias: str) -> bool:
    """
    判断某个别名是否出现在（已转小写的）文本中。

    对长度 ≤ 2 的英文缩写（js、ts、go、sql 等）额外加一层边界校验，
    避免「js」误命中「json」、「go」误命中「google」这类情况。
    """
    if len(alias) <= 2 and alias.isascii():
        return re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", low_text) is not None
    return alias in low_text


def find_alternative_groups(jd_text: str):
    """
    识别 JD 里的「任选其一」关系。

    很多 JD 会这样写：
        「熟悉至少一种后端框架（Flask / FastAPI / Django）」
        「熟悉 MySQL 或 PostgreSQL」
    这类表述中，候选技能是**并列可替代**的，命中任意一个就满足要求。
    如果不做处理，程序会把三个可选项当成三个必须项，导致分数被严重低估。

    返回：一组技能名集合的列表，每个集合代表一个「任选其一」的分组。
    """
    groups = []
    seen = set()

    def _collect(fragment: str):
        """从一小段文本里收集所有出现的技能名。"""
        low = _lower(fragment)
        return {name for alias, name in _ALIAS_TO_NAME.items() if _contains(low, alias)}

    # 情况一：括号里面用 / 或「或」列举
    for m in re.finditer(r"[（(]([^）)]{0,150})[）)]", jd_text or ""):
        inner = m.group(1)
        if "/" in inner or "或" in inner:
            names = _collect(inner)
            if len(names) >= 2:
                groups.append(names)

    # 情况二：直接用「或」连接两个技能，例如「MySQL 或 PostgreSQL」
    for m in re.finditer(r"([^，。；\s]{1,20})\s*或\s*([^，。；\s]{1,20})", jd_text or ""):
        names = _collect(m.group(1)) | _collect(m.group(2))
        if len(names) >= 2:
            groups.append(names)

    # 去重：完全包含关系的小组不再重复处理
    result = []
    for g in groups:
        key = tuple(sorted(g))
        if key in seen:
            continue
        seen.add(key)
        result.append(g)
    return result

# ---------------------------------------------------------------------------
# 2. 权重修饰词
#    JD 里的"必须/精通"和"了解/加分"应该区别对待，
#    这是匹配打分比"数关键词个数"更合理的地方。
# ---------------------------------------------------------------------------
STRONG_WORDS = ["精通", "熟练掌握", "熟悉", "必须", "要求", "扎实", "深入", "至少", "熟悉掌握"]
WEAK_WORDS   = ["了解", "优先", "加分", "加分项", "有经验者优先", "可选", "最好", "接触过"]

# 学历门槛关键词（从高到低）
DEGREE_LEVELS = [
    ("博士", 5), ("硕士", 4), ("研究生", 4),
    ("本科", 3), ("学士", 3), ("大专", 2), ("专科", 2), ("中专", 1),
]

# 用户自身学历水平（用于判断门槛是否满足）
# 说明：这是使用者自己的情况，可在网页上选择，这里给默认值。
DEGREE_RANK = {"博士": 5, "硕士": 4, "本科": 3, "大专": 2, "中专": 1, "无": 0}


def _lower(text: str) -> str:
    """统一转小写，便于大小写不敏感匹配。"""
    return (text or "").lower()


def extract_skills(text: str):
    """
    从文本中提取所有出现的技能（标准名集合）。

    做法：遍历词典里的每个别名，看它是否作为子串出现在文本中。
    对别名长度小于等于 2 的英文缩写（如 js、ts、go），
    额外加一层边界校验，避免"js"误命中"json"这类情况。
    """
    low = _lower(text)
    found = set()
    for alias, name in _ALIAS_TO_NAME.items():
        if _contains(low, alias):
            found.add(name)
    return found


def extract_requirements(jd_text: str):
    """
    从 JD 中提取"要求项"，并给每一项计算权重。

    权重规则：
      基础权重 1.0
      + 该技能在 JD 中出现多次，每多一次 +0.3（最多 +0.9）
      + 附近出现强修饰词（精通/熟悉/必须…）  → ×1.5
      + 附近出现弱修饰词（了解/优先/加分…）  → ×0.6
    最后四舍五入保留 2 位小数。

    返回：{技能名: 权重}
    """
    low = _lower(jd_text)
    reqs = {}

    for alias, name in _ALIAS_TO_NAME.items():
        # --- 统计出现次数（短英文缩写需要边界校验，所以这里用正则在文本里找位置）---
        if len(alias) <= 2 and alias.isascii():
            positions = [m.start() for m in
                         re.finditer(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", low)]
        else:
            positions = [m.start() for m in re.finditer(re.escape(alias), low)]

        if not positions:
            continue

        weight = 1.0
        count = len(positions)
        weight += min(0.3 * (count - 1), 0.9)

        # --- 看修饰词 ---
        strong_hit = weak_hit = False
        for pos in positions:
            window = low[max(0, pos - 25): pos + 25]
            if any(w in window for w in STRONG_WORDS):
                strong_hit = True
            if any(w in window for w in WEAK_WORDS):
                weak_hit = True

        if strong_hit:
            weight *= 1.5
        elif weak_hit:
            weight *= 0.6

        # --- 按类别打折（软性要求权重减半）---
        weight *= CATEGORY_FACTOR.get(_NAME_TO_CATEGORY.get(name, ""), 1.0)

        # 同一技能通过不同别名命中时，取较高权重
        if name not in reqs or weight > reqs[name]:
            reqs[name] = round(weight, 2)

    return reqs


def detect_degree_requirement(jd_text: str):
    """识别 JD 里的学历门槛，返回 (要求的学历文字, 等级数值)；没有则返回 (None, 0)。"""
    low = _lower(jd_text)
    best_text, best_rank = None, 0
    for word, rank in DEGREE_LEVELS:
        if word in low and rank > best_rank:
            best_text, best_rank = word, rank
    return best_text, best_rank


def detect_experience_requirement(jd_text: str):
    """识别 JD 里的工作经验年限门槛，返回年限整数；没有则返回 0。"""
    low = _lower(jd_text)
    # 匹配"3年经验""3年以上工作经验""工作经验3年"等常见写法
    patterns = [
        r"(\d+)\s*年(?:以上)?(?:相关)?(?:工作)?经验",
        r"工作(?:经验)?\s*(\d+)\s*年",
        r"(\d+)\s*年(?:以上)?(?:的)?(?:开发|项目|从业)",
    ]
    years = 0
    for p in patterns:
        for m in re.finditer(p, low):
            try:
                years = max(years, int(m.group(1)))
            except ValueError:
                pass
    return years


def match(resume_text: str, jd_text: str, user_degree: str = "本科",
          user_work_years: int = 0):
    """
    主入口：分析简历与 JD 的匹配情况。

    参数：
        resume_text    —— 简历全文
        jd_text        —— 岗位 JD 全文
        user_degree    —— 用户自身学历（本科 / 大专 / 硕士 …）
        user_work_years—— 用户自身工作年限（应届生填 0）

    返回一个字典，包含评分、命中项、缺失项、门槛判断等，供前端渲染。
    """
    have = extract_skills(resume_text)          # 简历里已有的技能
    reqs = extract_requirements(jd_text)        # JD 要求的技能及权重

    # --- 处理「任选其一」关系，避免把可选项当成必须项 ---
    #
    # 规则：
    #   · 若该组中已经命中了至少一个  → 视为要求已满足，
    #     组内其余未命中项直接剔除（既不计入分母，也不列为缺失）；
    #   · 若该组一个都没命中          → 整组只保留权重最高的那一项作为缺失项，
    #     因为对求职者来说"这三个里你一个都不会"比"你缺三个"更准确。
    alt_groups = find_alternative_groups(jd_text)
    for group in alt_groups:
        members = [n for n in group if n in reqs]
        if len(members) < 2:
            continue
        hit_members = [n for n in members if n in have]
        if hit_members:
            for n in members:
                if n not in hit_members:
                    del reqs[n]
        else:
            # 未满足：整组只保留权重最高的那一项作为缺失项。
            # 注意先 sorted 再取 max——因为 group 是 set，遍历顺序不稳定，
            # 权重相同时（例如 Flask / Django / FastAPI 都是 1.5）
            # 不排序会导致每次跑出来的缺失项不一致，破坏"结果可复现"这一设计目标。
            best = max(sorted(members), key=lambda n: reqs[n])
            for n in members:
                if n != best:
                    del reqs[n]

    # --- 计算加权匹配度 ---
    total_weight = sum(reqs.values())
    hit_weight = sum(w for name, w in reqs.items() if name in have)

    if total_weight == 0:
        score = 0.0
    else:
        score = hit_weight / total_weight * 100

    # --- 区分命中 / 缺失，并附带权重供排序 ---
    hit = sorted([(n, w) for n, w in reqs.items() if n in have],
                 key=lambda x: -x[1])
    missing = sorted([(n, w) for n, w in reqs.items() if n not in have],
                     key=lambda x: -x[1])

    # --- 门槛判定 ---
    deg_text, deg_rank = detect_degree_requirement(jd_text)
    exp_years = detect_experience_requirement(jd_text)

    degree_ok = True
    if deg_rank > DEGREE_RANK.get(user_degree, 3):
        degree_ok = False

    exp_ok = exp_years <= user_work_years

    # --- 门槛不符时扣分（学历扣得更重，因为它是硬门槛）---
    penalty = 0
    if not degree_ok:
        penalty += 25
    if not exp_ok:
        penalty += 15
    final_score = max(0.0, score - penalty)

    # --- 生成提示语 ---
    notes = []
    if deg_text and not degree_ok:
        notes.append(f"该岗位要求「{deg_text}」学历，你的学历为「{user_degree}」，"
                     f"属于硬门槛不符，建议优先投递其他岗位或先在沟通中确认是否放宽。")
    elif deg_text:
        notes.append(f"该岗位要求「{deg_text}」学历，你的学历符合要求。")

    if exp_years and not exp_ok:
        notes.append(f"该岗位要求 {exp_years} 年经验，你目前 {user_work_years} 年，"
                     f"若为应届可主动说明实习/项目经历以弥补。")
    elif exp_years:
        notes.append(f"该岗位经验要求 {exp_years} 年，你满足该要求。")

    if total_weight == 0:
        notes.append("未能从岗位描述中识别出技能关键词，可能是 JD 文本过短或格式特殊，"
                     "建议粘贴完整的岗位要求部分。")

    # --- 给出可操作建议（纯规则，不依赖大模型）---
    suggestions = []
    for name, w in missing[:6]:
        cat = _NAME_TO_CATEGORY.get(name, "")
        if w >= 1.5:
            suggestions.append(f"【高优先级】岗位明确强调「{name}」（{cat}），"
                               f"这是简历筛选的关键词，务必核实是否真的具备；"
                               f"若具备，请写进技能栏并用项目经历佐证。")
        else:
            suggestions.append(f"建议补充「{name}」（{cat}）相关的能力描述或学习经历。")

    if hit:
        top_hits = "、".join(n for n, _ in hit[:8])
        suggestions.append(f"你已命中的核心关键词：{top_hits}。"
                           f"建议把其中与岗位最相关的 3—5 项放到简历技能栏的前排位置。")

    return {
        "score": round(final_score, 1),            # 最终匹配度（含门槛扣分）
        "raw_score": round(score, 1),              # 纯技能匹配度
        "penalty": penalty,
        "grade": _grade(final_score),
        "skill_total": len(reqs),
        "skill_hit": len(hit),
        "hit": [{"name": n, "weight": w, "category": _NAME_TO_CATEGORY.get(n, "")} for n, w in hit],
        "missing": [{"name": n, "weight": w, "category": _NAME_TO_CATEGORY.get(n, "")} for n, w in missing],
        "degree": {"required": deg_text, "ok": degree_ok, "yours": user_degree},
        "experience": {"required": exp_years, "ok": exp_ok, "yours": user_work_years},
        "notes": notes,
        "suggestions": suggestions,
    }


def _grade(score: float) -> str:
    """把分数翻译成一句人话，方便阅读。"""
    if score >= 85:
        return "高度匹配，建议优先投递"
    if score >= 70:
        return "较为匹配，可以投递并针对性调整简历"
    if score >= 50:
        return "部分匹配，需要补强关键词后再投"
    if score > 0:
        return "匹配度偏低，除非有特别理由，不建议优先投递"
    return "无法评估（JD 中未识别到技能关键词）"
