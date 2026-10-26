import os
import time
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import (
    roc_auc_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report
)
import joblib

def main():
    print("=" * 60)
    print("Pre-Checkout Return Risk Analyzer: ML Training Pipeline")
    print("=" * 60)
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_path = os.path.join(base_dir, "data", "bracket_buying_returns_1M.csv")
    model_output_path = os.path.join(base_dir, "lgbm_return_model.pkl")
    holdout_output_path = os.path.join(base_dir, "data", "holdout_test_data.csv")
    
    # -------------------------------------------------------------
    # Step 1 & 2: Data Loading & Preprocessing
    # -------------------------------------------------------------
    print(f"\n[1/6] Loading dataset from: {dataset_path}")
    start_time = time.time()
    df = pd.read_csv(dataset_path)
    print(f"Loaded {len(df):,} rows and {len(df.columns)} columns in {time.time() - start_time:.2f}s")
    
    # Categorical Handling
    print("\n[2/6] Processing features and casting categories...")
    df['category'] = df['category'].astype('category')
    
    # Feature columns
    feature_cols = [
        'category',
        'price',
        'product_historical_return_rate',
        'account_age_days',
        'user_historical_return_rate',
        'cart_total_value',
        'total_items_in_cart',
        'duplicate_variant_count'
    ]
    target_col = 'is_returned'
    group_col = 'transaction_id'
    
    # -------------------------------------------------------------
    # Step 3: Leakage-Free Splitting using GroupShuffleSplit
    # -------------------------------------------------------------
    print("\n[3/6] Performing leakage-free GroupShuffleSplit on 'transaction_id' (80/20)...")
    gss = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=42)
    train_idx, test_idx = next(gss.split(df, groups=df[group_col]))
    
    df_train = df.iloc[train_idx]
    df_test = df.iloc[test_idx]
    
    print(f"Train samples: {len(df_train):,} ({len(df_train[group_col].unique()):,} unique carts)")
    print(f"Test samples:  {len(df_test):,} ({len(df_test[group_col].unique()):,} unique carts)")
    
    # Save the holdout test data for the streaming producer
    print(f"Exporting holdout test data for streaming producer to: {holdout_output_path}")
    df_test.to_csv(holdout_output_path, index=False)
    
    X_train = df_train[feature_cols].copy()
    y_train = df_train[target_col].copy()
    
    X_test = df_test[feature_cols].copy()
    y_test = df_test[target_col].copy()
    
    # Verify transaction_id is completely dropped from model inputs
    assert group_col not in X_train.columns and group_col not in X_test.columns, "transaction_id must be dropped from model inputs!"
    
    # -------------------------------------------------------------
    # Step 4: LightGBM Model Configuration & Training
    # -------------------------------------------------------------
    print("\n[4/6] Initializing and training LightGBM Classifier...")
    model = lgb.LGBMClassifier(
        objective='binary',
        metric='auc',
        n_estimators=1000,
        learning_rate=0.05,
        random_state=42,
        class_weight='balanced',
        n_jobs=-1,
        verbose=-1
    )
    
    callbacks = [
        lgb.early_stopping(stopping_rounds=50, verbose=True),
        lgb.log_evaluation(period=50)
    ]
    
    fit_start = time.time()
    model.fit(
        X_train,
        y_train,
        eval_set=[(X_test, y_test)],
        callbacks=callbacks
    )
    print(f"Training completed in {time.time() - fit_start:.2f}s")
    
    # -------------------------------------------------------------
    # Step 5: Custom Threshold Evaluation
    # -------------------------------------------------------------
    print("\n[5/6] Evaluating model with custom risk threshold (threshold = 0.80)...")
    y_proba = model.predict_proba(X_test)[:, 1]
    
    roc_auc = roc_auc_score(y_test, y_proba)
    print(f"Test ROC-AUC Score: {roc_auc:.4f}")
    
    threshold = 0.80
    y_pred = (y_proba >= threshold).astype(int)
    
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    cm = confusion_matrix(y_test, y_pred)
    
    print("-" * 50)
    print(f"Threshold: {threshold:.2f}")
    print(f"Precision: {precision:.4f}  (Highest priority)")
    print(f"Recall:    {recall:.4f}")
    print(f"F1 Score:  {f1:.4f}")
    print("-" * 50)
    print("Confusion Matrix:")
    print(cm)
    print("\nClassification Report (threshold = 0.80):")
    print(classification_report(y_test, y_pred, target_names=["Not Returned (0)", "Returned (1)"], zero_division=0))
    
    # -------------------------------------------------------------
    # Step 6: Model Export
    # -------------------------------------------------------------
    print(f"\n[6/6] Exporting model to {model_output_path}...")
    joblib.dump(model, model_output_path)
    
    print("=" * 60)
    print(f"SUCCESS: LightGBM model successfully exported to: {model_output_path}")
    print("Ready for FastAPI real-time inference backend.")
    print("=" * 60)

if __name__ == "__main__":
    main()
