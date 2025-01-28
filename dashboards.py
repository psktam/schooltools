import openpyxl as op
import pandas as pd
import plotly.express as px
import streamlit as st

import parsers


@st.cache_resource
def _goodnesses() -> dict:
    return {}


def main():
    st.set_page_config(layout="wide")
    st.title("Donors Quick Assessments")
    donor_file = st.file_uploader("Upload Donor CSV")
    if donor_file is None:
        return

    wb = op.open(donor_file)
    sheets = list(wb.sheetnames)
    wb.close()

    dfs = {
        parsers.extract_rep(sheet).lower(): pd.read_excel(donor_file, sheet)
        for sheet in sheets
    }

    raw_donor_counts = parsers.list_all_donors(dfs)
    raw_donor_strings = set(raw_donor_counts)
    additional_blacklist = st.multiselect("Blacklist any strings", raw_donor_strings)

    donor_strings = [
        string for string in raw_donor_strings
        if string not in additional_blacklist
    ]

    distance_matrix = parsers.calculate_dist_matrix(donor_strings)

    cluster_dist = st.number_input(
        "Clustering threshold for strings (higher values means more dissimilar strings)"
        " will get mapped to the same donor",
        4
    )
    donor_map = parsers.collapse_donor_list(donor_strings, distance_matrix, cluster_dist)

    # Sort the table such that the donors that had the most strings matched to them appear
    # at the top.
    reversed_donor_map = parsers.reverse_donor_map(donor_map)
    donor_counts = {}
    for donor, strings in reversed_donor_map.items():
        donor_counts[donor] = sum([raw_donor_counts[string] for string in strings])
    # These list comprehensions are abominable
    sort_order = [
        tup[0] for tup in sorted(enumerate(reversed_donor_map.items()), key=lambda e: -len(e[1][1]))
    ]
    reversed_df = pd.DataFrame({
        "donor": [list(reversed_donor_map.keys())[i] for i in sort_order],
        "strings": [", ".join(sorted(v)) for v in [list(reversed_donor_map.values())[i] for i in sort_order]]
    })

    expander0 = st.expander("strings -> donor mapping")
    expander0.table(reversed_df)

    certainties = {}

    rep = parsers.extract_rep(st.selectbox("select a representative to view", sheets)).lower()
    donors_for_rep = sorted(parsers.list_donors(dfs[rep], parsers.DEFAULT_DONOR_BLACKLIST | set(additional_blacklist)))
    weighting_form = st.expander("Assign Weights", expanded=True).form("weighting-form")
    weighting_form.write(
        "For each donor, give an assessment from -2 to +2 "
        "as to whether or not they're good on school vouchers. "
        "-2 is really bad, +2 is really good, and 0 is neutral, "
        "as well as a certainty for each assessment.\n\n When "
        "you are done assigning weights, make sure to click the "
        "'assign weights' button at the bottom of this section."
    )
    for raw_donor in donors_for_rep:
        donor = donor_map[raw_donor]
        c0, c1, c2 = weighting_form.columns(3)
        c0.markdown(donor)
        print(f"Setting {donor} to {_goodnesses().get(donor, 0)}")
        _goodnesses()[donor] = c1.number_input(
            "goodness", min_value=-2, max_value=2, value=_goodnesses().get(donor, 0), key=f"{donor}-goodness"
        )
        certainties[donor] = c2.selectbox(
            "certainty", ["unsure", "sure", "very sure"], key=f"{donor}-certainty"
        )
    btn = weighting_form.form_submit_button("assign weights")

    # At this points, donors are assigned weights. It's time to calculate influence for
    # each representative, based on donations.
    contributions_df = parsers.clean_contribution_data(
        rep,
        dfs[rep],
        donor_map,
        _goodnesses()
    )

    plotting_df = contributions_df.copy()
    plotting_df["goodness"] = plotting_df["goodness"].apply(str)
    fig = px.bar(
        plotting_df,
        y="candidate", x="amount",
        color="goodness", hover_data="donor",
        orientation='h',
        # IBM colorblind-safe palette
        color_discrete_map={
            "-2": "#dc267f",
            "-1": "#fe6100",
            "0": "#ffb000",
            "1": "#785ef0",
            "2": "#648fff"
        }

    )
    st.plotly_chart(fig)

if __name__ == "__main__":
    main()
