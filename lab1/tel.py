# data_generator.py

import random

# Initialize the dictionary with the original data
tel = {
    'jack': '4098',
    'sape': '4139'
}

# 1. Determine the number of new entries needed
# Need 1000 - 2 = 998 new entries.
num_new_entries = 1000 - len(tel)

# 2. Generate the new entries and update the dictionary
for i in range(1, num_new_entries + 1):
    # Create a unique key (e.g., 'user_1', 'user_2', ...)
    key = f'user_{i}'

    # Generate a random 9-digit number as a string (100000000 to 999999999)
    value = str(random.randint(100000000, 999999999))

    # Add the new key-value pair to the dictionary
    tel[key] = value

# The dictionary 'tel' now contains 1000 entries.