/**
 * SDK de referencia del contrato público de FirmasNoCualificadas.
 *
 * Además del cliente, exporta `runFncContractTests`: la suite que cualquier
 * adaptador de tenant debe pasar. Un adaptador propio que la ejecute contra sí
 * mismo prueba que cumple el contrato, en vez de afirmarlo.
 */
export { FncClient, TransportError } from "./client";
export type { RequestSigner, ClientOptions } from "./client";
export { buildSampleRequest, runFncContractTests } from "./contract";
export type { ContractEnvironment } from "./contract";
export type * from "./types";
