PYTHON = python
DATASET_DIR = datasets
RESULTS_DIR = results
EXPERTS_DIR = experts
TOP_K = 10
MIN_VOTES = 3

.PHONY: analyze compare compare-detailed compare-all clean-results clean-experts clean help

## Analiz çalıştır → results/ + experts/*/template.txt oluşturur
analyze:
	$(PYTHON) structural_analysis.py $(DATASET_DIR) -k $(TOP_K)

## Tek dataset karşılaştır (DATASET=hub_application)
compare:
	$(PYTHON) compare_expert.py $(RESULTS_DIR)/$(DATASET)_results.txt -e $(EXPERTS_DIR) -m $(MIN_VOTES)

## Tek dataset detaylı karşılaştır
compare-detailed:
	$(PYTHON) compare_expert.py $(RESULTS_DIR)/$(DATASET)_results.txt -e $(EXPERTS_DIR) -m $(MIN_VOTES) --detailed

## Tüm dataset'leri karşılaştır
compare-all:
	$(PYTHON) compare_expert.py $(RESULTS_DIR) -e $(EXPERTS_DIR) -m $(MIN_VOTES) --all

## Tüm dataset'leri detaylı karşılaştır
compare-all-detailed:
	$(PYTHON) compare_expert.py $(RESULTS_DIR) -e $(EXPERTS_DIR) -m $(MIN_VOTES) --all --detailed

## Sonuç dosyalarını sil
clean-results:
	rm -f $(RESULTS_DIR)/*_results.txt

## Uzman şablonlarını ve dataset klasörlerini sil
clean-experts:
	rm -rf $(EXPERTS_DIR)/*/

## Tüm üretilen dosyaları sil
clean: clean-results clean-experts

## Sıfırdan çalıştır: analiz + karşılaştır
all: analyze compare-all

help:
	@echo "Kullanım:"
	@echo "  make analyze                  Tüm dataset'leri analiz et"
	@echo "  make compare DATASET=hub_application   Tek dataset karşılaştır"
	@echo "  make compare-detailed DATASET=hub_application"
	@echo "  make compare-all              Tüm dataset'leri karşılaştır"
	@echo "  make compare-all-detailed     Tüm dataset'leri detaylı karşılaştır"
	@echo "  make clean                    Üretilen dosyaları sil"
	@echo "  make all                      Analiz + karşılaştır"
	@echo ""
	@echo "Parametreler:"
	@echo "  TOP_K=10       Kategori başına gösterilecek bileşen sayısı"
	@echo "  MIN_VOTES=3    Çoğunluk eşiği (varsayılan: 3/5)"
	@echo "  DATASET=...    Dataset adı (compare/compare-detailed için)"
