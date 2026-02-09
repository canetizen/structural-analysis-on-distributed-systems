#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Expert Evaluation Comparison Tool

Compares system structural analysis results with expert evaluations.
Implements majority voting across multiple experts (≥3 out of 5).
Computes Precision@K, nDCG@K, and Fleiss' κ for K=5, 10.

Expert evaluations are in simple TXT format:
- One file per expert (expert_1.txt, expert_2.txt, etc.)
- E = anomaly, H = not anomaly

Output format matches paper Table format:
- Component Type | K | Prec@K | nDCG@K | Fleiss' κ
"""

import argparse
import math
from pathlib import Path


def parse_results_txt(path):
    """Parse result TXT file and extract component rankings"""
    with open(path, encoding="utf-8") as f:
        content = f.read()
    
    results = {"applications": [], "topics": [], "nodes": [], "libraries": []}
    
    # Find RAW DATA section
    if "RAW DATA" in content:
        raw = content.split("RAW DATA")[1]
    else:
        raw = content
    
    def parse_section(section_text):
        """Parse a section and extract name-score pairs"""
        items = []
        for line in section_text.strip().split("\n")[2:]:  # Skip header lines
            parts = line.split()
            if len(parts) >= 2:
                # Find first numeric value (Score column)
                for i, part in enumerate(parts):
                    try:
                        score = float(part)
                        name = " ".join(parts[:i])
                        if name:
                            items.append({"name": name, "score": score})
                        break
                    except ValueError:
                        continue
        return items
    
    # Parse each section
    if "APPLICATIONS" in raw:
        section = raw.split("APPLICATIONS")[1].split("TOPICS")[0]
        results["applications"] = parse_section(section)
    
    if "TOPICS" in raw:
        if "NODES" in raw.split("TOPICS")[1]:
            section = raw.split("TOPICS")[1].split("NODES")[0]
        else:
            section = raw.split("TOPICS")[1]
        results["topics"] = parse_section(section)
    
    if "NODES" in raw:
        if "LIBRARIES" in raw.split("NODES")[1]:
            section = raw.split("NODES")[1].split("LIBRARIES")[0]
        else:
            section = raw.split("NODES")[1]
        results["nodes"] = parse_section(section)
    
    if "LIBRARIES" in raw:
        section = raw.split("LIBRARIES")[1]
        results["libraries"] = parse_section(section)
    
    return results


def parse_expert_txt(path):
    """Parse expert evaluation TXT file.
    
    Format:
    [APPLICATIONS]
    ComponentName: E
    ComponentName2: H
    
    [TOPICS]
    TopicName: E
    ...
    """
    with open(path, encoding="utf-8") as f:
        content = f.read()
    
    evaluations = {
        "applications": [],
        "topics": [],
        "nodes": [],
        "libraries": []
    }
    
    section_map = {
        "[APPLICATIONS]": "applications",
        "[TOPICS]": "topics",
        "[NODES]": "nodes",
        "[LIBRARIES]": "libraries"
    }
    
    current_section = None
    
    for line in content.split("\n"):
        line = line.strip()
        
        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue
        
        # Check for section header (supports optional suffix like "(Top-10)")
        matched_section = None
        for header, section_key in section_map.items():
            if line.startswith(header):
                matched_section = section_key
                break
        if matched_section:
            current_section = matched_section
            continue
        
        # Parse component evaluation
        if current_section and ":" in line:
            parts = line.split(":", 1)
            name = parts[0].strip()
            value = parts[1].strip().upper() if len(parts) > 1 else ""
            
            if name and value in ["E", "H"]:
                is_anomaly = value == "E"
                evaluations[current_section].append({
                    "name": name,
                    "is_anomaly": is_anomaly
                })
    
    return evaluations


def get_top_k_names(results, category, k):
    """Return top-k component names sorted by score descending"""
    sorted_items = sorted(results[category], key=lambda x: x["score"], reverse=True)
    return [item["name"] for item in sorted_items[:k]]


def apply_majority_voting(expert_evaluations_list, category, min_votes=3):
    """
    Apply majority voting to determine ground truth.
    
    A component is considered "anomalous" if at least min_votes experts
    marked it as anomalous (is_anomaly=True).
    
    Returns: List of component names that are anomalous according to majority
    """
    if not expert_evaluations_list:
        return []
    
    # Count votes for each component
    vote_counts = {}
    
    for expert_eval in expert_evaluations_list:
        if category not in expert_eval:
            continue
        
        for component in expert_eval[category]:
            name = component["name"]
            is_anomaly = component.get("is_anomaly", False)
            
            if name not in vote_counts:
                vote_counts[name] = 0
            if is_anomaly:
                vote_counts[name] += 1
    
    # Return components with majority votes
    anomalous = [name for name, votes in vote_counts.items() if votes >= min_votes]
    return anomalous


def compute_ndcg_at_k(ranked_names, expert_anomalous, k):
    """Compute nDCG@K.
    
    Relevance is binary: 1 if expert majority says atypical, 0 otherwise.
    Uses standard DCG with log2(i+1) discount.
    """
    expert_set = set(expert_anomalous)
    top_k = ranked_names[:k]
    
    # DCG@K
    dcg = 0.0
    for i, name in enumerate(top_k):
        rel = 1.0 if name in expert_set else 0.0
        dcg += rel / math.log2(i + 2)  # i is 0-indexed, formula uses log2(rank+1)
    
    # IDCG@K: ideal ranking puts all relevant items first
    num_relevant = min(len(expert_set), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(num_relevant))
    
    return dcg / idcg if idcg > 0 else 0.0


def compute_fleiss_kappa(expert_evaluations_list, category):
    """Compute Fleiss' kappa for inter-rater agreement.
    
    Measures agreement among multiple experts on binary classification
    (E=atypical vs H=normal) for a given component category.
    """
    if len(expert_evaluations_list) < 2:
        return None
    
    # Collect all component names rated in this category
    all_names = set()
    for expert_eval in expert_evaluations_list:
        for comp in expert_eval.get(category, []):
            all_names.add(comp["name"])
    
    if not all_names:
        return None
    
    n_raters = len(expert_evaluations_list)
    name_list = sorted(all_names)
    N = len(name_list)
    
    # Build rating matrix: for each component, count E and H votes
    matrix = []  # matrix[i] = [e_count, h_count]
    for name in name_list:
        e_count = 0
        h_count = 0
        for expert_eval in expert_evaluations_list:
            for comp in expert_eval.get(category, []):
                if comp["name"] == name:
                    if comp.get("is_anomaly", False):
                        e_count += 1
                    else:
                        h_count += 1
                    break
        matrix.append([e_count, h_count])
    
    # P_i for each subject: agreement proportion
    P_sum = 0.0
    for votes in matrix:
        n_i = sum(votes)
        if n_i <= 1:
            continue
        P_sum += (sum(v * v for v in votes) - n_i) / (n_i * (n_i - 1))
    
    P_bar = P_sum / N if N > 0 else 0.0
    
    # P_e: expected agreement by chance
    total_ratings = sum(sum(row) for row in matrix)
    if total_ratings == 0:
        return None
    
    p_j_list = []
    for j in range(2):  # 2 categories: E, H
        col_sum = sum(matrix[i][j] for i in range(N))
        p_j_list.append(col_sum / total_ratings)
    
    P_e = sum(p * p for p in p_j_list)
    
    if P_e >= 1.0:
        return 1.0
    
    return (P_bar - P_e) / (1.0 - P_e)


def evaluate_all_k_values(results, expert_anomalous, category, k_values=[5, 10]):
    """Evaluate Precision@K and nDCG@K for multiple K values."""
    evaluations = []
    
    # Get full ranked list by score
    sorted_items = sorted(results[category], key=lambda x: x["score"], reverse=True)
    ranked_names = [item["name"] for item in sorted_items]
    expert_set = set(expert_anomalous)
    
    for k in k_values:
        top_k = ranked_names[:k]
        
        # Precision@K
        tp = len(set(top_k) & expert_set)
        precision = tp / len(top_k) if top_k else 0.0
        
        # nDCG@K
        ndcg = compute_ndcg_at_k(ranked_names, expert_anomalous, k)
        
        evaluations.append({
            "k": k,
            "precision": precision,
            "ndcg": ndcg,
        })
    
    return evaluations


def print_table(all_results, num_experts, min_votes, kappa_values=None, output_file=None):
    """Print results in paper table format with Prec@K, nDCG@K, Fleiss' κ."""
    lines = []
    
    lines.append("=" * 70)
    lines.append("EXPERT EVALUATION RESULTS")
    lines.append("=" * 70)
    lines.append(f"Number of experts: {num_experts}")
    lines.append(f"Majority threshold: ≥{min_votes} votes")
    lines.append("")
    lines.append(f"{'Component Type':<20} {'K':<5} {'Prec@K':<12} {'nDCG@K':<12} {'Fleiss κ':<12}")
    lines.append("-" * 70)
    
    category_names = {
        "applications": "Application",
        "topics": "Topic",
        "nodes": "Node",
        "libraries": "Library"
    }
    
    for category, evaluations in all_results.items():
        if not evaluations:
            continue
        display_name = category_names.get(category, category)
        kappa = kappa_values.get(category) if kappa_values else None
        kappa_str = f"{kappa:.2f}" if kappa is not None else "—"
        
        for i, metrics in enumerate(evaluations):
            if i == 0:
                cat_display = display_name
                k_display = kappa_str
            else:
                cat_display = ""
                k_display = ""
            
            lines.append(f"{cat_display:<20} {metrics['k']:<5} {metrics['precision']:<12.2f} {metrics['ndcg']:<12.2f} {k_display:<12}")
    
    lines.append("-" * 70)
    lines.append("")
    
    # LaTeX table output
    lines.append("=" * 70)
    lines.append("LaTeX TABLE FORMAT")
    lines.append("=" * 70)
    lines.append("")
    
    for category, evaluations in all_results.items():
        if not evaluations:
            continue
        display_name = category_names.get(category, category)
        kappa = kappa_values.get(category) if kappa_values else None
        kappa_str = f"{kappa:.2f}" if kappa is not None else "—"
        n_rows = len(evaluations)
        
        for i, metrics in enumerate(evaluations):
            if i == 0:
                cat_display = f"\\multirow{{{n_rows}}}{{*}}{{{display_name}}}"
                k_col = f"\\multirow{{{n_rows}}}{{*}}{{{kappa_str}}}"
            else:
                cat_display = ""
                k_col = ""
            
            lines.append(f"{cat_display} & {metrics['k']} & {metrics['precision']:.2f} & {metrics['ndcg']:.2f} & {k_col} \\\\")
        lines.append("\\hline")
    
    lines.append("")
    
    # Print to console
    for line in lines:
        print(line)
    
    # Write to file if specified
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"\nResults saved to: {output_file}")


def print_detailed_results(results, expert_evaluations_list, expert_anomalous_by_category, min_votes):
    """Print detailed comparison for debugging"""
    print("\n" + "=" * 70)
    print("DETAILED COMPARISON")
    print("=" * 70)
    
    categories = ["applications", "topics", "nodes", "libraries"]
    category_names = {
        "applications": "APPLICATIONS",
        "topics": "TOPICS",
        "nodes": "NODES",
        "libraries": "LIBRARIES"
    }
    
    for category in categories:
        if not results[category]:
            continue
            
        print(f"\n[{category_names.get(category, category.upper())}]")
        
        # System ranking
        system_items = sorted(results[category], key=lambda x: x["score"], reverse=True)
        print("  System Ranking (Score):")
        for i, item in enumerate(system_items[:10], 1):
            marker = "✓" if item["name"] in expert_anomalous_by_category.get(category, []) else " "
            print(f"    {marker} {i}. {item['name']} (Score: {item['score']:.3f})")
        
        # Expert ground truth
        expert_anomalous = expert_anomalous_by_category.get(category, [])
        print(f"\n  Expert Assessment (atypical with ≥{min_votes} votes):")
        for name in expert_anomalous:
            print(f"    • {name}")
        
        if not expert_anomalous:
            print("    (no component reached majority vote)")


def main():
    parser = argparse.ArgumentParser(
        description="Compare system results with expert evaluations using majority voting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  python compare_expert.py results/hub_application_results.txt -e experts/
  python compare_expert.py results/ -e experts/ --all
  
Expert evaluation files should be named: expert_1.txt, expert_2.txt, etc.
        """
    )
    parser.add_argument("results_path", help="Results file or directory (with --all)")
    parser.add_argument("--expert-dir", "-e", default="experts/",
                        help="Base directory containing per-dataset expert folders")
    parser.add_argument("--min-votes", "-m", type=int, default=3,
                        help="Minimum votes for majority (default: 3 out of 5)")
    parser.add_argument("--output", "-o", help="Output file for results")
    parser.add_argument("--detailed", "-d", action="store_true",
                        help="Show detailed comparison")
    parser.add_argument("--all", "-a", action="store_true",
                        help="Process all result files in directory")
    
    args = parser.parse_args()
    
    results_path = Path(args.results_path)
    expert_base_dir = Path(args.expert_dir)
    
    if not expert_base_dir.exists():
        print(f"Error: Expert base directory not found: {expert_base_dir}")
        return
    
    # Determine files to process
    if args.all and results_path.is_dir():
        result_files = sorted(results_path.glob("*_results.txt"))
    elif results_path.is_file():
        result_files = [results_path]
    else:
        print(f"Error: Invalid path: {results_path}")
        return
    
    if not result_files:
        print("Error: No result files found.")
        return

    # Aggregate results across all datasets for combined table
    combined_results = {"applications": [], "topics": [], "nodes": [], "libraries": []}
    combined_kappas = {"applications": [], "topics": [], "nodes": [], "libraries": []}
    datasets_processed = 0

    for result_file in result_files:
        # Derive dataset name: hub_application_results.txt → hub_application
        dataset_name = result_file.stem.replace("_results", "")
        expert_dir = expert_base_dir / dataset_name
        
        if not expert_dir.exists():
            print(f"Warning: Expert folder not found for {dataset_name}: {expert_dir}")
            continue
        
        expert_files = sorted(expert_dir.glob("expert_*.txt"))
        if not expert_files:
            print(f"Warning: No expert files in {expert_dir}")
            continue
        
        print(f"\n{'='*70}")
        print(f"Dataset: {dataset_name}")
        print(f"Result file: {result_file.name}")
        print(f"Expert files: {len(expert_files)}")
        for ef in expert_files:
            print(f"  • {ef.name}")
        print(f"Minimum votes for majority: {args.min_votes}")
        print(f"{'='*70}")
        
        # Parse expert evaluations for this dataset
        expert_evaluations_list = []
        for ef in expert_files:
            try:
                eval_data = parse_expert_txt(ef)
                expert_evaluations_list.append(eval_data)
            except Exception as e:
                print(f"Warning: Error parsing {ef.name}: {e}")
        
        if len(expert_evaluations_list) < args.min_votes:
            print(f"Warning: Only {len(expert_evaluations_list)} experts, but minimum votes is {args.min_votes}")
        
        # Parse results
        results = parse_results_txt(result_file)
        
        # Apply majority voting and compute metrics for each category
        categories = ["applications", "topics", "nodes", "libraries"]
        expert_anomalous_by_category = {}
        dataset_results = {}
        kappa_values = {}
        
        for category in categories:
            expert_anomalous = apply_majority_voting(expert_evaluations_list, category, args.min_votes)
            expert_anomalous_by_category[category] = expert_anomalous
            
            kappa = compute_fleiss_kappa(expert_evaluations_list, category)
            kappa_values[category] = kappa
            
            if results[category]:
                evaluations = evaluate_all_k_values(results, expert_anomalous, category)
                dataset_results[category] = evaluations
                combined_results[category].append(evaluations)
                combined_kappas[category].append(kappa)
        
        # Print per-dataset results
        print_table(dataset_results, len(expert_evaluations_list), args.min_votes, kappa_values)
        
        if args.detailed:
            print_detailed_results(results, expert_evaluations_list, expert_anomalous_by_category, args.min_votes)
        
        datasets_processed += 1
    
    # Print combined (averaged) results if multiple datasets
    if datasets_processed > 1:
        print(f"\n\n{'#'*70}")
        print(f"COMBINED RESULTS (averaged across all datasets)")
        print(f"{'#'*70}")
        
        averaged_results = {}
        avg_kappas = {}
        for category in ["applications", "topics", "nodes", "libraries"]:
            if not combined_results[category]:
                continue
            
            # Average kappa across datasets
            valid_kappas = [k for k in combined_kappas[category] if k is not None]
            avg_kappas[category] = sum(valid_kappas) / len(valid_kappas) if valid_kappas else None
            
            # Average across datasets for each K
            k_values = [5, 10]
            avg_evaluations = []
            for ki, k in enumerate(k_values):
                precisions = []
                ndcgs = []
                for dataset_evals in combined_results[category]:
                    if ki < len(dataset_evals):
                        precisions.append(dataset_evals[ki]["precision"])
                        ndcgs.append(dataset_evals[ki]["ndcg"])
                
                if precisions:
                    avg_evaluations.append({
                        "k": k,
                        "precision": sum(precisions) / len(precisions),
                        "ndcg": sum(ndcgs) / len(ndcgs)
                    })
            
            if avg_evaluations:
                averaged_results[category] = avg_evaluations
        
        output_file = args.output if args.output else None
        print_table(averaged_results, datasets_processed, args.min_votes, avg_kappas, output_file)


if __name__ == "__main__":
    main()
