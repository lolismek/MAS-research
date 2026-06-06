import mwclient
from datetime import datetime, timedelta

# Connect to Wikipedia
site = mwclient.Site('en.wikipedia.org')

# Function to get revisions for a page
def get_revisions(page_name, start_date, end_date):
    print(f"Fetching revisions for {page_name} from {start_date} to {end_date}...")
    page = site.pages[page_name]
    revisions = page.revisions(start=start_date, end=end_date, dir='newer')
    return list(revisions)

# Function to count Twitter/X citations
def count_citations(revisions):
    citation_count = 0
    for revision in revisions:
        if 'twitter.com' in revision.get('*', ''):
            citation_count += 1
    return citation_count

# Example usage: Get revisions for a sample page and count citations
page_name = 'Sample_Page'  # Change this to the desired page
start_date = '2023-06-01'
end_date = '2023-06-30'

revisions = get_revisions(page_name, start_date, end_date)
citation_count = count_citations(revisions)

print(f'Total Twitter/X citations found: {citation_count}')

# Extended: Calculate daily citation counts for August
def daily_citation_counts(page_name):
    august_dates = [datetime(2023, 8, day) for day in range(1, 32)]
    date_format = "%Y-%m-%d"
    
    for date in august_dates:
        start_date = date.strftime(date_format)
        end_date = (date + timedelta(days=1)).strftime(date_format)
        
        revisions = get_revisions(page_name, start_date, end_date)
        citation_count = count_citations(revisions)
        
        print(f"Date: {start_date}, Citations: {citation_count}")

# Run analysis for the desired page
daily_citation_counts(page_name)
