# Appointment reminders for patients who cannot read

## The problem

HealthConnect texts patients an appointment confirmation and a reminder a day before, to cut missed appointments. But many people in rural Ghana **speak** Twi, Ewe, Ga or Dagbani without being able to **read** them, and may not read English either. Translating the SMS would not reach them. So the team asked a different question: *how* should each patient be reminded?

## What is built

When registering a patient, the CHV records **how to remind them** and **the language they speak**. Both can be changed on the patient page.

| Method | What happens |
|---|---|
| **Text message (SMS)** | As before: an English SMS with the clinic, date and time, and the patient reference. A family member can read it out. |
| **CHV visits in person** | No SMS is sent. The appointment appears on the CHV's **Remind in person** list. |
| **Voice call in their language** | Designed, **not built** (see below). Until then it works like a CHV visit. |

The CHV's home screen lists their patients' appointments in the next 7 days that a text message will not reach: those who chose a CHV visit or a voice call, those with no phone, and those whose SMS failed. Each entry shows the date, the clinic and the language the patient speaks.

The reminder job (`backend/reminders.py`) never texts a patient who chose a voice call or a CHV visit.

## Voice calls: the design (not built)

1. **Provider:** a Ghanaian voice-message service places the call. Several bulk-SMS companies also offer voice messages; the team would compare cost per call and coverage.
2. **Recordings:** the message has fixed parts ("You have an appointment at…", "Please come on time") and changing parts (clinic, day, time). The fixed parts are recorded once per language by a native speaker. The changing parts are either recorded pieces joined together (each clinic name, each weekday, each hour) or text-to-speech; GhanaNLP Khaya's documentation lists speech for Twi, Ewe, Ga and Dagbani, but this was not tested.
3. **Privacy (Act 843):** like the SMS, the call says no name and no diagnosis, because the phone may be shared.
4. **Fallback:** if the call is not answered after two tries, the appointment goes on the CHV's Remind in person list.

**Why it is not built:** it needs a paid provider account and recordings in four languages. The CHV visit already reaches every patient, so it is the safe default while voice calls are arranged.
