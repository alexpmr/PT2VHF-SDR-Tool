"""Synthetic tests for privacy-safe native CDB stack summaries (no debugger)."""
from scripts.ci_native_stack_summary import summarize, main


def test_extracts_only_module_and_symbol_from_cdb_stack():
    raw = (
        "Access violation - code c0000005 (first chance)\n"
        "00 000000a1\x6080000000 00007fff\x6012345678 Qt6Widgets!QWidget::destroy+0x42\n"
        "01 000000a1\x6080000008 00007fff\x6012345679 python312!Py_Exit+0x9\n"
        "C:\\Users\\runneradmin\\private\\path\\secret.txt\n"
    )
    found, frames = summarize(raw)
    assert found is True
    assert frames == ["Qt6Widgets!QWidget::destroy", "python312!Py_Exit"]
    assert all("secret" not in frame and "00007" not in frame for frame in frames)


def test_missing_exception_does_not_count_as_success():
    found, frames = summarize("00 000000a1 00007fff ntdll!RtlExitUserProcess+0x12")
    assert not found
    assert frames == ["ntdll!RtlExitUserProcess"]


def test_caps_frame_count_and_rejects_invalid_limit():
    import pytest
    log = "ExceptionCode: c0000005 (Access violation)\n" + "\n".join(
        f"{i:02x} 000000a1 00007fff module!symbol{i}+0x1" for i in range(40)
    )
    assert len(summarize(log, limit=4)[1]) == 4
    with pytest.raises(ValueError):
        summarize(log, limit=0)


def test_main_does_not_echo_raw_log_or_private_paths(tmp_path, capsys):
    log = tmp_path / "crash.log"
    log.write_text("Access violation - code c0000005 (first chance)\n00 000000a1 00007fff module!function+0x1\n"
                   "C:\\private\\secret.txt\n", encoding="utf-8")
    assert main([str(log)]) == 0
    output = capsys.readouterr().out
    assert "CI-NATIVE-STACK frame=module!function" in output
    assert "private" not in output and "00007fff" not in output
    assert main([str(tmp_path / "absent.log")]) == 4
    assert "log-unavailable" in capsys.readouterr().out


def test_no_av_is_not_accepted(tmp_path, capsys):
    log = tmp_path / "clean.log"
    log.write_text("process exited with code 0", encoding="utf-8")
    assert main([str(log)]) == 2
    assert "not-observed" in capsys.readouterr().out


def test_debugger_configuration_is_not_native_crash_evidence():
    """CDB sxe command/standalone code must never satisfy the AV gate."""
    raw = (
        "0:000> sxe c0000005\\n"
        "c0000005\\n"
        "00 000000a1 00007fff ntdll!RtlExitUserProcess+0x12\\n"
    )
    found, frames = summarize(raw)
    assert found is False
    assert frames == ["ntdll!RtlExitUserProcess"]


def test_accepts_explicit_windows_exception_record_variants():
    for marker in (
        "Access violation - code c0000005 (first chance)",
        "ExceptionCode: c0000005 (Access violation)",
        "EXCEPTION_CODE: (NTSTATUS) 0xc0000005",
        "Exception code: 0xC0000005",
    ):
        found, frames = summarize(
            marker + "\\n"
            "00 000000a1 00007fff Qt6Core!QCoreApplication::sendPostedEvents+0x2f"
        )
        assert found is True
        assert frames == ["Qt6Core!QCoreApplication::sendPostedEvents"]


def test_negative_or_unrelated_exception_text_is_not_av():
    for log in (
        "No exception code c0000005 was observed",
        "EXCEPTION_CODE: 0xc0000409",
        "sxe c0000005",
    ):
        assert summarize(log)[0] is False
