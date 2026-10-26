import os
import time
import json
import threading
from collections import deque
import requests
import streamlit as st
import pandas as pd

# Page Configuration
st.set_page_config(
    page_title="Pre-Checkout Return Risk Analyzer",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

BACKEND_STREAM_URL = os.getenv("BACKEND_STREAM_URL", "http://backend:8000/stream")
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://backend:8000")

# Custom Command-Center CSS
st.markdown("""
<style>
    /* Global Reset & Command Center Aesthetic */
    .stApp {
        background-color: #0E1117 !important;
        color: #FAFAFA !important;
        font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
    
    /* Terminal Monospace Container */
    .terminal-container {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 4px;
        padding: 14px;
        margin-top: 10px;
        max-height: 580px;
        overflow-y: auto;
        font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', Courier, monospace;
    }
    
    .terminal-header {
        font-size: 0.82rem;
        color: #8B949E;
        border-bottom: 1px solid #21262D;
        padding-bottom: 8px;
        margin-bottom: 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        letter-spacing: 0.5px;
    }
    
    /* Alert Card in Monospace */
    .alert-card {
        background-color: #0D1117;
        border-left: 4px solid #FF4B4B;
        border-top: 1px solid #21262D;
        border-right: 1px solid #21262D;
        border-bottom: 1px solid #21262D;
        border-radius: 2px;
        padding: 10px 14px;
        margin-bottom: 8px;
        font-size: 0.85rem;
        transition: transform 0.1s ease;
    }
    
    .alert-card:hover {
        background-color: #1F161A;
        border-left: 4px solid #FF6B6B;
    }
    
    .alert-badge {
        background-color: #FF4B4B;
        color: #FFFFFF;
        font-weight: 700;
        font-size: 0.75rem;
        padding: 2px 7px;
        border-radius: 2px;
        letter-spacing: 0.5px;
    }
    
    .bracket-badge {
        background-color: #F85149;
        color: #FFFFFF;
        font-size: 0.72rem;
        font-weight: 600;
        padding: 2px 6px;
        border-radius: 2px;
        margin-left: 6px;
    }
    
    .alert-time {
        color: #8B949E;
        font-weight: 500;
    }
    
    .alert-tx {
        color: #58A6FF;
        font-weight: 600;
    }
    
    /* Metric Cards */
    .metric-card {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 4px;
        padding: 16px 20px;
        text-align: left;
    }
    
    .metric-title {
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 1px;
        text-transform: uppercase;
        color: #8B949E;
        margin-bottom: 6px;
    }
    
    .metric-value {
        font-size: 2.1rem;
        font-weight: 700;
        font-family: 'JetBrains Mono', 'Fira Code', monospace;
        line-height: 1.1;
    }
    
    .metric-val-green {
        color: #3FB950;
    }
    
    .metric-val-red {
        color: #FF4B4B;
    }
    
    .metric-val-blue {
        color: #58A6FF;
    }
    
    .metric-val-yellow {
        color: #D29922;
    }
    
    /* Status Bar */
    .status-badge-online {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background-color: #12261E;
        color: #3FB950;
        border: 1px solid #238636;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    
    .status-badge-offline {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background-color: #301818;
        color: #FF4B4B;
        border: 1px solid #DA3633;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    
    .pulse-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: #3FB950;
        box-shadow: 0 0 6px #3FB950;
    }
    
    .pulse-dot-red {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: #FF4B4B;
        box-shadow: 0 0 6px #FF4B4B;
    }
</style>
""", unsafe_allow_html=True)

# Shared in-memory data store across reruns
@st.cache_resource
def get_stream_buffer():
    class StreamBuffer:
        def __init__(self):
            self.lock = threading.Lock()
            self.events_per_sec = 0.0
            self.total_processed = 0
            self.total_flagged = 0
            self.flag_rate_pct = 0.0
            self.recent_alerts = deque(maxlen=50)
            self.connection_status = "CONNECTING"
            self.last_update_ts = time.time()
            self.worker_thread = None

        def update_metrics(self, data: dict):
            with self.lock:
                self.events_per_sec = float(data.get("events_per_sec", 0.0))
                self.total_processed = int(data.get("total_processed", 0))
                self.total_flagged = int(data.get("total_flagged", 0))
                self.flag_rate_pct = float(data.get("flag_rate_pct", 0.0))
                self.connection_status = "CONNECTED"
                self.last_update_ts = time.time()

        def add_alert(self, alert: dict):
            with self.lock:
                self.recent_alerts.appendleft(alert)
                self.connection_status = "CONNECTED"
                self.last_update_ts = time.time()

        def set_status(self, status: str):
            with self.lock:
                self.connection_status = status

    return StreamBuffer()

buffer = get_stream_buffer()

def sse_listener_worker(stream_url: str):
    """Background listener that maintains persistent connection to FastAPI SSE."""
    headers = {"Accept": "text/event-stream"}
    
    while True:
        try:
            buffer.set_status("CONNECTING")
            with requests.get(stream_url, headers=headers, stream=True, timeout=10) as resp:
                if resp.status_code != 200:
                    buffer.set_status("RETRYING")
                    time.sleep(2)
                    continue
                
                buffer.set_status("CONNECTED")
                event_type = "message"
                
                for line in resp.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    if line.startswith("event:"):
                        event_type = line[len("event:"):].strip()
                    elif line.startswith("data:"):
                        data_str = line[len("data:"):].strip()
                        try:
                            data = json.loads(data_str)
                            if event_type == "alert":
                                buffer.add_alert(data)
                            elif event_type in ("metrics", "sync"):
                                buffer.update_metrics(data)
                                # If sync has initial alerts
                                if "recent_alerts" in data:
                                    for a in reversed(data["recent_alerts"]):
                                        buffer.add_alert(a)
                            elif event_type == "ping":
                                with buffer.lock:
                                    buffer.connection_status = "CONNECTED"
                        except json.JSONDecodeError:
                            pass
        except Exception:
            buffer.set_status("DISCONNECTED - RETRYING...")
            time.sleep(2)

# Start background listener once
if buffer.worker_thread is None or not buffer.worker_thread.is_alive():
    buffer.worker_thread = threading.Thread(
        target=sse_listener_worker,
        args=(BACKEND_STREAM_URL,),
        daemon=True,
        name="SSEClientThread"
    )
    buffer.worker_thread.start()

# Header Layout
col_title, col_status = st.columns([4, 1])
with col_title:
    st.markdown("### 🛡️ Live Pre-Checkout Risk Monitoring")
    st.caption("Real-Time ML Streaming Pipeline • LightGBM Bracket Buying Detection (Inference Threshold $\ge 0.80$)")

# Render metrics and feed inside an auto-refreshing fragment
@st.fragment(run_every="0.5s")
def render_dashboard():
    with buffer.lock:
        status = buffer.connection_status
        eps = buffer.events_per_sec
        total_p = buffer.total_processed
        total_f = buffer.total_flagged
        rate = buffer.flag_rate_pct
        alerts = list(buffer.recent_alerts)
        last_updated = buffer.last_update_ts

    # Check connection staleness (if no data in 4 seconds)
    if time.time() - last_updated > 4.0 and status == "CONNECTED":
        status = "CONNECTING (WAITING FOR DATA)"

    # Status Pill
    if status == "CONNECTED":
        status_html = '<div class="status-badge-online"><div class="pulse-dot"></div>STREAMING ACTIVE</div>'
    else:
        status_html = f'<div class="status-badge-offline"><div class="pulse-dot-red"></div>{status}</div>'
    
    with col_status:
        st.markdown(f"<div style='text-align: right; padding-top: 8px;'>{status_html}</div>", unsafe_allow_html=True)

    # 4 Key Metric Cards
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Throughput</div>
            <div class="metric-value metric-val-green">{eps:.1f} <span style="font-size: 0.9rem; color: #8B949E;">evt/s</span></div>
        </div>
        """, unsafe_allow_html=True)
    with m2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Total Processed</div>
            <div class="metric-value metric-val-blue">{total_p:,}</div>
        </div>
        """, unsafe_allow_html=True)
    with m3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Flagged High-Risk (≥80%)</div>
            <div class="metric-value metric-val-red">{total_f:,}</div>
        </div>
        """, unsafe_allow_html=True)
    with m4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Return Flag Rate</div>
            <div class="metric-value metric-val-yellow">{rate:.2f}%</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # Terminal Feed Container
    feed_header = f"""
    <div class="terminal-header">
        <span>⚡ LIVE KAFKA EVENT STREAM &bull; AUTONOMOUS RISK INTERCEPTION</span>
        <span>SHOWING LAST {len(alerts)} HIGH-RISK DETECTIONS</span>
    </div>
    """
    
    if not alerts:
        if status == "CONNECTED":
            alert_items = "<div style='color: #8B949E; text-align: center; padding: 40px;'>Waiting for live Kafka stream...</div>"
        else:
            alert_items = "<div style='color: #FF4B4B; text-align: center; padding: 40px;'>Connection to stream lost. Retrying...</div>"
    else:
        cards_html = []
        for a in alerts:
            tx = a.get("transaction_id", "N/A")
            risk = float(a.get("risk_score", 0.0)) * 100.0
            cat = a.get("category", "General")
            price = a.get("price", 0.0)
            cart_val = a.get("cart_total_value", 0.0)
            items = a.get("total_items_in_cart", 1)
            duplicates = a.get("duplicate_variant_count", 0)
            ts = a.get("timestamp", "--:--:--")
            
            bracket_badge = ""
            if duplicates > 1:
                bracket_badge = f'<span class="bracket-badge">⚠️ BRACKET BUY ({duplicates} VARIANTS)</span>'
                
            card = f"""
            <div class="alert-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                    <div>
                        <span class="alert-time">[{ts}]</span> &nbsp;
                        <span class="alert-badge">RISK: {risk:.1f}%</span>
                        {bracket_badge}
                    </div>
                    <div>
                        <span class="alert-tx">TX: {tx}</span>
                    </div>
                </div>
                <div style="color: #C9D1D9; font-size: 0.82rem; margin-top: 4px;">
                    Category: <b>{cat}</b> &nbsp;|&nbsp; 
                    Unit Price: <b>${price:.2f}</b> &nbsp;|&nbsp; 
                    Cart Value: <b>${cart_val:.2f}</b> &nbsp;|&nbsp; 
                    Items in Cart: <b>{items}</b> &nbsp;|&nbsp; 
                    Duplicate Variants: <b>{duplicates}</b>
                </div>
            </div>
            """
            cards_html.append(card)
        alert_items = "".join(cards_html)

    st.markdown(f"""
    <div class="terminal-container">
        {feed_header}
        {alert_items}
    </div>
    """, unsafe_allow_html=True)

# Execute the rendering fragment
render_dashboard()
