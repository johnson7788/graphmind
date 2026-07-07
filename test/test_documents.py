"""文档上传/列表/删除接口测试，以及编码转换单元测试。

覆盖:
    POST   /api/datasets/{id}/documents
    GET    /api/datasets/{id}/documents
    DELETE /api/datasets/{id}/documents/{filename}
    单元测试: document_service._decode_to_utf8
"""

from __future__ import annotations

import pytest
import requests


class TestDocuments:
    @pytest.fixture
    def dataset(self, api):
        """为文档测试创建一个临时数据集，用完即删。"""
        r = requests.post(f"{api}/datasets", json={"name": "test_docs"})
        ds_id = r.json()["id"]
        yield ds_id
        requests.delete(f"{api}/datasets/{ds_id}")

    def test_upload_utf8_txt(self, api, dataset, sample_txt):
        with open(sample_txt, "rb") as f:
            r = requests.post(
                f"{api}/datasets/{dataset}/documents",
                files={"files": ("sample.txt", f, "text/plain")},
            )
        assert r.status_code == 200
        assert r.json()["uploaded"] == 1

    def test_upload_gbk_txt(self, api, dataset, sample_gbk):
        """GBK 编码文件上传后应转换为 UTF-8。"""
        with open(sample_gbk, "rb") as f:
            r = requests.post(
                f"{api}/datasets/{dataset}/documents",
                files={"files": ("gbk_file.txt", f, "text/plain")},
            )
        assert r.status_code == 200
        data = r.json()
        assert data["uploaded"] == 1
        assert data["documents"][0]["extracted_chars"] > 0

    def test_upload_utf16_txt(self, api, dataset, sample_utf16):
        """UTF-16 编码文件上传后应转换为 UTF-8。"""
        with open(sample_utf16, "rb") as f:
            r = requests.post(
                f"{api}/datasets/{dataset}/documents",
                files={"files": ("utf16_file.txt", f, "text/plain")},
            )
        assert r.status_code == 200
        data = r.json()
        assert data["uploaded"] == 1
        assert data["documents"][0]["extracted_chars"] > 0

    def test_upload_uppercase_extension(self, api, dataset, sample_txt):
        """.TXT 扩展名应被归一化为 .txt。"""
        with open(sample_txt, "rb") as f:
            r = requests.post(
                f"{api}/datasets/{dataset}/documents",
                files={"files": ("test_file.TXT", f, "text/plain")},
            )
        assert r.status_code == 200
        assert r.json()["documents"][0]["name"] == "test_file.txt"

    def test_upload_unsupported_type(self, api, dataset, tmp_path):
        """不支持的文件类型应被拒绝（400）。"""
        p = tmp_path / "test.exe"
        p.write_bytes(b"\x00\x01\x02")
        with open(p, "rb") as f:
            r = requests.post(
                f"{api}/datasets/{dataset}/documents",
                files={"files": ("test.exe", f, "application/octet-stream")},
            )
        assert r.status_code == 400

    def test_list_documents(self, api, dataset, sample_txt):
        with open(sample_txt, "rb") as f:
            requests.post(
                f"{api}/datasets/{dataset}/documents",
                files={"files": ("sample.txt", f, "text/plain")},
            )
        r = requests.get(f"{api}/datasets/{dataset}/documents")
        assert r.status_code == 200
        assert len(r.json()["documents"]) == 1

    def test_delete_document(self, api, dataset, sample_txt):
        with open(sample_txt, "rb") as f:
            requests.post(
                f"{api}/datasets/{dataset}/documents",
                files={"files": ("sample.txt", f, "text/plain")},
            )
        r = requests.delete(f"{api}/datasets/{dataset}/documents/sample.txt")
        assert r.status_code == 200

        r = requests.get(f"{api}/datasets/{dataset}/documents")
        assert len(r.json()["documents"]) == 0


class TestEncoding:
    """直接测试 _decode_to_utf8 辅助函数（不依赖后端）。"""

    def test_utf8(self):
        from app.services.document_service import _decode_to_utf8
        assert _decode_to_utf8("你好世界".encode("utf-8"), "test.txt") == "你好世界"

    def test_utf8_bom(self):
        from app.services.document_service import _decode_to_utf8
        assert _decode_to_utf8("你好世界".encode("utf-8-sig"), "test.txt") == "你好世界"

    def test_utf16_le(self):
        from app.services.document_service import _decode_to_utf8
        assert "你好世界" in _decode_to_utf8("你好世界".encode("utf-16"), "test.txt")

    def test_gbk(self):
        from app.services.document_service import _decode_to_utf8
        assert _decode_to_utf8("你好世界".encode("gbk"), "test.txt") == "你好世界"

    def test_gb2312(self):
        from app.services.document_service import _decode_to_utf8
        assert _decode_to_utf8("人工智能".encode("gb2312"), "test.txt") == "人工智能"
