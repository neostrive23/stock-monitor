# 📈 股票监控系统

实时监控 A股 + 港股 + 美股，多指标智能分析。

## 功能特性

- **多市场监控**: A股(09:30-15:00)、港股(09:30-16:00)、美股(20:30-04:00)
- **技术指标**: RSI、MACD、布林带三指标融合
- **信号推送**: 买入/卖出信号自动推送（非交易时段静默）
- **策略回测**: 支持多种止损止盈策略回测

## 安装依赖

```bash
# 创建虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install akshare yfinance requests
```

## 监控模式

### 运行监控

```bash
cd /workspace/stock-monitor
python3 monitor/realtime_monitor.py
```

### 配置股票

编辑 `config.json`:

```json
{
    "stocks": {
        "A股": ["600519", "000858", "601318"],
        "港股": ["00700", "09988"],
        "美股": ["AAPL", "TSLA"]
    },
    "interval": 60,
    "push_enabled": true
}
```

### 参数说明

| 参数 | 说明 |
|------|------|
| interval | 刷新间隔(秒)，默认60 |
| rsi.period | RSI周期，默认14 |
| rsi.overbought | RSI超买阈值，默认70 |
| rsi.oversold | RSI超卖阈值，默认30 |
| macd.fast/slow/signal | MACD参数 |
| bollinger.period/std | 布林带参数 |

## 回测模式

### 基本用法

```bash
python3 backtest/backtest.py <成交文件> -s <开始日期> -e <结束日期>
```

### 示例

```bash
# 止损策略回测
python3 backtest/backtest.py ~/交易记录.xls -s 20250101 -e 20250301 --stop-loss 8

# 止盈策略回测  
python3 backtest/backtest.py ~/交易记录.xls -s 20250101 -e 20250301 --take-profit 20

# 移动止盈回测
python3 backtest/backtest.py ~/交易记录.xls -s 20250101 -e 20250301 --trailing 10

# MA止损回测
python3 backtest/backtest.py ~/交易记录.xls -s 20250101 -e 20250301 --ma 20

# 组合策略
python3 backtest/backtest.py ~/交易记录.xls -s 20250101 -e 20250301 --stop-loss 8 --take-profit 20 --trailing 10
```

### 参数说明

| 参数 | 说明 |
|------|------|
| --stop-loss | 止损百分比，如 8 表示 -8% 止损 |
| --take-profit | 止盈百分比，如 20 表示 +20% 止盈 |
| --trailing | 移动止盈回调百分比 |
| --ma | MA止损周期，如 20 表示跌破20日均线卖出 |
| -s | 开始日期，格式 YYYYMMDD |
| -e | 结束日期，格式 YYYYMMDD |

## 信号说明

| 信号 | 说明 |
|------|------|
| 🟢 买入 | 多个指标共振显示买入时机 |
| 🔴 卖出 | 多个指标共振显示卖出时机 |
| ⚪ 持有 | 无明显信号 |

## 技术指标

- **RSI**: 相对强弱指数，超卖(<30)买入，超买(>70)卖出
- **MACD**: 移动平均收敛发散，金叉买入，死叉卖出
- **布林带**: 价格触及下轨买入，触及上轨卖出
