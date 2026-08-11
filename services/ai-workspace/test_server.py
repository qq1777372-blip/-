import base64
import gc
import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

import server


class WorkspaceApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        server.DB = Path(cls.temp.name) / "test.db"
        server.FILES = Path(cls.temp.name) / "files"
        cls.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}/api/"
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.thread.join(timeout=5)
        cls.httpd.server_close()
        gc.collect()
        cls.temp.cleanup()

    def request(self, path, payload=None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(self.base + path, data=data, headers={"Content-Type": "application/json", "X-Workspace-User": "local", "X-Workspace-Role": "superadmin"}, method="POST" if data is not None else "GET")
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_workspace_crud_and_retrieval(self):
        self.assertTrue(self.request("status")["online"])

        self.request("config", {"base_url": "https://example.invalid/v1", "model": "test-model", "api_key": "secret"})
        preserved = self.request("config", {"model": "test-model-2", "api_key": ""})
        self.assertTrue(preserved["has_key"])
        self.assertEqual(preserved["model"], "test-model-2")

        knowledge_id = self.request("knowledge", {"name": "运营规则"})["id"]
        skill_id = self.request("skills", {"name": "审校", "content": "回答前检查事实。"})["id"]
        model_id = self.request("models", {"name": "运营助手", "base_model": "test-model", "temperature": 0.4, "skill_ids": [skill_id]})["id"]
        self.request("models/update", {"id": model_id, "name": "高级运营助手", "base_model": "test-model-2", "temperature": 0.8, "top_p": 0.7, "max_tokens": 3000, "knowledge_id": knowledge_id, "skill_ids": [skill_id], "tool_ids": ["builtin-calculator"]})
        model = next(item for item in self.request("models")["models"] if item["id"] == model_id)
        self.assertEqual(model["name"], "高级运营助手")
        self.assertEqual(model["max_tokens"], 3000)

        raw = ("店铺日常检查内容。" * 160 + "银河检索目标片段。" + "售后规则。" * 160).encode("utf-8")
        uploaded = self.request("documents/import-file", {"filename": "rules.txt", "data": base64.b64encode(raw).decode("ascii")})["file"]
        self.request("files/assign", {"file_id": uploaded["id"], "knowledge_id": knowledge_id})
        matches = self.request("search", {"query": "银河检索目标", "knowledge_id": knowledge_id})["documents"]
        self.assertTrue(matches)
        self.assertIn("银河检索目标片段", matches[0]["content"])
        self.assertTrue(self.request("search", {"query": "售后", "knowledge_id": knowledge_id})["documents"])

        self.request("chats/save", {"id": "chat-1", "user_id": "user-1", "title": "测试会话", "messages": [{"role": "user", "content": "你好"}]})
        self.assertEqual(len(self.request("chats?user_id=user-1")["chats"]), 1)
        self.request("chats/delete", {"id": "chat-1", "user_id": "user-1"})
        self.assertEqual(len(self.request("chats?user_id=user-1")["chats"]), 0)

        self.request("files/delete", {"id": uploaded["id"]})
        self.assertFalse(server.FILES.joinpath(f"{uploaded['id']}-rules.txt").exists())
        self.request("models/delete", {"id": model_id})
        self.request("skills/delete", {"id": skill_id})
        self.request("knowledge/delete", {"id": knowledge_id})

    def test_builtin_calculator(self):
        result = server.calculate_expression("请计算 12+8 和 10/4")
        self.assertIn("12+8 = 20", result)
        self.assertIn("10/4 = 2.5", result)

    def test_standard_tool_specs_and_execution(self):
        connection = server.db()
        try:
            specs, tools = server.tool_specs(connection, ["builtin-calculator", "builtin-time"])
            self.assertEqual(len(specs), 2)
            calculator_name = next(item["function"]["name"] for item in specs if "expression" in item["function"]["parameters"]["properties"])
            self.assertIn("3*7 = 21", server.execute_tool(tools[calculator_name], {"expression": "3*7"}))
        finally:
            connection.close()

    def test_sync_provider_models(self):
        self.request("config", {"base_url": "https://provider.invalid/v1", "api_key": "secret"})
        with patch.object(server, "fetch_provider_model_ids", return_value=["model-a", "model-b"]):
            first = self.request("models/sync", {})
            second = self.request("models/sync", {})
        self.assertEqual(first, {"ok": True, "total": 2, "added": 2})
        self.assertEqual(second["added"], 0)
        models = self.request("models")["models"]
        self.assertEqual({item["base_model"] for item in models}, {"model-a", "model-b"})

    def test_document_generation(self):
        docx, _ = server.generate_document("Test", "hello\nworld", "docx")
        xlsx, _ = server.generate_document("Test", "name\tvalue\na\t1", "xlsx")
        pdf, _ = server.generate_document("测试", "中文内容", "pdf")
        self.assertTrue(docx.startswith(b"PK"))
        self.assertTrue(xlsx.startswith(b"PK"))
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_memory_workflow_and_usage_foundations(self):
        memory_id = self.request("memories", {"content": "用户偏好简洁回答"})["id"]
        self.assertEqual(self.request("memories")["memories"][0]["id"], memory_id)
        workflow_id = self.request("workflows", {"name": "计算流程", "steps": [{"type": "tool", "tool_id": "builtin-calculator", "arguments": {"expression": "6*7"}}]})["id"]
        self.assertEqual(self.request("workflows")["workflows"][0]["id"], workflow_id)
        job_id = self.request("workflows/run", {"id": workflow_id, "input": ""})["job_id"]
        for _ in range(20):
            job = next(item for item in self.request("jobs")["jobs"] if item["id"] == job_id)
            if job["status"] in ("completed", "failed"): break
            threading.Event().wait(0.05)
        self.assertEqual(job["status"], "completed")
        self.assertIn("42", job["output"])
        usage = self.request("usage")
        self.assertIn("summary", usage)
        self.request("memories/delete", {"id": memory_id})
        self.request("workflows/delete", {"id": workflow_id})


if __name__ == "__main__":
    unittest.main()
