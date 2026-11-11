// Public source selection only; credentials and target stay in the Node proxy.
export const isMockMode = import.meta.env.VITE_TRACE_API_MODE !== 'live'
export const sourceLabel = isMockMode ? 'SYNTHETIC' : 'LIVE API'
export const apiLabel = isMockMode ? 'mock API' : 'API'
