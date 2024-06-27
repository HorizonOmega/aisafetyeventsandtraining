import os
import json
from datetime import datetime, timedelta, UTC
from exa_py.api import Exa
from dotenv import load_dotenv

load_dotenv()

NUM_RESULTS = 10
AUTO_PROMPT = False
DAYS = 30


def get_date_range(days):
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=days)
    return start_date.isoformat(), end_date.isoformat()


def process_results(results, query):
    processed_results = []
    for item in results:
        result = {
            "title": getattr(item, "title", "No title available"),
            "url": getattr(item, "url", "No URL available"),
            # "published": getattr(item, "published", "No publication date available"),
            "summary": getattr(item, "text", "No summary available")[:500] + "...",
        }
        processed_results.append(result)
    return {"query": query, "results": processed_results}


def export_to_json(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def export_to_markdown(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        f.write("# AI Safety Event Search Results\n\n")
        for query_results in data:
            f.write(f"## Query: {query_results['query']}\n\n")
            for item in query_results["results"]:
                f.write(f"### {item['title']}\n")
                f.write(f"- URL: {item['url']}\n")
                # f.write(f"- Published: {item['published']}\n")
                f.write(f"- Summary: {item['summary']}\n\n")


def main():
    api_key = os.environ.get("EXA_API_KEY")
    if not api_key:
        raise ValueError("Please set the EXA_API_KEY environment variable")
    exa = Exa(api_key=api_key)

    start_date_str, end_date_str = get_date_range(days=DAYS)

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

    all_results = []

    # Create a 'results' folder if it doesn't exist
    results_folder = "results"
    os.makedirs(results_folder, exist_ok=True)

    for query in queries:
        try:
            search_response = exa.search_and_contents(
                query,
                type="neural",
                use_autoprompt=AUTO_PROMPT,
                num_results=NUM_RESULTS,
                text=True,
                start_published_date=start_date_str,
                end_published_date=end_date_str,
            )
            processed_results = process_results(search_response.results, query)
            all_results.append(processed_results)
            print(f"Processed query: {query}")
            if search_response.autoprompt_string:
                print(f"Autoprompt string: {search_response.autoprompt_string}")
        except Exception as e:
            print(f"Error querying for '{query}': {str(e)}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_filename = os.path.join(results_folder, f"ai_safety_events_{timestamp}.json")
    markdown_filename = os.path.join(results_folder, f"ai_safety_events_{timestamp}.md")

    export_to_json(all_results, json_filename)
    export_to_markdown(all_results, markdown_filename)

    print(f"Results exported to {json_filename} and {markdown_filename}")
    print("Query process completed.")


if __name__ == "__main__":
    main()
