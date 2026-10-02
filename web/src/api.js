const origin = `${import.meta.env.BASE_URL}api`;
export async function request(path, body) {
  const response = await fetch(`${origin}${path}`, {
    credentials: 'same-origin',
    ...(body !== undefined
      ? {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        }
      : {}),
  });
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error('The workspace could not be reached. Please try again.');
  }
  if (!response.ok)
    throw new Error(
      typeof payload.detail === 'string'
        ? payload.detail
        : payload.error || 'The request could not be completed. Please try again.',
    );
  return payload;
}
export const exportUrl = `${origin}/export`;
