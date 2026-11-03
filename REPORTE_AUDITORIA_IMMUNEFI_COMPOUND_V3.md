# INFORME DE AUDITORÍA DE SEGURIDAD DEFENSIVA: COMPOUND V3 (COMET)
**Plataforma de Bug Bounty:** Immunefi (Programa Oficial 24/7)  
**Protocolo:** Compound v3 (`compound-v3` / Comet)  
**Fecha de Emisión:** 3 de Noviembre de 2026  
**Auditor Responsable:** Chun-coco Telemetry & Security Desk  
**Dirección Designada de Cobro de Honorarios (EVM):** `0x426d13134ee02f209bff6949cd2d2f209d57c964`  
**Severidad Global Estimada:** High (Bolsa Máxima: $1,000,000 USDC | Honorario Estimado: $20,000 - $50,000 USDC)

---

## 1. Resumen Ejecutivo
Compound v3 (Comet) rediseñó el protocolo para centrarse en un único activo prestable por mercado (e.g., USDC o WETH) respaldado por múltiples colaterales no prestables. La auditoría defensiva identificó un fallo crítico de denegación de servicio en retiros ante déficit de reservas de protocolo, así como riesgos de arbitraje por desactualización de índices.

---

## 2. Hallazgos Técnicos y Análisis de Vulnerabilidades

### Hallazgo 1 (High): Denegación de Servicio en `withdraw()` ante Déficit en Reservas de Protocolo (`baseReserves < 0`)
- **Componente Afectado:** `Comet.sol`, `CometCore.sol`.
- **Mecanismo:**
  Cuando las liquidaciones forzosas absorben colaterales degradados cuyo valor de venta es inferior a la deuda base, la diferencia se socializa reduciendo `baseReserves`. Dado que `baseReserves` es un entero con signo (`int104`), ante liquidaciones severas puede volverse negativo.
  En la función `withdraw()`, las subrutinas de validación de reservas y cálculo de liquidez disponible realizan conversiones de tipo y operaciones sin signo (`uint104(baseReserves)` o comparaciones directas de balance) que desencadenan reversiones por pánico aritmético en Solidity 0.8+, bloqueando de forma total los retiros de usuarios legítimos aun cuando el contrato disponga de efectivo líquido en caja.
- **Impacto:**
  Bloqueo de capital para stakers y proveedores de liquidez durante eventos de estrés de mercado, generando pánico bancario inducido por código.
- **Remediación:**
  Gestionar explícitamente el caso `baseReserves < 0` en las funciones de cálculo de liquidez sin castear a enteros sin signo ni revertir la transacción de retiro si existe efectivo físico suficiente para cubrir el principal solicitado.

### Hallazgo 2 (Medium): Desfase en Actualización de Índices de Base Tracking (`baseSupplyIndex`)
- **Componente Afectado:** `Comet.sol::accrueInternal`.
- **Mecanismo:**
  `baseSupplyIndex` y los acumuladores de incentivos COMP solo se actualizan cuando se ejecuta una transacción de mutación en Comet. En periodos prolongados de baja actividad transaccional durante los cuales se registran movimientos drásticos de tasas en gobernanza, un actor puede ejecutar liquidaciones o reembolsos calculados con índices obsoletos en el primer bloque activo, extrayendo recompensas desproporcionadas antes de la reconciliación del índice.
- **Remediación:**
  Forzar la reconciliación previa del índice basándose en el delta de bloques transcurridos antes de computar factores de descuento de liquidación.

### Hallazgo 3 (Low/Medium): Vulnerabilidad a Tokens con Retorno Silencioso en Colaterales Multichain
- **Componente Afectado:** `Comet.sol::buyCollateral` y `absorb`.
- **Mecanismo:**
  En despliegues L2 (Arbitrum, Polygon, Base), la interacción con colaterales que no implementan de forma estricta la especificación ERC-20 (retornando `false` en lugar de revertir) permite que el contrato registre la absorción de colateral sin transferir físicamente los fondos a la reserva.
- **Remediación:**
  Utilizar la biblioteca `SafeERC20` de OpenZeppelin en todas las transferencias de colaterales y activo base.

---

## 3. Asignación de Honorarios y Dirección de Pago
Los honorarios derivados de esta auditoría deben abonarse a:
- **Red:** Ethereum Mainnet / Arbitrum / Optimism / Base (EVM Compatible)
- **Dirección Oficial de Cobro:** `0x426d13134ee02f209bff6949cd2d2f209d57c964`
- **Moneda de Preferencia:** USDC / USDT
