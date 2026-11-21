# Trek.io — Academic Management Portal & Adaptive Learning Frontend

This frontend suite provides the user interface for **Trek.io: Personalized Learning Path Recommender & Academic Management Portal**.

It is constructed adhering to the **Academic Precision** design system (Material 3 tokens, Tailwind CSS, Plus Jakarta Sans & Inter typography, and Material Symbols).

---

## 🧭 Portal Architecture & Directory Layout

```
frontend/
├── index.html                                                      # Master Portal Hub & Live Interactive Viewer
├── academic_precision/
│   └── DESIGN.md                                                   # Design system tokens, color roles, typography, elevation
├── student_dashboard_consolidated_overview_roadmap/                # Student Dashboard (Consolidated Cockpit)
│   ├── code.html                                                   # Live responsive HTML/Tailwind app
│   └── screen.png                                                  # High-fidelity reference screen
├── student_dashboard_topics_mastery_roadmap/                       # Student Topics Mastery & Dynamic Roadmap
│   ├── code.html                                                   # Live responsive HTML/Tailwind app
│   └── screen.png                                                  # High-fidelity reference screen
├── student_dashboard_browser_history_style_quiz_attempts/           # Quiz Attempts & Performance History
│   ├── code.html                                                   # Live responsive HTML/Tailwind app
│   └── screen.png                                                  # High-fidelity reference screen
├── topics_mastery_detailed_curriculum_roadmap_study_hub/            # Curriculum Roadmap & Study Hub
│   ├── code.html                                                   # Live responsive HTML/Tailwind app
│   └── screen.png                                                  # High-fidelity reference screen
├── teacher_dashboard_simplified_class_mastery_interventions/        # Instructor Class Mastery & Interventions
│   ├── code.html                                                   # Live responsive HTML/Tailwind app
│   └── screen.png                                                  # High-fidelity reference screen
└── admin_console_user_management_system_telemetry/                  # Platform Telemetry & Governance Console
    ├── code.html                                                   # Live responsive HTML/Tailwind app
    └── screen.png                                                  # High-fidelity reference screen
```

---

## 📱 Screen Catalog & PRD User Stories

### 1. Student Consolidated Overview & Roadmap (`student_dashboard_consolidated_overview_roadmap/`)
* **Primary Persona:** Asha Sharma (Learner)
* **PRD Stories:** US-01, US-02, US-03, FR-501
* **Key Features:**
  - Next Recommended Lesson card with transparent recommendation reasons (Arm A rule-based vs Arm B hybrid)
  - Interactive 7-stop curriculum roadmap workbench (from Arrays & Strings to Dynamic Programming and Greedy Algorithms)
  - Topic mastery radar breakdown (74% overall progress)
  - Quick-start adaptive quiz trigger

### 2. Student Topics Mastery & Dynamic Roadmap (`student_dashboard_topics_mastery_roadmap/`)
* **Primary Persona:** Asha Sharma (Learner)
* **PRD Stories:** US-02, FR-301 to FR-307
* **Key Features:**
  - In-depth topic competency breakdown (Weak < 50%, Developing 50-79%, Strong ≥ 80%)
  - Confidence scoring and knowledge decay indicators
  - Prerequisite dependency tracing across curriculum modules

### 3. Quiz Attempts & History (`student_dashboard_browser_history_style_quiz_attempts/`)
* **Primary Persona:** Asha Sharma (Learner)
* **PRD Stories:** US-04, FR-601 to FR-605
* **Key Features:**
  - Browser-history chronological timeline of diagnostic and adaptive quizzes
  - IRT (Item Response Theory) dynamic difficulty step adjustment charts
  - Question-by-question pass/fail breakdown and detailed explanation traces

### 4. Curriculum Roadmap & Study Hub (`topics_mastery_detailed_curriculum_roadmap_study_hub/`)
* **Primary Persona:** Asha Sharma (Learner)
* **PRD Stories:** US-01, US-03
* **Key Features:**
  - Prerequisite visual tree and lock state verification
  - Curated study materials, algorithm cheat-sheets, and interactive coding labs
  - Targeted drill launch buttons

### 5. Instructor Dashboard: Class Mastery & Interventions (`teacher_dashboard_simplified_class_mastery_interventions/`)
* **Primary Persona:** Prof. Rao / Dr. Thorne (Course Faculty)
* **PRD Stories:** US-05, US-06, US-07, FR-701 to FR-706
* **Key Features:**
  - 342-learner cohort monitoring across sections A1, B2, C1 for CS 301
  - Class-wide mastery heatmaps and dynamic curriculum bottleneck detection (DP 48% failure alert)
  - "Students Needing Attention" high-priority intervention list with 1-click tailored drill dispatch and office hours scheduler

### 6. Admin Console & Platform Telemetry (`admin_console_user_management_system_telemetry/`)
* **Primary Persona:** Platform Administrator & Systems Operator
* **PRD Stories:** US-09, US-10, US-11, FR-801 to FR-807
* **Key Features:**
  - A/B Experiment #04 switchboard: Rule-Based (Arm A) vs Embedding-Hybrid Vector Engine (Arm B)
  - Zero-downtime hot-swap and emergency kill-switch (FR-807)
  - GDPR-compliant direct user credential generator modal (FR-104)
  - Real-time p95 recommendation latency and vector store sync telemetry

---

## 🎨 Design System: Academic Precision (`academic_precision/DESIGN.md`)

* **Primary Color:** `#070235` (Deep Navy) — Navigational anchors and high-emphasis typography
* **Primary Container:** `#1e1b4b` (Dark Slate Indigo) — Active tab and modal containers
* **Secondary Color:** `#006c4a` (Academic Mint) — Mastery milestones, positive trends, and passing states
* **Secondary Container:** `#82f5c1` (Light Mint Accent)
* **Tertiary Color:** `#cf7100` (Warm Amber) — Developing competencies and active review cycles
* **Error / Critical:** `#ba1a1a` — High-priority intervention flags and diagnostic bottlenecks
* **Surface Background:** `#f8f9ff` — Clean, high-legibility canvas
* **Typography:** Plus Jakarta Sans (Headings & Display), Inter (Body & Labels)
* **Iconography:** Material Symbols Outlined

---

## 🚀 How to Run & View

### Option 1: Direct File Open
Open `frontend/index.html` directly in any modern browser (Chrome, Edge, Firefox, Safari).

### Option 2: Local HTTP Server (Python)
From the project root:
```bash
python -m http.server 3000 --directory frontend
```
Then visit `http://localhost:3000` in your browser.

### Option 3: Node / NPX Serve
```bash
npx serve frontend
```

