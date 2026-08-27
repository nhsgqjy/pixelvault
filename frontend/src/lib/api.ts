import { createApiClient } from '../../../packages/api-client/src';

const configuredOrigin = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? '';

export const api = createApiClient({
  baseUrl: `${configuredOrigin}/api`,
  credentials: 'include',
});
