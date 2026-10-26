| Document 05 — Backend Schema Template | |
| :--- | :--- |
| **Schema: Kafka JSON Payload** | `transaction_id` (string), `category` (string), `price` (float), `product_historical_return_rate` (float), `account_age_days` (int), `user_historical_return_rate` (float), `cart_total_value` (float), `total_items_in_cart` (int), `duplicate_variant_count` (int) |
| **Relationships** | N/A (Flat payload representing one cart item at a time). |
| **Auth Provider** | N/A |
| **Row Level Security** | N/A |
| **User Roles** | N/A |
| **File Storage** | N/A |
| **Sensitive Fields** | N/A |