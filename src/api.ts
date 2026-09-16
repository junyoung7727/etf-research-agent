export async function getJson<T>(
  path: string,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(path, {
    signal,
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(
      typeof body.detail === 'string'
        ? body.detail
        : body.error?.message ||
            `데이터를 불러오지 못했어요 (${response.status}).`,
    )
  }
  return response.json() as Promise<T>
}
