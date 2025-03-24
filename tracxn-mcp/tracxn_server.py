import asyncio
import aiohttp
import sys
import logging
import json
import os
import copy

from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
from pydantic import AnyUrl
import mcp.server.stdio

# Initialize server and logging
server = Server("tracxn-mcp")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)

logging.info("Tracxn MCP Server starting up")

# Helper function for making API calls to Tracxn
async def tracxn_api_call(endpoint: str, data: dict, use_playground: bool = True) -> dict:
    """
    Make an API call to the Tracxn API with proper headers and error handling.
    
    Args:
        endpoint: API endpoint to call
        data: Request data to send to the API
        use_playground: Whether to use the playground API (default) or production API
    """
    # Get API key from environment - use TRACXN_ACCESS_TOKEN instead of TRACXN_API_KEY
    api_key = os.getenv("TRACXN_ACCESS_TOKEN")
    
    if not api_key:
        return {"error": "TRACXN_ACCESS_TOKEN environment variable is not set"}
    
    # Log the request (for debugging)
    logging.info(f"Making request to Tracxn API endpoint: {endpoint}")
    logging.info(f"Request data: {json.dumps(data)[:500]}...")
    
    # Prepare headers - note lowercase 'accesstoken' as required by API
    headers = {
        "accesstoken": api_key,
        "cache-control": "no-cache",
        "Content-Type": "application/json"
    }
    
    # Determine the correct URL base - default to playground as specified
    base_url = "https://platform.tracxn.com/api/2.2"
    if use_playground:
        base_url += "/playground"
    
    url = f"{base_url}/{endpoint}"
    logging.info(f"Using API URL: {url}")
    
    # Make the API call
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers) as response:
                response_status = response.status
                logging.info(f"Tracxn API response status: {response_status}")
                
                if response_status == 200:
                    response_json = await response.json()
                    return response_json
                elif response_status == 429:
                    # Handle rate limiting specifically
                    error_text = await response.text()
                    logging.error(f"Rate limit exceeded: {error_text}")
                    return {"error": "Tracxn API rate limit exceeded. Please try again later."}
                else:
                    error_text = await response.text()
                    logging.error(f"Error from Tracxn API: {error_text}")
                    return {"error": f"API returned status code {response_status}: {error_text}"}
    except Exception as e:
        logging.error(f"Exception in API call: {str(e)}")
        return {"error": f"API call failed: {str(e)}"}

# Debug helper function
async def debug_api_call(endpoint: str = "companies", data: dict = None, use_playground: bool = True) -> dict:
    """
    Debug an API call to help diagnose issues with the Tracxn API.
    Shows the exact request and response.
    
    Args:
        endpoint: API endpoint to call
        data: Request data to send to the API
        use_playground: Whether to use the playground API (default) or production API
    """
    if data is None:
        # Default to a basic Cybersecurity search if no data provided
        data = {
            "filter": {"feedName": ["Cybersecurity"]},
            "size": 1
        }
    
    # Get API key from environment - use TRACXN_ACCESS_TOKEN instead of TRACXN_API_KEY
    api_key = os.getenv("TRACXN_ACCESS_TOKEN")
    if not api_key:
        return {"error": "TRACXN_ACCESS_TOKEN environment variable is not set"}
    
    # Prepare headers
    headers = {
        "accesstoken": api_key,
        "cache-control": "no-cache",
        "Content-Type": "application/json"
    }
    
    # Determine the correct URL base - default to playground as specified
    base_url = "https://platform.tracxn.com/api/2.2"
    if use_playground:
        base_url += "/playground"
    
    url = f"{base_url}/{endpoint}"
    
    # Make the API call and capture all details
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers) as response:
                response_status = response.status
                response_headers = dict(response.headers)
                
                # Try to parse as JSON, but keep as text if that fails
                try:
                    if response_status == 200:
                        response_body = await response.json()
                    else:
                        response_text = await response.text()
                        try:
                            response_body = json.loads(response_text)
                        except:
                            response_body = response_text
                except:
                    response_body = await response.text()
                
                # Return detailed debug info
                return {
                    "request": {
                        "url": url,
                        "headers": headers,
                        "data": data
                    },
                    "response": {
                        "status_code": response_status,
                        "headers": response_headers,
                        "body" if response_status == 200 else "error": response_body
                    }
                }
    except Exception as e:
        return {
            "request": {
                "url": url,
                "headers": headers,
                "data": data
            },
            "response": {
                "error": f"Exception: {str(e)}"
            }
        }

# Tracxn API Functions
@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    """
    List available prompts for the Tracxn MCP.
    """
    return [
        types.Prompt(
            name="search_cybersecurity_companies",
            description="Search for information about cybersecurity companies in the Tracxn database",
            arguments=[
                types.PromptArgument(
                    name="limit",
                    description="Number of companies to retrieve (max 10)",
                    required=False,
                ),
            ],
        ),
        types.Prompt(
            name="lookup_company",
            description="Lookup detailed information about a specific company by domain name",
            arguments=[
                types.PromptArgument(
                    name="domain",
                    description="Company domain (e.g., 'crowdstrike.com')",
                    required=True,
                ),
            ],
        ),
        types.Prompt(
            name="search_funded_companies",
            description="Find cybersecurity companies with specific funding amounts",
            arguments=[
                types.PromptArgument(
                    name="min_funding",
                    description="Minimum funding amount in USD",
                    required=False,
                ),
                types.PromptArgument(
                    name="max_funding",
                    description="Maximum funding amount in USD",
                    required=False,
                ),
            ],
        ),
    ]

@server.get_prompt()
async def handle_get_prompt(
    name: str, arguments: dict[str, str] | None
) -> types.GetPromptResult:
    """
    Generate a prompt based on the requested name and arguments.
    """
    if name == "search_cybersecurity_companies":
        limit = (arguments or {}).get("limit", "5")
        return types.GetPromptResult(
            description=f"Searching for top {limit} cybersecurity companies",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=f"Find information about the top {limit} cybersecurity companies",
                    ),
                ),
            ],
        )
    elif name == "lookup_company":
        domain = (arguments or {}).get("domain", "")
        return types.GetPromptResult(
            description=f"Looking up information about {domain}",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=f"Find detailed information about the company with domain {domain}",
                    ),
                ),
            ],
        )
    elif name == "search_funded_companies":
        min_funding = (arguments or {}).get("min_funding", "10000000")
        max_funding = (arguments or {}).get("max_funding", "100000000")
        return types.GetPromptResult(
            description=f"Finding cybersecurity companies with funding between ${min_funding} and ${max_funding}",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=f"Find cybersecurity companies with funding between ${min_funding} and ${max_funding}",
                    ),
                ),
            ],
        )
    
    raise ValueError(f"Unknown prompt: {name}")

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """
    List all available tools provided by the Tracxn MCP.
    """
    return [
        types.Tool(
            name="search_companies",
            description="Search for companies in Tracxn database by sector and other criteria",
            inputSchema={
                "type": "object",
                "properties": {
                    "sector": {"type": "string", "default": "Cybersecurity", "description": "Sector name (e.g., 'Cybersecurity', 'Fintech')"},
                    "limit": {"type": "integer", "default": 5, "description": "Number of results to retrieve (max 20)"},
                    "from": {"type": "integer", "default": 0, "description": "Pagination offset"},
                    "sort_by": {"type": "string", "enum": ["relevance", "companyName", "foundedYear", "totalMoneyRaised", "editorRating", "tracxnScore"], "default": "relevance", "description": "Field to sort results by"},
                    "sort_order": {"type": "string", "enum": ["asc", "desc"], "default": "desc", "description": "Sort order (ascending or descending)"},
                    "country": {"type": "string", "description": "Filter by country (e.g., 'United States')"},
                    "city": {"type": "string", "description": "Filter by city (e.g., 'San Francisco')"},
                    "founded_year": {"type": "string", "description": "Filter by founded year (e.g., '2020')"},
                    "min_funding": {"type": "number", "description": "Minimum total funding in USD"},
                    "max_funding": {"type": "number", "description": "Maximum total funding in USD"}
                },
                "required": ["sector"],
            },
        ),
        types.Tool(
            name="company_lookup",
            description="Look up detailed information about a company by domain",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Company domain (e.g., 'crowdstrike.com')"},
                },
                "required": ["domain"],
            },
        ),
        types.Tool(
            name="funded_companies",
            description="Find companies with specific funding amounts",
            inputSchema={
                "type": "object",
                "properties": {
                    "min_funding": {"type": "integer", "default": 10000000, "description": "Minimum funding amount in USD"},
                    "max_funding": {"type": "integer", "default": 100000000, "description": "Maximum funding amount in USD"},
                    "sector": {"type": "string", "default": "Cybersecurity", "description": "Sector to filter by (e.g., 'Cybersecurity')"},
                    "limit": {"type": "integer", "default": 5, "description": "Number of results to retrieve (max 20)"},
                    "sort_by": {"type": "string", "enum": ["totalMoneyRaised", "foundedYear", "companyName"], "default": "totalMoneyRaised", "description": "Field to sort results by"},
                    "sort_order": {"type": "string", "enum": ["asc", "desc"], "default": "desc", "description": "Sort order (ascending or descending)"},
                    "country": {"type": "string", "description": "Filter by country (e.g., 'United States')"}
                },
                "required": ["min_funding", "max_funding"],
            },
        ),
        types.Tool(
            name="debug_api_call",
            description="Debug an API call to Tracxn for troubleshooting",
            inputSchema={
                "type": "object",
                "properties": {
                    "endpoint": {"type": "string", "default": "companies", "description": "API endpoint to call"},
                    "data": {"type": "object", "description": "Request data to send to the API"},
                },
            },
        ),
        types.Tool(
            name="search_companies_by_name",
            description="Search for companies by name to get their IDs and domains",
            inputSchema={
                "type": "object",
                "properties": {
                    "company_name": {"type": "string", "description": "Company name to search for (e.g., 'Apple')"}
                },
                "required": ["company_name"],
            },
        ),
        types.Tool(
            name="search_transactions",
            description="Search for funding rounds/transactions in the Tracxn database",
            inputSchema={
                "type": "object",
                "properties": {
                    "sector": {"type": "string", "description": "Sector/feed name (e.g., 'Cybersecurity')"},
                    "round_type": {"type": "string", "description": "Funding round type (e.g., 'Series A', 'Series B')"},
                    "min_amount": {"type": "integer", "description": "Minimum funding amount in USD"},
                    "max_amount": {"type": "integer", "description": "Maximum funding amount in USD"},
                    "start_date": {"type": "string", "description": "Start date for funding rounds (dd/mm/yyyy)"},
                    "end_date": {"type": "string", "description": "End date for funding rounds (dd/mm/yyyy)"},
                    "investor_domain": {"type": "string", "description": "Investor domain to filter by (e.g., 'sequoiacap.com')"},
                    "country": {"type": "string", "description": "Country to filter by"},
                    "limit": {"type": "integer", "default": 5, "description": "Number of results to retrieve (max 20)"},
                    "offset": {"type": "integer", "default": 0, "description": "Pagination offset"},
                    "sort_by": {"type": "string", "enum": ["transactionFundingRoundAmount", "transactionFundingRoundDate"], "default": "transactionFundingRoundDate", "description": "Field to sort results by"},
                    "sort_order": {"type": "string", "enum": ["asc", "desc"], "default": "desc", "description": "Sort order (ascending or descending)"}
                }
            },
        ),
        types.Tool(
            name="search_investors",
            description="Search for investors in the Tracxn database",
            inputSchema={
                "type": "object",
                "properties": {
                    "investor_name": {"type": "string", "description": "Investor name to search for"},
                    "investor_type": {"type": "string", "description": "Type of investor (e.g., 'Venture Capital Funds', 'Corporate Investors')"},
                    "investor_country": {"type": "string", "description": "Country where the investor is based"},
                    "portfolio_sector": {"type": "string", "description": "Sector/feed name in their portfolio (e.g., 'Cybersecurity')"},
                    "limit": {"type": "integer", "default": 5, "description": "Number of results to retrieve (max 20)"},
                    "offset": {"type": "integer", "default": 0, "description": "Pagination offset"},
                    "min_investment_score": {"type": "integer", "description": "Minimum investment score (0-100)"}
                }
            },
        ),
        types.Tool(
            name="search_acquisitions",
            description="Search for acquisitions in the Tracxn database",
            inputSchema={
                "type": "object",
                "properties": {
                    "acquisition_type": {"type": "string", "description": "Type of acquisition (e.g., 'Business Acquisition')"},
                    "start_date": {"type": "string", "description": "Start date for acquisitions (dd/mm/yyyy)"},
                    "end_date": {"type": "string", "description": "End date for acquisitions (dd/mm/yyyy)"},
                    "acquirer_domain": {"type": "string", "description": "Domain of the acquirer (e.g., 'google.com')"},
                    "sector": {"type": "string", "description": "Sector/feed name (e.g., 'Cybersecurity')"},
                    "min_amount": {"type": "integer", "description": "Minimum acquisition amount in USD"},
                    "max_amount": {"type": "integer", "description": "Maximum acquisition amount in USD"},
                    "country": {"type": "string", "description": "Country to filter by"},
                    "limit": {"type": "integer", "default": 5, "description": "Number of results to retrieve (max 20)"},
                    "offset": {"type": "integer", "default": 0, "description": "Pagination offset"},
                    "sort_by": {"type": "string", "enum": ["announcementDate", "acquisitiontransactionNormalizedAmount"], "default": "announcementDate", "description": "Field to sort results by"},
                    "sort_order": {"type": "string", "enum": ["asc", "desc"], "default": "desc", "description": "Sort order (ascending or descending)"}
                }
            },
        ),
        types.Tool(
            name="search_practice_areas",
            description="Search for practice areas in the Tracxn database",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Practice area name to search for (e.g., 'Enterprise Infrastructure')"},
                    "id": {"type": "string", "description": "Practice area ID to search for"},
                    "limit": {"type": "integer", "default": 5, "description": "Number of results to retrieve (max 20)"},
                    "offset": {"type": "integer", "default": 0, "description": "Pagination offset"}
                }
            },
        ),
        types.Tool(
            name="search_feeds",
            description="Search for feeds in the Tracxn database",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Feed name to search for (e.g., 'Aviation Software')"},
                    "primary_geography": {"type": "string", "description": "Primary geography (e.g., 'Global')"},
                    "id": {"type": "string", "description": "Feed ID to search for"},
                    "limit": {"type": "integer", "default": 5, "description": "Number of results to retrieve (max 20)"},
                    "offset": {"type": "integer", "default": 0, "description": "Pagination offset"}
                }
            },
        ),
        types.Tool(
            name="search_business_models",
            description="Search for business models in the Tracxn database",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Business model name to search for"},
                    "id": {"type": "string", "description": "Business model ID to search for"},
                    "limit": {"type": "integer", "default": 5, "description": "Number of results to retrieve (max 20)"},
                    "offset": {"type": "integer", "default": 0, "description": "Pagination offset"}
                },
                "anyOf": [
                    {"required": ["name"]},
                    {"required": ["id"]}
                ]
            },
        ),
        types.Tool(
            name="diagnose_api_request",
            description="Diagnose API request format issues by trying different variations",
            inputSchema={
                "type": "object",
                "properties": {
                    "endpoint": {"type": "string", "description": "API endpoint to test"},
                    "request_data": {"type": "object", "description": "Initial request data to test"}
                },
                "required": ["endpoint", "request_data"]
            },
        ),
    ]

@server.call_tool()
async def call_tool(
    name: str, arguments: dict
) -> list[types.TextContent | types.ImageContent]:
    """
    Call the specified tool with the provided arguments.
    """
    if name == "search_companies":
        sector = arguments.get("sector", "Cybersecurity")
        
        # Fix: Validate sector to avoid invalid feeds
        valid_sectors = ["Cybersecurity", "Fintech", "Enterprise Infrastructure", "Cloud Infrastructure"]
        if sector not in valid_sectors:
            sector = "Cybersecurity"  # Default to Cybersecurity if invalid sector
        
        limit = min(arguments.get("limit", 5), 20)  # Cap at 20 for performance
        from_val = max(arguments.get("from", 0), 0)  # Ensure from is not negative
        
        # Build the request data with filters
        request_data = {
            "filter": {"feedName": [sector]},
            "size": limit,
            "from": from_val
        }
        
        # Add optional filters if provided
        if "country" in arguments and arguments["country"]:
            request_data["filter"]["country"] = [arguments["country"]]
        
        if "city" in arguments and arguments["city"]:
            request_data["filter"]["city"] = [arguments["city"]]
        
        if "founded_year" in arguments and arguments["founded_year"]:
            request_data["filter"]["foundedYear"] = [arguments["founded_year"]]
        
        if "min_funding" in arguments and "max_funding" in arguments:
            request_data["filter"]["totalMoneyRaised"] = {
                "min": arguments["min_funding"],
                "max": arguments["max_funding"]
            }
        
        # Add sorting if provided
        if "sort_by" in arguments and arguments["sort_by"]:
            sort_order = arguments.get("sort_order", "desc")
            request_data["sort"] = [{arguments["sort_by"]: sort_order}]
        
        result = await search_companies_with_filters(request_data)
        return [types.TextContent(type="text", text=result)]
    
    elif name == "company_lookup":
        domain = arguments.get("domain", "")
        if not domain:
            return [types.TextContent(type="text", text="Error: domain is required")]
        
        result = await company_lookup(domain)
        return [types.TextContent(type="text", text=result)]
    
    elif name == "funded_companies":
        min_funding = arguments.get("min_funding", 10000000)
        max_funding = arguments.get("max_funding", 100000000)
        sector = arguments.get("sector", "Cybersecurity")
        limit = min(arguments.get("limit", 5), 20)  # Cap at 20 for performance
        
        # Build request data
        request_data = {
            "filter": {
                "feedName": [sector],
                "totalMoneyRaised": {
                    "min": min_funding,
                    "max": max_funding
                }
            },
            "size": limit,
            "from": 0
        }
        
        # Add optional filters
        if "country" in arguments and arguments["country"]:
            request_data["filter"]["country"] = [arguments["country"]]
        
        # Add sorting if provided
        if "sort_by" in arguments and arguments["sort_by"]:
            sort_order = arguments.get("sort_order", "desc")
            request_data["sort"] = [{arguments["sort_by"]: sort_order}]
            
        result = await search_companies_with_filters(request_data)
        return [types.TextContent(type="text", text=result)]
    
    elif name == "debug_api_call":
        endpoint = arguments.get("endpoint", "companies")
        data = arguments.get("data", None)
        
        result = await debug_api_call(endpoint, data)
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    
    elif name == "search_companies_by_name":
        company_name = arguments.get("company_name", "")
        if not company_name:
            return [types.TextContent(type="text", text="Error: company_name is required")]
        
        result = await search_companies_by_name(company_name)
        return [types.TextContent(type="text", text=result)]
    
    elif name == "search_transactions":
        # Build filters
        filters = {}
        
        # Add sector filter if provided
        if "sector" in arguments and arguments["sector"]:
            filters["feedName"] = [arguments["sector"]]
        
        # Add round type filter if provided
        if "round_type" in arguments and arguments["round_type"]:
            filters["transactionFundingRoundCategory"] = [arguments["round_type"]]
        
        # Add date range filter if provided
        if "start_date" in arguments and "end_date" in arguments:
            filters["transactionFundingRoundDate"] = {
                "min": arguments["start_date"],
                "max": arguments["end_date"]
            }
        
        # Add amount range filter if provided
        if "min_amount" in arguments and "max_amount" in arguments:
            filters["transactionFundingRoundAmount"] = {
                "min": arguments["min_amount"],
                "max": arguments["max_amount"]
            }
        
        # Add investor filter if provided
        if "investor_domain" in arguments and arguments["investor_domain"]:
            filters["transactionInvestor"] = {
                "transactionInstitutionalInvestorDomain": [arguments["investor_domain"]]
            }
        
        # Add country filter if provided
        if "country" in arguments and arguments["country"]:
            filters["country"] = [arguments["country"]]
        
        # Get pagination and sorting parameters
        limit = min(arguments.get("limit", 5), 20)
        offset = max(arguments.get("offset", 0), 0)
        sort_by = arguments.get("sort_by", "transactionFundingRoundDate")
        sort_order = arguments.get("sort_order", "desc")
        
        result = await search_transactions(filters, sort_by, sort_order, limit, offset)
        return [types.TextContent(type="text", text=result)]
    
    elif name == "search_investors":
        # Build filters
        filters = {}
        
        # Add investor name filter if provided
        if "investor_name" in arguments and arguments["investor_name"]:
            filters["investorDomainName"] = [arguments["investor_name"]]
        
        # Add investor type filter if provided
        if "investor_type" in arguments and arguments["investor_type"]:
            filters["investorType"] = [arguments["investor_type"]]
        
        # Add investor country filter if provided
        if "investor_country" in arguments and arguments["investor_country"]:
            filters["investorCountry"] = [arguments["investor_country"]]
        
        # Add portfolio sector filter if provided
        if "portfolio_sector" in arguments and arguments["portfolio_sector"]:
            filters["feedName"] = [arguments["portfolio_sector"]]
        
        # Add investment score filter if provided
        if "min_investment_score" in arguments:
            filters["tracxnInvestmentScore"] = {
                "min": arguments["min_investment_score"]
            }
        
        # Get pagination parameters
        limit = min(arguments.get("limit", 5), 20)
        offset = max(arguments.get("offset", 0), 0)
        
        result = await search_investors(filters, None, "desc", limit, offset)
        return [types.TextContent(type="text", text=result)]
    
    elif name == "search_acquisitions":
        # Build filters
        filters = {}
        
        # Add acquisition type filter if provided
        if "acquisition_type" in arguments and arguments["acquisition_type"]:
            filters["acquisitionType"] = [arguments["acquisition_type"]]
        
        # Add date range filter if provided
        if "start_date" in arguments and "end_date" in arguments:
            filters["announcementDate"] = {
                "min": arguments["start_date"],
                "max": arguments["end_date"]
            }
        
        # Add acquirer filter if provided
        if "acquirer_domain" in arguments and arguments["acquirer_domain"]:
            filters["acquirerListDomain"] = [arguments["acquirer_domain"]]
        
        # Add sector filter if provided
        if "sector" in arguments and arguments["sector"]:
            filters["feedName"] = [arguments["sector"]]
        
        # Add amount range filter if provided
        if "min_amount" in arguments and "max_amount" in arguments:
            filters["acquisitionAmount"] = {
                "min": arguments["min_amount"],
                "max": arguments["max_amount"]
            }
        
        # Add country filter if provided
        if "country" in arguments and arguments["country"]:
            filters["country"] = [arguments["country"]]
        
        # Get pagination and sorting parameters
        limit = min(arguments.get("limit", 5), 20)
        offset = max(arguments.get("offset", 0), 0)
        sort_by = arguments.get("sort_by", "announcementDate")
        sort_order = arguments.get("sort_order", "desc")
        
        result = await search_acquisitions(filters, sort_by, sort_order, limit, offset)
        return [types.TextContent(type="text", text=result)]
    
    elif name == "search_practice_areas":
        name_param = arguments.get("name")
        id_param = arguments.get("id")
        
        # Convert ID to list if provided
        ids = [id_param] if id_param else None
        
        # Get pagination parameters
        limit = min(arguments.get("limit", 5), 20)
        offset = max(arguments.get("offset", 0), 0)
        
        result = await search_practice_areas(name_param, ids, limit, offset)
        return [types.TextContent(type="text", text=result)]
    
    elif name == "search_feeds":
        name_param = arguments.get("name")
        primary_geography = arguments.get("primary_geography")
        id_param = arguments.get("id")
        
        # Convert ID to list if provided
        ids = [id_param] if id_param else None
        
        # Get pagination parameters
        limit = min(arguments.get("limit", 5), 20)
        offset = max(arguments.get("offset", 0), 0)
        
        result = await search_feeds(name_param, primary_geography, ids, limit, offset)
        return [types.TextContent(type="text", text=result)]
    
    elif name == "search_business_models":
        name_param = arguments.get("name")
        id_param = arguments.get("id")
        
        # Business models API requires at least one filter
        if not name_param and not id_param:
            return [types.TextContent(type="text", text="Error: At least one of 'name' or 'id' is required for business model search")]
        
        # Convert ID to list if provided
        ids = [id_param] if id_param else None
        
        # Get pagination parameters
        limit = min(arguments.get("limit", 5), 20)
        offset = max(arguments.get("offset", 0), 0)
        
        result = await search_business_models(name_param, ids, limit, offset)
        return [types.TextContent(type="text", text=result)]
    
    elif name == "diagnose_api_request":
        endpoint = arguments.get("endpoint")
        request_data = arguments.get("request_data")
        
        if not endpoint or not request_data:
            return [types.TextContent(type="text", text="Error: Both endpoint and request_data are required")]
        
        result = await diagnose_api_request(endpoint, request_data)
        return [types.TextContent(type="text", text=result)]
    
    else:
        return [types.TextContent(type="text", text=f"Error: Unknown tool '{name}'")]

# New helper function to handle searches with advanced filters
async def search_companies_with_filters(request_data: dict, use_playground: bool = True) -> str:
    """
    Search for companies using the provided request data with filters.
    
    Args:
        request_data: Complete request data to send to the API
        use_playground: Whether to use the playground API (default) or production API
    """
    logging.info(f"Searching for companies with filters: {json.dumps(request_data)[:500]}...")
    
    endpoint = "companies"
    result = await tracxn_api_call(endpoint, request_data, use_playground=use_playground)
    
    if "error" in result:
        return f"Error retrieving companies: {result['error']}"
    
    companies = result.get("result", [])
    
    if not companies:
        return f"No companies found matching the criteria"
    
    # Format the results with more detailed information
    formatted_results = []
    for company in companies:
        company_data = {
            "name": company.get("name", "Unknown"),
            "domain": company.get("domain", "N/A"),
            "founded_year": company.get("foundedYear", "N/A"),
            "location": {
                "country": company.get("location", {}).get("country", "N/A"),
                "city": company.get("location", {}).get("city", "N/A"),
                "state": company.get("location", {}).get("state", "N/A")
            },
            "stage": company.get("stage", "N/A"),
            "description": company.get("description", {}).get("short", "N/A"),
            "business_models": list(set(model.get("name", "N/A") for model in company.get("businessModelList", [])))[:5]
        }
        
        # Extract funding info if available
        funding_amount = None
        equity_funding = company.get("totalEquityFunding", {})
        if equity_funding:
            amount_data = equity_funding.get("amount", {})
            usd_data = amount_data.get("USD", {})
            funding_amount = usd_data.get("value")
            if funding_amount:
                company_data["total_funding"] = funding_amount
        
        formatted_results.append(company_data)
    
    return json.dumps({
        "total_count": result.get("total_count", 0),
        "companies": formatted_results,
        "filters_applied": request_data.get("filter", {}),
        "sort": request_data.get("sort", []),
        "pagination": {
            "from": request_data.get("from", 0),
            "size": request_data.get("size", 0),
            "has_more": result.get("total_count", 0) > (request_data.get("from", 0) + request_data.get("size", 0))
        }
    }, indent=2)

# Actual implementation of API functions
async def search_companies(sector: str = "Cybersecurity", limit: int = 5) -> str:
    """
    Search for companies in a specific sector.
    
    Args:
        sector: Sector name (e.g., "Cybersecurity")
        limit: Number of results to return (max 20)
    """
    logging.info(f"Searching for companies in sector: {sector}")
    
    endpoint = "companies"
    request_data = {
        "filter": {"feedName": [sector]},
        "size": min(limit, 20),
        "from": 0
    }
    
    result = await tracxn_api_call(endpoint, request_data)
    
    if "error" in result:
        return f"Error retrieving companies: {result['error']}"
    
    companies = result.get("result", [])
    
    if not companies:
        return f"No companies found in sector: {sector}"
    
    # Format the results
    formatted_results = []
    for company in companies:
        formatted_results.append({
            "name": company.get("name", "Unknown"),
            "domain": company.get("domain", "N/A"),
            "founded_year": company.get("foundedYear", "N/A"),
            "location": {
                "country": company.get("location", {}).get("country", "N/A"),
                "city": company.get("location", {}).get("city", "N/A")
            },
            "stage": company.get("stage", "N/A"),
            "description": company.get("description", {}).get("short", "N/A"),
            "business_model": list(set(model.get("name", "N/A") for model in company.get("businessModelList", [])))[:2]
        })
    
    return json.dumps({
        "total_count": result.get("total_count", 0),
        "sector": sector,
        "companies": formatted_results
    }, indent=2)

async def company_lookup(domain: str, use_playground: bool = True) -> str:
    """
    Get detailed information about a company by domain.
    
    Args:
        domain: Company domain (e.g., "crowdstrike.com")
        use_playground: Whether to use the playground API (default) or production API
    """
    # Clean the domain
    domain_clean = domain.lower().strip()
    if domain_clean.startswith("http://"):
        domain_clean = domain_clean[7:]
    if domain_clean.startswith("https://"):
        domain_clean = domain_clean[8:]
    if domain_clean.startswith("www."):
        domain_clean = domain_clean[4:]
    
    logging.info(f"Looking up company with domain: {domain_clean}")
    
    endpoint = "companies"
    # The domain parameter might need a different format - let's test both
    # Option 1: Single domain as string in a list
    request_data = {
        "filter": {"domain": [domain_clean]},
        "size": 1
    }
    
    result = await tracxn_api_call(endpoint, request_data, use_playground=use_playground)
    
    # If we get an error about domain format, try the alternative format
    if "error" in result and "domain" in str(result["error"]):
        # Option 2: Try without the list brackets
        request_data = {
            "filter": {"domain": domain_clean},
            "size": 1
        }
        result = await tracxn_api_call(endpoint, request_data, use_playground=use_playground)
    
    if "error" in result:
        return f"Error retrieving company information: {result['error']}"
    
    companies = result.get("result", [])
    
    if not companies:
        return f"No company found with domain {domain_clean}"
    
    company = companies[0]
    
    # Extract funding info if available
    funding_amount = None
    equity_funding = company.get("totalEquityFunding", {})
    if equity_funding:
        amount_data = equity_funding.get("amount", {})
        usd_data = amount_data.get("USD", {})
        funding_amount = usd_data.get("value")
    
    # Format response
    response = {
        "name": company.get("name", "Unknown"),
        "domain": company.get("domain", "N/A"),
        "founded_year": company.get("foundedYear", "N/A"),
        "location": {
            "country": company.get("location", {}).get("country", "N/A"),
            "city": company.get("location", {}).get("city", "N/A"),
            "state": company.get("location", {}).get("state", "N/A")
        },
        "stage": company.get("stage", "N/A"),
        "total_funding": funding_amount,
        "description": company.get("description", {}).get("long", "N/A"),
        "business_models": list(set(model.get("name", "N/A") for model in company.get("businessModelList", [])))[:5]
    }
    
    return json.dumps(response, indent=2)

async def funded_companies(
    min_funding: int = 10000000,
    max_funding: int = 100000000,
    sector: str = "Cybersecurity",
    limit: int = 5
) -> str:
    """
    Find companies with specific funding amounts.
    
    Args:
        min_funding: Minimum funding amount in USD
        max_funding: Maximum funding amount in USD
        sector: Sector name (e.g., "Cybersecurity")
        limit: Number of results to return (max 20)
    """
    # Since direct funding filters are not supported, let's fetch more companies
    # and filter locally based on any funding information in the response
    
    logging.info(f"Looking for {sector} companies with funding between ${min_funding} and ${max_funding}")
    
    endpoint = "companies"
    request_data = {
        "filter": {"feedName": [sector]},
        "size": min(100, limit * 5),  # Request more to filter locally
        "from": 0
    }
    
    # Execute the basic sector search
    result = await tracxn_api_call(endpoint, request_data)
    
    if "error" in result:
        return (f"Error retrieving {sector} companies: {result['error']}\n\n"
                f"Request data: {json.dumps(request_data, indent=2)}")
    
    # Process the results to extract and filter companies with funding data
    all_companies = result.get("result", [])
    filtered_companies = []
    
    for company in all_companies:
        # Try multiple potential funding fields based on the observed API response structure
        funding_amount = None
        
        # Check for totalEquityFunding
        equity_funding = company.get("totalEquityFunding", {})
        if equity_funding:
            amount_data = equity_funding.get("amount", {})
            usd_data = amount_data.get("USD", {})
            funding_amount = usd_data.get("value")
        
        # Alternative funding fields to check if totalEquityFunding isn't available
        if funding_amount is None:
            # Try other potential funding fields in the response
            funding_amount = (
                company.get("funding", {}).get("amount", 0) or
                company.get("totalFunding", 0) or
                company.get("fundingAmount", 0)
            )
        
        # Include company in results if we have funding info that's in range
        if funding_amount and min_funding <= funding_amount <= max_funding:
            filtered_companies.append({
                "name": company.get("name", "Unknown"),
                "domain": company.get("domain", "N/A"),
                "founded_year": company.get("foundedYear", "N/A"),
                "location": {
                    "country": company.get("location", {}).get("country", "N/A"),
                    "city": company.get("location", {}).get("city", "N/A")
                },
                "stage": company.get("stage", "N/A"),
                "total_funding": funding_amount,
                "business_model": list(set(m.get("name", "N/A") for m in company.get("businessModelList", [])))[:2]
            })
    
    # Sort by funding amount (descending)
    filtered_companies.sort(key=lambda x: x.get("total_funding", 0), reverse=True)
    
    # Limit to requested number
    filtered_companies = filtered_companies[:limit]
    
    # If we couldn't find any companies with funding info, return top companies anyway
    if not filtered_companies and all_companies:
        top_companies = []
        for company in all_companies[:limit]:
            top_companies.append({
                "name": company.get("name", "Unknown"),
                "domain": company.get("domain", "N/A"),
                "founded_year": company.get("foundedYear", "N/A"),
                "location": {
                    "country": company.get("location", {}).get("country", "N/A"),
                    "city": company.get("location", {}).get("city", "N/A")
                },
                "stage": company.get("stage", "N/A"),
                "note": "Funding information not available"
            })
        
        return json.dumps({
            "note": "Couldn't find companies matching the funding criteria. Showing top companies regardless of funding.",
            "sector": sector,
            "funding_criteria": {"min": min_funding, "max": max_funding},
            "companies": top_companies
        }, indent=2)
    
    return json.dumps({
        "total_found": len(filtered_companies),
        "sector": sector, 
        "funding_criteria": {"min": min_funding, "max": max_funding},
        "companies": filtered_companies
    }, indent=2)

async def search_companies_by_name(company_name: str) -> str:
    """
    Search for companies by name using the Companies Name Search API.
    
    Args:
        company_name: Name of the company to search for
    """
    logging.info(f"Searching for company by name: {company_name}")
    
    endpoint = "companies/search"
    request_data = {
        "filter": {
            "companyName": company_name
        }
    }
    
    result = await tracxn_api_call(endpoint, request_data)
    
    if "error" in result:
        return f"Error searching for company: {result['error']}"
    
    # Handle the response format specific to the name search API
    companies = result.get("result", [])
    
    if not companies:
        return f"No companies found matching name: {company_name}"
    
    # Format the results
    formatted_results = []
    for company in companies:
        formatted_results.append({
            "id": company.get("id", "Unknown"),
            "name": company.get("name", "Unknown"),
            "domain": company.get("domain", "N/A")
        })
    
    return json.dumps({
        "companies": formatted_results,
        "search_term": company_name,
        "count": len(formatted_results)
    }, indent=2)

async def search_transactions(filters: dict = None, sort_by: str = None, sort_order: str = "desc", limit: int = 5, offset: int = 0) -> str:
    """
    Search for funding rounds/transactions with filters.
    
    Args:
        filters: Dictionary of filter criteria
        sort_by: Field to sort by (e.g., 'transactionFundingRoundAmount')
        sort_order: Sort direction ('asc' or 'desc')
        limit: Number of results to return
        offset: Pagination offset
    """
    logging.info(f"Searching for transactions with filters: {filters}")
    
    # Fix: The API expects "sortField" instead of using the "sort" array format
    request_data = {
        "size": min(limit, 20),
        "from": offset,
        "sortField": sort_by if sort_by else "transactionFundingRoundDate",
        "sortOrder": sort_order
    }
    
    # Add filters if provided
    if filters:
        request_data["filter"] = filters
    
    endpoint = "transactions"
    result = await tracxn_api_call(endpoint, request_data)
    
    if "error" in result:
        return f"Error retrieving transactions: {result['error']}"
    
    transactions = result.get("result", [])
    
    if not transactions:
        return "No transactions found matching the criteria"
    
    # Format the results
    formatted_results = []
    for transaction in transactions:
        # Extract company details
        company_details = transaction.get("companyDetails", {})
        
        # Build transaction data
        transaction_data = {
            "id": transaction.get("id", "N/A"),
            "type": transaction.get("type", "N/A"),
            "name": transaction.get("name", "N/A"),
            "funding_date": transaction.get("fundingDate", "N/A"),
            "company": {
                "name": company_details.get("name", "N/A"),
                "domain": company_details.get("domain", "N/A"),
                "location": company_details.get("location", {})
            }
        }
        
        # Add amount if available
        amount = transaction.get("amount", {})
        if amount:
            usd_amount = amount.get("USD", {})
            if usd_amount:
                transaction_data["amount_usd"] = usd_amount.get("value")
        
        # Add investors if available
        investor_list = transaction.get("investorList", [])
        if investor_list:
            transaction_data["investors"] = [
                {
                    "name": investor.get("name", "N/A"),
                    "domain": investor.get("domain", "N/A"),
                    "type": investor.get("type", "N/A"),
                    "is_lead": investor.get("isLead", False)
                }
                for investor in investor_list[:5]  # Limit to first 5 investors
            ]
        
        formatted_results.append(transaction_data)
    
    return json.dumps({
        "total_count": result.get("total_count", 0),
        "transactions": formatted_results,
        "filters_applied": request_data.get("filter", {}),
        "sort": request_data.get("sort", []),
        "pagination": {
            "from": request_data.get("from", 0),
            "size": request_data.get("size", 0),
            "has_more": result.get("total_count", 0) > (request_data.get("from", 0) + request_data.get("size", 0))
        }
    }, indent=2)

async def search_investors(filters: dict = None, sort_by: str = None, sort_order: str = "desc", limit: int = 5, offset: int = 0) -> str:
    """
    Search for investors with filters.
    
    Args:
        filters: Dictionary of filter criteria
        sort_by: Field to sort by
        sort_order: Sort direction ('asc' or 'desc')
        limit: Number of results to return
        offset: Pagination offset
    """
    logging.info(f"Searching for investors with filters: {filters}")
    
    # Build request data
    request_data = {
        "size": min(limit, 20),
        "from": offset
    }
    
    # Add filters if provided
    if filters:
        request_data["filter"] = filters
    
    # Add sorting if provided
    if sort_by:
        request_data["sort"] = [{sort_by: sort_order}]
    
    endpoint = "investors"
    result = await tracxn_api_call(endpoint, request_data)
    
    if "error" in result:
        return f"Error retrieving investors: {result['error']}"
    
    investors = result.get("result", [])
    
    if not investors:
        return "No investors found matching the criteria"
    
    # Format the results
    formatted_results = []
    for investor in investors:
        investor_data = {
            "name": investor.get("name", "N/A"),
            "domain": investor.get("domain", "N/A"),
            "type": investor.get("type", "N/A"),
            "investor_type": investor.get("investorType", "N/A")
        }
        
        # Add locations if available
        locations = investor.get("locations", [])
        if locations:
            investor_data["locations"] = [
                {
                    "country": location.get("country", "N/A"),
                    "city": location.get("city", "N/A"),
                    "state": location.get("state", "N/A")
                }
                for location in locations[:3]  # Limit to first 3 locations
            ]
        
        # Add description if available
        description = investor.get("description", {})
        if description:
            investor_data["description"] = description.get("short", "N/A")
        
        # Add investment score if available
        score = investor.get("tracxnInvestmentScore")
        if score:
            investor_data["investment_score"] = score
        
        formatted_results.append(investor_data)
    
    return json.dumps({
        "total_count": result.get("total_count", 0),
        "investors": formatted_results,
        "filters_applied": request_data.get("filter", {}),
        "sort": request_data.get("sort", []),
        "pagination": {
            "from": request_data.get("from", 0),
            "size": request_data.get("size", 0),
            "has_more": result.get("total_count", 0) > (request_data.get("from", 0) + request_data.get("size", 0))
        }
    }, indent=2)

async def search_acquisitions(filters: dict = None, sort_by: str = None, sort_order: str = "desc", limit: int = 5, offset: int = 0) -> str:
    """
    Search for acquisitions with filters.
    
    Args:
        filters: Dictionary of filter criteria
        sort_by: Field to sort by
        sort_order: Sort direction ('asc' or 'desc')
        limit: Number of results to return
        offset: Pagination offset
    """
    logging.info(f"Searching for acquisitions with filters: {filters}")
    
    # Fix: The API expects "sortField" instead of using the "sort" array format
    request_data = {
        "size": min(limit, 20),
        "from": offset,
        "sortField": sort_by if sort_by else "announcementDate",
        "sortOrder": sort_order
    }
    
    # Add filters if provided
    if filters:
        request_data["filter"] = filters
    
    endpoint = "acquisitiontransactions"
    result = await tracxn_api_call(endpoint, request_data)
    
    if "error" in result:
        return f"Error retrieving acquisitions: {result['error']}"
    
    acquisitions = result.get("result", [])
    
    if not acquisitions:
        return "No acquisitions found matching the criteria"
    
    # Format the results
    formatted_results = []
    for acquisition in acquisitions:
        # Extract company info
        company = acquisition.get("company", {})
        
        # Extract acquirer info
        acquirer_list = acquisition.get("acquirerList", [])
        acquirers = []
        if acquirer_list:
            for acquirer in acquirer_list[:3]:  # Limit to first 3 acquirers
                acquirers.append({
                    "name": acquirer.get("name", "N/A"),
                    "domain": acquirer.get("domain", "N/A")
                })
        
        # Extract basic round details
        basic_round = acquisition.get("basicRoundDetail", {})
        
        acquisition_data = {
            "id": acquisition.get("id", "N/A"),
            "status": acquisition.get("status", "N/A"),
            "company": {
                "name": company.get("name", "N/A"),
                "domain": company.get("domain", "N/A")
            },
            "acquirers": acquirers,
            "announcement_date": basic_round.get("announcementDate", "N/A"),
            "acquisition_type": basic_round.get("acquisitionType", "N/A")
        }
        
        # Add amount if available
        if "normalizedAmount" in basic_round:
            usd_amount = basic_round.get("normalizedAmount", {}).get("USD", {})
            if usd_amount:
                acquisition_data["amount_usd"] = usd_amount.get("value")
        
        # Add stake acquired if available
        stake = basic_round.get("stakesAcquired")
        if stake:
            acquisition_data["stake_acquired"] = stake
        
        formatted_results.append(acquisition_data)
    
    return json.dumps({
        "total_count": result.get("total_count", 0),
        "acquisitions": formatted_results,
        "filters_applied": request_data.get("filter", {}),
        "sort": request_data.get("sort", []),
        "pagination": {
            "from": request_data.get("from", 0),
            "size": request_data.get("size", 0),
            "has_more": result.get("total_count", 0) > (request_data.get("from", 0) + request_data.get("size", 0))
        }
    }, indent=2)

async def search_practice_areas(name: str = None, ids: list = None, limit: int = 5, offset: int = 0) -> str:
    """
    Search for practice areas.
    
    Args:
        name: Practice area name to search for
        ids: List of practice area IDs
        limit: Number of results to return
        offset: Pagination offset
    """
    logging.info(f"Searching for practice areas with name: {name}, ids: {ids}")
    
    # Build request data
    request_data = {
        "size": min(limit, 20),
        "from": offset
    }
    
    # Add filters
    filters = {}
    if name:
        filters["name"] = [name]
    if ids:
        filters["id"] = ids
    
    if filters:
        request_data["filter"] = filters
    
    endpoint = "practiceareas"
    result = await tracxn_api_call(endpoint, request_data)
    
    if "error" in result:
        return f"Error retrieving practice areas: {result['error']}"
    
    practice_areas = result.get("result", [])
    
    if not practice_areas:
        return "No practice areas found matching the criteria"
    
    # Format the results
    formatted_results = []
    for area in practice_areas:
        practice_area_data = {
            "id": area.get("id", "N/A"),
            "name": area.get("name", "N/A"),
            "category": area.get("category", "N/A"),
            "tracxn_id": area.get("tracxnId", "N/A"),
            "companies_url": area.get("companiesInEntireTreeUrl", "N/A")
        }
        
        # Add feed list if available
        feed_list = area.get("feedList", [])
        if feed_list:
            practice_area_data["feeds"] = [
                {
                    "id": feed.get("id", "N/A"),
                    "name": feed.get("name", "N/A")
                }
                for feed in feed_list[:5]  # Limit to first 5 feeds
            ]
        
        formatted_results.append(practice_area_data)
    
    return json.dumps({
        "total_count": result.get("total_count", 0),
        "practice_areas": formatted_results,
        "filters_applied": request_data.get("filter", {}),
        "pagination": {
            "from": request_data.get("from", 0),
            "size": request_data.get("size", 0),
            "has_more": result.get("total_count", 0) > (request_data.get("from", 0) + request_data.get("size", 0))
        }
    }, indent=2)

async def search_feeds(name: str = None, primary_geography: str = None, ids: list = None, limit: int = 5, offset: int = 0) -> str:
    """
    Search for feeds with filters.
    
    Args:
        name: Feed name to search for
        primary_geography: Primary geography of the feed (e.g., "Global")
        ids: List of feed IDs
        limit: Number of results to return
        offset: Pagination offset
    """
    logging.info(f"Searching for feeds with name: {name}, primary_geography: {primary_geography}, ids: {ids}")
    
    # Build request data
    request_data = {
        "size": min(limit, 20),
        "from": offset
    }
    
    # Add filters
    filters = {}
    if name:
        filters["name"] = [name]
    if primary_geography:
        filters["primaryGeography"] = [primary_geography]
    if ids:
        filters["id"] = ids
    
    if filters:
        request_data["filter"] = filters
    
    endpoint = "feeds"
    result = await tracxn_api_call(endpoint, request_data)
    
    if "error" in result:
        return f"Error retrieving feeds: {result['error']}"
    
    feeds = result.get("result", [])
    
    if not feeds:
        return "No feeds found matching the criteria"
    
    # Format the results
    formatted_results = []
    for feed in feeds:
        feed_data = {
            "id": feed.get("id", "N/A"),
            "name": feed.get("name", "N/A"),
            "tracxn_id": feed.get("tracxnId", "N/A"),
            "primary_geo": feed.get("primaryGeo", "N/A"),
            "curation_type": feed.get("curationType", "N/A"),
            "companies_url": feed.get("companiesInEntireTreeUrl", "N/A")
        }
        
        # Add description if available
        description = feed.get("description")
        if description:
            feed_data["description"] = description
        
        # Add practice area list if available
        practice_area_list = feed.get("practiceAreaList", [])
        if practice_area_list:
            feed_data["practice_areas"] = [
                {
                    "id": area.get("id", "N/A"),
                    "name": area.get("name", "N/A")
                }
                for area in practice_area_list[:3]  # Limit to first 3 practice areas
            ]
        
        formatted_results.append(feed_data)
    
    return json.dumps({
        "total_count": result.get("total_count", 0),
        "feeds": formatted_results,
        "filters_applied": request_data.get("filter", {}),
        "pagination": {
            "from": request_data.get("from", 0),
            "size": request_data.get("size", 0),
            "has_more": result.get("total_count", 0) > (request_data.get("from", 0) + request_data.get("size", 0))
        }
    }, indent=2)

async def search_business_models(name: str = None, ids: list = None, limit: int = 5, offset: int = 0) -> str:
    """
    Search for business models.
    
    Args:
        name: Business model name to search for
        ids: List of business model IDs
        limit: Number of results to return
        offset: Pagination offset
    """
    logging.info(f"Searching for business models with name: {name}, ids: {ids}")
    
    # Build request data
    request_data = {
        "size": min(limit, 20),
        "from": offset
    }
    
    # Add filters (at least one filter is required for this API)
    filters = {}
    if name:
        filters["name"] = [name]
    if ids:
        filters["id"] = ids
    
    if not filters:
        return "Error: Business Model API requires at least one filter (name or id)"
    
    request_data["filter"] = filters
    
    endpoint = "businessmodels"
    result = await tracxn_api_call(endpoint, request_data)
    
    if "error" in result:
        return f"Error retrieving business models: {result['error']}"
    
    models = result.get("result", [])
    
    if not models:
        return "No business models found matching the criteria"
    
    # Format the results
    formatted_results = []
    for model in models:
        model_data = {
            "id": model.get("id", "N/A"),
            "name": model.get("name", "N/A"),
            "node_type": model.get("nodeType", "N/A"),
            "tracxn_id": model.get("tracxnId", "N/A"),
            "feed_id": model.get("feedId", "N/A"),
            "feed_name": model.get("feedName", "N/A"),
            "absolute_name": model.get("absoluteName", "N/A"),
            "companies_in_node_url": model.get("companiesInNodeOnlyUrl", "N/A"),
            "companies_in_tree_url": model.get("companiesInEntireTreeUrl", "N/A")
        }
        
        # Add description if available
        description = model.get("description")
        if description:
            model_data["description"] = description
        
        # Add path information
        full_path_string = model.get("fullPathString")
        if full_path_string:
            model_data["full_path"] = full_path_string
        
        # Add notable companies if available
        notable_companies = model.get("notableCompanies")
        if notable_companies:
            model_data["notable_companies"] = notable_companies
        
        formatted_results.append(model_data)
    
    return json.dumps({
        "total_count": result.get("total_count", 0),
        "business_models": formatted_results,
        "filters_applied": request_data.get("filter", {}),
        "pagination": {
            "from": request_data.get("from", 0),
            "size": request_data.get("size", 0),
            "has_more": result.get("total_count", 0) > (request_data.get("from", 0) + request_data.get("size", 0))
        }
    }, indent=2)

async def diagnose_api_request(endpoint: str, request_data: dict) -> str:
    """
    Try different variations of an API request to diagnose format issues.
    
    Args:
        endpoint: API endpoint to test
        request_data: Initial request data to test and modify
    """
    logging.info(f"Diagnosing API request format for endpoint: {endpoint}")
    
    # Try the original request
    logging.info(f"Trying original request format: {json.dumps(request_data)}")
    original_result = await tracxn_api_call(endpoint, request_data)
    
    results = {
        "original_request": {
            "data": request_data,
            "result": original_result
        },
        "variations": []
    }
    
    # If we got an error, try some variations
    if "error" in original_result:
        error_message = str(original_result["error"])
        logging.info(f"Original request failed with error: {error_message}")
        
        # Test for sort field format issues
        if "sort" in request_data and "sortField" not in request_data:
            variation = request_data.copy()
            # Extract sort field and order from the sort array
            sort_item = variation["sort"][0] if variation["sort"] else {}
            sort_field = list(sort_item.keys())[0] if sort_item else "defaultSortField"
            sort_order = sort_item.get(sort_field, "desc")
            
            # Add as sortField and sortOrder
            variation["sortField"] = sort_field
            variation["sortOrder"] = sort_order
            del variation["sort"]
            
            logging.info(f"Trying with sortField format: {json.dumps(variation)}")
            variation_result = await tracxn_api_call(endpoint, variation)
            
            results["variations"].append({
                "description": "Converted 'sort' array to 'sortField' and 'sortOrder'",
                "data": variation,
                "result": variation_result
            })
        
        # Test for domain format issues
        if "filter" in request_data and "domain" in request_data["filter"]:
            variation = copy.deepcopy(request_data)
            domain_value = variation["filter"]["domain"]
            
            # If domain is a list, try string
            if isinstance(domain_value, list):
                variation["filter"]["domain"] = domain_value[0] if domain_value else ""
                logging.info(f"Trying with domain as string: {json.dumps(variation)}")
                variation_result = await tracxn_api_call(endpoint, variation)
                
                results["variations"].append({
                    "description": "Converted 'domain' from list to string",
                    "data": variation,
                    "result": variation_result
                })
            # If domain is a string, try list
            else:
                variation["filter"]["domain"] = [domain_value]
                logging.info(f"Trying with domain as list: {json.dumps(variation)}")
                variation_result = await tracxn_api_call(endpoint, variation)
                
                results["variations"].append({
                    "description": "Converted 'domain' from string to list",
                    "data": variation,
                    "result": variation_result
                })
    
    return json.dumps(results, indent=2)

async def main():
    """Main entry point for the Tracxn MCP server."""
    API_KEY = os.getenv("TRACXN_ACCESS_TOKEN")
    if not API_KEY:
        raise ValueError("TRACXN_ACCESS_TOKEN environment variable is required")

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="tracxn-mcp",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

def cli():
    """CLI entry point for tracxn-mcp"""
    logging.basicConfig(level=logging.INFO)

    API_KEY = os.getenv("TRACXN_ACCESS_TOKEN")
    if not API_KEY:
        print(
            "Error: TRACXN_ACCESS_TOKEN environment variable is required",
            file=sys.stderr,
        )
        sys.exit(1)

    # Log which key is being used (first 4 chars and last 4 chars for security)
    api_key_safe = f"{API_KEY[:4]}...{API_KEY[-4:]}" if len(API_KEY) > 8 else "***invalid***"
    logging.info(f"Using Tracxn API key: {api_key_safe}")
    
    logging.info("Starting Tracxn MCP server...")
    asyncio.run(main())

if __name__ == "__main__":
    cli()