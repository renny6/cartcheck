# Pre-Checkout Return Risk Analyzer: ML Training Pipeline Instructions

**Target Agent:** Anti-Gravity (or similar AI Coding Assistant)
**Objective:** Write a complete, execution-ready Python script to train, evaluate, and export a LightGBM binary classifier for a real-time e-commerce return prediction pipeline. 
**Context:** The dataset (`bracket_buying_returns_1M.csv`) contains 1,000,000 rows representing individual cart items. The goal is to predict the `is_returned` label based on cart composition (specifically bracket buying) and historical user/product behavior.

**CRITICAL CONSTRAINTS:**
1. **NO SHAP:** Do not include SHAP, LIME, or any explainability libraries. This model is being built for high-throughput real-time streaming, and we are prioritizing speed over explainability.
2. **NO RANDOM SPLITTING:** Standard `train_test_split` will cause catastrophic data leakage. You MUST use `GroupShuffleSplit` grouped by `transaction_id`.

Please generate a single Python script (`train_model.py`) that strictly follows these sequential steps:

## Step 1: Dependencies and Imports
* Required libraries: `pandas`, `lightgbm`, `scikit-learn`, `joblib`.
* Import `GroupShuffleSplit` from `sklearn.model_selection`.
* Import `roc_auc_score`, `precision_score`, `recall_score`, `f1_score`, `confusion_matrix` from `sklearn.metrics`.

## Step 2: Data Loading & Preprocessing
* Load `bracket_buying_returns_1M.csv` using `pandas`.
* **Categorical Handling:** LightGBM requires categorical features to be explicitly typed. Cast the `category` column: `df['category'] = df['category'].astype('category')`.
* **Feature Selection:** 
  * Drop non-predictive identifiers: `user_id`, `product_id`.
  * Keep `transaction_id` ONLY for the splitting phase.
  * Define Features (`X`): `category`, `price`, `product_historical_return_rate`, `account_age_days`, `user_historical_return_rate`, `cart_total_value`, `total_items_in_cart`, `duplicate_variant_count`.
  * Define Target (`y`): `is_returned`.

## Step 3: Leakage-Free Splitting
* Initialize `GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)`.
* Split the data using `transaction_id` as the `groups` parameter. This ensures all items from a single cart end up entirely in the training set or entirely in the test set.
* **Cleanup:** Immediately drop the `transaction_id` column from both `X_train` and `X_test` after the split is complete. It must not be passed to the model.

## Step 4: LightGBM Model Configuration & Training
* Initialize `lightgbm.LGBMClassifier` with the following parameters:
  * `objective='binary'`
  * `metric='auc'`
  * `n_estimators=1000`
  * `learning_rate=0.05`
  * `random_state=42`
  * `class_weight='balanced'` (Since the dataset has a ~33% positive class rate).
* **Fit the model:** Pass `X_train` and `y_train`. 
* **Validation:** Pass `[(X_test, y_test)]` to the `eval_set` parameter.
* **Early Stopping:** Implement early stopping to halt training if the validation AUC does not improve for 50 rounds.

## Step 5: Custom Threshold Evaluation
* Predict continuous probabilities on `X_test` using `model.predict_proba(X_test)[:, 1]`.
* Apply a custom business logic threshold: `threshold = 0.80`.
* Convert probabilities to binary predictions: `1` if probability >= 0.80, else `0`.
* Calculate and print the standard metrics (ROC-AUC, Precision, Recall, F1, Confusion Matrix) using the threshold-adjusted predictions. (Note: Precision is our highest priority metric here).

## Step 6: Model Export
* Save the trained model to disk using `joblib.dump(model, 'lgbm_return_model.pkl')`.
* Print a success message confirming the model has been exported and is ready for the FastAPI inference backend.