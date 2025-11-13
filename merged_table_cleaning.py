import pandas as pd
import numpy as np
from datetime import datetime
from typing import Union, Tuple
from pandas import read_csv
import re

data = pd.read_csv("C:/Users/garden/Desktop/univ/3-2/openpj/Data/merged.csv")

onehot_columns = ['Progress', 'Priority', 'Race', 'Sex'] # Define categorical columns for one-hot encoding
for col in onehot_columns: # Convert to categorical dtype
    data[col] = data[col].astype('category')

def height_to_inches(h):
    if pd.isna(h):
        return 0 
    if not isinstance(h, str):
        return 0  
    
    # Example: "5 ft. 3 in."
    match = re.match(r'(\d+)\s*ft\.\s*(\d+)\s*in\.', h)
    if match:
        feet = int(match.group(1))
        inches = int(match.group(2))
        return feet * 12 + inches

    return 0

# Convert Height to inches
data['Height_in_inches'] = data['Height'].apply(height_to_inches)


# One-hot encoding for categorical variables
data = pd.get_dummies(data, columns=onehot_columns, drop_first=True)


data[['Call_Code', 'Call_Desc']] = data['Call_Type'].str.split(' - ', n=1, expand=True)
data.drop(columns=['Call_Type'], inplace=True)

print(data.head())

# save cleaned data as a new CSV file
data.to_csv("C:/Users/garden/Desktop/univ/3-2/openpj/Data/merged_table_cleaned.csv", index=False)


# pr practice