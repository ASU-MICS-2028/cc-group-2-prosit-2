"""Starter training modules. Draft teaching content: a nurse or doctor must approve each one.

The answers stay on the server. "answer" is the position of the right option, counting from 0.
"""
TRAINING_MODULES = {
    "danger_signs": {
        "title": "Recognising danger signs",
        "body": "Some signs mean a patient needs a health facility now. Convulsions and difficulty breathing are danger signs. "
                "A patient who is unconscious or very drowsy must be referred urgently. "
                "Heavy bleeding is a danger sign. A patient unable to drink or eat must go to a facility. "
                "Do not wait to see if a danger sign improves.",
        "questions": [
            {"text": "A patient is having convulsions. What should you do?",
             "options": ["Give home-care advice", "Refer urgently to a facility", "Visit again next week"], "answer": 1},
            {"text": "Which of these is a danger sign?", "options": ["Very drowsy patient", "Mild cough", "Small rash"], "answer": 0},
            {"text": "A patient cannot drink or eat. This is:", "options": ["Normal", "A reason to wait", "A danger sign"], "answer": 2},
            {"text": "A danger sign seems to improve a little. You should:",
             "options": ["Still refer the patient", "Cancel the referral", "Tell the patient to rest only"], "answer": 0},
            {"text": "Heavy bleeding needs:", "options": ["A follow-up next month", "Urgent referral", "Only a note in the record"], "answer": 1},
        ],
    },
    "malaria_testing": {
        "title": "Fever and malaria testing",
        "body": "Every patient with a fever should be tested for malaria. Use a rapid diagnostic test before treatment. "
                "Record the result in the patient's visit. Sleeping under a treated net helps prevent malaria. "
                "Fever with danger signs needs urgent referral.",
        "questions": [
            {"text": "Who should be tested for malaria?", "options": ["Only children", "Every patient with a fever", "Nobody"], "answer": 1},
            {"text": "When is the test done?", "options": ["Before treatment", "A month after treatment", "Never"], "answer": 0},
            {"text": "Fever with convulsions needs:", "options": ["Rest at home", "Urgent referral", "Only a malaria test"], "answer": 1},
            {"text": "What helps prevent malaria?", "options": ["Skipping meals", "Sleeping under a treated net", "Avoiding water"], "answer": 1},
            {"text": "After testing you should:", "options": ["Forget the result", "Tell only neighbours", "Record the result"], "answer": 2},
        ],
    },
    "privacy_consent": {
        "title": "Patient privacy and consent",
        "body": "Ask for the patient's consent before you record their details. Collect only the information needed for their care. "
                "Never share a patient's health details with neighbours or family without permission. "
                "Keep your phone locked and never share your password. Ghana's Data Protection Act protects patient data.",
        "questions": [
            {"text": "When do you ask for consent?", "options": ["Before recording details", "After a year", "Never"], "answer": 0},
            {"text": "How much information should you collect?", "options": ["Everything possible", "Only what care needs", "Other people's details too"], "answer": 1},
            {"text": "A neighbour asks about a patient's illness. You:", "options": ["Tell them", "Show the record", "Do not share it"], "answer": 2},
            {"text": "Your password should be:", "options": ["Shared with colleagues", "Kept to yourself", "Written on the phone"], "answer": 1},
            {"text": "Which law protects patient data in Ghana?", "options": ["The Data Protection Act", "The Road Traffic Act", "No law does"], "answer": 0},
        ],
    },
}
