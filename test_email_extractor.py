import unittest
import re
from typing import Dict, List, Any

# Assuming email_extractor.py is in the same directory
from email_extractor import extract_emails

class TestExtractEmails(unittest.TestCase):

    def test_single_email(self):
        data = {"user": {"name": "Test User", "email": "test@example.com"}}
        self.assertEqual(extract_emails(data), ["test@example.com"])

    def test_multiple_emails(self):
        data = {
            "users": [
                {"email": "user1@example.com"},
                {"email": "user2@test.org"}
            ]
        }
        self.assertCountEqual(extract_emails(data), ["user1@example.com", "user2@test.org"])

    def test_no_emails(self):
        data = {"name": "No Email", "age": 30}
        self.assertEqual(extract_emails(data), [])

    def test_invalid_emails(self):
        data = {
            "contact": {
                "email1": "invalid-email",
                "email2": "another@invalid",
                "email3": "valid@domain.com"
            }
        }
        self.assertEqual(extract_emails(data), ["valid@domain.com"])

    def test_nested_data(self):
        data = {
            "level1": {
                "level2": {
                    "admin_email": "admin@company.com",
                    "support": {
                        "email": "support@company.com"
                    }
                }
            },
            "other_email": "other@external.net"
        }
        expected_emails = ["admin@company.com", "support@company.com", "other@external.net"]
        actual_emails = extract_emails(data)
        self.assertCountEqual(actual_emails, expected_emails)

    def test_list_of_strings(self):
        data = {"emails": ["a@b.com", "c@d.net", "not_an_email"]}
        self.assertEqual(extract_emails(data), ["a@b.com", "c@d.net"])

    def test_empty_data(self):
        data = {}
        self.assertEqual(extract_emails(data), [])

    def test_mixed_types_and_none(self):
        data = {
            "key1": "email1@example.com",
            "key2": 123,
            "key3": True,
            "key4": None,
            "key5": ["email2@example.com", 456],
            "key6": {"sub_key": "email3@example.com"}
        }
        expected_emails = ["email1@example.com", "email2@example.com", "email3@example.com"]
        actual_emails = extract_emails(data)
        self.assertCountEqual(actual_emails, expected_emails)

if __name__ == '__main__':
    unittest.main()
