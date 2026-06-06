# Budget Tracker User Manual

Welcome to the Budget Tracker application! This software is designed to help you monitor your expenses and savings efficiently. Below, you will find a comprehensive guide on how to install, set up, and use the Budget Tracker.

## Quick Install

To get started with the Budget Tracker, you need to install the necessary environment dependencies. Follow the steps below:

1. **Install Python**: Ensure you have Python installed on your system. You can download it from [python.org](https://www.python.org/downloads/).

2. **Install pip**: Make sure pip, the Python package manager, is installed. It usually comes with Python, but you can install it separately if needed.

3. **Install Dependencies**: Open your terminal or command prompt and navigate to the directory where the `requirements.txt` file is located. Run the following command to install the required packages:

   ```bash
   pip install -r requirements.txt
   ```

   This will install the `pandas` library, which is necessary for exporting data to Excel.

## Main Functions of the Software

The Budget Tracker application provides the following main functions:

- **Add Expenses**: Record your expenses by entering a description and the amount spent.
- **Add Savings**: Record your savings by entering a description and the amount saved.
- **Summary**: View a summary of your total expenses and savings.
- **Export to Excel**: Export your expenses and savings data to an Excel file for further analysis or record-keeping.

## How to Use the Budget Tracker

1. **Launch the Application**: Run the `main.py` file to start the Budget Tracker application. You can do this by navigating to the directory containing `main.py` and executing the following command:

   ```bash
   python main.py
   ```

2. **Add an Expense**:
   - Enter a description for the expense in the "Expense Description" field.
   - Enter the amount spent in the "Expense Amount" field.
   - Click the "Add Expense" button to record the expense.

3. **Add Savings**:
   - Enter a description for the savings in the "Savings Description" field.
   - Enter the amount saved in the "Savings Amount" field.
   - Click the "Add Savings" button to record the savings.

4. **View Summary**: The application will automatically update and display a summary of your total expenses and savings at the bottom of the window.

5. **Export Data to Excel**:
   - Click the "Export to Excel" button to save your expenses and savings data to an Excel file named `budget_tracker.xlsx`.
   - The file will contain two sheets: one for expenses and one for savings.

## Additional Information

- **Error Handling**: If you enter an invalid amount (non-numeric), the application will display an error message prompting you to enter a valid amount.
- **Data Persistence**: Please note that the data is not saved between sessions. Make sure to export your data to Excel if you wish to keep a record.

We hope you find the Budget Tracker useful in managing your finances. If you have any questions or need further assistance, please feel free to reach out to our support team.

Happy budgeting!