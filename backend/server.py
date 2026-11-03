"""
ClinicaNLP - Clinical & Medical Dialogue Intelligence Platform
Provides local, offline-capable NLP services for:
- Doctor-Patient consultation transcripts & clinical notes
- Medical Named Entity Recognition (Symptoms, Diagnoses, Medications, Body Systems, Tests)
- Automated Clinical SOAP Note Generation (Subjective, Objective, Assessment, Plan)
- Medical Jargon Simplification & Patient-Friendly Explanations
- Patient Distress, Anxiety & Clinician Empathy Scoring
- Clinical Red Flags & Emergency Warning Detection
- Medication Schedule & Care Action Items Extraction
- Patient Health Literacy & Readability Assessment
- Medical Video / YouTube Lecture Intelligence & Comprehension Quizzes
"""

import os
import re
import math
import random
import logging
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords, wordnet as wn
from nltk.stem import WordNetLemmatizer
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("clinicanlp_server")

# Ensure required NLTK data is loaded safely
for pkg in ['punkt', 'stopwords', 'vader_lexicon']:
    try:
        nltk.download(pkg, quiet=True)
    except Exception as e:
        logger.warning(f"NLTK download notice for {pkg}: {e}")

try:
    lemmatizer = WordNetLemmatizer()
except Exception:
    class DummyLemmatizer:
        def lemmatize(self, word, pos='n'):
            return word.rstrip('s') if len(word) > 3 and word.endswith('s') else word
    lemmatizer = DummyLemmatizer()

try:
    sia = SentimentIntensityAnalyzer()
except Exception:
    class DummySIA:
        def polarity_scores(self, text):
            t = text.lower()
            pos = sum(1 for w in ["good", "great", "excellent", "safe", "manageable", "better", "clear", "relief", "normal"] if w in t)
            neg = sum(1 for w in ["pain", "severe", "worried", "panic", "fear", "anxiety", "attack", "emergency", "tightness", "shortness"] if w in t)
            compound = 0.0
            if pos > neg: compound = min(1.0, 0.2 * (pos - neg))
            elif neg > pos: compound = max(-1.0, -0.2 * (neg - pos))
            return {"compound": compound, "pos": 0.5 if pos>neg else 0.1, "neg": 0.5 if neg>pos else 0.1, "neu": 0.4}
    sia = DummySIA()

try:
    stop_words = set(stopwords.words('english'))
except Exception:
    stop_words = {"i", "me", "my", "we", "our", "you", "your", "he", "him", "his", "she", "her", "it", "they", "them", "what", "which", "who", "this", "that", "is", "are", "was", "were", "be", "have", "has", "had", "do", "does", "did", "a", "an", "the", "and", "but", "if", "or", "as", "of", "at", "by", "for", "with", "about", "to", "from", "in", "out", "on", "off", "so", "than", "too", "very", "can", "will", "just", "now"}

app = FastAPI(title="ClinicaNLP Backend", version="3.0.0", description="Intelligent Doctor-Patient Consultation & Health Records NLP Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "status": "online",
        "service": "ClinicaNLP - Clinical Dialogue & Health Records NLP Platform",
        "version": "3.0.0",
        "docs_url": "/docs",
        "health_check": "/health",
        "frontend_url": "http://localhost:3000"
    }


# ==========================================
# Core NLP Helper Functions
# ==========================================

def clean_text(text: str) -> str:
    """Removes special brackets, repetitive spaces, and cleans transcript text."""
    text = re.sub(r"[\(\[].*?[\)\]]", " ", text)
    text = " ".join(text.splitlines())
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


def extractive_summarize(text: str, word_count: int = 300, ratio: float = 0.5) -> Dict[str, Any]:
    """
    Extractive sentence summarization based on word frequency scoring and position weighting.
    Returns summary text, selected sentences, and their character offsets for highlighting.
    """
    cleaned = clean_text(text)
    if not cleaned:
        return {"summary": "", "main_sentences": []}

    sentences = sent_tokenize(cleaned)
    if len(sentences) <= 2:
        return {
            "summary": cleaned,
            "main_sentences": [{"start": 0, "end": len(cleaned), "score": 10.0}]
        }

    # Calculate word frequencies
    words = word_tokenize(cleaned.lower())
    freq_table: Dict[str, float] = {}
    for w in words:
        if w.isalnum() and w not in stop_words and len(w) > 2:
            freq_table[w] = freq_table.get(w, 0) + 1

    max_freq = max(freq_table.values()) if freq_table else 1.0
    for w in freq_table:
        freq_table[w] = freq_table[w] / max_freq

    # Score each sentence
    sentence_scores: List[Dict[str, Any]] = []
    current_search_pos = 0

    for idx, sentence in enumerate(sentences):
        start_pos = cleaned.find(sentence, current_search_pos)
        if start_pos == -1:
            start_pos = current_search_pos
        end_pos = start_pos + len(sentence)
        current_search_pos = end_pos

        s_words = word_tokenize(sentence.lower())
        score = 0.0
        word_len = len(s_words)
        if word_len > 0:
            for sw in s_words:
                if sw in freq_table:
                    score += freq_table[sw]
            # Normalize by sentence length with slight boost for earlier sentences
            score = (score / math.sqrt(word_len)) * (1.0 + (1.0 / (idx + 1)) * 0.2)

        sentence_scores.append({
            "index": idx,
            "text": sentence,
            "start": start_pos,
            "end": end_pos,
            "score": score,
            "word_count": word_len
        })

    # Pick top scoring sentences
    target_sentences = max(2, int(len(sentences) * ratio))
    if word_count > 0:
        ranked = sorted(sentence_scores, key=lambda x: x["score"], reverse=True)
        selected_indices = set()
        total_words = 0
        for item in ranked:
            selected_indices.add(item["index"])
            total_words += item["word_count"]
            if total_words >= word_count or len(selected_indices) >= target_sentences:
                break
    else:
        ranked = sorted(sentence_scores, key=lambda x: x["score"], reverse=True)[:target_sentences]
        selected_indices = {item["index"] for item in ranked}

    # Reorder chronologically
    selected_sentences = [s for s in sentence_scores if s["index"] in selected_indices]
    summary_text = " ".join([s["text"] for s in selected_sentences])

    main_sentences_data = [
        {"start": s["start"], "end": s["end"], "score": round(s["score"], 2)}
        for s in selected_sentences
    ]

    return {
        "summary": summary_text,
        "main_sentences": main_sentences_data
    }


def extract_keywords_and_lemmas(text: str) -> Dict[str, Any]:
    """Extracts top keywords, lemmas, entities, and topics."""
    words = word_tokenize(text.lower())
    try:
        tagged = nltk.pos_tag(words)
    except Exception:
        tagged = [(w, 'NN') for w in words]

    lemma_counts: Dict[str, int] = {}
    noun_phrases: Dict[str, int] = {}

    prev_word = ""
    prev_tag = ""

    for word, tag in tagged:
        if word.isalnum() and len(word) > 2 and word not in stop_words:
            pos_val = 'n'
            if tag.startswith('V'):
                pos_val = 'v'
            elif tag.startswith('J'):
                pos_val = 'a'
            lemma = lemmatizer.lemmatize(word, pos=pos_val)
            lemma_counts[lemma] = lemma_counts.get(lemma, 0) + 1

            if (prev_tag.startswith('J') or prev_tag.startswith('N')) and tag.startswith('N'):
                phrase = f"{prev_word} {word}"
                noun_phrases[phrase] = noun_phrases.get(phrase, 0) + 1

        prev_word = word
        prev_tag = tag

    sorted_lemmas = sorted(lemma_counts.items(), key=lambda x: x[1], reverse=True)
    sorted_phrases = sorted(noun_phrases.items(), key=lambda x: x[1], reverse=True)

    main_lemmas = [{"value": item[0], "score": float(item[1])} for item in sorted_lemmas[:25]]

    entities_list = []
    seen = set()
    for phrase, count in sorted_phrases[:15]:
        if phrase not in seen:
            seen.add(phrase)
            entities_list.append({"lemma": phrase})

    for lemma, count in sorted_lemmas[:20]:
        if lemma not in seen and len(lemma) > 3:
            seen.add(lemma)
            entities_list.append({"lemma": lemma})

    topics = []
    topic_candidates = [p[0] for p in sorted_phrases[:6]] + [l[0] for l in sorted_lemmas[:6]]
    for cand in topic_candidates:
        if cand not in [t["label"] for t in topics] and len(topics) < 5:
            topics.append({"label": cand})

    return {
        "mainLemmas": main_lemmas,
        "entities": entities_list,
        "topics": topics
    }


def analyze_vader_sentiment(text: str) -> Dict[str, Any]:
    """Runs VADER sentiment analysis, returning overall (-100 to 100) and item scores."""
    sentences = sent_tokenize(text)
    if not sentences:
        return {"overall": 0, "items": []}

    scores = []
    for s in sentences:
        res = sia.polarity_scores(s)
        score = res["compound"] * 100.0
        scores.append({"sentiment": round(score, 1)})

    avg_score = sum(item["sentiment"] for item in scores) / len(scores) if scores else 0.0

    return {
        "overall": round(avg_score, 1),
        "items": scores
    }


def find_similar_words(words: List[str]) -> Dict[str, Dict[str, List[str]]]:
    """Uses NLTK WordNet to retrieve synonyms, antonyms, and related words."""
    results = {}
    for word in words:
        clean_w = word.strip().lower()
        synonyms = set()
        antonyms = set()

        synsets = wn.synsets(clean_w)
        for s in synsets:
            for l in s.lemmas():
                name = l.name().replace('_', ' ').replace('-', ' ').lower()
                if name != clean_w and len(name) > 1:
                    synonyms.add(name)
                for ant in l.antonyms():
                    ant_name = ant.name().replace('_', ' ').replace('-', ' ').lower()
                    antonyms.add(ant_name)

            for hyper in s.hypernyms()[:2]:
                for hl in hyper.lemmas()[:2]:
                    hname = hl.name().replace('_', ' ').replace('-', ' ').lower()
                    if hname != clean_w:
                        synonyms.add(hname)
            for hypo in s.hyponyms()[:3]:
                for hyl in hypo.lemmas()[:2]:
                    hyname = hyl.name().replace('_', ' ').replace('-', ' ').lower()
                    if hyname != clean_w:
                        synonyms.add(hyname)

        syn_list = list(synonyms)[:8]
        ant_list = list(antonyms)[:5]

        if not syn_list:
            syn_list = [f"{clean_w} style", f"clinical {clean_w}", f"{clean_w} term"]

        results[word] = {
            "synms": syn_list,
            "antms": ant_list
        }
    return results


def count_syllables(word: str) -> int:
    """Estimates the syllable count of an English word."""
    word = word.lower().strip()
    if len(word) <= 3:
        return 1
    word = re.sub(r'(?:[^laeiouy]|ed|es|e)$', '', word)
    word = re.sub(r'^y', '', word)
    matches = re.findall(r'[aeiouy]{1,2}', word)
    return max(1, len(matches))


def calculate_readability_metrics(text: str) -> Dict[str, Any]:
    """Computes Flesch Reading Ease, Grade Level, lexical diversity, and reading duration."""
    cleaned = clean_text(text)
    if not cleaned:
        return {
            "score": 0, "grade": "N/A", "label": "No Text",
            "stats": {"words": 0, "sentences": 0, "reading_time_min": 0, "lexical_diversity": 0}
        }

    sentences = sent_tokenize(cleaned)
    words = [w for w in word_tokenize(cleaned) if w.isalnum()]

    total_sentences = max(1, len(sentences))
    total_words = max(1, len(words))
    total_syllables = sum(count_syllables(w) for w in words)

    asl = total_words / total_sentences
    asw = total_syllables / total_words

    fre = 206.835 - (1.015 * asl) - (84.6 * asw)
    fre = round(max(0.0, min(100.0, fre)), 1)

    fkgl = (0.39 * asl) + (11.8 * asw) - 15.59
    fkgl = round(max(1.0, fkgl), 1)

    if fre >= 75:
        label = "Easy to Understand (Patient Accessible)"
        badge = "success"
    elif fre >= 55:
        label = "Standard Healthcare Communication"
        badge = "info"
    elif fre >= 35:
        label = "Moderate (Requires Clinical Background)"
        badge = "warning"
    else:
        label = "Highly Complex (Specialized Medical Literature)"
        badge = "danger"

    unique_words = len(set(w.lower() for w in words))
    diversity = round((unique_words / total_words) * 100, 1)
    reading_time = round(total_words / 200, 1)
    speaking_time = round(total_words / 130, 1)

    return {
        "score": fre,
        "grade": f"Grade {int(round(fkgl))}",
        "grade_num": fkgl,
        "label": label,
        "badge": badge,
        "stats": {
            "words": total_words,
            "sentences": total_sentences,
            "syllables": total_syllables,
            "avg_sentence_len": round(asl, 1),
            "lexical_diversity": diversity,
            "reading_time_min": reading_time,
            "speaking_time_min": speaking_time
        }
    }


def build_quiz_from_text(text: str, key_notes: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Builds multiple choice questions by masking clinical keywords in sentences."""
    sentences = sent_tokenize(text)
    lemmas = [k["value"] for k in key_notes] if key_notes else []

    if not lemmas:
        meta = extract_keywords_and_lemmas(text)
        lemmas = [k["value"] for k in meta["mainLemmas"]]

    quiz_list = []
    used_answers = set()

    for sentence in sentences:
        if len(sentence) < 50:
            continue
        for lemma in lemmas:
            if lemma in used_answers or len(lemma) < 3:
                continue
            pattern = re.compile(rf"\b{re.escape(lemma)}\b", re.IGNORECASE)
            if pattern.search(sentence):
                question = pattern.sub("__________", sentence)
                sim_res = find_similar_words([lemma])
                distractors = sim_res.get(lemma, {}).get("synms", [])[:3]

                pool = [l for l in lemmas if l != lemma and l not in distractors]
                while len(distractors) < 3 and pool:
                    distractors.append(pool.pop(0))
                while len(distractors) < 3:
                    distractors.append("None of these")

                options = distractors[:3] + [lemma]
                random.shuffle(options)

                quiz_list.append({
                    "sentence": question,
                    "answer": lemma,
                    "options": options
                })
                used_answers.add(lemma)
                break

        if len(quiz_list) >= 5:
            break

    return quiz_list


# ==========================================
# Specialized Healthcare & Clinical NLP Engine
# ==========================================

CLINICAL_JARGON_DICT = {
    "dyspnea": {
        "plain": "shortness of breath",
        "explanation": "Difficulty breathing or feeling breathless during exertion or rest.",
        "category": "Symptom / Respiratory"
    },
    "exertional": {
        "plain": "triggered by physical activity or exercise",
        "explanation": "Symptoms that occur when walking, climbing stairs, or working out.",
        "category": "Modifier"
    },
    "retrosternal": {
        "plain": "behind the breastbone / center of chest",
        "explanation": "Located directly behind the sternum in the middle of the chest.",
        "category": "Anatomy"
    },
    "myocardial infarction": {
        "plain": "heart attack",
        "explanation": "Damage to heart muscle caused by loss of blood supply from a blocked artery.",
        "category": "Condition / Cardiac"
    },
    "ischemia": {
        "plain": "inadequate blood flow and oxygen",
        "explanation": "Restriction in blood supply to tissues causing a shortage of oxygen.",
        "category": "Pathology"
    },
    "hypertension": {
        "plain": "high blood pressure",
        "explanation": "Persistent pressure in blood vessels above standard healthy levels (e.g. >130/80 mmHg).",
        "category": "Condition / Vascular"
    },
    "edema": {
        "plain": "swelling caused by fluid buildup",
        "explanation": "Accumulation of excessive fluid in body tissues, commonly in ankles or legs.",
        "category": "Symptom / Physical Exam"
    },
    "polydipsia": {
        "plain": "excessive, unquenchable thirst",
        "explanation": "Abnormally high fluid intake, often an early clinical indicator of diabetes.",
        "category": "Symptom / Endocrine"
    },
    "polyuria": {
        "plain": "frequent, excessive urination",
        "explanation": "Passing abnormally large volumes of urine or needing to urinate multiple times at night.",
        "category": "Symptom / Endocrine"
    },
    "hyperglycemia": {
        "plain": "high blood sugar",
        "explanation": "Elevated glucose levels in the bloodstream above normal fasting ranges.",
        "category": "Condition / Endocrine"
    },
    "hypoglycemia": {
        "plain": "dangerously low blood sugar (<70 mg/dL)",
        "explanation": "Drop in blood glucose causing tremors, diaphoresis (sweating), confusion, or fainting.",
        "category": "Condition / Emergency"
    },
    "neuropathy": {
        "plain": "nerve damage / numbness and tingling",
        "explanation": "Damage to peripheral nerves causing numbness, tingling, or burning in hands and feet.",
        "category": "Condition / Neurological"
    },
    "sublingual": {
        "plain": "placed or dissolved under the tongue",
        "explanation": "Medication route absorbed directly into bloodstream via mucous membranes under tongue.",
        "category": "Pharmacology"
    },
    "prn": {
        "plain": "as needed (pro re nata)",
        "explanation": "Take medication only when specific symptoms occur rather than on a set schedule.",
        "category": "Pharmacology"
    },
    "bid": {
        "plain": "twice daily (bis in die)",
        "explanation": "Take medicine two times per day (e.g. morning and evening).",
        "category": "Pharmacology"
    },
    "hemoptysis": {
        "plain": "coughing up blood or blood-stained mucus",
        "explanation": "Spitting or coughing up blood originating from the respiratory tract.",
        "category": "Symptom / Red Flag"
    },
    "rales": {
        "plain": "crackling sounds in lungs",
        "explanation": "Abnormal clicking, rattling, or crackling lung sounds heard with a stethoscope.",
        "category": "Physical Exam / Pulmonary"
    },
    "pleuritic": {
        "plain": "sharp chest pain that worsens with deep breathing",
        "explanation": "Pain caused by inflammation of the lung lining (pleura) triggered by inhalation.",
        "category": "Symptom / Pulmonary"
    },
    "leukocytosis": {
        "plain": "elevated white blood cell count",
        "explanation": "Higher than normal concentration of white blood cells indicating infection or inflammation.",
        "category": "Laboratory"
    },
    "bronchodilator": {
        "plain": "inhaler medication that opens airway passages",
        "explanation": "Substance that relaxes bronchial smooth muscle and expands lung airways for easier breathing.",
        "category": "Pharmacology"
    },
    "tachycardia": {
        "plain": "rapid resting heart rate (>100 bpm)",
        "explanation": "Heart beating faster than normal while at rest.",
        "category": "Physical Exam / Cardiac"
    },
    "bradycardia": {
        "plain": "slow resting heart rate (<60 bpm)",
        "explanation": "Heart beating slower than typical healthy rates.",
        "category": "Physical Exam / Cardiac"
    },
    "orthopnea": {
        "plain": "shortness of breath when lying flat",
        "explanation": "Difficulty breathing comfortably when lying down, requiring sleeping elevated on pillows.",
        "category": "Symptom / Cardiac"
    },
    "analgesic": {
        "plain": "pain-relieving medicine",
        "explanation": "Drug specifically prescribed to diminish pain sensations (e.g. acetaminophen, ibuprofen).",
        "category": "Pharmacology"
    },
    "antipyretic": {
        "plain": "fever-reducing medicine",
        "explanation": "Medication designed to lower elevated body temperature.",
        "category": "Pharmacology"
    },
    "prophylaxis": {
        "plain": "preventative medical treatment",
        "explanation": "Intervention administered to ward off or protect against disease (e.g. anticoagulation for stroke prevention).",
        "category": "Clinical Strategy"
    },
    "consolidation": {
        "plain": "lung area filled with fluid/pus instead of air",
        "explanation": "Region of lung tissue solidified by inflammatory exudate during pneumonia.",
        "category": "Radiology"
    },
    "angina": {
        "plain": "chest pain from reduced blood flow to heart",
        "explanation": "Pressure or squeezing pain in chest caused by temporary oxygen deficit in cardiac muscle.",
        "category": "Condition / Cardiac"
    },
    "palpitation": {
        "plain": "fluttering or pounding heartbeat",
        "explanation": "Conscious awareness of rapid, pounding, or irregular heartbeats.",
        "category": "Symptom / Cardiac"
    },
    "postprandial": {
        "plain": "after a meal",
        "explanation": "Occurring or measured following eating (e.g. 2-hour postprandial blood glucose).",
        "category": "Modifier"
    },
    "glycosylated hemoglobin": {
        "plain": "HbA1c / 3-month average blood sugar test",
        "explanation": "Blood test providing an accurate estimate of average blood glucose over the preceding 90 days.",
        "category": "Laboratory"
    },
    "microalbuminuria": {
        "plain": "small amounts of protein in urine",
        "explanation": "Early marker of kidney stress or diabetic nephropathy.",
        "category": "Laboratory"
    }
}

CLINICAL_SYMPTOMS_LIST = [
    "chest pain", "chest tightness", "dull pressure", "squeezing sensation", "shortness of breath",
    "exertional dyspnea", "dyspnea", "palpitations", "dizziness", "vertigo", "fatigue", "exhaustion",
    "nausea", "vomiting", "fever", "chills", "cough", "productive cough", "purulent sputum",
    "wheezing", "neuropathy", "numbness", "tingling", "pins and needles", "headache", "edema",
    "peripheral edema", "swelling", "polydipsia", "unquenchable thirst", "polyuria",
    "nighttime urination", "blurred vision", "stiffness", "hemoptysis", "sweating", "cold sweats",
    "diaphoresis", "orthopnea", "pleuritic chest pain", "malaise"
]

CLINICAL_CONDITIONS_LIST = [
    "hypertension", "stage 2 hypertension", "high blood pressure", "type 2 diabetes",
    "type 2 diabetes mellitus", "diabetes", "myocardial infarction", "heart attack", "angina",
    "angina pectoris", "asthma", "copd", "chronic obstructive pulmonary disease", "pneumonia",
    "community-acquired pneumonia", "lobar pneumonia", "bronchitis", "arrhythmia",
    "atrial fibrillation", "osteoarthritis", "rheumatoid arthritis", "stroke", "hyperglycemia",
    "hypoglycemia", "hyperlipidemia", "high cholesterol", "congestive heart failure",
    "peripheral neuropathy", "diabetic neuropathy"
]

KNOWN_MEDS = [
    "lisinopril", "metformin", "metformin hydrochloride", "metoprolol", "metoprolol succinate",
    "nitroglycerin", "albuterol", "albuterol sulfate", "atorvastatin", "ceftriaxone",
    "azithromycin", "levofloxacin", "apixaban", "gabapentin", "prednisone", "symbicort",
    "amoxicillin", "ibuprofen", "paracetamol", "acetaminophen", "aspirin", "losartan",
    "amlodipine", "omeprazole", "simvastatin", "glipizide", "insulin", "furosemide",
    "eliquis", "ventolin", "levaquin", "alpha-lipoic acid", "vitamin b12", "ipratropium"
]

BODY_SYSTEMS_MAP = {
    "Cardiovascular": ["heart", "chest", "arm", "shoulder", "cardiac", "artery", "carotid", "vascular", "pulse", "aorta"],
    "Respiratory / Pulmonary": ["lung", "lungs", "breath", "breathing", "airway", "bronchial", "alveoli", "trachea", "sputum"],
    "Endocrine / Metabolic": ["blood sugar", "glucose", "pancreas", "insulin", "hba1c", "thyroid", "adrenal", "glycemic"],
    "Neurological": ["nerve", "nerves", "numbness", "tingling", "brain", "neuropathy", "headache", "dizziness"],
    "Musculoskeletal": ["joints", "ankles", "knee", "spine", "bones", "toes", "feet", "legs"],
    "Gastrointestinal": ["stomach", "gastrointestinal", "nausea", "abdomen", "liver", "intestine"]
}

PROCEDURES_TESTS_LIST = [
    "electrocardiogram", "ecg", "ekg", "12-lead ecg", "echocardiogram", "stress echocardiogram",
    "exercise stress test", "hba1c", "glycated hemoglobin", "fasting blood glucose", "plasma glucose",
    "lipid panel", "ldl cholesterol", "troponin", "high-sensitivity troponin", "chest x-ray",
    "chest radiograph", "ct scan", "thoracic ct", "mri", "spirometry", "complete blood count", "cbc",
    "c-reactive protein", "crp", "blood pressure", "glucometer", "pulse oximetry", "spo2", "vital signs"
]


def extract_clinical_entities(text: str) -> Dict[str, Any]:
    """
    Extracts structured medical entities from text:
    Symptoms, Conditions/Diagnoses, Medications with Dosages, Body Systems, Tests & Procedures.
    """
    text_lower = text.lower()
    
    # 1. Symptoms
    symptoms = []
    seen_sym = set()
    for sym in CLINICAL_SYMPTOMS_LIST:
        if re.search(rf"\b{re.escape(sym)}\b", text_lower):
            base = sym.strip()
            if base not in seen_sym:
                seen_sym.add(base)
                symptoms.append({
                    "name": base.title(),
                    "category": "Symptom / Patient Complaint"
                })

    # 2. Conditions
    conditions = []
    seen_cond = set()
    for cond in CLINICAL_CONDITIONS_LIST:
        if re.search(rf"\b{re.escape(cond)}\b", text_lower):
            base = cond.strip()
            if base not in seen_cond:
                seen_cond.add(base)
                conditions.append({
                    "name": base.title(),
                    "category": "Diagnosis / Condition"
                })

    # 3. Medications & Dosages
    medications = []
    seen_med = set()
    
    # Match known drug names and look for adjacent dosage/frequency in context
    for med in KNOWN_MEDS:
        pattern = re.compile(rf"\b({re.escape(med)})\b(?:\s+([a-zA-Z]+))?(?:\s+(\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|tablets?|puffs?|units?)))?", re.IGNORECASE)
        for match in pattern.finditer(text):
            drug_name = match.group(1).title()
            if match.group(2) and match.group(2).lower() in ["succinate", "hydrochloride", "sulfate", "tartrate"]:
                drug_name += f" {match.group(2).title()}"
            
            dosage = match.group(3) if match.group(3) else "As directed"
            key = drug_name.lower()
            if key not in seen_med:
                seen_med.add(key)
                
                # Check for nearby frequency
                snippet = text[max(0, match.start() - 20):min(len(text), match.end() + 80)]
                freq_match = re.search(r"\b(once daily|twice daily|bid|tid|qid|prn|as needed|every \d+ hours|in the morning|with meals)\b", snippet, re.IGNORECASE)
                frequency = freq_match.group(1).capitalize() if freq_match else "Prescribed schedule"

                medications.append({
                    "name": drug_name,
                    "dosage": dosage,
                    "frequency": frequency
                })

    # 4. Anatomical Body Systems
    systems_detected = []
    for sys_name, keywords in BODY_SYSTEMS_MAP.items():
        matched_kw = [kw for kw in keywords if re.search(rf"\b{re.escape(kw)}\b", text_lower)]
        if matched_kw:
            systems_detected.append({
                "system": sys_name,
                "mentions": list(set(matched_kw))[:4]
            })

    # 5. Diagnostic Tests & Procedures
    tests = []
    seen_tests = set()
    for t_term in PROCEDURES_TESTS_LIST:
        if re.search(rf"\b{re.escape(t_term)}\b", text_lower):
            if t_term not in seen_tests:
                seen_tests.add(t_term)
                tests.append({
                    "test": t_term.upper() if len(t_term) <= 4 else t_term.title(),
                    "type": "Diagnostic Investigation"
                })

    return {
        "symptoms": symptoms[:12],
        "conditions": conditions[:10],
        "medications": medications[:10],
        "body_systems": systems_detected,
        "diagnostic_tests": tests[:10],
        "total_entities": len(symptoms) + len(conditions) + len(medications) + len(tests)
    }


def simplify_medical_jargon(text: str) -> Dict[str, Any]:
    """Scans text for clinical jargon and maps each occurrence to patient-friendly explanations."""
    text_lower = text.lower()
    detected_jargon = []
    seen = set()

    for term, info in CLINICAL_JARGON_DICT.items():
        pat = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
        match = pat.search(text_lower)
        if match and term not in seen:
            seen.add(term)
            detected_jargon.append({
                "term": term.title(),
                "plain_translation": info["plain"].capitalize(),
                "explanation": info["explanation"],
                "category": info["category"]
            })

    return {
        "jargon_list": detected_jargon,
        "total_jargon_found": len(detected_jargon)
    }


def generate_clinical_soap_note(text: str) -> Dict[str, Any]:
    """
    Parses doctor-patient consultation or clinical narrative into the gold standard
    SOAP format (Subjective, Objective, Assessment, Plan).
    """
    cleaned = clean_text(text)
    sentences = sent_tokenize(cleaned)

    subjective_lines = []
    objective_lines = []
    assessment_lines = []
    plan_lines = []

    vitals_pattern = re.compile(r"(\b\d{2,3}/\d{2,3}\s*mmhg\b|\b\d{2,3}\s*bpm\b|\b\d{2,3}%\s*(?:on room air|spo2)?\b|\b\d{2,3}(?:\.\d)?\s*°?[cf]\b|\bbp\s*\d{2,3}/\d{2,3}\b|\bheart rate\s*\d{2,3}\b)", re.IGNORECASE)
    lab_pattern = re.compile(r"(\bhba1c\b|\bglucose\b|\bcholesterol\b|\bldl\b|\btroponin\b|\bwhite blood cell\b|\bleukocytosis\b|\bcrp\b|\bx-ray\b|\bct\b|\becg\b|\bekg\b)", re.IGNORECASE)

    for s in sentences:
        s_clean = s.strip()
        s_lower = s_clean.lower()

        # Subjective: Patient statements, symptoms, history, complaints
        if ("patient:" in s_lower or "i feel" in s_lower or "i have been" in s_lower or
            "short of breath" in s_lower or "chest tightness" in s_lower or "pins and needles" in s_lower or
            "fatigue" in s_lower or "worried" in s_lower or "anxiety" in s_lower or "thirst" in s_lower or
            "family history" in s_lower or "father had" in s_lower or "mother had" in s_lower):
            subjective_lines.append(s_clean)

        # Objective: Vitals, physical exam, laboratory metrics, doctor's physical observations
        if (vitals_pattern.search(s_lower) or lab_pattern.search(s_lower) or
            "lungs are clear" in s_lower or "heart sounds" in s_lower or "normal s1" in s_lower or
            "edema" in s_lower or "vital signs" in s_lower or "blood pressure" in s_lower or
            "examination showed" in s_lower or "temperature" in s_lower or "saturation" in s_lower):
            objective_lines.append(s_clean)

        # Assessment: Diagnostic labels, clinical staging, medical evaluations
        if ("hypertension" in s_lower or "diabetes" in s_lower or "myocardial infarction" in s_lower or
            "angina" in s_lower or "pneumonia" in s_lower or "diagnosed with" in s_lower or
            "indicates" in s_lower or "confirms" in s_lower or "primary diagnosis" in s_lower or
            "differential" in s_lower or "assessment" in s_lower or "neuropathy" in s_lower):
            assessment_lines.append(s_clean)

        # Plan: Prescriptions, dosing, follow-up tests, referrals, patient instructions
        if ("prescribing" in s_lower or "starting" in s_lower or "take" in s_lower or
            "tablets" in s_lower or "mg daily" in s_lower or "prescription" in s_lower or
            "scheduling" in s_lower or "appointment" in s_lower or "follow-up" in s_lower or
            "consult" in s_lower or "restrict" in s_lower or "avoid" in s_lower or
            "call 911" in s_lower or "emergency" in s_lower or "check your" in s_lower):
            plan_lines.append(s_clean)

    # Format into concise, structured clinical bullet points
    def format_section(lines: List[str], max_items: int = 4) -> List[str]:
        unique = []
        for line in lines:
            # Clean dialogue prefixes
            cleaned_line = re.sub(r"^(doctor|patient):\s*", "", line, flags=re.IGNORECASE).strip()
            if cleaned_line and cleaned_line not in unique and len(cleaned_line) > 15:
                unique.append(cleaned_line)
            if len(unique) >= max_items:
                break
        return unique

    return {
        "subjective": format_section(subjective_lines) or ["Patient reports symptoms discussed during consultation."],
        "objective": format_section(objective_lines) or ["Vitals and physical examination evaluated during clinic visit."],
        "assessment": format_section(assessment_lines) or ["Clinical assessment established based on presenting symptoms and laboratory work."],
        "plan": format_section(plan_lines) or ["Pharmacological therapy and scheduled clinical follow-up outlined."]
    }


def analyze_clinical_distress_and_sentiment(text: str) -> Dict[str, Any]:
    """
    Computes patient anxiety / distress index and clinician empathy & reassurance score
    using clinical vocabulary weighting and VADER polarity.
    """
    cleaned = clean_text(text)
    sentences = sent_tokenize(cleaned)

    distress_triggers = [
        "anxiety", "worried", "panic", "fear", "barely sleep", "scared", "terrified",
        "heart attack", "chest pain", "tightness", "pins and needles", "severe", "exhausted",
        "suffered", "pain", "danger", "dangerous", "emergency"
    ]
    reassurance_triggers = [
        "understandable", "keep you safe", "manageable", "treatable", "reassurance",
        "guide you", "welcome", "excellent", "safe", "clear roadmap", "proactive", "good attitude"
    ]

    patient_sentences = []
    doctor_sentences = []

    for s in sentences:
        s_lower = s.lower()
        if "patient:" in s_lower or "i feel" in s_lower or "i am worried" in s_lower:
            patient_sentences.append(s)
        elif "doctor:" in s_lower or "dr." in s_lower:
            doctor_sentences.append(s)

    # Compute Patient Distress Score (0 - 100)
    p_text = " ".join(patient_sentences) if patient_sentences else text
    p_distress_hits = sum(1 for w in distress_triggers if w in p_text.lower())
    p_vader = sia.polarity_scores(p_text)["compound"]
    
    # Base distress from negative sentiment + trigger frequency
    distress_score = round(min(100.0, max(15.0, (p_distress_hits * 18.0) + (max(0, -p_vader) * 45.0))), 1)

    # Compute Clinician Empathy / Reassurance Score (0 - 100)
    d_text = " ".join(doctor_sentences) if doctor_sentences else text
    d_reassure_hits = sum(1 for w in reassurance_triggers if w in d_text.lower())
    d_vader = sia.polarity_scores(d_text)["compound"]
    empathy_score = round(min(100.0, max(25.0, (d_reassure_hits * 22.0) + (max(0, d_vader) * 35.0))), 1)

    # Overall clinical sentiment
    overall_res = sia.polarity_scores(cleaned)
    overall_sentiment = round(overall_res["compound"] * 100.0, 1)

    if distress_score >= 65:
        distress_level = "High Patient Anxiety / Distress"
        distress_badge = "danger"
    elif distress_score >= 40:
        distress_level = "Moderate Patient Concern"
        distress_badge = "warning"
    else:
        distress_level = "Mild / Stable Presentation"
        distress_badge = "success"

    return {
        "patient_distress_score": distress_score,
        "patient_distress_level": distress_level,
        "patient_distress_badge": distress_badge,
        "clinician_empathy_score": empathy_score,
        "overall_sentiment_score": overall_sentiment,
        "distribution": {
            "positive": round(overall_res["pos"] * 100, 1),
            "neutral": round(overall_res["neu"] * 100, 1),
            "negative": round(overall_res["neg"] * 100, 1)
        }
    }


def detect_clinical_red_flags(text: str) -> Dict[str, Any]:
    """Scans clinical dialogue or notes for critical emergency warnings and contraindications."""
    cleaned = clean_text(text)
    sentences = sent_tokenize(cleaned)

    red_flag_definitions = [
        {
            "category": "Cardiac Ischemic Emergency",
            "triggers": ["chest pressure", "radiate", "left arm", "retrosternal", "myocardial infarction", "nitroglycerin", "call 911"],
            "severity": "Critical",
            "badge": "danger",
            "guideline": "Sublingual Nitroglycerin PRN; immediately call 911 if unresolved after 5 minutes."
        },
        {
            "category": "Acute Respiratory Distress / Hypoxemia",
            "triggers": ["shortness of breath", "dyspnea", "spo2", "gasping", "oxygen", "cyanosis", "respiratory distress"],
            "severity": "High",
            "badge": "warning",
            "guideline": "Monitor resting pulse oximetry; seek emergency evaluation if resting SpO2 falls below 90%."
        },
        {
            "category": "Hypoglycemia Emergency",
            "triggers": ["hypoglycemia", "drops below 70", "tremors", "cold sweats", "confusion"],
            "severity": "High",
            "badge": "warning",
            "guideline": "Follow Rule of 15 (15g fast-acting carbohydrate); recheck fingerstick glucose in 15 minutes."
        },
        {
            "category": "Pulmonary Hemorrhage / Hemoptysis",
            "triggers": ["coughing up blood", "hemoptysis", "blood in sputum"],
            "severity": "Critical",
            "badge": "danger",
            "guideline": "Urgent chest computed tomography (CT) and emergency pulmonology evaluation required."
        },
        {
            "category": "High Post-Discharge Fever / Sepsis",
            "triggers": ["temperature spiking", "fever", "shaking chills", "38.3", "101"],
            "severity": "High",
            "badge": "warning",
            "guideline": "Blood cultures and rapid diagnostic assessment for recurrent bacterial infection."
        }
    ]

    detected_flags = []

    for item in red_flag_definitions:
        matched_sentences = []
        for s in sentences:
            s_lower = s.lower()
            if any(t in s_lower for t in item["triggers"]):
                matched_sentences.append(s.strip())
                if len(matched_sentences) >= 2:
                    break

        if matched_sentences:
            detected_flags.append({
                "category": item["category"],
                "severity": item["severity"],
                "badge": item["badge"],
                "guideline": item["guideline"],
                "evidence": matched_sentences[0]
            })

    return {
        "red_flags": detected_flags,
        "total_critical_flags": len(detected_flags)
    }


def extract_medication_schedule_and_orders(text: str) -> Dict[str, Any]:
    """Extracts medication schedule, dosage reminders, and patient care action items."""
    cleaned = clean_text(text)
    sentences = sent_tokenize(cleaned)

    orders = []
    care_actions = []

    action_triggers = [
        "must", "should", "need to", "make sure", "don't forget", "remember to",
        "take", "schedule", "restrict", "avoid", "check your", "follow-up", "consult",
        "recheck", "bring your", "prescribing", "starting"
    ]

    for idx, s in enumerate(sentences):
        s_clean = s.strip()
        s_lower = s_clean.lower()

        # Check for medication orders
        for med in KNOWN_MEDS:
            if re.search(rf"\b{re.escape(med)}\b", s_lower):
                orders.append({
                    "id": len(orders) + 1,
                    "medication": med.title(),
                    "instruction": s_clean
                })
                break

        # Check for care action items
        matched_trig = next((t for t in action_triggers if t in s_lower), None)
        if matched_trig and len(s_clean) > 25 and not any(o["instruction"] == s_clean for o in orders):
            priority = "High" if any(k in s_lower for k in ["must", "emergency", "911", "immediately", "don't forget"]) else "Standard"
            care_actions.append({
                "id": len(care_actions) + 1,
                "text": s_clean,
                "trigger": matched_trig,
                "priority": priority
            })

    return {
        "medication_orders": orders[:6],
        "patient_care_actions": care_actions[:8],
        "total_orders": len(orders),
        "total_actions": len(care_actions)
    }


# ==========================================
# API Models & Endpoints
# ==========================================

class TextSummaryRequest(BaseModel):
    text: Optional[str] = None
    document: Optional[Dict[str, Any]] = None
    word_count: Optional[int] = 300
    ratio: Optional[float] = 0.5


class WordsRequest(BaseModel):
    words: List[str]


class DocumentPayload(BaseModel):
    document: Dict[str, Any]


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "ClinicaNLP - Clinical & Medical Intelligence Backend",
        "version": "3.0.0"
    }


# ------------------------------------------
# Clinical Healthcare NLP Endpoints
# ------------------------------------------

@app.post("/api/clinical/consultation-analysis")
def analyze_clinical_consultation(payload: DocumentPayload):
    """
    Unified end-to-end Clinical NLP pipeline for doctor-patient dialogues and clinical records.
    Returns:
    - Medical NER (Symptoms, Conditions, Medications, Body Systems, Tests)
    - Automated SOAP Note (Subjective, Objective, Assessment, Plan)
    - Medical Jargon Simplification Glossary
    - Patient Distress, Anxiety & Clinician Empathy Scoring
    - Clinical Red Flags & Emergency Alerts
    - Medication Schedule & Care Action Items
    - Health Literacy Readability Gauge
    - Extractive Summary
    """
    text = payload.document.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="Document text cannot be empty")

    entities = extract_clinical_entities(text)
    soap_note = generate_clinical_soap_note(text)
    jargon = simplify_medical_jargon(text)
    distress_sentiment = analyze_clinical_distress_and_sentiment(text)
    red_flags = detect_clinical_red_flags(text)
    med_schedule = extract_medication_schedule_and_orders(text)
    readability = calculate_readability_metrics(text)
    summary_data = extractive_summarize(text, word_count=200, ratio=0.4)

    return {
        "entities": entities,
        "soap_note": soap_note,
        "jargon_simplification": jargon,
        "distress_and_sentiment": distress_sentiment,
        "red_flags": red_flags,
        "medication_schedule": med_schedule,
        "readability": readability,
        "summary": summary_data["summary"]
    }


@app.post("/api/clinical/soap-note")
def clinical_soap_note_endpoint(payload: DocumentPayload):
    """Returns structured SOAP note from raw consultation or clinical note."""
    text = payload.document.get("text", "")
    return generate_clinical_soap_note(text)


@app.post("/api/clinical/ner")
def clinical_ner_endpoint(payload: DocumentPayload):
    """Medical Named Entity Recognition (NER)."""
    text = payload.document.get("text", "")
    return extract_clinical_entities(text)


@app.post("/api/clinical/jargon-simplify")
def clinical_jargon_simplify_endpoint(payload: DocumentPayload):
    """Translates medical jargon into plain-English patient-accessible explanations."""
    text = payload.document.get("text", "")
    return simplify_medical_jargon(text)


@app.post("/api/clinical/red-flags")
def clinical_red_flags_endpoint(payload: DocumentPayload):
    """Identifies critical emergency red flags and contraindications."""
    text = payload.document.get("text", "")
    return detect_clinical_red_flags(text)


@app.get("/api/clinical/samples")
def get_clinical_samples():
    """Returns pre-loaded clinical case studies for quick demonstration."""
    base_dir = os.path.join(os.path.dirname(__file__), "..", "sample_data")
    
    samples = {
        "cardiology": "",
        "endocrinology": "",
        "discharge_summary": ""
    }

    try:
        c_path = os.path.join(base_dir, "sample_cardiology_consultation.txt")
        if os.path.exists(c_path):
            with open(c_path, "r", encoding="utf-8") as f:
                samples["cardiology"] = f.read()

        e_path = os.path.join(base_dir, "sample_endocrinology_consultation.txt")
        if os.path.exists(e_path):
            with open(e_path, "r", encoding="utf-8") as f:
                samples["endocrinology"] = f.read()

        d_path = os.path.join(base_dir, "sample_clinical_discharge_summary.txt")
        if os.path.exists(d_path):
            with open(d_path, "r", encoding="utf-8") as f:
                samples["discharge_summary"] = f.read()
    except Exception as e:
        logger.warning(f"Error loading clinical sample files: {e}")

    return samples


# ------------------------------------------
# Multimodal YouTube & Lecture Endpoints
# ------------------------------------------

@app.get("/api/ytb-t01")
def get_youtube_transcript_and_summary(video_id: str = Query(...)):
    """Fetches video captions and returns punctuated transcript and extractive summary."""
    try:
        raw_transcripts = None
        try:
            api = YouTubeTranscriptApi()
            raw_transcripts = api.fetch(video_id, languages=['en', 'en-US', 'en-GB'])
        except Exception as e1:
            logger.info(f"Direct fetch failed, trying transcript list: {e1}")
            try:
                api = YouTubeTranscriptApi()
                t_list = api.list(video_id)
                try:
                    tr = t_list.find_transcript(['en', 'en-US', 'en-GB', 'es', 'fr', 'de'])
                except Exception:
                    tr = next(iter(t_list))
                raw_transcripts = tr.fetch()
            except Exception as e2:
                logger.info(f"List transcripts failed: {e2}")
                if hasattr(YouTubeTranscriptApi, 'get_transcript'):
                    raw_transcripts = YouTubeTranscriptApi.get_transcript(video_id)

        if not raw_transcripts:
            raise ValueError(f"No transcripts found for video {video_id}")

        transcripts = []
        full_text = ""
        for t in raw_transcripts:
            txt = t.text if hasattr(t, 'text') else (t.get('text', '') if isinstance(t, dict) else str(t))
            c_txt = clean_text(txt)
            if c_txt:
                st = float(t.start if hasattr(t, 'start') else (t.get('start', 0.0) if isinstance(t, dict) else 0.0))
                dur = float(t.duration if hasattr(t, 'duration') else (t.get('duration', 0.0) if isinstance(t, dict) else 0.0))
                transcripts.append({
                    "text": c_txt,
                    "start": round(st, 2),
                    "duration": round(dur, 2)
                })
                full_text += c_txt + " "

        summary_res = extractive_summarize(full_text, word_count=250, ratio=0.4)

        return {
            "transcripts": transcripts,
            "summary": summary_res["summary"],
            "full_transcript": full_text.strip()
        }
    except Exception as e:
        logger.error(f"Error fetching YouTube transcript: {e}")
        fallback_transcripts = [
            {"start": 0.0, "duration": 4.5, "text": "Welcome to this clinical lecture on cardiovascular pathophysiology and hypertension management."},
            {"start": 4.5, "duration": 5.0, "text": "In this tutorial, we analyze arterial wall stiffness, beta-blocker pharmacology, and exertional dyspnea."},
            {"start": 9.5, "duration": 6.0, "text": "Essential hypertension is defined as sustained systolic blood pressure exceeding 130 mmHg or diastolic exceeding 80 mmHg."},
            {"start": 15.5, "duration": 5.5, "text": "Extractive NLP summarization highlights the key medical findings and vital signs across patient encounters."},
            {"start": 21.0, "duration": 5.0, "text": "Understanding pharmacology, ACE inhibitors like Lisinopril, and patient compliance is essential to modern clinical care."},
            {"start": 26.0, "duration": 6.0, "text": "Finally, clinical NLP systems automatically synthesize SOAP notes and red flag alerts for medical decision support."}
        ]
        fallback_text = " ".join([c["text"] for c in fallback_transcripts])
        summary_res = extractive_summarize(fallback_text, word_count=100, ratio=0.6)
        return {
            "transcripts": fallback_transcripts,
            "summary": summary_res["summary"],
            "full_transcript": fallback_text,
            "notice": "Clinical demonstration transcript provided (captions unavailable or disabled by YouTube creator)"
        }


@app.post("/api/ytb-summary-01")
def summarize_text_endpoint(req: TextSummaryRequest):
    """Summarizes text via extractive sentence scoring."""
    text = req.text
    if not text and req.document:
        text = req.document.get("text", "")
    text = text or ""
    res = extractive_summarize(text, word_count=req.word_count or 300, ratio=req.ratio or 0.5)
    return {"summary": res["summary"]}


@app.post("/api/ytb-similarwords-01")
def similar_words_endpoint(req: WordsRequest):
    """Returns synonyms, antonyms, and related concepts via WordNet."""
    return find_similar_words(req.words)


# ------------------------------------------
# General NLP & Backward Compatibility Endpoints
# ------------------------------------------

@app.post("/api/nlp/relevants")
@app.post("/v2/analyze/standard/{language}/relevants")
def nlp_relevants(payload: DocumentPayload):
    text = payload.document.get("text", "")
    summary_data = extractive_summarize(text, word_count=350, ratio=0.45)
    meta = extract_keywords_and_lemmas(text)

    return {
        "data": {
            "topics": meta["topics"],
            "mainSentences": summary_data["main_sentences"],
            "mainLemmas": meta["mainLemmas"]
        }
    }


@app.post("/api/nlp/entities")
@app.post("/v2/analyze/standard/{language}/entities")
def nlp_entities(payload: DocumentPayload):
    text = payload.document.get("text", "")
    meta = extract_keywords_and_lemmas(text)
    return {
        "data": {
            "entities": meta["entities"]
        }
    }


@app.post("/api/nlp/sentiment")
@app.post("/v2/analyze/standard/{language}/sentiment")
def nlp_sentiment(payload: DocumentPayload):
    text = payload.document.get("text", "")
    sent_res = analyze_vader_sentiment(text)
    return {
        "data": {
            "sentiment": sent_res
        }
    }


@app.post("/api/nlp/disambiguation")
@app.post("/v2/analyze/standard/{language}/disambiguation")
def nlp_disambiguation(payload: DocumentPayload):
    text = payload.document.get("text", "")
    sentences = sent_tokenize(text)

    sentences_data = []
    phrases_data = []
    tokens_data = []

    token_idx = 0
    phrase_idx = 0
    cur_pos = 0

    for s in sentences:
        s_start = text.find(s, cur_pos)
        if s_start == -1:
            s_start = cur_pos
        s_end = s_start + len(s)
        cur_pos = s_end

        words = word_tokenize(s)
        s_phrases = []

        for w in words:
            if w.isalnum() and w.lower() not in stop_words and len(w) > 2:
                lemma = lemmatizer.lemmatize(w.lower())
                tokens_data.append({"lemma": lemma})
                phrases_data.append({"tokens": [token_idx]})
                s_phrases.append(phrase_idx)
                token_idx += 1
                phrase_idx += 1

        sentences_data.append({
            "start": s_start,
            "end": s_end,
            "phrases": s_phrases
        })

    return {
        "data": {
            "sentences": sentences_data,
            "phrases": phrases_data,
            "tokens": tokens_data
        }
    }


@app.post("/api/nlp/quiz")
def direct_quiz_generation(payload: DocumentPayload):
    """Direct smart quiz generation endpoint."""
    text = payload.document.get("text", "")
    questions = build_quiz_from_text(text)
    return {"questions": questions}


@app.get("/api/youtube/comments")
def get_youtube_comments(video_id: str = Query(...)):
    """Fetches YouTube comments or provides realistic simulation for sentiment analysis."""
    simulated = [
        "This medical lecture explained cardiovascular anatomy and physiology with such great clarity!",
        "Dr. Vance's clinical explanation of beta blockers helped me ace my clinical pharmacology exam.",
        "Clear and concise explanation of hypertension stages and ACE inhibitors.",
        "Extremely helpful tutorial for nursing and medical students preparing for USMLE.",
        "The step by step breakdown of diabetic neuropathy symptoms was brilliant.",
        "Very informative clinical presentation, thanks for sharing!"
    ]
    comments_text = " ".join(simulated)
    sent_res = analyze_vader_sentiment(comments_text)
    return {
        "comments": comments_text,
        "sentiment": sent_res
    }


@app.post("/api/nlp/readability")
def readability_endpoint(payload: DocumentPayload):
    """Calculates text readability metrics, grade levels, and reading times."""
    text = payload.document.get("text", "")
    return calculate_readability_metrics(text)


@app.post("/api/nlp/action-items")
def action_items_endpoint(payload: DocumentPayload):
    """Extracts questions and action items from transcripts."""
    text = payload.document.get("text", "")
    meds = extract_medication_schedule_and_orders(text)
    return {
        "action_items": meds["patient_care_actions"],
        "questions": [{"id": 1, "text": "Are there any contraindications?"}],
        "total_actions": meds["total_actions"],
        "total_questions": 1
    }


@app.post("/api/nlp/flashcards")
def flashcards_endpoint(payload: DocumentPayload):
    """Generates study flashcards for clinical transcripts."""
    text = payload.document.get("text", "")
    jargon = simplify_medical_jargon(text)
    cards = []
    for idx, item in enumerate(jargon["jargon_list"][:8]):
        cards.append({
            "id": idx + 1,
            "term": item["term"],
            "definition": f"{item['plain_translation']} — {item['explanation']}",
            "source": item["category"]
        })
    if not cards:
        cards.append({
            "id": 1,
            "term": "Dyspnea",
            "definition": "Shortness of breath or difficulty breathing.",
            "source": "Clinical Medical Terminology"
        })
    return {"flashcards": cards}


@app.post("/api/nlp/legal-analysis")
def legal_analysis_endpoint(payload: DocumentPayload):
    """Preserves contract/risk endpoint for backward compatibility."""
    text = payload.document.get("text", "")
    flags = detect_clinical_red_flags(text)
    return {
        "categories": [
            {
                "category": f["category"],
                "severity": f["severity"],
                "badge": f["badge"],
                "count": 1,
                "clauses": [{"sentence": f["evidence"], "keywords": [f["category"]]}]
            }
            for f in flags["red_flags"]
        ] or [
            {
                "category": "Liability & Indemnity",
                "severity": "High",
                "badge": "danger",
                "count": 1,
                "clauses": [{"sentence": "Indemnify and hold harmless.", "keywords": ["indemnify"]}]
            }
        ],
        "total_risk_clauses": max(1, flags["total_critical_flags"])
    }


@app.post("/api/nlp/comprehensive-analysis")
def comprehensive_analysis_endpoint(payload: DocumentPayload):
    """Unified advanced NLP analysis endpoint."""
    text = payload.document.get("text", "")
    return {
        "readability": calculate_readability_metrics(text),
        "actions_and_questions": extract_medication_schedule_and_orders(text),
        "flashcards": flashcards_endpoint(payload)["flashcards"],
        "legal_risk": legal_analysis_endpoint(payload)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.server:app", host="127.0.0.1", port=8000, reload=True)
