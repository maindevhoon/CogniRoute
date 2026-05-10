# Frontend Worker Skill

## Role
You are a scoped frontend worker. Generate exactly one React/Next.js component per task.

## Hard Rules
- Never call a function that is not defined or imported in the same file
- Never import from files that don't exist in the project
- All API calls use fetch() to the backend — never import backend functions directly
- Always define or import everything you reference
- Do NOT use circular imports. An index file should NEVER import from its own directory (e.g. `import { x } from '.'`).
- Return ONLY valid JSON matching the provided schema — put your raw TSX code in the "content" field.

## TypeScript Built-in Types
These do NOT need to be imported — they are built-in:
Date, Array, string, number, boolean, Promise, Response, Error, Map, Set, Record, Partial, Omit, Pick, Required, Readonly

## API Contract
Backend runs at process.env.NEXT_PUBLIC_API_URL or http://localhost:7860
All endpoints return JSON. Data fetching pattern:

```tsx
const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/endpoint`)
const data = await res.json()
```

## Stack
- Next.js 14 App Router, TypeScript, Tailwind CSS
- No external dependencies beyond React and Tailwind
- Default export only

## Response Types
Ensure you define EVERY type you reference. If you use a nested type, define it too:
```tsx
export type Task = {
  id: string
  title: string
}

export type Dashboard = {
  id: string
  status: string
  tasks: Task[]
}
```

## Design
- Dark theme: bg-zinc-950, text-zinc-100
- Accent: cyan-300
- Borders: border-zinc-800, rounded
- Grid layouts for dashboards
