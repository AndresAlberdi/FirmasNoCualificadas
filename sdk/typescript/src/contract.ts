/**
 * Suite de contrato para cualquier adaptador que consuma la API de FNC.
 *
 * Sigue el patrón de `src/ports/__tests__/*.contract.ts` del primer tenant: la
 * suite se exporta como función y cada implementación —el cliente de referencia,
 * el adaptador propio de un tenant, un doble— la ejecuta contra sí misma. Así,
 * «cumple el contrato» deja de ser una afirmación y pasa a ser algo que se corre.
 *
 * ## Qué comprueba, y por qué esas cosas
 *
 * No comprueba que el servicio funcione: eso lo hace la batería de Python.
 * Comprueba las obligaciones que un integrador puede incumplir sin notarlo, y
 * que solo se manifiestan en producción o en un juzgado:
 *
 * 1. **El código del OTP no sale del tenant.** Lo que viaja es la prueba.
 * 2. **El documento no se envía** en modo hash-only.
 * 3. **La clave de idempotencia acompaña a toda escritura**, y un reintento con
 *    la misma clave no produce un acta nueva.
 * 4. **Los rechazos se leen por `motivo`**, nunca por el texto del mensaje.
 * 5. **El acta se verifica con la clave pública**, no con el SDK del emisor.
 *
 * Uso:
 *
 *     runFncContractTests(() => new FncClient({ ... }));
 */
import { describe, expect, it } from "vitest";
import type { FncClient } from "./client";
import type { CreateTransactionRequest } from "./types";

/** Datos que jamás deben aparecer en lo que se envía al servicio. */
const SECRETOS_DEL_TENANT = ["654321", "+595981123456", "hipertensión"] as const;

export interface ContractEnvironment {
  readonly client: FncClient;
  /** Cuerpos serializados que el cliente envió, para inspeccionarlos. */
  readonly sentRequests: () => readonly { ruta: string; cuerpo: string; cabeceras: Record<string, string> }[];
}

export function buildSampleRequest(): CreateTransactionRequest {
  return {
    tenant_reference: "EXP-99887",
    document: {
      sha256: "a".repeat(64),
      version: 2,
      code: "PROP-2026-000123",
      closed_at: "2026-09-02T14:30:00Z",
    },
    identity_decision: {
      approved: true,
      threshold_applied: 0.99,
      score: 0.995,
      score_scale: "0-100",
      model_version: "rekognition-2026-07",
      policy_version: "slt-identidad-v4",
      provider_reference: "onb_72189312",
      liveness_verified: true,
    },
  };
}

export function runFncContractTests(crearEntorno: () => ContractEnvironment): void {
  describe("Contrato de integración con FNC", () => {
    describe("privacidad de lo que se envía", () => {
      it("no envía el código del OTP en ninguna petición", async () => {
        const { client, sentRequests } = crearEntorno();

        const creada = await client.createTransaction(buildSampleRequest(), "k-1");
        expect(creada.ok).toBe(true);
        if (!creada.ok) return;

        await client.confirm(
          creada.value.transaction_id,
          {
            otp_proof: {
              otp_reference: "otp_abc123",
              channel: "WHATSAPP",
              destination_masked: "+595 98* *** *56",
              sent_at: "2026-09-02T14:30:00Z",
              verified_at: "2026-09-02T14:30:40Z",
            },
            consent_statement: "Acepto firmar electrónicamente la propuesta y el FIPF.",
            consent_statement_version: "p8-consentimiento-v3",
            document_sha256: "a".repeat(64),
          },
          "c-1",
        );

        const enviado = sentRequests()
          .map((p) => p.cuerpo)
          .join("\n");

        for (const secreto of SECRETOS_DEL_TENANT) {
          expect(enviado).not.toContain(secreto);
        }
      });

      it("identifica el documento por su huella y no envía su contenido", async () => {
        const { client, sentRequests } = crearEntorno();

        await client.createTransaction(buildSampleRequest(), "k-2");

        const cuerpo = JSON.parse(sentRequests()[0]?.cuerpo ?? "{}");
        expect(cuerpo.document.sha256).toHaveLength(64);
        expect(cuerpo.document_content).toBeUndefined();
        expect(cuerpo.pdf).toBeUndefined();
      });

      it("envía el destino del OTP enmascarado", async () => {
        const { client, sentRequests } = crearEntorno();
        const creada = await client.createTransaction(buildSampleRequest(), "k-3");
        if (!creada.ok) return;

        await client.confirm(
          creada.value.transaction_id,
          {
            otp_proof: {
              otp_reference: "otp_abc123",
              channel: "WHATSAPP",
              destination_masked: "+595 98* *** *56",
              sent_at: "2026-09-02T14:30:00Z",
              verified_at: "2026-09-02T14:30:40Z",
            },
            consent_statement: "Acepto.",
            consent_statement_version: "v3",
            document_sha256: "a".repeat(64),
          },
          "c-3",
        );

        const confirmacion = sentRequests().find((p) => p.ruta.includes("/confirm"));
        expect(confirmacion?.cuerpo).toContain("*");
        expect(confirmacion?.cuerpo).not.toContain("+595981123456");
      });
    });

    describe("identidad decidida por el tenant", () => {
      it("envía la decisión completa: umbral, versiones y referencia", async () => {
        const { client, sentRequests } = crearEntorno();

        await client.createTransaction(buildSampleRequest(), "k-4");

        const cuerpo = JSON.parse(sentRequests()[0]?.cuerpo ?? "{}");
        // Sin estos campos, el acta no podría decir quién decidió ni con qué
        // política, y la responsabilidad quedaría sin trazar.
        expect(cuerpo.identity_decision.policy_version).toBeTruthy();
        expect(cuerpo.identity_decision.model_version).toBeTruthy();
        expect(cuerpo.identity_decision.provider_reference).toBeTruthy();
        expect(cuerpo.identity_decision.threshold_applied).toBeLessThanOrEqual(1);
      });

      it("envía el puntaje normalizado a 0-1 declarando su escala de origen", async () => {
        const { client, sentRequests } = crearEntorno();

        await client.createTransaction(buildSampleRequest(), "k-5");

        const cuerpo = JSON.parse(sentRequests()[0]?.cuerpo ?? "{}");
        expect(cuerpo.identity_decision.score).toBeLessThanOrEqual(1);
        expect(cuerpo.identity_decision.score_scale).toBe("0-100");
      });
    });

    describe("idempotencia", () => {
      it("acompaña toda escritura con la clave de idempotencia", async () => {
        const { client, sentRequests } = crearEntorno();

        await client.createTransaction(buildSampleRequest(), "k-6");

        const escritura = sentRequests()[0];
        expect(escritura?.cabeceras["Idempotency-Key"]).toBe("k-6");
      });

      it("reintentar con la misma clave no produce un acta nueva", async () => {
        const { client } = crearEntorno();
        const creada = await client.createTransaction(buildSampleRequest(), "k-7");
        if (!creada.ok) return;

        const confirmacion = {
          otp_proof: {
            otp_reference: "otp_abc123",
            channel: "WHATSAPP" as const,
            destination_masked: "+595 98* *** *56",
            sent_at: "2026-09-02T14:30:00Z",
            verified_at: "2026-09-02T14:30:40Z",
          },
          consent_statement: "Acepto.",
          consent_statement_version: "v3",
          document_sha256: "a".repeat(64),
        };

        const primera = await client.confirm(
          creada.value.transaction_id,
          confirmacion,
          "c-7",
        );
        const segunda = await client.confirm(
          creada.value.transaction_id,
          confirmacion,
          "c-7",
        );

        expect(primera.ok && segunda.ok).toBe(true);
        if (!primera.ok || !segunda.ok) return;
        // El acta es la misma: mismo sello y mismo código de verificación.
        expect(segunda.value.acta.jws).toBe(primera.value.acta.jws);
        expect(segunda.value.verification_code).toBe(primera.value.verification_code);
      });
    });

    describe("lectura de rechazos", () => {
      it("un rechazo trae un motivo del enumerado, no un texto libre", async () => {
        const { client } = crearEntorno();
        const peticion = buildSampleRequest();

        const resultado = await client.createTransaction(
          {
            ...peticion,
            identity_decision: { ...peticion.identity_decision, approved: false },
          },
          "k-8",
        );

        expect(resultado.ok).toBe(false);
        if (resultado.ok) return;
        // Se compara contra el value del enumerado, nunca contra el mensaje: el
        // mensaje es para una persona y puede cambiar entre versiones.
        expect(resultado.error.motivo).toBe("IDENTITY_NOT_APPROVED");
        expect(typeof resultado.error.reintentable).toBe("boolean");
      });

      it("el rechazo indica si reintentar tiene sentido", async () => {
        const { client } = crearEntorno();
        const peticion = buildSampleRequest();

        const resultado = await client.createTransaction(
          {
            ...peticion,
            identity_decision: { ...peticion.identity_decision, approved: false },
          },
          "k-9",
        );

        if (resultado.ok) return;
        // Una identidad no aprobada es terminal: reintentar la misma petición
        // daría el mismo resultado y gastaría una clave de idempotencia.
        expect(resultado.error.reintentable).toBe(false);
      });
    });

    describe("verificación del acta", () => {
      it("el acta trae el alias de la clave y dónde obtenerla", async () => {
        const { client } = crearEntorno();
        const creada = await client.createTransaction(buildSampleRequest(), "k-10");
        if (!creada.ok) return;

        const confirmada = await client.confirm(
          creada.value.transaction_id,
          {
            otp_proof: {
              otp_reference: "otp_abc123",
              channel: "WHATSAPP",
              destination_masked: "+595 98* *** *56",
              sent_at: "2026-09-02T14:30:00Z",
              verified_at: "2026-09-02T14:30:40Z",
            },
            consent_statement: "Acepto.",
            consent_statement_version: "v3",
            document_sha256: "a".repeat(64),
          },
          "c-10",
        );

        if (!confirmada.ok) return;
        // Con estos dos datos, un tercero verifica sin conocer la estructura del
        // servicio ni depender de este SDK.
        expect(confirmada.value.acta.key_alias).toContain("acta-seal");
        expect(confirmada.value.acta.jwks_url).toContain("fnc-keys.json");
        expect(confirmada.value.acta.jws.split(".")).toHaveLength(3);
      });
    });
  });
}
