# AI Safety Events and Training

This project helps find, process, and evaluate information about AI safety events and training programs using the Exa API and OpenRouter API.

## Features

- Search for AI safety events (conferences, workshops, seminars)
- Process and export results to JSON and Markdown
- Customizable queries for AI safety, governance, ethics, etc.
- Automatic date range for up-to-date results
- AI-powered scoring of results for relevance to AI safety
- Error handling and retry mechanism

## Requirements

- [Rye](https://rye-up.com/)
- Exa API Key (set `EXA_API_KEY` in `.env` file)
- OpenRouter API Key (set `OPENROUTER_API_KEY` in `.env` file)

## Setup and Usage

1. Clone the repository
2. Create a `.env` file in the project root and add your API keys:
   ```
   EXA_API_KEY=your_exa_api_key_here
   OPENROUTER_API_KEY=your_openrouter_api_key_here
   ```
3. Run `rye sync` to set up the project
4. Run `rye run python -m aisafetyeventsandtraining.main`
5. Check the `./results` folder for output files (JSON and Markdown)

## Output

The script generates two types of output files in the `results` folder:

1. JSON file: Contains raw data of search results and AI safety scores
2. Markdown file: Presents a formatted list of results, sorted by AI safety relevance score

## Customization

You can modify the following variables in `main.py` to customize the script's behavior:

- `NUM_RESULTS`: Number of results to fetch per query
- `DAYS`: Number of days in the past to search for events
- `OPENAI_MODEL`: The OpenAI model to use for scoring (via OpenRouter)
- `MAX_SUMMARY_LENGTH`: Maximum length of result summaries

## License

[MIT License](LICENSE)
