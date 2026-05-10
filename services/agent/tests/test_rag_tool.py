from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.tools.shared.rag import _build_source_summary, build_rag_search_tool


class RagToolTests(unittest.IsolatedAsyncioTestCase):
    def test_build_source_summary_counts_sources(self) -> None:
        summary = _build_source_summary(
            [
                {
                    "collection": "global_tax",
                    "score": 0.84,
                    "metadata": {"document_id": "tax-doc-1"},
                },
                {
                    "collection": "user_company-1",
                    "score": 0.92,
                    "metadata": {"source": "upload-7"},
                },
            ],
            include_user_documents=True,
        )

        self.assertEqual(summary["retrieved_count"], 2)
        self.assertEqual(summary["collections"]["global_tax"], 1)
        self.assertEqual(summary["collections"]["user_company-1"], 1)
        self.assertEqual(summary["documents"]["tax-doc-1"], 1)
        self.assertEqual(summary["documents"]["upload-7"], 1)
        self.assertEqual(summary["top_score"], 0.92)
        self.assertTrue(summary["user_documents_requested"])
        self.assertTrue(summary["user_documents_included"])

    async def test_rag_tool_prepends_source_summary(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/retrieve")
            payload = json.loads(request.content.decode("utf-8"))
            self.assertTrue(payload["include_user_documents"])
            return httpx.Response(
                status_code=200,
                json={
                    "chunks": [
                        {
                            "collection": "global_tax",
                            "score": 0.88,
                            "metadata": {"filename": "tax.md", "document_id": "tax-doc-1"},
                            "text": "Tax clause text",
                        },
                        {
                            "collection": "user_company-1",
                            "score": 0.93,
                            "metadata": {"source": "upload-42"},
                            "text": "Company policy text",
                        },
                    ]
                },
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://knowledge") as knowledge_http:
            tool = build_rag_search_tool(
                "user-1",
                "company-1",
                SimpleNamespace(knowledge_http=knowledge_http),
            )
            result = await tool.ainvoke({"query": "Explain VAT"})

        summary_line, _sep, remainder = result.partition("\n\n")
        self.assertTrue(summary_line.startswith("RAG source summary: "))
        summary_json = summary_line.removeprefix("RAG source summary: ")
        summary = json.loads(summary_json)
        self.assertEqual(summary["retrieved_count"], 2)
        self.assertIn("global_tax", summary["collections"])
        self.assertIn("user_company-1", summary["collections"])
        self.assertIn("[1] collection=global_tax", remainder)
        self.assertIn("[2] collection=user_company-1", remainder)

    async def test_rag_tool_keeps_anti_loop_behavior(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                status_code=200,
                json={"chunks": [{"collection": "global_tax", "score": 0.8, "metadata": {}, "text": "A"}]},
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://knowledge") as knowledge_http:
            tool = build_rag_search_tool(
                "user-1",
                "company-1",
                SimpleNamespace(knowledge_http=knowledge_http),
            )
            _first = await tool.ainvoke({"query": "same question"})
            second = await tool.ainvoke({"query": "same question"})

        self.assertIn("RAG search skipped", second)


if __name__ == "__main__":
    unittest.main()
