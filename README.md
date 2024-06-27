# aisafetyeventsandtraining

This project is designed to help you find and process information about AI safety events and training programs. It uses the Exa API to search for relevant events, processes the results, and exports them to JSON and Markdown files for easy viewing and sharing.

### Features
- **Search for AI Safety Events**: The tool queries the Exa API for various AI safety-related events, including conferences, workshops, seminars, and more.
- **Process and Export Results**: The search results are processed to include titles, URLs, publication dates, and summaries. These results are then exported to both JSON and Markdown formats.
- **Customizable Queries**: The tool includes a set of predefined queries related to AI safety, governance, ethics, and more. You can modify these queries to suit your needs.
- **Automatic Date Range**: The tool automatically calculates a date range for the past 30 days to ensure the search results are up-to-date.
- **Error Handling**: The tool includes error handling to manage issues that may arise during the querying process.

### Requirements
- **Python 3.7+**
- **Exa API Key**: You need an Exa API key to use this tool. Set the `EXA_API_KEY` environment variable in your `.env` file.

### Setup
1. Clone the repository.
2. Create a virtual environment and activate it.
3. Install the required dependencies using `pip install -r requirements.txt`.
4. Set up your `.env` file with your Exa API key.

### Usage
1. Sync the project using `rye sync`.
2. Run the main script using `rye run python -m aisafetyeventsandtraining.main`.
3. Check the `./results` folder for the output files in JSON and Markdown formats.

