#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TC-aware Publish–Subscribe Structural Analysis

Implements:
- LCP-based topic categorization
- Structural metrics (paper-aligned)
- Q1/Q3 relative interpretation
- Rule-based patterns
- OS^P + capped UNI + final Score
"""

import json
import math
import sys
from itertools import combinations
from pathlib import Path

import pandas as pd


# =============================
# CONFIGURATION
# =============================

MIN_LCP_LEN = 3
TAU = 0.30
LAMBDA = 0.30


# =============================
# LCP-BASED TOPIC CATEGORIZATION
# =============================

def longest_common_prefix(str1, str2):
    """Return longest common prefix of two strings."""
    idx = 0
    max_len = min(len(str1), len(str2))
    while idx < max_len and str1[idx] == str2[idx]:
        idx += 1
    return str1[:idx]


def build_topic_categories(topic_names):
    """
    Build topic categories using longest common prefix (LCP).

    Args:
        topic_names (dict): topic_id -> topic_name

    Returns:
        dict: topic_id -> category
    """
    categories = {}

    for tid, name in topic_names.items():
        best_prefix = ""
        for other_id, other_name in topic_names.items():
            if tid == other_id:
                continue
            lcp = longest_common_prefix(name, other_name)
            if len(lcp) >= MIN_LCP_LEN and len(lcp) > len(best_prefix):
                best_prefix = lcp

        categories[tid] = best_prefix if best_prefix else name

    return categories


# =============================
# DATA EXTRACTION
# =============================

def load_dataset(path):
    """Load JSON dataset."""
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def extract_sets(dataset):
    """Extract core sets and relations."""
    apps = {a["id"] for a in dataset.get("applications", [])}
    topics = {t["id"] for t in dataset.get("topics", [])}
    nodes = {n["id"] for n in dataset.get("nodes", [])}
    libs = {l["id"] for l in dataset.get("libraries", [])}

    y_app = {a: set() for a in apps}
    a_app = {a: set() for a in apps}
    y_topic = {t: set() for t in topics}
    a_topic = {t: set() for t in topics}
    s_node = {n: set() for n in nodes}
    l_app = {a: set() for a in apps}
    u_lib = {l: set() for l in libs}

    rel = dataset.get("relationships", {})

    for r in rel.get("publishes_to", []):
        y_app[r["from"]].add(r["to"])
        y_topic[r["to"]].add(r["from"])

    for r in rel.get("subscribes_to", []):
        a_app[r["from"]].add(r["to"])
        a_topic[r["to"]].add(r["from"])

    for r in rel.get("runs_on", []):
        s_node[r["to"]].add(r["from"])

    for r in rel.get("uses", []):
        l_app[r["from"]].add(r["to"])
        u_lib[r["to"]].add(r["from"])

    return apps, topics, nodes, libs, y_app, a_app, y_topic, a_topic, s_node, l_app, u_lib


# =============================
# METRICS
# =============================

def compute_app_metrics(apps, y_app, a_app, y_topic, a_topic, categories):
    rows = []

    for app in sorted(apps):
        reached = set()

        for topic in y_app[app]:
            reached |= a_topic.get(topic, set())

        for topic in a_app[app]:
            reached |= y_topic.get(topic, set())

        reached.discard(app)

        reach = len(reached)
        amp = reach / (len(y_app[app]) + 1)
        ra = (len(y_app[app]) - len(a_app[app])) / (
            len(y_app[app]) + len(a_app[app]) + 1
        )

        contexts = {
            categories[t] for t in (y_app[app] | a_app[app])
        }
        tc = len(contexts)
        le = 0

        rows.append({
            "id": app,
            "R": reach,
            "A": amp,
            "RA": ra,
            "TC": tc,
            "LE": le,
        })

    return pd.DataFrame(rows)


def compute_topic_metrics(topics, y_topic, a_topic, app_node):
    rows = []

    for topic in sorted(topics):
        pubs = y_topic[topic]
        subs = a_topic[topic]

        coverage = len(pubs) + len(subs)
        imbalance = abs(len(pubs) - len(subs)) / (coverage + 1)

        nodes = {app_node[a] for a in pubs | subs if a in app_node}
        ps = len(nodes)

        rows.append({
            "id": topic,
            "C": coverage,
            "I": imbalance,
            "PS": ps,
        })

    return pd.DataFrame(rows)


def compute_node_metrics(nodes, s_node, y_topic, a_topic):
    rows = []

    for node in sorted(nodes):
        apps = list(s_node[node])
        nd = len(apps)

        nid = 0
        for a1, a2 in combinations(apps, 2):
            for topic in y_topic:
                if (
                    (a1 in y_topic[topic] and a2 in a_topic[topic])
                    or (a2 in y_topic[topic] and a1 in a_topic[topic])
                ):
                    nid += 1
                    break

        rows.append({
            "id": node,
            "ND": nd,
            "NID": nid,
        })

    return pd.DataFrame(rows)


# =============================
# RELATIVE INTERPRETATION
# =============================

def apply_relative_flags(df, metrics):
    for metric in metrics:
        q1 = df[metric].quantile(0.25)
        q3 = df[metric].quantile(0.75)
        df[f"{metric}_up"] = df[metric] > q3
        df[f"{metric}_down"] = df[metric] < q1
    return df


# =============================
# PATTERNS
# =============================

def apply_app_patterns(df):
    df["WR"] = df["R_up"] & df["A_up"]
    df["RS"] = df["RA_up"] | df["RA_down"]
    df["CS"] = df["TC_up"]
    df["SD"] = df["LE_up"]
    return df


def apply_topic_patterns(df):
    df["CB"] = df["C_up"] & df["I_down"]
    df["DC"] = df["I_up"]
    return df


def apply_node_patterns(df):
    df["IH"] = df["ND_up"] & df["NID_up"]
    return df


# =============================
# SCORING
# =============================

def compute_os_p(df, patterns):
    counts = {p: df[p].sum() for p in patterns}

    def score(row):
        total = 0.0
        for p in patterns:
            if row[p] and counts[p] > 0:
                total += 1.0 / counts[p]
        return total

    df["OS_P"] = df.apply(score, axis=1)
    return df


def compute_uni(df, metrics):
    uni = []

    for metric in metrics:
        q3 = df[metric].quantile(0.75)
        vmax = df[metric].max()

        def u(x):
            if x <= q3:
                return 0.0
            if vmax == q3:
                return 1.0
            return min(1.0, (x - q3) / (vmax - q3))

        uni.append(df[metric].apply(lambda x: min(u(x), TAU)))

    df["UNI"] = sum(uni)
    return df


def finalize_score(df):
    df["Score"] = df["OS_P"] + LAMBDA * df["UNI"]
    return df


# =============================
# PIPELINE
# =============================

def analyze_dataset(path):
    ds = load_dataset(path)
    (
        apps, topics, nodes, libs,
        y_app, a_app, y_topic, a_topic,
        s_node, l_app, u_lib
    ) = extract_sets(ds)

    topic_names = {
        t["id"]: t.get("name", t["id"])
        for t in ds.get("topics", [])
    }
    categories = build_topic_categories(topic_names)

    app_node = {}
    for node, aset in s_node.items():
        for app in aset:
            app_node[app] = node

    apps_df = compute_app_metrics(
        apps, y_app, a_app, y_topic, a_topic, categories
    )
    topics_df = compute_topic_metrics(
        topics, y_topic, a_topic, app_node
    )
    nodes_df = compute_node_metrics(
        nodes, s_node, y_topic, a_topic
    )

    apps_df = apply_relative_flags(apps_df, ["R", "A", "RA", "TC", "LE"])
    topics_df = apply_relative_flags(topics_df, ["C", "I", "PS"])
    nodes_df = apply_relative_flags(nodes_df, ["ND", "NID"])

    apps_df = apply_app_patterns(apps_df)
    topics_df = apply_topic_patterns(topics_df)
    nodes_df = apply_node_patterns(nodes_df)

    apps_df = compute_os_p(apps_df, ["WR", "RS", "CS", "SD"])
    topics_df = compute_os_p(topics_df, ["CB", "DC"])
    nodes_df = compute_os_p(nodes_df, ["IH"])

    apps_df = compute_uni(apps_df, ["R", "A", "RA", "TC", "LE"])
    topics_df = compute_uni(topics_df, ["C", "I", "PS"])
    nodes_df = compute_uni(nodes_df, ["ND", "NID"])

    apps_df = finalize_score(apps_df)
    topics_df = finalize_score(topics_df)
    nodes_df = finalize_score(nodes_df)

    print("\n===", path.name, "===")
    print("\nApplications:")
    print(apps_df.sort_values("Score", ascending=False)[
        ["id", "Score", "OS_P", "UNI", "WR", "RS", "CS", "SD"]
    ])

    print("\nTopics:")
    print(topics_df.sort_values("Score", ascending=False)[
        ["id", "Score", "OS_P", "UNI", "CB", "DC"]
    ])

    print("\nNodes:")
    print(nodes_df.sort_values("Score", ascending=False)[
        ["id", "Score", "OS_P", "UNI", "IH"]
    ])


# =============================
# ENTRY POINT
# =============================

def main():
    if len(sys.argv) != 2:
        print("Usage: python structural_analysis.py <dataset_dir>")
        sys.exit(1)

    base = Path(sys.argv[1])
    for json_file in sorted(base.glob("*.json")):
        analyze_dataset(json_file)


if __name__ == "__main__":
    main()
