import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from anthropic import Anthropic
from pyairtable import Api
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Config:
    """Configuration constants"""

    # API Configuration
    AIRTABLE_API_KEY: str = os.getenv("AIRTABLE_API_KEY", "")
    AIRTABLE_BASE_ID: str = os.getenv("AIRTABLE_BASE_ID", "")
    CLAUDE_API_KEY: str = os.getenv("CLAUDE_API_KEY", "")
    CLAUDE_MODEL: str = "claude-3-5-sonnet-20241022"
    CLAUDE_MAX_TOKENS: int = 2000
    DAYS_LOOKBACK: int = 7

    # Airtable Configuration
    TABLE_NAME: str = "Calendar"
    FIELD_NAMES = {
        "name": "Name",
        "created_date": "Created date",
        "publish": "Publish?",
        "description": "Description",
        "start_date": "Start date",
        "end_date": "End date",
        "type": "Type",
        "location": "Location",
        "url": "URL",
    }

    # Add output directory configuration
    OUTPUT_DIR: str = "output"

    # Output Files
    OUTPUT_FILES = {
        "newsletter": lambda: os.path.join(
            Config.OUTPUT_DIR, f"newsletter_{Config.get_iso_week_str()}.md"
        ),
        "social": lambda: os.path.join(
            Config.OUTPUT_DIR, f"social_{Config.get_iso_week_str()}.md"
        ),
    }

    # LLM Prompts
    SYSTEM_PROMPT: str = """You are a formatter for AI safety events. Your task is to generate two types of content:
    1. A detailed newsletter post
    2. A concise social media post

    For both formats:
    - Sort events chronologically
    - Use consistent date formatting
    - Ensure proper location formatting (city names, not countries)
    - Format URLs as markdown links
    - Maintain consistent spacing and structure
    """

    NEWSLETTER_PROMPT: str = """Create a newsletter post with this structure:

    # AI Safety Events and Training: {YEAR} Week {WEEK} update
    [AISafety Events & Training Newsletter](https://www.aisafety.com/events-and-training)

    This is a weekly newsletter listing newly announced AI safety events and training programs. Visit [AISafety.com/events-and-training](https://www.aisafety.com/events-and-training) for the full list of upcoming events and programs.

    ## Events
    - [Event Name](URL) *Month DD* (Location).
      <-- Two spaces here for description indent -->Description goes here with two space indent.

    ## Training opportunities
    - [Program Name](URL) *Month DD – Month DD* (Location).
      <-- Two spaces here for description indent -->Description goes here with two space indent.

    Rules:
    1. Dates use full month names (e.g., "November" not "Nov")
    2. Date ranges use en dash (–) with spaces: "Month DD – Month DD"
    3. Descriptions MUST be indented with two spaces on a new line
    4. Locations end with period
    5. Two blank lines between sections
    6. Events must be sorted chronologically
    7. No HTML comments in final output
    """

    SOCIAL_PROMPT: str = """Create a social media post with this structure:

    # AI Safety Events and Training: {YEAR} Week {WEEK} update
    [AISafety Events & Training Newsletter](https://www.aisafety.com/events-and-training)

    Events
    - Event: MMM DD (City)
    - Multi-day: MMM DD-DD (City)

    Training opportunities
    - Program: MMM DD-MMM DD (City)

    Notes
    • Visit [AISafety.com/events-and-training](https://www.aisafety.com/events-and-training)

    Rules:
    1. Use EXACTLY 3-letter capitalized months (e.g., "NOV" not "November")
    2. Use hyphen WITHOUT spaces for date ranges (e.g., "NOV 15-17" not "NOV 15 - 17")
    3. One blank line between sections (no double lines)
    4. Use specific cities only, never countries (e.g., "London" not "UK")
    5. Events must be sorted chronologically
    6. Keep descriptions very brief - one line per event
    """

    @staticmethod
    def get_iso_week_str() -> str:
        """Get current ISO week string in format YYYYWWW (e.g., 2024W46)"""
        current_date = datetime.now()
        return f"{current_date.year}W{current_date.isocalendar()[1]:02d}"


class AirtableClient:
    """Handles Airtable operations"""

    def __init__(self):
        self.api = Api(Config.AIRTABLE_API_KEY)
        self.table = self.api.table(Config.AIRTABLE_BASE_ID, Config.TABLE_NAME)

    def get_recent_unpublished_events(self) -> List[Dict]:
        """Get events added in the last 7 days that aren't published"""
        cutoff_date = (datetime.now() - timedelta(days=Config.DAYS_LOOKBACK)).strftime(
            "%Y-%m-%d"
        )

        try:
            logger.info(
                f"Fetching records from base: {Config.AIRTABLE_BASE_ID}, table: {Config.TABLE_NAME}"
            )
            records = self.table.all()
            filtered_records = [
                record
                for record in records
                if (
                    record["fields"].get(Config.FIELD_NAMES["created_date"], "")
                    >= cutoff_date
                    and record["fields"].get(Config.FIELD_NAMES["publish"], False)
                )
            ]
            return sorted(
                filtered_records,
                key=lambda x: x["fields"].get(Config.FIELD_NAMES["start_date"], ""),
            )
        except Exception as e:
            logger.error(f"Error fetching Airtable records: {e}")
            return []


class ContentGenerator:
    """Handles content generation using Claude"""

    def __init__(self):
        self.client = Anthropic(api_key=Config.CLAUDE_API_KEY)

    def prepare_events_data(self, events: List[Dict]) -> str:
        """Convert events to simple text format for LLM"""
        formatted_events = []
        for event in events:
            fields = event["fields"]
            event_str = (
                f'Name: "{fields.get(Config.FIELD_NAMES["name"], "")}"'
                f'\nDates: "{fields.get(Config.FIELD_NAMES["start_date"], "")}" to "{fields.get(Config.FIELD_NAMES["end_date"], "")}"'
                f'\nLocation: "{fields.get(Config.FIELD_NAMES["location"], "")}"'
                f'\nDescription: "{fields.get(Config.FIELD_NAMES["description"], "")}"'
                f'\nType: "{fields.get(Config.FIELD_NAMES["type"], ["Event"])}"'
                f'\nURL: "{fields.get(Config.FIELD_NAMES["url"], "")}"'
            )
            formatted_events.append(event_str)
        return "\n\n".join(formatted_events)

    def generate_content(self, events: List[Dict]) -> Tuple[str, str]:
        """Generate both newsletter and social posts"""
        if not events:
            return "No events to display", "No events to display"

        events_data = self.prepare_events_data(events)
        current_week = datetime.now().isocalendar()[1]
        current_year = datetime.now().year

        try:
            # Generate newsletter with year and week
            newsletter = (
                self.client.messages.create(
                    model=Config.CLAUDE_MODEL,
                    max_tokens=Config.CLAUDE_MAX_TOKENS,
                    system=Config.SYSTEM_PROMPT,
                    messages=[
                        {
                            "role": "user",
                            "content": f"{Config.NEWSLETTER_PROMPT.format(YEAR=current_year, WEEK=current_week)}\n\nEvents:\n{events_data}",
                        }
                    ],
                )
                .content[0]
                .text
            )

            # Generate social post with year and week
            social = (
                self.client.messages.create(
                    model=Config.CLAUDE_MODEL,
                    max_tokens=Config.CLAUDE_MAX_TOKENS,
                    system=Config.SYSTEM_PROMPT,
                    messages=[
                        {
                            "role": "user",
                            "content": f"{Config.SOCIAL_PROMPT.format(YEAR=current_year, WEEK=current_week)}\n\nEvents:\n{events_data}",
                        }
                    ],
                )
                .content[0]
                .text
            )

            return newsletter, social
        except Exception as e:
            logger.error(f"Error generating content: {e}")
            return "Error generating content", "Error generating content"


def main():
    """Main execution function"""
    logger.info(f"Using Airtable Base ID: {Config.AIRTABLE_BASE_ID}")
    logger.info(f"Using Table Name: {Config.TABLE_NAME}")

    airtable_client = AirtableClient()
    content_generator = ContentGenerator()

    events = airtable_client.get_recent_unpublished_events()
    if not events:
        logger.info("No new unpublished events found")
        return

    newsletter_content, social_content = content_generator.generate_content(events)

    try:
        # Create output directory if it doesn't exist
        os.makedirs(Config.OUTPUT_DIR, exist_ok=True)

        with open(Config.OUTPUT_FILES["newsletter"](), "w") as f:
            f.write(newsletter_content)
        with open(Config.OUTPUT_FILES["social"](), "w") as f:
            f.write(social_content)
        logger.info("Successfully wrote content to files")
    except Exception as e:
        logger.error(f"Error writing to files: {e}")


if __name__ == "__main__":
    main()
