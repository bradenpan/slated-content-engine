"""Tests for _validate_generated_post() in src/blog_generator.py.

Covers fix #10: BlogGeneratorError raised on missing critical frontmatter
(title, slug, description).
"""

import sys
from unittest.mock import MagicMock

import pytest

# Mock the anthropic module before importing blog_generator (which transitively
# imports claude_api which requires anthropic).
sys.modules.setdefault("anthropic", MagicMock())

from src.shared.blog_generator import BlogGenerator, BlogGeneratorError


@pytest.fixture
def generator():
    """Create a BlogGenerator with a mocked ClaudeAPI."""
    mock_claude = MagicMock()
    return BlogGenerator(claude=mock_claude)


def _mdx(frontmatter_yaml: str, body: str = "Some body content " * 50) -> str:
    """Build an MDX string from raw YAML frontmatter and body text."""
    return f"---\n{frontmatter_yaml}\n---\n\n{body}"


VALID_FRONTMATTER = (
    'title: "Test Post Title"\n'
    'slug: "test-post-title"\n'
    'description: "A test description for the post"\n'
    'date: "2026-02-27"\n'
    'type: "recipe"\n'
    "pillar: 3\n"
    'heroImage: "/images/test.jpg"\n'
    'category: "recipes"\n'
    "keywords:\n  - test\n"
    "ctaPillarVariant: 3\n"
)

SPEC = {"post_id": "TEST-01", "pillar": 3, "content_type": "recipe"}


class TestMissingCriticalFrontmatter:
    """Missing title, slug, or description must raise BlogGeneratorError."""

    def test_missing_title_raises(self, generator):
        fm = VALID_FRONTMATTER.replace('title: "Test Post Title"\n', "")
        mdx = _mdx(fm)
        with pytest.raises(BlogGeneratorError, match="title"):
            generator._validate_generated_post(mdx, "recipe", SPEC)

    def test_missing_slug_raises(self, generator):
        fm = VALID_FRONTMATTER.replace('slug: "test-post-title"\n', "")
        mdx = _mdx(fm)
        with pytest.raises(BlogGeneratorError, match="slug"):
            generator._validate_generated_post(mdx, "recipe", SPEC)

    def test_missing_description_raises(self, generator):
        fm = VALID_FRONTMATTER.replace(
            'description: "A test description for the post"\n', ""
        )
        mdx = _mdx(fm)
        with pytest.raises(BlogGeneratorError, match="description"):
            generator._validate_generated_post(mdx, "recipe", SPEC)


class TestEmptyWhitespaceCriticalFields:
    """Empty or whitespace-only critical fields must raise BlogGeneratorError."""

    def test_empty_title_raises(self, generator):
        fm = VALID_FRONTMATTER.replace(
            'title: "Test Post Title"', 'title: ""'
        )
        mdx = _mdx(fm)
        with pytest.raises(BlogGeneratorError, match="title"):
            generator._validate_generated_post(mdx, "recipe", SPEC)

    def test_whitespace_title_raises(self, generator):
        fm = VALID_FRONTMATTER.replace(
            'title: "Test Post Title"', 'title: "   "'
        )
        mdx = _mdx(fm)
        with pytest.raises(BlogGeneratorError, match="title"):
            generator._validate_generated_post(mdx, "recipe", SPEC)


class TestNonCriticalIssuesDoNotRaise:
    """Low word count and missing CTA should warn, not raise."""

    def test_low_word_count_does_not_raise(self, generator):
        short_body = "Just a few words."
        mdx = _mdx(VALID_FRONTMATTER, body=short_body)
        # Should not raise -- only logs a warning
        generator._validate_generated_post(mdx, "recipe", SPEC)

    def test_missing_cta_does_not_raise(self, generator):
        body_no_cta = "This body has no CTA components at all. " * 80
        mdx = _mdx(VALID_FRONTMATTER, body=body_no_cta)
        # Should not raise -- only logs a warning
        generator._validate_generated_post(mdx, "recipe", SPEC)

    def test_valid_post_does_not_raise(self, generator):
        body = (
            "This is a valid blog post body with enough words. " * 40
            + '\n<BlogCTA variant="inline" pillar={3} />\n'
            + '\n<BlogCTA variant="end" pillar={3} />\n'
        )
        mdx = _mdx(VALID_FRONTMATTER, body=body)
        generator._validate_generated_post(mdx, "recipe", SPEC)


class TestEmptyContentRaises:
    """Empty or whitespace-only MDX content must raise."""

    def test_empty_string_raises(self, generator):
        with pytest.raises(BlogGeneratorError, match="Empty"):
            generator._validate_generated_post("", "recipe", SPEC)

    def test_whitespace_only_raises(self, generator):
        with pytest.raises(BlogGeneratorError, match="Empty"):
            generator._validate_generated_post("   \n  ", "recipe", SPEC)
