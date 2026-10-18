import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

# 頁面設置
st.set_page_config(page_title="AI 投研閉環系統 (DL+財報+新聞)", page_icon="🧠", layout="wide")

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
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="6mo")
            info = stock.info
            
            if hist.empty: return None
            
            close = hist['Close']
            high = hist['High']
            low = hist['Low']
            
            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rsi = (100 - (100 / (1 + (gain / loss)))).iloc[-1]
            
            tp = (high + low + close) / 3
            sma_tp = tp.rolling(window=20).mean()
            mad_tp = tp.rolling(window=20).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
            cci = ((tp - sma_tp) / (0.015 * mad_tp)).iloc[-1]
            if pd.isna(cci) or np.isinf(cci): cci = 0
            
            period_high = high.max()
            period_low = low.min()
            current_price = close.iloc[-1]
            fib_618 = period_high - 0.618 * (period_high - period_low)
            
            fcf = info.get('freeCashflow', 0)
            market_cap = info.get('marketCap', 1)
            fcf_yield = (fcf / market_cap) * 100 if fcf and market_cap else 0
            
            eps_surprise = "N/A"
            try:
                earnings_dates = stock.earnings_dates
                if earnings_dates is not None and not earnings_dates.empty:
                    latest_earn = earnings_dates.iloc[0]
                    if 'EPS Estimate' in latest_earn and 'Reported EPS' in latest_earn:
                        actual = latest_earn['Reported EPS']
                        estimate = latest_earn['EPS Estimate']
                        if pd.notna(actual) and pd.notna(estimate) and estimate != 0:
                            eps_surprise = ((actual - estimate) / abs(estimate)) * 100
            except:
                pass
                
            gross_margin = info.get('grossMargins', 0) * 100 if info.get('grossMargins') else 0
            forward_pe = info.get('forwardPE', 'N/A')
            short_float = info.get('shortPercentOfFloat', 0) * 100 if info.get('shortPercentOfFloat') else 0
            inst_hold = info.get('heldPercentInstitutions', 0) * 100 if info.get('heldPercentInstitutions') else 0
            
            return {
                "代碼": ticker, "當前價": round(current_price, 2),
                "RSI(14)": round(rsi, 1), "CCI(20)": round(cci, 1),
                "FIB 61.8%": round(fib_618, 2),
                "FCF Yield (%)": round(fcf_yield, 2),
                "EPS Surprise (%)": round(eps_surprise, 2) if isinstance(eps_surprise, float) else eps_surprise,
                "毛利率 (%)": round(gross_margin, 2),
                "Forward PE": round(forward_pe, 2) if isinstance(forward_pe, (int, float)) else forward_pe,
                "做空比例 (%)": round(short_float, 2), "機構持倉 (%)": round(inst_hold, 2)
            }
        except Exception as e:
            return {"代碼": ticker, "Error": str(e)}

    st.markdown("### 📊 個股深度掃描 (財報 × 技術 × 資金)")
    data_list = []
    for t in tickers:
        data = get_deep_stock_data(t)
        if data: data_list.append(data)
    df = pd.DataFrame(data_list)

    def highlight_cells(df):
        styles = pd.DataFrame('', index=df.index, columns=df.columns)
        if 'RSI(14)' in df.columns:
            styles.loc[df['RSI(14)'] < 30, 'RSI(14)'] = 'background-color: #d4edda; color: black'
            styles.loc[df['RSI(14)'] > 70, 'RSI(14)'] = 'background-color: #f8d7da; color: black'
        if 'FCF Yield (%)' in df.columns:
            styles.loc[df['FCF Yield (%)'] > 5, 'FCF Yield (%)'] = 'background-color: #d4edda; color: black'
        if '做空比例 (%)' in df.columns:
            styles.loc[df['做空比例 (%)'] > 10, '做空比例 (%)'] = 'background-color: #fff3cd; color: black'
        return styles

    if not df.empty and 'Error' not in df.columns:
        st.dataframe(df.style.apply(highlight_cells, axis=None), use_container_width=True, hide_index=True)
    elif not df.empty:
        st.error(f"部分代碼獲取失敗: {df['Error'].tolist()}")

    st.markdown("---")
    st.markdown("### 🧠 AI 研判與實戰紀律執行")
    for index, row in df.iterrows():
        if 'Error' in row: continue
        st.markdown(f"#### 🎯 {row['代碼']} 綜合研判")
        rsi, fcf, eps_s, margin, short_pct = row['RSI(14)'], row['FCF Yield (%)'], row['EPS Surprise (%)'], row['毛利率 (%)'], row['做空比例 (%)']
        insights = []
        
        if fcf > 5 and margin > 30: insights.append("💎 **基本面極佳**：高 FCF 與高毛利率，具備極強護城河。")
        elif eps_s != "N/A" and eps_s > 5: insights.append("🚀 **盈利驚喜**：最新財報 EPS 超預期，具備向上催化劑。")
        if short_pct > 10 and rsi < 40: insights.append(f"🔥 **軋空潛力**：做空比例 {short_pct}%，技術偏弱，極易引發 Short Squeeze。")

        if macro_score <= 35: 
            if rsi < 30:
                insights.append("⚠️ **觸發實戰紀律：宏觀緊縮 + 微觀超賣**")
                insights.append("🎯 **執行動作：輕倉試探技術反彈 (建議倉位 10%-20%)**")
                insights.append("💡 **期權策略**：避免買長線 Call。建議在 FIB 61.8% 附近 **Sell Cash-Secured Put**，或買入極短期 Call 博弈反彈。")
            else: insights.append("🛡️ **宏觀緊縮防禦**：流動性收緊，減少曝險，優先持有高 FCF 資產。")
        elif macro_score >= 65: 
            if rsi > 50 and fcf > 3:
                insights.append("🌊 **順風局重倉**：宏觀寬鬆 + 基本面強勁 + 技術多頭。建議順勢加倉。")
                insights.append("💡 **期權策略**：VIX 較低時，買入遠月 Call (LEAPS) 性價比極高。")
        else: insights.append("⚖️ **震盪市操作**：流動性中性，嚴格在 FIB 支撐與阻力區間內高拋低吸。")

        for ins in insights:
            if "觸發實戰紀律" in ins: st.error(ins)
            elif "執行動作" in ins or "期權策略" in ins: st.warning(ins)
            else: st.info(ins)
        st.divider()

# ================= Tab 2: 即時新聞情報局 =================
with tab2:
    st.header("📰 即時新聞情報局：捕捉漲跌催化劑")
    st.markdown("自動掃描您關注股票的最新新聞，結合技術面判斷是『情緒錯殺』還是『基本面惡化』。")
    
    @st.cache_data(ttl=1800) # 新聞緩存 30 分鐘
    def get_stock_news(tickers_list):
        all_news = []
        for t in tickers_list:
            try:
                ticker_obj = yf.Ticker(t)
                news = ticker_obj.news
                if news:
                    for n in news:
                        # 兼容 yfinance 新舊版本的新聞數據結構
                        title, link, publisher, pub_time, summary = "", "", "", "", ""
                        
                        if 'content' in n: # 新版結構
                            content = n['content']
                            title = content.get('title', '')
                            link = content.get('canonicalUrl', {}).get('url', '')
                            publisher = content.get('provider', {}).get('displayName', '')
                            pub_time = content.get('pubDate', '')
                            summary = content.get('summary', '')
                        else: # 舊版結構
                            title = n.get('title', '')
                            link = n.get('link', '')
                            publisher = n.get('publisher', '')
                            pub_time = n.get('providerPublishTime', '')
                            summary = n.get('summary', '')
                            
                        # 處理時間格式
                        if isinstance(pub_time, int):
                            pub_time = datetime.fromtimestamp(pub_time).strftime('%Y-%m-%d %H:%M')
                        elif isinstance(pub_time, str) and 'T' in pub_time:
                            try:
                                pub_time = datetime.fromisoformat(pub_time.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M')
                            except:
                                pass
                                
                        all_news.append({
                            "股票代碼": t,
                            "發布時間": pub_time if pub_time else "未知",
                            "新聞標題": title,
                            "發布者": publisher,
                            "摘要": summary if summary else "無摘要，請點擊原文查看。",
                            "原文鏈接": link
                        })
            except Exception as e:
                continue
        return all_news

    news_list = get_stock_news(tickers)
    
    if news_list:
        # 按時間排序 (盡量)
        df_news = pd.DataFrame(news_list)
        
        # 使用卡片式佈局展示新聞
        for index, row in df_news.iterrows():
            with st.container():
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"### 🏷️ [{row['股票代碼']}] {row['新聞標題']}")
                    st.caption(f"🏢 來源: {row['發布者']} | 🕒 時間: {row['發布時間']}")
                    # 限制摘要長度，避免頁面過長
                    summary_text = row['摘要'][:300] + "..." if len(row['摘要']) > 300 else row['摘要']
                    st.markdown(f"*{summary_text}*")
                with col2:
                    st.markdown(f"<br><br>", unsafe_allow_html=True)
                    st.markdown(f"[🔗 **閱讀全文**]({row['原文鏈接']})", unsafe_allow_html=True)
                st.divider()
    else:
        st.info("暫無相關新聞，或 API 獲取受限。請稍後刷新。")
        
    st.markdown("---")
    st.markdown("### 💡 新聞 × 技術面 實戰思考指南")
    st.warning("""
    **如何判斷新聞是「黃金坑」還是「價值陷阱」？**
    1. **利空新聞 + 宏觀緊縮 + RSI 跌破 30**：極大概率是價值陷阱，**嚴格執行紀律，最多輕倉試探，絕不重倉抄底**。
    2. **利空新聞 + 宏觀寬鬆 + 股價打在 FIB 61.8% 支撐位**：這通常是市場情緒錯殺（黃金牛市中的回調），是**絕佳的買入/買 Call 時機**。
    3. **利好新聞 + 宏觀緊縮 + RSI > 70**：警惕「利好出盡是利空」，主力可能藉機出貨，**考慮賣出 Covered Call 鎖定利潤**。
    """)
