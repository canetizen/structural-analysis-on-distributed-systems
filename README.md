# Structural Analysis of Publish–Subscribe Architectures

This repository contains the **research prototype and synthetic datasets**
used to **experimentally validate the metric formulation and combined scoring
model** proposed in the following academic study:

> **Yayınla–Abone Ol Tabanlı Dağıtık Sistemlerde Yapısal Etkileşim  
> Örüntülerinin Çizge Tabanlı Statik Analiz ile İncelenmesi**  
> *A Graph-Based Static Analysis of Structural Interaction Patterns  
> in Publish–Subscribe Based Distributed Systems*  
>  
> UYMS 2026 (under review / submitted)

**Important:**  
This repository does **not** implement static analysis or CodeQL extraction.
It assumes that architectural relationships are already available as input.

---

## Purpose

The goal of this repository is to **evaluate and stress-test the proposed
structural metric definitions and combined anomaly scoring model** under
different architectural scenarios.

Specifically, it aims to:

- apply the **formal metric definitions** presented in the paper,
- evaluate **rule-based structural patterns** derived from relative metric behavior,
- compute the **combined anomaly score** used for prioritization,
- analyze what types of architectural situations are captured or missed
  by the scoring model.

The analysis is intentionally limited to **relative ranking**, not defect
detection or classification.

---

## Scope and Assumptions

- Input data represents an **already-extracted architectural graph**
  (applications, topics, nodes, libraries).
- No source code parsing, static analysis, or runtime data is involved.
- All thresholds are **system-relative** (quartile-based).
- Results are meaningful only **within the same system context**.

---

## Methodology Overview

The implementation directly follows the **formulation layer** of the paper:

1. **Structural Metrics**
   - Metrics are computed at application, topic, node, and library levels
   - Definitions correspond exactly to the mathematical formulations

2. **Relative Interpretation**
   - Metrics are interpreted using system-wide distributions (Q1 / Q3)
   - No absolute thresholds are used

3. **Rule-Based Structural Patterns**
   - Multiple metrics are combined into interpretable architectural patterns
   - Single-metric dominance is explicitly avoided

4. **Combined Anomaly Score**
   - Pattern-based anomaly score
   - Limited single-metric contribution
   - Used solely for **relative prioritization**

---

## Datasets

The `datasets/` directory contains **small synthetic architectural graphs**
designed to simulate different structural scenarios discussed in the paper
(e.g., dominant hubs, communication backbones, node-level concentration,
single-metric outliers).

These datasets are **illustrative**, not realistic production systems.

---

## Running the Analysis

### Requirements
- Python **3.9**
- `pandas`