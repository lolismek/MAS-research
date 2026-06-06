import pandas as pd

# Load the Excel file
file_path = '/workspace/API_NY.GNS.ICTR.ZS_DS2_en_excel_v2_13395.xls'
data = pd.read_excel(file_path, skiprows=3)

# Filter countries with savings over 35% for all years from 2001 to 2010
filtered_countries = data[
    (data.loc[:, '2001':'2010'] > 35).all(axis=1)
]

# Get the list of country names
country_list = filtered_countries['Country Name'].tolist()
country_list.sort()

# Print the result in alphabetical order
print(', '.join(country_list))
