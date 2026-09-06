"""Golden-path smoke checks. Extend with real specs as routes/flows are built."""

from _common import BASE_URL, browser_page


def test_index_loads():
    with browser_page() as page:
        resp = page.goto("/")
        assert resp.status == 200


def test_health_endpoint():
    with browser_page() as page:
        resp = page.request.get(f"{BASE_URL}/_health")
        assert resp.status == 200
        assert resp.json() == {"status": "ok"}


TESTS = [test_index_loads, test_health_endpoint]

if __name__ == "__main__":
    for t in TESTS:
        t()
        print(f"PASS {t.__name__}")
