'''
Main application file for the Palindrome Detector with GUI using tkinter.
'''
import tkinter as tk
from tkinter import filedialog, messagebox
from utils import is_palindrome
class PalindromeApp:
    def __init__(self, master):
        self.master = master
        master.title("Palindrome Detector")
        self.label = tk.Label(master, text="Select a text file to detect palindromes:")
        self.label.pack()
        self.load_button = tk.Button(master, text="Load File", command=self.load_file)
        self.load_button.pack()
        self.result_text = tk.Text(master, height=15, width=50)
        self.result_text.pack()
    def load_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if file_path:
            with open(file_path, 'r') as file:
                text = file.read()
                palindromes = self.detect_palindromes(text)
                self.display_results(palindromes)
    def detect_palindromes(self, text):
        words = text.split()
        palindromes = [word for word in words if is_palindrome(word)]
        return palindromes
    def display_results(self, palindromes):
        self.result_text.delete(1.0, tk.END)
        if palindromes:
            self.result_text.insert(tk.END, "Palindromes found:\n")
            for palindrome in palindromes:
                self.result_text.insert(tk.END, f"{palindrome}\n")
        else:
            self.result_text.insert(tk.END, "No palindromes found.")
if __name__ == "__main__":
    root = tk.Tk()
    app = PalindromeApp(root)
    root.mainloop()