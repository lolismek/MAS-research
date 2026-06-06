import requests
import json

# Define the criteria
criteria = {
    'MolecularWeight': {'min': 0, 'max': 100},
    'HeavyAtomCount': {'min': 6, 'max': 6},
    'HBondDonorCount': {'min': 0, 'max': 1},
    'Complexity': {'min': 10, 'max': 15}
}

# Base URL for the PubChem PUG REST API
base_url = 'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/property/'

# Function to perform API request
def query_pubchem(criteria):
    headers = {'Content-Type': 'application/json'}
    response = requests.post(base_url + 'json', headers=headers, json=criteria)
    if response.status_code == 200:
        return response.json()
    print(f'Response Code: {response.status_code}')

# Query PubChem
results = query_pubchem(criteria)

# Save results to file
with open('pubchem_results.json', 'w') as f:
    json.dump(results, f)
print('Results saved to pubchem_results.json.')
