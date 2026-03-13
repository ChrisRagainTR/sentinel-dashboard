"""Sentinel Wealth & Tax — Research Dashboard"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf
import json, os, datetime, requests
from pathlib import Path

st.set_page_config(
    page_title="Sentinel Research Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Styling ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
    .metric-card { background: white; border-radius: 8px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin: 4px; }
    .alert-red { color: #cc0000; font-weight: bold; }
    .alert-green { color: #007700; font-weight: bold; }
    h1 { color: #1a1a2e; }
    .stTabs [data-baseweb="tab"] { font-size: 15px; }
</style>
""", unsafe_allow_html=True)

WORKSPACE = Path(r"C:\Users\craga\.openclaw\workspace")
GITHUB_RAW = "https://raw.githubusercontent.com/ChrisRagainTR/sentinel-dashboard/master/data"

PORTFOLIOS = {
    "Power":  ["CIEN","DY","GM","NEM","KGC","CDE","EAT","AMD","INCY","CLS","MU","ALL",
               "SKYW","PPC","ATI","CCL","UNFI","MFC","WLDN","TTMI","COHR","STRL","BRK-B",
               "TMUS","FN","VISN","PARR","SYF","W","BLBD","UBER","OKTA","TWLO","SSRM",
               "TIGO","ARQT","APP","CRDO"],
    "Core":   ["SO","LNG","CIEN","AMD","INCY","CRM","MU","ATI","SLM","BRK-B","PLD","VRDN"],
    "Income": ["OKE","VZ","NMR","BMY","PFE","ABEV","MO","CNQ","MFC","EXR","ABR","AXIA",
               "STWD","OMF","PINE","NLCP","BST"],
}
ALL_HOLDINGS = sorted(set(t for h in PORTFOLIOS.values() for t in h))

@st.cache_data(ttl=300)
def load_ratings():
    try:
        return pd.read_csv(f"{GITHUB_RAW}/weekly_ratings.csv")
    except:
        local = WORKSPACE / "weekly_ratings.csv"
        return pd.read_csv(local) if local.exists() else pd.DataFrame()

@st.cache_data(ttl=300)
def load_comparisons():
    try:
        return pd.read_csv(f"{GITHUB_RAW}/portfolio_comparison.csv")
    except:
        local = WORKSPACE / "portfolio_comparison.csv"
        return pd.read_csv(local) if local.exists() else pd.DataFrame()

@st.cache_data(ttl=300)
def load_deep_research():
    results = []
    for fname in ["deep_research.json", "deep_research_expanded.json"]:
        try:
            r = requests.get(f"{GITHUB_RAW}/{fname}", timeout=15)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list):
                    results.extend(data)
                continue
        except:
            pass
        local = WORKSPACE / fname
        if local.exists():
            with open(local) as f:
                data = json.load(f)
                if isinstance(data, list):
                    results.extend(data)
    return results

@st.cache_data(ttl=60)
def fetch_prices(tickers):
    try:
        data = yf.download(tickers, period="2d", interval="1d",
                           progress=False, auto_adjust=True)
        closes = data["Close"]
        result = {}
        for t in tickers:
            try:
                vals = closes[t].dropna() if isinstance(closes, pd.DataFrame) else closes.dropna()
                if len(vals) >= 2:
                    prev, curr = float(vals.iloc[-2]), float(vals.iloc[-1])
                    pct = (curr - prev) / prev * 100
                    result[t] = {"price": curr, "prev": prev, "pct": round(pct, 2)}
                elif len(vals) == 1:
                    result[t] = {"price": float(vals.iloc[-1]), "prev": None, "pct": None}
            except:
                pass
        return result
    except:
        return {}

@st.cache_data(ttl=300)
def fetch_news(tickers):
    news = {}
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            items = tk.news or []
            headlines = [n.get("title", "") for n in items[:4] if n.get("title")]
            if headlines:
                news[t] = headlines
        except:
            pass
    return news

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.image("https://i.imgur.com/placeholder.png", width=40) if False else None
st.sidebar.title("📊 Sentinel Wealth")
st.sidebar.caption("Research Dashboard")
st.sidebar.markdown("---")
selected_portfolio = st.sidebar.selectbox("Portfolio Filter", ["All", "Power", "Core", "Income"])
move_threshold = st.sidebar.slider("Alert Threshold (%)", 1.0, 10.0, 3.0, 0.5)
st.sidebar.markdown("---")
st.sidebar.caption(f"Updated: {datetime.datetime.now().strftime('%b %d, %Y %I:%M %p ET')}")

# ── Main Tabs ─────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🔔 Market Alerts", "📈 Portfolio", "⭐ Stock Ratings", "🔄 Matchups", "🔍 Research"
])

# ═══════════════════════════════════════════════════════════
# TAB 1 — MARKET ALERTS (live)
# ═══════════════════════════════════════════════════════════
with tab1:
    st.header("Live Market Alerts — Sentinel Holdings")
    st.caption("Prices refresh every 5 minutes · Pre/post market shown when available")

    holdings = ALL_HOLDINGS
    if selected_portfolio != "All":
        holdings = PORTFOLIOS[selected_portfolio]

    with st.spinner("Fetching live prices..."):
        prices = fetch_prices(holdings)

    if prices:
        rows = []
        for t in holdings:
            d = prices.get(t, {})
            portfolios = [p for p, h in PORTFOLIOS.items() if t in h]
            rows.append({
                "Ticker": t,
                "Portfolio": " / ".join(portfolios),
                "Price": d.get("price"),
                "Prev Close": d.get("prev"),
                "Day Change %": d.get("pct"),
                "Alert": "🔴" if (d.get("pct") or 0) <= -move_threshold
                         else "🟢" if (d.get("pct") or 0) >= move_threshold
                         else "—"
            })

        df = pd.DataFrame(rows)
        df_sorted = df.sort_values("Day Change %", key=lambda x: x.abs(), ascending=False, na_position="last")

        # Big movers section
        big_movers = df_sorted[df_sorted["Day Change %"].abs() >= move_threshold]
        if not big_movers.empty:
            st.subheader(f"⚠️ Big Movers (>{move_threshold}%)")
            st.dataframe(
                big_movers.style.format({"Price": "${:.2f}", "Prev Close": "${:.2f}", "Day Change %": "{:+.2f}%"})
                .applymap(lambda v: "color: red" if isinstance(v, float) and v < -move_threshold
                          else ("color: green" if isinstance(v, float) and v > move_threshold else ""),
                          subset=["Day Change %"]),
                use_container_width=True, hide_index=True
            )
        else:
            st.success(f"✅ No holdings moving more than {move_threshold}% today.")

        st.subheader("All Holdings")
        st.dataframe(
            df_sorted.style.format({"Price": "${:.2f}", "Prev Close": "${:.2f}", "Day Change %": "{:+.2f}%"},
                                   na_rep="—"),
            use_container_width=True, hide_index=True
        )

        # News
        st.subheader("📰 Latest News on Holdings")
        with st.spinner("Loading news..."):
            news = fetch_news(holdings[:30])
        if news:
            for ticker, headlines in list(news.items())[:20]:
                with st.expander(f"**{ticker}** — {headlines[0][:80]}..."):
                    for h in headlines:
                        st.write(f"• {h}")
    else:
        st.warning("Could not fetch live price data.")

# ═══════════════════════════════════════════════════════════
# TAB 2 — PORTFOLIO OVERVIEW
# ═══════════════════════════════════════════════════════════
with tab2:
    st.header("Portfolio Holdings Overview")

    ratings_df = load_ratings()

    for port_name, holdings in PORTFOLIOS.items():
        if selected_portfolio != "All" and selected_portfolio != port_name:
            continue
        st.subheader(f"{'🚀' if port_name=='Power' else '🏛️' if port_name=='Core' else '💰'} {port_name} Model")

        if not ratings_df.empty:
            port_df = ratings_df[ratings_df["ticker"].isin(holdings)].copy() if "ticker" in ratings_df.columns else pd.DataFrame()
            if not port_df.empty:
                cols = [c for c in ["ticker","name","sector","quant_rating","quant_score","val_grade","growth_grade",
                                    "profit_grade","mom_grade","rev_grade","div_yield","upside","price","pe_fwd","rev_growth"] if c in port_df.columns]
                st.dataframe(port_df[cols].sort_values("quant_score", ascending=False) if "quant_score" in port_df.columns else port_df[cols],
                             use_container_width=True, hide_index=True)
            else:
                st.info(f"Holdings: {', '.join(holdings)}")
        else:
            st.info(f"Holdings: {', '.join(holdings)}")
        st.markdown("---")

# ═══════════════════════════════════════════════════════════
# TAB 3 — STOCK RATINGS (full universe)
# ═══════════════════════════════════════════════════════════
with tab3:
    st.header("Stock Ratings — Full Universe (1,600+ stocks)")

    ratings_df = load_ratings()
    if ratings_df.empty:
        st.warning("Ratings data not loaded. Run the weekly pipeline first.")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            sector_filter = st.selectbox("Sector", ["All"] + sorted(ratings_df["sector"].dropna().unique().tolist()) if "sector" in ratings_df.columns else ["All"])
        with col2:
            rating_filter = st.selectbox("Rating", ["All", "Buy", "Hold", "Sell"]) if "quant_rating" in ratings_df.columns else st.selectbox("Rating", ["All"])
        with col3:
            search = st.text_input("Search ticker / name")

        filtered = ratings_df.copy()
        if sector_filter != "All" and "sector" in filtered.columns:
            filtered = filtered[filtered["sector"] == sector_filter]
        if rating_filter != "All" and "quant_rating" in filtered.columns:
            filtered = filtered[filtered["quant_rating"] == rating_filter]
        if search:
            mask = filtered.apply(lambda r: search.upper() in str(r.get("ticker","")).upper()
                                  or search.lower() in str(r.get("name","")).lower(), axis=1)
            filtered = filtered[mask]

        if "quant_score" in filtered.columns:
            filtered = filtered.sort_values("quant_score", ascending=False)

        cols = [c for c in ["ticker","name","sector","quant_rating","quant_score","val_grade","growth_grade",
                             "profit_grade","mom_grade","rev_grade","div_yield","upside"] if c in filtered.columns]
        st.caption(f"Showing {len(filtered):,} of {len(ratings_df):,} stocks")
        st.dataframe(filtered[cols], use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════════════════
# TAB 4 — REPLACEMENT MATCHUPS
# ═══════════════════════════════════════════════════════════
with tab4:
    st.header("Replacement Matchups")
    st.caption("Top alternatives for each holding by quant score delta")

    comp_df = load_comparisons()
    if comp_df.empty:
        st.warning("Comparison data not found.")
    else:
        port_filter = st.selectbox("Portfolio", ["All", "Power", "Core", "Income"], key="matchup_port")
        # Handle both capitalized and lowercase column name
        port_col = "Portfolio" if "Portfolio" in comp_df.columns else "portfolio" if "portfolio" in comp_df.columns else None
        if port_filter != "All" and port_col:
            comp_df = comp_df[comp_df[port_col] == port_filter]

        cols = [c for c in comp_df.columns if c not in ("Unnamed: 0",)]
        st.dataframe(comp_df[cols], use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════════════════
# TAB 5 — DEEP RESEARCH
# ═══════════════════════════════════════════════════════════
with tab5:
    st.header("Deep Research")
    st.caption("Fundamental analysis — SEC filings, earnings calls, key risks")

    research = load_deep_research()
    if not research:
        st.warning("Research data not found.")
    else:
        search_r = st.text_input("Search ticker or company", key="research_search")
        verdict_filter = st.selectbox("Verdict", ["All", "BUY", "HOLD", "WATCH", "AVOID"])

        filtered_r = research
        if search_r:
            filtered_r = [r for r in filtered_r if
                          search_r.upper() in str(r.get("ticker","")).upper() or
                          search_r.lower() in str(r.get("name","")).lower()]
        if verdict_filter != "All":
            filtered_r = [r for r in filtered_r if str(r.get("verdict","")).startswith(verdict_filter)]

        st.caption(f"{len(filtered_r)} records")

        for rec in filtered_r[:50]:
            ticker = rec.get("ticker","?")
            name   = rec.get("name", "")
            verdict = rec.get("verdict","")
            thesis  = rec.get("thesis","")
            color   = "🟢" if "BUY" in str(verdict) else "🔴" if "AVOID" in str(verdict) else "🟡"
            with st.expander(f"{color} **{ticker}** — {name} | {verdict}"):
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**Thesis:** {thesis}")
                    st.write(f"**Revenue:** {rec.get('revenue_trend','—')}")
                    st.write(f"**EPS:** Actual {rec.get('latest_eps_actual','—')} vs Est {rec.get('latest_eps_estimate','—')} → {rec.get('beat_miss','—')}")
                    st.write(f"**Guidance:** {rec.get('guidance','—')}")
                with c2:
                    st.write(f"**Sector:** {rec.get('sector','—')}")
                    st.write(f"**Div Yield:** {rec.get('div_yield','—')}")
                    st.write(f"**D/E Ratio:** {rec.get('debt_equity_ratio','—')}")
                    st.write(f"**Cash:** {rec.get('cash_position','—')}")
                risks = rec.get("key_risks", [])
                if risks:
                    st.write("**Key Risks:** " + " · ".join(risks))
                tone = rec.get("earnings_call_tone","")
                if tone:
                    st.write(f"**Earnings Call:** {tone}")
