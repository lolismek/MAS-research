def calculate_checksum(number, weight, transposed_indices=None):
    if transposed_indices:
        idx1, idx2 = transposed_indices
        number[idx1], number[idx2] = number[idx2], number[idx1]

    checksum = 0
    for i, num in enumerate(number[:-1]):
        if i % 2 == 0:
            checksum += int(num) * 1
        else:
            checksum += int(num) * weight

    checksum = (10 - (checksum % 10)) % 10
    return checksum == int(number[-1])

def find_valid_weights_and_indices(numbers):
    valid_combinations = []

    for weight in range(2, 10):
        for number in numbers:
            # We ignore dashes and focus only on numbers
            number = number.replace("-", "")
            for index in range(3, len(number) - 2):
                # Check if swapping the current index with the next creates a valid checksum
                if calculate_checksum(list(number), weight, transposed_indices=(index, index + 1)):
                    valid_combinations.append((weight, index))
    
    return valid_combinations

numbers = [
    "978-354181391-9",
    "978-946669746-1",
    "978-398036139-6",
    "978-447656680-4",
    "978-279586664-7",
    "978-595073693-3",
    "978-976647652-6",
    "978-591178125-5",
    "978-728465924-5",
    "978-414825155-9"
]

results = find_valid_weights_and_indices(numbers)
print("Valid (weight, index) pairs:", results)
