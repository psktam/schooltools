from xml.etree import ElementTree

import numpy as np
import plotly.graph_objects as go


def load_districts(filepath: str):
    tree = ElementTree.parse(filepath).getroot()
    namespace = tree.tag.split("}")[0][1:]

    districts = {}

    for placemark in tree.findall(f".//{{{namespace}}}Placemark"):
        district = placemark.find(f"./{{{namespace}}}name").text
        district = int(district.split()[1])
        coords_text = placemark.find(
            f".//{{{namespace}}}MultiGeometry").find(
                f".//{{{namespace}}}coordinates").text

        coords = np.array(
            [[float(cc) for cc in c.split(",")]
             for c in coords_text.split()
        ])

        districts[district] = coords

    return districts


def plot_district(fig, coordinates):
    return fig.add_trace(
        go.Scattermap(
            fill="toself",
            lon=coordinates[:, 0],
            lat=coordinates[:, 1],
            marker={"size": 0}
        )
    )
