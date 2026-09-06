# dudu-merchandise

Merchandise storefront for Eric's insect macro photography — prints and apparel.

## Local setup

```bash
conda activate ds
pip install -r requirements.txt -r requirements-dev.txt
python app.py
```

Runs at `http://127.0.0.1:5000`.

## Tests

```bash
pytest                             # unit tests
conda run -n ds python e2e/run.py  # e2e suite, against a running server
```
