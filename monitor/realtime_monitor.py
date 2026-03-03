#!/usr/bin/env python3
"""
股票实时监控系统
- A股+港股 (09:00-16:00 工作日)
- 美股 (20:30-次日05:00)
- RSI/MACD/布林带多指标融合分析
- 买入/卖出信号自动推送
- 非交易时段自动静默
"""

import os
import sys
import time
import json
import signal
from datetime import datetime, time as dt
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

class StockMonitor:
    """股票实时监控"""
    
    # 交易时段
    A_STOCK_START = dt(9, 30)   # A股上午盘
    A_STOCK_MID = dt(11, 30)     # A股午休
    A_STOCK_RESTART = dt(13, 0)  # A股下午盘
    A_STOCK_END = dt(15, 0)       # A股收盘
    
    HK_STOCK_START = dt(9, 30)    # 港股开盘
    HK_STOCK_END = dt(16, 0)      # 港股收盘
    
    US_STOCK_START = dt(20, 30)   # 美股开盘
    US_STOCK_END = dt(4, 0)       # 美股收盘(次日)
    
    def __init__(self, config_path: str = None):
        self.config = self.load_config(config_path)
        self.running = True
        self.last_signals: Dict[str, dict] = {}
        
        # Signal handler
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)
    
    def load_config(self, config_path: str = None) -> dict:
        """加载配置"""
        if config_path is None:
            config_path = PROJECT_ROOT / "config.json"
        
        default_config = {
            "stocks": {
                "A股": ["600519", "000858", "601318", "600036", "300750"],
                "港股": ["00700", "09988", "01810"],
                "美股": ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"]
            },
            "indicators": {
                "rsi": {"period": 14, "overbought": 70, "oversold": 30},
                "macd": {"fast": 12, "slow": 26, "signal": 9},
                "bollinger": {"period": 20, "std": 2}
            },
            "interval": 60,  # 刷新间隔(秒)
            "push_enabled": True
        }
        
        if os.path.exists(config_path):
            with open(config_path) as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config
    
    def is_trading_time(self, market: str) -> bool:
        """检查是否在交易时段"""
        now = datetime.now()
        current_time = now.time()
        weekday = now.weekday()  # 0=周一, 6=周日
        
        # 周末不交易
        if weekday >= 5:
            return False
        
        if market == "A股":
            # 上午盘 9:30-11:30, 下午盘 13:00-15:00
            return (dt(9, 30) <= current_time <= dt(11, 30)) or \
                   (dt(13, 0) <= current_time <= dt(15, 0))
        elif market == "港股":
            # 9:30-16:00
            return dt(9, 30) <= current_time <= dt(16, 0)
        elif market == "美股":
            # 20:30-04:00(次日)
            if current_time >= dt(20, 30):
                return True
            elif current_time <= dt(4, 0):
                return True
            return False
        
        return False
    
    def get_stock_data(self, symbol: str, market: str, days: int = 100) -> Optional[dict]:
        """获取股票数据"""
        try:
            if market == "A股":
                return self.get_a_stock_data(symbol, days)
            elif market == "港股":
                return self.get_hk_stock_data(symbol, days)
            elif market == "美股":
                return self.get_us_stock_data(symbol, days)
        except Exception as e:
            print(f"[{market}] {symbol} 获取数据失败: {e}")
        return None
    
    def get_a_stock_data(self, symbol: str, days: int = 100) -> Optional[dict]:
        """获取A股数据"""
        try:
            import akshare as ak
            # 尝试获取日K线
            if symbol.startswith("6"):
                stock_symbol = f"sh{symbol}"
            else:
                stock_symbol = f"sz{symbol}"
            
            df = ak.stock_zh_a_hist(symbol=symbol, period="daily", 
                                   start_date=(datetime.now() - datetime.timedelta(days * 2)).strftime("%Y%m%d"),
                                   end_date=datetime.now().strftime("%Y%m%d"),
                                   adjust="qfq")
            
            if df is None or df.empty:
                return None
            
            df = df.tail(days)
            return {
                "close": df["收盘"].astype(float).tolist(),
                "high": df["最高"].astype(float).tolist(),
                "low": df["最低"].astype(float).tolist(),
                "volume": df["成交量"].astype(float).tolist(),
                "dates": df["日期"].astype(str).tolist()
            }
        except Exception as e:
            # 尝试备用数据源
            return self.get_a_stock_data_fallback(symbol, days)
    
    def get_a_stock_data_fallback(self, symbol: str, days: int = 100) -> Optional[dict]:
        """备用A股数据源"""
        try:
            import requests
            # 使用腾讯财经API
            if symbol.startswith("6"):
                sym = f"sh{symbol}"
            else:
                sym = f"sz{symbol}"
            
            url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=kline_dayfq&param={sym},day,2023-01-01,,600,qfq"
            resp = requests.get(url, timeout=10)
            text = resp.text.replace("kline_dayfq=", "")
            data = json.loads(text)
            
            if "data" not in data or sym not in data["data"]:
                return None
            
            bars = data["data"][sym].get("qfqday", []) or data["data"][sym].get("day", [])
            if not bars:
                return None
            
            bars = bars[-days:]
            return {
                "close": [float(b[2]) for b in bars],
                "high": [float(b[3]) for b in bars],
                "low": [float(b[4]) for b in bars],
                "volume": [float(b[5]) for b in bars],
                "dates": [b[0] for b in bars]
            }
        except Exception as e:
            print(f"A股 {symbol} 备用数据源失败: {e}")
            return None
    
    def get_hk_stock_data(self, symbol: str, days: int = 100) -> Optional[dict]:
        """获取港股数据"""
        try:
            import requests
            # 港股代码格式: 00700 -> hk00700
            hk_code = f"hk{symbol.zfill(5)}"
            
            url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=kline_dayfq&param={hk_code},day,2023-01-01,,600,qfq"
            resp = requests.get(url, timeout=10)
            text = resp.text.replace("kline_dayfq=", "")
            data = json.loads(text)
            
            if "data" not in data or hk_code not in data["data"]:
                return None
            
            bars = data["data"][hk_code].get("day", [])
            if not bars:
                return None
            
            bars = bars[-days:]
            return {
                "close": [float(b[2]) for b in bars],
                "high": [float(b[3]) for b in bars],
                "low": [float(b[4]) for b in bars],
                "volume": [float(b[5]) for b in bars],
                "dates": [b[0] for b in bars]
            }
        except Exception as e:
            print(f"港股 {symbol} 获取失败: {e}")
            return None
    
    def get_us_stock_data(self, symbol: str, days: int = 100) -> Optional[dict]:
        """获取美股数据"""
        try:
            import yfinance as yf
            
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=f"{days}d")
            
            if hist.empty:
                return None
            
            return {
                "close": hist["Close"].astype(float).tolist(),
                "high": hist["High"].astype(float).tolist(),
                "low": hist["Low"].astype(float).tolist(),
                "volume": hist["Volume"].astype(float).tolist(),
                "dates": hist.index.strftime("%Y-%m-%d").tolist()
            }
        except Exception as e:
            print(f"美股 {symbol} 获取失败: {e}")
            return None
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """计算RSI"""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_macd(self, prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
        """计算MACD"""
        if len(prices) < slow + signal:
            return 0, 0, 0
        
        # EMA
        def ema(data, period):
            multiplier = 2 / (period + 1)
            ema_val = data[0]
            for price in data[1:]:
                ema_val = (price * multiplier) + (ema_val * (1 - multiplier))
            return ema_val
        
        # Simplified MACD using recent data
        ema_fast = sum(prices[-fast:]) / fast
        ema_slow = sum(prices[-slow:]) / slow
        macd_line = ema_fast - ema_slow
        
        # Signal line (simplified)
        signal_line = macd_line * 0.9  # Approximation
        
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    def calculate_bollinger(self, prices: List[float], period: int = 20, std_dev: int = 2) -> tuple:
        """计算布林带"""
        if len(prices) < period:
            return 0, 0, 0
        
        recent = prices[-period:]
        sma = sum(recent) / period
        variance = sum((p - sma) ** 2 for p in recent) / period
        std = variance ** 0.5
        
        upper_band = sma + (std_dev * std)
        lower_band = sma - (std_dev * std)
        
        return upper_band, sma, lower_band
    
    def generate_signal(self, data: dict) -> dict:
        """生成交易信号"""
        if not data or len(data["close"]) < 30:
            return {"signal": "无", "reason": "数据不足"}
        
        close = data["close"]
        current_price = close[-1]
        
        # 计算各项指标
        rsi = self.calculate_rsi(close)
        macd, signal, hist = self.calculate_macd(close)
        upper, middle, lower = self.calculate_bollinger(close)
        
        signals = []
        reasons = []
        
        # RSI 信号
        rsi_config = self.config["indicators"]["rsi"]
        if rsi < rsi_config["oversold"]:
            signals.append("买入")
            reasons.append(f"RSI超卖({rsi:.1f})")
        elif rsi > rsi_config["overbought"]:
            signals.append("卖出")
            reasons.append(f"RSI超买({rsi:.1f})")
        
        # MACD 信号
        if hist > 0 and macd > signal:
            signals.append("买入")
            reasons.append("MACD金叉")
        elif hist < 0 and macd < signal:
            signals.append("卖出")
            reasons.append("MACD死叉")
        
        # 布林带信号
        if current_price < lower:
            signals.append("买入")
            reasons.append("触及布林下轨")
        elif current_price > upper:
            signals.append("卖出")
            reasons.append("触及布林上轨")
        
        # 综合判断
        if not signals:
            return {"signal": "持有", "reason": "无明显信号", "rsi": rsi, "macd": macd, "price": current_price}
        
        # 多数投票
        buy_count = signals.count("买入")
        sell_count = signals.count("卖出")
        
        if buy_count > sell_count:
            return {"signal": "买入", "reason": "; ".join(reasons), "rsi": rsi, "macd": macd, "price": current_price}
        elif sell_count > buy_count:
            return {"signal": "卖出", "reason": "; ".join(reasons), "rsi": rsi, "macd": macd, "price": current_price}
        else:
            return {"signal": "持有", "reason": "信号平衡", "rsi": rsi, "macd": macd, "price": current_price}
    
    def check_and_push(self, symbol: str, market: str, signal: dict):
        """检查信号变化并推送"""
        key = f"{market}:{symbol}"
        last_signal = self.last_signals.get(key, {}).get("signal")
        current_signal = signal["signal"]
        
        if last_signal != current_signal:
            # 信号发生变化
            self.last_signals[key] = signal
            
            if current_signal in ["买入", "卖出"]:
                msg = f"【{market} {symbol}】信号变化: {current_signal}\n原因: {signal.get('reason', 'N/A')}\n价格: {signal.get('price', 0):.2f}\nRSI: {signal.get('rsi', 0):.1f}"
                print(f"\n🚨 {msg}\n")
                
                # 可以在这里集成推送渠道（如Telegram、微信等）
                if self.config.get("push_enabled"):
                    self.push_message(msg)
    
    def push_message(self, message: str):
        """推送消息（可扩展）"""
        # TODO: 集成 Telegram/微信/飞书 推送
        print(f"📤 推送消息: {message}")
    
    def run(self):
        """主循环"""
        print("=" * 50)
        print("📈 股票监控系统启动")
        print(f"监控标的: {json.dumps(self.config['stocks'], ensure_ascii=False)}")
        print("按 Ctrl+C 停止")
        print("=" * 50)
        
        while self.running:
            now = datetime.now()
            current_time = now.time()
            
            for market, symbols in self.config["stocks"].items():
                # 检查是否在交易时段
                if not self.is_trading_time(market):
                    continue
                
                print(f"\n[{now.strftime('%H:%M:%S')}] 检查 {market}...")
                
                for symbol in symbols:
                    try:
                        data = self.get_stock_data(symbol, market)
                        if data:
                            signal = self.generate_signal(data)
                            signal["market"] = market
                            signal["symbol"] = symbol
                            
                            # 显示信号
                            emoji = "🟢" if signal["signal"] == "买入" else "🔴" if signal["signal"] == "卖出" else "⚪"
                            print(f"  {symbol}: {emoji} {signal['signal']} (RSI:{signal.get('rsi', 0):.1f})")
                            
                            # 检查变化并推送
                            self.check_and_push(symbol, market, signal)
                        else:
                            print(f"  {symbol}: ❌ 无数据")
                    except Exception as e:
                        print(f"  {symbol}: ❌ 错误 - {e}")
            
            # 等待下次检查
            interval = self.config.get("interval", 60)
            for _ in range(interval):
                if not self.running:
                    break
                time.sleep(1)
    
    def stop(self, signum=None, frame=None):
        """停止监控"""
        print("\n\n🛑 收到停止信号，正在关闭...")
        self.running = False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="股票实时监控系统")
    parser.add_argument("-c", "--config", help="配置文件路径")
    args = parser.parse_args()
    
    monitor = StockMonitor(args.config)
    monitor.run()


if __name__ == "__main__":
    main()
