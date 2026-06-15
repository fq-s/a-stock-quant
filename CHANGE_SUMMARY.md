# Codex 第一轮增强说明

## 已完成

- 增加 Windows 一键安装和启动脚本。
- 自动识别本机 Python 3.11、3.12 或 3.13。
- 使用国内 PyPI 镜像，避免依赖安装长时间无响应。
- 补齐 `pyarrow` 依赖，使 Parquet 数据缓存可正常使用。
- 修复 Windows 中文控制台输出 emoji 时的编码崩溃。
- 修复净值不变时夏普比率显示异常大数的问题。
- 增加项目整合路线和中文入门说明。

## 验证结果

- `python -m compileall -q .`：通过
- `python -m pytest tests -q`：95 passed
- 平安银行 `000001`，2026-01-01 至 2026-03-31 真实数据下载：通过
- 单股真实数据回测入口：通过
- Parquet 本地缓存写入和读取：通过

## GitHub 状态

- Fork 已创建：https://github.com/fq-s/a-stock-quant
- ChatGPT Codex Connector 已安装并仅授权此仓库。
- 本轮改动提交至 `codex/windows-ready` 分支。
