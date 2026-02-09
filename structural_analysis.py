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
K_LCR = 2  # Threshold for "low connectivity" in LCR metric


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
    """Extract core sets and relations.
    
    Note: Only applications are considered for pub/sub/uses relationships.
    Libraries are excluded from these relationships (libraries do not
    publish, subscribe, or use other libraries in this analysis).
    """
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

    # Only include publishes_to relationships where 'from' is an application (not a library)
    for r in rel.get("publishes_to", []):
        if r["from"] in apps and r["to"] in topics:
            y_app[r["from"]].add(r["to"])
            y_topic[r["to"]].add(r["from"])

    # Only include subscribes_to relationships where 'from' is an application (not a library)
    for r in rel.get("subscribes_to", []):
        if r["from"] in apps and r["to"] in topics:
            a_app[r["from"]].add(r["to"])
            a_topic[r["to"]].add(r["from"])

    for r in rel.get("runs_on", []):
        if r["from"] in apps and r["to"] in nodes:
            s_node[r["to"]].add(r["from"])

    # Only include uses relationships where 'from' is an application (not a library)
    # Libraries using other libraries are excluded
    for r in rel.get("uses", []):
        if r["from"] in apps and r["to"] in libs:
            l_app[r["from"]].add(r["to"])
            u_lib[r["to"]].add(r["from"])

    return apps, topics, nodes, libs, y_app, a_app, y_topic, a_topic, s_node, l_app, u_lib


# =============================
# METRICS
# =============================

def compute_app_metrics(apps, y_app, a_app, y_topic, a_topic, categories, app_names, l_app):
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
        le = len(l_app.get(app, set()))  # Library Exposure: number of libraries used

        rows.append({
            "id": app,
            "name": app_names.get(app, app),
            "R": reach,
            "A": amp,
            "RA": ra,
            "TC": tc,
            "LE": le,
        })

    return pd.DataFrame(rows)


def compute_topic_metrics(topics, y_topic, a_topic, app_node, topic_names, y_app, a_app):
    rows = []

    for topic in sorted(topics):
        pubs = y_topic[topic]
        subs = a_topic[topic]
        connected_apps = pubs | subs

        coverage = len(pubs) + len(subs)
        imbalance = abs(len(pubs) - len(subs)) / (coverage + 1)

        nodes = {app_node[a] for a in connected_apps if a in app_node}
        ps = len(nodes)

        # LCR: Low Connectivity Ratio
        # Count apps connected to this topic that have low overall connectivity
        low_conn_count = 0
        for app in connected_apps:
            total_topics = len(y_app.get(app, set()) | a_app.get(app, set()))
            if total_topics <= K_LCR:
                low_conn_count += 1
        lcr = low_conn_count / (len(connected_apps) + 1)

        rows.append({
            "id": topic,
            "name": topic_names.get(topic, topic),
            "C": coverage,
            "I": imbalance,
            "PS": ps,
            "LCR": lcr,
        })

    return pd.DataFrame(rows)


def compute_node_metrics(nodes, s_node, y_topic, a_topic, node_names):
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
            "name": node_names.get(node, node),
            "ND": nd,
            "NID": nid,
        })

    return pd.DataFrame(rows)


def compute_lib_metrics(libs, u_lib, s_node, lib_names):
    """Compute library-level metrics: LC and LCon."""
    rows = []

    # Build app -> node mapping for LCon calculation
    app_to_node = {}
    for node, apps in s_node.items():
        for app in apps:
            app_to_node[app] = node

    for lib in sorted(libs):
        users = u_lib[lib]
        
        # LC: Library Coverage - number of apps using this library
        lc = len(users)
        
        # LCon: Library Concentration - max apps using this lib on any single node
        node_counts = {}
        for app in users:
            if app in app_to_node:
                node = app_to_node[app]
                node_counts[node] = node_counts.get(node, 0) + 1
        lcon = max(node_counts.values()) if node_counts else 0

        rows.append({
            "id": lib,
            "name": lib_names.get(lib, lib),
            "LC": lc,
            "LCon": lcon,
        })

    return pd.DataFrame(rows)


# =============================
# RELATIVE INTERPRETATION
# =============================

def apply_relative_flags(df, metrics):
    for metric in metrics:
        q1 = df[metric].quantile(0.25)
        q3 = df[metric].quantile(0.75)
        
        # Handle edge case: if Q1=Q3, use stricter comparison
        # to avoid marking everyone as "high" or "low"
        if q1 == q3:
            # When all values are similar, only mark true outliers
            # Use max for "up" and min for "down"
            vmax = df[metric].max()
            vmin = df[metric].min()
            if vmax == vmin:
                # All values are identical - no outliers
                df[f"{metric}_up"] = False
                df[f"{metric}_down"] = False
            else:
                df[f"{metric}_up"] = df[metric] == vmax
                df[f"{metric}_down"] = df[metric] == vmin
        else:
            df[f"{metric}_up"] = df[metric] >= q3
            df[f"{metric}_down"] = df[metric] <= q1
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
    df["PA"] = df["LCR_up"]  # Peripheral Aggregator
    return df


def apply_node_patterns(df):
    df["IH"] = df["ND_up"] & df["NID_up"]
    return df


def apply_lib_patterns(df):
    df["WUL"] = df["LC_up"]   # Widely Used Library
    df["CL"] = df["LCon_up"]  # Concentrated Library
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

    app_names = {
        a["id"]: a.get("name", a["id"])
        for a in ds.get("applications", [])
    }
    topic_names = {
        t["id"]: t.get("name", t["id"])
        for t in ds.get("topics", [])
    }
    node_names = {
        n["id"]: n.get("name", n["id"])
        for n in ds.get("nodes", [])
    }
    lib_names = {
        l["id"]: l.get("name", l["id"])
        for l in ds.get("libraries", [])
    }
    categories = build_topic_categories(topic_names)

    app_node = {}
    for node, aset in s_node.items():
        for app in aset:
            app_node[app] = node

    apps_df = compute_app_metrics(
        apps, y_app, a_app, y_topic, a_topic, categories, app_names, l_app
    )
    topics_df = compute_topic_metrics(
        topics, y_topic, a_topic, app_node, topic_names, y_app, a_app
    )
    nodes_df = compute_node_metrics(
        nodes, s_node, y_topic, a_topic, node_names
    )
    libs_df = compute_lib_metrics(
        libs, u_lib, s_node, lib_names
    )

    apps_df = apply_relative_flags(apps_df, ["R", "A", "RA", "TC", "LE"])
    topics_df = apply_relative_flags(topics_df, ["C", "I", "PS", "LCR"])
    nodes_df = apply_relative_flags(nodes_df, ["ND", "NID"])
    if len(libs_df) > 0:
        libs_df = apply_relative_flags(libs_df, ["LC", "LCon"])

    apps_df = apply_app_patterns(apps_df)
    topics_df = apply_topic_patterns(topics_df)
    nodes_df = apply_node_patterns(nodes_df)
    if len(libs_df) > 0:
        libs_df = apply_lib_patterns(libs_df)

    apps_df = compute_os_p(apps_df, ["WR", "RS", "CS", "SD"])
    topics_df = compute_os_p(topics_df, ["CB", "DC", "PA"])
    nodes_df = compute_os_p(nodes_df, ["IH"])
    if len(libs_df) > 0:
        libs_df = compute_os_p(libs_df, ["WUL", "CL"])

    apps_df = compute_uni(apps_df, ["R", "A", "RA", "TC", "LE"])
    topics_df = compute_uni(topics_df, ["C", "I", "PS", "LCR"])
    nodes_df = compute_uni(nodes_df, ["ND", "NID"])
    if len(libs_df) > 0:
        libs_df = compute_uni(libs_df, ["LC", "LCon"])

    apps_df = finalize_score(apps_df)
    topics_df = finalize_score(topics_df)
    nodes_df = finalize_score(nodes_df)
    if len(libs_df) > 0:
        libs_df = finalize_score(libs_df)

    return apps_df, topics_df, nodes_df, libs_df


# =============================
# PATTERN EXPLANATIONS (condition | question)
# =============================

PATTERN_EXPLANATIONS = {
    "WR": "R≥Q3 ∧ A≥Q3 | Does this application reach a wide set of applications through a limited number of publish channels?",
    "RS": "RA≥Q3 ∨ RA≤Q1 | Does this application concentrate predominantly in a publisher or subscriber role?",
    "CS": "TC≥Q3 | Does this application participate in many different functional contexts (topic categories)?",
    "SD": "LE≥Q3 | Does this application depend on a relatively high number of shared libraries?",
    "CB": "C≥Q3 ∧ I≤Q1 | Does this topic connect many applications in a balanced manner?",
    "DC": "I≥Q3 | Does this topic exhibit a unidirectional communication pattern (publish- or subscribe-heavy)?",
    "PA": "LCR≥Q3 | Does this topic predominantly aggregate low-connectivity applications?",
    "IH": "ND≥Q3 ∧ NID≥Q3 | Does this worker node have high application density and high intra-node interaction density?",
    "WUL": "LC≥Q3 | Is this library used by a large number of applications?",
    "CL": "LCon≥Q3 | Is the usage of this library concentrated on specific worker nodes?",
}


def generate_findings(apps_df, topics_df, nodes_df, libs_df, top_k):
    """Generate human-readable findings summary."""
    findings = []
    
    # Top-K applications
    apps_sorted = apps_df.sort_values("Score", ascending=False).head(top_k)
    if len(apps_sorted) > 0:
        findings.append("=" * 70)
        findings.append(f"TOP {min(top_k, len(apps_sorted))} HIGHEST SCORING APPLICATIONS")
        findings.append("=" * 70)
        
        for _, row in apps_sorted.iterrows():
            if row["Score"] > 0:
                findings.append(f"\n▶ {row['name']} (Score: {row['Score']:.3f})")
                patterns = []
                if row.get("WR"): patterns.append("WR")
                if row.get("RS"): patterns.append("RS")
                if row.get("CS"): patterns.append("CS")
                if row.get("SD"): patterns.append("SD")
                
                if patterns:
                    findings.append(f"  Triggered patterns: {', '.join(patterns)}")
                    for p in patterns:
                        findings.append(f"    • {p}: {PATTERN_EXPLANATIONS[p]}")
                else:
                    findings.append("  No pattern triggered (UNI contribution only)")
    
    # Top-K topics
    topics_sorted = topics_df.sort_values("Score", ascending=False).head(top_k)
    if len(topics_sorted) > 0:
        findings.append("\n" + "=" * 70)
        findings.append(f"TOP {min(top_k, len(topics_sorted))} HIGHEST SCORING TOPICS")
        findings.append("=" * 70)
        
        for _, row in topics_sorted.iterrows():
            if row["Score"] > 0:
                findings.append(f"\n▶ {row['name']} (Score: {row['Score']:.3f})")
                patterns = []
                if row.get("CB"): patterns.append("CB")
                if row.get("DC"): patterns.append("DC")
                if row.get("PA"): patterns.append("PA")
                
                if patterns:
                    findings.append(f"  Triggered patterns: {', '.join(patterns)}")
                    for p in patterns:
                        findings.append(f"    • {p}: {PATTERN_EXPLANATIONS[p]}")
                else:
                    findings.append("  No pattern triggered (UNI contribution only)")
    
    # Top-K nodes
    nodes_sorted = nodes_df.sort_values("Score", ascending=False).head(top_k)
    if len(nodes_sorted) > 0:
        findings.append("\n" + "=" * 70)
        findings.append(f"TOP {min(top_k, len(nodes_sorted))} HIGHEST SCORING NODES")
        findings.append("=" * 70)
        
        for _, row in nodes_sorted.iterrows():
            if row["Score"] > 0:
                findings.append(f"\n▶ {row['name']} (Score: {row['Score']:.3f})")
                if row.get("IH"):
                    findings.append(f"  Triggered pattern: IH")
                    findings.append(f"    • IH: {PATTERN_EXPLANATIONS['IH']}")
                else:
                    findings.append("  No pattern triggered (UNI contribution only)")
    
    # Top-K libraries
    if len(libs_df) > 0:
        libs_sorted = libs_df.sort_values("Score", ascending=False).head(top_k)
        if len(libs_sorted) > 0:
            findings.append("\n" + "=" * 70)
            findings.append(f"TOP {min(top_k, len(libs_sorted))} HIGHEST SCORING LIBRARIES")
            findings.append("=" * 70)
            
            for _, row in libs_sorted.iterrows():
                if row["Score"] > 0:
                    findings.append(f"\n▶ {row['name']} (Score: {row['Score']:.3f})")
                    patterns = []
                    if row.get("WUL"): patterns.append("WUL")
                    if row.get("CL"): patterns.append("CL")
                    
                    if patterns:
                        findings.append(f"  Triggered patterns: {', '.join(patterns)}")
                        for p in patterns:
                            findings.append(f"    • {p}: {PATTERN_EXPLANATIONS[p]}")
                    else:
                        findings.append("  No pattern triggered (UNI contribution only)")
    
    # Summary statistics
    findings.append("\n" + "=" * 70)
    findings.append("SUMMARY STATISTICS")
    findings.append("=" * 70)
    
    app_with_pattern = len(apps_df[(apps_df["WR"]) | (apps_df["RS"]) | (apps_df["CS"]) | (apps_df["SD"])])
    topic_with_pattern = len(topics_df[(topics_df["CB"]) | (topics_df["DC"]) | (topics_df["PA"])])
    node_with_pattern = len(nodes_df[nodes_df["IH"]])
    
    findings.append(f"  Total applications: {len(apps_df)}, pattern triggered: {app_with_pattern} ({100*app_with_pattern/len(apps_df):.1f}%)")
    findings.append(f"  Total topics: {len(topics_df)}, pattern triggered: {topic_with_pattern} ({100*topic_with_pattern/len(topics_df):.1f}%)")
    findings.append(f"  Total nodes: {len(nodes_df)}, pattern triggered: {node_with_pattern} ({100*node_with_pattern/len(nodes_df):.1f}%)")
    
    if len(libs_df) > 0:
        lib_with_pattern = len(libs_df[(libs_df["WUL"]) | (libs_df["CL"])])
        findings.append(f"  Total libraries: {len(libs_df)}, pattern triggered: {lib_with_pattern} ({100*lib_with_pattern/len(libs_df):.1f}%)")
    
    return "\n".join(findings)


def write_results(path, apps_df, topics_df, nodes_df, libs_df, output_dir, top_k):
    """Write analysis results to a text file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{path.stem}_results.txt"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"=== {path.name} ===\n")
        f.write(f"{'='*60}\n\n")

        # Findings summary
        f.write("FINDINGS SUMMARY (Top-{})\n".format(top_k))
        f.write("-" * 60 + "\n")
        f.write(generate_findings(apps_df, topics_df, nodes_df, libs_df, top_k))
        f.write("\n\n")

        # Raw data
        f.write("\n" + "=" * 60 + "\n")
        f.write("RAW DATA\n")
        f.write("=" * 60 + "\n\n")

        f.write("APPLICATIONS\n")
        f.write("-" * 60 + "\n")
        apps_sorted = apps_df.sort_values("Score", ascending=False)
        f.write(apps_sorted[
            ["name", "Score", "OS_P", "UNI", "WR", "RS", "CS", "SD"]
        ].to_string(index=False))
        f.write("\n\n")

        f.write("TOPICS\n")
        f.write("-" * 60 + "\n")
        topics_sorted = topics_df.sort_values("Score", ascending=False)
        f.write(topics_sorted[
            ["name", "Score", "OS_P", "UNI", "CB", "DC", "PA"]
        ].to_string(index=False))
        f.write("\n\n")

        f.write("NODES\n")
        f.write("-" * 60 + "\n")
        nodes_sorted = nodes_df.sort_values("Score", ascending=False)
        f.write(nodes_sorted[
            ["name", "Score", "OS_P", "UNI", "IH"]
        ].to_string(index=False))
        f.write("\n")

        if len(libs_df) > 0:
            f.write("\nLIBRARIES\n")
            f.write("-" * 60 + "\n")
            libs_sorted = libs_df.sort_values("Score", ascending=False)
            f.write(libs_sorted[
                ["name", "Score", "OS_P", "UNI", "WUL", "CL"]
            ].to_string(index=False))
            f.write("\n")

    return output_file


def generate_expert_template(path, apps_df, topics_df, nodes_df, libs_df, expert_dir, top_k=10):
    """Generate expert evaluation template for a dataset.
    
    Creates experts/<dataset_name>/template.txt with top-K components
    per category (sorted by Score), ready for experts to fill in.
    """
    dataset_name = path.stem  # e.g. hub_application
    template_dir = expert_dir / dataset_name
    template_dir.mkdir(parents=True, exist_ok=True)
    template_file = template_dir / "template.txt"

    lines = []
    lines.append(f"# EXPERT EVALUATION TEMPLATE — {dataset_name}")
    lines.append("# ========================================")
    lines.append("# Expert: [Your name]")
    lines.append("# Date: [Date]")
    lines.append("#")
    lines.append("# DESCRIPTION:")
    lines.append('# This evaluation does NOT aim to determine whether components are')
    lines.append("# \"good/bad\" or \"correct/incorrect\"; it aims to identify whether a")
    lines.append("# component is RELATIVELY DIFFERENT/ATYPICAL compared to the system's")
    lines.append("# overall structural patterns.")
    lines.append("#")
    lines.append("# For each component, enter one of the following values:")
    lines.append("#   E = Yes, STRUCTURALLY ATYPICAL")
    lines.append("#       This component exhibits a relatively different/notable structural")
    lines.append("#       pattern compared to other similar components in the system.")
    lines.append("#")
    lines.append("#   H = No, STRUCTURALLY NORMAL")
    lines.append("#       This component conforms to the system's general structural pattern.")
    lines.append("#")
    lines.append("# IMPORTANT:")
    lines.append('# - \"It is designed this way\" does NOT affect the evaluation.')
    lines.append("# - Goal: Determine which components should receive special attention")
    lines.append("#   during architectural review.")
    lines.append("#")
    lines.append("# ========================================")
    lines.append("")

    # Applications (top-K)
    apps_sorted = apps_df.sort_values("Score", ascending=False).head(top_k)
    lines.append(f"[APPLICATIONS] (Top-{min(top_k, len(apps_df))})")
    for name in apps_sorted["name"]:
        lines.append(f"{name}: ")
    lines.append("")

    # Topics (top-K)
    topics_sorted = topics_df.sort_values("Score", ascending=False).head(top_k)
    lines.append(f"[TOPICS] (Top-{min(top_k, len(topics_df))})")
    for name in topics_sorted["name"]:
        lines.append(f"{name}: ")
    lines.append("")

    # Nodes (top-K)
    nodes_sorted = nodes_df.sort_values("Score", ascending=False).head(top_k)
    lines.append(f"[NODES] (Top-{min(top_k, len(nodes_df))})")
    for name in nodes_sorted["name"]:
        lines.append(f"{name}: ")
    lines.append("")

    # Libraries (top-K)
    if len(libs_df) > 0:
        libs_sorted = libs_df.sort_values("Score", ascending=False).head(top_k)
        lines.append(f"[LIBRARIES] (Top-{min(top_k, len(libs_df))})")
        for name in libs_sorted["name"]:
            lines.append(f"{name}: ")
        lines.append("")

    with open(template_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return template_file


# =============================
# ENTRY POINT
# =============================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Publish-Subscribe Structural Analysis Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  python structural_analysis.py datasets/           # Analyze all JSON files
  python structural_analysis.py datasets/ -k 5      # Show top 5 results
  python structural_analysis.py datasets/ --top 3   # Show top 3 results
        """
    )
    parser.add_argument("dataset_dir", help="Directory containing JSON dataset files")
    parser.add_argument("-k", "--top", type=int, default=5, 
                        help="Maximum number of results per category (default: 5)")
    
    args = parser.parse_args()
    
    base = Path(args.dataset_dir)
    output_dir = base.parent / "results"
    expert_dir = base.parent / "experts"
    top_k = args.top

    print(f"Analyzing datasets in: {base}")
    print(f"Results will be saved to: {output_dir}")
    print(f"Expert templates will be saved to: {expert_dir}")
    print(f"Top-K: {top_k}\n")

    for json_file in sorted(base.glob("*.json")):
        # Skip expert files
        if "expert" in json_file.name.lower():
            continue
        apps_df, topics_df, nodes_df, libs_df = analyze_dataset(json_file)
        output_file = write_results(json_file, apps_df, topics_df, nodes_df, libs_df, output_dir, top_k)
        template_file = generate_expert_template(json_file, apps_df, topics_df, nodes_df, libs_df, expert_dir, top_k)
        print(f"✓ {json_file.name} → {output_file.name}, {template_file.relative_to(base.parent)}")


if __name__ == "__main__":
    main()
