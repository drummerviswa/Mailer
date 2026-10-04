import urllib3
import requests
from bs4 import BeautifulSoup
urllib3.disable_warnings()

query = 'TENSORHUB TECHNOLOGIES official website'
r = requests.post('https://lite.duckduckgo.com/lite/', data={'q': query}, verify=False, timeout=8)
print('DDG Lite Status:', r.status_code)
soup = BeautifulSoup(r.text, 'html.parser')
links = [a.get('href') for a in soup.select('a.result-link')]
print('DDG Lite Links:', links[:3])

# Also test DuckDuckGo HTML
r2 = requests.post('https://html.duckduckgo.com/html/', data={'q': query}, verify=False, timeout=8)
print('DDG HTML Status:', r2.status_code)
soup2 = BeautifulSoup(r2.text, 'html.parser')
links2 = [a.text.strip() for a in soup2.select('.result__url')]
print('DDG HTML Links:', links2[:3])

# Also test Bing Search HTML
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
r3 = requests.get(f'https://www.bing.com/search?q={query}', headers=headers, verify=False, timeout=8)
print('Bing Status:', r3.status_code)
soup3 = BeautifulSoup(r3.text, 'html.parser')
b_links = [a.get('href') for a in soup3.select('li.b_algo h2 a')]
print('Bing Links:', b_links[:3])
