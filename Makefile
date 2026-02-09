PYTHON = python
DATASET_DIR = datasets
RESULTS_DIR = results
EXPERTS_DIR = experts
TOP_K = 10
MIN_VOTES = 3

.PHONY: analyze compare compare-detailed compare-all clean-results clean-experts clean help

## Run analysis → generates results/ + experts/*/template.txt
analyze:
	$(PYTHON) structural_analysis.py $(DATASET_DIR) -k $(TOP_K)

## Compare single dataset (DATASET=hub_application)
compare:
	$(PYTHON) compare_expert.py $(RESULTS_DIR)/$(DATASET)_results.txt -e $(EXPERTS_DIR) -m $(MIN_VOTES)

## Compare single dataset with detailed output
compare-detailed:
	$(PYTHON) compare_expert.py $(RESULTS_DIR)/$(DATASET)_results.txt -e $(EXPERTS_DIR) -m $(MIN_VOTES) --detailed

## Compare all datasets
compare-all:
	$(PYTHON) compare_expert.py $(RESULTS_DIR) -e $(EXPERTS_DIR) -m $(MIN_VOTES) --all

## Compare all datasets with detailed output
compare-all-detailed:
	$(PYTHON) compare_expert.py $(RESULTS_DIR) -e $(EXPERTS_DIR) -m $(MIN_VOTES) --all --detailed

## Remove result files
clean-results:
	rm -f $(RESULTS_DIR)/*_results.txt

## Remove expert templates and dataset folders
clean-experts:
	rm -rf $(EXPERTS_DIR)/*/

## Remove all generated files
clean: clean-results clean-experts

## Run from scratch: analyze + compare
all: analyze compare-all

help:
	@echo "Usage:"
	@echo "  make analyze                  Analyze all datasets"
	@echo "  make compare DATASET=hub_application   Compare single dataset"
	@echo "  make compare-detailed DATASET=hub_application"
	@echo "  make compare-all              Compare all datasets"
	@echo "  make compare-all-detailed     Compare all datasets with detailed output"
	@echo "  make clean                    Remove generated files"
	@echo "  make all                      Analyze + compare"
	@echo ""
	@echo "Parameters:"
	@echo "  TOP_K=10       Number of components per category"
	@echo "  MIN_VOTES=3    Majority threshold (default: 3/5)"
	@echo "  DATASET=...    Dataset name (for compare/compare-detailed)"
