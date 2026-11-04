# 导入 Flask 框架和相关模块
from flask import Flask, render_template, request, jsonify
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from datetime import datetime
import config
import requests
import re
import ahocorasick
import jieba
import bisect
import threading
import ipaddress
from urllib.parse import urlparse

# 敏感词检测Plus引擎 (方案A: ToolGood.Words - AC自动机 + 文本归一化, 无jieba依赖)
from sensitive_plus import SensitivePlusEngine

import docx # 导入 docx 库用于处理 Word 文档
import PyPDF2 # 导入 PyPDF2 库用于处理 PDF 文档
import io # 导入 io 模块用于处理字节流
import os

# jieba 线程安全锁 (M-6: jieba.tokenize 非线程安全)
_jieba_lock = threading.Lock()

app = Flask(__name__)
app.config.from_object(config)

log_dir = Path.cwd() / "logs"
log_dir.mkdir(parents=True, exist_ok=True)
_log_file = log_dir / "user_actions.log"
action_logger = logging.getLogger("user_actions")
if not action_logger.handlers:
    handler = TimedRotatingFileHandler(_log_file, when="midnight", interval=1, backupCount=30, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(message)s")
    handler.setFormatter(formatter)
    action_logger.addHandler(handler)
    action_logger.setLevel(logging.INFO)

def _client_ip():
    ip = request.headers.get("X-Forwarded-For")
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()
    if not ip:
        ip = request.remote_addr
    return ip or "-"

def log_user_action(feature, text):
    content = text if isinstance(text, str) else str(text)
    content = content.replace("\n", "\\n")
    # m-5: 截断长文本避免日志泄露完整敏感内容
    if len(content) > 200:
        content = content[:200] + f"...(截断,共{len(content)}字符)"
    action_logger.info(f"[{feature}] ip={_client_ip()} input={content}")

def load_sensitive_words():
    print(f"尝试从以下路径加载敏感词: {config.SENSITIVE_WORDS_PATH}")
    try:
        with open(config.SENSITIVE_WORDS_PATH, 'r', encoding='utf-8') as f:
            words = [line.strip() for line in f if line.strip()]
            words.sort(key=len, reverse=True)
            print(f"成功加载 {len(words)} 个敏感词。")
            return words
    except FileNotFoundError:
        print(f"错误: 在 {config.SENSITIVE_WORDS_PATH} 未找到 sensitive_words.txt 文件")
        return []
    except Exception as e:
        print(f"加载敏感词时发生意外错误: {e}")
        return []

sensitive_words = load_sensitive_words()
DICT_SET = set(sensitive_words)

def build_automaton(words):
    a = ahocorasick.Automaton()
    for w in words:
        a.add_word(w, w)
    a.make_automaton()
    return a

AC_AUTOMATON = build_automaton(sensitive_words)
MAX_WORD_LEN = max((len(w) for w in sensitive_words), default=1)

# 敏感词检测Plus引擎 (使用同一词库, 无jieba依赖, 支持变体检测)
PLUS_ENGINE = SensitivePlusEngine(sensitive_words)

def _is_alnum(word):
    return word.isascii() and word.isalnum()

def _has_cjk(w):
    return any('\u4e00' <= ch <= '\u9fff' for ch in w)

def _has_ascii_alnum(w):
    return any(ch.isascii() and ch.isalnum() for ch in w)

def _is_mixed_cjk_ascii(w):
    """检查是否为中英文混合词(如 傻B, 傻x)"""
    return _has_cjk(w) and _has_ascii_alnum(w)

for _w in sensitive_words:
    if not _is_alnum(_w) and len(_w) >= 3:
        try:
            jieba.add_word(_w, freq=2000000)
        except Exception:
            pass

from collections import defaultdict
LONGER_BY_PREFIX = defaultdict(list)
for v in sensitive_words:
    if not _is_alnum(v) and len(v) >= 3:
        p2 = v[:2]
        if p2 in DICT_SET:
            LONGER_BY_PREFIX[p2].append(v)

def _is_cjk(ch):
    return '\u4e00' <= ch <= '\u9fff'

BLOCKLIST_INNER = {"中出", "女干", "性病"}

# M-1: ALLOW_INNER 改为手动维护
# 之前自动收集所有纯中文2字词(5579个),导致"人民"、"北京"等正常词汇被误报
# 只保留确认需要跳过token边界校验的2字敏感词
ALLOW_INNER = {"脑残", "傻逼", "煞笔", "傻B", "傻b", "傻X", "傻x"}


def _is_word_boundary(text, start, end_inclusive):
    left = text[start - 1] if start > 0 else ''
    right = text[end_inclusive + 1] if end_inclusive + 1 < len(text) else ''
    # 只检查ASCII字母数字作为边界判断
    # Python3中文字符isalnum()返回True,导致英文词被中文包围时误判为非边界
    def _is_ascii_alnum(ch):
        return ch.isascii() and ch.isalnum()
    return (not left or not _is_ascii_alnum(left)) and (not right or not _is_ascii_alnum(right))

def _token_boundaries(text):
    """C-3: 返回排序后的 token starts 和 token_map, 供二分查找使用"""
    token_starts = []
    token_map = {}
    with _jieba_lock:
        tokens = list(jieba.tokenize(text))
    for tk, s, e in tokens:
        token_map[(s, e)] = tk
        token_starts.append(s)
    token_starts.sort()
    return token_starts, token_map

def _find_containing_token(token_starts, token_map, start, end_exclusive):
    """C-3: 用二分查找定位包含 [start, end_exclusive] 的 token, O(log N)"""
    idx = bisect.bisect_right(token_starts, start) - 1
    if idx < 0:
        return None
    ts = token_starts[idx]
    # 在 token_map 中找以 ts 开头的 token
    for (s, e), tok in token_map.items():
        if s == ts and ts <= start and end_exclusive <= e:
            return tok
    return None

def scan_sensitive(text):
    if not text:
        return []
    matches = []
    if len(text) <= 200000:
        token_starts, token_map = _token_boundaries(text)
        for end, w in AC_AUTOMATON.iter(text):
            start = end - len(w) + 1
            if _is_alnum(w):
                if _is_word_boundary(text, start, end):
                    matches.append((start, end + 1, w))
            elif _is_mixed_cjk_ascii(w):
                matches.append((start, end + 1, w))
            else:
                span = (start, end + 1)
                if span in token_map and token_map[span] == w:
                    matches.append((start, end + 1, w))
                else:
                    tok = _find_containing_token(token_starts, token_map, start, end + 1)
                    if tok is not None and tok in DICT_SET and tok.startswith(w) and start == _find_token_start(token_starts, start):
                        matches.append((start, end + 1, w))
                    if len(w) == 2 and w in LONGER_BY_PREFIX:
                        subs = text[start:]
                        for v in LONGER_BY_PREFIX[w]:
                            if subs.startswith(v):
                                matches.append((start, end + 1, w))
                                break
                    if len(w) == 2 and w in ALLOW_INNER:
                        matches.append((start, end + 1, w))
        return matches
    res = []
    chunk = 200000
    overlap = MAX_WORD_LEN - 1
    base = 0
    while base < len(text):
        seg = text[base: min(len(text), base + chunk)]
        token_starts, token_map = _token_boundaries(seg)
        for end, w in AC_AUTOMATON.iter(seg):
            start = end - len(w) + 1
            if _is_alnum(w):
                if _is_word_boundary(seg, start, end):
                    res.append((base + start, base + end + 1, w))
            elif _is_mixed_cjk_ascii(w):
                res.append((base + start, base + end + 1, w))
            else:
                span = (start, end + 1)
                if span in token_map and token_map[span] == w:
                    res.append((base + start, base + end + 1, w))
                else:
                    tok = _find_containing_token(token_starts, token_map, start, end + 1)
                    if tok is not None and tok in DICT_SET and tok.startswith(w) and start == _find_token_start(token_starts, start):
                        res.append((base + start, base + end + 1, w))
                    if len(w) == 2 and w in LONGER_BY_PREFIX:
                        subs = seg[start:]
                        for v in LONGER_BY_PREFIX[w]:
                            if subs.startswith(v):
                                res.append((base + start, base + end + 1, w))
                                break
                    if len(w) == 2 and w in ALLOW_INNER:
                        res.append((base + start, base + end + 1, w))
        if base + chunk >= len(text):
            break
        base = base + chunk - overlap
    return res

def _find_token_start(token_starts, pos):
    """返回 <= pos 的最大 token start"""
    idx = bisect.bisect_right(token_starts, pos) - 1
    if idx < 0:
        return -1
    return token_starts[idx]

def _escape_markdown(text):
    """M-2: 转义 Markdown 特殊字符, 防止破坏 Markdown 结构"""
    return text.replace('\\', '\\\\').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('`', '\\`')

def highlight_matches(text, matches):
    if not matches:
        return text
    spans = sorted(matches, key=lambda x: x[0])
    out = []
    cur = 0
    for s, e, _w in spans:
        if s < cur:
            continue
        out.append(text[cur:s])
        out.append("**")
        out.append(_escape_markdown(text[s:e]))
        out.append("**")
        cur = e
    out.append(text[cur:])
    return ''.join(out)

def scan_sensitive_buggy(text):
    found = set()
    for end, w in AC_AUTOMATON.iter(text):
        found.add(w)
    return found

@app.route('/', methods=['GET', 'POST'])
def index():
    """
    主页路由，处理敏感词检测的 GET 和 POST 请求。
    GET 请求用于显示初始页面，POST 请求用于处理用户提交的文本进行敏感词检测。
    """
    result = None
    sensitive_result = "待检测"
    text = ""
    # 定义默认文本，用于在页面加载时显示示例内容
    default_text = """工信处女干事每月经过下属科室都要亲口交代24口交换机等技术性器件的安装工作
    
真不知道你们这群人是怎么想的，还在吹捧[某个明星/产品]？简直是瞎了眼。那个[XXX]就是个彻头彻尾的垃圾，演的戏/做的东西跟屎一样难看。粉丝也都是一群没脑子的傻B，天天在网上控评，看着就恶心。我话就放这里了，谁再敢吹他，谁就全家XXX。不服来辩啊，我今天就在这跟你们群脑残粉耗到底了！滚出这个贴吧！

各位大佬好，新人刚入坑《XX世界》，目前30级，主线刚推到风暴城。感觉这游戏上手难度还是有点大啊，特别是副本机制，昨天打[XXX副本]灭了好几次。我看攻略说要躲好BOSS的二阶段技能，但那个红圈范围太大了，根本跑不出去。请问各位有没有什么技巧？比如配装上有什么讲究吗？我是不是该先把武器强化一下？我现在用的是系统送的蓝装，感觉伤害有点刮痧。求一个老玩家带带，或者分享一个详细的开荒指南，感激不尽！

really, why the fucking [国家A] always against us? they are just doing that. checks their news, all are negative. i think that attack is the only way to go, we must be hard, can not be a peace animal. all people should be alert, otherwise our descendants will be affected! those who still believe in reconciliation, are fools!

老司机带路】懂的都懂，现在风头紧，好东西不好找了。我这里有渠道，各种“烟”和“酒”，保证纯正，价格公道。我们只做熟客生意，新人需要验证。想上车的兄弟，加我扣扣：【1 2 3 四 5 6 七 8 9】，或者私信我你的联（系）方（式）。我们还提供各种发.票、代.开.证明服务，绝对安全，物流保密。别再问了，懂的自然懂。

关于最近很火的[某AI模型]，我谈谈我的个人看法。我详细阅读了他们的技术白皮书，感觉在[某某架构]上的创新确实可圈可点。它解决了一部分传统模型在处理长序列依赖时的效率问题。但是，我也注意到它的训练成本非常高昂，需要大量的算力支持，这对于中小型企业来说几乎是无法承受的。我担心这会进一步加剧行业内的“军备竞赛”。大家觉得这项技术未来是会走向普及，还是会成为少数巨头的专属工具？欢迎楼下理性讨论，谢绝无意义的争吵。
"""

    if request.method == 'POST':
        text = request.form['text']
        check_type = request.form['check_type']

        if check_type == 'sensitive':
            log_user_action('敏感词检测', text)
            matches = scan_sensitive(text)
            found_words = sorted({w for _, _, w in matches})
            if found_words:
                sensitive_result = f"发现敏感词: <font color='red'>{', '.join(found_words)}</font>"
            else:
                sensitive_result = "未发现敏感词。"
        elif check_type == 'sensitive_plus':
            log_user_action('敏感词检测Plus', text)
            found_words = PLUS_ENGINE.find_words(text)
            if found_words:
                sensitive_result = f"发现敏感词: <font color='red'>{', '.join(found_words)}</font><br><span style='font-size:0.85em;color:#6c757d'>(Plus引擎: 支持全角/繁体/符号干扰变体检测)</span>"
            else:
                sensitive_result = "未发现敏感词。<br><span style='font-size:0.85em;color:#6c757d'>(Plus引擎: 支持全角/繁体/符号干扰变体检测)</span>"
        elif check_type == 'sensitive_buggy':
            log_user_action('敏感词检测（典型错误）', text)
            found_words = sorted(scan_sensitive_buggy(text))
            if found_words:
                sensitive_result = f"发现敏感词: <font color='red'>{', '.join(found_words)}</font>"
            else:
                sensitive_result = "未发现敏感词。"
    else: # GET request
        text = "" # 初始加载时设置文本为空
    # 渲染 index.html 模板，并传递检测结果和文本内容
    return render_template('index.html', sensitive_result=sensitive_result, text=text, default_text=default_text)

@app.route('/upload_file', methods=['POST'])
def upload_file():
    """
    文件上传路由，处理用户上传的文本文件（txt, docx, pdf）。
    解析文件内容并以 JSON 格式返回。
    """
    if 'file' not in request.files:
        return jsonify({'error': '未找到文件部分'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400
    if file:
        filename = file.filename
        try:
            # C-4: 限制文件大小 (10MB)
            max_size = getattr(config, 'MAX_CONTENT_LENGTH', 10 * 1024 * 1024)
            file_bytes = file.read(max_size + 1)
            if len(file_bytes) > max_size:
                return jsonify({'error': f'文件大小超过{max_size // 1024 // 1024}MB限制'}), 400
            text = extract_text_from_file(filename, file_bytes)
            return jsonify({'text': text})
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    return jsonify({'error': '未知错误'}), 500

def _is_internal_ip(hostname):
    """M-5: 检查是否为内网地址, 防止 SSRF"""
    try:
        ip = ipaddress.ip_address(hostname)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        # 不是 IP 地址, 检查常见内网域名
        internal_domains = ('localhost', '127.0.0.1', '0.0.0.0', '169.254.169.254',
                           'metadata.google.internal', 'metadata.tencentyun.com')
        return hostname.lower() in internal_domains

def extract_text_from_file(filename, file_content):
    """
    从文件内容中提取文本
    :param filename: 文件名或路径
    :param file_content: 文件字节流 或 文件路径字符串
    :return: 提取的文本
    """
    file_extension = str(filename).rsplit('.', 1)[1].lower() if '.' in str(filename) else ''
    text = ''

    # 检查是否为 URL
    if isinstance(file_content, str) and (file_content.startswith('http://') or file_content.startswith('https://')):
        # M-5: SSRF 防护 - 拦截内网地址
        parsed = urlparse(file_content)
        hostname = parsed.hostname or ''
        if _is_internal_ip(hostname):
            raise ValueError("不允许访问内网地址")
        try:
            response = requests.get(file_content, timeout=30)
            response.raise_for_status()
            file_content = response.content
        except Exception as e:
            raise ValueError(f"无法从 URL 下载文件: {str(e)}")

    # 如果传入的是路径且内容为空（或为None），则尝试打开文件读取
    elif isinstance(file_content, str) and os.path.exists(file_content):
         with open(file_content, 'rb') as f:
             file_content = f.read()
    elif isinstance(file_content, str):
        if len(file_content) < 256:
             raise FileNotFoundError(f"File not found: {file_content}")

    # 确保 file_content 是 bytes
    if not isinstance(file_content, bytes):
         raise ValueError("File content must be bytes or a valid file path")

    if file_extension == 'txt':
        # m-4: 尝试 UTF-8, 失败则用 GBK
        try:
            text = file_content.decode('utf-8')
        except UnicodeDecodeError:
            text = file_content.decode('gbk', errors='replace')
    elif file_extension == 'docx':
        doc = docx.Document(io.BytesIO(file_content))
        for para in doc.paragraphs:
            text += para.text + '\n'
    elif file_extension == 'pdf':
        reader = PyPDF2.PdfReader(io.BytesIO(file_content))
        for page_num in range(len(reader.pages)):
            text += reader.pages[page_num].extract_text() + '\n'
    else:
        raise ValueError('不支持的文件类型')
    
    return text

def api_response(data=None, message="操作成功！", code=200, success=True):
    return jsonify({
        "message": message,
        "code": code,
        "success": success,
        "data": data
    }), code


@app.route('/semantic_check', methods=['POST'])
def semantic_check_ajax():
    """
    语义检测路由，通过 AJAX 请求调用大模型进行语义分析。
    """
    # M-4: JSON 防御性解析
    data = request.get_json(silent=True, force=True)
    if not data:
        return jsonify({'error': '请求必须是JSON格式'}), 400
    text = data.get('text')
    if not text:
        return jsonify({'error': '未提供文本'}), 400
    log_user_action('语义检测', text)

    try:
        headers = {
            'Authorization': f'Bearer {config.LLM_API_KEY}',
            'Content-Type': 'application/json'
        }
        payload = {
            "model": config.LLM_MODEL_NAME,
            "messages": [
                {
                    "role": "system",
                    "content": config.SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": config.USER_PROMPT_TEMPLATE.format(text=text)
                }
            ]
        }
        # M-3: 添加超时 (连接10s, 读取120s)
        response = requests.post(config.LLM_API_URL, headers=headers, json=payload, timeout=(10, 120))
        response.raise_for_status()
        result = response.json()['choices'][0]['message']['content']
        return jsonify({'result': result})
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 500

def _semantic_check_plus_core(text, question=''):
    """
    m-3: 提取公共函数 — 语义检测Plus核心逻辑
    被语义检测Plus路由和API路由共用
    返回: (llm_analysis, found_words_str, error_message)
    """
    matches = scan_sensitive(text)
    found_words_in_text = {w for _, _, w in matches}
    sentences = re.split(r'(?<=[.!?。！？])\s*', text)
    sensitive_sentences_info = []
    text_for_llm = highlight_matches(text, matches)
    if matches:
        for s in sentences:
            if any(w.lower() in s.lower() for w in found_words_in_text):
                if s not in sensitive_sentences_info:
                    sensitive_sentences_info.append(s)

    user_prompt_content = f"**待分析文本：**\n{text_for_llm}\n"
    if sensitive_sentences_info:
        user_prompt_content += "\n**注意：以下句子中包含敏感词（已用双星号标记）：**\n"
        for s_sentence in sensitive_sentences_info:
            user_prompt_content += f"- {s_sentence}\n"
        user_prompt_content += "\n请特别关注这些句子进行语义分析。\n"

    system_prompt_content = config.SYSTEM_PROMPT_PLUS
    if question:
        system_prompt_content = question

    messages = [
        {"role": "system", "content": system_prompt_content},
        {"role": "user", "content": user_prompt_content}
    ]

    response = requests.post(
        config.LLM_API_URL,
        headers={
            "Authorization": f"Bearer {config.LLM_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": config.LLM_MODEL_NAME,
            "messages": messages,
            "temperature": 0.0
        },
        timeout=(10, 120)  # M-3: 连接超时10s, 读取超时120s
    )
    response.raise_for_status()
    llm_result = response.json()

    if not (llm_result and llm_result.get("choices")):
        return None, None, "大模型未返回有效响应"

    llm_analysis = llm_result["choices"][0]["message"]['content']
    found_words = sorted({w for _, _, w in matches})
    found_words_str = ";".join(found_words) if found_words else ""
    return llm_analysis, found_words_str, None

@app.route('/semantic_check_plus', methods=['POST'])
def semantic_check_plus_ajax():
    """增强型语义检测路由，结合敏感词检测和大模型语义分析。"""
    data = request.get_json(silent=True, force=True)
    if not data:
        return jsonify({'error': '请求必须是JSON格式'}), 400
    text = data.get('text')
    if not text:
        return jsonify({'error': '未提供文本'}), 400
    log_user_action('语义检测Plus', text)
    try:
        llm_analysis, _, err = _semantic_check_plus_core(text)
        if err:
            return jsonify({'error': err}), 500
        return jsonify({"result": llm_analysis})
    except requests.exceptions.RequestException as e:
        app.logger.error(f"大模型 API 请求失败: {e}")
        return jsonify({'error': f"大模型 API 请求失败: {e}"}), 500
    except Exception as e:
        app.logger.error(f"调用大模型时发生意外错误: {e}")
        return jsonify({'error': f"发生意外错误: {e}"}), 500

@app.route('/api/sensitive_check', methods=['POST'])
def api_sensitive_check():
    """
    敏感词检测 API
    """
    try:
        data = request.get_json(silent=True, force=True)
        if not data:
             return api_response(message="Invalid JSON", code=400, success=False)
        
        content = data.get('content')
        content_type = data.get('type', 0)
        
        if not content:
            return api_response(message="Content is required", code=400, success=False)
            
        text = ""
        if content_type == 1:
            # content is file path
            try:
                text = extract_text_from_file(content, content)
            except Exception as e:
                return api_response(message=f"File read error: {str(e)}", code=404, success=False)
        else:
            text = content
            
        log_user_action('API:敏感词检测', text)
        
        matches = scan_sensitive(text)
        found_words = sorted({w for _, _, w in matches})
        
        result_data = ""
        if found_words:
            result_data = ";".join(found_words)
            
        return api_response(data=result_data)

    except Exception as e:
        app.logger.error(f"API Error: {e}")
        return api_response(message=str(e), code=500, success=False)

@app.route('/api/semantic_check_plus', methods=['POST'])
def api_semantic_check_plus():
    """语义检测Plus API"""
    try:
        data = request.get_json(silent=True, force=True)
        if not data:
            return api_response(message="Invalid JSON", code=400, success=False)

        content = data.get('content')
        content_type = data.get('type', 0)
        question = data.get('question', '')

        if not content:
            return api_response(message="Content is required", code=400, success=False)

        text = ""
        if content_type == 1:
            try:
                text = extract_text_from_file(content, content)
            except Exception as e:
                return api_response(message=f"File read error: {str(e)}", code=404, success=False)
        else:
            text = content

        log_user_action('API:语义检测Plus', text)

        llm_analysis, _, err = _semantic_check_plus_core(text, question)
        if err:
            return api_response(message=err, code=500, success=False)
        return api_response(data=llm_analysis)

    except requests.exceptions.RequestException as e:
        app.logger.error(f"大模型 API 请求失败: {e}")
        return api_response(message=f"大模型 API 请求失败: {e}", code=500, success=False)
    except Exception as e:
        app.logger.error(f"API Error: {e}")
        return api_response(message=str(e), code=500, success=False)


# zj
@app.route('/api/v2/semantic_check_plus', methods=['POST'])
def api_semantic_check_plus_v2():
    """语义检测Plus API V2 (返回 llm_analysis + found_words)"""
    try:
        data = request.get_json(silent=True, force=True)
        if not data:
            return api_response(message="Invalid JSON", code=400, success=False)

        content = data.get('content')
        content_type = data.get('type', 0)
        question = data.get('question', '')

        if not content:
            return api_response(message="Content is required", code=400, success=False)

        text = ""
        if content_type == 1:
            try:
                text = extract_text_from_file(content, content)
            except Exception as e:
                return api_response(message=f"File read error: {str(e)}", code=404, success=False)
        else:
            text = content

        log_user_action('API:语义检测Plus', text)

        llm_analysis, found_words_str, err = _semantic_check_plus_core(text, question)
        if err:
            return api_response(message=err, code=500, success=False)

        result_data = {
            "llm_analysis": llm_analysis,
            "found_words": found_words_str
        }
        return api_response(data=result_data)

    except requests.exceptions.RequestException as e:
        app.logger.error(f"大模型 API 请求失败: {e}")
        return api_response(message=f"大模型 API 请求失败: {e}", code=500, success=False)
    except Exception as e:
        app.logger.error(f"API Error: {e}")
        return api_response(message=str(e), code=500, success=False)


@app.route('/sensitive_plus_check', methods=['POST'])
def sensitive_plus_check_ajax():
    """敏感词检测Plus AJAX接口 (方案A: ToolGood.Words引擎)"""
    data = request.get_json(silent=True, force=True)
    if not data:
        return jsonify({'error': '请求必须是JSON格式'}), 400
    text = data.get('text')
    if not text:
        return jsonify({'error': '未提供文本'}), 400
    log_user_action('敏感词检测Plus(AJAX)', text)
    
    found_words = PLUS_ENGINE.find_words(text)
    highlighted = PLUS_ENGINE.highlight(text)
    return jsonify({
        'found_words': found_words,
        'highlighted': highlighted,
        'count': len(found_words)
    })


@app.route('/api/sensitive_plus_check', methods=['POST'])
def api_sensitive_plus_check():
    """敏感词检测Plus API接口 (方案A: ToolGood.Words引擎)"""
    try:
        data = request.get_json(silent=True, force=True)
        if not data:
            return api_response(message="Invalid JSON", code=400, success=False)

        content = data.get('content')
        content_type = data.get('type', 0)

        if not content:
            return api_response(message="Content is required", code=400, success=False)

        text = ""
        if content_type == 1:
            try:
                text = extract_text_from_file(content, content)
            except Exception as e:
                return api_response(message=f"File read error: {str(e)}", code=404, success=False)
        else:
            text = content

        log_user_action('API:敏感词检测Plus', text)

        found_words = PLUS_ENGINE.find_words(text)
        found_words_str = ";".join(found_words) if found_words else ""
        return api_response(data=found_words_str)

    except Exception as e:
        app.logger.error(f"API Error: {e}")
        return api_response(message=str(e), code=500, success=False)


@app.route('/api_test')
def api_test():
    """API在线测试页面"""
    return render_template('api_test.html')


if __name__ == '__main__':
    # C-2: 通过环境变量控制 debug 模式, 默认关闭
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_mode, port=3309, host="0.0.0.0")  #部署到服务器
