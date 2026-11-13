PYTHON ?= /usr/bin/python3

.PHONY: test sources mosaic
test:
	$(PYTHON) Lidar-pipeline/verify.py
	$(PYTHON) -m unittest discover -s tests -v
sources:
	$(PYTHON) download_sources.py
	$(PYTHON) prepare_sources.py
mosaic:
	$(PYTHON) mosaic_dem.py
