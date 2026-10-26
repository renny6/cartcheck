import os
import sys
import json
import time
import asyncio
import logging
from typing import Dict, Any, List, Set
from collections import deque
from contextlib import asynccontextmanager

import joblib
import pandas as pd
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [BACKEND] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("CartCheckBackend")

KAFKA_BROKER = os.getenv("KAFKA_BROKER_URL", "localhost:9092")
TOPIC_NAME = os.getenv("KAFKA_TOPIC", "live_cart_events")
MODEL_PATH = os.getenv("MODEL_PATH", "")

FEATURE_COLS = [
    'category',
    'price',
    'product_historical_return_rate',
    'account_age_days',
    'user_historical_return_rate',
    'cart_total_value',
    'total_items_in_cart',
    'duplicate_variant_count'
]

# Shared Global State
class StreamState:
    def __init__(self):
        self.model = None
        self.is_running = True
        self.total_processed: int = 0
        self.total_flagged: int = 0
        self.rolling_timestamps: deque = deque(maxlen=2000)
        self.recent_alerts: deque = deque(maxlen=50)
        self.subscribers: Set[asyncio.Queue] = set()
        self.lock = asyncio.Lock()
        self.kafka_connected = False

    def get_throughput(self) -> float:
        now = time.time()
        # Keep timestamps within the last 2 seconds
        while self.rolling_timestamps and (now - self.rolling_timestamps[0] > 2.0):
            self.rolling_timestamps.popleft()
        if not self.rolling_timestamps:
            return 0.0
        duration = max(now - self.rolling_timestamps[0], 0.1)
        return round(len(self.rolling_timestamps) / duration, 1)

state = StreamState()

def resolve_model_path():
    candidates = [
        MODEL_PATH,
        os.path.join(os.path.dirname(__file__), "models", "lgbm_return_model.pkl"),
        os.path.join(os.path.dirname(__file__), "..", "lgbm_return_model.pkl"),
        os.path.join("/app", "models", "lgbm_return_model.pkl"),
        os.path.join("/app", "lgbm_return_model.pkl"),
        "lgbm_return_model.pkl"
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return None

def load_ml_model():
    path = resolve_model_path()
    if not path:
        logger.error("Could not find 'lgbm_return_model.pkl'!")
        return None
    logger.info(f"Loading LightGBM model from: {path}")
    try:
        model = joblib.load(path)
        logger.info("LightGBM model loaded successfully.")
        return model
    except Exception as e:
        logger.error(f"Error loading model: {e}")
        return None

def create_kafka_consumer():
    max_retries = 30
    retry_interval = 3
    logger.info(f"Connecting to Kafka at '{KAFKA_BROKER}' for topic '{TOPIC_NAME}'...")
    
    for attempt in range(1, max_retries + 1):
        try:
            consumer = KafkaConsumer(
                TOPIC_NAME,
                bootstrap_servers=KAFKA_BROKER,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                auto_offset_reset="latest",
                enable_auto_commit=True,
                group_id="cartcheck-inference-group",
                consumer_timeout_ms=1000
            )
            logger.info(f"Kafka consumer successfully connected to '{KAFKA_BROKER}' (attempt {attempt})")
            state.kafka_connected = True
            return consumer
        except NoBrokersAvailable:
            logger.warning(f"Kafka broker not ready (attempt {attempt}/{max_retries}). Retrying in {retry_interval}s...")
            time.sleep(retry_interval)
        except Exception as e:
            logger.error(f"Kafka consumer error: {e}. Retrying in {retry_interval}s...")
            time.sleep(retry_interval)
    logger.critical(f"Could not connect to Kafka after {max_retries} attempts.")
    return None

async def broadcast_event(event_dict: Dict[str, Any]):
    async with state.lock:
        dead_subscribers = set()
        for q in state.subscribers:
            try:
                q.put_nowait(event_dict)
            except asyncio.QueueFull:
                dead_subscribers.add(q)
        for dead in dead_subscribers:
            state.subscribers.remove(dead)

def kafka_consumer_worker(loop: asyncio.AbstractEventLoop):
    """Runs in a background thread to continuously consume Kafka events."""
    consumer = create_kafka_consumer()
    if not consumer:
        logger.error("Consumer worker terminating: No Kafka connection.")
        return

    logger.info("Starting inference loop on Kafka stream...")
    
    last_metrics_broadcast = time.time()
    
    while state.is_running:
        try:
            msg_pack = consumer.poll(timeout_ms=500, max_records=50)
            now = time.time()
            
            for tp, records in msg_pack.items():
                for record in records:
                    payload = record.value
                    state.total_processed += 1
                    state.rolling_timestamps.append(now)
                    
                    # Extract items list if present, otherwise single item from flat payload
                    raw_items = payload.get("items")
                    if not raw_items:
                        raw_items = [{
                            "product_id": payload.get("product_id", "P00000"),
                            "category": payload.get("category", "General"),
                            "price": float(payload.get("price", 0.0)),
                            "product_historical_return_rate": float(payload.get("product_historical_return_rate", 0.0)),
                            "duplicate_variant_count": int(payload.get("duplicate_variant_count", 0))
                        }]
                    
                    # Prepare batch input for LightGBM
                    input_rows = []
                    account_age = int(payload.get('account_age_days', 0))
                    user_ret = float(payload.get('user_historical_return_rate', payload.get('user_return_rate', 0.0)))
                    cart_val = float(payload.get('cart_total_value', 0.0))
                    total_items = int(payload.get('total_items_in_cart', len(raw_items)))
                    cart_dup_variants = int(payload.get('duplicate_variant_count', 0))
                    
                    for item in raw_items:
                        input_rows.append({
                            'category': item.get('category', 'General'),
                            'price': float(item.get('price', 0.0)),
                            'product_historical_return_rate': float(item.get('product_historical_return_rate', 0.0)),
                            'account_age_days': account_age,
                            'user_historical_return_rate': user_ret,
                            'cart_total_value': cart_val,
                            'total_items_in_cart': total_items,
                            'duplicate_variant_count': int(item.get('duplicate_variant_count', cart_dup_variants))
                        })
                    
                    df_batch = pd.DataFrame(input_rows, columns=FEATURE_COLS)
                    df_batch['category'] = df_batch['category'].astype('category')
                    
                    # Run inference across all items in cart
                    item_probs = [0.0] * len(input_rows)
                    if state.model is not None:
                        item_probs = state.model.predict_proba(df_batch)[:, 1]
                    
                    evaluated_items = []
                    any_flagged = False
                    
                    for i, item in enumerate(raw_items):
                        prob = float(item_probs[i])
                        is_it_flagged = (prob >= 0.80)
                        if is_it_flagged:
                            any_flagged = True
                            
                        # Explicit reasoning logic for this item
                        dup_variants = int(input_rows[i]['duplicate_variant_count'])
                        prod_ret = float(input_rows[i]['product_historical_return_rate'])
                        trigger_reasons = []
                        if dup_variants >= 2:
                            trigger_reasons.append(f"Bracket Buying - {dup_variants} duplicate variants")
                        if user_ret >= 0.25:
                            trigger_reasons.append(f"Serial Returner - High User History ({user_ret*100:.1f}%)")
                        elif user_ret >= 0.18:
                            trigger_reasons.append(f"Elevated User Return History ({user_ret*100:.1f}%)")
                        if prod_ret >= 0.20 and not trigger_reasons:
                            trigger_reasons.append(f"High Return Risk Category ({prod_ret*100:.1f}%)")
                        if not trigger_reasons:
                            trigger_reasons.append(f"High Return Risk Profile ({prob*100:.1f}%)")
                        
                        item_reason = " & ".join(trigger_reasons)
                        
                        evaluated_items.append({
                            "product_id": str(item.get("product_id", f"P{i:04d}")),
                            "category": str(item.get("category", "General")),
                            "price": float(item.get("price", 0.0)),
                            "risk_score": round(prob, 4),
                            "is_flagged": is_it_flagged,
                            "duplicate_variant_count": dup_variants,
                            "product_historical_return_rate": prod_ret,
                            "reason": item_reason if is_it_flagged else ""
                        })
                    
                    if any_flagged:
                        state.total_flagged += 1
                        cart_risk = max(it["risk_score"] for it in evaluated_items)
                        
                        alert_data = {
                            "type": "alert",
                            "transaction_id": payload.get("transaction_id", "UNKNOWN"),
                            "user_id": payload.get("user_id", "U" + str(payload.get("transaction_id", "000000")).replace("T", "")),
                            "risk_score": round(cart_risk, 4),
                            "account_age_days": account_age,
                            "user_historical_return_rate": user_ret,
                            "cart_total_value": cart_val,
                            "total_items_in_cart": total_items,
                            "duplicate_variant_count": cart_dup_variants,
                            "timestamp": time.strftime("%H:%M:%S"),
                            "items": evaluated_items
                        }
                        state.recent_alerts.appendleft(alert_data)
                        
                        # Immediately broadcast high-risk cart alert
                        asyncio.run_coroutine_threadsafe(broadcast_event(alert_data), loop)

            # Broadcast throughput & aggregate metrics once per second
            if now - last_metrics_broadcast >= 1.0:
                tps = state.get_throughput()
                flag_rate = (state.total_flagged / max(state.total_processed, 1)) * 100.0
                metrics_data = {
                    "type": "metrics",
                    "events_per_sec": tps,
                    "total_processed": state.total_processed,
                    "total_flagged": state.total_flagged,
                    "flag_rate_pct": round(flag_rate, 2),
                    "timestamp": time.strftime("%H:%M:%S")
                }
                asyncio.run_coroutine_threadsafe(broadcast_event(metrics_data), loop)
                last_metrics_broadcast = now
                
        except Exception as e:
            logger.error(f"Error during consumer poll/inference: {e}")
            time.sleep(1)
            
    consumer.close()
    logger.info("Kafka consumer worker closed.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing FastAPI Backend...")
    state.model = load_ml_model()
    loop = asyncio.get_running_loop()
    
    # Start consumer in a background daemon thread
    import threading
    consumer_thread = threading.Thread(
        target=kafka_consumer_worker,
        args=(loop,),
        daemon=True,
        name="KafkaConsumerThread"
    )
    consumer_thread.start()
    
    yield
    # Shutdown
    state.is_running = False
    logger.info("FastAPI backend shutting down...")

app = FastAPI(
    title="Pre-Checkout Return Risk Analyzer API",
    version="1.0.0",
    description="Real-time ML streaming inference engine for bracket buying detection",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {
        "service": "Pre-Checkout Return Risk Analyzer Backend",
        "status": "online",
        "model_loaded": state.model is not None,
        "kafka_connected": state.kafka_connected
    }

@app.get("/health")
def health():
    return {
        "status": "healthy" if (state.model is not None and state.kafka_connected) else "degraded",
        "model_loaded": state.model is not None,
        "kafka_connected": state.kafka_connected,
        "total_processed": state.total_processed,
        "total_flagged": state.total_flagged,
        "events_per_sec": state.get_throughput()
    }

@app.get("/stats")
def get_stats():
    return {
        "events_per_sec": state.get_throughput(),
        "total_processed": state.total_processed,
        "total_flagged": state.total_flagged,
        "flag_rate_pct": round((state.total_flagged / max(state.total_processed, 1)) * 100.0, 2),
        "recent_alerts": list(state.recent_alerts)
    }

@app.get("/stream")
async def stream_events(request: Request):
    """Server-Sent Events endpoint pushing real-time metrics and flagged alerts."""
    client_queue = asyncio.Queue(maxsize=100)
    async with state.lock:
        state.subscribers.add(client_queue)
    
    logger.info(f"New SSE client connected. Active subscribers: {len(state.subscribers)}")
    
    async def event_generator():
        try:
            # Send initial sync payload
            initial_stats = {
                "type": "sync",
                "events_per_sec": state.get_throughput(),
                "total_processed": state.total_processed,
                "total_flagged": state.total_flagged,
                "flag_rate_pct": round((state.total_flagged / max(state.total_processed, 1)) * 100.0, 2),
                "recent_alerts": list(state.recent_alerts),
                "timestamp": time.strftime("%H:%M:%S")
            }
            yield {
                "event": "sync",
                "data": json.dumps(initial_stats)
            }
            
            while True:
                # Disconnect check
                if await request.is_disconnected():
                    break
                
                try:
                    event_dict = await asyncio.wait_for(client_queue.get(), timeout=1.5)
                    event_type = event_dict.get("type", "message")
                    yield {
                        "event": event_type,
                        "data": json.dumps(event_dict)
                    }
                except asyncio.TimeoutError:
                    # Keep-alive heartbeat
                    yield {
                        "event": "ping",
                        "data": json.dumps({"timestamp": time.strftime("%H:%M:%S")})
                    }
        except asyncio.CancelledError:
            pass
        finally:
            async with state.lock:
                if client_queue in state.subscribers:
                    state.subscribers.remove(client_queue)
            logger.info(f"SSE client disconnected. Active subscribers: {len(state.subscribers)}")

    return EventSourceResponse(event_generator())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend:app", host="0.0.0.0", port=8000, log_level="info")
