"""probe 单元测试：结构、序列化、能力级别计算（不要求二进制存在）。"""

from __future__ import annotations

from pdf_toolbox.engine.probe import (
    SPEC,
    Dependency,
    capability_level,
    find_binary,
    probe_all,
)


class TestFindBinary:
    def test_windows_gs_alias(self, monkeypatch):
        import pdf_toolbox.engine.probe as probe_mod

        def fake_which(name):
            return {"gswin64c": r"C:\Program Files\gs\gswin64c.exe"}.get(name)

        monkeypatch.setattr(probe_mod.shutil, "which", fake_which)
        # Windows 上 ghostscript 叫 gswin64c——按候选名应能找到
        assert find_binary("gs") == r"C:\Program Files\gs\gswin64c.exe"
        assert find_binary("qpdf") is None

    def test_plain_name(self):
        # 非 Windows 上 gs 就是 gs
        assert find_binary("definitely_missing_xyz") is None


class TestProbe:
    def test_spec_levels(self):
        # L0 qpdf / L1 poppler / L2 tesseract / L3 gs —— 与 PLAN §5 分级一致
        by_name = {name: level for name, (level, _, _) in SPEC.items()}
        assert by_name == {"qpdf": 0, "pdfinfo": 1, "tesseract": 2, "gs": 3}

    def test_probe_all_structure(self):
        deps = probe_all()
        assert len(deps) == 4
        for dep in deps:
            assert isinstance(dep, Dependency)
            assert dep.found is True or dep.install  # 缺失时必须给安装命令
            d = dep.as_dict()
            assert set(d) == {"name", "level", "found", "version", "install", "error"}

    def test_capability_level_bounds(self):
        level = capability_level()
        assert -1 <= level <= 3
