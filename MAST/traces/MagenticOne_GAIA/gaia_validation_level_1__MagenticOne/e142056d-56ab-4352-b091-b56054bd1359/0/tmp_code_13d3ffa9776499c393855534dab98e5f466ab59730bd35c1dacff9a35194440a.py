def calculate_distributions_and_min_winnings():
    total_coins = 30
    min_winnings = float('inf')  # Start with infinity to find the minimum

    # Iterate over all possible combinations of coins in the boxes
    for x in range(2, total_coins - 1):  # x should be at least 2
        for y in range(total_coins - x):  # y should be non-negative
            z = total_coins - x - y  # The third box

            if z < 0:
                continue

            # Ensure one box has 6 more coins than another
            if (abs(x - y) == 6 or abs(y - z) == 6 or abs(z - x) == 6):
                # Determine the optimal strategy for Bob
                guesses = sorted([x, y, z])  # Sorted guesses will maximize winnings
                max_winning_strategy = sum(sorted(guesses)[:2])  # Take the two smallest guesses
                min_winnings = min(min_winnings, max_winning_strategy)

    # Calculate the minimum money Bob can guarantee
    guaranteed_min_money = min_winnings * 1000
    return guaranteed_min_money  # Return in dollars

# Calculate and print the result
result = calculate_distributions_and_min_winnings()
print(f"The minimum amount of money Bob can guarantee to win is: ${result}")
