from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
6
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Windows; Windows x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.114 Safari/537.36'
}

class Screener:
    def __init__(self, headers):
        self.headers = headers

def extract_data(self, html_content, section_id):
    if not html_content:
        return {}
        
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        section = soup.find('section', id=section_id, class_='card card-large')
        
        if not section:
            print(f"Section {section_id} not found")
            return {}
            
        table = section.find('table', class_='data-table')
        if not table:
            print(f"No data table found for section {section_id}")
            return {}
            
        headers = [th.text.strip() for th in table.find('thead').find_all('th')]
        data = []
        
        for row in table.find('tbody').find_all('tr'):
            cells = row.find_all('td')
            if len(cells) == len(headers):
                row_data = {headers[0]: cells[0].text.strip()}
                for header, cell in zip(headers[1:], cells[1:]):
                    row_data[header] = cell.text.strip()
                data.append(row_data)
            
        return data
    except Exception as e:
        print(f"Error extracting data for {section_id}: {e}")
        return {}

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
@app.route('/api/stock-data', methods=['POST'])
def get_stock_data():
    try:
        data = request.get_json()
        stock_name = data.get('stockName')
        
        if not stock_name:
            return jsonify({'error': 'Stock name is required'}), 400

        # Search for the company first
        screener = Screener(HEADERS)
        search_results = screener.search_companies(stock_name)
        
        if not search_results:
            return jsonify({'error': 'No company found with the given name'}), 404
        
        # Use the first matching company
        first_company = search_results[0]
        company = Company(first_company['name'], f"/company/{first_company['code']}/")
        
        # Fetch all data
        result = company.fetch_all_data(screener)
        
        if result:
            # Add metadata
            response_data = {
                'stock_name': company.name,
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