import os
import sqlite3
import unittest

import app


class AccountWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.old_db_file = app.DB_FILE
        os.makedirs(".tmp", exist_ok=True)
        self.db_file = os.path.join(".tmp", "test_account_workflow.db")
        if os.path.exists(self.db_file):
            os.remove(self.db_file)
        app.DB_FILE = self.db_file

        conn = sqlite3.connect(self.db_file)
        conn.execute("""
            CREATE TABLE questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_test_pdf TEXT,
                source_key_pdf TEXT,
                exam_name TEXT,
                year INTEGER,
                level TEXT,
                question_number INTEGER,
                page_number INTEGER,
                top_y REAL,
                bottom_y REAL,
                question_text TEXT,
                code_block TEXT,
                choices TEXT,
                answer TEXT,
                group_id TEXT,
                group_type TEXT,
                shared_context TEXT
            )
        """)
        conn.execute("""
            INSERT INTO questions
            (source_test_pdf, exam_name, year, level, question_number, question_text, code_block,
             choices, answer, group_id, group_type, shared_context)
            VALUES ('_archive_cache/Written/2026/Inv A/sample.pdf', 'sample_exam', 2026, 'invitational', 1, 'What is 1 + 1?',
                    '', 'A) 1 B) 2 C) 3 D) 4 E) 5', 'B', '', 'single', '')
        """)
        conn.execute("""
            INSERT INTO questions
            (source_test_pdf, exam_name, year, level, question_number, question_text, code_block,
             choices, answer, group_id, group_type, shared_context)
            VALUES ('_archive_cache/Written/2025/Stacey Tests/test.pdf', '2025_stacey_tests_test_02', 2025, 'invitational', 1,
                    'What is 2 + 2?', '', 'A) 1 B) 2 C) 3 D) 4 E) 5', 'D', '', 'single', '')
        """)
        conn.execute("""
            INSERT INTO questions
            (source_test_pdf, exam_name, year, level, question_number, question_text, code_block,
             choices, answer, group_id, group_type, shared_context)
            VALUES ('_archive_cache/Written/2025/District/official.pdf', '2025_district', 2025, 'district', 1,
                    'What is 3 + 3?', '', 'A) 4 B) 5 C) 6 D) 7 E) 8', 'C', '', 'single', '')
        """)
        conn.execute("""
            INSERT INTO questions
            (source_test_pdf, exam_name, year, level, question_number, page_number, top_y, bottom_y,
             question_text, code_block, choices, answer, group_id, group_type, shared_context)
            VALUES ('_archive_cache/Written/2025/District/official.pdf', '2025_district', 2025, 'district', 2,
                    1, 10, 80, 'What is printed by line #1?', 'int x = 1;', 'A) 1 B) 2', 'A', '', 'single', '')
        """)
        conn.execute("""
            INSERT INTO questions
            (source_test_pdf, exam_name, year, level, question_number, page_number, top_y, bottom_y,
             question_text, code_block, choices, answer, group_id, group_type, shared_context)
            VALUES ('_archive_cache/Written/2025/District/official.pdf', '2025_district', 2025, 'district', 3,
                    1, 80, 150, 'What is printed by line #2?', 'out.println(x); //line #2', 'A) 1 B) 2', 'A', '', 'single', '')
        """)
        conn.execute("""
            INSERT INTO questions
            (source_test_pdf, exam_name, year, level, question_number, page_number, top_y, bottom_y,
             question_text, code_block, choices, answer, group_id, group_type, shared_context)
            VALUES ('_archive_cache/Written/2025/District/official.pdf', '2025_district', 2025, 'district', 33,
                    9, 10, 80, '33. E This is an explanation for the answer key, not a question.', '', '', 'E', '', 'single', '')
        """)
        conn.commit()
        conn.close()
        app.init_app_tables()
        self.client = app.app.test_client()

    def tearDown(self):
        app.DB_FILE = self.old_db_file
        if os.path.exists(self.db_file):
            os.remove(self.db_file)

    def test_report_issue_page_collects_feedback(self):
        old_feedback_file = app.PARSE_FEEDBACK_FILE
        feedback_file = os.path.join(".tmp", "test_parse_feedback.jsonl")
        if os.path.exists(feedback_file):
            os.remove(feedback_file)
        app.PARSE_FEEDBACK_FILE = feedback_file
        try:
            response = self.client.get("/report/1?return_to=/%3Fkeyword%3Drecursion")
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"What looks wrong?", response.data)

            response = self.client.post(
                "/report/1",
                data={
                    "return_to": "/?keyword=recursion",
                    "issue_type": "search_tag",
                    "detail": "This question should not appear for recursion.",
                    "reporter_context": "prototype tester",
                },
                follow_redirects=False,
            )
            self.assertEqual(response.status_code, 302)
            self.assertTrue(os.path.exists(feedback_file))
            with open(feedback_file, encoding="utf-8") as f:
                saved = f.read()
            self.assertIn("search_tag", saved)
            self.assertIn("prototype tester", saved)
        finally:
            app.PARSE_FEEDBACK_FILE = old_feedback_file
            if os.path.exists(feedback_file):
                os.remove(feedback_file)

    def test_user_can_register_save_attempt_and_view_dashboard(self):
        response = self.client.post(
            "/register",
            data={"username": "student1", "password": "password123"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

        payload = {
            "exam_key": "2026|invitational|sample_exam",
            "year": 2026,
            "level": "invitational",
            "exam_name": "sample_exam",
            "total_questions": 1,
            "questions": [
                {
                    "question_id": 1,
                    "question_number": 1,
                    "response": "B",
                    "correct": True,
                }
            ],
        }
        response = self.client.post("/api/test_attempts", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])

        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"sample_exam", response.data)

    def test_dashboard_missed_topic_tags_link_to_search(self):
        response = self.client.post(
            "/register",
            data={"username": "student2", "password": "password123"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

        conn = sqlite3.connect(self.db_file)
        conn.execute(
            "UPDATE questions SET code_block = ? WHERE id = 3",
            ("double value = Math.sqrt(36);",),
        )
        conn.commit()
        conn.close()

        payload = {
            "exam_key": "2026|invitational|sample_exam",
            "year": 2026,
            "level": "invitational",
            "exam_name": "sample_exam",
            "total_questions": 1,
            "questions": [
                {
                    "question_id": 3,
                    "question_number": 1,
                    "response": "A",
                    "correct": False,
                }
            ],
        }
        response = self.client.post("/api/test_attempts", json=payload)
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'class="tag tag-link"', response.data)
        self.assertIn(b"/?keyword=math", response.data)

    def test_logged_in_user_can_write_shared_question_explanation(self):
        response = self.client.post(
            "/register",
            data={"username": "teacher1", "password": "password123"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.post(
            "/explanation/1",
            data={
                "return_to": "/question/1",
                "explanation": "Add before multiplying: 1 + 1 equals 2.",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

        conn = sqlite3.connect(self.db_file)
        saved = conn.execute(
            "SELECT explanation FROM question_explanations WHERE question_id = 1"
        ).fetchone()
        conn.close()
        self.assertEqual(saved[0], "Add before multiplying: 1 + 1 equals 2.")

        response = self.client.get("/question/1")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Team Explanation", response.data)
        self.assertIn(b"Add before multiplying", response.data)

    def test_exam_catalog_splits_uil_and_other_collections(self):
        catalog = app.fetch_exam_catalog()
        by_exam = {item["exam_name"]: item for item in catalog}

        self.assertEqual(by_exam["2025_district"]["collection"], "UIL")
        self.assertEqual(by_exam["2025_district"]["question_count"], 3)
        self.assertEqual(by_exam["2025_stacey_tests_test_02"]["collection"], "Other")

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"UIL Official", response.data)
        self.assertIn(b"Other", response.data)

    def test_context_dependent_single_question_uses_neighbor_crop_bounds(self):
        conn = app.get_connection()
        row = conn.execute("SELECT * FROM questions WHERE exam_name = '2025_district' AND question_number = 3").fetchone()
        bounds = app.infer_neighbor_context_bounds(conn, row)
        conn.close()

        self.assertEqual(bounds, (10.0, 150.0, 2))

    def test_explanation_rows_are_excluded_from_test_questions_and_search(self):
        questions = app.fetch_test_questions(2025, "district", "2025_district")
        self.assertNotIn(33, [question["question_number"] for question in questions])

        response = self.client.get("/?keyword=explanation")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"Q33", response.data)

    def test_question_page_marks_missing_answer_as_unavailable(self):
        conn = sqlite3.connect(self.db_file)
        conn.execute("UPDATE questions SET answer = '' WHERE id = 1")
        conn.commit()
        conn.close()

        response = self.client.get("/question/1")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Answer key unavailable", response.data)


if __name__ == "__main__":
    unittest.main()
