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
            (exam_name, year, level, question_number, question_text, code_block,
             choices, answer, group_id, group_type, shared_context)
            VALUES ('sample_exam', 2026, 'invitational', 1, 'What is 1 + 1?',
                    '', 'A) 1 B) 2 C) 3 D) 4 E) 5', 'B', '', 'single', '')
        """)
        conn.commit()
        conn.close()
        app.init_app_tables()
        self.client = app.app.test_client()

    def tearDown(self):
        app.DB_FILE = self.old_db_file
        if os.path.exists(self.db_file):
            os.remove(self.db_file)

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


if __name__ == "__main__":
    unittest.main()
