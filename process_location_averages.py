import pandas as pd


def process_location_averages(input_file):
    # Load the property dataset
    df = pd.read_csv(input_file)

    # Group by Location and keep coordinates (Same Location has the same Long/Lat)
    # Then aggregate importatn columns
    result = (
        df.groupby(["Location", "Latitude", "Longitude"])
        .agg(
            Avg_Rent_per_sqft=("Rent_per_sqft", "mean"),
            Properties_Count=("Rent_per_sqft", "count"),
        )
        .reset_index()
    )

    result = result.rename(columns={"Rent_per_sqft": "Avg_Rent_per_sqft"})

    return result
