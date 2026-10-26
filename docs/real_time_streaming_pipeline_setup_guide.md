# Pre-Checkout Return Risk Analyzer: Real-Time Pipeline Instructions

**Target Agent:** Anti-Gravity (or similar AI Coding Assistant)
**Objective:** Build a complete real-time event streaming architecture consisting of a Kafka Producer (Firehose), a FastAPI backend (Consumer & ML Inference), and a Streamlit frontend (Command Center).
**Context:** The ML model (`lgbm_return_model.pkl`) has been trained. The dataset (`bracket_buying_returns_1M.csv`) contains the necessary features. The system must process continuous data autonomously to demonstrate "enterprise-grade" real-time capabilities.

**CRITICAL ARCHITECTURE CONSTRAINTS:**
*   **Zero-Database MVP:** To ensure rapid deployment, assume the Kafka payload *already contains* all required features (historical rates, cart values). Do not implement Redis or a database lookup for this build.
*   **Communication:** Use Server-Sent Events (SSE) or WebSockets to stream data from FastAPI to Streamlit.
*   **Threshold Logic:** Only flag carts where `return_probability >= 0.80`.

Please generate three separate Python scripts (`producer.py`, `backend.py`, `dashboard.py`) following these exact specifications:

## Script 1: The Traffic Generator (`producer.py`)
**Goal:** Simulate a high-throughput stream of live cart events.
*   **Libraries:** `kafka-python` (or `confluent_kafka`), `pandas`, `json`, `time`, `random`.
*   **Logic:**
    1. Load the holdout/test portion of `bracket_buying_returns_1M.csv`.
    2. Initialize a Kafka Producer connecting to `localhost:9092`.
    3. Create an infinite loop that randomly samples rows from the dataframe.
    4. Convert each row into a JSON payload. Ensure categorical fields (like `category`) remain strings and numerics are standard Python floats/ints.
    5. Send the JSON payload to a Kafka topic named `live_cart_events`.
    6. Add a small random sleep delay (e.g., `time.sleep(random.uniform(0.01, 0.1))`) to simulate a realistic firehose of 10-100 events per second.

## Script 2: Inference Engine & API (`backend.py`)
**Goal:** Consume Kafka events, run LightGBM inference, and stream results.
*   **Libraries:** `fastapi`, `uvicorn`, `kafka-python`, `joblib`, `pandas`, `asyncio`, `sse_starlette` (or standard WebSocket).
*   **Logic:**
    1. **Initialization:** Load the `lgbm_return_model.pkl` globally on startup.
    2. **Kafka Consumer:** Set up an async generator that consumes messages from the `live_cart_events` topic.
    3. **Inference Pipeline:** As each JSON message arrives:
        * Convert the JSON to a single-row Pandas DataFrame.
        * Ensure the columns perfectly match the ML training schema (cast `category` to a pandas categorical type if required by the model).
        * Run `model.predict_proba(df)[:, 1]` to get the risk score.
    4. **Thresholding & Output:** 
        * Calculate rolling throughput (events processed per second).
        * If the risk score is >= 0.80, append a `flagged: True` and `risk_score` key to the payload. Otherwise, `flagged: False`.
    5. **API Endpoint (`/stream`):** Create an SSE (Server-Sent Events) or WebSocket endpoint that pushes a combined payload (current throughput + any flagged cart details) to the frontend continuously.

## Script 3: Command Center Dashboard (`dashboard.py`)
**Goal:** Visualize the continuous data stream in real-time.
*   **Libraries:** `streamlit`, `requests`, `websockets` (or `sseclient-py`), `pandas`.
*   **UI Layout & Logic:**
    1. **Header:** "Live Pre-Checkout Risk Monitoring".
    2. **Top Metrics Row:** Display a live-updating big number metric for "Events Processed / Sec".
    3. **Live Alert Feed:** 
        * Create an empty placeholder (`st.empty()`).
        * Connect to the FastAPI `/stream` endpoint.
        * Maintain a local Python list of the last 50 *flagged* events.
        * As flagged events arrive from the backend, prepend them to the list and render them in the placeholder as a Pandas DataFrame or a styled list of alert cards (e.g., "🚨 ALERT: Transaction [ID] | Bracket Buy Detected | Risk: 85%").
    4. **Constraint:** Use `st.rerun()` or Streamlit's fragment decorators efficiently so the dashboard doesn't freeze under high update volumes.