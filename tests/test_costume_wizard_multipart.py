import unittest

from zet.web.app import _parse_costume_wizard_multipart


class CostumeWizardMultipartTests(unittest.TestCase):
    def test_reads_captions_and_binary_uploads_without_form_parser_dependency(self):
        boundary = "wizard-boundary"
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"name\"\r\n\r\nCloak\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption_1\"\r\n\r\nFront view\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"image_1\"; filename=\"cloak.png\"\r\n"
            "Content-Type: image/png\r\n\r\n"
        ).encode("ascii") + b"\x89PNG\x00\xff\r\n" + f"\r\n--{boundary}--\r\n".encode("ascii")

        form = _parse_costume_wizard_multipart(
            f"multipart/form-data; boundary={boundary}", body
        )

        self.assertEqual(form["name"], "Cloak")
        self.assertEqual(form["caption_1"], "Front view")
        self.assertEqual(form["image_1"]["filename"], "cloak.png")
        self.assertEqual(form["image_1"]["contents"], b"\x89PNG\x00\xff\r\n")

    def test_rejects_wrong_content_type_and_oversized_form(self):
        with self.assertRaisesRegex(ValueError, "multipart costume wizard form"):
            _parse_costume_wizard_multipart("application/json", b"{}")
        with self.assertRaisesRegex(ValueError, "less than 80 MB"):
            _parse_costume_wizard_multipart("multipart/form-data; boundary=x", b"x" * (80 * 1024 * 1024 + 1))


if __name__ == "__main__":
    unittest.main()
