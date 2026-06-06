'''
Main application file for the Budget Tracker.
'''
import tkinter as tk
from tkinter import messagebox
import pandas as pd
class Expense:
    '''
    Class to represent an expense entry.
    '''
    def __init__(self, description, amount):
        self.description = description
        self.amount = amount
class Savings:
    '''
    Class to represent a savings entry.
    '''
    def __init__(self, description, amount):
        self.description = description
        self.amount = amount
class BudgetTrackerApp:
    '''
    Main class to initialize and run the budget tracker application.
    '''
    def __init__(self, root):
        self.root = root
        self.root.title("Budget Tracker")
        self.expenses = []
        self.savings = []
        self.create_widgets()
    def create_widgets(self):
        '''
        Create and place GUI components.
        '''
        # Configure grid to handle resizing
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(5, weight=1)
        # Labels for Expenses
        tk.Label(self.root, text="Expense Description").grid(row=0, column=0, sticky='ew')
        tk.Label(self.root, text="Expense Amount").grid(row=0, column=1, sticky='ew')
        # Entry fields for Expenses
        self.expense_desc_entry = tk.Entry(self.root)
        self.expense_desc_entry.grid(row=1, column=0, sticky='ew')
        self.expense_amount_entry = tk.Entry(self.root)
        self.expense_amount_entry.grid(row=1, column=1, sticky='ew')
        # Labels for Savings
        tk.Label(self.root, text="Savings Description").grid(row=2, column=0, sticky='ew')
        tk.Label(self.root, text="Savings Amount").grid(row=2, column=1, sticky='ew')
        # Entry fields for Savings
        self.savings_desc_entry = tk.Entry(self.root)
        self.savings_desc_entry.grid(row=3, column=0, sticky='ew')
        self.savings_amount_entry = tk.Entry(self.root)
        self.savings_amount_entry.grid(row=3, column=1, sticky='ew')
        # Buttons
        tk.Button(self.root, text="Add Expense", command=self.add_expense).grid(row=4, column=0, sticky='ew')
        tk.Button(self.root, text="Add Savings", command=self.add_savings).grid(row=4, column=1, sticky='ew')
        tk.Button(self.root, text="Export to Excel", command=self.export_to_excel).grid(row=6, column=0, columnspan=2, sticky='ew')
        # Summary
        self.summary_label = tk.Label(self.root, text="Summary: Expenses = $0, Savings = $0")
        self.summary_label.grid(row=5, column=0, columnspan=2, sticky='ew')
    def add_expense(self):
        '''
        Add an expense to the list.
        '''
        description = self.expense_desc_entry.get()
        try:
            amount = float(self.expense_amount_entry.get())
            self.expenses.append(Expense(description, amount))
            self.update_summary()
        except ValueError:
            messagebox.showerror("Invalid input", "Please enter a valid amount.")
    def add_savings(self):
        '''
        Add savings to the list.
        '''
        description = self.savings_desc_entry.get()
        try:
            amount = float(self.savings_amount_entry.get())
            self.savings.append(Savings(description, amount))
            self.update_summary()
        except ValueError:
            messagebox.showerror("Invalid input", "Please enter a valid amount.")
    def update_summary(self):
        '''
        Update the summary of expenses and savings.
        '''
        total_expenses = sum(exp.amount for exp in self.expenses)
        total_savings = sum(sav.amount for sav in self.savings)
        self.summary_label.config(text=f"Summary: Expenses = ${total_expenses}, Savings = ${total_savings}")
    def export_to_excel(self):
        '''
        Export expenses and savings data to an Excel file.
        '''
        expenses_data = [{'Description': exp.description, 'Amount': exp.amount} for exp in self.expenses]
        savings_data = [{'Description': sav.description, 'Amount': sav.amount} for sav in self.savings]
        # Create DataFrames
        expenses_df = pd.DataFrame(expenses_data)
        savings_df = pd.DataFrame(savings_data)
        # Write to Excel
        with pd.ExcelWriter('budget_tracker.xlsx') as writer:
            expenses_df.to_excel(writer, sheet_name='Expenses', index=False)
            savings_df.to_excel(writer, sheet_name='Savings', index=False)
        messagebox.showinfo("Export Successful", "Data exported to budget_tracker.xlsx")
def main():
    '''
    Function to start the application.
    '''
    root = tk.Tk()
    app = BudgetTrackerApp(root)
    root.mainloop()
if __name__ == "__main__":
    main()