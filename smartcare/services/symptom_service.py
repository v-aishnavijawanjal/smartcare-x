"""Rule-based symptom to department mapping using keyword matching."""

DEPARTMENT_KEYWORDS = {
    "Cardiology": [
        "chest pain", "chest tightness", "heart", "cardiac", "cardio",
        "palpitation", "blood pressure", "bp", "hypertension", "high bp",
        "low bp", "shortness of breath", "breathless", "breathlessness",
        "heart attack", "angina", "arrhythmia", "cholesterol",
        "coronary", "pulse", "heart disease", "irregular heartbeat",
    ],
    "Orthopedics": [
        "bone", "fracture", "joint", "back pain", "backache", "knee",
        "shoulder", "arthritis", "sprain", "muscle", "spine", "hip",
        "ligament", "tendon", "dislocation", "osteoporosis",
        "slip disc", "slipped disc", "sports injury", "neck pain",
        "leg pain", "ankle", "elbow", "wrist pain", "cramp", "stiffness",
    ],
    "Pediatrics": [
        "child", "baby", "infant", "kid", "newborn", "toddler",
        "vaccination", "vaccine", "immunization", "growth delay",
        "pediatric", "teething", "children", "son", "daughter",
    ],
    "Dermatology": [
        "skin", "rash", "acne", "itching", "itch", "allergy",
        "hair fall", "hair loss", "eczema", "pimple", "dandruff",
        "mole", "psoriasis", "fungal infection", "skin infection",
        "wart", "nail problem", "dry skin", "pigmentation", "boil",
        "hives", "sunburn",
    ],
    "Neurology": [
        "headache", "migraine", "seizure", "epilepsy", "dizziness",
        "numbness", "memory loss", "tremor", "fainting", "vertigo",
        "stroke", "paralysis", "nerve pain", "sciatica", "parkinson",
        "brain", "nervous system", "tingling", "convulsion",
        "forgetfulness", "balance problem",
    ],
    "General Medicine": [
        "fever", "cold", "cough", "flu", "influenza", "infection",
        "weakness", "fatigue", "tiredness", "body ache", "bodyache",
        "sore throat", "vomiting", "diarrhea", "stomach pain",
        "stomach ache", "nausea", "checkup", "check up", "check-up",
        "routine test", "general illness", "dehydration", "typhoid",
        "malaria", "dengue", "jaundice", "diabetes", "sugar",
        "viral infection", "chills", "cold and cough", "throat pain",
        "gas", "acidity", "constipation", "food poisoning",
    ],
}


def suggest_department(symptom_text):
    """Return the best matching department, or None if no match is found."""
    if not symptom_text or not symptom_text.strip():
        return None

    text = symptom_text.lower()
    best_department = None
    best_score = 0

    for department_name, keywords in DEPARTMENT_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in text)
        if score > best_score:
            best_score = score
            best_department = department_name

    return best_department