import logging
from typing import List, Optional, Dict, Any
from google import genai
import re

from safetrade.settings.utils.get_env import env

logger = logging.getLogger("metadata_performance")


class GoogleGenAISEOKeywordService:
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the service with Google GenAI."""
        self.api_key = api_key or env.get("GOOGLE_API_KEY")

        if not self.api_key:
            raise ValueError(
                "Google API key is required. Set GOOGLE_API_KEY environment variable or pass api_key parameter."
            )

        self.client = genai.Client(api_key=self.api_key)

        # Keyword intent categories
        self.intent_types = {
            "commercial": "Commercial intent (buy, purchase, order, shop)",
            "informational": "Informational intent (how to, what is, guide, tips)",
            "navigational": "Navigational intent (brand searches, specific sites)",
            "transactional": "Transactional intent (deals, discount, price, compare)",
            "local": "Local intent (near me, local, in [city])",
        }

    def generate_keywords(
        self,
        seed_term: str,
        count: int = 20,
        intent_filter: Optional[str] = None,
        include_long_tail: bool = True,
        target_audience: Optional[str] = None,
        business_type: Optional[str] = None,
    ) -> List[str]:
        """
        Generate SEO keywords using Google GenAI.

        Args:
            seed_term: The main keyword/product to generate variations for
            count: Number of keywords to generate
            intent_filter: Filter by intent type ('commercial', 'informational', etc.)
            include_long_tail: Whether to include long-tail keywords
            target_audience: Target audience description
            business_type: Type of business (e.g., 'e-commerce', 'service', 'blog')

        Returns:
            List of generated keywords
        """
        try:
            prompt = self._build_prompt(
                seed_term,
                count,
                intent_filter,
                include_long_tail,
                target_audience,
                business_type,
            )

            response = self.client.models.generate_content(
                model="gemini-2.0-flash", contents=prompt
            )

            keywords = self._parse_response(response.text)

            # Clean and validate keywords
            cleaned_keywords = self._clean_keywords(keywords, seed_term)

            return cleaned_keywords[:count]

        except Exception as e:
            logger.error(f"Error generating keywords: {str(e)}")
            return self._fallback_keywords(seed_term, count)

    def _build_prompt(
        self,
        seed_term: str,
        count: int,
        intent_filter: Optional[str],
        include_long_tail: bool,
        target_audience: Optional[str],
        business_type: Optional[str],
    ) -> str:
        """Build the prompt for Google GenAI."""
        variants = []

        prompt = f"""You are an expert SEO keyword researcher. Generate {count} high-value SEO keywords based on the seed term: "{seed_term}"

        Requirements:
        - Generate keywords with different search intents
        - Include variations with different word orders
        - Focus on keywords that real users would search for
        - Include both short-tail and long-tail keywords
        - Consider commercial viability and search volume potential
        - Add variant-specific keywords: {', '.join(variants)}

        """

        if intent_filter and intent_filter in self.intent_types:
            prompt += f"- Focus primarily on {self.intent_types[intent_filter]}\n"

        if not include_long_tail:
            prompt += "- Focus on short-tail keywords (1-3 words)\n"
        else:
            prompt += "- Include long-tail keywords (4+ words) for better targeting\n"

        if target_audience:
            prompt += f"- Target audience: {target_audience}\n"

        if business_type:
            prompt += f"- Business type: {business_type}\n"

        prompt += f"""
            Include these types of keywords:
            1. Commercial intent: "buy {seed_term}", "best {seed_term}", "{seed_term} for sale"
            2. Informational intent: "how to use {seed_term}", "{seed_term} guide", "what is {seed_term}"
            3. Comparison keywords: "{seed_term} vs", "best {seed_term} brands"
            4. Local keywords: "{seed_term} near me", "local {seed_term}"
            5. Problem-solving: "{seed_term} for [problem]", "{seed_term} benefits"
            6. Modifier combinations: "cheap {seed_term}", "professional {seed_term}", "quality {seed_term}"

            Format your response as a simple list, one keyword per line, without numbering or bullet points.
            Focus on keywords that would actually be searched by potential customers.
            """

        return prompt

    def _parse_response(self, response_text: str) -> List[str]:
        """Parse the GenAI response into a list of keywords."""
        keywords = []

        # Split by lines and clean
        lines = response_text.strip().split("\n")

        for line in lines:
            # Remove common prefixes like "1.", "-", "*", etc.
            cleaned_line = re.sub(r"^[\d\.\-\*\s]+", "", line.strip())

            if cleaned_line and len(cleaned_line) > 2:
                keywords.append(cleaned_line)

        return keywords

    def _clean_keywords(self, keywords: List[str], seed_term: str) -> List[str]:
        """Clean and validate the generated keywords."""
        cleaned = []
        seen = set()

        for keyword in keywords:
            # Basic cleaning
            keyword = keyword.strip().lower()
            keyword = re.sub(
                r"[^\w\s\-]", "", keyword
            )  # Remove special chars except hyphens
            keyword = re.sub(r"\s+", " ", keyword)  # Normalize spaces

            # Skip if too short, too long, or already seen
            if len(keyword) < 3 or len(keyword) > 100 or keyword in seen:
                continue

            # Skip if identical to seed term
            if keyword == seed_term.lower():
                continue

            seen.add(keyword)
            cleaned.append(keyword)

        return cleaned

    def _fallback_keywords(self, seed_term: str, count: int) -> List[str]:
        """Generate basic keywords if GenAI fails."""
        prefixes = ["buy", "best", "cheap", "quality", "professional", "top", "good"]
        suffixes = ["online", "store", "deals", "reviews", "guide", "tips", "near me"]

        keywords = []

        # Generate prefix combinations
        for prefix in prefixes:
            keywords.append(f"{prefix} {seed_term}")

        # Generate suffix combinations
        for suffix in suffixes:
            keywords.append(f"{seed_term} {suffix}")

        # Add some long-tail variations
        keywords.extend(
            [
                f"how to choose {seed_term}",
                f"what is the best {seed_term}",
                f"where to buy {seed_term}",
                f"{seed_term} comparison",
                f"{seed_term} benefits",
            ]
        )

        return keywords[:count]

    def analyze_keyword_intent(self, keyword: str) -> Dict[str, Any]:
        """Analyze the search intent of a keyword using GenAI."""
        prompt = f"""Analyze the search intent for this keyword: "{keyword}"

        Provide analysis in the following format:
        Intent Type: [commercial/informational/navigational/transactional/local]
        Search Volume Potential: [high/medium/low]
        Competition Level: [high/medium/low]
        Commercial Value: [high/medium/low]
        User Journey Stage: [awareness/consideration/decision]
        Brief Explanation: [2-3 sentences about why users would search this]
        """

        try:
            response = self.model.generate_content(prompt)
            return self._parse_intent_analysis(response.text)
        except Exception as e:
            logger.error(f"Error analyzing intent: {str(e)}")
            return {"error": str(e)}

    def _parse_intent_analysis(self, response_text: str) -> Dict[str, Any]:
        """Parse the intent analysis response."""
        analysis = {}

        lines = response_text.strip().split("\n")
        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                analysis[key.strip()] = value.strip()

        return analysis

    def generate_keyword_clusters(
        self, seed_term: str, num_clusters: int = 5
    ) -> Dict[str, List[str]]:
        """Generate keyword clusters organized by topics."""
        prompt = f"""Create {num_clusters} keyword clusters for the main term: "{seed_term}"

        Each cluster should focus on a specific aspect or subtopic. For each cluster:
        1. Give it a descriptive name
        2. List 5-8 related keywords

        Format as:
        Cluster Name 1:
        - keyword 1
        - keyword 2
        ...

        Cluster Name 2:
        - keyword 1
        - keyword 2
        ...
        Focus on creating clusters that would be useful for content planning and SEO strategy.
        """

        try:
            response = self.model.generate_content(prompt)
            return self._parse_clusters(response.text)
        except Exception as e:
            logger.error(f"Error generating clusters: {str(e)}")
            return {}

    def _parse_clusters(self, response_text: str) -> Dict[str, List[str]]:
        """Parse the keyword clusters response."""
        clusters = {}
        current_cluster = None

        lines = response_text.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if this is a cluster name (doesn't start with -)
            if not line.startswith("-") and ":" in line:
                current_cluster = line.replace(":", "").strip()
                clusters[current_cluster] = []
            elif line.startswith("-") and current_cluster:
                keyword = line.replace("-", "").strip()
                if keyword:
                    clusters[current_cluster].append(keyword)

        return clusters
