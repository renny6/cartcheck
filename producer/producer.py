import os
import sys
import json
import time
import random
import logging
import pandas as pd
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [PRODUCER] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("CartCheckProducer")

KAFKA_BROKER = os.getenv("KAFKA_BROKER_URL", "localhost:9092")
TOPIC_NAME = os.getenv("KAFKA_TOPIC", "live_cart_events")
DATASET_PATH = os.getenv("DATASET_PATH", "")

def find_dataset_file():
    candidates = [
        DATASET_PATH,
        os.path.join(os.path.dirname(__file__), "data", "holdout_test_data.csv"),
        os.path.join(os.path.dirname(__file__), "..", "data", "holdout_test_data.csv"),
        os.path.join("/app", "data", "holdout_test_data.csv"),
        os.path.join(os.path.dirname(__file__), "data", "bracket_buying_returns_1M.csv"),
        os.path.join(os.path.dirname(__file__), "..", "data", "bracket_buying_returns_1M.csv"),
        os.path.join("/app", "data", "bracket_buying_returns_1M.csv")
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return None

def connect_kafka_producer(broker_url, max_retries=30, retry_interval=3):
    logger.info(f"Connecting to Kafka broker at '{broker_url}'...")
    for attempt in range(1, max_retries + 1):
        try:
            producer = KafkaProducer(
                bootstrap_servers=broker_url,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                acks=1,
                request_timeout_ms=10000
            )
            logger.info(f"Successfully connected to Kafka broker '{broker_url}' (attempt {attempt})")
            return producer
        except NoBrokersAvailable:
            logger.warning(f"Kafka broker not available yet (attempt {attempt}/{max_retries}). Retrying in {retry_interval}s...")
            time.sleep(retry_interval)
        except Exception as e:
            logger.error(f"Unexpected error connecting to Kafka: {e}. Retrying in {retry_interval}s...")
            time.sleep(retry_interval)
    logger.critical(f"Failed to connect to Kafka broker '{broker_url}' after {max_retries} attempts.")
    sys.exit(1)

def find_carts_file():
    candidates = [
        os.path.join(os.path.dirname(__file__), "data", "holdout_carts.json"),
        os.path.join(os.path.dirname(__file__), "..", "data", "holdout_carts.json"),
        os.path.join("/app", "data", "holdout_carts.json"),
        "data/holdout_carts.json"
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return None

def main():
    logger.info("Initializing Live Cart Traffic Generator (Producer)...")
    
    carts_file = find_carts_file()
    carts = []
    if carts_file:
        logger.info(f"Loading pre-grouped carts from: {carts_file}")
        with open(carts_file, "r") as f:
            carts = json.load(f)
        logger.info(f"Loaded {len(carts):,} complete carts with all associated items.")
    else:
        data_file = find_dataset_file()
        if not data_file:
            logger.error("Could not find dataset! Please check DATASET_PATH.")
            sys.exit(1)
        logger.info(f"Grouping cart transactions from: {data_file}")
        df = pd.read_csv(data_file)
        for tx_id, g in df.groupby("transaction_id", sort=False):
            first = g.iloc[0]
            items = []
            for _, r in g.iterrows():
                items.append({
                    "product_id": str(r["product_id"]),
                    "category": str(r["category"]),
                    "price": float(r["price"]),
                    "product_historical_return_rate": float(r["product_historical_return_rate"]),
                    "duplicate_variant_count": int(r["duplicate_variant_count"])
                })
            carts.append({
                "transaction_id": str(tx_id),
                "user_id": str(first.get("user_id", "U000000")),
                "account_age_days": int(first["account_age_days"]),
                "user_historical_return_rate": float(first["user_historical_return_rate"]),
                "cart_total_value": float(first["cart_total_value"]),
                "total_items_in_cart": int(first["total_items_in_cart"]),
                "duplicate_variant_count": int(first["duplicate_variant_count"]),
                "items": items
            })
        logger.info(f"Grouped {len(carts):,} carts from CSV.")
    
    total_carts = len(carts)
    producer = connect_kafka_producer(KAFKA_BROKER)
    logger.info(f"Beginning continuous cart event blast to Kafka topic '{TOPIC_NAME}'...")
    
    events_sent = 0
    start_time = time.time()
    last_log_time = start_time
    last_log_events = 0
    
    try:
        while True:
            # Pick a random cart
            idx = random.randint(0, total_carts - 1)
            cart = carts[idx]
            
            # Format payload with complete cart items
            first_item = cart["items"][0] if cart.get("items") else {}
            payload = {
                "transaction_id": cart["transaction_id"],
                "user_id": cart["user_id"],
                "product_id": first_item.get("product_id", "P00000"),
                "category": first_item.get("category", "General"),
                "price": float(first_item.get("price", 0.0)),
                "product_historical_return_rate": float(first_item.get("product_historical_return_rate", 0.0)),
                "account_age_days": cart["account_age_days"],
                "user_historical_return_rate": cart["user_historical_return_rate"],
                "cart_total_value": cart["cart_total_value"],
                "total_items_in_cart": cart["total_items_in_cart"],
                "duplicate_variant_count": cart["duplicate_variant_count"],
                "items": cart["items"]
            }
            
            producer.send(TOPIC_NAME, value=payload)
            events_sent += 1
            
            # Target throughput: 20-50 events per second (sleep 0.015 - 0.045 seconds)
            time.sleep(random.uniform(0.015, 0.045))
            
            current_time = time.time()
            if current_time - last_log_time >= 5.0:
                elapsed = current_time - last_log_time
                delta_events = events_sent - last_log_events
                rate = delta_events / elapsed
                logger.info(f"Throughput: {rate:.1f} events/sec | Total Sent: {events_sent:,} events to '{TOPIC_NAME}'")
                last_log_time = current_time
                last_log_events = events_sent
                
    except KeyboardInterrupt:
        logger.info("Producer stopped by user signal.")
    finally:
        logger.info("Flushing and closing Kafka producer...")
        producer.flush()
        producer.close()
        logger.info(f"Producer shut down. Total events published: {events_sent:,}")

if __name__ == "__main__":
    main()
