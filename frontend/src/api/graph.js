import { api } from "./client.js";

export function getGraph(id, depth = 2) {
  return api.request(`/graph/${encodeURIComponent(id)}?depth=${depth}`);
}

export function traceMoney(from, to, max_depth = 4) {
  const q = new URLSearchParams({ from, to, max_depth });
  return api.request(`/graph/trace?${q.toString()}`);
}

export function health() {
  return api.request("/health");
}
