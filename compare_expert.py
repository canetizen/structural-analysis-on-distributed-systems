#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Expert Evaluation Comparison Tool

Compares system results with expert opinions and
computes Precision@K, Recall@K, F1@K, Jaccard metrics.

Experts input component NAMEs, system converts to IDs.
Both formats are shown in output.
"""

import json
import argparse
from pathlib import Path


def load_json(path):
    """Load JSON file"""
    with open(path) as f:
        return json.load(f)


def build_name_id_maps(dataset):
    """Build name↔id mappings from dataset"""
    maps = {
        "applications": {"name_to_id": {}, "id_to_name": {}},
        "topics": {"name_to_id": {}, "id_to_name": {}},
        "nodes": {"name_to_id": {}, "id_to_name": {}},
    }
    
    for category in ["applications", "topics", "nodes"]:
        for item in dataset.get(category, []):
            item_id = item["id"]
            item_name = item.get("name", item_id)
            maps[category]["name_to_id"][item_name] = item_id
            maps[category]["id_to_name"][item_id] = item_name
    
    return maps


def names_to_ids(names, name_to_id_map):
    """Convert name list to ID list"""
    ids = []
    for name in names:
        if name in name_to_id_map:
            ids.append(name_to_id_map[name])
        else:
            print(f"  ⚠ Warning: '{name}' not found, skipping...")
    return ids


def ids_to_names(ids, id_to_name_map):
    """Convert ID list to name list"""
    return [id_to_name_map.get(item_id, item_id) for item_id in ids]


def parse_results_txt(path):
    """Parse result TXT file"""
    with open(path) as f:
        content = f.read()
    
    results = {"apps": [], "topics": [], "nodes": []}
    
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
                results["apps"].append({
                    "id": parts[0],
                    "score": float(parts[1])
                })
    
    # Topics
    if "TOPICS" in ham:
        section = ham.split("TOPICS")[1].split("NODES")[0]
        for line in section.strip().split("\n")[2:]:
            parts = line.split()
            if len(parts) >= 2:
                results["topics"].append({
                    "id": parts[0],
                    "score": float(parts[1])
                })
    
    # Nodes
    if "NODES" in ham:
        section = ham.split("NODES")[1]
        for line in section.strip().split("\n")[2:]:
            parts = line.split()
            if len(parts) >= 2:
                results["nodes"].append({
                    "id": parts[0],
                    "score": float(parts[1])
                })
    
    return results


def get_top_k(results, category, k):
    """Return top-k IDs sorted by score"""
    sorted_items = sorted(results[category], key=lambda x: x["score"], reverse=True)
    return [item["id"] for item in sorted_items[:k]]


def compute_metrics(system_ids, expert_ids):
    """Compute Precision, Recall, F1, Jaccard (ID-based)"""
    if not expert_ids:
        return {"precision": None, "recall": None, "f1": None, "jaccard": None, "note": "Expert list empty"}
    
    system_set = set(system_ids)
    expert_set = set(expert_ids)
    
    intersection = system_set & expert_set
    union = system_set | expert_set
    
    k = len(system_ids)
    n_expert = len(expert_ids)
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
        "intersection_ids": sorted(intersection),
        "system_only_ids": sorted(system_set - expert_set),
        "expert_only_ids": sorted(expert_set - system_set)
    }


def evaluate_scenario(scenario_name, results_path, expert_data, dataset, k):
    """Evaluate all categories for a scenario"""
    results = parse_results_txt(results_path)
    maps = build_name_id_maps(dataset)
    
    evaluation = {
        "scenario": scenario_name,
        "k": k,
        "categories": {}
    }
    
    category_map = {
        "applications": "apps",
        "topics": "topics", 
        "nodes": "nodes"
    }
    
    for expert_key, results_key in category_map.items():
        # Convert expert names to IDs
        expert_names = expert_data.get(expert_key, [])
        expert_ids = names_to_ids(expert_names, maps[expert_key]["name_to_id"])
        
        # Get system top-k IDs
        system_ids = get_top_k(results, results_key, k)
        
        # Compute metrics (ID-based)
        metrics = compute_metrics(system_ids, expert_ids)
        
        # Convert to names (for display)
        id_to_name = maps[expert_key]["id_to_name"]
        metrics["system_names"] = ids_to_names(system_ids, id_to_name)
        metrics["expert_names"] = expert_names
        metrics["intersection_names"] = ids_to_names(metrics["intersection_ids"], id_to_name)
        metrics["system_only_names"] = ids_to_names(metrics["system_only_ids"], id_to_name)
        metrics["expert_only_names"] = ids_to_names(metrics["expert_only_ids"], id_to_name)
        
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
            print(f"  Intersection: {metrics['intersection_names']}")
            print(f"  Precision:    {metrics['precision']:.2%} ({len(metrics['intersection_ids'])}/{evaluation['k']})")
            print(f"  Recall:       {metrics['recall']:.2%} ({len(metrics['intersection_ids'])}/{len(metrics['expert_names'])})")
            print(f"  F1:           {metrics['f1']:.2%}")
            print(f"  Jaccard:      {metrics['jaccard']:.2%}")
            
            if metrics["system_only_names"]:
                print(f"  System+:      {metrics['system_only_names']}")
                print(f"                (not in expert list)")
            if metrics["expert_only_names"]:
                print(f"  Expert+:      {metrics['expert_only_names']}")
                print(f"                (not in system top-k)")
        else:
            print(f"  {metrics.get('note', 'Evaluation failed')}")


def print_summary(all_evaluations):
    """Print overall summary table"""
    print(f"\n{'='*75}")
    print("OVERALL SUMMARY")
    print(f"{'='*75}")
    
    print(f"\n{'Scenario':<32} {'Category':<15} {'P@K':<8} {'R@K':<8} {'F1':<8} {'Jaccard':<8}")
    print("-" * 79)
    
    total_p, total_r, total_f1, total_j = 0, 0, 0, 0
    count = 0
    
    for eval_result in all_evaluations:
        scenario = eval_result["scenario"][:30]
        for cat_name, metrics in eval_result["categories"].items():
            if metrics.get("precision") is not None:
                p = metrics["precision"]
                r = metrics["recall"]
                f1 = metrics["f1"]
                j = metrics["jaccard"]
                print(f"{scenario:<32} {cat_name:<15} {p:<8.2%} {r:<8.2%} {f1:<8.2%} {j:<8.2%}")
                total_p += p
                total_r += r
                total_f1 += f1
                total_j += j
                count += 1
                scenario = ""  # Don't show scenario name in subsequent rows
    
    if count > 0:
        print("-" * 79)
        print(f"{'AVERAGE':<32} {'':<15} {total_p/count:<8.2%} {total_r/count:<8.2%} {total_f1/count:<8.2%} {total_j/count:<8.2%}")
        
        print(f"\n{'='*75}")
        print("CONCLUSION")
        print(f"{'='*75}")
        avg_f1 = total_f1 / count
        if avg_f1 >= 0.7:
            print(f"  ✅ Average F1={avg_f1:.2%} - System has HIGH agreement with expert evaluation")
        elif avg_f1 >= 0.5:
            print(f"  ⚠️  Average F1={avg_f1:.2%} - System has MODERATE agreement with expert evaluation")
        else:
            print(f"  ❌ Average F1={avg_f1:.2%} - System has LOW agreement with expert evaluation")


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
    parser.add_argument("--datasets", "-d", default="datasets",
                        help="Directory containing dataset files")
    parser.add_argument("-k", "--top", type=int, default=5,
                        help="Number of top-k to compare")
    
    args = parser.parse_args()
    
    results_dir = Path(args.results_dir)
    datasets_dir = Path(args.datasets)
    expert_opinions = load_json(args.expert)
    k = args.top
    
    print(f"Expert file: {args.expert}")
    print(f"Dataset directory: {datasets_dir}")
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
        dataset_path = datasets_dir / dataset_file
        results_path = results_dir / results_file
        
        if not results_path.exists():
            print(f"⚠ {results_file} not found, skipping...")
            continue
        
        if not dataset_path.exists():
            print(f"⚠ {dataset_file} not found, skipping...")
            continue
        
        if scenario_name not in expert_opinions:
            print(f"⚠ No expert opinion for {scenario_name}, skipping...")
            continue
        
        dataset = load_json(dataset_path)
        
        evaluation = evaluate_scenario(
            scenario_name, 
            results_path, 
            expert_opinions[scenario_name],
            dataset,
            k
        )
        all_evaluations.append(evaluation)
        print_evaluation(evaluation)
    
    # Overall summary
    if all_evaluations:
        print_summary(all_evaluations)


if __name__ == "__main__":
    main()
