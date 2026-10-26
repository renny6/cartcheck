import joblib
import pandas as pd

model = joblib.load('lgbm_return_model.pkl')
df = pd.read_csv('data/holdout_test_data.csv', nrows=100000)
FEATURE_COLS = ['category', 'price', 'product_historical_return_rate', 'account_age_days', 'user_historical_return_rate', 'cart_total_value', 'total_items_in_cart', 'duplicate_variant_count']
X = df[FEATURE_COLS].copy()
X['category'] = X['category'].astype('category')
probs = model.predict_proba(X)[:, 1]
df['risk_score'] = probs

flagged = df[df['risk_score'] >= 0.80].copy()

def get_reason(r):
    if r['duplicate_variant_count'] >= 2:
        return 'Bracket Buying Detected'
    elif r['account_age_days'] < 30:
        return 'New Account Anomaly (Hit-and-Run Risk)'
    elif r['product_historical_return_rate'] > 0.30:
        return 'Historically Volatile SKU'
    elif r['cart_total_value'] > 500:
        return "High Cart Value (Buyer's Remorse Risk)"
    else:
        return 'Serial Returner Profile'

flagged['reason'] = flagged.apply(get_reason, axis=1)
print(flagged['reason'].value_counts())

for r_name in [
    'Bracket Buying Detected',
    'New Account Anomaly (Hit-and-Run Risk)',
    'Historically Volatile SKU',
    "High Cart Value (Buyer's Remorse Risk)",
    'Serial Returner Profile'
]:
    sub = flagged[flagged['reason'] == r_name]
    if len(sub) > 0:
        print(f"\n=== {r_name} ===")
        print(sub.iloc[0][['transaction_id', 'product_id', 'category', 'price', 'risk_score', 'duplicate_variant_count', 'account_age_days', 'product_historical_return_rate', 'cart_total_value', 'user_historical_return_rate']].to_dict())
    else:
        print(f"\n=== {r_name} (None found in first 100k, finding close or synthetic) ===")
