import pandas as pd

# Load the Excel file
file_path = '7bd855d8-463d-4ed5-93ca-5fe35145f733.xlsx'
data = pd.read_excel(file_path)

# Specify the food item columns
food_columns = ['Burgers', 'Hot Dogs', 'Salads', 'Fries', 'Ice Cream']

# Calculate the total sales from food items
total_food_sales = data[food_columns].sum().sum()

# Print the total sales rounded to two decimal places
print(f"Total food sales: ${total_food_sales:.2f}")
