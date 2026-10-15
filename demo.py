"""
demo.py —— 命令行演示脚本

用途：不开网页也能直接看到匹配引擎的工作效果。
运行：
    python demo.py                                  # 用内置样例简历和样例 JD
    python demo.py 我的简历.txt JD.txt               # 指定自己的文件

这个脚本同时也是很好的"验证工具"：
当你改了 matcher.py 里的词典或权重规则，跑一下这个脚本就能立刻看到影响。
"""

import os
import sys

import matcher
import parser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 内置样例简历（当没有传参时使用）
SAMPLE_RESUME = """
张杰睿  本科在读  计算机科学与技术
联系方式：15241135555 / 2138731381@qq.com  现所在地：沈阳

教育背景
2025.09—2027.06  沈阳城市学院  计算机科学与技术  本科
2022.09—2025.06  沈阳职业技术学院  软件技术  大专

专业技能
编程语言：Java、Python、JavaScript
Web 与数据库：HTML5/CSS3、jQuery、Vue、MySQL、SQLite
开发工具：Git、Linux、Postman
其他：软件测试、微信小程序、Android 基础

项目经历
校园资讯平台（Web）  独立开发  2023.03—2023.06
使用 HTML5 + CSS3 + JavaScript + jQuery + MySQL 实现新闻浏览、
分类筛选、用户评论与后台管理模块，独立完成前端架构与响应式布局。

智慧校园 AI 助手  项目负责人  2025.09—至今
校级创新创业项目，带领团队完成需求调研、功能设计与原型迭代。
"""


def load_text(path: str) -> str:
    """按扩展名自动解析文件。"""
    with open(path, "rb") as f:
        data = f.read()
    return parser.parse_upload(os.path.basename(path), data)


def main():
    if len(sys.argv) >= 3:
        resume_text = load_text(sys.argv[1])
        jd_text = load_text(sys.argv[2])
        print(f"简历来源：{sys.argv[1]}")
        print(f"JD 来源：{sys.argv[2]}")
    else:
        resume_text = SAMPLE_RESUME
        jd_text = load_text(os.path.join(BASE_DIR, "samples", "JD_AI应用开发.txt"))
        print("（未指定文件，使用内置样例简历 + 样例 JD）")

    # 这里传的用户情况：本科、应届（0 年经验）
    result = matcher.match(resume_text, jd_text, user_degree="本科", user_work_years=0)

    print()
    print("=" * 64)
    print(f"  综合匹配度：{result['score']} 分   （纯技能匹配 {result['raw_score']} 分）")
    print(f"  结论：{result['grade']}")
    print("=" * 64)

    print(f"\n技能命中：{result['skill_hit']} / {result['skill_total']}")

    print("\n【已命中】")
    for item in result["hit"]:
        print(f"  ✓ {item['name']}（{item['category']}）权重 ×{item['weight']}")

    print("\n【缺失】")
    for item in result["missing"]:
        flag = "  ← 高权重，重点补" if item["weight"] >= 1.5 else ""
        print(f"  ✗ {item['name']}（{item['category']}）权重 ×{item['weight']}{flag}")

    print("\n【门槛判定】")
    for n in result["notes"]:
        print(f"  · {n}")

    print("\n【规则生成的改进建议】")
    for s in result["suggestions"]:
        print(f"  · {s}")

    print("\n" + "=" * 64)
    print(f"  提示：把用户学历改成「大专」重跑，可以看到学历门槛对总分的影响。")
    print("=" * 64)


if __name__ == "__main__":
    main()
