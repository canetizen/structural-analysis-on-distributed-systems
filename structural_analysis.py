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
# PATTERN DEFINITIONS & EXPERT QUESTIONS
# =============================

# Pattern definitions with metric conditions (for display)
PATTERN_CONDITIONS = {
    "WR": "R≥Q3 ∧ A≥Q3",
    "RS": "RA≥Q3 ∨ RA≤Q1", 
    "CS": "TC≥Q3",
    "SD": "LE≥Q3",
    "CB": "C≥Q3 ∧ I≤Q1",
    "DC": "I≥Q3",
    "PA": "LCR≥Q3",
    "IH": "ND≥Q3 ∧ NID≥Q3",
    "WUL": "LC≥Q3",
    "CL": "LCon≥Q3",
}

# Metric full names (Turkish - matching paper terminology)
METRIC_NAMES = {
    "R": "Etki Alanı (Reach)",
    "A": "Yoğunlaştırma (Amplification)",
    "RA": "Rol Asimetrisi (Role Asymmetry)",
    "TC": "Bağlam Çeşitliliği (Topic Context Diversity)",
    "LE": "Kütüphane Maruziyeti (Library Exposure)",
    "C": "Kapsayıcılık (Coverage)",
    "I": "Dengesizlik (Imbalance)",
    "PS": "Fiziksel Yayılım (Physical Spread)",
    "LCR": "Düşük Bağlantılı Uygulama Oranı (Low Connectivity Ratio)",
    "ND": "Düğüm Yoğunluğu (Node Density)",
    "NID": "Düğüm İçi Etkileşim Yoğunluğu (Node Interaction Density)",
    "LC": "Kütüphane Yaygınlığı (Library Coverage)",
    "LCon": "Kütüphane Yoğunlaşması (Library Concentration)",
}

# Pattern full names (Turkish - matching paper terminology)
PATTERN_NAMES = {
    "WR": "Geniş Etki Alanı (Wide Reach)",
    "RS": "Rol Dengesizliği (Role Skew)",
    "CS": "Bağlam Yayılımı (Context Spread)",
    "SD": "Ortak Bağımlılık Maruziyeti (Shared Dependency)",
    "CB": "İletişim Omurgası (Communication Backbone)",
    "DC": "Yönlü Yoğunlaşma (Directional Concentration)",
    "PA": "Çevresel Toplayıcı (Peripheral Aggregator)",
    "IH": "Yoğunlaşmış Etkileşim Kümesi (Interaction Hotspot)",
    "WUL": "Yaygın Ortak Kütüphane (Widely Used Library)",
    "CL": "Yoğunlaşmış Ortak Kütüphane (Concentrated Library)",
}

# Pattern descriptions - what each pattern means (Turkish)
PATTERN_DESCRIPTIONS = {
    "WR": "Bu uygulama, az sayıda yayın kanalı kullanarak çok sayıda uygulamaya dolaylı olarak erişebiliyor. Etki Alanı (R) ve Yoğunlaştırma (A) metrikleri görece yüksek.",
    "RS": "Bu uygulama, yayıncı veya abone rollerinden birinde belirgin şekilde yoğunlaşıyor. Rol Asimetrisi (RA) metriği görece uç değerde.",
    "CS": "Bu uygulama, birçok farklı işlevsel bağlamda (konu kategorisinde) etkileşimde bulunuyor. Bağlam Çeşitliliği (TC) metriği görece yüksek.",
    "SD": "Bu uygulama, görece yüksek sayıda ortak kütüphaneye bağımlı. Kütüphane Maruziyeti (LE) metriği görece yüksek.",
    "CB": "Bu konu, çok sayıda uygulamayı dengeli biçimde (hem yayıncı hem abone) birbirine bağlıyor. Kapsayıcılık (C) yüksek, Dengesizlik (I) düşük.",
    "DC": "Bu konu, tek yönlü iletişim örüntüsü sergiliyor (ağırlıklı yayın veya abonelik). Dengesizlik (I) metriği görece yüksek.",
    "PA": "Bu konu, sistem genelinde düşük bağlantılı uygulamaları bir araya topluyor. Düşük Bağlantılı Uygulama Oranı (LCR) görece yüksek.",
    "IH": "Bu çalışma düğümünde hem çok sayıda uygulama konumlanmış hem de uygulamalar arası etkileşim yoğun. Düğüm Yoğunluğu (ND) ve Düğüm İçi Etkileşim (NID) görece yüksek.",
    "WUL": "Bu kütüphane, sistem genelinde çok sayıda uygulama tarafından kullanılıyor. Kütüphane Yaygınlığı (LC) görece yüksek.",
    "CL": "Bu kütüphanenin kullanımı belirli çalışma düğümlerinde yoğunlaşmış. Kütüphane Yoğunlaşması (LCon) görece yüksek.",
}

# Expert survey questions per pattern (Turkish) - Three-phase questions
# Phase 1: Detection accuracy - pattern-specific (Tespit doğru mu?)
# Phase 2: If correct, awareness (Farkında mıydınız?)
# Phase 3: Component-level - any other anomaly? (Başka aykırılık var mı?)

# Soru 1: Pattern'e özgü tespit doğrulama soruları
PATTERN_QUESTIONS_PHASE1 = {
    "WR": "Bu uygulama sınırlı sayıda yayın kanalıyla geniş bir uygulama kümesine ulaşıyor mu?",
    "RS": "Bu uygulama ağırlıklı olarak yayıncı veya abone rolünde yoğunlaşıyor mu?",
    "CS": "Bu uygulama birçok farklı işlevsel bağlamda (konu kategorisinde) yer alıyor mu?",
    "SD": "Bu uygulama görece yüksek sayıda ortak kütüphaneye bağımlı mı?",
    "CB": "Bu konu çok sayıda uygulamayı dengeli biçimde birbirine bağlıyor mu?",
    "DC": "Bu konu tek yönlü iletişim örüntüsü (yayın veya abonelik ağırlıklı) sergiliyor mu?",
    "PA": "Bu konu ağırlıklı olarak düşük bağlantılı uygulamaları bir araya topluyor mu?",
    "IH": "Bu çalışma düğümünde yüksek uygulama yoğunluğu ve düğüm içi etkileşim yoğunluğu var mı?",
    "WUL": "Bu kütüphane çok sayıda uygulama tarafından kullanılıyor mu?",
    "CL": "Bu kütüphanenin kullanımı belirli çalışma düğümlerinde yoğunlaşıyor mu?",
}
SURVEY_OPTIONS_1 = "(a) Evet | (b) Hayır"

# Soru 2: Farkındalık sorusu (Soru 1 = Evet ise)
SURVEY_QUESTION_2 = "Bu durum için farkında mıydınız?"
SURVEY_OPTIONS_2 = "(a) Evet, tasarımsal bir tercih | (b) Hayır, fark edilmemişti"

# Soru 3: Komponent bazında ek aykırılık sorusu
SURVEY_QUESTION_3 = "Bu bileşen için tespit edilenler dışında başka bir yapısal aykırılık var mı?"
SURVEY_OPTIONS_3 = "(a) Hayır | (b) Evet (açıklayınız)"

# Legacy compatibility
PATTERN_QUESTIONS_PHASE2 = {p: SURVEY_QUESTION_2 for p in PATTERN_QUESTIONS_PHASE1}

# Legacy single question format (for backward compatibility)
PATTERN_QUESTIONS = PATTERN_QUESTIONS_PHASE1

# Legacy format for backward compatibility
PATTERN_EXPLANATIONS = {
    p: f"{PATTERN_CONDITIONS[p]} | {PATTERN_QUESTIONS[p]}" 
    for p in PATTERN_CONDITIONS
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


def generate_expert_survey_csv(apps_df, topics_df, nodes_df, libs_df, top_k=10):
    """Generate CSV format expert survey with top-K components and their triggered patterns.
    
    Three-phase questions per component:
    - Phase 1: Tespit doğru mu? (Pattern-specific)
    - Phase 2: Farkında mıydınız? (If Phase 1 = Yes)
    - Phase 3: Başka aykırılık var mı? (Component-level, once per component)
    """
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
    
    # Header
    writer.writerow([
        "Bileşen Türü",
        "Bileşen Adı", 
        "Birleşik Skor",
        "Örüntü Kodu",
        "Örüntü Açıklaması",
        "Soru 1: Tespit doğru mu?",
        "Şıklar",
        "Cevap 1",
        "Soru 2: Farkında mıydınız? (Cevap 1=a ise)",
        "Şıklar",
        "Cevap 2",
        "Soru 3: Başka aykırılık var mı?",
        "Şıklar",
        "Cevap 3",
        "Açıklama/Yorum"
    ])
    
    def write_component_rows(writer, comp_type, row, patterns, pattern_list):
        """Write rows for a single component with all its patterns + final question."""
        triggered = [p for p in pattern_list if row.get(p, False)]
        
        if not triggered and row["Score"] <= 0:
            return  # Skip components with no patterns and no score
        
        # Write each triggered pattern as a row
        for i, p in enumerate(triggered):
            is_last = (i == len(triggered) - 1)
            writer.writerow([
                comp_type,
                row["name"],
                f"{row['Score']:.3f}",
                p,
                PATTERN_DESCRIPTIONS[p],
                PATTERN_QUESTIONS_PHASE1[p],
                SURVEY_OPTIONS_1,
                "",
                SURVEY_QUESTION_2,
                SURVEY_OPTIONS_2,
                "",
                SURVEY_QUESTION_3 if is_last else "",
                SURVEY_OPTIONS_3 if is_last else "",
                "",
                ""
            ])
        
        # If no pattern triggered but has UNI score
        if not triggered and row["Score"] > 0:
            writer.writerow([
                comp_type,
                row["name"],
                f"{row['Score']:.3f}",
                "-",
                "Örüntü tetiklenmedi - yalnızca tek-boyutlu aykırılık katkısı (UNI) mevcut.",
                "Bu bileşen için metrik değerleri görece uç konumda mı?",
                SURVEY_OPTIONS_1,
                "",
                SURVEY_QUESTION_2,
                SURVEY_OPTIONS_2,
                "",
                SURVEY_QUESTION_3,
                SURVEY_OPTIONS_3,
                "",
                ""
            ])
    
    # Applications - Top K
    apps_sorted = apps_df.sort_values("Score", ascending=False).head(top_k)
    app_patterns = ["WR", "RS", "CS", "SD"]
    for _, row in apps_sorted.iterrows():
        write_component_rows(writer, "Uygulama", row, app_patterns, app_patterns)
    
    # Topics - Top K
    topics_sorted = topics_df.sort_values("Score", ascending=False).head(top_k)
    topic_patterns = ["CB", "DC", "PA"]
    for _, row in topics_sorted.iterrows():
        write_component_rows(writer, "Konu", row, topic_patterns, topic_patterns)
    
    # Nodes - Top K
    nodes_sorted = nodes_df.sort_values("Score", ascending=False).head(top_k)
    node_patterns = ["IH"]
    for _, row in nodes_sorted.iterrows():
        write_component_rows(writer, "Çalışma Düğümü", row, node_patterns, node_patterns)
    
    # Libraries - Top K
    if len(libs_df) > 0:
        libs_sorted = libs_df.sort_values("Score", ascending=False).head(top_k)
        lib_patterns = ["WUL", "CL"]
        for _, row in libs_sorted.iterrows():
            write_component_rows(writer, "Kütüphane", row, lib_patterns, lib_patterns)
    
    return output.getvalue()


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

    # Write CSV expert survey
    csv_file = output_dir / f"{path.stem}_expert_survey.csv"
    csv_content = generate_expert_survey_csv(apps_df, topics_df, nodes_df, libs_df, top_k=10)
    with open(csv_file, "w", encoding="utf-8-sig", newline="") as f:
        f.write(csv_content)

    return output_file


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
    top_k = args.top

    print(f"Analyzing datasets in: {base}")
    print(f"Results will be saved to: {output_dir}")
    print(f"Top-K: {top_k}\n")

    for json_file in sorted(base.glob("*.json")):
        # Skip expert_opinions.json
        if "expert" in json_file.name.lower():
            continue
        apps_df, topics_df, nodes_df, libs_df = analyze_dataset(json_file)
        output_file = write_results(json_file, apps_df, topics_df, nodes_df, libs_df, output_dir, top_k)
        csv_file = output_dir / f"{json_file.stem}_expert_survey.csv"
        print(f"✓ {json_file.name} → {output_file.name}, {csv_file.name}")


if __name__ == "__main__":
    main()
