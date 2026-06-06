# Sales data for Wharvton and Algrimand
wharvton_sales = [1983, 2008, 2014, 2015, 2017, 2018]
algrimand_sales = [1958, 1971, 1982, 1989, 1998, 2009]

# Calculate total sales for each city
total_wharvton_sales = sum(wharvton_sales)
total_algrimand_sales = sum(algrimand_sales)

# Output the results
print("Total sales for Wharvton:", total_wharvton_sales)
print("Total sales for Algrimand:", total_algrimand_sales)

# Determine which city had the greater total sales
if total_wharvton_sales > total_algrimand_sales:
    print("Wharvton had greater total sales.")
elif total_wharvton_sales < total_algrimand_sales:
    print("Algrimand had greater total sales.")
else:
    print("Both cities had equal total sales.")
