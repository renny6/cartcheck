| Document 02 — TRD Template | |
| :--- | :--- |
| **Frontend** | Streamlit (Python) |
| **Backend** | Python / FastAPI |
| **Database** | None (Zero-Database MVP. Data flows directly via Kafka to FastAPI). |
| **Auth** | None required for this admin dashboard. |
| **Hosting / Infrastructure** | Docker & Docker Compose (Local deployment encompassing Kafka, Zookeeper, FastAPI, and Streamlit). |
| **Third-party APIs** | None. |
| **Key Libraries** | `kafka-python`, `fastapi`, `uvicorn`, `lightgbm`, `pandas`, `joblib`, `streamlit`, `sse_starlette`. |
| **Environment Variables** | `KAFKA_BROKER_URL`, `MODEL_PATH`, `DATASET_PATH`. |
| **Constraints** | Continuous execution mode (agent must not stop between phases unless terminal error). Must load pre-trained `.pkl` LightGBM model. All code must run inside Docker. |