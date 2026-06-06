'''
This is the main file for the Fibonacci number generator application.
It sets up the GUI and handles user interactions.
'''
import tkinter as tk
from tkinter import messagebox
def fibonacci_sequence(n):
    '''
    Generates Fibonacci numbers up to a given number n.
    Parameters:
    n (int): The upper limit for Fibonacci numbers.
    Returns:
    list: A list of Fibonacci numbers up to n.
    '''
    fib_sequence = []
    a, b = 0, 1
    while a <= n:
        fib_sequence.append(a)
        a, b = b, a + b
    return fib_sequence
class FibonacciApp:
    '''
    The main application class for the Fibonacci number generator.
    '''
    def __init__(self, root):
        '''
        Initializes the main window and sets up the GUI components.
        Parameters:
        root (Tk): The root window of the application.
        '''
        self.root = root
        self.root.title("Fibonacci Number Generator")
        self.label = tk.Label(root, text="Enter a number:")
        self.label.pack(pady=10)
        self.entry = tk.Entry(root)
        self.entry.pack(pady=5)
        self.generate_button = tk.Button(root, text="Generate", command=self.generate_fibonacci)
        self.generate_button.pack(pady=10)
        self.result_label = tk.Label(root, text="")
        self.result_label.pack(pady=10)
    def generate_fibonacci(self):
        '''
        Generates Fibonacci numbers up to the given number and displays them in the GUI.
        '''
        try:
            n = int(self.entry.get())
            if n < 0:
                raise ValueError("Number must be non-negative.")
            fib_numbers = fibonacci_sequence(n)
            self.result_label.config(text="Fibonacci numbers: " + ", ".join(map(str, fib_numbers)))
        except ValueError as e:
            messagebox.showerror("Invalid input", str(e))
if __name__ == "__main__":
    root = tk.Tk()
    app = FibonacciApp(root)
    root.mainloop()