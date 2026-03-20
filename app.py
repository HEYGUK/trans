from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from openai import OpenAI  # ⭐ OpenRouter 使用 OpenAI SDK
import json
import re
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⭐ OpenRouter 客户端初始化
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
client = OpenAI(
    base_url=app.config["OPENROUTER_BASE_URL"],  # ⭐ 指向 OpenRouter
    api_key=app.config["OPENROUTER_API_KEY"],     # ⭐ OpenRouter Key
)
MODEL = app.config["MODEL_NAME"]  # ⭐ 如 "anthropic/claude-sonnet-4-20250514"

# ⭐ OpenRouter 推荐的额外请求头
EXTRA_HEADERS = {
    "HTTP-Referer": "http://localhost:5000",
    "X-Title": "Student Translator",
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 系统提示词（与 API 无关，不用改）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SYSTEM_PROMPTS = {
    "general": """你是一位专业的留学生翻译助手。请提供准确、自然的翻译。
规则：
1. 保持原文的语气和风格
2. 专业术语需要在括号中标注原文
3. 翻译要符合目标语言的表达习惯""",

    "academic": """你是一位学术论文翻译专家，熟悉各学科的专业术语。
规则：
1. 使用学术正式语体
2. 专业术语必须准确，并在首次出现时用括号标注原文
3. 保持学术论文的逻辑严谨性
4. 数学公式、引用格式保持不变
5. 在翻译末尾提供【关键术语对照表】""",

    "daily": """你是一位生活翻译助手，帮助留学生处理日常沟通。
规则：
1. 使用口语化、自然的表达
2. 考虑文化差异，必要时添加说明
3. 对俚语/习语提供解释""",

    "email": """你是一位邮件翻译专家，帮助留学生撰写和翻译正式邮件。
规则：
1. 使用正式但不过于生硬的语气
2. 遵循英文邮件格式规范
3. 注意礼貌用语和文化差异
4. 如果是中译英，提供适当的邮件开头和结尾""",

    "polish": """你是一位英语学术写作润色专家。
规则：
1. 修正语法和拼写错误
2. 改善句子结构和表达流畅度
3. 提升学术写作水平
4. 用【修改说明】标注主要改动及理由
5. 保持原文的核心意思不变""",
}

LANGUAGE_MAP = {
    "zh-en": ("中文", "英文"),
    "en-zh": ("英文", "中文"),
    "zh-ja": ("中文", "日文"),
    "ja-zh": ("日文", "中文"),
    "zh-ko": ("中文", "韩文"),
    "ko-zh": ("韩文", "中文"),
    "zh-fr": ("中文", "法文"),
    "fr-zh": ("法文", "中文"),
    "zh-de": ("中文", "德文"),
    "de-zh": ("德文", "中文"),
    "zh-es": ("中文", "西班牙文"),
    "es-zh": ("西班牙文", "中文"),
    "en-ja": ("英文", "日文"),
    "ja-en": ("日文", "英文"),
    "auto":  ("自动检测", "自动"),
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 翻译核心函数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _build_user_message(text, lang_pair, mode, subject):
    """构造用户消息"""
    if lang_pair == "auto":
        lang_instruction = "请自动检测源语言，并翻译为另一种语言（中文↔英文优先）。"
    else:
        src, tgt = LANGUAGE_MAP.get(lang_pair, ("中文", "英文"))
        lang_instruction = f"请将以下{src}文本翻译为{tgt}。"
    if subject:
        lang_instruction += f"\n学科领域：{subject}"
    if mode == "polish":
        return f"请润色以下英文文本：\n\n{text}"
    return f"{lang_instruction}\n\n{text}"


def translate_normal(text, lang_pair, mode, subject=""):
    """
    普通翻译（一次性返回）
    ⭐ 使用 OpenAI SDK 的 chat.completions.create
    """
    system_prompt = SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["general"])
    user_message = _build_user_message(text, lang_pair, mode, subject)

    # ⭐ OpenRouter 调用方式（同 OpenAI 格式）
    response = client.chat.completions.create(
        model=MODEL,                                  # ⭐ "anthropic/claude-sonnet-4-20250514"
        max_tokens=4096,
        messages=[
            {"role": "system", "content": system_prompt},  # ⭐ system 放在 messages 里
            {"role": "user",   "content": user_message},
        ],
        extra_headers=EXTRA_HEADERS,                  # ⭐ OpenRouter 推荐
    )
    # ⭐ 读取结果: response.choices[0].message.content
    return response.choices[0].message.content


def translate_stream(text, lang_pair, mode, subject=""):
    """
    流式翻译（逐字返回）
    ⭐ 使用 OpenAI SDK 的 stream=True
    """
    system_prompt = SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["general"])
    user_message = _build_user_message(text, lang_pair, mode, subject)

    # ⭐ OpenRouter 流式调用
    stream = client.chat.completions.create(
        model=MODEL,
        max_tokens=4096,
        stream=True,                                  # ⭐ 开启流式
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
        extra_headers=EXTRA_HEADERS,
    )
    # ⭐ 逐 chunk 读取: chunk.choices[0].delta.content
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 路由
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/translate", methods=["POST"])
def api_translate():
    """普通翻译接口"""
    data = request.json or {}
    text = data.get("text", "").strip()
    lang_pair = data.get("lang_pair", "auto")
    mode = data.get("mode", "general")
    subject = data.get("subject", "")

    if not text:
        return jsonify({"error": "请输入要翻译的文本"}), 400
    if len(text) > app.config["MAX_TEXT_LENGTH"]:
        return jsonify({"error": f"文本不能超过 {app.config['MAX_TEXT_LENGTH']} 字符"}), 400

    try:
        result = translate_normal(text, lang_pair, mode, subject)
        return jsonify({
            "result": result,
            "engine": f"OpenRouter → {MODEL}",
            "mode": mode,
            "char_count": len(text),
        })
    except Exception as e:
        return jsonify({"error": f"翻译失败: {str(e)}"}), 500


@app.route("/api/translate/stream", methods=["POST"])
def api_translate_stream():
    """流式翻译接口"""
    data = request.json or {}
    text = data.get("text", "").strip()
    lang_pair = data.get("lang_pair", "auto")
    mode = data.get("mode", "general")
    subject = data.get("subject", "")

    if not text:
        return jsonify({"error": "请输入要翻译的文本"}), 400

    def generate():
        try:
            for chunk in translate_stream(text, lang_pair, mode, subject):
                yield f"data: {json.dumps({'text': chunk})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/detect-terms", methods=["POST"])
def api_detect_terms():
    """提取专业术语"""
    data = request.json or {}
    text = data.get("text", "").strip()
    subject = data.get("subject", "")

    if not text:
        return jsonify({"error": "请输入文本"}), 400

    prompt = f"""请从以下文本中提取专业术语，并提供中英对照。
学科领域：{subject if subject else '自动检测'}
以 JSON 数组格式返回，每项包含 term（原文）和 translation（译文）。
只返回 JSON，不要其他内容。

文本：{text}"""

    try:
        # ⭐ OpenRouter 调用
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
            extra_headers=EXTRA_HEADERS,
        )
        response_text = response.choices[0].message.content  # ⭐

        json_match = re.search(r"\[.*\]", response_text, re.DOTALL)
        terms = json.loads(json_match.group()) if json_match else []
        return jsonify({"terms": terms})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/model-info")
def api_model_info():
    """返回当前使用的模型信息"""
    return jsonify({"model": MODEL})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    print(f"🚀 翻译助手启动中...")
    print(f"⭐ OpenRouter 模型: {MODEL}")
    print(f"📎 访问 http://localhost:5000")
    app.run(debug=True, port=5000)
