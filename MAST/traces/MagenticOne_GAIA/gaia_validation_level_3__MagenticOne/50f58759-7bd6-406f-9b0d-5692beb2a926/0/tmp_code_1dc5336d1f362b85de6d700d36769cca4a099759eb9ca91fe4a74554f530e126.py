import mwclient

# Connect to Wikipedia
site = mwclient.Site('en.wikipedia.org')

# Function to get revisions of a page
def get_revisions(page_name, start_date, end_date):
    page = site.pages[page_name]
    revisions = page.revisions(start=start_date, end=end_date, dir='newer')
    return revisions

# Function to count Twitter/X citations
def count_citations(revisions):
    citation_count = 0
    for revision in revisions:
        if 'twitter.com' in revision['*']:
            citation_count += 1
    return citation_count

# Example usage: Get revisions for a sample page
page_name = 'Sample_Page'
start_date = '2023-06-01'
end_date = '2023-06-30'

revisions = get_revisions(page_name, start_date, end_date)
citation_count = count_citations(revisions)

print(f'Total Twitter/X citations: {citation_count}')
