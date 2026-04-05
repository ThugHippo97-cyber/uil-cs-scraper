import os
import unittest

import main
import app


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


class ParserRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._cache = {}

    @classmethod
    def load_grouped_questions(cls, filename):
        if filename not in cls._cache:
            path = os.path.join(DATA_DIR, filename)
            parsed = main.parse_test_pdf(path)
            grouped = main.assign_groups(
                parsed,
                main.normalize_exam_name(filename),
                main.infer_year(filename),
            )
            cls._cache[filename] = {
                question["question_number"]: question
                for question in grouped
            }
        return cls._cache[filename]

    def test_2017_invitational_a_questions_22_to_24_stay_in_one_shared_group(self):
        questions = self.load_grouped_questions("2017_invitationalA_test.pdf.pdf")

        q22 = questions[22]
        q23 = questions[23]
        q24 = questions[24]

        expected_group_id = "2017_2017_invitationala_p6_shared_22_24"

        self.assertEqual(q22["group_id"], expected_group_id)
        self.assertEqual(q23["group_id"], expected_group_id)
        self.assertEqual(q24["group_id"], expected_group_id)
        self.assertEqual(q24["group_type"], "shared_code")

        shared_context = q24["shared_context"]
        self.assertIn("// Use to answer questions 22, 23 and", shared_context)
        self.assertIn("public class A {", shared_context)
        self.assertIn("public class B extends A {", shared_context)
        self.assertIn("public int subtract(){", shared_context)
        self.assertTrue(shared_context.strip().endswith("}"))

    def test_2017_invitational_a_question_23_keeps_full_client_code_in_prompt(self):
        questions = self.load_grouped_questions("2017_invitationalA_test.pdf.pdf")
        q23 = questions[23]

        self.assertIn('out.print((b1 instanceof A)+" ");', q23["question_text"])
        self.assertIn('out.print((b1 instanceof B)+" ");', q23["question_text"])
        self.assertIn('out.print((b2 instanceof A)+" ");', q23["question_text"])
        self.assertIn('out.print((b2 instanceof B));', q23["question_text"])

        self.assertTrue(q23["choices"].startswith("A) true true true true"))
        self.assertNotIn('A)+" ");', q23["choices"])

    def test_2017_invitational_a_output_questions_do_not_false_group(self):
        questions = self.load_grouped_questions("2017_invitationalA_test.pdf.pdf")

        self.assertEqual(questions[25]["group_type"], "single")
        self.assertEqual(questions[26]["group_type"], "single")

    def test_2017_invitational_a_question_9_keeps_all_answer_choices(self):
        questions = self.load_grouped_questions("2017_invitationalA_test.pdf.pdf")
        q9 = questions[9]

        self.assertEqual(
            q9["code_block"],
            'int x=1;\nwhile(x<7){\nout.print("*");\nx++;\n}',
        )
        self.assertIn("A) None", q9["choices"])
        self.assertIn("B) 5", q9["choices"])
        self.assertIn("C) 6", q9["choices"])
        self.assertIn("D) 7", q9["choices"])
        self.assertIn("E) 8", q9["choices"])

    def test_2017_invitational_b_questions_16_and_17_share_linked_list_context(self):
        questions = self.load_grouped_questions("2017_invitationalB_test.pdf.pdf")

        q16 = questions[16]
        q17 = questions[17]

        self.assertEqual(q16["group_id"], q17["group_id"])
        self.assertEqual(q16["group_type"], "shared_code")
        self.assertIn("LinkedList<Integer>();", q16["shared_context"])
        self.assertIn('out.print(list.get(4)+" ");', q17["shared_context"])

    def test_2025_invitational_a_questions_24_to_27_share_class_context(self):
        questions = self.load_grouped_questions("2025_invitationalA_test.pdf.pdf")

        expected_group_id = "2025_2025_invitationala_p6_shared_24_27"
        for qnum in (24, 25, 26, 27):
            self.assertEqual(questions[qnum]["group_id"], expected_group_id)
            self.assertEqual(questions[qnum]["group_type"], "shared_code")

        shared_context = questions[27]["shared_context"]
        self.assertIn("class A{", shared_context)
        self.assertIn("class B extends A{", shared_context)
        self.assertIn("///////////client code////////////", shared_context)

    def test_2024_invitational_a_recursion_questions_share_method_context(self):
        questions = self.load_grouped_questions("2024_invitationalA_test.pdf.pdf")

        expected_group_id = "2024_2024_invitationala_p6_shared_25_27"
        for qnum in (25, 26, 27):
            self.assertEqual(questions[qnum]["group_id"], expected_group_id)
            self.assertEqual(questions[qnum]["group_type"], "shared_code")

        shared_context = questions[25]["shared_context"]
        self.assertIn("public static int Park(int A, int B)", shared_context)
        self.assertIn("return Park(A-1, B) + A;", shared_context)
        self.assertIn("return Park(A, B-2) + B;", shared_context)

    def test_2024_invitational_a_recursion_inline_choices_render_separately(self):
        questions = self.load_grouped_questions("2024_invitationalA_test.pdf.pdf")
        prepared = app.prepare_question({
            "id": 0,
            "exam_name": "2024_invitationala",
            "year": 2024,
            "level": "invitational",
            "question_number": 25,
            "question_text": questions[25]["question_text"],
            "code_block": questions[25]["code_block"],
            "choices": questions[25]["choices"],
            "answer": "A",
            "group_id": questions[25]["group_id"],
            "group_type": questions[25]["group_type"],
            "shared_context": questions[25]["shared_context"],
        })

        self.assertEqual(
            prepared["parsed_choices"],
            [
                {"letter": "A", "text": "3"},
                {"letter": "B", "text": "4"},
                {"letter": "C", "text": "5"},
                {"letter": "D", "text": "6"},
                {"letter": "E", "text": "7"},
            ],
        )

    def test_2017_invitational_a_question_9_inline_choices_render_separately(self):
        questions = self.load_grouped_questions("2017_invitationalA_test.pdf.pdf")
        prepared = app.prepare_question({
            "id": 0,
            "exam_name": "2017_invitationala",
            "year": 2017,
            "level": "invitational",
            "question_number": 9,
            "question_text": questions[9]["question_text"],
            "code_block": questions[9]["code_block"],
            "choices": questions[9]["choices"],
            "answer": "C",
            "group_id": questions[9]["group_id"],
            "group_type": questions[9]["group_type"],
            "shared_context": questions[9]["shared_context"],
        })

        self.assertEqual(
            prepared["parsed_choices"],
            [
                {"letter": "A", "text": "None"},
                {"letter": "B", "text": "5"},
                {"letter": "C", "text": "6"},
                {"letter": "D", "text": "7"},
                {"letter": "E", "text": "8"},
            ],
        )

    def test_method_reference_questions_can_share_following_method_definition(self):
        parsed = [
            {
                "question_number": 20,
                "page_number": 7,
                "top_y": 70,
                "bottom_y": 180,
                "question_text": "What is returned when method go(-3) is called?",
                "code_block": "",
                "choices": "A. 0",
                "group_id": "temp20",
                "group_type": "single",
                "shared_context": "",
            },
            {
                "question_number": 21,
                "page_number": 7,
                "top_y": 180,
                "bottom_y": 290,
                "question_text": "How many times is the method go() called?",
                "code_block": "public int go(int num)\n{\nif(num <= 0)\nreturn num;\nreturn go(num - 1);\n}",
                "choices": "A. 1",
                "group_id": "temp21",
                "group_type": "single",
                "shared_context": "",
            },
            {
                "question_number": 22,
                "page_number": 7,
                "top_y": 290,
                "bottom_y": 390,
                "question_text": "How many times is the method go() called when go(21) is called?",
                "code_block": "",
                "choices": "A. 1",
                "group_id": "temp22",
                "group_type": "single",
                "shared_context": "",
            },
        ]

        grouped = main.apply_method_reference_groups(parsed, "2024_sample", 2024)

        self.assertEqual(grouped[0]["group_type"], "shared_code")
        self.assertEqual(grouped[0]["group_id"], grouped[1]["group_id"])
        self.assertEqual(grouped[1]["group_id"], grouped[2]["group_id"])
        self.assertIn("public int go(int num)", grouped[0]["shared_context"])
        self.assertIn("return go(num - 1);", grouped[2]["shared_context"])


if __name__ == "__main__":
    unittest.main()
