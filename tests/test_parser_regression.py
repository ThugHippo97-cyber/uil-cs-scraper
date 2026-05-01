import os
import unittest

import main
import app


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
ARCHIVE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "_archive_cache",
    "Written-20260405T175554Z-3-001",
    "Written",
)


class ParserRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._cache = {}
        cls._archive_cache = {}

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

    @classmethod
    def load_archive_questions(cls, relative_path):
        if relative_path not in cls._archive_cache:
            path = os.path.join(ARCHIVE_DIR, *relative_path)
            if not os.path.exists(path):
                raise unittest.SkipTest(f"Archive fixture missing: {path}")
            parsed = main.parse_test_pdf(path)
            cls._archive_cache[relative_path] = {
                question["question_number"]: question
                for question in parsed
            }
        return cls._archive_cache[relative_path]

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

    def test_line_marker_questions_share_prior_code_context(self):
        parsed = [
            {
                "question_number": 16,
                "page_number": 5,
                "top_y": 100,
                "bottom_y": 220,
                "question_text": "What is output by line //1 in the code to the right?",
                "code_block": "Map<Integer, Character> m;\nm = new HashMap<>();\nm.put(22, 'Z');\nm.put(7, 'w');",
                "choices": "A) w B) r C) e D) Z E) error",
            },
            {
                "question_number": 17,
                "page_number": 5,
                "top_y": 220,
                "bottom_y": 340,
                "question_text": "What is output by line //2 in the code to the right?",
                "code_block": "m.put(7,(char)101); //1\nout.println(m.size()); //2",
                "choices": "A) 4 B) 2 C) 3 D) 5 E) error",
            },
        ]

        grouped = main.assign_groups(parsed, "sample", 2026)

        self.assertEqual(grouped[0]["group_id"], grouped[1]["group_id"])
        self.assertEqual(grouped[0]["group_type"], "shared_code")
        self.assertIn("Map<Integer, Character> m;", grouped[0]["shared_context"])
        self.assertIn("out.println(m.size()); //2", grouped[1]["shared_context"])

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

    def test_2025_invitational_a_questions_35_to_38_share_data_struct_context(self):
        questions = self.load_grouped_questions("2025_invitationalA_test.pdf.pdf")

        expected_group_id = "2025_2025_invitationala_p8_shared_35_38"
        for qnum in (35, 36, 37, 38):
            self.assertEqual(questions[qnum]["group_id"], expected_group_id)
            self.assertEqual(questions[qnum]["group_type"], "shared_code")

        shared_context = questions[38]["shared_context"]
        self.assertIn("class DataStruct", shared_context)
        self.assertIn("public T peek()", shared_context)
        self.assertIn("public T pop()", shared_context)
        self.assertIn("public T push(T data)", shared_context)

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

    def test_choice_text_with_embedded_letter_references_does_not_split_into_fake_choices(self):
        prepared = app.prepare_question({
            "id": 0,
            "exam_name": "2025_invitationala",
            "year": 2025,
            "level": "invitational",
            "question_number": 22,
            "question_text": "Which choice is correct?",
            "code_block": "",
            "choices": "A. option one B. option two C. option three D. A. and C. E. A. and B.",
            "answer": "D",
            "group_id": "",
            "group_type": "single",
            "shared_context": "",
        })

        self.assertEqual(
            prepared["parsed_choices"],
            [
                {"letter": "A", "text": "option one"},
                {"letter": "B", "text": "option two"},
                {"letter": "C", "text": "option three"},
                {"letter": "D", "text": "A. and C."},
                {"letter": "E", "text": "A. and B."},
            ],
        )

    def test_compact_choice_grid_with_values_on_following_lines_parses_separately(self):
        parsed = app.parse_choices("A) B) C)\n3 2 5\nD) E)\n6 1")

        self.assertEqual(
            parsed,
            [
                {"letter": "A", "text": "3"},
                {"letter": "B", "text": "2"},
                {"letter": "C", "text": "5"},
                {"letter": "D", "text": "6"},
                {"letter": "E", "text": "1"},
            ],
        )

    def test_sparse_choice_labels_can_still_parse_later_answer(self):
        parsed = app.parse_choices("C. bit class package\nE. throw final")

        self.assertEqual(
            parsed,
            [
                {"letter": "C", "text": "bit class package"},
                {"letter": "E", "text": "throw final"},
            ],
        )

    def test_unlabeled_five_line_choices_are_mapped_to_a_through_e(self):
        parsed = app.parse_choices("Queue\nStack\nLinked List\nTree\nHashMap")

        self.assertEqual(
            parsed,
            [
                {"letter": "A", "text": "Queue"},
                {"letter": "B", "text": "Stack"},
                {"letter": "C", "text": "Linked List"},
                {"letter": "D", "text": "Tree"},
                {"letter": "E", "text": "HashMap"},
            ],
        )

    def test_unlabeled_single_line_choices_with_delimiters_are_mapped(self):
        parsed = app.parse_choices("Queue | Stack | Linked List | Tree | HashMap")

        self.assertEqual(
            parsed,
            [
                {"letter": "A", "text": "Queue"},
                {"letter": "B", "text": "Stack"},
                {"letter": "C", "text": "Linked List"},
                {"letter": "D", "text": "Tree"},
                {"letter": "E", "text": "HashMap"},
            ],
        )

    def test_adjacent_empty_visual_choice_labels_are_preserved(self):
        parsed = app.parse_choices("A) B) C)\nD) A and C\nE) A, B and C")

        self.assertEqual([choice["letter"] for choice in parsed], ["A", "B", "C", "D", "E"])
        self.assertEqual(parsed[3]["text"], "A and C")

    def test_ocr_variant_choice_labels_are_normalized(self):
        parsed = app.parse_choices("A) 20 B) 24 €) 25 OD) 30 E) 32")

        self.assertEqual(
            parsed,
            [
                {"letter": "A", "text": "20"},
                {"letter": "B", "text": "24"},
                {"letter": "C", "text": "25"},
                {"letter": "D", "text": "30"},
                {"letter": "E", "text": "32"},
            ],
        )

    def test_answer_sanity_flags_non_choice_key_for_choice_question(self):
        issues = main.evaluate_answer_sanity(
            "What is the output?",
            "A. 1\nB. 2\nC. 3\nD. 4\nE. 5",
            "merge",
        )

        self.assertIn("choice_question_non_choice_answer", issues)

    def test_answer_sanity_flags_letter_key_not_in_available_labels(self):
        issues = main.evaluate_answer_sanity(
            "True/False question",
            "T. True\nF. False",
            "A",
        )

        self.assertIn("answer_not_in_parsed_choices", issues)

    def test_prepare_question_keeps_valid_short_choices_over_noisy_crop_recovery(self):
        original = app.extract_question_crop_text
        try:
            app.extract_question_crop_text = lambda row: (
                "Question 4.\nA) prior\nB) prior\nC) prior\nD) prior\nE) prior\n"
                "Question 5.\nA) true B) false\nQuestion 6."
            )
            prepared = app.prepare_question({
                "id": 0,
                "exam_name": "2018_invitationalb",
                "year": 2018,
                "level": "invitational",
                "question_number": 5,
                "question_text": "What is the output?",
                "code_block": "out.print(flag);",
                "choices": "A) true B) false",
                "answer": "A",
                "group_id": "",
                "group_type": "single",
                "shared_context": "",
                "source_test_pdf": "",
                "page_number": 0,
                "top_y": 0,
                "bottom_y": 0,
            })
        finally:
            app.extract_question_crop_text = original

        self.assertEqual(
            prepared["parsed_choices"],
            [
                {"letter": "A", "text": "true"},
                {"letter": "B", "text": "false"},
            ],
        )

    def test_prepare_question_recovers_missing_trailing_choice_from_code_prefix(self):
        prepared = app.prepare_question({
            "id": 0,
            "exam_name": "2025_stacey_tests_test_11",
            "year": 2025,
            "level": "invitational",
            "question_number": 9,
            "question_text": "What is the output by the code to the right?\ndo{",
            "code_block": "7.8 g-=a-=3;\n}\nwhile (a++ > -2);\nout.println(g);",
            "choices": "A. 15.8 B. 13.8 C. 11.8 D. 9.8 E.",
            "answer": "B",
            "group_id": "",
            "group_type": "single",
            "shared_context": "",
        })

        self.assertEqual(
            prepared["parsed_choices"],
            [
                {"letter": "A", "text": "15.8"},
                {"letter": "B", "text": "13.8"},
                {"letter": "C", "text": "11.8"},
                {"letter": "D", "text": "9.8"},
                {"letter": "E", "text": "7.8"},
            ],
        )
        self.assertIn("g-=a-=3;", prepared["code_block"])

    def test_visual_choice_fallback_handles_image_only_answer_sets(self):
        prepared = app.prepare_question({
            "id": 0,
            "exam_name": "2017_invitationala",
            "year": 2017,
            "level": "invitational",
            "question_number": 34,
            "question_text": "Which diagram is correct?",
            "code_block": "",
            "choices": "",
            "answer": "D",
            "group_id": "",
            "group_type": "single",
            "shared_context": "",
        })

        self.assertTrue(prepared["is_visual_choice"])
        self.assertEqual(prepared["visual_choice_labels"], ["A", "B", "C", "D", "E"])
        self.assertFalse(prepared["is_open_response"])

    def test_visual_choice_fallback_handles_incomplete_ocr_choice_sets(self):
        prepared = app.prepare_question({
            "id": 0,
            "exam_name": "2024_regional",
            "year": 2024,
            "level": "regional",
            "question_number": 38,
            "question_text": "What is output by the code to the right?",
            "code_block": "",
            "choices": "A) 21\nB) 25\n¢) 29\nD) 33\nE) 35\nout.print(C);",
            "answer": "C",
            "group_id": "",
            "group_type": "single",
            "shared_context": "",
        })

        self.assertTrue(prepared["is_visual_choice"])
        self.assertEqual(prepared["visual_choice_labels"], ["A", "B", "C", "D", "E"])
        self.assertEqual(prepared["parsed_choices"], [])
        self.assertIn("cropped PDF image", " ".join(prepared["display_issues"]))

    def test_visual_choice_fallback_handles_extended_choice_sets(self):
        prepared = app.prepare_question({
            "id": 0,
            "exam_name": "2024_regional",
            "year": 2024,
            "level": "regional",
            "question_number": 26,
            "question_text": "Which token belongs in the blank?",
            "code_block": "",
            "choices": "A) int\nB) private\nC) public\nD) Regional\nF) String\nG) super\nH) void",
            "answer": "F",
            "group_id": "",
            "group_type": "single",
            "shared_context": "",
        })

        self.assertTrue(prepared["is_visual_choice"])
        self.assertEqual(prepared["visual_choice_labels"], ["A", "B", "C", "D", "E", "F", "G", "H"])
        self.assertEqual(prepared["parsed_choices"], [])

    def test_two_choice_questions_keep_parsed_choices(self):
        prepared = app.prepare_question({
            "id": 0,
            "exam_name": "sample",
            "year": 2026,
            "level": "practice",
            "question_number": 1,
            "question_text": "What is printed?",
            "code_block": "",
            "choices": "A) true B) false",
            "answer": "A",
            "group_id": "",
            "group_type": "single",
            "shared_context": "",
        })

        self.assertFalse(prepared["is_visual_choice"])
        self.assertEqual([choice["letter"] for choice in prepared["parsed_choices"]], ["A", "B"])

    def test_extract_choice_block_from_crop_text_recovers_separate_choice_lines(self):
        crop_text = """Question 31.
Which of the following is the output of the main method shown here?
A)
abcdeabcdef
B)
fedcbaedcba
C)
cabdebacedf
D)
cedbaefdbca
E)
cbaededfbac
Question 32.
"""

        recovered = app.extract_choice_block_from_crop_text(crop_text, 31)

        self.assertIn("A)", recovered)
        self.assertIn("E)", recovered)
        parsed = app.parse_choices(recovered)
        self.assertEqual(parsed[0], {"letter": "A", "text": "abcdeabcdef"})
        self.assertEqual(parsed[-1], {"letter": "E", "text": "cbaededfbac"})

    def test_open_response_normalization_treats_numeric_equivalents_the_same(self):
        self.assertEqual(app.normalize_open_response_value("04"), "4")
        self.assertEqual(app.normalize_open_response_value("4.0"), "4")
        self.assertEqual(app.normalize_open_response_value(" 4 "), "4")

    def test_open_response_normalization_keeps_boolean_and_expression_operators(self):
        self.assertEqual(
            app.normalize_open_response_value("A ^ !C | !B or !A ^ C | !B"),
            "A^!C|!BOR!A^C|!B",
        )
        self.assertEqual(
            app.normalize_open_response_value("A B + C * D E – F G + * /"),
            "AB+C*DE-FG+*/",
        )

    def test_trim_rendered_blank_tail_removes_footer_gap(self):
        from PIL import Image, ImageDraw

        image = Image.new("RGB", (500, 700), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((40, 30, 460, 120), outline="black")
        draw.text((55, 55), "Question 40", fill="black")
        draw.line((40, 650, 460, 650), fill="black", width=2)

        trimmed = app.trim_rendered_blank_tail(image, min_gap_px=90, padding_px=20, min_height_px=100)

        self.assertLess(trimmed.height, 220)
        self.assertGreaterEqual(trimmed.height, 100)

    def test_normalize_answer_does_not_collapse_long_sentence_to_first_letter(self):
        text = "Tests may not be turned in until 45 minutes have elapsed."
        self.assertEqual(app.normalize_answer(text), text.upper())

    def test_normalize_answer_keeps_open_response_expression_starting_with_letter(self):
        self.assertEqual(app.normalize_answer("A ^ !C | !B"), "A ^ !C | !B")
        self.assertEqual(app.normalize_answer("D-B-G-C-A"), "D-B-G-C-A")

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

    def test_2017_invitational_c_question_39_stays_open_response_without_fake_choices(self):
        questions = self.load_archive_questions(
            ("2017", "Inv C (Round Rock)", "MC1703a_Written_QUESTIONS.pdf")
        )
        q39 = questions[39]

        self.assertIn("reverse Polish notation", q39["question_text"])
        self.assertNotIn("B)", q39["choices"])
        self.assertEqual(q39["choices"], "")

    def test_2025_district_question_39_does_not_bleed_into_question_40(self):
        questions = self.load_archive_questions(
            ("2025", "2025", "District", "CompSciWritten_StudyPacket_D_25.pdf")
        )
        q39 = questions[39]

        self.assertNotIn("Question 40", q39["question_text"])
        self.assertNotIn("Q uestion 40", q39["question_text"])
        self.assertNotIn("Convert the prefix expression", q39["question_text"])
        self.assertIn(40, questions)


if __name__ == "__main__":
    unittest.main()
