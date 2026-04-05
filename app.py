from flask import Flask, render_template, request, send_file, redirect, url_for
import sqlite3
import re
import pdfplumber
import io
import os

app = Flask(__name__)
DB_FILE = "uil_cs_questions_v2.db"

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


def remove_noise_lines(text):
    if not text:
        return ""

    noise_patterns = [
        r"^written test",
        r"^test\s+[–-]",
        r"^uil computer science\b",
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


def resolve_pdf_path(stored_path):
    if not stored_path:
        return ""
    if os.path.exists(stored_path):
        return stored_path

    candidate = os.path.join("data", stored_path)
    if os.path.exists(candidate):
        return candidate

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


def clean_text_for_display(text):
    if not text:
        return ""

    text = remove_noise_lines(text)
    text = text.replace("\r", "\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


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


def explode_inline_choice_labels(text):
    if not text:
        return ""

    return re.sub(
        r'(?<!^)(?<!\n)\s+((?:[A-E]|TRUE|FALSE|T|F)[\.)]\s+)',
        r'\n\1',
        text.strip(),
        flags=re.IGNORECASE,
    )


def trim_to_first_choice_label(text):
    if not text:
        return ""

    lines = explode_inline_choice_labels(text).replace("\r", "\n").splitlines()
    for idx, line in enumerate(lines):
        if re.match(r"^\s*(?:[A-E]|TRUE|FALSE|T|F)[\.)]\s+", line, re.IGNORECASE):
            return "\n".join(lines[idx:]).strip()
    return text.strip()


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


def parse_choices(choices_text):
    if not choices_text:
        return []

    parsed = []
    current_label = None
    current_lines = []

    for raw_line in trim_to_first_choice_label(choices_text).replace("\r", "\n").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = re.match(r"^\s*((?:[A-E]|TRUE|FALSE|T|F))[\.)]\s*(.*)$", line, re.IGNORECASE)
        if match:
            if current_label is not None:
                content = clean_text_for_display("\n".join(current_lines))
                parsed.append({"letter": current_label, "text": content})

            label = match.group(1).strip().upper()
            content_start = match.group(2).strip()

            if label == "TRUE":
                label = "T"
            elif label == "FALSE":
                label = "F"

            current_label = label
            current_lines = [content_start] if content_start else []
        elif current_label is not None:
            current_lines.append(line)

    if current_label is not None:
        content = clean_text_for_display("\n".join(current_lines))
        parsed.append({"letter": current_label, "text": content})

    return parsed


def normalize_answer(answer_text):
    raw = clean_text_for_display(answer_text or "").upper().strip()

    if not raw:
        return ""
    if raw.startswith("TRUE"):
        return "T"
    if raw.startswith("FALSE"):
        return "F"

    m = re.search(r'\b([A-Z])\b', raw)
    if m:
        return m.group(1)
    m = re.search(r'([A-Z])', raw)
    return m.group(1) if m else raw


def prepare_question(row):
    display_question = row["question_text"] or ""
    display_code = row["code_block"] or ""
    display_choices = row["choices"] or ""
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

    final_choices_text = cleaned_choices.strip()

    return {
        "id": row["id"],
        "exam_name": row["exam_name"],
        "year": row["year"],
        "level": row["level"],
        "question_number": row["question_number"],
        "question_text": clean_text_for_display(cleaned_question),
        "code_block": clean_text_for_display("\n".join(merged_code)),
        "choices": clean_text_for_display(final_choices_text),
        "parsed_choices": parse_choices(final_choices_text),
        "answer": normalize_answer(row["answer"]),
        "group_id": row["group_id"] or "",
        "group_type": row["group_type"] or "single"
    }


def row_matches_terms(row, terms):
    question_text = str(row["question_text"] or "")
    code_block = str(row["code_block"] or "")
    choices = str(row["choices"] or "")
    answer = str(row["answer"] or "")
    shared_context = str(row["shared_context"] or "")
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


def score_search_match(row, keyword):
    keyword = (keyword or "").strip().lower()
    if not keyword:
        return None

    expanded_terms = [keyword, *expand_keyword(keyword)]
    question_text = str(row["question_text"] or "")
    code_block = str(row["code_block"] or "")
    choices = str(row["choices"] or "")
    answer = str(row["answer"] or "")
    shared_context = str(row["shared_context"] or "")
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
    question_pattern = re.compile(rf"(?im)\bquestion\s*{qnum}\b")
    compact_pattern = re.compile(rf"(?im)\bquestion\s*{qnum}(?:\D|$)")
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

    start_pattern = re.compile(rf"(?i)\bquestion\s*{int(question_number)}\b")
    end_pattern = None
    if end_question_number is not None:
        end_pattern = re.compile(rf"(?i)\bquestion\s*{int(end_question_number)}\b")

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
                    .startswith(("uil computer science", "written test", "test -", "test –"))
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
        safe_bottom = min(page.height, bottom)

        if safe_bottom >= page.height - 1:
            meaningful_bottom = max(
                (
                    line["bottom"]
                    for line in extract_page_lines(page)
                    if not remove_noise_lines(line["text"])
                        .lower()
                        .startswith(("uil computer science", "written test", "test -", "test –"))
                ),
                default=safe_bottom,
            )
            safe_bottom = min(safe_bottom, meaningful_bottom + 10)

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
        return img_bytes


@app.route("/")
def index():
    keyword = request.args.get("keyword", "").strip()
    year = request.args.get("year", "").strip()
    level = request.args.get("level", "").strip()
    exam_name = request.args.get("exam_name", "").strip()

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
        exam_name=exam_name
    )


@app.route("/question_image/<int:question_id>")
def question_image(question_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()

    if not row:
        conn.close()
        return "Not found", 404

    end_question_number = infer_visual_end_question_number(conn, row)
    conn.close()

    pdf_path = resolve_pdf_path(row["source_test_pdf"])
    img_bytes = render_pdf_crop(
        pdf_path,
        row["page_number"],
        row["top_y"],
        row["bottom_y"],
        question_number=row["question_number"],
        question_text=row["question_text"] or "",
        end_question_number=end_question_number,
    )
    return send_file(img_bytes, mimetype="image/png")


@app.route("/group_image/<group_id>")
def group_image(group_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM questions
        WHERE group_id = ?
        ORDER BY question_number
    """, (group_id,)).fetchall()
    if not rows:
        conn.close()
        return "Group not found", 404

    first = rows[0]
    top = min(row["top_y"] for row in rows)
    bottom = max(row["bottom_y"] for row in rows)
    pdf_path = resolve_pdf_path(first["source_test_pdf"])
    end_question_number = infer_visual_end_question_number(conn, rows[-1]) if rows else None
    conn.close()

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

    if row["group_type"] and row["group_type"] != "single" and row["group_id"]:
        return redirect(url_for("group_detail", group_id=row["group_id"]))

    question = prepare_question(row)
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

    if not rows:
        return "Group not found", 404

    prepared_questions = [prepare_question(row) for row in rows]

    return render_template(
        "group.html",
        group_id=group_id,
        group_type=rows[0]["group_type"] or "shared_code",
        shared_context=clean_text_for_display(rows[0]["shared_context"] or ""),
        questions=prepared_questions
    )


if __name__ == "__main__":
    app.run(debug=True)
