# 敏感词服务

Flask Web/API 服务，提供普通词库检测、Plus 归一化检测、TXT/DOCX/PDF 文本抽取和模型语义审核。主入口为 `app.py`，默认端口 3309。

## 本地准备

1. 安装 `requirements.txt` 中的依赖。
2. 默认的 `sensitive_words.example.txt` 仅有两条合成示例词。实际使用时，将 `SENSITIVE_WORDS_PATH` 设置为自己的 UTF-8 词库路径。
3. 如需语义审核，显式设置进程环境中的 `LLM_API_KEY`、`LLM_API_URL`、`LLM_MODEL_NAME`。`.env.example` 是变量说明，本程序不会自动加载 `.env`。
4. 从本目录执行 `python app.py`。缺少模型配置时，普通检测与语义审核的可用性应分别检查。

完整业务词库、真实密钥、日志和归档资料不属于公开代码范围。本次恢复了主程序与 Plus 模块并检查语法，未验证外部模型或部署。词库在启动时加载；修改后需按实际进程策略重启。正式部署还需核对访问控制、文件路径和 URL 读取边界。
