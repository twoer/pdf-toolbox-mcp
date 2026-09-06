"""结构化错误体系：MCP 层序列化为 {"ok": False, "error": ...}，agent 可直接路由。"""

from __future__ import annotations


class ToolboxError(Exception):
    """引擎错误基类。子类通过 as_dict() 输出结构化负载。"""

    error_code = "tool_error"

    def as_dict(self) -> dict:
        return {"ok": False, "error": self.error_code, "message": str(self)}


class MissingDependencyError(ToolboxError):
    """系统工具缺失（L0–L3）。install 为各平台安装命令。"""

    error_code = "missing_dependency"

    def __init__(
        self,
        binary: str,
        level: int,
        install: dict[str, str],
        unlocks: tuple[str, ...] = (),
    ):
        self.binary = binary
        self.level = level
        self.install = install
        self.unlocks = unlocks
        unlocked = f"；安装后可用: {', '.join(unlocks)}" if unlocks else ""
        super().__init__(f"缺少系统依赖 {binary}（L{level}）{unlocked}")

    def as_dict(self) -> dict:
        return {
            "ok": False,
            "error": self.error_code,
            "binary": self.binary,
            "level": self.level,
            "install": self.install,
            "unlocks": list(self.unlocks),
            "message": str(self),
        }


class EncryptedPdfError(ToolboxError):
    """文件已加密——引导先 unlock_pdf（差异化刚需的路由入口）。"""

    error_code = "encrypted_pdf"

    def __init__(self, path: str, hint: str = "先用 unlock_pdf 解锁（user 打开密码即可）"):
        super().__init__(f"文件已加密: {path}；{hint}")


class WrongPasswordError(ToolboxError):
    error_code = "wrong_password"
