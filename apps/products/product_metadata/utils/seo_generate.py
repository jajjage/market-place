import os
import re
import requests
from typing import List, Set
import json
import logging

logger = logging.getLogger(__name__)


class LocalSEOKeywordService:
    def __init__(self):
        """Initialize the service with keyword templates and modifiers."""
        self.ahrefs_token = os.environ.get("AHREFS_API_TOKEN")

        # Common keyword prefixes and suffixes
        self.prefixes = [
            "buy",
            "best",
            "cheap",
            "affordable",
            "quality",
            "premium",
            "discount",
            "top",
            "good",
            "great",
            "excellent",
            "professional",
            "durable",
            "wholesale",
            "bulk",
            "custom",
            "personalized",
            "branded",
            "original",
        ]

        self.suffixes = [
            "for sale",
            "online",
            "store",
            "shop",
            "deals",
            "offers",
            "price",
            "reviews",
            "comparison",
            "guide",
            "tips",
            "benefits",
            "features",
            "specifications",
            "warranty",
            "delivery",
            "shipping",
            "near me",
        ]

        # Intent-based keywords
        self.buyer_intent = [
            "buy {term}",
            "purchase {term}",
            "order {term}",
            "get {term}",
            "find {term}",
            "shop {term}",
            "{term} store",
            "{term} shop",
        ]

        self.informational_intent = [
            "{term} review",
            "{term} guide",
            "how to use {term}",
            "{term} benefits",
            "{term} features",
            "what is {term}",
            "{term} comparison",
            "{term} vs",
            "best {term}",
        ]

        # Category-specific modifiers
        self.category_modifiers = {
            "electronics": [
                "wireless",
                "bluetooth",
                "smart",
                "digital",
                "portable",
                "rechargeable",
            ],
            "clothing": [
                "cotton",
                "comfortable",
                "stylish",
                "fashion",
                "trendy",
                "casual",
            ],
            "home": ["modern", "decorative", "functional", "space-saving", "elegant"],
            "sports": ["professional", "training", "outdoor", "fitness", "exercise"],
            "beauty": ["natural", "organic", "anti-aging", "moisturizing", "gentle"],
            "food": ["fresh", "organic", "healthy", "gourmet", "homemade", "natural"],
        }

        # Load common words to filter out
        self.stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "up",
            "about",
            "into",
            "through",
            "during",
        }

    def fetch_from_keyword_api(self, seed_term: str) -> List[str]:
        """Fetch keywords from external APIs like Ahrefs."""
        if not self.ahrefs_token:
            return []

        url = "https://apiv2.ahrefs.com/related_terms"
        try:
            resp = requests.get(
                url,
                params={
                    "token": self.ahrefs_token,
                    "target": seed_term,
                    "mode": "phrase_match",
                },
                timeout=30,
            )
            resp.raise_for_status()

            data = resp.json().get("related_terms", [])
            data.sort(key=lambda x: x.get("volume", 0), reverse=True)
            return [item["keyword"] for item in data[:15]]

        except requests.RequestException as e:
            print(f"Error fetching from Ahrefs API: {e}")
            return []

    def fetch_from_free_apis(self, seed_term: str) -> List[str]:
        """Fetch from free keyword APIs."""
        keywords = []

        # Try Google Suggest API (free)
        try:
            suggest_url = "http://suggestqueries.google.com/complete/search"
            params = {"client": "firefox", "q": seed_term}
            resp = requests.get(suggest_url, params=params, timeout=10)
            if resp.status_code == 200:
                suggestions = resp.json()[1]  # Second element contains suggestions
                keywords.extend([s for s in suggestions if len(s) > len(seed_term)])
        except Exception:
            pass

        return keywords[:10]

    def generate_template_keywords(self, seed_term: str, count: int = 10) -> List[str]:
        """Generate keywords using templates and patterns."""
        keywords = set()

        # Clean the seed term
        clean_term = self.clean_term(seed_term)
        words = clean_term.lower().split()

        # 1. Prefix + term combinations
        for prefix in self.prefixes[:8]:
            keywords.add(f"{prefix} {clean_term}")

        # 2. Term + suffix combinations
        for suffix in self.suffixes[:8]:
            keywords.add(f"{clean_term} {suffix}")

        # 3. Buyer intent keywords
        for pattern in self.buyer_intent:
            keywords.add(pattern.format(term=clean_term))

        # 4. Informational intent keywords
        for pattern in self.informational_intent:
            keywords.add(pattern.format(term=clean_term))

        # 5. Long-tail variations
        keywords.update(self.generate_longtail_variations(clean_term))

        # 6. Category-specific keywords
        category = self.detect_category(clean_term)
        if category:
            modifiers = self.category_modifiers[category]
            for modifier in modifiers[:5]:
                keywords.add(f"{modifier} {clean_term}")
                keywords.add(f"{clean_term} {modifier}")

        # Convert to list and limit
        return list(keywords)[:count]

    def generate_longtail_variations(self, term: str) -> Set[str]:
        """Generate long-tail keyword variations."""
        variations = set()

        # Question-based long-tails
        question_words = ["what", "how", "where", "when", "why", "which"]
        for qword in question_words:
            variations.add(f"{qword} is the best {term}")
            variations.add(f"{qword} to buy {term}")
            variations.add(f"{qword} to choose {term}")

        # Location-based
        variations.add(f"{term} near me")
        variations.add(f"{term} in my area")
        variations.add(f"local {term}")

        # Price-related
        variations.add(f"cheap {term} under $50")
        variations.add(f"budget {term}")
        variations.add(f"expensive {term}")

        # Brand/quality related
        variations.add(f"branded {term}")
        variations.add(f"high quality {term}")
        variations.add(f"professional grade {term}")

        return variations

    def detect_category(self, term: str) -> str:
        """Simple category detection based on keywords."""
        term_lower = term.lower()

        if any(
            word in term_lower
            for word in ["phone", "laptop", "lenovo", "camera", "headphones", "speaker"]
        ):
            return "electronics"
        elif any(
            word in term_lower
            for word in ["shirt", "dress", "shoes", "jacket", "pants"]
        ):
            return "clothing"
        elif any(
            word in term_lower
            for word in ["chair", "table", "lamp", "decor", "furniture"]
        ):
            return "home"
        elif any(
            word in term_lower
            for word in ["ball", "equipment", "fitness", "exercise", "gym"]
        ):
            return "sports"
        elif any(
            word in term_lower
            for word in ["cream", "lotion", "makeup", "skincare", "beauty"]
        ):
            return "beauty"
        elif any(
            word in term_lower
            for word in ["organic", "food", "snack", "drink", "cooking"]
        ):
            return "food"

        return None

    def clean_term(self, term: str) -> str:
        """Clean and normalize the input term."""
        # Remove extra spaces and special characters
        cleaned = re.sub(r"[^\w\s-]", "", term)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def generate_semantic_variations(self, term: str) -> List[str]:
        """Generate semantic variations using word associations."""
        variations = []
        words = term.lower().split()

        # Simple synonym mapping (you could expand this)
        synonyms = {
            "buy": ["purchase", "get", "acquire", "order"],
            "cheap": ["affordable", "budget", "low-cost", "inexpensive"],
            "good": ["quality", "excellent", "great", "top"],
            "fast": ["quick", "rapid", "speedy", "instant"],
            "new": ["latest", "modern", "recent", "updated"],
            "small": ["compact", "mini", "portable", "tiny"],
            "big": ["large", "huge", "massive", "giant"],
        }

        for word in words:
            if word in synonyms:
                for synonym in synonyms[word]:
                    new_term = term.replace(word, synonym)
                    variations.append(new_term)

        return variations

    def generate_competitor_based_keywords(self, term: str) -> List[str]:
        """Generate keywords based on common competitor patterns."""
        competitors = []

        # Generic competitor patterns
        patterns = [
            f"{term} vs competitors",
            f"best {term} brands",
            f"top {term} companies",
            f"{term} alternatives",
            f"compare {term}",
            f"{term} comparison chart",
        ]

        return patterns

    def generate_keywords(self, seed_term: str, count: int = 10) -> List[str]:
        """Main method to generate keywords using all local methods."""
        all_keywords = set()

        # 1. Template-based keywords (primary method)
        template_keywords = self.generate_template_keywords(seed_term, count)
        all_keywords.update(template_keywords)

        # 2. Semantic variations
        semantic_keywords = self.generate_semantic_variations(seed_term)
        all_keywords.update(semantic_keywords)

        # 3. Competitor-based keywords
        competitor_keywords = self.generate_competitor_based_keywords(seed_term)
        all_keywords.update(competitor_keywords)

        # 4. Try free APIs
        try:
            free_api_keywords = self.fetch_from_free_apis(seed_term)
            all_keywords.update(free_api_keywords)
        except Exception as e:
            logger.error(f"Error fetching free API keywords: {str(e)}")
            pass

        # # 5. Try paid APIs if available
        # try:
        #     api_keywords = self.fetch_from_keyword_api(seed_term)
        #     all_keywords.update(api_keywords)
        # except:
        #     pass

        # Filter and clean results
        final_keywords = []
        for keyword in all_keywords:
            if keyword and len(keyword) > 3 and keyword.lower() != seed_term.lower():
                final_keywords.append(keyword.strip())

        # Remove duplicates while preserving order
        seen = set()
        unique_keywords = []
        for keyword in final_keywords:
            if keyword.lower() not in seen:
                seen.add(keyword.lower())
                unique_keywords.append(keyword)

        return unique_keywords[:count]


# Alternative: File-based keyword generator
class FileBasedKeywordService:
    """Generate keywords from local files/databases."""

    def __init__(self, keywords_file_path: str = None):
        self.keywords_file = keywords_file_path
        self.keyword_database = self.load_keyword_database()

    def load_keyword_database(self) -> dict:
        """Load keywords from a local file."""
        if not self.keywords_file or not os.path.exists(self.keywords_file):
            # Return a basic database if no file exists
            return {
                "modifiers": ["best", "cheap", "quality", "buy", "top", "good"],
                "suffixes": ["online", "store", "deals", "reviews", "guide"],
                "categories": {"general": ["product", "item", "goods", "merchandise"]},
            }

        try:
            with open(self.keywords_file, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def generate_keywords(self, seed_term: str, count: int = 10) -> List[str]:
        """Generate keywords from file-based database."""
        keywords = []

        modifiers = self.keyword_database.get("modifiers", [])
        suffixes = self.keyword_database.get("suffixes", [])

        # Generate combinations
        for modifier in modifiers:
            keywords.append(f"{modifier} {seed_term}")

        for suffix in suffixes:
            keywords.append(f"{seed_term} {suffix}")

        return keywords[:count]
