from numbers import Real
import time

import numpy as np
import pandas as pd
import streamlit as st
from geopy.geocoders import GoogleV3
import plotly.graph_objects as go
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
        locate_start = time.time()
        try:
            location = get_locator(api_key).geocode(address_string)
        except Exception as err:
            print(f"Failed to geocode {address_string} with error {err}")
            uncoded[key] = address_string
            continue

        if location is None:
            uncoded[key] = address_string
            continue

        coded[key] = location
        locate_dur = time.time() - locate_start
        time.sleep(max(0.0, locate_dur - rate_limit))

    return coded, uncoded


def generate_district_maps(
    idx_to_locations,
    idx_to_addresses,
    idx_to_districts,
    district_polygons
):
    """
    Return list(s) of house district maps showing where members
    live in those districts.
    """
    districts_to_idxs = {}
    for idx, district in idx_to_districts.items():
        districts_to_idxs.setdefault(district, set()).add(idx)

    fig = go.Figure(layout={"height": 1000})
    scatter_xs = []
    scatter_ys = []
    scatter_text = []
    lower_left = np.array([np.inf] * 2)
    upper_right = np.array([-np.inf] * 2)

    for district in sorted(districts_to_idxs.keys()):
        polygon: Polygon = district_polygons[district]
        poly_points = np.array(polygon.exterior.coords)
        fig.add_trace(go.Scattermap(
            name=f"HD {district}",
            fill="toself",
            lon=poly_points[:, 0],
            lat=poly_points[:, 1],
            marker={"size": 0}
        ))

        for idx in districts_to_idxs[district]:
            location = idx_to_locations[idx]
            scatter_xs.append(location.longitude)
            scatter_ys.append(location.latitude)
            scatter_text.append(idx_to_addresses[idx])

        lower_left = np.min(np.r_[poly_points, lower_left[None, :]], axis=0)
        upper_right = np.max(np.r_[poly_points, upper_right[None, :]], axis=0)

    fig.add_trace(go.Scattermap(
        name="member addresses",
        lon=scatter_xs,
        lat=scatter_ys,
        text=scatter_text,
        mode='markers',
        marker_color='red'
    ))
    center = 0.5 * (lower_left + upper_right)

    fig.update_layout(map={
        "center": {"lon": center[0], "lat": center[1]},
        "zoom": 10
    })
    return fig


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
    api_key = address_form.text_input("provide the API key")
    address_form.form_submit_button("search")

    if api_key == "":
        st.write("## You need to provide an API key to use this tool."
                 " Please fill in the field in the form above")
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
                raw_val = int(raw_val)

            address_string += " " + str(raw_val)

        addresses[idx] = address_string.strip()

    locations, uncoded = geocode_addresses(api_key, addresses, 2.0)

    if len(uncoded) > 0:
        st.write("# Fix addresses")
        st.write(
            "We were unable to locate some addresses. Use the form below to correct "
            "them and try searching again."
        )
        fixing_form = st.form("fixes")
        fixed_strings = {}
        spacing = [0.1, 0.45, 0.45]
        header0, header1, header2 = fixing_form.columns(spacing)
        header0.write("**include**")
        header1.write("**address string**")
        header2.write("**additional information**")
        for key, wrong_string in uncoded.items():
            row0, row1, row2 = fixing_form.columns(spacing)
            rest_of_row = {col: members_df.loc[key][col] for col in members_df.columns if col not in address_cols}
            include = row0.checkbox("", True, key=f"include-{key}")
            if include:
                fixed_strings[key] = row1.text_input("fix", value=wrong_string, key=str(key))
            row2.write(rest_of_row)

        fixes_submitted = fixing_form.form_submit_button("fix addresses")
        if fixes_submitted:
            st.session_state["fixes_submitted"] = True

        new_locations, still_uncoded = geocode_addresses(api_key, fixed_strings, 1.0)
        addresses.update(fixed_strings)

        locations.update(new_locations)

        if len(still_uncoded) > 0 and st.session_state.get("fixes_submitted", False):
            st.write(
                "Still have some non-working addresses. You can "
                "try re-editing them in the form above."
            )
            for addr_string in still_uncoded.values():
                st.markdown(f"- {addr_string}")

    districts_col = {}
    for key, location in locations.items():
        coord = Point(location.longitude, location.latitude)
        for district, district_shape in districts.items():
            if district_shape.contains(coord):
                districts_col[key] = district
                break

    st.write("# Export District Data")
    fig = generate_district_maps(
        locations,
        addresses,
        districts_col,
        districts
    )

    st.write(f"Member Distribution")
    st.plotly_chart(fig, use_container_width=True)

    output_form = st.form("output")
    district_colname = output_form.text_input("name of district column", value="house_district")
    output_form.form_submit_button("set")

    members_df[district_colname] = districts_col
    output_data = members_df.to_csv().encode("utf-8")
    st.download_button(label="download", data=output_data, file_name="data_with_districts.csv", mime="text/csv")


if __name__ == "__main__":
    main()
