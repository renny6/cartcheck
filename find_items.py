import pandas as pd
import json

df = pd.read_csv('data/holdout_test_data.csv')
tx_ids = ['T0000026', 'T0061000', 'T0000539', 'T0007299', 'T0000356']
sub = df[df['transaction_id'].isin(tx_ids)]

carts_to_send = []
for tx in tx_ids:
    g = sub[sub['transaction_id'] == tx]
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
    cart_obj = {
        "transaction_id": str(tx),
        "user_id": f"U{str(tx).replace('T', '')}",
        "account_age_days": int(first["account_age_days"]),
        "user_historical_return_rate": float(first["user_historical_return_rate"]),
        "cart_total_value": float(first["cart_total_value"]),
        "total_items_in_cart": int(first["total_items_in_cart"]),
        "duplicate_variant_count": int(first["duplicate_variant_count"]),
        "items": items
    }
    carts_to_send.append(cart_obj)
    print(f"Cart {tx}: {len(items)} items, val=${cart_obj['cart_total_value']:.2f}")

with open("demo_5_scenarios.json", "w") as f:
    json.dump(carts_to_send, f, indent=2)
print("Saved demo_5_scenarios.json")
