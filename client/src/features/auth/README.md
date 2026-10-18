# auth

Sign-in. Only users (admins and managers) can sign in; anyone else gets `not_onboarded`. The login page is one "Continue with Google" button. In development it opens a list of accounts from the server (the server's `DEV_AUTH` stub, which names the caller by the `X-Dev-User-Email` header); a production build goes to Google (the contract as in Mdm Duro, built last). There is no email/password sign-in.

## Endpoints

| Method and path | Where it is called | What it does |
|---|---|---|
| `GET /dev/accounts` | `getDevAccounts`, `useDevAccounts` | Development only: the accounts the login page lists (admins and managers, plus a couple of plain members shown as refused). A 404 unless the server runs with `DEV_AUTH` |
| `GET /me` | `devSignIn`, `getMe`, `src/hooks/useCurrentUser.ts` | The signed-in person. `getMe` also reads `GET /teams/{id}/members` and `GET /board` to build the assignable people and the "needs review" count |
| `GET /auth/google/exchange?code=` | `exchangeGoogleCode` | Production, not built on the server yet: trade the callback code for a session; errors come back as `/login?error=<code>` |

## Folder map

```
auth/
├── LoginPage.tsx
├── hooks/                 useDevSignIn, useGoogleExchange, useSignOut, useDevAccounts
└── index.ts
```
