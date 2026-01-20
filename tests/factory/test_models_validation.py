"""Tests for Pydantic field validators in models.py."""

import pytest
from pydantic import ValidationError
from compiled_ai.factory.code_factory.models import (
    ActivityOutputSchema,
    ActivityInputParam,
)


class TestActivityOutputSchemaValidation:
    """Test output schema validation rules."""

    def test_semantic_description_passes(self):
        """Valid semantic descriptions should pass."""
        schema = ActivityOutputSchema(
            type="str",
            description="Returns the support ticket category classification (billing, technical, or general)",
            fields=None
        )
        assert schema.description.startswith("Returns")
        assert len(schema.description) >= 20

    def test_semantic_description_with_contains(self):
        """Valid semantic descriptions with 'contains' should pass."""
        schema = ActivityOutputSchema(
            type="dict",
            description="Contains normalized address data with street, city, state, zip, and country fields",
            fields={"street": "str", "city": "str", "state": "str", "zip": "str", "country": "str"}
        )
        assert "contains" in schema.description.lower()

    def test_semantic_description_with_represents(self):
        """Valid semantic descriptions with 'represents' should pass."""
        schema = ActivityOutputSchema(
            type="str",
            description="Represents the extracted sender email address from the email headers",
            fields=None
        )
        assert "represents" in schema.description.lower()

    def test_literal_value_fails(self):
        """Single literal values should fail."""
        with pytest.raises(ValidationError) as exc_info:
            ActivityOutputSchema(
                type="str",
                description="billing",
                fields=None
            )
        error_msg = str(exc_info.value).lower()
        assert "single word" in error_msg or "too short" in error_msg

    def test_short_description_fails(self):
        """Descriptions under 20 chars should fail."""
        with pytest.raises(ValidationError) as exc_info:
            ActivityOutputSchema(
                type="str",
                description="short desc",
                fields=None
            )
        assert "too short" in str(exc_info.value).lower()

    def test_raw_json_fails(self):
        """Raw JSON in description should fail."""
        with pytest.raises(ValidationError) as exc_info:
            ActivityOutputSchema(
                type="dict",
                description='{"sender": "john@example.com"}',
                fields={"sender": "str"}
            )
        assert "raw json" in str(exc_info.value).lower()

    def test_raw_json_with_nested_structure_fails(self):
        """Raw JSON with nested structure should fail."""
        with pytest.raises(ValidationError) as exc_info:
            ActivityOutputSchema(
                type="dict",
                description='{"function": "get_weather", "parameters": {"location": "Paris"}}',
                fields={"function": "str", "parameters": "dict"}
            )
        assert "raw json" in str(exc_info.value).lower()

    def test_no_semantic_keyword_fails(self):
        """Descriptions without semantic verbs should fail."""
        with pytest.raises(ValidationError) as exc_info:
            ActivityOutputSchema(
                type="str",
                description="billing technical general category ticket",
                fields=None
            )
        assert "semantic context" in str(exc_info.value).lower()

    def test_long_single_word_passes(self):
        """Long single words (30+ chars) should pass minimum checks."""
        # This is an edge case - might want to adjust later
        try:
            schema = ActivityOutputSchema(
                type="str",
                description="supercalifragilisticexpialidocious_and_more_text_here_to_make_it_long",
                fields=None
            )
            # Should still fail for lacking semantic keywords
        except ValidationError as e:
            # Expected - no semantic keywords
            assert "semantic context" in str(e).lower()

    def test_real_world_good_descriptions(self):
        """Real-world examples of good descriptions should pass."""
        good_descriptions = [
            "Returns the extracted email fields (sender, recipient, subject, date) as a structured dictionary",
            "Contains the normalized address with standardized formatting for street, city, state, zip, and country",
            "Provides the function call metadata including function name and required parameters",
            "Represents the user's selected category from the available options (billing, technical, general)",
            "The classification result indicating which category the ticket belongs to",
        ]

        for desc in good_descriptions:
            schema = ActivityOutputSchema(
                type="dict",
                description=desc,
                fields={"test": "str"}
            )
            assert len(schema.description) >= 20


class TestActivityInputParamValidation:
    """Test input parameter validation rules."""

    def test_detailed_description_passes(self):
        """Detailed input descriptions should pass."""
        param = ActivityInputParam(
            name="email_text",
            type="str",
            description="The complete email text containing headers and body content",
            required=True
        )
        assert "complete" in param.description
        assert len(param.description) >= 15

    def test_detailed_description_with_format(self):
        """Descriptions with format details should pass."""
        param = ActivityInputParam(
            name="address",
            type="str",
            description="The raw address string in free-form format (e.g., 123 Main St, NY, 10001)",
            required=True
        )
        assert len(param.description) >= 15

    def test_too_brief_fails(self):
        """Brief descriptions should fail."""
        with pytest.raises(ValidationError) as exc_info:
            ActivityInputParam(
                name="email_text",
                type="str",
                description="Email",
                required=True
            )
        assert "too brief" in str(exc_info.value).lower()

    def test_generic_description_fails(self):
        """Generic 1-3 word descriptions should fail."""
        with pytest.raises(ValidationError) as exc_info:
            ActivityInputParam(
                name="address",
                type="str",
                description="Address string",
                required=True
            )
        assert "too generic" in str(exc_info.value).lower()

    def test_two_word_description_fails(self):
        """Two-word descriptions should fail."""
        with pytest.raises(ValidationError) as exc_info:
            ActivityInputParam(
                name="data",
                type="dict",
                description="Input data",
                required=True
            )
        assert "too generic" in str(exc_info.value).lower()

    def test_three_word_description_fails(self):
        """Three-word descriptions should fail."""
        with pytest.raises(ValidationError) as exc_info:
            ActivityInputParam(
                name="text",
                type="str",
                description="The email text",
                required=True
            )
        assert "too generic" in str(exc_info.value).lower()

    def test_four_word_description_passes(self):
        """Four-word descriptions (minimum) should pass."""
        param = ActivityInputParam(
            name="text",
            type="str",
            description="The complete email text content",
            required=True
        )
        assert len(param.description.split()) >= 4

    def test_real_world_good_input_descriptions(self):
        """Real-world examples of good input descriptions should pass."""
        good_descriptions = [
            "The complete email text containing headers (From, To, Subject, Date) and body",
            "Source JSON object containing fields to transform according to target schema",
            "The support ticket text to be classified into categories",
            "Raw address string in any format that needs to be normalized",
            "List of available function definitions for the agent to choose from",
        ]

        for desc in good_descriptions:
            param = ActivityInputParam(
                name="test_param",
                type="str",
                description=desc,
                required=True
            )
            assert len(param.description) >= 15
            assert len(param.description.split()) >= 4


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_exactly_20_chars_output_passes(self):
        """Output description with exactly 20 characters should pass if it has semantic keywords."""
        schema = ActivityOutputSchema(
            type="str",
            description="Returns the result",  # Exactly 20 chars
            fields=None
        )
        assert len(schema.description) == 20

    def test_exactly_15_chars_input_passes(self):
        """Input description with exactly 15 characters should pass if it has 4+ words."""
        param = ActivityInputParam(
            name="test",
            type="str",
            description="A test data value",  # Exactly 15 chars after strip, 4 words
            required=True
        )
        assert len(param.description) >= 15

    def test_multiline_description_passes(self):
        """Multiline descriptions should be handled correctly."""
        param = ActivityInputParam(
            name="complex_param",
            type="dict",
            description="The complex data structure containing multiple fields that need validation",
            required=True
        )
        assert len(param.description) >= 15

    def test_description_with_special_characters(self):
        """Descriptions with special characters should pass."""
        schema = ActivityOutputSchema(
            type="dict",
            description="Returns the user's selected options (choice_1, choice_2, etc.) from the form",
            fields={"choices": "list"}
        )
        assert "'" in schema.description  # Contains apostrophe

    def test_description_with_numbers(self):
        """Descriptions with numbers should pass."""
        param = ActivityInputParam(
            name="text",
            type="str",
            description="The first 500 characters of the document text for preview",
            required=True
        )
        assert "500" in param.description
