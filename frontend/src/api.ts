import type { ExifMetadata, Photo, PhotoDraft } from "./types";

let csrfToken = "";

type ApiError = Error & { status?: number };

async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  const method = (options.method ?? "GET").toUpperCase();
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method) && csrfToken) {
    headers.set("X-CSRF-Token", csrfToken);
  }

  const response = await fetch(url, { ...options, headers, credentials: "include" });
  const contentType = response.headers.get("content-type") ?? "";
  const body = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    const error = new Error(body?.error || "Не удалось выполнить запрос.") as ApiError;
    error.status = response.status;
    throw error;
  }
  return body as T;
}

export async function getCsrf(): Promise<string> {
  const response = await request<{ csrfToken: string }>("/api/csrf");
  csrfToken = response.csrfToken;
  return csrfToken;
}

export async function getPublicPhotos(): Promise<Photo[]> {
  const response = await request<{ photos: Photo[] }>("/api/photos");
  return response.photos;
}

export async function getAdminSession(): Promise<{ authenticated: boolean; username?: string | null }> {
  return request("/api/admin/session");
}

export async function login(username: string, password: string): Promise<void> {
  if (!csrfToken) await getCsrf();
  const response = await request<{ csrfToken: string }>("/api/admin/login", {
    method: "POST",
    body: JSON.stringify({ username, password })
  });
  csrfToken = response.csrfToken;
}

export async function logout(): Promise<void> {
  await request("/api/admin/logout", { method: "POST" });
  csrfToken = "";
}

export async function getAdminPhotos(): Promise<Photo[]> {
  const response = await request<{ photos: Photo[] }>("/api/admin/photos");
  return response.photos;
}

export async function inspectPhoto(file: File): Promise<{ uploadToken: string; previewUrl: string; metadata: ExifMetadata }> {
  const form = new FormData();
  form.append("image", file);
  return request("/api/admin/photos/inspect", { method: "POST", body: form });
}

export async function createPhoto(draft: PhotoDraft): Promise<Photo> {
  const response = await request<{ photo: Photo }>("/api/admin/photos", {
    method: "POST",
    body: JSON.stringify(draft)
  });
  return response.photo;
}

export async function updatePhoto(id: number, draft: PhotoDraft): Promise<Photo> {
  const response = await request<{ photo: Photo }>(`/api/admin/photos/${id}`, {
    method: "PUT",
    body: JSON.stringify(draft)
  });
  return response.photo;
}

export async function deletePhoto(id: number): Promise<void> {
  await request(`/api/admin/photos/${id}`, { method: "DELETE" });
}

export async function reorderPhotos(ids: number[]): Promise<void> {
  await request("/api/admin/photos/reorder", {
    method: "PUT",
    body: JSON.stringify({ ids })
  });
}

