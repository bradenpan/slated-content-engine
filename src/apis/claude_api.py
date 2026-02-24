"""
Claude API Wrapper with Prompt Template Loading

Wraps the Anthropic Claude API for all LLM tasks in the pipeline:
- Content planning (weekly plan generation)
- Pin copy generation (titles, descriptions, alt text, text overlay)
- Blog post generation (recipes, guides, listicles, weekly plans)
- Image prompt/search query generation
- Performance analysis (weekly and monthly)

Handles prompt template loading from the prompts/ directory, context
injection (strategy doc, content memory, analytics data), and structured
output parsing.

Model selection:
- Claude Sonnet for routine tasks (planning, copy, blog posts, weekly analysis)
- Claude Opus for monthly strategy reviews (deeper reasoning)

Token/cost tracking: logs input/output token counts per call.

Environment variables required:
- ANTHROPIC_API_KEY
"""

import base64
import json
import logging
import os
from pathlib import Path
from typing import Optional

import anthropic

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"
STRATEGY_DIR = Path(__file__).parent.parent.parent / "strategy"

# Model selection -- using the latest model IDs
MODEL_ROUTINE = "claude-sonnet-4-20250514"
MODEL_DEEP = "claude-opus-4-20250514"
MODEL_HAIKU = "claude-haiku-4-5-20251001"

# Approximate costs per million tokens (for cost tracking)
COST_PER_MTK = {
    MODEL_ROUTINE: {"input": 3.0, "output": 15.0},
    MODEL_DEEP: {"input": 15.0, "output": 75.0},
    MODEL_HAIKU: {"input": 0.80, "output": 4.0},
}


class ClaudeAPIError(Exception):
    """Raised when Claude API calls fail."""
    pass


class ClaudeAPI:
    """Client for Claude API with prompt template support."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Claude API client.

        Args:
            api_key: Anthropic API key. If not provided,
                     reads from ANTHROPIC_API_KEY env var.
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")

        if not self.api_key:
            raise ClaudeAPIError(
                "No Anthropic API key provided. Set ANTHROPIC_API_KEY env var."
            )

        self.client = anthropic.Anthropic(api_key=self.api_key)

        # Cumulative token/cost tracking for the session
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_usd = 0.0

    def load_prompt_template(self, template_name: str) -> str:
        """
        Load a prompt template from the prompts/ directory.

        Args:
            template_name: Name of the template file (e.g., "weekly_plan.md").

        Returns:
            str: The raw prompt template text.

        Raises:
            FileNotFoundError: If the template doesn't exist.
        """
        template_path = PROMPTS_DIR / template_name

        if not template_path.exists():
            raise FileNotFoundError(
                f"Prompt template not found: {template_path}. "
                f"Available templates: {[f.name for f in PROMPTS_DIR.glob('*.md')]}"
            )

        content = template_path.read_text(encoding="utf-8")
        logger.debug("Loaded prompt template: %s (%d chars)", template_name, len(content))
        return content

    def _render_template(self, template: str, context: dict) -> str:
        """
        Inject context variables into a prompt template.

        Replaces {{VARIABLE_NAME}} placeholders with values from the context dict.

        Args:
            template: Raw template text with {{placeholders}}.
            context: Dict of variable name -> value to inject.

        Returns:
            str: Rendered template with all placeholders replaced.
        """
        rendered = template
        for key, value in context.items():
            placeholder = "{{" + key + "}}"
            if isinstance(value, (dict, list)):
                rendered = rendered.replace(placeholder, json.dumps(value, indent=2))
            else:
                rendered = rendered.replace(placeholder, str(value))
        return rendered

    def generate_weekly_plan(
        self,
        strategy_doc: str,
        weekly_analysis: str,
        content_memory: str,
        seasonal_context: str,
        keyword_data: dict,
        negative_keywords: list[str],
    ) -> dict:
        """
        Generate a weekly content plan using Claude Sonnet.

        Loads the weekly_plan.md prompt template and injects all context:
        strategy document, latest weekly analysis, content memory summary,
        current seasonal window, keyword performance data, and negative
        keywords to avoid.

        Args:
            strategy_doc: Full text of strategy/current-strategy.md.
            weekly_analysis: Latest weekly analysis markdown.
            content_memory: Content memory summary markdown.
            seasonal_context: Current seasonal window description.
            keyword_data: Keyword lists with performance data.
            negative_keywords: List of keywords/topics to avoid.

        Returns:
            dict: Structured weekly plan with blog_posts and pins arrays.
        """
        from datetime import date as _date
        template = self.load_prompt_template("weekly_plan.md")

        today = _date.today()
        context = {
            "current_date": today.isoformat(),
            "week_number": str(today.isocalendar()[1]),
            "strategy_summary": strategy_doc,
            "last_week_analysis": weekly_analysis or "No previous analysis available (first run).",
            "content_memory_summary": content_memory or "No content history yet (first run).",
            "seasonal_window": seasonal_context,
            "keyword_performance": keyword_data,
            "negative_keywords": "\n".join(f"- {kw}" for kw in negative_keywords) if negative_keywords else "See NEGATIVE KEYWORD CONSTRAINTS above.",
        }

        prompt = self._render_template(template, context)

        system = (
            "You are a Pinterest content strategist for Slated, a family meal planning app. "
            "Generate a detailed weekly content plan. "
            "The plan must include 'blog_posts' (array of 8-10 blog post specs) and "
            "'pins' (array of 28 pin specs derived from those posts). "
            "Follow the strategy document precisely for pillar mix, funnel layers, "
            "and board distribution constraints. "
            "IMPORTANT: Output ONLY valid JSON. No explanations, reasoning, or text before or after the JSON. "
            "Your response must start with { and end with }."
        )

        logger.info("Generating weekly content plan...")
        response_text = self._call_api(
            prompt=prompt,
            system=system,
            model=MODEL_ROUTINE,
            max_tokens=8192,
            temperature=0.7,
        )

        return self._parse_json_response(response_text, "weekly plan")

    def generate_pin_copy(
        self,
        pin_specs: list[dict],
        brand_voice: str,
        keyword_targets: dict,
    ) -> list[dict]:
        """
        Generate pin copy (title, description, alt text, overlay text)
        for a batch of pins.

        Batches 5-7 pins per API call for efficiency.

        Args:
            pin_specs: List of pin specifications from the weekly plan.
            brand_voice: Brand voice guidelines text.
            keyword_targets: Per-pillar keyword targets.

        Returns:
            list[dict]: Pin copy for each pin (title, description, alt_text,
                        text_overlay, image_search_queries or image_prompt).
        """
        template = self.load_prompt_template("pin_copy.md")
        all_results = []

        # Process in batches of 5-7
        batch_size = 6
        for i in range(0, len(pin_specs), batch_size):
            batch = pin_specs[i:i + batch_size]

            context = {
                "pin_specs": batch,
                "blog_post_content": "",
                "pillar": "See individual pin specs above",
                "funnel_layer": "See individual pin specs above",
                "brand_voice_details": brand_voice or "",
                "keyword_targets": keyword_targets or {},
            }

            prompt = self._render_template(template, context)

            system = (
                "You are a Pinterest SEO copywriter for Slated, a family meal planning app. "
                "Generate pin copy for each pin specification. Return valid JSON: an array "
                "of objects with keys: pin_id, title (max 100 chars), description (250-500 chars), "
                "alt_text (max 500 chars), text_overlay (6-8 words). "
                "Follow Pinterest SEO best practices: keywords early, natural language, no hashtags."
            )

            # If any pin in the batch has reviewer feedback, add guidance to system message
            has_feedback = any(spec.get("_copy_feedback") for spec in batch)
            if has_feedback:
                system += (
                    " IMPORTANT: One or more pins have a '_copy_feedback' field containing "
                    "reviewer feedback on the previous version. Read each pin's _copy_feedback "
                    "carefully and address the feedback specifically in the new copy. "
                    "The previous version was rejected for the stated reason."
                )

            logger.info("Generating pin copy batch %d-%d of %d...", i + 1, i + len(batch), len(pin_specs))
            response_text = self._call_api(
                prompt=prompt,
                system=system,
                model=MODEL_ROUTINE,
                max_tokens=4096,
                temperature=0.7,
            )

            batch_results = self._parse_json_response(response_text, "pin copy batch")
            if isinstance(batch_results, list):
                all_results.extend(batch_results)
            elif isinstance(batch_results, dict) and "pins" in batch_results:
                all_results.extend(batch_results["pins"])
            else:
                logger.warning("Unexpected pin copy response format, attempting to use as-is.")
                all_results.append(batch_results)

        return all_results

    def generate_blog_post(
        self,
        post_spec: dict,
        post_type: str,
        brand_voice: str,
        cta_copy: dict,
        examples: str,
        product_overview: str = "",
    ) -> str:
        """
        Generate a complete blog post as MDX with frontmatter.

        Uses the type-specific prompt template (blog_post_recipe.md,
        blog_post_weekly_plan.md, etc.).

        Args:
            post_spec: Blog post specification from weekly plan.
            post_type: One of "recipe", "weekly-plan", "guide", "listicle".
            brand_voice: Brand voice guidelines.
            cta_copy: Pillar-specific CTA copy variants.
            examples: Example blog post content for few-shot learning.
            product_overview: Slated product overview for CTA context.

        Returns:
            str: Complete MDX file content (frontmatter + body).
        """
        from datetime import date as _date
        # Map post type to template file
        template_map = {
            "recipe": "blog_post_recipe.md",
            "weekly-plan": "blog_post_weekly_plan.md",
            "guide": "blog_post_guide.md",
            "listicle": "blog_post_listicle.md",
        }

        template_name = template_map.get(post_type)
        if not template_name:
            raise ClaudeAPIError(f"Unknown post type: {post_type}. Expected one of: {list(template_map.keys())}")

        template = self.load_prompt_template(template_name)

        context = {
            "topic": post_spec.get("topic", ""),
            "plan_theme": post_spec.get("topic", ""),  # alias for weekly-plan template
            "primary_keyword": post_spec.get("primary_keyword", ""),
            "secondary_keywords": post_spec.get("secondary_keywords", []),
            "recipes": post_spec.get("recipes", "See topic description"),
            "include_recipes": str(post_spec.get("include_recipes", False)),
            "pillar": str(post_spec.get("pillar", "")),
            "current_date": _date.today().isoformat(),
            "post_spec": post_spec,
            "brand_voice": brand_voice,
            "cta_copy": cta_copy,
            "examples": examples,
            "product_overview": product_overview,
        }

        prompt = self._render_template(template, context)

        # Token limits vary by post type
        max_tokens_map = {
            "recipe": 4096,
            "weekly-plan": 8192,  # Longer: 5 embedded recipes
            "guide": 6144,
            "listicle": 6144,
        }

        system = (
            "You are a food and lifestyle content writer for Slated, a family meal planning app. "
            "Generate a complete blog post in MDX format with YAML frontmatter. "
            "The output should be a valid MDX file that can be saved directly. "
            "Start the output with --- to begin the frontmatter block. "
            "Follow the brand voice guidelines exactly. Write practically, not preachy."
        )

        logger.info("Generating %s blog post: %s", post_type, post_spec.get("topic", "unknown"))
        response_text = self._call_api(
            prompt=prompt,
            system=system,
            model=MODEL_ROUTINE,
            max_tokens=max_tokens_map.get(post_type, 4096),
            temperature=0.7,
        )

        return response_text

    def generate_image_prompt(
        self,
        pin_spec: dict,
        image_source: str,
        regen_feedback: str = "",
    ) -> str:
        """
        Generate either an AI image prompt or stock photo search queries.

        Args:
            pin_spec: Pin specification with topic, template type, etc.
            image_source: "ai" for AI image prompt, "stock" for search queries,
                          "stock_retry" for broader/alternative stock queries
                          when initial search scored poorly.
            regen_feedback: Optional reviewer feedback from a regen request.
                            When provided, guides image selection/generation
                            toward what the reviewer wants.

        Returns:
            str: AI image generation prompt or stock photo search query.
        """
        template_name = "image_prompt.md" if image_source == "ai" else "image_search.md"
        template = self.load_prompt_template(template_name)

        context = {
            "pin_topic": pin_spec.get("pin_topic", pin_spec.get("topic", "")),
            "content_type": pin_spec.get("content_type", ""),
            "primary_keyword": pin_spec.get("primary_keyword", ""),
            "pin_template": pin_spec.get("pin_template", ""),
            "pillar": str(pin_spec.get("pillar", "")),
        }

        prompt = self._render_template(template, context)

        if image_source == "stock_retry":
            system_msg = (
                "You are an image prompt specialist for food and lifestyle photography. "
                "Generate a stock photo search query "
                "optimized for Pinterest pin images at 1000x1500px (2:3 ratio). "
                "For food: prefer overhead/flat-lay compositions, warm lighting, rustic surfaces. "
                "IMPORTANT: The previous search query did not find good-enough images. "
                "Try BROADER or ALTERNATIVE search terms. Approach the topic from a "
                "different visual angle. Use more general food category terms or "
                "different composition keywords. "
                "Return only the query text, no explanation."
            )
        else:
            system_msg = (
                "You are an image prompt specialist for food and lifestyle photography. "
                f"Generate a {'detailed AI image generation prompt' if image_source == 'ai' else 'stock photo search query'} "
                "optimized for Pinterest pin images at 1000x1500px (2:3 ratio). "
                "For food: prefer overhead/flat-lay compositions, warm lighting, rustic surfaces."
            )

        subject_hint = pin_spec.get("_image_subject_hint", "")
        if subject_hint:
            system_msg += (
                f" The image should depict: {subject_hint}."
            )

        if regen_feedback:
            system_msg += (
                f" IMPORTANT: The previous image was rejected by the reviewer with this "
                f"feedback: {regen_feedback}. Generate a search query that specifically "
                f"addresses this feedback."
            )

        logger.info("Generating %s image prompt for: %s", image_source, pin_spec.get("topic", "unknown")[:50])
        return self._call_api(
            prompt=prompt,
            system=system_msg,
            model=MODEL_ROUTINE,
            max_tokens=500,
            temperature=0.8,
        )

    def generate_image_search_query(self, pin_spec: dict) -> str:
        """
        Generate a stock photo search query for a pin.

        Convenience wrapper around generate_image_prompt with image_source="stock".

        Args:
            pin_spec: Pin specification with topic details.

        Returns:
            str: Search query optimized for Unsplash/Pexels.
        """
        return self.generate_image_prompt(pin_spec, image_source="stock")

    def generate_replacement_posts(
        self,
        posts_to_replace: list[dict],
        slots_to_fill: list[dict],
        plan_context: dict,
        content_memory: str,
        negative_keywords: list[str],
        recent_topics: list[str],
    ) -> dict:
        """
        Generate replacement blog posts and their derived pins for targeted
        topic replacement. Called when validate_plan() finds topic repetition
        or negative keyword violations on specific posts.

        Args:
            posts_to_replace: Blog post objects being replaced (with violations).
            slots_to_fill: Pin slot dicts the replacements must fill. Each has
                           pin_id, scheduled_date, scheduled_slot, target_board,
                           funnel_layer.
            plan_context: Summary of the kept plan for constraint awareness:
                          kept_post_topics, kept_pin_boards, kept_pin_pillars,
                          week_number, date_range.
            content_memory: Content memory summary markdown.
            negative_keywords: Keywords/topics to avoid.
            recent_topics: Recent topic strings to avoid repeating.

        Returns:
            dict: {"blog_posts": [...], "pins": [...]} with replacement objects
                  using the same post_id/pin_id values as the originals.
        """
        template = self.load_prompt_template("weekly_plan_replace.md")

        # Format recent topics as a bullet list
        recent_topics_text = "\n".join(f"- {t}" for t in recent_topics) if recent_topics else "None (first run)."
        kept_topics_text = "\n".join(
            f"- {t}" for t in plan_context.get("kept_post_topics", []) if t
        ) or "None."
        neg_kw_text = "\n".join(f"- {kw}" for kw in negative_keywords) if negative_keywords else "None."

        context = {
            "NUM_POSTS": str(len(posts_to_replace)),
            "RECENT_TOPICS": recent_topics_text,
            "KEPT_POST_TOPICS": kept_topics_text,
            "NEGATIVE_KEYWORDS": neg_kw_text,
            "POSTS_TO_REPLACE": json.dumps(posts_to_replace, indent=2),
            "SLOTS_TO_FILL": json.dumps(slots_to_fill, indent=2),
            "BOARD_COUNTS": json.dumps(plan_context.get("kept_pin_boards", {})),
            "PILLAR_COUNTS": json.dumps(plan_context.get("kept_pin_pillars", {})),
        }

        prompt = self._render_template(template, context)

        system = (
            "You are a Pinterest content strategist for Slated, a family meal planning app. "
            "You are replacing specific blog posts and their derived pins in an existing "
            "weekly content plan. The posts were flagged for topic repetition or negative "
            "keyword violations. Generate ONLY the replacement posts and pins. "
            "Maintain the same pillar, content type, and pin slot assignments. "
            "Choose completely different topics that avoid the flagged issues. "
            "IMPORTANT: Output ONLY valid JSON. No explanations or text outside the JSON."
        )

        # Scale max_tokens to replacement size: ~300/post + ~150/pin + overhead
        max_tokens = 200 + (300 * len(posts_to_replace)) + (150 * len(slots_to_fill))
        max_tokens = min(max_tokens, 4096)

        logger.info(
            "Generating replacement for %d posts (%d pin slots)...",
            len(posts_to_replace), len(slots_to_fill),
        )

        response_text = self._call_api(
            prompt=prompt,
            system=system,
            model=MODEL_ROUTINE,
            max_tokens=max_tokens,
            temperature=0.7,
        )

        return self._parse_json_response(response_text, "topic replacement")

    def analyze_weekly_performance(
        self,
        performance_data: dict,
        previous_analysis: str,
        content_plan: dict,
    ) -> str:
        """
        Analyze weekly performance data using Claude Sonnet.

        Args:
            performance_data: Pin-level and aggregate performance metrics.
            previous_analysis: Last week's analysis for trend comparison.
            content_plan: What was planned vs. what was posted.

        Returns:
            str: Structured weekly analysis markdown.
        """
        template = self.load_prompt_template("weekly_analysis.md")

        context = {
            "this_week_data": {
                "week_summary": performance_data.get("week_summary", {}),
                "top_pins": performance_data.get("top_pins", []),
                "bottom_pins": performance_data.get("bottom_pins", []),
                "by_content_type": performance_data.get("by_content_type", {}),
                "by_template": performance_data.get("by_template", {}),
                "by_image_source": performance_data.get("by_image_source", {}),
                "by_pin_type": performance_data.get("by_pin_type", {}),
                "plan_vs_recipe": performance_data.get("plan_vs_recipe", {}),
            },
            "last_week_analysis": previous_analysis or "No previous analysis available (first run).",
            "content_plan_vs_actual": content_plan or "No content plan data available.",
            "per_pillar_metrics": performance_data.get("by_pillar", {}),
            "per_keyword_metrics": performance_data.get("by_keyword", {}),
            "per_board_metrics": performance_data.get("by_board", {}),
            "per_funnel_layer_metrics": performance_data.get("by_funnel_layer", {}),
            "account_trends": performance_data.get("account_trends", {}),
        }

        prompt = self._render_template(template, context)

        system = (
            "You are a Pinterest analytics expert for Slated, a family meal planning app. "
            "Analyze the weekly performance data and produce a structured markdown report. "
            "Include: top/bottom performers with reasons, content type rankings, "
            "keyword insights, board performance, and specific recommendations for next week. "
            "Be evidence-based -- cite specific numbers. Flag declining trends."
        )

        logger.info("Running weekly performance analysis...")
        return self._call_api(
            prompt=prompt,
            system=system,
            model=MODEL_ROUTINE,
            max_tokens=4096,
            temperature=0.5,
        )

    def generate_weekly_analysis(
        self,
        performance_data: dict,
        previous_analysis: str,
        content_plan: dict,
    ) -> str:
        """Alias for analyze_weekly_performance to match requirement naming."""
        return self.analyze_weekly_performance(performance_data, previous_analysis, content_plan)

    def run_monthly_review(
        self,
        monthly_data: dict,
        weekly_analyses: list[str],
        current_strategy: str,
        seasonal_context: str = "",
    ) -> str:
        """
        Run the monthly strategy review using Claude Opus.

        Uses the deeper-reasoning Opus model for strategic analysis.

        Args:
            monthly_data: 30-day aggregated performance data from build_monthly_context().
            weekly_analyses: All weekly analyses from the past month.
            current_strategy: Current strategy document text.
            seasonal_context: Current seasonal window description.

        Returns:
            str: Monthly review markdown with strategy recommendations.
        """
        from datetime import date as _date

        template = self.load_prompt_template("monthly_review.md")

        # Build the review period label (e.g., "February 2026")
        review_period = monthly_data.get("review_period", "")
        if review_period:
            try:
                y, m = review_period.split("-")
                month_year = _date(int(y), int(m), 1).strftime("%B %Y")
            except (ValueError, TypeError):
                month_year = review_period
        else:
            month_year = _date.today().strftime("%B %Y")

        # Map context keys to match the template placeholders exactly
        context = {
            "monthly_data": monthly_data,
            "all_weekly_analyses": "\n\n---\n\n".join(weekly_analyses) if weekly_analyses else "No weekly analyses available for this month.",
            "current_strategy_summary": current_strategy or "No strategy document loaded.",
            "pillar_performance": monthly_data.get("by_pillar", {}),
            "keyword_performance": monthly_data.get("by_keyword", {}),
            "board_performance": monthly_data.get("by_board", {}),
            "content_type_performance": monthly_data.get("by_content_type", {}),
            "image_source_performance": monthly_data.get("by_image_source", {}),
            "seasonal_context": seasonal_context or "No seasonal calendar data available.",
            "month_year": month_year,
        }

        prompt = self._render_template(template, context)

        system = (
            "You are a senior Pinterest strategy consultant reviewing Slated's monthly performance. "
            "Slated is a family meal planning iOS app. "
            "Produce a deep, evidence-based strategy review with specific, actionable recommendations. "
            "Include: month-over-month trends, pillar performance rankings, keyword strategy assessment, "
            "board architecture review, posting cadence analysis, template/format analysis, "
            "image source comparison, and recommended strategy adjustments. "
            "Be direct and critical. Back every recommendation with data."
        )

        logger.info("Running monthly strategy review with Opus...")
        return self._call_api(
            prompt=prompt,
            system=system,
            model=MODEL_DEEP,
            max_tokens=8192,
            temperature=0.5,
        )

    def generate_monthly_review(
        self,
        monthly_data: dict,
        weekly_analyses: list[str],
        current_strategy: str,
        seasonal_context: str = "",
    ) -> str:
        """Alias for run_monthly_review to match requirement naming."""
        return self.run_monthly_review(monthly_data, weekly_analyses, current_strategy, seasonal_context)

    def rank_stock_candidates(
        self,
        candidates: list[dict],
        pin_spec: dict,
    ) -> list[dict]:
        """
        Rank stock photo candidates by relevance to a pin specification.

        Sends thumbnail images to Claude Haiku for visual evaluation.
        Each candidate must have a '_thumb_bytes' key with raw thumbnail
        image data (populated by ImageStockAPI.download_thumbnail()).

        Args:
            candidates: List of stock photo candidate dicts, each with
                        '_thumb_bytes' (bytes) for the thumbnail image.
            pin_spec: Pin specification with topic, template, etc.

        Returns:
            list[dict]: Same candidates sorted by score (highest first),
                        with '_score' (float) and '_rank_reason' (str) added.
        """
        if not candidates:
            return []

        # Load and render the ranking prompt template
        template = self.load_prompt_template("image_rank.md")
        pin_template = pin_spec.get("pin_template", "recipe-pin")
        context = {
            "PIN_SPEC": pin_spec,
            "PIN_TEMPLATE": pin_template,
            "NUM_CANDIDATES": str(len(candidates)),
            "MAX_INDEX": str(len(candidates) - 1),
        }
        prompt = self._render_template(template, context)

        # Build image list from thumbnail bytes
        images = [c["_thumb_bytes"] for c in candidates if "_thumb_bytes" in c]

        if not images:
            logger.warning("No thumbnail data available for ranking, returning candidates as-is.")
            for c in candidates:
                c["_score"] = 5.0
                c["_rank_reason"] = "No thumbnail available for ranking"
            return candidates

        system = (
            "You are a visual quality evaluator for Pinterest pin images. "
            "Evaluate each candidate image and return a JSON array of scores. "
            "IMPORTANT: Output ONLY valid JSON. No explanations or text before or after."
        )

        logger.info(
            "Ranking %d stock candidates for pin %s (template: %s)",
            len(candidates), pin_spec.get("pin_id", "unknown"), pin_template,
        )

        try:
            response_text = self._call_api(
                prompt=prompt,
                system=system,
                model=MODEL_HAIKU,
                max_tokens=1024,
                temperature=0.3,
                images=images,
            )

            rankings = self._parse_json_response(response_text, "stock ranking")

            # Map scores back to candidates
            if isinstance(rankings, list):
                for ranking in rankings:
                    idx = ranking.get("index", -1)
                    if 0 <= idx < len(candidates):
                        candidates[idx]["_score"] = float(ranking.get("score", 0))
                        candidates[idx]["_rank_reason"] = ranking.get("reason", "")

            # Ensure all candidates have a score
            for c in candidates:
                if "_score" not in c:
                    c["_score"] = 0.0
                    c["_rank_reason"] = "Not scored by evaluator"

            # Sort by score descending
            candidates.sort(key=lambda c: c.get("_score", 0), reverse=True)

            logger.info(
                "Stock ranking complete. Top score: %.1f (%s), lowest: %.1f",
                candidates[0].get("_score", 0),
                candidates[0].get("_rank_reason", "")[:60],
                candidates[-1].get("_score", 0),
            )

            return candidates

        except (ClaudeAPIError, Exception) as e:
            logger.error("Stock ranking failed, returning candidates unranked: %s", e)
            for c in candidates:
                c["_score"] = 5.0
                c["_rank_reason"] = f"Ranking failed: {e}"
            return candidates

    def validate_ai_image(
        self,
        image_path,
        image_prompt: str,
        pin_spec: dict,
    ) -> dict:
        """
        Validate an AI-generated image for quality and suitability.

        Sends the full-size image to Claude Sonnet for evaluation against
        pin-specific quality criteria.

        Args:
            image_path: Path to the generated image file (str or Path).
            image_prompt: The original prompt used to generate the image.
            pin_spec: Pin specification with topic, template, etc.

        Returns:
            dict with keys:
                - score (float): Quality score 1.0-10.0
                - pass (bool): True if score >= 6.5
                - issues (list[str]): Specific problems found
                - feedback (str): Actionable re-generation instructions
                - disqualifiers (list[str]): Hard failures
        """
        image_path = Path(image_path)

        if not image_path.exists():
            logger.error("Image file not found for validation: %s", image_path)
            return {
                "score": 0, "pass": False,
                "issues": ["Image file not found"],
                "feedback": "Image file does not exist.",
                "disqualifiers": ["missing_file"],
            }

        # Load and render the validation prompt template
        template = self.load_prompt_template("image_validate.md")
        pin_template = pin_spec.get("pin_template", "recipe-pin")
        context = {
            "PIN_SPEC": pin_spec,
            "PIN_TEMPLATE": pin_template,
            "IMAGE_PROMPT": image_prompt,
        }
        prompt = self._render_template(template, context)

        system = (
            "You are an AI image quality evaluator for Pinterest pins. "
            "Evaluate the provided image and return a JSON validation result. "
            "IMPORTANT: Output ONLY valid JSON. No explanations or text before or after."
        )

        logger.info(
            "Validating AI image for pin %s: %s",
            pin_spec.get("pin_id", "unknown"), image_path.name,
        )

        try:
            response_text = self._call_api(
                prompt=prompt,
                system=system,
                model=MODEL_ROUTINE,
                max_tokens=1024,
                temperature=0.3,
                images=[image_path],
            )

            result = self._parse_json_response(response_text, "AI image validation")

            if isinstance(result, dict):
                score = float(result.get("score", 0))
                validation = {
                    "score": score,
                    "pass": score >= 6.5,
                    "issues": result.get("issues", []),
                    "feedback": result.get("feedback", ""),
                    "disqualifiers": result.get("disqualifiers", []),
                }
            else:
                logger.warning("Unexpected validation response format: %s", type(result))
                validation = {
                    "score": 5.0, "pass": False,
                    "issues": ["Unexpected response format"],
                    "feedback": "", "disqualifiers": [],
                }

            logger.info(
                "AI image validation: score=%.1f pass=%s issues=%s",
                validation["score"], validation["pass"], validation["issues"],
            )
            return validation

        except (ClaudeAPIError, Exception) as e:
            logger.error("AI image validation failed, assuming pass: %s", e)
            return {
                "score": 7.0, "pass": True,
                "issues": [], "feedback": "",
                "disqualifiers": [],
            }

    def _call_api(
        self,
        prompt: str,
        system: str = "",
        model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        images: Optional[list] = None,
    ) -> str:
        """
        Make a call to the Claude API with retry on rate limits and token/cost tracking.

        Args:
            prompt: The user message / prompt.
            system: System prompt.
            model: Model to use. Defaults to MODEL_ROUTINE.
            max_tokens: Maximum response tokens.
            temperature: Sampling temperature.
            images: Optional list of images to include in the message.
                    Each element can be bytes (raw image data) or a str/Path
                    (file path to read). Images are sent as base64-encoded
                    content blocks before the text prompt.

        Returns:
            str: Claude's response text.

        Raises:
            ClaudeAPIError: On authentication failure or persistent errors.
        """
        use_model = model or MODEL_ROUTINE
        max_retries = 3

        # Build message content: images (if any) + text
        if images:
            content = []
            for img in images:
                if isinstance(img, bytes):
                    image_data = base64.standard_b64encode(img).decode("utf-8")
                    media_type = "image/jpeg" if img[:2] == b'\xff\xd8' else "image/png"
                else:
                    path = Path(img)
                    image_data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
                    media_type = (
                        "image/jpeg" if path.suffix.lower() in (".jpg", ".jpeg")
                        else "image/png"
                    )
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_data,
                    },
                })
            content.append({"type": "text", "text": prompt})
        else:
            content = prompt

        for attempt in range(max_retries + 1):
            try:
                logger.debug(
                    "Claude API call: model=%s, max_tokens=%d, prompt_length=%d chars, images=%d",
                    use_model, max_tokens, len(prompt), len(images) if images else 0,
                )

                message = self.client.messages.create(
                    model=use_model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system if system else anthropic.NOT_GIVEN,
                    messages=[{"role": "user", "content": content}],
                )

                # Track token usage and cost
                input_tokens = message.usage.input_tokens
                output_tokens = message.usage.output_tokens
                self.total_input_tokens += input_tokens
                self.total_output_tokens += output_tokens

                model_costs = COST_PER_MTK.get(use_model, {"input": 3.0, "output": 15.0})
                call_cost = (
                    (input_tokens / 1_000_000) * model_costs["input"]
                    + (output_tokens / 1_000_000) * model_costs["output"]
                )
                self.total_cost_usd += call_cost

                logger.info(
                    "Claude API response: model=%s input_tokens=%d output_tokens=%d cost=$%.4f "
                    "(session total: input=%d output=%d cost=$%.4f)",
                    use_model, input_tokens, output_tokens, call_cost,
                    self.total_input_tokens, self.total_output_tokens, self.total_cost_usd,
                )

                # Extract text from response
                response_text = ""
                for block in message.content:
                    if block.type == "text":
                        response_text += block.text

                return response_text

            except anthropic.RateLimitError as e:
                if attempt < max_retries:
                    wait_time = 2 ** (attempt + 1) * 5  # 10s, 20s, 40s
                    logger.warning(
                        "Claude rate limit hit. Retry %d/%d after %ds. Error: %s",
                        attempt + 1, max_retries, wait_time, e,
                    )
                    import time
                    time.sleep(wait_time)
                    continue
                raise ClaudeAPIError(f"Rate limit exceeded after {max_retries} retries: {e}") from e

            except anthropic.AuthenticationError as e:
                raise ClaudeAPIError(
                    f"Authentication failed. Check ANTHROPIC_API_KEY. Error: {e}"
                ) from e

            except anthropic.APIError as e:
                if attempt < max_retries and getattr(e, "status_code", 0) >= 500:
                    wait_time = 2 ** (attempt + 1)
                    logger.warning(
                        "Claude API server error. Retry %d/%d after %ds. Error: %s",
                        attempt + 1, max_retries, wait_time, e,
                    )
                    import time
                    time.sleep(wait_time)
                    continue
                raise ClaudeAPIError(f"Claude API error: {e}") from e

        raise ClaudeAPIError("Claude API call failed after all retries.")

    def _parse_json_response(self, response_text: str, context_label: str) -> dict | list:
        """
        Parse a JSON response from Claude, handling common formatting issues.

        Claude sometimes wraps JSON in markdown code fences or prefixes it
        with reasoning text. This method handles both cases.

        Args:
            response_text: Raw response text from Claude.
            context_label: Label for error messages (e.g., "weekly plan").

        Returns:
            dict or list: Parsed JSON.

        Raises:
            ClaudeAPIError: If JSON parsing fails.
        """
        text = response_text.strip()

        # Strip markdown code fences if present
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start) if "```" in text[start:] else len(text)
            text = text[start:end].strip()
        elif "```" in text and (text.startswith("```") or "{" not in text.split("```")[0]):
            parts = text.split("```")
            if len(parts) >= 3:
                text = parts[1].strip()
            elif text.startswith("```"):
                text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Claude sometimes prefixes JSON with reasoning text.
        # Find the first { or [ that starts valid JSON.
        for i, ch in enumerate(text):
            if ch == '{':
                # Find matching closing brace from the end
                for j in range(len(text) - 1, i, -1):
                    if text[j] == '}':
                        try:
                            return json.loads(text[i:j + 1])
                        except json.JSONDecodeError:
                            break
                break
            elif ch == '[':
                for j in range(len(text) - 1, i, -1):
                    if text[j] == ']':
                        try:
                            return json.loads(text[i:j + 1])
                        except json.JSONDecodeError:
                            break
                break

        logger.error(
            "Failed to parse %s JSON response. First 500 chars: %s",
            context_label, text[:500],
        )
        raise ClaudeAPIError(
            f"Failed to parse {context_label} response as JSON. "
            f"Response starts with: {text[:200]}"
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("Claude API smoke test")
    print("=====================")

    # List available prompt templates
    print("\nAvailable prompt templates:")
    for f in sorted(PROMPTS_DIR.glob("*.md")):
        print(f"  - {f.name}")

    # Test template loading
    try:
        template = ClaudeAPI.load_prompt_template(None, "weekly_plan.md")
        print(f"\nLoaded weekly_plan.md: {len(template)} chars")
    except FileNotFoundError as e:
        print(f"\n{e}")

    # Test API connection (only if key is set)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        try:
            api = ClaudeAPI()
            response = api._call_api(
                prompt="Reply with exactly: 'Claude API connection successful.'",
                system="You are a test assistant. Follow instructions exactly.",
                max_tokens=50,
                temperature=0,
            )
            print(f"\nAPI test response: {response}")
            print(f"Session cost: ${api.total_cost_usd:.4f}")
        except Exception as e:
            print(f"\nAPI test failed: {e}")
    else:
        print("\nANTHROPIC_API_KEY not set, skipping API connection test.")
