'''
Utility functions for the Palindrome Detector application.
'''
def is_palindrome(word):
    '''
    Check if a given word is a palindrome.
    :param word: The word to check.
    :return: True if the word is a palindrome, False otherwise.
    '''
    word = word.lower()
    return word == word[::-1]