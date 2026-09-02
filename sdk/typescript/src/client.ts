/**
 * Cliente de referencia del contrato público v1.
 *
 * Implementa la firma HMAC de la petición, la idempotencia y el mapeo de errores
 * a `Result`. Un tenant puede usarlo tal cual o tomarlo como especificación
 * ejecutable de su propio adaptador.
 *
 * ## Lo que este client NO hace, a propósito
 *
 * - **No reintenta solo.** Un reintento sin la misma clave de idempotencia
 *   produce un acta nueva para el mismo acto de firma; con ella, es seguro. La
 *   decisión de reintentar es del llamador, que es quien sabe si la clave sigue
 *   siendo la misma operación.
 * - **No guarda ni acepta el código del OTP.** El contrato recibe la prueba, no
 *   el secreto.
 * - **No verifica el acta.** Verificar con el SDK del emisor demuestra
 *   consistencia, no autenticidad: use una librería JOSE con la clave pública de
 *   `/.well-known/fnc-keys.json`.
 */
import type {
  Artifacts,
  ConfirmTransactionRequest,
  PublicVerification,
  CreateTransactionRequest,
  ErrorResponse,
  Result,
  TransactionConfirmed,
  TransactionCreated,
} from "./types";

export const HEADER_CLIENT = "X-PSCNC-Client";
export const HEADER_TIMESTAMP = "X-PSCNC-Timestamp";
export const HEADER_SIGNATURE = "X-PSCNC-Signature";
export const HEADER_IDEMPOTENCY = "Idempotency-Key";

/** Firma criptográfica de la petición. Inyectable para poder probar el client. */
export interface RequestSigner {
  /**
   * HMAC-SHA256 hexadecimal de la cadena canónica
   * `MÉTODO\nruta\ntimestamp\nsha256(cuerpo)`.
   */
  sign(metodo: string, ruta: string, timestamp: string, cuerpo: string): Promise<string>;
}

export interface ClientOptions {
  readonly baseUrl: string;
  readonly tenantId: string;
  readonly signer: RequestSigner;
  /** Inyectable para pruebas; por defecto el `fetch` del entorno. */
  readonly fetch?: typeof globalThis.fetch;
  /** Inyectable para pruebas deterministas. */
  readonly ahora?: () => Date;
}

/** Error de transporte: la petición no llegó a producir una respuesta del contrato. */
export class TransportError extends Error {
  constructor(
    message: string,
    readonly causa?: unknown,
  ) {
    super(message);
    this.name = "TransportError";
  }
}

export class FncClient {
  private readonly baseUrl: string;
  private readonly tenantId: string;
  private readonly signer: RequestSigner;
  private readonly fetchImpl: typeof globalThis.fetch;
  private readonly ahora: () => Date;

  constructor(opciones: ClientOptions) {
    // Sin la barra final, `new URL(ruta, base)` descarta el último segmento.
    this.baseUrl = opciones.baseUrl.replace(/\/+$/, "");
    this.tenantId = opciones.tenantId;
    this.signer = opciones.signer;
    this.fetchImpl = opciones.fetch ?? globalThis.fetch;
    this.ahora = opciones.ahora ?? (() => new Date());
  }

  /**
   * Abre una transacción de firma.
   *
   * `idempotencyKey` es obligatoria: sin ella el servicio rechaza la petición,
   * porque un reintento produciría una transacción nueva para el mismo acto.
   */
  async createTransaction(
    peticion: CreateTransactionRequest,
    idempotencyKey: string,
  ): Promise<Result<TransactionCreated>> {
    return this.escribir<TransactionCreated>("/v1/transactions", peticion, idempotencyKey);
  }

  /**
   * Confirma el acto y obtiene el acta sellada.
   *
   * Repetir la llamada con la misma clave devuelve **el acta original**, no una
   * nueva: es lo que hace seguro el reintento tras un tiempo de espera agotado.
   */
  async confirm(
    transactionId: string,
    peticion: ConfirmTransactionRequest,
    idempotencyKey: string,
  ): Promise<Result<TransactionConfirmed>> {
    return this.escribir<TransactionConfirmed>(
      `/v1/transactions/${encodeURIComponent(transactionId)}/confirm`,
      peticion,
      idempotencyKey,
    );
  }

  /** Recupera el acta y el código de verificación de una transacción. */
  async artifacts(transactionId: string): Promise<Result<Artifacts>> {
    return this.leer<Artifacts>(
      `/v1/transactions/${encodeURIComponent(transactionId)}/artifacts`,
      true,
    );
  }

  /**
   * Constancia pública de un acto de firma.
   *
   * No exige credenciales: la consulta quien recibió el documento. Un código
   * inexistente devuelve `exists: false` en lugar de un error.
   */
  async verify(codigo: string): Promise<Result<PublicVerification>> {
    return this.leer<PublicVerification>(`/v1/verify/${encodeURIComponent(codigo)}`, false);
  }

  /** Claves públicas con las que verify un acta, en formato JWKS. */
  async publicKeys(): Promise<Result<{ keys: readonly unknown[] }>> {
    return this.leer<{ keys: readonly unknown[] }>("/.well-known/fnc-keys.json", false);
  }

  // ------------------------------------------------------------- Interno --
  private async escribir<T>(
    ruta: string,
    cuerpo: unknown,
    idempotencyKey: string,
  ): Promise<Result<T>> {
    const serializado = JSON.stringify(cuerpo);
    const cabeceras = await this.cabecerasFirmadas("POST", ruta, serializado);
    cabeceras[HEADER_IDEMPOTENCY] = idempotencyKey;

    return this.enviar<T>(ruta, {
      method: "POST",
      headers: { ...cabeceras, "Content-Type": "application/json" },
      body: serializado,
    });
  }

  private async leer<T>(ruta: string, autenticada: boolean): Promise<Result<T>> {
    const cabeceras = autenticada
      ? await this.cabecerasFirmadas("GET", ruta, "")
      : {};
    return this.enviar<T>(ruta, { method: "GET", headers: cabeceras });
  }

  private async cabecerasFirmadas(
    metodo: string,
    ruta: string,
    cuerpo: string,
  ): Promise<Record<string, string>> {
    const timestamp = this.ahora().toISOString();
    return {
      [HEADER_CLIENT]: this.tenantId,
      [HEADER_TIMESTAMP]: timestamp,
      [HEADER_SIGNATURE]: await this.signer.sign(metodo, ruta, timestamp, cuerpo),
    };
  }

  private async enviar<T>(ruta: string, init: RequestInit): Promise<Result<T>> {
    let respuesta: Response;
    try {
      respuesta = await this.fetchImpl(`${this.baseUrl}${ruta}`, init);
    } catch (causa) {
      // Un fallo de red no es un rechazo del contrato: se distingue para que el
      // llamador pueda reintentar con la misma clave de idempotencia, que es
      // exactamente el caso para el que esa clave existe.
      throw new TransportError(`No se pudo contactar al servicio en ${ruta}`, causa);
    }

    const texto = await respuesta.text();
    let cuerpo: unknown;
    try {
      cuerpo = texto ? JSON.parse(texto) : {};
    } catch (causa) {
      throw new TransportError(
        `El servicio respondió algo que no es JSON (HTTP ${respuesta.status})`,
        causa,
      );
    }

    if (respuesta.ok) {
      return { ok: true, value: cuerpo as T };
    }

    const error = cuerpo as Partial<ErrorResponse>;
    if (typeof error?.motivo !== "string") {
      // Un error sin motivo no cumple el contrato; se normaliza para que el
      // llamador nunca tenga que comprobar si el campo existe.
      throw new TransportError(
        `El servicio respondió HTTP ${respuesta.status} sin un motivo del contrato`,
      );
    }

    return {
      ok: false,
      error: {
        motivo: error.motivo,
        mensaje: error.mensaje ?? "",
        ...(error.transaction_id !== undefined
          ? { transaction_id: error.transaction_id }
          : {}),
        ...(error.detalle !== undefined ? { detalle: error.detalle } : {}),
        reintentable: error.reintentable ?? false,
      },
    };
  }
}
