# Movigoo Landings MKT — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir un hub Next.js multi-landing desplegado en Vercel cuyos formularios crean Contacts en Freshsales asignados a Listas por campaña.

**Architecture:** Monorepo Next.js (App Router) basado en el template [ai-website-cloner-template](https://github.com/JCodesMore/ai-website-cloner-template). Cada landing es una ruta (`app/(landings)/<slug>/`). Un solo API route server-side (`/api/leads`) valida con Zod, aplica honeypot + rate limit, y llama a la API de Freshsales. Config central en `landings/config.ts` mapea cada slug a su Lista de Freshsales y schema de form.

**Tech Stack:** Next.js 16 (App Router, React 19, TS strict), Tailwind v4, shadcn/ui, Zod, Vitest, Node 24+, Vercel.

**Spec:** [docs/superpowers/specs/2026-04-21-movigoo-landings-mkt-design.md](../specs/2026-04-21-movigoo-landings-mkt-design.md)

---

## Pre-requisitos

- Node.js 24+ instalado (`node -v` para verificar)
- `gh` CLI autenticado con cuentas `segurosfly` **y** `felix171029`
- SSH config con alias `github.com-freshsale` ya funcionando (se usa en `FreshSale_Movigoo`)
- Credenciales de Freshsales del `.env` del ETL a mano: `FRESHSALE_DOMAIN`, `FRESHSALE_API_KEY`

## Estructura de archivos objetivo

```
/Users/felix/movigoo-landings-mkt/
├── app/
│   ├── (landings)/
│   │   └── lp-nbqk5exo/             # primera LP clonada (renombrable)
│   │       ├── page.tsx
│   │       ├── gracias/page.tsx
│   │       └── components/
│   ├── api/
│   │   └── leads/route.ts           # POST handler
│   └── page.tsx                     # landing root del template
├── landings/
│   └── config.ts                    # registry slug → {listId, schema, successUrl}
├── lib/
│   ├── freshsales.ts                # cliente HTTP para Freshsales API
│   ├── rate-limit.ts                # rate limiter in-memory por IP
│   └── validation.ts                # helpers de payload + honeypot
├── tests/
│   ├── freshsales.test.ts
│   ├── rate-limit.test.ts
│   ├── validation.test.ts
│   └── api-leads.test.ts
├── .env.local                       # gitignored
├── .env.example
├── .github/workflows/ci.yml
├── vitest.config.ts
├── package.json
└── README.md
```

**Responsabilidades:**
- `lib/freshsales.ts` — única capa que habla con la API externa; expone `upsertContact()` y `addContactToList()`
- `lib/validation.ts` — parsea payloads contra el schema de la landing, valida honeypot
- `lib/rate-limit.ts` — contador in-memory por IP con ventana deslizante
- `landings/config.ts` — fuente única de verdad de qué landings existen y a qué lista mapean
- `app/api/leads/route.ts` — orquesta: rate limit → honeypot → validación → freshsales

---

## Task 1: Setup del proyecto local y cuenta de GitHub

**Goal:** Carpeta `/Users/felix/movigoo-landings-mkt/` con el template clonado, git inicializado en local, cuenta `felix171029` activa en `gh`.

**Files:** crea toda la carpeta del proyecto desde el template.

- [ ] **Step 1: Verificar Node 24+**

```bash
node -v
```

Expected: `v24.x.x` o superior. Si no, instalar con `nvm install 24 && nvm use 24`.

- [ ] **Step 2: Cambiar cuenta activa de gh a felix171029**

```bash
gh auth switch -u felix171029
gh auth status
```

Expected: `Active account: true` bajo `felix171029`.

- [ ] **Step 3: Clonar el template al path final**

```bash
cd /Users/felix
git clone https://github.com/JCodesMore/ai-website-cloner-template.git movigoo-landings-mkt
cd movigoo-landings-mkt
```

- [ ] **Step 4: Desvincular del repo origen del template**

```bash
rm -rf .git
git init
git branch -M main
```

- [ ] **Step 5: Configurar git local (no global) con la identidad de felix171029**

```bash
git config user.name "felix171029"
git config user.email "<email-de-felix171029>"   # pedirle a Felix el email asociado si no está claro
```

Nota: usar el mismo email que está en `~/FreshSale_Movigoo/.git/config` si existe override local ahí. Verificar con:

```bash
git -C /Users/felix/FreshSale_Movigoo config user.email
```

- [ ] **Step 6: Instalar dependencias**

```bash
npm install
```

Expected: instala sin errores, se crea `node_modules/` y `package-lock.json`.

- [ ] **Step 7: Verificar build del template base**

```bash
npm run build
```

Expected: build termina OK (puede tardar 1–2 min la primera vez).

- [ ] **Step 8: Crear `.env.example` y `.env.local`**

`.env.example`:

```
# Freshsales CRM — reutiliza credenciales del ETL
FRESHSALE_DOMAIN=yourdomain.freshsales.io
FRESHSALE_API_KEY=your_api_key_here
```

`.env.local` (copiar valores reales del `.env` de `FreshSale_Movigoo`):

```bash
cp .env.example .env.local
# Editar .env.local con los valores reales
```

Verificar que `.env.local` esté en `.gitignore` (el template ya lo incluye por defecto de Next.js).

- [ ] **Step 9: Commit inicial**

```bash
git add -A
git commit -m "chore: bootstrap movigoo-landings-mkt from ai-website-cloner-template"
```

---

## Task 2: Crear repo en GitHub bajo felix171029 y primer push

**Goal:** Repo `felix171029/movigoo-landings-mkt` (privado) live en GitHub con `origin` configurado vía SSH alias.

- [ ] **Step 1: Confirmar cuenta activa de gh**

```bash
gh auth status | grep -A2 "Active account: true"
```

Expected: `felix171029` listado como activa.

- [ ] **Step 2: Crear repo privado en GitHub**

```bash
gh repo create felix171029/movigoo-landings-mkt \
  --private \
  --description "Hub multi-landing de Movigoo con integración a Freshsales CRM" \
  --source=. \
  --remote=origin \
  --push=false
```

Expected: `✓ Created repository felix171029/movigoo-landings-mkt on GitHub`.

- [ ] **Step 3: Reemplazar remote HTTPS por SSH alias**

`gh repo create` configura el remote vía HTTPS. Cambiar al alias SSH que ya usa `FreshSale_Movigoo`:

```bash
git remote set-url origin git@github.com-freshsale:felix171029/movigoo-landings-mkt.git
git remote -v
```

Expected: ambas líneas muestran `git@github.com-freshsale:felix171029/movigoo-landings-mkt.git`.

- [ ] **Step 4: Primer push**

```bash
git push -u origin main
```

- [ ] **Step 5: Verificar en GitHub**

```bash
gh repo view felix171029/movigoo-landings-mkt
```

Expected: owner es `felix171029`, privacidad `private`, último commit visible.

---

## Task 3: Instalar Vitest y configurar testing

**Goal:** Vitest listo, un test de sanity verde.

**Files:**
- Create: `vitest.config.ts`
- Create: `tests/sanity.test.ts`
- Modify: `package.json` (scripts)

- [ ] **Step 1: Instalar Vitest y dependencias**

```bash
npm install -D vitest @vitest/ui @types/node
```

- [ ] **Step 2: Crear `vitest.config.ts`**

```typescript
// vitest.config.ts
import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  test: {
    environment: "node",
    include: ["tests/**/*.test.ts"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./"),
    },
  },
});
```

- [ ] **Step 3: Añadir scripts a `package.json`**

En la sección `"scripts"` agregar:

```json
"test": "vitest run",
"test:watch": "vitest"
```

- [ ] **Step 4: Escribir test de sanity**

`tests/sanity.test.ts`:

```typescript
import { describe, it, expect } from "vitest";

describe("sanity", () => {
  it("runs vitest", () => {
    expect(1 + 1).toBe(2);
  });
});
```

- [ ] **Step 5: Ejecutar tests**

```bash
npm test
```

Expected: `1 passed`.

- [ ] **Step 6: Commit**

```bash
git add vitest.config.ts package.json package-lock.json tests/
git commit -m "test: setup Vitest with sanity test"
```

---

## Task 4: Clonar la primera LP con el skill ai-website-cloner

**Goal:** LP `https://nbqk5exo.fwfmsites.com/` reproducida como ruta `app/(landings)/lp-nbqk5exo/` y accesible en `localhost:3000/lp-nbqk5exo`.

> **Ejecución especial:** este task usa el skill `/clone-website` del template. Claude Code debe correr con `--chrome` para que el skill pueda hacer reconnaissance visual. El skill hace el trabajo de creación de la LP; nosotros lo invocamos y luego movemos los archivos al layout multi-landing.

- [ ] **Step 1: Arrancar Claude Code con Chrome habilitado**

Desde `/Users/felix/movigoo-landings-mkt/`:

```bash
claude --chrome
```

- [ ] **Step 2: Invocar el skill de clonado**

Dentro de Claude Code, ejecutar:

```
/clone-website https://nbqk5exo.fwfmsites.com/
```

El skill ejecuta su pipeline multi-fase (reconnaissance → foundation → specs → parallel build → assembly). Esto puede tardar varios minutos. El output queda en `app/page.tsx` y sus componentes.

- [ ] **Step 3: Validar visualmente la LP clonada**

En terminal separada:

```bash
npm run dev
```

Abrir `http://localhost:3000/` y comparar visualmente contra la LP original. El skill hace visual diff automático, pero verificar manualmente también.

- [ ] **Step 4: Mover la LP clonada al layout multi-landing**

Reorganizar para que la LP viva bajo `app/(landings)/lp-nbqk5exo/`:

```bash
mkdir -p "app/(landings)/lp-nbqk5exo"
git mv app/page.tsx "app/(landings)/lp-nbqk5exo/page.tsx"

# Si el clone creó carpetas de componentes en app/components o similar,
# moverlas también. Verificar estructura después del clone antes de mover.
# Los imports dentro de page.tsx pueden necesitar ajuste de paths.
```

Luego crear un `app/page.tsx` mínimo de índice:

```tsx
// app/page.tsx
export default function Home() {
  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold">Movigoo Landings</h1>
      <p className="mt-2 text-sm text-gray-600">
        Hub interno de landing pages de marketing.
      </p>
    </main>
  );
}
```

- [ ] **Step 5: Verificar rutas nuevas**

```bash
npm run dev
```

- `http://localhost:3000/` → muestra el índice mínimo
- `http://localhost:3000/lp-nbqk5exo` → muestra la LP clonada

Si hay imports rotos después del move, ajustarlos. Si los assets (imágenes) quedaron en `public/`, siguen funcionando — `public/` es global en Next.js.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: clone first LP into app/(landings)/lp-nbqk5exo"
```

---

## Task 5: Deploy inicial a Vercel

**Goal:** LP live en Vercel bajo el dominio que te asigne el servicio; deploy continuo activo.

> **No automatizable por completo:** Vercel se configura en su UI web. El plan lista los pasos exactos.

- [ ] **Step 1: Asegurar push a main**

```bash
git push origin main
```

- [ ] **Step 2: Importar repo en Vercel**

1. Ir a https://vercel.com/new
2. Importar `felix171029/movigoo-landings-mkt` (puede requerir autorizar GitHub App para la cuenta `felix171029`)
3. Framework: autodetecta Next.js
4. Build command: `npm run build` (default)
5. Output: `.next` (default)

- [ ] **Step 3: Configurar environment variables en Vercel**

En *Project Settings → Environment Variables*:

| Name | Value | Environments |
|---|---|---|
| `FRESHSALE_DOMAIN` | *(mismo valor que el ETL)* | Production, Preview |
| `FRESHSALE_API_KEY` | *(mismo valor que el ETL)* | Production, Preview |

Después de añadir, hacer un redeploy para que apliquen.

- [ ] **Step 4: Validar deploy**

Abrir la URL de Vercel (ej. `movigoo-landings-mkt-xxx.vercel.app`) y verificar:
- `/` → índice mínimo
- `/lp-nbqk5exo` → LP clonada

- [ ] **Step 5: Subdominio custom (opcional en este task, se puede diferir)**

En *Project Settings → Domains*:

1. Añadir el subdominio deseado (ej. `landings.movigoo.com`)
2. Vercel muestra el CNAME a configurar en tu DNS
3. Añadir ese CNAME en el DNS de `movigoo.com`
4. Esperar propagación (puede tardar minutos a horas)

> Si el nombre del subdominio aún no está decidido, saltar este step y completarlo cuando esté definido — no bloquea el resto del plan.

---

## Task 6: Crear el registry `landings/config.ts`

**Goal:** Registry central con la primera landing registrada y schema Zod mínimo.

**Files:**
- Create: `landings/config.ts`
- Install: `zod`

- [ ] **Step 1: Instalar Zod**

```bash
npm install zod
```

- [ ] **Step 2: Crear `landings/config.ts`**

```typescript
// landings/config.ts
import { z } from "zod";

export type LandingConfig = {
  slug: string;
  name: string;
  freshsalesListId: number | null;
  formSchema: z.ZodTypeAny;
  successUrl: string;
};

// Schema base mínimo — se extiende por landing según los campos reales del form.
// La primera LP usa este schema hasta definir los campos finales en Task 10.
const baseLeadSchema = z.object({
  nombre: z.string().min(2, "Nombre requerido"),
  email: z.string().email("Email inválido"),
  telefono: z.string().min(7, "Teléfono requerido"),
});

export const LANDINGS: Record<string, LandingConfig> = {
  "lp-nbqk5exo": {
    slug: "lp-nbqk5exo",
    name: "LP nbqk5exo (primera campaña)",
    freshsalesListId: null, // se setea en Task 11 cuando se cree la Lista en Freshsales
    formSchema: baseLeadSchema,
    successUrl: "/lp-nbqk5exo/gracias",
  },
};

export function getLanding(slug: string): LandingConfig | null {
  return LANDINGS[slug] ?? null;
}
```

- [ ] **Step 3: Commit**

```bash
git add landings/ package.json package-lock.json
git commit -m "feat: add landings registry with base schema"
```

---

## Task 7: TDD `lib/validation.ts` — honeypot y validación de payload

**Goal:** Funciones puras que (a) detecten honeypot lleno y (b) validen un payload contra el schema de una landing.

**Files:**
- Create: `lib/validation.ts`
- Test: `tests/validation.test.ts`

- [ ] **Step 1: Escribir los tests**

`tests/validation.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { z } from "zod";
import { isHoneypotFilled, validatePayload } from "@/lib/validation";

describe("isHoneypotFilled", () => {
  it("returns false when hp_field is missing", () => {
    expect(isHoneypotFilled({})).toBe(false);
  });

  it("returns false when hp_field is empty string", () => {
    expect(isHoneypotFilled({ hp_field: "" })).toBe(false);
  });

  it("returns true when hp_field has any value", () => {
    expect(isHoneypotFilled({ hp_field: "bot-filled-this" })).toBe(true);
  });
});

describe("validatePayload", () => {
  const schema = z.object({
    nombre: z.string().min(2),
    email: z.string().email(),
  });

  it("returns ok=true with parsed data on valid input", () => {
    const result = validatePayload(
      { nombre: "Felix", email: "f@example.com" },
      schema,
    );
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data).toEqual({ nombre: "Felix", email: "f@example.com" });
    }
  });

  it("returns ok=false with errors on invalid input", () => {
    const result = validatePayload({ nombre: "x", email: "no-email" }, schema);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors).toHaveProperty("nombre");
      expect(result.errors).toHaveProperty("email");
    }
  });

  it("strips unknown fields from output", () => {
    const result = validatePayload(
      { nombre: "Felix", email: "f@example.com", extra: "ignored" },
      schema,
    );
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data).not.toHaveProperty("extra");
    }
  });
});
```

- [ ] **Step 2: Correr tests — deben fallar**

```bash
npm test
```

Expected: `Cannot find module '@/lib/validation'` (o similar).

- [ ] **Step 3: Implementar `lib/validation.ts`**

```typescript
// lib/validation.ts
import { z } from "zod";

export function isHoneypotFilled(body: Record<string, unknown>): boolean {
  const value = body.hp_field;
  return typeof value === "string" && value.length > 0;
}

export type ValidationResult<T> =
  | { ok: true; data: T }
  | { ok: false; errors: Record<string, string> };

export function validatePayload<T>(
  input: unknown,
  schema: z.ZodType<T>,
): ValidationResult<T> {
  const result = schema.safeParse(input);
  if (result.success) {
    return { ok: true, data: result.data };
  }
  const errors: Record<string, string> = {};
  for (const issue of result.error.issues) {
    const key = issue.path.join(".") || "_";
    if (!errors[key]) errors[key] = issue.message;
  }
  return { ok: false, errors };
}
```

- [ ] **Step 4: Correr tests — deben pasar**

```bash
npm test
```

Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add lib/validation.ts tests/validation.test.ts
git commit -m "feat: add payload validation and honeypot check"
```

---

## Task 8: TDD `lib/rate-limit.ts`

**Goal:** Rate limiter in-memory por IP con ventana deslizante de 60s y cap de 10 requests.

**Files:**
- Create: `lib/rate-limit.ts`
- Test: `tests/rate-limit.test.ts`

- [ ] **Step 1: Escribir los tests**

`tests/rate-limit.test.ts`:

```typescript
import { describe, it, expect, beforeEach, vi } from "vitest";
import { createRateLimiter } from "@/lib/rate-limit";

describe("rate limiter", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-04-21T10:00:00Z"));
  });

  it("allows up to limit requests per window", () => {
    const limiter = createRateLimiter({ limit: 3, windowMs: 60_000 });
    expect(limiter.check("1.1.1.1").allowed).toBe(true);
    expect(limiter.check("1.1.1.1").allowed).toBe(true);
    expect(limiter.check("1.1.1.1").allowed).toBe(true);
  });

  it("blocks requests over the limit", () => {
    const limiter = createRateLimiter({ limit: 2, windowMs: 60_000 });
    limiter.check("1.1.1.1");
    limiter.check("1.1.1.1");
    expect(limiter.check("1.1.1.1").allowed).toBe(false);
  });

  it("tracks different IPs independently", () => {
    const limiter = createRateLimiter({ limit: 1, windowMs: 60_000 });
    expect(limiter.check("1.1.1.1").allowed).toBe(true);
    expect(limiter.check("2.2.2.2").allowed).toBe(true);
  });

  it("resets after window passes", () => {
    const limiter = createRateLimiter({ limit: 1, windowMs: 60_000 });
    expect(limiter.check("1.1.1.1").allowed).toBe(true);
    expect(limiter.check("1.1.1.1").allowed).toBe(false);
    vi.advanceTimersByTime(61_000);
    expect(limiter.check("1.1.1.1").allowed).toBe(true);
  });
});
```

- [ ] **Step 2: Correr tests — deben fallar**

```bash
npm test -- rate-limit
```

Expected: `Cannot find module '@/lib/rate-limit'`.

- [ ] **Step 3: Implementar `lib/rate-limit.ts`**

```typescript
// lib/rate-limit.ts
type Options = { limit: number; windowMs: number };
type Entry = { count: number; windowStart: number };

export function createRateLimiter({ limit, windowMs }: Options) {
  const buckets = new Map<string, Entry>();

  return {
    check(key: string): { allowed: boolean; remaining: number } {
      const now = Date.now();
      const existing = buckets.get(key);

      if (!existing || now - existing.windowStart >= windowMs) {
        buckets.set(key, { count: 1, windowStart: now });
        return { allowed: true, remaining: limit - 1 };
      }

      if (existing.count >= limit) {
        return { allowed: false, remaining: 0 };
      }

      existing.count += 1;
      return { allowed: true, remaining: limit - existing.count };
    },
  };
}

// Instancia global compartida (per-instance en serverless, best-effort)
export const leadsRateLimiter = createRateLimiter({
  limit: 10,
  windowMs: 60_000,
});
```

- [ ] **Step 4: Correr tests — deben pasar**

```bash
npm test -- rate-limit
```

Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add lib/rate-limit.ts tests/rate-limit.test.ts
git commit -m "feat: add in-memory rate limiter"
```

---

## Task 9: TDD `lib/freshsales.ts` — cliente de Freshsales

**Goal:** Dos funciones puras: `upsertContact()` (crea o actualiza por email) y `addContactToList()` (añade el ID a la Lista).

**Files:**
- Create: `lib/freshsales.ts`
- Test: `tests/freshsales.test.ts`

**Referencia API:** Freshsales CRM (Freshworks) docs:
- Crear Contact con upsert: `POST https://{domain}/api/contacts?unique_identifier=email`
- Añadir contact a lista: `POST https://{domain}/api/lists/{listId}/bulk_add`
- Auth: header `Authorization: Token token={api_key}`

- [ ] **Step 1: Escribir los tests**

`tests/freshsales.test.ts`:

```typescript
import { describe, it, expect, beforeEach, vi } from "vitest";
import { upsertContact, addContactToList } from "@/lib/freshsales";

describe("upsertContact", () => {
  beforeEach(() => {
    vi.stubEnv("FRESHSALE_DOMAIN", "movigoo.freshsales.io");
    vi.stubEnv("FRESHSALE_API_KEY", "test-key");
    vi.restoreAllMocks();
  });

  it("POSTs to /api/contacts with email as unique_identifier and returns id", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ contact: { id: 42, emails: [{ value: "x@y.com" }] } }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await upsertContact({
      first_name: "Felix",
      email: "x@y.com",
      mobile_number: "3000000",
    });

    expect(result.id).toBe(42);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("https://movigoo.freshsales.io/api/contacts");
    expect(url).toContain("unique_identifier[emails]=x%40y.com");
    expect(init.method).toBe("POST");
    expect(init.headers["Authorization"]).toBe("Token token=test-key");
    const body = JSON.parse(init.body);
    expect(body.contact).toEqual({
      first_name: "Felix",
      email: "x@y.com",
      mobile_number: "3000000",
    });
  });

  it("throws FreshsalesError on non-2xx response", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      text: async () => '{"errors":{"email":"invalid"}}',
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      upsertContact({ first_name: "X", email: "bad", mobile_number: "1" }),
    ).rejects.toThrow(/422/);
  });
});

describe("addContactToList", () => {
  beforeEach(() => {
    vi.stubEnv("FRESHSALE_DOMAIN", "movigoo.freshsales.io");
    vi.stubEnv("FRESHSALE_API_KEY", "test-key");
    vi.restoreAllMocks();
  });

  it("POSTs to /api/lists/{listId}/bulk_add with contact_ids", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ success: true }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await addContactToList(12345, 42);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("https://movigoo.freshsales.io/api/lists/12345/bulk_add");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({
      contact: { ids: [42] },
    });
  });

  it("throws on non-2xx", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      text: async () => "list not found",
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(addContactToList(99, 42)).rejects.toThrow(/404/);
  });
});
```

- [ ] **Step 2: Correr tests — deben fallar**

```bash
npm test -- freshsales
```

Expected: `Cannot find module '@/lib/freshsales'`.

- [ ] **Step 3: Implementar `lib/freshsales.ts`**

```typescript
// lib/freshsales.ts
export type ContactPayload = {
  first_name: string;
  last_name?: string;
  email: string;
  mobile_number?: string;
  [key: string]: unknown; // permite campos custom sin bloquear la compilación
};

export class FreshsalesError extends Error {
  constructor(public status: number, public responseBody: string) {
    super(`Freshsales API error ${status}: ${responseBody.slice(0, 200)}`);
    this.name = "FreshsalesError";
  }
}

function getConfig() {
  const domain = process.env.FRESHSALE_DOMAIN;
  const apiKey = process.env.FRESHSALE_API_KEY;
  if (!domain || !apiKey) {
    throw new Error("Missing FRESHSALE_DOMAIN or FRESHSALE_API_KEY env vars");
  }
  return { domain, apiKey };
}

function authHeaders(apiKey: string): Record<string, string> {
  return {
    Authorization: `Token token=${apiKey}`,
    "Content-Type": "application/json",
  };
}

export async function upsertContact(
  contact: ContactPayload,
): Promise<{ id: number }> {
  const { domain, apiKey } = getConfig();
  const url =
    `https://${domain}/api/contacts` +
    `?unique_identifier[emails]=${encodeURIComponent(contact.email)}`;

  const res = await fetch(url, {
    method: "POST",
    headers: authHeaders(apiKey),
    body: JSON.stringify({ contact }),
  });

  if (!res.ok) {
    throw new FreshsalesError(res.status, await res.text());
  }

  const data = (await res.json()) as { contact: { id: number } };
  return { id: data.contact.id };
}

export async function addContactToList(
  listId: number,
  contactId: number,
): Promise<void> {
  const { domain, apiKey } = getConfig();
  const url = `https://${domain}/api/lists/${listId}/bulk_add`;

  const res = await fetch(url, {
    method: "POST",
    headers: authHeaders(apiKey),
    body: JSON.stringify({ contact: { ids: [contactId] } }),
  });

  if (!res.ok) {
    throw new FreshsalesError(res.status, await res.text());
  }
}
```

- [ ] **Step 4: Correr tests — deben pasar**

```bash
npm test -- freshsales
```

Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add lib/freshsales.ts tests/freshsales.test.ts
git commit -m "feat: add Freshsales client (upsert contact, add to list)"
```

---

## Task 10: TDD `/api/leads` route — orquestador

**Goal:** POST handler que compone rate limit + honeypot + validación + freshsales.

**Files:**
- Create: `app/api/leads/route.ts`
- Test: `tests/api-leads.test.ts`

- [ ] **Step 1: Escribir los tests**

`tests/api-leads.test.ts`:

```typescript
import { describe, it, expect, beforeEach, vi } from "vitest";

// Mocks del módulo de Freshsales: los tests del route no deben llamar a la red.
vi.mock("@/lib/freshsales", () => ({
  upsertContact: vi.fn(),
  addContactToList: vi.fn(),
}));

import { POST } from "@/app/api/leads/route";
import { upsertContact, addContactToList } from "@/lib/freshsales";
import { LANDINGS } from "@/landings/config";

function makeRequest(body: Record<string, unknown>, ip = "9.9.9.9"): Request {
  return new Request("http://localhost/api/leads", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-forwarded-for": ip,
    },
    body: JSON.stringify(body),
  });
}

describe("POST /api/leads", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (upsertContact as any).mockResolvedValue({ id: 42 });
    (addContactToList as any).mockResolvedValue(undefined);
    // Set listId manualmente en el registry para el test
    LANDINGS["lp-nbqk5exo"].freshsalesListId = 12345;
  });

  it("returns 400 when landing_slug is missing", async () => {
    const res = await POST(makeRequest({ nombre: "Felix" }));
    expect(res.status).toBe(400);
  });

  it("returns 404 when landing_slug does not exist", async () => {
    const res = await POST(
      makeRequest({ landing_slug: "nope", nombre: "F", email: "a@b.c", telefono: "123456789" }),
    );
    expect(res.status).toBe(404);
  });

  it("returns 200 silently when honeypot is filled (bot)", async () => {
    const res = await POST(
      makeRequest({
        landing_slug: "lp-nbqk5exo",
        nombre: "Felix",
        email: "f@x.com",
        telefono: "3000000",
        hp_field: "bot",
      }),
    );
    expect(res.status).toBe(200);
    expect(upsertContact).not.toHaveBeenCalled();
    expect(addContactToList).not.toHaveBeenCalled();
  });

  it("returns 400 on invalid payload", async () => {
    const res = await POST(
      makeRequest({
        landing_slug: "lp-nbqk5exo",
        nombre: "x",
        email: "not-an-email",
        telefono: "1",
      }),
    );
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.errors).toBeDefined();
  });

  it("calls upsertContact + addContactToList on valid payload and returns redirect", async () => {
    const res = await POST(
      makeRequest(
        {
          landing_slug: "lp-nbqk5exo",
          nombre: "Felix",
          email: "felix@example.com",
          telefono: "3001234567",
        },
        "5.5.5.5",
      ),
    );
    expect(res.status).toBe(200);
    expect(upsertContact).toHaveBeenCalledOnce();
    expect(addContactToList).toHaveBeenCalledWith(12345, 42);
    const body = await res.json();
    expect(body.ok).toBe(true);
    expect(body.redirect).toBe("/lp-nbqk5exo/gracias");
  });

  it("returns 500 when Freshsales throws", async () => {
    (upsertContact as any).mockRejectedValueOnce(new Error("freshsales down"));
    const res = await POST(
      makeRequest(
        {
          landing_slug: "lp-nbqk5exo",
          nombre: "Felix",
          email: "felix@example.com",
          telefono: "3001234567",
        },
        "6.6.6.6",
      ),
    );
    expect(res.status).toBe(500);
  });
});
```

- [ ] **Step 2: Correr tests — deben fallar**

```bash
npm test -- api-leads
```

Expected: `Cannot find module '@/app/api/leads/route'`.

- [ ] **Step 3: Implementar `app/api/leads/route.ts`**

```typescript
// app/api/leads/route.ts
import { z } from "zod";
import { getLanding } from "@/landings/config";
import { isHoneypotFilled, validatePayload } from "@/lib/validation";
import { leadsRateLimiter } from "@/lib/rate-limit";
import { upsertContact, addContactToList, FreshsalesError } from "@/lib/freshsales";

function getClientIp(req: Request): string {
  const xff = req.headers.get("x-forwarded-for");
  if (xff) return xff.split(",")[0].trim();
  return "unknown";
}

const slugSchema = z.object({ landing_slug: z.string().min(1) });

export async function POST(req: Request): Promise<Response> {
  const ip = getClientIp(req);

  // Rate limit primero — barato y evita trabajo innecesario
  const rate = leadsRateLimiter.check(ip);
  if (!rate.allowed) {
    return Response.json({ error: "rate_limited" }, { status: 429 });
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return Response.json({ error: "invalid_json" }, { status: 400 });
  }

  if (typeof body !== "object" || body === null) {
    return Response.json({ error: "invalid_body" }, { status: 400 });
  }

  const slugParse = slugSchema.safeParse(body);
  if (!slugParse.success) {
    return Response.json({ error: "missing_landing_slug" }, { status: 400 });
  }

  const landing = getLanding(slugParse.data.landing_slug);
  if (!landing) {
    return Response.json({ error: "unknown_landing" }, { status: 404 });
  }

  // Honeypot: bots se ignoran silenciosamente con 200 OK
  if (isHoneypotFilled(body as Record<string, unknown>)) {
    return Response.json({ ok: true });
  }

  const validation = validatePayload(body, landing.formSchema);
  if (!validation.ok) {
    return Response.json(
      { ok: false, errors: validation.errors },
      { status: 400 },
    );
  }

  if (landing.freshsalesListId === null) {
    console.error(`Landing ${landing.slug} has no freshsalesListId configured`);
    return Response.json({ error: "landing_not_ready" }, { status: 500 });
  }

  try {
    const data = validation.data as Record<string, unknown>;
    const { id } = await upsertContact({
      first_name: String(data.nombre),
      email: String(data.email),
      mobile_number: String(data.telefono),
    });
    await addContactToList(landing.freshsalesListId, id);
  } catch (err) {
    console.error("Freshsales error:", err);
    const status = err instanceof FreshsalesError ? 502 : 500;
    return Response.json({ error: "crm_error" }, { status });
  }

  return Response.json({ ok: true, redirect: landing.successUrl });
}
```

- [ ] **Step 4: Correr tests — deben pasar**

```bash
npm test
```

Expected: todos los suites verdes (sanity + validation + rate-limit + freshsales + api-leads).

- [ ] **Step 5: Commit**

```bash
git add app/api/ tests/api-leads.test.ts
git commit -m "feat: implement /api/leads orchestrator route"
```

---

## Task 11: Conectar el form de la LP + thank-you page + honeypot

**Goal:** El form de `lp-nbqk5exo` envía a `/api/leads`, muestra errores inline, redirige al success. Incluye honeypot oculto.

**Files:**
- Create/Modify: `app/(landings)/lp-nbqk5exo/components/LeadForm.tsx`
- Create: `app/(landings)/lp-nbqk5exo/gracias/page.tsx`
- Modify: `app/(landings)/lp-nbqk5exo/page.tsx` (para incluir el LeadForm)

> **Nota:** los campos finales del form pueden diferir según lo que traiga la LP clonada. Este task usa `nombre`, `email`, `telefono` (los del `baseLeadSchema`). Si la LP requiere más campos, actualizar el `formSchema` en `landings/config.ts` y añadir los inputs correspondientes aquí.

- [ ] **Step 1: Crear el componente `LeadForm`**

`app/(landings)/lp-nbqk5exo/components/LeadForm.tsx`:

```tsx
"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";

export function LeadForm({ landingSlug }: { landingSlug: string }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setErrors({});
    setSubmitError(null);

    const form = new FormData(e.currentTarget);
    const payload = {
      landing_slug: landingSlug,
      nombre: String(form.get("nombre") ?? ""),
      email: String(form.get("email") ?? ""),
      telefono: String(form.get("telefono") ?? ""),
      hp_field: String(form.get("hp_field") ?? ""),
    };

    try {
      const res = await fetch("/api/leads", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();

      if (!res.ok) {
        if (data.errors) setErrors(data.errors);
        else setSubmitError("No se pudo enviar. Intenta de nuevo.");
        setLoading(false);
        return;
      }

      if (data.redirect) router.push(data.redirect);
      else router.push("/");
    } catch {
      setSubmitError("Error de red. Intenta de nuevo.");
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3 max-w-md">
      {/* Honeypot: invisible para humanos, bots suelen rellenar todos los inputs */}
      <input
        type="text"
        name="hp_field"
        tabIndex={-1}
        autoComplete="off"
        style={{ position: "absolute", left: "-9999px", opacity: 0, height: 0 }}
        aria-hidden="true"
      />

      <div>
        <input
          type="text"
          name="nombre"
          placeholder="Nombre"
          className="w-full border rounded px-3 py-2"
          required
        />
        {errors.nombre && <p className="text-sm text-red-600">{errors.nombre}</p>}
      </div>

      <div>
        <input
          type="email"
          name="email"
          placeholder="Correo"
          className="w-full border rounded px-3 py-2"
          required
        />
        {errors.email && <p className="text-sm text-red-600">{errors.email}</p>}
      </div>

      <div>
        <input
          type="tel"
          name="telefono"
          placeholder="Teléfono"
          className="w-full border rounded px-3 py-2"
          required
        />
        {errors.telefono && <p className="text-sm text-red-600">{errors.telefono}</p>}
      </div>

      <button
        type="submit"
        disabled={loading}
        className="bg-black text-white rounded px-4 py-2 disabled:opacity-50"
      >
        {loading ? "Enviando..." : "Enviar"}
      </button>

      {submitError && <p className="text-sm text-red-600">{submitError}</p>}
    </form>
  );
}
```

- [ ] **Step 2: Integrar el form en la página de la LP**

Editar `app/(landings)/lp-nbqk5exo/page.tsx` para importar y montar `<LeadForm landingSlug="lp-nbqk5exo" />` donde corresponda dentro del diseño clonado. La ubicación exacta depende del diseño; buscar la sección de form original y reemplazar por este componente.

- [ ] **Step 3: Crear la thank-you page**

`app/(landings)/lp-nbqk5exo/gracias/page.tsx`:

```tsx
export default function Gracias() {
  return (
    <main className="min-h-screen flex items-center justify-center p-8">
      <div className="text-center max-w-md">
        <h1 className="text-3xl font-bold mb-3">¡Gracias!</h1>
        <p className="text-gray-600">
          Recibimos tu información. Un asesor se pondrá en contacto contigo pronto.
        </p>
      </div>
    </main>
  );
}
```

- [ ] **Step 4: Validar en local**

```bash
npm run dev
```

Probar manualmente en `http://localhost:3000/lp-nbqk5exo`:
- Submit vacío → errores del navegador (required)
- Submit con email inválido → error inline del backend
- Submit válido → redirige a `/lp-nbqk5exo/gracias`

> En este punto Freshsales fallará con 500 porque `freshsalesListId` es `null`. Eso se resuelve en Task 12. Para probar solo el form+validación: setear `freshsalesListId: 999999` temporalmente en `config.ts` y con la API key de prod, el upsert del contact funcionará pero `addContactToList` dará 404 — la respuesta será 502 con `crm_error`. Suficiente para ver que el flujo del browser funciona.

- [ ] **Step 5: Commit**

```bash
git add app/
git commit -m "feat: add LeadForm with honeypot, inline errors, and thank-you page"
```

---

## Task 12: Crear la Lista en Freshsales + test end-to-end real

**Goal:** La primera campaña tiene su propia Lista en Freshsales; un submit real desde la LP crea un Contact y lo agrega.

> **No automatizable:** la creación de la Lista se hace en la UI de Freshsales.

- [ ] **Step 1: Crear la Lista en Freshsales**

1. Entrar a Freshsales → *Contacts → Lists → New List*
2. Nombre: `LP - lp-nbqk5exo` (o el nombre real de la campaña)
3. Tipo: Static List (o Dynamic si aplica; para LPs siempre Static)
4. Guardar

- [ ] **Step 2: Obtener el ID de la Lista**

Opción A — desde URL: abrir la lista, la URL muestra `/lists/<ID>`.
Opción B — vía API:

```bash
curl -s "https://$FRESHSALE_DOMAIN/api/lists" \
  -H "Authorization: Token token=$FRESHSALE_API_KEY" | jq '.lists[] | {id, name}'
```

- [ ] **Step 3: Actualizar `landings/config.ts` con el listId real**

Editar `landings/config.ts`:

```typescript
"lp-nbqk5exo": {
  // ...
  freshsalesListId: <ID_REAL>, // reemplazar null
  // ...
},
```

- [ ] **Step 4: Commit y deploy**

```bash
git add landings/config.ts
git commit -m "feat: wire lp-nbqk5exo to Freshsales list <ID>"
git push origin main
```

Vercel desplegará automáticamente.

- [ ] **Step 5: Test end-to-end en Preview/Production**

1. Esperar que Vercel termine el deploy
2. Abrir la URL de producción (o Preview)
3. Enviar un submit real con email de prueba propio
4. Verificar en Freshsales:
   - *Contacts* → el contacto aparece con los datos enviados
   - *Lists → LP - lp-nbqk5exo* → el contacto está en la lista
5. Enviar un segundo submit con el mismo email → verificar que **no se duplica** el contacto (upsert funcionando)

---

## Task 13: CI en GitHub Actions

**Goal:** Cada push a `main` y cada PR corre lint + typecheck + tests + build.

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Crear el workflow**

`.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: "24"
          cache: "npm"

      - name: Install deps
        run: npm ci

      - name: Lint
        run: npm run lint

      - name: Typecheck
        run: npm run typecheck

      - name: Tests
        run: npm test

      - name: Build
        run: npm run build
        env:
          FRESHSALE_DOMAIN: ${{ secrets.FRESHSALE_DOMAIN }}
          FRESHSALE_API_KEY: ${{ secrets.FRESHSALE_API_KEY }}
```

- [ ] **Step 2: Añadir secrets en GitHub**

```bash
gh secret set FRESHSALE_DOMAIN --body "<valor>"
gh secret set FRESHSALE_API_KEY --body "<valor>"
```

Alternativa: UI de GitHub → *Settings → Secrets and variables → Actions → New repository secret*.

- [ ] **Step 3: Commit y push**

```bash
git add .github/
git commit -m "ci: add GitHub Actions workflow (lint, typecheck, test, build)"
git push origin main
```

- [ ] **Step 4: Verificar que el workflow corre verde**

```bash
gh run list --limit 1
gh run watch
```

Expected: `✓ CI` con todas las steps en verde.

---

## Notas finales

**Qué queda después de este plan (ampliaciones futuras, fuera de alcance):**

- Añadir una segunda landing: correr `/clone-website` con otra URL, añadir entrada a `landings/config.ts`, crear otra Lista en Freshsales, configurar dominio si aplica
- Migrar rate limit a Vercel KV / Upstash si aparece tráfico abusivo
- Añadir Sentry para observabilidad de errores en producción
- Crear deals además de contacts para campañas específicas (agregar `createDeal` flag al `LandingConfig`)
- reCAPTCHA v3 si el honeypot no es suficiente
- Dominio propio por campaña (Vercel soporta mapping de dominio → ruta)

**Convención para añadir una nueva LP (resumen):**

1. `claude --chrome` desde la raíz del repo
2. `/clone-website <url>`
3. Mover el output a `app/(landings)/<slug>/`
4. Añadir entrada a `landings/config.ts` con `listId`, `schema`, `successUrl`
5. Añadir `<LeadForm landingSlug="<slug>" />` en el page.tsx clonado
6. Crear thank-you page en `app/(landings)/<slug>/gracias/page.tsx`
7. Crear Lista en Freshsales, poner el ID en config
8. Commit + push → Vercel despliega automáticamente
