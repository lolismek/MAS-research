import sympy as sp

# Define the variable and function
x = sp.symbols('x')
f = x**3 + 4*x**2 - 3*x + 8
# Calculate the derivative
derivative_f = sp.diff(f, x)

# Convert the symbolic functions to numerical functions
f_num = sp.lambdify(x, f, 'numpy')
derivative_f_num = sp.lambdify(x, derivative_f, 'numpy')

# Initial values
x_n = -5
n = 0
precision = 4

# Iterate using Newton's Method
while True:
    n += 1
    x_n1 = x_n - f_num(x_n) / derivative_f_num(x_n)
    
    # Check if the result rounds to the same 4 decimal places
    if round(x_n, precision) == round(x_n1, precision):
        break
    x_n = x_n1

# Output the smallest n
print('The smallest n is:', n)
