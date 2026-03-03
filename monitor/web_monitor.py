#!/usr/bin/env python3
"""
股票监控系统 - Web版本
支持实时监控 + Web状态页面
"""

from flask import Flask, render_template_string, jsonify
import threading
import time
import json
from datetime import datetime
from pathlib import Path

app = Flask(__name__)

# 全局状态
MONITOR_STATE = {
    "running": False,
    "last_update": None,
    "signals": {},
    "config": {}
}

def load_config():
    """加载配置"""
    config_path = Path(__file__).parent / "config.json"
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {
        "stocks": {
            "A股": ["600519", "000858", "601318"],
            "港股": ["00700", "09988"],
            "美股": ["AAPL", "MSFT"]
        },
        "indicators": {
            "rsi": {"period": 14, "overbought": 70, "oversold": 30},
            "macd": {"fast": 12, "slow": 26, "signal": 9},
            "bollinger": {"period": 20, "std": 2}
        },
        "interval": 60
    }

def get_stock_data(symbol, market):
    """获取股票数据"""
    import requests
    
    try:
        if market == "A股":
            sym = f"sh{symbol}" if symbol.startswith("6") else f"sz{symbol}"
        elif market == "港股":
            sym = f"hk{symbol.zfill(5)}"
        else:
            sym = symbol
        
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=kline_dayfq&param={sym},day,2025-01-01,,30,qfq"
        resp = requests.get(url, timeout=10)
        text = resp.text.replace("kline_dayfq=", "")
        data = json.loads(text)
        
        bars = data.get("data", {}).get(sym, {}).get("qfqday", []) or data.get("data", {}).get(sym, {}).get("day", [])
        
        if not bars:
            return None
        
        close = [float(b[2]) for b in bars]
        high = [float(b[3]) for b in bars]
        low = [float(b[4]) for b in bars]
        
        return {"close": close, "high": high, "low": low, "price": close[-1] if close else 0}
    except Exception as e:
        return None

def calculate_rsi(prices, period=14):
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
    return 100 - (100 / (1 + rs))

def generate_signal(data):
    """生成信号"""
    if not data or len(data.get("close", [])) < 30:
        return "数据不足"
    
    close = data["close"]
    price = data.get("price", close[-1])
    rsi = calculate_rsi(close)
    
    if rsi < 30:
        return "🟢 买入 (RSI超卖)"
    elif rsi > 70:
        return "🔴 卖出 (RSI超买)"
    else:
        return "⚪ 持有"

def monitor_loop():
    """监控循环"""
    global MONITOR_STATE
    
    config = load_config()
    MONITOR_STATE["config"] = config
    
    while MONITOR_STATE["running"]:
        signals = {}
        now = datetime.now()
        
        for market, symbols in config.get("stocks", {}).items():
            signals[market] = {}
            for symbol in symbols:
                data = get_stock_data(symbol, market)
                if data:
                    signal = generate_signal(data)
                    signals[market][symbol] = {
                        "signal": signal,
                        "price": data.get("price", 0),
                        "rsi": calculate_rsi(data["close"]) if len(data.get("close", [])) >= 15 else 50
                    }
        
        MONITOR_STATE["signals"] = signals
        MONITOR_STATE["last_update"] = now.strftime("%H:%M:%S")
        
        # 等待下次更新
        for _ in range(config.get("interval", 60)):
            if not MONITOR_STATE["running"]:
                break
            time.sleep(1)

@app.route('/')
def index():
    """主页"""
    config = MONITOR_STATE.get("config", load_config())
    signals = MONITOR_STATE.get("signals", {})
    last_update = MONITOR_STATE.get("last_update", "未启动")
    
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>📈 股票监控系统</title>
        <style>
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                max-width: 800px; margin: 0 auto; padding: 20px;
                background: #0a0a0a; color: #fff;
            }
            h1 { text-align: center; color: #fff; }
            .status { text-align: center; color: #888; margin-bottom: 20px; }
            .market { margin-bottom: 20px; }
            .market h2 { color: #4a9; border-bottom: 1px solid #333; padding-bottom: 10px; }
            .stock { 
                display: flex; justify-content: space-between; 
                padding: 10px; margin: 5px 0; background: #1a1a1a; 
                border-radius: 8px;
            }
            .stock .symbol { font-weight: bold; color: #888; }
            .stock .price { color: #4a9; }
            .stock .signal { font-weight: bold; }
            .green { color: #4a9; }
            .red { color: #f55; }
            .yellow { color: #fa0; }
            .controls { text-align: center; margin: 20px 0; }
            .btn { 
                padding: 10px 20px; margin: 5px; border: none; 
                border-radius: 8px; cursor: pointer; font-size: 16px;
            }
            .btn-start { background: #4a9; color: #000; }
            .btn-stop { background: #f55; color: #fff; }
            .btn-refresh { background: #444; color: #fff; }
            .last-update { text-align: center; color: #666; font-size: 12px; }
        </style>
    </head>
    <body>
        <h1>📈 股票监控系统</h1>
        <div class="status">当前监控 {{ config.get('stocks', {})|length }} 只股票</div>
        
        <div class="controls">
            <button class="btn btn-start" onclick="startMonitor()">▶ 启动监控</button>
            <button class="btn btn-stop" onclick="stopMonitor()">⏹ 停止监控</button>
            <button class="btn btn-refresh" onclick="location.reload()">🔄 刷新</button>
        </div>
        
        {% for market, stocks in signals.items() %}
        <div class="market">
            <h2>{{ market }}</h2>
            {% for symbol, data in stocks.items() %}
            <div class="stock">
                <span class="symbol">{{ symbol }}</span>
                <span class="price">¥{{ "%.2f"|format(data.price) }}</span>
                <span class="signal {% if '买入' in data.signal %}green{% elif '卖出' in data.signal %}red{% else %}yellow{% endif %}">{{ data.signal }}</span>
            </div>
            {% endfor %}
        </div>
        {% endfor %}
        
        <div class="last-update">最后更新: {{ last_update }}</div>
        
        <script>
        function startMonitor() {
            fetch('/start', {method: 'POST'}).then(r => location.reload());
        }
        function stopMonitor() {
            fetch('/stop', {method: 'POST'}).then(r => location.reload());
        }
        // Auto refresh every 30s
        setTimeout(() => location.reload(), 30000);
        </script>
    </body>
    </html>
    '''
    return render_template_string(html, config=config, signals=signals, last_update=last_update)

@app.route('/api/signals')
def api_signals():
    """API接口"""
    return jsonify(MONITOR_STATE)

@app.route('/start', methods=['POST'])
def start():
    """启动监控"""
    if not MONITOR_STATE["running"]:
        MONITOR_STATE["running"] = True
        thread = threading.Thread(target=monitor_loop, daemon=True)
        thread.start()
    return "OK"

@app.route('/stop', methods=['POST'])
def stop():
    """停止监控"""
    MONITOR_STATE["running"] = False
    return "OK"

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
