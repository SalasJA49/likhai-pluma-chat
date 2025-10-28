from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient


class EDATopNTest(TestCase):
	def setUp(self):
		self.client = APIClient()

	def test_top_n_purchases_per_customer(self):
		# Minimal sample matching the screenshot columns
		data = {
			"data": [
				{"date": "2024-01-01", "category": "Electronic", "product": "P0", "sales": 1000, "quantity": 10, "region": "North", "customer": "C1"},
				{"date": "2024-01-02", "category": "Clothing",   "product": "P1", "sales": 500,  "quantity": 5,  "region": "South", "customer": "C1"},
				{"date": "2024-01-03", "category": "Food",       "product": "P2", "sales": 900,  "quantity": 9,  "region": "East",  "customer": "C2"},
				{"date": "2024-01-04", "category": "Books",      "product": "P3", "sales": 200,  "quantity": 2,  "region": "West",  "customer": "C3"},
				{"date": "2024-01-05", "category": "Electronic", "product": "P4", "sales": 300,  "quantity": 3,  "region": "North", "customer": "C2"},
			],
			"prompt": "calculate total purchases per customer, show top 2",
		}
		url = reverse("api:eda-process") if False else "/api/eda/process/"
		res = self.client.post(url, data, format="json")
		self.assertEqual(res.status_code, 200)
		body = res.json()
		# Tables present
		self.assertIn("tables", body)
		self.assertIn("top_n", body["tables"])  # type: ignore
		top = body["tables"]["top_n"]  # type: ignore
		self.assertEqual(len(top.get("rows", [])), 2)
		# Charts include at least bar and pie
		charts = body.get("charts", {}).get("charts", [])
		types = {c.get("type") for c in charts}
		self.assertTrue({"bar", "pie"}.issubset(types))
