def caesar_decrypt(ciphertext, shift):
    decrypted_message = []
    for char in ciphertext:
        if char.isalpha():
            shift_base = ord('a') if char.islower() else ord('A')
            decrypted_char = chr((ord(char) - shift_base - shift) % 26 + shift_base)
            decrypted_message.append(decrypted_char)
        else:
            decrypted_message.append(char)
    return ''.join(decrypted_message)

ciphertext = "Zsmxsm sc sx Zyvilsec Zvkjk."

for shift in range(1, 26):
    possible_message = caesar_decrypt(ciphertext, shift)
    print(f"Shift {shift}: {possible_message}")
