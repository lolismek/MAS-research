import pandas as pd

# Prepare and load the data
data = {
    "Name": [
        "Hollie Wallace", "Nabil Bates", "Abi Haines", "Tyrone Miller", "Laurence Vale",
        "Jerry Randolph", "Rehan O'Gallagher", "Rahim Cummings", "Dominik Rollins", "Safwan Sanders",
        "Davina Mckay", "Harris Bright", "Tiana Rubio", "Judith Gordon", "Annabelle Cortez",
        "Fleur Woodard", "Helena Lloyd", "Amelia Molina", "Kaylee Hebert", "Chester Gilmore",
        "Kara Mcmahon", "Karen Singleton", "Cecily Jackson", "Lucille Blevins", "Alannah Clark",
        "Daniel Rangel", "Tim Harmon", "Tariq Nixon", "Carmen Jennings", "Natasha Johnson",
        "Maxwell Patrick", "Isha Middleton", "Amir Fadel", "Anthony Waters", "Darren Trujillo",
        "Poppie Gibbs", "Kelly Bentley", "Louis Welch", "Caiden Ross", "Eliot Farrell",
        "Lillie Mcknight", "Subhan Hahn", "Erika Oconnor", "Meghan Buckley", "Crystal Hansen",
        "Kiera Moore", "Marco Vance", "Polly Fowler"
    ],
    "Degree Level": [
        "Master", "Ph. D.", "Master", "Bachelor", "Master",
        "Master", "Bachelor", "Bachelor", "Bachelor", "Bachelor",
        "Ph. D.", "Bachelor", "Ph. D.", "Ph. D.", "Master",
        "Bachelor", "Master", "Ph. D.", "Associate", "Master",
        "Ph. D.", "Bachelor", "Master", "Master", "Master",
        "Master", "Ph. D.", "Associate", "Associate", "Master",
        "Master", "Master", "Ph. D.", "Associate", "Master",
        "Bachelor", "Master", "Ph. D.", "Ph. D.", "Master",
        "Ph. D.", "Master", "Bachelor", "Master", "Master",
        "Ph. D.", "Ph. D.", "Master"
    ],
    "Experience (Years)": [
        2, 4, 3, 3, 5,
        6, 2, 2, 4, 4,
        1, 5, 5, 2, 1,
        3, 10, 3, 3, 3,
        4, 3, 2, 1, 3,
        3, 4, 8, 2, 5,
        4, 5, 5, 5, 7,
        4, 4, 4, 1, 4,
        4, 2, 1, 2, 3,
        5, 2, 9
    ],
    "Publications": [
        4, 1, 4, 4, 5,
        5, 5, 2, 6, 6,
        5, 5, 5, 5, 1,
        5, 4, 3, 5, 5,
        4, 6, 5, 3, 3,
        6, 3, 2, 2, 2,
        1, 5, 4, 5, 3,
        1, 3, 5, 6, 2,
        6, 4, 4, 6, 6,
        4, 3, 5
    ],
    "Lab Trained (Y/N)": [
        "Y", "Y", "Y", "Y", "N",
        "Y", "Y", "N", "Y", "Y",
        "Y", "Y", "N", "Y", "Y",
        "N", "Y", "Y", "Y", "N",
        "Y", "Y", "Y", "Y", "Y",
        "Y", "Y", "Y", "Y", "Y",
        "Y", "Y", "Y", "Y", "Y",
        "Y", "Y", "Y", "Y", "Y",
        "Y", "Y", "N", "Y", "Y",
        "N", "Y", "Y"
    ],
    "Citizen (Y/N)": [
        "N", "Y", "Y", "Y", "Y",
        "Y", "N", "Y", "Y", "Y",
        "Y", "N", "Y", "N", "Y",
        "Y", "Y", "Y", "N", "Y",
        "Y", "N", "Y", "Y", "Y",
        "Y", "N", "Y", "Y", "Y",
        "Y", "Y", "N", "Y", "Y",
        "Y", "Y", "Y", "Y", "Y",
        "Y", "Y", "N", "Y", "Y",
        "Y", "Y", "N"
    ],
    "Programming Lang": [
        "C++", "Fortran", "C#", "Fortran", "Perl",
        "Fortran", "C#", "Fortran", "Java", "C#",
        "C++", "C++", "Fortran", "JavaSFortranript", "C#",
        "C#", "C#", "Fortran", "C#", "Fortran",
        "C#", "C++", "C#", "C#", "Fortran",
        "C#", "C#", "Fortran", "Fortran", "C++",
        "C++", "C#", "Fortran", "Python", "C++",
        "Fortran", "Python", "Haskell", "Fortran", "Java",
        "C++", "C++", "Python", "JavaSFortranript", "JavaSFortranript",
        "Fortran", "C++", "C#"
    ],
    "Second Language": [
        None, "Spanish", "German", None, "Spanish",
        "German", None, "Spanish", "Spanish", "Arabic",
        None, "Spanish", "Arabic", "French", None,
        "Chinese", "Arabic", "Chinese", None, "Spanish",
        "French", "Chinese", None, "Chinese", None,
        "Spanish", None, "German", "Spanish", "Chinese",
        "Spanish", None, "Chinese", "German", None,
        "Chinese", "Chinese", None, "Spanish", "French",
        None, "Spanish", "Spanish", "Japanese", None,
        "French", "German", None
    ]
}

df = pd.DataFrame(data)

def missing_qualifications(row):
    missing = 0
    # Check degree level
    if row["Degree Level"] not in ["Master", "Ph. D."]:
        missing += 1
    # Check experience
    if row["Experience (Years)"] < 3:
        missing += 1
    # Check lab training
    if row["Lab Trained (Y/N)"] == "N":
        missing += 1
    # Check publications
    if row["Publications"] < 3:
        missing += 1
    # Check citizenship
    if row["Citizen (Y/N)"] == "N":
        missing += 1
    # Check programming languages
    if row["Programming Lang"] not in ["C++", "C#", "Fortran"]:
        missing += 1
    # Check second language
    if not row["Second Language"]:
        missing += 1
    return missing

# Add a new column for counting missing qualifications
df["Missing Qualifications"] = df.apply(missing_qualifications, axis=1)

# Filter out applicants missing exactly one qualification
applicants_missing_one = df[df["Missing Qualifications"] == 1]

print("Applicants missing exactly one qualification:")
print(applicants_missing_one[["Name"]])
