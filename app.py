import json
import os
import re
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter

from flask import Flask, jsonify, redirect, render_template, request, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

with open("questions.json", encoding="utf-8") as f:
    QUESTION_BANK = json.load(f)

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
    "in", "into", "is", "it", "of", "on", "or", "that", "the", "their",
    "this", "to", "was", "what", "when", "which", "with", "you", "your",
}

TOPIC_LIBRARY = {
    "photosynthesis": {
        "spark": "Photosynthesis is the plant kingdom's way of turning sunlight into survival.",
        "core_ideas": [
            "Plants use chlorophyll to capture light energy inside chloroplasts.",
            "The light reaction produces ATP and NADPH, which fuel later synthesis steps.",
            "The Calvin cycle fixes carbon dioxide into glucose using the stored chemical energy.",
        ],
        "exam_traps": [
            "Do not mix up the site of light reaction and Calvin cycle.",
            "Remember glucose is the end product, oxygen is the by-product.",
            "Questions often ask the role of stomata and chlorophyll separately.",
        ],
        "memory_hook": "Think: sunlight in, sugar made, oxygen out.",
    },
    "indian constitution": {
        "spark": "The Indian Constitution is the operating system that keeps every institution aligned.",
        "core_ideas": [
            "It defines powers, limits, and relationships among legislature, executive, and judiciary.",
            "Fundamental Rights protect individuals while Directive Principles guide governance goals.",
            "Amendment provisions balance flexibility with constitutional stability.",
        ],
        "exam_traps": [
            "Fundamental Rights are enforceable, Directive Principles are not directly enforceable.",
            "The Supreme Court is the guardian of the Constitution through judicial review.",
            "Schedules, parts, and amendment procedures are frequent factual traps.",
        ],
        "memory_hook": "Rights protect citizens, principles guide the state, courts protect the balance.",
    },
    "quadratic equations": {
        "spark": "Quadratic equations are pattern machines: once you see the form, solution methods open up.",
        "core_ideas": [
            "The standard form is ax^2 + bx + c = 0 where a cannot be zero.",
            "Solutions can be found by factorization, completing the square, or the quadratic formula.",
            "The discriminant decides the nature of roots before you solve fully.",
        ],
        "exam_traps": [
            "Do not forget to move every term to one side before applying formulas.",
            "The discriminant is b^2 - 4ac, not b^2 + 4ac.",
            "Roots may be equal, distinct, or imaginary depending on the discriminant.",
        ],
        "memory_hook": "Form first, discriminant second, roots third.",
    },
    "cell division": {
        "spark": "Cell division is how life grows, repairs, and passes genetic instructions forward.",
        "core_ideas": [
            "Mitosis creates two identical cells for growth and repair.",
            "Meiosis creates gametes and reduces chromosome number by half.",
            "Chromosome behavior is the key comparison point in most biology exams.",
        ],
        "exam_traps": [
            "Mitosis maintains chromosome number, meiosis reduces it.",
            "Crossing over occurs in meiosis, not in mitosis.",
            "Prophase sequence questions are common and easy to confuse.",
        ],
        "memory_hook": "Mitosis maintains, meiosis mixes.",
    },
}

CONNECTOR_WORDS = {
    "because", "therefore", "however", "moreover", "thus", "first", "second",
    "finally", "for example", "in conclusion", "whereas",
}

TEXT_UPLOAD_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".log"}
QUESTION_STARTERS = (
    "what", "why", "how", "explain", "define", "discuss", "compare", "differentiate",
    "describe", "enumerate", "illustrate", "derive", "prove", "justify", "comment",
    "evaluate", "analyse", "analyze", "list", "write short note", "short note",
)
QUESTION_STYLE_TEMPLATES = {
    "short": "Write a short note on {topic}.",
    "concept": "Explain {topic} with its core logic, structure, and one exam-focused example.",
    "compare": "Differentiate {topic} from a closely related concept with exam-ready points.",
    "analysis": "Analyse the importance of {topic} and explain why it is likely to matter in {exam_label}.",
}

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-5.4")
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")

EXAM_BLUEPRINTS = {
    "UPSC": {
        "Polity": ["Fundamental Rights", "Parliament", "Judiciary"],
        "History": ["National Movement", "Ancient India", "Medieval India"],
        "Geography": ["Indian Geography", "World Geography", "Environment"],
        "Economy": ["Inflation", "Budget", "Banking"],
        "Science": ["Biology", "Physics", "Chemistry"],
    },
    "SSC CGL": {
        "Math": ["Arithmetic", "Algebra", "Geometry"],
        "Reasoning": ["Series", "Coding-Decoding", "Analogies"],
        "English": ["Grammar", "Vocabulary", "Comprehension"],
        "GK": ["Static GK", "Current Affairs", "Science"],
    },
    "SSC CHSL": {
        "Math": ["Percentages", "Ratio", "Time and Work"],
        "Reasoning": ["Classification", "Blood Relations", "Directions"],
        "English": ["Grammar", "Fillers", "Synonyms"],
        "GK": ["History", "Polity", "Science"],
    },
    "RRB NTPC": {
        "Math": ["Simplification", "Profit and Loss", "Mensuration"],
        "Reasoning": ["Seating", "Series", "Puzzle"],
        "General Awareness": ["Railways GK", "Polity", "Current Affairs"],
    },
    "Bank PO": {
        "Quant": ["DI", "Simplification", "Probability"],
        "Reasoning": ["Puzzle", "Syllogism", "Seating Arrangement"],
        "English": ["Reading Comprehension", "Error Spotting", "Cloze Test"],
        "Banking Awareness": ["RBI", "Monetary Policy", "Financial Terms"],
    },
    "Bank Clerk": {
        "Quant": ["Number Series", "Approximation", "Percentages"],
        "Reasoning": ["Inequality", "Input Output", "Coding"],
        "English": ["Fillers", "Para Jumbles", "Error Spotting"],
        "Banking Awareness": ["Static Banking", "Current Affairs", "Digital Banking"],
    },
    "NEET": {
        "Biology": ["Cell Division", "Photosynthesis", "Genetics"],
        "Chemistry": ["Organic Chemistry", "Physical Chemistry", "Inorganic Chemistry"],
        "Physics": ["Mechanics", "Optics", "Current Electricity"],
    },
    "JEE Main": {
        "Math": ["Calculus", "Coordinate Geometry", "Probability"],
        "Chemistry": ["Organic", "Inorganic", "Physical"],
        "Physics": ["Mechanics", "Thermodynamics", "Electrostatics"],
    },
    "JEE Advanced": {
        "Math": ["Advanced Calculus", "Vectors", "3D Geometry"],
        "Chemistry": ["Reaction Mechanism", "Coordination Compounds", "Equilibrium"],
        "Physics": ["Rotation", "Waves", "Modern Physics"],
    },
    "CAT": {
        "VARC": ["Reading Comprehension", "Para Summary", "Critical Reasoning"],
        "DILR": ["Tables", "Games and Tournaments", "Venn Diagrams"],
        "QA": ["Arithmetic", "Algebra", "Geometry"],
    },
    "CUET": {
        "English": ["Grammar", "Vocabulary", "Comprehension"],
        "General Test": ["Reasoning", "Numerical Ability", "Current Affairs"],
        "Domain": ["Accountancy", "Economics", "Biology"],
    },
    "NDA": {
        "Math": ["Algebra", "Trigonometry", "Statistics"],
        "GAT": ["English", "Physics", "History"],
    },
    "CDS": {
        "English": ["Sentence Improvement", "Vocabulary", "Comprehension"],
        "GK": ["History", "Geography", "Polity"],
        "Math": ["Arithmetic", "Geometry", "Trigonometry"],
    },
    "CAPF": {
        "General Ability": ["Security Issues", "Polity", "History"],
        "Essay": ["Internal Security", "Governance", "Society"],
    },
    "State PSC": {
        "Polity": ["State Government", "Constitution", "Governance"],
        "History": ["National Movement", "Regional History", "Culture"],
        "Geography": ["State Geography", "India", "Resources"],
    },
    "UGC NET": {
        "Paper 1": ["Teaching Aptitude", "Research Aptitude", "ICT"],
        "Commerce": ["Management", "Accounting", "Business Environment"],
        "Political Science": ["Political Theory", "Indian Government", "IR"],
    },
    "CTET": {
        "Child Development": ["Learning Theories", "Inclusive Education", "Pedagogy"],
        "Math Pedagogy": ["Concept Teaching", "Error Analysis", "TLM"],
        "EVS": ["Environment", "Pedagogy", "Daily Life Science"],
    },
    "GATE": {
        "General Aptitude": ["Verbal", "Numerical", "Reasoning"],
        "CS": ["DSA", "OS", "DBMS"],
        "EE": ["Machines", "Power Systems", "Network Theory"],
    },
    "EPFO": {
        "Industrial Relations": ["Labour Laws", "Wages", "Social Security"],
        "Accounts": ["Accounting Basics", "Costing", "Audit"],
        "General English": ["Grammar", "Usage", "Comprehension"],
    },
    "LIC AAO": {
        "Quant": ["Arithmetic", "Data Interpretation", "Probability"],
        "Reasoning": ["Puzzle", "Syllogism", "Logical Order"],
        "Insurance Awareness": ["Insurance Terms", "Policies", "Regulation"],
    },
    "NABARD": {
        "Agriculture": ["Agronomy", "Soil Science", "Agri Economics"],
        "Rural Development": ["SHG", "Poverty", "Rural Institutions"],
        "Quant": ["Arithmetic", "DI", "Percentages"],
    },
    "Railway Group D": {
        "Math": ["Simplification", "Ratio", "Mensuration"],
        "Reasoning": ["Classification", "Series", "Puzzle"],
        "General Science": ["Biology", "Physics", "Chemistry"],
        "Current Affairs": ["National", "Sports", "Science and Tech"],
    },
    "IBPS SO": {
        "Reasoning": ["Puzzle", "Seating", "Syllogism"],
        "English": ["Reading Comprehension", "Vocabulary", "Error Detection"],
        "Banking Awareness": ["Banking Terms", "Current Banking", "Regulation"],
        "Professional Knowledge": ["IT", "Law", "HR"],
    },
    "CLAT": {
        "Legal Reasoning": ["Constitutional Law", "Torts", "Contracts"],
        "Logical Reasoning": ["Assumptions", "Arguments", "Inference"],
        "English": ["Comprehension", "Vocabulary", "Tone"],
        "GK": ["Polity", "International Affairs", "Awards"],
    },
    "CUET PG": {
        "General": ["Reasoning", "Language", "Numerical Ability"],
        "Science": ["Biology", "Physics", "Chemistry"],
        "Commerce": ["Accounting", "Business Studies", "Economics"],
        "Humanities": ["History", "Political Science", "Sociology"],
    },
    "Agniveer": {
        "General Knowledge": ["Defence Awareness", "Geography", "Polity"],
        "Reasoning": ["Analogy", "Series", "Coding-Decoding"],
        "Math": ["Arithmetic", "Algebra", "Trigonometry"],
        "Science": ["Physics", "Chemistry", "Biology"],
    },
    "BPSC": {
        "History": ["Modern India", "Bihar History", "National Movement"],
        "Polity": ["Constitution", "Governance", "Panchayati Raj"],
        "Geography": ["Bihar Geography", "India", "Environment"],
        "Economy": ["Budget", "Agriculture", "Development"],
    },
    "REET": {
        "Child Development": ["Pedagogy", "Learning Theories", "Assessment"],
        "Language": ["Grammar", "Comprehension", "Usage"],
        "Math": ["Pedagogy", "Number Sense", "Problem Solving"],
        "EVS": ["Environment", "Pedagogy", "Everyday Science"],
    },
}

OBJECTIVE_EXAMS = {
    "SSC CGL", "SSC CHSL", "RRB NTPC", "Bank PO", "Bank Clerk", "NEET", "JEE Main",
    "JEE Advanced", "CTET", "Railway Group D", "Agniveer", "IBPS SO", "LIC AAO",
    "NABARD", "EPFO", "CUET", "CUET PG",
}

MIXED_FORMAT_EXAMS = {"UPSC", "CAT", "CLAT", "UGC NET", "GATE", "CDS", "NDA", "CAPF", "State PSC", "BPSC"}

SUBJECT_PLAYBOOKS = [
    {
        "aliases": ["operating systems", "operating system"],
        "units": ["Process Management", "CPU Scheduling", "Deadlocks", "Memory Management", "File Systems", "Disk Scheduling"],
        "question_forms": ["Short note", "Long answer", "Diagram/process flow"],
        "visual_focus": "Show a process moving through states, memory blocks, and scheduler decisions.",
    },
    {
        "aliases": ["dbms", "database management system", "database systems"],
        "units": ["ER Model", "Relational Model", "Normalization", "SQL", "Transactions", "Indexing"],
        "question_forms": ["Definition + example", "SQL/problem", "Transaction/normalization long answer"],
        "visual_focus": "Show tables, keys, relationships, and transaction flow as a connected map.",
    },
    {
        "aliases": ["data structures", "data structures and algorithms", "dsa"],
        "units": ["Arrays and Linked Lists", "Stacks and Queues", "Trees", "Graphs", "Sorting", "Searching"],
        "question_forms": ["Algorithm question", "Complexity question", "Application-based theory"],
        "visual_focus": "Display the structure shape, operations, and time-complexity ladder.",
    },
    {
        "aliases": ["computer networks", "networking", "cn"],
        "units": ["OSI and TCP/IP", "Physical Layer", "Data Link Layer", "Network Layer", "Transport Layer", "Application Layer"],
        "question_forms": ["Layer comparison", "Protocol question", "Diagram/flow answer"],
        "visual_focus": "Draw packets moving through layers and protocols.",
    },
    {
        "aliases": ["software engineering"],
        "units": ["SDLC Models", "Requirements Engineering", "Design Principles", "Testing", "Maintenance", "Project Estimation"],
        "question_forms": ["Lifecycle explanation", "Comparison question", "Testing/design long answer"],
        "visual_focus": "Map the software lifecycle from requirements to maintenance.",
    },
    {
        "aliases": ["microeconomics", "micro economics"],
        "units": ["Demand and Supply", "Elasticity", "Consumer Behaviour", "Production", "Cost and Revenue", "Market Structures"],
        "question_forms": ["Graph-based answer", "Short note", "Theory application"],
        "visual_focus": "Show demand-supply curves, elasticity shifts, and market structure comparisons.",
    },
    {
        "aliases": ["macroeconomics", "macro economics"],
        "units": ["National Income", "Inflation", "Money and Banking", "Fiscal Policy", "Monetary Policy", "Business Cycles"],
        "question_forms": ["Definition + causes", "Policy answer", "Graph/explanation"],
        "visual_focus": "Show inflation, output, and policy levers on a macro dashboard.",
    },
    {
        "aliases": ["political science", "polity", "indian constitution"],
        "units": ["Constitutional Framework", "Fundamental Rights", "Parliament", "Judiciary", "Federalism", "Political Thought"],
        "question_forms": ["Short note", "10-marker theory", "Comparison/governance answer"],
        "visual_focus": "Build a governance map linking institutions, rights, and power flow.",
    },
    {
        "aliases": ["physics"],
        "units": ["Mechanics", "Thermodynamics", "Waves and Oscillations", "Electricity and Magnetism", "Optics", "Modern Physics"],
        "question_forms": ["Numerical/problem", "Derivation", "Conceptual explanation"],
        "visual_focus": "Show force, energy, fields, and wave motion with labeled concept scenes.",
    },
    {
        "aliases": ["chemistry"],
        "units": ["Atomic Structure", "Chemical Bonding", "Thermodynamics", "Equilibrium", "Organic Reactions", "Electrochemistry"],
        "question_forms": ["Conceptual explanation", "Reaction/problem", "Mechanism/short note"],
        "visual_focus": "Connect atomic structure, bonding, and reaction flow visually.",
    },
    {
        "aliases": ["biology", "life science"],
        "units": ["Cell Structure", "Genetics", "Photosynthesis", "Human Physiology", "Reproduction", "Ecology"],
        "question_forms": ["Diagram-based answer", "Function/process question", "Short note"],
        "visual_focus": "Use cell/process diagrams and cause-effect biological flows.",
    },
    {
        "aliases": ["mathematics", "maths", "math"],
        "units": ["Algebra", "Calculus", "Coordinate Geometry", "Probability", "Vectors and 3D", "Differential Equations"],
        "question_forms": ["Problem-solving", "Formula derivation", "Application question"],
        "visual_focus": "Present formula ladders, curve shapes, and stepwise solution paths.",
    },
    {
        "aliases": ["english", "english literature", "communication skills"],
        "units": ["Grammar", "Reading Comprehension", "Writing Skills", "Vocabulary", "Poetry or Prose Analysis", "Communication"],
        "question_forms": ["Short note", "Passage analysis", "Grammar/application"],
        "visual_focus": "Show grammar rules, writing structure, and text interpretation layers.",
    },
]


def get_connection():
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row
    return conn


def ensure_column(cursor, table_name, column_name, definition):
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing = {row[1] for row in cursor.fetchall()}
    if column_name not in existing:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users(
            username TEXT PRIMARY KEY,
            password TEXT,
            score INTEGER DEFAULT 0
        )
        """
    )
    ensure_column(cursor, "users", "attempts", "INTEGER DEFAULT 0")
    ensure_column(cursor, "users", "best_score", "INTEGER DEFAULT 0")
    ensure_column(cursor, "users", "weak_areas", "TEXT DEFAULT '[]'")
    ensure_column(cursor, "users", "last_exam", "TEXT DEFAULT ''")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS study_artifacts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner TEXT NOT NULL,
            artifact_type TEXT NOT NULL,
            title TEXT NOT NULL,
            source_topic TEXT DEFAULT '',
            summary TEXT DEFAULT '',
            content TEXT DEFAULT '',
            metadata TEXT DEFAULT '{}',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


init_db()


def normalize_owner(username):
    cleaned = (username or "").strip()
    return cleaned if cleaned else "guest"


def ai_enabled():
    return bool(os.getenv("OPENAI_API_KEY"))


def ai_provider_summary():
    if not ai_enabled():
        return {
            "enabled": False,
            "provider": "local-fallback",
            "model": "rule-engine",
            "image_model": "svg-visualizer",
        }
    return {
        "enabled": True,
        "provider": "openai",
        "model": OPENAI_TEXT_MODEL,
        "image_model": OPENAI_IMAGE_MODEL,
    }


def word_tokens(text):
    return re.findall(r"[A-Za-z][A-Za-z'-]{1,}", text.lower())


def sentence_tokens(text):
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def extract_keywords(text, limit=8):
    counts = Counter(word for word in word_tokens(text) if word not in STOP_WORDS and len(word) > 2)
    return [word for word, _ in counts.most_common(limit)]


def clamp(value, lower, upper):
    return max(lower, min(value, upper))


def build_exam_catalog():
    catalog = []
    seen = set()
    ordered_exams = list(EXAM_BLUEPRINTS.keys()) + [exam for exam in QUESTION_BANK.keys() if exam not in EXAM_BLUEPRINTS]
    for exam in ordered_exams:
        if exam in seen:
            continue
        seen.add(exam)
        blueprint_subjects = EXAM_BLUEPRINTS.get(exam, {})
        bank_subjects = QUESTION_BANK.get(exam, {})
        subject_names = list(blueprint_subjects.keys()) + [name for name in bank_subjects.keys() if name not in blueprint_subjects]
        subjects = []
        question_count = 0
        for subject in subject_names:
            count = len(bank_subjects.get(subject, []))
            question_count += count
            bank_topics = []
            seen_topics = set()
            for question in bank_subjects.get(subject, []):
                topic_name = (question.get("topic") or "").strip()
                if topic_name and topic_name not in seen_topics:
                    seen_topics.add(topic_name)
                    bank_topics.append(topic_name)
            merged_topics = blueprint_subjects.get(subject, []) + [topic for topic in bank_topics if topic not in blueprint_subjects.get(subject, [])]
            subjects.append(
                {
                    "name": subject,
                    "count": count,
                    "topics": merged_topics,
                    "ai_ready": True,
                }
            )
        catalog.append(
            {
                "exam": exam,
                "subjects": subjects,
                "question_count": question_count,
                "ai_ready": True,
            }
        )
    return catalog


def build_exam_atlas_payload():
    catalog = build_exam_catalog()
    tracks = []
    total_topics = 0

    for exam in catalog:
        topic_count = sum(len(subject["topics"]) for subject in exam["subjects"])
        total_topics += topic_count
        signature_subjects = [subject["name"] for subject in exam["subjects"][:3]]
        signature_topics = []
        for subject in exam["subjects"]:
            signature_topics.extend(subject["topics"][:1])

        tracks.append(
            {
                "exam": exam["exam"],
                "question_count": exam["question_count"],
                "subject_count": len(exam["subjects"]),
                "topic_count": topic_count,
                "signature": ", ".join(signature_topics[:3]) or ", ".join(signature_subjects[:3]) or exam["exam"],
                "study_modes": [
                    "Classic bank drills" if exam["question_count"] else "AI infinite drills",
                    "Visual explainers",
                    "Professor answer review",
                ],
                "subjects": exam["subjects"],
            }
        )

    featured = sorted(
        tracks,
        key=lambda item: (item["question_count"] > 0, item["topic_count"], item["subject_count"]),
        reverse=True,
    )[:6]

    return {
        "stats": {
            "total_exams": len(catalog),
            "total_subjects": sum(len(exam["subjects"]) for exam in catalog),
            "total_topics": total_topics,
            "classic_questions": sum(exam["question_count"] for exam in catalog),
        },
        "featured": featured,
        "tracks": tracks,
    }


def normalize_phrase(text):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower())).strip()


def titleize_phrase(text):
    return " ".join(word.capitalize() for word in normalize_phrase(text).split()[:5]) or "General Focus"


def format_study_label(text, fallback="General Subject"):
    cleaned = (text or "").strip()
    if not cleaned:
        return fallback
    acronym_words = {"ai", "ml", "dbms", "dsa", "sql", "os", "cn", "tcp", "ip", "cpu", "ram", "rom", "ugc", "ssc", "rrb"}
    parts = re.split(r"\s+", cleaned)
    fixed = []
    for index, part in enumerate(parts):
        letters = re.sub(r"[^A-Za-z]", "", part)
        if letters.lower() in acronym_words or part.isupper():
            fixed.append(part.upper())
        elif letters.lower() in {"of", "and", "to", "for", "in", "on", "the"} and index != 0:
            fixed.append(part.lower())
        else:
            fixed.append(part[:1].upper() + part[1:])
    return " ".join(fixed)


def subject_alias_match(subject_norm, alias_norm):
    if not subject_norm or not alias_norm:
        return False
    if len(alias_norm) <= 4:
        return subject_norm == alias_norm or subject_norm.startswith(f"{alias_norm} ") or subject_norm.endswith(f" {alias_norm}")
    return alias_norm in subject_norm or subject_norm in alias_norm


def get_subject_playbook(subject_name):
    subject_norm = normalize_phrase(subject_name)
    if not subject_norm:
        return None
    best_match = None
    best_score = -1
    for playbook in SUBJECT_PLAYBOOKS:
        for alias in playbook["aliases"]:
            alias_norm = normalize_phrase(alias)
            if subject_alias_match(subject_norm, alias_norm):
                score = len(alias_norm)
                if score > best_score:
                    best_match = playbook
                    best_score = score
    return best_match


def match_exam_subject_topics(exam_name, subject_name):
    blueprint = EXAM_BLUEPRINTS.get(exam_name, {})
    subject_norm = normalize_phrase(subject_name)
    best_topics = []
    best_score = -1
    for candidate, topics in blueprint.items():
        candidate_norm = normalize_phrase(candidate)
        if subject_alias_match(subject_norm, candidate_norm):
            score = len(candidate_norm)
            if score > best_score:
                best_topics = topics
                best_score = score
    return best_topics


def parse_syllabus_topics(syllabus_text, limit=10):
    topics = []
    seen = set()
    for chunk in re.split(r"[\n,;/|]+", syllabus_text or ""):
        cleaned = re.sub(r"^(unit|module|chapter)\s*\d+\s*[:.\-)]*\s*", "", chunk.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"^\d+\s*[:.\-)]*\s*", "", cleaned).strip(" -")
        if len(cleaned) < 3:
            continue
        label = cleaned if any(char.isupper() for char in cleaned[:12]) else format_study_label(cleaned, cleaned)
        key = normalize_phrase(label)
        if not key or key in seen:
            continue
        seen.add(key)
        topics.append(label[:80])
        if len(topics) >= limit:
            break
    return topics


def infer_assessment_mode(exam_name="", university_name=""):
    if university_name.strip():
        return "theory"
    if exam_name in OBJECTIVE_EXAMS:
        return "objective"
    if exam_name in MIXED_FORMAT_EXAMS:
        return "mixed"
    return "theory"


def build_question_forms(topic, mode, subject_label):
    if mode == "objective":
        return [
            f"MCQ concept check on {topic}.",
            f"Statement-based elimination question from {topic}.",
            f"Application-based trap from {topic} in {subject_label}.",
        ]
    if mode == "mixed":
        return [
            f"10-marker explanation on {topic}.",
            f"Short note on the core framework of {topic}.",
            f"Application or comparison question around {topic}.",
        ]
    return [
        f"Write a short note on {topic}.",
        f"Explain {topic} with structure, example, and importance.",
        f"Draw or describe the most likely diagram/process from {topic}.",
    ]


def split_day_windows(days):
    if days <= 4:
        window_count = 2
    elif days <= 10:
        window_count = 3
    else:
        window_count = 4
    base = max(1, days // window_count)
    extra = days % window_count
    windows = []
    start = 1
    for index in range(window_count):
        span = base + (1 if index < extra else 0)
        end = min(days, start + span - 1)
        windows.append((start, end))
        start = end + 1
        if start > days:
            break
    return windows


def infer_year_label(label, fallback_index):
    match = re.search(r"(19\d{2}|20\d{2})", label or "")
    return match.group(1) if match else f"Source {fallback_index}"


def decode_uploaded_bytes(blob):
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return blob.decode(encoding)
        except UnicodeDecodeError:
            continue
    return blob.decode("utf-8", errors="ignore")


def extract_text_from_upload(file_storage, fallback_index):
    filename = (file_storage.filename or f"paper_{fallback_index}.txt").strip()
    extension = os.path.splitext(filename)[1].lower()
    if extension == ".pdf":
        raise RuntimeError(
            f"{filename}: PDF text extraction is not available in this build. Upload a text file or paste extracted paper text."
        )

    blob = file_storage.read()
    if not blob:
        raise RuntimeError(f"{filename}: the uploaded file is empty.")
    text = decode_uploaded_bytes(blob).strip()
    if not text:
        raise RuntimeError(f"{filename}: no readable text was found.")
    if extension and extension not in TEXT_UPLOAD_EXTENSIONS:
        text = text[:200000]
    return {
        "label": filename,
        "year": infer_year_label(filename, fallback_index),
        "text": text,
        "source": "upload",
    }


def extract_youtube_video_id(video_url):
    if not video_url:
        return ""
    parsed = urllib.parse.urlparse(video_url.strip())
    host = parsed.netloc.lower()
    if "youtu.be" in host:
        return parsed.path.strip("/").split("/")[0]
    if "youtube.com" in host:
        if parsed.path == "/watch":
            return urllib.parse.parse_qs(parsed.query).get("v", [""])[0]
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live"}:
            return parts[1]
    return ""


def fetch_youtube_metadata(video_url):
    video_id = extract_youtube_video_id(video_url)
    metadata = {
        "title": "YouTube Study Video",
        "author": "YouTube Creator",
        "thumbnail_url": "",
        "video_id": video_id,
    }
    if not video_url:
        return metadata
    endpoint = f"https://www.youtube.com/oembed?url={urllib.parse.quote(video_url, safe='')}&format=json"
    try:
        request_obj = urllib.request.Request(endpoint, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request_obj, timeout=6) as response:
            payload = json.loads(response.read().decode("utf-8"))
            metadata["title"] = payload.get("title", metadata["title"])
            metadata["author"] = payload.get("author_name", metadata["author"])
            metadata["thumbnail_url"] = payload.get("thumbnail_url", "")
            return metadata
    except Exception:
        if video_id:
            metadata["title"] = f"YouTube Lesson // {video_id}"
        return metadata


def chunk_items(items, chunk_count=3):
    if not items:
        return []
    size = max(1, (len(items) + chunk_count - 1) // chunk_count)
    return [items[idx: idx + size] for idx in range(0, len(items), size)]


def extract_topic_phrases(text, limit=10):
    terms = [word for word in word_tokens(text) if word not in STOP_WORDS and len(word) > 3]
    bigrams = Counter()
    for first, second in zip(terms, terms[1:]):
        if first == second:
            continue
        bigrams[f"{first} {second}"] += 1

    phrases = [titleize_phrase(phrase) for phrase, score in bigrams.most_common(limit) if score > 1]
    if len(phrases) < limit:
        singles = Counter(terms)
        for word, _ in singles.most_common(limit):
            candidate = titleize_phrase(word)
            if candidate not in phrases:
                phrases.append(candidate)
            if len(phrases) >= limit:
                break
    return phrases[:limit]


def extract_question_candidates(text):
    candidates = []
    seen = set()
    line_candidates = re.split(r"[\r\n]+", text or "")
    sentence_candidates = sentence_tokens(text) if len(line_candidates) < 60 else []

    def maybe_add(raw_value):
        cleaned = re.sub(
            r"^\s*(?:q(?:uestion)?\s*\d+[:.)-]?|\d+\s*[.)-]|[ivxlcdm]+\s*[.)-])\s*",
            "",
            raw_value.strip(),
            flags=re.IGNORECASE,
        ).strip(" -:\t")
        normalized = normalize_phrase(cleaned)
        if not normalized or normalized in seen:
            return
        if len(cleaned) < 24 or len(cleaned) > 260:
            return
        lower = cleaned.lower()
        if (
            "?" in cleaned
            or lower.startswith(QUESTION_STARTERS)
            or any(marker in lower for marker in ["short note", "differentiate", "compare", "justify", "evaluate"])
        ):
            seen.add(normalized)
            candidates.append(cleaned.rstrip("."))

    for line in line_candidates:
        maybe_add(line)
    for sentence in sentence_candidates:
        maybe_add(sentence)
    return candidates


def detect_question_style(question):
    lower = question.lower()
    if any(term in lower for term in ["short note", "list", "define", "state", "enumerate"]):
        return "short"
    if any(term in lower for term in ["compare", "differentiate", "distinguish"]):
        return "compare"
    if any(term in lower for term in ["analyse", "analyze", "evaluate", "justify", "derive", "prove", "critically"]):
        return "analysis"
    return "concept"


def estimate_question_difficulty(question):
    lower = question.lower()
    score = 0
    if len(question.split()) > 14:
        score += 1
    if any(term in lower for term in ["analyse", "analyze", "evaluate", "justify", "derive", "prove", "critically"]):
        score += 2
    elif any(term in lower for term in ["explain", "describe", "discuss", "why", "how", "compare", "differentiate"]):
        score += 1
    if score >= 3:
        return "Hard"
    if score >= 1:
        return "Medium"
    return "Easy"


def build_topic_records(exam, corpus):
    blueprint = EXAM_BLUEPRINTS.get(exam, {})
    lowered = corpus.lower()
    chapter_counts = Counter()
    topic_records = []

    for subject, topics in blueprint.items():
        subject_hits = lowered.count(subject.lower())
        if subject_hits:
            chapter_counts[subject] += subject_hits
        for topic in topics:
            hits = lowered.count(topic.lower())
            if hits:
                chapter_counts[subject] += hits
                topic_records.append({"topic": topic, "chapter": subject, "count": hits})

    if topic_records:
        topic_records.sort(key=lambda item: item["count"], reverse=True)
        return topic_records[:12], chapter_counts

    phrases = extract_topic_phrases(corpus, limit=10)
    for phrase in phrases:
        normalized = normalize_phrase(phrase)
        count = max(1, lowered.count(normalized))
        topic_records.append({"topic": phrase, "chapter": "General Focus", "count": count})
    return topic_records, chapter_counts


def assign_question_topic(question, topic_records):
    question_normalized = normalize_phrase(question)
    question_words = set(question_normalized.split())
    best_record = None
    best_score = 0

    for record in topic_records:
        topic_normalized = normalize_phrase(record["topic"])
        if topic_normalized and topic_normalized in question_normalized:
            return record["topic"], record.get("chapter", "General Focus")
        overlap = len(question_words & set(topic_normalized.split()))
        if overlap > best_score:
            best_score = overlap
            best_record = record

    if best_record and best_score > 0:
        return best_record["topic"], best_record.get("chapter", "General Focus")

    fallback_topic = extract_topic_phrases(question, limit=1)
    return (fallback_topic[0] if fallback_topic else "General Focus"), "General Focus"


def get_topic_profile(topic):
    normalized = topic.strip().lower()
    if normalized in TOPIC_LIBRARY:
        return TOPIC_LIBRARY[normalized]
    for key, profile in TOPIC_LIBRARY.items():
        if key in normalized or normalized in key:
            return profile
    return None


def openai_post(path, payload):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    body = json.dumps(payload).encode("utf-8")
    request_obj = urllib.request.Request(
        f"{OPENAI_BASE_URL}{path}",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request_obj, timeout=90) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"OpenAI API error: {details or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenAI API connection failed: {exc.reason}") from exc


def extract_response_output_text(response_json):
    if response_json.get("output_text"):
        return response_json["output_text"]

    chunks = []
    for item in response_json.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                chunks.append(content.get("text", ""))
            elif content.get("type") == "refusal":
                chunks.append(content.get("refusal", ""))
    return "".join(chunks).strip()


def call_ai_json(schema_name, schema, developer_prompt, user_prompt, effort="medium"):
    response_json = openai_post(
        "/responses",
        {
            "model": OPENAI_TEXT_MODEL,
            "reasoning": {"effort": effort},
            "input": [
                {"role": "developer", "content": developer_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": schema,
                    "strict": True,
                }
            },
        },
    )
    output_text = extract_response_output_text(response_json)
    return json.loads(output_text)


def call_ai_text(developer_prompt, user_prompt, effort="medium"):
    response_json = openai_post(
        "/responses",
        {
            "model": OPENAI_TEXT_MODEL,
            "reasoning": {"effort": effort},
            "input": [
                {"role": "developer", "content": developer_prompt},
                {"role": "user", "content": user_prompt},
            ],
        },
    )
    return extract_response_output_text(response_json)


def call_ai_image(prompt):
    response_json = openai_post(
        "/images/generations",
        {
            "model": OPENAI_IMAGE_MODEL,
            "prompt": prompt,
            "size": "1024x1024",
            "quality": "medium",
        },
    )
    image_data = response_json.get("data", [])
    if image_data and image_data[0].get("b64_json"):
        return {
            "kind": "image",
            "mime_type": "image/png",
            "data_url": f"data:image/png;base64,{image_data[0]['b64_json']}",
            "revised_prompt": image_data[0].get("revised_prompt", ""),
        }
    raise RuntimeError("No image was returned by the model.")


def build_local_visual_payload(topic, bullets):
    title = topic.strip().title() or "Visual Explainer"
    points = bullets[:4] if bullets else [title, "Definition", "Mechanism", "Application"]
    node_positions = [(220, 90), (80, 220), (220, 350), (360, 220)]
    labels = [title] + points[:3]
    circles = []
    texts = []
    lines = [
        '<line x1="220" y1="120" x2="100" y2="200" stroke="#22d3ee" stroke-width="3" opacity="0.7" />',
        '<line x1="220" y1="120" x2="220" y2="320" stroke="#ff7a18" stroke-width="3" opacity="0.7" />',
        '<line x1="220" y1="120" x2="340" y2="200" stroke="#ffd166" stroke-width="3" opacity="0.7" />',
    ]
    for idx, (x, y) in enumerate(node_positions[:len(labels)]):
        radius = 54 if idx == 0 else 46
        fill = "#ff7a18" if idx == 0 else "#101826"
        circles.append(f'<circle cx="{x}" cy="{y}" r="{radius}" fill="{fill}" opacity="0.95" stroke="#ffffff22" stroke-width="2"/>')
        texts.append(
            f'<text x="{x}" y="{y}" text-anchor="middle" fill="#f8fafc" font-size="14" font-family="Trebuchet MS">{labels[idx][:18]}</text>'
        )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="440" height="440" viewBox="0 0 440 440">'
        '<rect width="440" height="440" rx="32" fill="#0d1117"/>'
        '<circle cx="80" cy="60" r="80" fill="#22d3ee22"/>'
        '<circle cx="360" cy="360" r="100" fill="#ff7a1822"/>'
        + "".join(lines + circles + texts)
        + "</svg>"
    )
    return {
        "kind": "svg",
        "mime_type": "image/svg+xml",
        "data_url": f"data:image/svg+xml;utf8,{urllib.parse.quote(svg)}",
        "summary": "Local concept map generated as an instant visual explainer.",
    }


def create_note_modules(topic_title, exam_label, goal_label, profile=None):
    if profile:
        core_ideas = profile["core_ideas"]
        exam_traps = profile["exam_traps"]
        spark = profile["spark"]
        memory_hook = profile["memory_hook"]
    else:
        keywords = extract_keywords(f"{topic_title} {goal_label} {exam_label}", limit=4)
        anchor = ", ".join(keywords[:3]) if keywords else topic_title
        core_ideas = [
            f"Start with the definition, scope, and why {topic_title} matters in real exam language.",
            f"Break {topic_title} into process, parts, and application so each answer has structure.",
            f"Link {topic_title} with examples, keywords, and one high-probability previous-year style angle.",
        ]
        exam_traps = [
            f"Do not write a generic answer; connect {topic_title} with {exam_label} expectations.",
            f"Differentiate core concept vs example in {topic_title} questions.",
            f"Use one precise term or formula early so the evaluator sees clarity immediately.",
        ]
        spark = f"{topic_title} becomes easy once you anchor it to {anchor} and revise it as a pattern, not a paragraph."
        memory_hook = f"Anchor {topic_title} with one keyword chain: concept -> logic -> example -> exam use."

    answer_frame = [
        f"Open with a precise definition of {topic_title}.",
        "Add 2 to 3 organized points instead of one long paragraph.",
        "Close with application, significance, or one comparison.",
    ]
    micro_plan = [
        f"5 min: read the spark note and headline points for {topic_title}.",
        "10 min: convert the points into your own language.",
        "5 min: answer the rapid-fire questions aloud.",
        "2 min: write one mistake you must avoid in the exam.",
    ]
    concept_web = [
        topic_title,
        f"{topic_title} -> mechanism",
        f"{topic_title} -> exam application",
        f"{topic_title} -> common trap",
    ]
    professor_pitch = (
        f"If a professor asks for a 45-second explanation of {topic_title}, define it first, explain the working logic, and end with one sharp application."
    )
    rapid_fire = [
        f"What is the one-line definition of {topic_title}?",
        f"Which sub-part of {topic_title} is most likely to appear in {exam_label}?",
        f"Can you explain {topic_title} in 30 seconds without looking?",
    ]
    return spark, memory_hook, answer_frame, micro_plan, concept_web, professor_pitch, rapid_fire, core_ideas, exam_traps


def build_notes_payload(topic, exam="", goal="", depth="smart"):
    topic_title = topic.strip().title() or "Untitled Topic"
    exam_label = exam.strip() or "Any Competitive Exam"
    goal_label = goal.strip() or f"Build confident recall for {topic_title}"
    profile = get_topic_profile(topic)
    pieces = create_note_modules(topic_title, exam_label, goal_label, profile)
    spark, memory_hook, answer_frame, micro_plan, concept_web, professor_pitch, rapid_fire, core_ideas, exam_traps = pieces

    depth_map = {
        "quick": "Quick Revision Mode",
        "smart": "Smart Notes Mode",
        "deep": "Deep Dive Mode",
    }
    return {
        "title": f"{topic_title} // Precision Notes",
        "mode": depth_map.get(depth, depth_map["smart"]),
        "exam": exam_label,
        "goal": goal_label,
        "spark": spark,
        "memory_hook": memory_hook,
        "concept_web": concept_web,
        "professor_pitch": professor_pitch,
        "modules": [
            {"label": "Core Frame", "points": core_ideas},
            {"label": "Exam Traps", "points": exam_traps},
            {"label": "Answer Blueprint", "points": answer_frame},
            {"label": "Micro Study Sprint", "points": micro_plan},
        ],
        "rapid_fire": rapid_fire,
    }


def format_notes_payload(payload):
    lines = [payload["title"], payload["spark"], ""]
    for module in payload["modules"]:
        lines.append(f"{module['label']}:")
        lines.extend(f"- {point}" for point in module["points"])
        lines.append("")
    lines.append(f"Memory Hook: {payload['memory_hook']}")
    return "\n".join(lines).strip()


def build_summary_payload(text):
    sentences = sentence_tokens(text)
    if not sentences:
        return {
            "overview": "Paste some content and I will compress it into a high-yield exam brief.",
            "bullet_points": [],
            "keywords": [],
            "flashcards": [],
            "exam_questions": [],
            "lecture_outline": [],
            "professor_take": "",
            "stats": {"words": 0, "reading_minutes": 0},
        }

    tokens = [word for word in word_tokens(text) if word not in STOP_WORDS]
    keyword_counts = Counter(tokens)
    sentence_scores = []
    for idx, sentence in enumerate(sentences):
        unique_words = {word for word in word_tokens(sentence) if word not in STOP_WORDS}
        score = sum(keyword_counts[word] for word in unique_words)
        sentence_scores.append((idx, score, sentence))

    ranked = sorted(sentence_scores, key=lambda item: (item[1], len(item[2])), reverse=True)
    chosen = sorted(ranked[: min(4, len(ranked))], key=lambda item: item[0])
    bullet_points = [item[2] for item in chosen]
    keywords = [word.title() for word, _ in keyword_counts.most_common(6)]

    flashcards = []
    for keyword in keywords[:4]:
        flashcards.append(
            {
                "q": f"What role does {keyword} play in this passage?",
                "a": f"{keyword} is central because it repeatedly appears in the source and anchors the main explanation.",
            }
        )

    return {
        "overview": bullet_points[0],
        "bullet_points": bullet_points,
        "keywords": keywords,
        "flashcards": flashcards,
        "exam_questions": [
            "Explain the central idea of the passage in 40 words.",
            "Write two high-yield keywords from the passage and define them.",
            "State one likely application or implication of the passage.",
        ],
        "lecture_outline": [
            "Open with the core definition or idea in one sentence.",
            "Explain the process, cause, or framework in 2 to 3 bullets.",
            "Close with importance, application, or likely exam angle.",
        ],
        "professor_take": "A faculty member will like this more if the keywords are reused inside a short structured answer, not memorized separately.",
        "stats": {"words": len(text.split()), "reading_minutes": max(1, round(len(text.split()) / 180))},
    }


def format_summary_payload(payload):
    bullets = "\n".join(f"- {point}" for point in payload["bullet_points"])
    keywords = ", ".join(payload["keywords"])
    return f"Overview: {payload['overview']}\n\nKey Points:\n{bullets}\n\nKeywords: {keywords}".strip()


def build_battlecards_payload(topic="", text="", exam=""):
    source = text.strip() or topic.strip()
    exam_label = exam.strip() or "Any Exam"
    if not source:
        return {"title": "Battlecards need a topic or source text.", "memory_system": "", "cards": [], "power_move": ""}

    keywords = extract_keywords(source, limit=6)
    topic_title = topic.strip().title() or (keywords[0].title() if keywords else "Core Topic")
    profile = get_topic_profile(topic or source)
    memory_system = profile["memory_hook"] if profile else f"Use a three-beat chain for {topic_title}: definition, mechanism, exam application."

    seed_words = keywords[:4] or [word.title() for word in word_tokens(source)[:4]]
    cards = []
    for idx, word in enumerate(seed_words, start=1):
        cards.append(
            {
                "title": f"Card {idx}: {word.title()}",
                "trigger": f"What is the fastest way to explain {word.title()} in {exam_label} language?",
                "response": f"Define {word.title()}, attach it to {topic_title}, and give one precise use-case or example.",
                "trap": f"Do not leave {word.title()} as a vague keyword. Tie it to mechanism or significance.",
                "visual": f"Imagine {word.title()} glowing on a control panel that activates {topic_title}.",
            }
        )

    power_move = f"Read each card aloud, cover the answer, and explain it in under 20 seconds. That turns {topic_title} into active recall."
    return {"title": f"{topic_title} Memory Battlecards", "memory_system": memory_system, "cards": cards, "power_move": power_move}


def build_war_room_payload(exam="", hours=2, days=7, topics="", energy="balanced", weak_areas=None):
    exam_label = exam.strip() or "Target Exam"
    hours = clamp(int(hours or 2), 1, 12)
    days = clamp(int(days or 7), 1, 30)
    weak_areas = weak_areas or []
    topic_list = [item.strip().title() for item in topics.split(",") if item.strip()]
    if not topic_list and weak_areas:
        topic_list = [item.strip().title() for item in weak_areas if item.strip()]
    if not topic_list:
        topic_list = ["Core Concepts", "Revision Stack", "Mock Recovery"]

    energy_map = {"calm": "Calm Precision Mode", "balanced": "Balanced Strike Mode", "beast": "High Intensity Beast Mode"}
    daily_plan = []
    for day in range(1, days + 1):
        topic = topic_list[(day - 1) % len(topic_list)]
        focus = "Concept Build" if day % 3 == 1 else "Recall Pressure" if day % 3 == 2 else "Mock Recovery"
        daily_plan.append(
            {
                "day": day,
                "theme": topic,
                "focus": focus,
                "sprints": [
                    f"{max(25, hours * 12)} min: build notes for {topic}",
                    f"{max(20, hours * 10)} min: active recall and battlecards on {topic}",
                    f"{max(15, hours * 8)} min: exam-style answer or mini test",
                ],
                "output": f"Finish day {day} with one page of revision ammo for {topic}.",
            }
        )

    return {
        "mode": energy_map.get(energy, energy_map["balanced"]),
        "exam": exam_label,
        "focus_statement": f"For {exam_label}, your best gains will come from repeating {', '.join(topic_list[:3])} through notes, recall, and timed pressure.",
        "daily_plan": daily_plan,
        "risk_alerts": [
            "Do not start a new chapter before closing one recall loop.",
            "Mock mistakes should become next-day notes, not forgotten pain.",
            "If energy drops, shorten the session but keep the streak alive.",
        ],
        "ritual_stack": [
            "Open with 3 minutes of rapid recall before reading anything.",
            "End every session with one 30-second oral explanation.",
            "After every mock, convert weak topics into notes within the same day.",
        ],
        "scoreboard": [
            "1 point for finishing a note sprint.",
            "2 points for completing active recall without reading.",
            "3 points for a mock review completed on the same day.",
        ],
        "hours": hours,
        "days": days,
    }


def maybe_ai_pass_pathfinder_refine(payload, subject_label, exam_label, university_label, topics):
    if not ai_enabled():
        payload["provider"] = "local"
        return payload

    schema = {
        "type": "object",
        "properties": {
            "headline": {"type": "string"},
            "mission": {"type": "string"},
            "confidence_note": {"type": "string"},
            "question_stack": {"type": "array", "items": {"type": "string"}},
            "survival_rules": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["headline", "mission", "confidence_note", "question_stack", "survival_rules"],
        "additionalProperties": False,
    }
    try:
        refined = call_ai_json(
            "pass_pathfinder_refine",
            schema,
            "You are a high-performance academic mentor. Build exam-saving plans for students who feel lost and need a clear pass-focused roadmap.",
            (
                f"Subject: {subject_label}\n"
                f"Exam: {exam_label or 'University exam'}\n"
                f"University: {university_label or 'General track'}\n"
                f"Detected topics: {', '.join(topics[:8])}\n"
                "Rewrite the headline, mission, confidence note, survival rules, and likely question stack in a high-value student-friendly way."
            ),
            effort="medium",
        )
        payload.update(refined)
        payload["provider"] = "openai"
        return payload
    except Exception:
        payload["provider"] = "local"
        return payload


def build_pass_pathfinder_payload(
    exam="",
    university="",
    semester="",
    subject="",
    days=21,
    hours=3,
    syllabus_text="",
    start_level="blank",
    target_mode="pass",
):
    subject_label = format_study_label(subject, "General Subject")
    exam_label = exam.strip()
    university_label = university.strip()
    semester_label = semester.strip() or "Current Semester"
    days = clamp(int(days or 21), 1, 120)
    hours = clamp(int(hours or 3), 1, 12)
    start_level = (start_level or "blank").strip()
    target_mode = (target_mode or "pass").strip()

    provided_topics = parse_syllabus_topics(syllabus_text, limit=10)
    exam_topics = match_exam_subject_topics(exam_label, subject_label) if exam_label else []
    playbook = get_subject_playbook(subject_label)
    inferred_topics = provided_topics or exam_topics or (playbook["units"][:] if playbook else [])
    if not inferred_topics:
        inferred_topics = extract_topic_phrases(f"{subject_label} {university_label} {semester_label}", limit=6)
    if not inferred_topics:
        inferred_topics = [
            f"Foundations of {subject_label}",
            f"Core Principles of {subject_label}",
            f"Problem Solving in {subject_label}",
            f"Applications of {subject_label}",
            f"Revision and PYQ Focus for {subject_label}",
        ]

    topics = [format_study_label(topic, "Core Unit") for topic in inferred_topics[:8]]
    syllabus_source = (
        "Provided syllabus"
        if provided_topics
        else "Exam blueprint inference"
        if exam_topics
        else "Subject-pattern inference"
        if playbook
        else "General AI inference"
    )
    assessment_mode = infer_assessment_mode(exam_label, university_label)
    target_modes = {
        "pass": "Pass Safely",
        "score": "Score Push",
        "rescue": "Crash Recovery",
    }
    start_labels = {
        "blank": "Zero-to-Start",
        "basic": "Some Idea",
        "revision": "Revision Mode",
    }

    high_cutoff = max(2, min(4, len(topics) // 2 or 2))
    medium_cutoff = min(len(topics), high_cutoff + 2)
    total_hours = days * hours
    chapter_map = []
    question_stack = []
    for index, topic in enumerate(topics):
        priority = "High" if index < high_cutoff else "Medium" if index < medium_cutoff else "Support"
        likely_questions = build_question_forms(topic, assessment_mode, subject_label)
        time_share = max(2, round(total_hours / max(len(topics), 1))) + (2 if priority == "High" else 0)
        chapter_map.append(
            {
                "unit": topic,
                "priority": priority,
                "hours": time_share,
                "why": (
                    f"Start here because {topic} is either foundational or repeatedly connected to other chapters."
                    if priority == "High"
                    else f"Use {topic} after the core units so your understanding becomes exam-ready."
                ),
                "likely_questions": likely_questions[:2],
            }
        )
        question_stack.extend(likely_questions[:2])
    question_stack = list(dict.fromkeys(question_stack))

    windows = split_day_windows(days)
    phase_names = ["Stabilize", "Core Build", "Recall Pressure", "Exam Finish"]
    study_windows = []
    for index, (start_day, end_day) in enumerate(windows):
        main_topic = topics[min(index, len(topics) - 1)]
        backup_topic = topics[min(index + 1, len(topics) - 1)]
        focus_title = phase_names[min(index, len(phase_names) - 1)]
        actions = [
            f"Build one-page notes for {main_topic}.",
            f"Explain {main_topic} aloud and test yourself on {backup_topic}.",
            "End the block with one written answer, mini mock, or oral recall loop.",
        ]
        if start_level == "blank" and index == 0:
            actions.insert(0, "Spend the first session understanding the syllabus map before opening bulky books.")
        study_windows.append(
            {
                "label": f"Days {start_day}-{end_day}" if start_day != end_day else f"Day {start_day}",
                "focus": focus_title,
                "topic": main_topic,
                "actions": actions,
                "checkpoint": f"By the end of this block, {main_topic} should feel explainable without reading.",
            }
        )

    orientation = [
        "Do not start by reading everything. Start by mastering the syllabus map and the top priority units.",
        "Every unit should create one note page, one recall list, and one answer-ready question set.",
        "Use visuals, voice recall, and likely questions together so learning becomes sticky faster.",
    ]
    if start_level == "blank":
        orientation.insert(0, "You are not behind. Your first goal is clarity, not full coverage on day one.")
    if target_mode == "rescue":
        orientation.append("In rescue mode, skip low-weight chapters until the high-priority stack feels stable.")

    survival_rules = [
        "Never study a chapter without creating at least one answer-ready question from it.",
        "After every reading block, close the page and explain the concept in your own words.",
        "If time is short, finish high-priority units deeply instead of touching everything once.",
        "Use PYQ Lab and Mock Arena only after one clean concept pass, not before.",
    ]
    confidence_note = (
        f"With {days} day(s) and about {hours} hour(s) per day, this is a realistic pass path if you stay focused on the priority units."
    )

    visual_scenes = []
    scene_topics = topics[:3]
    for index, topic in enumerate(scene_topics, start=1):
        visual_scenes.append(
            {
                "label": f"3D Scene {index:02d}",
                "topic": topic,
                "direction": (
                    playbook["visual_focus"]
                    if playbook and index == 1
                    else f"Imagine {topic} as a layered board showing definition, working logic, and exam application."
                ),
                "benefit": f"This visual anchor helps {topic} feel recallable instead of abstract.",
            }
        )

    exam_display = exam_label or f"{university_label} {semester_label} Exam".strip() or "Target Exam"
    payload = {
        "headline": f"{subject_label} Pass Pathfinder",
        "mission": (
            f"If you feel lost right now, start with {topics[0]}, then lock {topics[1] if len(topics) > 1 else topics[0]}, "
            f"and use the likely question stack to turn reading into exam preparation fast."
        ),
        "coverage": {
            "exam": exam_display,
            "university": university_label or "Independent Track",
            "semester": semester_label,
            "subject": subject_label,
            "days": days,
            "hours": hours,
            "mode": start_labels.get(start_level, start_labels["blank"]),
            "target": target_modes.get(target_mode, target_modes["pass"]),
            "syllabus_source": syllabus_source,
            "assessment_mode": assessment_mode.title(),
        },
        "orientation": orientation,
        "chapter_map": chapter_map,
        "study_windows": study_windows,
        "question_stack": question_stack[:10],
        "survival_rules": survival_rules,
        "confidence_note": confidence_note,
        "visual_scenes": visual_scenes,
        "visual_topic": topics[0],
        "next_actions": [
            f"Forge notes for {topics[0]} first.",
            f"Run PYQ Lab on {subject_label} after the first concept pass.",
            "Move into Mock Arena once the top two units feel stable.",
        ],
        "provider": "local",
    }
    return maybe_ai_pass_pathfinder_refine(payload, subject_label, exam_label, university_label, topics)


def build_professor_lab_payload(question, answer, exam="", tone="balanced"):
    question = question.strip()
    answer = answer.strip()
    exam_label = exam.strip() or "Any Exam"
    question_keywords = extract_keywords(question, limit=6)
    answer_keywords = extract_keywords(answer, limit=10)
    overlap = sorted(set(question_keywords) & set(answer_keywords))
    sentences = sentence_tokens(answer)
    word_count = len(answer.split())
    connector_hits = sum(1 for item in CONNECTOR_WORDS if item in answer.lower())

    structure_score = clamp(10 + min(len(sentences), 5) * 3 + min(connector_hits, 3) * 2, 0, 25)
    relevance_score = clamp(10 + len(overlap) * 5 + (3 if word_count >= 25 else 0), 0, 25)
    depth_score = clamp(8 + min(word_count // 14, 11) + min(len(answer_keywords), 6), 0, 25)
    exam_fit_score = clamp(
        10 + (3 if word_count >= 40 else 0) + (4 if len(sentences) >= 2 else 0) +
        (3 if any(term in answer.lower() for term in ["for example", "therefore", "in conclusion"]) else 0) +
        (2 if len(overlap) >= 2 else 0),
        0,
        25,
    )
    if word_count < 18:
        structure_score = min(structure_score, 14)
        depth_score = min(depth_score, 12)
        exam_fit_score = min(exam_fit_score, 13)

    overall_score = structure_score + relevance_score + depth_score + exam_fit_score
    band = "Distinction" if overall_score >= 80 else "Strong" if overall_score >= 65 else "Recoverable" if overall_score >= 45 else "Needs Rebuild"
    rubric = [
        {"label": "Structure", "score": structure_score},
        {"label": "Relevance", "score": relevance_score},
        {"label": "Depth", "score": depth_score},
        {"label": "Exam Fit", "score": exam_fit_score},
    ]

    strengths = []
    if structure_score >= 18:
        strengths.append("Answer has a readable flow instead of random statements.")
    if relevance_score >= 18:
        strengths.append("Question keywords are being addressed directly.")
    if depth_score >= 18:
        strengths.append("There is enough detail to feel academically serious.")
    if exam_fit_score >= 18:
        strengths.append("The answer already looks closer to an exam response than casual notes.")
    if not strengths:
        strengths.append("You have started the idea; now it needs better structure and sharper keywords.")

    fixes = []
    if structure_score < 16:
        fixes.append("Break the answer into intro, explanation, and closing impact.")
    if relevance_score < 16:
        fixes.append("Reuse more words from the question so the evaluator sees direct relevance.")
    if depth_score < 16:
        fixes.append("Add one mechanism, one example, or one comparison to deepen the answer.")
    if exam_fit_score < 16:
        fixes.append("End with significance or application so the answer feels complete.")

    topic_anchor = " ".join(word.title() for word in question_keywords[:3]) or "the asked concept"
    student_line = sentences[0] if sentences else f"{topic_anchor} should be introduced with a clear definition."
    tone_map = {
        "supportive": "A good professor would see effort here, but the next draft should be sharper and more structured.",
        "balanced": "This answer has promise, but professors will remember it only if clarity and exam framing improve together.",
        "strict": "A strict evaluator would not accept vague depth; every line must directly serve the question.",
    }

    return {
        "overall_score": overall_score,
        "band": band,
        "verdict": f"{band}: {overall_score}/100. The answer is {'already impressive' if overall_score >= 80 else 'moving in the right direction' if overall_score >= 60 else 'recoverable with structure' if overall_score >= 45 else 'too generic right now'}.",
        "rubric": rubric,
        "strengths": strengths,
        "fixes": fixes,
        "improved_answer": "\n".join([
            f"Definition: {topic_anchor} should be introduced in one precise line connected to {exam_label}.",
            f"Core explanation: {student_line}",
            "Expansion: Add 2 focused points explaining mechanism, significance, or comparison.",
            "Exam finish: End with one line on why the concept matters or where it is applied.",
        ]),
        "viva_questions": [
            f"Define {topic_anchor} without using filler words.",
            f"Why is {topic_anchor} important in {exam_label} style questions?",
            f"Give one example or application connected to {topic_anchor}.",
        ],
        "professor_note": tone_map.get(tone, tone_map["balanced"]),
        "question_keywords": [word.title() for word in question_keywords],
    }


def maybe_ai_notes_payload(topic, exam="", goal="", depth="smart"):
    fallback = build_notes_payload(topic, exam, goal, depth)
    if not ai_enabled():
        fallback["provider"] = "local"
        return fallback

    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "mode": {"type": "string"},
            "exam": {"type": "string"},
            "goal": {"type": "string"},
            "spark": {"type": "string"},
            "memory_hook": {"type": "string"},
            "concept_web": {"type": "array", "items": {"type": "string"}},
            "professor_pitch": {"type": "string"},
            "rapid_fire": {"type": "array", "items": {"type": "string"}},
            "modules": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "points": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["label", "points"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["title", "mode", "exam", "goal", "spark", "memory_hook", "concept_web", "professor_pitch", "rapid_fire", "modules"],
        "additionalProperties": False,
    }
    try:
        payload = call_ai_json(
            "study_notes_payload",
            schema,
            "You create premium exam notes for Indian competitive exams. Keep them crisp, structured, memorable, and student-friendly.",
            (
                f"Create a study notes payload for topic: {topic}\n"
                f"Exam: {exam or 'Any Competitive Exam'}\n"
                f"Goal: {goal or 'Confident recall'}\n"
                f"Depth: {depth}\n"
                "Return concise but high-value notes with concept web, memory hook, and strong rapid-fire questions."
            ),
            effort="medium",
        )
        payload["provider"] = "openai"
        return payload
    except Exception:
        fallback["provider"] = "local"
        return fallback


def maybe_ai_summary_payload(text):
    fallback = build_summary_payload(text)
    if not ai_enabled():
        fallback["provider"] = "local"
        return fallback

    schema = {
        "type": "object",
        "properties": {
            "overview": {"type": "string"},
            "bullet_points": {"type": "array", "items": {"type": "string"}},
            "keywords": {"type": "array", "items": {"type": "string"}},
            "flashcards": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"q": {"type": "string"}, "a": {"type": "string"}},
                    "required": ["q", "a"],
                    "additionalProperties": False,
                },
            },
            "exam_questions": {"type": "array", "items": {"type": "string"}},
            "lecture_outline": {"type": "array", "items": {"type": "string"}},
            "professor_take": {"type": "string"},
        },
        "required": ["overview", "bullet_points", "keywords", "flashcards", "exam_questions", "lecture_outline", "professor_take"],
        "additionalProperties": False,
    }
    try:
        payload = call_ai_json(
            "summary_payload",
            schema,
            "You compress study material into premium revision output for Indian exam prep. Make it accurate, readable, and exam-useful.",
            f"Summarize this text for exam preparation:\n\n{text}",
            effort="medium",
        )
        payload["stats"] = {"words": len(text.split()), "reading_minutes": max(1, round(len(text.split()) / 180))}
        payload["provider"] = "openai"
        return payload
    except Exception:
        fallback["provider"] = "local"
        return fallback


def generate_practice_set_payload(exam, subject, topic="", difficulty="medium", question_count=10, engine="ai"):
    question_count = clamp(int(question_count or 10), 3, 30)
    subject_questions = QUESTION_BANK.get(exam, {}).get(subject, [])
    if engine == "classic" and subject_questions:
        questions = []
        for idx in range(question_count):
            question = subject_questions[idx % len(subject_questions)]
            questions.append(
                {
                    "id": idx + 1,
                    "question": question["question"],
                    "options": question["options"],
                    "answer": question["answer"],
                    "topic": question.get("topic", subject),
                    "explanation": question.get("explanation", ""),
                    "difficulty": difficulty,
                }
            )
        return {
            "set_title": f"{exam} / {subject} / Classic Drill",
            "provider": "local",
            "questions": questions,
        }

    if ai_enabled():
        schema = {
            "type": "object",
            "properties": {
                "set_title": {"type": "string"},
                "questions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string"},
                            "options": {
                                "type": "array",
                                "items": {"type": "string"},
                                "minItems": 4,
                                "maxItems": 4,
                            },
                            "answer": {"type": "string"},
                            "explanation": {"type": "string"},
                            "topic": {"type": "string"},
                            "difficulty": {"type": "string"},
                        },
                        "required": ["question", "options", "answer", "explanation", "topic", "difficulty"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["set_title", "questions"],
            "additionalProperties": False,
        }
        try:
            payload = call_ai_json(
                "practice_set",
                schema,
                "You generate high-quality MCQs for Indian competitive exams. Every question must have exactly one correct answer present in the options, and explanations must be short and clear.",
                (
                    f"Exam: {exam}\nSubject: {subject}\nTopic: {topic or subject}\nDifficulty: {difficulty}\n"
                    f"Question count: {question_count}\n"
                    "Generate a premium mock/practice set aligned to the exam pattern."
                ),
                effort="medium",
            )
            for idx, item in enumerate(payload["questions"], start=1):
                item["id"] = idx
            payload["provider"] = "openai"
            return payload
        except Exception:
            pass

    if subject_questions:
        return generate_practice_set_payload(exam, subject, topic, difficulty, question_count, engine="classic")

    generated = []
    seed_topic = topic or subject or "General Aptitude"
    for idx in range(question_count):
        generated.append(
            {
                "id": idx + 1,
                "question": f"Which statement best captures the core idea of {seed_topic} for {exam}?",
                "options": [
                    f"It explains the main concept of {seed_topic}",
                    f"It is unrelated to {seed_topic}",
                    f"It can never appear in {exam}",
                    f"It replaces all revision",
                ],
                "answer": f"It explains the main concept of {seed_topic}",
                "explanation": f"For fallback mode, the question checks whether the learner recognizes the main concept of {seed_topic}.",
                "topic": seed_topic,
                "difficulty": difficulty,
            }
        )
    return {"set_title": f"{exam} / {subject} / Smart Fallback Set", "provider": "local", "questions": generated}


def generate_wrong_answer_review(question, selected, exam="", subject=""):
    correct = question.get("answer", "")
    explanation = question.get("explanation", "")
    fallback = {
        "correct_answer": correct,
        "why_wrong": f"You selected '{selected}' but the question expects '{correct}'.",
        "explanation": explanation or "Revisit the underlying concept and compare each option with the definition asked.",
        "repair_steps": [
            f"Read the question stem again and identify the asked concept in {question.get('topic', subject)}.",
            f"Note why '{correct}' fits better than '{selected}'.",
            "Revise this concept once more and attempt a similar question.",
        ],
        "visual_prompt": f"Concept map for {question.get('topic', subject)}",
        "provider": "local",
    }
    if not ai_enabled():
        return fallback

    schema = {
        "type": "object",
        "properties": {
            "correct_answer": {"type": "string"},
            "why_wrong": {"type": "string"},
            "explanation": {"type": "string"},
            "repair_steps": {"type": "array", "items": {"type": "string"}},
            "visual_prompt": {"type": "string"},
        },
        "required": ["correct_answer", "why_wrong", "explanation", "repair_steps", "visual_prompt"],
        "additionalProperties": False,
    }
    try:
        payload = call_ai_json(
            "wrong_answer_review",
            schema,
            "You analyze why a student got a competitive exam question wrong. Be concise, supportive, and instructional.",
            (
                f"Exam: {exam}\nSubject: {subject}\nQuestion: {question.get('question', '')}\n"
                f"Options: {json.dumps(question.get('options', []), ensure_ascii=True)}\n"
                f"Student answer: {selected}\nCorrect answer: {correct}\nKnown explanation: {explanation}"
            ),
            effort="low",
        )
        payload["provider"] = "openai"
        return payload
    except Exception:
        return fallback


def generate_visual_payload(topic, context="", exam=""):
    bullets = sentence_tokens(context)[:4] or extract_keywords(f"{topic} {context}", limit=4)
    if ai_enabled():
        try:
            image = call_ai_image(
                f"Create a clean, educational, diagram-like visual for Indian exam prep about {topic}. "
                f"Make it easy to understand, labeled, visually clear, and suitable for students preparing for {exam or 'competitive exams'}. "
                f"Focus on concepts from: {context[:400]}"
            )
            image["summary"] = "AI-generated study visual created for quick concept understanding."
            image["provider"] = "openai"
            return image
        except Exception:
            pass
    visual = build_local_visual_payload(topic, bullets)
    visual["provider"] = "local"
    return visual


def build_ai_studio_payload(topic, exam="", style="visual map", goal="strong recall"):
    topic_label = topic.strip().title() or "Study Concept"
    exam_label = exam or "Any Competitive Exam"
    style_label = style or "visual map"
    goal_label = goal or "strong recall"
    profile = get_topic_profile(topic)
    keywords = extract_keywords(f"{topic_label} {exam_label} {goal_label}", limit=6)

    fallback = {
        "title": f"{topic_label} Immersion Deck",
        "hook": (
            profile["spark"]
            if profile
            else f"The best way to master {topic_label} is to see it through the flow of definition, mechanism, and exam application."
        ),
        "style": style_label,
        "goal": goal_label,
        "learning_path": [
            f"Start with the one-line meaning of {topic_label}.",
            f"Break {topic_label} into 3 exam-ready building blocks for {exam_label}.",
            f"Convert {topic_label} into one visual pattern and one memory chain.",
            f"Close with one self-test round before moving to the next concept.",
        ],
        "board_flow": [
            {"label": "Frame 01", "detail": f"Write the core definition of {topic_label} in 12 to 18 words."},
            {"label": "Frame 02", "detail": f"Show the internal logic, process, or structure behind {topic_label}."},
            {"label": "Frame 03", "detail": f"Add one exam trap, one example, and one recall shortcut for {topic_label}."},
        ],
        "memory_anchors": [
            profile["memory_hook"] if profile else f"{topic_label}: concept -> logic -> example -> exam use",
            f"Keyword chain: {' -> '.join(keywords[:4])}" if keywords else f"{topic_label} -> trigger -> recall",
            f"Use {style_label} mode to replay {topic_label} in under 30 seconds.",
        ],
        "rapid_check": [
            f"What is the core definition of {topic_label}?",
            f"Which part of {topic_label} is most likely to appear in {exam_label}?",
            f"What is one common trap students make in {topic_label}?",
        ],
        "challenge_prompts": [
            f"Explain {topic_label} as if you are teaching a first-year student in 25 seconds.",
            f"Write one MCQ and one descriptive question from {topic_label}.",
            f"Link {topic_label} with a real exam or classroom scenario.",
        ],
        "professor_bridge": f"Professor tip: start {topic_label} with structure first, then add one precise example so the evaluator sees clarity immediately.",
        "campus_pitch": f"Use this deck before mock practice so {topic_label} shifts from passive reading to active retrieval for {exam_label}.",
        "provider": "local",
    }

    if ai_enabled():
        schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "hook": {"type": "string"},
                "style": {"type": "string"},
                "goal": {"type": "string"},
                "learning_path": {"type": "array", "items": {"type": "string"}},
                "board_flow": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "detail": {"type": "string"},
                        },
                        "required": ["label", "detail"],
                        "additionalProperties": False,
                    },
                },
                "memory_anchors": {"type": "array", "items": {"type": "string"}},
                "rapid_check": {"type": "array", "items": {"type": "string"}},
                "challenge_prompts": {"type": "array", "items": {"type": "string"}},
                "professor_bridge": {"type": "string"},
                "campus_pitch": {"type": "string"},
            },
            "required": [
                "title",
                "hook",
                "style",
                "goal",
                "learning_path",
                "board_flow",
                "memory_anchors",
                "rapid_check",
                "challenge_prompts",
                "professor_bridge",
                "campus_pitch",
            ],
            "additionalProperties": False,
        }
        try:
            payload = call_ai_json(
                "ai_studio_payload",
                schema,
                "You turn study concepts into immersive teaching decks for Indian students. Be vivid, exam-relevant, memorable, and cleanly structured.",
                (
                    f"Topic: {topic_label}\n"
                    f"Exam: {exam_label}\n"
                    f"Learning style: {style_label}\n"
                    f"Goal: {goal_label}\n"
                    "Return a premium teaching deck with learning path, board flow, memory anchors, rapid checks, and challenge prompts."
                ),
                effort="medium",
            )
            payload["provider"] = "openai"
            payload["visual"] = generate_visual_payload(
                topic_label,
                context=" ".join(payload["learning_path"] + payload["memory_anchors"] + [payload["professor_bridge"]]),
                exam=exam_label,
            )
            return payload
        except Exception:
            pass

    fallback["visual"] = generate_visual_payload(
        topic_label,
        context=" ".join(fallback["learning_path"] + fallback["memory_anchors"] + [fallback["professor_bridge"]]),
        exam=exam_label,
    )
    return fallback


def build_video_notes_payload(video_url, transcript="", exam="", focus="", note_style="smart"):
    metadata = fetch_youtube_metadata(video_url)
    exam_label = exam.strip() or "Any Competitive Exam"
    focus_label = focus.strip() or metadata["title"]
    source_text = transcript.strip() or f"{metadata['title']}. Focus area: {focus_label}."
    summary = maybe_ai_summary_payload(source_text)
    battlecards = build_battlecards_payload(topic=focus_label, text=source_text, exam=exam_label)
    source_sentences = sentence_tokens(transcript)[:12] if transcript.strip() else summary["bullet_points"][:]
    blocks = []

    for index, chunk in enumerate(chunk_items(source_sentences or summary["lecture_outline"], 3), start=1):
        blocks.append(
            {
                "label": f"Segment {index:02d}",
                "focus": chunk[0] if chunk else focus_label,
                "takeaways": chunk[:3] if chunk else [focus_label],
            }
        )

    return {
        "title": metadata["title"],
        "creator": metadata["author"],
        "video_id": metadata["video_id"],
        "thumbnail_url": metadata["thumbnail_url"],
        "capture_mode": "Transcript Mode" if transcript.strip() else "Link + Focus Mode",
        "overview": summary["overview"],
        "important_notes": summary["bullet_points"],
        "keywords": summary["keywords"],
        "study_blocks": blocks,
        "exam_questions": summary["exam_questions"],
        "action_stack": summary["lecture_outline"] + [
            "Turn one note block into a 30-second oral explanation.",
            "Convert the top two ideas into one short answer before ending the session.",
        ],
        "memory_hook": battlecards["memory_system"],
        "transcript_tip": (
            "Add the transcript or pasted video notes for more precise extraction."
            if not transcript.strip()
            else "Transcript captured successfully. Use the note blocks for active recall."
        ),
        "provider": summary.get("provider", "local"),
        "style": note_style or "smart",
        "focus": focus_label,
        "exam": exam_label,
    }


def maybe_ai_trend_refine(payload, exam_label, course_label, all_questions):
    if not ai_enabled():
        payload["provider"] = "local"
        return payload

    schema = {
        "type": "object",
        "properties": {
            "headline": {"type": "string"},
            "trend_summary": {"type": "string"},
            "confidence_note": {"type": "string"},
            "probable_questions": {"type": "array", "items": {"type": "string"}},
            "study_plan": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["headline", "trend_summary", "confidence_note", "probable_questions", "study_plan"],
        "additionalProperties": False,
    }
    excerpt = "\n".join(all_questions[:18])[:5000]
    try:
        refined = call_ai_json(
            "trend_lab_refine",
            schema,
            "You analyze previous-year exam papers, identify repetition trends, and predict the most probable next questions. Stay practical, evidence-based, and exam-focused.",
            (
                f"Exam: {exam_label}\nCourse: {course_label or exam_label}\n"
                f"Historical question sample:\n{excerpt}\n"
                f"Detected hot topics: {', '.join(payload['most_important_topics'][:8])}\n"
                "Rewrite the headline, trend summary, confidence note, study plan, and probable questions."
            ),
            effort="medium",
        )
        payload.update(refined)
        payload["provider"] = "openai"
        return payload
    except Exception:
        payload["provider"] = "local"
        return payload


def build_trend_lab_payload(exam="", course_title="", goal="", paper_sources=None):
    paper_sources = paper_sources or []
    exam_label = exam.strip() or course_title.strip() or "Uploaded Papers"
    course_label = course_title.strip() or exam_label
    all_questions = []
    year_breakdown = []

    for index, source in enumerate(paper_sources, start=1):
        extracted_questions = extract_question_candidates(source["text"])
        if not extracted_questions:
            extracted_questions = [sentence for sentence in sentence_tokens(source["text"])[:8] if len(sentence) > 24]
        all_questions.extend(extracted_questions)
        year_breakdown.append(
            {
                "label": source.get("year") or infer_year_label(source.get("label", ""), index),
                "question_count": len(extracted_questions),
                "source": source.get("label", f"Paper {index}"),
            }
        )

    if not all_questions:
        all_questions = [
            f"Explain the most important concept in {course_label}.",
            f"Analyse one repeated theme from {course_label}.",
            f"Write a short note on a high-probability chapter from {course_label}.",
        ]

    style_counts = Counter(detect_question_style(question) for question in all_questions)
    difficulty_counts = Counter(estimate_question_difficulty(question) for question in all_questions)
    topic_records, chapter_counts = build_topic_records(exam, "\n".join(all_questions))
    grouped_questions = {}

    for question in all_questions:
        topic, chapter = assign_question_topic(question, topic_records)
        key = (topic, chapter)
        grouped_questions.setdefault(key, []).append(question)

    topicwise_groups = []
    for (topic, chapter), questions in grouped_questions.items():
        local_difficulties = Counter(estimate_question_difficulty(question) for question in questions)
        topicwise_groups.append(
            {
                "topic": topic,
                "chapter": chapter,
                "count": len(questions),
                "difficulty": local_difficulties.most_common(1)[0][0],
                "questions": questions[:5],
            }
        )

    topicwise_groups.sort(key=lambda item: item["count"], reverse=True)
    chapter_priority = []
    if chapter_counts:
        chapter_lookup = {}
        for item in topicwise_groups:
            chapter_lookup.setdefault(item["chapter"], []).append(item["topic"])
        for chapter, weight in chapter_counts.most_common(6):
            chapter_priority.append(
                {
                    "chapter": chapter,
                    "weight": weight,
                    "reason": f"Repeated through {', '.join(chapter_lookup.get(chapter, [])[:3]) or 'multiple recurring questions'}.",
                }
            )
    else:
        for item in topicwise_groups[:6]:
            chapter_priority.append(
                {
                    "chapter": item["topic"],
                    "weight": item["count"],
                    "reason": "This cluster keeps appearing across the uploaded question set.",
                }
            )

    dominant_styles = [style for style, _ in style_counts.most_common(3)] or ["concept"]
    probable_questions = []
    for index, item in enumerate(topicwise_groups[:8]):
        style = dominant_styles[index % len(dominant_styles)]
        template = QUESTION_STYLE_TEMPLATES.get(style, QUESTION_STYLE_TEMPLATES["concept"])
        probable_questions.append(template.format(topic=item["topic"], exam_label=exam_label))

    heatmap = []
    for item in topicwise_groups[:8]:
        trend_signal = "Very Hot" if item["count"] >= 3 else "Emerging" if item["count"] == 2 else "Watchlist"
        heatmap.append(
            {
                "topic": item["topic"],
                "chapter": item["chapter"],
                "frequency": item["count"],
                "trend": trend_signal,
                "difficulty": item["difficulty"],
            }
        )

    covered_years = [item["label"] for item in year_breakdown]
    most_important_topics = [item["topic"] for item in topicwise_groups[:8]]
    confidence_note = (
        "High confidence: multiple paper sources show repeatable patterns and stable topic recurrence."
        if len(year_breakdown) >= 3 and len(all_questions) >= 18
        else "Moderate confidence: good directional signal, but more paper years will sharpen the prediction."
    )
    payload = {
        "headline": f"{course_label} Trend Lab // Predictive Brief",
        "trend_summary": (
            f"Across {len(year_breakdown)} source(s), the strongest repetition is around "
            f"{', '.join(most_important_topics[:4]) or 'core concepts'}. "
            f"The dominant question style is {style_counts.most_common(1)[0][0]} and the dominant difficulty is {difficulty_counts.most_common(1)[0][0]}."
        ),
        "question_volume": len(all_questions),
        "years_covered": covered_years,
        "year_breakdown": year_breakdown,
        "chapter_priority": chapter_priority,
        "topic_heatmap": heatmap,
        "topicwise_groups": topicwise_groups[:6],
        "most_important_topics": most_important_topics,
        "probable_questions": probable_questions,
        "study_plan": [
            f"Start with {chapter_priority[0]['chapter'] if chapter_priority else course_label} because it has the strongest recurrence signal.",
            "Convert every repeated topic into one-page notes and one oral explanation.",
            "Practice the probable questions in full-length answer format before attempting new material.",
            "Use the historical pattern to revise fewer chapters more deeply instead of reading everything once.",
        ],
        "practice_pack": [
            f"Practice prompt {index + 1}: {question}"
            for index, question in enumerate(probable_questions[:6])
        ],
        "goal": goal.strip() or "Predict the most likely questions and prepare the highest-yield topics.",
        "confidence_note": confidence_note,
        "difficulty_profile": {
            "easy": difficulty_counts.get("Easy", 0),
            "medium": difficulty_counts.get("Medium", 0),
            "hard": difficulty_counts.get("Hard", 0),
            "dominant": difficulty_counts.most_common(1)[0][0],
        },
    }
    return maybe_ai_trend_refine(payload, exam_label, course_label, all_questions)


def maybe_ai_pyq_refine(payload, exam_label, subject_label, chapter_filter, question_bank):
    if not ai_enabled():
        payload["provider"] = "local"
        return payload

    schema = {
        "type": "object",
        "properties": {
            "headline": {"type": "string"},
            "summary": {"type": "string"},
            "probable_next": {"type": "array", "items": {"type": "string"}},
            "rapid_revision": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["headline", "summary", "probable_next", "rapid_revision"],
        "additionalProperties": False,
    }
    excerpt = "\n".join(question_bank[:14])[:5000]
    try:
        refined = call_ai_json(
            "pyq_lab_refine",
            schema,
            "You are an exam strategist who organizes previous-year questions into high-yield chapter plans. Stay concise, practical, and exam-useful.",
            (
                f"Exam: {exam_label or 'Any Exam'}\n"
                f"Subject: {subject_label or 'General Subject'}\n"
                f"Focus chapter: {chapter_filter or 'Full subject coverage'}\n"
                f"Question sample:\n{excerpt}\n"
                f"Current hot chapters: {', '.join(payload['most_important_topics'][:6])}\n"
                "Rewrite the headline, summary, probable next questions, and rapid revision stack."
            ),
            effort="medium",
        )
        payload.update(refined)
        payload["provider"] = "openai"
        return payload
    except Exception:
        payload["provider"] = "local"
        return payload


def build_pyq_lab_payload(exam="", subject="", chapter="", question_count=12, difficulty="mixed"):
    exam_label = exam.strip()
    subject_label = subject.strip()
    chapter_filter = chapter.strip()
    question_limit = clamp(int(question_count or 12), 4, 24)
    difficulty_label = (difficulty or "mixed").strip().title()

    subject_questions = QUESTION_BANK.get(exam_label, {}).get(subject_label, [])
    blueprint_topics = EXAM_BLUEPRINTS.get(exam_label, {}).get(subject_label, [])
    source_mode = "Classic PYQ Bank" if subject_questions else "AI Chapter Forecast"

    topic_groups = {}
    if subject_questions:
        for item in subject_questions:
            topic_name = item.get("topic") or subject_label or "Core Topic"
            topic_groups.setdefault(topic_name, []).append(
                {
                    "question": item["question"],
                    "answer": item["answer"],
                    "explanation": item.get("explanation", "Review the concept behind the correct option and turn it into one recall line."),
                    "difficulty": estimate_question_difficulty(item["question"]),
                    "source": "classic",
                }
            )
    else:
        seed_topics = blueprint_topics[:] or ([chapter_filter] if chapter_filter else [])
        if not seed_topics:
            seed_topics = [subject_label or exam_label or "Core Topic"]
        styles = list(QUESTION_STYLE_TEMPLATES.keys())
        per_topic = max(2, min(4, max(question_limit // max(len(seed_topics), 1), 2)))
        for topic_index, topic_name in enumerate(seed_topics[:6], start=1):
            generated = []
            for item_index in range(per_topic):
                style = styles[(topic_index + item_index - 1) % len(styles)]
                template = QUESTION_STYLE_TEMPLATES[style][item_index % len(QUESTION_STYLE_TEMPLATES[style])]
                generated.append(
                    {
                        "question": template.format(topic=topic_name, exam=exam_label or "this exam"),
                        "answer": f"Build the answer around definition, core logic, and one exam-useful application of {topic_name}.",
                        "explanation": f"Use {topic_name} in a structured 3-part answer: concept, mechanism, and relevance to {subject_label or exam_label or 'the exam'}.",
                        "difficulty": "Medium" if difficulty_label == "Mixed" else difficulty_label,
                        "source": "generated",
                    }
                )
            topic_groups[topic_name] = generated

    if chapter_filter:
        filtered_groups = {}
        needle = normalize_phrase(chapter_filter)
        for topic_name, entries in topic_groups.items():
            topic_key = normalize_phrase(topic_name)
            if needle in topic_key or topic_key in needle:
                filtered_groups[topic_name] = entries
                continue
            if any(needle in normalize_phrase(entry["question"]) for entry in entries):
                filtered_groups[topic_name] = entries
        if filtered_groups:
            topic_groups = filtered_groups

    topic_scores = {}
    for topic_name, entries in topic_groups.items():
        topic_scores[topic_name] = len(entries) + (2 if topic_name in blueprint_topics else 0)

    ordered_groups = sorted(topic_groups.items(), key=lambda item: (topic_scores.get(item[0], 0), len(item[1]), item[0]), reverse=True)
    chapter_cards = []
    flat_questions = []
    per_chapter_display = max(2, min(4, question_limit // max(len(ordered_groups), 1) + 1))

    for topic_name, entries in ordered_groups[:6]:
        difficulty_counts = Counter(entry["difficulty"] for entry in entries)
        dominant_difficulty = difficulty_counts.most_common(1)[0][0] if difficulty_counts else difficulty_label
        chapter_cards.append(
            {
                "chapter": topic_name,
                "count": len(entries),
                "difficulty": dominant_difficulty,
                "mastery_signal": (
                    f"{len(entries)} classic question(s) are clustered here, so this chapter is a repeat zone."
                    if any(entry["source"] == "classic" for entry in entries)
                    else f"No direct bank was found, so the system built previous-style drills for {topic_name}."
                ),
                "questions": entries[:per_chapter_display],
            }
        )
        flat_questions.extend(entry["question"] for entry in entries)

    if not chapter_cards:
        chapter_cards = [
            {
                "chapter": chapter_filter or subject_label or exam_label or "Core Topic",
                "count": 1,
                "difficulty": difficulty_label,
                "mastery_signal": "This focus area was generated as a starter chapter because the direct bank is limited.",
                "questions": [
                    {
                        "question": f"Explain the most important idea from {chapter_filter or subject_label or exam_label or 'this topic'}.",
                        "answer": "Start with a definition, move into the mechanism, and close with exam relevance.",
                        "explanation": "Use this as your opening practice question and expand it into a full answer.",
                        "difficulty": difficulty_label,
                        "source": "generated",
                    }
                ],
            }
        ]
        flat_questions = [chapter_cards[0]["questions"][0]["question"]]

    most_important_topics = [card["chapter"] for card in chapter_cards[:5]]
    lead_topic = most_important_topics[0]
    probable_next = []
    for card in chapter_cards[:4]:
        probable_next.append(f"Explain {card['chapter']} with one definition, one mechanism, and one exam application.")
        probable_next.append(f"Write a short note on the recurring traps and scoring angle of {card['chapter']}.")
    if chapter_filter:
        probable_next.insert(0, f"Prepare a full-answer question on {chapter_filter} because it is the active focus filter.")

    deduped_probables = []
    seen_probables = set()
    for question_text in probable_next + flat_questions:
        if question_text in seen_probables:
            continue
        seen_probables.add(question_text)
        deduped_probables.append(question_text)
    probable_next = deduped_probables[:8]

    rapid_revision = [
        f"Start with {lead_topic} because it has the strongest visible repeat signal right now.",
        "Convert each answer explanation into one-line recall prompts before moving to fresh theory.",
        "After every chapter, attempt one oral explanation and one written answer to lock retention.",
    ]
    if len(most_important_topics) > 1:
        rapid_revision.insert(1, f"Pair {lead_topic} with {most_important_topics[1]} and revise them together as a high-yield chapter cluster.")

    practice_lanes = []
    for index, card in enumerate(chapter_cards[:3], start=1):
        practice_lanes.append(
            {
                "label": f"Sprint {index:02d}",
                "focus": card["chapter"],
                "drills": [
                    f"Solve the visible PYQs from {card['chapter']} without looking at the options first.",
                    f"Rewrite one answer from {card['chapter']} in 3 bullet points and then in exam format.",
                    f"Create a quick wrong-answer trap list for {card['chapter']} so revision becomes faster later.",
                ],
            }
        )

    dominant_difficulty = Counter(card["difficulty"] for card in chapter_cards).most_common(1)[0][0]
    payload = {
        "headline": f"{subject_label or exam_label or 'Subject'} PYQ Navigator",
        "summary": (
            f"The strongest chapter signal is around {', '.join(most_important_topics[:3])}. "
            f"Use these topic-wise previous questions to revise less content with more precision."
        ),
        "source_mode": source_mode,
        "coverage": {
            "exam": exam_label or "Custom Track",
            "subject": subject_label or "General Subject",
            "focus": chapter_filter or "Full subject scan",
            "question_total": sum(card["count"] for card in chapter_cards),
            "topic_total": len(chapter_cards),
            "difficulty": dominant_difficulty if difficulty_label == "Mixed" else difficulty_label,
        },
        "chapter_cards": chapter_cards,
        "most_important_topics": most_important_topics,
        "probable_next": probable_next,
        "rapid_revision": rapid_revision,
        "practice_lanes": practice_lanes,
        "visual_topic": lead_topic,
        "provider": "local",
    }
    return maybe_ai_pyq_refine(payload, exam_label, subject_label, chapter_filter, flat_questions)


def save_artifact(owner, artifact_type, title, source_topic, summary, content, metadata=None):
    conn = get_connection()
    cursor = conn.cursor()
    content_value = content if isinstance(content, str) else json.dumps(content, ensure_ascii=True, indent=2)
    metadata_value = json.dumps(metadata or {}, ensure_ascii=True)
    cursor.execute(
        """
        INSERT INTO study_artifacts (owner, artifact_type, title, source_topic, summary, content, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (normalize_owner(owner), artifact_type, title, source_topic, summary, content_value, metadata_value),
    )
    artifact_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return artifact_id


def serialize_artifact(row):
    try:
        metadata = json.loads(row["metadata"] or "{}")
    except json.JSONDecodeError:
        metadata = {}
    return {
        "id": row["id"],
        "owner": row["owner"],
        "artifact_type": row["artifact_type"],
        "title": row["title"],
        "source_topic": row["source_topic"],
        "summary": row["summary"],
        "preview": row["summary"] or row["content"][:180],
        "content": row["content"],
        "metadata": metadata,
        "created_at": row["created_at"],
    }


def get_recent_artifacts(owner, limit=6):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, owner, artifact_type, title, source_topic, summary, content, metadata, created_at
        FROM study_artifacts
        WHERE owner = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (normalize_owner(owner), limit),
    )
    items = [serialize_artifact(row) for row in cursor.fetchall()]
    conn.close()
    return items


def get_vault_payload(username=""):
    owner = normalize_owner(username)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, owner, artifact_type, title, source_topic, summary, content, metadata, created_at
        FROM study_artifacts
        WHERE owner = ?
        ORDER BY id DESC
        LIMIT 40
        """,
        (owner,),
    )
    items = [serialize_artifact(row) for row in cursor.fetchall()]
    conn.close()
    counts = Counter(item["artifact_type"] for item in items)
    return {
        "owner": owner,
        "is_guest": owner == "guest",
        "stats": {
            "total": len(items),
            "notes": counts.get("notes", 0),
            "summaries": counts.get("summary", 0),
            "plans": counts.get("war_room", 0) + counts.get("pass_pathfinder", 0),
            "video": counts.get("video_notes", 0),
            "predictors": counts.get("trend_lab", 0) + counts.get("pyq_lab", 0),
            "professor": counts.get("professor_lab", 0),
            "studio": counts.get("ai_studio", 0),
        },
        "spotlight": items[0] if items else None,
        "items": items,
    }


def build_daily_quest(user_snapshot, recent_artifacts):
    if user_snapshot and user_snapshot["weak_areas"]:
        weak_target = user_snapshot["weak_areas"][0]
        return {
            "title": f"Close {weak_target} today",
            "steps": [
                f"Forge notes for {weak_target}.",
                f"Generate one summary or battlecard set for {weak_target}.",
                "Attempt one mock or oral recall round before ending the session.",
            ],
        }

    artifact_types = {item["artifact_type"] for item in recent_artifacts}
    steps = []
    if "notes" not in artifact_types:
        steps.append("Forge one note pack.")
    if "summary" not in artifact_types:
        steps.append("Compress one chapter.")
    if "professor_lab" not in artifact_types:
        steps.append("Get one answer checked in Professor Lab.")
    if "pass_pathfinder" not in artifact_types:
        steps.append("Build one Pass Pathfinder roadmap for your main subject.")
    if not steps:
        steps = [
            "Review one saved note from your vault.",
            "Do one mock and convert mistakes into notes.",
            "Explain one concept aloud in under 30 seconds.",
        ]
    return {"title": "Daily Momentum Quest", "steps": steps}


def get_user_snapshot(username):
    if not username:
        return None
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT username, score, attempts, best_score, weak_areas, last_exam
        FROM users
        WHERE username = ?
        """,
        (username,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "username": row["username"],
        "score": row["score"] or 0,
        "attempts": row["attempts"] or 0,
        "best_score": row["best_score"] or row["score"] or 0,
        "weak_areas": json.loads(row["weak_areas"] or "[]"),
        "last_exam": row["last_exam"] or "No exam attempted yet",
    }


def get_dashboard_payload(username=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT username, best_score, attempts, score, last_exam
        FROM users
        ORDER BY best_score DESC, attempts DESC, username ASC
        LIMIT 5
        """
    )
    top_users = [dict(row) for row in cursor.fetchall()]
    cursor.execute("SELECT COUNT(*) AS total_users FROM users")
    total_users = cursor.fetchone()["total_users"]
    conn.close()

    catalog = build_exam_catalog()
    user_snapshot = get_user_snapshot(username)
    owner = normalize_owner(username)
    recent_artifacts = get_recent_artifacts(owner, limit=6)
    vault_payload = get_vault_payload(owner)

    mission = (
        f"{user_snapshot['username']}, your current best is {user_snapshot['best_score']}%. Push one more focused attempt to strengthen {', '.join(user_snapshot['weak_areas'][:2]) or 'speed and recall'}."
        if user_snapshot
        else "Start with AI Notes, compress a chapter in Summarizer, then jump into a timed mock."
    )
    return {
        "mission": mission,
        "stats": {
            "total_users": total_users,
            "total_subjects": sum(len(exam["subjects"]) for exam in catalog),
            "total_questions": sum(exam["question_count"] for exam in catalog),
            "exam_count": len(catalog),
            "vault_items": vault_payload["stats"]["total"],
        },
        "user": user_snapshot,
        "top_users": top_users,
        "exam_radar": catalog,
        "recent_artifacts": recent_artifacts,
        "quest": build_daily_quest(user_snapshot, recent_artifacts),
    }


@app.route("/")
def home():
    dashboard_payload = get_dashboard_payload()
    return render_template(
        "index.html",
        catalog=build_exam_catalog(),
        leaderboard_preview=dashboard_payload["top_users"][:3],
        total_questions=sum(exam["question_count"] for exam in build_exam_catalog()),
    )


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/exam-atlas")
def exam_atlas():
    return render_template("exam_atlas.html", atlas=build_exam_atlas_payload())


@app.route("/notes")
def notes():
    return render_template("notes.html", catalog=build_exam_catalog())


@app.route("/pass-pathfinder")
def pass_pathfinder():
    return render_template("pass_pathfinder.html", catalog=build_exam_catalog())


@app.route("/pyq-lab")
def pyq_lab():
    return render_template("pyq_lab.html", catalog=build_exam_catalog())


@app.route("/video-notes")
def video_notes():
    return render_template("video_notes.html", catalog=build_exam_catalog())


@app.route("/summarizer")
def summarizer():
    return render_template("summarizer.html")


@app.route("/ai-studio")
def ai_studio():
    return render_template("ai_studio.html", catalog=build_exam_catalog())


@app.route("/war-room")
def war_room():
    return render_template("war_room.html", catalog=build_exam_catalog())


@app.route("/trend-lab")
def trend_lab():
    return render_template("trend_lab.html", catalog=build_exam_catalog())


@app.route("/professor-lab")
def professor_lab():
    return render_template("professor_lab.html", catalog=build_exam_catalog())


@app.route("/vault")
def vault():
    return render_template("vault.html")


@app.route("/mock")
def mock():
    return render_template("mock.html", catalog=build_exam_catalog())


@app.route("/practice")
def practice():
    return redirect(url_for("mock"))


@app.route("/login")
def login_page():
    return render_template("login.html")


@app.route("/leaderboard")
def leaderboard():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT username, score, attempts, best_score, last_exam
        FROM users
        ORDER BY best_score DESC, attempts DESC, username ASC
        """
    )
    users = cursor.fetchall()
    conn.close()
    return render_template("leaderboard.html", users=users)


@app.route("/api/catalog")
def catalog():
    return jsonify({"catalog": build_exam_catalog(), "ai": ai_provider_summary()})


@app.route("/api/exam-atlas")
def exam_atlas_api():
    return jsonify({"atlas": build_exam_atlas_payload(), "ai": ai_provider_summary()})


@app.route("/api/dashboard")
def dashboard_api():
    return jsonify(get_dashboard_payload(request.args.get("username", "").strip()))


@app.route("/api/vault")
def vault_api():
    return jsonify(get_vault_payload(request.args.get("username", "").strip()))


@app.route("/api/ai-status")
def ai_status():
    return jsonify(ai_provider_summary())


@app.route("/register", methods=["POST"])
def register():
    data = request.get_json(force=True)
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if len(username) < 3 or len(password) < 4:
        return jsonify({"msg": "invalid"})

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE username = ?", (username,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"msg": "exists"})

    cursor.execute(
        """
        INSERT INTO users (username, password, score, attempts, best_score, weak_areas, last_exam)
        VALUES (?, ?, 0, 0, 0, '[]', '')
        """,
        (username, generate_password_hash(password)),
    )
    conn.commit()
    conn.close()
    return jsonify({"msg": "ok"})


@app.route("/login_user", methods=["POST"])
def login_user():
    data = request.get_json(force=True)
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return jsonify({"msg": "fail"})

    stored_password = row["password"]
    is_hash = stored_password.startswith("pbkdf2:") or stored_password.startswith("scrypt:")
    is_valid = check_password_hash(stored_password, password) if is_hash else stored_password == password
    return jsonify({"msg": "success" if is_valid else "fail"})


@app.route("/api/notes", methods=["POST"])
def api_notes():
    data = request.get_json(force=True)
    topic = data.get("topic", "").strip()
    if not topic:
        return jsonify({"error": "Topic is required."}), 400
    return jsonify(maybe_ai_notes_payload(topic, data.get("exam", ""), data.get("goal", ""), data.get("depth", "smart")))


@app.route("/api/video-notes", methods=["POST"])
def api_video_notes():
    data = request.get_json(force=True)
    video_url = data.get("video_url", "").strip()
    transcript = data.get("transcript", "").strip()
    focus = data.get("focus", "").strip()
    if not video_url and not transcript:
        return jsonify({"error": "Add a YouTube URL or paste transcript text."}), 400
    return jsonify(
        build_video_notes_payload(
            video_url=video_url,
            transcript=transcript,
            exam=data.get("exam", "").strip(),
            focus=focus,
            note_style=data.get("style", "smart"),
        )
    )


@app.route("/generate_notes", methods=["POST"])
def generate_notes():
    data = request.get_json(force=True)
    topic = data.get("topic", "").strip()
    if not topic:
        return jsonify({"notes": "Please enter a topic first."}), 400
    return jsonify({"notes": format_notes_payload(maybe_ai_notes_payload(topic, data.get("exam", ""), data.get("goal", ""), data.get("depth", "smart")))})


@app.route("/api/summarize", methods=["POST"])
def api_summarize():
    data = request.get_json(force=True)
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Text is required."}), 400
    return jsonify(maybe_ai_summary_payload(text))


@app.route("/generate_summary", methods=["POST"])
def generate_summary():
    data = request.get_json(force=True)
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"summary": "Paste some text first."}), 400
    return jsonify({"summary": format_summary_payload(maybe_ai_summary_payload(text))})


@app.route("/api/battlecards", methods=["POST"])
def api_battlecards():
    data = request.get_json(force=True)
    topic = data.get("topic", "").strip()
    text = data.get("text", "").strip()
    if not topic and not text:
        return jsonify({"error": "Topic or source text is required."}), 400
    return jsonify(build_battlecards_payload(topic=topic, text=text, exam=data.get("exam", "")))


@app.route("/api/war-room", methods=["POST"])
def api_war_room():
    data = request.get_json(force=True)
    return jsonify(
        build_war_room_payload(
            exam=data.get("exam", ""),
            hours=data.get("hours", 2),
            days=data.get("days", 7),
            topics=data.get("topics", ""),
            energy=data.get("energy", "balanced"),
            weak_areas=data.get("weak_areas", []),
        )
    )


@app.route("/api/trend-lab", methods=["POST"])
def api_trend_lab():
    uploaded_files = request.files.getlist("papers")
    paper_sources = []
    errors = []

    pasted_text = request.form.get("papers_text", "").strip()
    if pasted_text:
        paper_sources.append(
            {
                "label": "Pasted Papers",
                "year": infer_year_label(pasted_text.splitlines()[0] if pasted_text.splitlines() else "", 0),
                "text": pasted_text,
                "source": "paste",
            }
        )

    for index, upload in enumerate(uploaded_files, start=1):
        if not upload or not (upload.filename or "").strip():
            continue
        try:
            paper_sources.append(extract_text_from_upload(upload, index))
        except RuntimeError as exc:
            errors.append(str(exc))

    if not paper_sources:
        return jsonify({"error": "Upload at least one text-based paper file or paste previous-year paper text.", "errors": errors}), 400

    payload = build_trend_lab_payload(
        exam=request.form.get("exam", "").strip(),
        course_title=request.form.get("course_title", "").strip(),
        goal=request.form.get("goal", "").strip(),
        paper_sources=paper_sources,
    )
    payload["warnings"] = errors
    return jsonify(payload)


@app.route("/api/practice-set", methods=["POST"])
def api_practice_set():
    data = request.get_json(force=True)
    exam = data.get("exam", "").strip()
    subject = data.get("subject", "").strip()
    if not exam or not subject:
        return jsonify({"error": "Exam and subject are required."}), 400
    return jsonify(
        generate_practice_set_payload(
            exam=exam,
            subject=subject,
            topic=data.get("topic", "").strip(),
            difficulty=data.get("difficulty", "medium"),
            question_count=data.get("question_count", 10),
            engine=data.get("engine", "ai"),
        )
    )


@app.route("/api/pass-pathfinder", methods=["POST"])
def api_pass_pathfinder():
    data = request.get_json(force=True)
    subject = data.get("subject", "").strip()
    if not subject:
        return jsonify({"error": "Subject is required."}), 400
    return jsonify(
        build_pass_pathfinder_payload(
            exam=data.get("exam", "").strip(),
            university=data.get("university", "").strip(),
            semester=data.get("semester", "").strip(),
            subject=subject,
            days=data.get("days", 21),
            hours=data.get("hours", 3),
            syllabus_text=data.get("syllabus", "").strip(),
            start_level=data.get("start_level", "blank"),
            target_mode=data.get("target_mode", "pass"),
        )
    )


@app.route("/api/pyq-lab", methods=["POST"])
def api_pyq_lab():
    data = request.get_json(force=True)
    exam = data.get("exam", "").strip()
    subject = data.get("subject", "").strip()
    if not exam or not subject:
        return jsonify({"error": "Exam and subject are required."}), 400
    return jsonify(
        build_pyq_lab_payload(
            exam=exam,
            subject=subject,
            chapter=data.get("chapter", "").strip(),
            question_count=data.get("question_count", 12),
            difficulty=data.get("difficulty", "mixed"),
        )
    )


@app.route("/api/professor-lab", methods=["POST"])
def api_professor_lab():
    data = request.get_json(force=True)
    question = data.get("question", "").strip()
    answer = data.get("answer", "").strip()
    if not question or not answer:
        return jsonify({"error": "Question and answer are required."}), 400
    return jsonify(build_professor_lab_payload(question, answer, data.get("exam", ""), data.get("tone", "balanced")))


@app.route("/api/ai-studio", methods=["POST"])
def api_ai_studio():
    data = request.get_json(force=True)
    topic = data.get("topic", "").strip()
    if not topic:
        return jsonify({"error": "Topic is required."}), 400
    return jsonify(
        build_ai_studio_payload(
            topic,
            data.get("exam", "").strip(),
            data.get("style", "").strip(),
            data.get("goal", "").strip(),
        )
    )


@app.route("/api/question-review", methods=["POST"])
def api_question_review():
    data = request.get_json(force=True)
    question = data.get("question", {})
    if not question or not data.get("selected", "").strip():
        return jsonify({"error": "Question and selected answer are required."}), 400
    return jsonify(
        generate_wrong_answer_review(
            question=question,
            selected=data.get("selected", "").strip(),
            exam=data.get("exam", ""),
            subject=data.get("subject", ""),
        )
    )


@app.route("/api/visual-explainer", methods=["POST"])
def api_visual_explainer():
    data = request.get_json(force=True)
    topic = data.get("topic", "").strip()
    context = data.get("context", "").strip()
    if not topic and not context:
        return jsonify({"error": "Topic or context is required."}), 400
    return jsonify(generate_visual_payload(topic or "Concept", context, data.get("exam", "")))


@app.route("/api/save-artifact", methods=["POST"])
def api_save_artifact():
    data = request.get_json(force=True)
    artifact_type = data.get("artifact_type", "").strip()
    title = data.get("title", "").strip()
    if not artifact_type or not title:
        return jsonify({"error": "Artifact type and title are required."}), 400

    artifact_id = save_artifact(
        owner=data.get("username", ""),
        artifact_type=artifact_type,
        title=title,
        source_topic=data.get("source_topic", "").strip(),
        summary=data.get("summary", "").strip(),
        content=data.get("content", ""),
        metadata=data.get("metadata", {}),
    )
    return jsonify({"msg": "saved", "id": artifact_id})


@app.route("/start_mock", methods=["POST"])
def start_mock():
    data = request.get_json(force=True)
    exam = data.get("exam", "").strip()
    subject = data.get("subject", "").strip()
    if not exam or not subject:
        return jsonify([])

    subject_questions = QUESTION_BANK.get(exam, {}).get(subject, [])
    questions = []
    for idx, question in enumerate(subject_questions, start=1):
        questions.append(
            {
                "id": idx,
                "question": question["question"],
                "options": question["options"],
                "answer": question["answer"],
                "topic": question.get("topic", subject),
                "explanation": question.get("explanation", ""),
            }
        )
    return jsonify(questions)


@app.route("/submit_mock", methods=["POST"])
def submit_mock():
    data = request.get_json(force=True)
    questions = data.get("questions", [])
    answers = data.get("answers", [])
    username = data.get("username", "").strip()
    exam = data.get("exam", "").strip()
    subject = data.get("subject", "").strip()

    score = 0
    weak_areas = []
    for idx, question in enumerate(questions):
        selected = answers[idx] if idx < len(answers) else None
        if selected == question.get("answer"):
            score += 1
        else:
            weak_areas.append(
                {
                    "question": question.get("question"),
                    "correct": question.get("answer"),
                    "topic": question.get("topic", subject or "Concept Review"),
                    "explanation": question.get("explanation", ""),
                }
            )

    total = len(questions)
    percent = int((score / total) * 100) if total else 0
    weak_topics = []
    for item in weak_areas:
        if item["topic"] not in weak_topics:
            weak_topics.append(item["topic"])

    if username:
        snapshot = get_user_snapshot(username)
        if snapshot:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE users
                SET score = ?, attempts = ?, best_score = ?, weak_areas = ?, last_exam = ?
                WHERE username = ?
                """,
                (
                    percent,
                    snapshot["attempts"] + 1,
                    max(snapshot["best_score"], percent),
                    json.dumps(weak_topics[:5]),
                    f"{exam or 'Exam'} - {subject or 'Subject'}",
                    username,
                ),
            )
            conn.commit()
            conn.close()

    recommendation = (
        "Excellent momentum. Switch to Summary Lab or Professor Lab and convert this chapter into a faculty-grade answer."
        if percent >= 75
        else "Revise the weak areas, make micro-notes, and attempt one more round within 20 minutes."
    )
    return jsonify({"score": score, "total": total, "percent": percent, "weak": weak_areas, "weak_topics": weak_topics, "recommendation": recommendation})


if __name__ == "__main__":
    app.run(debug=True)
