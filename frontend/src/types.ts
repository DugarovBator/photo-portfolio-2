export const CATEGORIES = ["Портреты", "Улица", "Природа", "Архитектура", "Ночная съёмка"] as const;
export type Category = (typeof CATEGORIES)[number];

export type Photo = {
  id: number;
  title: string;
  category: Category;
  description: string;
  image: string;
  accentColor: string;
  sortOrder?: number;
  camera?: string | null;
  lens?: string | null;
  capturedAt?: string | null;
  iso?: string | null;
  focalLength?: string | null;
  shutterSpeed?: string | null;
  aperture?: string | null;
  width?: number | null;
  height?: number | null;
};

export type ExifMetadata = Pick<Photo, "camera" | "lens" | "capturedAt" | "iso" | "focalLength" | "shutterSpeed" | "aperture" | "width" | "height">;

export type PhotoDraft = {
  title: string;
  category: Category;
  description: string;
  accentColor: string;
  uploadToken?: string;
  camera: string;
  lens: string;
  capturedAt: string;
  iso: string;
  focalLength: string;
  shutterSpeed: string;
  aperture: string;
  width: string;
  height: string;
};

