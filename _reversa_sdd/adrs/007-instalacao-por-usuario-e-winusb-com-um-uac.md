# ADR 007: Instalacao por usuario e winusb com um uac

- **Status:** Aceito (retroativo)
- **Data/origem:** 2026-11-07 (v0.4.0)

## Contexto
Usuários domésticos não devem precisar de administrador para instalar o programa, mas o RTL-SDR no Windows exige o driver WinUSB.

## Decisão
Instalador Inno Setup por usuário (sem admin), seguindo o padrão PT2VHF. A troca de driver usa o `wdi-simple.exe` (libwdi, base do Zadig) embarcado, com uma única elevação UAC (`runas`).

## Evidência
🟢 `pt2vhf/sources/rtl_driver.py:4,104-125`; CHANGELOG 0.4.0; `packaging/installer.iss`.

## Consequências
Instalação simples; a elevação é pontual e explícita, mas a troca de driver é irreversível sem ação manual.
