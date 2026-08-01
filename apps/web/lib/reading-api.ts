// Reading resource client.
import { request } from "./http";

export interface TextListItem {
  id: string; title: string; author: string; source_type: string;
  level: number; summary: string; external_url: string;
}
export interface ReadingText {
  id: string; title: string; author: string; source_type: string; level: number;
  body: string; external_url: string; summary: string; status: string;
}
export interface Lookup {
  word: string; found: boolean; term?: string; translation?: string;
  part_of_speech?: string; item_id?: string;
}
export interface Annotation {
  id: string; start: number; end: number; quote: string; note: string;
}

export const reading = {
  library: (level?: number) =>
    request<TextListItem[]>(`/api/v1/reading${level ? `?level=${level}` : ""}`),
  get: (id: string) => request<ReadingText>(`/api/v1/reading/${id}`),
  lookup: (word: string) =>
    request<Lookup>(`/api/v1/reading/lookup?word=${encodeURIComponent(word)}`),
  annotations: (id: string) => request<Annotation[]>(`/api/v1/reading/${id}/annotations`),
  addAnnotation: (id: string, start: number, end: number, note: string) =>
    request<Annotation>(`/api/v1/reading/${id}/annotations`,
      { method: "POST", body: JSON.stringify({ start, end, note }) }),
  deleteAnnotation: (annotationId: string) =>
    request<{ id: string; deleted: boolean }>(`/api/v1/reading/annotations/${annotationId}`,
      { method: "DELETE" }),
};
