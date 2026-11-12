"""Executor de pytest para CI PySide6: encerra sem finalizadores nativos do Qt.

pytest.main() já executou as funções de teste, fixtures, teardown e reportou
seu código de retorno antes da chamada a os._exit. A saída por os._exit evita
a dupla destruição de objetos Qt/C++ na saída do intérprete (em Windows e
Ubuntu), conhecida por gerar status 1 ou segfault 139 depois de "N passed".

Isto NÃO mascara falhas: o status retornado por pytest.main é preservado
integralmente. Se o processo morrer DURANTE os testes, o executor não chega
a os._exit, e o runner informa o erro nativo.
"""
import os
import sys


def main():
    import pytest
    probe = None
    if os.environ.get("PT2VHF_CI_NATIVE_LIFECYCLE") == "1":
        from ci_native_lifecycle import report as probe
        probe("before-pytest")
    result = pytest.main(["-q", *sys.argv[1:]])
    if probe is not None:
        probe("after-pytest")
    if os.environ.get("PT2VHF_CI_QT_DISPOSE_AFTER_PYTEST") == "1":
        # Opt-in diagnostic only; never used by regular CI or release.
        from ci_native_lifecycle import dispose_qt_top_levels
        dispose_qt_top_levels()
        if probe is not None:
            probe("after-qt-disposal")
    sys.stdout.flush()
    sys.stderr.flush()
    # Diagnostic-only alternative: compare ordinary Python/Qt shutdown with
    # the legacy hard exit on Windows. Never enable for release builds.
    exit_mode = os.environ.get("PT2VHF_TEST_EXIT_MODE", "hard")
    if exit_mode == "normal":
        return int(result)
    if exit_mode != "hard":
        raise ValueError("PT2VHF_TEST_EXIT_MODE must be 'hard' or 'normal'")
    # Experimental CI timing probe only: determine whether native background
    # activity at pytest shutdown is time-sensitive. Default remains zero.
    delay_raw = os.environ.get("PT2VHF_TEST_EXIT_DELAY_MS", "0")
    if delay_raw not in {"0", "250", "1000", "2000"}:
        raise ValueError("PT2VHF_TEST_EXIT_DELAY_MS must be 0, 250, 1000 or 2000")
    if delay_raw != "0":
        import time
        time.sleep(int(delay_raw) / 1000)
        sys.stdout.flush()
        sys.stderr.flush()
    if probe is not None:
        probe("before-hard-exit")
    os._exit(int(result))


if __name__ == "__main__":
    raise SystemExit(main())
