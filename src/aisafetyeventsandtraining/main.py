"""
AI Safety Events and Training Search

This script searches for and processes information about upcoming AI safety events,
training opportunities, and open calls. It uses the Exa API for searching and the
OpenAI API (via OpenRouter) for scoring and filtering results.

Key features:
- Searches multiple queries related to AI safety events and training
- Uses concurrent processing to improve performance
- Scores and filters results based on relevance to AI safety
- Exports results in both JSON and Markdown formats

Usage:
    python main.py [--days DAYS] [--results RESULTS] [--model MODEL]

Arguments:
    --days DAYS     Number of days to search (default: 30)
    --results RESULTS   Number of results per query (default: 10)
    --model MODEL   OpenAI model to use (default: "openai/gpt-4o-mini")

Environment variables required:
    EXA_API_KEY: API key for Exa
    OPENROUTER_API_KEY: API key for OpenRouter

Output:
    - JSON file with full results
    - Markdown file with formatted results
    - Log messages for tracking progress and errors

Note: Ensure all required libraries are installed and environment variables are set
before running the script.

Author: Orpheus Lummis
Version: 1.0
"""

import os
import json
import logging
import argparse
from datetime import datetime, timedelta, UTC
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
from exa_py.api import Exa
from dotenv import load_dotenv
from openai import OpenAI
from tenacity import retry, wait_exponential, stop_after_attempt
from ratelimit import limits, sleep_and_retry
import html

load_dotenv()

# Add these checks after load_dotenv()
if "EXA_API_KEY" not in os.environ:
    raise EnvironmentError("EXA_API_KEY environment variable is not set")
if "OPENROUTER_API_KEY" not in os.environ:
    raise EnvironmentError("OPENROUTER_API_KEY environment variable is not set")

NUM_RESULTS = 10
DAYS = 30
OPENAI_MODEL = "openai/gpt-4o-mini"
MAX_SUMMARY_LENGTH = 500
RETRY_ATTEMPTS = 5
RESULTS_FOLDER = "results"

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])

def get_date_range(days: int) -> tuple[str, str]:
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=days)
    return start_date.isoformat(), end_date.isoformat()

def process_results(results: List[Any], query: str) -> Dict[str, Any]:
    return {
        "query": query,
        "results": [
            {
                "title": getattr(item, "title", "No title available"),
                "url": getattr(item, "url", "No URL available"),
                "summary": getattr(item, "text", "No summary available")[:MAX_SUMMARY_LENGTH] + "...",
            }
            for item in results
        ]
    }

@retry(wait=wait_exponential(multiplier=1, min=4, max=10), stop=stop_after_attempt(RETRY_ATTEMPTS))
@sleep_and_retry
@limits(calls=5, period=60)  # Adjust these values based on API limits
def call_openai_api(messages: List[Dict[str, str]]) -> str:
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL, 
            messages=messages,
            timeout=30  # Add a timeout
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"OpenRouter API error: {str(e)}")
        raise

def remove_duplicates(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    unique_results = []
    for query_results in data:
        query_results['results'] = [
            item for item in query_results['results']
            if item['url'] not in seen and not seen.add(item['url'])
        ]
        unique_results.append(query_results)
    return unique_results

def score_results(data: List[Dict[str, Any]], batch_size: int = 10) -> List[Dict[str, Any]]:
    prompt_template = f"""
    Today's date: {datetime.now(UTC).date().isoformat()}

    You are an AI expert tasked with evaluating potential AI safety events, training opportunities, and open calls. 
    This is for the AI Safety Events and Training newsletter.
    This newsletter ONLY includes upcoming events, training programs, and open calls related to AI safety.

    Given the following information about search results, rate each on a scale of 0-10 based on the following STRICT criteria:

    Scoring guidelines:
    10: Highly relevant upcoming event, training program, or open call specifically focused on AI safety, with clear future dates and detailed participation information.
    8-9: Relevant upcoming opportunity in AI safety, but may lack some minor details or have a slightly broader focus.
    6-7: Upcoming AI safety related event or opportunity, but missing some important details or not exclusively focused on safety.
    1-5: DO NOT USE THESE SCORES.
    0: Anything that is not a specific upcoming event, training program, or open call related to AI safety. This includes past events, general articles, resources without participation options, or topics not directly tied to AI safety.

    Key points:
    - If it's not an upcoming event, training, or open call, it MUST be scored 0.
    - If the date/deadline is in the past or not clearly specified as a future date, it MUST be scored 0.
    - If it lacks a specific date or clear participation information, it should be scored 6 or lower.
    - Only score 8 or above if it's highly relevant to AI safety AND provides clear details for future participation.
    - Pay close attention to avoid duplicate events. If you suspect an event is a duplicate, mention it in the explanation.

    Provide your response in the following format for each item:
    Item [number]:
    Score: [0, 6, 7, 8, 9, or 10]
    Explanation: [2-3 sentence justification, including the specific date of the event/deadline if available. Mention if it appears to be a duplicate.]

    Search results:
    """

    all_items = [item for query_results in data for item in query_results['results']]

    for i in range(0, len(all_items), batch_size):
        batch = all_items[i:i+batch_size]
        full_prompt = prompt_template + "\n".join([f"Item {j+1}:\n" + json.dumps(item) for j, item in enumerate(batch)])
        
        try:
            batch_scores = call_openai_api([
                {"role": "system", "content": "You are an AI safety expert."},
                {"role": "user", "content": full_prompt}
            ])
            
            if batch_scores:
                item_scores = batch_scores.split("\n\n")
                for j, item_score in enumerate(item_scores):
                    if i + j < len(all_items):
                        lines = item_score.split("\n")
                        score = 0
                        explanation = "Failed to parse score and explanation."
                        
                        try:
                            for line in lines:
                                if line.startswith("Score:"):
                                    score = int(line.split(":")[1].strip())
                                elif line.startswith("Explanation:"):
                                    explanation = line.replace("Explanation:", "").strip()
                                    explanation += " ".join(lines[lines.index(line)+1:])
                                    break
                        except (IndexError, ValueError) as e:
                            logging.warning(f"Failed to parse score for item: {batch[j].get('title', 'Unknown')}. Error: {str(e)}")
                        
                        all_items[i + j]['ai_safety_score'] = score
                        all_items[i + j]['score_explanation'] = explanation
            else:
                logging.warning("Empty batch_scores from OpenAI")
                for j in range(batch_size):
                    if i + j < len(all_items):
                        all_items[i + j]['ai_safety_score'] = 0
                        all_items[i + j]['score_explanation'] = "Empty batch_scores from OpenAI"
        except Exception as e:
            logging.error(f"Error scoring batch: {str(e)}")
            for j in range(batch_size):
                if i + j < len(all_items):
                    all_items[i + j]['ai_safety_score'] = 0
                    all_items[i + j]['score_explanation'] = "Error occurred during batch scoring."

    item_index = 0
    for query_results in data:
        query_results['results'] = [
            item for item in all_items[item_index:item_index+len(query_results['results'])]
            if item['ai_safety_score'] >= 6  # Only keep items with score 6 or higher
        ]
        item_index += len(query_results['results'])

    data = remove_duplicates(data)
    return data

def export_to_json(data: List[Dict[str, Any]], filename: str) -> None:
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logging.error(f"Error writing JSON file: {str(e)}")

def export_to_markdown(data: List[Dict[str, Any]], filename: str) -> None:
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write("# AI Safety Event Search Results\n\n")
            
            all_items = [item for query_results in data for item in query_results["results"]]
            sorted_items = sorted(all_items, key=lambda x: x['ai_safety_score'], reverse=True)
            
            if not sorted_items:
                f.write("No relevant AI safety events found.\n")
            else:
                for item in sorted_items:
                    f.write(f"## {html.escape(item['title'])} (Score: {item['ai_safety_score']})\n")
                    f.write(f"- URL: {html.escape(item['url'])}\n")
                    f.write(f"- Summary: {html.escape(item['summary'])}\n")
                    f.write(f"- Explanation: {html.escape(item['score_explanation'])}\n\n")
    except IOError as e:
        logging.error(f"Error writing Markdown file: {str(e)}")

def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI Safety Events and Training Search")
    parser.add_argument("--days", type=int, default=DAYS, help="Number of days to search")
    parser.add_argument("--results", type=int, default=NUM_RESULTS, help="Number of results per query")
    parser.add_argument("--model", type=str, default=OPENAI_MODEL, help="OpenAI model to use")
    return parser.parse_args()

@retry(wait=wait_exponential(multiplier=1, min=4, max=10), stop=stop_after_attempt(RETRY_ATTEMPTS))
def search_and_process(exa: Exa, query: str, start_date: str, end_date: str, num_results: int) -> Dict[str, Any]:
    try:
        search_response = exa.search_and_contents(
            query, type="neural", use_autoprompt=False, num_results=num_results,
            text=True, start_published_date=start_date, end_published_date=end_date,
        )
        processed_results = process_results(search_response.results, query)
        logging.info(f"Processed query: {query}")
        return processed_results
    except Exception as e:
        logging.error(f"Error querying for '{query}': {str(e)}")
        return {"query": query, "results": []}

def main() -> None:
    setup_logging()
    args = parse_arguments()
    
    global OPENAI_MODEL
    OPENAI_MODEL = args.model  # Use the model specified in arguments

    try:
        exa = Exa(api_key=os.environ["EXA_API_KEY"])

        # Test API connections
        exa.search("test", num_results=1)
        logging.info("Exa API connection successful")

        client.chat.completions.create(
            model=args.model,
            messages=[{"role": "user", "content": "Hello, this is a test."}],
            max_tokens=5
        )
        logging.info("OpenRouter API connection successful")

        start_date_str, end_date_str = get_date_range(days=args.days)

        queries = [
            "AI safety OR alignment conference OR workshop",
            "AI governance OR policy symposium OR forum",
            "Machine learning safety OR robustness event OR seminar",
            "AI ethics OR responsible AI development seminar OR workshop",
            "Explainable AI OR interpretable machine learning conference OR workshop",
            "AI safety research summit OR symposium",
            "AI safety OR alignment career workshop OR fair",
            "AI security evaluation OR testing competition OR challenge",
            "AI safety course OR training program OR bootcamp",
            "Effective altruism AI safety event OR meetup",
            "Large language model OR LLM safety workshop OR seminar",
            "AI existential risk OR long-term AI safety symposium OR conference",
            "AI cooperation OR coordination strategies workshop OR forum",
            "AI value alignment OR ethics panel OR discussion",
            "Transformative AI impact OR risk assessment seminar OR workshop",
        ]

        if not os.path.exists(RESULTS_FOLDER):
            os.makedirs(RESULTS_FOLDER)
        else:
            logging.info(f"Results folder '{RESULTS_FOLDER}' already exists.")

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(search_and_process, exa, query, start_date_str, end_date_str, args.results) for query in queries]
            
            all_results = []
            for future in as_completed(futures):
                result = future.result()
                if result["results"]:
                    all_results.append(result)

        successful_queries = sum(1 for result in all_results if result["results"])
        failed_queries = len(queries) - successful_queries
        logging.info(f"Processed {successful_queries} queries successfully, {failed_queries} queries failed")

        if not all_results:
            logging.warning("No results found for any query. Exiting.")
            return

        scored_results = score_results(all_results, batch_size=10)
        unique_results = remove_duplicates(scored_results)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_filename = os.path.join(RESULTS_FOLDER, f"ai_safety_events_{timestamp}.json")
        markdown_filename = os.path.join(RESULTS_FOLDER, f"ai_safety_events_{timestamp}.md")

        export_to_json(unique_results, json_filename)
        export_to_markdown(unique_results, markdown_filename)

        logging.info(f"Results exported to {json_filename} and {markdown_filename}")
        logging.info("Query process completed.")
    except Exception as e:
        logging.critical(f"An unexpected error occurred: {str(e)}")
        raise

if __name__ == "__main__":
    main()