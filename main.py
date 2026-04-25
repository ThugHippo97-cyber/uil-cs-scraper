import pdfplumber
import sqlite3
import re
import os
import glob
import sys
import io
import json
import zipfile
import shutil
from datetime import datetime
import subprocess
import tempfile

DB_FILE = "uil_cs_questions_v2.db"
DATA_FOLDER = "data"
ARCHIVE_OVERRIDE_FILE = "archive_overrides.json"
QUESTION_OVERRIDE_FILE = "question_overrides.json"
ARCHIVE_CACHE_ROOT = "_archive_cache"
ANSWER_SANITY_FILE = "answer_sanity_queue.jsonl"
_OCR_UNAVAILABLE_WARNED = False


def connect_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA journal_mode=MEMORY")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


conn = connect_db()
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_test_pdf TEXT NOT NULL,
    source_key_pdf TEXT,
    exam_name TEXT NOT NULL,
    year INTEGER,
    level TEXT,
    question_number INTEGER NOT NULL,
    page_number INTEGER,
    top_y REAL,
    bottom_y REAL,
    question_text TEXT,
    code_block TEXT,
    choices TEXT,
    answer TEXT,
    group_id TEXT,
    group_type TEXT,
    shared_context TEXT,
    UNIQUE(source_test_pdf, question_number)
)
""")
conn.commit()

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


def should_attempt_ocr(extracted_text: str):
    cleaned = (extracted_text or "").strip()
    if not cleaned:
        return True
    alnum_chars = re.findall(r"[A-Za-z0-9]", cleaned)
    return len(alnum_chars) < 60


def extract_text_with_tesseract_ocr(file_path: str, max_pages=14, dpi=220):
    global _OCR_UNAVAILABLE_WARNED
    tesseract_cmd = shutil.which("tesseract")
    if not tesseract_cmd:
        if not _OCR_UNAVAILABLE_WARNED:
            print("OCR fallback unavailable: install 'tesseract' and ensure it is on PATH.")
            _OCR_UNAVAILABLE_WARNED = True
        return ""

    try:
        import pypdfium2 as pdfium
    except Exception:
        if not _OCR_UNAVAILABLE_WARNED:
            print("OCR fallback unavailable: install Python package 'pypdfium2'.")
            _OCR_UNAVAILABLE_WARNED = True
        return ""

    text_pages = []
    try:
        pdf = pdfium.PdfDocument(file_path)
    except Exception:
        return ""

    total_pages = min(len(pdf), max_pages)
    for page_index in range(total_pages):
        image_path = None
        try:
            page = pdf[page_index]
            pil_image = page.render(scale=dpi / 72).to_pil()
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                image_path = tmp.name
            pil_image.save(image_path, format="PNG")
            run = subprocess.run(
                [tesseract_cmd, image_path, "stdout", "--dpi", str(dpi), "-l", "eng", "--psm", "6"],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
            if run.returncode == 0 and run.stdout.strip():
                text_pages.append(run.stdout.strip())
        except Exception:
            continue
        finally:
            if image_path and os.path.exists(image_path):
                try:
                    os.remove(image_path)
                except Exception:
                    pass

    return "\n".join(text_pages).strip()


def extract_full_text(file_path: str, allow_ocr=True):
    pages = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    extracted = "\n".join(pages).strip()

    if allow_ocr and should_attempt_ocr(extracted):
        ocr_text = extract_text_with_tesseract_ocr(file_path)
        if ocr_text and len(ocr_text) > len(extracted):
            return ocr_text

    return extracted


def infer_year(filename: str):
    m = re.search(r"(20\d{2})", filename.lower())
    return int(m.group(1)) if m else None


def infer_year_from_path(path_text: str):
    m = re.search(r"(20\d{2})", path_text.lower())
    return int(m.group(1)) if m else None


def infer_level(filename: str):
    name = filename.lower()
    for token in ["district", "regional", "state", "invitational"]:
        if token in name:
            return token
    return "unknown"


def infer_level_from_path(path_text: str):
    normalized = path_text.replace("\\", "/").lower()
    name = normalized
    base = os.path.basename(normalized)

    if re.search(r"(?<![a-z])dist(?:rict)?(?:\s*\d+)?(?![a-z])", base):
        return "district"
    if re.search(r"(?<![a-z])reg(?:ional)?(?![a-z])", base):
        return "regional"
    if re.search(r"(?<![a-z])state(?![a-z])", base):
        return "state"
    if re.search(r"(?<![a-z])inv(?:itational)?(?:\s*[ab])?(?![a-z])", base):
        return "invitational"

    level_tokens = {
        "district": ["district", "dist"],
        "regional": ["regional", "region"],
        "state": ["state"],
        "invitational": ["invitational", "inv"],
    }

    for level, variants in level_tokens.items():
        if any(re.search(rf"(?<![a-z]){re.escape(token)}(?![a-z])", name) for token in variants):
            return level

    path_parts = [part.strip().lower() for part in normalized.split("/") if part.strip()]
    for idx, part in enumerate(path_parts):
        if re.fullmatch(r"20\d{2}", part) and idx + 1 < len(path_parts):
            next_part = path_parts[idx + 1]
            if next_part in {"a", "b", "c"}:
                return "invitational"
            if next_part in {"d", "district"}:
                return "district"
            if next_part in {"r", "region", "regional"}:
                return "regional"
            if next_part in {"s", "state"}:
                return "state"

    if "study_packet_a" in name or "studypacket_a" in name:
        return "invitational"
    if "study_packet_b" in name or "studypacket_b" in name:
        return "invitational"
    if "study_packet_d" in name or "studypacket_d" in name:
        return "district"
    if "study_packet_s" in name or "studypacket_s" in name:
        return "state"

    if re.search(r"(?i)(?:^|[^a-z])computer_(?:sci|science)_[abcd]_(?:20)?\d{2}(?:[^a-z]|$)", normalized):
        if "_d_" in normalized:
            return "district"
        return "invitational"

    path_parts = [part.strip().lower() for part in normalized.split("/") if part.strip()]
    if len(path_parts) >= 3:
        for idx, part in enumerate(path_parts):
            if re.fullmatch(r"20\d{2}", part) and idx + 1 < len(path_parts):
                next_part = path_parts[idx + 1]
                if next_part not in {"district", "regional", "region", "state", "a", "b", "c", "d", "r", "s", "written"}:
                    return "invitational"
    return "unknown"


def load_archive_overrides():
    if not os.path.exists(ARCHIVE_OVERRIDE_FILE):
        return {}

    try:
        with open(ARCHIVE_OVERRIDE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        print(f"Warning: could not load {ARCHIVE_OVERRIDE_FILE}: {exc}")
        return {}

    return data if isinstance(data, dict) else {}


def load_question_overrides():
    if not os.path.exists(QUESTION_OVERRIDE_FILE):
        return {}

    try:
        with open(QUESTION_OVERRIDE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        print(f"Warning: could not load {QUESTION_OVERRIDE_FILE}: {exc}")
        return {}

    return data if isinstance(data, dict) else {}


def normalize_archive_key(path_text: str):
    return path_text.replace("\\", "/").strip().lower()


def should_ignore_archive_entry(path_text: str, size: int):
    normalized = normalize_archive_key(path_text)
    base = os.path.basename(normalized)

    if size == 0:
        return "empty_file"
    if "/__macosx/" in normalized or base.startswith("~$"):
        return "temporary_file"
    if base.endswith((".docx", ".doc", ".jpeg", ".jpg", ".png")):
        return "unsupported_extension"
    if "answersheet" in base or "answer_sheet" in base or "answer sheet" in base:
        return "answer_sheet"
    if "programming" in normalized:
        return "programming_packet"
    return ""


def detect_pdf_type_from_text(sample_text: str):
    text = sample_text.lower()

    if "contains tests and keys from only" in text or "study packet" in text:
        return "packet"
    if "answer key" in text:
        return "key"
    if re.search(r"(?im)^\s*key\b", sample_text):
        return "key"
    if "questions (+6 points for each correct answer" in text:
        return "key"
    if "explanations:" in text and re.search(r"(?im)^\s*1[\).]\s*[a-e0-9-]+", sample_text):
        return "key"
    if re.search(r"(?im)^\s*question\s*1", sample_text) and (
        "answer key" in text or re.search(r"(?im)^\s*1[\).]\s*[a-e0-9-]+", sample_text)
    ):
        return "combo"
    if re.search(r"(?im)^\s*question\s*1", sample_text):
        return "test"
    if re.search(r"(?im)^\s*1[\).]\s*[a-e0-9-]+", sample_text):
        return "key"
    return "unknown"


def sniff_pdf_text_from_bytes(pdf_bytes: bytes):
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages = pdf.pages
            if not pages:
                return ""

            page_indices = sorted({0, max(0, len(pages) - 2), len(pages) - 1})
            samples = []
            for idx in page_indices:
                text = pages[idx].extract_text() or ""
                if text:
                    samples.append(text)
            return "\n".join(samples)
    except Exception:
        return ""


def sniff_pdf_text_from_path(file_path: str):
    try:
        with open(file_path, "rb") as f:
            return sniff_pdf_text_from_bytes(f.read())
    except Exception:
        return ""


def classify_pdf_type(file_path: str):
    name = os.path.basename(file_path).lower()

    if any(token in name for token in ["study packet", "study_packet", "studypacket"]):
        return "combo"
    if "& key" in name or "testkey" in name or "test & key" in name or "test and key" in name:
        return "combo"
    if any(x in name for x in ["_combo", " combo", "combined", "allinone", "all_in_one"]):
        return "combo"
    if any(x in name for x in ["_key", "-key", " key", "answers", "answer", "solution", "solutions", "_sol", " sol"]):
        return "key"
    if re.search(r"(?<![a-z])(inv(?:itational)?\s*[ab]?|state|reg(?:ional)?|dist(?:rict)?(?:\s*\d+)?)(?![a-z])", name):
        return "test"
    if any(x in name for x in ["_test", "-test", " test", "written", "exam"]):
        return "test"

    return "unknown"


def normalize_exam_name(file_path: str):
    name = os.path.basename(file_path).lower()
    name = re.sub(r"(\.pdf)+$", "", name)
    name = re.sub(r'[_\-\s]*(test|key|combo|combined|answers?|solutions?|sol|written|exam)\b', '', name)
    name = re.sub(r'[_\-\s]+', '_', name).strip('_')
    return name


def guess_exam_name_from_archive_path(path_text: str, pdf_type: str):
    normalized = path_text.replace("\\", "/")
    base = os.path.basename(normalized).lower()
    base = re.sub(r"(\.pdf)+$", "", base)
    path_parts = [part.strip().lower() for part in normalized.split("/") if part.strip()]

    cleaned = re.sub(r'[_\-\s]*(test|key|combo|combined|answers?|solutions?|sol|written|exam|study|packet)\b', '', base)
    cleaned = re.sub(r'^\d+[_\-\s]*', '', cleaned)
    cleaned = re.sub(r'[_\-\s]+', '_', cleaned).strip('_')

    year = infer_year_from_path(normalized)
    level = infer_level_from_path(normalized)

    level_suffix = {
        "district": "district",
        "regional": "regional",
        "state": "state",
        "invitational": "invitational",
    }

    letter_match = re.search(r"(?i)(?:invitational\s*|inv\s*|study[_\s]*packet[_\s]*|studypacket[_\s]*)([a-d])(?:[^a-z]|$)", normalized)
    if "invitational" in level_suffix.get(level, "") and letter_match:
        return f"{year}_{level_suffix[level]}{letter_match.group(1).lower()}"

    if year:
        for idx, part in enumerate(path_parts):
            if re.fullmatch(r"20\d{2}", part) and idx + 1 < len(path_parts):
                school_part = path_parts[idx + 1]
                if school_part not in {
                    "written", "district", "regional", "region", "state",
                    "a", "b", "c", "d", "r", "s", str(year)
                }:
                    school_clean = re.sub(r"[^a-z0-9]+", "_", school_part).strip("_")
                    number_match = re.search(r"(?i)\btest\s*(\d{1,2})\b", base)
                    sample_match = re.search(r"(?i)sample[_\-\s]*test(?:[_\-\s]*(\d{1,2}))?", base)
                    if number_match:
                        return f"{year}_{school_clean}_test_{number_match.group(1)}"
                    if sample_match:
                        sample_num = sample_match.group(1) or "1"
                        return f"{year}_{school_clean}_sample_test_{sample_num}"
                    if school_clean:
                        return f"{year}_{school_clean}"

    for idx, part in enumerate(path_parts):
        if re.fullmatch(r"20\d{2}", part) and idx + 1 < len(path_parts):
            next_part = path_parts[idx + 1]
            if next_part in {"a", "b", "c"}:
                return f"{year}_invitational{next_part}"
            if next_part in {"d", "district"}:
                return f"{year}_district"
            if next_part in {"r", "region", "regional"}:
                return f"{year}_regional"
            if next_part in {"s", "state"}:
                return f"{year}_state"

    if year and level != "unknown":
        level_name = level_suffix[level]
        if level_name in {"district", "regional", "state"}:
            return f"{year}_{level_name}"

    folder_hint = normalized.lower().split("/")
    for part in reversed(folder_hint):
        part = part.strip()
        if not part or part in {"written", str(year or "")}:
            continue
        candidate = re.sub(r"[^a-z0-9]+", "_", part).strip("_")
        if candidate and candidate not in {"key", "test", "combo", "a", "b", "c", "d", "s", "r"}:
            if year and level != "unknown" and candidate not in {str(year), level_suffix.get(level, "")}:
                return f"{year}_{candidate}"

    if cleaned:
        return cleaned
    return f"{year or 'unknown'}_{pdf_type}"


def classify_archive_pdf(entry_path: str, size: int, text_sampler, overrides):
    normalized_key = normalize_archive_key(entry_path)
    override = overrides.get(normalized_key, {})

    filename_type = classify_pdf_type(entry_path)
    sample_text = ""
    content_type = "unknown"

    if override.get("pdf_type"):
        pdf_type = override["pdf_type"]
    else:
        sample_text = text_sampler()
        content_type = detect_pdf_type_from_text(sample_text)
        if filename_type == "packet":
            pdf_type = "packet"
        elif filename_type == "combo":
            pdf_type = "combo"
        elif filename_type == "key":
            pdf_type = "key"
        elif filename_type == "test":
            pdf_type = "test"
        elif content_type == "combo":
            pdf_type = "combo"
        else:
            pdf_type = content_type

    year = override.get("year") or infer_year_from_path(entry_path)
    level = override.get("level") or infer_level_from_path(entry_path)
    exam_name = override.get("exam_name") or guess_exam_name_from_archive_path(entry_path, pdf_type)

    issues = []
    if pdf_type == "unknown":
        issues.append("unknown_pdf_type")
    if pdf_type == "packet" or content_type == "packet":
        issues.append("multi_exam_packet")
    if year is None:
        issues.append("missing_year")
    if level == "unknown":
        issues.append("missing_level")
    if "answersheet" in normalized_key:
        issues.append("looks_like_answer_sheet")

    return {
        "path": entry_path,
        "size": size,
        "pdf_type": pdf_type,
        "filename_type": filename_type,
        "content_type": content_type,
        "year": year,
        "level": level,
        "exam_name": exam_name,
        "issues": issues,
        "override_applied": bool(override),
    }


def build_archive_report(entries, overrides):
    report = {
        "total_entries": len(entries),
        "usable_pdfs": [],
        "ignored": [],
        "ambiguous": [],
    }

    for entry in entries:
        ignore_reason = should_ignore_archive_entry(entry["path"], entry["size"])
        if ignore_reason:
            report["ignored"].append({
                "path": entry["path"],
                "reason": ignore_reason,
                "size": entry["size"],
            })
            continue

        if not entry["path"].lower().endswith(".pdf"):
            report["ignored"].append({
                "path": entry["path"],
                "reason": "unsupported_extension",
                "size": entry["size"],
            })
            continue

        classified = classify_archive_pdf(entry["path"], entry["size"], entry["text_sampler"], overrides)
        report["usable_pdfs"].append(classified)

    by_exam = {}
    for row in report["usable_pdfs"]:
        by_exam.setdefault(row["exam_name"], []).append(row)

    for exam_rows in by_exam.values():
        type_counts = {}
        for row in exam_rows:
            type_counts[row["pdf_type"]] = type_counts.get(row["pdf_type"], 0) + 1

        duplicate_issue_map = {
            "test": "duplicate_test_files",
            "key": "duplicate_key_files",
            "combo": "duplicate_combo_files",
        }
        for pdf_type, issue_name in duplicate_issue_map.items():
            if type_counts.get(pdf_type, 0) > 1:
                for row in exam_rows:
                    if row["pdf_type"] == pdf_type and issue_name not in row["issues"]:
                        row["issues"].append(issue_name)

    for row in report["usable_pdfs"]:
        if row["issues"]:
            report["ambiguous"].append(row)

    return report


def build_safe_archive_exam_groups(report):
    grouped = {}

    for row in report["usable_pdfs"]:
        if row["issues"]:
            continue
        if row["pdf_type"] not in {"test", "key", "combo"}:
            continue

        exam_name = row["exam_name"]
        if exam_name not in grouped:
            grouped[exam_name] = {
                "exam_name": exam_name,
                "year": row["year"],
                "level": row["level"],
                "test": None,
                "key": None,
                "combo": None,
            }

        grouped[exam_name][row["pdf_type"]] = row["path"]

    safe_groups = {}
    for exam_name, files in grouped.items():
        if files["combo"] or (files["test"] and files["key"]):
            safe_groups[exam_name] = files

    return safe_groups


def materialize_archive_file(source_path: str, entry_path: str):
    if zipfile.is_zipfile(source_path):
        archive_name = os.path.splitext(os.path.basename(source_path))[0]
        target_path = os.path.join(ARCHIVE_CACHE_ROOT, archive_name, *entry_path.replace("\\", "/").split("/"))
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        if not os.path.exists(target_path):
            with zipfile.ZipFile(source_path, "r") as zf:
                with zf.open(entry_path) as src, open(target_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)

        return target_path

    return os.path.join(source_path, entry_path)


def iter_archive_entries(source_path: str):
    if zipfile.is_zipfile(source_path):
        with zipfile.ZipFile(source_path, "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                pdf_bytes = None
                if info.filename.lower().endswith(".pdf"):
                    pdf_bytes = zf.read(info)

                yield {
                    "path": info.filename,
                    "size": info.file_size,
                    "text_sampler": (lambda data=pdf_bytes: sniff_pdf_text_from_bytes(data)) if pdf_bytes is not None else (lambda: ""),
                }
        return

    for root, _, files in os.walk(source_path):
        for file_name in files:
            full_path = os.path.join(root, file_name)
            rel_path = os.path.relpath(full_path, source_path)
            size = os.path.getsize(full_path)
            yield {
                "path": rel_path,
                "size": size,
                "text_sampler": lambda path=full_path: sniff_pdf_text_from_path(path),
            }


def write_archive_report(report, output_path="archive_scan_report.json"):
    serializable = {
        "total_entries": report["total_entries"],
        "usable_pdfs": report["usable_pdfs"],
        "ignored": report["ignored"],
        "ambiguous": report["ambiguous"],
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)


def print_archive_report(report):
    usable = report["usable_pdfs"]
    ambiguous = report["ambiguous"]
    ignored = report["ignored"]

    type_counts = {}
    level_counts = {}
    for item in usable:
        type_counts[item["pdf_type"]] = type_counts.get(item["pdf_type"], 0) + 1
        level_counts[item["level"]] = level_counts.get(item["level"], 0) + 1

    print(f"Archive scan found {report['total_entries']} file(s).")
    print(f"Usable PDFs: {len(usable)}")
    print(f"Ignored files: {len(ignored)}")
    print(f"Ambiguous PDFs needing review: {len(ambiguous)}")

    if type_counts:
        print("\nPDF types:")
        for key, count in sorted(type_counts.items()):
            print(f"  {key}: {count}")

    if level_counts:
        print("\nLevels:")
        for key, count in sorted(level_counts.items()):
            print(f"  {key}: {count}")

    if ignored:
        print("\nIgnored sample:")
        for item in ignored[:10]:
            print(f"  {item['reason']}: {item['path']}")

    if ambiguous:
        print("\nAmbiguous sample:")
        for item in ambiguous[:20]:
            issue_text = ", ".join(item["issues"])
            print(
                f"  {item['path']} | type={item['pdf_type']} | year={item['year']} "
                f"| level={item['level']} | exam_name={item['exam_name']} | {issue_text}"
            )


def extract_question_section(full_text: str):
    start_match = re.search(r"(?im)^\s*Question\s*1(?:\D|$)", full_text)
    if not start_match:
        raise ValueError("Could not find start of question section ('Question 1').")

    start = start_match.start()
    key_match = re.search(r"(?im)^\s*KEY\b", full_text[start:])
    if key_match:
        end = start + key_match.start()
        return full_text[start:end]
    return full_text[start:]


def validate_question_sequence(parsed_questions, source_name):
    nums = [q["question_number"] for q in parsed_questions]

    if not nums:
        print(f"{source_name}: warning - no questions parsed")
        return

    expected = list(range(1, max(nums) + 1))
    if nums != expected:
        print(f"{source_name}: warning - question numbers parsed were {nums}")


def split_questions(question_text: str):
    matches = list(re.finditer(r"(?im)^\s*Question\s*(\d+)", question_text))
    questions = []

    for i, match in enumerate(matches):
        qnum = int(match.group(1))
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(question_text)
        block = question_text[start:end].strip()
        questions.append((qnum, block))

    return questions


def looks_like_shared_reference(text):
    if not text:
        return False

    text = text.lower()
    phrases = [
        "the code",
        "code to the right",
        "code above",
        "shown",
        "above",
        "to the right",
        "following code",
        "given code",
        "consider the following",
        "class shown",
        "method shown"
    ]
    return any(p in text for p in phrases)


def looks_like_explicit_shared_reference(text):
    if not text:
        return False

    text = text.lower()
    phrases = [
        "use this code",
        "use the code",
        "answer questions",
        "given class",
        "given classes",
        "class shown",
        "method shown",
        "client code",
        "line marked",
        "implementation",
        "replace <",
        "filled in correctly",
        "compiles and functions as intended",
        "functions correctly",
    ]
    return any(p in text for p in phrases)


def code_block_size(text):
    if not text:
        return 0
    return len([line.strip() for line in text.splitlines() if line.strip()])


def code_block_declares_shared_usage(text):
    if not text:
        return False

    normalized = " ".join(line.strip().lower() for line in text.splitlines() if line.strip())
    return "answer question" in normalized or "use this code" in normalized or "use the code" in normalized


def code_block_declares_reusable_definition(text):
    if not text:
        return False

    lines = [line.strip().lower() for line in text.splitlines() if line.strip()]
    if not lines:
        return False

    signature_patterns = [
        r"^(public|private|protected)\s+static\s+\w[\w<>\[\]]*\s+\w+\s*\(",
        r"^(public|private|protected)\s+\w[\w<>\[\]]*\s+\w+\s*\(",
        r"^class\s+\w+",
        r"^public\s+class\s+\w+",
    ]

    return any(re.match(pattern, line) for pattern in signature_patterns for line in lines[:3])


def normalize_code_line(line):
    cleaned = re.sub(r"\s+", " ", line.strip().lower())
    cleaned = re.sub(r"[^a-z0-9_<>{}()[\].,+\-/*=;:!\"' ]+", "", cleaned)
    return cleaned.strip()


def code_blocks_overlap(text1, text2):
    if not text1 or not text2:
        return False

    lines1 = {
        normalize_code_line(line)
        for line in text1.splitlines()
        if normalize_code_line(line) and len(normalize_code_line(line)) >= 8
    }
    lines2 = {
        normalize_code_line(line)
        for line in text2.splitlines()
        if normalize_code_line(line) and len(normalize_code_line(line)) >= 8
    }

    return bool(lines1 & lines2)


def merge_code_blocks(*blocks):
    merged_lines = []
    seen = set()

    for block in blocks:
        if not block:
            continue

        for raw_line in block.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.lower().startswith("written test"):
                continue

            key = normalize_code_line(line)
            should_dedupe = key not in {"{", "}"}

            if not should_dedupe:
                merged_lines.append(line)
                continue

            if key and key not in seen:
                seen.add(key)
                merged_lines.append(line)

    return "\n".join(merged_lines).strip()


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


def question_references_method_name(question_text, method_names):
    text = (question_text or "").lower()
    if not text or not method_names:
        return False

    for method_name in method_names:
        if re.search(rf"\b{re.escape(method_name)}\s*\(", text):
            return True
        if re.search(rf"\bmethod\s+{re.escape(method_name)}\b", text):
            return True

    return False


def apply_method_reference_groups(parsed_questions, exam_name, year):
    assigned = set()

    for idx, question in enumerate(parsed_questions):
        if idx in assigned or question.get("group_type", "single") != "single":
            continue

        anchor_code = question.get("code_block", "")
        method_names = extract_declared_method_names(anchor_code)
        if code_block_size(anchor_code) < 3 or not method_names:
            continue

        member_indices = [idx]

        left = idx - 1
        while left >= 0:
            candidate = parsed_questions[left]
            if candidate.get("group_type", "single") != "single":
                break
            if candidate.get("page_number") != question.get("page_number"):
                break
            if candidate.get("question_number") != parsed_questions[left + 1].get("question_number", 0) - 1:
                break
            if question_references_method_name(candidate.get("question_text", ""), method_names):
                member_indices.insert(0, left)
                left -= 1
                continue
            break

        right = idx + 1
        while right < len(parsed_questions):
            candidate = parsed_questions[right]
            if candidate.get("group_type", "single") != "single":
                break
            if candidate.get("page_number") != question.get("page_number"):
                break
            if candidate.get("question_number") != parsed_questions[right - 1].get("question_number", 0) + 1:
                break
            if (
                question_references_method_name(candidate.get("question_text", ""), method_names)
                or (
                    looks_like_explicit_shared_reference(candidate.get("question_text", ""))
                    and code_block_size(candidate.get("code_block", "")) < 3
                )
            ):
                member_indices.append(right)
                right += 1
                continue
            break

        if len(member_indices) <= 1:
            continue

        first_member = parsed_questions[member_indices[0]]
        last_member = parsed_questions[member_indices[-1]]
        page_number = first_member.get("page_number", 0)
        group_id = (
            f"{year}_{exam_name}_p{page_number}_shared_"
            f"{first_member['question_number']}_{last_member['question_number']}"
        )
        shared_context = merge_code_blocks(
            *(parsed_questions[member_idx].get("code_block", "") for member_idx in member_indices)
        )

        for member_idx in member_indices:
            parsed_questions[member_idx]["group_id"] = group_id
            parsed_questions[member_idx]["group_type"] = "shared_code"
            parsed_questions[member_idx]["shared_context"] = shared_context
            assigned.add(member_idx)

    return parsed_questions


def question_can_anchor_shared_group(question):
    code_block = question.get("code_block", "")
    question_text = question.get("question_text", "")

    return (
        code_block_size(code_block) >= 3 and
        (
            looks_like_explicit_shared_reference(question_text) or
            code_block_declares_shared_usage(code_block) or
            code_block_declares_reusable_definition(code_block)
        )
    )


def question_uses_fill_in_placeholder(text):
    return bool(re.search(r"<\d+\*>", text or ""))


def extract_search_tags(question_text, code_block, shared_context=""):
    tags = set()
    combined_code = "\n".join(part for part in [code_block, shared_context] if part)
    combined_text = "\n".join(part for part in [question_text, combined_code] if part).lower()

    normalized_code = combined_code.lower()

    for method_name in extract_declared_method_names(combined_code):
        if normalized_code.count(f"{method_name.lower()}(") > 1:
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


def looks_like_code_line(line):
    stripped = line.strip()
    if not stripped:
        return False

    code_starts = (
        "//",
        "for(", "for (", "while(", "while (", "if(", "if (",
        "else", "return ", "public ", "private ", "protected ",
        "static ", "class ", "new ", "try", "catch", "throws ",
        "Scanner ", "System.out", "out.print", "out.println"
    )

    if stripped.startswith(code_starts):
        return True
    if stripped.endswith(";"):
        return True
    if stripped in {"{", "}"}:
        return True
    if "++" in stripped or "--" in stripped:
        return True
    if re.search(r"\b[A-Za-z_]\w*\s*=\s*.+", stripped):
        return True

    return False


def split_prompt_and_embedded_code(prompt_text):
    if not prompt_text:
        return "", ""

    if re.search(r"(?i)\boutput of (?:this|the)\s+client code\b", prompt_text):
        return prompt_text.strip(), ""

    prompt_lines = []
    code_lines = []
    for raw_line in prompt_text.replace("\r", "\n").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if looks_like_code_line(line):
            code_lines.append(line)
            continue

        if re.match(r"(?i)^\s*}\s*(?:catch|finally|else|while)\b", line):
            code_lines.append(line)
            continue

        if re.match(r"(?i)^\s*(?:catch|finally|else)\b", line):
            code_lines.append(line)
            continue

        prompt_lines.append(line)

    return "\n".join(prompt_lines).strip(), "\n".join(code_lines).strip()


def split_prompt_and_leaked_choice_labels(prompt_text):
    if not prompt_text:
        return "", []

    kept_lines = []
    leaked_labels = []
    for raw_line in prompt_text.replace("\r", "\n").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        label_only = re.fullmatch(r"(?i)([A-E])[\.)]\s*", line)
        if label_only:
            leaked_labels.append(f"{label_only.group(1).upper()})")
            continue

        kept_lines.append(line)

    return "\n".join(kept_lines).strip(), leaked_labels


def split_prompt_and_code(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    prompt_lines = []
    code_lines = []

    for line in lines:
        if looks_like_code_line(line):
            code_lines.append(line)
        else:
            prompt_lines.append(line)

    return "\n".join(prompt_lines).strip(), "\n".join(code_lines).strip()


def split_choices(text):
    choice_start = re.search(r"(?m)^\s*A[\.)]\s+", text)
    if choice_start:
        return text[:choice_start.start()].strip(), text[choice_start.start():].strip()
    return text.strip(), ""


def is_choice_line(text):
    if not text:
        return False
    return bool(re.match(r"^\s*[A-E][\.)]\s+", text, re.IGNORECASE))


def remove_parser_noise_lines(text):
    if not text:
        return ""

    noise_patterns = [
        r"^written test",
        r"^test\s+[–-]",
        r"^uil computer science\b",
        r"^\(?c\)?\s*a\+",
        r"^©\s*a\+",
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


def count_inline_choice_markers(text):
    if not text:
        return 0
    return len(re.findall(r'(?i)(?<!\w)[A-E][\.)]\s*', text))


def normalize_choice_fragment(text):
    return re.sub(r"\s+", " ", (text or "").strip()).strip()


def split_trailing_choice_leak(prompt_text):
    if not prompt_text:
        return "", ""

    lines = [line.strip() for line in prompt_text.splitlines() if line.strip()]
    if not lines:
        return "", ""

    leak_idx = None
    for idx in range(len(lines)):
        if not re.match(r'(?i)^[A-E][\.)]\s*', lines[idx]):
            continue
        remaining = "\n".join(lines[idx:])
        marker_count = count_inline_choice_markers(remaining)
        if marker_count >= 2:
            leak_idx = idx
            break
        if idx == len(lines) - 1 and marker_count == 1:
            leak_idx = idx
            break

    if leak_idx is None:
        return prompt_text.strip(), ""

    cleaned_prompt = "\n".join(lines[:leak_idx]).strip()
    leaked_choices = "\n".join(lines[leak_idx:]).strip()
    return cleaned_prompt, leaked_choices


def rebuild_choice_block(*parts):
    raw = "\n".join(part for part in parts if part).strip()
    if not raw:
        return ""

    matches = list(re.finditer(r'(?i)(?<!\w)([A-E])[\.)]\s*', raw))
    if not matches:
        return raw

    label_to_content = {}
    for idx, match in enumerate(matches):
        label = match.group(1).upper()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(raw)
        content = normalize_choice_fragment(raw[start:end])
        if content and (label not in label_to_content or len(content) > len(label_to_content[label])):
            label_to_content[label] = content

    rebuilt = []
    for label in ["A", "B", "C", "D", "E"]:
        if label in label_to_content:
            rebuilt.append(f"{label}. {label_to_content[label]}")

    return "\n".join(rebuilt).strip() if rebuilt else raw


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

    footer_match = re.search(r"(?im)^\s*uil computer science\b", block)
    if footer_match:
        block = block[:footer_match.start()]

    label_match = re.search(r"(?im)^\s*([A-E][\.)]\s+)", block)
    if not label_match:
        return ""

    return block[label_match.start(1):].strip()


def rebuild_compact_choice_grid(text):
    if not text:
        return ""

    def scalar_tokens(line):
        normalized = (line or "").replace("−", "-").replace("–", "-").replace("—", "-")
        normalized = re.sub(r"(?<!\w)-\s+(?=\d)", "-", normalized)
        return re.findall(r"(?i)LINE\s*#\d+|[+-]?\d+(?:\.\d+)?|[A-Za-z_][\w'.:/+-]*", normalized)

    lines = [line.strip() for line in text.replace("\r", "\n").splitlines() if line.strip()]
    if not lines:
        return ""

    choice_values = {}
    pending_labels = []
    signed_label = None

    for line in lines:
        if looks_like_code_line(line) and not re.match(r"(?i)^[A-E][\.)]", line):
            continue

        label_matches = list(re.finditer(r"(?i)\b([A-E])[\.)]", line))
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

        if signed_label and signed_label in choice_values and choice_values[signed_label] in {"-", "+"} and len(tokens) == len(pending_labels) + 1:
            choice_values[signed_label] = f"{choice_values[signed_label]}{tokens[0]}"
            tokens = tokens[1:]
            signed_label = None

        if len(tokens) != len(pending_labels):
            continue

        for label, token in zip(pending_labels, tokens):
            choice_values[label] = token
        pending_labels = []

    rebuilt = []
    for label in ["A", "B", "C", "D", "E"]:
        value = normalize_choice_fragment(choice_values.get(label, ""))
        if value:
            rebuilt.append(f"{label}) {value}")

    return "\n".join(rebuilt).strip()


def count_parsed_choice_entries(text):
    if not text:
        return 0

    try:
        from app import parse_choices
        return len(parse_choices(text))
    except Exception:
        return 0


def split_choice_prefix_from_code_line(line):
    if not line:
        return "", ""

    match = re.match(
        r'^\s*(-?\d+(?:\.\d+)?)\s+(?=(?:for\s*\(|while\s*\(|if\s*\(|do\{?|return\b|out\.|[A-Za-z_]\w*\s*(?:\+\+|--|=)|[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\s*\())',
        line,
        re.IGNORECASE,
    )
    if not match:
        return "", line

    choice_text = normalize_choice_fragment(match.group(1))
    remainder = line[match.end(1):].strip()
    if not choice_text or not remainder:
        return "", line

    return choice_text, remainder


def split_right_side_reference(text):
    patterns = [
        r"(.*?\bcode to the right\??)(.*)",
        r"(.*?\bclient code to the right\??)(.*)",
        r"(.*?\bclass shown to the right\??)(.*)",
        r"(.*?\bmethod shown to the right\??)(.*)",
        r"(.*?\bline marked .*?\bto the right\??)(.*)",
        r"(.*?\blisted to the right\??)(.*)",
    ]

    for pattern in patterns:
        m = re.match(pattern, text, re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1).strip(), m.group(2).strip()

    return text.strip(), ""


def pull_code_out_of_choices(choices_text):
    if not choices_text:
        return "", ""

    lines = [line.strip() for line in choices_text.splitlines() if line.strip()]
    cleaned_choice_lines = []
    extracted_code_lines = []

    for line in lines:
        label_match = re.match(r"^([A-E][\.)])\s*(.*)$", line, re.IGNORECASE)
        if not label_match:
            cleaned_choice_lines.append(line)
            continue

        label = label_match.group(1).upper().replace(".", ")")
        body = (label_match.group(2) or "").strip()
        if not body:
            cleaned_choice_lines.append(f"{label}")
            continue

        # Conservative leak recovery: only split when a numeric scalar option
        # is immediately followed by a code statement that clearly belongs to
        # prompt/shared code, not a legitimate code-like answer choice.
        scalar_then_code = re.match(r"^([+-]?\d+(?:\.\d+)?)\s+(.+)$", body)
        if scalar_then_code:
            scalar = scalar_then_code.group(1).strip()
            trailing = scalar_then_code.group(2).strip()
            if trailing and looks_like_code_line(trailing):
                cleaned_choice_lines.append(f"{label} {scalar}")
                extracted_code_lines.append(trailing)
                continue

        cleaned_choice_lines.append(f"{label} {body}".strip())

    return "\n".join(cleaned_choice_lines).strip(), "\n".join(extracted_code_lines).strip()


def parse_question_block(block: str):
    lines = [line.strip() for line in block.splitlines() if line.strip()]

    if lines and re.match(r"Question\s+\d+\b\.?", lines[0], re.IGNORECASE):
        lines = lines[1:]

    joined = "\n".join(lines)
    before_choices, choices_part = split_choices(joined)
    prompt_candidate, right_side_candidate = split_right_side_reference(before_choices)

    code_lines = []
    extra_prompt_lines = []

    if right_side_candidate:
        right_lines = [line.strip() for line in right_side_candidate.splitlines() if line.strip()]
        for line in right_lines:
            if looks_like_code_line(line):
                code_lines.append(line)
            else:
                extra_prompt_lines.append(line)

    if not right_side_candidate:
        prompt_text, code_block = split_prompt_and_code(before_choices)
    else:
        prompt_text = prompt_candidate
        if extra_prompt_lines:
            prompt_text = (prompt_text + "\n" + "\n".join(extra_prompt_lines)).strip()
        code_block = "\n".join(code_lines).strip()

    cleaned_choices, extra_code_from_choices = pull_code_out_of_choices(choices_part)
    if extra_code_from_choices:
        code_block = (code_block + "\n" + extra_code_from_choices).strip() if code_block else extra_code_from_choices

    return prompt_text.strip(), code_block.strip(), cleaned_choices.strip()


def parse_test_pdf(file_path: str):
    filename = os.path.basename(file_path).lower()
    layout_parsed = None

    try:
        layout_parsed = extract_questions_layout_aware(file_path, split_x=280)
    except Exception:
        layout_parsed = None

    if layout_parsed:
        question_numbers = [q["question_number"] for q in layout_parsed]
        if len(layout_parsed) >= 35 and question_numbers and max(question_numbers) >= 35:
            validate_question_sequence(layout_parsed, os.path.basename(file_path))
            return layout_parsed

    full_text = extract_full_text(file_path)
    question_section = extract_question_section(full_text)
    question_blocks = split_questions(question_section)

    parsed = []
    for qnum, block in question_blocks:
        question_text, code_block, choices_text = parse_question_block(block)
        parsed.append({
            "question_number": qnum,
            "question_text": question_text,
            "code_block": code_block,
            "choices": choices_text,
            "page_number": 0,
            "top_y": 0,
            "bottom_y": 0,
        })

    if layout_parsed and len(layout_parsed) > len(parsed):
        validate_question_sequence(layout_parsed, os.path.basename(file_path))
        return layout_parsed

    validate_question_sequence(parsed, os.path.basename(file_path))
    return parsed


def parse_answers_from_text(answer_text: str):
    answers = {}
    symbolic_token_pattern = re.compile(r"^(?:<<|>>|<=|>=|==|!=|\+\+|--|&&|\|\||[+\-*/%^~!<>&|]{1,4})$")

    def salvage_open_response_token(value: str):
        cleaned = " ".join((value or "").split()).strip()
        if not cleaned:
            return ""
        if cleaned.lower().startswith("see explanation"):
            return "See Explanation"

        token = cleaned.split()[0].strip().rstrip(",;")
        if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", token):
            return token
        if symbolic_token_pattern.fullmatch(token):
            return token
        if "cid:" in token.lower():
            if len(token) >= 12 and token.lower().count("cid:") >= 2:
                return token
            return ""
        if re.fullmatch(r"[A-Za-z0-9+\-*/.=()]{2,48}", token):
            return token
        return ""

    def is_plausible_answer_value(value: str, qnum=None):
        cleaned = (value or "").strip()
        if not cleaned:
            return False
        allow_leading_symbolic = (
            qnum is not None
            and int(qnum) >= 37
            and re.match(r"^[!<>()+\-*/]", cleaned)
        )
        if re.match(r"^[,;:.!?)]", cleaned) and not allow_leading_symbolic:
            return False
        if symbolic_token_pattern.fullmatch(cleaned):
            return True
        if not re.search(r"[A-Za-z0-9]", cleaned):
            return False

        lowered = cleaned.lower()
        disallowed_fragments = (
            "which of the following",
            "convert the",
            "make the boolean",
            "question ",
        )
        if qnum is None or int(qnum) < 39:
            disallowed_fragments = ("cid:", *disallowed_fragments)
        if any(fragment in lowered for fragment in disallowed_fragments):
            return False

        if "cid:" in lowered:
            return len(cleaned) >= 12 and lowered.count("cid:") >= 2

        words = re.findall(r"[A-Za-z0-9+\-*/.=]+", cleaned)
        max_words = 20 if qnum is not None and int(qnum) >= 37 else 6
        if len(words) > max_words:
            return False
        if cleaned.count(",") >= 2 and len(words) > 3 and not (qnum is not None and int(qnum) >= 37):
            return False
        return True

    def answer_quality(value: str):
        if not value:
            return 0
        if re.fullmatch(r"[A-E]", value, re.IGNORECASE):
            return 100
        if re.fullmatch(r"(?:TRUE|FALSE|T|F)", value, re.IGNORECASE):
            return 95
        if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", value):
            return 90
        if " " in value:
            return 65
        return 80

    def normalize_answer_value(raw_value: str):
        value = " ".join((raw_value or "").replace("\r", " ").replace("\n", " ").split()).strip()
        if not value:
            return ""

        letter_match = re.match(r"^([A-E])\b", value, re.IGNORECASE)
        if letter_match:
            return letter_match.group(1).upper()
        numeric_with_explanation = re.match(r"^([+-]?\d+(?:\.\d+)?)\s+[A-Za-z]", value)
        if numeric_with_explanation:
            return numeric_with_explanation.group(1)

        value = value.lstrip("*").strip()
        value = re.sub(r"\s*\*+$", "", value).strip()
        return value

    qnum_pattern = re.compile(r"(?<![A-Za-z0-9:])\*?\s*(\d+)(?:\)|\.(?=\s))\s*")

    for raw_line in answer_text.replace("\r", "\n").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        likely_choice_text = bool(re.search(r"(?i)\b[A-E][\.)]\s+", line))
        compact_pairs = re.findall(r"(?<!\w)(\d{1,2})\s+([A-E]|TRUE|FALSE|T|F)\b", line, re.IGNORECASE)
        if (
            len(compact_pairs) >= 2
            and re.match(r"^\*?\s*\d", line)
            and not likely_choice_text
        ):
            for raw_qnum, raw_answer in compact_pairs:
                qnum = int(raw_qnum)
                if qnum < 1 or qnum > 40:
                    continue
                candidate = normalize_answer_value(raw_answer)
                if not is_plausible_answer_value(candidate, qnum=qnum):
                    continue
                existing = answers.get(qnum)
                if not existing or answer_quality(candidate) > answer_quality(existing):
                    answers[qnum] = candidate

        matches = list(qnum_pattern.finditer(line))
        if not matches:
            continue

        if re.search(r"[A-Za-z]", line[:matches[0].start()]):
            continue

        for idx, match in enumerate(matches):
            qnum = int(match.group(1))
            if qnum < 1 or qnum > 40:
                continue

            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(line)
            candidate = normalize_answer_value(line[start:end])
            if not is_plausible_answer_value(candidate, qnum=qnum):
                if qnum >= 39 and qnum not in answers:
                    fallback = salvage_open_response_token(candidate)
                    if fallback:
                        answers[qnum] = fallback
                continue

            existing = answers.get(qnum)
            if not existing or answer_quality(candidate) > answer_quality(existing):
                answers[qnum] = candidate

    return answers


def parse_key_pdf(file_path: str):
    full_text = extract_full_text(file_path)
    answers = parse_answers_from_text(full_text)
    if not answers:
        raise ValueError("Could not parse any answers from key PDF.")
    return answers


def normalize_choice_answer_token(answer: str):
    token = (answer or "").strip().upper()
    if token == "TRUE":
        return "T"
    if token == "FALSE":
        return "F"
    return token


def evaluate_answer_sanity(question_text: str, choices_text: str, answer: str):
    issues = []
    normalized_answer = normalize_choice_answer_token(answer)
    question_text = question_text or ""
    choices_text = choices_text or ""

    from app import parse_choices  # Keep sanity checks aligned with runtime choice parsing.

    parsed_choices = parse_choices(choices_text)
    parsed_labels = [choice["letter"] for choice in parsed_choices if choice.get("text", "").strip()]
    has_choice_markers = bool(re.search(r"(?i)\b(?:[A-E]|TRUE|FALSE|T|F)[\.)](?=\s|$)", choices_text))
    likely_choice_question = bool(parsed_labels) or has_choice_markers

    if not normalized_answer:
        issues.append("missing_answer")
        return issues

    if likely_choice_question:
        if not re.fullmatch(r"[A-ETF]", normalized_answer, re.IGNORECASE):
            issues.append("choice_question_non_choice_answer")
        elif parsed_labels and normalized_answer not in parsed_labels:
            issues.append("answer_not_in_parsed_choices")
        elif not parsed_labels:
            issues.append("choice_labels_not_parsed")
    else:
        if re.fullmatch(r"[A-ETF]", normalized_answer, re.IGNORECASE):
            # Open-response rows with letter answers are usually parse mistakes.
            if len(question_text.strip()) > 0:
                issues.append("open_response_letter_answer")

    return issues


def append_answer_sanity_findings(entries):
    if not entries:
        return
    with open(ANSWER_SANITY_FILE, "a", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def vertical_overlap(q1, q2, tolerance=40):
    return not (
        q1["bottom_y"] < q2["top_y"] - tolerance or
        q2["bottom_y"] < q1["top_y"] - tolerance
    )


def assign_groups(parsed_questions, exam_name, year):
    grouped = []
    i = 0

    while i < len(parsed_questions):
        q = parsed_questions[i]
        page_number = q.get("page_number", 0)

        group_id = f"{year}_{exam_name}_p{page_number}_q{q['question_number']}"
        group_type = "single"
        shared_context = ""

        if question_can_anchor_shared_group(q):
            members = [q]
            j = i + 1
            shared_code = q.get("code_block", "").strip()

            while j < len(parsed_questions):
                next_q = parsed_questions[j]
                same_page = next_q["page_number"] == q["page_number"]
                close_number = next_q["question_number"] == members[-1]["question_number"] + 1
                overlaps_shared_code = code_blocks_overlap(shared_code, next_q.get("code_block", ""))
                references_shared = (
                    looks_like_explicit_shared_reference(next_q.get("question_text", ""))
                    and (
                        overlaps_shared_code
                        or code_block_size(next_q.get("code_block", "")) < 3
                        or question_uses_fill_in_placeholder(next_q.get("question_text", ""))
                    )
                )
                placeholder_chain = (
                    code_block_declares_reusable_definition(shared_code)
                    and (
                        question_uses_fill_in_placeholder(members[-1].get("question_text", ""))
                        or question_uses_fill_in_placeholder(next_q.get("question_text", ""))
                    )
                    and code_block_size(next_q.get("code_block", "")) >= 3
                )
                overlaps = vertical_overlap(members[-1], next_q)

                if same_page and close_number and overlaps and (references_shared or overlaps_shared_code or placeholder_chain):
                    members.append(next_q)
                    if next_q.get("code_block", "").strip():
                        shared_code = (shared_code + "\n" + next_q["code_block"].strip()).strip()
                    j += 1
                else:
                    break

            if len(members) > 1:
                group_id = f"{year}_{exam_name}_p{page_number}_shared_{q['question_number']}_{members[-1]['question_number']}"
                group_type = "shared_code"
                shared_context = merge_code_blocks(*(member.get("code_block", "") for member in members))

                for member in members:
                    member["group_id"] = group_id
                    member["group_type"] = group_type
                    member["shared_context"] = shared_context
                grouped.extend(members)
                i = j
                continue

        q["group_id"] = group_id
        q["group_type"] = group_type
        q["shared_context"] = shared_context
        grouped.append(q)
        i += 1

    return apply_method_reference_groups(grouped, exam_name, year)


def pair_pdfs(pdf_files):
    grouped = {}
    for pdf_file in pdf_files:
        exam_name = normalize_exam_name(pdf_file)
        pdf_type = classify_pdf_type(pdf_file)

        if exam_name not in grouped:
            grouped[exam_name] = {"test": None, "key": None, "combo": None, "unknown": []}

        if pdf_type == "test":
            grouped[exam_name]["test"] = pdf_file
        elif pdf_type == "key":
            grouped[exam_name]["key"] = pdf_file
        elif pdf_type == "combo":
            grouped[exam_name]["combo"] = pdf_file
        else:
            grouped[exam_name]["unknown"].append(pdf_file)

    return grouped


def insert_questions(rows):
    before = conn.total_changes

    c.executemany("""
    INSERT INTO questions
    (source_test_pdf, source_key_pdf, exam_name, year, level, question_number,
     page_number, top_y, bottom_y, question_text, code_block, choices, answer,
     group_id, group_type, shared_context)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(source_test_pdf, question_number) DO UPDATE SET
        source_key_pdf=excluded.source_key_pdf,
        exam_name=excluded.exam_name,
        year=excluded.year,
        level=excluded.level,
        page_number=excluded.page_number,
        top_y=excluded.top_y,
        bottom_y=excluded.bottom_y,
        question_text=excluded.question_text,
        code_block=excluded.code_block,
        choices=excluded.choices,
        answer=excluded.answer,
        group_id=excluded.group_id,
        group_type=excluded.group_type,
        shared_context=excluded.shared_context
    """, rows)

    conn.commit()
    after = conn.total_changes
    return after - before


def clear_questions_table():
    c.execute("DELETE FROM questions")
    conn.commit()


def ingest_exam_pair(exam_name, test_pdf, key_pdf, year=None, level=None, source_test_id=None, source_key_id=None):
    test_source = source_test_id or os.path.basename(test_pdf)
    key_source = source_key_id or (os.path.basename(key_pdf) if key_pdf else None)

    year = year if year is not None else infer_year(test_source)
    level = level if level is not None else infer_level(test_source)

    questions = parse_test_pdf(test_pdf)
    questions = assign_groups(questions, exam_name, year)
    answers = parse_key_pdf(key_pdf) if key_pdf else {}

    rows = []
    sanity_findings = []
    for q in questions:
        qnum = q["question_number"]
        answer_value = answers.get(qnum, "")
        sanity_issues = evaluate_answer_sanity(
            q.get("question_text", ""),
            q.get("choices", ""),
            answer_value,
        )
        if sanity_issues:
            sanity_findings.append({
                "reported_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "exam_name": exam_name,
                "source_test_pdf": test_source,
                "source_key_pdf": key_source,
                "question_number": qnum,
                "issues": sanity_issues,
                "answer": answer_value,
                "question_preview": re.sub(r"\s+", " ", (q.get("question_text", "") or "")).strip()[:180],
                "choices_preview": re.sub(r"\s+", " ", (q.get("choices", "") or "")).strip()[:180],
            })

        rows.append((
            test_source,
            key_source,
            exam_name,
            year,
            level,
            qnum,
            q.get("page_number", 0),
            q.get("top_y", 0),
            q.get("bottom_y", 0),
            q["question_text"],
            q["code_block"],
            q["choices"],
            answer_value,
            q.get("group_id", ""),
            q.get("group_type", "single"),
            q.get("shared_context", "")
        ))

    inserted = insert_questions(rows)
    append_answer_sanity_findings(sanity_findings)
    if sanity_findings:
        print(
            f"{exam_name}: answer sanity flagged {len(sanity_findings)} question(s) "
            f"(logged to {ANSWER_SANITY_FILE})"
        )
    return len(rows), inserted


def ingest_all_pdfs():
    pdf_files = sorted(glob.glob(os.path.join(DATA_FOLDER, "*.pdf")))

    if not pdf_files:
        print("No PDF files found in data/.")
        return

    pairs = pair_pdfs(pdf_files)
    total_parsed = 0
    total_inserted = 0

    for exam_name, files in sorted(pairs.items()):
        test_pdf = files["test"]
        key_pdf = files["key"]
        combo_pdf = files["combo"]

        if combo_pdf:
            test_pdf = combo_pdf
            key_pdf = combo_pdf

        if not test_pdf and not key_pdf:
            continue
        if not test_pdf:
            print(f"{exam_name}: skipped, no test PDF found")
            continue
        if not key_pdf:
            print(f"{exam_name}: warning, no key PDF found; answers will be blank")

        try:
            parsed, inserted = ingest_exam_pair(exam_name, test_pdf, key_pdf)
            total_parsed += parsed
            total_inserted += inserted
            print(
                f"{exam_name}: parsed {parsed}, inserted {inserted}, "
                f"test={os.path.basename(test_pdf)}, key={os.path.basename(key_pdf) if key_pdf else 'NONE'}"
            )
        except Exception as e:
            print(f"{exam_name}: ERROR -> {e}")

    print(f"\nFinished. Parsed {total_parsed} questions across all paired exams.")
    print(f"New rows inserted: {total_inserted}")


def ingest_safe_archive(source_path, rebuild=True):
    overrides = load_archive_overrides()
    entries = list(iter_archive_entries(source_path))
    report = build_archive_report(entries, overrides)
    write_archive_report(report)
    print_archive_report(report)

    safe_groups = build_safe_archive_exam_groups(report)
    if not safe_groups:
        print("\nNo safe archive exam sets were found to ingest.")
        return

    if rebuild:
        clear_questions_table()

    total_parsed = 0
    total_inserted = 0

    print(f"\nIngesting {len(safe_groups)} safe exam set(s) from archive...")
    for exam_name, files in sorted(safe_groups.items()):
        test_entry = files["combo"] or files["test"]
        key_entry = files["combo"] or files["key"]

        test_pdf = materialize_archive_file(source_path, test_entry)
        key_pdf = materialize_archive_file(source_path, key_entry) if key_entry else None

        try:
            parsed, inserted = ingest_exam_pair(
                exam_name,
                test_pdf,
                key_pdf,
                year=files["year"],
                level=files["level"],
                source_test_id=test_pdf.replace("\\", "/"),
                source_key_id=key_pdf.replace("\\", "/") if key_pdf else None,
            )
            total_parsed += parsed
            total_inserted += inserted
            print(
                f"{exam_name}: parsed {parsed}, inserted {inserted}, "
                f"test={os.path.basename(test_pdf)}, key={os.path.basename(key_pdf) if key_pdf else 'NONE'}"
            )
        except Exception as exc:
            print(f"{exam_name}: ERROR -> {exc}")

    print(f"\nFinished archive ingest. Parsed {total_parsed} questions across {len(safe_groups)} exam sets.")
    print(f"Rows inserted/updated: {total_inserted}")


def clean_text_for_display(text):
    if not text:
        return ""

    text = text.replace("\r", "\n")
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def make_preview(text, max_len=110):
    text = clean_text_for_display(text).replace("\n", " ")
    if len(text) > max_len:
        return text[:max_len - 3] + "..."
    return text


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


def row_matches_terms(row, terms):
    question_text = str(row[5] or "")
    code_block = str(row[6] or "")
    choices = str(row[7] or "")
    answer = str(row[8] or "")
    shared_context = str(row[15] or "") if len(row) > 15 else ""
    tags = extract_search_tags(question_text, code_block, shared_context)
    searchable_text = build_search_blob(question_text, code_block, choices, answer, shared_context)

    keyword = (terms[0] if terms else "").strip().lower()
    if not keyword:
        return False

    direct_hit = contains_search_term(searchable_text, keyword)
    tag_hit = keyword in tags
    synonym_hits = {
        term.lower()
        for term in terms
        if term.strip() and contains_search_term(searchable_text, term)
    }

    if direct_hit or tag_hit:
        return True

    if keyword in TOPIC_SYNONYMS:
        if keyword in STRICT_TOPIC_MATCHES:
            return len(synonym_hits) >= 2
        return len(synonym_hits) >= 1

    return False


def score_search_match_tuple(row, keyword):
    keyword = (keyword or "").strip().lower()
    if not keyword:
        return None

    expanded_terms = [keyword, *expand_keyword(keyword)]
    question_text = str(row[5] or "")
    code_block = str(row[6] or "")
    choices = str(row[7] or "")
    answer = str(row[8] or "")
    shared_context = str(row[15] or "") if len(row) > 15 else ""
    tags = extract_search_tags(question_text, code_block, shared_context)
    searchable_text = build_search_blob(question_text, code_block, choices, answer, shared_context)

    direct_hit = contains_search_term(searchable_text, keyword)
    tag_hit = keyword in tags
    synonym_hits = []
    for term in expanded_terms[1:]:
        normalized = term.lower()
        if normalized == keyword:
            continue
        if normalized not in synonym_hits and contains_search_term(searchable_text, term):
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

    if direct_hit:
        score += 58
        reasons.append(f'exact "{keyword}" match')

    if tag_hit:
        score += 60 if keyword in {"recursion", "recursive"} else 34
        reasons.append(f"{keyword} tag")

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


def group_words_into_lines(words, y_tol=3):
    lines = []
    current = []

    for word in sorted(words, key=lambda w: (round(w["top"], 1), w["x0"])):
        if not current:
            current = [word]
            continue

        if abs(word["top"] - current[0]["top"]) <= y_tol:
            current.append(word)
        else:
            lines.append(current)
            current = [word]

    if current:
        lines.append(current)

    return lines


def words_to_line_text(line_words):
    line_words = sorted(line_words, key=lambda w: w["x0"])
    return " ".join(w["text"] for w in line_words).strip()


def extract_page_lines_by_column(page, split_x=280):
    words = page.extract_words(
        x_tolerance=2,
        y_tolerance=2,
        keep_blank_chars=False,
        use_text_flow=False
    )

    left_words = [w for w in words if w["x0"] < split_x]
    right_words = [w for w in words if w["x0"] >= split_x]

    left_lines = []
    for group in group_words_into_lines(left_words):
        text = words_to_line_text(group)
        if text:
            left_lines.append({"top": min(w["top"] for w in group), "text": text})

    right_lines = []
    for group in group_words_into_lines(right_words):
        text = words_to_line_text(group)
        if text:
            right_lines.append({"top": min(w["top"] for w in group), "text": text})

    return left_lines, right_lines


def extract_questions_layout_aware(file_path: str, split_x=280):
    parsed = []
    question_line_regex = re.compile(r"^\s*Q\s*u\s*e\s*s\s*t\s*i\s*o\s*n\s*(\d+)\b", re.IGNORECASE)

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            left_lines, right_lines = extract_page_lines_by_column(page, split_x=split_x)

            q_starts = []
            for line in left_lines:
                m = question_line_regex.match(line["text"])
                if m:
                    q_starts.append({"qnum": int(m.group(1)), "top": line["top"]})

            if not q_starts:
                continue

            for i, q in enumerate(q_starts):
                qnum = q["qnum"]
                top_start = q["top"]
                top_end = q_starts[i + 1]["top"] if i + 1 < len(q_starts) else page.height
                crop_text = page.within_bbox((0, top_start, page.width, top_end)).extract_text(
                    x_tolerance=1,
                    y_tolerance=2,
                ) or ""

                left_block = [
                    line["text"] for line in left_lines
                    if top_start <= line["top"] < top_end
                ]

                in_range_indices = [
                    idx for idx, line in enumerate(right_lines)
                    if top_start - 5 <= line["top"] < top_end
                ]

                right_block_lines = []
                if in_range_indices:
                    first_idx = in_range_indices[0]
                    last_idx = in_range_indices[-1]

                    while last_idx + 1 < len(right_lines):
                        current_top = right_lines[last_idx]["top"]
                        next_top = right_lines[last_idx + 1]["top"]
                        if next_top - current_top <= 18:
                            last_idx += 1
                        else:
                            break

                    right_block_lines = [right_lines[idx]["text"] for idx in range(first_idx, last_idx + 1)]

                if left_block and question_line_regex.match(left_block[0]):
                    left_block = left_block[1:]

                left_text = "\n".join(left_block).strip()
                right_choice_lines = [line for line in right_block_lines if is_choice_line(line)]
                right_non_choice_lines = [line for line in right_block_lines if not is_choice_line(line)]
                right_prompt_lines = [line for line in right_non_choice_lines if not looks_like_code_line(line)]
                right_code_lines = [line for line in right_non_choice_lines if looks_like_code_line(line)]
                before_choices, choices_part = split_choices(left_text)
                if right_choice_lines:
                    combined_choices = "\n".join(part for part in [choices_part, "\n".join(right_choice_lines)] if part).strip()
                else:
                    combined_choices = choices_part

                dangling_choice_marker = bool(re.search(r'(?i)(?<!\w)[A-E][\.)]\s*$', combined_choices))
                should_salvage_choice_text = dangling_choice_marker or count_inline_choice_markers(combined_choices) < 5
                leaked_prompt_choices = ""
                if should_salvage_choice_text:
                    before_choices, leaked_prompt_choices = split_trailing_choice_leak(before_choices)

                leaked_code_choice = ""
                salvageable_right_prompt_lines = [
                    line for line in right_prompt_lines
                    if line.strip()
                    and line.strip().lower() != "right?"
                    and not re.match(
                        r'(?i)^(?:do\{?|for\s*\(|while\s*\(|if\s*\(|return\b|out\.|[A-Za-z_]\w*\s*(?:\+\+|--|=)|[A-Za-z_]\w*\s*\()',
                        line.strip(),
                    )
                ]

                if dangling_choice_marker:
                    for idx, line in enumerate(list(salvageable_right_prompt_lines)):
                        leaked_code_choice, remainder = split_choice_prefix_from_code_line(line)
                        if leaked_code_choice:
                            salvageable_right_prompt_lines.pop(idx)
                            if remainder:
                                right_code_lines.insert(0, remainder)
                            break

                if dangling_choice_marker and not leaked_code_choice:
                    for idx, line in enumerate(right_code_lines):
                        leaked_code_choice, remainder = split_choice_prefix_from_code_line(line)
                        if leaked_code_choice:
                            right_code_lines[idx] = remainder
                            break

                right_text = "\n".join(right_code_lines).strip()
                dangling_choice_marker = bool(re.search(r'(?i)(?<!\w)[A-E][\.)]\s*$', combined_choices))

                if leaked_prompt_choices or leaked_code_choice or (dangling_choice_marker and salvageable_right_prompt_lines):
                    combined_choices = rebuild_choice_block(
                        combined_choices,
                        leaked_prompt_choices,
                        leaked_code_choice,
                        "\n".join(salvageable_right_prompt_lines) if dangling_choice_marker else "",
                    )
                elif right_prompt_lines:
                    before_choices = "\n".join(part for part in [before_choices, "\n".join(right_prompt_lines)] if part).strip()

                before_choices, leaked_prompt_labels = split_prompt_and_leaked_choice_labels(before_choices)
                if leaked_prompt_labels:
                    combined_choices = rebuild_choice_block("\n".join(leaked_prompt_labels), combined_choices)

                crop_choices = extract_choice_block_from_crop_text(crop_text, qnum)
                compact_crop_choices = rebuild_compact_choice_grid(crop_choices)
                if count_parsed_choice_entries(compact_crop_choices) > count_parsed_choice_entries(combined_choices):
                    combined_choices = compact_crop_choices
                elif count_parsed_choice_entries(crop_choices) > count_parsed_choice_entries(combined_choices):
                    combined_choices = crop_choices

                cleaned_choice_text, leaked_code_from_choices = pull_code_out_of_choices(combined_choices)
                combined_choices = cleaned_choice_text
                if leaked_code_from_choices:
                    right_text = "\n".join(part for part in [right_text, leaked_code_from_choices] if part).strip()

                parsed.append({
                    "question_number": qnum,
                    "question_text": "",
                    "code_block": "",
                    "choices": remove_parser_noise_lines(combined_choices.strip()),
                    "page_number": page.page_number - 1,
                    "top_y": top_start,
                    "bottom_y": top_end
                })
                prompt_text, embedded_code = split_prompt_and_embedded_code(before_choices.strip())
                merged_code = "\n".join(part for part in [embedded_code, right_text.strip()] if part).strip()
                parsed[-1]["question_text"] = remove_parser_noise_lines(prompt_text)
                parsed[-1]["code_block"] = remove_parser_noise_lines(merged_code)

    return parsed


def normalize_filter(value):
    value = value.strip()
    if value.lower() in ("", "blank", "none", "null"):
        return None
    return value


def count_choice_labels(text):
    if not text:
        return 0
    normalized = re.sub(r'(?<!^)(?<!\n)\s+([A-E][\.)]\s+)', r'\n\1', text.strip(), flags=re.IGNORECASE)
    return len(re.findall(r'(?im)^\s*[A-E][\.)]\s+', normalized))


def parse_choice_labels_for_audit(text):
    if not text:
        return []

    from app import parse_choices  # Keep audit behavior aligned with the UI parser.

    return [(choice["letter"], choice["text"]) for choice in parse_choices(text)]


def detect_parse_issues(row):
    issues = []
    question_text = row["question_text"] or ""
    code_block = row["code_block"] or ""
    choices = row["choices"] or ""
    shared_context = row["shared_context"] or ""
    answer = (row["answer"] or "").strip()
    combined = "\n".join(part for part in [question_text, code_block, choices, shared_context] if part)
    lower_combined = combined.lower()
    open_response_answer = bool(answer) and not bool(re.fullmatch(r"[A-ETF]", answer, re.IGNORECASE))

    if "uil computer science" in lower_combined or "written test" in lower_combined:
        issues.append("footer_text_leaked")

    if row["group_type"] == "shared_code":
        if not shared_context.strip():
            issues.append("shared_group_missing_context")
        if code_block_size(shared_context) < 4:
            issues.append("shared_context_short")

    if not answer:
        issues.append("missing_answer")

    parsed_choices = parse_choice_labels_for_audit(choices)
    choice_label_count = len(parsed_choices)
    parsed_choice_labels = [label for label, content in parsed_choices if content]
    expected_short_sets = [
        ["A", "B"],
        ["A", "B", "C"],
    ]

    if choice_label_count == 0:
        if not open_response_answer:
            issues.append("no_choice_labels")
    elif choice_label_count < 5:
        valid_short_choice_set = parsed_choice_labels in expected_short_sets and len(parsed_choice_labels) == choice_label_count
        if not valid_short_choice_set:
            issues.append(f"only_{choice_label_count}_choice_labels")

    if any(not content for _, content in parsed_choices):
        issues.append("empty_choice_text")

    valid_short_choice_set = parsed_choice_labels in expected_short_sets and len(parsed_choice_labels) == choice_label_count

    if re.search(r'(?i)\b[A-E][\.)]\s+\S+\s+[A-E][\.)]\s+', choices) and choice_label_count < 5 and not valid_short_choice_set:
        issues.append("inline_choices_same_line")

    if parsed_choice_labels and any(label != expected for label, expected in zip(parsed_choice_labels, ["A", "B", "C", "D", "E"])):
        issues.append(f"only_{choice_label_count}_choice_labels")

    if question_text.count("(") > question_text.count(")"):
        issues.append("question_unbalanced_parentheses")

    if code_block.count("{") != code_block.count("}"):
        issues.append("code_unbalanced_braces")

    if re.search(r'(?im)^\s*(else|return)\b', code_block) and not re.search(
        r'(?im)^\s*(public|private|protected|class|if|for|while|switch|try)\b',
        code_block,
    ):
        issues.append("code_starts_mid_block")

    searchable_tags = extract_search_tags(question_text, code_block, shared_context)
    if "recursion" in searchable_tags and row["group_type"] == "single" and code_block_size(code_block) >= 4:
        issues.append("recursive_question_not_grouped")

    if len(clean_text_for_display(question_text)) < 20:
        issues.append("question_text_very_short")

    return issues


def audit_database(limit=50):
    audit_conn = sqlite3.connect(DB_FILE)
    audit_conn.row_factory = sqlite3.Row
    rows = audit_conn.execute("""
        SELECT id, exam_name, year, question_number, group_id, group_type,
               question_text, code_block, choices, answer, shared_context
        FROM questions
        ORDER BY year, exam_name, question_number
    """).fetchall()
    audit_conn.close()

    flagged = []
    for row in rows:
        issues = detect_parse_issues(row)
        if issues:
            severity = len(issues)
            preview_source = row["question_text"] or row["code_block"] or row["choices"] or ""
            preview = make_preview(preview_source, max_len=90)
            flagged.append({
                "severity": severity,
                "exam_name": row["exam_name"],
                "year": row["year"],
                "question_number": row["question_number"],
                "group_type": row["group_type"],
                "issues": issues,
                "preview": preview,
            })

    flagged.sort(
        key=lambda item: (
            -item["severity"],
            item["year"] or 0,
            item["exam_name"],
            item["question_number"],
        )
    )

    issue_counts = {}
    for item in flagged:
        for issue in item["issues"]:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1

    print(f"Audit scanned {len(rows)} questions in {DB_FILE}.")
    print(f"Flagged {len(flagged)} question(s).")

    if issue_counts:
        print("\nIssue summary:")
        for issue, count in sorted(issue_counts.items(), key=lambda pair: (-pair[1], pair[0])):
            print(f"  {issue}: {count}")

    if not flagged:
        return

    print(f"\nTop {min(limit, len(flagged))} flagged questions:")
    for item in flagged[:limit]:
        issue_text = ", ".join(item["issues"])
        print(
            f"  {item['year']} | {item['exam_name']} | Q{item['question_number']} "
            f"| {item['group_type']} | {issue_text}"
        )
        print(f"    {item['preview']}")


def export_review_queue(output_path="parse_review_queue.json"):
    audit_conn = sqlite3.connect(DB_FILE)
    audit_conn.row_factory = sqlite3.Row
    rows = audit_conn.execute("""
        SELECT id, source_test_pdf, exam_name, year, level, question_number, page_number,
               top_y, bottom_y, group_id, group_type, question_text, code_block, choices,
               answer, shared_context
        FROM questions
        ORDER BY year, exam_name, question_number
    """).fetchall()
    audit_conn.close()

    overrides = load_question_overrides()
    queue = []
    for row in rows:
        issues = detect_parse_issues(row)
        if not issues:
            continue

        override_key = f"{row['exam_name']}#{row['question_number']}"
        queue.append({
            "id": row["id"],
            "exam_name": row["exam_name"],
            "year": row["year"],
            "level": row["level"],
            "question_number": row["question_number"],
            "page_number": row["page_number"],
            "group_id": row["group_id"] or "",
            "group_type": row["group_type"] or "single",
            "source_test_pdf": row["source_test_pdf"],
            "issues": issues,
            "question_preview": make_preview(row["question_text"] or row["code_block"] or row["choices"] or "", max_len=140),
            "has_manual_override": override_key in overrides,
            "override_key": override_key,
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2)

    print(f"Wrote {len(queue)} flagged question(s) to {output_path}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].lower() == "audit":
        limit = 50
        if len(sys.argv) > 2 and sys.argv[2].isdigit():
            limit = int(sys.argv[2])
        audit_database(limit=limit)
        conn.close()
        raise SystemExit(0)

    if len(sys.argv) > 1 and sys.argv[1].lower() == "review_queue":
        output_path = sys.argv[2] if len(sys.argv) > 2 else "parse_review_queue.json"
        export_review_queue(output_path=output_path)
        conn.close()
        raise SystemExit(0)

    if len(sys.argv) > 2 and sys.argv[1].lower() == "scan_archive":
        source_path = sys.argv[2]
        overrides = load_archive_overrides()
        entries = list(iter_archive_entries(source_path))
        report = build_archive_report(entries, overrides)
        write_archive_report(report)
        print_archive_report(report)
        print("\nWrote archive_scan_report.json")
        conn.close()
        raise SystemExit(0)

    if len(sys.argv) > 2 and sys.argv[1].lower() == "ingest_archive":
        source_path = sys.argv[2]
        rebuild = not (len(sys.argv) > 3 and sys.argv[3].lower() == "append")
        ingest_safe_archive(source_path, rebuild=rebuild)
        conn.close()
        raise SystemExit(0)

    ingest_all_pdfs()

    while True:
        keyword = input("\nEnter a keyword to search (or 'quit'): ").strip()
        if keyword.lower() == "quit":
            break
        if not keyword:
            continue

        year_input = normalize_filter(input("Filter by year (blank for none): ").strip())
        level_input = normalize_filter(input("Filter by level (blank for none): ").strip())
        exam_input = normalize_filter(input("Filter by exam name (blank for none): ").strip())

        year = int(year_input) if year_input and year_input.isdigit() else None
        level = level_input
        exam_name = exam_input

        query = """
        SELECT id, exam_name, year, level, question_number, question_text, code_block, choices, answer, source_test_pdf
        FROM questions
        WHERE 1=1
        """
        params = []

        if year is not None:
            query += " AND year = ?"
            params.append(year)
        if level is not None:
            query += " AND lower(level) LIKE ?"
            params.append(f"%{level.lower()}%")
        if exam_name is not None:
            query += " AND lower(exam_name) LIKE ?"
            params.append(f"%{exam_name.lower()}%")

        query += " ORDER BY year, exam_name, question_number"
        c.execute(query, params)
        all_rows = c.fetchall()
        results = []
        for row in all_rows:
            match = score_search_match_tuple(row, keyword)
            if match:
                results.append((row, match))

        results.sort(
            key=lambda item: (
                -item[1]["score"],
                -(item[0][2] or 0),
                str(item[0][1] or ""),
                item[0][4] or 0,
            )
        )

        if not results:
            print("No questions found.")
            continue

        print(f"\nExpanded search terms: {[keyword, *expand_keyword(keyword)]}")
        print(f"Found {len(results)} matching questions for '{keyword}':\n")

        for i, (row, match) in enumerate(results, start=1):
            db_id, exam_name, year, level, qnum, qtext, code_block, choices, answer, source_test_pdf = row
            preview = make_preview(qtext if qtext else code_block)
            print(
                f"[{i}] {exam_name} | {year} | {level} | Q{qnum} "
                f"| {match['confidence']} {match['score']}"
                f" | {preview}"
            )

    conn.close()
