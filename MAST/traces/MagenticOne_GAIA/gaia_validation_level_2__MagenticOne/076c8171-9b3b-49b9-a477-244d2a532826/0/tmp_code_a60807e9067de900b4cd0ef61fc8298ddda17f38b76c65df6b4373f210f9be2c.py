import pandas as pd

# Data from the spreadsheet
data = {
    "Name": [
        "Rainforest Bistro", "Panorama Outfitters", "Zack's Cameras and Trail Mix",
        "SignPro Custom DeSign", "Serenity Indoor Fountains", "Budapest Comics",
        "Dottie's Lattes", "Gumball Utopia", "Your Uncle's Basement",
        "Carnivore Loan Specialists", "Harry's Steakhouse", "Two Guys Paper Supplies",
        "Dragon Pizza", "Us Three: The U2 Fan Store", "Jimmy's Buffett",
        "Franz Equipment Rentals", "Nigel's Board Games", "Destructor's Den",
        "Hook Me Up", "Slam Dunk", "Ben's Hungarian-Asian Fusion",
        "PleaseBurgers", "Reagan's Vegan", "FreshCart Store-to-Table"
    ],
    "Type": [
        "Restaurant", "Apparel", "Electronics / Food", "Signage", "Decor", "Comics",
        "Restaurant", "Candy", "Sports Collectibles", "Finance", "Restaurant", "Office Supplies",
        "Restaurant", "Music", "Restaurant", "Industrial Supplies", "Board Games", "Baby Supplies",
        "Sporting Goods", "Restaurant", "Restaurant", "Restaurant", "Restaurant", "Restaurant"
    ],
    "Revenue": [
        32771, 23170, 33117, 21246, 25234, 12251, 34427, 13271, 11119,
        31000, 46791, 76201, 10201, 10201, 10027, 20201, 62012, 79915,
        56503, 61239, 68303, 20132, 20201, 83533
    ],
    "Rent": [
        1920, 1788, 1001, 1121, 6359, 2461, 1293, 3420, 8201,
        50312, 1327, 1120, 2000, 1200, 3201, 2201, 2013, 5203,
        1940, 5820, 2011, 1402, 6201, 2751
    ]
}

# Creating a DataFrame
df = pd.DataFrame(data)

# Calculate the revenue-to-rent ratio
df['Revenue_to_Rent_Ratio'] = df['Revenue'] / df['Rent']

# Identify the vendor with the lowest ratio
vendor_with_lowest_ratio = df.loc[df['Revenue_to_Rent_Ratio'].idxmin()]

# Print the vendor's type
vendor_type = vendor_with_lowest_ratio['Type']
print("The vendor with the lowest revenue-to-rent ratio is:", vendor_with_lowest_ratio['Name'])
print("The type for this vendor is:", vendor_type)
