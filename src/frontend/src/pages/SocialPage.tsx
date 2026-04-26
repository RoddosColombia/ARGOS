import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api";
import type { SocialAccount, SocialPost } from "@/types/social";

const ACCOUNTS_REFRESH_MS = 30 * 60 * 1000; // 30 min
const POSTS_REFRESH_MS = 30 * 60 * 1000;

const NUM = new Intl.NumberFormat("es-CO");
const REL = new Intl.RelativeTimeFormat("es-CO", { numeric: "auto" });

function formatCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return NUM.format(n);
}

function formatRelative(iso: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  const diffSec = (date.getTime() - Date.now()) / 1000;
  const abs = Math.abs(diffSec);
  if (abs < 3600) return REL.format(Math.round(diffSec / 60), "minute");
  if (abs < 86400) return REL.format(Math.round(diffSec / 3600), "hour");
  return REL.format(Math.round(diffSec / 86400), "day");
}

function PlatformPill({ plataforma }: { plataforma: string }) {
  const styles: Record<string, string> = {
    tiktok: "bg-pink-100 text-pink-800",
    ig: "bg-purple-100 text-purple-800",
    youtube: "bg-red-100 text-red-800",
  };
  const labels: Record<string, string> = { tiktok: "TikTok", ig: "Instagram", youtube: "YouTube" };
  const cls = styles[plataforma] ?? "bg-ink-100 text-ink-500";
  const label = labels[plataforma] ?? plataforma;
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${cls}`}>
      {label}
    </span>
  );
}

function avatarInitial(username: string): string {
  return (username || "?").charAt(0).toUpperCase();
}

function truncate(s: string, n: number): string {
  if (!s) return "";
  return s.length > n ? `${s.slice(0, n)}…` : s;
}

export function SocialPage() {
  const accountsQ = useQuery<SocialAccount[]>({
    queryKey: ["social", "accounts"],
    queryFn: () => apiRequest<SocialAccount[]>("/api/v1/social/accounts?limit=20"),
    refetchInterval: ACCOUNTS_REFRESH_MS,
    refetchIntervalInBackground: false,
  });

  const postsQ = useQuery<SocialPost[]>({
    queryKey: ["social", "posts"],
    queryFn: () => apiRequest<SocialPost[]>("/api/v1/social/posts?limit=30"),
    refetchInterval: POSTS_REFRESH_MS,
    refetchIntervalInBackground: false,
  });

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <header>
        <h1 className="text-2xl font-semibold text-ink-900">Social Listening</h1>
        <p className="mt-1 text-sm text-ink-500">
          Cuentas IG/TikTok del nicho repuestos motos · posts virales (≥ 50K vistas) · refresh diario 04:00
        </p>
      </header>

      {/* Top Cuentas */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-500">
          Top Cuentas
        </h2>
        {accountsQ.isLoading && (
          <div className="rounded-lg border border-ink-200 bg-white p-8 text-center text-sm text-ink-500">
            Cargando cuentas…
          </div>
        )}
        {accountsQ.isError && (
          <div className="rounded-lg border border-ink-200 bg-white p-8 text-center text-sm text-red-700">
            Error: {(accountsQ.error as Error).message}
          </div>
        )}
        {accountsQ.data && accountsQ.data.length === 0 && (
          <div className="rounded-lg border border-ink-200 bg-white p-8 text-center text-sm text-ink-500">
            Sin cuentas todavía · próximo refresh corre a las 04:00 UTC
          </div>
        )}
        {accountsQ.data && accountsQ.data.length > 0 && (
          <div
            className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
            data-testid="social-accounts-grid"
          >
            {accountsQ.data.map((a) => (
              <article
                key={a.id}
                className="flex flex-col gap-2 rounded-lg border border-ink-200 bg-white p-4 shadow-sm hover:border-brand-500"
              >
                <div className="flex items-start gap-3">
                  <div className="grid size-10 shrink-0 place-items-center rounded-full bg-brand-100 text-base font-semibold text-brand-700">
                    {avatarInitial(a.username)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      {a.url_perfil ? (
                        <a
                          href={a.url_perfil}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="truncate text-sm font-semibold text-ink-900 hover:underline"
                        >
                          @{a.username}
                        </a>
                      ) : (
                        <span className="truncate text-sm font-semibold text-ink-900">
                          @{a.username}
                        </span>
                      )}
                      <PlatformPill plataforma={a.plataforma} />
                    </div>
                    {a.descripcion && (
                      <p className="mt-1 text-xs text-ink-500">{truncate(a.descripcion, 100)}</p>
                    )}
                  </div>
                </div>
                <div className="mt-auto flex items-center justify-between gap-2 border-t border-ink-100 pt-2 text-xs">
                  <div>
                    <div className="font-semibold text-ink-900">{formatCount(a.seguidores)}</div>
                    <div className="text-ink-500">seguidores</div>
                  </div>
                  <div className="text-right">
                    <div className="font-semibold text-emerald-700">
                      {a.engagement_rate.toFixed(1)}%
                    </div>
                    <div className="text-ink-500">engagement</div>
                  </div>
                  <div className="text-right">
                    <div className="font-semibold text-ink-900">{a.relevancia_score.toFixed(0)}</div>
                    <div className="text-ink-500">relevancia</div>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      {/* Posts Virales */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-500">
          Posts Virales
        </h2>
        <div className="overflow-hidden rounded-lg border border-ink-200 bg-white shadow-sm">
          {postsQ.isLoading && (
            <div className="p-8 text-center text-sm text-ink-500">Cargando posts…</div>
          )}
          {postsQ.isError && (
            <div className="p-8 text-center text-sm text-red-700">
              Error: {(postsQ.error as Error).message}
            </div>
          )}
          {postsQ.data && postsQ.data.length === 0 && (
            <div className="p-8 text-center text-sm text-ink-500">
              Sin posts virales detectados todavía
            </div>
          )}
          {postsQ.data && postsQ.data.length > 0 && (
            <ul data-testid="social-posts-list" className="divide-y divide-ink-100">
              {postsQ.data.map((p) => (
                <li key={p.id} className="flex items-start gap-3 px-4 py-3">
                  <div className="grid size-12 shrink-0 place-items-center rounded-md bg-ink-100 text-xs font-medium text-ink-500">
                    📹
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <PlatformPill plataforma={p.plataforma} />
                      {p.url_post ? (
                        <a
                          href={p.url_post}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="truncate text-sm font-medium text-ink-900 hover:underline"
                        >
                          @{p.username}
                        </a>
                      ) : (
                        <span className="truncate text-sm font-medium text-ink-900">
                          @{p.username}
                        </span>
                      )}
                      <span className="text-xs text-ink-500">
                        · {formatRelative(p.fecha_publicacion)}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-ink-700">{truncate(p.descripcion, 200)}</p>
                    {p.hashtags.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {p.hashtags.slice(0, 6).map((tag) => (
                          <span
                            key={tag}
                            className="inline-flex items-center rounded-md bg-ink-100 px-1.5 py-0.5 text-xs text-ink-700"
                          >
                            #{tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex shrink-0 gap-4 text-right text-xs tabular-nums">
                    <div>
                      <div className="font-semibold text-ink-900">{formatCount(p.vistas)}</div>
                      <div className="text-ink-500">vistas</div>
                    </div>
                    <div>
                      <div className="font-semibold text-ink-900">{formatCount(p.likes)}</div>
                      <div className="text-ink-500">likes</div>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}
