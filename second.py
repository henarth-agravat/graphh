from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Windows; Windows x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.114 Safari/537.36'
}

class Screener:
    def __init__(self, headers):
        self.headers = headers

    def search_companies(self, query):
        search_url = f"https://www.screener.in/api/company/search/?q={query}&v={len(query)}&fts=1"
        try:
            response = requests.get(search_url)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                return [company for company in data if company.get('id') is not None]
            return []
        except Exception as e:
            print(f"Error searching companies: {e}")
            return []

    def fetch_company_page(self, company_url):
        base_url = "https://www.screener.in"
        full_url = base_url + company_url
        try:
            response = requests.get(full_url)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Error fetching company page: {e}")
            return None

    def extract_data(self, html_content, section_id):
        if not html_content:
            return {}
            
        soup = BeautifulSoup(html_content, 'html.parser')
        section = soup.find('section', id=section_id, class_='card card-large')
        
        if not section:
            return {}
            
        table = section.find('table', class_='data-table')
        if not table:
            return {}
            
        headers = [th.text.strip() for th in table.find('thead').find_all('th')]
        data = []
        
        for row in table.find('tbody').find_all('tr'):
            cells = row.find_all('td')
            row_data = {headers[0]: cells[0].text.strip()}
            for header, cell in zip(headers[1:], cells[1:]):
                row_data[header] = cell.text.strip()
            data.append(row_data)
            
        return data

class Company:
    def __init__(self, name, url):
        self.name = name
        self.url = url
        self.data = {}

    def fetch_all_data(self, screener: Screener):
        html_content = screener.fetch_company_page(self.url)
        if html_content:
            self.data = {
                'profit_loss': screener.extract_data(html_content, 'profit-loss'),
                'balance_sheet': screener.extract_data(html_content, 'balance-sheet'),
                'cash_flow': screener.extract_data(html_content, 'cash-flow'),
                'quarterly_results': screener.extract_data(html_content, 'quarters')
            }
            return self.data
        return None

@app.route('/api/stock-data', methods=['POST'])
def get_stock_data():
    try:
        data = request.get_json()
        stock_name = data.get('stockName')
        
        if not stock_name:
            return jsonify({'error': 'Stock name is required'}), 400

        # Initialize screener
        screener = Screener(HEADERS)
        
        # Create company instance
        company = Company(stock_name, f"/company/{stock_name}/")
        
        # Fetch all data
        result = company.fetch_all_data(screener)
        
        if result:
            # Add metadata
            response_data = {
                'stock_name': stock_name,
                'extraction_date': datetime.now().isoformat(),
                'data': result
            }
            return jsonify(response_data)
        else:
            return jsonify({'error': 'Failed to fetch stock data'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/search-companies', methods=['GET'])
def search_companies():
    try:
        query = request.args.get('query', '')
        if not query:
            return jsonify({'error': 'Search query is required'}), 400
            
        screener = Screener(HEADERS)
        results = screener.search_companies(query)
        return jsonify(results)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)