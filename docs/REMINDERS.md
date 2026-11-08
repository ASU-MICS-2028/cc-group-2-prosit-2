# Appointment reminders for patients who cannot read

## The problem

HealthConnect texts patients an appointment confirmation and a reminder a day before, to cut missed appointments. But many people in rural Ghana **speak** Twi, Ewe, Ga or Dagbani without being able to **read** them, and may not read English either. Translating the SMS would not reach them. So the team asked a different question: *how* should each patient be reminded?

## What is built

When registering a patient, the CHV records **how to remind them** and **the language they speak**. Both can be changed on the patient page.

| Method | What happens |
|---|---|
| **Text message (SMS)** | As before: an English SMS with the clinic, date and time, and the patient reference. A family member can read it out. |
| **CHV visits in person** | No SMS is sent. The appointment appears on the CHV's **Remind in person** list. |

The CHV's home screen lists their patients' appointments in the next 7 days that a text message will not reach: those who chose a CHV visit, those with no phone, and those whose SMS failed. Each entry shows the date, the clinic and the language the patient speaks, so the CHV knows which language to use.

The reminder job (`backend/reminders.py`) never texts a patient who chose a CHV visit.

Like the SMS, the CHV's list follows need-to-know: a CHV sees only their own patients.
