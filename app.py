import streamlit as st
import akshare as ak
import pandas as pd
import datetime
import plotly.express as px

# ================= 1. 初始化与配置 =================
st.set_page_config(page_title="CIO 旗舰指挥台 V6.2", layout="wide", page_icon="🏦")

# 默认持仓
DEFAULT_HOLDINGS = [
    {'name': '科创50',    'code': 'sh588000', 'cost': 0, 'principal': 4181.81, 'type': 'ETF'},
    {'name': '消费电子',  'code': 'sz159732', 'cost': 0,  'principal': 4341.96, 'type': 'ETF'},
    {'name': '人工智能',  'code': 'sz159819', 'cost': 0,    'principal': 3787.17,     'type': 'ETF'},
    {'name': '纳斯达克',  'code': 'sz159941', 'cost': 0,  'principal': 4871.39,'type': 'ETF'},
]

# === 🌟 升级：全市场超级雷达池 ===
MARKET_SCANNER = {
    '🚀 核心成长': [
        {'name': '半导体ETF',   'code': 'sh000990', 'etf': '512480'},
        {'name': '人工智能ETF', 'code': 'sz159819', 'etf': '159819'},
        {'name': '新能车ETF',   'code': 'sz399976', 'etf': '515030'},
        {'name': '光伏ETF',     'code': 'sh931151', 'etf': '515790'},
        {'name': '科创50ETF',   'code': 'sh000688', 'etf': '588000'},
        {'name': '创业板ETF',   'code': 'sz399006', 'etf': '159915'},
    ],
    '💰 稳健/周期': [
        {'name': '红利低波',    'code': 'sh000814', 'etf': '512890'},
        {'name': '证券ETF',     'code': 'sz399975', 'etf': '512000'},
        {'name': '银行ETF',     'code': 'sz399986', 'etf': '512800'},
        {'name': '煤炭ETF',     'code': 'sh000820', 'etf': '515220'},
        {'name': '医疗ETF',     'code': 'sz399989', 'etf': '512170'},
    ],
    '🌍 全球/另类': [
        {'name': '纳指科技',    'code': 'sz159509', 'etf': '159509 (景顺)'},
        {'name': '标普500',     'code': 'sh513500', 'etf': '513500'},
        {'name': '恒生科技',    'code': 'sz159740', 'etf': '159740'},
        {'name': '黄金ETF',     'code': 'sh518880', 'etf': '518880'},
        {'name': '日经ETF',     'code': 'sh513520', 'etf': '513520'},
    ]
}

if 'my_holdings' not in st.session_state:
    st.session_state['my_holdings'] = pd.DataFrame(DEFAULT_HOLDINGS)
if 'show_popup' not in st.session_state:
    st.session_state['show_popup'] = True

# ================= 2. 核心数据引擎 =================

def is_trading_time():
    now = datetime.datetime.now()
    if now.weekday() > 4: return False
    morning_open = now.replace(hour=9, minute=30, second=0)
    afternoon_close = now.replace(hour=15, minute=0, second=0)
    return morning_open <= now <= afternoon_close

@st.cache_data(ttl=300)
def get_data(symbol, type_hint="ETF"):
    clean_code = symbol.replace("sh", "").replace("sz", "").split(" ")[0] # 兼容带备注的代码
    is_etf = True if (type_hint == "ETF" or clean_code.startswith(('15', '51', '16'))) else False
    
    try:
        if is_etf:
            df = ak.fund_etf_hist_em(symbol=clean_code, period="daily", start_date="20240101", adjust="qfq")
            df = df[['日期', '收盘', '成交量', '开盘']].rename(columns={'日期': 'date', '收盘': 'close', '成交量': 'volume', '开盘': 'open'})
        else:
            df = ak.stock_zh_index_daily(symbol=symbol)
            
        df['date'] = pd.to_datetime(df['date']).dt.date
        
        # 实时数据拼接
        if is_trading_time():
            try:
                spot_func = ak.fund_etf_spot_em if is_etf else ak.stock_zh_index_spot
                df_spot = spot_func()
                row = df_spot[df_spot['代码'] == clean_code]
                if not row.empty:
                    curr_price = row['最新价'].values[0]
                    curr_vol = row['成交量'].values[0]
                    now = datetime.datetime.now()
                    start = now.replace(hour=9, minute=30, second=0)
                    mins = (now - start).seconds / 60
                    if now.hour >= 13: mins -= 90
                    ratio = max(1, min(240, mins)) / 240
                    proj_vol = curr_vol / ratio if ratio > 0 else curr_vol
                    
                    new_row = pd.DataFrame({'date': [datetime.date.today()], 'close': [curr_price], 'volume': [proj_vol], 'open': [curr_price]})
                    df = pd.concat([df, new_row], ignore_index=True)
            except: pass

        df['MA5'] = df['close'].rolling(5).mean()
        df['MA20'] = df['close'].rolling(20).mean()
        df['VOL_MA5'] = df['volume'].rolling(5).mean()
        return df
    except: return None

def analyze_trend(df):
    if df is None: return None
    today = df.iloc[-1]
    prev = df.iloc[-2]
    price = today['close']
    ma5 = today['MA5']
    ma20 = today['MA20']
    vol_ratio = today['volume'] / today['VOL_MA5'] if today['VOL_MA5'] > 0 else 1.0
    
    trend = "bull" if price > ma5 else "bear"
    signal = "观望"
    score = 0 
    action_type = "HOLD"
    
    if trend == "bull":
        if vol_ratio > 1.2:
            signal = "🚀 放量进攻"; score = 90; action_type = "BUY"
        else:
            signal = "✅ 温和上涨"; score = 70; action_type = "HOLD"
    else:
        if vol_ratio > 1.2:
            signal = "⚠️ 放量下跌"; score = 85; action_type = "SELL"
        else:
            signal = "📉 缩量回调"; score = 40; action_type = "HOLD"
            
    if price > ma20 and price > ma5 and vol_ratio > 1.1 and (price - prev['close']) > 0:
        signal = "🎯 黄金买点"; score = 100; action_type = "BUY"
        
    return {
        'price': price, 
        'pct': (price-prev['close'])/prev['close']*100, 
        'signal': signal, 
        'score': score, 
        'action_type': action_type,
        'vol_ratio': vol_ratio,
        'data_df': df 
    }

# ================= 3. 数据处理 (已加入去重逻辑) =================

all_recommendations = []
portfolio_display_list = [] 
held_set = set() # 新增：用于存储已持有的代码，防止雷达重复推荐

df_holdings = st.session_state['my_holdings']
total_principal = 0
total_market_value = 0
today_pnl = 0

# 1. 分析持仓 (先处理持仓，并记录代码)
for index, row in df_holdings.iterrows():
    if row['principal'] >= 0:
        # 记录已持有的代码 (去掉 sh/sz 前缀，只留数字，方便对比)
        clean_code = row['code'].replace("sh", "").replace("sz", "")
        held_set.add(clean_code)

        data = get_data(row['code'], row.get('type', 'ETF'))
        if data is not None:
            res = analyze_trend(data)
            
            current_val = 0
            holding_pnl = 0
            holding_pnl_pct = 0
            
            if row['principal'] > 0:
                cost = row['cost'] if row['cost'] > 0 else res['price']
                ret_rate = (res['price'] - cost) / cost
                current_val = row['principal'] * (1 + ret_rate)
                holding_pnl = current_val - row['principal']
                holding_pnl_pct = ret_rate * 100
                
                total_principal += row['principal']
                total_market_value += current_val
                
                prev_price = data.iloc[-2]['close']
                day_change = (res['price'] - prev_price) / prev_price
                today_pnl += current_val * day_change
            
            portfolio_display_list.append({
                'name': row['name'],
                'price': res['price'],
                'pct': res['pct'],
                'holding_pnl': holding_pnl,
                'holding_pnl_pct': holding_pnl_pct,
                'current_val': current_val,
                'signal': res['signal'],
                'data': data
            })

            final_score = res['score']
            if res['action_type'] == 'SELL': final_score += 15 # 止损加权
            
            all_recommendations.append({
                'name': row['name'], 'code': row['code'], 'signal': res['signal'],
                'action': res['action_type'], 'score': final_score, 'is_holding': True, 'pct': res['pct']
            })

# 2. 分析雷达 (显示具体ETF代码 + 去重)
for cat, items in MARKET_SCANNER.items():
    for item in items:
        # --- 新增去重逻辑 ---
        # 提取雷达配置中的ETF代码数字部分
        clean_etf = item['etf'].split(" ")[0].replace("sh", "").replace("sz", "")
        # 如果这个代码已经在我的持仓里了，跳过，不再重复推荐
        if clean_etf in held_set:
            continue
        # ------------------

        data = get_data(item['code'])
        if data is not None:
            res = analyze_trend(data)
            if res['score'] >= 80:
                all_recommendations.append({
                    'name': item['name'], 
                    'code': item['etf'], 
                    'signal': res['signal'],
                    'action': res['action_type'], 
                    'score': res['score'], 
                    'is_holding': False, 
                    'pct': res['pct']
                })

all_recommendations.sort(key=lambda x: x['score'], reverse=True)
top_5_ops = all_recommendations[:5]

# ================= 4. UI 渲染 =================

# --- A. 智能弹窗 (带代码) ---
if st.session_state['show_popup'] and top_5_ops:
    with st.container():
        st.markdown("""<div style="background-color:#f0f2f6; padding:15px; border-radius:10px; border-left: 5px solid #FF4B4B; margin-bottom: 20px;">
        <h4 style="margin-top:0;">🔔 今日 CIO 核心内参</h4>
        """, unsafe_allow_html=True)
        cols = st.columns(len(top_5_ops))
        for i, op in enumerate(top_5_ops):
            with cols[i]:
                badge = "👜持仓" if op['is_holding'] else "🔭机会"
                color = "green" if op['action'] == "SELL" else "red"
                st.caption(f"{badge} {op['name']}")
                st.markdown(f"**:{color}[{op['action']}]** {op['pct']:.2f}%")
                if not op['is_holding']:
                    st.code(op['code'], language="text") # 直接显示代码方便复制
                else:
                    st.caption(f"信号: {op['signal']}")
        
        if st.button("已阅"):
            st.session_state['show_popup'] = False
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

# --- B. 资产大屏 ---
st.title("🏦 私人资产指挥台 V6.2")

total_return_val = total_market_value - total_principal
total_return_pct_val = (total_return_val/total_principal*100) if total_principal>0 else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("总资产", f"¥ {total_market_value:,.0f}")
c2.metric("今日盈亏", f"¥ {today_pnl:+,.0f}", help="根据今日涨跌幅估算的持仓变动")
c3.metric("总收益", f"¥ {total_return_val:+,.0f}", f"{total_return_pct_val:+.2f}%")
c4.metric("市场状态", "交易中 🟢" if is_trading_time() else "已休市 🔴")

st.divider()

# --- C. 持仓管理 ---
st.subheader("💼 我的持仓管理")
col_edit, col_vis = st.columns([1.5, 1])
with col_edit:
    with st.expander("🛠️ 展开修改持仓成本与本金", expanded=False):
        edited_df = st.data_editor(
            st.session_state['my_holdings'],
            num_rows="dynamic",
            column_config={
                "name": "名称", "code": "监控代码",
                "cost": st.column_config.NumberColumn("持仓成本", format="%.3f"),
                "principal": st.column_config.NumberColumn("投入本金", format="¥%d"),
                "type": st.column_config.SelectboxColumn("类型", options=["ETF", "INDEX"])
            },
            use_container_width=True
        )
        if not edited_df.equals(st.session_state['my_holdings']):
            st.session_state['my_holdings'] = edited_df
            st.rerun()

with col_vis:
    if portfolio_display_list:
        pf_df = pd.DataFrame(portfolio_display_list)
        if not pf_df.empty and pf_df['current_val'].sum() > 0:
            fig = px.pie(pf_df, values='current_val', names='name', title='持仓分布', hole=0.4)
            fig.update_layout(margin=dict(t=30, b=0, l=0, r=0), height=200)
            st.plotly_chart(fig, use_container_width=True)

st.markdown("### 📈 持仓实时看板")
if portfolio_display_list:
    cols = st.columns(4)
    for i, item in enumerate(portfolio_display_list):
        with cols[i % 4]:
            st.markdown(f"**{item['name']}**")
            st.metric(
                label=f"现价 {item['price']:.3f}",
                value=f"{item['pct']:.2f}%",
                delta_color="normal"
            )
            if item['current_val'] > 0:
                pnl_color = "red" if item['holding_pnl'] > 0 else "green"
                st.markdown(f"""<small>盈亏: <span style='color:{pnl_color}'>¥{item['holding_pnl']:,.0f}</span></small>""", unsafe_allow_html=True)
            
            if "买点" in item['signal'] or "进攻" in item['signal']:
                st.success(item['signal'])
            elif "下跌" in item['signal']:
                st.error(item['signal'])
            else:
                st.info(item['signal'])
            st.line_chart(item['data'].tail(20)['close'], height=30)
else:
    st.info("暂无持仓数据")

# --- D. 市场雷达 (带代码推荐) ---
st.divider()
st.subheader("🔭 市场雷达 (建议关注)")

scan_tabs = st.tabs(list(MARKET_SCANNER.keys()))
for i, (cat, items) in enumerate(MARKET_SCANNER.items()):
    with scan_tabs[i]:
        cols = st.columns(5) # 5列布局更紧凑
        for idx, item in enumerate(items):
            with cols[idx % 5]:
                data = get_data(item['code'])
                if data is not None:
                    res = analyze_trend(data)
                    st.markdown(f"**{item['name']}**")
                    st.metric(label=item['etf'], value=f"{res['pct']:.2f}%", label_visibility="visible")
                    
                    if res['score'] >= 80:
                        st.success(f"{res['signal']}")
                        st.markdown(f"👉 **`{item['etf']}`**") # 重点：显示具体代码
                    else:
                        st.caption(res['signal'])
                    

                    st.line_chart(data.tail(10)['close'], height=20)
