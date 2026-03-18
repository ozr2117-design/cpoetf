import streamlit as st
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import requests
import datetime
import re

# ==========================================
# 0. 页面配置与定时刷新
# ==========================================
st.set_page_config(layout="wide", page_title="算力波段监控")

# 每 60000 毫秒（60秒）自动刷新一次页面
st_autorefresh(interval=60000, key="data_refresh")

# ==========================================
# 1. 移动端侧边栏（动态参数控制面板）
# ==========================================
st.sidebar.header("⚙️ 参数调节区")

st.sidebar.subheader("RSI 参数")
rsi_window = st.sidebar.number_input("窗口期", value=14, step=1)
rsi_overbought = st.sidebar.slider("超买阈值", min_value=70, max_value=90, value=75, step=1)
rsi_oversold = st.sidebar.slider("超卖阈值", min_value=10, max_value=30, value=25, step=1)

st.sidebar.subheader("布林带参数")
boll_window = st.sidebar.number_input("窗口期 (BOLL)", value=20, step=1)
boll_std = st.sidebar.slider("标准差倍数", min_value=1.5, max_value=3.0, value=2.0, step=0.1)

st.sidebar.subheader("背离报警阈值")
div_threshold = st.sidebar.slider("主动基金与ETF盘中差值报警线 (%)", min_value=0.5, max_value=3.0, value=1.5, step=0.1)

# ==========================================
# 2. 数据获取与处理模块
# ==========================================
FUND_WEIGHTS = {
    'sz300502': 0.0969, 'sz301377': 0.0964, 'sz300308': 0.0958,
    'sh688498': 0.0950, 'sh600183': 0.0941, 'sz002463': 0.0914,
    'sh688195': 0.0903, 'sz300476': 0.0877, 'sh688183': 0.0861,
    'sh601138': 0.0672
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Referer": "http://finance.sina.com.cn"
}

@st.cache_data(ttl=3600)
def get_historical_data(symbol="sh515880"):
    """使用腾讯接口获取历史日线，防封杀"""
    url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,,,300,qfq"
    res = requests.get(url, timeout=10)
    data = res.json()
    try:
        kline = data['data'][symbol]['qfqday']
    except KeyError:
        kline = data['data'][symbol]['day']
    
    # 解析数据：日期, 开盘, 收盘, 最高, 最低, 成交量
    df = pd.DataFrame(kline, columns=['date', 'open', 'close', 'high', 'low', 'volume'])
    df['date'] = pd.to_datetime(df['date'])
    for col in ['open', 'close', 'high', 'low', 'volume']:
        df[col] = df[col].astype(float)
    return df

def get_realtime_data(symbols):
    """使用新浪API获取实时报价"""
    symbols_str = ",".join(symbols)
    url = f"http://hq.sinajs.cn/list={symbols_str}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=5)
        res.encoding = 'gbk'
        lines = res.text.strip().split('\n')
    except Exception as e:
        st.error(f"实时数据获取失败: {e}")
        return {}

    realtime_dict = {}
    for line in lines:
        if not line: continue
        match = re.search(r'var hq_str_(\w+)="(.*)";', line)
        if match:
            sym = match.group(1)
            data_parts = match.group(2).split(',')
            if len(data_parts) > 3:
                name = data_parts[0]
                open_px = float(data_parts[1])
                pre_close = float(data_parts[2])
                price = float(data_parts[3])
                high = float(data_parts[4])
                low = float(data_parts[5])
                
                # 计算涨跌幅
                pct_chg = (price / pre_close - 1) * 100 if pre_close > 0 else 0.0
                realtime_dict[sym] = {
                    'name': name,
                    'price': price,
                    'pre_close': pre_close,
                    'open': open_px,
                    'high': high,
                    'low': low,
                    'pct_chg': pct_chg
                }
    return realtime_dict

# 需要获取的实时标的：515880, 515050, 及 021528持仓的10只个股
required_symbols = ['sh515880', 'sh515050'] + list(FUND_WEIGHTS.keys())
rt_data = get_realtime_data(required_symbols)

# ==========================================
# 3. 核心指标计算
# ==========================================

# (1) 021528拟合涨跌幅计算
active_fund_pct = 0.0
weight_sum = sum(FUND_WEIGHTS.values())
for sym, weight in FUND_WEIGHTS.items():
    if sym in rt_data:
        # 按个股涨跌幅加权
        active_fund_pct += rt_data[sym]['pct_chg'] * (weight / weight_sum)

# (2) 合并历史与实时 K 线数据，计算技术指标 (515880)
df_hist = get_historical_data("sh515880")
if 'sh515880' in rt_data:
    rt_515880 = rt_data['sh515880']
    today_date = pd.to_datetime(datetime.date.today())
    
    # 如果历史数据最后一天不是今天，追加今天的实时K线
    if df_hist.iloc[-1]['date'].date() != today_date.date():
        new_row = pd.DataFrame([{
            'date': today_date,
            'open': rt_515880['open'],
            'close': rt_515880['price'],
            'high': rt_515880['high'],
            'low': rt_515880['low'],
            'volume': 0
        }])
        df_hist = pd.concat([df_hist, new_row], ignore_index=True)
    else:
        # 更新最后一天的实时数据
        df_hist.at[df_hist.index[-1], 'close'] = rt_515880['price']
        df_hist.at[df_hist.index[-1], 'high'] = max(df_hist.iloc[-1]['high'], rt_515880['high'])
        df_hist.at[df_hist.index[-1], 'low'] = min(df_hist.iloc[-1]['low'], rt_515880['low'])
        if df_hist.iloc[-1]['open'] == 0:
             df_hist.at[df_hist.index[-1], 'open'] = rt_515880['open']

# 计算布林带 (BOLL)
df_hist['MA'] = df_hist['close'].rolling(window=boll_window).mean()
df_hist['STD'] = df_hist['close'].rolling(window=boll_window).std()
df_hist['BBU'] = df_hist['MA'] + boll_std * df_hist['STD']
df_hist['BBL'] = df_hist['MA'] - boll_std * df_hist['STD']

# 计算 RSI
delta = df_hist['close'].diff()
gain = delta.where(delta > 0, 0).ewm(alpha=1/rsi_window, adjust=False).mean()
loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/rsi_window, adjust=False).mean()
rs = gain / loss
df_hist['RSI'] = 100 - (100 / (1 + rs))

# 获取最新一条记录的技术指标
latest_k = df_hist.iloc[-1]
curr_price = latest_k['close']
curr_rsi = latest_k['RSI']
curr_bbl = latest_k['BBL']
curr_bbu = latest_k['BBU']

etf_pct = rt_data.get('sh515880', {}).get('pct_chg', 0.0)
etf_515050_pct = rt_data.get('sh515050', {}).get('pct_chg', 0.0)

# ==========================================
# 4. 前端展示 (UI)
# ==========================================

# 顶部状态卡片
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("515880 (通信ETF) 实时", f"{rt_data.get('sh515880', {}).get('price', 0.0):.3f}", f"{etf_pct:.2f}%")
with col2:
    st.metric("021528 (主动基金) 拟合", "计算中...", f"{active_fund_pct:.2f}%")
with col3:
    st.metric("515050 (5G ETF) 实时", f"{rt_data.get('sh515050', {}).get('price', 0.0):.3f}", f"{etf_515050_pct:.2f}%")

# 操作备忘录
with st.expander("📖 波段交易规则与参数说明", expanded=False):
    st.markdown("""
    - **RSI 策略**：低于超卖阈值为 **击球区**，高于超买阈值为 **分批止盈区**。
    - **BOLL 策略**：跌破下轨为 **极度恐慌黄金坑**，触碰上轨注意 **回调风险**。
    - **021528 聪明资金背离策略**：如果 ETF 跌但 021528 抗跌且差值突破报警线，说明机构在护盘/吸筹；反之说明机构在撤退。
    """)

# ==========================================
# 5. 动态信号灯区
# ==========================================
st.markdown("### 🔔 实时信号预警")

# 1. 聪明资金背离策略信号
divergence = active_fund_pct - etf_pct
if etf_pct < 0 and divergence >= div_threshold:
    st.success(f"🚨【聪明资金背离】ETF下跌，但主动基金严重抗跌 (领先 ETF {divergence:.2f}%)，超过设定的 {div_threshold}% 报警线！机构疑似护盘/吸筹！")
elif etf_pct > 0 and divergence <= -div_threshold:
    st.warning(f"⚠️【机构撤退风险】ETF上涨，但主动基金明显滞涨 (落后 ETF {-divergence:.2f}%)，警惕机构获利了结！")
else:
    st.info(f"💡 当前暂无显著背离。主动基金相对基准差值：{divergence:.2f}%")

# 2. RSI 策略信号
if not pd.isna(curr_rsi):
    if curr_rsi < rsi_oversold:
        st.success(f"🟢【击球区】当前 RSI ({curr_rsi:.2f}) 低于超卖阈值 {rsi_oversold}，市场处于超卖状态，可考虑建仓！")
    elif curr_rsi > rsi_overbought:
        st.warning(f"⚠️【止盈区】当前 RSI ({curr_rsi:.2f}) 高于超买阈值 {rsi_overbought}，市场处于超买状态，注意分批止盈！")

# 3. BOLL 策略信号
if not pd.isna(curr_bbl) and not pd.isna(curr_bbu):
    if curr_price < curr_bbl:
        st.success(f"🟢【黄金坑】当前价格 ({curr_price:.3f}) 已跌破布林线下轨 ({curr_bbl:.3f})，极度恐慌出现黄金坑！")
    elif curr_price > curr_bbu:
        st.error(f"⚠️【回调风险】当前价格 ({curr_price:.3f}) 已突破布林线上轨 ({curr_bbu:.3f})，短期回调风险巨大！")

# 图表渲染代码（包含K线和BOLL轨迹）已移除，以提高主界面刷新和加载速度。
