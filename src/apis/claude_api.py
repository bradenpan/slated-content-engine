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

import os
import json
import logging
from pathlib import Path
from typing import Optional

import anthropic

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"
STRATEGY_DIR = Path(__file__).parent.parent.parent / "strategy"

# Model selection -- using the latest model IDs
MODEL_ROUTINE = "claude-sonnet-4-20250514"
MODEL_DEEP = "claude-opus-4-20250514"

# Approximate costs per million tokens (for cost tracking)
COST_PER_MTK = {
    MODEL_ROUTINE: {"input": 3.0, "output": 15.0},
    MODEL_DEEP: {"input": 15.0, "output": 75.0},
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
            }

            prompt = self._render_template(template, context)

            system = (
                "You are a Pinterest SEO copywriter for Slated, a family meal planning app. "
                "Generate pin copy for each pin specification. Return valid JSON: an array "
                "of objects with keys: pin_id, title (max 100 chars), description (250-500 chars), "
                "alt_text (max 500 chars), text_overlay (6-8 words). "
                "Follow Pinterest SEO best practices: keywords early, natural language, no hashtags."
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

    def generate_image_prompt(self, pin_spec: dict, image_source: str) -> str:
        """
        Generate either an AI image prompt or stock photo search queries.

        Args:
            pin_spec: Pin specification with topic, template type, etc.
            image_source: "ai" for AI image prompt, "stock" for search queries.

        Returns:
            str: AI image generation prompt or stock photo search query.
        """
        template_name = "image_prompt.md" if image_source == "ai" else "image_search.md"
        template = self.load_prompt_template(template_name)

        context = {
            "PIN_SPEC": pin_spec,
            "IMAGE_SOURCE": image_source,
        }

        prompt = self._render_template(template, context)

        system_msg = (
            "You are an image prompt specialist for food and lifestyle photography. "
            f"Generate a {'detailed AI image generation prompt' if image_source == 'ai' else 'stock photo search query'} "
            "optimized for Pinterest pin images at 1000x1500px (2:3 ratio). "
            "For food: prefer overhead/flat-lay compositions, warm lighting, rustic surfaces. "
            "Return only the prompt/query text, no explanation."
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
            "PERFORMANCE_DATA": performance_data,
            "PREVIOUS_ANALYSIS": previous_analysis,
            "CONTENT_PLAN": content_plan,
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
    ) -> str:
        """
        Run the monthly strategy review using Claude Opus.

        Uses the deeper-reasoning Opus model for strategic analysis.

        Args:
            monthly_data: 30-day aggregated performance data.
            weekly_analyses: All weekly analyses from the past month.
            current_strategy: Current strategy document text.

        Returns:
            str: Monthly review markdown with strategy recommendations.
        """
        template = self.load_prompt_template("monthly_review.md")

        context = {
            "MONTHLY_DATA": monthly_data,
            "WEEKLY_ANALYSES": "\n\n---\n\n".join(weekly_analyses),
            "CURRENT_STRATEGY": current_strategy,
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
    ) -> str:
        """Alias for run_monthly_review to match requirement naming."""
        return self.run_monthly_review(monthly_data, weekly_analyses, current_strategy)

    def _call_api(
        self,
        prompt: str,
        system: str = "",
        model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """
        Make a call to the Claude API with retry on rate limits and token/cost tracking.

        Args:
            prompt: The user message / prompt.
            system: System prompt.
            model: Model to use. Defaults to MODEL_ROUTINE.
            max_tokens: Maximum response tokens.
            temperature: Sampling temperature.

        Returns:
            str: Claude's response text.

        Raises:
            ClaudeAPIError: On authentication failure or persistent errors.
        """
        use_model = model or MODEL_ROUTINE
        max_retries = 3

        for attempt in range(max_retries + 1):
            try:
                logger.debug(
                    "Claude API call: model=%s, max_tokens=%d, prompt_length=%d chars",
                    use_model, max_tokens, len(prompt),
                )

                message = self.client.messages.create(
                    model=use_model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system if system else anthropic.NOT_GIVEN,
                    messages=[{"role": "user", "content": prompt}],
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
