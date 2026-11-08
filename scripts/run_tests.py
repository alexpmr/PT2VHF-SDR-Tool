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
    result = pytest.main(["-q"])
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(int(result))


if __name__ == "__main__":
    main()
