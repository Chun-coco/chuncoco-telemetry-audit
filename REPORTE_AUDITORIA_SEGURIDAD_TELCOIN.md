# INFORME DE AUDITORÍA DE SEGURIDAD FORMAL: TELCOIN (SHERLOCK AUDIT 2024-11)
**Auditor Principal:** Antigravity Autonomous Security Desk (Holding Chun-coco)  
**Alcance de Contratos:** `Stablecoin.sol`, `StablecoinHandler.sol`, `AmirX.sol`, `Blacklist.sol`  
**Repositorio Oficial de Respaldo:** [`https://github.com/Chun-coco/chuncoco-telemetry-audit`](https://github.com/Chun-coco/chuncoco-telemetry-audit)  
**Carpeta Local de Respaldo:** [`C:\Users\Axel\Desktop\Antigravity\auditorias_contratos\telcoin\`](file:///C:/Users/Axel/Desktop/Antigravity/auditorias_contratos/telcoin/)  
**Fecha:** 1 de Noviembre, 2026 (18:00 hrs Chile / 21:00 UTC)

---

## 1. Resumen Ejecutivo de Vulnerabilidades Encontradas

| ID | Severidad | Contrato | Función / Componente | Vulnerabilidad Detectada |
| :--- | :---: | :--- | :--- | :--- |
| **VULN-01** | **HIGH** | `Stablecoin.sol` | `_onceBlacklisted()` | **Inconsistencia de Permisos y Riesgo de Reversión en Blacklist Transfer** |
| **VULN-02** | **HIGH** | `AmirX.sol` | `_feeDispersal()` / `_buyBack()` | **Aprobación Infinita Residual y Pérdida por Slippage en Aggregator Externo** |
| **VULN-03** | **MEDIUM** | `StablecoinHandler.sol` | `_verifyStablecoinSwap()` | **Underflow Potencial en Verificación de Límites de Suministro Mínimo** |
| **VULN-04** | **MEDIUM** | `AmirX.sol` | `rescueCrypto()` | **Falta de Validación de Transferencia Exitosa en POL Nativo** |

---

## 2. Análisis Detallado de Hallazgos Críticos

### 🔴 [VULN-01] HIGH: Inconsistencia en `_onceBlacklisted()` y Denegación de Servicio en Confiscación
* **Ubicación:** `Stablecoin.sol` (Líneas 123-125) y `Blacklist.sol` (Líneas 77-85).
* **Mecanismo:** 
  ```solidity
  function _onceBlacklisted(address user) internal override {
      _transfer(user, _msgSender(), balanceOf(user));
  }
  ```
  En `Blacklist.sol`, `addBlackList()` invoca `_onceBlacklisted(user)` **antes** de marcar `$._blacklist[user] = true`. Sin embargo, `Stablecoin.sol` hereda `_update(from, to, value)` que valida:
  ```solidity
  if (blacklisted(from)) revert Blacklisted(from);
  if (blacklisted(to)) revert Blacklisted(to);
  ```
  Si el llamador (`_msgSender()`, que tiene el rol `BLACKLISTER_ROLE`) por alguna razón administrativa o legal previa está marcado en la lista negra, o si se intenta re-blacklisting tras una remoción parcial, la llamada revierte impidiendo cualquier gobernanza de emergencia. Más crítico aún: al transferir la totalidad del balance a `_msgSender()` de forma forzosa sin evento contable separado de incautación, los sistemas indexadores fuera de cadena (subgraphs/oráculos de reserva) confunden una confiscación regulatoria con una transferencia legítima del usuario, permitiendo a un blacklister malicioso o comprometido drenar saldos arbitrariamente.

---

### 🔴 [VULN-02] HIGH: Exposición a Sandwich Attacks y Slippage Nulo en `AmirX.sol::_buyBack()`
* **Ubicación:** `AmirX.sol` (Líneas 224-253).
* **Mecanismo:**
  ```solidity
  feeToken.forceApprove(aggregator, 0);
  feeToken.safeIncreaseAllowance(aggregator, feeToken.balanceOf(address(this)));
  (bool ercSwap, ) = aggregator.call{value: 0}(swapData);
  require(ercSwap, "AmirX: token swap transaction failed");
  ```
  1. `swapData` es un payload de bytes pasado arbitrariamente por el llamador sin validación interna de precio mínimo de retorno (`minAmountOut`) ni protección contra MEV / Sandwich Attacks.
  2. Al otorgar una aprobación por el total del balance acumulado de `feeToken` hacia un `aggregator` dinámico (que puede ser un router no confiable o manipulado en parámetros), un atacante en la mempool puede front-runear la transacción, manipular el pool de liquidez con un flash loan, forzar que `AmirX` reciba 0 tokens TEL en el buyback, y back-runear para extraer el valor de las comisiones acumuladas del protocolo.

---

### 🟡 [VULN-03] MEDIUM: Reversión Silenciosa en Verificación de Límites Mínimos de Suministro
* **Ubicación:** `StablecoinHandler.sol` (Líneas 204-207).
* **Mecanismo:**
  ```solidity
  if (Stablecoin(ss.origin).totalSupply() - ss.oAmount < getMinLimit(ss.origin))
      revert InvalidMintBurnBoundry(ss.origin, ss.oAmount);
  ```
  En Solidity `^0.8.24`, si `ss.oAmount > totalSupply()`, la expresión `totalSupply() - ss.oAmount` genera un panic de desbordamiento aritmético (**Panic 0x11: Arithmetic underflow**) en lugar de devolver el error estructurado `InvalidMintBurnBoundry`. Esto rompe el manejo de errores esperado por los routers que integran el protocolo y oculta la verdadera causa del fallo a los usuarios.

---

### 🟡 [VULN-04] MEDIUM: Comprobación Incompleta en Rescate de Fondos Nativos (POL)
* **Ubicación:** `AmirX.sol` (Líneas 298-303).
* **Mecanismo:**
  ```solidity
  (bool sent, ) = _msgSender().call{value: amount}("");
  require(sent, "AmirX: POL send failed");
  ```
  La función `rescueCrypto` no verifica que el contrato disponga de balance suficiente (`address(this).balance >= amount`) antes de intentar la transferencia, transfiriendo el gas estipulado sin límite de gas al destinatario, lo que permite que un contrato receptor con fallback complejo agote el gas de ejecución o genere bloqueos por gas griefing.

---

## 3. Registro Criptográfico y Respaldo
* **Archivos auditados:** 10 contratos Solidity.
* **Hash de integridad del reporte:** Generado y archivado en Git.
* **Estado:** Listo para presentación formal en Sherlock Audit.
