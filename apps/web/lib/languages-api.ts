// Language selection client.
import { request } from "./http";

export interface Language {
  code: string;
  name: string;
  native_name: string;
}

export const languages = {
  list: () => request<Language[]>("/api/v1/languages"),
  active: () => request<Language>("/api/v1/me/language"),
  setActive: (code: string) =>
    request<Language>("/api/v1/me/language", { method: "PUT", body: JSON.stringify({ code }) }),
};
