import unittest
from unittest.mock import patch

import main


class _FakePage:
    def __init__(self, text):
        self._text = text

    def extract_text(self):
        return self._text


class _FakePdf:
    def __init__(self, texts):
        self.pages = [_FakePage(t) for t in texts]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class OcrFallbackTests(unittest.TestCase):
    def test_should_attempt_ocr_for_empty_or_tiny_text(self):
        self.assertTrue(main.should_attempt_ocr(""))
        self.assertTrue(main.should_attempt_ocr("Page 1"))

    def test_should_not_attempt_ocr_for_normal_text(self):
        text = "Question 1 A. one B. two C. three D. four E. five " * 4
        self.assertFalse(main.should_attempt_ocr(text))

    def test_extract_full_text_uses_ocr_when_pdf_text_is_empty(self):
        with patch("main.pdfplumber.open", return_value=_FakePdf(["", ""])) as open_mock:
            with patch("main.extract_text_with_tesseract_ocr", return_value="Question 1\nA. one") as ocr_mock:
                text = main.extract_full_text("dummy.pdf", allow_ocr=True)

        self.assertEqual(text, "Question 1\nA. one")
        open_mock.assert_called_once()
        ocr_mock.assert_called_once_with("dummy.pdf")

    def test_extract_full_text_skips_ocr_when_text_is_present(self):
        rich_text = (
            "Question 1 A. option one B. option two C. option three D. option four E. option five\n"
            "Question 2 A. alpha B. beta C. gamma D. delta E. epsilon\n"
        )
        with patch("main.pdfplumber.open", return_value=_FakePdf([rich_text, rich_text])):
            with patch("main.extract_text_with_tesseract_ocr", return_value="OCR text") as ocr_mock:
                text = main.extract_full_text("dummy.pdf", allow_ocr=True)

        self.assertIn("Question 1", text)
        self.assertEqual(ocr_mock.call_count, 0)


if __name__ == "__main__":
    unittest.main()
