#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Graph-based design quality analysis for
publish–subscribe microservice architectures.
"""

import json
from analyzer import Canalyzer, BasicStatistics


# -------------------------------------------------
# Dataset loading
# -------------------------------------------------

def load_dataset(path: str):
    """Load dataset.json."""
    with open(path, encoding="utf-8") as file:
        return json.load(file)


# -------------------------------------------------
# Main
# -------------------------------------------------

def main():
    """
    Main execution function.
    """
    data = load_dataset("dataset.json")

    # Perform complex analysis
    canalyzer = Canalyzer(data)
    canalyzer.run_analysis()
    result = canalyzer.get_json_results()
    report = canalyzer.generate_human_report()

    with open("analysis_report.txt", "w", encoding="utf-8") as f:
        f.write(report)

    with open("analysis_result.json", "w", encoding="utf-8") as file:
        json.dump(result, file, indent=2, ensure_ascii=False)

    print("✔ Karmaşık Analiz Tamamlandı")
    print(
        f"AY={len(result['AY'])}, GB={len(result['GB'])}, AK={len(result['AK'])}, "
        f"BM={len(result['BM'])}, MKon={len(result['MKon'])}, DTHN={len(result['DTHN'])}"
    )
    print("-" * 30)

    # Perform basic statistical analysis
    basic_stats = BasicStatistics(data)
    basic_report = basic_stats.generate_report()
    print(basic_report)


if __name__ == "__main__":
    main()

