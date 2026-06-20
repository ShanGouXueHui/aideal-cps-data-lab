from __future__ import annotations

from pathlib import Path


PATH = Path(__file__).resolve().parents[2] / "docs/DOCUMENT_AUTHORITY.md"


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"authority replacement precondition failed: {old[:60]!r}")
    return text.replace(old, new, 1)


def main() -> int:
    text = PATH.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "2. 绑定当前 main HEAD 的运行报告",
        "2. quality-reports 分支中绑定当前 main HEAD 的运行报告",
    )
    text = replace_once(
        text,
        "reports/project_engineering_audit_latest.json\nreports/offline_quality_latest.json",
        "quality-reports:reports/project_engineering_audit_latest.json\nquality-reports:reports/offline_quality_latest.json",
    )
    text = replace_once(
        text,
        "报告使用规则：\n\n- 检查 `generated_at`；\n- 检查 `git_head` 是否等于当前 main；",
        "报告使用规则：\n\n- 工程审计和 Offline Quality 必须从 `quality-reports` 分支读取；\n- main 中相同路径仅为权威指针，不是运行结果；\n- 检查 `generated_at`；\n- 检查 `git_head` 是否等于当前 main；",
    )
    text = replace_once(
        text,
        "- 最新已提交审计扫描 306 个文件，global/full gate blocker=210；\n- active/compatibility blocker=0，但全局门禁失败；\n- 最新已提交 Offline Quality 为 66 项 PASS、0 failure、0 error、`jd_live_called=false`；\n- 两份报告均只对各自 `git_head` 有效，必须在当前 main 上重跑；\n- 审计器尚未完整覆盖重复变量、模块常量、配置键和默认值多源；\n- 完成该能力并取得全局零 blocker 前，不得宣称代码问题 100% 解决。",
        "- PR #4 已验证 global/full 及全部 scope blocker=0；\n- 重复定义、赋值、常量、配置键、默认值多源和跨文件实现均为 0；\n- 大文件、长函数和 Python/Shell/config syntax blocker 均为 0；\n- Offline Quality 为 68 项 PASS、0 failure、0 error、`jd_live_called=false`；\n- 上述结果只有合并并在 main workflow 重跑后才构成正式 main 验收。",
    )
    text = replace_once(
        text,
        "audit git_head=current main\noffline git_head=current main",
        "audit report ref=quality-reports\noffline report ref=quality-reports\naudit git_head=current main\noffline git_head=current main",
    )
    text = replace_once(
        text,
        "- 当前 main 和绑定当前 HEAD 的报告优先于文档；",
        "- 当前 main 和 quality-reports 中绑定当前 HEAD 的报告优先于文档；",
    )
    PATH.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
