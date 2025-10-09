import pandas as pd
import numpy as np
from datetime import datetime
from typing import Union, Tuple

def get_crime_frequency_from_table(
    table: pd.DataFrame,
    latlon_col: str,
    date_col: str,
    lat: float,
    lon: float,
    r: float,
    start_time: Union[str, datetime],
    end_time: Union[str, datetime],
) -> Tuple[pd.DataFrame, int]:
    """
    Function: gives you frequency of the crime (Jennie)
    Given the center (lat, lon), radius r (int),
    starting time(datetime), end time(datetime)
    → numbers of crime that happened in radius R
    between xxx period of time.
    """
    df = table.copy()

    # convert to datetime & filter invalid rows
    df["_dt"] = pd.to_datetime(df[date_col], errors="coerce", utc=True)
    start = pd.to_datetime(start_time, utc=True)
    end = pd.to_datetime(end_time, utc=True)

    # split lat, lon & filter invalid rows
    latlon_split = df[latlon_col].astype(str).str.split(",", n=1, expand=True)
    df["_lat"] = pd.to_numeric(latlon_split[0], errors="coerce")
    df["_lon"] = pd.to_numeric(latlon_split[1], errors="coerce")
    df = df.dropna(subset=["_lat", "_lon", "_dt"]).copy()

    # Haversine formula to calculate real distance
    R_earth = 6_371_000.0  # meters
    lat1, lon1 = np.radians(lat), np.radians(lon)
    lat2, lon2 = np.radians(df["_lat"].to_numpy()), np.radians(df["_lon"].to_numpy())
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    c = 2 * np.arcsin(np.sqrt(a))
    dist_m = R_earth * c

    # filter by distance and time
    mask = (dist_m <= r) & (df["_dt"].between(start, end))
    filtered = df.loc[mask].copy()

    return filtered, len(filtered)


# EXAMPLE USAGE
if __name__ == "__main__":
    table = pd.read_excel("Dummy Data Cleaned table.xlsx",sheet_name="Dataset")
    print(table.head())


    filtered, count = get_crime_frequency_from_table(
        table=table,
        latlon_col="Lat, Lon",           
        date_col="CreateDatetime",       
        lat=37.8715,                      
        lon=-122.2730,
        r=1000,                         
        start_time="2022-11-15 22:00:00",
        end_time="2022-12-31 00:00:00"
    )


    print(f"Count of Crimes: {count}")
    print(filtered.head())
