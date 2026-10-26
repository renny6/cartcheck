| Document 03 — App Flow Template | |
| :--- | :--- |
| **Pages List** | `/` (Single page Dashboard) |
| **Navigation Type** | None (Single view monitoring station) |
| **First Screen** | Dashboard showing "Live Pre-Checkout Risk Monitoring", total events processed per second, and an empty live alert feed. |
| **Auth Flow** | N/A |
| **Core User Journey 1** | Admin opens dashboard → Frontend automatically connects to FastAPI SSE endpoint → Admin watches live terminal-like stream of flagged high-risk carts. |
| **Empty States** | "Waiting for live Kafka stream..." displayed in the alert feed area. |
| **Error States** | "Connection to stream lost. Retrying..." if FastAPI disconnects. |
| **Redirects** | N/A |