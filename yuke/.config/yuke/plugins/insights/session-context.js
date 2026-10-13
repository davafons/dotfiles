//! Shared current-context reads, without quota or historical database work.
import { client } from "yuke";

/** Read current session context and model catalog for an inspection view. No session yields a null item. Engine failures throw; the caller owns the result. @param {string | null} sessionId */
export async function readSessionContext(sessionId) {
  const item = sessionId ? await client.sessionContextInfo(sessionId) : null;
  const catalog = await client.catalogList(null);
  return { item, catalog };
}
