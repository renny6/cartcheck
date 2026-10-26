import os
import time
import json
import threading
from collections import deque
import requests
import streamlit as st

# Page Configuration
st.set_page_config(
    page_title="Live Cart Inspector",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

BACKEND_STREAM_URL = os.getenv("BACKEND_STREAM_URL", "http://backend:8000/stream")

# Thread-safe persistent stream buffer
@st.cache_resource
def get_stream_buffer():
    class StreamBuffer:
        def __init__(self):
            self.lock = threading.Lock()
            self.events_per_sec = 0.0
            self.total_processed = 0
            self.total_flagged = 0
            self.unconsumed_alerts = deque(maxlen=200)
            self.is_connected = False
            self.worker_thread = None

        def update_metrics(self, data: dict):
            with self.lock:
                self.events_per_sec = float(data.get("events_per_sec", 0.0))
                self.total_processed = int(data.get("total_processed", 0))
                self.total_flagged = int(data.get("total_flagged", 0))
                self.is_connected = True

        def add_alert(self, alert: dict):
            with self.lock:
                self.unconsumed_alerts.append(alert)
                self.is_connected = True

        def pop_all_alerts(self) -> list:
            with self.lock:
                alerts = list(self.unconsumed_alerts)
                self.unconsumed_alerts.clear()
                return alerts

        def get_metrics(self):
            with self.lock:
                return self.events_per_sec, self.total_processed, self.total_flagged, self.is_connected

    return StreamBuffer()

buffer = get_stream_buffer()

def sse_listener_worker(stream_url: str):
    """Persistent background listener maintaining SSE connection without blocking Streamlit."""
    headers = {"Accept": "text/event-stream"}
    while True:
        try:
            with requests.get(stream_url, headers=headers, stream=True, timeout=10) as resp:
                if resp.status_code != 200:
                    time.sleep(2)
                    continue
                
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
                                if "recent_alerts" in data and not buffer.unconsumed_alerts:
                                    for a in data["recent_alerts"]:
                                        buffer.add_alert(a)
                        except json.JSONDecodeError:
                            pass
        except Exception:
            time.sleep(2)

# Start background listener thread once
if buffer.worker_thread is None or not buffer.worker_thread.is_alive():
    buffer.worker_thread = threading.Thread(
        target=sse_listener_worker,
        args=(BACKEND_STREAM_URL,),
        daemon=True,
        name="SSEListenerThread"
    )
    buffer.worker_thread.start()

# Initialize session state for rolling FIFO list of exactly 5 most recent high-risk carts
if "flagged_carts" not in st.session_state:
    st.session_state.flagged_carts = []

# Title & Header
st.title("🛡️ Live Cart Inspector")
st.caption("Real-Time ML Pre-Checkout Return Risk Analyzer (LightGBM Inference Threshold ≥ 0.80)")

# Live Demo Toggle: Pause Live Feed
paused = st.toggle(
    "Pause Live Feed",
    value=False,
    help="Freeze the UI updates to present and explain current cart details. Background stream remains connected and processing."
)

if paused:
    st.warning("⏸️ Live Feed Paused — Preserving current cart state for inspection. Backend streaming continues in background.")
else:
    st.success("🟢 Live Feed Active — Continuously monitoring Kafka event stream.")

# Real-time display fragment
@st.fragment(run_every="0.5s")
def render_live_cart_inspector():
    eps, total_p, total_f, is_connected = buffer.get_metrics()

    # When NOT paused, pull new incoming high-risk alerts and maintain exactly 5 in FIFO
    if not paused:
        new_alerts = buffer.pop_all_alerts()
        for alert in new_alerts:
            risk = float(alert.get("risk_score", 0.0))
            if risk >= 0.80:
                # Insert at index 0 (newest on top)
                st.session_state.flagged_carts.insert(0, alert)
        
        # Keep strictly the 5 most recent high-risk carts, visually pushing the oldest one out
        if len(st.session_state.flagged_carts) > 5:
            st.session_state.flagged_carts = st.session_state.flagged_carts[:5]

    # Top Metrics Row using native st.metric
    col_metric1, col_metric2, col_metric3 = st.columns(3)
    col_metric1.metric(label="Events/Sec", value=f"{eps:.1f}")
    col_metric2.metric(label="Total Processed", value=f"{total_p:,}")
    col_metric3.metric(label="High-Risk Alerts", value=f"{total_f:,}")

    st.divider()

    st.subheader(f"⚡ High-Risk Cart Feed ({len(st.session_state.flagged_carts)} of 5 Visible Carts)")

    if not st.session_state.flagged_carts:
        if is_connected:
            st.info("Waiting for live high-risk carts (Risk Score ≥ 0.80) from Kafka stream...")
        else:
            st.warning("Connecting to FastAPI stream backend at http://backend:8000/stream...")
        return

    # Render each of the 5 visible carts using native st.container and st.columns
    for idx, cart in enumerate(st.session_state.flagged_carts):
        tx_id = cart.get("transaction_id", "UNKNOWN")
        risk_score = float(cart.get("risk_score", 0.0))
        user_id = cart.get("user_id", "U000000")
        product_id = cart.get("product_id", "P00000")
        account_age = int(cart.get("account_age_days", 0))
        user_ret = float(cart.get("user_historical_return_rate", cart.get("user_return_rate", 0.0)))
        prod_ret = float(cart.get("product_historical_return_rate", 0.0))
        category = cart.get("category", "General")
        price = float(cart.get("price", 0.0))
        cart_val = float(cart.get("cart_total_value", 0.0))
        total_items = int(cart.get("total_items_in_cart", 1))
        dup_count = int(cart.get("duplicate_variant_count", 0))
        ts = cart.get("timestamp", "--:--:--")

        # Explicit reasoning logic
        reason = cart.get("reason")
        if not reason:
            reasons = []
            if dup_count >= 2:
                reasons.append(f"Bracket Buying - {dup_count} duplicate variants")
            if user_ret >= 0.25:
                reasons.append(f"Serial Returner - High User History ({user_ret*100:.1f}%)")
            elif user_ret >= 0.18:
                reasons.append(f"Elevated User Return History ({user_ret*100:.1f}%)")
            if prod_ret >= 0.20 and not reasons:
                reasons.append(f"High Return Risk Category ({prod_ret*100:.1f}%)")
            if not reasons:
                reasons.append(f"High-Risk Cart Profile ({risk_score*100:.1f}%)")
            reason = " & ".join(reasons)

        with st.container(border=True):
            header_col1, header_col2, header_col3 = st.columns([3, 1, 1])
            with header_col1:
                st.subheader(f"Cart #{idx + 1} • Transaction {tx_id}")
            with header_col2:
                st.metric(label="Risk Score", value=f"{risk_score * 100:.1f}%")
            with header_col3:
                st.caption("Detection Time")
                st.write(f"⏱️ {ts}")

            # Customer Profile Section
            st.write("**Customer Profile**")
            p_col1, p_col2, p_col3 = st.columns(3)
            with p_col1:
                st.caption("User ID")
                st.write(f"👤 `{user_id}`")
            with p_col2:
                st.caption("Account Age")
                st.write(f"📅 {account_age} days ({account_age // 365} yrs {account_age % 365 // 30} mos)")
            with p_col3:
                st.caption("User Historical Return Rate")
                st.write(f"🔄 {user_ret * 100:.1f}%")

            # Cart Items & Details Section
            st.write("**Cart Items & Details**")
            i_col1, i_col2, i_col3, i_col4 = st.columns(4)
            with i_col1:
                st.caption("Product & Category")
                st.write(f"📦 `{product_id}` ({category})")
            with i_col2:
                st.caption("Item Price")
                st.write(f"💵 ${price:.2f}")
            with i_col3:
                st.caption("Cart Total Value")
                st.write(f"💰 ${cart_val:.2f}")
            with i_col4:
                st.caption("Items & Variants")
                st.write(f"🔢 {total_items} items ({dup_count} duplicate variants)")

            # Threshold Violation Trigger with Explicit Reason
            st.error(f"🚨 Flagged Item: {category} (Risk: {risk_score * 100:.1f}%) | Reason: {reason}")

render_live_cart_inspector()
