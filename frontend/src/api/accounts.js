import { api } from "./client.js";

export function getAccounts({ sort = "risk", order = "desc", risk_level, q: search, limit = 50, offset = 0 } = {}) {
  const q = new URLSearchParams({ sort, order, limit, offset });
  if (risk_level) q.set("risk_level", risk_level);
  if (search) q.set("q", search);
  return api.request(`/accounts?${q.toString()}`);
}

export function getAccount(id) {
  return api.request(`/accounts/${encodeURIComponent(id)}`);
}

export function getTransactions(id, { limit = 20, offset = 0, order = "desc" } = {}) {
  const q = new URLSearchParams({ limit, offset, order });
  return api.request(`/accounts/${encodeURIComponent(id)}/transactions?${q}`);
}

export function getConnected(id) {
  return api.request(`/accounts/${encodeURIComponent(id)}/connected`);
}
