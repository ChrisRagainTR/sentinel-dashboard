"""Sentinel Wealth & Tax — Research Dashboard"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf
import json, os, datetime, requests
from io import StringIO
from pathlib import Path

st.set_page_config(
    page_title="Sentinel Research Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
    h1, h2, h3 { color: #1a1a2e; }

    /* Light sidebar */
    section[data-testid="stSidebar"] {
        background-color: #ffffff !important;
    }

    /* Nav buttons — full-width, left-aligned, no border */
    section[data-testid="stSidebar"] .stButton > button {
        width: 100% !important;
        text-align: left !important;
        background-color: transparent !important;
        color: #333333 !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 11px 18px !important;
        font-size: 15px !important;
        font-weight: 500 !important;
        margin-bottom: 3px !important;
        transition: background 0.15s, color 0.15s;
        box-shadow: none !important;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background-color: #f0eaf4 !important;
        color: #3d1152 !important;
    }
</style>
""", unsafe_allow_html=True)

WORKSPACE   = Path(r"C:\Users\craga\.openclaw\workspace")
GITHUB_RAW  = "https://raw.githubusercontent.com/ChrisRagainTR/sentinel-dashboard/master/data"

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

def fetch_from_github(filename):
    try:
        r = requests.get(f"{GITHUB_RAW}/{filename}", timeout=20)
        r.raise_for_status()
        return r.text
    except:
        return None

@st.cache_data(ttl=300)
def load_ratings():
    text = fetch_from_github("weekly_ratings.csv")
    if text:
        return pd.read_csv(StringIO(text))
    local = WORKSPACE / "weekly_ratings.csv"
    return pd.read_csv(local) if local.exists() else pd.DataFrame()

@st.cache_data(ttl=300)
def load_comparisons():
    text = fetch_from_github("portfolio_comparison.csv")
    if text:
        return pd.read_csv(StringIO(text))
    local = WORKSPACE / "portfolio_comparison.csv"
    return pd.read_csv(local) if local.exists() else pd.DataFrame()

@st.cache_data(ttl=300)
def load_deep_research():
    results = []
    for fname in ["deep_research.json", "deep_research_expanded.json"]:
        text = fetch_from_github(fname)
        if text:
            try:
                data = json.loads(text)
                if isinstance(data, list):
                    results.extend(data)
                continue
            except:
                pass
        local = WORKSPACE / fname
        if local.exists():
            with open(local) as f:
                try:
                    data = json.load(f)
                    if isinstance(data, list):
                        results.extend(data)
                except:
                    pass
    return results

@st.cache_data(ttl=60)
def fetch_prices(tickers):
    try:
        data = yf.download(list(tickers), period="2d", interval="1d",
                           progress=False, auto_adjust=True)
        closes = data["Close"]
        result = {}
        for t in tickers:
            try:
                col = closes[t] if isinstance(closes, pd.DataFrame) else closes
                vals = col.dropna()
                if len(vals) >= 2:
                    prev, curr = float(vals.iloc[-2]), float(vals.iloc[-1])
                    result[t] = {"price": curr, "prev": prev, "pct": round((curr-prev)/prev*100, 2)}
                elif len(vals) == 1:
                    result[t] = {"price": float(vals.iloc[-1]), "prev": None, "pct": None}
            except:
                pass
        return result
    except:
        return {}

@st.cache_data(ttl=600)
def fetch_performance(tickers):
    """Fetch today / weekly / MTD / YTD performance for a list of tickers."""
    import datetime as dt
    result = {}
    try:
        data = yf.download(list(tickers), period="ytd", interval="1d",
                           progress=False, auto_adjust=True)
        closes = data["Close"] if "Close" in data else data

        today       = dt.date.today()
        month_start = today.replace(day=1)
        year_start  = today.replace(month=1, day=1)
        week_ago    = today - dt.timedelta(days=7)

        for t in tickers:
            try:
                col = closes[t] if isinstance(closes, pd.DataFrame) else closes
                col = col.dropna()
                if col.empty:
                    continue

                # Convert index to plain date objects — avoids all tz issues
                dates = [d.date() if hasattr(d, "date") else d for d in col.index]
                values = col.values
                curr = float(values[-1])

                def pct_since(target_date):
                    candidates = [(i, d) for i, d in enumerate(dates) if d <= target_date]
                    if not candidates:
                        return None
                    idx = candidates[-1][0]
                    base = float(values[idx])
                    return round((curr - base) / base * 100, 2) if base else None

                today_pct = None
                if len(values) >= 2:
                    prev = float(values[-2])
                    today_pct = round((curr - prev) / prev * 100, 2) if prev else None

                result[t] = {
                    "price":     curr,
                    "today_pct": today_pct,
                    "week_pct":  pct_since(week_ago),
                    "mtd_pct":   pct_since(month_start),
                    "ytd_pct":   pct_since(year_start),
                }
            except:
                pass
    except:
        pass
    return result

def fmt_pct(val):
    if val is None: return "—"
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.2f}%"

@st.cache_data(ttl=600)
def fetch_news_for_holdings(tickers_tuple):
    """Fetch news via Yahoo Finance RSS — reliable from cloud."""
    import xml.etree.ElementTree as ET
    news_out = {}
    headers = {"User-Agent": "Mozilla/5.0"}
    for t in tickers_tuple:
        try:
            url = f"https://finance.yahoo.com/rss/headline?s={t}"
            r = requests.get(url, headers=headers, timeout=8)
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.content)
            items = root.findall(".//item")
            headlines = []
            for item in items[:5]:
                title = item.findtext("title", "")
                link  = item.findtext("link", "")
                pub   = item.findtext("pubDate", "")
                if title:
                    try:
                        dt = datetime.datetime.strptime(pub, "%a, %d %b %Y %H:%M:%S %z")
                        date_str = dt.strftime("%b %d")
                    except:
                        date_str = pub[:12] if pub else ""
                    headlines.append({"title": title, "link": link, "date": date_str})
            if headlines:
                news_out[t] = headlines
        except:
            pass
    return news_out

def grade_to_num(g):
    """Convert letter grade to number for comparison."""
    mapping = {"A+":12,"A":11,"A-":10,"B+":9,"B":8,"B-":7,"C+":6,"C":5,"C-":4,"D+":3,"D":2,"D-":1,"F":0}
    return mapping.get(str(g).strip(), -1)

def build_why(row):
    """Generate a plain-English reason why the alt is better."""
    reasons = []
    grade_pairs = [
        ("Holding Val","Alt Val","Valuation"),
        ("Holding Growth","Alt Growth","Growth"),
        ("Holding Profit","Alt Profit","Profitability"),
        ("Holding Mom","Alt Mom","Momentum"),
        ("Holding Rev","Alt Rev","EPS Revisions"),
    ]
    for hcol, acol, label in grade_pairs:
        h = grade_to_num(row.get(hcol,""))
        a = grade_to_num(row.get(acol,""))
        if a > h and a >= 0:
            reasons.append(label)
    score_diff = row.get("Score Diff", 0)
    if isinstance(score_diff, (int, float)) and score_diff > 0:
        prefix = f"+{score_diff:.2f} score"
    else:
        prefix = ""
    if reasons:
        return f"{prefix} — stronger {', '.join(reasons[:3])}"
    return prefix or "Higher composite score"

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.image(
    "https://raw.githubusercontent.com/ChrisRagainTR/sentinel-dashboard/master/sentinel_logo_cropped.png",
    use_container_width=True
)
st.sidebar.markdown("---")

NAV_ITEMS = [
    ("🔔", "Market Alerts"),
    ("📈", "Portfolio"),
    ("⭐", "Stock Ratings"),
    ("🔄", "Matchups"),
    ("🔍", "Research"),
]

if "page" not in st.session_state:
    st.session_state.page = "Market Alerts"

for icon, label in NAV_ITEMS:
    active = st.session_state.page == label
    # Inject active class via markdown wrapper
    if active:
        st.sidebar.markdown(
            f'<div style="background:#3d1152;border-radius:8px;margin-bottom:3px;">'
            f'<span style="display:block;padding:11px 18px;color:#ffffff;font-size:15px;font-weight:700;">'
            f'{icon}&nbsp;&nbsp;{label}</span></div>',
            unsafe_allow_html=True
        )
    else:
        if st.sidebar.button(f"{icon}  {label}", key=f"nav_{label}"):
            st.session_state.page = label
            st.rerun()

page = st.session_state.page
st.sidebar.markdown("---")
port_filter_global = st.sidebar.selectbox("Portfolio Filter", ["All","Power","Core","Income"])
move_threshold = st.sidebar.slider("Alert Threshold (%)", 1.0, 10.0, 3.0, 0.5)
st.sidebar.markdown("---")
st.sidebar.caption(f"Updated: {datetime.datetime.now().strftime('%b %d %I:%M %p ET')}")

# ═══════════════════════════════════════════════════════════════════════════
if page == "🔔 Market Alerts":
    st.header("Live Market Alerts — Sentinel Holdings")
    st.caption("Prices refresh every minute · Holdings across all three portfolios")

    holdings = ALL_HOLDINGS if port_filter_global == "All" else PORTFOLIOS[port_filter_global]

    with st.spinner("Fetching live prices..."):
        prices = fetch_prices(tuple(holdings))

    if prices:
        rows = []
        for t in holdings:
            d = prices.get(t, {})
            pct = d.get("pct")
            port_list = [p for p, h in PORTFOLIOS.items() if t in h]
            flag = "🔴" if (pct or 0) <= -move_threshold else "🟢" if (pct or 0) >= move_threshold else ""
            rows.append({
                "": flag,
                "Ticker": t,
                "Portfolio": " / ".join(port_list),
                "Price": f"${d['price']:.2f}" if d.get("price") else "—",
                "Day Change": f"{'+' if (pct or 0) > 0 else ''}{pct:.2f}%" if pct is not None else "—",
                "_pct": pct or 0
            })

        df = pd.DataFrame(rows).sort_values("_pct", key=abs, ascending=False).drop(columns=["_pct"])

        big = df[df[""].isin(["🔴","🟢"])]
        if not big.empty:
            st.subheader(f"⚠️ Big Movers Today (>{move_threshold}%)")
            st.dataframe(big, use_container_width=True, hide_index=True)

        st.subheader("All Holdings")
        st.dataframe(df, use_container_width=True, hide_index=True)

        # ── News ──────────────────────────────────────────────────────────────
        st.subheader("📰 Latest News")
        with st.spinner("Loading news headlines..."):
            news = fetch_news_for_holdings(tuple(holdings))

        if news:
            # Prioritize big movers
            priority = [r["Ticker"] for _, r in df.iterrows() if r[""] in ("🔴","🟢")]
            other    = [t for t in holdings if t not in priority]
            ordered  = priority + other
            shown = 0
            for t in ordered:
                if t not in news or shown >= 25:
                    break
                port_list = [p for p, h in PORTFOLIOS.items() if t in h]
                with st.expander(f"**{t}** ({', '.join(port_list)}) — {news[t][0]['title'][:80]}"):
                    for item in news[t]:
                        link = item.get("link","")
                        date = item.get("date","")
                        title = item.get("title","")
                        if link:
                            st.markdown(f"• [{title}]({link}) *{date}*")
                        else:
                            st.write(f"• {title} *{date}*")
                shown += 1
        else:
            st.info("News headlines unavailable right now — try refreshing in a moment.")
    else:
        st.warning("Could not fetch live price data. Markets may be closed.")

elif page == "📈 Portfolio":
    st.header("Portfolio Holdings")
    ratings_df = load_ratings()

    for pname, holdings in PORTFOLIOS.items():
        if port_filter_global != "All" and port_filter_global != pname:
            continue
        icon = "🚀" if pname=="Power" else "🏛️" if pname=="Core" else "💰"
        st.subheader(f"{icon} {pname} Model — {len(holdings)} holdings")

        with st.spinner(f"Loading {pname} performance..."):
            perf = fetch_performance(tuple(holdings))

        if not ratings_df.empty and "ticker" in ratings_df.columns:
            pdf = ratings_df[ratings_df["ticker"].isin(holdings)].copy()
        else:
            pdf = pd.DataFrame({"ticker": holdings})

        # Merge performance data
        perf_rows = []
        for t in holdings:
            p = perf.get(t, {})
            perf_rows.append({
                "ticker":    t,
                "Price":     f"${p['price']:.2f}" if p.get("price") else "—",
                "Today":     fmt_pct(p.get("today_pct")),
                "Week":      fmt_pct(p.get("week_pct")),
                "MTD":       fmt_pct(p.get("mtd_pct")),
                "YTD":       fmt_pct(p.get("ytd_pct")),
            })
        perf_df = pd.DataFrame(perf_rows)

        if not pdf.empty and "ticker" in pdf.columns:
            merged = perf_df.merge(
                pdf[["ticker"] + [c for c in ["name","sector","quant_score","quant_rating",
                     "val_grade","growth_grade","profit_grade","mom_grade","rev_grade","div_yield"] if c in pdf.columns]],
                on="ticker", how="left"
            )
        else:
            merged = perf_df

        # Rename for display
        merged = merged.rename(columns={
            "ticker": "Ticker", "name": "Name", "sector": "Sector",
            "quant_score": "Score", "quant_rating": "Rating",
            "val_grade": "Val", "growth_grade": "Growth",
            "profit_grade": "Profit", "mom_grade": "Mom",
            "rev_grade": "Rev", "div_yield": "Div Yield"
        })

        display_cols = [c for c in ["Ticker","Name","Price","Today","Week","MTD","YTD","Score","Rating",
                                     "Val","Growth","Profit","Mom","Rev","Div Yield","Sector"] if c in merged.columns]
        display_df = merged[display_cols]
        if "Score" in display_df.columns:
            display_df = display_df.sort_values("Score", ascending=False)

        def color_score(val):
            try:
                v = float(val)
                if v >= 4.0:   return "background-color: #1a7a3c; color: white; font-weight: bold"
                elif v >= 3.0: return "background-color: #1565c0; color: white; font-weight: bold"
                elif v >= 2.0: return "background-color: #ffeb9c; color: #7d4a00; font-weight: bold"
                elif v >= 1.0: return "background-color: #ff9800; color: white; font-weight: bold"
                else:          return "background-color: #c62828; color: white; font-weight: bold"
            except:
                return ""

        def color_perf(val):
            try:
                v = float(str(val).replace("%","").replace("+",""))
                if v > 0:  return "color: #1a7a3c; font-weight: bold"
                elif v < 0: return "color: #9c0006; font-weight: bold"
            except:
                pass
            return ""

        styled = display_df.style
        if "Score" in display_df.columns:
            styled = styled.applymap(color_score, subset=["Score"])
        for col in ["Today","Week","MTD","YTD"]:
            if col in display_df.columns:
                styled = styled.applymap(color_perf, subset=[col])

        st.dataframe(styled, use_container_width=True, hide_index=True, height=800)
        st.markdown("---")

elif page == "⭐ Stock Ratings":
    st.header("Stock Ratings — Full Universe")
    ratings_df = load_ratings()

    if ratings_df.empty:
        st.warning("Loading ratings data...")
        st.stop()

    c1, c2, c3 = st.columns(3)
    with c1:
        sectors = ["All"] + sorted(ratings_df["sector"].dropna().unique().tolist()) if "sector" in ratings_df.columns else ["All"]
        sector_f = st.selectbox("Sector", sectors)
    with c2:
        rating_f = st.selectbox("Rating", ["All","Buy","Hold","Sell"])
    with c3:
        search = st.text_input("Search ticker / name")

    filt = ratings_df.copy()
    if sector_f != "All": filt = filt[filt["sector"]==sector_f]
    if rating_f != "All": filt = filt[filt["quant_rating"]==rating_f]
    if search:
        s = search.upper()
        filt = filt[filt.apply(lambda r: s in str(r.get("ticker","")).upper() or
                                          search.lower() in str(r.get("name","")).lower(), axis=1)]
    if "quant_score" in filt.columns:
        filt = filt.sort_values("quant_score", ascending=False)

    show = [c for c in ["ticker","name","sector","quant_rating","quant_score","val_grade",
                         "growth_grade","profit_grade","mom_grade","rev_grade","price",
                         "div_yield","upside"] if c in filt.columns]
    st.caption(f"Showing {len(filt):,} of {len(ratings_df):,} stocks")
    st.dataframe(filt[show], use_container_width=True, hide_index=True, height=1100)

elif page == "🔄 Matchups":
    st.header("Replacement Matchups")
    st.info("💡 Every alternative shown scores **higher** than the current holding. Green = significant upgrade. Color intensity reflects the score gap.")

    comp_df = load_comparisons()
    if comp_df.empty:
        st.warning("Loading matchup data...")
        st.stop()

    # Normalize column names
    comp_df.columns = [c.strip() for c in comp_df.columns]
    port_col = "Portfolio" if "Portfolio" in comp_df.columns else "portfolio"

    pf = st.selectbox("Portfolio", ["All","Power","Core","Income"], key="matchup_p")
    if pf != "All" and port_col in comp_df.columns:
        comp_df = comp_df[comp_df[port_col] == pf]

    # Build "Why" column
    comp_df["Why Better"] = comp_df.apply(build_why, axis=1)

    # Build score diff numeric
    comp_df["_diff"] = pd.to_numeric(comp_df.get("Score Diff", 0), errors="coerce").fillna(0)

    # Select and reorder columns — most important on left
    display_cols = []
    col_map = {
        "Portfolio":        port_col,
        "Holding":          "Current Holding",
        "Hold. Score":      "Holding Score",
        "Hold. Rating":     "Holding Quant",
        "→ Alt Ticker":     "Alt Ticker",
        "Alt Name":         "Alt Name",
        "Alt Score":        "Alt Score",
        "Alt Rating":       "Alt Quant",
        "Score ↑":          "Score Diff",
        "Why Better":       "Why Better",
        "Alt Div Yield":    "Alt Div Yield",
        "Sector":           "Holding Sector",
    }

    out_rows = []
    for _, row in comp_df.iterrows():
        r = {}
        for display, src in col_map.items():
            r[display] = row.get(src, "")
        out_rows.append(r)

    out_df = pd.DataFrame(out_rows)

    # Color the Score ↑ column
    def color_diff(val):
        try:
            v = float(val)
            if v >= 1.0:   return "background-color: #c6efce; color: #276221"
            elif v >= 0.5: return "background-color: #e2efda; color: #375623"
            elif v > 0:    return "background-color: #f2f9ee"
        except:
            pass
        return ""

    st.caption(f"Showing {len(out_df)} matchups")
    st.dataframe(
        out_df.style.applymap(color_diff, subset=["Score ↑"]),
        use_container_width=True,
        hide_index=True,
        height=1100
    )

elif page == "🔍 Research":
    st.header("Deep Research")
    st.caption("Fundamental analysis from SEC filings, earnings calls, and analyst data")

    research = load_deep_research()
    if not research:
        st.warning("Loading research data...")
        st.stop()

    c1, c2 = st.columns(2)
    with c1:
        search_r = st.text_input("Search ticker or company")
    with c2:
        verdict_f = st.selectbox("Verdict", ["All","BUY","HOLD","WATCH","AVOID"])

    filt_r = research
    if search_r:
        filt_r = [r for r in filt_r if search_r.upper() in str(r.get("ticker","")).upper()
                  or search_r.lower() in str(r.get("name","")).lower()]
    if verdict_f != "All":
        filt_r = [r for r in filt_r if str(r.get("verdict","")).upper().startswith(verdict_f)]

    st.caption(f"{len(filt_r)} records")
    for rec in filt_r[:60]:
        ticker  = rec.get("ticker","?")
        name    = rec.get("name","")
        verdict = rec.get("verdict","")
        icon    = "🟢" if "BUY" in str(verdict).upper() else "🔴" if "AVOID" in str(verdict).upper() else "🟡"
        with st.expander(f"{icon} **{ticker}** — {name} | {verdict}"):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Thesis:** {rec.get('thesis','—')}")
                st.write(f"**Revenue:** {rec.get('revenue_trend','—')}")
                st.write(f"**EPS:** {rec.get('latest_eps_actual','—')} actual vs {rec.get('latest_eps_estimate','—')} est → {rec.get('beat_miss','—')}")
                st.write(f"**Guidance:** {rec.get('guidance','—')}")
                st.write(f"**Earnings Tone:** {rec.get('earnings_call_tone','—')}")
            with col2:
                st.write(f"**Sector:** {rec.get('sector','—')}")
                st.write(f"**Div Yield:** {rec.get('div_yield','—')}")
                st.write(f"**D/E:** {rec.get('debt_equity_ratio','—')}")
                st.write(f"**Cash:** {rec.get('cash_position','—')}")
                risks = rec.get("key_risks",[])
                if risks:
                    st.write("**Key Risks:** " + " · ".join(str(r) for r in risks[:3]))
