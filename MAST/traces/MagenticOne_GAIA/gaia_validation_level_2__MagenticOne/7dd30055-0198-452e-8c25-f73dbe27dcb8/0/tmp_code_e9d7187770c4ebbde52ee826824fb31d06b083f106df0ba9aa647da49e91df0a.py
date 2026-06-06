from Bio import PDB
import math

# Parse the PDB file
file_path = '7dd30055-0198-452e-8c25-f73dbe27dcb8.pdb'
parser = PDB.PDBParser(QUIET=True)
structure = parser.get_structure('5wb7', file_path)

# Function to calculate the Euclidean distance between two coordinates
def calculate_distance(coord1, coord2):
    return math.sqrt((coord1[0] - coord2[0]) ** 2 + 
                     (coord1[1] - coord2[1]) ** 2 + 
                     (coord1[2] - coord2[2]) ** 2)

# Extract the first and second atom coordinates
first_atom = None
second_atom = None

for model in structure:
    for chain in model:
        for residue in chain:
            for atom in residue:
                if first_atom is None:
                    first_atom = atom
                elif second_atom is None:
                    second_atom = atom
                    break # Exit after finding the second atom
            if second_atom:
                break
        if second_atom:
            break
    if second_atom:
        break

if first_atom and second_atom:
    coord1 = first_atom.coord
    coord2 = second_atom.coord
    distance = calculate_distance(coord1, coord2)
    distance_rounded = round(distance, 5) * 10000 # Convert to picometers and round
    print(f"The distance between the first and second atoms is approximately {distance_rounded} pm.")
else:
    print("Failed to find two atoms in the PDB file.")
