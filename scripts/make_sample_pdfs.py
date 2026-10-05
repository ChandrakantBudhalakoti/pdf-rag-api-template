"""Generate the three synthetic sample PDFs in data/pdfs/.

All content is original and fictional (the company "Brightleaf Analytics" does
not exist). Run:  python scripts/make_sample_pdfs.py
"""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "pdfs"
DISCLAIMER = "This is a fictional sample document created for testing a RAG pipeline."

DOCUMENTS = {
    "brightleaf_company_profile.pdf": (
        "Brightleaf Analytics - Company Profile",
        [
            [
                ("h", "1. Company Overview"),
                ("p", "Brightleaf Analytics Pvt. Ltd. is a business-to-business software company. "
                      "It was founded in March 2016 in Pune, India, by Asha Menon, who serves as Chief "
                      "Executive Officer (CEO), and Ravi Kulkarni, who serves as Chief Technology Officer (CTO)."),
                ("p", "The company headquarters is on the 4th floor of Riverside Tech Park, Pune. Brightleaf "
                      "also operates offices in Bengaluru, India, and Singapore. The Singapore office opened in 2021."),
                ("p", "As of January 2025, Brightleaf Analytics employs 240 people and serves customers in "
                      "18 countries, mainly mid-sized retail and consumer-goods businesses."),
                ("h", "2. Products"),
                ("p", "LeafSight is the flagship product. It is a retail demand-forecasting platform that "
                      "predicts store-level product demand up to 12 weeks ahead using sales history, "
                      "promotions and local holiday calendars."),
                ("p", "LeafPulse is the second product, launched in 2022. It is a customer-sentiment dashboard "
                      "that analyses product reviews and support tickets."),
            ],
            [
                ("h", "3. LeafSight Pricing Plans"),
                ("p", "LeafSight is sold as a subscription in three plans. Prices are in US dollars."),
                ("p", "<b>Starter plan:</b> US$49 per user per month. Up to 10 users, email support only, "
                      "and 1 data-source integration."),
                ("p", "<b>Growth plan:</b> US$99 per user per month. Up to 100 users, email and live-chat "
                      "support, and up to 10 data-source integrations."),
                ("p", "<b>Enterprise plan:</b> custom pricing, with a minimum of 50 users. Includes unlimited "
                      "integrations, 24/7 phone support and a dedicated customer success manager. Phone support "
                      "is available only on the Enterprise plan."),
                ("p", "Customers who choose annual billing instead of monthly billing receive a 15% discount "
                      "on the Starter and Growth plans."),
                ("p", "A 14-day free trial of the Growth plan is available. No credit card is required to "
                      "start the trial."),
            ],
        ],
    ),
    "brightleaf_employee_handbook.pdf": (
        "Brightleaf Analytics - Employee Handbook (2025 Edition)",
        [
            [
                ("h", "1. Working Hours and Hybrid Work"),
                ("p", "Core working hours are 10:00 to 16:00 India Standard Time (IST). Outside core hours, "
                      "employees may plan their own schedule."),
                ("p", "Brightleaf follows a hybrid model: employees may work remotely up to 3 days per week. "
                      "Tuesdays and Thursdays are in-office collaboration days for all teams."),
                ("h", "2. Leave Policy"),
                ("p", "Full-time employees receive 24 days of paid annual leave per calendar year. Up to 8 "
                      "unused annual leave days can be carried forward to the next calendar year; any "
                      "additional unused days lapse on 31 December."),
                ("p", "Employees receive 12 days of paid sick leave per calendar year. Sick leave of more "
                      "than 2 consecutive days requires a medical certificate."),
                ("p", "Parental leave is 26 weeks of paid leave for the primary caregiver and 4 weeks of "
                      "paid leave for the secondary caregiver."),
            ],
            [
                ("h", "3. Probation and Notice Period"),
                ("p", "All new employees serve a probation period of 6 months. During probation, the notice "
                      "period for resignation or termination is 30 days."),
                ("p", "After an employee is confirmed (has completed probation), the notice period is 60 days."),
                ("h", "4. Performance Reviews"),
                ("p", "Performance reviews take place twice a year, in April and in October. Salary "
                      "revisions are decided in the April review cycle."),
                ("h", "5. Benefits"),
                ("p", "Each employee has a learning and development budget of US$1,200 per calendar year. "
                      "It can be used for online courses, professional certifications and conference tickets. "
                      "Requests must be approved by the employee's manager."),
                ("p", "Group health insurance covers the employee, their spouse and up to two children, with a "
                      "sum insured of INR 500,000 per family per year."),
                ("p", "The employee referral bonus is US$1,000. It is paid after the referred new hire "
                      "successfully completes their probation period."),
            ],
        ],
    ),
    "brightleaf_support_and_refund_policy.pdf": (
        "Brightleaf Analytics - Customer Support, SLA and Refund Policy",
        [
            [
                ("h", "1. Support Channels"),
                ("p", "Customers can contact support by email at support@brightleaf.example and through live "
                      "chat in the LeafSight application. Phone support is available only to Enterprise plan "
                      "customers, 24 hours a day, 7 days a week."),
                ("h", "2. Uptime Commitment and Service Credits"),
                ("p", "Brightleaf commits to 99.9% monthly uptime for the LeafSight platform. If monthly uptime "
                      "falls below this commitment, customers are eligible for service credits on that "
                      "month's subscription fee:"),
                ("p", "- Uptime from 99.0% up to (but not including) 99.9%: 10% service credit.<br/>"
                      "- Uptime from 95.0% up to (but not including) 99.0%: 25% service credit.<br/>"
                      "- Uptime below 95.0%: 50% service credit."),
                ("p", "Service credits must be requested within 30 days after the end of the affected month."),
                ("h", "3. Incident Priorities and Response Times"),
                ("p", "- Priority 1 (P1), platform down: first response within 1 hour, 24/7.<br/>"
                      "- Priority 2 (P2), major feature impaired: first response within 4 business hours.<br/>"
                      "- Priority 3 (P3), minor issue: first response within 1 business day.<br/>"
                      "- Priority 4 (P4), general question: first response within 3 business days."),
            ],
            [
                ("h", "4. Cancellation and Refunds"),
                ("p", "Monthly subscriptions can be cancelled at any time. The cancellation takes effect at the "
                      "end of the current billing month. Monthly subscription fees are not refundable."),
                ("p", "Annual subscriptions receive a full refund if they are cancelled within 30 days of "
                      "purchase. Annual subscriptions cancelled after 30 days are not refunded, but the service "
                      "remains active until the end of the paid annual term."),
                ("p", "Approved refunds are processed within 10 business days to the original payment method."),
                ("h", "5. Data Retention After Cancellation"),
                ("p", "After a subscription ends, customer data is retained for 60 days, during which the "
                      "customer can export it. After 60 days the data is permanently deleted."),
                ("h", "6. Price Changes"),
                ("p", "Brightleaf gives customers at least 45 days of written notice before any price change "
                      "takes effect."),
            ],
        ],
    ),
}


def build_pdf(path: Path, title: str, pages: list[list[tuple[str, str]]]) -> None:
    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Title"]), Paragraph(f"<i>{DISCLAIMER}</i>", styles["Normal"]),
             Spacer(1, 0.5 * cm)]
    for i, blocks in enumerate(pages):
        if i:
            story.append(PageBreak())
        for kind, text in blocks:
            story.append(Paragraph(text, styles["Heading2" if kind == "h" else "BodyText"]))
            story.append(Spacer(1, 0.2 * cm))

    def footer(canvas, doc):
        canvas.setFont("Helvetica", 8)
        canvas.drawString(2 * cm, 1.2 * cm, f"{title} - page {doc.page}")

    SimpleDocTemplate(str(path), pagesize=A4, title=title, author="Brightleaf Analytics (fictional)",
                      invariant=1).build(story, onFirstPage=footer, onLaterPages=footer)


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for filename, (title, pages) in DOCUMENTS.items():
        build_pdf(OUT_DIR / filename, title, pages)
        print(f"wrote {OUT_DIR / filename}")
