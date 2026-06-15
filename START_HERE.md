# 从这里开始

这个版本已经选定为你的 A股量化主项目底座。

## 最简单的使用顺序

1. 双击 `setup_windows.bat` 安装项目依赖。
2. 双击 `run_tests.bat` 检查项目是否正常。
3. 双击 `run_backtest.bat` 运行单股回测。
4. 双击 `run_portfolio_backtest.bat` 运行组合回测。
5. 双击 `run_web.bat` 打开管理面板。

项目已在 Windows + Python 3.13 环境完成验证：

- 95 个自动化测试通过
- 单股真实数据回测入口通过
- Windows 中文控制台输出兼容

## 当前限制

这台电脑已经检测到 Python 3.13。`setup_windows.bat` 会自动识别其安装位置，不依赖 PATH。

## 安全原则

当前只使用回测和模拟盘。没有确认策略、风控、账户权限之前，不连接真实交易账户。

详细整合计划见 `INTEGRATION_ROADMAP.md`。
