from numbers import Real
import time

import numpy as np
import pandas as pd
import streamlit as st
from geopy.geocoders import GoogleV3
from shapely.geometry import Point
from shapely.geometry.polygon import Polygon

from src import mapper


@st.cache_resource
def get_locator(api_key: str):
    return GoogleV3(api_key=api_key)


@st.cache_data
def geocode_addresses(api_key, address_dict, rate_limit):
    uncoded = {}
    coded = {}
    for key, address_string in address_dict.items():
        print(f"Geocoding {address_string}")
        locate_start = time.time()
        try:
            location = get_locator(api_key).geocode(address_string)
        except Exception as err:
            print(f"    Failed with {err}")
            uncoded[key] = address_string
            continue

        if location is None:
            uncoded[key] = address_string
            continue

        print("    Got a hit!")
        coded[key] = location
        locate_dur = time.time() - locate_start
        time.sleep(max(0.0, locate_dur - rate_limit))

    return coded, uncoded


def main():
    st.title("Find Members in Districts")
    districts = {
        key: Polygon(shape[:, :2])
        for key, shape in mapper.load_districts("data/PlanH2316.kml").items()
    }
    member_list = st.file_uploader("Upload spreadsheet of member data")
    if member_list is None:
        return

    filetype = member_list.name.split(".")[-1].lower()
    if filetype == "csv":
        members_df = pd.read_csv(member_list)
    else:
        raise ValueError(
            f"Unrecognized filetype: {filetype}. "
            "This application works best with CSVs"
        )

    address_form = st.form("addresses")
    address_cols = address_form.multiselect(
        "Select the column(s) that define the address, in the order "
        "they should appear in the address",
        options=members_df.columns
    )
    num_addresses = address_form.number_input("limit search to this many addresses", 10)
    api_key = st.text_input("provide the API key")
    submitted = address_form.form_submit_button("search")

    if not submitted:
        return

    addresses = {}

    for idxidx, (idx, row) in enumerate(members_df.iterrows()):
        if idxidx >= num_addresses:
            break
        # Build the address string
        address_string = ""
        for col in address_cols:
            raw_val = row[col]
            if raw_val is None or (isinstance(raw_val, (np.number, Real)) and np.isnan(raw_val)):
                continue
            elif isinstance(raw_val, (np.number, Real)):
                print("Cast to integer")
                raw_val = int(raw_val)

            address_string += " " + str(raw_val)

        addresses[idx] = address_string.strip()

    locations, uncoded = geocode_addresses(api_key, addresses, 2.0)

    if len(uncoded) > 0:
        fixing_form = st.form("fixes")
        fixed_strings = {}
        for key, wrong_string in uncoded.items():
            fixed_strings[key] = fixing_form.text_input("fix", value=wrong_string, key=str(key))

        fix_submitted = fixing_form.form_submit_button("fix addresses")

        if fix_submitted:
            new_locations, still_uncoded = geocode_addresses(api_key, fixed_strings, 1.0)
        else:
            return

        locations.update(new_locations)

        if len(still_uncoded) > 0:
            st.write("Still have some non-working addresses")
            for addr_string in still_uncoded.keys():
                st.markdown(f"- {addr_string}")

    districts_col = {}
    for key, location in locations.items():
        coord = Point(location.longitude, location.latitude)
        for district, district_shape in districts.items():
            if district_shape.contains(coord):
                districts_col[key] = district
                break

    output_form = st.form("output")
    district_colname = output_form.text_input("name of district column", value="house_district")
    output_form.form_submit_button("set")

    members_df[district_colname] = districts_col
    output_data = members_df.to_csv().encode("utf-8")
    st.download_button(label="download", data=output_data, file_name="data_with_districts.csv", mime="text/csv")


if __name__ == "__main__":
    main()
