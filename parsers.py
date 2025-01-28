from itertools import product

from Levenshtein import distance as ldist
import numpy as np
import pandas as pd


# Some problematic strings we want to scrub out
DEFAULT_DONOR_BLACKLIST = {e.lower() for e in
    [
        "This can be for donors to the officeholder and their opponents",
        'In general, it seems the bulk of his contributions come from health insurance and pharmaceutical companies. United Health, Elevance, Novartis corporation PAC, CVS.',
        'Special note: '
    ]
}


def list_all_donors(
    sheets_by_rep: dict[str, pd.DataFrame],
    blacklist: set[str] = DEFAULT_DONOR_BLACKLIST
) -> dict[str, int]:
    """
    Find all raw donor strings in the excel file.
    """
    all_donor_counts = {}
    for df in sheets_by_rep.values():
        for donor in list_donors(df, blacklist):
            count = all_donor_counts.setdefault(donor, 0)
            all_donor_counts[donor] = count + 1

    return all_donor_counts


def list_donors(
    df: pd.DataFrame,
    blacklist: set[str]
) -> list[str]:
    donors = []
    for entry in df["NAME"]:
        if isinstance(entry, str) and entry.lower() not in blacklist:
            donors.append(entry.lower().strip())
    return donors


def calculate_dist_matrix(donor_list: list[str]) -> np.ndarray:
    matrix = np.zeros((len(donor_list), len(donor_list)), dtype=int)

    for i, j in product(range(len(donor_list)), range(len(donor_list))):
        if i == j:
            continue

        matrix[i, j] = ldist(donor_list[i], donor_list[j])

    return matrix


def collapse_donor_list(
    donor_list: list[str],
    distance_matrix: np.ndarray,
    cluster_dist: int
) -> dict[str, str]:
    """
    Use some fuzzy logic to merge similar strings.

    Returns a map that links each string to the group
    of words that it's similar to. Two words are
    considered similar if their distances in the
    distance_matrix are equal to or less than the
    provided `cluster_dist`.
    """
    strings_to_donor = {}

    for i, string in enumerate(donor_list):
        similar = [
            donor_list[idx]
            for idx in np.where(distance_matrix[i] <= cluster_dist)[0]
        ]
        donor_id = sorted([string] + similar)[0]

        strings_to_donor.update({donor_string: donor_id for donor_string in [string] + similar})
    return strings_to_donor


def reverse_donor_map(donor_map: dict[str, str]) -> dict[str, set[str]]:
    reversed = {}
    for donor_string, donor in donor_map.items():
        reversed.setdefault(donor, set()).add(donor_string)
    return reversed


def extract_district(name: str) -> str:
    return name.split("(")[1].strip()[:-1]


def extract_rep(name: str) -> str:
    return name.split("(")[0].strip()


def normalize_donee(rep_name: str, raw_donee_string: str) -> str:
    """
    For a given representative, normalize a list of raw
    strings that represent people who were donated to.
    Sometimes people use last names, or the full names when
    entering into the spreadsheet(s).
    """
    raw_donee_string = raw_donee_string.lower().strip()

    # First, check if this name is our representative.
    # If so, insert the representative's name.
    if len(rep_name.split()) == 1:
        # Rep name is just a single word.
        if rep_name in raw_donee_string.split():
            return rep_name
        else:
            return raw_donee_string

    # We have the full representative's name. Now
    # check if this donee is a single word.
    elif len(raw_donee_string.split()) == 1:
        if raw_donee_string in rep_name.split():
            return rep_name
        else:
            return raw_donee_string

    # In this case, we have the full representative's
    # name, and the donor is multiple words
    return raw_donee_string


def clean_contribution_data(
    rep: str,
    df: pd.DataFrame,
    strings_to_donor: dict[str, str],
    goodnesses: dict[str, int]
):
    cleaned_rows = []
    for _, row in df.iterrows():
        raw_name = row["NAME"]
        if not isinstance(raw_name, str):
            continue
        raw_name = raw_name.lower().strip()
        if raw_name not in strings_to_donor:
            continue

        donor = strings_to_donor[raw_name]

        raw_donee = row["DONATED TO"]
        if not isinstance(raw_donee, str):
            continue

        donee = normalize_donee(rep, raw_donee)
        try:
            amount = normalize_donation_amt(row["DONATION AMOUNT"])
        except ValueError:
            continue
        goodness = goodnesses[donor]

        cleaned_rows.append({
            "donor": donor,
            "candidate": donee,
            "amount": amount,
            "goodness": goodness
        })
    return pd.DataFrame(cleaned_rows).sort_values(by=["goodness", "amount"])


def normalize_donation_amt(donation_amount) -> float:
    if isinstance(donation_amount, str):
        donation_amount = donation_amount.replace("$", "").replace(",", "").strip()
        return float(donation_amount)
    return float(donation_amount)
