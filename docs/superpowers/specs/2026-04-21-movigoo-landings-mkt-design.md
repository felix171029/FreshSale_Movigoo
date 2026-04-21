# Movigoo Landings MKT — Design Spec

**Fecha:** 2026-04-21
**Estado:** Aprobado, pendiente de implementación
**Autor:** Felix (wilker@segurosfly.com) + brainstorming con Claude

## Contexto

Movigoo necesita un hub de landing pages (LPs) de marketing. Cada campaña genera leads vía un formulario que debe insertar contactos directamente en el CRM Freshsales, asignándolos a una Lista específica por campaña.

El proyecto es independiente del ETL `FreshSale_Movigoo` pero reutiliza las credenciales de la API de Freshsales (`FRESHSALE_DOMAIN`, `FRESHSALE_API_KEY`) ya en uso.

La primera LP a clonar es `https://nbqk5exo.fwfmsites.com/` usando el template [ai-website-cloner-template](https://github.com/JCodesMore/ai-website-cloner-template) (Next.js + TypeScript + Tailwind + shadcn/ui).

## Objetivo

Un repositorio único que sirva múltiples landings bajo un mismo subdominio, cada una conectada a su propia Lista en Freshsales, desplegado en Vercel con deploy continuo desde GitHub.

## Alcance

**Incluye:**
- Setup del proyecto Next.js basado en ai-website-cloner-template
- Estructura multi-landing por rutas
- Integración server-side con Freshsales API (crear Contact + añadir a Lista)
- Validación, honeypot anti-spam y rate limit básico
- Deploy en Vercel con subdominio único
- Tests unitarios del cliente Freshsales y de la validación
- Clonado de la primera LP (`nbqk5exo.fwfmsites.com`)

**No incluye:**
- Creación de Deals/Leads/Tasks en Freshsales (solo Contacts)
- Persistencia de leads en SQL Server (la LP habla solo con Freshsales; el ETL existente sincroniza Freshsales → SQL en su propio ciclo)
- reCAPTCHA o anti-spam avanzado (se deja como ampliación futura)
- CMS headless para editar contenido (cada LP se clona como código estático)
- Multi-dominio por campaña (todas bajo un subdominio; migrable después si aplica)

## Arquitectura

### Stack

- **Framework:** Next.js (App Router) + TypeScript
- **Styling:** Tailwind CSS + shadcn/ui (viene del template)
- **Validación:** Zod
- **Tests:** Vitest
- **Hosting:** Vercel
- **Repo:** `felix171029/movigoo-landings-mkt` (GitHub)
- **Path local:** `/Users/felix/movigoo-landings-mkt/`

### Estructura de carpetas

```
movigoo-landings-mkt/
├── app/
│   ├── (landings)/
│   │   └── <slug>/              # ej. promo-abril
│   │       ├── page.tsx         # LP clonada
│   │       ├── gracias/page.tsx # thank-you page (opcional)
│   │       └── components/
│   ├── api/
│   │   └── leads/
│   │       └── route.ts         # POST: recibe form, crea Contact en Freshsales
│   └── page.tsx                 # índice (opcional)
├── landings/
│   └── config.ts                # registry: slug → { listId, schema, successUrl }
├── lib/
│   ├── freshsales.ts            # cliente HTTP para Freshsales API
│   └── validation.ts            # helpers de validación + honeypot
├── components/ui/               # shadcn shared
├── tests/                       # Vitest
├── .env.local                   # credenciales (no commitear)
├── .env.example                 # plantilla (sí commitear)
└── ...
```

### Flujo de submit end-to-end

```
[Browser / LP]
   └─ POST /api/leads
        body: { landing_slug, nombre, email, telefono, ...,
                hp_field (honeypot) }

[Next.js API route: /api/leads]
   1. Valida honeypot (hp_field vacío = humano; con valor = bot → 200 silencioso)
   2. Rate limit básico por IP (in-memory por ahora)
   3. Busca config en landings.config.ts por landing_slug
   4. Valida payload con el schema Zod de esa landing
   5. Llama lib/freshsales.ts:
       a. POST /api/contacts con unique_identifier por email (idempotente: upsert)
       b. POST /api/lists/{listId}/bulk_add con el ID del contact
   6. Retorna { ok: true, redirect: successUrl } o { ok: false, error } en 4xx/5xx

[Browser]
   └─ Redirect a successUrl (thank-you page o URL externa)
```

### Config por landing

Archivo `landings/config.ts`:

```typescript
import { z } from "zod";

export const LANDINGS = {
  // NOTA: slug, listId y campos del form son ejemplos — se definen
  // con Felix en la fase 4 (después de clonar la LP).
  "promo-abril": {
    slug: "promo-abril",
    name: "Promo Abril 2026",
    freshsalesListId: 123456,
    formSchema: z.object({
      nombre: z.string().min(2),
      email: z.string().email(),
      telefono: z.string().min(7),
    }),
    successUrl: "/promo-abril/gracias",
  },
} as const;

export type LandingSlug = keyof typeof LANDINGS;
```

Añadir una campaña nueva requiere: (1) nueva entrada en este registry, (2) crear carpeta `app/(landings)/<slug>/`, (3) crear la Lista en Freshsales y poner su ID aquí.

### Variables de entorno

`.env.local` (no commitear):

```
FRESHSALE_DOMAIN=tudominio.freshsales.io
FRESHSALE_API_KEY=xxxxx
```

Las mismas credenciales que usa el ETL `FreshSale_Movigoo`. En Vercel se configuran en *Project Settings → Environment Variables* para Production y Preview. Nunca se exponen al cliente: el fetch a Freshsales ocurre en el API route (server-side).

`.env.example` documenta las variables requeridas sin valores reales.

### Seguridad y anti-abuso

- **Honeypot:** campo oculto en el form (invisible en CSS, sin label). Si viene con valor → bot → se descarta silenciosamente con 200 OK (no dar pistas al atacante).
- **Rate limit:** best-effort in-memory por IP en el API route (10 req/min/IP). En Vercel serverless esto es *per-instance*, no globalmente consistente — sirve como primera línea de defensa contra clicks repetidos, no contra un atacante distribuido. Si aparecen abusos reales, migrar a Vercel KV o Upstash Redis para rate limit global.
- **Validación Zod estricta:** el API route solo acepta los campos declarados en el schema de la landing; cualquier extra se rechaza.
- **Credenciales server-side:** nunca en `NEXT_PUBLIC_*`, solo en `process.env.FRESHSALE_*` accesibles desde el API route.

### Manejo de errores

- Falla de Freshsales (4xx/5xx) → API retorna 500 al cliente con mensaje genérico ("Intenta de nuevo"). Detalle del error va a consola de Vercel.
- Payload inválido → 400 con mensaje por campo.
- Landing slug inexistente → 404.
- Observabilidad: logs a `console.error` (visibles en Vercel). Sentry queda como mejora futura.

## Testing

Escalado al alcance real: no sobre-testear componentes visuales, sí cubrir la capa de datos.

| Área | Tipo | Qué cubre |
|---|---|---|
| `lib/freshsales.ts` | Unit (fetch mockeado) | Crear contact OK, upsert por email existente, añadir a lista, errores 4xx/5xx |
| `lib/validation.ts` | Unit | Un test por schema de landing (campos válidos pasan, inválidos son rechazados) |
| `/api/leads` | Integración (Freshsales mockeado) | Honeypot descarta bots, payload válido → 200, inválido → 400, landing inexistente → 404 |
| LPs (UI) | Manual | Smoke test en Preview de Vercel antes de Production |

Stack: **Vitest** (mejor integración con Next.js que Jest, más rápido).

## Fases de implementación

| # | Fase | Entregable |
|---|---|---|
| 1 | **Setup** — crear carpeta local, switch de cuenta gh a `felix171029`, clonar template, config de git local, crear repo en GitHub bajo `felix171029`, primer commit + push | Repo `felix171029/movigoo-landings-mkt` live, build local OK |
| 2 | **Clonar primera LP** — correr skill ai-website-cloner contra `https://nbqk5exo.fwfmsites.com/`, output a `app/(landings)/<slug>/` | LP servida en `localhost:3000/<slug>`, visualmente idéntica |
| 3 | **Deploy inicial a Vercel** — conectar repo, configurar env vars, apuntar subdominio (ej. `landings.movigoo.com` — nombre final TBD con Felix) vía CNAME | LP live en producción (sin integración aún) |
| 4 | **Definir form** — revisar LP clonada, decidir campos finales, actualizar `landings/config.ts` con schema Zod | Form funcional con validación client-side |
| 5 | **Integración Freshsales** — crear Lista en Freshsales, obtener ID, implementar `lib/freshsales.ts` y `/api/leads`, conectar submit | Submit end-to-end: form → Contact + añadido a Lista |
| 6 | **UX de cierre** — thank-you page, mensajes de error, honeypot, rate limit básico | LP lista para campaña real |
| 7 | **Tests** — cubrir lo descrito en sección Testing, CI en GitHub Actions | CI verde |

Cada fase es un bloque autocontenido: se puede pausar entre fases sin dejar nada roto.

### Notas críticas de setup (Fase 1)

Felix tiene múltiples cuentas de GitHub en su Mac. El repo **debe** crearse bajo `felix171029`:

1. `gh auth switch -u felix171029` antes de crear el repo
2. Configurar `git config user.email` local a la carpeta (no global) con el email asociado a felix171029
3. `gh repo create felix171029/movigoo-landings-mkt --private --source=. --remote=origin`
4. Verificar que `origin` use el SSH host alias: `git@github.com-freshsale:felix171029/movigoo-landings-mkt.git`
5. `gh repo view felix171029/movigoo-landings-mkt` debe mostrar a `felix171029` como owner

## Escalabilidad futura (fuera de alcance inmediato)

- Migrar a Turborepo cuando haya 10+ landings activas o ciclos de deploy independientes
- Soportar dominio propio por campaña (Vercel permite mapear dominio → ruta, sin migración)
- Opción B: crear también un Deal además del Contact (config por landing)
- Anti-spam avanzado con reCAPTCHA v3 o Cloudflare Turnstile
- Observabilidad con Sentry
- A/B testing por landing

## Decisiones clave (resumen)

| Decisión | Elegido | Alternativa descartada | Razón |
|---|---|---|---|
| Estructura | Monorepo Next.js con rutas | Turborepo multi-app | YAGNI — simplicidad primero |
| Hosting | Vercel serverless | Backend en Linux on-prem | Cero mantenimiento, LP no necesita SQL |
| Entidad en Freshsales | Contact | Lead (sin permisos) / Deal (ensucia pipeline) | Confirmado por Felix |
| Segmentación | Lista en Freshsales | Tag / campo custom | Confirmado por Felix |
| Multi-landing | Un subdominio, rutas | Un dominio por LP | Un CNAME único, escala sin tocar DNS |
| Anti-spam | Honeypot + rate limit | reCAPTCHA | Menos fricción, suficiente para empezar |

## Referencias

- Template: https://github.com/JCodesMore/ai-website-cloner-template
- Primera LP a clonar: https://nbqk5exo.fwfmsites.com/
- CRM Freshsales — documentación API: https://developers.freshworks.com/crm/api/
- Proyecto hermano: `FreshSale_Movigoo` (ETL Freshsales → SQL Server)
