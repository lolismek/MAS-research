# Variables
initial_honey_weight = 5.355  # kg
mayonnaise_weight = 3.4446  # kg
weight_per_cup_honey = 0.3347  # kg

# Calculate cups to remove
cups_to_remove = 0
current_honey_weight = initial_honey_weight

while current_honey_weight > mayonnaise_weight:
    current_honey_weight -= weight_per_cup_honey
    cups_to_remove += 1

# Print the result
print(cups_to_remove)
