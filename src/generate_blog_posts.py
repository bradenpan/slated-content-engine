"""
Blog Post Generation Orchestrator

Orchestrates the generation of all blog posts from the approved weekly
content plan. Runs as part of the generate-content.yml workflow, BEFORE
pin content generation (blog-first workflow).

Blog posts must exist before pins because:
1. Pins need destination URLs
2. Recipe-pull pins excerpt content from their parent blog post
3. Blog posts must be deployed to Vercel before pins are posted

Weekly blog post production target (Month 1-2 launch phase):
- 2 weekly plan posts (5 recipes each, 1,200-1,800 words)
- 1-2 family-friendly recipe posts (Pillar 2)
- 3-4 standalone recipe posts (Pillar 3)
- 0.5-1 guide posts (Pillar 2/4)
- 1-2 dietary/appliance posts (Pillar 5)
- Total: ~8-10 new blog posts/week

Production tapers as the library matures (see strategy Section 3).
"""

import json
import logging
from typing import Optional

from src.blog_generator import BlogGenerator
from src.paths import DATA_DIR, STRATEGY_DIR, BLOG_OUTPUT_DIR

logger = logging.getLogger(__name__)

OUTPUT_DIR = BLOG_OUTPUT_DIR


def generate_blog_posts(plan_path: Optional[str] = None) -> dict:
    """
    Generate all blog posts from the approved weekly plan.

    This is the main entry point, called by the generate-content.yml workflow.

    Steps:
    1. Load the approved plan (from local JSON or Google Sheets)
    2. Filter to only "new content" blog posts (not fresh treatments)
    3. For each blog post in the plan:
       - Determine the post type
       - Load appropriate CTA copy based on pillar
       - Call blog_generator.generate()
       - Validate output
    4. Store generated MDX files in data/generated/blog/
    5. Store hero image references for each post
    6. Return list of generated blog post specs

    Args:
        plan_path: Optional path to the plan JSON file. If None, loads
                   the most recent plan from data/ directory.

    Returns:
        dict: post_id -> {slug, title, file_path, pillar, content_type,
              mdx_content, status, error}
    """
    logger.info("Starting blog post generation")

    # Load the plan
    plan = _load_plan(plan_path)
    if not plan:
        logger.error("No plan found to generate blog posts from")
        return {}

    blog_post_specs = plan.get("blog_posts", [])
    if not blog_post_specs:
        logger.warning("No blog posts in the plan")
        return {}

    # Filter to only new content (not fresh treatments which reuse existing posts)
    new_content_specs = [
        spec for spec in blog_post_specs
        if spec.get("is_new_content", True)
    ]

    logger.info(
        "Plan contains %d blog posts total, %d are new content",
        len(blog_post_specs),
        len(new_content_specs),
    )

    # Initialize generator
    generator = BlogGenerator()

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Generate all blog posts
    batch_results = generator.generate_batch(new_content_specs)

    # Save generated posts and build results dict
    results: dict = {}
    saved_paths: list[Path] = []

    for result in batch_results:
        post_id = result["post_id"]

        if result["status"] == "success" and result["mdx_content"]:
            slug = result["slug"]

            # Save the MDX file
            file_path = generator.save_post(slug, result["mdx_content"], OUTPUT_DIR)
            saved_paths.append(file_path)

            # Determine hero image reference (from frontmatter if present)
            hero_image = None
            if result.get("frontmatter"):
                hero_image = result["frontmatter"].get("heroImage")

            results[post_id] = {
                "slug": slug,
                "title": result.get("title", ""),
                "file_path": str(file_path),
                "pillar": result.get("pillar"),
                "content_type": result.get("content_type"),
                "mdx_content": result["mdx_content"],
                "hero_image": hero_image,
                "status": "success",
                "error": None,
            }
        else:
            results[post_id] = {
                "slug": None,
                "title": result.get("title", ""),
                "file_path": None,
                "pillar": result.get("pillar"),
                "content_type": result.get("content_type"),
                "mdx_content": None,
                "hero_image": None,
                "status": "failed",
                "error": result.get("error", "Unknown error"),
            }

    # Log summary
    succeeded = sum(1 for r in results.values() if r["status"] == "success")
    failed = sum(1 for r in results.values() if r["status"] == "failed")
    logger.info(
        "Blog post generation complete: %d succeeded, %d failed",
        succeeded, failed,
    )

    if failed > 0:
        failed_ids = [pid for pid, r in results.items() if r["status"] == "failed"]
        logger.warning("Failed blog post IDs: %s", failed_ids)

    # Save generation results metadata to a JSON file for downstream steps
    _save_generation_metadata(results)

    # Content Queue sheet write and Slack notification are handled by
    # generate_pin_content.py, which runs after this step and writes
    # both blog posts and pins together.

    return results


def _load_plan(plan_path: Optional[str] = None) -> dict:
    """
    Load the approved weekly plan from a JSON file.

    If plan_path is not provided, finds the most recent plan file in data/.

    Args:
        plan_path: Optional explicit path to the plan JSON file.

    Returns:
        dict: The weekly plan, or empty dict if not found.
    """
    if plan_path:
        path = Path(plan_path)
        if path.exists():
            logger.info("Loading plan from explicit path: %s", path)
            return json.loads(path.read_text(encoding="utf-8"))
        else:
            logger.error("Plan file not found: %s", path)
            return {}

    # Find the most recent plan file in data/
    plan_files = sorted(
        DATA_DIR.glob("weekly-plan-*.json"),
        reverse=True,
    )

    if not plan_files:
        logger.warning("No plan files found in %s", DATA_DIR)
        return {}

    latest = plan_files[0]
    logger.info("Loading most recent plan: %s", latest)
    return json.loads(latest.read_text(encoding="utf-8"))


def _save_generation_metadata(results: dict) -> None:
    """
    Save generation metadata to a JSON file for downstream pipeline steps.

    This metadata file is read by generate_pin_content.py to know which
    blog posts were generated and their locations.

    Args:
        results: Generation results dict.
    """
    metadata = {}
    for post_id, result in results.items():
        metadata[post_id] = {
            "slug": result.get("slug"),
            "title": result.get("title"),
            "file_path": result.get("file_path"),
            "pillar": result.get("pillar"),
            "content_type": result.get("content_type"),
            "hero_image": result.get("hero_image"),
            "status": result.get("status"),
            "error": result.get("error"),
        }

    metadata_path = DATA_DIR / "blog-generation-results.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Saved generation metadata to %s", metadata_path)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    print("Blog post generation orchestrator - run via generate-content.yml workflow")
    results = generate_blog_posts()
    succeeded = sum(1 for r in results.values() if r["status"] == "success")
    failed = sum(1 for r in results.values() if r["status"] == "failed")
    print(f"Generated {succeeded} blog posts ({failed} failed)")
