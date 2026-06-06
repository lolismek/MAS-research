import pandas as pd

# Load the spreadsheet
xls_file_path = 'extracted_files/food_duplicates.xls'
df = pd.read_excel(xls_file_path, header=None)  # No headers

# Unpivot the dataframe to count occurrences of each food item
food_items = df.stack().value_counts()

# Find the unique food item
unique_food_item = food_items[food_items == 1].index[0]

print(f"The food item that appears uniquely in the spreadsheet is: '{unique_food_item}'")
