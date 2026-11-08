# Sustainability plan (PROSIT 2, Week 4)

How HealthConnect Ghana could keep running after the student team leaves. Each section says what is **built** and what is only **proposed**. No partner has agreed to anything in this document.

## 1. Revenue model

| Stream | Status | Who pays | Prototype price |
|---|---|---|---|
| Consultation fee | Built (Paystack) | Patient, recorded at the centre | Set by each centre, default GH₵1, can be free |
| Insurance premium | Built (Paystack) | Scheme member | GH₵1 a month |
| Training fee | Built (Paystack) | Nurses, doctors, pharmacists | GH₵1 per certificate |
| Training | Free by design | CHVs | They are volunteers |

These prices exist to demonstrate the payment flow. They are not market research or actuarial figures. Live payments have only been used for small team demos: **running a real insurance scheme needs regulatory licensing, which we do not hold.**

Fairness rules: a CHV never pays to train, a centre can set its fee to zero, and nothing in the app blocks care if a fee is unpaid.

## 2. Cost estimate

Our runbook estimates the AWS set-up at **about $60 to $70 a month** if left running ([AWS_DEPLOYMENT.md](AWS_DEPLOYMENT.md)). Check this against the AWS bill before quoting it. SMS and Paystack charges are extra.

Illustrative break-even, using **assumed** figures to be replaced with current ones: at $65 a month and GH₵12 to the dollar, hosting costs about GH₵780 a month, which is about 780 payments of GH₵1 before provider charges. At a higher fee of GH₵5 it is about 156 consultations. Shared across 10 centres, that is about 16 consultations per centre per month.

## 3. Community ownership

**Built:** the admin can name a nurse or doctor as a health centre's manager. The manager can enable or disable their own centre's staff, set its consultation fee, and see its monthly visits, referrals, appointments and money collected. They see totals, never patient records. Every action is in the audit log.

**Proposed:**
- A district assembly health committee oversees each centre's manager.
- Fee income stays with the centre, after a share towards hosting.
- Women's groups, religious leaders and youth groups are represented on the committee.
- Fees and income are reported publicly at community meetings.

## 4. Open source

**Built:** the code is public under the MIT licence (see `LICENSE`). Modules others could reuse are the offline encrypted queue, danger-sign triage rules, referral prioritisation, certificates and the Paystack payment module.

**Caution:** the triage rules and training content are not clinically validated, and must be reviewed before anyone reuses them.

## 5. Local capacity building (proposed)

| Level | Who | Learns |
|---|---|---|
| 1. Super-users | One CHV or nurse per centre | Everyday support, resetting devices, helping colleagues |
| 2. Centre managers | Nurse or doctor | Staff accounts, fees, reading the monthly figures |
| 3. District technical officers | District health information staff | Backups, alarms, updates, AWS costs |

The brief's target of 200 trained administrators is not met or measured. Our training module system could host this content.

## 6. Partnerships (proposed, none signed)

| Partner | Possible role |
|---|---|
| Ghana Health Service | Curriculum approval, DHIMS2 connection, recognising certificates |
| National Health Insurance Authority | Cover verification and claims |
| Kintampo and Dodowa research centres | Field trials and CHV training |
| University of Ghana Medical School | Specialist consultations, clinical review |
| Licensed pharmacy networks | Prescription fulfilment |
| MTN, Telecel | Health messaging rates, mobile money |

## 7. Honest limits

- No real patient has used the system, so no health or financial outcome has been measured.
- Certificates are not GHS qualifications.
- The manager role is a working prototype that has not been tried at a real centre.
- Automatic payment confirmation (webhooks) is not built; staff press confirm.
