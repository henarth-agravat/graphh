from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import os
import re
from datetime import datetime
from typing import Dict, List, Optional

app = Flask(__name__)

# Get allowed origins from environment variable or use defaults
ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', 'http://localhost:5173,https://stockpro-seven.vercel.app').split(',')

# Updated CORS configuration
CORS(app, resources={
    r"/api/*": {
        "origins": ALLOWED_ORIGINS,
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "Accept"],
        "supports_credentials": True
    }
})

# Add security headers middleware
@app.after_request
def add_security_headers(response):
    response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Cross-Origin-Opener-Policy'] = 'same-origin-allow-popups'
    response.headers['Cross-Origin-Resource-Policy'] = 'cross-origin'
    
    # Handle preflight requests
    if request.method == 'OPTIONS':
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Accept'
        response.headers['Access-Control-Max-Age'] = '3600'
    
    return response

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Windows; Windows x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.114 Safari/537.36'
}

class RobustScreenerScraper:
    def _init_(self, headers=None):
        self.headers = headers or HEADERS
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36'
        ]

    def search_companies(self, query: str) -> List[Dict]:
        """
        Search for companies on Screener.in
        
        :param query: Company name or partial name to search
        :return: List of matching companies
        """
        search_url = f"https://www.screener.in/api/company/search/?q={query}&v={len(query)}&fts=1"
        try:
            response = requests.get(search_url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            return [company for company in data if company.get('id') is not None]
        except Exception as e:
            print(f"Error searching companies: {e}")
            return []

    def fetch_page(self, url: str, retry_count: int = 3) -> Optional[str]:
        """
        Fetch webpage with multiple retry and user agent rotation
        """
        for attempt in range(retry_count):
            try:
                # Rotate user agents
                self.headers['User-Agent'] = self.user_agents[attempt % len(self.user_agents)]
                
                response = requests.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()
                return response.text
            except (requests.RequestException, requests.Timeout) as e:
                print(f"Fetch attempt {attempt + 1} failed: {e}")
                if attempt == retry_count - 1:
                    print(f"Failed to fetch {url} after {retry_count} attempts")
                    return None

    def extract_financial_data(self, html_content: str, section_id: str) -> List[Dict]:
        """
        Robust method to extract financial data from different sections
        """
        if not html_content:
            return []

        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            section = soup.find('section', id=section_id, class_='card card-large')

            if not section:
                print(f"Section {section_id} not found")
                return []

            table = section.find('table', class_='data-table')
            if not table:
                print(f"No data table found for section {section_id}")
                return []

            # Advanced header extraction with fallback
            headers = self._extract_headers(table)
            
            # Robust data extraction
            data = self._extract_table_data(table, headers)

            # Data cleaning and validation
            cleaned_data = self._clean_and_validate_data(data)

            return cleaned_data

        except Exception as e:
            print(f"Error extracting data for {section_id}: {e}")
            return []

    def _extract_headers(self, table) -> List[str]:
        """
        Intelligent header extraction with multiple fallback strategies
        """
        # Try standard header extraction
        headers = [th.get_text(strip=True) for th in table.find('thead').find_all('th')]
        
        # If headers are empty or problematic, try alternative strategies
        if not headers or len(headers) < 2:
            # Try extracting from first row
            first_row = table.find('tbody').find('tr')
            if first_row:
                headers = [td.get_text(strip=True) for td in first_row.find_all('td')]
        
        return headers

    def _extract_table_data(self, table, headers) -> List[Dict]:
        """
        Robust table data extraction with error handling and row names
        """
        data = []
        for row in table.find('tbody').find_all('tr'):
            cells = row.find_all('td')
            
            # Ensure first cell is the row name (item description)
            if not cells:
                continue

            row_name = cells[0].get_text(strip=True)
            
            # Skip rows with inconsistent cell count
            if len(cells) != len(headers):
                continue

            row_data = {'row_name': row_name}
            for header, cell in zip(headers, cells):
                # Clean and standardize cell text
                cell_text = cell.get_text(strip=True)
                row_data[header] = self._clean_cell_value(cell_text)
            
            data.append(row_data)
        
        return data

    def _clean_cell_value(self, value: str) -> str:
        """
        Clean and standardize cell values
        """
        # Remove commas, handle numeric values
        value = value.replace(',', '')
        
        # Remove any non-numeric characters except decimal point
        value = re.sub(r'[^\d.-]', '', value)
        
        return value.strip()

    def _clean_and_validate_data(self, data: List[Dict]) -> List[Dict]:
        """
        Additional data cleaning and validation
        """
        cleaned_data = []
        for item in data:
            # Remove entries with no meaningful data
            if len(item) <= 1:  # only row_name present
                continue
            cleaned_data.append(item)
        
        return cleaned_data

    def scrape_financial_sections(self, company_code: str) -> Dict:
        """
        Comprehensive financial data extraction
        """
        base_url = f"https://www.screener.in/company/{company_code}/consolidated/"
        
        # Fetch the main page
        html_content = self.fetch_page(base_url)
        
        if not html_content:
            return {"error": "Could not fetch company page"}

        # Extract financial sections
        financial_sections = {
            'profit_loss': self.extract_financial_data(html_content, 'profit-loss'),
            'balance_sheet': self.extract_financial_data(html_content, 'balance-sheet'),
            'cash_flow': self.extract_financial_data(html_content, 'cash-flow'),
            'quarterly_results': self.extract_financial_data(html_content, 'quarters')
        }

        # Add metadata
        result = {
            'stock_name': company_code,
            'extraction_date': datetime.now().isoformat(),
            'data': financial_sections
        }

        return result

@app.route('/api/stock-data', methods=['POST'])
def get_stock_data():
    """
    API endpoint to fetch stock data based on company name/code
    
    :return: JSON response with company financial data
    """
    try:
        data = request.get_json()
        stock_name = data.get('stockName')
        
        if not stock_name:
            return jsonify({'error': 'Stock name is required'}), 400

        # Search for the company
        screener = RobustScreenerScraper()
        search_results = screener.search_companies(stock_name)
        
        if not search_results:
            return jsonify({'error': 'No company found with the given name'}), 404
        
        # Use the first matching company
        first_company = search_results[0]
        company_code = first_company.get('code', stock_name)
        
        # Fetch all data
        result = screener.scrape_financial_sections(company_code)
        
        if result:
            return jsonify(result)
        else:
            return jsonify({'error': 'Failed to fetch stock data'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/search-companies', methods=['GET'])
def search_companies():
    """
    API endpoint to search for companies
    
    :return: JSON response with matching companies
    """
    try:
        query = request.args.get('query', '')
        if not query:
            return jsonify({'error': 'Search query is required'}), 400
            
        screener = RobustScreenerScraper()
        results = screener.search_companies(query)
        return jsonify(results)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """
    Health check endpoint
    
    :return: JSON response indicating service is healthy
    """
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)