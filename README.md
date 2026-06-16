# ABOIA — Autonomous Business Operations Intelligence Agent

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org) [![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green)](https://fastapi.tiangolo.com) [![LangGraph](https://img.shields.io/badge/LangGraph-agentic-purple)](https://langchain-ai.github.io/langgraph/) [![LLM](https://img.shields.io/badge/LLM-Gemini-orange)](https://ai.google.dev)


> **Enterprise Safety & Evaluation Report**     
> For a deeper technical and operational analysis of ABOIA — including governance architecture, anomaly detection methodology, SLA lifecycle design, escalation policies, and enterprise scalability considerations — refer to the full [Technical Report](REPORT.md).

## 📌 Overview 

ABOIA is a governed agentic framework that transforms e-commerce KPI anomalies into prioritized, auditable, and operationally safe actions.

It combines:  
-   Statistical anomaly detection
-   LLM-based root cause reasoning (Gemini)
-   Deterministic validation guardrails
-   Risk-driven prioritization and SLA enforcement
-   Human-in-the-loop approval gates
-   Structured lifecycle execution with full observability

Rather than allowing the LLM to directly control execution, ABOIA separates probabilistic reasoning from deterministic governance. This enables the system to validate, prioritize, and safely route operational actions while preventing unsafe automation caused by unreliable or low-confidence AI reasoning.

The system is demonstrated using the Olist Brazilian E-Commerce Dataset, where raw transactional records are aggregated into daily business KPIs for anomaly detection, reasoning, and operational action simulation. Initial exploratory data analysis on the Olist dataset is available in [data/analysis/](data/analysis/).

![Consolidated Episode Timeline](assets/main_dashboard.png)

## 🧠 Why ABOIA Is Different

- Separates probabilistic LLM reasoning from deterministic governance and policy enforcement
- Enforces structured lifecycle transitions (approval → execution → SLA resolution)
- Prevents unsafe automation through governance-based escalation overrides
- Ensures idempotent and replay-safe action execution
- Maintains a complete audit trail across the operational lifecycle

## 📋 Table of Contents

- [Architecture](#-architecture)
- [Agent Pipeline](#-agent-pipeline)
- [Key Features](#-key-features)
- [Action Lifecycle State Machine](#-action-lifecycle-state-machine)
- [Approval & Risk Policy](#-approval--risk-policy)
- [Config-Driven Policy](#️-config-driven-policy)
- [LLM Reliability & Safety Design](#-llm-reliability--safety-design)
- [Agent Data Contracts](#-agent-data-contracts)
- [Project Structure](#-project-structure)
- [Setup & Installation](#-setup--installation)
- [Running the System](#-running-the-system)
- [API Reference](#-api-reference)
- [Notification System](#-notification-system)
- [Debugging & Observability](#-debugging--observability)
- [Tech Stack](#-tech-stack)
- [Summary](#-summary)


---

## 🏗 Architecture

ABOIA is built as three loosely coupled components: a FastAPI backend, a Streamlit dashboard, and a SQLite persistence layer for state tracking and lifecycle management. The core workflow is orchestrated using LangGraph:

```mermaid
graph TD
    Z[0. IngestionAgent: KPI Data Load] -->|Historical KPIs| A[1. MonitoringAgent: Statistical Detection]
    A -->|Detected Anomalies| B[2. ReasoningAgent: LLM + ReasoningValidator]
    B -->|Reasoning & Governance Scores| C[3. PlannerAgent: Action Planning, Risk Policy & Override Rules]
    
    C -->|Action Plan| D[(4. ActionAgent: SQLite & SLA Tracking)]
    D -.->|Requires Approval| E[Human-in-the-Loop UI]
    D -.->|Notifications| F[Slack Routing]
    D -.->|SLA Breach Alerts| G[Escalation Alerts]
```

The system operates as a daily batch simulation. Each execution processes KPIs for a single simulated date, persists the resulting state, and then advances to the next day. This ensures chronological isolation, preventing agents from accessing future telemetry data during anomaly detection and reasoning.

---

## 📊 Agent Pipeline

| Step / Node | Agent / Component | Inputs | Primary Outputs / Artifacts | Key Responsibility |
|:---:|:---|:---|:---|:---|
| **0️⃣** | **DataIngestionAgent** | Raw CSV transaction logs in `data/` | `daily_kpis` (Pandas DataFrame) | Loads and aggregates KPI data while enforcing timeline isolation and warmup rules. |
| **1️⃣** | **MonitoringAgent** | `daily_kpis` + historical KPI data | `metrics_df` + anomaly episodes | Runs statistical anomaly detection, seasonal analysis, and cross-metric correlation checks. |
| **2️⃣** | **ReasoningAgent** | `anomalies` + `metrics_df` | Structured LLM reasoning output + governance scorecard | Generates structured root-cause reasoning and validates responses using deterministic governance checks. |
| **3️⃣** | **PlannerAgent** | Reasoning output + Validation results | Persisted action_plan records | Maps diagnoses to predefined operational actions and applies governance override rules. |
| **4️⃣** | **ActionAgent** | `action_plan` | Ticket state updates + Slack notifications | Handles approvals, execution lifecycle management, and SLA tracking and escalation workflows. |

---

## 🛠 Key Features

- **Multi-method anomaly detection**: Rolling z-score, percentage change, IQR (global), EWMA, seasonal, and cross-metric correlation checks. Z-score and percentage-change thresholds are **auto-tuned per metric** using the 95th percentile of historical values.
- **LLM reasoning with deterministic guard-rails**: Gemini generates root cause and risk level assessments, while the `ReasoningValidator` evaluates outputs across four governance dimensions (**Metric Grounding**, **Analytical Depth**, **Risk Policy Alignment**, and **Confidence Parity**).
- **Three-tier priority system (P0/P1/P2)** driven by risk level, governance validation and escalation rules.
- **Human-in-the-loop approval gate**: High-risk or high-uncertainty actions require approval from a Business Head before execution.
- **Slack notification routing**: based on owner team (Marketing, Product, Engineering, Operations) and operational event type.
- **Full audit trail**: through structured NDJSON debug logs for every pipeline stage (`debug_output/`).
- **Idempotent lifecycle execution**: Re-running the lifecycle worker never re-executes completed actions or mutates terminal execution states.

---

## 🔄 Action Lifecycle State Machine

### Execution Lifecycle:

```mermaid
stateDiagram-v2 
    [*] --> pending_approval : approval required 
    [*] --> approved : no approval required 
    
    pending_approval --> approved 
    pending_approval --> rejected 
    
    approved --> in_progress 
    in_progress --> completed 
    in_progress --> failed 
    
    completed --> [*] 
    failed --> [*] 
    rejected --> [*]
```

![Action Plan](assets/actionplan1.png)
![Action Plan](assets/actionplan2.png)

### SLA tracking:

```mermaid
stateDiagram-v2 
    [*] --> active 
    active --> resolved 
    active --> breached : SLA deadline exceeded
```

- SLA tracking is maintained independently from execution state transitions.
- `rejected`, `failed`, and `completed` are terminal execution states.
- Completed, rejected, and failed actions all resolve SLA tracking.
- The lifecycle worker is idempotent and replay-safe.

![SLA](assets/sla.png)

---

## 🎯 Approval & Risk Policy

### Base Policy (Risk → Priority)

| Risk Level | Priority | SLA | Requires Approval |
|------------|----------|-----|------------------|
| `high` | **P0** | 4 hours | ✅ Always (Business Head) |
| `medium` | **P1** | 8 hours | ❌ Default No |
| `low` | **P2** | 24 hours | ❌ Default No |

![Governance Scorecard](assets/governance_scorecard.png)

### Confidence Signals
ABOIA maintains two independent confidence signals used during governance evaluation and escalation decisions:

| Signal | Source | Range | Description |
|--------|--------|-------|-------------|
| `anomaly_confidence` | Deterministic (system) | 0–100 | Statistical signal strength derived from anomaly severity, metric overlap, and affected KPIs |
| `reasoning_confidence` | LLM (Gemini) | 0–100 | LLM’s self-reported confidence in the generated root-cause analysis |

A large divergence between these signals (for example, strong statistical anomalies combined with low LLM confidence) triggers escalation to manual approval.

### Governance Escalation & Priority Overrides
When governance checks fail or confidence signals become unreliable, the `PlannerAgent` applies escalation rules that increase ticket priority and require human approval before execution:

| Escalation Override Rule | Trigger Condition | Governance Action |
| :--- | :--- | :--- |
| **Critical Validation Override** | `validation_severity == "critical"` | Priority escalated by one level + `requires_approval = True` |
| **Confidence Gap Override** | `abs(anomaly_confidence - reasoning_confidence) > 50` | `requires_approval = True` |
| **Unrecognized Playbook Override** | No matching action mapping found | Priority escalated by one level + `requires_approval = True` |
| **Low Overall Reasoning Override** | `overall_reasoning_score < 50` | Priority escalated by one level + `requires_approval = True` |
| **Weak Metric Grounding Override** | `grounding_score < 40` | `requires_approval = True` |
| **Risk Misalignment Override** | `risk_alignment_score < 60` | Priority escalated by one level + `requires_approval = True` |

---

## ⚙️ Configuration-Driven Orchestration

To keep operational logic separate from application code, KPI definitions, monitoring rules, governance policies, and action mappings are externalized through YAML configuration files under `config/`:

* `kpis.yaml`: Defines KPI aggregation rules, source columns, and derived metric formulas (e.g., `conversion_rate = orders / visits`).
* `monitoring.yaml`: Specifies the KPI metrics monitored by the anomaly detection pipeline.
* `risk_policy.yaml`: Stores risk-to-priority mappings, SLA targets, approval requirements, governance score weights, and escalation thresholds.
* `root_cause_action_map.yaml`: Maps LLM-generated root-cause keywords to predefined operational actions, ticket types, and owner teams.

---

## 🤖 LLM Reliability & Safety Design

The LLM integration layer is designed with reliability and safety safeguards to prevent workflow instability:

- Configurable timeout enforcement
- Automatic retries for transient failures (up to 3 total attempts)
- Deterministic JSON extraction from model output
- Structured fallback responses on repeated failure
- NDJSON debug logging for prompts and model outputs

If the LLM fails, the system safely degrades without interrupting the deterministic monitoring and governance pipeline.

This ensures the AI reasoning layer enhances — but never destabilizes — operational automation.

---

## 📐 Agent Data Contracts

Key input/output structures flowing through the pipeline:

### Monitoring Output — Anomaly Record
```json
{
  "date": "2024-01-15",
  "metric": "visits",
  "value": 1823.0,
  "type": "zscore",
  "score": 3.4
}
```
One record is generated per detected anomaly. Multiple monitoring methods may flag the same `(date, metric)` pair — these are deduplicated before episode construction.

---

### Reasoning Output — LLM Result
```json
{
  "root_cause": "Traffic drop from paid campaigns",
  "business_impact": "Revenue at risk due to reduced funnel entry",
  "risk_level": "high",
  "anomaly_confidence": 90,
  "reasoning_confidence": 85
}
```
Generated by Gemini and validated by `ReasoningValidator` before influencing downstream planning decisions.

---

### Action Plan — Planner Output
```json
{
  "generated_at": "2024-01-15T10:00:00",
  "risk_level": "high",
  "priority": "P0",
  "actions": [
    {
      "action_id": "uuid",
      "type": "investigation",
      "description": "Investigate traffic sources and ad campaigns",
      "owner": "Marketing Team",
      "priority": "P0",
      "sla_hours": 4,
      "requires_approval": true,
      "approval_role": "Business Head",
      "status": "pending"
    }
  ],
  "decision_trace": {
    "risk_level": "high",
    "anomaly_confidence": 90,
    "reasoning_confidence": 85,
    "validation_severity": "none",
    "confidence_gap": 5,
    "escalation_flags": [],
    "matched_keywords": ["traffic"]
  }
}
```
Produced deterministically from `risk_level` and governance escalation rules. No LLM involvement occurs at this stage.

---

## 📁 Project Structure

```
ABOIA/ 
├── app/ 
│ ├── agents/ # Core agent pipeline (ingestion, monitoring, reasoning, planning, execution) 
│ ├── graph/ # LangGraph workflow orchestration 
│ ├── api/ # FastAPI route handlers 
│ ├── services/ # LLM integration, validation, notifications, logging, auth 
│ ├── db/ # SQLite models and persistence layer 
│ ├── utils/ # KPI aggregation and validation utilities 
│ ├── main.py # FastAPI entrypoint 
│ └── state.py # Shared LangGraph AgentState 
│ 
├── config/ 
│ ├── kpis.yaml 
│ ├── monitoring.yaml 
│ ├── risk_policy.yaml 
│ └── root_cause_action_map.yaml 
│ 
├── data/
│ ├── raw/ # Raw Olist dataset CSVs
│ └── analysis/ # Exploratory data analysis notebook (EDA on KPI trends, dataset structure)
│
├── debug_output/ # NDJSON pipeline traces and validation logs 
├── logs/ # Application logs 
├── .env.example # Environment variable template 
└── requirements.txt
```

---

## 📦 Setup & Installation

### Prerequisites

- Python 3.11+
- A Gemini API key (from [Google AI Studio](https://aistudio.google.com))
- (Optional) Slack Bot Token for notification routing

### 1. Clone the Repository & Create a Virtual Environment

```bash
git clone <your-repo-url>
cd ABOIA
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Required
API_KEY=your_api_key_here

GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=model_name_here

# Slack notifications
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_MARKETING_CHANNEL=#marketing-alerts
SLACK_PRODUCT_CHANNEL=#product-alerts
SLACK_ENGINEERING_CHANNEL=#engineering-alerts
SLACK_OPERATIONS_CHANNEL=#operations-alerts
SLACK_APPROVAL_CHANNEL=#approvals
SLACK_ALERT_CHANNEL=#sla-alerts
```

### 4. Add Dataset Files

The project was developed and evaluated using the **Olist Brazilian E-Commerce Dataset**. Raw transactional CSV files should be placed inside `data/raw/`. The ingestion pipeline aggregates these records into daily KPI windows for downstream monitoring and reasoning.

---

## 🚀 Running the System

ABOIA can be executed either through the interactive Streamlit dashboard (recommended for visualization and approvals) or directly through REST API endpoints.

### Option A: Streamlit Dashboard

1. **Start the FastAPI Backend:**
   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

2. **Start the Streamlit Frontend (in a separate terminal):**
   ```bash
   streamlit run streamlit_app/dashboard.py
   ```

3. Open the local dashboard URL displayed in the terminal (typically `http://localhost:8501`).

---

### Option B: REST API Execution

1. **Start the FastAPI Backend**
   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

2. **Run the Agent Pipeline for a Simulated Day**
   ```bash
   curl -X POST http://127.0.0.1:8000/v1/run_day \
     -H "x-api-key: your_api_key_here" \
     -H "Content-Type: application/json" \
     -d '{"start_date": "2018-08-27", "end_date": "2018-08-27"}'
   ```
   This executes the full workflow for a single simulated day:

   `Ingestion → Monitoring → Reasoning → Planning → Action`

3. **Run the Lifecycle Worker**
   ```bash
   curl -X POST http://127.0.0.1:8000/v1/system/run_lifecycle \
     -H "x-api-key: your_api_key_here"
   ```
   Use this endpoint after approving actions to process execution workflows, lifecycle transitions, and SLA auditing.

---

### Execution Model

The pipeline currently executes synchronously inside the HTTP request lifecycle. This design preserves deterministic execution semantics and simplifies debugging for development and demonstration environments.

In production deployments, the workflow can be offloaded to background workers (e.g., task queues or asynchronous executors) to prevent long-running LLM calls from blocking request threads.

The architecture cleanly separates orchestration, state transitions, and lifecycle execution, making future migration to asynchronous execution straightforward without requiring changes to core business logic.

---

## 📚 API Reference

The FastAPI backend exposes REST endpoints for pipeline execution, approvals, lifecycle orchestration, SLA monitoring, and observability.

### Core Endpoint Groups

| Category | Example Endpoints | 
|--------|-------------|
| Pipeline Execution | `POST /v1/run_day`, `POST /v1/run_simulation` |
| Action Management | `GET /v1/actions/`, `GET /v1/actions/{action_id}` | 
| Approvals | `GET /v1/approvals/pending`, `POST /approve`, `POST /reject` |
| Episodes & Reasoning | `GET /v1/episodes/` |
| SLA Monitoring | `GET /v1/sla/breached`, `GET /v1/sla/active` |
| System Operations | `GET /v1/system/health`, `POST /v1/system/run_lifecycle` |

### Example Queries

GET /v1/actions/?status=pending_approval  
GET /v1/actions/?priority=P0&owner=Marketing Team    
GET /v1/actions/?sla_status=breached

### API Design Notes

- All public endpoints are versioned under `/v1`
- List endpoints support `limit` and `offset` pagination
- State-changing routes require `x-api-key` authentication
- Read-only observability endpoints remain public for monitoring use cases

### Interactive API docs

 `http://127.0.0.1:8000/docs`

---

## 📢 Notification System

Slack notifications are dispatched for the following operational events:

| Event | Notification Routing |
|-------|----------|
| `created` | Owner team channel |
| `approval_required` | Owner team channel + centralized approval channel |
| `approved` | Owner team channel + centralized approval channel |
| `rejected` | Owner team channel + centralized approval channel |
| `completed` | Owner team channel |
| `failed` | Owner team channel |
| `sla_breached` | centralized alert channel |

If `SLACK_BOT_TOKEN` is not configured, notification delivery is safely skipped without interrupting workflow execution.

---

## 🔎 Debugging & Observability

### Structured Logging

All agent activity is logged to both `logs/system.log` and the application console:
```
2026-02-23 11:43:08 | INFO | ABOIA | >>> ENTER PlannerAgent.run
```

Set `LOG_LEVEL=DEBUG` in `.env` to enable verbose execution traces.

### NDJSON Debug Traces

Each pipeline stage emits structured debug artifacts to `debug_output/` for observability and replay analysis:

| File | Description |
|------|----------|
| `daily_kpis.csv` | Aggregated KPI windows |
| `anomalies.json` | Raw anomaly signals |
| `deduplicated_anomalies.json` | Consolidated anomaly episodes |
| `episode_reasoning.ndjson` | Per-episode reasoning summaries and outputs |
| `planner_agent.ndjson` | Final action plans and escalation traces |
| `llm_calls.ndjson` | LLM prompts, raw outputs, and parsed responses |
| `reasoning_validation.ndjson` | Governance validation results |
| `node_state.ndjson` | LangGraph node input/output state snapshots |

--- 

## 🧩 Tech Stack

-   Python 3.11+
-   FastAPI
-   LangGraph
-   SQLAlchemy + SQLite (development environment)
-   Gemini (Google AI Studio)
-   Slack Bot API
-   YAML-driven configuration for KPIs, monitoring rules, governance policies, and action mappings

---

## 🏁 Summary

ABOIA is a governed agentic operations framework that combines statistical anomaly detection, LLM-backed root-cause reasoning, and deterministic governance to transform business KPI anomalies into structured operational workflows.

The system emphasizes safe automation through human-in-the-loop approvals, governance-based escalation policies, lifecycle-aware execution, and end-to-end observability across every decision stage.