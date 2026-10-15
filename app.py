"""
app.py —— Web 服务主程序（Flask）

职责：
  1. 提供一个网页界面（templates/index.html）
  2. 接收前端提交的简历文件和岗位 JD
  3. 依次调用 parser（解析）→ matcher（打分）→ llm（可选建议）
  4. 把结果以 JSON 返回给前端

启动方式：
    python app.py
然后浏览器打开 http://127.0.0.1:5000
"""

import json
import os

from flask import Flask, jsonify, render_template, request

import llm
import matcher
import parser

# 项目根目录，用于定位 config.json
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024   # 上传文件最大 10MB


def load_config() -> dict:
    """读取 config.json；不存在或格式错误时返回一份默认配置，保证程序能起来。"""
    path = os.path.join(BASE_DIR, "config.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"llm": {"api_key": "", "base_url": llm.DEFAULT_BASE_URL,
                        "model": llm.DEFAULT_MODEL, "timeout": 60}}


@app.route("/")
def index():
    """首页：返回页面模板，并告知前端当前是否已配置大模型。"""
    cfg = load_config()
    return render_template(
        "index.html",
        llm_ready=llm.is_configured(cfg),
        llm_model=cfg.get("llm", {}).get("model") or llm.DEFAULT_MODEL,
    )


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """
    分析接口。前端用 fetch 提交 FormData：
        resume_file —— 简历文件（可选）
        resume_text —— 简历文本（可选，与文件二选一）
        jd_text     —— 岗位 JD（必填）
        degree      —— 用户学历（可选，默认本科）
        work_years  —— 用户工作年限（可选，默认 0）

    返回 JSON：{ ok: true, data: {...} } 或 { ok: false, error: "..." }
    """
    try:
        jd_text = (request.form.get("jd_text") or "").strip()
        if not jd_text:
            return jsonify({"ok": False, "error": "请先粘贴岗位 JD 内容。"})

        degree = (request.form.get("degree") or "本科").strip()
        try:
            work_years = int(request.form.get("work_years") or 0)
        except ValueError:
            work_years = 0

        # ---- 第一步：拿到简历文本（优先用上传的文件，其次用文本框）----
        resume_text = ""
        source = ""
        uploaded = request.files.get("resume_file")
        if uploaded and uploaded.filename:
            raw = uploaded.read()
            if raw:
                resume_text = parser.parse_upload(uploaded.filename, raw)
                source = f"文件：{uploaded.filename}"

        if not resume_text.strip():
            resume_text = (request.form.get("resume_text") or "").strip()
            if resume_text:
                source = "粘贴文本"

        if not resume_text.strip():
            return jsonify({"ok": False,
                            "error": "没有读到简历内容。请上传文件，或把简历文字粘贴到文本框。"})

        # ---- 第二步：核心匹配打分（纯规则，必定能跑通）----
        result = matcher.match(resume_text, jd_text,
                               user_degree=degree, user_work_years=work_years)

        # ---- 第三步：尝试用大模型生成建议，失败就回退规则建议 ----
        cfg = load_config()
        advice, advice_error = llm.generate_advice(resume_text, jd_text, result, cfg)

        result["resume_source"] = source
        result["resume_preview"] = parser.summarize(resume_text, 160)
        result["jd_preview"] = parser.summarize(jd_text, 160)
        result["ai_advice"] = advice              # 可能是 None
        result["ai_advice_error"] = advice_error  # 失败原因（用于界面提示）
        result["llm_enabled"] = llm.is_configured(cfg)

        return jsonify({"ok": True, "data": result})

    except ValueError as e:
        # 解析类的可预期错误，直接把原因告诉用户
        return jsonify({"ok": False, "error": str(e)})
    except Exception as e:
        app.logger.exception("分析过程出错")
        return jsonify({"ok": False, "error": f"分析出错：{type(e).__name__}: {e}"})


if __name__ == "__main__":
    cfg = load_config()
    print("=" * 60)
    print("  AI 岗位匹配分析器")
    print("=" * 60)
    print(f"  大模型状态：{'已配置 ' + str(cfg.get('llm', {}).get('model')) if llm.is_configured(cfg) else '未配置（将使用规则建议，功能不受影响）'}")
    print("  访问地址：http://127.0.0.1:5000")
    print("  停止服务：在本窗口按 Ctrl+C")
    print("=" * 60)
    app.run(host="127.0.0.1", port=5000, debug=False)
