#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Expert Evaluation Comparison Tool

Compares system results with expert opinions and
computes Precision@K, Recall@K, F1@K, Jaccard, and Spearman correlation metrics.

Both expert opinions and system results use component NAMEs.
"""

import json
import argparse
from pathlib import Path

try:
    from scipy.stats import spearmanr
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


def load_json(path):
    """Load JSON file"""
    with open(path) as f:
        return json.load(f)


def parse_results_txt(path):
    """Parse result TXT file (name-based)"""
    with open(path) as f:
        content = f.read()
    
    results = {"apps": [], "topics": [], "nodes": [], "libs": []}
    
    # Support both Turkish (HAM) and English (RAW) headers
    if "RAW DATA" in content:
        ham = content.split("RAW DATA")[1]
    elif "HAM" in content:
        ham = content.split("HAM")[1]
    else:
        ham = content
    
    # Applications
    if "APPLICATIONS" in ham:
        section = ham.split("APPLICATIONS")[1].split("TOPICS")[0]
        for line in section.strip().split("\n")[2:]:
            parts = line.split()
            if len(parts) >= 2:
                # Name might contain spaces, Score is always second-to-last numeric
                # Format: name Score OS_P UNI WR RS CS SD
                # Find where numeric values start (Score column)
                for i, part in enumerate(parts):
                    try:
                        score = float(part)
                        name = " ".join(parts[:i])
                        results["apps"].append({
                            "name": name,
                            "score": score
                        })
                        break
                    except ValueError:
                        continue
    
    # Topics
    if "TOPICS" in ham:
        if "NODES" in ham.split("TOPICS")[1]:
            section = ham.split("TOPICS")[1].split("NODES")[0]
        else:
            section = ham.split("TOPICS")[1]
        for line in section.strip().split("\n")[2:]:
            parts = line.split()
            if len(parts) >= 2:
                for i, part in enumerate(parts):
                    try:
                        score = float(part)
                        name = " ".join(parts[:i])
                        results["topics"].append({
                            "name": name,
                            "score": score
                        })
                        break
                    except ValueError:
                        continue
    
    # Nodes
    if "NODES" in ham:
        if "LIBRARIES" in ham.split("NODES")[1]:
            section = ham.split("NODES")[1].split("LIBRARIES")[0]
        else:
            section = ham.split("NODES")[1]
        for line in section.strip().split("\n")[2:]:
            parts = line.split()
            if len(parts) >= 2:
                for i, part in enumerate(parts):
                    try:
                        score = float(part)
                        name = " ".join(parts[:i])
                        results["nodes"].append({
                            "name": name,
                            "score": score
                        })
                        break
                    except ValueError:
                        continue
    
    # Libraries
    if "LIBRARIES" in ham:
        section = ham.split("LIBRARIES")[1]
        for line in section.strip().split("\n")[2:]:
            parts = line.split()
            if len(parts) >= 2:
                for i, part in enumerate(parts):
                    try:
                        score = float(part)
                        name = " ".join(parts[:i])
                        results["libs"].append({
                            "name": name,
                            "score": score
                        })
                        break
                    except ValueError:
                        continue
    
    return results


def get_top_k(results, category, k):
    """Return top-k names sorted by score"""
    sorted_items = sorted(results[category], key=lambda x: x["score"], reverse=True)
    return [item["name"] for item in sorted_items[:k]]


def get_all_ranked(results, category):
    """Return all items sorted by score with their ranks"""
    sorted_items = sorted(results[category], key=lambda x: x["score"], reverse=True)
    return {item["name"]: rank + 1 for rank, item in enumerate(sorted_items)}


def compute_spearman(system_ranks, expert_names):
    """
    Compute Spearman rank correlation between system and expert rankings.
    
    Expert list is treated as a ranked list (first item = rank 1, etc.)
    Only items appearing in both lists are considered.
    """
    if not SCIPY_AVAILABLE:
        return {"spearman": None, "p_value": None, "note": "scipy not installed"}
    
    if not expert_names or len(expert_names) < 2:
        return {"spearman": None, "p_value": None, "note": "Need at least 2 expert items"}
    
    # Expert ranking: position in expert list (1-indexed)
    expert_ranks = {name: rank + 1 for rank, name in enumerate(expert_names)}
    
    # Find common items
    common_items = set(system_ranks.keys()) & set(expert_ranks.keys())
    
    if len(common_items) < 2:
        return {"spearman": None, "p_value": None, "note": f"Only {len(common_items)} common items"}
    
    # Build rank vectors for common items
    system_vector = [system_ranks[item] for item in common_items]
    expert_vector = [expert_ranks[item] for item in common_items]
    
    # Compute Spearman correlation
    correlation, p_value = spearmanr(system_vector, expert_vector)
    
    return {
        "spearman": correlation,
        "p_value": p_value,
        "n_common": len(common_items)
    }


def compute_metrics(system_names, expert_names):
    """Compute Precision, Recall, F1, Jaccard (name-based)"""
    if not expert_names:
        return {"precision": None, "recall": None, "f1": None, "jaccard": None, "note": "Expert list empty"}
    
    system_set = set(system_names)
    expert_set = set(expert_names)
    
    intersection = system_set & expert_set
    union = system_set | expert_set
    
    k = len(system_names)
    n_expert = len(expert_names)
    n_intersection = len(intersection)
    
    precision = n_intersection / k if k > 0 else 0
    recall = n_intersection / n_expert if n_expert > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    jaccard = n_intersection / len(union) if len(union) > 0 else 0
    
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "jaccard": jaccard,
        "intersection": sorted(intersection),
        "system_only": sorted(system_set - expert_set),
        "expert_only": sorted(expert_set - system_set)
    }


def evaluate_scenario(scenario_name, results_path, expert_data, k):
    """Evaluate all categories for a scenario"""
    results = parse_results_txt(results_path)
    
    evaluation = {
        "scenario": scenario_name,
        "k": k,
        "categories": {}
    }
    
    category_map = {
        "applications": "apps",
        "topics": "topics", 
        "nodes": "nodes",
        "libraries": "libs"
    }
    
    for expert_key, results_key in category_map.items():
        # Expert names directly from expert_opinions.json
        expert_names = expert_data.get(expert_key, [])
        
        # Get system top-k names
        system_names = get_top_k(results, results_key, k)
        
        # Get all system ranks for Spearman
        system_ranks = get_all_ranked(results, results_key)
        
        # Compute metrics (name-based)
        metrics = compute_metrics(system_names, expert_names)
        
        # Compute Spearman correlation
        spearman_result = compute_spearman(system_ranks, expert_names)
        metrics.update(spearman_result)
        
        # Add display info
        metrics["system_names"] = system_names
        metrics["expert_names"] = expert_names
        
        evaluation["categories"][expert_key] = metrics
    
    return evaluation


def print_evaluation(evaluation):
    """Print evaluation results"""
    print(f"\n{'='*75}")
    print(f"SCENARIO: {evaluation['scenario']} (K={evaluation['k']})")
    print(f"{'='*75}")
    
    for cat_name, metrics in evaluation["categories"].items():
        print(f"\n  [{cat_name.upper()}]")
        print(f"  System Top-{evaluation['k']}:")
        for i, name in enumerate(metrics['system_names']):
            print(f"    {i+1}. {name}")
        
        print(f"  Expert List:")
        for name in metrics['expert_names']:
            print(f"    • {name}")
        
        if metrics.get("precision") is not None:
            print(f"  ─────────────────────────────────────────────────")
            print(f"  Intersection: {metrics['intersection']}")
            print(f"  Precision:    {metrics['precision']:.2%} ({len(metrics['intersection'])}/{evaluation['k']})")
            print(f"  Recall:       {metrics['recall']:.2%} ({len(metrics['intersection'])}/{len(metrics['expert_names'])})")
            print(f"  F1:           {metrics['f1']:.2%}")
            print(f"  Jaccard:      {metrics['jaccard']:.2%}")
            
            # Spearman correlation
            if metrics.get("spearman") is not None:
                print(f"  Spearman ρ:   {metrics['spearman']:.3f} (p={metrics['p_value']:.4f}, n={metrics['n_common']})")
            elif metrics.get("note"):
                print(f"  Spearman ρ:   N/A ({metrics['note']})")
            
            if metrics["system_only"]:
                print(f"  System+:      {metrics['system_only']}")
                print(f"                (not in expert list)")
            if metrics["expert_only"]:
                print(f"  Expert+:      {metrics['expert_only']}")
                print(f"                (not in system top-k)")
        else:
            print(f"  {metrics.get('note', 'Evaluation failed')}")


def print_summary(all_evaluations):
    """Print overall summary table"""
    print(f"\n{'='*90}")
    print("OVERALL SUMMARY")
    print(f"{'='*90}")
    
    print(f"\n{'Scenario':<32} {'Category':<15} {'P@K':<8} {'R@K':<8} {'F1':<8} {'Jaccard':<8} {'Spearman':<10}")
    print("-" * 90)
    
    total_p, total_r, total_f1, total_j, total_s = 0, 0, 0, 0, 0
    count = 0
    spearman_count = 0
    
    for eval_result in all_evaluations:
        scenario = eval_result["scenario"][:30]
        for cat_name, metrics in eval_result["categories"].items():
            if metrics.get("precision") is not None:
                p = metrics["precision"]
                r = metrics["recall"]
                f1 = metrics["f1"]
                j = metrics["jaccard"]
                s = metrics.get("spearman")
                
                s_str = f"{s:.3f}" if s is not None else "N/A"
                print(f"{scenario:<32} {cat_name:<15} {p:<8.2%} {r:<8.2%} {f1:<8.2%} {j:<8.2%} {s_str:<10}")
                
                total_p += p
                total_r += r
                total_f1 += f1
                total_j += j
                if s is not None:
                    total_s += s
                    spearman_count += 1
                count += 1
                scenario = ""  # Don't show scenario name in subsequent rows
    
    if count > 0:
        print("-" * 90)
        avg_s_str = f"{total_s/spearman_count:.3f}" if spearman_count > 0 else "N/A"
        print(f"{'AVERAGE':<32} {'':<15} {total_p/count:<8.2%} {total_r/count:<8.2%} {total_f1/count:<8.2%} {total_j/count:<8.2%} {avg_s_str:<10}")
        
        print(f"\n{'='*90}")
        print("CONCLUSION")
        print(f"{'='*90}")
        avg_f1 = total_f1 / count
        if avg_f1 >= 0.7:
            print(f"  ✅ Average F1={avg_f1:.2%} - System has HIGH agreement with expert evaluation")
        elif avg_f1 >= 0.5:
            print(f"  ⚠️  Average F1={avg_f1:.2%} - System has MODERATE agreement with expert evaluation")
        else:
            print(f"  ❌ Average F1={avg_f1:.2%} - System has LOW agreement with expert evaluation")
        
        if spearman_count > 0:
            avg_s = total_s / spearman_count
            if avg_s >= 0.7:
                print(f"  ✅ Average Spearman ρ={avg_s:.3f} - Strong rank correlation with expert")
            elif avg_s >= 0.4:
                print(f"  ⚠️  Average Spearman ρ={avg_s:.3f} - Moderate rank correlation with expert")
            elif avg_s >= 0:
                print(f"  ❌ Average Spearman ρ={avg_s:.3f} - Weak rank correlation with expert")
            else:
                print(f"  ❌ Average Spearman ρ={avg_s:.3f} - Negative rank correlation with expert")


def main():
    parser = argparse.ArgumentParser(
        description="Compare system results with expert evaluations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  python compare_expert.py results/ -k 5
  python compare_expert.py results/ --expert datasets/expert_opinions.json -k 3
        """
    )
    parser.add_argument("results_dir", help="Directory containing result files")
    parser.add_argument("--expert", "-e", default="datasets/expert_opinions.json",
                        help="Expert opinions JSON file")
    parser.add_argument("-k", "--top", type=int, default=5,
                        help="Number of top-k to compare")
    
    args = parser.parse_args()
    
    results_dir = Path(args.results_dir)
    expert_opinions = load_json(args.expert)
    k = args.top
    
    print(f"Expert file: {args.expert}")
    print(f"Results directory: {results_dir}")
    print(f"Top-K: {k}")
    
    all_evaluations = []
    
    # Evaluate each scenario
    scenario_files = {
        "hub_application": ("hub_application.json", "hub_application_results.txt"),
        "single_backbone_topic": ("single_backbone_topic.json", "single_backbone_topic_results.txt"),
        "single_metric_outlier": ("single_metric_outlier.json", "single_metric_outlier_results.txt"),
        "context_diversity_comparison": ("context_diversity_comparison.json", "context_diversity_comparison_results.txt")
    }
    
    for scenario_name, (dataset_file, results_file) in scenario_files.items():
        results_path = results_dir / results_file
        
        if not results_path.exists():
            print(f"⚠ {results_file} not found, skipping...")
            continue
        
        if scenario_name not in expert_opinions:
            print(f"⚠ No expert opinion for {scenario_name}, skipping...")
            continue
        
        evaluation = evaluate_scenario(
            scenario_name, 
            results_path, 
            expert_opinions[scenario_name],
            k
        )
        all_evaluations.append(evaluation)
        print_evaluation(evaluation)
    
    # Overall summary
    if all_evaluations:
        print_summary(all_evaluations)


if __name__ == "__main__":
    main()
