# AI Safety Events and Training

This project helps find and process information about AI safety events and training programs using the Exa API.

## Features
- Search for AI safety events (conferences, workshops, seminars)
- Process and export results to JSON and Markdown
- Customizable queries for AI safety, governance, ethics, etc.
- Automatic date range for up-to-date results
- Error handling

## Requirements
- [Rye](https://rye-up.com/)
- Exa API Key (set `EXA_API_KEY` in `.env` file)

## Setup and Usage
1. Clone the repository
2. Run `rye sync` to set up the project
3. Run `rye run python -m aisafetyeventsandtraining.main`
4. Check the `./results` folder for output files

## License
[MIT License](LICENSE)