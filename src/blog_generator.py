"""
Blog Post Generator

Generates blog post files (MDX with frontmatter) from the approved
weekly content plan. Blog posts are the primary content unit -- pins
are derived from them.

Supports four blog post types:
- weekly-plan: 5 embedded recipes + grocery list (1,200-1,800 words)
- recipe: Standalone recipe with Schema.org markup (600-800 words)
- guide: Structured guide/tips post (800-1,200 words)
- listicle: Numbered list format (800-1,200 words)

Each generated MDX file includes:
- Frontmatter: title, slug, description, date, type, pillar, heroImage,
  category, keywords, ctaPillarVariant, schema fields
- Body: Markdown content with appropriate structure
- CTAs: Mid-post and end-of-post CTAs using pillar-specific copy

Output files follow the goslated.com content structure:
    content/blog/{slug}.mdx
"""

import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Optional

import yaml

from src.apis.claude_api import ClaudeAPI
from src.paths import STRATEGY_DIR, TEMPLATES_DIR as _BASE_TEMPLATES_DIR
from src.utils.strategy_utils import load_brand_voice

logger = logging.getLogger(__name__)

TEMPLATES_DIR = _BASE_TEMPLATES_DIR / "blog"

# Word count targets by post type
WORD_COUNT_TARGETS = {
    "weekly-plan": (1200, 1800),
    "recipe": (600, 800),
    "guide": (800, 1200),
    "listicle": (800, 1200),
}

# Required frontmatter fields for all post types
REQUIRED_FRONTMATTER_FIELDS = [
    "title",
    "slug",
    "description",
    "date",
    "type",
    "pillar",
    "heroImage",
    "category",
    "keywords",
    "ctaPillarVariant",
]

# Additional required fields for recipe posts
RECIPE_SCHEMA_FIELDS = [
    "prepTime",
    "cookTime",
    "totalTime",
    "recipeYield",
    "recipeIngredient",
    "recipeInstructions",
]

# ISO 8601 duration pattern (e.g., PT30M, PT1H15M)
ISO_8601_DURATION_PATTERN = re.compile(
    r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$"
)


class BlogGeneratorError(Exception):
    """Raised when blog post generation fails."""
    pass


class BlogGenerator:
    """Generates MDX blog posts from content plan specifications."""

    def __init__(self, claude: Optional[ClaudeAPI] = None):
        """
        Initialize the blog generator.

        Args:
            claude: ClaudeAPI instance. Creates a new one if not provided.
        """
        self.claude = claude or ClaudeAPI()
        self._cta_cache: Optional[dict] = None
        self._brand_voice_cache: Optional[str] = None
        self._product_overview_cache: Optional[str] = None

    def generate(self, post_spec: dict) -> tuple[str, dict]:
        """
        Generate a single blog post. Main dispatch method.

        Routes to the appropriate type-specific generator based on content_type.

        Args:
            post_spec: Blog post specification from weekly plan.

        Returns:
            tuple: (mdx_content, frontmatter_dict)

        Raises:
            BlogGeneratorError: If generation fails.
        """
        content_type = post_spec.get("content_type", "recipe")
        logger.info(
            "Generating %s blog post: %s (post_id=%s)",
            content_type,
            post_spec.get("topic", "unknown"),
            post_spec.get("post_id", "unknown"),
        )

        generators = {
            "recipe": self.generate_recipe_post,
            "weekly-plan": self.generate_weekly_plan_post,
            "guide": self.generate_guide_post,
            "listicle": self.generate_listicle_post,
        }

        generator_fn = generators.get(content_type)
        if generator_fn is None:
            raise BlogGeneratorError(
                f"Unknown content_type: {content_type}. "
                f"Valid types: {list(generators.keys())}"
            )

        mdx_content = generator_fn(post_spec)
        frontmatter = self._extract_frontmatter(mdx_content)

        # Strip duplicate H1 if it matches the frontmatter title
        title = frontmatter.get("title", "")
        body = self._extract_body(mdx_content)
        body_lines = body.split("\n")
        stripped_h1 = False
        for i, line in enumerate(body_lines):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("# "):
                h1_text = stripped[2:].strip()
                if h1_text.lower() == title.lower() or title.lower() in h1_text.lower():
                    body_lines[i] = ""
                    stripped_h1 = True
                    logger.info("Stripped duplicate H1 from blog body: %s", h1_text)
            break

        if stripped_h1:
            body = "\n".join(body_lines)

            # Reconstruct mdx_content with cleaned body
            if mdx_content.startswith("---"):
                try:
                    end_idx = mdx_content.index("---", 3)
                    mdx_content = mdx_content[: end_idx + 3] + "\n\n" + body.strip() + "\n"
                except ValueError:
                    logger.warning("Could not find frontmatter closing delimiter during H1 reconstruction")

        return mdx_content, frontmatter

    def generate_blog_post(self, post_spec: dict) -> str:
        """
        Generate a single blog post as MDX content.

        Args:
            post_spec: Blog post specification from weekly plan with fields:
                - post_id: Unique ID (e.g., "W12-P01")
                - pillar: Content pillar (1-5)
                - content_type: "weekly-plan", "recipe", "guide", "listicle"
                - topic: Specific blog post topic
                - primary_keyword: Target keyword phrase
                - secondary_keywords: Additional keywords
                - schema_type: "Recipe", "Article", etc.
                - cta_pillar_variant: CTA copy variant (1-5)
                - seasonal_hook: Optional seasonal angle

        Returns:
            str: Complete MDX file content with frontmatter + body.

        Raises:
            BlogGeneratorError: If generation fails.
        """
        mdx_content, _ = self.generate(post_spec)
        return mdx_content

    def generate_batch(self, post_specs: list[dict]) -> list[dict]:
        """
        Generate a batch of blog posts from the weekly plan.

        Processes each post independently so that a failure in one does not
        block the rest.

        Args:
            post_specs: List of blog post specifications.

        Returns:
            list[dict]: Results with post_id, slug, mdx_content, frontmatter,
                        status ("success" or "failed"), error (if any).
        """
        results = []

        for spec in post_specs:
            post_id = spec.get("post_id", "unknown")
            try:
                mdx_content, frontmatter = self.generate(spec)
                slug = frontmatter.get("slug", self._generate_slug(spec.get("topic", "")))

                results.append({
                    "post_id": post_id,
                    "slug": slug,
                    "title": frontmatter.get("title", spec.get("topic", "")),
                    "mdx_content": mdx_content,
                    "frontmatter": frontmatter,
                    "content_type": spec.get("content_type"),
                    "pillar": spec.get("pillar"),
                    "status": "success",
                    "error": None,
                })
                logger.info("Successfully generated blog post: %s (%s)", slug, post_id)

            except Exception as e:
                logger.error("Failed to generate blog post %s: %s", post_id, e)
                results.append({
                    "post_id": post_id,
                    "slug": None,
                    "title": spec.get("topic", ""),
                    "mdx_content": None,
                    "frontmatter": None,
                    "content_type": spec.get("content_type"),
                    "pillar": spec.get("pillar"),
                    "status": "failed",
                    "error": str(e),
                })

        succeeded = sum(1 for r in results if r["status"] == "success")
        failed = sum(1 for r in results if r["status"] == "failed")
        logger.info(
            "Batch generation complete: %d succeeded, %d failed out of %d total",
            succeeded, failed, len(post_specs),
        )

        return results

    # Default pillar fallback by post type (used when spec omits pillar)
    _DEFAULT_PILLAR = {
        "recipe": 3,
        "weekly-plan": 1,
        "guide": 2,
        "listicle": 3,
    }

    def _generate_typed_post(self, spec: dict, post_type: str) -> str:
        """
        Generate a blog post of the given type.

        Loads brand voice, CTA copy, product overview, and example post,
        then delegates to ClaudeAPI.generate_blog_post() and validates
        the output.

        Args:
            spec: Blog post specification from the weekly plan.
            post_type: One of "recipe", "weekly-plan", "guide", "listicle".

        Returns:
            str: Complete MDX content.
        """
        default_pillar = self._DEFAULT_PILLAR.get(post_type, 3)
        pillar = spec.get("pillar", default_pillar)
        cta_copy = self._load_cta_copy(pillar)
        brand_voice = self._load_brand_voice()
        product_overview = self._load_product_overview()
        example = self._load_example_post(post_type)

        mdx_content = self.claude.generate_blog_post(
            post_spec=spec,
            post_type=post_type,
            brand_voice=brand_voice,
            cta_copy=cta_copy,
            examples=example,
            product_overview=product_overview,
        )

        self._validate_generated_post(mdx_content, post_type, spec)

        return mdx_content

    def generate_recipe_post(self, spec: dict) -> str:
        """Generate a recipe blog post (600-800 words) with Schema.org Recipe markup."""
        return self._generate_typed_post(spec, "recipe")

    def generate_weekly_plan_post(self, spec: dict) -> str:
        """Generate a weekly plan blog post (1200-1800 words)."""
        return self._generate_typed_post(spec, "weekly-plan")

    def generate_guide_post(self, spec: dict) -> str:
        """Generate a guide/tips blog post (800-1200 words)."""
        return self._generate_typed_post(spec, "guide")

    def generate_listicle_post(self, spec: dict) -> str:
        """Generate a listicle blog post (800-1200 words)."""
        return self._generate_typed_post(spec, "listicle")

    def validate_frontmatter(self, frontmatter: dict) -> list[str]:
        """
        Check that all required frontmatter fields are present and valid.

        Args:
            frontmatter: Parsed frontmatter dictionary.

        Returns:
            list[str]: List of validation warnings (empty if all pass).
        """
        warnings = []

        for field in REQUIRED_FRONTMATTER_FIELDS:
            if field not in frontmatter or frontmatter[field] is None:
                warnings.append(f"Missing required frontmatter field: {field}")
            elif isinstance(frontmatter[field], str) and not frontmatter[field].strip():
                warnings.append(f"Empty frontmatter field: {field}")

        # Validate pillar is 1-5
        pillar = frontmatter.get("pillar")
        if pillar is not None and pillar not in (1, 2, 3, 4, 5):
            warnings.append(f"Invalid pillar value: {pillar} (must be 1-5)")

        # Validate type is one of the known types
        post_type = frontmatter.get("type")
        valid_types = {"weekly-plan", "recipe", "guide", "listicle"}
        if post_type and post_type not in valid_types:
            warnings.append(f"Invalid post type: {post_type} (must be one of {valid_types})")

        # Validate keywords is a list
        keywords = frontmatter.get("keywords")
        if keywords is not None and not isinstance(keywords, list):
            warnings.append("keywords must be a list")

        # Validate description length (SEO meta description: 120-160 chars ideal)
        desc = frontmatter.get("description", "")
        if isinstance(desc, str) and len(desc) > 300:
            warnings.append(f"Description too long ({len(desc)} chars, max 300)")

        return warnings

    def validate_schema_fields(self, frontmatter: dict) -> list[str]:
        """
        For recipe posts, verify schema fields are present and correctly formatted.

        Checks prepTime, cookTime, recipeIngredient, recipeInstructions
        use ISO 8601 durations, etc.

        Args:
            frontmatter: Parsed frontmatter dictionary.

        Returns:
            list[str]: Validation warnings.
        """
        warnings = []
        post_type = frontmatter.get("type", "")

        if post_type != "recipe":
            return warnings

        for field in RECIPE_SCHEMA_FIELDS:
            if field not in frontmatter or frontmatter[field] is None:
                warnings.append(f"Missing recipe schema field: {field}")

        # Validate ISO 8601 duration fields
        for time_field in ("prepTime", "cookTime", "totalTime"):
            value = frontmatter.get(time_field, "")
            if value and not ISO_8601_DURATION_PATTERN.match(str(value)):
                warnings.append(
                    f"Invalid ISO 8601 duration for {time_field}: '{value}' "
                    f"(expected format like PT30M, PT1H15M)"
                )

        # Validate recipeIngredient is a non-empty list
        ingredients = frontmatter.get("recipeIngredient")
        if ingredients is not None:
            if not isinstance(ingredients, list):
                warnings.append("recipeIngredient must be a list of strings")
            elif len(ingredients) == 0:
                warnings.append("recipeIngredient is empty")

        # Validate recipeInstructions is a non-empty list
        instructions = frontmatter.get("recipeInstructions")
        if instructions is not None:
            if not isinstance(instructions, list):
                warnings.append("recipeInstructions must be a list of strings")
            elif len(instructions) == 0:
                warnings.append("recipeInstructions is empty")

        # Validate recipeYield
        recipe_yield = frontmatter.get("recipeYield")
        if recipe_yield is not None and not isinstance(recipe_yield, str):
            warnings.append("recipeYield must be a string (e.g., '4 servings')")

        return warnings

    def _validate_generated_post(
        self, mdx_content: str, post_type: str, spec: dict
    ) -> None:
        """
        Validate a generated blog post. Logs warnings but does not raise
        exceptions for non-critical issues.

        Args:
            mdx_content: The generated MDX content.
            post_type: Expected post type.
            spec: Original post specification.
        """
        if not mdx_content or not mdx_content.strip():
            raise BlogGeneratorError(
                f"Empty MDX content generated for {spec.get('post_id')}"
            )

        # Check frontmatter is present
        if not mdx_content.startswith("---"):
            logger.warning(
                "Generated post %s is missing frontmatter delimiters",
                spec.get("post_id"),
            )
            return

        frontmatter = self._extract_frontmatter(mdx_content)

        # Validate frontmatter fields
        fm_warnings = self.validate_frontmatter(frontmatter)
        for w in fm_warnings:
            logger.warning("Post %s: %s", spec.get("post_id"), w)

        # Hard-fail on critical missing frontmatter that would break deployment
        for critical_field in ("title", "slug", "description"):
            value = frontmatter.get(critical_field)
            if not value or (isinstance(value, str) and not value.strip()):
                raise BlogGeneratorError(
                    f"Post {spec.get('post_id')} is missing required "
                    f"frontmatter field: {critical_field}"
                )

        # Validate schema fields for recipe posts
        if post_type == "recipe":
            schema_warnings = self.validate_schema_fields(frontmatter)
            for w in schema_warnings:
                logger.warning("Post %s: %s", spec.get("post_id"), w)

        # Check word count
        body = self._extract_body(mdx_content)
        word_count = len(body.split())
        min_words, max_words = WORD_COUNT_TARGETS.get(post_type, (400, 2000))

        if word_count < min_words * 0.8:  # Allow 20% undercount tolerance
            logger.warning(
                "Post %s word count (%d) is below target range (%d-%d)",
                spec.get("post_id"), word_count, min_words, max_words,
            )
        elif word_count > max_words * 1.2:  # Allow 20% overcount tolerance
            logger.warning(
                "Post %s word count (%d) is above target range (%d-%d)",
                spec.get("post_id"), word_count, min_words, max_words,
            )

        # Check CTA component presence
        has_inline_cta = '<BlogCTA variant="inline"' in body
        has_end_cta = '<BlogCTA variant="end"' in body
        if not has_inline_cta:
            logger.warning(
                "Post %s is missing inline CTA (<BlogCTA variant=\"inline\" ... />)",
                spec.get("post_id"),
            )
        if not has_end_cta:
            logger.warning(
                "Post %s is missing end-of-post CTA (<BlogCTA variant=\"end\" ... />)",
                spec.get("post_id"),
            )

    def _extract_frontmatter(self, mdx_content: str) -> dict:
        """
        Extract frontmatter from MDX content as a dictionary.

        Parses the YAML block between --- delimiters using yaml.safe_load(),
        which correctly handles all YAML types (nested objects, quoted strings,
        multiline values) that the previous custom parser could misparse.

        Args:
            mdx_content: Complete MDX content.

        Returns:
            dict: Parsed frontmatter fields.
        """
        if not mdx_content.startswith("---"):
            return {}

        try:
            end_idx = mdx_content.index("---", 3)
        except ValueError:
            return {}

        yaml_block = mdx_content[3:end_idx].strip()

        try:
            parsed = yaml.safe_load(yaml_block)
        except yaml.YAMLError as e:
            logger.warning("Failed to parse frontmatter YAML: %s", e)
            return {}

        if not isinstance(parsed, dict):
            return {}

        return parsed

    def _extract_body(self, mdx_content: str) -> str:
        """
        Extract the body content (after frontmatter) from MDX.

        Args:
            mdx_content: Complete MDX content.

        Returns:
            str: Body content without frontmatter.
        """
        if not mdx_content.startswith("---"):
            return mdx_content

        try:
            end_idx = mdx_content.index("---", 3)
            return mdx_content[end_idx + 3:].strip()
        except ValueError:
            return mdx_content

    def _load_brand_voice(self) -> str:
        """Load brand voice guidelines from strategy/brand-voice.md."""
        if self._brand_voice_cache is not None:
            return self._brand_voice_cache

        self._brand_voice_cache = load_brand_voice()

        return self._brand_voice_cache

    def _load_product_overview(self) -> str:
        """Load Slated product overview from strategy/product-overview.md."""
        if self._product_overview_cache is not None:
            return self._product_overview_cache

        overview_path = STRATEGY_DIR / "product-overview.md"
        try:
            self._product_overview_cache = overview_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.warning("product-overview.md not found, using empty string")
            self._product_overview_cache = ""

        return self._product_overview_cache

    def _load_cta_copy(self, pillar: int) -> dict:
        """
        Load pillar-specific CTA copy from strategy/cta-variants.json.

        Args:
            pillar: Content pillar number (1-5).

        Returns:
            dict: With keys mid_post_cta and end_post_cta.
        """
        if self._cta_cache is None:
            cta_path = STRATEGY_DIR / "cta-variants.json"
            try:
                self._cta_cache = json.loads(cta_path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                logger.warning("cta-variants.json not found, using empty CTA")
                self._cta_cache = {"pillars": {}}

        pillar_str = str(pillar)
        pillar_cta = self._cta_cache.get("pillars", {}).get(pillar_str, {})

        return {
            "mid_post_cta": pillar_cta.get("mid_post_cta", ""),
            "end_post_cta": pillar_cta.get("end_post_cta", ""),
            "pillar_name": pillar_cta.get("name", ""),
        }

    def _load_example_post(self, post_type: str) -> str:
        """
        Load an example blog post for few-shot learning.

        Args:
            post_type: "weekly-plan", "recipe", "guide", or "listicle".

        Returns:
            str: Example post content, or empty string if not found.
        """
        type_to_file = {
            "weekly-plan": "weekly-plan-post-example.md",
            "recipe": "recipe-post-example.md",
            "guide": "guide-post-example.md",
            "listicle": "listicle-post-example.md",
        }

        filename = type_to_file.get(post_type)
        if filename is None:
            return ""

        example_path = TEMPLATES_DIR / filename
        try:
            return example_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.warning("Example post template not found: %s", example_path)
            return ""

    def _generate_slug(self, title: str) -> str:
        """
        Generate a URL-friendly slug from a blog post title.

        Normalizes unicode, lowercases, strips non-alphanumeric characters,
        and replaces whitespace with hyphens.

        Args:
            title: Blog post title.

        Returns:
            str: URL slug (e.g., "30-minute-chicken-stir-fry").
        """
        # Normalize unicode characters
        normalized = unicodedata.normalize("NFKD", title)
        # Convert to ASCII, ignore errors
        ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
        # Lowercase
        lower = ascii_text.lower()
        # Replace non-alphanumeric (except hyphens) with spaces
        cleaned = re.sub(r"[^a-z0-9\s-]", "", lower)
        # Replace whitespace (and multiple hyphens) with single hyphens
        slug = re.sub(r"[\s-]+", "-", cleaned).strip("-")

        return slug

    def save_post(self, slug: str, mdx_content: str, output_dir: Path) -> Path:
        """
        Save a generated blog post to disk.

        Args:
            slug: Blog post slug.
            mdx_content: Complete MDX content.
            output_dir: Directory to save the file.

        Returns:
            Path: Path to the saved file.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / f"{slug}.mdx"
        file_path.write_text(mdx_content, encoding="utf-8")
        logger.info("Saved blog post to %s", file_path)
        return file_path


if __name__ == "__main__":
    generator = BlogGenerator()
    test_spec = {
        "post_id": "TEST-P01",
        "pillar": 3,
        "content_type": "recipe",
        "topic": "30-Minute Chicken Stir Fry",
        "primary_keyword": "easy weeknight dinners",
        "secondary_keywords": ["chicken stir fry", "30 minute meals"],
        "schema_type": "Recipe",
        "cta_pillar_variant": 3,
    }
    result = generator.generate_blog_post(test_spec)
    print(f"Generated post length: {len(result)} chars")
