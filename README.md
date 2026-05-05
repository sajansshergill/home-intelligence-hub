# 🏥 Home Care Intelligence Hub

A production-grade data pipeline and analytics platform simulating care coordination workflows for home health patients —— built on the modern data stack.

## Problem Statement
When a patient is discharged from a hospital and referrerd to home health care, three things must align: the **referral get accepted**, the **payor authorizes the visit**, and a **clinician shows up on time**. If any one of these breaks down, the patient goes without care.

Most home health agencies track this across spreadsheets, EMR exports, and phone calls —— with no unified view of where referrals are stalling, which payors are slow to authorize, or which clinicians are over or underutilized.

**This project builds the data foundation that answers the three questions an operations director asks every Monday morning:**
1. Where are referrals dropping off? <em>(funnel leakage)
2. Which payors are delaying authorizations —— and by how much? <em>(revenue risk)
3. Are we burning out our clinicians or leaving capacity on the table? <em>(workforce efficiency)

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





