import unittest

import app


class SearchRelevanceTests(unittest.TestCase):
    def make_row(self, question_text="", code_block="", choices="", answer="", shared_context=""):
        return {
            "question_text": question_text,
            "code_block": code_block,
            "choices": choices,
            "answer": answer,
            "shared_context": shared_context,
        }

    def test_class_search_ignores_generic_method_only_problem(self):
        row = self.make_row(
            question_text="What value is returned by the recursive method call?",
            code_block="public static int solve(int n) { return n <= 1 ? 1 : solve(n - 1); }",
        )

        self.assertFalse(app.row_matches_terms(row, ["class", *app.expand_keyword("class")]))

    def test_class_search_matches_actual_oop_context(self):
        row = self.make_row(
            question_text="What is printed by the following classes?",
            code_block="class A {}\nclass B extends A {}\nA obj = new B();",
        )

        self.assertTrue(app.row_matches_terms(row, ["class", *app.expand_keyword("class")]))

    def test_math_search_ignores_plain_assignment_and_loops(self):
        row = self.make_row(
            question_text="What is printed after the loop finishes?",
            code_block="int total = 0;\nfor (int i = 0; i < 5; i++) {\n    total += i;\n}",
        )

        self.assertFalse(app.row_matches_terms(row, ["math", *app.expand_keyword("math")]))

    def test_math_search_matches_math_library_usage(self):
        row = self.make_row(
            question_text="What value is produced by the Math call?",
            code_block="double x = Math.sqrt(49) + Math.abs(-3);",
        )

        self.assertTrue(app.row_matches_terms(row, ["math", *app.expand_keyword("math")]))

    def test_exact_topic_match_scores_higher_than_synonym_only_match(self):
        direct_row = self.make_row(
            question_text="This class hierarchy prints a value.",
            code_block="class A {}\nclass B extends A {}",
        )
        synonym_row = self.make_row(
            question_text="An object uses a constructor and an instance field.",
            code_block="Widget obj = new Widget();",
        )

        direct_match = app.score_search_match(direct_row, "class")
        synonym_match = app.score_search_match(synonym_row, "class")

        self.assertIsNotNone(direct_match)
        self.assertIsNotNone(synonym_match)
        self.assertGreater(direct_match["score"], synonym_match["score"])
        self.assertEqual(direct_match["confidence"], "High")

    def test_low_confidence_match_still_reports_confidence_tier(self):
        row = self.make_row(
            question_text="An object is created from a constructor with one instance field.",
            code_block="Thing t = new Thing();",
        )

        match = app.score_search_match(row, "class")

        self.assertIsNotNone(match)
        self.assertEqual(match["confidence"], "Low")
        self.assertIn("related terms", " ".join(match["reasons"]))

    def test_recursive_code_without_keyword_still_scores_as_meaningful_recursion_match(self):
        row = self.make_row(
            question_text="How many times is the method go() called?",
            code_block="public int go(int num) { if (num <= 0) return num; return go(num - 1); }",
        )

        match = app.score_search_match(row, "recursion")

        self.assertIsNotNone(match)
        self.assertGreaterEqual(match["score"], 60)
        self.assertIn("recursion tag", " ".join(match["reasons"]))

    def test_priority_queue_search_matches_heap_style_question(self):
        row = self.make_row(
            question_text="What value is removed next from the heap?",
            code_block="PriorityQueue<Integer> pq = new PriorityQueue<>(); pq.offer(7); pq.poll();",
        )

        self.assertTrue(app.row_matches_terms(row, ["priority queue", *app.expand_keyword("priority queue")]))

    def test_stack_search_ignores_choice_only_mentions(self):
        row = self.make_row(
            question_text="Which generic modifier is required by this declaration?",
            code_block="public class Box<T extends Comparable<T>> {}",
            choices="A) LinkedList B) Queue C) Stack D) Vector E) Deque",
        )

        self.assertFalse(app.row_matches_terms(row, ["stack", *app.expand_keyword("stack")]))
        self.assertIsNone(app.score_search_match(row, "stack"))

    def test_big_o_search_matches_runtime_question(self):
        row = self.make_row(
            question_text="What is the worst case runtime in Big O notation?",
            code_block="for (int i = 0; i < n; i++) { for (int j = 0; j < n; j++) {} }",
        )

        self.assertTrue(app.row_matches_terms(row, ["big o", *app.expand_keyword("big o")]))


if __name__ == "__main__":
    unittest.main()
