import unittest

import main
import official_explanations


class KeyParsingTests(unittest.TestCase):
    def test_parse_answers_from_two_column_key_line_captures_all_pairs(self):
        text = """1) D 21) A
2) C 22) B
19) B 39) 3
20) A 40) 11000101
"""

        answers = main.parse_answers_from_text(text)

        self.assertEqual(answers[1], "D")
        self.assertEqual(answers[21], "A")
        self.assertEqual(answers[39], "3")
        self.assertEqual(answers[40], "11000101")
        self.assertEqual(len(answers), 8)

    def test_parse_answers_keeps_open_response_tokens_from_compact_key_rows(self):
        text = "39) AB/CD*E-+ 40) 11100101"

        answers = main.parse_answers_from_text(text)

        self.assertEqual(answers[39], "AB/CD*E-+")
        self.assertEqual(answers[40], "11100101")

    def test_parse_answers_ignores_noisy_question_text_like_tokens(self):
        text = """How many ordered pairs of (cid:12), (cid:17), and (cid:18), make the boolean
17) ;
18) C
39) (cid:
40) See Explanation
"""

        answers = main.parse_answers_from_text(text)

        self.assertNotIn(17, answers)
        self.assertEqual(answers[18], "C")
        self.assertNotIn(39, answers)
        self.assertEqual(answers[40], "See Explanation")

    def test_parse_answers_does_not_treat_decimals_as_question_numbers(self):
        text = """1. D 11. E 21. B 31. E
double a = 4.99, b = 3.5;
2. C 12. D 22. A 32. B
"""

        answers = main.parse_answers_from_text(text)

        self.assertEqual(answers[1], "D")
        self.assertEqual(answers[2], "C")
        self.assertEqual(answers[11], "E")
        self.assertNotIn(4, answers)
        self.assertNotIn(3, answers)

    def test_parse_answers_ignores_choice_lines_when_detecting_compact_pairs(self):
        text = """A) None B) 1 C) 2 D) 3 E) 4
2) C 12) D 22) A 32) B
"""

        answers = main.parse_answers_from_text(text)

        self.assertEqual(answers[2], "C")

    def test_parse_answers_salvages_open_response_token_from_explanation_line(self):
        text = "39. 32 Here is the evolution of the stack: Bottom -> Top"

        answers = main.parse_answers_from_text(text)

        self.assertEqual(answers[39], "32")

    def test_parse_answers_keeps_cid_expression_for_open_response(self):
        text = """9) D 19) D 29) C *39) (cid:28)((cid:26)lg(cid:26))
10) A 20) D 30) B *40) See Explanation
"""

        answers = main.parse_answers_from_text(text)

        self.assertTrue(answers[39].startswith("(cid:"))
        self.assertEqual(answers[40], "See Explanation")

    def test_parse_answers_keeps_operator_only_open_response_tokens(self):
        text = "17) C 37) >>\n18) A 38) 100\n19) D 39) merge"

        answers = main.parse_answers_from_text(text)

        self.assertEqual(answers[37], ">>")
        self.assertEqual(answers[38], "100")
        self.assertEqual(answers[39], "merge")

    def test_parse_answers_keeps_symbolic_boolean_expression_for_q39(self):
        text = "19) B 39) ((!(B&&C)&&B)^(B&&C))||(!A&&(!(B&&C)&&B))\n20) A 40) 8"

        answers = main.parse_answers_from_text(text)

        self.assertEqual(answers[39], "((!(B&&C)&&B)^(B&&C))||(!A&&(!(B&&C)&&B))")
        self.assertEqual(answers[40], "8")

    def test_parse_answers_allows_q39_expression_starting_with_not(self):
        text = "19) B 39) !C&&B&&!(A&&B) or !A&&B&&!C\n20) A 40) 42"

        answers = main.parse_answers_from_text(text)

        self.assertEqual(answers[39], "!C&&B&&!(A&&B) or !A&&B&&!C")
        self.assertEqual(answers[40], "42")

    def test_parse_answers_keeps_postfix_expression_with_spaced_operators(self):
        text = "37) C\n38) A\n39) + * 3 5 / 6 2\n40) 8"

        answers = main.parse_answers_from_text(text)

        self.assertEqual(answers[39], "+ * 3 5 / 6 2")
        self.assertEqual(answers[40], "8")

    def test_rebuild_choice_block_can_merge_prompt_leak_and_blank_e_choice(self):
        prompt, leaked = main.split_trailing_choice_leak(
            "Which of the following is equivalent?\nD. fourth choice\nE. fifth choice"
        )

        rebuilt = main.rebuild_choice_block(
            "A. first B. second C. third",
            leaked,
        )

        self.assertEqual(prompt, "Which of the following is equivalent?")
        self.assertEqual(
            rebuilt,
            "A. first\nB. second\nC. third\nD. fourth choice\nE. fifth choice",
        )

    def test_rebuild_compact_choice_grid_handles_label_row_then_value_row(self):
        rebuilt = main.rebuild_compact_choice_grid(
            "A) B) C) D) E)\nLINE #1 LINE #2 LINE #3 LINE #4 LINE #5"
        )

        self.assertEqual(
            rebuilt,
            "A) LINE #1\nB) LINE #2\nC) LINE #3\nD) LINE #4\nE) LINE #5",
        )

    def test_rebuild_compact_choice_grid_can_merge_negative_sign_prefix(self):
        rebuilt = main.rebuild_compact_choice_grid(
            "A) - B) C) D)\n5.0 5.0 -5.5 6.0\nE)\n-6.0"
        )

        self.assertEqual(
            rebuilt,
            "A) -5.0\nB) 5.0\nC) -5.5\nD) 6.0\nE) -6.0",
        )

    def test_parse_official_explanations_from_numbered_section(self):
        text = """Answer Key
1) A 2) B

Explanations:
1. A 64 + 16 + 8 + 4 + 1 = 93
2. D 15-10/5+8*2 = 29
This spans another line.
3. A The escape sequence prints a quote.
"""

        explanations = official_explanations.parse_explanations_from_text(text)

        self.assertEqual(explanations[1], "A 64 + 16 + 8 + 4 + 1 = 93")
        self.assertEqual(explanations[2], "D 15-10/5+8*2 = 29\nThis spans another line.")
        self.assertEqual(explanations[3], "A The escape sequence prints a quote.")

    def test_parse_official_explanations_ignores_grader_notes(self):
        text = """#2324-14 KEY
1) A 2) B
Note to Graders:
All code is syntactically correct unless otherwise stated.
"""

        explanations = official_explanations.parse_explanations_from_text(text)

        self.assertEqual(explanations, {})


if __name__ == "__main__":
    unittest.main()
