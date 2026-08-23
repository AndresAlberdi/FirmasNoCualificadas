# Panel B2B · Folleto Forense

Prototipo del visualizador de evidencias que consumen los departamentos jurídicos y los
peritos informáticos de los clientes corporativos.

```bash
npm install
npm run dev        # http://localhost:5173
npm run build
npm run typecheck
```

## Estado

Prototipo funcional con **datos sintéticos** (`src/lib/mockData.ts`). Falta la
integración con `GET /v1/signing-sessions/{id}/evidence`, el flujo de autenticación
con Cognito (MFA obligatoria) y el explorador de transacciones.

## Reglas de diseño que el código implementa

1. **Enmascaramiento por defecto.** La cédula, la MRZ, el teléfono y las imágenes de
   identidad se muestran ocultas. La revelación exige una acción explícita.
2. **Auditoría de la revelación.** Cada `REVEAL_PII` y cada descarga emiten un evento
   que el backend persiste en `PSCNC_Dashboard_Audit_Log`.
3. **Descargas efímeras.** El panel nunca sirve binarios: solicita una URL pre-firmada
   de S3 con vigencia de 300 segundos.
4. **Semáforo biométrico.** Verde ≥ 95 %, ámbar 90–94,9 %, rojo < 90 %, conforme al
   umbral declarado en la DPSC.
5. **Banda de integridad.** Estado visible y permanente de la comparación entre el hash
   registrado y el documento resguardado.
6. **Sin almacenamiento local de datos personales.** No se usa `localStorage` ni
   `sessionStorage` para información del firmante.

## Pendientes

* Cliente HTTP con firma HMAC de las peticiones y manejo de expiración de sesión.
* Explorador de transacciones con filtros por cédula, rango de fechas y puntaje.
* Vista general con métricas operativas (firmas por día, latencia de la TSA, motivos de
  rechazo del onboarding).
* Pruebas de componentes y auditoría de accesibilidad WCAG 2.1 AA.
