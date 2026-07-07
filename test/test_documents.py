"""文档上传/列表/删除接口测试。

覆盖:
    POST   /api/datasets/{id}/documents
    GET    /api/datasets/{id}/documents
    DELETE /api/datasets/{id}/documents/{filename}

注: 迁移到 LightRAG + RAG-Anything 后，文件按原样保存（不再做编码转换/文本抽取），
    故 extracted_chars 恒为 0，文件名也保持原样（大小写不归一化）。
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
        """GBK 编码文件应能正常上传（内容按原样保存，不做转换）。"""
        with open(sample_gbk, "rb") as f:
            r = requests.post(
                f"{api}/datasets/{dataset}/documents",
                files={"files": ("gbk_file.txt", f, "text/plain")},
            )
        assert r.status_code == 200
        assert r.json()["uploaded"] == 1

    def test_upload_utf16_txt(self, api, dataset, sample_utf16):
        """UTF-16 编码文件应能正常上传（内容按原样保存，不做转换）。"""
        with open(sample_utf16, "rb") as f:
            r = requests.post(
                f"{api}/datasets/{dataset}/documents",
                files={"files": ("utf16_file.txt", f, "text/plain")},
            )
        assert r.status_code == 200
        assert r.json()["uploaded"] == 1

    def test_upload_uppercase_extension(self, api, dataset, sample_txt):
        """大写扩展名 .TXT 应被接受（校验时忽略大小写），文件名按原样保存。"""
        with open(sample_txt, "rb") as f:
            r = requests.post(
                f"{api}/datasets/{dataset}/documents",
                files={"files": ("test_file.TXT", f, "text/plain")},
            )
        assert r.status_code == 200
        assert r.json()["documents"][0]["name"] == "test_file.TXT"

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
