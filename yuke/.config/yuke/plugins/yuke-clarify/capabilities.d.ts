/** The persistent clarification inbox supplies session-scoped attention state. */
declare module "yuke" {
  interface Capabilities {
    "yuke-clarify": {
      /** True while this session has a pending question or an uncertain answer delivery. No bytes transfer. */
      pending(sessionId: string): boolean;
    };
  }
  interface Events {
    /** The sessions that need clarification changed. Re-read the inbox capability. */
    "yuke-clarify:changed"(): void;
  }
}
export {};
