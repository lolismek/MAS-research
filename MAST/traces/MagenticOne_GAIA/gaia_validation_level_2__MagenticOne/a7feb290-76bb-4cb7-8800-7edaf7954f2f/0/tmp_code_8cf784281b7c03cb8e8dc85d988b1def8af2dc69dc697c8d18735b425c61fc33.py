import requests
from bs4 import BeautifulSoup

def count_ps_versions(url):
    # Send a GET request to the URL
    response = requests.get(url)
    response.raise_for_status()  # Check for request errors
    
    # Parse the page content
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find all entries with 'other' links
    articles = soup.find_all('a', string='other')
    
    # Count the articles with 'other' links
    count = len(articles)
    
    print(f"Number of articles with 'other' links (potential ps versions): {count}")

# URL for January 2020 High Energy Physics - Lattice articles
url = "https://arxiv.org/list/hep-lat/2020-01"
count_ps_versions(url)
