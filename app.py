from functools import wraps
from flask import Flask, render_template, request, send_file, redirect, url_for, session, g, jsonify
import sqlite3
import re
import pdfplumber
import io
import os
import json
import random
import hashlib
from datetime import UTC, datetime
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
DEFAULT_DEV_SECRET_KEY = "dev-team-practice-secret"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def get_secret_key():
    secret_key = os.environ.get("UIL_CS_SECRET_KEY")
    if secret_key:
        return secret_key
    if os.environ.get("UIL_CS_REQUIRE_SECRET") == "1":
        raise RuntimeError("UIL_CS_SECRET_KEY must be set when UIL_CS_REQUIRE_SECRET=1.")
    return DEFAULT_DEV_SECRET_KEY


app.secret_key = get_secret_key()


def resolve_app_state_path(path, default_name):
    selected = path or os.path.join(BASE_DIR, default_name)
    if os.path.isabs(selected):
        return selected
    return os.path.join(BASE_DIR, selected)


DB_FILE = resolve_app_state_path(os.environ.get("UIL_CS_DB_FILE"), "uil_cs_questions_v2.db")
QUESTION_OVERRIDE_FILE = resolve_app_state_path("question_overrides.json", "question_overrides.json")
PARSE_FEEDBACK_FILE = resolve_app_state_path("parse_feedback.jsonl", "parse_feedback.jsonl")
_QUESTION_OVERRIDES_CACHE = None
_CROP_TEXT_CACHE = {}

TOPIC_SYNONYMS = {
    "primitive": ["primitive", "int", "double", "boolean", "short", "long", "byte", "char", "float", "casting"],
    "primitives": ["primitive", "int", "double", "boolean", "short", "long", "byte", "char", "float", "casting"],
    "arithmetic": ["arithmetic", "+", "-", "*", "/", "%", "string concatenation"],
    "assignment": ["assignment", "=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^="],
    "increment": ["increment", "decrement", "++", "--", "postfix", "prefix"],
    "loop": ["loop", "for", "while", "do-while", "nested loop"],
    "loops": ["loop", "for", "while", "do-while", "nested loop"],
    "branching": ["if", "else", "if/else", "else if", "switch", "break"],
    "recursion": ["recursion", "recursive", "base case", "stack overflow"],
    "dynamic programming": ["dynamic programming", "dp", "memoization", "tabulation"],
    "greedy": ["greedy", "greedy algorithm", "huffman", "activity selection", "fractional knapsack"],
    "graph": ["graph", "graph algorithm", "bfs", "dfs", "dijkstra", "kruskal", "prim", "topological sort", "cycle detection"],
    "graphs": ["graph", "graph algorithm", "bfs", "dfs", "dijkstra", "kruskal", "prim", "topological sort", "cycle detection"],
    "class": ["class", "object", "constructor", "instance", "field", "extends", "implements"],
    "oop": ["class", "object", "constructor", "inheritance", "polymorphism", "encapsulation", "super", "extends"],
    "inheritance": ["inheritance", "extends", "super", "subclass", "parent class", "child class"],
    "polymorphism": ["polymorphism", "override", "overload", "dynamic binding"],
    "encapsulation": ["encapsulation", "private", "public", "protected", "access modifier"],
    "interfaces": ["interface", "interfaces", "implements"],
    "overloading": ["overload", "overloading"],
    "overriding": ["override", "overriding"],
    "final": ["final", "final class", "final method", "final variable"],
    "static": ["static", "class variable", "class method", "static variable", "static method"],
    "superclass": ["superclass", "supertype", "subtype", "subtypes", "super", "extends", "upcasting"],
    "comparison": ["equals", "==", "!=", "<", "<=", ">", ">=", "compareTo", "Comparable"],
    "enum": ["enum", "enumerated type", "enumeration"],
    "enums": ["enum", "enumerated type", "enumeration"],
    "collections": ["collection", "collections", "ArrayList", "LinkedList", "HashMap", "TreeMap", "Set", "Queue", "Stack"],
    "queue": ["queue", "fifo", "first in first out", "deque", "priority queue", "linkedlist"],
    "queues": ["queue", "fifo", "first in first out", "deque", "priority queue", "linkedlist"],
    "stack": ["stack", "lifo", "last in first out", "push", "pop", "peek"],
    "stacks": ["stack", "lifo", "last in first out", "push", "pop", "peek"],
    "linked list": ["linked list", "linkedlist", "node", "next", "prev"],
    "linked lists": ["linked list", "linkedlist", "node", "next", "prev"],
    "hashmap": ["hashmap", "hash map", "map", "key", "value", "put", "get"],
    "hashset": ["hashset", "hash set", "set", "contains", "add", "remove"],
    "arraylist": ["arraylist", "list", "add", "remove", "get", "size"],
    "priority queue": ["priority queue", "heap", "poll", "offer", "peek"],
    "priorityqueue": ["priority queue", "priorityqueue", "heap", "poll", "offer", "peek"],
    "generic collections": ["collection", "collections", "List", "Set", "Map", "Stack", "Queue", "PriorityQueue", "ArrayList", "LinkedList", "HashSet", "TreeSet", "HashMap", "TreeMap"],
    "generics": ["generic", "generics", "<T>", "Comparable<T>", "Collection", "List", "Set", "Map"],
    "array": ["array", "arrays", "[]"],
    "arrays": ["array", "arrays", "[]"],
    "string": ["string", "substring", "charAt", "indexOf", "length"],
    "parsing": ["parse", "parsing", "split", "String.split", "Integer.parseInt", "Double.parseDouble"],
    "file": ["file", "files", "Scanner", "PrintWriter", "BufferedReader", "IOException"],
    "regex": ["regex", "regular expression", "Pattern", "Matcher", "matches", "replaceAll"],
    "regular expressions": ["regex", "regular expression", "Pattern", "Matcher", "matches", "replaceAll"],
    "sorting": ["sort", "sorted", "selection sort", "insertion sort", "merge sort", "quicksort"],
    "sorts": ["sort", "sorted", "selection sort", "insertion sort", "merge sort", "quicksort", "bubble sort", "radix sort"],
    "selection sort": ["selection sort", "minimum", "swap", "unsorted portion"],
    "insertion sort": ["insertion sort", "insert", "shift", "sorted portion"],
    "merge sort": ["merge sort", "divide and conquer", "merge", "halves"],
    "quick sort": ["quick sort", "quicksort", "pivot", "partition"],
    "quicksort": ["quick sort", "quicksort", "pivot", "partition"],
    "binary search": ["binary search", "middle", "sorted array", "half"],
    "linear search": ["linear search", "sequential search", "scan"],
    "sequential search": ["sequential search", "linear search", "scan"],
    "searching": ["search", "binary search", "linear search"],
    "searches": ["search", "binary search", "linear search", "sequential search"],
    "math": ["Math.random", "Math.pow", "Math.sqrt", "Math.abs", "Math.min", "Math.max", "random"],
    "java standard library": ["String", "Integer", "Double", "Character", "Math", "Object", "Comparable", "Scanner", "File", "Random", "Array", "Arrays", "assert"],
    "stdlib": ["String", "Integer", "Double", "Character", "Math", "Object", "Comparable", "Scanner", "File", "Random", "Array", "Arrays", "assert"],
    "exception": ["exception", "IOException", "try", "catch", "throws", "finally"],
    "exceptions": ["exception", "IOException", "try", "catch", "throws", "finally"],
    "boolean": ["boolean", "true", "false", "&&", "||", "!"],
    "logic": ["boolean", "true", "false", "&&", "||", "!"],
    "bitwise": ["bitwise", "&", "|", "^", "~", "<<", ">>", ">>>"],
    "boolean simplification": ["boolean simplification", "boolean identities", "DeMorgan", "A'B", "AB", "logic gate"],
    "base conversion": ["base conversion", "binary", "octal", "hex", "hexadecimal", "decimal", "base 2", "base 8", "base 10", "base 16"],
    "two's complement": ["two's complement", "2's complement", "negative 8-bit integer", "8 bits"],
    "twos complement": ["two's complement", "2's complement", "negative 8-bit integer", "8 bits"],
    "binary tree": ["binary tree", "tree", "root", "leaf", "inorder", "preorder", "postorder"],
    "tree traversal": ["inorder", "preorder", "postorder", "level order", "traversal"],
    "preorder": ["preorder", "tree traversal", "root left right"],
    "inorder": ["inorder", "tree traversal", "left root right"],
    "postorder": ["postorder", "tree traversal", "left right root"],
    "prefix": ["prefix", "prefix notation", "polish notation"],
    "postfix": ["postfix", "postfix notation", "reverse polish notation"],
    "big o": ["big o", "runtime", "time complexity", "space complexity", "worst case", "average case"],
    "time complexity": ["time complexity", "runtime", "big o", "worst case", "average case", "best case"],
    "space complexity": ["space complexity", "memory", "big o", "runtime"],
    "bst traversal": ["binary search tree", "bst", "preorder", "inorder", "postorder"],
    "polish notation": ["prefix notation", "postfix notation", "infix", "prefix", "postfix"],
    "finite state machine": ["finite state machine", "fsm", "state machine"],
    "fsm": ["finite state machine", "fsm", "state machine"],
    "languages": ["formal grammar", "bnf", "language classification", "grammar", "languages"],
    "formal languages": ["formal grammar", "bnf", "language classification", "grammar", "languages"],
    "design patterns": ["design pattern", "singleton", "factory", "strategy"],
    "multithreading": ["multithreading", "thread", "threads", "concurrency", "synchronized"],
    "concurrency": ["multithreading", "thread", "threads", "concurrency", "synchronized"],
    "lambda": ["lambda", "->", "removeIf", "forEach", "Consumer", "Predicate", "Function", "Supplier", "BiFunction", "stream"],
    "functional": ["lambda", "->", "removeIf", "forEach", "Consumer", "Predicate", "Function", "Supplier", "BiFunction", "stream"],
    "functional programming": ["lambda", "->", "removeIf", "forEach", "Consumer", "Predicate", "Function", "Supplier", "BiFunction", "stream"],
    "data structures": ["array", "list", "stack", "queue", "linked list", "tree", "bst", "avl", "red-black tree", "heap", "priority queue", "hash table", "trie", "disjoint set union", "segment tree", "fenwick tree"],
    "trees": ["tree", "bst", "binary search tree", "avl", "red-black tree", "heap", "priority queue", "trie", "segment tree", "fenwick tree"],
    "bst": ["bst", "binary search tree", "tree"],
    "heap": ["heap", "priority queue"],
    "probability": ["probability", "monte carlo", "randomized quicksort", "reservoir sampling", "floyd cycle detection"],
    "runtime": ["runtime", "time complexity", "space complexity", "Big-O", "worst case", "average case", "best case", "statement execution counts"],
    "complexity": ["runtime", "time complexity", "space complexity", "Big-O", "worst case", "average case", "best case"],
    "geometry": ["geometry", "convex hull", "line intersection", "closest pair of points"],
    "digital electronics": ["digital electronics", "logic gate", "NOT", "AND", "XOR", "OR", "NAND", "NOR", "NXOR"],
}

STRICT_TOPIC_MATCHES = {"class", "math", "oop", "inheritance", "polymorphism", "encapsulation"}
CHOICE_ONLY_NOISE_TOPICS = {
    "stack",
    "stacks",
    "queue",
    "queues",
    "linked list",
    "linked lists",
    "linkedlist",
    "priority queue",
    "priorityqueue",
    "deque",
    "vector",
}


def remove_noise_lines(text):
    if not text:
        return ""

    noise_patterns = [
        r"^written test",
        r"^test\s+[Ã¢â‚¬â€œ-]",
        r"^uil computer science\b",
        r"^\(?c\)?\s*a\+",
        r"^Ã‚Â©\s*a\+",
        r"^copyright\b",
        r"^page\s+\d+\b",
        r"^www\.",
        r"^questions$",
        r"^free response$",
        r"^your answers\b",
        r"^double-check\b",
    ]

    cleaned_lines = []
    for raw_line in text.replace("\r", "\n").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = line.lower()
        if any(re.match(pattern, lowered) for pattern in noise_patterns):
            continue
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA journal_mode=MEMORY")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.row_factory = sqlite3.Row
    return conn


def init_app_tables():
    conn = get_connection()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS test_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        exam_key TEXT NOT NULL,
        year INTEGER,
        level TEXT,
        exam_name TEXT,
        total_questions INTEGER NOT NULL,
        answered_count INTEGER NOT NULL,
        correct_count INTEGER NOT NULL,
        score_percent REAL NOT NULL,
        started_at TEXT,
        completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS attempt_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        attempt_id INTEGER NOT NULL,
        question_id INTEGER NOT NULL,
        question_number INTEGER NOT NULL,
        response TEXT,
        correct INTEGER NOT NULL,
        FOREIGN KEY(attempt_id) REFERENCES test_attempts(id),
        FOREIGN KEY(question_id) REFERENCES questions(id)
    );

    CREATE TABLE IF NOT EXISTS question_bookmarks (
        user_id INTEGER NOT NULL,
        question_id INTEGER NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(user_id, question_id),
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(question_id) REFERENCES questions(id)
    );

    CREATE TABLE IF NOT EXISTS question_explanations (
        question_id INTEGER PRIMARY KEY,
        explanation TEXT NOT NULL,
        author_user_id INTEGER,
        updated_by_user_id INTEGER,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(question_id) REFERENCES questions(id),
        FOREIGN KEY(author_user_id) REFERENCES users(id),
        FOREIGN KEY(updated_by_user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS parse_issue_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reported_at TEXT NOT NULL,
        question_id INTEGER,
        exam_name TEXT,
        question_number INTEGER,
        issue_type TEXT,
        detail TEXT,
        reporter_context TEXT,
        return_to TEXT,
        raw_json TEXT NOT NULL,
        report_hash TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(question_id) REFERENCES questions(id)
    );

    CREATE INDEX IF NOT EXISTS idx_test_attempts_user_completed
        ON test_attempts(user_id, completed_at DESC);
    CREATE INDEX IF NOT EXISTS idx_attempt_questions_question
        ON attempt_questions(question_id);
    CREATE INDEX IF NOT EXISTS idx_parse_issue_reports_question
        ON parse_issue_reports(question_id, reported_at DESC);
    """)
    conn.commit()
    conn.close()


init_app_tables()


@app.before_request
def load_current_user():
    user_id = session.get("user_id")
    g.current_user = None
    if not user_id:
        return
    conn = get_connection()
    g.current_user = conn.execute(
        "SELECT id, username FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    conn.close()


@app.context_processor
def inject_current_user():
    return {"current_user": g.get("current_user")}


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not g.get("current_user"):
            return redirect(url_for("login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapped


def validate_username(username):
    return bool(re.fullmatch(r"[A-Za-z0-9_]{3,32}", username or ""))


def load_question_overrides():
    global _QUESTION_OVERRIDES_CACHE
    if _QUESTION_OVERRIDES_CACHE is not None:
        return _QUESTION_OVERRIDES_CACHE

    if not os.path.exists(QUESTION_OVERRIDE_FILE):
        _QUESTION_OVERRIDES_CACHE = {}
        return _QUESTION_OVERRIDES_CACHE

    try:
        with open(QUESTION_OVERRIDE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}

    _QUESTION_OVERRIDES_CACHE = data if isinstance(data, dict) else {}
    return _QUESTION_OVERRIDES_CACHE


def get_question_override(row):
    exam_name = str(row["exam_name"] or "")
    question_number = row["question_number"]
    override_key = f"{exam_name}#{question_number}"
    return load_question_overrides().get(override_key, {})


def save_parse_issue_report(conn, report_entry):
    feedback = report_entry.get("user_feedback") or {}
    raw_json = json.dumps(report_entry, sort_keys=True)
    report_hash = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()
    conn.execute(
        """
        INSERT OR IGNORE INTO parse_issue_reports
        (reported_at, question_id, exam_name, question_number, issue_type,
         detail, reporter_context, return_to, raw_json, report_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(report_entry.get("reported_at") or ""),
            report_entry.get("id"),
            report_entry.get("exam_name"),
            report_entry.get("question_number"),
            str(feedback.get("issue_type") or ""),
            str(feedback.get("detail") or ""),
            str(feedback.get("reporter_context") or ""),
            str(feedback.get("return_to") or ""),
            raw_json,
            report_hash,
        ),
    )


def row_value(row, key, default=""):
    try:
        value = row[key]
    except Exception:
        return default
    return default if value is None else value


def resolve_pdf_path(stored_path):
    if not stored_path:
        return ""
    if os.path.exists(stored_path):
        return stored_path

    project_candidate = os.path.join(BASE_DIR, stored_path)
    if os.path.exists(project_candidate):
        return project_candidate

    candidate = os.path.join("data", stored_path)
    if os.path.exists(candidate):
        return candidate

    project_data_candidate = os.path.join(BASE_DIR, "data", stored_path)
    if os.path.exists(project_data_candidate):
        return project_data_candidate

    return stored_path


def expand_keyword(keyword):
    key = keyword.lower().strip()
    if key in TOPIC_SYNONYMS:
        return TOPIC_SYNONYMS[key]
    return [keyword]


def contains_search_term(text, term):
    haystack = (text or "").lower()
    needle = (term or "").strip().lower()

    if not haystack or not needle:
        return False

    if " " in needle:
        return re.search(re.escape(needle), haystack, re.IGNORECASE) is not None

    if not re.search(r"[a-z0-9]", needle):
        return needle in haystack

    return re.search(rf"\b{re.escape(needle)}\b", haystack, re.IGNORECASE) is not None


def build_search_blob(question_text, code_block, choices, answer, shared_context):
    return " ".join([question_text, code_block, choices, answer, shared_context]).lower()


def confidence_label_for_score(score):
    if score >= 85:
        return "High"
    if score >= 60:
        return "Medium"
    return "Low"


def extract_declared_method_names(code_block):
    method_names = set()
    for name in re.findall(
        r"(?im)^\s*(?:public|private|protected)?\s*(?:static\s+)?[\w<>\[\]]+\s+([A-Za-z_]\w*)\s*\(",
        code_block or "",
    ):
        lowered = name.lower()
        if lowered not in {"if", "for", "while", "switch", "catch"}:
            method_names.add(lowered)
    return method_names


def has_recursive_self_call(code_block):
    code = code_block or ""
    declaration_pattern = re.compile(
        r"(?im)^\s*(?:public|private|protected)?\s*(?:static\s+)?[\w<>\[\]]+\s+([A-Za-z_]\w*)\s*\([^)]*\)\s*\{"
    )

    for match in declaration_pattern.finditer(code):
        method_name = match.group(1)
        lowered = method_name.lower()
        if lowered in {"if", "for", "while", "switch", "catch"}:
            continue

        body_start = match.end()
        depth = 1
        idx = body_start
        while idx < len(code) and depth > 0:
            if code[idx] == "{":
                depth += 1
            elif code[idx] == "}":
                depth -= 1
            idx += 1

        body = code[body_start : idx - 1] if depth == 0 else code[body_start:]
        if re.search(rf"(?<![\w.]){re.escape(method_name)}\s*\(", body):
            return True

    return False


def clean_text_for_display(text):
    if not text:
        return ""

    text = remove_noise_lines(text)
    text = text.replace(chr(8722), "-").replace(chr(8211), "-").replace(chr(8212), "-")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def looks_like_code_line(line):
    normalized = (line or "").strip()
    if not normalized:
        return False

    code_patterns = [
        r"\b(?:if|else|for|while|switch|case|return|do)\b",
        r"\b(?:public|private|protected|class|static|void|int|double|boolean|char|String)\b",
        r"\b(?:out\.print|out\.println|Arrays\.toString)\b",
        r"[{};]",
        r"->",
        r"\b[A-Za-z_]\w*\s*(?:\+\+|--|[+\-*/%]?=)",
        r"\b[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\s*\(",
    ]
    return any(re.search(pattern, normalized) for pattern in code_patterns)


def extract_inline_code_fragments(text):
    if not text:
        return "", ""

    working = text
    extracted_code = []

    code_patterns = [
        r'(for\s*\(.*?\))',
        r'(while\s*\(.*?\))',
        r'(if\s*\(.*?\))',
        r'(out\.print(?:ln)?\s*\(.*?\)\s*;)',
        r'([A-Za-z_]\w*\s*=\s*.*?;)',
        r'((?:int|double|boolean|char|String)\s+[A-Za-z_]\w*\s*=\s*.*?;)',
    ]

    for pattern in code_patterns:
        matches = re.findall(pattern, working)
        for match in matches:
            if match not in extracted_code:
                extracted_code.append(match)
        working = re.sub(pattern, '', working)

    cleaned_text = re.sub(r'\s+', ' ', working).strip()
    code_block = "\n".join(extracted_code).strip()

    return cleaned_text, code_block


def extract_code_from_choices(choices_text):
    if not choices_text:
        return "", ""

    working = choices_text
    extracted_code = []

    code_patterns = [
        r'(out\.print(?:ln)?\s*\(.*?\)\s*;)',
        r'(for\s*\(.*?\))',
        r'(while\s*\(.*?\))',
        r'([A-Za-z_]\w*\s*=\s*.*?;)',
    ]

    for pattern in code_patterns:
        matches = re.findall(pattern, working)
        for match in matches:
            if match not in extracted_code:
                extracted_code.append(match)
        working = re.sub(pattern, '', working)

    return working.strip(), "\n".join(extracted_code).strip()


def normalize_choice_fragment(text):
    return re.sub(r"\s+", " ", (text or "").strip()).strip()


def parse_choice_label_sequence(text):
    return [label.upper() for label in re.findall(r"(?i)\b([A-L])[\.)](?=\s|$)", text or "")]


def parse_extended_choice_label_sequence(text):
    return [label.upper() for label in re.findall(r"(?i)\b([A-L])[\.)](?=\s|$)", text or "")]


def split_choice_prefix_from_code_line(line):
    match = re.match(
        r"^\s*(-?\d+(?:\.\d+)?)\s+(?=(?:for\s*\(|while\s*\(|if\s*\(|do\{?|return\b|out\.|case\b|[A-Za-z_]\w*\s*(?:\+\+|--|[+\-*/%]?=)|[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\s*\())",
        line or "",
        re.IGNORECASE,
    )
    if not match:
        return "", line

    choice_text = normalize_choice_fragment(match.group(1))
    remainder = (line or "")[match.end(1):].strip()
    if not choice_text or not remainder:
        return "", line

    return choice_text, remainder


def explode_inline_choice_labels(text):
    if not text:
        return ""

    return re.sub(
        r'(?<!^)(?<!\n)\s+((?:[A-L]|TRUE|FALSE|T|F)[\.)]\s+)',
        r'\n\1',
        text.strip(),
        flags=re.IGNORECASE,
    )


def trim_to_first_choice_label(text):
    if not text:
        return ""

    normalized = text.replace("\r", "\n")
    match = re.search(r"(?im)^\s*((?:[A-L]|TRUE|FALSE|T|F)[\.)]\s+)", normalized)
    if match:
        return normalized[match.start(1):].strip()
    return normalized.strip()


def extract_question_crop_text(row):
    source_test_pdf = row_value(row, "source_test_pdf", "")
    if not source_test_pdf:
        return ""

    cache_key = (
        source_test_pdf,
        row_value(row, "page_number", 0),
        round(float(row_value(row, "top_y", 0) or 0), 2),
        round(float(row_value(row, "bottom_y", 0) or 0), 2),
        row_value(row, "question_number", 0),
    )
    if cache_key in _CROP_TEXT_CACHE:
        return _CROP_TEXT_CACHE[cache_key]

    pdf_path = resolve_pdf_path(source_test_pdf)
    if not pdf_path or not os.path.exists(pdf_path):
        _CROP_TEXT_CACHE[cache_key] = ""
        return ""

    try:
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[row_value(row, "page_number", 0)]
            top = max(0, (row_value(row, "top_y", 0) or 0) - 22)
            bottom = min(page.height, (row_value(row, "bottom_y", page.height) or page.height) + 24)
            cropped = page.within_bbox((0, top, page.width, bottom))
            text = cropped.extract_text(x_tolerance=1, y_tolerance=3) or ""
    except Exception:
        text = ""

    _CROP_TEXT_CACHE[cache_key] = text
    return text


def extract_choice_block_from_crop_text(crop_text, question_number):
    if not crop_text:
        return ""

    block = crop_text
    question_word = r"Q\s*u\s*e\s*s\s*t\s*i\s*o\s*n"
    start_match = re.search(rf"(?im)^\s*{question_word}\s*{question_number}\.?\s*$", block)
    if start_match:
        block = block[start_match.end():]

    next_question_match = re.search(rf"(?im)^\s*{question_word}\s*\d+\.?\s*$", block)
    if next_question_match:
        block = block[:next_question_match.start()]

    label_match = re.search(r"(?im)^\s*((?:[A-L]|TRUE|FALSE|T|F)[\.)]\s+)", block)
    if not label_match:
        return ""

    return block[label_match.start(1):].strip()


def maybe_recover_choice_text(row, question_text, code_block, choices_text, answer):
    normalized_choices = trim_to_first_choice_label(choices_text).strip()
    parsed = parse_choices(normalized_choices)
    answer_is_letter = bool(re.fullmatch(r"[A-L]", answer or "", re.IGNORECASE))
    parsed_letters = [choice["letter"] for choice in parsed if choice["text"].strip()]
    valid_short_choice_set = parsed_letters in (["A", "B"], ["A", "B", "C"])
    if answer_is_letter and valid_short_choice_set and answer.upper() in parsed_letters:
        return question_text, code_block, normalized_choices

    needs_recovery = (
        answer_is_letter and (
            not parsed
            or len(parsed) < 5
            or any(not choice["text"].strip() for choice in parsed)
        )
    )
    if not needs_recovery:
        return question_text, code_block, normalized_choices

    question_lines = [line for line in (question_text or "").splitlines() if line.strip()]
    trailing_question_choices = []
    while question_lines and re.match(r"(?i)^\s*[A-L][\.)]\s*", question_lines[-1]):
        trailing_question_choices.insert(0, question_lines.pop())
    if trailing_question_choices:
        normalized_choices = "\n".join(trailing_question_choices + ([normalized_choices] if normalized_choices else [])).strip()
        question_text = "\n".join(question_lines).strip()

    parsed = parse_choices(normalized_choices)
    parsed_by_letter = {choice["letter"]: choice["text"].strip() for choice in parsed}
    missing_letters = [
        letter
        for letter in [chr(code) for code in range(ord("A"), ord("L") + 1)]
        if not parsed_by_letter.get(letter)
    ]
    code_lines = []
    recovered_choice_lines = []
    for line in (code_block or "").splitlines():
        recovered_choice, remainder = split_choice_prefix_from_code_line(line)
        if recovered_choice and missing_letters:
            recovered_label = missing_letters.pop(0)
            blank_label_pattern = rf"(?im){re.escape(recovered_label)}[\.)]\s*$"
            if re.search(blank_label_pattern, normalized_choices):
                normalized_choices = re.sub(
                    blank_label_pattern,
                    f"{recovered_label}. {recovered_choice}",
                    normalized_choices,
                )
            else:
                recovered_choice_lines.append(f"{recovered_label}. {recovered_choice}")
            code_lines.append(remainder)
        else:
            code_lines.append(line)

    if recovered_choice_lines:
        normalized_choices = "\n".join([part for part in [normalized_choices, *recovered_choice_lines] if part]).strip()
        code_block = "\n".join(code_lines).strip()

    parsed = parse_choices(normalized_choices)
    if not parsed or len(parsed) < 5 or any(not choice["text"].strip() for choice in parsed):
        crop_choices = extract_choice_block_from_crop_text(extract_question_crop_text(row), row["question_number"])
        if crop_choices:
            crop_normalized = trim_to_first_choice_label(crop_choices)
            crop_parsed = parse_choices(crop_normalized)
            parsed_letters = [choice["letter"] for choice in parsed if choice["text"].strip()]
            crop_letters = [choice["letter"] for choice in crop_parsed if choice["text"].strip()]
            current_has_answer = answer.upper() in parsed_letters if answer else False
            crop_has_answer = answer.upper() in crop_letters if answer else False
            if len(crop_letters) > len(parsed_letters) and (crop_has_answer or not current_has_answer):
                normalized_choices = crop_normalized

    return question_text, code_block, normalized_choices


def infer_visual_choice_labels(answer, choices_text=""):
    extended_labels = parse_extended_choice_label_sequence(choices_text)
    if re.fullmatch(r"[A-L]", answer or "", re.IGNORECASE) and any(label in {"F", "G", "H", "I", "J", "K", "L"} for label in extended_labels):
        last_label = max(extended_labels, key=lambda label: ord(label)) if extended_labels else "L"
        return [chr(code) for code in range(ord("A"), ord(last_label) + 1)]
    if re.fullmatch(r"[A-E]", answer or "", re.IGNORECASE):
        return ["A", "B", "C", "D", "E"]
    if re.fullmatch(r"[TF]", answer or "", re.IGNORECASE):
        return ["T", "F"]
    return []


def should_use_visual_choice_fallback(parsed_choices, answer, choices_text):
    normalized_answer = (answer or "").strip().upper()
    if not re.fullmatch(r"[A-L]", normalized_answer):
        return False

    parsed_labels = [
        choice["letter"]
        for choice in parsed_choices
        if choice.get("text", "").strip()
    ]
    raw_labels = parse_choice_label_sequence(choices_text)
    extended_labels = parse_extended_choice_label_sequence(choices_text)
    if any(label in {"F", "G", "H", "I", "J", "K", "L"} for label in extended_labels):
        last_label = max(extended_labels, key=lambda label: ord(label))
        expected_labels = [chr(code) for code in range(ord("A"), ord(last_label) + 1)]
        return normalized_answer in extended_labels and (
            normalized_answer not in parsed_labels
            or len(set(parsed_labels)) < len(set(extended_labels))
            or sorted(set(extended_labels)) != expected_labels
        )

    has_five_choice_intent = (
        normalized_answer in {"C", "D", "E"}
        or (normalized_answer == "B" and len(set(parsed_labels)) <= 1 and raw_labels == ["A"])
        or len(set(raw_labels)) >= 3
        or any(label in {"C", "D", "E"} for label in raw_labels)
        or any(label in {"C", "D", "E"} for label in parsed_labels)
    )
    if not has_five_choice_intent:
        return False

    return len(set(parsed_labels)) < 5 or normalized_answer not in parsed_labels


def infer_display_issues(question_text, code_block, parsed_choices, answer, is_open_response, is_visual_choice):
    issues = []
    if parsed_choices and any(not choice["text"].strip() for choice in parsed_choices):
        issues.append("A choice still looks blank after recovery.")
    if parsed_choices and len(parsed_choices) < 5 and not is_open_response and not is_visual_choice:
        issues.append("This question still has fewer than five parsed answer choices.")
    if not parsed_choices and not is_open_response and not is_visual_choice and answer:
        issues.append("Choices could not be parsed from text, so the cropped PDF may still be the source of truth here.")
    if code_block.count("{") != code_block.count("}") and code_block:
        issues.append("The parsed code block may still be incomplete.")
    if len(clean_text_for_display(question_text)) < 20:
        issues.append("The parsed prompt is very short and may be truncated.")
    return issues


def extract_search_tags(question_text, code_block, shared_context=""):
    tags = set()
    combined_code = "\n".join(part for part in [code_block, shared_context] if part)
    combined_text = "\n".join(part for part in [question_text, combined_code] if part).lower()

    normalized_code = combined_code.lower()

    if re.search(r"(?i)\brecurs(?:ion|ive|ively)?\b|\bbase\s+case\b|\bstack\s+overflow\b", combined_text):
        tags.update({"recursion", "recursive"})
    elif has_recursive_self_call(combined_code):
        tags.update({"recursion", "recursive"})

    if re.search(r"(?i)\bclass\s+[A-Za-z_]\w*|\bextends\b|\bimplements\b", combined_code):
        tags.update({"class", "oop"})

    if re.search(r"(?i)\bextends\b|\bsuper\b", combined_text):
        tags.add("inheritance")

    if re.search(r"(?i)\bmath\s*\.\s*(?:random|pow|sqrt|abs|min|max)\b", combined_text):
        tags.add("math")

    lambda_markers = ["->", "removeif", "foreach", "consumer", "predicate", "function", "supplier", "bifunction", "stream"]
    if any(marker in combined_text for marker in lambda_markers):
        tags.update({"lambda", "functional"})

    return sorted(tags)


def parse_choices(choices_text):
    if not choices_text:
        return []

    def normalize_ocr_choice_labels(text):
        normalized = text or ""
        replacements = [
            (r"(?im)(^|[\s\n])C[c¢€]\s*[\.)]\s*", r"\1C) "),
            (r"(?im)(^|[\s\n])€\s*[\.)]\s*", r"\1C) "),
            (r"(?im)(^|[\s\n])O[Dd]\s*[\.)]\s*", r"\1D) "),
            (r"(?im)(^|[\s\n])0[Dd]\s*[\.)]\s*", r"\1D) "),
        ]
        for pattern, replacement in replacements:
            normalized = re.sub(pattern, replacement, normalized)
        return normalized

    def normalize_choice_label(label):
        label = (label or "").strip().upper()
        if label == "TRUE":
            return "T"
        if label == "FALSE":
            return "F"
        return label

    def choice_label_pattern(label):
        if label == "T":
            return r"(?:TRUE|T)"
        if label == "F":
            return r"(?:FALSE|F)"
        return re.escape(label)

    def parse_scalar_choice_grid(grid_text):
        lines = [line.strip() for line in grid_text.replace("\r", "\n").splitlines() if line.strip()]
        if not lines:
            return []

        def scalar_tokens(line):
            normalized = (line or "").replace(chr(8722), "-").replace(chr(8211), "-").replace(chr(8212), "-")
            normalized = re.sub(r"(?<!\w)-\s+(?=\d)", "-", normalized)
            return re.findall(r"(?i)LINE\s*#\d+|[+-]?\d+(?:\.\d+)?|[A-Za-z_][\w'.:/+-]*", normalized)

        choice_values = {}
        pending_labels = []
        signed_label = None

        for line in lines:
            label_matches = list(re.finditer(r"(?i)\b([A-L])[\.)](?=\s|$)", line))
            if label_matches:
                for idx, match in enumerate(label_matches):
                    label = match.group(1).upper()
                    start = match.end()
                    end = label_matches[idx + 1].start() if idx + 1 < len(label_matches) else len(line)
                    inline_text = normalize_choice_fragment(line[start:end])
                    if inline_text:
                        choice_values[label] = inline_text
                        if inline_text in {"-", "+"}:
                            signed_label = label
                    else:
                        pending_labels.append(label)
                continue

            if not pending_labels:
                continue

            tokens = scalar_tokens(line)
            if not tokens:
                continue

            if (
                signed_label
                and signed_label in choice_values
                and choice_values[signed_label] in {"-", "+"}
                and len(tokens) == len(pending_labels) + 1
            ):
                choice_values[signed_label] = f"{choice_values[signed_label]}{tokens[0]}"
                tokens = tokens[1:]
                signed_label = None

            if len(tokens) != len(pending_labels):
                return []

            for label, token in zip(pending_labels, tokens):
                choice_values[label] = token
            pending_labels = []

        if pending_labels:
            return []

        parsed_grid = []
        for label in [chr(code) for code in range(ord("A"), ord("L") + 1)]:
            value = normalize_choice_fragment(choice_values.get(label, ""))
            if value:
                parsed_grid.append({"letter": label, "text": value})

        ordered_letters = [item["letter"] for item in parsed_grid]
        if ordered_letters not in [
            ["A", "B", "C", "D", "E"],
            ["A", "B", "C", "D"],
            ["A", "B", "C"],
        ]:
            return []

        return parsed_grid

    def parse_unlabeled_choice_block(unlabeled_text):
        normalized_text = (unlabeled_text or "").replace("\r", "\n").strip()
        if not normalized_text:
            return []

        raw_lines = [normalize_choice_fragment(line) for line in normalized_text.splitlines() if line.strip()]

        if len(raw_lines) == 5:
            if any(looks_like_code_line(line) for line in raw_lines):
                return []
            if any(len(line) > 120 for line in raw_lines):
                return []
            return [
                {"letter": chr(ord("A") + idx), "text": line}
                for idx, line in enumerate(raw_lines)
            ]

        if len(raw_lines) != 1:
            return []

        line = raw_lines[0]
        split_patterns = [
            r"\s*\|\s*",
            r"\s{2,}",
            r"\t+",
            r"\s*,\s*",
        ]
        for pattern in split_patterns:
            parts = [normalize_choice_fragment(part) for part in re.split(pattern, line) if normalize_choice_fragment(part)]
            if len(parts) != 5:
                continue
            if any(looks_like_code_line(part) for part in parts):
                continue
            if any(len(part) > 60 for part in parts):
                continue
            return [
                {"letter": chr(ord("A") + idx), "text": part}
                for idx, part in enumerate(parts)
            ]

        return []

    text = trim_to_first_choice_label(normalize_ocr_choice_labels(choices_text)).replace("\r", "\n").strip()
    text = text.replace(chr(8722), "-").replace(chr(8211), "-").replace(chr(8212), "-")
    text = re.sub(r"(?<!\w)-\s+(?=\d)", "-", text)
    if not text:
        return []

    grid_fallback = parse_scalar_choice_grid(text)
    if grid_fallback:
        return grid_fallback

    start_match = re.match(r"^\s*((?:[A-E]|TRUE|FALSE|T|F))[\.)]\s*", text, re.IGNORECASE)
    if not start_match:
        return parse_unlabeled_choice_block(text)

    first_label = normalize_choice_label(start_match.group(1))
    if first_label in {"T", "F"}:
        label_order = ["T", "F"]
    else:
        label_order = [chr(code) for code in range(ord("A"), ord("L") + 1)]

    try:
        current_index = label_order.index(first_label)
    except ValueError:
        return []

    parsed = []
    current_label = first_label
    content_start = start_match.end()

    while True:
        next_index = current_index + 1
        if next_index >= len(label_order):
            content = clean_text_for_display(text[content_start:])
            parsed.append({"letter": current_label, "text": content})
            break

        next_match = None
        matched_label = None
        for candidate_label in label_order[next_index:]:
            candidate_match = re.search(
                rf"(?:(?<=\n)|(?<=\s)|^){choice_label_pattern(candidate_label)}(?:[)]\s*|[.](?=\s|$))",
                text[content_start:],
                re.IGNORECASE,
            )
            if candidate_match and (next_match is None or candidate_match.start() < next_match.start()):
                next_match = candidate_match
                matched_label = candidate_label

        if not next_match:
            content = clean_text_for_display(text[content_start:])
            parsed.append({"letter": current_label, "text": content})
            break

        next_pos = content_start + next_match.start()
        content = clean_text_for_display(text[content_start:next_pos])
        parsed.append({"letter": current_label, "text": content})

        current_label = matched_label
        current_index = label_order.index(matched_label)
        content_start += next_match.end()

    return parsed


def normalize_answer(answer_text):
    raw = clean_text_for_display(answer_text or "").upper().strip()

    if not raw:
        return ""
    if re.fullmatch(r"(?:TRUE|T)", raw):
        return "T"
    if re.fullmatch(r"(?:FALSE|F)", raw):
        return "F"
    if re.fullmatch(r"[A-L]", raw):
        return raw

    prefixed = re.match(r"^\*?\s*(?:\d+\s*[\.)]\s*)?([A-L]|TRUE|FALSE|T|F)\b", raw, re.IGNORECASE)
    if prefixed:
        rest = raw[prefixed.end():].strip()
        if not rest:
            token = prefixed.group(1).upper()
            if token == "TRUE":
                return "T"
            if token == "FALSE":
                return "F"
            return token

    return raw


def normalize_open_response_value(value):
    text = (value or "").replace(chr(8722), "-").replace(chr(8211), "-").replace(chr(8212), "-")
    text = text.strip().upper()
    text = re.sub(r"[,\s]+", "", text)
    text = re.sub(r"[.;:!?]+$", "", text)
    if re.fullmatch(r"[+-]?\d+(?:\.0+)?", text):
        return str(int(float(text)))
    if re.fullmatch(r"[+-]?\d+\.\d+", text):
        text = text.rstrip("0").rstrip(".")
    return re.sub(r"[^A-Z0-9+\-*/.=!&|^()]", "", text)


def prepare_question(row):
    override = get_question_override(row)
    display_question = override.get("question_text", row["question_text"] or "")
    display_code = override.get("code_block", row["code_block"] or "")
    display_choices = override.get("choices", row["choices"] or "")
    display_answer = override.get("answer", row["answer"] or "")
    is_shared_group = (row["group_type"] or "single") != "single" and bool(row["shared_context"])

    if is_shared_group:
        cleaned_question = clean_text_for_display(display_question)
        extra_code_from_question = ""
    else:
        cleaned_question, extra_code_from_question = extract_inline_code_fragments(display_question)
    cleaned_choices, extra_code_from_choices = extract_code_from_choices(display_choices)
    cleaned_choices = trim_to_first_choice_label(cleaned_choices)

    merged_code_parts = []
    if is_shared_group and row["shared_context"]:
        merged_code_parts.append((row["shared_context"] or "").strip())
    elif display_code.strip():
        merged_code_parts.append(display_code.strip())
    if extra_code_from_question.strip():
        merged_code_parts.append(extra_code_from_question.strip())
    if not is_shared_group and extra_code_from_choices.strip():
        merged_code_parts.append(extra_code_from_choices.strip())

    seen = set()
    merged_code = []
    for part in merged_code_parts:
        for line in part.splitlines():
            line = line.strip()
            if line and line not in seen:
                merged_code.append(line)
                if line not in {"{", "}"}:
                    seen.add(line)

    merged_code_text = clean_text_for_display("\n".join(merged_code))
    cleaned_question, merged_code_text, final_choices_text = maybe_recover_choice_text(
        row,
        clean_text_for_display(cleaned_question),
        merged_code_text,
        cleaned_choices.strip(),
        normalize_answer(display_answer),
    )
    parsed_choices = parse_choices(final_choices_text)
    labels_only_text = re.sub(r"(?i)\b(?:[A-L]|TRUE|FALSE|T|F)[\.)](?=\s|$)", " ", final_choices_text or "")
    label_only_choices = bool(parse_choice_label_sequence(final_choices_text)) and not labels_only_text.strip()
    if label_only_choices:
        parsed_choices = []
    normalized_answer = normalize_answer(display_answer)
    if parsed_choices and normalized_answer and not re.fullmatch(r"[A-LTF]", normalized_answer):
        normalized_answer = ""
    visual_fallback_used = should_use_visual_choice_fallback(
        parsed_choices,
        normalized_answer,
        final_choices_text,
    )
    if visual_fallback_used:
        parsed_choices = []
    is_open_response = (
        not parsed_choices
        and not clean_text_for_display(final_choices_text)
        and bool(normalized_answer)
        and not re.fullmatch(r"[A-LTF]", normalized_answer)
    )
    visual_choice_labels = infer_visual_choice_labels(normalized_answer, final_choices_text) if (label_only_choices or visual_fallback_used or not parsed_choices) and not is_open_response else []
    is_visual_choice = bool(visual_choice_labels)
    display_issues = infer_display_issues(
        cleaned_question,
        merged_code_text,
        parsed_choices,
        normalized_answer,
        is_open_response,
        is_visual_choice,
    )
    if visual_fallback_used:
        display_issues.append("Parsed choices look incomplete, so the cropped PDF image is being used as the answer-choice source.")
    code_line_count = len([line for line in merged_code_text.splitlines() if line.strip()])

    return {
        "id": row["id"],
        "exam_name": row["exam_name"],
        "year": row["year"],
        "level": row["level"],
        "question_number": row["question_number"],
        "question_text": clean_text_for_display(cleaned_question),
        "code_block": merged_code_text,
        "choices": clean_text_for_display(final_choices_text),
        "parsed_choices": parsed_choices,
        "answer": normalized_answer,
        "normalized_open_response_answer": normalize_open_response_value(display_answer),
        "is_open_response": is_open_response,
        "is_visual_choice": is_visual_choice,
        "visual_choice_labels": visual_choice_labels,
        "display_issues": display_issues,
        "code_line_count": code_line_count,
        "group_id": row["group_id"] or "",
        "group_type": row["group_type"] or "single",
        "shared_context": clean_text_for_display(row["shared_context"] or ""),
    }


def row_matches_terms(row, terms):
    question_text = str(row["question_text"] or "")
    code_block = str(row["code_block"] or "")
    choices = str(row["choices"] or "")
    answer = str(row["answer"] or "")
    shared_context = str(row["shared_context"] or "")
    tags = extract_search_tags(question_text, code_block, shared_context)
    searchable_text = build_search_blob(question_text, code_block, choices, answer, shared_context)
    core_text = build_search_blob(question_text, code_block, "", answer, shared_context)

    keyword = (terms[0] if terms else "").strip().lower()
    if not keyword:
        return False
    if keyword.isdigit() and str(row_value(row, "year", "")).strip() == keyword:
        return True

    core_hit = contains_search_term(core_text, keyword)
    choices_hit = contains_search_term(choices, keyword)
    allow_choice_only_match = keyword not in CHOICE_ONLY_NOISE_TOPICS
    direct_hit = core_hit or (allow_choice_only_match and choices_hit)
    tag_hit = keyword in tags
    synonym_hits = {
        term.lower()
        for term in terms
        if term.strip() and contains_search_term(core_text if not allow_choice_only_match else searchable_text, term)
    }

    if direct_hit or tag_hit:
        return True

    if keyword in TOPIC_SYNONYMS:
        if keyword in STRICT_TOPIC_MATCHES:
            return len(synonym_hits) >= 2
        return len(synonym_hits) >= 1

    return False


def score_search_match(row, keyword):
    keyword = (keyword or "").strip().lower()
    if not keyword:
        return None

    if keyword.isdigit() and str(row_value(row, "year", "")).strip() == keyword:
        return {
            "score": 86,
            "confidence": confidence_label_for_score(86),
            "matched_terms": [keyword],
            "reasons": [f"year {keyword} match"],
        }

    expanded_terms = [keyword, *expand_keyword(keyword)]
    question_text = str(row["question_text"] or "")
    code_block = str(row["code_block"] or "")
    choices = str(row["choices"] or "")
    answer = str(row["answer"] or "")
    shared_context = str(row["shared_context"] or "")
    tags = extract_search_tags(question_text, code_block, shared_context)
    searchable_text = build_search_blob(question_text, code_block, choices, answer, shared_context)
    core_text = build_search_blob(question_text, code_block, "", answer, shared_context)
    allow_choice_only_match = keyword not in CHOICE_ONLY_NOISE_TOPICS

    core_hit = contains_search_term(core_text, keyword)
    choices_hit = contains_search_term(choices, keyword)
    direct_hit = core_hit or (allow_choice_only_match and choices_hit)
    tag_hit = keyword in tags
    synonym_hits = []
    for term in expanded_terms[1:]:
        normalized = term.lower()
        if normalized == keyword:
            continue
        haystack = searchable_text if allow_choice_only_match else core_text
        if normalized not in synonym_hits and contains_search_term(haystack, term):
            synonym_hits.append(normalized)

    if not direct_hit and not tag_hit:
        if keyword in TOPIC_SYNONYMS:
            minimum_hits = 2 if keyword in STRICT_TOPIC_MATCHES else 1
            if len(synonym_hits) < minimum_hits:
                return None
        else:
            return None

    score = 0
    reasons = []

    if core_hit:
        score += 58
        reasons.append(f'exact "{keyword}" match')
    elif choices_hit and allow_choice_only_match:
        score += 16
        reasons.append(f'"{keyword}" found in choices')

    if tag_hit:
        score += 60 if keyword in {"recursion", "recursive"} else 34
        reasons.append(f'{keyword} tag')

    if synonym_hits:
        bonus = min(24, len(synonym_hits) * 12)
        score += bonus
        shown = ", ".join(synonym_hits[:3])
        if len(synonym_hits) > 3:
            shown += ", ..."
        reasons.append(f"related terms: {shown}")

    score = min(100, score)
    return {
        "score": score,
        "confidence": confidence_label_for_score(score),
        "matched_terms": [keyword, *synonym_hits],
        "reasons": reasons,
    }


def find_question_page(pdf, question_number, question_text=""):
    if question_number is None:
        return 0

    qnum = int(question_number)
    question_word = r"q\s*u\s*e\s*s\s*t\s*i\s*o\s*n"
    question_pattern = re.compile(rf"(?im)\b{question_word}\s*{qnum}\b")
    compact_pattern = re.compile(rf"(?im)\b{question_word}\s*{qnum}(?:\D|$)")
    prompt_snippet = ""
    if question_text:
        words = re.findall(r"[A-Za-z0-9_]+", question_text)
        if words:
            prompt_snippet = " ".join(words[:5]).lower()

    for idx, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        if not text:
            continue
        if question_pattern.search(text) or compact_pattern.search(text):
            return idx

    for idx, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        if not text:
            continue
        lowered = text.lower()
        if prompt_snippet and prompt_snippet in lowered:
            return idx

    return 0


def extract_page_lines(page, tolerance=3):
    words = page.extract_words(use_text_flow=True, keep_blank_chars=False)
    if not words:
        return []

    rows = []
    for word in words:
        text = (word.get("text") or "").strip()
        if not text:
            continue
        placed = False
        for row in rows:
            if abs(word["top"] - row["top"]) <= tolerance:
                row["words"].append(word)
                row["top"] = min(row["top"], word["top"])
                row["bottom"] = max(row["bottom"], word["bottom"])
                placed = True
                break
        if not placed:
            rows.append({
                "top": word["top"],
                "bottom": word["bottom"],
                "words": [word],
            })

    lines = []
    for row in rows:
        ordered = sorted(row["words"], key=lambda item: item["x0"])
        text = " ".join(item["text"] for item in ordered).strip()
        if text:
            lines.append({
                "text": text,
                "top": row["top"],
                "bottom": row["bottom"],
            })

    return sorted(lines, key=lambda item: item["top"])


def find_question_bounds_on_page(page, question_number, end_question_number=None):
    if question_number is None:
        return None

    question_word = r"q\s*u\s*e\s*s\s*t\s*i\s*o\s*n"
    start_pattern = re.compile(rf"(?i)\b{question_word}\s*{int(question_number)}\b")
    end_pattern = None
    if end_question_number is not None:
        end_pattern = re.compile(rf"(?i)\b{question_word}\s*{int(end_question_number)}\b")

    start_top = None
    end_top = None

    lines = extract_page_lines(page)

    for line in lines:
        if start_top is None and start_pattern.search(line["text"]):
            start_top = line["top"]
            continue
        if start_top is not None and end_pattern and end_pattern.search(line["text"]):
            end_top = line["top"]
            break

    if start_top is None:
        return None

    padding_top = 6
    padding_bottom = 10
    safe_top = max(0, start_top - padding_top)
    if end_top is not None:
        safe_bottom = min(page.height, end_top - 2)
    else:
        meaningful_bottom = max(
            (
                line["bottom"]
                for line in lines
                if not remove_noise_lines(line["text"])
                    .lower()
                    .startswith(("uil computer science", "written test", "test -", "test Ã¢â‚¬â€œ"))
            ),
            default=page.height - padding_bottom,
        )
        safe_bottom = min(page.height, meaningful_bottom + padding_bottom)

    if safe_bottom <= safe_top:
        return None

    return safe_top, safe_bottom


def infer_visual_end_question_number(conn, row):
    current_qnum = int(row["question_number"] or 0)
    if not current_qnum:
        return None

    if row["group_type"] and row["group_type"] != "single":
        last = conn.execute(
            """
            SELECT MAX(question_number) AS max_q
            FROM questions
            WHERE group_id = ?
            """,
            (row["group_id"],),
        ).fetchone()
        if last and last["max_q"]:
            return int(last["max_q"]) + 1

    question_text = (row["question_text"] or "").lower()
    line_match = re.search(r"\bline\s+(\d+)\b", question_text)
    if not line_match:
        return current_qnum + 1

    current_line = int(line_match.group(1))
    max_qnum = current_qnum

    next_rows = conn.execute(
        """
        SELECT question_number, question_text
        FROM questions
        WHERE exam_name = ? AND question_number > ?
        ORDER BY question_number
        LIMIT 4
        """,
        (row["exam_name"], current_qnum),
    ).fetchall()

    expected_line = current_line + 1
    for next_row in next_rows:
        next_text = (next_row["question_text"] or "").lower()
        next_match = re.search(r"\bline\s+(\d+)\b", next_text)
        if next_match and int(next_match.group(1)) == expected_line:
            max_qnum = int(next_row["question_number"])
            expected_line += 1
        else:
            break

    return max_qnum + 1


def trim_rendered_blank_tail(image, min_gap_px=90, padding_px=18, min_height_px=180):
    """Remove large blank tails before footer lines in last-on-page crops."""
    rendered = image.convert("RGB")
    width, height = rendered.size
    if height <= min_height_px:
        return rendered

    pixels = rendered.load()
    active_rows = []
    row_threshold = max(8, int(width * 0.002))
    for y in range(height):
        dark_count = 0
        for x in range(width):
            r, g, b = pixels[x, y]
            if r < 242 or g < 242 or b < 242:
                dark_count += 1
                if dark_count >= row_threshold:
                    active_rows.append(y)
                    break

    if not active_rows:
        return rendered

    gaps = []
    previous = active_rows[0]
    for current in active_rows[1:]:
        if current - previous > min_gap_px:
            gaps.append((previous, current))
        previous = current

    if not gaps:
        return rendered

    first_content_row = active_rows[0]
    for gap_start, gap_end in gaps:
        crop_bottom = min(height, gap_start + padding_px)
        if crop_bottom - first_content_row >= min_height_px and gap_end > height * 0.45:
            return rendered.crop((0, 0, width, crop_bottom))

    return rendered


def render_pdf_crop(
    pdf_path,
    page_num,
    top,
    bottom,
    resolution=350,
    question_number=None,
    question_text="",
    end_question_number=None,
):
    with pdfplumber.open(pdf_path) as pdf:
        top = float(top or 0)
        bottom = float(bottom or 0)
        resolved_page_num = page_num if 0 <= int(page_num or 0) < len(pdf.pages) else 0
        invalid_crop = bottom <= top or bottom <= 0

        if invalid_crop:
            resolved_page_num = find_question_page(pdf, question_number, question_text)

        page = pdf.pages[resolved_page_num]
        safe_top = max(0, top - 2)
        safe_bottom = min(page.height, bottom + 2)
        should_trim_blank_tail = not invalid_crop and bottom >= page.height - 1

        if safe_bottom >= page.height - 1:
            meaningful_bottom = max(
                (
                    line["bottom"]
                    for line in extract_page_lines(page)
                    if not remove_noise_lines(line["text"])
                        .lower()
                        .startswith(("uil computer science", "written test", "test -", "test Ã¢â‚¬â€œ"))
                ),
                default=safe_bottom,
            )
            safe_bottom = min(safe_bottom, meaningful_bottom + 10)

        crop_height = safe_bottom - safe_top

        # Older archive-ingested rows may not have crop coordinates yet.
        # In that case, estimate a vertical crop from the question header
        # down to the next question header on the matched page.
        if invalid_crop or safe_bottom <= safe_top:
            estimated_bounds = find_question_bounds_on_page(page, question_number, end_question_number)
            if estimated_bounds:
                est_top, est_bottom = estimated_bounds
                render_target = page.within_bbox((
                    0,
                    est_top,
                    page.width,
                    est_bottom
                ))
            else:
                render_target = page
        else:
            render_target = page.within_bbox((
                0,
                safe_top,
                page.width,
                safe_bottom
            ))

        img = render_target.to_image(resolution=resolution)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        min_visual_height = 80
        if not invalid_crop and crop_height < min_visual_height:
            from PIL import Image

            rendered = Image.open(img_bytes).convert("RGB")
            padding_px = int((min_visual_height - crop_height) * resolution / 72)
            if padding_px > 0:
                padded = Image.new("RGB", (rendered.width, rendered.height + padding_px), "white")
                padded.paste(rendered, (0, 0))
                img_bytes = io.BytesIO()
                padded.save(img_bytes, format="PNG")
                img_bytes.seek(0)

        if should_trim_blank_tail:
            from PIL import Image

            rendered = Image.open(img_bytes).convert("RGB")
            trimmed = trim_rendered_blank_tail(rendered)
            if trimmed.size != rendered.size:
                img_bytes = io.BytesIO()
                trimmed.save(img_bytes, format="PNG")
                img_bytes.seek(0)

        img_bytes.seek(0)
        return img_bytes


def render_pdf_page(pdf_path, page_num, resolution=250):
    with pdfplumber.open(pdf_path) as pdf:
        resolved_page_num = page_num if 0 <= int(page_num or 0) < len(pdf.pages) else 0
        img = pdf.pages[resolved_page_num].to_image(resolution=resolution)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        return img_bytes


def is_explanation_or_key_row(row):
    question_text = row["question_text"] or ""
    choices = row["choices"] or ""
    answer = (row["answer"] or "").strip()
    qnum = int(row["question_number"] or 0)
    if choices.strip() or not answer or not qnum:
        return False
    if not re.fullmatch(r"[A-E]", answer, re.IGNORECASE):
        return False
    if not re.match(rf"(?is)^\s*{qnum}\.\s*{re.escape(answer)}\b", question_text):
        return False
    return len(question_text.strip()) > 40


def needs_neighbor_context(row):
    combined = "\n".join([
        row["question_text"] or "",
        row["code_block"] or "",
        row["choices"] or "",
    ])
    return bool(re.search(r"(?i)\bline\s*#\d+\b|\bcomment\s*#\d+\b|<\*\d+>|client code", combined))


def infer_neighbor_context_bounds(conn, row):
    if not needs_neighbor_context(row):
        return None

    current_qnum = int(row["question_number"] or 0)
    if not current_qnum:
        return None

    rows = conn.execute(
        """
        SELECT question_number, page_number, top_y, bottom_y
        FROM questions
        WHERE exam_name = ?
          AND source_test_pdf = ?
          AND page_number = ?
          AND question_number BETWEEN ? AND ?
        ORDER BY question_number
        """,
        (
            row["exam_name"],
            row["source_test_pdf"],
            row["page_number"],
            current_qnum - 1,
            current_qnum + 1,
        ),
    ).fetchall()

    valid_rows = [
        candidate for candidate in rows
        if float(candidate["bottom_y"] or 0) > float(candidate["top_y"] or 0)
    ]
    if len(valid_rows) < 2:
        return None

    return (
        min(float(candidate["top_y"] or 0) for candidate in valid_rows),
        max(float(candidate["bottom_y"] or 0) for candidate in valid_rows),
        int(valid_rows[0]["question_number"] or current_qnum),
    )


def fetch_exam_catalog():
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT *
        FROM questions
        WHERE year IS NOT NULL
          AND level IS NOT NULL
          AND exam_name IS NOT NULL
        ORDER BY year DESC, level ASC, exam_name ASC
        """
    ).fetchall()
    conn.close()

    grouped = {}
    for row in rows:
        if is_explanation_or_key_row(row):
            continue
        key = (int(row["year"]), str(row["level"] or ""), str(row["exam_name"] or ""))
        item = grouped.setdefault(
            key,
            {
                "year": key[0],
                "level": key[1],
                "exam_name": key[2],
                "question_numbers": set(),
                "source_test_pdf": str(row["source_test_pdf"] or ""),
            },
        )
        item["question_numbers"].add(int(row["question_number"] or 0))

    catalog = [
        {
            "year": item["year"],
            "level": item["level"],
            "exam_name": item["exam_name"],
            "question_count": len(item["question_numbers"]),
            "collection": classify_exam_collection(
                item["exam_name"],
                item["source_test_pdf"],
            ),
        }
        for item in grouped.values()
    ]
    return sorted(catalog, key=lambda item: (-item["year"], item["level"], item["exam_name"]))


def classify_exam_collection(exam_name, source_test_pdf=""):
    combined = f"{exam_name} {source_test_pdf}".lower()
    other_markers = (
        "stacey",
        "caney creek",
        "caney_creek",
        "carthage",
        "college station",
        "college_station",
        "sulphur springs",
        "sulphur_springs",
        "whitehouse",
        "virtual",
    )
    if any(marker in combined for marker in other_markers):
        return "Other"

    normalized = str(exam_name or "").lower()
    if re.fullmatch(r"\d{4}_(invitational[a-z]?|district|regional|state)", normalized):
        return "UIL"
    if re.fullmatch(r"\d{4}_compsciw_study_packet_[abcdsr]_\d{2}_pdf", normalized):
        return "UIL"

    return "Other"


def fetch_test_questions(year, level, exam_name):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT *
        FROM questions
        WHERE year = ?
          AND lower(level) = lower(?)
          AND exam_name = ?
        ORDER BY question_number ASC, id DESC
        """,
        (year, level, exam_name),
    ).fetchall()
    conn.close()

    latest_by_number = {}
    for row in rows:
        qnum = int(row["question_number"] or 0)
        if qnum and qnum not in latest_by_number:
            latest_by_number[qnum] = row

    ordered_rows = [
        latest_by_number[qnum]
        for qnum in sorted(latest_by_number.keys())
        if not is_explanation_or_key_row(latest_by_number[qnum])
    ]
    prepared = [prepare_question(row) for row in ordered_rows]

    group_anchor_seen = set()
    test_questions = []
    for q in prepared:
        is_shared_group = q["group_type"] != "single" and bool(q["group_id"])
        group_id = q["group_id"] if is_shared_group else ""
        is_group_anchor = False
        if is_shared_group and group_id not in group_anchor_seen:
            is_group_anchor = True
            group_anchor_seen.add(group_id)

        if q["parsed_choices"]:
            choice_letters = [choice["letter"] for choice in q["parsed_choices"]]
        elif q["visual_choice_labels"]:
            choice_letters = list(q["visual_choice_labels"])
        else:
            labels = parse_choice_label_sequence(q["choices"])
            choice_letters = labels if labels else (["A", "B", "C", "D", "E"] if re.fullmatch(r"[A-E]", q["answer"] or "", re.IGNORECASE) else [])

        test_questions.append(
            {
                "id": q["id"],
                "question_number": q["question_number"],
                "question_text": q["question_text"],
                "code_block": q["code_block"],
                "answer": (q["answer"] or "").strip().upper(),
                "normalized_open_response_answer": q["normalized_open_response_answer"],
                "is_open_response": bool(q["is_open_response"]),
                "is_shared_group": is_shared_group,
                "group_id": group_id,
                "is_group_anchor": is_group_anchor,
                "shared_context": q["shared_context"] if is_shared_group else "",
                "choice_letters": choice_letters,
                "display_issues": q["display_issues"],
            }
        )

    return test_questions


def fetch_bookmark_ids(question_ids):
    if not g.get("current_user") or not question_ids:
        return set()
    conn = get_connection()
    placeholders = ",".join("?" for _ in question_ids)
    rows = conn.execute(
        f"""
        SELECT question_id
        FROM question_bookmarks
        WHERE user_id = ? AND question_id IN ({placeholders})
        """,
        [g.current_user["id"], *question_ids],
    ).fetchall()
    conn.close()
    return {int(row["question_id"]) for row in rows}


def fetch_explanations(question_ids):
    if not question_ids:
        return {}
    conn = get_connection()
    placeholders = ",".join("?" for _ in question_ids)
    rows = conn.execute(
        f"""
        SELECT qe.question_id, qe.explanation, qe.created_at, qe.updated_at,
               author.username AS author_username,
               updater.username AS updated_by_username
        FROM question_explanations qe
        LEFT JOIN users author ON author.id = qe.author_user_id
        LEFT JOIN users updater ON updater.id = qe.updated_by_user_id
        WHERE qe.question_id IN ({placeholders})
        """,
        question_ids,
    ).fetchall()
    conn.close()
    return {int(row["question_id"]): dict(row) for row in rows}


def attach_question_state(questions):
    question_ids = [question["id"] for question in questions]
    bookmark_ids = fetch_bookmark_ids(question_ids)
    explanations = fetch_explanations(question_ids)
    for question in questions:
        question["is_bookmarked"] = question["id"] in bookmark_ids
        question["explanation"] = explanations.get(question["id"])
    return questions


@app.route("/register", methods=["GET", "POST"])
def register():
    error = ""
    next_url = request.args.get("next") or url_for("index")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        next_url = request.form.get("next") or next_url

        if not validate_username(username):
            error = "Use 3-32 letters, numbers, or underscores."
        elif len(password) < 8:
            error = "Use at least 8 characters for the password."
        else:
            conn = get_connection()
            try:
                cursor = conn.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, generate_password_hash(password)),
                )
                conn.commit()
                session["user_id"] = cursor.lastrowid
                return redirect(next_url)
            except sqlite3.IntegrityError:
                error = "That username is already taken."
            finally:
                conn.close()

    return render_template("auth.html", mode="register", error=error, next_url=next_url)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    next_url = request.args.get("next") or url_for("index")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        next_url = request.form.get("next") or next_url

        conn = get_connection()
        user = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            return redirect(next_url)
        error = "Username or password did not match."

    return render_template("auth.html", mode="login", error=error, next_url=next_url)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    user_id = g.current_user["id"]
    conn = get_connection()
    summary = conn.execute(
        """
        SELECT
            COUNT(*) AS attempt_count,
            COALESCE(SUM(total_questions), 0) AS total_questions,
            COALESCE(SUM(correct_count), 0) AS correct_count,
            COALESCE(AVG(score_percent), 0) AS average_score
        FROM test_attempts
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()
    recent_attempts = conn.execute(
        """
        SELECT id, year, level, exam_name, total_questions, answered_count,
               correct_count, score_percent, completed_at
        FROM test_attempts
        WHERE user_id = ?
        ORDER BY completed_at DESC, id DESC
        LIMIT 12
        """,
        (user_id,),
    ).fetchall()
    missed_rows = conn.execute(
        """
        SELECT q.question_text, q.code_block, q.shared_context
        FROM attempt_questions aq
        JOIN test_attempts ta ON ta.id = aq.attempt_id
        JOIN questions q ON q.id = aq.question_id
        WHERE ta.user_id = ? AND aq.correct = 0
        ORDER BY ta.completed_at DESC
        LIMIT 200
        """,
        (user_id,),
    ).fetchall()
    bookmarks = conn.execute(
        """
        SELECT q.id, q.exam_name, q.year, q.level, q.question_number,
               q.question_text, q.group_id, q.group_type
        FROM question_bookmarks qb
        JOIN questions q ON q.id = qb.question_id
        WHERE qb.user_id = ?
        ORDER BY qb.created_at DESC
        LIMIT 20
        """,
        (user_id,),
    ).fetchall()
    conn.close()

    tag_counts = {}
    for row in missed_rows:
        tags = extract_search_tags(
            row["question_text"] or "",
            row["code_block"] or "",
            row["shared_context"] or "",
        )
        for tag in tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    weak_tags = sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))[:8]

    return render_template(
        "dashboard.html",
        summary=summary,
        recent_attempts=recent_attempts,
        weak_tags=weak_tags,
        bookmarks=bookmarks,
    )


@app.route("/")
def index():
    keyword = request.args.get("keyword", "").strip()
    year = request.args.get("year", "").strip()
    level = request.args.get("level", "").strip()
    exam_name = request.args.get("exam_name", "").strip()
    exam_catalog = fetch_exam_catalog()

    results = []

    if keyword:
        conn = get_connection()
        query = "SELECT * FROM questions WHERE 1=1"
        params = []

        if year.isdigit():
            query += " AND year = ?"
            params.append(int(year))

        if level:
            query += " AND lower(level) LIKE ?"
            params.append(f"%{level.lower()}%")

        if exam_name:
            query += " AND lower(exam_name) LIKE ?"
            params.append(f"%{exam_name.lower()}%")

        query += " ORDER BY year, exam_name, question_number"

        rows = conn.execute(query, params).fetchall()
        conn.close()

        filtered = []
        for row in rows:
            if is_explanation_or_key_row(row):
                continue
            match = score_search_match(row, keyword)
            if match:
                filtered.append((row, match))

        filtered.sort(
            key=lambda item: (
                -item[1]["score"],
                -(item[0]["year"] or 0),
                str(item[0]["exam_name"] or ""),
                item[0]["question_number"] or 0,
            )
        )
        # Keep relevance-focused results while shuffling inside narrow score bands
        # so repeated searches do not always show the exact same top few entries.
        bucketed = {}
        for item in filtered:
            band = int(item[1]["score"] // 5)
            bucketed.setdefault(band, []).append(item)

        diversified = []
        for band in sorted(bucketed.keys(), reverse=True):
            band_rows = bucketed[band]
            random.shuffle(band_rows)
            diversified.extend(band_rows)
        filtered = diversified

        seen_groups = set()
        for row, match in filtered:
            group_key = row["group_id"] or f"question-{row['id']}"
            if group_key in seen_groups:
                continue
            seen_groups.add(group_key)

            q = prepare_question(row)
            preview = q["question_text"].replace("\n", " ")
            if len(preview) > 120:
                preview = preview[:117] + "..."
            q["preview"] = preview
            q["tags"] = extract_search_tags(
                row["question_text"] or "",
                row["code_block"] or "",
                row["shared_context"] or "",
            )
            q["confidence_score"] = match["score"]
            q["confidence_label"] = match["confidence"]
            q["match_summary"] = "; ".join(match["reasons"])
            results.append(q)

    return render_template(
        "index.html",
        results=results,
        keyword=keyword,
        year=year,
        level=level,
        exam_name=exam_name,
        exam_catalog=exam_catalog,
    )


@app.route("/test")
def test_mode():
    year_text = request.args.get("year", "").strip()
    level = request.args.get("level", "").strip()
    exam_name = request.args.get("exam_name", "").strip()

    if not (year_text.isdigit() and level and exam_name):
        return redirect(url_for("index"))

    year = int(year_text)
    questions = fetch_test_questions(year, level, exam_name)
    if not questions:
        return redirect(url_for("index"))

    exam_key = f"{year}|{level.lower()}|{exam_name}"
    return render_template(
        "test_mode.html",
        year=year,
        level=level,
        exam_name=exam_name,
        exam_key=exam_key,
        total_questions=len(questions),
        questions=questions,
    )


@app.route("/api/test_attempts", methods=["POST"])
@login_required
def save_test_attempt():
    payload = request.get_json(silent=True) or {}
    questions = payload.get("questions") if isinstance(payload.get("questions"), list) else []
    total_questions = int(payload.get("total_questions") or len(questions) or 0)

    normalized_rows = []
    correct_count = 0
    answered_count = 0
    for item in questions:
        if not isinstance(item, dict):
            continue
        try:
            question_id = int(item.get("question_id"))
            question_number = int(item.get("question_number"))
        except (TypeError, ValueError):
            continue
        response = str(item.get("response") or "")[:500]
        correct = 1 if item.get("correct") else 0
        answered_count += 1
        correct_count += correct
        normalized_rows.append((question_id, question_number, response, correct))

    if total_questions <= 0 or not normalized_rows:
        return jsonify({"ok": False, "error": "No answered questions to save."}), 400

    score_percent = round((correct_count / total_questions) * 100, 2)
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO test_attempts
        (user_id, exam_key, year, level, exam_name, total_questions,
         answered_count, correct_count, score_percent, started_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            g.current_user["id"],
            str(payload.get("exam_key") or ""),
            int(payload.get("year") or 0) or None,
            str(payload.get("level") or ""),
            str(payload.get("exam_name") or ""),
            total_questions,
            answered_count,
            correct_count,
            score_percent,
            str(payload.get("started_at") or ""),
        ),
    )
    attempt_id = cursor.lastrowid
    conn.executemany(
        """
        INSERT INTO attempt_questions
        (attempt_id, question_id, question_number, response, correct)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (attempt_id, question_id, question_number, response, correct)
            for question_id, question_number, response, correct in normalized_rows
        ],
    )
    conn.commit()
    conn.close()

    return jsonify({
        "ok": True,
        "attempt_id": attempt_id,
        "correct_count": correct_count,
        "answered_count": answered_count,
        "score_percent": score_percent,
    })


@app.route("/bookmark/<int:question_id>", methods=["POST"])
@login_required
def toggle_bookmark(question_id):
    action = request.form.get("action", "toggle")
    return_to = request.form.get("return_to", "").strip()
    conn = get_connection()
    existing = conn.execute(
        "SELECT 1 FROM question_bookmarks WHERE user_id = ? AND question_id = ?",
        (g.current_user["id"], question_id),
    ).fetchone()

    if action == "remove" or existing:
        conn.execute(
            "DELETE FROM question_bookmarks WHERE user_id = ? AND question_id = ?",
            (g.current_user["id"], question_id),
        )
    else:
        conn.execute(
            "INSERT OR IGNORE INTO question_bookmarks (user_id, question_id) VALUES (?, ?)",
            (g.current_user["id"], question_id),
        )
    conn.commit()
    conn.close()

    if return_to:
        return redirect(return_to)
    return redirect(url_for("question_detail", question_id=question_id))


@app.route("/question_image/<int:question_id>")
def question_image(question_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()

    if not row:
        conn.close()
        return "Not found", 404
    if is_explanation_or_key_row(row):
        conn.close()
        return "Question not available", 404

    end_question_number = infer_visual_end_question_number(conn, row)
    context_bounds = infer_neighbor_context_bounds(conn, row)
    conn.close()

    pdf_path = resolve_pdf_path(row["source_test_pdf"])
    if not os.path.exists(pdf_path):
        return "Source PDF not found", 404

    top = row["top_y"]
    bottom = row["bottom_y"]
    question_number = row["question_number"]
    if context_bounds:
        top, bottom, question_number = context_bounds

    img_bytes = render_pdf_crop(
        pdf_path,
        row["page_number"],
        top,
        bottom,
        question_number=question_number,
        question_text=row["question_text"] or "",
        end_question_number=end_question_number,
    )
    return send_file(img_bytes, mimetype="image/png")


@app.route("/question_page_image/<int:question_id>")
def question_page_image(question_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
    conn.close()

    if not row:
        return "Not found", 404

    pdf_path = resolve_pdf_path(row["source_test_pdf"])
    if not os.path.exists(pdf_path):
        return "Source PDF not found", 404

    img_bytes = render_pdf_page(pdf_path, row["page_number"])
    return send_file(img_bytes, mimetype="image/png")


@app.route("/group_image/<group_id>")
def group_image(group_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM questions
        WHERE group_id = ?
        ORDER BY question_number
    """, (group_id,)).fetchall()
    rows = [row for row in rows if not is_explanation_or_key_row(row)]
    if not rows:
        conn.close()
        return "Group not found", 404

    first = rows[0]
    top = min(row["top_y"] for row in rows)
    bottom = max(row["bottom_y"] for row in rows)
    if first["group_type"] and first["group_type"] != "single":
        bottom = 999999
    pdf_path = resolve_pdf_path(first["source_test_pdf"])
    end_question_number = infer_visual_end_question_number(conn, rows[-1]) if rows else None
    conn.close()
    if not os.path.exists(pdf_path):
        return "Source PDF not found", 404

    img_bytes = render_pdf_crop(
        pdf_path,
        first["page_number"],
        top,
        bottom,
        question_number=first["question_number"],
        question_text=first["question_text"] or "",
        end_question_number=end_question_number,
    )
    return send_file(img_bytes, mimetype="image/png")


@app.route("/question/<int:question_id>")
def question_detail(question_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
    conn.close()

    if row is None:
        return "Question not found", 404
    if is_explanation_or_key_row(row):
        return "Question not available", 404

    if row["group_type"] and row["group_type"] != "single" and row["group_id"]:
        return_to = request.args.get("return_to", "").strip()
        if return_to:
            return redirect(url_for("group_detail", group_id=row["group_id"], return_to=return_to))
        return redirect(url_for("group_detail", group_id=row["group_id"]))

    question = attach_question_state([prepare_question(row)])[0]
    return render_template("question.html", question=question)


@app.route("/group/<group_id>")
def group_detail(group_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM questions
        WHERE group_id = ?
        ORDER BY question_number
    """, (group_id,)).fetchall()
    conn.close()
    rows = [row for row in rows if not is_explanation_or_key_row(row)]

    if not rows:
        return "Group not found", 404

    prepared_questions = []
    for row in rows:
        prepared_questions.append(prepare_question(row))
    attach_question_state(prepared_questions)

    return render_template(
        "group.html",
        group_id=group_id,
        group_type=rows[0]["group_type"] or "shared_code",
        shared_context=clean_text_for_display(rows[0]["shared_context"] or ""),
        questions=prepared_questions
    )


@app.route("/explanation/<int:question_id>", methods=["POST"])
@login_required
def save_explanation(question_id):
    explanation = request.form.get("explanation", "").strip()
    return_to = request.form.get("return_to", "").strip()
    if not explanation:
        if return_to:
            return redirect(return_to)
        return redirect(url_for("question_detail", question_id=question_id))

    conn = get_connection()
    row = conn.execute("SELECT id FROM questions WHERE id = ?", (question_id,)).fetchone()
    if row is None:
        conn.close()
        return "Question not found", 404

    existing = conn.execute(
        "SELECT question_id FROM question_explanations WHERE question_id = ?",
        (question_id,),
    ).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE question_explanations
            SET explanation = ?, updated_by_user_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE question_id = ?
            """,
            (explanation, g.current_user["id"], question_id),
        )
    else:
        conn.execute(
            """
            INSERT INTO question_explanations
            (question_id, explanation, author_user_id, updated_by_user_id)
            VALUES (?, ?, ?, ?)
            """,
            (question_id, explanation, g.current_user["id"], g.current_user["id"]),
        )
    conn.commit()
    conn.close()

    if return_to:
        return redirect(return_to)
    return redirect(url_for("question_detail", question_id=question_id))


@app.route("/report/<int:question_id>", methods=["GET", "POST"])
def report_parse_issue(question_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
    conn.close()

    if row is None:
        return "Question not found", 404
    if is_explanation_or_key_row(row):
        return "Question not available", 404

    prepared = prepare_question(row)
    return_to = (
        request.values.get("return_to", "").strip()
        or request.referrer
        or url_for("question_detail", question_id=question_id)
    )

    if request.method == "GET":
        return render_template(
            "report_issue.html",
            question=prepared,
            return_to=return_to,
        )

    issue_type = request.form.get("issue_type", "").strip()
    detail = request.form.get("detail", "").strip()
    reporter_context = request.form.get("reporter_context", "").strip()
    report_entry = {
        "reported_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "id": row["id"],
        "exam_name": row["exam_name"],
        "question_number": row["question_number"],
        "group_id": row["group_id"] or "",
        "group_type": row["group_type"] or "single",
        "source_test_pdf": row["source_test_pdf"],
        "page_number": row["page_number"],
        "display_issues": prepared["display_issues"],
        "question_text": row["question_text"] or "",
        "code_block": row["code_block"] or "",
        "choices": row["choices"] or "",
        "answer": row["answer"] or "",
        "user_feedback": {
            "issue_type": issue_type,
            "detail": detail,
            "reporter_context": reporter_context,
            "return_to": return_to,
        },
    }

    with open(PARSE_FEEDBACK_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(report_entry) + "\n")

    conn = get_connection()
    save_parse_issue_report(conn, report_entry)
    conn.commit()
    conn.close()

    return redirect(url_for("report_parse_issue", question_id=question_id, return_to=return_to, submitted="1"))


if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG") == "1",
        use_reloader=False,
    )
