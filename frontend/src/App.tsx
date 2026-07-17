import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type CSSProperties,
  type DragEvent,
  type FormEvent
} from "react";

import {
  createPhoto,
  deletePhoto,
  getAdminPhotos,
  getAdminSession,
  getCsrf,
  getPublicPhotos,
  inspectPhoto,
  login,
  logout,
  reorderPhotos,
  updatePhoto
} from "./api";
import fallbackPhotos from "./data/photos.json";
import type { Category, ExifMetadata, Photo, PhotoDraft } from "./types";
import { CATEGORIES } from "./types";

const fallback = fallbackPhotos as Photo[];
const filterOptions = ["Все", ...CATEGORIES] as const;
type Filter = (typeof filterOptions)[number];

function useReveal<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (!("IntersectionObserver" in window)) {
      node.classList.add("is-visible");
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          node.classList.add("is-visible");
          observer.disconnect();
        }
      },
      { threshold: 0.08 }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return ref;
}

function Eyebrow({ children }: { children: string }) {
  return <p className="eyebrow"><span />{children}</p>;
}

function PublicSite() {
  const [photos, setPhotos] = useState<Photo[]>(fallback);
  const [activeFilter, setActiveFilter] = useState<Filter>("Все");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [apiAvailable, setApiAvailable] = useState(true);
  const galleryRef = useReveal<HTMLElement>();
  const contactRef = useReveal<HTMLElement>();

  useEffect(() => {
    let active = true;
    getPublicPhotos()
      .then((items) => {
        if (active && items.length) setPhotos(items);
      })
      .catch(() => {
        if (active) setApiAvailable(false);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  const visiblePhotos = useMemo(
    () => activeFilter === "Все" ? photos : photos.filter((photo) => photo.category === activeFilter),
    [activeFilter, photos]
  );
  const selectedIndex = selectedId === null ? -1 : visiblePhotos.findIndex((photo) => photo.id === selectedId);
  const selectedPhoto = selectedIndex >= 0 ? visiblePhotos[selectedIndex] : null;

  useEffect(() => {
    if (selectedId !== null && selectedIndex < 0) setSelectedId(null);
  }, [selectedId, selectedIndex]);

  const setFilter = (filter: Filter) => {
    setActiveFilter(filter);
    setSelectedId(null);
  };

  const heroImage = photos[2]?.image ?? fallback[2].image;

  return (
    <div className="site-shell">
      <header className="site-header">
        <a className="brand" href="#top" aria-label="Батор Дугаров — на главную">
          <span className="brand-mark">BD</span>
          <span className="brand-name">Батор Дугаров</span>
        </a>
        <nav className="main-nav" aria-label="Основная навигация">
          <a href="#works">Работы</a>
          <a href="#contact">Связь</a>
        </nav>
        <a className="admin-link" href="/admin">Войти <span>↗</span></a>
      </header>

      <main id="top">
        <section className="hero" aria-labelledby="hero-title">
          <div className="hero-image" style={{ backgroundImage: `url(${heroImage})` }} />
          <div className="hero-grain" />
          <div className="hero-orbit hero-orbit-one" />
          <div className="hero-orbit hero-orbit-two" />
          <div className="hero-content page-width">
            <div className="hero-kicker"><span className="status-dot" /> Архив визуальных наблюдений</div>
            <h1 id="hero-title">Батор<br /><em>Дугаров</em></h1>
            <div className="hero-bottomline">
              <p className="hero-role">Фотограф</p>
              <p className="hero-statement">Фотография — это способ<br />оставить тишину видимой.</p>
              <button className="hero-cta" onClick={() => document.getElementById("works")?.scrollIntoView({ behavior: "smooth" })}>
                Смотреть работы <span>↓</span>
              </button>
            </div>
          </div>
          <div className="hero-index" aria-hidden="true">01 <span /> 04</div>
        </section>

        <section className="gallery-section page-width reveal" id="works" ref={galleryRef} aria-labelledby="works-title">
          <div className="section-heading">
            <div>
              <Eyebrow>Избранное</Eyebrow>
              <h2 id="works-title">Работы<span>.</span></h2>
            </div>
            <p className="section-note">Кадры о свете, пространстве<br />и присутствии человека.</p>
          </div>

          <div className="filter-bar" role="tablist" aria-label="Фильтр работ">
            {filterOptions.map((filter) => (
              <button
                key={filter}
                className={activeFilter === filter ? "filter-button is-active" : "filter-button"}
                role="tab"
                aria-selected={activeFilter === filter}
                onClick={() => setFilter(filter)}
              >
                {filter}
              </button>
            ))}
            <span className="filter-count">{String(visiblePhotos.length).padStart(2, "0")} {photoCountLabel(visiblePhotos.length)}</span>
          </div>

          {loading && <div className="gallery-status">Собираем архив…</div>}
          {!apiAvailable && <div className="gallery-status is-muted">Показаны временные кадры. Подключите сервер, чтобы увидеть актуальный архив.</div>}
          <div className="gallery-grid" key={activeFilter} aria-live="polite">
            {visiblePhotos.map((photo, index) => (
              <button
                type="button"
                className={`art-card art-card-${index % 6}`}
                key={photo.id}
                style={{ "--accent": photo.accentColor } as CSSProperties}
                onClick={() => setSelectedId(photo.id)}
                aria-label={`Открыть фотографию «${photo.title}»`}
              >
                <img src={photo.image} alt={photo.title} loading={index < 3 ? "eager" : "lazy"} />
                <span className="card-wash" />
                <span className="card-glow" />
                <span className="card-meta">
                  <span className="card-category">{photo.category}</span>
                  <strong>{photo.title}</strong>
                  <span className="card-open">Открыть <i>↗</i></span>
                </span>
                <span className="card-number">{String(index + 1).padStart(2, "0")}</span>
              </button>
            ))}
          </div>
          {!visiblePhotos.length && <div className="empty-state">В этой категории пока нет кадров.</div>}
        </section>

        <section className="contact-section page-width reveal" id="contact" ref={contactRef} aria-labelledby="contact-title">
          <div className="contact-rule" />
          <div className="contact-layout">
            <div>
              <Eyebrow>Открытая линия</Eyebrow>
              <h2 id="contact-title">Давайте создадим<br /><em>что-то настоящее.</em></h2>
            </div>
            <div className="contact-side">
              <p>Для съёмок, проектов и тихих разговоров о визуальном языке.</p>
              <div className="contact-links">
                <a href="https://t.me/" target="_blank" rel="noreferrer">Telegram <span>↗</span></a>
                <a href="https://instagram.com/" target="_blank" rel="noreferrer">Instagram <span>↗</span></a>
                <a href="mailto:hello@example.com">Email <span>↗</span></a>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="site-footer page-width">
        <span>Батор Дугаров</span>
        <span>© {new Date().getFullYear()}</span>
        <a href="#top">Наверх ↑</a>
      </footer>

      {selectedPhoto && (
        <Lightbox
          photo={selectedPhoto}
          index={selectedIndex}
          total={visiblePhotos.length}
          onClose={() => setSelectedId(null)}
          onNavigate={(direction) => {
            const nextIndex = (selectedIndex + direction + visiblePhotos.length) % visiblePhotos.length;
            setSelectedId(visiblePhotos[nextIndex].id);
          }}
        />
      )}
    </div>
  );
}

function Lightbox({
  photo,
  index,
  total,
  onClose,
  onNavigate
}: {
  photo: Photo;
  index: number;
  total: number;
  onClose: () => void;
  onNavigate: (direction: number) => void;
}) {
  const closeRef = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key === "ArrowLeft") onNavigate(-1);
      if (event.key === "ArrowRight") onNavigate(1);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [onClose, onNavigate]);

  const technical = [
    ["Камера", photo.camera],
    ["Объектив", photo.lens],
    ["Дата", photo.capturedAt ? formatCapturedAt(photo.capturedAt) : null],
    ["ISO", photo.iso],
    ["Фокусное", photo.focalLength],
    ["Выдержка", photo.shutterSpeed],
    ["Диафрагма", photo.aperture],
    ["Размер", photo.width && photo.height ? `${photo.width} × ${photo.height}` : null]
  ].filter((item): item is [string, string] => Boolean(item[1]));

  return (
    <div className="lightbox" role="dialog" aria-modal="true" aria-labelledby="lightbox-title">
      <button className="lightbox-backdrop" aria-label="Закрыть просмотр" onClick={onClose} />
      <button ref={closeRef} className="lightbox-close" onClick={onClose} aria-label="Закрыть просмотр">Закрыть <span>×</span></button>
      <button className="lightbox-arrow lightbox-prev" onClick={() => onNavigate(-1)} aria-label="Предыдущая фотография">←</button>
      <button className="lightbox-arrow lightbox-next" onClick={() => onNavigate(1)} aria-label="Следующая фотография">→</button>
      <div className="lightbox-frame">
        <div className="lightbox-image-wrap" style={{ "--accent": photo.accentColor } as CSSProperties}>
          <span className="lightbox-image-glow" />
          <img src={photo.image} alt={photo.title} />
        </div>
        <div className="lightbox-info">
          <div className="lightbox-title-row">
            <div>
              <p className="card-category">{photo.category}</p>
              <h2 id="lightbox-title">{photo.title}</h2>
            </div>
            <span className="lightbox-counter">{String(index + 1).padStart(2, "0")} / {String(total).padStart(2, "0")}</span>
          </div>
          <p className="lightbox-description">{photo.description}</p>
          {technical.length > 0 && (
            <div className="technical-grid" aria-label="Технические параметры кадра">
              {technical.map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}
            </div>
          )}
        </div>
      </div>
      <p className="lightbox-hint">← → листать&nbsp;&nbsp;·&nbsp;&nbsp;Esc закрыть</p>
    </div>
  );
}

function formatCapturedAt(value: string) {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function photoCountLabel(count: number) {
  const lastTwo = count % 100;
  const last = count % 10;
  if (lastTwo >= 11 && lastTwo <= 14) return "кадров";
  if (last === 1) return "кадр";
  if (last >= 2 && last <= 4) return "кадра";
  return "кадров";
}

function AdminApp() {
  const [status, setStatus] = useState<"loading" | "login" | "ready">("loading");
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [loginError, setLoginError] = useState("");
  const [editorPhoto, setEditorPhoto] = useState<Photo | null | undefined>(undefined);
  const dragIndex = useRef<number | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        await getCsrf();
        const session = await getAdminSession();
        if (!session.authenticated) {
          setStatus("login");
          return;
        }
        setPhotos(await getAdminPhotos());
        setStatus("ready");
      } catch {
        setLoginError("Сервер временно недоступен. Проверьте запуск Flask.");
        setStatus("login");
      }
    })();
  }, []);

  const handleLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoginError("");
    const form = new FormData(event.currentTarget);
    try {
      await login(String(form.get("username") ?? ""), String(form.get("password") ?? ""));
      setPhotos(await getAdminPhotos());
      setStatus("ready");
    } catch (error) {
      setLoginError(error instanceof Error ? error.message : "Не удалось войти.");
    }
  };

  const handleLogout = async () => {
    try { await logout(); } finally { setStatus("login"); }
  };

  if (status === "loading") return <div className="admin-loading">Проверяем доступ…</div>;
  if (status === "login") return <AdminLogin error={loginError} onSubmit={handleLogin} />;

  const savePhoto = (photo: Photo) => {
    setPhotos((current) => {
      const exists = current.some((item) => item.id === photo.id);
      return exists ? current.map((item) => item.id === photo.id ? photo : item) : [...current, photo];
    });
    setEditorPhoto(undefined);
  };

  const removePhoto = async (photo: Photo) => {
    if (!window.confirm(`Удалить «${photo.title}»?`)) return;
    try {
      await deletePhoto(photo.id);
      setPhotos((current) => current.filter((item) => item.id !== photo.id));
    } catch (error) {
      setLoginError(error instanceof Error ? error.message : "Не удалось удалить фото.");
    }
  };

  const movePhoto = async (index: number, direction: number) => {
    const nextIndex = index + direction;
    if (nextIndex < 0 || nextIndex >= photos.length) return;
    const previous = photos;
    const next = [...photos];
    [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
    setPhotos(next);
    try {
      await reorderPhotos(next.map((photo) => photo.id));
    } catch (error) {
      setPhotos(previous);
      setLoginError(error instanceof Error ? error.message : "Не удалось сохранить порядок.");
    }
  };

  const onDrop = (event: DragEvent<HTMLLIElement>, targetIndex: number) => {
    event.preventDefault();
    const sourceIndex = dragIndex.current;
    dragIndex.current = null;
    if (sourceIndex === null || sourceIndex === targetIndex) return;
    const next = [...photos];
    const [moved] = next.splice(sourceIndex, 1);
    next.splice(targetIndex, 0, moved);
    setPhotos(next);
    void reorderPhotos(next.map((photo) => photo.id)).catch(() => setPhotos(photos));
  };

  return (
    <div className="admin-shell">
      <header className="admin-header">
        <a className="brand" href="/"><span className="brand-mark">BD</span><span className="brand-name">Батор Дугаров</span></a>
        <div className="admin-header-right"><span>Панель галереи</span><button onClick={() => void handleLogout()}>Выйти</button></div>
      </header>
      <main className="admin-main">
        <div className="admin-intro">
          <div><Eyebrow>Приватная зона</Eyebrow><h1>Архив<span>.</span></h1><p>Управляйте кадрами, описаниями и техническими данными.</p></div>
          <button className="admin-primary" onClick={() => setEditorPhoto(null)}>+ Добавить фото</button>
        </div>
        {loginError && <p className="admin-alert">{loginError}</p>}
        <div className="admin-stats"><div><span>Кадров в архиве</span><strong>{String(photos.length).padStart(2, "0")}</strong></div><div><span>Категорий</span><strong>{new Set(photos.map((photo) => photo.category)).size}</strong></div><div><span>Порядок</span><strong>ручной</strong></div></div>
        <div className="admin-list-heading"><span>Все фотографии</span><span>Перетаскивайте или используйте стрелки</span></div>
        <ol className="admin-photo-list">
          {photos.map((photo, index) => (
            <li key={photo.id} draggable onDragStart={() => { dragIndex.current = index; }} onDragOver={(event) => event.preventDefault()} onDrop={(event) => onDrop(event, index)}>
              <span className="drag-handle" aria-hidden="true">⠿</span>
              <img src={photo.image} alt="" />
              <div className="admin-photo-copy"><span>{photo.category}</span><strong>{photo.title}</strong><small>{photo.description}</small></div>
              <div className="admin-order"><button onClick={() => void movePhoto(index, -1)} disabled={index === 0} aria-label="Переместить выше">↑</button><span>{String(index + 1).padStart(2, "0")}</span><button onClick={() => void movePhoto(index, 1)} disabled={index === photos.length - 1} aria-label="Переместить ниже">↓</button></div>
              <div className="admin-row-actions"><button onClick={() => setEditorPhoto(photo)}>Изменить</button><button className="danger-button" onClick={() => void removePhoto(photo)}>Удалить</button></div>
            </li>
          ))}
        </ol>
      </main>
      <footer className="site-footer page-width"><span>Батор Дугаров</span><span>Админ-панель</span><a href="/">Вернуться на сайт ↗</a></footer>
      {editorPhoto !== undefined && <PhotoEditor photo={editorPhoto} onClose={() => setEditorPhoto(undefined)} onSaved={savePhoto} />}
    </div>
  );
}

function AdminLogin({ error, onSubmit }: { error: string; onSubmit: (event: FormEvent<HTMLFormElement>) => void }) {
  return (
    <div className="admin-login-page">
      <a className="brand login-brand" href="/"><span className="brand-mark">BD</span><span className="brand-name">Батор Дугаров</span></a>
      <div className="login-card"><Eyebrow>Приватная зона</Eyebrow><h1>Вход в архив<span>.</span></h1><p>Доступ только для владельца галереи.</p><form onSubmit={onSubmit}><label>Логин<input name="username" autoComplete="username" required /></label><label>Пароль<input name="password" type="password" autoComplete="current-password" required /></label>{error && <div className="form-error" role="alert">{error}</div>}<button className="admin-primary" type="submit">Войти <span>↗</span></button></form><a className="back-link" href="/">← Вернуться на сайт</a></div>
    </div>
  );
}

const emptyDraft = (): PhotoDraft => ({ title: "", category: "Портреты", description: "", accentColor: "#8095b8", camera: "", lens: "", capturedAt: "", iso: "", focalLength: "", shutterSpeed: "", aperture: "", width: "", height: "" });

function draftFromPhoto(photo: Photo | null): PhotoDraft {
  if (!photo) return emptyDraft();
  return { title: photo.title, category: photo.category, description: photo.description, accentColor: photo.accentColor, camera: photo.camera ?? "", lens: photo.lens ?? "", capturedAt: photo.capturedAt ?? "", iso: photo.iso ?? "", focalLength: photo.focalLength ?? "", shutterSpeed: photo.shutterSpeed ?? "", aperture: photo.aperture ?? "", width: photo.width ? String(photo.width) : "", height: photo.height ? String(photo.height) : "" };
}

function metadataToDraft(metadata: ExifMetadata): Partial<PhotoDraft> {
  const result: Partial<PhotoDraft> = {};
  (Object.keys(metadata) as (keyof ExifMetadata)[]).forEach((key) => {
    const value = metadata[key];
    if (value !== null && value !== undefined && value !== "") result[key] = String(value) as never;
  });
  return result;
}

function PhotoEditor({ photo, onClose, onSaved }: { photo: Photo | null; onClose: () => void; onSaved: (photo: Photo) => void }) {
  const [draft, setDraft] = useState<PhotoDraft>(() => draftFromPhoto(photo));
  const [preview, setPreview] = useState(photo?.image ?? "");
  const [inspecting, setInspecting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previous; };
  }, []);

  const onFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setError("");
    setInspecting(true);
    try {
      const result = await inspectPhoto(file);
      setPreview(result.previewUrl);
      setDraft((current) => ({ ...current, ...metadataToDraft(result.metadata), uploadToken: result.uploadToken }));
    } catch (inspectionError) {
      setError(inspectionError instanceof Error ? inspectionError.message : "Не удалось прочитать файл.");
    } finally {
      setInspecting(false);
    }
  };

  const setField = (field: keyof PhotoDraft, value: string) => setDraft((current) => ({ ...current, [field]: value }));
  const clearField = (field: keyof PhotoDraft) => setField(field, "");

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      if (!photo && !draft.uploadToken) throw new Error("Сначала выберите фотографию.");
      const saved = photo ? await updatePhoto(photo.id, draft) : await createPhoto(draft);
      onSaved(saved);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Не удалось сохранить изменения.");
    } finally {
      setSaving(false);
    }
  };

  const technicalFields: { key: keyof PhotoDraft; label: string }[] = [
    { key: "camera", label: "Камера" }, { key: "lens", label: "Объектив" }, { key: "capturedAt", label: "Дата съёмки" },
    { key: "iso", label: "ISO" }, { key: "focalLength", label: "Фокусное расстояние" }, { key: "shutterSpeed", label: "Выдержка" },
    { key: "aperture", label: "Диафрагма" }, { key: "width", label: "Ширина" }, { key: "height", label: "Высота" }
  ];

  return (
    <div className="editor-overlay" role="dialog" aria-modal="true" aria-labelledby="editor-title">
      <div className="editor-backdrop" onClick={onClose} />
      <section className="editor-panel">
        <header className="editor-header"><div><Eyebrow>{photo ? "Редактирование" : "Новый кадр"}</Eyebrow><h2 id="editor-title">{photo ? photo.title : "Добавить фотографию"}</h2></div><button className="editor-close" onClick={onClose} aria-label="Закрыть">×</button></header>
        <form className="editor-form" onSubmit={submit}>
          <div className="editor-preview"><div className="preview-frame">{preview ? <img src={preview} alt="Предпросмотр" /> : <span>Выберите<br />изображение</span>}</div><label className="file-button">{inspecting ? "Читаем EXIF…" : preview ? "Заменить файл" : "Выбрать файл"}<input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => void onFileChange(event)} disabled={inspecting} /></label><small>JPEG, PNG или WebP · до 20 МБ<br />GPS из исходного файла удаляется при сохранении.</small></div>
          <div className="editor-fields">
            <label>Название<input value={draft.title} onChange={(event) => setField("title", event.target.value)} maxLength={160} required /></label>
            <label>Категория<select value={draft.category} onChange={(event) => setField("category", event.target.value)}>{CATEGORIES.map((category) => <option key={category}>{category}</option>)}</select></label>
            <label>Описание<textarea value={draft.description} onChange={(event) => setField("description", event.target.value)} maxLength={1600} rows={4} /></label>
            <label className="color-field">Акцентный цвет<div><input type="color" value={draft.accentColor} onChange={(event) => setField("accentColor", event.target.value)} /><input value={draft.accentColor} onChange={(event) => setField("accentColor", event.target.value)} pattern="#[0-9a-fA-F]{6}" /></div></label>
            <div className="form-divider"><span>EXIF и параметры</span><small>Можно исправить или очистить каждое поле</small></div>
            <div className="exif-edit-grid">{technicalFields.map(({ key, label }) => <label key={key}>{label}<span className="clearable-input"><input value={draft[key] as string} onChange={(event) => setField(key, event.target.value)} /><button type="button" onClick={() => clearField(key)} aria-label={`Очистить поле ${label}`}>×</button></span></label>)}</div>
            {error && <div className="form-error" role="alert">{error}</div>}
            <div className="editor-actions"><button type="button" className="secondary-button" onClick={onClose}>Отмена</button><button type="submit" className="admin-primary" disabled={saving || inspecting}>{saving ? "Сохраняем…" : "Сохранить кадр"}</button></div>
          </div>
        </form>
      </section>
    </div>
  );
}

export default function App() {
  return window.location.pathname.startsWith("/admin") ? <AdminApp /> : <PublicSite />;
}
