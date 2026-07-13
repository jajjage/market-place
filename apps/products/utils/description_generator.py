import os
import logging
from typing import List, Optional, Dict, Any
from google import genai
import re

logger = logging.getLogger(__name__)


class GoogleGenAISEODescriptionService:
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the service with Google GenAI."""
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")

        if not self.api_key:
            raise ValueError(
                "Google API key is required. Set GOOGLE_API_KEY environment variable or pass api_key parameter."
            )

        self.client = genai.Client(api_key=self.api_key)

        # Description types
        self.description_types = {
            "short": "Short description (50-100 words)",
            "detailed": "Detailed description (150-300 words)",
            "marketing": "Marketing-focused description with strong CTAs",
            "technical": "Technical specification-focused description",
            "benefits": "Benefits and value proposition focused",
        }

    def generate_description(
        self,
        product_title: str,
        product_info: Dict[str, Any],
        description_type: str = "detailed",
        target_audience: Optional[str] = None,
        tone: str = "professional",
        include_keywords: Optional[List[str]] = None,
        max_length: Optional[int] = None,
    ) -> str:
        """
        Generate SEO-optimized product description using Google GenAI.

        Args:
            product_title: The product title
            product_info: Dictionary containing product details
            description_type: Type of description ('meta', 'short', 'detailed', 'marketing', 'technical', 'benefits')
            target_audience: Target audience description
            tone: Writing tone ('professional', 'casual', 'enthusiastic', 'technical')
            include_keywords: List of keywords to naturally incorporate
            max_length: Maximum character/word length

        Returns:
            Generated description string
        """
        try:
            prompt = self._build_description_prompt(
                product_title,
                product_info,
                description_type,
                target_audience,
                tone,
                include_keywords,
                max_length,
            )

            response = self.client.models.generate_content(
                model="gemini-2.0-flash", contents=prompt
            )
            description = self._clean_description(
                response.text, description_type, max_length
            )
            description = self.optimize_existing_description(
                current_description=description,
                product_title=product_title,
                optimization_goal="seo",
                target_keywords=include_keywords,
            )
            bullet_point = self.generate_product_bullets(
                product_title=product_title,
                product_info=product_info,
                num_bullets=10,
                focus_area="features",
            )

            return f"{description}\n {bullet_point}"

        except Exception as e:
            logger.error(f"Error generating description: {str(e)}")
            return self._fallback_description(
                product_title, product_info, description_type
            )

    def _build_description_prompt(
        self,
        product_title: str,
        product_info: Dict[str, Any],
        description_type: str,
        target_audience: Optional[str],
        tone: str,
        include_keywords: Optional[List[str]],
        max_length: Optional[int],
    ) -> str:
        """Build the prompt for description generation."""

        prompt = f"""You are an expert e-commerce copywriter.
            Write a compelling SEO {self.description_types.get(description_type, 'detailed')} descriptions for this product:
            Product: {product_title} Product Information:
            """

        for key, value in product_info.items():
            if not value:
                continue

            if key == "variants" and isinstance(value, list):
                for i, variant in enumerate(value, start=1):
                    prompt += f"\n- Variant {i}:\n"
                    for v_key, v_value in variant.items():
                        if v_key == "options" and isinstance(v_value, list):
                            for opt in v_value:
                                prompt += f"  • {opt['type']}: {opt['slug']}\n"
                        else:
                            prompt += (
                                f"  • {v_key.replace('_', ' ').title()}: {v_value}\n"
                            )
            else:
                prompt += f"- {key.replace('_', ' ').title()}: {value}\n"

        prompt += "\nWriting Requirements:\n"
        prompt += f"- Tone: {tone}\n"
        prompt += f"- Description Type: {description_type}\n"

        if target_audience:
            prompt += f"- Target Audience: {target_audience}\n"

        if include_keywords:
            prompt += (
                f"- Keywords to include naturally: {', '.join(include_keywords)}\n"
            )

        if description_type == "short":
            prompt += "- Length: 50-100 words\n"
            prompt += "- Highlight main features and benefits\n"
        elif description_type == "detailed":
            prompt += "- Length: 150-300 words\n"
            prompt += "- Include features, benefits, and specifications\n"
        elif description_type == "marketing":
            prompt += "- Length: 100-200 words\n"
            prompt += "- Strong call-to-action\n"
            prompt += "- Emphasize value proposition and urgency\n"
        elif description_type == "technical":
            prompt += "- Length: 200-400 words\n"
            prompt += "- Focus on technical specifications and capabilities\n"
        elif description_type == "benefits":
            prompt += "- Length: 100-250 words\n"
            prompt += "- Focus on customer benefits and problem-solving\n"

        if max_length:
            prompt += f"- Maximum length: {max_length} characters\n"

        prompt += f"""
            Writing Guidelines:
            - Write in {tone} tone
            - Use active voice and engaging language
            - Include specific product benefits, not just features
            - Make it scannable with natural keyword integration
            - Focus on what matters most to customers
            - Include emotional triggers and value propositions
            - Avoid jargon unless writing for technical audience
            - End with a subtle call-to-action if appropriate

            Description Guidelines:
            - Focus on trust and transparency to build buyer confidence.
            - Clearly highlight product features: material, size, color, condition, and other relevant specifications.
            - Mention any unique selling points: eco-friendly, limited edition, fast shipping, etc.
            - Use natural language that incorporates relevant keywords users may search for.
            - Use a persuasive yet friendly tone; aim to inform and reassure the buyer.
            - Include information about authenticity guarantees or return policies if available.
            - Escrow Protection Notice: All payments are securely held in escrow and only released to the seller once the buyer confirms satisfaction with the product. This ensures a safe and fair transaction for both parties under our platform’s buyer protection policy.
            - Avoid overstatements or misleading claims; always be accurate and clear.

            Return only the description text, no additional formatting or explanations.
            """

        return prompt

    def _clean_description(
        self, description: str, description_type: str, max_length: Optional[int]
    ) -> str:
        """Clean and format the generated description."""
        # Remove quotes and extra whitespace
        description = description.strip().strip("\"'")
        description = re.sub(r"\s+", " ", description)

        # Handle length constraints
        if description_type == "short" and len(description) > 100:
            description = description[:98] + "..."
        elif max_length and len(description) > max_length:
            description = description[: max_length - 3] + "..."

        return description

    def _fallback_description(
        self, product_title: str, product_info: Dict[str, Any], description_type: str
    ) -> str:
        """Generate basic description if AI fails."""
        brand = product_info.get("brand", "")
        category = product_info.get("category", "")
        condition = product_info.get("condition", "")
        price = product_info.get("price", "")

        if description_type == "meta":
            return f"Buy {product_title} online. {brand} {category} in {condition} condition. Great deals available!"
        elif description_type == "short":
            return f"High-quality {product_title} from {brand}. {condition} condition. Perfect for your needs. Order now!"
        else:
            return f"Discover the {product_title} - a premium {category} from {brand}. This {condition} item offers exceptional value and quality. Features include professional-grade construction and reliable performance. Ideal for both personal and professional use. Available at competitive prices with fast shipping. Don't miss out on this excellent opportunity to own this quality product."

    def generate_multiple_descriptions(
        self,
        product_title: str,
        product_info: Dict[str, Any],
        description_types: List[str],
        target_audience: Optional[str] = None,
        include_keywords: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """Generate multiple description types for a product."""
        descriptions = {}

        for desc_type in description_types:
            try:
                description = self.generate_description(
                    product_title=product_title,
                    product_info=product_info,
                    description_type=desc_type,
                    target_audience=target_audience,
                    include_keywords=include_keywords,
                )
                descriptions[desc_type] = description
            except Exception as e:
                logger.error(f"Error generating {desc_type} description: {str(e)}")
                descriptions[desc_type] = self._fallback_description(
                    product_title, product_info, desc_type
                )

        return descriptions

    def optimize_existing_description(
        self,
        current_description: str,
        product_title: str,
        optimization_goal: str = "seo",
        target_keywords: Optional[List[str]] = None,
    ) -> str:
        """Optimize an existing product description."""

        prompt = f"""
            You are an expert SEO copywriter. Optimize this existing product description for better {optimization_goal} performance:
            Current Description: {current_description}
            Product: {product_title}
            Optimization Goal: {optimization_goal}
            """

        if target_keywords:
            prompt += f"Target Keywords: {', '.join(target_keywords)}\n"

        prompt += """
            Optimization Requirements:
            - Maintain the original length and tone
            - Improve keyword density naturally
            - Enhance readability and engagement
            - Strengthen call-to-action elements
            - Improve search engine visibility
            - Keep all factual information accurate

            Return only the optimized description.
            """

        try:
            response = self.client.models.generate_content(
                model="gemini-2.0-flash", contents=prompt
            )
            return self._clean_description(response.text, "detailed", None)
        except Exception as e:
            logger.error(f"Error optimizing description: {str(e)}")
            return current_description

    def analyze_description_quality(
        self, description: str, product_title: str
    ) -> Dict[str, Any]:
        """Analyze the quality of a product description."""
        prompt = f"""Analyze this product description for quality and SEO effectiveness:

            Product: {product_title}
            Description: {description}

            Provide analysis in the following format:
            SEO Score: [1-10]
            Readability Score: [1-10]
            Engagement Score: [1-10]
            Keyword Density: [low/medium/high]
            Call-to-Action Strength: [weak/moderate/strong]
            Length Assessment: [too short/optimal/too long]
            Key Strengths: [list 2-3 strengths]
            Improvement Areas: [list 2-3 areas for improvement]
            Overall Assessment: [2-3 sentences summary]
            """

        try:
            response = self.client.models.generate_content(
                model="gemini-2.0-flash", contents=prompt
            )
            return self._parse_quality_analysis(response.text)
        except Exception as e:
            logger.error(f"Error analyzing description quality: {str(e)}")
            return {"error": str(e)}

    def _parse_quality_analysis(self, response_text: str) -> Dict[str, Any]:
        """Parse the quality analysis response."""
        analysis = {}

        lines = response_text.strip().split("\n")
        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                analysis[key.strip()] = value.strip()

        return analysis

    def generate_product_bullets(
        self,
        product_title: str,
        product_info: Dict[str, Any],
        num_bullets: int = 5,
        focus_area: str = "features",
    ) -> List[str]:
        """Generate bullet points for product features/benefits."""
        prompt = f"""Create {num_bullets} compelling bullet points for this product focusing on {focus_area}:

            Product: {product_title}

            Product Information:
            """

        for key, value in product_info.items():
            if not value:
                continue

            if key == "variants" and isinstance(value, list):
                for i, variant in enumerate(value, start=1):
                    prompt += f"\n- Variant {i}:\n"
                    for v_key, v_value in variant.items():
                        if v_key == "options" and isinstance(v_value, list):
                            for opt in v_value:
                                prompt += f"  • {opt['type']}: {opt['slug']}\n"
                        else:
                            prompt += (
                                f"  • {v_key.replace('_', ' ').title()}: {v_value}\n"
                            )
            else:
                prompt += f"- {key.replace('_', ' ').title()}: {value}\n"

        prompt += f"""
            Requirements:
            - Focus on {focus_area}
            - Each bullet should be 5-15 words
            - Use action-oriented language
            - Highlight unique selling points
            - Make them scannable and impactful
            - Start with strong action verbs or descriptive words

            Format as a simple list, one bullet per line, without bullet symbols.
            """

        try:
            response = self.client.models.generate_content(
                model="gemini-2.0-flash", contents=prompt
            )
            bullets = [
                line.strip()
                for line in response.text.strip().split("\n")
                if line.strip()
            ]
            return bullets[:num_bullets]
        except Exception as e:
            logger.error(f"Error generating bullets: {str(e)}")
            return [
                f"High-quality {product_title}",
                "Premium construction and materials",
                "Perfect for everyday use",
                "Reliable performance guaranteed",
                "Excellent value for money",
            ][:num_bullets]


# # Usage example
# if __name__ == "__main__":
#     # Initialize the service
#     service = GoogleGenAISEODescriptionService()

#     # Sample product info
#     product_info = {
#         "brand": "Sony",
#         "category": "Electronics",
#         "condition": "New",
#         "price": "$299.99",
#         "color": "Black",
#         "features": "Wireless, Noise Cancelling, 30-hour battery",
#     }

#     # Generate different types of descriptions
#     descriptions = service.generate_multiple_descriptions(
#         product_title="Sony WH-1000XM4 Wireless Headphones",
#         product_info=product_info,
#         description_types=["meta", "short", "detailed"],
#         target_audience="music enthusiasts",
#         include_keywords=["wireless headphones", "noise cancelling", "sony"],
#     )

#     print("Generated Descriptions:")
#     for desc_type, description in descriptions.items():
#         print(f"\n{desc_type.upper()}:")
#         print(description)

#     # Generate bullet points
#     bullets = service.generate_product_bullets(
#         product_title="Sony WH-1000XM4 Wireless Headphones",
#         product_info=product_info,
#         num_bullets=5,
#         focus_area="benefits",
#     )

#     print("\nBullet Points:")
#     for bullet in bullets:
#         print(f"• {bullet}")
