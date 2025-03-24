# Tracxn MCP Server

A Model Control Protocol (MCP) server implementation for interacting with the Tracxn API. This server enables AI models to access Tracxn's comprehensive database of companies, investors, transactions, and market intelligence.

## 🚧 Work in Progress

This project is currently under active development. Some features may be incomplete or subject to change.

## Features

### Company Information

- Search companies by sector, name, or domain
- Filter by funding amounts, location, founding year
- Detailed company profiles including business models and funding history

### Investment Data

- Search funding transactions and rounds
- Filter by date, amount, round type
- Investor details and portfolio information

### Market Intelligence

- Practice area insights
- Business model categorization
- Industry feeds and sectors

## Requirements

- Python 3.8 or higher
- Tracxn API access token

## Installation

1. Clone the repository:

```bash

git clone 
cd tracxn-mcp

```

2. Install dependencies:

```bash

pip install -r requirements.txt

```

3. Set your Tracxn API token:

```bash

# On macOS/Linux

export TRACXN_ACCESS_TOKEN = "your-token-here"


# On Windows Command Prompt

set TRACXN_ACCESS_TOKEN = your-token-here


# On Windows PowerShell

$env:TRACXN_ACCESS_TOKEN="your-token-here"

```

## Usage

Run the server:

```bash

python tracxn_server.py

```

## Tools Available

1.`search_companies`: Search companies with various filters

2.`company_lookup`: Get detailed information about a specific company

3.`funded_companies`: Find companies within specific funding ranges

4.`search_companies_by_name`: Search companies by their name

5.`search_transactions`: Find funding rounds and transactions

6.`search_investors`: Search for investors and their portfolios

7.`search_acquisitions`: Find acquisition deals

8.`search_practice_areas`: Explore practice areas

9.`search_feeds`: Access industry feeds

10.`search_business_models`: Find business model categories

11.`debug_api_call`: Debug API requests

12.`diagnose_api_request`: Diagnose API request format issues

## API Endpoints

The server uses Tracxn's API v2.2 with both playground and production environments:

- Playground: `https://platform.tracxn.com/api/2.2/playground`
- Production: `https://platform.tracxn.com/api/2.2`

## Known Issues and Limitations

- Maximum of 20 results per request
- Some sectors may require specific access permissions
- Rate limiting applies to API calls
- Sort fields must be specified in certain formats
- The following errors may occur:
- Sort field errors: Some endpoints require specific sort field formats
- Domain format issues: Company lookup may need domain as a list or string
- Invalid sector access: Some sectors may not be accessible depending on API permissions

## Error Handling

The server handles various API response codes:

- 200: Success
- 400: Bad Request
- 401: Authentication Issue
- 403: Unauthorized/Credit Limit Exceeded
- 404: Not Found
- 429: Rate Limit Exceeded
- 500: Internal Server Error

## Development

### Project Structure

-`tracxn_server.py`: Main server implementation

-`requirements.txt`: Python dependencies

-`README.md`: Project documentation

### Debugging

Use the `debug_api_call` and `diagnose_api_request` tools to troubleshoot API issues.

## Contributing

This is a work in progress, and contributions are welcome. Please ensure you test your changes thoroughly before submitting pull requests.

## License

[Add your license information here]

## Support

For API-related issues, contact Tracxn support at support@tracxn.com

---

**Note**: This implementation is still under development. Features and functionality may change as we continue to improve the integration with Tracxn's API.
