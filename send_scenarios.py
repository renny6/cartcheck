import json
import time
from kafka import KafkaProducer

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

with open('demo_5_scenarios.json', 'r') as f:
    carts = json.load(f)

# carts order in json:
# [0] T0000026: Bracket Buying
# [1] T0061000: Hit-and-Run Risk
# [2] T0000539: Volatile Product
# [3] T0007299: Buyer's Remorse
# [4] T0000356: Serial Returner

# Send in reverse order so [0] ends up at the top (Cart #1)
reverse_carts = list(reversed(carts))

print("Sending 5 carts in reverse order...")
for cart in reverse_carts:
    print(f"Producing cart {cart['transaction_id']} (val=${cart['cart_total_value']:.2f})...")
    producer.send('live_cart_events', value=cart)
    producer.flush()
    time.sleep(0.5)

producer.close()
print("All 5 carts sent successfully!")
