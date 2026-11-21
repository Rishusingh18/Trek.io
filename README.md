# Trek.io — Academic Management Portal & Adaptive Learning Engine

**Trek.io** is a full-stack personalized learning path recommender and academic management system. It bridges **FastAPI modular monolith backend**, **Machine Learning recommendation & adaptive IRT testing models**, and **Stitch-crafted high-fidelity portal frontend**.

---

## 🏗️ Architecture & Integration

```
┌────────────────────────────────────────────────────────────────────────┐
│                          STITCH FRONTEND SUITE                         │
│  - Master Portal Hub (index.html)                                      │
│  - Student Cockpit & 7-Stop Curriculum Workbench (Asha Sharma)        │
│  - Adaptive Quiz History & Diagnostics                                 │
│  - Instructor Class Heatmap & Intervention Dispatch (Prof. Rao)       │
│  - Admin A/B Switchboard & Telemetry Engine (Arm A vs Arm B)          │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (REST /v1, JWT Auth, CORS)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        FASTAPI BACKEND GATEWAY                         │
│  - Modular Routers: /auth, /courses, /knowledge, /quiz, /recommender  │
│  - Middlewares: Sliding-window Rate Limiter, Latency Logger            │
│  - Static Mount: Serves /portal and redirects / -> /portal/index.html │
└─────────────────┬───────────────────────────────────┬──────────────────┘
                  │                                   │
                  ▼                                   ▼
┌──────────────────────────────────┐ ┌───────────────────────────────────┐
│        ML & ALGORITHMS           │ │         PERSISTENCE LAYER         │
│  - Rule-Based Engine (Arm A)     │ │  - PostgreSQL 16 / SQLite Fallback│
│  - Embedding-Hybrid (Arm B)      │ │  - Redis / In-Memory Cache        │
│  - Item-Item Collaborative Filter│ │  - Precomputed Analytics Rollups  │
│  - IRT Adaptive Difficulty Engine│ │  - 342 Cohort Learners & Attempts │
└──────────────────────────────────┘ └───────────────────────────────────┘
```

---

## ⚡ Quick Start

In a fresh Python environment:

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Configure environment:**
Set a private `SECRET_KEY` in your environment or `.env` file (required for startup):
```bash
# On Linux/macOS
export SECRET_KEY=your-secure-random-secret-key
# On Windows PowerShell
$env:SECRET_KEY="your-secure-random-secret-key"
```

3. **Launch the unified system (API + ML Recommender + Frontend) on a single port:**

```bash
python run.py
```

Open your browser:
* 🧭 **Portal Hub:** [http://localhost:8000/](http://localhost:8000/) or [http://localhost:8000/portal/index.html](http://localhost:8000/portal/index.html)
* 📚 **API Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
* 🩺 **Health Endpoint:** [http://localhost:8000/health](http://localhost:8000/health)

---

## 👥 Pre-Seeded Personas & Demo Accounts

Learner and instructor demo accounts use password: `password123`.

For the administrator persona (`admin@campus.edu`), you must configure `ADMIN_PASSWORD` in your environment before the first seed. In local development or test environments, shared-password access can optionally be enabled by setting `ALLOW_LOCAL_DEMO_ADMIN=true`.

| Role | Persona | Email | Password | Purpose & Features |
| :--- | :--- | :--- | :--- | :--- |
| **Learner** | **Asha Sharma** | `asha@campus.edu` | `password123` | Self-paced roadmap, ML recommendations (Arm B), dynamic 7-stop workbench, topic mastery radar |
| **Instructor** | **Prof. Rao** | `profr@campus.edu` | `password123` | CS 301 cohort (342 learners), Dynamic Programming bottleneck alert (48%), at-risk drill dispatch |
| **Administrator** | **Platform Admin** | `admin@campus.edu` | Deployment-provided `ADMIN_PASSWORD` (or `password123` if `ALLOW_LOCAL_DEMO_ADMIN=true` in dev/local/test) | A/B Experiment #04 switchboard (Arm A vs B), zero-downtime override, credential generator |

---

## 🧠 Machine Learning Components

1. **Recommender Strategies (`backend/app/modules/recommender/strategies/`)**:
   - **Arm A (Rule-Based)**: Multi-objective score combining knowledge gap, prerequisites readiness, and fit:  
     \(S(i) = w_1 \cdot \text{gap} + w_2 \cdot \text{fit} + w_3 \cdot \text{ready} + w_4 \cdot \text{eng}\)
   - **Arm B (Embedding-Hybrid Vector)**: Content vectors and learner profile vectors computed via TF-IDF / sentence embeddings, blended with fit via cosine similarity.
   - **Collaborative Filtering**: Item-item co-occurrence matrix trained on successful completions from learner interaction histories (`demo data/learner_interaction_data/`).
2. **Item Response Theory (IRT) Adaptive Quiz Engine (`backend/app/modules/quiz/`)**:
   - Next-question difficulty dynamic adjustment (+0.05 on streak, -0.05 on miss).
   - Real-time atomic mastery updates and stop-rule confidence triggers.
3. **Knowledge Decay & Rollup Engine (`backend/app/worker/jobs.py`)**:
   - Exponential knowledge decay formula: \(m_{\text{new}} = m_{\text{last}} \cdot e^{-\lambda \cdot t}\).

---

## 🧪 Verification & Health Check

Run the direct-service smoke test verifying all 6 modules (Auth, Course, Mastery, ML Recommendations, Adaptive Quiz, Instructor Analytics) directly against internal services (keep HTTP endpoint checks separate via the live server):

```bash
python backend/scripts/verify_api.py
```

To re-seed or regenerate the CS 301 dataset with 342 learners and calibrated ML models:

```bash
python run.py --seed-only
```
