import pandas as pd

def count_even_address_awning_clients(file_path):
    # Load the Excel file
    df = pd.read_excel(file_path, sheet_name='Sheet1')
    
    # Extract the street addresses
    street_addresses = df['Street Address']
    
    # Function to determine if a street number is even
    def is_even_address(street_address):
        # Extract the leading street number
        street_number = int(street_address.split()[0])
        # Return True if even, else False
        return street_number % 2 == 0
    
    # Count even-numbered addresses
    even_address_count = sum(is_even_address(address) for address in street_addresses)
    
    print(f"Number of clients receiving the sunset awning design: {even_address_count}")

# Specify the file path
file_path = '4d51c4bf-4b0e-4f3d-897b-3f6687a7d9f2.xlsx'

# Execute the function
count_even_address_awning_clients(file_path)
