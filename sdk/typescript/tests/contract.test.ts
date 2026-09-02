/**
 * Ejecuta la suite de contrato contra el cliente de referencia.
 *
 * El servicio se sustituye por un doble que implementa el contrato: estas
 * pruebas verifican **al integrador**, no al servicio. Que el servicio se
 * comporte como dice es lo que prueba la batería de Python; que el cliente
 * mande lo que debe y lea los rechazos como debe, se prueba acá.
 *
 * La distinción importa: un adaptador puede hablar con un servicio correcto y
 * aun así filtrar el código del OTP, olvidar la clave de idempotencia o leer el
 * mensaje de error en vez del motivo. Nada de eso lo detecta el servidor.
 */
import { beforeEach, describe, expect, it } from "vitest";
import { FncClient, TransportError } from "../src/client";
import { buildSampleRequest, runFncContractTests } from "../src/contract";
import type { ContractEnvironment } from "../src/contract";

interface PeticionRegistrada {
  ruta: string;
  cuerpo: string;
  cabeceras: Record<string, string>;
}

/**
 * Doble del servicio: implementa lo justo del contrato para que el cliente pueda
 * ejercitarse, incluida la idempotencia.
 */
function crearServicioFalso(registro: PeticionRegistrada[]): typeof globalThis.fetch {
  const transacciones = new Map<string, { confirmada: boolean; acta?: unknown }>();
  const idempotencia = new Map<string, { status: number; body: unknown }>();

  return (async (url: string | URL | Request, init?: RequestInit) => {
    const ruta = new URL(String(url)).pathname;
    const cuerpo = typeof init?.body === "string" ? init.body : "";
    const cabeceras = (init?.headers ?? {}) as Record<string, string>;

    registro.push({ ruta, cuerpo, cabeceras });

    const responder = (status: number, body: unknown): Response =>
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      });

    const clave = cabeceras["Idempotency-Key"];
    if (init?.method === "POST") {
      if (!clave) {
        return responder(400, {
          motivo: "IDEMPOTENCY_KEY_REQUIRED",
          mensaje: "Falta la cabecera Idempotency-Key.",
          reintentable: false,
        });
      }
      const guardada = idempotencia.get(`${ruta}:${clave}`);
      if (guardada) return responder(guardada.status, guardada.body);
    }

    // -------------------------------------------------- crear transacción --
    if (ruta === "/v1/transactions") {
      const peticion = JSON.parse(cuerpo);
      if (peticion.identity_decision?.approved !== true) {
        return responder(403, {
          motivo: "IDENTITY_NOT_APPROVED",
          mensaje: "El tenant declaró que la verificación no fue aprobada.",
          reintentable: false,
        });
      }
      const id = `tx-${transacciones.size + 1}`;
      transacciones.set(id, { confirmada: false });
      const body = {
        transaction_id: id,
        tenant_reference: peticion.tenant_reference,
        status: "CREATED",
        service_level: "1",
        jurisdiction: "PY",
        document_sha256: peticion.document.sha256,
        created_at: "2026-09-02T14:31:00Z",
        expires_at: "2026-09-02T15:31:00Z",
      };
      idempotencia.set(`${ruta}:${clave}`, { status: 201, body });
      return responder(201, body);
    }

    // ---------------------------------------------------------- confirmar --
    const confirm = ruta.match(/^\/v1\/transactions\/([^/]+)\/confirm$/);
    if (confirm) {
      const id = decodeURIComponent(confirm[1] ?? "");
      const transaccion = transacciones.get(id);
      if (!transaccion) {
        return responder(404, {
          motivo: "TRANSACTION_NOT_FOUND",
          mensaje: "No existe.",
          reintentable: false,
        });
      }
      if (transaccion.confirmada) {
        return responder(409, {
          motivo: "TRANSACTION_ALREADY_CONFIRMED",
          mensaje: "Ya confirmada.",
          reintentable: false,
        });
      }
      transaccion.confirmada = true;
      const body = {
        transaction_id: id,
        tenant_reference: "EXP-99887",
        status: "CONFIRMED",
        service_level: "1",
        confirmed_at: "2026-09-02T14:32:00Z",
        acta: {
          jws: "cabecera.payload.firma",
          payload_sha256: "b".repeat(64),
          key_alias: "alias/fnc/dev/segurolotengo/acta-seal/v1",
          algorithm: "ES256",
          jwks_url: "/.well-known/fnc-keys.json",
        },
        verification_code: "ABCDEFGH2345",
      };
      idempotencia.set(`${ruta}:${clave}`, { status: 200, body });
      return responder(200, body);
    }

    return responder(404, {
      motivo: "TRANSACTION_NOT_FOUND",
      mensaje: "Ruta desconocida.",
      reintentable: false,
    });
  }) as typeof globalThis.fetch;
}

function crearEntorno(): ContractEnvironment {
  const registro: PeticionRegistrada[] = [];
  const client = new FncClient({
    baseUrl: "https://api.fnc.invalid",
    tenantId: "segurolotengo",
    signer: {
      // El signer real usa HMAC-SHA256 con el secreto del tenant. Acá solo
      // interesa que el cliente lo invoque y adjunte el resultado.
      sign: async (metodo, ruta, timestamp) => `firma(${metodo} ${ruta} ${timestamp})`,
    },
    fetch: crearServicioFalso(registro),
    ahora: () => new Date("2026-09-02T14:31:00Z"),
  });

  return { client, sentRequests: () => registro };
}

// La suite completa del contrato, ejecutada contra el cliente de referencia.
runFncContractTests(crearEntorno);

describe("FncClient — comportamiento propio del cliente", () => {
  let registro: PeticionRegistrada[];

  beforeEach(() => {
    registro = [];
  });

  it("firma cada petición autenticada con las tres cabeceras", async () => {
    const client = new FncClient({
      baseUrl: "https://api.fnc.invalid",
      tenantId: "segurolotengo",
      signer: { sign: async () => "firma-de-prueba" },
      fetch: crearServicioFalso(registro),
      ahora: () => new Date("2026-09-02T14:31:00Z"),
    });

    await client.createTransaction(buildSampleRequest(), "k-firma");

    const cabeceras = registro[0]?.cabeceras ?? {};
    expect(cabeceras["X-PSCNC-Client"]).toBe("segurolotengo");
    expect(cabeceras["X-PSCNC-Signature"]).toBe("firma-de-prueba");
    expect(cabeceras["X-PSCNC-Timestamp"]).toBe("2026-09-02T14:31:00.000Z");
  });

  it("la verificación pública no lleva credenciales", async () => {
    const client = new FncClient({
      baseUrl: "https://api.fnc.invalid",
      tenantId: "segurolotengo",
      signer: {
        sign: async () => {
          throw new Error("no debe firmarse una llamada pública");
        },
      },
      fetch: (async () =>
        new Response(JSON.stringify({ verification_code: "X", exists: false }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })) as typeof globalThis.fetch,
    });

    const resultado = await client.verify("ABCDEFGH2345");

    expect(resultado.ok).toBe(true);
  });

  it("un fallo de red se distingue de un rechazo del contrato", async () => {
    // La distinción es la que decide si reintentar con la misma clave de
    // idempotencia tiene sentido: ante un fallo de red, sí.
    const client = new FncClient({
      baseUrl: "https://api.fnc.invalid",
      tenantId: "t",
      signer: { sign: async () => "f" },
      fetch: (async () => {
        throw new TypeError("conexión rechazada");
      }) as typeof globalThis.fetch,
    });

    await expect(
      client.createTransaction(buildSampleRequest(), "k-red"),
    ).rejects.toBeInstanceOf(TransportError);
  });

  it("una respuesta de error sin motivo no se hace pasar por un rechazo válido", async () => {
    const client = new FncClient({
      baseUrl: "https://api.fnc.invalid",
      tenantId: "t",
      signer: { sign: async () => "f" },
      fetch: (async () =>
        new Response(JSON.stringify({ detail: "algo salió mal" }), {
          status: 500,
        })) as typeof globalThis.fetch,
    });

    await expect(
      client.createTransaction(buildSampleRequest(), "k-sin-motivo"),
    ).rejects.toBeInstanceOf(TransportError);
  });

  it("normaliza la URL base con barra final", async () => {
    const client = new FncClient({
      baseUrl: "https://api.fnc.invalid/",
      tenantId: "t",
      signer: { sign: async () => "f" },
      fetch: crearServicioFalso(registro),
    });

    await client.createTransaction(buildSampleRequest(), "k-url");

    expect(registro[0]?.ruta).toBe("/v1/transactions");
  });
});
