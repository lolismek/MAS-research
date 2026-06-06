# Constants
P = 101325000  # Pressure in Pa
M = 0.12091    # Molar mass in kg/mol
R = 63.31      # Gas constant in J/(mol·K)
T = 276        # Temperature in K
Z = 1.1        # Compressibility factor
mass_freon = 0.312  # Mass in kg

# Calculate density
density = (P * M) / (Z * R * T)

# Calculate volume
volume = mass_freon / density

# Output rounded volume
print(round(volume * 1000))  # Convert m³ to mL and round
