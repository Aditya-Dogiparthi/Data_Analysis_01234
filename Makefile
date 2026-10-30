.PHONY: install profile pipeline test dashboard notebook
install:
	python -m pip install -r requirements.txt
profile:
	python scripts/profile_data.py
pipeline:
	python scripts/run_pipeline.py
test:
	pytest -q
dashboard:
	streamlit run app/dashboard.py
notebook:
	jupyter notebook notebooks/07_end_to_end_investigation.ipynb
