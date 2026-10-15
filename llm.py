"""
llm.py —— 大模型调用模块（可选增强，不参与核心打分）

【这一版最重要的设计取舍】
大模型只被用来做一件事：把已经算好的匹配结果，
翻译成一段有针对性、说人话的「简历改进建议」。

匹配打分本身**完全不依赖大模型**。这样设计的好处：
1. 即使没有配置 API Key、或者现场网络断了，工具依然能跑出完整结果；
2. 分数稳定可复现，面试官问"这个 72 分怎么来的"能逐条解释；
3. 大模型万一返回了离谱内容，也污染不了核心结论。

调用的是「OpenAI 兼容」格式的接口，
所以只要改 config.json 里的 base_url 和 model，
就能在智谱、通义、DeepSeek、腾讯混元等平台之间自由切换，业务代码不用动。
"""

import json
import os
import urllib.request
import urllib.error

# 默认使用智谱开放平台的免费模型（手机号注册即可，永久免费）
DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
DEFAULT_MODEL = "glm-4.7-flash"

# 系统提示词：约束模型的角色和输出格式
SYSTEM_PROMPT = """你是一位有十年经验的互联网技术岗招聘官兼简历顾问。
你会收到三份材料：一份简历、一份岗位JD、以及一份由程序计算出的关键词匹配结果。

请基于这些材料，输出一份简洁、具体、可执行的简历改进建议。

要求：
1. 严格基于给定材料，不要编造候选人没有的经历、学历或项目；
2. 如果建议补充某项技能，必须提醒候选人「仅在你真实具备时才写」；
3. 分点输出，每点不超过 60 字；
4. 优先指出最影响简历通过率的问题，最多 6 点；
5. 不要复述匹配结果里的数字，直接给建议；
6. 用中文，语气专业、直接，不要说客套话。"""


def is_configured(cfg: dict) -> bool:
    """判断是否已经配置好可用的 API Key。"""
    key = _get_api_key(cfg)
    return bool(key) and not key.startswith("在这里")


def _get_api_key(cfg: dict) -> str:
    """
    取 API Key，两种方式，环境变量优先：
      1. 环境变量 ZHIPU_API_KEY / LLM_API_KEY（推荐，不写进文件，避免误传上 GitHub）
      2. config.json 里的 api_key 字段
    """
    env_key = os.environ.get("ZHIPU_API_KEY") or os.environ.get("LLM_API_KEY")
    if env_key:
        return env_key.strip()
    return (cfg.get("llm", {}).get("api_key") or "").strip()


def _build_prompt(resume_text: str, jd_text: str, result: dict) -> str:
    """把三份材料拼成一段提示词。过长的文本会截断，避免超出上下文限制。"""
    hit_names = "、".join(item["name"] for item in result.get("hit", [])) or "无"
    miss_names = "、".join(item["name"] for item in result.get("missing", [])) or "无"

    return f"""【简历正文】
{resume_text[:3000]}

【岗位JD】
{jd_text[:2000]}

【程序计算的匹配结果】
加权技能匹配度：{result.get('raw_score')} 分
学历门槛：{result.get('degree', {}).get('required') or '未提及'}（是否满足：{'是' if result.get('degree', {}).get('ok') else '否'}）
经验门槛：{result.get('experience', {}).get('required') or 0} 年（是否满足：{'是' if result.get('experience', {}).get('ok') else '否'}）
已命中的关键词：{hit_names}
缺失的关键词：{miss_names}

请给出这份简历针对该岗位的改进建议。"""


def generate_advice(resume_text: str, jd_text: str, result: dict, cfg: dict):
    """
    调用大模型生成改进建议。

    返回 (建议文本, 错误信息)：
      - 成功：(建议字符串, None)
      - 失败：(None, 错误说明)
    调用方拿到 None 时会自动回退到 matcher 里生成的规则建议，功能不受影响。
    """
    if not is_configured(cfg):
        return None, "未配置 API Key，已改用规则生成的建议（不影响匹配度计算）。"

    llm_cfg = cfg.get("llm", {})
    base_url = (llm_cfg.get("base_url") or DEFAULT_BASE_URL).rstrip("/")
    model = llm_cfg.get("model") or DEFAULT_MODEL
    timeout = int(llm_cfg.get("timeout") or 60)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_prompt(resume_text, jd_text, result)},
        ],
        "temperature": 0.3,   # 调低随机性，让建议更稳定
        "stream": False,
    }

    req = urllib.request.Request(
        url=f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_get_api_key(cfg)}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"].strip()
        if not content:
            return None, "大模型返回了空内容，已改用规则生成的建议。"
        return content, None

    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8")[:300]
        except Exception:
            pass
        hint = ""
        if e.code == 401:
            hint = "（API Key 无效或已过期，请检查 config.json）"
        elif e.code == 429:
            hint = "（免费额度触发限流，稍等片刻再试即可）"
        return None, f"调用大模型失败：HTTP {e.code} {hint} {detail}"
    except urllib.error.URLError as e:
        return None, f"网络请求失败（可能是断网或需要代理）：{e.reason}"
    except Exception as e:
        return None, f"调用大模型时发生意外错误：{type(e).__name__}: {e}"
