# Software Requirements Specification: Personalized Learning Path Recommender for Online Education

Oct 22, 2026 · @rishu

Version 1.0 draft, structured after IEEE 830 / ISO/IEC/IEEE 29148. It specifies what the system must do; the companion PRD explains why.

## 1. Introduction

### 1.1 Purpose

This document specifies the software requirements for the Personalized Learning Path Recommender for Online Education. It is written for developers, testers, instructors and project evaluators, and is the baseline for design, implementation and testing.

### 1.2 Scope

The system analyzes a learner's quiz performance and engagement patterns and recommends a personalized sequence of learning content.

- **In scope:** knowledge model per learner and topic; recommendation engine; adaptive quizzing; learner and instructor progress dashboards; A/B testable recommendation strategies; basic account, role and content-tagging management.
- **Out of scope (v1):** authoring course content, live video or tutoring, payments and certificates, native mobile apps, free-text answer grading.

### 1.3 Definitions and abbreviations

| Term | Meaning |
| --- | --- |
| Mastery score | Estimate between 0 and 1 of how well a learner knows a topic |
| Knowledge model | Component that stores and updates mastery per learner and topic |
| Learning path | Ordered sequence of content items recommended to a learner |
| Strategy | A recommendation algorithm behind a common interface (rules, embeddings, collaborative filtering) |
| Arm | One variant of an A/B experiment, tied to one strategy and its parameters |
| Cold start | A learner or content item with no history yet |
| Adaptive quiz | Quiz whose next question difficulty depends on previous answers |
| SRS / PRD | Software requirements specification / product requirements document |
| RBAC | Role-based access control |

### 1.4 References

- IEEE 830-1998 and ISO/IEC/IEEE 29148:2018, requirements specification standards.
- Companion document: PRD for the Personalized Learning Path Recommender (goals, personas, user stories US-01 to US-12).

### 1.5 Document conventions

Requirements use "shall" and carry unique IDs: FR for functional, NFR for non-functional. Priority is M (must), S (should) or C (could). Default parameter values are initial settings that administrators can change.

## 2. Overall description

### 2.1 Product perspective

&#91;embedded content: system architecture · 4 layers\]

The system is a self-contained web application. Clients talk only to the API gateway; services never expose themselves directly. The recommender sits behind a strategy interface so that algorithms can be swapped and A/B tested without changing clients.

### 2.2 Product functions

- Track per-topic mastery for each learner.
- Recommend a personalized sequence of content.
- Adapt quiz difficulty from performance.
- Show progress to learners and instructors.
- Run A/B tests across recommendation strategies.

### 2.3 User classes

| Class | Description | Technical skill |
| --- | --- | --- |
| Learner | Takes quizzes and follows the recommended path | Basic web use |
| Instructor | Monitors class progress and at-risk learners | Basic web use |
| Administrator | Tags content, configures strategies and experiments | Moderate |

### 2.4 Operating environment

Modern desktop and mobile browsers (current and previous major versions of Chrome, Firefox, Safari, Edge); server side runs on a Linux host or container platform.

### 2.5 Design and implementation constraints

- Every recommendation must be explainable with a one-line reason.
- Learner data is personal data; access follows role-based rules.
- Recommendation strategies must implement one common interface.

### 2.6 Assumptions and dependencies

- A course catalog of lessons and quizzes exists or is seeded.
- Content can be tagged by topic, difficulty and prerequisites.
- Learners authenticate with an account before any tracking happens.

## 3. External interface requirements

| ID | Interface | Requirement |
| --- | --- | --- |
| EI-1 | User interface | A responsive web interface shall provide: login, course home with the recommended path, quiz player, learner dashboard, instructor dashboard and admin console. |
| EI-2 | User interface | The interface shall meet WCAG 2.1 level AA and work from a 360 px wide screen up. |
| EI-3 | Software: API | Clients shall use a versioned REST API exchanging JSON; every endpoint except login and registration shall require an authenticated token. |
| EI-4 | Software: database | The services shall access a relational database for structured data and an append-only event log for interaction events. |
| EI-5 | Software: LMS (optional) | If the system is embedded in an existing learning platform, it shall accept launches through the LTI standard. Decision pending in the PRD open questions. |
| EI-6 | Hardware | No special hardware. Clients need a modern browser; the server runs on a standard Linux host or container. |
| EI-7 | Communication | All traffic shall use HTTPS with TLS 1.2 or later. |

## 4. Functional requirements

Each module lists its requirements, priority and the PRD user story it traces to.

### 4.1 Accounts and access (FR-1xx)

| ID | Requirement | Pri | Traces to |
| --- | --- | --- | --- |
| FR-101 | The system shall let a user register and log in with email and password. | M | All |
| FR-102 | The system shall support three roles: learner, instructor, administrator. | M | US-07, US-09 |
| FR-103 | The system shall restrict each role to its own functions; a learner sees only their own data and an instructor only their own courses. | M | US-07, US-08 |
| FR-104 | The system shall record the learner's consent before tracking activity. | M | Privacy |

### 4.2 Content management (FR-2xx)

| ID | Requirement | Pri | Traces to |
| --- | --- | --- | --- |
| FR-201 | An administrator shall create, edit and retire courses, topics, content items and quiz questions. | M | US-09 |
| FR-202 | Each content item shall carry topic, difficulty (1 to 5), type, estimated duration and prerequisite topics. | M | US-09 |
| FR-203 | The system shall report content items missing required tags. | S | US-09 |

### 4.3 Knowledge model (FR-3xx)

| ID | Requirement | Pri | Traces to |
| --- | --- | --- | --- |
| FR-301 | The system shall keep a mastery score (0 to 1) and a confidence value for every learner-topic pair. | M | US-02 |
| FR-302 | The system shall update mastery after each graded attempt, before the next recommendation or question is served. | M | US-02, US-04 |
| FR-303 | The system shall initialize mastery from the diagnostic quiz, or from a default prior when none exists. | M | US-01 |
| FR-304 | The system shall weight recent attempts more than older ones. | S | US-02 |
| FR-305 | The system shall decay mastery for topics not practiced for a configurable period. | S | US-03 |
| FR-306 | The system shall label each topic weak, developing or strong using configurable thresholds (default: weak below 0.40, strong 0.80 or above). | M | US-02 |
| FR-307 | The system shall log engagement events (content opened, completed, skipped, time on task, quiz answered) and derive per-learner completion rate, skip rate and average session time. | M | US-03, US-06 |

### 4.4 Recommendation engine (FR-5xx)

| ID | Requirement | Pri | Traces to |
| --- | --- | --- | --- |
| FR-501 | On request, the system shall return an ordered list of the next N content items for a learner (default N = 5). | M | US-03 |
| FR-502 | The system shall not recommend items already completed, unless a review is due for a weak topic. | M | US-03 |
| FR-503 | The system shall not recommend an item whose prerequisite topics are still weak. | M | US-03 |
| FR-504 | The system shall rank candidates by the weighted score defined in section 7.2. | M | US-03 |
| FR-505 | The system shall attach a one-line, human-readable reason to every recommendation. | M | US-03 |
| FR-506 | The system shall implement every strategy behind one common interface: rule-based (MVP), embeddings plus rules, collaborative filtering. | M | US-10 |
| FR-507 | The embeddings strategy shall compute content similarity from title, description and tags. | S | US-03 |
| FR-508 | The collaborative strategy shall use paths that similar learners completed successfully. | C | US-03 |
| FR-509 | The system shall let a learner dismiss a recommendation and shall not re-suggest it for a configurable period. | S | US-05 |
| FR-510 | For a learner with no history, the system shall fall back to diagnostic results, or to entry-level content. | M | US-01 |

### 4.5 Adaptive quizzing (FR-6xx)

| ID | Requirement | Pri | Traces to |
| --- | --- | --- | --- |
| FR-601 | The system shall offer a diagnostic quiz covering every topic when a learner joins a course. | M | US-01 |
| FR-602 | The system shall choose the next question's difficulty from current mastery and recent answers, stepping up after consecutive correct answers and down after consecutive incorrect ones (section 7.3). | M | US-04 |
| FR-603 | The system shall not repeat a question within one quiz session. | M | US-04 |
| FR-604 | The system shall store every attempt with correctness, time taken and timestamp. | M | US-02 |
| FR-605 | The system shall end a quiz when mastery confidence passes a threshold or a maximum length is reached. | S | US-04 |
| FR-606 | The system shall recalibrate question difficulty from aggregate response data. | C | US-04 |

### 4.6 Dashboards (FR-7xx)

| ID | Requirement | Pri | Traces to |
| --- | --- | --- | --- |
| FR-701 | The learner dashboard shall show mastery per topic, recommended next items, completion and time spent. | M | US-02, US-06 |
| FR-702 | The instructor dashboard shall show a class mastery heatmap by topic, average completion and an at-risk learner list with configurable criteria. | M | US-07 |
| FR-703 | An instructor shall open one learner's attempt and activity history. | S | US-08 |
| FR-704 | Dashboards shall filter by course, topic and date range. | S | US-07 |
| FR-705 | A user shall export their visible report as CSV or PDF. | C | US-12 |

### 4.7 A/B testing (FR-8xx)

| ID | Requirement | Pri | Traces to |
| --- | --- | --- | --- |
| FR-801 | An administrator shall create an experiment with a name, arms (strategy and parameters), allocation split, primary metric and start and stop dates. | M | US-10 |
| FR-802 | The system shall assign each learner to one arm at random and keep that assignment fixed for the experiment. | M | US-10 |
| FR-803 | The system shall log each recommendation with its experiment and arm. | M | US-10 |
| FR-804 | The system shall compute per arm: recommendation acceptance rate, 8-week completion rate and post-test score gain. | M | US-10 |
| FR-805 | The system shall report significance and a confidence interval for each metric. | S | US-10 |
| FR-806 | The system shall pause an experiment automatically if a guardrail metric worsens beyond its limit. | S | US-10 |
| FR-807 | An administrator shall switch a strategy on or off without redeploying. | S | US-11 |

## 5. Data requirements

### 5.1 Entities

| Entity | Key attributes | Belongs to / links |
| --- | --- | --- |
| User | user\_id (PK), email, role, consent\_at | Parent of Attempt, MasteryScore, InteractionEvent, Recommendation, ExperimentAssignment |
| Course | course\_id (PK), title | Parent of Topic |
| Topic | topic\_id (PK), course\_id (FK), name, prerequisite topic IDs | Parent of ContentItem, Question |
| ContentItem | content\_id (PK), topic\_id (FK), type, difficulty 1 to 5, duration | Appears in Recommendation, InteractionEvent |
| Question | question\_id (PK), topic\_id (FK), difficulty, correct answer | Answered in Attempt |
| Attempt | attempt\_id (PK), user\_id (FK), question\_id (FK), correct, time taken, answered\_at | Feeds MasteryScore |
| MasteryScore | user\_id + topic\_id (composite PK), score, confidence, updated\_at | One row per learner and topic |
| InteractionEvent | event\_id (PK), user\_id (FK), content\_id (FK), event type, duration, timestamp | Source of engagement features |
| Recommendation | rec\_id (PK), user\_id (FK), content\_id (FK), arm\_id (FK), rank, reason, shown\_at, outcome | Outcome: accepted, dismissed or ignored |
| Experiment | experiment\_id (PK), name, primary metric, status, start and end | Parent of Arm |
| Arm | arm\_id (PK), experiment\_id (FK), strategy, parameters, allocation share | Used by Recommendation |
| ExperimentAssignment | user\_id + experiment\_id (composite PK), arm\_id (FK), assigned\_at | Fixes a learner's arm |

### 5.2 Relationships

- Course 1 to N Topic; Topic 1 to N ContentItem; Topic 1 to N Question.
- User 1 to N Attempt; Question 1 to N Attempt.
- User N to M Topic through MasteryScore.
- User 1 to N Recommendation; ContentItem 1 to N Recommendation.
- Experiment 1 to N Arm; User N to M Experiment through ExperimentAssignment.

### 5.3 Data rules

- A learner's personal data shall be deleted or anonymized on request.
- Events older than a configurable retention period shall be aggregated, then removed. The period is an open question for the institution.

## 6. Non-functional requirements

Sizing figures marked (assumed) are starting points to confirm with the institution.

| ID | Category | Requirement | Verified by |
| --- | --- | --- | --- |
| NFR-01 | Performance | A recommendation request shall return within 500 ms at the 95th percentile with 1,000 concurrent learners (assumed). | Load test |
| NFR-02 | Performance | The instructor dashboard shall load within 3 seconds for a class of 500 learners. | Load test |
| NFR-03 | Performance | A mastery update shall be visible to the next request within 1 second of the attempt. | Integration test |
| NFR-04 | Scalability | The API and services shall scale horizontally; the system shall support 10,000 registered learners (assumed). | Load test, review |
| NFR-05 | Security | Passwords shall be stored using a salted adaptive hash; sessions shall expire after inactivity. | Review, security test |
| NFR-06 | Security | The system shall enforce role-based access on every endpoint and validate all input against the OWASP Top 10 risks. | Security test |
| NFR-07 | Privacy | The system shall collect only data needed for recommendations, honor deletion requests and comply with applicable data-protection law. | Audit |
| NFR-08 | Reliability | Monthly availability shall be at least 99.5% (assumed); if a strategy fails, the system shall fall back to the rule-based strategy. | Monitoring, fault test |
| NFR-09 | Reliability | Data shall be backed up daily and restorable. | Restore drill |
| NFR-10 | Usability | A new learner shall complete the diagnostic quiz without instructions; the UI shall meet WCAG 2.1 AA. | Usability test, audit |
| NFR-11 | Explainability | Every recommendation shall show a reason a learner can read in under 5 seconds. | Demonstration |
| NFR-12 | Maintainability | New strategies shall be added by implementing one interface, with no change to clients; core logic shall have at least 70% unit-test coverage. | Code review, coverage report |
| NFR-13 | Configurability | Thresholds, weights and learning rates shall be changeable without redeploying. | Demonstration |
| NFR-14 | Portability | The system shall run in containers on any Linux host. | Deployment test |

## 7. Algorithms and models

The MVP uses simple, explainable formulas. Values below are initial defaults, tunable by administrators.

### 7.1 Mastery update

After each graded attempt on a question of difficulty d (scaled 0 to 1), the learner's mastery m for that topic moves toward the observed outcome y (1 correct, 0 incorrect).

```latex
p_t = \sigma\big(\beta\,(m_t - d)\big), \qquad m_{t+1} = \mathrm{clip}\big(m_t + \eta\,(y_t - p_t),\,0,\,1\big)
```

Idle topics decay with time since last practice:

```latex
m(\Delta t) = m_{\text{last}}\; e^{-\lambda\,\Delta t}
```

### 7.2 Recommendation ranking

Each eligible content item i is scored; the top N are returned with a reason.

```latex
S(i) = w_1\,\text{gap}(i) + w_2\,\text{fit}(i) + w_3\,\text{ready}(i) + w_4\,\text{eng}(i)
```

| Term | Meaning | Range |
| --- | --- | --- |
| gap(i) | 1 minus mastery of the item's topic: bigger for weaker topics | 0 to 1 |
| fit(i) | Closeness of item difficulty to the learner's mastery plus a small stretch | 0 to 1 |
| ready(i) | Lowest mastery among the item's prerequisite topics | 0 to 1 |
| eng(i) | Learner's historical completion rate for this content type | 0 to 1 |

### 7.3 Adaptive difficulty

Target difficulty is the current mastery plus a stretch: d\* = clip(m + δ, 0, 1). Step the target up one level after consecutive correct answers and down one level after consecutive incorrect ones.

| Parameter | Symbol | Default |
| --- | --- | --- |
| Learning rate | η | 0.10 |
| Sensitivity slope | β | 4 |
| Decay rate per day | λ | 0.01 |
| Ranking weights | w1, w2, w3, w4 | 0.4, 0.3, 0.2, 0.1 |
| Stretch | δ | 0.10 |
| Step up after | correct in a row | 3 |
| Step down after | incorrect in a row | 2 |

For the embeddings and collaborative strategies (FR-507, FR-508), the similarity score replaces or is blended into fit(i); the interface and output stay the same.

## 8. Use cases and acceptance criteria

### UC-01 Take the diagnostic quiz (FR-601, FR-303)

- **Actor:** learner. **Precondition:** enrolled in a course, consent given.
- **Main flow:** 1) Learner starts the diagnostic. 2) System serves questions across all topics. 3) Learner answers. 4) System stores attempts and sets initial mastery per topic. 5) System shows the first recommended path.
- **Acceptance:** Given a new learner, when the diagnostic ends, then every topic has a mastery score and at least one recommendation is shown.

### UC-02 Follow the recommended path (FR-501 to FR-505)

- **Actor:** learner. **Precondition:** at least one mastery score exists.
- **Main flow:** 1) Learner opens the course home. 2) System returns the top N items with reasons. 3) Learner opens an item; the system logs the event. 4) Learner may dismiss an item (FR-509).
- **Alternate:** no history exists, so the fallback in FR-510 applies.
- **Acceptance:** Given weak topic T, when the learner requests recommendations, then the list includes items for T, excludes items with weak prerequisites, and each item shows a reason.

### UC-03 Take an adaptive quiz (FR-602 to FR-605)

- **Actor:** learner.
- **Main flow:** 1) System selects a question at the target difficulty. 2) Learner answers. 3) System updates mastery and the next target difficulty. 4) Repeat until the stop rule fires.
- **Acceptance:** Given three correct answers in a row, the next question is one difficulty level higher; given two incorrect in a row, one level lower; no question repeats in a session.

### UC-04 Review at-risk learners (FR-702, FR-703)

- **Actor:** instructor.
- **Main flow:** 1) Instructor opens the class dashboard. 2) System shows a topic heatmap and an at-risk list. 3) Instructor opens one learner's history.
- **Acceptance:** Given a learner who meets the configured at-risk criteria, the learner appears in the list; an instructor cannot view learners outside their own courses.

### UC-05 Run an A/B experiment (FR-801 to FR-806)

- **Actor:** administrator.
- **Main flow:** 1) Admin defines arms, split and primary metric. 2) System assigns learners at random, once. 3) System logs recommendations per arm. 4) Admin reads per-arm metrics with confidence intervals.
- **Acceptance:** Given a 50/50 split, each learner stays in one arm for the whole experiment, and a guardrail breach pauses it automatically.

## 9. Traceability matrix

Every PRD user story maps to requirements and a verification method.

| PRD story | Functional requirements | Non-functional | Verification |
| --- | --- | --- | --- |
| US-01 Diagnostic quiz | FR-601, FR-303, FR-510 | NFR-10 | UC-01 acceptance test |
| US-02 Strength per topic | FR-301, FR-302, FR-306, FR-604, FR-701 | NFR-03 | Unit tests on mastery update; dashboard check |
| US-03 Recommended next lesson | FR-501 to FR-505, FR-305, FR-307 | NFR-01, NFR-11 | UC-02 acceptance test; load test |
| US-04 Adaptive quizzes | FR-602, FR-603, FR-605 | NFR-03 | UC-03 acceptance test |
| US-05 Dismiss a recommendation | FR-509 | None | Functional test |
| US-06 Streaks and time spent | FR-307, FR-701 | None | Dashboard check |
| US-07 Class mastery and at-risk | FR-702, FR-704, FR-103 | NFR-02 | UC-04 acceptance test |
| US-08 Learner drill-down | FR-703, FR-103 | NFR-06 | Access-control test |
| US-09 Content tagging | FR-201, FR-202, FR-203 | None | Functional test |
| US-10 A/B experiments | FR-506, FR-801 to FR-806 | NFR-12 | UC-05 acceptance test |
| US-11 Strategy switch | FR-807 | NFR-13 | Demonstration |
| US-12 Export report | FR-705 | None | Functional test |
