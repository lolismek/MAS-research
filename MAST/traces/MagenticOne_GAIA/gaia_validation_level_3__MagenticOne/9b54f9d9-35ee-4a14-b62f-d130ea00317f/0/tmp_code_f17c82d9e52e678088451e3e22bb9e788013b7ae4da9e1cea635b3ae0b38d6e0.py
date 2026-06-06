import pandas as pd

# Load the spreadsheet
xls_file_path = 'extracted_files/food_duplicates.xls'
xls = pd.ExcelFile(xls_file_path)

# Assume sheet1 contains the relevant data; modify as necessary if different
sheet_name = xls.sheet_names[0]
df = pd.read_excel(xls_file_path, sheet_name=sheet_name)

# Assuming there's a column named 'FoodItem', modify if the name is different
food_column_name = 'FoodItem'  # Placeholder name, adjust if necessary
# If unsure about the columns, uncomment the following line to check column names
# print(df.columns)

# Get the count of each food item
food_counts = df[food_column_name].value_counts()

# Determine the food item that appears only once
unique_food_item = food_counts[food_counts == 1].index[0]

print(f"The food item that appears uniquely in the spreadsheet is: '{unique_food_item}'")
