# 🏥 Home Care Intelligence Hub

A production-grade data pipeline and analytics platform simulating care coordination workflows for home health patients —— built on the modern data stack.

## Problem Statement
When a patient is discharged from a hospital and referrerd to home health care, three things must align: the **referral get accepted**, the **payor authorizes the visit**, and a **clinician shows up on time**. If any one of these breaks down, the patient goes without care.

Most home health agencies track this across spreadsheets, EMR exports, and phone calls —— with no unified view of where referrals are stalling, which payors are slow to authorize, or which clinicians are over or underutilized.

**This project builds the data foundation that answers the three questions an operations director asks every Monday morning:**
1. Where are referrals dropping off? <em>(funnel leakage)
2. Which payors are delaying authorizations —— and by how much? <em>(revenue risk)</em>
3. Are we burning out our clinicians or leaving capacity on the table? <em>(workforce efficiency)</em>

## Architecture
<img width="361" height="596" alt="image" src="https://github.com/user-attachments/assets/85dbcb2d-898b-4f1e-8bc5-e33bb71f4a10" />

## Tech Stack
<img width="285" height="256" alt="image" src="https://github.com/user-attachments/assets/04e640fe-4692-4f26-a784-07b9d345bbc8" />

## Project Structure
<img width="371" height="893" alt="image" src="https://github.com/user-attachments/assets/caae81aa-4cae-4e4a-8c92-3353ac49fe55" />

## Data Model
<img width="371" height="177" alt="image" src="https://github.com/user-attachments/assets/eb75f4a6-8bac-4411-9893-06fc250bfd10" />

## Mart Models (Analytics Layer)
mart_patient_referral_funnel Tracks patient progression from referral -> authorization -> first visit. Powers conversion rate analysis by referring provider and time period.

mart_payor_authorization_lag Calculates business-day lag between authorization submission and approval, grouped by payor. Surfaces which insurers are creating the most delays and patient-risk exposure.

mart_clinician_utilization Compares scheduled vs. completed visits against each clinician's weekly capacity. Flags over-utilization (burnout risk) and under-utilization (capacity opportunity).

## Data Quality
All dbt models are covered by:
- **Generic tests**: not_null, unique, accepted_values, relationships
- **Custom tests**: visit completion rate floor, authorization lag outlier detection
- **Elementary**: Row count anomaly monitoring with Slack alerting (simulated)

## HIPAA Considerations
⚠️ This project uses 100% synthetic data generated with the Faker library. No real patient data is used at any point.

In a production environment with real PHI, the following controls would apply:
<img width="585" height="274" alt="image" src="https://github.com/user-attachments/assets/15024468-2d69-4064-a827-598da7a13f40" />

Columns that would requir masking in production: patient_name, date_of_birth, address, insurance_member_id.

## Dashboard —— Key Metrics
<img width="637" height="238" alt="image" src="https://github.com/user-attachments/assets/85744bc4-fbce-4782-a8b1-acddb76be4e2" />

## Getting Started
**Prerequisites**
- Docker + Docker Compose
- Snowflake account (free trial at snowflake.com)
- Python 3.11+

## Local Setup
#### 1. Clone the repo
git clone https://github.com/sajanshergill/home-care-intelligence-hub.git
cd home-care-intelligence-hub

#### 2. Copy environment variables
cp .env.example .env
##### Fill in your Snowflake credentials in .env

#### 3. Generate synthetic data
python scripts/generate_synthetic_data.py

#### 4. Start services
docker-compose up -d

#### 5. Run dbt transformations
cd dbt
dbt deps
dbt run
dbt test

#### 6. Launch dashboard
cd ../dashboard
streamlit run app.py

## Running the Full Pipeline (Airflow)
#### Airflow UI available at http://localhost:8080
#### Username: admin | Password: admin (dev only)
#### Trigger DAG: home_care_daily_pipeline

## CI/CD
GitHub Actions runs on every pull request to main:
push to PR → lint (sqlfluff) → dbt compile → dbt test → pytest → build Docker image

## Roadmap

- Add real-time ingestion path via Kafka for visit status updates
- Implement dbt incremental models for large referral history tables
- Add ML-ready feature mart for authorization approval prediction
- Integrate Elementary Cloud for hosted observability dashboard
- Add data lineage visualization via dbt docs
