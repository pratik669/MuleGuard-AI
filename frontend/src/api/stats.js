import { api } from "./client.js";
export function getStats() {
  return api.request("/stats");
}
