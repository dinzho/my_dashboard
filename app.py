import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import requests
from bs4 import BeautifulSoup

# 頁面設置
st.set_page_config(page_title="AI 投研閉環系統 (修復版)", page_icon="🧠", layout="wide")

st.title("🧠 AI 投研閉環系統：宏觀流動性 × 財報深度 × 新聞催化劑")
st.markdown("結合 Dollar Liquidity 底層邏輯 | 動態個股掃描 | 嚴格執行交易紀律 | 即時新聞追蹤")

# ================= 側邊欄：動態輸入與宏觀環境 =================
st.sidebar.header("⚙️ 控制面板")
ticker_input = st.sidebar.text_input("輸入股票代碼 (逗號分隔，如 MSFT, 0579.HK, NVO):", "MSFT, NVO, 0579.HK")
tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]

st.sidebar.markdown("---")
st.sidebar.subheader("🌍 宏觀流動性環境 (DL 邏輯)")

@st.cache_data(ttl=3600)
def get_macro_dl_data():
    try:
        macro = yf.download(["^VIX", "^TNX", "DX-Y.NYB", "HYG"], period="3mo", progress=False)['Close']
        latest = macro.iloc[-1]
        prev = macro.iloc[-10] 
        
        score = 50
        notes = []
        
        if latest['^VIX'] < 15: score += 15; notes.append("✅ VIX < 15：市場極度平靜，流動性充裕。")
        elif latest['^VIX'] > 25: score -= 15; notes.append("⚠️ VIX > 25：恐慌蔓延，流動性收緊。")
            
        if latest['^TNX'] < prev['^TNX']: score += 10; notes.append("✅ 10Y 收益率下行：估值壓力減輕。")
        else: score -= 10; notes.append("⚠️ 10Y 收益率上行：壓制高估值資產。")
            
        if latest['DX-Y.NYB'] < prev['DX-Y.NYB']: score += 10; notes.append("✅ 美元走弱：有利新興市場資金回流。")
        else: score -= 10; notes.append("⚠️ 美元走強：新興市場面臨抽水效應。")
            
        if latest['HYG'] > prev['HYG']: score += 15; notes.append("✅ 高收益債(HYG)走強：信用利差收緊，實體融資寬鬆。")
        else: score -= 15; notes.append("🚨 高收益債(HYG)走弱：信用利差走闊，市場定價違約風險！")
            
        score = max(0, min(100, score))
        
        if score >= 65: status = "🟢 寬鬆 (Risk-On)"
        elif score <= 35: status = "🔴 緊縮 (Risk-Off)"
        else: status = "🟡 中性 (Choppy)"
            
        return score, status, notes, latest['^VIX']
    except Exception as e:
        return 50, "🟡 中性 (數據異常)", ["請檢查網絡或 API 限制"], 15

macro_score, macro_status, macro_notes, current_vix = get_macro_dl_data()

st.sidebar.metric("DL 流動性評分", f"{macro_score}/100")
st.sidebar.metric("環境狀態", macro_status)
for note in macro_notes:
    st.sidebar.info(note)

if not tickers:
    st.warning("請在左側輸入至少一個股票代碼。")
    st.stop()

# ================= 建立雙分頁 (Tabs) =================
tab1, tab2 = st.tabs(["📊 個股深度研判 (財報×技術×紀律)", "📰 即時新聞情報局 (漲跌催化劑)"])

# ================= Tab 1: 個股深度研判 =================
with tab1:
    @st.cache_data(ttl=3600)
    def get_deep_stock_data(ticker):
        # 初始化默認字典，確保即使出錯也有完整的列名
        result = {
            "代碼": ticker, "當前價": "N/A", "RSI(14)": "N/A", "CCI(20)": "N/A",
            "FIB 61.8%": "N/A", "FCF Yield (%)": "N/A", "EPS Surprise (%)": "N/A",
            "毛利率 (%)": "N/A", "Forward PE": "N/A", "股息率 (%)": "N/A",
            "做空比例 (%)": "N/A", "機構持倉 (%)": "N/A"
        }
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="6mo")
            info = stock.info
            
            if hist.empty: return result
            
            close = hist['Close']
            high = hist['High']
            low = hist['Low']
            
            result["當前價"] = round(close.iloc[-1], 2)
            
            # 獨立容錯：技術指標
            try:
                delta = close.diff()
                gain = delta.where(delta > 0, 0).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = (100 - (100 / (1 + rs))).iloc[-1]
                result["RSI(14)"] = round(rsi, 1)
            except: pass
                
            try:
                tp = (high + low + close) / 3
                sma_tp = tp.rolling(window=20).mean()
                mad_tp = tp.rolling(window=20).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
                cci = ((tp - sma_tp) / (0.015 * mad_tp)).iloc[-1]
                if pd.notna(cci) and not np.isinf(cci): result["CCI(20)"] = round(cci, 1)
            except: pass
                
            try:
                period_high = high.max()
                period_low = low.min()
                fib_618 = period_high - 0.618 * (period_high - period_low)
                result["FIB 61.8%"] = round(fib_618, 2)
            except: pass
                
            # 獨立容錯：財報與估值
            try:
                fcf = info.get('freeCashflow')
                mcap = info.get('marketCap')
                if fcf and mcap and mcap != 0:
                    result["FCF Yield (%)"] = round((fcf / mcap) * 100, 2)
            except: pass
                
            try:
                gm = info.get('grossMargins')
                if gm: result["毛利率 (%)"] = round(gm * 100, 2)
            except: pass
                
            try:
                fpe = info.get('forwardPE')
                if fpe: result["Forward PE"] = round(fpe, 2)
            except: pass
                
            try:
                dy = info.get('dividendYield')
                if dy: result["股息率 (%)"] = round(dy * 100, 2)
            except: pass
                
            try:
                sf = info.get('shortPercentOfFloat')
                if sf: result["做空比例 (%)"] = round(sf * 100, 2)
            except: pass
                
            try:
                ih = info.get('heldPercentInstitutions')
                if ih: result["機構持倉 (%)"] = round(ih * 100, 2)
            except: pass
                
            # EPS Surprise
            try:
                ed = stock.earnings_dates
                if ed is not None and not ed.empty:
                    latest = ed.iloc[0]
                    actual = latest.get('Reported EPS')
                    estimate = latest.get('EPS Estimate')
                    if pd.notna(actual) and pd.notna(estimate) and estimate != 0:
                        result["EPS Surprise (%)"] = round(((actual - estimate) / abs(estimate)) * 100, 2)
            except: pass

        except Exception as e:
            pass # 即使整體出錯，也返回默認字典，保證表格結構完整
            
        return result

    st.markdown("### 📊 個股深度掃描 (財報 × 技術 × 資金)")
    st.markdown("💡 *核心關注：FCF Yield > 5% (現金流充沛), EPS Surprise > 0 (盈利超预期), 毛利率 > 30% (護城河).*")
    
    data_list = []
    for t in tickers:
        data_list.append(get_deep_stock_data(t))
        
    df = pd.DataFrame(data_list)

    # 條件格式化
    def highlight_cells(df):
        styles = pd.DataFrame('', index=df.index, columns=df.columns)
        for col in ['RSI(14)', 'FCF Yield (%)', '做空比例 (%)']:
            if col in df.columns:
                # 轉換為數值進行比較，忽略 N/A
                numeric_col = pd.to_numeric(df[col], errors='coerce')
                if col == 'RSI(14)':
                    styles.loc[numeric_col < 30, col] = 'background-color: #d4edda; color: black'
                    styles.loc[numeric_col > 70, col] = 'background-color: #f8d7da; color: black'
                elif col == 'FCF Yield (%)':
                    styles.loc[numeric_col > 5, col] = 'background-color: #d4edda; color: black'
                elif col == '做空比例 (%)':
                    styles.loc[numeric_col > 10, col] = 'background-color: #fff3cd; color: black'
        return styles

    st.dataframe(df.style.apply(highlight_cells, axis=None), use_container_width=True, hide_index=True)

    # ================= 港股價值防禦自動篩選 =================
    hk_stocks = df[df['代碼'].str.contains('.HK', na=False)]
    if not hk_stocks.empty:
        # 篩選 Forward PE < 10 且 股息率 > 3%
        value_picks = hk_stocks[
            (pd.to_numeric(hk_stocks['Forward PE'], errors='coerce') < 10) & 
            (pd.to_numeric(hk_stocks['股息率 (%)'], errors='coerce') > 3)
        ]
        if not value_picks.empty:
            codes = ", ".join(value_picks['代碼'].tolist())
            st.success(f"🛡️ **港股價值防禦雷達**：系統已自動鎖定符合您『低 PE + 高股息』標準的標的：**{codes}**。在宏觀緊縮時，這些是您極佳的防禦性加碼目標。")

    st.markdown("---")
    st.markdown("### 🧠 AI 研判與實戰紀律執行")
    
    for index, row in df.iterrows():
        st.markdown(f"#### 🎯 {row['代碼']} 綜合研判")
        
        # 安全獲取數值，將 N/A 轉為 NaN 以便比較
        rsi = pd.to_numeric(row['RSI(14)'], errors='coerce')
        fcf = pd.to_numeric(row['FCF Yield (%)'], errors='coerce')
        margin = pd.to_numeric(row['毛利率 (%)'], errors='coerce')
        short_pct = pd.to_numeric(row['做空比例 (%)'], errors='coerce')
        eps_s = pd.to_numeric(row['EPS Surprise (%)'], errors='coerce')
        
        insights = []
        
        # 1. 基本面定性
        if pd.notna(fcf) and fcf > 5 and pd.notna(margin) and margin > 30:
            insights.append("💎 **基本面極佳**：高 FCF 與高毛利率，具備極強護城河。")
        elif pd.notna(eps_s) and eps_s > 5:
            insights.append("🚀 **盈利驚喜**：最新財報 EPS 超預期，具備向上催化劑。")
            
        # 2. 資金面與軋空
        if pd.notna(short_pct) and short_pct > 10 and pd.notna(rsi) and rsi < 40:
            insights.append(f"🔥 **軋空潛力**：做空比例 {short_pct}%，技術偏弱，極易引發 Short Squeeze。")

        # 3. 核心：宏觀與微觀衝突的實戰紀律
        if macro_score <= 35: # 宏觀緊縮
            if pd.notna(rsi) and rsi < 30:
                insights.append("⚠️ **觸發實戰紀律：宏觀緊縮 + 微觀超賣**")
                insights.append("🎯 **執行動作：輕倉試探技術反彈 (建議倉位 10%-20%)**")
                insights.append("💡 **期權策略**：避免買長線 Call。建議在 FIB 61.8% 附近 **Sell Cash-Secured Put**，或買入極短期 Call 博弈反彈。")
            else: 
                insights.append("🛡️ **宏觀緊縮防禦**：流動性收緊，減少曝險，優先持有高 FCF 資產。")
        elif macro_score >= 65: # 宏觀寬鬆
            if pd.notna(rsi) and rsi > 50 and pd.notna(fcf) and fcf > 3:
                insights.append("🌊 **順風局重倉**：宏觀寬鬆 + 基本面強勁 + 技術多頭。建議順勢加倉。")
                insights.append("💡 **期權策略**：VIX 較低時，買入遠月 Call (LEAPS) 性價比極高。")
        else: 
            insights.append("⚖️ **震盪市操作**：流動性中性，嚴格在 FIB 支撐與阻力區間內高拋低吸。")

        if not insights:
            insights.append("ℹ️ **觀望中**：當前數據未觸發明確的極端信號，建議等待更清晰的技術突破或宏觀轉向。")

        for ins in insights:
            if "觸發實戰紀律" in ins: st.error(ins)
            elif "執行動作" in ins or "期權策略" in ins: st.warning(ins)
            else: st.info(ins)
        st.divider()

# ================= Tab 2: 即時新聞情報局 =================
with tab2:
    st.header("📰 即時新聞情報局：捕捉漲跌催化劑")
    st.markdown("自動掃描您關注股票的最新新聞，結合技術面判斷是『情緒錯殺』還是『基本面惡化』。")
    
    @st.cache_data(ttl=1800)
    def get_stock_news(tickers_list):
        all_news = []
        
        # 備用方案：使用 requests 抓取 Yahoo Finance 網頁
        def fetch_yahoo_web_news(ticker):
            url = f"https://finance.yahoo.com/quote/{ticker}/news"
            headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                soup = BeautifulSoup(resp.text, 'html.parser')
                items = []
                # 尋找新聞標題 (Yahoo 結構可能變動，嘗試多種標籤)
                for h3 in soup.find_all('h3'):
                    a_tag = h3.find('a')
                    if a_tag and a_tag.get('href') and a_tag.get_text(strip=True):
                        title = a_tag.get_text(strip=True)
                        link = a_tag['href']
                        if not link.startswith('http'): link = 'https://finance.yahoo.com' + link
                        items.append({"title": title, "link": link, "publisher": "Yahoo Finance", "time": "Recent"})
                return items[:5] # 最多取5條
            except:
                return []

        for t in tickers_list:
            news_items = []
            try:
                ticker_obj = yf.Ticker(t)
                raw_news = ticker_obj.news
                if raw_news:
                    for n in raw_news:
                        title, link, publisher, pub_time = "", "", "", ""
                        if isinstance(n, dict):
                            if 'content' in n:
                                c = n['content']
                                title = c.get('title', '')
                                link = c.get('canonicalUrl', {}).get('url', '')
                                publisher = c.get('provider', {}).get('displayName', '')
                                pub_time = c.get('pubDate', '')
                            else:
                                title = n.get('title', '')
                                link = n.get('link', '')
                                publisher = n.get('publisher', '')
                                pub_time = n.get('providerPublishTime', '')
                                
                        if title and link:
                            news_items.append({
                                "股票代碼": t, "發布時間": str(pub_time)[:16],
                                "新聞標題": title, "發布者": publisher,
                                "原文鏈接": link, "摘要": ""
                            })
            except:
                pass
                
            # 如果 yfinance 沒抓到，使用網頁抓取備用方案
            if not news_items:
                fb_news = fetch_yahoo_web_news(t)
                for fb in fb_news:
                    news_items.append({
                        "股票代碼": t, "發布時間": fb['time'],
                        "新聞標題": fb['title'], "發布者": fb['publisher'],
                        "原文鏈接": fb['link'], "摘要": "請點擊原文查看詳情。"
                    })
                    
            all_news.extend(news_items)
        return all_news

    news_list = get_stock_news(tickers)
    
    if news_list:
        for index, row in enumerate(news_list):
            with st.container():
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"### 🏷️ [{row['股票代碼']}] {row['新聞標題']}")
                    st.caption(f"🏢 來源: {row['發布者']} | 🕒 時間: {row['發布時間']}")
                    if row.get('摘要'):
                        st.markdown(f"*{row['摘要'][:200]}...*")
                with col2:
                    st.markdown(f"<br><br>", unsafe_allow_html=True)
                    st.markdown(f"[🔗 **閱讀全文**]({row['原文鏈接']})", unsafe_allow_html=True)
                st.divider()
    else:
        st.warning("暫無相關新聞，或 Yahoo API 暫時受限。請稍後刷新頁面。")
        
    st.markdown("---")
    st.markdown("### 💡 新聞 × 技術面 實戰思考指南")
    st.warning("""
    **如何判斷新聞是「黃金坑」還是「價值陷阱」？**
    1. **利空新聞 + 宏觀緊縮 + RSI 跌破 30**：極大概率是價值陷阱，**嚴格執行紀律，最多輕倉試探，絕不重倉抄底**。
    2. **利空新聞 + 宏觀寬鬆 + 股價打在 FIB 61.8% 支撐位**：這通常是市場情緒錯殺，是**絕佳的買入/買 Call 時機**。
    3. **利好新聞 + 宏觀緊縮 + RSI > 70**：警惕「利好出盡是利空」，主力可能藉機出貨，**考慮賣出 Covered Call 鎖定利潤**。
    """)
