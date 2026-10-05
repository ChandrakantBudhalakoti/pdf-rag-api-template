# RAG Evaluation Report

- Run at: 2026-09-30 05:57 UTC
- Provider: `gemini` | Embedding model: `gemini-embedding-001` | LLM: `gemini-2.5-flash-lite` | chunk size/overlap: 1000/200 | top_k: 4
- **Automated accuracy: 10/10 = 100%** (target 85%: PASSED)
- Expected source document retrieved: 9/9 answerable questions (informational only, not part of accuracy)
- API errors during the run: 0 (counted as incorrect)

Automated scoring checks that each answer contains the required facts (see `criteria`). The full answers are included below so they can be verified manually against the PDFs.

| # | Result | Question | Reason |
|---|--------|----------|--------|
| 1 | PASS | In which year and in which city was Brightleaf Analytics founded? | all required facts present |
| 2 | PASS | How much does the LeafSight Growth plan cost? | all required facts present |
| 3 | PASS | How many days of paid annual leave do full-time employees get, and how many unused days can be carried forward to the next year? | all required facts present |
| 4 | PASS | What is the notice period for an employee who has already completed probation? | all required facts present |
| 5 | PASS | What is the yearly learning and development budget per employee? | all required facts present |
| 6 | PASS | Can a customer get a refund on an annual subscription? | all required facts present |
| 7 | PASS | If LeafSight's monthly uptime was 98.5%, what service credit would a customer be eligible for? | all required facts present |
| 8 | PASS | What is the first-response time for a Priority 1 (P1) incident? | all required facts present |
| 9 | PASS | Who is the CEO of Brightleaf Analytics, and how many days of paid sick leave do its employees get per year? | all required facts present |
| 10 | PASS | What was Brightleaf Analytics' total revenue in 2024? | correctly reported that the answer is not in the documents |

## Q1 - PASS (direct fact / date)

**Question:** In which year and in which city was Brightleaf Analytics founded?

**Expected:** It was founded in March 2016 in Pune, India.  
**Expected source:** brightleaf_company_profile.pdf, page 1

**Criteria:** Answer must state both the year 2016 and the city Pune.

**Pipeline answer:** Brightleaf Analytics was founded in March 2016 in Pune, India.

**Cited sources:** brightleaf_company_profile.pdf, page 1  
**Retrieved chunks:** brightleaf_company_profile.pdf, page 1 (d=0.267), brightleaf_support_and_refund_policy.pdf, page 2 (d=0.297), brightleaf_company_profile.pdf, page 2 (d=0.303), brightleaf_support_and_refund_policy.pdf, page 1 (d=0.322)

**Scoring:** all required facts present (14.5s)

## Q2 - PASS (numeric (price))

**Question:** How much does the LeafSight Growth plan cost?

**Expected:** US$99 per user per month.  
**Expected source:** brightleaf_company_profile.pdf, page 2

**Criteria:** Answer must give the price 99 (US dollars) and that it is charged per user.

**Pipeline answer:** The LeafSight Growth plan costs US$99 per user per month. Customers who choose annual billing instead of monthly billing receive a 15% discount on this plan. A 14-day free trial of the Growth plan is available.

**Cited sources:** brightleaf_company_profile.pdf, page 2  
**Retrieved chunks:** brightleaf_company_profile.pdf, page 2 (d=0.214), brightleaf_company_profile.pdf, page 1 (d=0.326), brightleaf_support_and_refund_policy.pdf, page 2 (d=0.352), brightleaf_support_and_refund_policy.pdf, page 1 (d=0.353)

**Scoring:** all required facts present (14.6s)

## Q3 - PASS (numeric, two facts from one passage)

**Question:** How many days of paid annual leave do full-time employees get, and how many unused days can be carried forward to the next year?

**Expected:** 24 days of paid annual leave per calendar year; up to 8 unused days can be carried forward.  
**Expected source:** brightleaf_employee_handbook.pdf, page 1

**Criteria:** Answer must contain both 24 (annual leave days) and 8 (carry-forward days).

**Pipeline answer:** Full-time employees receive 24 days of paid annual leave per calendar year. Up to 8 unused annual leave days can be carried forward to the next calendar year.

**Cited sources:** brightleaf_employee_handbook.pdf, page 1  
**Retrieved chunks:** brightleaf_employee_handbook.pdf, page 1 (d=0.318), brightleaf_employee_handbook.pdf, page 2 (d=0.351), brightleaf_support_and_refund_policy.pdf, page 2 (d=0.427), brightleaf_company_profile.pdf, page 1 (d=0.433)

**Scoring:** all required facts present (9.8s)

## Q4 - PASS (direct fact (disambiguation))

**Question:** What is the notice period for an employee who has already completed probation?

**Expected:** 60 days.  
**Expected source:** brightleaf_employee_handbook.pdf, page 2

**Criteria:** Answer must state 60 days (the 30-day period applies only during probation).

**Pipeline answer:** The notice period for an employee who has completed probation is 60 days.

**Cited sources:** brightleaf_employee_handbook.pdf, page 2  
**Retrieved chunks:** brightleaf_employee_handbook.pdf, page 2 (d=0.286), brightleaf_employee_handbook.pdf, page 1 (d=0.389), brightleaf_support_and_refund_policy.pdf, page 2 (d=0.409), brightleaf_support_and_refund_policy.pdf, page 1 (d=0.424)

**Scoring:** all required facts present (11.6s)

## Q5 - PASS (numeric (amount))

**Question:** What is the yearly learning and development budget per employee?

**Expected:** US$1,200 per employee per calendar year.  
**Expected source:** brightleaf_employee_handbook.pdf, page 2

**Criteria:** Answer must state 1,200 (US dollars).

**Pipeline answer:** Each employee has a learning and development budget of US$1,200 per calendar year.

**Cited sources:** brightleaf_employee_handbook.pdf, page 2  
**Retrieved chunks:** brightleaf_employee_handbook.pdf, page 2 (d=0.341), brightleaf_company_profile.pdf, page 2 (d=0.394), brightleaf_employee_handbook.pdf, page 1 (d=0.409), brightleaf_company_profile.pdf, page 1 (d=0.418)

**Scoring:** all required facts present (12.5s)

## Q6 - PASS (policy condition)

**Question:** Can a customer get a refund on an annual subscription?

**Expected:** Yes, a full refund if the annual subscription is cancelled within 30 days of purchase; after 30 days there is no refund, but the service stays active until the end of the paid term.  
**Expected source:** brightleaf_support_and_refund_policy.pdf, page 2

**Criteria:** Answer must mention a full refund and the 30-day window after purchase.

**Pipeline answer:** Yes, annual subscriptions receive a full refund if they are cancelled within 30 days of purchase.

**Cited sources:** brightleaf_support_and_refund_policy.pdf, page 2  
**Retrieved chunks:** brightleaf_support_and_refund_policy.pdf, page 2 (d=0.247), brightleaf_support_and_refund_policy.pdf, page 1 (d=0.333), brightleaf_company_profile.pdf, page 2 (d=0.377), brightleaf_support_and_refund_policy.pdf, page 1 (d=0.380)

**Scoring:** all required facts present (11.8s)

## Q7 - PASS (reasoning over a table of ranges)

**Question:** If LeafSight's monthly uptime was 98.5%, what service credit would a customer be eligible for?

**Expected:** A 25% service credit (uptime from 95.0% up to but not including 99.0%).  
**Expected source:** brightleaf_support_and_refund_policy.pdf, page 1

**Criteria:** Answer must identify the 25% credit tier; 98.5% falls in the 95.0%-99.0% band.

**Pipeline answer:** A customer would be eligible for a 25% service credit if LeafSight's monthly uptime was from 95.0% up to (but not including) 99.0%.

**Cited sources:** brightleaf_support_and_refund_policy.pdf, page 1  
**Retrieved chunks:** brightleaf_support_and_refund_policy.pdf, page 1 (d=0.254), brightleaf_support_and_refund_policy.pdf, page 1 (d=0.280), brightleaf_company_profile.pdf, page 2 (d=0.305), brightleaf_support_and_refund_policy.pdf, page 2 (d=0.350)

**Scoring:** all required facts present (11.9s)

## Q8 - PASS (direct fact (time))

**Question:** What is the first-response time for a Priority 1 (P1) incident?

**Expected:** Within 1 hour, 24/7.  
**Expected source:** brightleaf_support_and_refund_policy.pdf, page 1

**Criteria:** Answer must state 1 hour.

**Pipeline answer:** The first response time for a Priority 1 (P1) incident is within 1 hour, 24/7.

**Cited sources:** brightleaf_support_and_refund_policy.pdf, page 1  
**Retrieved chunks:** brightleaf_support_and_refund_policy.pdf, page 1 (d=0.247), brightleaf_support_and_refund_policy.pdf, page 1 (d=0.333), brightleaf_employee_handbook.pdf, page 1 (d=0.397), brightleaf_support_and_refund_policy.pdf, page 2 (d=0.414)

**Scoring:** all required facts present (12.0s)

## Q9 - PASS (multi-document combination)

**Question:** Who is the CEO of Brightleaf Analytics, and how many days of paid sick leave do its employees get per year?

**Expected:** The CEO is Asha Menon (company profile); employees get 12 days of paid sick leave per calendar year (employee handbook).  
**Expected source:** brightleaf_company_profile.pdf, page 1; brightleaf_employee_handbook.pdf, page 1

**Criteria:** Answer must combine two documents: name Asha Menon as CEO and state 12 sick-leave days.

**Pipeline answer:** Asha Menon is the CEO of Brightleaf Analytics. Employees receive 12 days of paid sick leave per calendar year.

**Cited sources:** brightleaf_company_profile.pdf, page 1, brightleaf_employee_handbook.pdf, page 1  
**Retrieved chunks:** brightleaf_employee_handbook.pdf, page 1 (d=0.274), brightleaf_company_profile.pdf, page 1 (d=0.296), brightleaf_employee_handbook.pdf, page 2 (d=0.314), brightleaf_support_and_refund_policy.pdf, page 2 (d=0.318)

**Scoring:** all required facts present (12.2s)

## Q10 - PASS (unanswerable (hallucination check))

**Question:** What was Brightleaf Analytics' total revenue in 2024?

**Expected:** Not stated in the documents; the system must say it could not find the answer.  
**Expected source:** none (not in documents)

**Criteria:** Answer must be the not-found message and must not invent a revenue figure.

**Pipeline answer:** I could not find the answer in the provided documents.

**Cited sources:** (none)  
**Retrieved chunks:** brightleaf_company_profile.pdf, page 1 (d=0.275), brightleaf_company_profile.pdf, page 2 (d=0.294), brightleaf_support_and_refund_policy.pdf, page 2 (d=0.301), brightleaf_company_profile.pdf, page 1 (d=0.321)

**Scoring:** correctly reported that the answer is not in the documents (12.3s)
